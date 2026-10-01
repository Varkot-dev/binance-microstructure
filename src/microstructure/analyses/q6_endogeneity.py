"""Q6: branching-ratio panel, a Hawkes endogeneity cross-section on crypto.

Method: for each symbol, load one month of aggTrades (`load_events`),
extract event timestamps as int64 epoch-ms, estimate the intraday rate
profile (`intraday_rate_profile`, 48 bins) and rescale to business time
(`rescale_to_business_time`) before any Hawkes fitting. Fitting a Hawkes MLE
(or the count-variance estimator) on clock time cannot separate
self-excitation from a time-varying, non-self-exciting baseline rate: a
regime-switching Poisson process with no self-excitation produces a
spurious n̂ around 0.5-0.9 under both estimators (Filimonov & Sornette
2015; `tests/estimators/test_hawkes.py::
test_regime_switching_poisson_produces_spurious_endogeneity_trap` shows
n_hat > 0.2 and fitted alpha > 0.5 on such a process, and every crypto
symbol has an intraday U-shape / funding-hour pattern at least that strong).
The standard fix is the deterministic time change tau(t) = integral_0^t
rate(s) ds, under which a non-stationary-rate Poisson process becomes
homogeneous, so a Hawkes fit on tau(events) is not confounded by the daily
cycle.

Per symbol: the business-time series is split into K equal-width contiguous
sub-windows (`--windows`, default 6). Each is fit independently via
`fit_hawkes_exp` on (business_times - window_start). Runtime cap: if a
window holds more than `MAX_FIT_EVENTS` (250,000) events, the fit uses only
the first 250,000, which bounds the O(N log N) MLE cost; in the synthetic
tests, alpha from a single 250k-event fit has sd ~0.004 across seeds, so the
subsampling does not materially widen the uncertainty on alpha_median across
the 6 windows. alpha and convergence are recorded per window.

Seasonality-bias measurement: one extra fit on raw clock time (not
rescaled) for the first sub-window only, with the same event range and cap.
raw_delta = alpha_raw - alpha_rescaled_window1 is the per-symbol size of the
seasonality bias in a naive clock-time alpha.

Count-variance n_hat: computed once per symbol on the full business-time
series (not per window) via `branching_count_variance`, with
window_bt = COUNT_VARIANCE_WINDOW_BT (200 seconds of business time).

Cross-section: OLS of alpha_median on log10(n_events) (`np.polyfit`, with
intercept — no reason to expect alpha to vanish at zero activity); and
MLE-vs-count-variance agreement stats (median |alpha_median - alpha_cv|,
Pearson correlation) across the successful symbols.

Symbols are processed one at a time; a per-symbol exception (missing
parquet, insufficient events for the guards below, etc.) is logged into
`failures` and does not abort the run.

Outputs: q6_endogeneity.{json,md,parquet,png}. The PNG has two panels:
alpha_median vs log10(n_events) with sub-window-IQR errorbars, and an
MLE-vs-count-variance scatter with a y=x reference line.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from microstructure.analyses.q4_cross_section import SLOPE_MIN_SE, slope_is_distinguishable, slope_t
from microstructure.data.catalog import parquet_path
from microstructure.estimators.hawkes import branching_count_variance, fit_hawkes_exp
from microstructure.signals.eventtime import intraday_rate_profile, rescale_to_business_time
from microstructure.signals.load import load_events

N_BINS = 48  # intraday_rate_profile bin count

# Runtime cap on events per Hawkes MLE fit: fit_hawkes_exp's O(N log N)
# recursion (5 Nelder-Mead starts, ~500 iterations each) dominates per-symbol
# cost well before 250k events. Fitted alpha's cross-seed sd at similar sample
# sizes is ~0.004-0.02 (test_mle_alpha_stable_across_seeds), so truncating to
# the first 250k events costs little sampling noise and bounds fit time.
MAX_FIT_EVENTS = 250_000

# Count-variance window: must be >> 1/beta (the kernel decay timescale,
# typically ~0.1-2s of business time for liquid crypto aggressor flow) for the
# large-window asymptotic var(N_W)/mean(N_W) -> 1/(1-n)^2 to hold; short
# windows bias n_hat toward 0 (see `branching_count_variance`). The default is
# 200 business seconds. If a symbol's median fitted beta makes that too short
# (200 <= 20/median_beta), the window widens to 100/median_beta so a slowly
# decaying kernel does not silently understate n_hat.
COUNT_VARIANCE_WINDOW_BT_DEFAULT = 200.0
COUNT_VARIANCE_WINDOW_SAFETY_MULT = 20.0
COUNT_VARIANCE_WINDOW_FALLBACK_MULT = 100.0


def _fit_capped(times: np.ndarray, t_end: float) -> tuple[float, float, float, bool]:
    """Fit Hawkes MLE on `times`, capping to the first MAX_FIT_EVENTS if needed.

    Returns (mu, alpha, beta, converged). `t_end` must correspond to the
    (possibly truncated) `times` array passed in — the caller is
    responsible for cropping t_end to the last used event's containing
    window, not the full original window, when capping is applied.
    """
    if times.size > MAX_FIT_EVENTS:
        times = times[:MAX_FIT_EVENTS]
        t_end = float(times[-1])
    fit = fit_hawkes_exp(times, t_end)
    return fit.mu, fit.alpha, fit.beta, fit.converged


def _window_edges(bt: np.ndarray, windows: int) -> np.ndarray:
    """K+1 equal-width business-time edges spanning [bt[0], bt[-1]]."""
    return np.linspace(bt[0], bt[-1], windows + 1)


def _fit_business_time_windows(
    bt: np.ndarray, windows: int
) -> tuple[list[float], list[bool], list[float], list[float]]:
    """Fit each of K equal contiguous business-time sub-windows independently.

    Returns (alphas, converged_flags, betas, mus), each length `windows`.
    Windows with fewer than 2 events (can't fit) raise, since a symbol thin
    enough to leave a sub-window under 2 events is too thin for a reliable
    6-window panel entry — the caller's outer try/except turns this into a
    documented per-symbol failure rather than a silent skip.
    """
    edges = _window_edges(bt, windows)
    alphas: list[float] = []
    converged: list[bool] = []
    betas: list[float] = []
    mus: list[float] = []

    for i in range(windows):
        lo, hi = edges[i], edges[i + 1]
        mask = (bt >= lo) & (bt <= hi) if i == windows - 1 else (bt >= lo) & (bt < hi)
        window_times = bt[mask] - lo
        if window_times.size < 2:
            raise ValueError(f"sub-window {i} has only {window_times.size} events, need >= 2")
        t_end = float(window_times[-1])
        if t_end <= 0.0:
            raise ValueError(f"sub-window {i} has zero-length business-time span")
        mu, alpha, beta, conv = _fit_capped(window_times, t_end)
        alphas.append(alpha)
        converged.append(conv)
        betas.append(beta)
        mus.append(mu)

    return alphas, converged, betas, mus


def _raw_clock_time_first_window_alpha(ts_ms: np.ndarray, bt: np.ndarray, windows: int) -> float:
    """Fit ONE Hawkes MLE on RAW clock time restricted to the first business-time sub-window.

    Same event subset as business-time window 0 (so the comparison is
    apples-to-apples), but times are the original int64 ms timestamps
    converted to float seconds and NOT rescaled — this isolates the effect
    of skipping business-time rescaling for otherwise-identical data.
    """
    edges = _window_edges(bt, windows)
    lo, hi = edges[0], edges[1]
    mask = (bt >= lo) & (bt < hi)
    raw_times_s = (ts_ms[mask].astype(np.float64) - ts_ms[mask][0]) / 1000.0
    if raw_times_s.size < 2:
        raise ValueError("first sub-window has < 2 events for the raw-clock-time fit")
    t_end = float(raw_times_s[-1])
    if t_end <= 0.0:
        raise ValueError("first sub-window has zero-length raw-clock-time span")
    _mu, alpha, _beta, _conv = _fit_capped(raw_times_s, t_end)
    return alpha


def _count_variance_window(median_beta: float) -> float:
    """Business-time count-variance window, sanity-asserted to be >> 1/median_beta.

    See module docstring: default 200s unless that fails the >> criterion
    (window > 20/median_beta) for this symbol's own fitted decay rate, in
    which case fall back to 100/median_beta.
    """
    if median_beta <= 0.0 or not np.isfinite(median_beta):
        return COUNT_VARIANCE_WINDOW_BT_DEFAULT
    if COUNT_VARIANCE_WINDOW_BT_DEFAULT > COUNT_VARIANCE_WINDOW_SAFETY_MULT / median_beta:
        return COUNT_VARIANCE_WINDOW_BT_DEFAULT
    return COUNT_VARIANCE_WINDOW_FALLBACK_MULT / median_beta


def _symbol_record(root: Path, symbol: str, month: str, windows: int) -> dict:
    events = load_events(root, symbol, [month])
    n_events = events.height
    if n_events == 0:
        raise ValueError(f"no events for {symbol} in {month}")

    ts_ms = events["ts"].dt.epoch("ms").to_numpy().astype(np.int64)
    ts_ms.sort()  # load_events sorts (ts, sign); ts alone is already non-decreasing

    profile = intraday_rate_profile(ts_ms, N_BINS)
    bt = rescale_to_business_time(ts_ms, profile)

    if bt.size < 2 * windows:
        raise ValueError(
            f"{symbol}: only {bt.size} events, need >= {2 * windows} for {windows} "
            "sub-windows with >= 2 events each"
        )

    alphas, converged_flags, betas, mus = _fit_business_time_windows(bt, windows)
    n_converged = int(sum(converged_flags))

    alpha_arr = np.array(alphas)
    alpha_median = float(np.median(alpha_arr))
    alpha_iqr = float(np.percentile(alpha_arr, 75) - np.percentile(alpha_arr, 25))
    median_beta = float(np.median(betas))
    median_mu = float(np.median(mus))

    raw_alpha = _raw_clock_time_first_window_alpha(ts_ms, bt, windows)
    raw_delta = raw_alpha - alphas[0]

    window_bt = _count_variance_window(median_beta)
    t_end_bt = float(bt[-1])
    alpha_cv = branching_count_variance(bt, window=window_bt, t_end=t_end_bt)

    return {
        "symbol": symbol,
        "n_events": n_events,
        "alpha_median": alpha_median,
        "alpha_iqr": alpha_iqr,
        "alphas": alphas,
        "n_converged": n_converged,
        "alpha_cv": alpha_cv,
        "raw_delta": raw_delta,
        "raw_alpha_window1": raw_alpha,
        "median_beta": median_beta,
        "median_mu": median_mu,
        "count_variance_window_bt": window_bt,
    }


def _ols_with_intercept(x: np.ndarray, y: np.ndarray) -> dict:
    (slope, intercept), cov = np.polyfit(x, y, 1, cov=True)
    yhat = slope * x + intercept
    resid = y - yhat
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "stderr": float(np.sqrt(cov[0, 0])),
        "r2": r2,
        "n": int(x.size),
    }


def _activity_regression(records: list[dict]) -> dict | None:
    if len(records) < 3:
        return None
    log_n = np.array([np.log10(r["n_events"]) for r in records])
    if np.ptp(log_n) == 0.0:
        return None
    alpha_med = np.array([r["alpha_median"] for r in records])
    return _ols_with_intercept(log_n, alpha_med)


def _agreement_stats(records: list[dict]) -> dict:
    if not records:
        return {"median_abs_diff": None, "correlation": None, "n": 0}
    mle = np.array([r["alpha_median"] for r in records])
    cv = np.array([r["alpha_cv"] for r in records])
    diffs = np.abs(mle - cv)
    median_abs_diff = float(np.median(diffs))
    correlation = float(np.corrcoef(mle, cv)[0, 1]) if len(records) >= 2 and np.std(mle) > 0 and np.std(cv) > 0 else None
    return {"median_abs_diff": median_abs_diff, "correlation": correlation, "n": len(records)}


def run_q6(
    root: Path,
    out_dir: Path,
    symbols: list[str],
    month: str = "2023-06",
    windows: int = 6,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    failures: list[dict] = []

    for symbol in symbols:
        p = parquet_path(root, symbol, "aggTrades", month)
        if not p.exists():
            failures.append({"symbol": symbol, "reason": f"parquet not found: {p}"})
            continue
        try:
            records.append(_symbol_record(root, symbol, month, windows))
        except Exception as e:  # noqa: BLE001 - a per-symbol failure is logged, not fatal
            failures.append({"symbol": symbol, "reason": f"{type(e).__name__}: {e}"})

    activity_regression = _activity_regression(records)
    agreement = _agreement_stats(records)

    result = {
        "month": month,
        "windows": windows,
        "n_symbols_requested": len(symbols),
        "n_symbols_successful": len(records),
        "n_symbols_failed": len(failures),
        "records": records,
        "failures": failures,
        "activity_regression": activity_regression,
        "agreement": agreement,
    }

    _plot(out_dir, records, activity_regression)
    _write_results_parquet(out_dir, records)
    _write_results_md(out_dir, result)
    (out_dir / "q6_endogeneity.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    return result


_PARQUET_COLUMNS = [
    "symbol", "n_events", "alpha_median", "alpha_iqr", "n_converged",
    "alpha_cv", "raw_delta", "median_beta", "median_mu",
]


def _write_results_parquet(out_dir: Path, records: list[dict]) -> None:
    if records:
        rows = [{k: r[k] for k in _PARQUET_COLUMNS} for r in records]
        df = pl.DataFrame(rows)
    else:
        df = pl.DataFrame(schema={
            "symbol": pl.Utf8, "n_events": pl.Int64, "alpha_median": pl.Float64,
            "alpha_iqr": pl.Float64, "n_converged": pl.Int64, "alpha_cv": pl.Float64,
            "raw_delta": pl.Float64, "median_beta": pl.Float64, "median_mu": pl.Float64,
        })
    df.write_parquet(out_dir / "q6_endogeneity.parquet")


def _plot(out_dir: Path, records: list[dict], activity_regression: dict | None) -> None:
    fig, (ax_act, ax_agree) = plt.subplots(1, 2, figsize=(13, 5))

    if records:
        log_n = np.array([np.log10(r["n_events"]) for r in records])
        alpha_med = np.array([r["alpha_median"] for r in records])
        alpha_iqr = np.array([r["alpha_iqr"] for r in records])
        ax_act.errorbar(
            log_n, alpha_med, yerr=alpha_iqr / 2, fmt="o", markersize=5, alpha=0.75,
            ecolor="gray", elinewidth=1.0, capsize=2,
        )
        if activity_regression is not None:
            slope, intercept = activity_regression["slope"], activity_regression["intercept"]
            x_line = np.array([log_n.min(), log_n.max()])
            ax_act.plot(x_line, slope * x_line + intercept, color="red",
                        label=f"OLS fit (slope={slope:.4f})")
            ax_act.legend()

        mle = np.array([r["alpha_median"] for r in records])
        cv = np.array([r["alpha_cv"] for r in records])
        ax_agree.scatter(mle, cv, s=36, alpha=0.8, c=log_n, cmap="viridis")
        lo = min(mle.min(), cv.min(), 0.0)
        hi = max(mle.max(), cv.max(), 1.0)
        ax_agree.plot([lo, hi], [lo, hi], color="gray", linestyle="--", linewidth=1.0, label="y = x")
        ax_agree.legend()

    ax_act.set_xlabel("log10(n_events)")
    ax_act.set_ylabel(r"$\hat\alpha_{median}$ (MLE branching ratio)")
    ax_act.set_title("Branching ratio vs. activity (errorbars = sub-window IQR)")

    ax_agree.set_xlabel(r"$\hat\alpha_{median}$ (MLE, business time)")
    ax_agree.set_ylabel(r"$\hat n$ (count-variance, business time)")
    ax_agree.set_title("MLE vs. count-variance agreement")

    fig.tight_layout()
    fig.savefig(out_dir / "q6_endogeneity.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _fmt_reg(reg: dict | None) -> str:
    if reg is None:
        return "not estimable (fewer than 3 successful symbols, or zero variance in log10(n_events))"
    return (
        f"slope = **{reg['slope']:.4f}** (stderr {reg['stderr']:.4f}), "
        f"intercept = {reg['intercept']:.4f}, R² = {reg['r2']:.4f}, n = {reg['n']}"
    )


def _write_results_md(out_dir: Path, result: dict) -> None:
    records = result["records"]
    month = result["month"]
    windows = result["windows"]
    reg = result["activity_regression"]
    agreement = result["agreement"]

    lines: list[str] = []
    lines.append("# Q6: branching-ratio panel, Hawkes endogeneity cross-section")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        f"**Symbol selection**: the {result['n_symbols_requested']} symbols listed in the "
        "file passed as `--symbols-file`. The committed list, "
        "`results/q6_symbols_2023-06.txt`, is the deduplicated union of (a) the fixed "
        "16-symbol panel (`results/panel_2023-06.txt`) and (b) the 40 most active symbols by "
        "June-2023 `n_events` within the 207-symbol universe "
        "(`results/universe_2023-06.txt`), ranked with the activity column in "
        "`results/q4_cross_section.parquet`. The panel was chosen to be liquid, so the two "
        f"sets overlap 15/16 and the union has {result['n_symbols_requested']} symbols, not "
        "the ~50-56 a naive 16+40 sum suggests."
    )
    lines.append("")
    lines.append(
        f"For each symbol I load one month ({month}) of aggTrades and collapse it to "
        "aggressor-level events (`load_events`). A per-symbol exception (missing parquet, "
        "too few events for the window/guard requirements) is logged in `failures` and "
        "does not abort the run."
    )
    lines.append("")
    lines.append(
        "**Business time first.** Timestamps are rescaled to business time "
        "(`intraday_rate_profile`, 48 bins, then `rescale_to_business_time`) before any "
        "Hawkes fitting. On clock time, neither the Hawkes MLE nor the count-variance "
        "estimator can separate self-excitation from a time-varying baseline rate. A "
        "synthetic trap test (`test_regime_switching_poisson_produces_spurious_"
        "endogeneity_trap`) shows a regime-switching Poisson process with no "
        "self-excitation yields a spurious count-variance n̂ > 0.2 and a spurious MLE alpha "
        "> 0.5 (Filimonov & Sornette 2015). Crypto flow has at least that strong an "
        "intraday U-shape and funding-hour clustering. The `raw_delta` column measures the "
        "bias per symbol."
    )
    lines.append("")
    lines.append(
        f"**Sub-windows**: the business-time series is split into {windows} equal "
        "contiguous sub-windows, each fit with `fit_hawkes_exp` on "
        f"(business_time − window_start). **Runtime cap**: a sub-window with more than "
        f"{MAX_FIT_EVENTS:,} events is fit on its first {MAX_FIT_EVENTS:,} only, to bound "
        "the O(N log N) MLE cost. Multi-seed synthetic tests give a fitted-alpha sampling "
        f"sd of ~0.004-0.02 at comparable sizes, small next to the spread from having only "
        f"{windows} windows per symbol. That sd comes from well-specified-kernel data. It "
        "does not cover exponential-kernel misspecification against a true power-law "
        "kernel (see the kernel caveat)."
    )
    lines.append("")
    lines.append(
        f"**alpha_median / alpha_iqr**: median and IQR of the {windows} per-window alphas. "
        f"**n_converged**: how many of the {windows} fits reported `converged=True`. The "
        "flag means the optimizer settled, not that the parameters are well identified, "
        "especially near alpha≈1 (see the `fit_hawkes_exp` docstring)."
    )
    lines.append("")
    lines.append(
        "**raw_delta**: one extra fit on the first sub-window using raw clock time, same "
        "events and cap. `raw_delta = alpha_raw − alpha_rescaled_window1`. A positive value "
        "means the clock-time fit overstates endogeneity."
    )
    lines.append("")
    lines.append(
        "**alpha_cv (count-variance n̂)**: `branching_count_variance` on the full "
        "business-time series, with window_bt = 200 business-time seconds by default. The "
        "window must be much larger than the kernel decay timescale 1/beta (typically "
        "~0.1-2s for liquid crypto flow), or the estimator truncates the kernel's memory "
        "and biases n̂ toward 0. When 200s does not clear 20/median_beta for a symbol, the "
        "window widens to 100/median_beta."
    )
    lines.append("")
    lines.append(
        "**Cross-section**: OLS (`np.polyfit`, with intercept) of alpha_median on "
        "log10(n_events). **MLE-vs-CV agreement**: median absolute difference and Pearson "
        "correlation between alpha_median and alpha_cv."
    )
    lines.append("")
    lines.append("## Run summary")
    lines.append("")
    lines.append(
        f"Requested: {result['n_symbols_requested']}. Successful: "
        f"{result['n_symbols_successful']}. Failed: {result['n_symbols_failed']}."
    )
    lines.append("")

    if records:
        sorted_records = sorted(records, key=lambda r: r["n_events"], reverse=True)
        lines.append("## Panel table (sorted by n_events)")
        lines.append("")
        lines.append(
            "| symbol | n_events | α̂_median | α̂ IQR | n_converged/6 | n̂_CV | raw_delta | "
            "median β̂ | median μ̂ |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in sorted_records:
            lines.append(
                f"| {r['symbol']} | {r['n_events']:,} | {r['alpha_median']:.4f} | "
                f"{r['alpha_iqr']:.4f} | {r['n_converged']}/{len(r['alphas'])} | "
                f"{r['alpha_cv']:.4f} | {r['raw_delta']:+.4f} | {r['median_beta']:.4f} | "
                f"{r['median_mu']:.4f} |"
            )
        lines.append("")

        lines.append("## Estimator agreement")
        lines.append("")
        lines.append("| symbol | α̂_median (MLE) | n̂_CV (count-variance) | |diff| |")
        lines.append("|---|---|---|---|")
        for r in sorted_records:
            diff = abs(r["alpha_median"] - r["alpha_cv"])
            lines.append(
                f"| {r['symbol']} | {r['alpha_median']:.4f} | {r['alpha_cv']:.4f} | {diff:.4f} |"
            )
        lines.append("")
        if agreement["median_abs_diff"] is not None:
            corr_str = f"{agreement['correlation']:.4f}" if agreement["correlation"] is not None else "n/a"
            lines.append(
                f"Median |α̂_median − n̂_CV| across {agreement['n']} symbols: "
                f"**{agreement['median_abs_diff']:.4f}**. Pearson correlation: **{corr_str}**."
            )
            lines.append("")
    else:
        lines.append("No symbols produced usable results, so there is no table.")
        lines.append("")

    lines.append("## Activity regression")
    lines.append("")
    lines.append(f"**α̂_median on log10(n_events)**: {_fmt_reg(reg)}")
    lines.append("")

    lines.append("## Findings")
    lines.append("")
    if records:
        alphas_med = [r["alpha_median"] for r in records]
        overall_median = float(np.median(alphas_med))
        lo, hi = min(alphas_med), max(alphas_med)
        lines.append(
            f"Across the {len(records)} successful symbols, the median endogeneity level "
            f"(median of per-symbol alpha_median) is **{overall_median:.4f}**, ranging from "
            f"{lo:.4f} to {hi:.4f}. Distance from criticality (alpha=1): "
            f"**{1.0 - overall_median:.4f}**."
        )
        lines.append("")
        lines.append(
            "**Comparison to the literature**: Mark, Sila & Weber (2022, *European Journal "
            "of Finance*) find BTC's endogeneity level, fit with power-law kernels, "
            "comparable to fiat FX markets, so crypto is not structurally different from "
            "mature, near-critical asset classes in that study. "
            f"This panel's exponential-kernel median of {overall_median:.4f} is "
            f"{'broadly consistent with a near-critical' if overall_median > 0.6 else 'well below a near-critical'} "
            "regime at face value. Given the exponential-kernel caveat below, it is a "
            "lower bound on the true (power-law) endogeneity level and not directly "
            "comparable to that literature's power-law fits."
        )
        lines.append("")
        if reg is not None and slope_is_distinguishable(reg):
            direction = "increases" if reg["slope"] > 0 else "decreases"
            lines.append(
                f"Endogeneity {direction} with log-activity across the panel "
                f"(slope {reg['slope']:.4f}, R² {reg['r2']:.4f}, n={reg['n']})."
            )
        elif reg is not None:
            lines.append(
                f"The slope of α̂_median on log-activity across the panel (slope "
                f"{reg['slope']:.4f}, stderr {reg['stderr']:.4f}, |t| = {slope_t(reg):.1f}, "
                f"R² {reg['r2']:.4f}, n={reg['n']}) is within {SLOPE_MIN_SE:g} standard errors "
                "of zero, so it is indistinguishable from no relationship with activity."
            )
        else:
            lines.append("The activity regression is not estimable in this run.")
        lines.append("")
        if agreement["median_abs_diff"] is not None:
            mle_med = float(np.median([r["alpha_median"] for r in records]))
            cv_med = float(np.median([r["alpha_cv"] for r in records]))
            corr_val = agreement["correlation"]
            if corr_val is None:
                corr_phrase = "n/a (fewer than 2 symbols)"
            else:
                corr_strength = "weak" if abs(corr_val) < 0.4 else "moderate" if abs(corr_val) < 0.7 else "strong"
                corr_sign = "positive" if corr_val > 0 else "negative" if corr_val < 0 else "zero"
                corr_phrase = f"{corr_val:.4f}, {corr_strength} {corr_sign}"
                if corr_strength != "strong":
                    corr_phrase += ", not a strong cross-check"
            n_cv_higher = sum(1 for r in records if r["alpha_cv"] > r["alpha_median"])
            frac_cv_higher = n_cv_higher / len(records)
            if frac_cv_higher >= 0.9 or frac_cv_higher <= 0.1:
                direction_note = (
                    f"the gap is one-directional: count-variance reads higher than the MLE "
                    f"for {n_cv_higher}/{len(records)} symbols ({frac_cv_higher:.0%}), not "
                    f"just on average (median n̂_CV ≈ {cv_med:.4f} vs. median α̂_median ≈ "
                    f"{mle_med:.4f})"
                )
            else:
                direction_note = (
                    f"the direction is mixed across symbols (count-variance reads higher "
                    f"for {n_cv_higher}/{len(records)}, {frac_cv_higher:.0%})"
                )
            lines.append(
                f"**The two branching-ratio estimators disagree substantially.** The median "
                f"absolute difference is {agreement['median_abs_diff']:.4f} (Pearson "
                f"correlation {corr_phrase}), and {direction_note}. Two explanations, not "
                "mutually exclusive. (1) Exponential-kernel misspecification: if the true "
                "kernel is a slowly decaying power law, the exponential MLE truncates "
                "long-range excitation and understates alpha, while "
                "`branching_count_variance` assumes no kernel shape. A gap in this "
                "direction fits that, but not uniquely. (2) Window sensitivity: n̂_CV uses "
                "one fixed 200s window per symbol, and its large-window asymptotic is "
                "approximate at any finite window (see the `branching_count_variance` "
                "docstring). The data here cannot separate the two. A power-law-kernel MLE "
                "refit and a window sweep on alpha_cv would, and I did not run either."
            )
        lines.append("")
        if records:
            raw_deltas = [r["raw_delta"] for r in records]
            median_raw_delta = float(np.median(raw_deltas))
            max_abs_raw_delta = float(np.max(np.abs(raw_deltas)))
            small_bias = max_abs_raw_delta < 0.05
            if small_bias:
                lines.append(
                    f"**The seasonality bias is near zero.** Median raw-vs-rescaled delta "
                    f"across the panel: **{median_raw_delta:+.4f}** (largest magnitude across "
                    f"all symbols: {max_abs_raw_delta:.4f}). A clock-time-only fit would have "
                    "mismeasured alpha by only a small fraction of a unit. That reflects this "
                    "market, not a redundant correction: crypto futures trade 24/7 with no "
                    "open/close or dominant regional session, and the 48-bin "
                    "`intraday_rate_profile` is close to flat, so `rescale_to_business_time` "
                    "is close to the identity. By contrast, the synthetic seasonal-baseline "
                    "Hawkes test in `test_eventtime.py` used a deep intraday trough (shape "
                    "amplitude as low as 1.05x baseline). Its raw-fit alpha was inflated by "
                    "+0.22 to +0.55 over truth, and this pipeline rescaled it back to within "
                    "~0.01. The fix works when the confound is large, and here the confound "
                    "is small. I apply it to every symbol since the profile's flatness is "
                    "not known in advance."
                )
            else:
                lines.append(
                    f"Median raw-vs-rescaled seasonality-bias delta across the panel: "
                    f"**{median_raw_delta:+.4f}** (largest magnitude: {max_abs_raw_delta:.4f}), "
                    "the typical amount by which a clock-time-only fit would have "
                    "mismeasured endogeneity relative to the business-time estimate on "
                    "this data."
                )
            lines.append("")
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
        f"- **Single month** ({month}): one market regime. Endogeneity levels are "
        "plausibly regime-dependent (activity, volatility) and may not carry over to "
        "other months."
    )
    lines.append(
        "- **Exponential kernel only**: per Hardiman & Bouchaud (2014) and the broader "
        "power-law-kernel literature, an exponential kernel fit to data with a true "
        "slowly decaying power-law kernel understates the branching ratio, because its "
        "finite memory truncates the long-range contribution. Read the alpha estimates "
        "as lower-bound-flavored, not exact. A power-law-kernel refit would likely push "
        "every number in the table up, possibly materially."
    )
    lines.append(
        "- **Convergence flag**: `n_converged` only says the Nelder-Mead search stopped "
        "improving locally. Near alpha≈1 the likelihood has a shallow mu-alpha ridge "
        "(`fit_hawkes_exp` docstring), so `converged=True` there is a weak signal."
    )
    lines.append(
        f"- **Runtime cap** ({MAX_FIT_EVENTS:,} events/window): windows above the cap are "
        "fit on a truncated prefix, so their alpha reflects only the earliest events of "
        "the window."
    )
    lines.append(
        "- **Count-variance window (200s default)**: fixed apart from the 20/median_beta "
        "widening. A different window could shift alpha_cv, especially near that threshold."
    )
    lines.append(
        "- **Heteroskedasticity in the activity regression**: alpha_iqr varies across the "
        "cross-section, so the OLS homoskedasticity assumption is almost certainly "
        "violated. The slope, R² and stderr are descriptive."
    )
    lines.append(
        "- **48-bin intraday profile**: it is estimated from the same month being fit, so "
        "real self-excitation clustering at the same time-of-day scale (unlikely at "
        "~30-minute resolution, but not provably absent) could be removed with the "
        "seasonal confound."
    )
    lines.append("")
    (out_dir / "q6_endogeneity.md").write_text("\n".join(lines))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Q6: branching-ratio (Hawkes endogeneity) panel")
    parser.add_argument("--root", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--symbols-file", type=Path, required=True,
                         help="one symbol per line")
    parser.add_argument("--month", type=str, default="2023-06")
    parser.add_argument("--windows", type=int, default=6)
    return parser.parse_args(argv)


def _read_symbols_file(path: Path) -> list[str]:
    lines = path.read_text().splitlines()
    return [s.strip() for s in lines if s.strip()]


if __name__ == "__main__":
    args = _parse_args()
    symbols = _read_symbols_file(args.symbols_file)
    run_q6(
        args.root, args.out, symbols=symbols, month=args.month,
        windows=args.windows,
    )
