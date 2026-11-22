"""Data-quality checks for the RPI trade recorder's output. No analysis of the retail flag.

Reads the files one or more recorder runs wrote (``rpi_trades_<run>.csv.gz`` and
``rpi_run_<run>.json``) and reports, per symbol: row counts, missing trade ids, rows that
disagree between overlapping runs, timestamps that go backwards in id order, invalid values,
and whether each run's summary agrees with its data file.

The pre-registration in ``research/rpi/PREREGISTRATION.md`` forbids looking at how the
``isRPITrade`` flag relates to anything before the plan is locked. This module therefore only
checks that the flag column holds 0 or 1 and, over the whole input, takes both values. It
never counts flagged rows by symbol, size, time or any other attribute.

    python -m microstructure.rpi.quality DIR [DIR ...] [--json report.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import polars as pl

COLUMNS = ("symbol", "id", "time", "price", "qty", "quoteQty", "isBuyerMaker", "isRPITrade")
_SCHEMA = {"symbol": pl.String, "id": pl.Int64, "time": pl.Int64, "price": pl.String,
           "qty": pl.String, "quoteQty": pl.String, "isBuyerMaker": pl.Int8,
           "isRPITrade": pl.Int8}
_VALUE_COLUMNS = [c for c in COLUMNS if c not in ("symbol", "id")]
MAX_GAPS_LISTED = 50


def run_id_of(path: Path) -> str:
    """``rpi_trades_20261122T231400Z.csv.gz`` -> ``20261122T231400Z``."""
    return path.name.split("_")[-1].split(".")[0]


def load_runs(paths: list[Path]) -> pl.DataFrame:
    """Read recorder CSVs as served (prices and quantities stay strings) with a ``run`` column."""
    frames = []
    for p in sorted(paths):
        df = pl.read_csv(p, schema_overrides=_SCHEMA)
        if tuple(df.columns) != COLUMNS:
            raise ValueError(f"{p.name}: columns {df.columns} are not {list(COLUMNS)}")
        frames.append(df.with_columns(pl.lit(run_id_of(p)).alias("run")))
    if not frames:
        raise ValueError("no rpi_trades_*.csv.gz files found")
    return pl.concat(frames)


def find_gaps(ids: list[int], times: list[int]) -> list[dict]:
    """Holes in a sorted, de-duplicated trade-id sequence, with the times on either side."""
    return [{"after_id": a, "before_id": b, "missing": b - a - 1,
             "after_time": ta, "before_time": tb}
            for a, b, ta, tb in zip(ids, ids[1:], times, times[1:], strict=False) if b > a + 1]


def check_symbol(df: pl.DataFrame) -> dict:
    """Quality report for one symbol's rows (possibly from several overlapping runs)."""
    n_rows = df.height
    # the same trade recorded by two runs must be identical in every field
    per_id = df.group_by("id").agg(pl.struct(_VALUE_COLUMNS).n_unique().alias("versions"),
                                   pl.len().alias("copies"))
    conflicting = per_id.filter(pl.col("versions") > 1).height
    within_run_dupes = n_rows - df.unique(["run", "id"]).height
    u = df.unique("id", keep="first").sort("id")
    ids, times = u["id"].to_list(), u["time"].to_list()
    gaps = find_gaps(ids, times)
    price, qty, quote = (u[c].cast(pl.Float64, strict=False) for c in ("price", "qty", "quoteQty"))
    unparsable = int(price.is_null().sum() + qty.is_null().sum() + quote.is_null().sum())
    notional = price * qty
    ok = (notional > 0).fill_null(False)
    rel = ((quote - notional).abs() / notional).filter(ok).drop_nulls()
    return {
        "rows": n_rows,
        "unique_trades": u.height,
        "first_id": ids[0], "last_id": ids[-1],
        "first_time": times[0], "last_time": times[-1],
        "missing_ids": sum(g["missing"] for g in gaps),
        "n_gaps": len(gaps),
        "gaps": gaps[:MAX_GAPS_LISTED],
        "ids_in_two_or_more_runs": per_id.filter(pl.col("copies") > 1).height,
        "conflicting_ids": conflicting,
        "duplicate_rows_within_a_run": within_run_dupes,
        "time_goes_backwards": int((u["time"].diff().drop_nulls() < 0).sum()),
        "unparsable_numbers": unparsable,
        "non_positive_price_or_qty": int(((price <= 0) | (qty <= 0)).fill_null(False).sum()),
        "flags_not_0_or_1": int((~u["isBuyerMaker"].is_in([0, 1])).sum()
                                + (~u["isRPITrade"].is_in([0, 1])).sum()),
        "quote_qty_max_rel_diff": float(rel.max()) if rel.len() else None,
        "quote_qty_share_inexact": float((rel > 1e-9).mean()) if rel.len() else None,
    }


