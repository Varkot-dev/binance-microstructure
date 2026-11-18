"""Weeks 1 to 2: order-flow proxies on the Q14 cross-sections (2023-06 and 2026-07).

For every Q14 unit that Q14 fitted in the 2023-06 cross-section (181 contracts) and
the 2026-07 cross-section (138 survivors of 2023 plus 113 crypto new listings), this
computes `microstructure.evolution.proxies.contract_month_proxies` on that
contract-month (monthly file only, as in e1_proxies.py) and joins the unit's Q14
metrics from results/q14_survivorship.json and its lifecycle status from
research/market_evolution/data/contract_lifecycle.csv. The 2026-07 units that Q14
labels stock, ETF or commodity (status new_listing_equity) are skipped and listed.

Data
- The 10 Q9 symbols: the local monthly parquet data/parquet/aggTrades/<S>/<P>.parquet
  is read in place and never deleted.
- Every other unit: the monthly aggTrades zip is downloaded with
  `microstructure.data.binance.download` (SHA-256 verified, through Q14's Prefetcher,
  at most 3 downloads ahead) into data/proxies_cs/tmp/, ingested there (never into the
  shared parquet layout), the proxies are computed, then the zip and parquet are
  deleted. CSVs up to Q14's STREAM_INGEST_BYTES go through `ingest_agg_trades`. Larger
  ones would need Q14's `ingest_agg_trades_streaming`, but it extracts the CSV next to
  the zip (zip + 4 to 5 GB of CSV for the two units concerned), which breaks the 3 GB
  temporary-disk budget; they are read in newline-aligned chunks straight from the zip
  with the same header sniffing, casts and schema, into parquet parts.
- Temporary disk is budgeted: a download is only started ahead if the estimated
  temporary bytes (zips in flight plus the current unit's zip and parquet) stay under
  TEMP_BUDGET. A sampler thread records the actual peak.

Resumable: one JSON per unit under data/proxies_cs/units/; units with status "ok" are
skipped, "failed" units are retried. Compute is one unit at a time.

Run from the repository root:
    POLARS_MAX_THREADS=2 PYTHONPATH=src .venv/bin/python \
        research/market_evolution/e2_proxies_cross_section.py [--stages run report]
Outputs: data/proxies_cross_section.parquet and data/proxies_cross_section.md
(next to this file). The correlations in the report are descriptive only.
"""
from __future__ import annotations

import argparse
import gc
import io
import json
import shutil
import threading
import time
import zipfile
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import rankdata

from microstructure.analyses.q14_survivorship import (
    NON_CRYPTO_BY_NAME,
    STREAM_INGEST_BYTES,
    Prefetcher,
)
from microstructure.data.events import to_aggressor_events
from microstructure.data.ingest import ingest_agg_trades
from microstructure.evolution.proxies import NEAR_CIRCULAR, PROXY_DOCS, contract_month_proxies

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATA = REPO / "data"
LOCAL_PARQUET = DATA / "parquet" / "aggTrades"
WORK = DATA / "proxies_cs"
UNITS = WORK / "units"
TMP = WORK / "tmp"
RUNS = WORK / "runs.json"
Q14_JSON = REPO / "results" / "q14_survivorship.json"
LIFECYCLE = HERE / "data" / "contract_lifecycle.csv"
OUT_PARQUET = HERE / "data" / "proxies_cross_section.parquet"
OUT_MD = HERE / "data" / "proxies_cross_section.md"

SETS = ("cross_2023", "cross_2026")
RAW_COLS = ["agg_trade_id", "ts", "price", "qty", "first_trade_id", "last_trade_id",
            "is_buyer_maker"]
Q14_METRICS = ("gbm_all", "linear", "persistence", "majority", "lift", "log10_events",
               "n_events")
