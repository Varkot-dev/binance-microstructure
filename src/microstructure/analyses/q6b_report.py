"""Q6b report writing: the Markdown writer, its line builders and the matplotlib figure.

Split out of `q6b_kernel_sensitivity` to keep that module focused on computation.
No computation lives here; it only formats a finished result dict.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from microstructure.analyses.q6b_common import (
    BOUNDARY_N_HAT,
    DESEASON_BIN_WIDTH_S,
    DRIFT_SUSPECT_MULTIPLIER,
    DRIFT_VERDICTS,
    INCONCLUSIVE_REASONS,
    MAX_FIT_EVENTS,
    N_BINS,
    _is_finite_number,
)
from microstructure.estimators.hawkes import DRIFT_K2_RISE_MIN, K2_GAIN_MIN_DLL

_REASON_PHRASES = {
    "no_rise": "show no K=2 rise at all",
    "k2_insignificant": "have a K=2 gain that is not significant",
    "mixed": "have a significant K=2 gain that the block baseline recovers only partly",
}


def _plot(out_dir: Path, records: list[dict], cross_section: dict) -> None:
    fig, (ax_delta, ax_slow) = plt.subplots(1, 2, figsize=(13, 5))

    if records:
        delta21s = np.array([r["delta21"] for r in records if _is_finite_number(r["delta21"])])
        if delta21s.size > 0:
            ax_delta.hist(delta21s, bins=min(20, max(5, delta21s.size // 2)), color="steelblue", alpha=0.85)
            ax_delta.axvline(0.15, color="red", linestyle="--", linewidth=1.0, label="Δ21 = 0.15")
            ax_delta.legend()
        ax_delta.set_xlabel(r"$\Delta_{21} = \hat n_2 - \hat n_1$ (median across sub-windows)")
        ax_delta.set_ylabel("symbol count")
        ax_delta.set_title("Distribution of K=1→K=2 branching-ratio jump")

        drift_suspect = np.array([r["drift_suspect"] for r in records])
        ratios = np.array(
            [_nan_if_none(r["ratio_inv_beta_slow_to_bin_width"]) for r in records], dtype=float
        )
        deltas = np.array([_nan_if_none(r["delta21"]) for r in records], dtype=float)
        colors = np.where(drift_suspect, "crimson", "steelblue")
        finite = np.isfinite(ratios) & np.isfinite(deltas)
        ax_slow.scatter(ratios[finite], deltas[finite], c=colors[finite], s=36, alpha=0.8)
        ax_slow.axvline(
            10.0, color="gray", linestyle="--", linewidth=1.0,
            label="drift-suspect threshold (10x bin width)",
        )
        ax_slow.legend()
    else:
        ax_delta.set_xlabel(r"$\Delta_{21} = \hat n_2 - \hat n_1$")
        ax_delta.set_ylabel("symbol count")
        ax_delta.set_title("Distribution of K=1→K=2 branching-ratio jump")

    ax_slow.set_xlabel(r"$1/\hat\beta_{slow}$ (K=2) ÷ deseasonalization bin width")
    ax_slow.set_ylabel(r"$\Delta_{21}$")
    ax_slow.set_title("Slow-timescale ratio vs. Δ21 (red = drift-suspect)")

    fig.tight_layout()
    fig.savefig(out_dir / "q6b_kernel_sensitivity.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _nan_if_none(value: float | None) -> float:
    return float("nan") if value is None else float(value)


def _fmt_ratio(ratio: float | None) -> str:
    if not _is_finite_number(ratio):
        return "n/a"
    return f"{ratio:.2f}x"


def _fmt_n(n_hat: float | None) -> str:
    """n-hat to 4 dp; a boundary fit (n-hat >= BOUNDARY_N_HAT) gets a dagger."""
    if n_hat is None:
        return "n/a"
    return f"{n_hat:.4f}" + ("†" if n_hat >= BOUNDARY_N_HAT else "")


def _fmt_signed(value: float | None, fmt: str) -> str:
    return "n/a" if value is None else format(value, fmt)


def _boundary_fit_counts(records: list[dict]) -> tuple[int, int]:
    """(per-window fits with n-hat >= BOUNDARY_N_HAT, total per-window fits), all K."""
    values = [v for r in records for w in r["per_window"] for v in w["n_by_k"].values()]
    return sum(1 for v in values if v >= BOUNDARY_N_HAT), len(values)


def _normalize_result(result: dict) -> dict:
    """Copy of `result` with int keys for n_median_by_k / n_converged_by_k.

    JSON round trips turn those keys into strings; the writers index them by int K.
    """
    def int_keys(d: dict) -> dict:
        return {int(k): v for k, v in d.items()}

    records = []
    for r in result["records"]:
        rec = dict(r)
        rec["n_median_by_k"] = int_keys(r["n_median_by_k"])
        rec["n_converged_by_k"] = int_keys(r["n_converged_by_k"])
        rec["per_window"] = [
            {**w, **{key: int_keys(w[key]) for key in ("n_by_k", "converged_by_k", "inv_beta_slow_by_k")}}
            for w in r["per_window"]
        ]
        records.append(rec)
    return {**result, "records": records}


def _drift_headline(
    counts: dict[str, int],
    reason_counts: dict[str, int],
    width_hours: float | None,
    n_requested: int,
    across_windows: dict | None = None,
) -> str:
    """One-sentence headline from verdict counts (majority of ASSESSED symbols).

    The denominator is stated: assessed symbols are those with a verdict;
    failed, errored and not-run symbols are excluded. The verdicts come from the
    first window only. `across_windows` ({n_above, n, median, windows}) adds the
    median-across-windows Delta21 count so the first-window result is not read as
    a panel-wide one.
    """
    assessed = sum(counts[v] for v in DRIFT_VERDICTS)
    denominator = (
        f"({assessed} of {n_requested} requested symbols assessed; "
        "failed, errored and not-run excluded)"
    )
    if assessed == 0:
        return f"**No symbol was assessed, so nothing can be said about drift versus memory {denominator}.**"
    if reason_counts["no_rise"] * 2 > assessed:
        sentence = (
            "On the first window, the one the drift control uses, most symbols show no "
            "material K=1→K=2 rise, so the control has no rise to explain there"
        )
    elif counts["drift"] * 2 > assessed:
        sentence = (
            "In this window, a block-wise baseline recovers at least half of the K=2 "
            "likelihood gain for most assessed symbols — consistent with slow baseline "
            "drift (heuristic screen; see caveats)"
        )
    elif counts["long_memory_candidate"] * 2 > assessed:
        width = (
            f"{width_hours:.1f} business-time hours (median block width)"
            if width_hours is not None else "the block width"
        )
        sentence = f"The K=2 rise is not explained by drift slower than {width}"
    else:
        inconclusive = counts["inconclusive"]
        if inconclusive > 0:
            top = max(INCONCLUSIVE_REASONS, key=lambda r: reason_counts[r])
            sentence = (
                f"No verdict holds a majority; {inconclusive} of {assessed} assessed symbols "
                f"are inconclusive ({reason_counts[top]} {_REASON_PHRASES[top]})"
            )
        else:
            sentence = "No verdict holds a majority; drift and long-memory-candidate verdicts split the assessed symbols"
    headline = f"**{sentence} {denominator}.**"
    if across_windows is not None and across_windows["n"] > 0:
        a = across_windows
        headline += (
            f" Across all {a['windows']} windows, the median-across-windows Δ21 exceeds "
            f"{DRIFT_K2_RISE_MIN:g} for {a['n_above']} of {a['n']} symbols (median Δ21 "
            f"{a['median']:+.3f}), so the first-window result is not a statement about "
            "the panel's K=2 rise in the other windows."
        )
    return headline


def _across_window_delta21(records: list[dict], windows: int) -> dict:
    deltas = [r["delta21"] for r in records if _is_finite_number(r["delta21"])]
    return {
        "windows": windows,
        "n": len(deltas),
        "n_above": sum(1 for d in deltas if d > DRIFT_K2_RISE_MIN),
        "median": float(np.median(deltas)) if deltas else float("nan"),
    }


def _drift_section_lines(result: dict) -> list[str]:
    """Markdown for 'Is the K=2 rise drift or memory?', templated from data."""
    lines = ["## Is the K=2 rise drift or memory?", ""]
    drift_blocks = result.get("drift_blocks", 0)
    if not drift_blocks:
        lines.append(
            "The block-wise-baseline control was disabled for this run (`--drift-blocks 0`), "
            "so the K=1→K=2 rise is not separated into drift and memory here."
        )
        lines.append("")
        return lines

    records = result["records"]
    counts = result["cross_section"]["drift_verdict_counts"]
    reasons = result["cross_section"]["drift_inconclusive_reason_counts"]
    assessed = [r for r in records if r.get("drift_verdict") in DRIFT_VERDICTS]
    widths = [r["drift_block_width_s"] for r in assessed if r.get("drift_block_width_s")]
    width_s = float(np.median(widths)) if widths else None
    width_hours = width_s / 3600.0 if width_s is not None else None

    lines.append(
        _drift_headline(
            counts, reasons, width_hours, result["n_symbols_requested"],
            _across_window_delta21(records, result["windows"]),
        )
    )
    lines.append("")
    lines.append(
        f"Verdict counts over {len(records)} symbols with results: drift = {counts['drift']}, "
        f"long_memory_candidate = {counts['long_memory_candidate']}, "
        f"inconclusive = {counts['inconclusive']} "
        f"(no_rise = {reasons['no_rise']}, k2_insignificant = {reasons['k2_insignificant']}, "
        f"mixed = {reasons['mixed']}), not run = {counts['not_run']}, "
        f"errored = {counts['errored']}."
    )
    lines.append("")
    width_txt = (
        f"{width_hours:.1f} business-time hours ({width_s:.0f} business-time seconds)"
        if width_s else "n/a"
    )
    lines.append(
        f"Per symbol, on the first business-time window only (to bound cost; that window is "
        f"capped at {MAX_FIT_EVENTS:,} events), I compare K=1 with one constant baseline "
        f"against K=1 with a piecewise-constant baseline over {drift_blocks} equal blocks, "
        f"and against the window's K=2 fit. Median block width: {width_txt}. `dll_pw` and "
        "`dll_k2` are the log-likelihood gains over constant-baseline K=1 from the block "
        "baseline and from the second kernel component. `threshold` is "
        "chi-square(0.95, blocks−1)/2."
    )
    lines.append("")
    lines.append("**Method caveats.**")
    lines.append(
        "- This is a heuristic likelihood-ratio screen, not a formal test. The fits are "
        "Nelder-Mead optima, the chi-square calibration is only approximate for Hawkes "
        "likelihoods, and the half-of-`dll_k2` cut-off is a convention."
    )
    lines.append(
        f"- Resolution limit: a block baseline absorbs only drift slower than the block "
        f"width (median {width_txt}). Faster baseline wobble averages out inside a block "
        "and looks like long memory, so `long_memory_candidate` means something only for "
        "drift slower than that width."
    )
    lines.append(
        "- Misspecification: when K=1 is wrong (real long memory), block counts are more "
        "dispersed than K=1 predicts, which inflates `dll_pw`. That can push a symbol with "
        "real long memory to `inconclusive` OR across the drift threshold into `drift`. A "
        "`drift` label means only that the block baseline recovers at least half of the K=2 "
        "gain. It does not exclude long memory."
    )
    lines.append(
        f"- `inconclusive` is split by reason: `no_rise` (K=2 n̂ − K=1 n̂ ≤ "
        f"{DRIFT_K2_RISE_MIN:g}, so there is nothing to explain), `k2_insignificant` (the "
        f"K=2 gain `dll_k2` is below {K2_GAIN_MIN_DLL:.2f} nats = chi-square(0.95, 2)/2), "
        "and `mixed` (a material, significant K=2 gain that the block baseline recovers "
        "significantly but by less than half)."
    )
    lines.append(
        "- Business-time rescaling has already removed the 48-bin periodic intraday "
        "profile, so the control targets aperiodic drift."
    )
    lines.append("")
    if assessed:
        lines.append(
            "| symbol | verdict | inconclusive reason | n̂_1 (const) | n̂_2 | n̂_1 (piecewise) | "
            "dll_pw | dll_k2 | threshold | block width (business-time h) |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for r in sorted(assessed, key=lambda r: r["n_events"], reverse=True):
            lines.append(
                f"| {r['symbol']} | {r['drift_verdict']} | "
                f"{r['drift_inconclusive_reason'] or '—'} | {_fmt_n(r['drift_n_k1'])} | "
                f"{_fmt_n(r['drift_n_k2'])} | {_fmt_n(r['n_k1_piecewise'])} | {r['dll_pw']:.2f} | "
                f"{r['dll_k2']:.2f} | {r['dll_threshold']:.2f} | "
                f"{r['drift_block_width_s'] / 3600.0:.2f} |"
            )
        lines.append("")
        boundary_cells = sum(
            1 for r in assessed for key in ("drift_n_k1", "drift_n_k2", "n_k1_piecewise")
            if r[key] >= BOUNDARY_N_HAT
        )
        if boundary_cells:
            lines.append(
                f"† n̂ ≥ {BOUNDARY_N_HAT:g}: the fit sits on the stationarity boundary (n̂ = 1), "
                "where mu and alpha are only weakly identified, so that value is not a "
                f"reliable estimate ({boundary_cells} such "
                f"{'entry' if boundary_cells == 1 else 'entries'} in this table)."
            )
            lines.append("")
    errors = [r for r in records if r.get("drift_error")]
    for r in errors:
        lines.append(f"- {r['symbol']}: drift control errored ({r['drift_error']}).")
    if errors:
        lines.append("")
    return lines


def _write_results_md(out_dir: Path, result: dict) -> None:
    result = _normalize_result(result)
    records = result["records"]
    month = result["month"]
    windows = result["windows"]
    ks = result["ks"]
    cross_section = result["cross_section"]

    lines: list[str] = []
    lines.append("# Q6b: kernel-K sensitivity panel, does n̂ rise with K, and why?")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        f"For each symbol I load one month ({month}) of aggTrades (`load_events`), rescale "
        "to business time as in Q6 (`intraday_rate_profile` + `rescale_to_business_time`, "
        f"{N_BINS} bins), and split it into {windows} equal contiguous sub-windows. Each "
        f"sub-window is refit at every K in {ks} with `fit_hawkes_multiexp` (a "
        "sum-of-K-exponentials Hawkes MLE), where Q6 used a single K=1 fit. For every K I "
        "record, per symbol and sub-window, n̂_K = sum(alpha_k) and β_slow_K = min(betas_K), "
        "the rate of the slowest-decaying component."
    )
    lines.append("")
    lines.append(
        f"**Runtime cap**: a sub-window with more than {MAX_FIT_EVENTS:,} events is fit "
        f"on its first {MAX_FIT_EVENTS:,} only, the same cap as Q6, applied at each K."
    )
    lines.append("")
    lines.append(
        "**Per-symbol summary**: the median across sub-windows of n̂_1, n̂_2, n̂_3, and "
        "Δ21 = median(n̂_2) − median(n̂_1), the K=1→K=2 branching-ratio jump. I also report "
        "the median across sub-windows of 1/β_slow at K=2 (the slower component's "
        "timescale in business-time seconds), as two ratios: against the deseasonalization "
        f"bin width ({DESEASON_BIN_WIDTH_S:.1f}s = 86400/{N_BINS}) and against the "
        "sub-window length."
    )
    lines.append("")
    lines.append("## The confound Δ21 alone does not resolve")
    lines.append("")
    lines.append(
        "**A K=1→K=2 rise in n̂ together with a slow kernel component can also come from "
        "residual baseline non-stationarity, not only from a long-memory kernel.** A "
        "synthetic control in this repo's tests (\"Case A\") shows it: a true n=0.4 "
        "single-exponential process with a ±30% baseline-rate wobble that survives "
        "imperfect deseasonalization fits at K=1 with n̂≈0.46 and at K=2 with n̂≈0.83. That "
        "is a large, spurious Δ21 with no long-memory kernel in the generating model. A "
        "second exponential with a very slow beta is flexible enough to absorb a slow drift "
        "in the baseline rate and inflate the K=2 branching-ratio sum. Filimonov & Sornette "
        "(2015) document the same mechanism for the count-variance estimator's "
        "regime-switching trap. Here it also affects the sum-of-exponentials MLE."
    )
    lines.append("")
    lines.append(
        "**Why I report 1/β_slow vs. bin width and not Δ21 alone.** A slow component "
        "decaying on a timescale comparable to or longer than the deseasonalization bin "
        "width is the shape a residual seasonality artifact at that scale would produce. "
        "The 48-bin intraday profile cannot resolve structure finer than one bin, so "
        "leftover non-stationarity at or above that scale could generate a slow K=2 "
        f"component. Symbols whose median 1/β_slow (K=2) exceeds {DRIFT_SUSPECT_MULTIPLIER:.0f}x "
        "the bin width are flagged **drift-suspect** in the panel table. For those, a "
        "large Δ21 is ambiguous between long memory and residual non-stationarity."
    )
    lines.append("")
    if result.get("drift_blocks"):
        lines.append(
            "**The decisive control runs on one window per symbol** (see \"Is the K=2 rise "
            "drift or memory?\" below): K=1 is refit with a block-wise (piecewise-constant) "
            "mu and compared with the K=2 gain. It is a heuristic screen with a stated "
            "resolution limit, so Δ21 and the drift-suspect flag remain triage quantities."
        )
    else:
        lines.append(
            "**The decisive control was not run** (`--drift-blocks 0`). Refitting K=1 with a "
            "block-wise (piecewise-constant) mu would separate the two explanations. Until "
            "then, Δ21 and the drift-suspect flag are triage quantities, not a verdict on "
            "kernel misspecification vs. residual drift."
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
            "| symbol | n_events | n̂_1 | n̂_2 | n̂_3 | Δ21 | 1/β_slow (K=2, s) | "
            "÷ bin width | ÷ window length | drift-suspect | within null | drift verdict |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in sorted_records:
            n1 = r["n_median_by_k"].get(1)
            n2 = r["n_median_by_k"].get(2)
            n3 = r["n_median_by_k"].get(3)
            n1s, n2s, n3s = _fmt_n(n1), _fmt_n(n2), _fmt_n(n3)
            within_null = r.get("within_finite_sample_null")
            within_null_s = "yes" if within_null else ("NO" if within_null is False else "n/a")
            lines.append(
                f"| {r['symbol']} | {r['n_events']:,} | {n1s} | {n2s} | {n3s} | "
                f"{_fmt_signed(r['delta21'], '+.4f')} | "
                f"{_fmt_signed(r['median_inv_beta_slow_k2_s'], '.2f')} | "
                f"{_fmt_ratio(r['ratio_inv_beta_slow_to_bin_width'])} | "
                f"{_fmt_ratio(r['ratio_inv_beta_slow_to_window_length'])} | "
                f"{'YES' if r['drift_suspect'] else 'no'} | {within_null_s} | "
                f"{r.get('drift_verdict') or 'n/a'} |"
            )
        lines.append("")
        n_boundary, n_fits = _boundary_fit_counts(records)
        if n_boundary:
            lines.append(
                f"† n̂ ≥ {BOUNDARY_N_HAT:g}. Across all per-window fits, {n_boundary} of "
                f"{n_fits} sit on the stationarity boundary (n̂ = 1), where mu and alpha are "
                "only weakly identified. The per-symbol medians above are taken over those "
                "fits too."
            )
            lines.append("")
    else:
        lines.append("No symbols produced usable results, so there is no table.")
        lines.append("")

    lines.append("## Cross-section")
    lines.append("")
    dist = cross_section["delta21_distribution"]
    if dist is not None:
        lines.append(
            f"**Δ21 distribution** across {dist['n']} symbols: median = **{dist['median']:.4f}**, "
            f"mean = {dist['mean']:.4f}, sd = {dist['std']:.4f}, range = "
            f"[{dist['min']:.4f}, {dist['max']:.4f}]."
        )
    else:
        lines.append("Δ21 distribution not estimable (no successful symbols with both K=1, K=2).")
    lines.append("")

    null_floor = cross_section.get("null_floor_p90")
    if null_floor is not None:
        n_within = sum(1 for r in records if r.get("within_finite_sample_null"))
        if n_within:
            consequence = (
                "For the symbols within it, Δ21 is no larger than a well-specified, "
                "non-long-memory K=1 process of this size would produce from sampling "
                "noise alone, so it is not evidence of long-memory kernel structure on "
                "its own."
            )
        else:
            consequence = (
                "No symbol's Δ21 falls at or below it, so sampling noise in a "
                "well-specified K=1 process of this size does not account for any "
                "symbol's rise."
            )
        calibrated_above_cap = null_floor["n_events_per_window"] > MAX_FIT_EVENTS
        stale = (
            f" The fits are capped at {MAX_FIT_EVENTS:,} events per window, so this null was "
            "calibrated at a larger size than the fits used. Rerunning recalibrates it at the "
            "capped size."
            if calibrated_above_cap
            else ""
        )
        basis = (
            ""
            if calibrated_above_cap
            else f" (the panel's median per-window count, capped at the {MAX_FIT_EVENTS:,}-event fit cap)"
        )
        lines.append(
            f"**Null floor for Δ21**, computed at {null_floor['n_events_per_window']:,} events "
            f"per window{basis} from "
            f"{null_floor['n_sims']} simulated well-specified K=1 processes with "
            f"alpha={null_floor['alpha_used']:.4f} (this panel's median n̂_1) and "
            f"beta={null_floor['beta_used']:.1f} (see `spurious_delta21_null`). The null's "
            f"90th percentile is **{null_floor['p90']:.4f}** (median {null_floor['median']:.4f}). "
            f"Symbols whose Δ21 does not exceed it are labeled **\"within finite-sample "
            f"null\"** in the panel table ({n_within}/{len(records)} symbols). "
            f"{consequence}{stale}"
        )
    else:
        lines.append(
            "Null floor not estimable (no successful symbols with a K=1 fit and recorded "
            "per-window event count)."
        )
    lines.append("")

    frac = cross_section["frac_n2_at_least_0_9"]
    if frac is not None:
        lines.append(
            f"**Fraction of symbols with n̂_2 ≥ 0.9** (near-critical at K=2): "
            f"**{frac:.1%}**."
        )
    else:
        lines.append("Fraction of symbols with n̂_2 ≥ 0.9 not estimable (no K=2 results).")
    lines.append("")
    cmp = cross_section["cv_comparison"]
    if cmp is not None:
        corr = f"{cmp['corr_n2_cv']:.4f}" if cmp["corr_n2_cv"] is not None else "n/a"
        closed = (
            f"{cmp['median_frac_gap_closed']:.0%}"
            if cmp["median_frac_gap_closed"] is not None
            else "n/a"
        )
        lines.append(
            f"**Against Q6's count-variance n̂** (n={cmp['n']}): the median gap is "
            f"{cmp['median_gap_k1']:.4f} at K=1 and {cmp['median_gap_k2']:.4f} at K=2, and "
            f"the median share of the gap closed by K=2 is {closed}. Across symbols, "
            f"corr(n̂_2, count-variance n̂) = {corr}. Δ21 is not correlated with the K=1 gap "
            "directly: both contain −n̂_1, so that correlation is high by construction."
        )
    elif result.get("q6_json_used"):
        lines.append(
            f"A Q6 JSON was supplied (`{result['q6_json_used']}`) but shares no symbols with "
            "this run, so the count-variance comparison was skipped."
        )
    else:
        lines.append("No `--q6-json` supplied, so the count-variance comparison was skipped.")
    lines.append("")

    lines.extend(_drift_section_lines(result))

    if result["failures"]:
        lines.append("## Failures")
        lines.append("")
        lines.append("| symbol | reason |")
        lines.append("|---|---|")
        for f in result["failures"]:
            lines.append(f"| {f['symbol']} | {f['reason']} |")
        lines.append("")

    lines.append("## Findings")
    lines.append("")
    if dist is not None:
        drift_count = sum(1 for r in records if r["drift_suspect"])
        lines.append(
            f"Across {dist['n']} successful symbols, the median K=1→K=2 branching-ratio "
            f"jump is **{dist['median']:+.4f}**. {drift_count}/{len(records)} symbols are "
            "flagged drift-suspect (median 1/β_slow at K=2 exceeds "
            f"{DRIFT_SUSPECT_MULTIPLIER:.0f}x the deseasonalization bin width of "
            f"{DESEASON_BIN_WIDTH_S:.1f}s)."
            + (
                " For those, Δ21 is ambiguous between long-memory kernel structure and "
                "residual baseline drift leaking through deseasonalization."
                if drift_count
                else " The second kernel component decays inside one deseasonalization "
                "bin for every symbol, so Δ21 is not explained by intraday seasonality "
                "that the rescaling missed."
            )
        )
    else:
        lines.append("No successful symbols in this run, so there is no finding.")
    lines.append("")

    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "- **The confound is only partly resolved.** A large Δ21 fits both long-memory "
        "kernel structure and residual baseline non-stationarity that survives "
        "deseasonalization. The block-wise-baseline control (first window per symbol, "
        "heuristic, limited to drift slower than its block width) is reported in \"Is the "
        "K=2 rise drift or memory?\" and is absent when `--drift-blocks 0`."
    )
    lines.append(
        f"- **Single month** ({month}): one market regime; results may not carry over to "
        "other months."
    )
    lines.append(
        "- **Higher-K identifiability**: per the `fit_hawkes_multiexp` docstring, "
        "individual alpha_k and beta_k become less identified as K grows relative to what "
        "the sample can resolve. n̂_K (the sum) is more trustworthy than any single "
        "component, but β_slow (the min beta) can still be noisy, at K=3 in particular."
    )
    lines.append(
        f"- **Runtime cap** ({MAX_FIT_EVENTS:,} events/window): windows above the cap are "
        "fit on a truncated prefix, applied independently at each K."
    )
    lines.append(
        "- **48-bin intraday profile**: as in Q6, the profile is estimated from the same "
        "month being fit, and real excitation clustering at ~30-minute resolution "
        "could leak into the deseasonalization."
    )
    lines.append("")
    (out_dir / "q6b_kernel_sensitivity.md").write_text("\n".join(lines))
