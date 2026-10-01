"""Q5: kernel panel -- does critical balance hold across the crypto cross-section?

Method: for each symbol in the panel, load one week of aggTrades events
(filtered to [start_day 00:00, end_day 24:00)) and the matching bookTicker
quotes, join each event to the mid strictly before it (`events_with_prior_mid`),
and compute:

- gamma_week: the sign-ACF power-law exponent over the SAME week's trades
  (`fit_power_law(sign_acf(signs, 1000), 10, 500)`), Q1's order-flow-memory
  statistic.
- beta (+ beta_block_sd): the DECONVOLVED impact-kernel exponent, via
  `kernel_exponent_blocked` (Phase-2 Task 1's propagator deconvolution). This
  separates the bare kernel from the confound of order-flow memory that a
  naive read of the response function R(l) would mix in.
- R(l): the naive (non-deconvolved) response function, kept for reference and
  plotting alongside the deconvolved kernel.
- G(l): the deconvolved cumulative kernel (`cumulative_kernel` on the same
  `deconvolve_kernel` output `kernel_exponent_blocked` computes internally,
  recomputed here once more for the plot/record -- see `_symbol_kernel`).

The critical-balance relation (Bouchaud et al. 2004's propagator-diffusivity
constraint, also used as a plausibility check in Q2) predicts
beta = (1 - gamma_week) / 2 for a linear propagator whose accumulated
response grows no faster than diffusively. balance_delta = beta - (1-gamma)/2
measures the (signed) departure from that prediction for each symbol.

Judgement rule: |balance_delta| <= 2*max(beta_block_sd, 0.04) => "consistent",
else "violated". The 2x multiplier gives a two-sigma-style band around
beta_block_sd, the block-bootstrap uncertainty on beta (`propagator.py`
documents why fit_power_law's OLS stderr must NOT be used for this -- it
understates true uncertainty by roughly 6.8x on synthetic long-memory data).
The 0.04 floor is not an arbitrary safety margin: propagator.py's own
docstring measures a systematic finite-L bias of ~+0.03 to +0.04 in the
recovered beta at L=300 (20-seed Monte Carlo, fractional_signs d=0.35),
i.e. even a PERFECTLY balanced symbol's beta_hat will typically read ~0.03-
0.04 too high purely from finite-sample deconvolution bias. Without this
floor, a low-noise symbol (small beta_block_sd) with a genuinely-zero true
balance_delta could still be flagged "violated" by nothing more than that
known, already-quantified bias -- which would be a dishonest false positive.
Flooring the band at the measured bias scale is the honest choice: it says
"we cannot distinguish a departure smaller than our own method's known bias
from a departure of zero," rather than pretending false precision.

Symbols are processed one at a time; any per-symbol exception (missing
parquet, insufficient n/L ratio for `kernel_exponent_blocked`'s guard, no
events in range, etc.) is caught and logged into `failures`, and never
aborts the run for the remaining symbols.

Outputs: q5_kernel_panel.{json,md,png}. The PNG has two subplots: G(l)
log-log for all symbols (colored by log10(n_events)), and balance_delta vs
log10(n_events) with a zero line and a +-0.04 bias-floor band.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from microstructure.estimators.acf import fit_power_law, sign_acf
from microstructure.estimators.propagator import (
    cumulative_kernel,
    deconvolve_kernel,
    kernel_exponent_blocked,
    sign_price_cross_cov,
)
from microstructure.estimators.response import response_function
from microstructure.signals.load import events_with_prior_mid, load_book_ticker, load_events

GAMMA_FIT_LO = 10
GAMMA_FIT_HI = 500
GAMMA_ACF_MAX_LAG = 1000
BETA_FIT_LO = 5
BALANCE_BIAS_FLOOR = 0.04  # see module docstring: measured finite-L bias scale
N_RECORDED_LAGS = 100


def _daily_periods(start_day: str, end_day: str) -> list[str]:
    start = date.fromisoformat(start_day)
    end = date.fromisoformat(end_day)
    out = []
    d = start
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _symbol_kernel(signs: np.ndarray, dm: np.ndarray, max_lag: int) -> np.ndarray:
    """Recompute G(l) (deconvolved cumulative kernel) on the full sample.

    `kernel_exponent_blocked` runs this same (cross-cov, deconvolve,
    cumulative, fit) pipeline internally per block and on the full sample,
    but only returns the fitted exponent, not the intermediate G array.
    Recomputing it once more here on the full sample is cheap relative to
    the blocked computation itself (1 extra pass vs. n_blocks+1) and keeps
    `kernel_exponent_blocked`'s contract simple (exponent + uncertainty only).
    """
    b = sign_price_cross_cov(signs, dm, max_lag=max_lag)
    acf = sign_acf(signs, max_lag=max_lag - 1)
    kappa = deconvolve_kernel(b, acf, n_samples=signs.size)
    return cumulative_kernel(kappa)


def _judge_balance(balance_delta: float, beta_block_sd: float) -> str:
    threshold = 2 * max(beta_block_sd, BALANCE_BIAS_FLOOR)
    return "consistent" if abs(balance_delta) <= threshold else "violated"


def _symbol_record(
    root: Path, symbol: str, month: str, daily_periods: list[str], max_lag: int
) -> dict:
    events = load_events(root, symbol, [month])
    ts_min = datetime.combine(date.fromisoformat(daily_periods[0]), datetime.min.time(), tzinfo=UTC)
    ts_max = datetime.combine(
        date.fromisoformat(daily_periods[-1]) + timedelta(days=1), datetime.min.time(), tzinfo=UTC
    )
    events = events.filter((events["ts"] >= ts_min) & (events["ts"] < ts_max))
    n_events_prejoin = events.height
    if n_events_prejoin == 0:
        raise ValueError(f"no events in range {ts_min}..{ts_max}")

    bt = load_book_ticker(root, symbol, daily_periods)
    joined, n_dropped = events_with_prior_mid(events, bt)

    signs = joined["sign"].to_numpy()
    mids = joined["mid"].to_numpy()
    n_events = signs.size
    if n_events <= max_lag + 1:
        raise ValueError(
            f"joined series length {n_events} too short for max_lag {max_lag}"
        )

    # gamma_week: sign-ACF power-law exponent over the same week's trades.
    acf_full = sign_acf(signs, GAMMA_ACF_MAX_LAG)
    gamma_fit = fit_power_law(acf_full, lo=GAMMA_FIT_LO, hi=GAMMA_FIT_HI)

    # dm[t] = mids[t+1] - mids[t], the price change following event t; drop
    # the last event (no "after" mid to difference against).
    dm = np.diff(mids)
    signs_aligned = signs[:-1]

    blocked = kernel_exponent_blocked(
        signs_aligned, dm, max_lag=max_lag, fit_lo=BETA_FIT_LO, fit_hi=max_lag // 2
    )
    G = _symbol_kernel(signs_aligned, dm, max_lag)
    R = response_function(signs, mids, max_lag)

    balance_delta = blocked.exponent - (1 - gamma_fit.exponent) / 2
    verdict = _judge_balance(balance_delta, blocked.block_sd)

    return {
        "symbol": symbol,
        "n_events": n_events,
        "gamma_week": gamma_fit.exponent,
        "gamma_week_stderr": gamma_fit.stderr,
        "beta": blocked.exponent,
        "beta_block_sd": blocked.block_sd,
        "balance_delta": balance_delta,
        "verdict": verdict,
        "R1": float(R[1]),
        "response": R[:N_RECORDED_LAGS].tolist(),
        "G": G[:N_RECORDED_LAGS].tolist(),
        "drop_rate": n_dropped / n_events_prejoin,
    }


def run_q5(
    root: Path,
    out_dir: Path,
    symbols: list[str],
    month: str = "2023-06",
    start_day: str = "2023-06-01",
    end_day: str = "2023-06-07",
    max_lag: int = 300,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    daily_periods = _daily_periods(start_day, end_day)

    records: list[dict] = []
    failures: list[dict] = []
    for symbol in symbols:
        try:
            records.append(_symbol_record(root, symbol, month, daily_periods, max_lag))
        except Exception as e:  # noqa: BLE001 - per-symbol robustness is the point
            failures.append({"symbol": symbol, "reason": f"{type(e).__name__}: {e}"})

    n_consistent = sum(1 for r in records if r["verdict"] == "consistent")
    n_violated = sum(1 for r in records if r["verdict"] == "violated")

    result = {
        "month": month,
        "start_day": start_day,
        "end_day": end_day,
        "max_lag": max_lag,
        "n_symbols_requested": len(symbols),
        "n_symbols_successful": len(records),
        "n_symbols_failed": len(failures),
        "n_consistent": n_consistent,
        "n_violated": n_violated,
        "records": records,
        "failures": failures,
    }

    _plot(out_dir, records)
    _write_results_md(out_dir, result)
    (out_dir / "q5_kernel_panel.json").write_text(json.dumps(result, indent=2))
    return result


def _plot(out_dir: Path, records: list[dict]) -> None:
    fig, (ax_g, ax_delta) = plt.subplots(1, 2, figsize=(13, 5))

    if records:
        log_n = np.array([np.log10(r["n_events"]) for r in records])
        norm = plt.Normalize(vmin=log_n.min(), vmax=log_n.max()) if np.ptp(log_n) > 0 else None
        cmap = plt.get_cmap("viridis")

        for r, ln in zip(records, log_n, strict=True):
            color = cmap(norm(ln)) if norm is not None else cmap(0.5)
            G = np.array(r["G"])
            lags = np.arange(1, len(G))
            ax_g.loglog(lags, np.clip(np.abs(G[1:]), 1e-12, None), "-", color=color,
                        alpha=0.8, linewidth=1.2)

        if norm is not None:
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            fig.colorbar(sm, ax=ax_g, label="log10(n_events)")

        deltas = np.array([r["balance_delta"] for r in records])
        ax_delta.scatter(log_n, deltas, s=36, alpha=0.85, c=log_n, cmap=cmap)
        ax_delta.axhline(0.0, color="gray", linestyle="-", linewidth=1.0)
        ax_delta.axhspan(-BALANCE_BIAS_FLOOR, BALANCE_BIAS_FLOOR, color="gray", alpha=0.15,
                          label=f"±{BALANCE_BIAS_FLOOR:.2f} bias floor")
        ax_delta.legend()

    ax_g.set_xlabel("lag ℓ (events)")
    ax_g.set_ylabel("|G(ℓ)| (deconvolved cumulative kernel)")
    ax_g.set_title("Deconvolved kernel, all panel symbols")

    ax_delta.set_xlabel("log10(n_events)")
    ax_delta.set_ylabel(r"balance $\Delta = \hat\beta - (1-\hat\gamma_{week})/2$")
    ax_delta.set_title("Critical-balance residual vs. activity")

    fig.tight_layout()
    fig.savefig(out_dir / "q5_kernel_panel.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _write_results_md(out_dir: Path, result: dict) -> None:
    records = result["records"]
    lines: list[str] = []
    lines.append("# Q5: kernel panel, critical balance across the cross-section")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        f"For each symbol in the panel I load one week of aggTrades "
        f"({result['start_day']}..{result['end_day']}, from the monthly period "
        f"`{result['month']}`) and join each event to the bookTicker mid strictly before "
        "it (`events_with_prior_mid`). A per-symbol failure (missing parquet, no events in "
        "range, or the n/L≥100 sample-sufficiency guard in `kernel_exponent_blocked`) is "
        "logged in `failures` and does not abort the run."
    )
    lines.append("")
    lines.append(
        "**gamma_week**: the sign-ACF power-law exponent over the same week "
        "(`fit_power_law(sign_acf(signs, 1000), lo=10, hi=500)`), the Q1 statistic."
    )
    lines.append(
        "**beta (deconvolved kernel exponent)**: `kernel_exponent_blocked` recovers the "
        "bare impact kernel by solving the Toeplitz system `sign_price_cross_cov = "
        "sign_ACF ⊛ kappa`, which separates the kernel from the order-flow memory that "
        "R(ℓ) mixes in. For uncertainty I use `beta_block_sd` (block-bootstrap sd over 5 "
        "contiguous blocks), not the fit's OLS stderr, which the `propagator.py` "
        "docstring measures as understating the uncertainty by roughly 6.8x on synthetic "
        "long-memory data."
    )
    lines.append(
        "**Critical balance**: the Bouchaud et al. (2004) propagator-diffusivity relation "
        "predicts beta = (1 - gamma_week) / 2 for a linear propagator whose accumulated "
        "response grows no faster than diffusively (dm[t] = sum_n kappa[n] * signs[t-n] + "
        "noise; see the `propagator.py` module docstring). balance_delta = beta - "
        "(1-gamma_week)/2 is the signed departure per symbol."
    )
    lines.append("")
    lines.append(
        "**Judgement rule**: |balance_delta| <= 2*max(beta_block_sd, 0.04) => "
        "\"consistent\", else \"violated\". The 0.04 floor is the finite-L bias of roughly "
        "+0.03 to +0.04 in the recovered beta at L=300 that the `kernel_exponent_blocked` "
        "docstring reports (20-seed Monte Carlo on `fractional_signs(d=0.35)`). Without "
        "the floor, a low-noise symbol with a truly zero balance_delta could be flagged "
        "\"violated\" by that bias alone. Departures smaller than the bias cannot be "
        "distinguished from zero."
    )
    lines.append("")
    lines.append("## Run summary")
    lines.append("")
    lines.append(
        f"Requested: {result['n_symbols_requested']}. Successful: "
        f"{result['n_symbols_successful']}. Failed: {result['n_symbols_failed']}. "
        f"Of the successful symbols: **{result['n_consistent']} consistent**, "
        f"**{result['n_violated']} violated**."
    )
    lines.append("")

    if records:
        sorted_records = sorted(records, key=lambda r: r["n_events"], reverse=True)
        lines.append("## Panel table (sorted by n_events)")
        lines.append("")
        lines.append(
            "| symbol | n_events | γ̂_week | β̂ | β̂ block_sd | Δ (balance) | verdict | "
            "R(1) | drop_rate |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in sorted_records:
            lines.append(
                f"| {r['symbol']} | {r['n_events']:,} | {r['gamma_week']:.4f} | "
                f"{r['beta']:.4f} | {r['beta_block_sd']:.4f} | {r['balance_delta']:+.4f} | "
                f"{r['verdict']} | {r['R1']:.3e} | {r['drop_rate']:.4%} |"
            )
        lines.append("")
    else:
        lines.append("No symbols produced usable results, so there is no table.")
        lines.append("")

    lines.append("## Findings")
    lines.append("")
    if records:
        frac_consistent = result["n_consistent"] / len(records)
        if result["n_violated"] == 0:
            lines.append(
                f"All {len(records)} successful panel symbols land within the balance "
                "band: the relation beta = (1-gamma_week)/2 **holds across this "
                "cross-section** at the bias-floored tolerance. That is consistent with a "
                "linear propagator model applying across the panel; see Caveats for what "
                "the test cannot rule out."
            )
        elif result["n_consistent"] == 0:
            lines.append(
                f"All {len(records)} successful panel symbols land outside the balance "
                "band: the relation **fails systematically** across this cross-section, "
                "not just for isolated symbols. The linear propagator model's diffusivity "
                "constraint does not hold uniformly for this panel and period."
            )
        else:
            lines.append(
                f"{result['n_consistent']} of {len(records)} symbols "
                f"({frac_consistent:.0%}) land within the balance band and "
                f"{result['n_violated']} do not, so critical balance holds for some but "
                "not all of the panel. Whether the split tracks activity (n_events) or "
                "other symbol characteristics is visible in the panel table. I assert no "
                f"such relation beyond the table, since {len(records)} points are too few "
                "to fit a reliable trend."
            )
    else:
        lines.append("No successful symbols in this run, so there is no finding.")
    lines.append("")

    if result["failures"]:
        lines.append("## Failures")
        lines.append("")
        lines.append("| symbol | reason |")
        lines.append("|---|---|")
        for f in result["failures"]:
            lines.append(f"| {f['symbol']} | {f['reason']} |")
        lines.append("")

    lines.append("## Caveats")
    lines.append("")
    lines.append(
        f"- **7-day window** ({result['start_day']}..{result['end_day']}): one week in "
        "one market regime. Order-flow memory statistics are regime-dependent (see Q8), "
        "so these results may not carry over to other weeks or volatility regimes."
    )
    lines.append(
        "- **L1 mids only**: the mid is the best-bid/best-ask midpoint from bookTicker. "
        "No order-book depth is used, so impact through queue depletion or hidden "
        "liquidity is not captured."
    )
    lines.append(
        "- **Linear-propagator assumption**: the deconvolved beta relies on the model "
        "dm[t] = sum_n kappa[n]*signs[t-n] + noise, in which each signed event's impact "
        "superposes additively and linearly. If real impact is nonlinear (saturating, or "
        "dependent on spread or depth), beta is an artifact of the linear model. The "
        "critical-balance relation beta = (1-gamma)/2 is also a linear/diffusive "
        "prediction (Bouchaud et al. 2004). A \"violated\" verdict fits both (a) nonlinear "
        "true impact and (b) a linear model whose beta-gamma relationship differs from the "
        "diffusivity constraint. This analysis cannot tell them apart."
    )
    lines.append(
        "- **0.04 bias floor**: the measured finite-L deconvolution bias at L=300 from the "
        "synthetic validation. The bias at this panel's max_lag "
        f"({result['max_lag']}) may differ."
    )
    lines.append(
        "- **beta_block_sd** uses only 5 contiguous non-overlapping blocks per symbol. "
        "With so few blocks it is a noisy uncertainty estimate and not a formal "
        "confidence interval."
    )
    lines.append("")
    (out_dir / "q5_kernel_panel.md").write_text("\n".join(lines))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Q5: kernel panel analysis")
    parser.add_argument("--root", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--symbols-file", type=Path, required=True,
                         help="one symbol per line")
    parser.add_argument("--month", type=str, default="2023-06")
    parser.add_argument("--start-day", type=str, default="2023-06-01")
    parser.add_argument("--end-day", type=str, default="2023-06-07")
    parser.add_argument("--max-lag", type=int, default=300)
    return parser.parse_args(argv)


def _read_symbols_file(path: Path) -> list[str]:
    lines = path.read_text().splitlines()
    return [s.strip() for s in lines if s.strip()]


if __name__ == "__main__":
    args = _parse_args()
    symbols = _read_symbols_file(args.symbols_file)
    run_q5(
        args.root, args.out, symbols=symbols, month=args.month,
        start_day=args.start_day, end_day=args.end_day, max_lag=args.max_lag,
    )