TEMP_BUDGET = 2_600_000_000      # bytes; hard limit asked for is 3 GB
LOOKAHEAD = 3
PARQUET_PER_ZIP = 1.0            # parquet bytes per zip byte (BTCUSDT 2023-06: 0.65)
HUGE_ZIP = 600_000_000           # processed last, with nothing downloaded alongside
CHUNK_BYTES = 256_000_000
N_BOOT = 2000
_AGG_COLS = ("agg_trade_id", "price", "qty", "first_trade_id", "last_trade_id", "ts_raw",
             "is_buyer_maker")


# ------------------------------------------------------------------ unit list (Q14)

def q14_units(q14: dict) -> tuple[list[dict], list[dict]]:
    """(units to measure, excluded 2026-07 non-crypto units) from Q14's result JSON.

    Included: every Q14-fitted (outcome ok) unit of cross_2023, and of cross_2026
    whose Q14 status is not a *_equity label. Excluded: cross_2026 units Q14 labels
    stock / ETF / commodity, whatever their Q14 outcome.
    """
    zb = q14["universe"]["zip_bytes"]
    keep, excluded = [], []
    for u in q14["units"]:
        if u["set"] not in SETS:
            continue
        if u["status_2023"].endswith("_equity"):
            excluded.append({"set": u["set"], "symbol": u["symbol"], "period": u["period"],
                             "q14_outcome": u["outcome"],
                             "label": NON_CRYPTO_BY_NAME.get(u["symbol"])
                             or "timing screen (US-equity trading hours)"})
            continue
        if u["outcome"] != "ok":
            continue
        keep.append({"set": u["set"], "symbol": u["symbol"], "period": u["period"],
                     "q14_status": u["status_2023"], "q9_symbol": bool(u.get("q9_symbol")),
                     "zip_bytes": (zb.get(u["symbol"]) or {}).get(u["period"]),
                     "metrics": {k: u["metrics"][k] for k in Q14_METRICS}})
    return keep, excluded


# ------------------------------------------------------------------ lifecycle join

def _month_bounds(period: str) -> tuple[str, str]:
    y, m = int(period[:4]), int(period[5:7])
    nxt = f"{y + (m == 12):04d}-{m % 12 + 1:02d}-01"
    last = (np.datetime64(nxt) - np.timedelta64(1, "D")).astype(str)
    return f"{period}-01", str(last)


def lifecycle_of(lc: pl.DataFrame, symbol: str, period: str) -> dict:
    """Lifecycle row of the life that trades in `period` (None fields if none does)."""
    lo, hi = _month_bounds(period)
    rows = lc.filter((pl.col("symbol") == symbol) & (pl.col("first_trade_day") <= hi)
                     & (pl.col("last_trade_day") >= lo))
    if rows.height == 0:
        return {"lifecycle_status": None, "lifecycle_life": None, "lifecycle_n_lives": None,
                "lifecycle_alive_at_end": None, "lifecycle_last_trade_day": None,
                "lifecycle_successor": None}
    r = rows.row(0, named=True)
    return {"lifecycle_status": r["status"], "lifecycle_life": int(r["life"]),
            "lifecycle_n_lives": int(r["n_lives"]),
            "lifecycle_alive_at_end": int(r["alive_at_end"]),
            "lifecycle_last_trade_day": r["last_trade_day"],
            "lifecycle_successor": r["successor"] or None}


def read_lifecycle(path: Path = LIFECYCLE) -> pl.DataFrame:
    return pl.read_csv(path, infer_schema=False).with_columns(
        pl.col("successor").fill_null(""))


def join_rows(units: list[dict], records: dict[tuple[str, str], dict],
              lc: pl.DataFrame) -> pl.DataFrame:
    """One row per unit: set, symbol, period, status, Q14 metrics, lifecycle, proxies.

    `records` maps (symbol, period) to the unit JSON written by the run stage. A unit
    with no record, or a failed one, keeps its row with null proxies and its reason.
    """
    proxy_keys: list[str] = []
    for rec in records.values():
        for k in rec.get("proxies") or {}:
            if k not in proxy_keys:
                proxy_keys.append(k)
    rows = []
    for u in units:
        rec = records.get((u["symbol"], u["period"])) or {}
        status = rec.get("status", "not_run")
        prox = rec.get("proxies") or {}
        row = {"set": u["set"], "symbol": u["symbol"], "period": u["period"],
               "status": status, "reason": rec.get("reason"),
               "q14_status": u["q14_status"], "q9_symbol": u["q9_symbol"],
               **{f"q14_{k}": u["metrics"][k] for k in Q14_METRICS},
               **lifecycle_of(lc, u["symbol"], u["period"])}
        for k in proxy_keys:
            v = prox.get(k)
            row[k] = float(v) if isinstance(v, int | float) and v is not None else None
        rows.append(row)
    return pl.DataFrame(rows, infer_schema_length=None)