def check_summaries(trades: pl.DataFrame, summaries: list[dict]) -> list[dict]:
    """Does each run's JSON summary agree with the rows in its data file?"""
    counts = {(r, s): n for r, s, n in
              trades.group_by("run", "symbol").len().select("run", "symbol", "len").iter_rows()}
    out = []
    for s in sorted(summaries, key=lambda x: x["run_id"]):
        sym = s["symbols"]
        mismatch = sorted(k for k, v in sym.items() if counts.get((s["run_id"], k), 0)
                          != v["trades"])
        out.append({
            "run_id": s["run_id"], "started": s["started"], "ended": s["ended"],
            "planned_end": s["planned_end"],
            "ended_early": s["ended"] < s["planned_end"],
            "rate_limit_responses": s["http_429_or_418"],
            "request_errors": sum(v["errors"] for v in sym.values()),
            "gaps_logged_by_recorder": sum(len(v["gaps"]) for v in sym.values()),
            "trades_missed_per_recorder": sum(g["missing"] for v in sym.values()
                                              for g in v["gaps"]),
            "symbols_not_rpi_enabled": sorted(k for k, v in sym.items() if not v["rpi_enabled"]),
            "symbols_without_trades": sorted(k for k, v in sym.items() if v["trades"] == 0),
            "row_count_mismatch": mismatch,
        })
    return out


def quality_report(trades: pl.DataFrame, summaries: list[dict]) -> dict:
    symbols = {s: check_symbol(df) for (s,), df in
               sorted(trades.partition_by("symbol", as_dict=True).items())}
    flag_values = sorted(trades["isRPITrade"].unique().to_list())
    problems = []
    for s, r in symbols.items():
        for key in ("missing_ids", "conflicting_ids", "duplicate_rows_within_a_run",
                    "time_goes_backwards", "unparsable_numbers", "non_positive_price_or_qty",
                    "flags_not_0_or_1"):
            if r[key]:
                problems.append(f"{s}: {key} = {r[key]}")
    runs = check_summaries(trades, summaries)
    for r in runs:
        for key in ("row_count_mismatch", "symbols_not_rpi_enabled", "symbols_without_trades"):
            if r[key]:
                problems.append(f"run {r['run_id']}: {key} = {r[key]}")
    if flag_values != [0, 1]:
        problems.append(f"isRPITrade takes values {flag_values} over the whole input, not [0, 1]")
    return {"runs": runs, "symbols": symbols,
            "rpi_flag_takes_both_values": flag_values == [0, 1], "problems": problems}


def report_from_dirs(dirs: list[Path]) -> dict:
    csvs = [p for d in dirs for p in d.rglob("rpi_trades_*.csv.gz")]
    summaries = [json.loads(p.read_text()) for d in dirs for p in d.rglob("rpi_run_*.json")]
    return quality_report(load_runs(csvs), summaries)


def format_report(rep: dict) -> str:
    lines = ["run               started                    rate-limits errors gaps missed"]
    for r in rep["runs"]:
        lines.append(f"{r['run_id']:<17} {r['started']:<26} {r['rate_limit_responses']:>11} "
                     f"{r['request_errors']:>6} {r['gaps_logged_by_recorder']:>4} "
                     f"{r['trades_missed_per_recorder']:>6}")
    header = (f"{'symbol':<14}{'trades':>10}{'missing':>9}{'conflicts':>10}"
              f"{'time<prev':>10}{'bad values':>11}{'quoteQty inexact':>18}")
    lines += ["", header]
    for s, r in rep["symbols"].items():
        bad = r["unparsable_numbers"] + r["non_positive_price_or_qty"] + r["flags_not_0_or_1"]
        lines.append(f"{s:<14}{r['unique_trades']:>10,}{r['missing_ids']:>9,}"
                     f"{r['conflicting_ids']:>10}{r['time_goes_backwards']:>10}{bad:>11}"
                     f"{(r['quote_qty_share_inexact'] or 0):>17.1%}")
    lines += ["", f"isRPITrade takes both values: {rep['rpi_flag_takes_both_values']}",
              "problems: " + ("none" if not rep["problems"] else "")]
    lines += [f"  - {p}" for p in rep["problems"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("dirs", nargs="+", type=Path)
    p.add_argument("--json", type=Path, help="also write the full report here")
    a = p.parse_args(argv)
    rep = report_from_dirs(a.dirs)
    if a.json:
        a.json.write_text(json.dumps(rep, indent=1) + "\n")
    print(format_report(rep))


if __name__ == "__main__":
    main()
