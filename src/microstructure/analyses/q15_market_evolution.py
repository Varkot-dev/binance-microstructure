"""Q15: why did next-trade-sign predictability rise, and does tick size cause sign persistence?

Assembles the Part A outputs of `research/market_evolution` into one result dict; it
fits nothing new except descriptive cross-sectional regressions and bootstrap intervals
on files that already exist:

- `e0_what_changed.json`: Q10's 10 symbols x 5 months, fresh-model accuracy;
- `e1_proxies.json`: the same coins' proxies (relative tick, trade size);
- `data/proxies_cross_section.parquet` (e2): the Q14 cross-sections, 2023-06 and 2026-07;
- `data/e4_panel_regressions.md` (e4 writes no JSON, so its tables are parsed);
- `data/event_study/e3_results.json`, `data/event_study/e5/e5_results.json`;
- the lock-box runs `data/event_study/e5/lockbox/e5_lockbox_run*.json` (one run of the
  frozen e5 design on the reserved 2026-08-06 and 2026-10-15 batches).

    PYTHONPATH=src .venv/bin/python -m microstructure.analyses.q15_market_evolution

writes results/q15_market_evolution.{json,md,png}. The report text is built by
`q15_report` from the dict alone.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import numpy as np

from microstructure.analyses import q15_report
from microstructure.data.jsonio import dumps_strict

REPO = Path(__file__).resolve().parents[3]
ME = Path("research") / "market_evolution"
E0 = ME / "e0_what_changed.json"
E1 = ME / "e1_proxies.json"
CROSS = ME / "data" / "proxies_cross_section.parquet"
E4_MD = ME / "data" / "e4_panel_regressions.md"
E3 = Path("data") / "event_study" / "e3_results.json"
E5 = Path("data") / "event_study" / "e5" / "e5_results.json"
LOCKBOX = Path("data") / "event_study" / "e5" / "lockbox"
OUT = Path("results")

N_BOOT = 2000
SEED = 0
PRIMARY = ("repeat_rate", "sign_acf_lag1")
SECONDARY = ("acc_refit", "refit_excess")
MECHANISMS = ("unchanged", "long_runs", "log_size", "log_events", "log_rel_tick")
Q10_FROM, Q10_TO = "2023-06", "2025-07"


# ---------------------------------------------------------------------------- helpers

def _iv(b, lo, hi, **extra) -> dict:
    return {"b": float(b), "lo": float(lo), "hi": float(hi), **extra}


def _boot_mean(x: np.ndarray, rng: np.random.Generator, n_boot: int = N_BOOT) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    draws = x[rng.integers(0, x.size, (n_boot, x.size))].mean(axis=1)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return _iv(x.mean(), lo, hi, n=int(x.size), draws=draws)


# ---------------------------------------------------------------------------- Q10 coins

def q10_coins(e0_rows: list[dict], e1_rows: list[dict]) -> dict:
    """Mean fresh-model accuracy of Q10's 10 coins by month, and their within-coin
    change in log relative tick and log median trade size from 2023-06 to 2025-07."""
    months = sorted({r["period"] for r in e0_rows})
    acc = {m: 100 * float(np.mean([r["acc_gbm_all"] for r in e0_rows if r["period"] == m]))
           for m in months}
    by = {(r["symbol"], r["period"]): r for r in e1_rows}
    syms = sorted({r["symbol"] for r in e1_rows})
    d_tick, d_size, d_acc = [], [], []
    for s in syms:
        a, b = by.get((s, Q10_FROM)), by.get((s, Q10_TO))
        if not a or not b:
            continue
        d_tick.append(math.log(b["rel_tick_bps"] / a["rel_tick_bps"]))
        d_size.append(math.log(b["median_notional_usd"] / a["median_notional_usd"]))
        d_acc.append(100 * (b["acc_gbm_all"] - a["acc_gbm_all"]))
    rng = np.random.default_rng(SEED)
    return {"n": len(syms), "months": months, "mean_acc_pp": acc,
            "from": Q10_FROM, "to": Q10_TO,
            "d_acc": _boot_mean(np.array(d_acc), rng),
            "d_log_rel_tick": _boot_mean(np.array(d_tick), rng),
            "d_log_size": _boot_mean(np.array(d_size), rng),
            "per_coin_d_log_rel_tick": dict(zip(syms, d_tick, strict=True))}


# ---------------------------------------------------------------------------- e2 parquet

def _cross_frame(path: Path):
    import polars as pl

    return (pl.read_parquet(path).filter(pl.col("status") == "ok")
            .with_columns((pl.col("q14_gbm_all") * 100).alias("acc"),
                          (pl.col("sign_repeat_rate") * 100).alias("rep"),
                          pl.col("median_notional_usd").log().alias("lsize"),
                          pl.col("rel_tick_bps").log().alias("ltick"),
                          (pl.col("q14_log10_events") * math.log(10)).alias("lev")))


def survivor_changes(df, n_boot: int = N_BOOT) -> dict:
    """Within-contract change 2026-07 minus 2023-06 for contracts in both cross-sections."""
    a = df.filter(df["set"] == "cross_2023").select("symbol", "acc", "rep", "lsize", "ltick")
    b = df.filter(df["set"] == "cross_2026").select("symbol", "acc", "rep", "lsize", "ltick")
    j = a.join(b, on="symbol", suffix="_26")
    rng = np.random.default_rng(SEED)
    out = {"n": j.height}
    for k in ("acc", "rep", "lsize", "ltick"):
        d = (j[f"{k}_26"] - j[k]).to_numpy().astype(float)
        out[k] = _boot_mean(d, rng, n_boot)
        out[k]["share_down"] = float((d < 0).mean())
    return out


def cross_section_multi(df, n_boot: int = N_BOOT) -> dict:
    """OLS across contracts, per month: outcome ~ ln size + ln relative tick + ln events.

    Descriptive (correlations at equal activity), 95% intervals from resampling contracts.
    """
    out = {}
    rng = np.random.default_rng(SEED)
    for per in sorted(df["set"].unique().to_list()):
        d = df.filter(df["set"] == per)
        X = np.column_stack([np.ones(d.height)] + [d[c].to_numpy().astype(float)
                                                   for c in ("lsize", "ltick", "lev")])
        for name in ("acc", "rep"):
            y = d[name].to_numpy().astype(float)
            ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
            Xo, yo = X[ok], y[ok]
            b = np.linalg.lstsq(Xo, yo, rcond=None)[0]
            bs = np.empty((n_boot, 4))
            for i in range(n_boot):
                ix = rng.integers(0, yo.size, yo.size)
                bs[i] = np.linalg.lstsq(Xo[ix], yo[ix], rcond=None)[0]
            lo, hi = np.percentile(bs, [2.5, 97.5], axis=0)
            out[f"{per}|{name}"] = {
                "n": int(ok.sum()),
                "log_size": _iv(b[1], lo[1], hi[1]),
                "log_rel_tick": _iv(b[2], lo[2], hi[2])}
    return out


# ---------------------------------------------------------------------------- e4 markdown

_N = r"[+-]?\d+(?:\.\d+)?"
_CELL = re.compile(rf"^\**({_N})\**\s*\(({_N}) to ({_N})\)$")
_RANGE = re.compile(rf"^({_N}) to ({_N})$")


def _table_after(text: str, marker: str) -> dict[str, list[str]]:
    """Rows (first cell -> other cells) of the first Markdown table after `marker`."""
    i = text.index(marker)
    rows: dict[str, list[str]] = {}
    started = False
    for line in text[i:].splitlines()[1:]:
        if line.startswith("|"):
            started = True
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not set(cells[0]) <= set("- "):
                rows.setdefault(cells[0], cells[1:])
        elif started:
            break
    return rows


def _cell(s: str) -> dict:
    m = _CELL.match(s.strip())
    if not m:
        raise ValueError(f"not an estimate with an interval: {s!r}")
    return _iv(*map(float, m.groups()))


def _cell_range(b: str, rng: str) -> dict:
    m = _RANGE.match(rng.strip())
    if not m:
        raise ValueError(f"not a range: {rng!r}")
    return _iv(float(b), *map(float, m.groups()))


def parse_e4(text: str) -> dict:
    comp = _table_after(text, "## 1. Composition split")["accuracy, mean"]
    noise = re.search(rf"2023-06 to 2023-07 moves mean accuracy by ({_N}) pp \(({_N}) to "
                      rf"({_N})\)", text)
    reg = _table_after(text, "| driver | step | (a1)")
    gel = _table_after(text, "**Main: survivors")
    imp = _table_after(text, "| model | implied effect of a 10x cut")
    models = ("a1_pooled", "a2_pooled_month", "b1_contract_fe", "b2_two_way_fe", "b3_ten_coins")
    return {
        "composition": {"acc_2023": float(comp[0]), "acc_2026": float(comp[1]),
                        "total": _cell(comp[2]), "exits": _cell(comp[3]),
                        "within": _cell(comp[4]), "entries": _cell(comp[5])},
        "noise_floor": _iv(*map(float, noise.groups())),
        "regression": {
            drv: dict(zip(models, (_cell(c) for c in reg[label][1:6]), strict=True))
            for drv, label in (("log_size", "log median trade size"),
                               ("log_rel_tick", "log relative tick"))},
        "gelbach": {
            k: _cell_range(gel[label][0], gel[label][1])
            for k, label in (("rise", "2026 coefficient, no drivers"),
                             ("unexplained", "2026 coefficient, with drivers (unexplained)"),
                             ("trade_size", "group: trade size (log size + under $1k)"),
                             ("rel_tick", "group: relative tick"))},
        "implied_10x_cut": {
            k: _cell_range(imp[label][0], imp[label][1])
            for k, label in (
                ("total", ("survivors, contract FE + 2026 dummy, relative tick only "
                          "(total effect)")),
                ("partial", ("survivors, all six drivers (partial: trade size etc. held "
                            "fixed)")))},
    }


# ---------------------------------------------------------------------------- e3, e5, lock-box

def _est(o: dict) -> dict:
    """The fields of one stacked estimate the report uses."""
    if not o:
        return {}
    r = _iv(o["b"], o["lo"], o["hi"], G=o.get("G"), treated=o.get("treated"),
            batches=o.get("batches"), pre_p=o.get("pre_p"))
    if "perm" in o:
        r["perm"] = {k: o["perm"][k] for k in ("p", "lo", "hi")}
    if "wild" in o:
        r["wild"] = {k: o["wild"].get(k) for k in ("p", "lo", "hi")}
    return r


def e3_summary(e3: dict) -> dict:
    keep = PRIMARY + ("acc_logit", "acc_refit", "unchanged", "log_rel_tick")
    return {ev: {"label": d["label"], "treated": len(d["treated"]),
                 "controls": len(d["controls"]),
                 **{k: _iv(d["outcomes"][k]["b"], d["outcomes"][k]["lo"], d["outcomes"][k]["hi"])
                    for k in keep if k in d["outcomes"]}}
            for ev, d in e3.items()}


def _models(models: dict) -> dict:
    return {m: {k: _est(o) for k, o in d.items() if k in PRIMARY + SECONDARY + MECHANISMS}
            for m, d in models.items()}


def _arms(arms: list[dict]) -> list[dict]:
    return [{"batch": a["batch"], "direction": a["direction"], "treated": a["treated"],
             "controls": a["controls"], "dose": a["dose"],
             **{k: a[k] for k in ("repeat_rate", "acc_refit") if k in a}} for a in arms]


def e5_summary(e5: dict) -> dict:
    return {"models": _models(e5["models"]), "arms": _arms(e5["arms"]),
            "coverage": e5["coverage"],
            "without_e3": {k: _est(o) for k, o in e5["pooled_without_e3"].items()},
            "by_year": {y: {m: _est(d[m].get("repeat_rate", {})) for m in d}
                        for y, d in e5["by_year"].items()},
            "cross_section": e5["cross_section"]}


def lockbox_summary(folder: Path) -> dict:
    """Every lock-box run (normally one) and the final one in full."""
    runs = []
    for p in sorted(folder.glob("e5_lockbox_run*.json"), key=lambda p: int(p.stem.removeprefix("e5_lockbox_run"))):
        r = json.loads(p.read_text())
        runs.append({"run": r["run"], "file": str(p.name), "rerun_reason": r["rerun_reason"],
                     "frozen_commit": r["frozen_commit"], "head": r["head"],
                     "analysed": r["analysed"], "models": _models(r["models"]),
                     "arms": _arms(r["arms"]), "coverage": r["coverage"],
                     "plan_arms": r["plan"]["arms"],
                     "verdict_e5_rule": r["verdict"]})
    if not runs:
        return {}
    led = folder / "e5_lockbox_ledger.json"
    downloaded = sum(json.loads(led.read_text()).values()) if led.exists() else None
    return {"runs": runs, "final": runs[-1], "downloaded_bytes": downloaded}


# ---------------------------------------------------------------------------- accounting

def tick_accounting(d_log_tick: dict, slope: dict, n_draws: int = N_BOOT) -> dict:
    """Change in the outcome implied by a mean change in log relative tick and the
    experimental slope per log point: d x slope, interval from resampled d times a
    normal draw of the slope (se from its 95% interval)."""
    rng = np.random.default_rng(SEED + 1)
    se = (slope["hi"] - slope["lo"]) / (2 * 1.96)
    draws = np.asarray(d_log_tick["draws"])[:n_draws] * rng.normal(slope["b"], se, n_draws)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return _iv(d_log_tick["b"] * slope["b"], lo, hi)


def _strip_draws(x):
    if isinstance(x, dict):
        return {k: _strip_draws(v) for k, v in x.items() if k != "draws"}
    if isinstance(x, list):
        return [_strip_draws(v) for v in x]
    return x


# ---------------------------------------------------------------------------- build

def build_result(root: Path = REPO, n_boot: int = N_BOOT) -> dict:
    e0 = json.loads((root / E0).read_text())
    e1 = json.loads((root / E1).read_text())["rows"]
    df = _cross_frame(root / CROSS)
    e5 = e5_summary(json.loads((root / E5).read_text()))
    res = {
        "question": ("Why did next-trade-sign predictability rise from 2023 to 2025 (Q10), "
                     "and does tick size cause sign persistence?"),
        "inputs": {k: str(v) for k, v in (("e0", E0), ("e1", E1), ("e2", CROSS), ("e4", E4_MD),
                                          ("e3", E3), ("e5", E5), ("lockbox", LOCKBOX))},
        "q10": q10_coins(e0, e1),
        "survivors": survivor_changes(df, n_boot),
        "cross_section": cross_section_multi(df, n_boot),
        "e4": parse_e4((root / E4_MD).read_text()),
        "e3": e3_summary(json.loads((root / E3).read_text())),
        "e5": e5,
        "lockbox": lockbox_summary(root / LOCKBOX),
    }
    slope = {k: e5["models"]["pooled"][k] for k in ("repeat_rate", "acc_refit")}
    res["tick_accounting"] = {
        grp: {k: tick_accounting(res[grp][key], slope[k]) for k in slope}
        for grp, key in (("survivors", "ltick"), ("q10", "d_log_rel_tick"))}
    # the report's lock-box rule must agree with the one e5 stored at run time
    lb = res["lockbox"]
    if lb:
        for key, v in lb["final"]["verdict_e5_rule"].items():
            m, k = key.split("|")
            mine = q15_report.classify(lb["final"]["models"].get(m, {}).get(k, {}),
                                       e5["models"].get(m, {}).get(k, {}))
            if mine != v["verdict"]:
                raise AssertionError(f"lock-box rule disagrees on {key}: {mine} vs {v}")
    return _strip_draws(res)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=REPO)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    a = ap.parse_args(argv)
    out = a.out or a.root / OUT
    out.mkdir(parents=True, exist_ok=True)
    res = build_result(a.root, a.n_boot)
    res["verdict"] = q15_report.verdict_paragraph(res)
    (out / "q15_market_evolution.json").write_text(dumps_strict(res))
    q15_report.write_markdown(out / "q15_market_evolution.md", res)
    q15_report.plot(out / "q15_market_evolution.png", res)
    print(res["verdict"])


if __name__ == "__main__":
    main()
