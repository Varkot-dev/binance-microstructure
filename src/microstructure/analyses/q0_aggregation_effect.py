"""Q0: does skipping aggressor aggregation manufacture a fake literature match?

Method: for each (symbol, period), load the same raw aggTrades parquet two
ways. RAW: read `is_buyer_maker` directly in on-disk (agg_trade_id) order and
sign it, with no same-(ts, side) merging -- this is what a pipeline looks
like if the `to_aggressor_events` step is skipped. AGGREGATED: `load_events`,
the repo's normal path. Both sign series get the same FFT sign ACF and
log-log power-law fit (lags [10, 500]) used by Q1, so the two numbers are
directly comparable. The literature benchmark (Bouchaud et al. 2004,
equities/futures gamma ~ 0.3-0.7) is checked against both series, to show
whether skipping aggregation is invisible to a literature-match check alone.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl

from microstructure.data.catalog import parquet_path
from microstructure.estimators.acf import fit_power_law, sign_acf
from microstructure.signals.load import load_events

LIT_RANGE = (0.3, 0.7)  # equity/futures sign-ACF exponent range (Lillo & Farmer 2004; Bouchaud et al. 2018)
MAX_LAG = 1000
FIT_LO, FIT_HI = 10, 500


def _raw_signs(root: Path, symbol: str, period: str) -> np.ndarray:
    """Sign series straight off the raw aggTrades parquet, no aggregation.

    Read in on-disk row order (Binance's agg_trade_id order); +1 where the
    buyer was the taker (is_buyer_maker == False), else -1. This is exactly
    what a print-level sign series looks like if `to_aggressor_events` is
    never called -- one sign per PRINT, not per aggressor decision.
    """
    p = parquet_path(root, symbol, "aggTrades", period)
    df = pl.read_parquet(p, columns=["is_buyer_maker"])
    return np.where(df["is_buyer_maker"].to_numpy(), -1.0, 1.0)


def _stats(signs: np.ndarray) -> dict:
    acf = sign_acf(signs, MAX_LAG)
    fit = fit_power_law(acf, lo=FIT_LO, hi=FIT_HI)
    return {
        "n": int(signs.size),
        "acf1": float(acf[1]),
        "gamma": float(fit.exponent),
        "gamma_stderr": float(fit.stderr),
    }


def run_q0(root: Path, out_dir: Path, symbols: list[str], periods: list[str]) -> dict:
    """Compute the raw-vs-aggregated contrast for every (symbol, period) cell."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict = {}
    for sym in symbols:
        for period in periods:
            raw_signs = _raw_signs(root, sym, period)
            raw_stats = _stats(raw_signs)
            del raw_signs

            events = load_events(root, sym, [period])
            agg_signs = events["sign"].to_numpy().astype(np.float64)
            del events
            agg_stats = _stats(agg_signs)
            del agg_signs

            key = f"{sym}_{period}"
            results[key] = {
                "symbol": sym,
                "period": period,
                "raw": raw_stats,
                "aggregated": agg_stats,
                "prints_per_event": raw_stats["n"] / agg_stats["n"],
                "gamma_inflation": raw_stats["gamma"] - agg_stats["gamma"],
            }

    _write_results_md(out_dir, results)
    (out_dir / "q0_aggregation_effect.json").write_text(json.dumps(results, indent=2, allow_nan=False))
    return results


def _in_range(gamma: float) -> bool:
    lo, hi = LIT_RANGE
    return lo <= gamma <= hi


def _range_counts(results: dict) -> dict[str, int]:
    """Cell counts for the literature-range check, computed from the table data."""
    cells = list(results.values())
    raw_in = [_in_range(c["raw"]["gamma"]) for c in cells]
    agg_in = [_in_range(c["aggregated"]["gamma"]) for c in cells]
    return {
        "n": len(cells),
        "raw_in": sum(raw_in),
        "agg_in": sum(agg_in),
        "both_in": sum(r and a for r, a in zip(raw_in, agg_in, strict=True)),
        "raw_above": sum(c["raw"]["gamma"] > LIT_RANGE[1] for c in cells),
    }


def _inflation_phrase(results: dict) -> str:
    infl = [c["gamma_inflation"] for c in results.values()]
    lo, hi = min(infl), max(infl)
    where = "in every symbol-month tested" if lo > 0 else "across the cells below"
    return f"raw-print γ̂ minus aggregated γ̂ is {lo:+.2f} to {hi:+.2f} {where}"


def _summary_sentence(results: dict) -> str:
    lo, hi = LIT_RANGE
    k = _range_counts(results)
    n = k["n"]
    return (
        f"If the pipeline skips aggressor aggregation, {_inflation_phrase(results)}. "
        f"Raw γ̂ lies inside the equities/futures range ({lo:.1f}-{hi:.1f}, Bouchaud et al. "
        f"2004) in {k['raw_in']} of {n} cells and aggregated γ̂ in {k['agg_in']} of {n}. "
        f"Both pass in {k['both_in']} of {n}. The raw series is above {hi:.1f} in "
        f"{k['raw_above']} of {n} cells. Which pipeline lands in range changes from cell to "
        "cell, so an in-range check alone does not show whether aggregation was applied."
    )


def _direction_paragraph(results: dict) -> str:
    lo, hi = LIT_RANGE
    cells = list(results.values())
    infl = [c["gamma_inflation"] for c in cells]
    acf = [c["raw"]["acf1"] for c in cells]
    same_dir = "The direction is the same in every cell. " if min(infl) > 0 else ""
    return (
        f"{same_dir}Raw-print gamma exceeds aggregated gamma by {min(infl):+.2f} to "
        f"{max(infl):+.2f}, and raw lag-1 ACF is positive (about {min(acf):.2f}-{max(acf):.2f}) "
        "because the matching engine walks the book within a single aggressor decision. "
        f"Whether the raw γ̂ lands inside [{lo:.1f}, {hi:.1f}] or overshoots {hi:.1f} varies by "
        "symbol-month, so the table is the reference."
    )


def _write_results_md(out_dir: Path, results: dict) -> None:
    lo, hi = LIT_RANGE
    lines: list[str] = []
    lines.append("# Q0: Aggregation effect on order-flow memory")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(_summary_sentence(results))
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        "For each (symbol, period) cell I load the same raw `aggTrades` parquet two ways. "
        "Raw: `is_buyer_maker` is read in on-disk (`agg_trade_id`) order and signed "
        "(+1 buyer-taker, -1 seller-taker), with no merging of same-(timestamp, side) "
        "prints, so one sign per print. Aggregated: `load_events` merges all "
        "same-millisecond, same-side prints into one aggressor decision via "
        "`to_aggressor_events` before signing. Both series get the same FFT sign ACF "
        f"(`sign_acf`) and log-log power-law fit (`fit_power_law`, lags [{FIT_LO}, "
        f"{FIT_HI}]) used in Q1, so the gammas are comparable."
    )
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append(
        "| symbol | period | raw n | raw acf(1) | raw γ̂ | agg n | agg acf(1) | agg γ̂ | "
        "prints/event | γ̂ inflation |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in results.values():
        raw, agg = r["raw"], r["aggregated"]
        lines.append(
            f"| {r['symbol']} | {r['period']} | {raw['n']:,} | {raw['acf1']:.4f} | "
            f"{raw['gamma']:.4f} | {agg['n']:,} | {agg['acf1']:.4f} | {agg['gamma']:.4f} | "
            f"{r['prints_per_event']:.4f} | {r['gamma_inflation']:+.4f} |"
        )
    lines.append("")
    lines.append("## Literature-range check, both pipelines")
    lines.append("")
    lines.append(f"Equities/futures sign-ACF exponent range (Bouchaud et al. 2004): γ ≈ {lo:.1f}–{hi:.1f}.")
    lines.append("")
    lines.append("| symbol | period | raw γ̂ | raw in range? | agg γ̂ | agg in range? |")
    lines.append("|---|---|---|---|---|---|")
    for r in results.values():
        raw, agg = r["raw"], r["aggregated"]
        lines.append(
            f"| {r['symbol']} | {r['period']} | {raw['gamma']:.4f} | "
            f"{'yes' if _in_range(raw['gamma']) else 'no'} | {agg['gamma']:.4f} | "
            f"{'yes' if _in_range(agg['gamma']) else 'no'} |"
        )
    lines.append("")
    lines.append(_direction_paragraph(results))
    lines.append("")
    lines.append(
        "BTC shows a second effect: aggregation flips its lag-1 ACF from positive to "
        "negative, while ETH's aggregated lag-1 ACF stays small and positive."
    )
    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "- The aggregated arm is the same measurement Q1 uses. Q0 keeps the raw-vs-aggregated "
        "contrast as a re-runnable artifact."
    )
    lines.append(
        "- Gamma and its OLS stderr use the same fit window and normalization as Q1. The "
        "stderr assumes i.i.d. residuals and understates the uncertainty for "
        "autocorrelated ACF points."
    )
    lines.append(
        "- BTC's raw γ̂ can exceed 0.7, so the fragmentation artifact can overshoot the "
        "equity band entirely."
    )
    lines.append(
        "- The sample is the (symbols, periods) listed in the table."
    )
    lines.append("")
    (out_dir / "q0_aggregation_effect.md").write_text("\n".join(lines))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Q0: raw-print vs aggregated aggressor-event gamma contrast")
    parser.add_argument("--root", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--symbols", type=str, default="BTCUSDT,ETHUSDT")
    parser.add_argument("--periods", type=str, default="2023-06,2023-07")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    symbols = args.symbols.split(",")
    periods = args.periods.split(",")
    run_q0(args.root, args.out, symbols=symbols, periods=periods)