# ------------------------------------------------------------------ statistics

def _resid(a: np.ndarray, z: np.ndarray) -> np.ndarray:
    X = np.column_stack([np.ones_like(z), z])
    beta, *_ = np.linalg.lstsq(X, a, rcond=None)
    return a - X @ beta


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a - a.mean(), b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else float("nan")


def spearman(x, y) -> float:
    return _pearson(rankdata(x), rankdata(y))


def partial_spearman(x, y, z) -> float:
    """Spearman correlation of x and y after partialling out z: ranks of x and y are
    each regressed on the ranks of z (OLS with intercept) and the residuals correlated."""
    rz = rankdata(z)
    return _pearson(_resid(rankdata(x), rz), _resid(rankdata(y), rz))


def boot_corrs(x, y, z, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """Spearman and partial Spearman with 95% percentile intervals from resampling
    contracts (rows) with replacement. Rows with a non-finite value are dropped."""
    x, y, z = (np.asarray(a, dtype=np.float64) for a in (x, y, z))
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    x, y, z = x[ok], y[ok], z[ok]
    out = {"n": int(x.size)}
    if x.size < 5:
        return out | {"rho": None, "rho_ci": None, "partial": None, "partial_ci": None}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, x.size, size=(n_boot, x.size))
    d_r = np.array([spearman(x[i], y[i]) for i in idx])
    d_p = np.array([partial_spearman(x[i], y[i], z[i]) for i in idx])

    def ci(d):
        d = d[np.isfinite(d)]
        return [float(v) for v in np.percentile(d, [2.5, 97.5])] if d.size else None

    return out | {"rho": spearman(x, y), "rho_ci": ci(d_r),
                  "partial": partial_spearman(x, y, z), "partial_ci": ci(d_p)}


# ------------------------------------------------------------------ ingest and compute

