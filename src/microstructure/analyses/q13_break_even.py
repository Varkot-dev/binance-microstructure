"""Q13: how far is the Q11 mid-direction edge from break-even, and is it worth
anything to a trader who must trade anyway?

Q11 found that the direction of the next mid-price change is predictable out
of sample but that the gross edge never covers a round-trip taker cost. Q13
turns that "no" into numbers, using only Q11's cached test-window predictions:
nothing is refitted and no new data is read.

Method
1. Cache. For each symbol the predictions are read from
   data/ml_cache/q11/<SYMBOL>/pred_<key>.npz, where <key> is what Q11's own
   `config_key` gives for its default run config and today's `fit_settings()`.
   Older keys (for example from before the tick-size fix) are never used; a
   symbol whose current key is missing is skipped with a reason.
2. Cut-offs. Q11 fixed its confidence cut-offs (the most confident 100%, 50%,
   20% and 5% of samples, ranked by |P(up) - P(down)|) on the validation days
   and stored them in meta_<key>.json. Q13 reads those stored thresholds and
   applies them unchanged; the "all" cut-off is the rule P(up) - P(down) != 0,
   which needs no data. Nothing is chosen on the test window.
3. Part A, break-even. Per cell (symbol x horizon x model x cut-off) the gross
   edge and the spread cost come from Q11's `_economics`, so they are Q11's
   numbers by construction; they are also checked against Q11's JSON. The
   break-even taker fee per side is (gross - spread cost) / 2, with the 95%
   day-block interval of mean(gross - spread) halved.
4. Part B, timing. A trader must buy or sell one unit at sample i. If the
   model predicts that the mid will move in the trader's favour (down for a
   buyer, up for a seller), the trader waits h events and trades then;
   otherwise now. The saving against always trading now, in bps of the mid,
   is the mid move in the trader's favour on the delayed orders and zero on
   the others. Buyers and sellers get equal weight, so the mean saving per
   order is half the mean of sign(score) x move over the fired samples times
   their share. It is compared with perfect foresight (wait exactly when the
   mid moves in the trader's favour) and a random wait with the model's delay
   rate. The cached spread is the sum of the half spreads at i and i+h, so the
   spread at the delayed time cannot be separated: the saving is mid-only.

Stages. `load_q11_predictions` finds and reads the cache; `score_symbol`
turns one symbol's predictions into every reported number; `check_against_q11`
compares with Q11's JSON and stops the run on a mismatch. Formatting lives in
`q13_report`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from microstructure.analyses import q11_mid_direction as q11
from microstructure.ml.evaluate import MS_PER_DAY, day_block_ci

TAKER_FEE_BPS = q11.TAKER_FEE_BPS
N_BOOT = q11.N_BOOT
SEED = 0  # Q11 uses seed 0 for every day-block interval; the same seed reproduces them.
DEFAULT_SYMBOLS = q11.DEFAULT_SYMBOLS
LEARNED = q11.LEARNED
TOP_FRACTIONS = q11.TOP_FRACTIONS
# The run config of Q11's command-line defaults (its `main`), which is what its
# committed results were produced with.
Q11_DEFAULT_CONFIG = {
    "train_start": "2023-06-05", "train_end": "2023-06-18",
    "test_start": "2023-07-03", "test_end": "2023-07-16",
    "valid_days": q11.VALID_DAYS, "embargo_days": q11.EMBARGO_DAYS,
    "horizons": sorted(q11.HORIZONS),
}
# Absolute tolerance (bps) when comparing with Q11's JSON; both sides come from
# the same float32 cache and the same code, so any real difference is large.
CHECK_TOL = 1e-9


# --------------------------------------------------------------------------
# Stage 1: find and read the Q11 cache
# --------------------------------------------------------------------------


def load_q11_predictions(cache: Path, symbol: str, cfg: dict) -> tuple[dict, dict] | str:
    """(meta, arrays) for the current Q11 key, or the reason it cannot be used."""
    key = q11.config_key(cfg)
    loaded = q11.load_cached(cache, symbol, cfg)
    if loaded is None:
        others = sorted(p.stem.removeprefix("pred_") for p in (cache / symbol).glob("pred_*.npz"))
        listing = ", ".join(others) if others else "none"
        return (f"no Q11 predictions under the current key {key} "
                f"(other keys on disk, not used: {listing})")
    meta, arrays = loaded
    for h in cfg["horizons"]:
        th = meta.get("horizons", {}).get(str(h), {}).get("thresholds", {})
        missing = [m for m in LEARNED if m not in th
                   or any(f"{q:g}" not in th[m] for q in TOP_FRACTIONS)]
        if missing:
            return f"meta_{key}.json has no validation-day cut-offs for h = {h}, {missing}"
    return meta, arrays


# --------------------------------------------------------------------------
# Stage 2: one symbol's predictions -> reported numbers
# --------------------------------------------------------------------------


def classify(break_even_fee: float | None, fee_bps: float) -> str:
    """'pays_at_fee', 'pays_below_fee' or 'no_pay' for one break-even fee per side."""
    if break_even_fee is None or break_even_fee <= 0:
        return "no_pay"
    return "pays_at_fee" if break_even_fee > fee_bps else "pays_below_fee"


def break_even_rows(
    p: dict[str, np.ndarray], model: str, thresholds: dict[str, float], fee_bps: float,
    n_boot: int, seed: int = SEED,
) -> list[dict]:
    """Q11's economics rows for one model, plus the break-even fee per side."""
    rows = q11._economics(p, model, thresholds, fee_bps, n_boot, seed)
    out = []
    for r in rows:
        row = {"top_fraction": r["top_fraction"], "threshold": thresholds[f"{r['top_fraction']:g}"],
               "n": r["n"], "share_of_test": r["share_of_test"]}
        if r["n"]:
            gross, spread = r["gross_bps"], r["spread_cost_bps"]
            # net = mean(gross - spread) - 2 fee, so adding the fees back and
            # halving gives the fee per side at which the cell breaks even.
            be = (r["net_bps"] + 2.0 * fee_bps) / 2.0
            be_ci = [(x + 2.0 * fee_bps) / 2.0 for x in r["net_ci95"]]
            row.update({
                "gross_bps": gross, "gross_ci95": r["gross_ci95"],
                "spread_cost_bps": spread, "cost_bps": r["cost_bps"],
                "hit_rate": r["hit_rate"],
                "net_bps": r["net_bps"], "net_ci95": r["net_ci95"],
                "break_even_fee_bps": be, "break_even_fee_ci95": be_ci,
                "pays_at_zero_fee": bool(gross > spread),
                "pays_at_fee": bool(be > fee_bps),
                "required_multiple": r["cost_bps"] / gross if gross > 0 else None,
                "required_multiple_zero_fee": spread / gross if gross > 0 else None,
                "category": classify(be, fee_bps),
            })
        out.append(row)
    return out