def _cast_agg(df: pl.DataFrame) -> pl.DataFrame:
    """The casts of q14_survivorship.ingest_agg_trades_streaming, on an eager frame."""
    ts = pl.col("ts_raw").cast(pl.Int64)
    return df.with_columns(
        pl.col("agg_trade_id").cast(pl.Int64),
        pl.col("first_trade_id").cast(pl.Int64),
        pl.col("last_trade_id").cast(pl.Int64),
        pl.col("is_buyer_maker").cast(pl.Utf8).str.to_lowercase().eq("true")
        .alias("is_buyer_maker"),
        pl.when(ts > 100_000_000_000_000).then(ts // 1000).otherwise(ts)
        .cast(pl.Datetime("ms")).dt.replace_time_zone("UTC").alias("ts"),
        pl.col("price").cast(pl.Float64),
        pl.col("qty").cast(pl.Float64),
    ).select("agg_trade_id", "price", "qty", "first_trade_id", "last_trade_id", "ts",
             "is_buyer_maker")


def ingest_zip_chunked(zip_path: Path, out_dir: Path, chunk_bytes: int = CHUNK_BYTES
                       ) -> list[Path]:
    """Ingest a zipped aggTrades CSV without extracting it: newline-aligned chunks of
    the member are parsed (all text, then cast) and written as parquet parts."""
    out_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
        if len(members) != 1:
            raise ValueError(f"{zip_path.name}: expected 1 member, got {len(members)}")
        with zf.open(members[0]) as fh:
            carry = b""
            has_header = None
            while True:
                buf = fh.read(chunk_bytes)
                data = carry + buf
                if not buf:
                    carry, block = b"", data
                else:
                    cut = data.rfind(b"\n") + 1
                    carry, block = data[cut:], data[:cut]
                if block.strip():
                    if has_header is None:
                        first = block[:256].split(b",", 1)[0].split(b"\n", 1)[0]
                        has_header = not first.strip().strip(b'"').strip(b"'").lstrip(
                            b"-").isdigit()
                        hdr = has_header
                    else:
                        hdr = False
                    df = pl.read_csv(io.BytesIO(block), has_header=hdr, infer_schema=False)
                    if df.width < len(_AGG_COLS):
                        raise ValueError(f"{zip_path.name}: expected >= {len(_AGG_COLS)} "
                                         f"cols, got {df.width}")
                    df = df.select(df.columns[:len(_AGG_COLS)])
                    df = _cast_agg(df.rename(dict(zip(df.columns, _AGG_COLS, strict=True))))
                    p = out_dir / f"part{len(parts):04d}.parquet"
                    df.write_parquet(p)
                    parts.append(p)
                    del df
                if not buf:
                    break
    return parts


def csv_bytes(zip_path: Path) -> int:
    with zipfile.ZipFile(zip_path) as zf:
        return sum(i.file_size for i in zf.infolist())


def _in_month(period: str) -> pl.Expr:
    """Rows of `period` (same rows as e1's strftime filter, without a string column)."""
    lo, hi = _month_bounds(period)
    start = pl.lit(lo).str.to_datetime("%Y-%m-%d", time_unit="ms", time_zone="UTC")
    end = pl.lit(hi).str.to_datetime("%Y-%m-%d", time_unit="ms", time_zone="UTC")
    return (pl.col("ts") >= start) & (pl.col("ts") < end + pl.duration(days=1))


LEAN_ROWS = 40_000_000
# Columns of raw that contract_month_proxies reads (relative_tick, aggregation_shape).
RAW_PROXY_COLS = ["agg_trade_id", "ts", "price", "first_trade_id", "last_trade_id"]


def day_by_day_events(lf: pl.LazyFrame, period: str) -> pl.DataFrame:
    """to_aggressor_events one UTC day at a time, concatenated. Events group prints by
    (ts, side), which never spans two days, and the output is sorted by (ts, sign), so
    this is the same frame as one call on the whole month, with a far smaller peak
    (one call on 93M prints, BANKUSDT 2026-07, needed over 12 GB)."""
    lo, _ = _month_bounds(period)
    first = np.datetime64(lo, "D")
    n_days = int((np.datetime64(_month_bounds(period)[1], "D") - first).astype(int)) + 1
    out = []
    for k in range(n_days):
        d0 = pl.lit(str(first + np.timedelta64(k, "D"))).str.to_datetime("%Y-%m-%d", time_unit="ms", time_zone="UTC")
        day = lf.filter((pl.col("ts") >= d0) & (pl.col("ts") < d0 + pl.duration(days=1)))
        ev = to_aggressor_events(day)
        if ev.height:
            out.append(ev)
        gc.collect()
    return pl.concat(out, rechunk=True)


def month_proxies_lean(paths: list[Path], period: str) -> dict | None:
    """month_proxies for very large months, with less memory: events are built from a
    lazy scan before raw is loaded, and raw keeps only the columns the proxies read.
    Same result as month_proxies when the files are in agg_trade_id order (the dumps
    are); returns None otherwise so the caller falls back."""
    lf = pl.scan_parquet(paths).filter(_in_month(period))
    if not lf.select((pl.col("agg_trade_id").diff().drop_nulls() > 0).all()).collect().item():
        return None
    events = day_by_day_events(lf.select("ts", "is_buyer_maker", "price", "qty"), period)
    gc.collect()
    raw = lf.select(RAW_PROXY_COLS).collect()
    out = contract_month_proxies(events, raw)
    if out.pop("month") != period:
        raise ValueError("proxies month does not match the unit's period")
    out["n_raw"] = raw.height
    return out


def month_proxies(paths: list[Path], period: str) -> dict:
    """e1_proxies.month_proxies on given parquet file(s): this month only, id order."""
    n = pl.scan_parquet(paths).select(pl.len()).collect().item()
    if n > LEAN_ROWS:
        out = month_proxies_lean(paths, period)
        if out is not None:
            return out
    raw = pl.read_parquet(paths, columns=RAW_COLS)
    in_month = _in_month(period)
    if not raw.select(in_month.all()).item():   # no copy when every row is in the month
        raw = raw.filter(in_month)
    if not raw["agg_trade_id"].is_sorted():
        raw = raw.sort("agg_trade_id")
    events = to_aggressor_events(raw)
    out = contract_month_proxies(events, raw)
    if out.pop("month") != period:
        raise ValueError("proxies month does not match the unit's period")
    out["n_raw"] = raw.height
    return out


def unit_path(symbol: str, period: str) -> Path:
    return UNITS / f"{symbol}_{period}.json"


def read_record(symbol: str, period: str) -> dict | None:
    p = unit_path(symbol, period)
    return json.loads(p.read_text()) if p.exists() else None


def _tree_bytes(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


class DiskPeak:
    """Samples the temporary directory's size every 0.5 s and keeps the maximum."""

    def __init__(self, path: Path):
        self.path, self.peak, self._stop = path, 0, threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.peak = max(self.peak, _tree_bytes(self.path))
            except OSError:
                pass
            self._stop.wait(0.5)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join()


def process_unit(u: dict, pre: Prefetcher) -> dict:
    sym, per = u["symbol"], u["period"]
    rec = {"set": u["set"], "symbol": sym, "period": per, "status": "failed",
           "reason": None, "source": None, "ingest": None, "seconds": None, "proxies": None}
    t0 = time.time()
    work = TMP / "parquet" / f"{sym}_{per}"
    zip_path: Path | None = None
    try:
        local = LOCAL_PARQUET / sym / f"{per}.parquet"
        if u["q9_symbol"]:
            if not local.exists():
                raise FileNotFoundError(f"local Q9 parquet missing: {local}")
            rec["source"], paths = "local", [local]
        else:
            rec["source"] = "download"
            zip_path = pre(sym, per)
            rec["zip_bytes"] = zip_path.stat().st_size
            rec["csv_bytes"] = csv_bytes(zip_path)
            work.mkdir(parents=True, exist_ok=True)
            if rec["csv_bytes"] > STREAM_INGEST_BYTES:
                rec["ingest"] = "chunked_from_zip"
                paths = ingest_zip_chunked(zip_path, work)
            else:
                rec["ingest"] = "ingest_agg_trades"
                paths = [ingest_agg_trades(zip_path, work)]
            zip_path.unlink(missing_ok=True)
            rec["parquet_bytes"] = sum(p.stat().st_size for p in paths)
        rec["proxies"] = month_proxies(paths, per)
        rec["status"] = "ok"
    except Exception as exc:  # noqa: BLE001 - recorded, retried on the next run
        rec["reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        if zip_path is not None:
            zip_path.unlink(missing_ok=True)
        shutil.rmtree(work, ignore_errors=True)   # only ever under data/proxies_cs/tmp
        rec["seconds"] = round(time.time() - t0, 1)
        gc.collect()
    UNITS.mkdir(parents=True, exist_ok=True)
    unit_path(sym, per).write_text(json.dumps(rec, indent=1))
    return rec


def ordered(units: list[dict]) -> list[dict]:
    """Q14 order, with the very large zips moved to the end."""
    small = [u for u in units if (u["zip_bytes"] or 0) < HUGE_ZIP or u["q9_symbol"]]
    huge = sorted((u for u in units if u not in small), key=lambda u: u["zip_bytes"])
    return small + huge


def _temp_need(u: dict) -> int:
    if u["q9_symbol"]:
        return 0
    return int((u["zip_bytes"] or 0) * (1 + PARQUET_PER_ZIP))


def run(units: list[dict], max_units: int | None = None) -> dict:
    todo = [u for u in ordered(units)
            if (read_record(u["symbol"], u["period"]) or {}).get("status") != "ok"]
    if max_units is not None:
        todo = todo[:max_units]
    TMP.mkdir(parents=True, exist_ok=True)
    pre = Prefetcher(TMP / "zips", workers=LOOKAHEAD)
    t0 = time.time()
    n_ok = n_fail = 0
    try:
        with DiskPeak(TMP) as peak:
            for i, u in enumerate(todo):
                budget = TEMP_BUDGET - _temp_need(u)
                in_flight = 0
                for t in todo[i + 1:i + 1 + LOOKAHEAD]:
                    if t["q9_symbol"]:
                        continue
                    z = _temp_need(t)    # its zip plus, later, its parquet
                    if (t["symbol"], t["period"]) in pre.futs:
                        in_flight += z
                        continue
                    if in_flight + z > budget:
                        break
                    pre.want(t["symbol"], t["period"])
                    in_flight += z
                rec = process_unit(u, pre)
                n_ok += rec["status"] == "ok"
                n_fail += rec["status"] != "ok"
                _log_run(t0, i + 1, n_ok, n_fail, peak.peak)
                print(f"[{i + 1}/{len(todo)}] {u['set']} {u['symbol']} {u['period']}: "
                      f"{rec['status']} {rec['seconds']}s"
                      f"{' ' + rec['reason'] if rec['reason'] else ''} "
                      f"(tmp peak {peak.peak / 1e9:.2f} GB)", flush=True)
    finally:
        pre.close()
        shutil.rmtree(TMP / "parquet", ignore_errors=True)
    return _log_run(t0, len(todo), n_ok, n_fail, peak.peak, finished=True)


def _log_run(t0: float, n_done: int, n_ok: int, n_fail: int, peak: int,
             finished: bool = False) -> dict:
    """Write (or update) this run's entry in runs.json after every unit, so a run
    that is killed still leaves its wall time and disk peak."""
    log = {"started_unix": t0, "wall_seconds": round(time.time() - t0, 1),
           "n_attempted": n_done, "n_ok": n_ok, "n_failed": n_fail,
           "tmp_peak_bytes": peak, "finished": finished}
    runs = json.loads(RUNS.read_text()) if RUNS.exists() else []
    runs = [r for r in runs if r["started_unix"] != t0] + [log]
    RUNS.write_text(json.dumps(runs, indent=1))
    return log


# ------------------------------------------------------------------ report

BOOKKEEPING = ("n_events", "days", "n_raw")


def corr_proxies(df: pl.DataFrame) -> list[str]:
    """Non-circular proxy columns for the correlation table (bookkeeping counts out)."""
    return [c for c in ["events_per_day", *PROXY_DOCS]
            if c in df.columns and c not in NEAR_CIRCULAR and c not in BOOKKEEPING]


def corr_table(df: pl.DataFrame, n_boot: int = N_BOOT) -> list[dict]:
    rows = []
    ok = df.filter(pl.col("status") == "ok")
    for k, period in enumerate(sorted(ok["period"].unique().to_list())):
        sub = ok.filter(pl.col("period") == period)
        y = sub["q14_gbm_all"].to_numpy()
        z = sub["q14_log10_events"].to_numpy()
        for j, c in enumerate(corr_proxies(ok)):
            x = sub[c].cast(pl.Float64).to_numpy()
            rows.append({"period": period, "proxy": c,
                         **boot_corrs(x, y, z, n_boot=n_boot, seed=1000 * k + j)})
    return rows


def _fmt(v, ci) -> str:
    if v is None or not np.isfinite(v):
        return "n/a"
    if ci is None:
        return f"{v:+.2f}"
    return f"{v:+.2f} [{ci[0]:+.2f}, {ci[1]:+.2f}]"


def write_md(df: pl.DataFrame, excluded: list[dict], corr: list[dict], runs: list[dict],
             records: dict) -> None:
    L = ["# Order-flow proxies on the Q14 cross-sections (`proxies_cross_section.parquet`)",
         "",
         ("Built by `research/market_evolution/e2_proxies_cross_section.py`. One row per Q14 "
         "unit: `set`, `symbol`, `period`, `status` (ok or failed, with `reason`), Q14's "
         "status label (`q14_status`), the Q14 metrics (`q14_gbm_all`, `q14_linear`, "
         "`q14_persistence`, `q14_majority`, `q14_lift`, `q14_log10_events`, "
         "`q14_n_events`, from `results/q14_survivorship.json`), the lifecycle status of "
         "the life trading in that month (`lifecycle_*`, from `contract_lifecycle.csv`), and "
         "every proxy of `contract_month_proxies` (definitions in "
         "`microstructure.evolution.proxies.PROXY_DOCS`) plus `n_raw`. The near-circular "
         f"proxies {', '.join('`' + c + '`' for c in NEAR_CIRCULAR)} are kept under those "
         "names; they are nearly the outcome and are descriptive only."), "",
         "## Coverage", "",
         "| set | units | ok | failed | local Q9 parquet | downloaded |",
         "|---|---|---|---|---|---|"]
    for s in SETS:
        sub = df.filter(pl.col("set") == s)
        src = [records.get((r["symbol"], r["period"]), {}).get("source")
               for r in sub.iter_rows(named=True)]
        L.append(f"| {s} | {sub.height} | {(sub['status'] == 'ok').sum()} | "
                 f"{(sub['status'] != 'ok').sum()} | {src.count('local')} | "
                 f"{src.count('download')} |")
    L += ["", "By Q14 status label:", "", "| set | q14_status | ok | not ok |", "|---|---|---|---|"]
    g = (df.group_by("set", "q14_status")
         .agg((pl.col("status") == "ok").sum().alias("ok"),
              (pl.col("status") != "ok").sum().alias("bad")).sort("set", "q14_status"))
    for r in g.iter_rows(named=True):
        L.append(f"| {r['set']} | {r['q14_status']} | {r['ok']} | {r['bad']} |")
    fails = df.filter(pl.col("status") != "ok")
    L += ["", "### Failures", ""]
    if fails.height == 0:
        L.append("None.")
    for r in fails.iter_rows(named=True):
        L.append(f"- {r['set']} {r['symbol']} {r['period']}: {r['status']}: {r['reason']}")
    chunked = sorted(f"{k[0]} {k[1]}" for k, v in records.items()
                     if v.get("ingest") == "chunked_from_zip")
    L += ["", "### Excluded (Q14 labels them stock, ETF or commodity; not measured)", "",
          f"{len(excluded)} cross_2026 units: "
          + ", ".join(f"{e['symbol']} ({e['label']}; Q14 {e['q14_outcome']})"
                      for e in excluded) + ".", "",
          ("Q14's other non-fitted units (incomplete months in 2023-06, too-thin units) have no "
          "Q14 metrics and are outside this table, as in Q14."), "",
          "## Runtime and disk", ""]
    lean = sorted(f"{k[0]} {k[1]} ({v['proxies']['n_raw'] / 1e6:.0f}M records)"
                  for k, v in records.items()
                  if (v.get("proxies") or {}).get("n_raw", 0) > LEAN_ROWS
                  and v.get("source") == "download")
    tot = sum(r["wall_seconds"] for r in runs)
    peak = max((r["tmp_peak_bytes"] for r in runs), default=0)
    secs = [v["seconds"] for v in records.values() if v.get("seconds") is not None]
    L += [(f"- {len(runs)} run(s), {tot / 3600:.2f} h wall in total; per-unit time "
           f"(download wait, ingest and proxies) median {np.median(secs):.0f} s, max "
           f"{max(secs):.0f} s.") if secs else "- no runs recorded",
          (f"- Peak temporary disk (zips plus parquet under data/proxies_cs/tmp, sampled every "
          f"0.5 s): {peak / 1e9:.2f} GB (budget 3 GB)."),
          "- Ingest: `ingest_agg_trades` for CSVs up to 1.5 GB; above that, chunked "
          "parsing straight from the zip (same casts and schema as Q14's streaming ingest, "
          "which would have extracted a 4 to 5 GB CSV and broken the disk budget): "
          + (", ".join(chunked) if chunked else "none") + ".",
          ("- Months over LEAN_ROWS raw records are measured by `month_proxies_lean` (events "
           "built one day at a time, raw reduced to the columns the proxies read; same "
           "result, checked on 1000PEPEUSDT 2023-06): "
           + (", ".join(lean) if lean else "none") + ". Its peak memory was about 11 GB, "
           "mostly inside `relative_tick`."),
          *[f"- Run note: {r['note']}." for r in runs if r.get("note")], "",
          "## First descriptive table: proxies against Q14 gbm_all accuracy", "",
          ("**Descriptive only.** Within each period, the Spearman correlation across "
          "contracts of each non-circular proxy with Q14's `gbm_all` accuracy, and the same "
          "after partialling out `log10_events` (ranks of both regressed on the rank of "
          "log10 events, residuals correlated). 95% intervals from 2000 bootstrap resamples "
          "of contracts. One cross-section per period, many proxies, no correction for "
          "multiple comparisons, no causal reading: these are leads for weeks 3 to 4. "
          "`lot` and `tick` are in coin and USDT units and are not comparable across "
          "contracts; they are shown for completeness. The run-length proxies are not in "
           "NEAR_CIRCULAR but are close to it: longer same-sign runs mean a higher sign "
           "repeat rate, so their large correlations are partly mechanical."), ""]
    periods = sorted({r["period"] for r in corr})
    hdr = "| proxy | " + " | ".join(f"{p} rho | {p} partial" for p in periods) + " |"
    L += [hdr, "|---|" + "---|---|" * len(periods)]
    by = {(r["period"], r["proxy"]): r for r in corr}
    for c in dict.fromkeys(r["proxy"] for r in corr):
        cells = []
        for p in periods:
            r = by.get((p, c), {})
            cells += [_fmt(r.get("rho"), r.get("rho_ci")),
                      _fmt(r.get("partial"), r.get("partial_ci"))]
        L.append(f"| {c} | " + " | ".join(cells) + " |")
    ns = {p: next((r["n"] for r in corr if r["period"] == p), 0) for p in periods}
    L += ["", "n per period: " + ", ".join(f"{p}: {n}" for p, n in ns.items())
          + " (rows with a missing value for a proxy are dropped for that proxy).", ""]
    OUT_MD.write_text("\n".join(L))


def report(units: list[dict], excluded: list[dict], n_boot: int = N_BOOT) -> None:
    records = {}
    for u in units:
        r = read_record(u["symbol"], u["period"])
        if r is not None:
            records[(u["symbol"], u["period"])] = r
    df = join_rows(units, records, read_lifecycle())
    df.write_parquet(OUT_PARQUET)
    corr = corr_table(df, n_boot)
    (WORK / "corr_table.json").write_text(json.dumps(corr, indent=1))
    runs = json.loads(RUNS.read_text()) if RUNS.exists() else []
    write_md(df, excluded, corr, runs, records)
    print(f"wrote {OUT_PARQUET} ({df.height} rows) and {OUT_MD}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", nargs="+", choices=("run", "report"),
                    default=["run", "report"])
    ap.add_argument("--max-units", type=int, default=None)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    args = ap.parse_args()
    units, excluded = q14_units(json.loads(Q14_JSON.read_text()))
    print(f"{len(units)} units ({sum(u['set'] == 'cross_2023' for u in units)} cross_2023, "
          f"{sum(u['set'] == 'cross_2026' for u in units)} cross_2026), "
          f"{len(excluded)} excluded", flush=True)
    if "run" in args.stages:
        print(run(units, args.max_units), flush=True)
    if "report" in args.stages:
        report(units, excluded, args.n_boot)


if __name__ == "__main__":
    main()