def _ci_dict(c) -> dict:
    return {"estimate": c.estimate, "ci95": [c.lo, c.hi], "n_days": c.n_days}


def _order_savings(fired: np.ndarray, side: np.ndarray, move: np.ndarray) -> np.ndarray:
    """Saving of every order, buyers then sellers, in bps of the mid.

    `side` is +1 where the policy delays the seller (mid expected up) and -1
    where it delays the buyer (mid expected down). A delayed seller gains
    +move, a delayed buyer gains -move; an order traded now saves 0.
    """
    buyer = np.where(fired & (side < 0), -move, 0.0)
    seller = np.where(fired & (side > 0), move, 0.0)
    return np.concatenate([buyer, seller])


def timing_stats(fired: np.ndarray, side: np.ndarray, move: np.ndarray, ts: np.ndarray,
                 half_spread_bps: float, n_boot: int, seed: int = SEED) -> dict:
    """Saving of the wait-or-trade-now policy against always trading now.

    Per sample there is one buyer and one seller, equally weighted, and at
    most one of them is delayed, so the per-sample mean saving is
    0.5 x fired x side x move, and its day-block interval resamples days of samples.
    """
    per_sample = 0.5 * np.where(fired, side * move, 0.0)
    c = day_block_ci(per_sample, None, ts, n_boot=n_boot, seed=seed)
    orders = _order_savings(fired, side, move)
    delayed = side[fired] * move[fired]
    return {
        "share_delayed": float(0.5 * fired.mean()) if fired.size else 0.0,
        "n_delayed": int(fired.sum()),
        "saving": _ci_dict(c),
        "sd_per_order": float(orders.std()) if orders.size else 0.0,
        "saving_when_delayed": float(delayed.mean()) if delayed.size else None,
        "sd_when_delayed": float(delayed.std()) if delayed.size else None,
        "share_worse_when_delayed": float((delayed < 0).mean()) if delayed.size else None,
        "saving_over_half_spread": (c.estimate / half_spread_bps
                                    if half_spread_bps > 0 else None),
    }


def timing_horizon(
    p: dict[str, np.ndarray], thresholds: dict[str, dict[str, float]], n_boot: int,
    seed: int = SEED,
) -> dict:
    """Part B for one symbol and horizon: every model and cut-off, plus the two baselines."""
    move = p["move_bps"].astype(np.float64)
    spread = p["spread_bps"].astype(np.float64)
    ts = p["ts"]
    # The cached spread is half(i) + half(i+h); its mean halved is the average
    # of the entry and exit half spreads, the only half-spread figure available.
    half = float(spread.mean() / 2.0) if spread.size else 0.0
    perfect = timing_stats(move != 0, np.sign(move), move, ts, half, n_boot, seed)
    out: dict = {"mean_half_spread_bps": half, "perfect_foresight": perfect, "models": {}}
    rng = np.random.default_rng(seed + 1)
    u, coin = rng.random(move.size), rng.random(move.size)
    rand_side = np.where(coin < 0.5, -1.0, 1.0)
    for m in LEARNED:
        s = q11.signed_score(p[f"{m}_move"].astype(np.float64), p[f"{m}_up"].astype(np.float64))
        rows = []
        for q in TOP_FRACTIONS:
            thr = thresholds[m][f"{q:g}"]
            fired = (np.abs(s) >= thr) & (s != 0)
            row = {"top_fraction": q, "threshold": thr,
                   **timing_stats(fired, np.sign(s), move, ts, half, n_boot, seed)}
            # Random wait: the same delay rate, a coin for the side, no information.
            rfired = u < fired.mean()
            rnd = timing_stats(rfired, rand_side, move, ts, half, n_boot, seed)
            row["random"] = {k: rnd[k] for k in ("share_delayed", "saving", "sd_per_order")}
            ps = perfect["saving"]["estimate"]
            row["share_of_perfect"] = row["saving"]["estimate"] / ps if ps > 0 else None
            rows.append(row)
        out["models"][m] = rows
    return out


def score_symbol(meta: dict, arrays: dict[str, np.ndarray], fee_bps: float,
                 n_boot: int = N_BOOT) -> dict:
    horizons = {}
    for h, info in meta["horizons"].items():
        prefix = f"h{h}_"
        p = {k[len(prefix):]: v for k, v in arrays.items() if k.startswith(prefix)}
        th = info["thresholds"]
        horizons[h] = {
            "n_test": int(p["label"].size),
            "n_test_days": int(np.unique(p["ts"] // MS_PER_DAY).size),
            "break_even": {m: break_even_rows(p, m, th[m], fee_bps, n_boot) for m in LEARNED},
            "timing": timing_horizon(p, th, n_boot),
        }
    return {
        "symbol": meta["symbol"], "tick": meta["tick"],
        "one_tick_time_share": meta["spread"]["one_tick_time_share"],
        "test_days": meta["test_days"], "valid_days": meta["valid_days"],
        "horizons": horizons,
    }


# --------------------------------------------------------------------------
# Check against Q11's own JSON
# --------------------------------------------------------------------------


def check_against_q11(symbols: list[dict], q11_summary: dict | None, fee_bps: float,
                      n_boot: int) -> dict:
    """Compare every break-even cell with Q11's economics table.

    Compared: n, gross edge, spread cost, the gross interval and, through
    net + 2 x fee, the net interval (the latter two only when the resample
    counts agree). Returns per-model maximum absolute differences and the
    cells that differ by more than CHECK_TOL.
    """
    if q11_summary is None:
        return {"status": "not_checked", "reason": "Q11 JSON not found", "by_model": {},
                "mismatches": []}
    q11_fee = q11_summary["config"]["taker_fee_bps"]
    same_boot = q11_summary["config"].get("n_boot") == n_boot
    by_symbol = {s["symbol"]: s for s in q11_summary["symbols"]}
    by_model: dict[str, dict] = {m: {"n_cells": 0, "max_abs_diff_bps": 0.0} for m in LEARNED}
    mismatches = []
    for s in symbols:
        ref = by_symbol.get(s["symbol"])
        if ref is None:
            mismatches.append({"symbol": s["symbol"], "reason": "symbol not in Q11 JSON"})
            continue
        for h, res in s["horizons"].items():
            for m in LEARNED:
                for mine, theirs in zip(res["break_even"][m],
                                        ref["horizons"][h]["economics"][m], strict=True):
                    cell = {"symbol": s["symbol"], "horizon": int(h), "model": m,
                            "top_fraction": mine["top_fraction"]}
                    if mine["n"] != theirs["n"]:
                        mismatches.append({**cell, "reason": f"n {mine['n']} vs {theirs['n']}"})
                        continue
                    if not mine["n"]:
                        continue
                    pairs = [(mine["gross_bps"], theirs["gross_bps"]),
                             (mine["spread_cost_bps"], theirs["spread_cost_bps"])]
                    if same_boot:
                        pairs += list(zip(mine["gross_ci95"], theirs["gross_ci95"], strict=True))
                        pairs += [(a + 2 * fee_bps, b + 2 * q11_fee) for a, b in
                                  zip(mine["net_ci95"], theirs["net_ci95"], strict=True)]
                    diff = max(abs(a - b) for a, b in pairs)
                    by_model[m]["n_cells"] += 1
                    by_model[m]["max_abs_diff_bps"] = max(by_model[m]["max_abs_diff_bps"], diff)
                    if diff > CHECK_TOL:
                        mismatches.append({**cell, "reason": f"differs by {diff:.3g} bps"})
    return {"status": "matched" if not mismatches else "mismatch",
            "intervals_compared": same_boot, "tolerance_bps": CHECK_TOL,
            "by_model": by_model, "mismatches": mismatches}


# --------------------------------------------------------------------------
# Verdict
# --------------------------------------------------------------------------


def _cells(symbols: list[dict]) -> list[dict]:
    return [
        {"symbol": s["symbol"], "horizon": int(h), "model": m, **r}
        for s in symbols for h, res in s["horizons"].items()
        for m, rows in res["break_even"].items() for r in rows if r["n"] > 0
    ]


def verdict(symbols: list[dict], fee_bps: float) -> dict:
    cells = _cells(symbols)
    per_symbol = []
    for s in symbols:
        mine = [c for c in cells if c["symbol"] == s["symbol"]]
        best = max(mine, key=lambda c: c["break_even_fee_bps"]) if mine else None
        timing = [
            {"horizon": int(h), "model": m, **r,
             "perfect_foresight": res["timing"]["perfect_foresight"],
             "mean_half_spread_bps": res["timing"]["mean_half_spread_bps"]}
            for h, res in s["horizons"].items()
            for m, rows in res["timing"]["models"].items() for r in rows
        ]
        best_t = max(timing, key=lambda r: r["saving"]["estimate"]) if timing else None
        per_symbol.append({
            "symbol": s["symbol"], "best_break_even": best,
            "category": classify(best["break_even_fee_bps"] if best else None, fee_bps),
            "best_timing": best_t,
        })
    return {
        "n_cells": len(cells),
        "n_pays_at_fee": sum(c["pays_at_fee"] for c in cells),
        "n_pays_at_zero_fee": sum(c["pays_at_zero_fee"] for c in cells),
        "best": max(cells, key=lambda c: c["break_even_fee_bps"]) if cells else None,
        "per_symbol": per_symbol,
    }


# --------------------------------------------------------------------------
# Q7 context (quoted from its results file, not recomputed)
# --------------------------------------------------------------------------


def q7_context(path: Path, symbols: list[str]) -> dict | None:
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    ev = d["evaluation"]
    return {
        "source": path.name, "month": d.get("month"), "days": ev["days"],
        "horizon_events": d["horizon_events"], "n_children": d["n_children"],
        "unit": d.get("shortfall_unit"),
        "summary": {k: ev["summary"][k] for k in ("twap", "frontloaded", "reactive")},
        "reactive_minus_twap": ev["summary"]["reactive_minus_twap"],
        "per_symbol": [r for r in ev["per_symbol"] if r["symbol"] in symbols],
    }


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def run_q13(root: Path, out: Path, symbols: list[str], fee_bps: float = TAKER_FEE_BPS,
            n_boot: int = N_BOOT, cache: Path | None = None, cfg: dict | None = None,
            q11_json: Path | None = None, q7_json: Path | None = None) -> dict:
    from microstructure.analyses.q13_report import write_outputs

    cfg = cfg or Q11_DEFAULT_CONFIG
    cache = cache or root / "ml_cache" / "q11"
    q11_json = q11_json or out / "q11_mid_direction.json"
    q7_json = q7_json or out / "q7_execution.json"
    results, skipped = [], []
    for symbol in symbols:
        loaded = load_q11_predictions(cache, symbol, cfg)
        if isinstance(loaded, str):
            skipped.append({"symbol": symbol, "reason": loaded})
            continue
        print(f"[q13] scoring {symbol}", flush=True)
        results.append(score_symbol(*loaded, fee_bps=fee_bps, n_boot=n_boot))
    q11_summary = json.loads(q11_json.read_text()) if q11_json.exists() else None
    check = check_against_q11(results, q11_summary, fee_bps, n_boot)
    if check["status"] == "mismatch":
        # Every later number rests on these matching; do not write a report that
        # silently disagrees with Q11.
        raise RuntimeError(f"Q13 does not reproduce Q11's economics table: {check['mismatches'][:5]}")
    summary = {
        "config": {
            "taker_fee_bps": fee_bps, "n_boot": n_boot, "q11_config": cfg,
            "q11_cache_key": q11.config_key(cfg), "horizons": cfg["horizons"],
            "models": list(LEARNED), "top_fractions": list(TOP_FRACTIONS),
        },
        "symbols": results,
        "skipped": skipped,
        "q11_check": check,
        "verdict": verdict(results, fee_bps),
        "q7": q7_context(q7_json, [s["symbol"] for s in results]),
    }
    write_outputs(summary, out)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--cache", type=Path, default=None,
                    help="Q11 cache directory (default: <root>/ml_cache/q11)")
    ap.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    ap.add_argument("--fee-bps", type=float, default=TAKER_FEE_BPS,
                    help="assumed taker fee per side in basis points")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    a = ap.parse_args()
    summary = run_q13(a.root, a.out, a.symbols, a.fee_bps, a.n_boot, cache=a.cache)
    v = summary["verdict"]
    print(f"[q13] {len(summary['symbols'])} symbol(s), {len(summary['skipped'])} skipped; "
          f"Q11 check: {summary['q11_check']['status']}; {v['n_pays_at_fee']} of {v['n_cells']} "
          f"cells pay at {a.fee_bps:g} bps, {v['n_pays_at_zero_fee']} at zero fee")


if __name__ == "__main__":
    main()
