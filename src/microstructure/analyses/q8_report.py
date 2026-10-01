"""Q8 report writing: the Markdown writer, its line builders and the matplotlib figure.

Split out of `q8_regimes` to keep that module focused on computation. No
computation lives here; it only formats the finished summaries.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from microstructure.analyses.q8_common import (
    FAST_MODE_BETA,
    FAST_MODE_SHIFT_FLAG,
    FLIP_SLOPE_MIN_SE,
    GAMMA_FLAT_R2_THRESHOLD,
    LOO_R2_SWING_LARGE,
    REGRESSION_MISMATCH_TOL,
    _chrono_key,
    _ols_with_intercept,
)


def _kernel_mode_lines(
    baseline_label: str,
    baseline_summary: dict,
    regime_summaries: dict[str, dict],
    ordered_regime_labels: list[str],
) -> list[str]:
    """Flag regimes whose alpha median moved because the exp-kernel fits changed mode."""
    base_fast = baseline_summary.get("fast_mode_fraction")
    if base_fast is None:
        return []
    shifted = [
        label
        for label in ordered_regime_labels
        if regime_summaries[label].get("fast_mode_fraction") is not None
        and abs(regime_summaries[label]["fast_mode_fraction"] - base_fast) > FAST_MODE_SHIFT_FLAG
    ]
    if not shifted:
        return []
    details = ", ".join(
        f"{label} ({regime_summaries[label]['fast_mode_fraction']:.2f})" for label in shifted
    )
    return [
        (
            f"**Kernel-mode shift: do not read the α median as an endogeneity change for "
            f"{details}.** The fast-mode share is the fraction of symbols whose "
            f"single-exponential fit has β̂ > {FAST_MODE_BETA:g} (decay faster than "
            f"{1 / FAST_MODE_BETA:g} business-time seconds). In the baseline "
            f"({baseline_label}) it is {base_fast:.2f}. A fast-mode fit captures only the "
            "fast component of a multi-timescale kernel, so its α̂ is lower by "
            "construction. Compare these regimes on the slow-mode α median (fits with "
            f"β̂ ≤ {FAST_MODE_BETA:g} only) or on the count-variance n̂_CV column, which "
            "assumes no kernel shape."
        ),
        "",
    ]


def _fmt_law(reg: dict | None) -> str:
    if reg is None:
        return "n/a | n/a"
    t = reg["slope"] / reg["stderr"] if reg["stderr"] > 0 else float("inf")
    return f"{reg['slope']:+.4f} (t {t:+.2f}) | {reg['r2']:.3f}"


def _cohort_split_lines(
    baseline_label: str, overlap_by_label: dict[str, dict], ordered_regime_labels: list[str]
) -> list[str]:
    """Refit both laws per cohort so a within-symbol change is not confused with composition."""
    lines = [
        "### Cohort split (native-universe regimes)",
        "",
        (
            "I refit both laws on three cohorts: the baseline's data restricted to symbols "
            "present in both periods, this regime's data on the same symbols, and this "
            "regime's newly listed symbols alone. A law that changes between the first two "
            "rows changed within the same contracts. A law that differs only in the third "
            "row is a composition effect. t = slope / OLS stderr."
        ),
        "",
        "| regime | cohort | n | flip slope (t) | flip R² | γ slope (t) | γ R² |",
        "|---|---|---|---|---|---|---|",
    ]
    cohort_names = (
        ("baseline_on_overlap", f"{baseline_label} data, shared symbols"),
        ("regime_on_overlap", "this regime, shared symbols"),
        ("regime_only", "this regime, new listings"),
    )
    for label in ordered_regime_labels:
        if label not in overlap_by_label:
            continue
        cohorts = overlap_by_label[label]["cohort_laws"]
        for key, name in cohort_names:
            laws = cohorts[key]
            reg = laws["p_flip_vs_activity"] or laws["gamma_vs_activity"]
            n = reg["n"] if reg else 0
            lines.append(
                f"| {label} | {name} | {n} | {_fmt_law(laws['p_flip_vs_activity'])} | "
                f"{_fmt_law(laws['gamma_vs_activity'])} |"
            )
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def _plot(
    out_dir: Path,
    baseline_label: str,
    baseline_q4: dict,
    regime_q4_by_label: dict[str, dict],
    overlap_records: Callable[[dict, dict], tuple[list[dict], list[dict]]],
) -> None:
    fig, (ax_flip, ax_gamma, ax_scatter) = plt.subplots(1, 3, figsize=(19, 5.5))

    all_labeled_q4 = {baseline_label: baseline_q4, **regime_q4_by_label}
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(all_labeled_q4), 1)))

    for (label, q4), color in zip(all_labeled_q4.items(), colors, strict=False):
        records = q4["symbols"]
        if not records:
            continue
        log_n = np.array([np.log10(r["n_events"]) for r in records])
        p_flip = np.array([r["p_flip"] for r in records])
        gamma = np.array([r["gamma"] for r in records])

        ax_flip.scatter(log_n, p_flip, s=18, alpha=0.6, color=color, label=label)
        reg = _ols_with_intercept(log_n, p_flip)
        if reg is not None:
            x_line = np.array([log_n.min(), log_n.max()])
            ax_flip.plot(x_line, reg["slope"] * x_line + reg["intercept"], color=color, linewidth=1.5)

        ax_gamma.scatter(log_n, gamma, s=18, alpha=0.6, color=color, label=label)
        reg_g = _ols_with_intercept(log_n, gamma)
        if reg_g is not None:
            x_line = np.array([log_n.min(), log_n.max()])
            ax_gamma.plot(x_line, reg_g["slope"] * x_line + reg_g["intercept"], color=color, linewidth=1.5)

    ax_flip.axhline(0.5, color="gray", linestyle="--", linewidth=1.0)
    ax_flip.set_xlabel("log10(n_events)")
    ax_flip.set_ylabel(r"$p_{flip}$")
    ax_flip.set_title("Flip law across regimes")
    if ax_flip.get_legend_handles_labels()[0]:
        ax_flip.legend(fontsize=8)

    ax_gamma.set_xlabel("log10(n_events)")
    ax_gamma.set_ylabel(r"$\hat{\gamma}$")
    ax_gamma.set_title(r"$\gamma$ vs. activity across regimes")
    if ax_gamma.get_legend_handles_labels()[0]:
        ax_gamma.legend(fontsize=8)

    # Symbol-level scatter: baseline p_flip vs. the chronologically first regime's p_flip.
    if regime_q4_by_label:
        first_label = min(regime_q4_by_label, key=_chrono_key)
        base_records, regime_records = overlap_records(baseline_q4, regime_q4_by_label[first_label])
        if base_records:
            base_p_flip = np.array([r["p_flip"] for r in base_records])
            regime_p_flip = np.array([r["p_flip"] for r in regime_records])
            ax_scatter.scatter(base_p_flip, regime_p_flip, s=24, alpha=0.7)
            lo = float(min(base_p_flip.min(), regime_p_flip.min(), 0.0))
            hi = float(max(base_p_flip.max(), regime_p_flip.max(), 1.0))
            ax_scatter.plot([lo, hi], [lo, hi], color="gray", linestyle="--", linewidth=1.0, label="y = x")
            ax_scatter.legend()
        ax_scatter.set_xlabel(f"p_flip ({baseline_label})")
        ax_scatter.set_ylabel(f"p_flip ({first_label})")
        ax_scatter.set_title(f"Symbol-level p_flip: {baseline_label} vs. {first_label}")
    else:
        ax_scatter.set_title("Symbol-level p_flip scatter (no regimes provided)")

    fig.tight_layout()
    fig.savefig(out_dir / "q8_regimes.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def _fmt_reg(reg: dict | None) -> str:
    if reg is None:
        return "not estimable (fewer than 3 successful symbols, or zero variance in log10(n_events))"
    return (
        f"slope = **{reg['slope']:.4f}** (stderr {reg['stderr']:.4f}), "
        f"intercept = {reg['intercept']:.4f}, R² = {reg['r2']:.4f}, n = {reg['n']}"
    )


def _fmt_corr(rho: float | None) -> str:
    return "n/a" if rho is None else f"{rho:.4f}"


def _loo_slope_sentence(influence: dict) -> str:
    """Consequence of the drop-one-out slope range, computed from the range itself."""
    lo, hi = influence["loo_slope_min"], influence["loo_slope_max"]
    if lo > 0.0:
        return (
            "The slope **stays positive under every single-symbol removal**, so the "
            "direction of the break does not depend on any one symbol."
        )
    if hi < 0.0:
        return (
            "The slope **stays negative under every single-symbol removal**, so the "
            "direction of the break does not depend on any one symbol."
        )
    if influence["full_slope"] > 0.0:
        flippers = [influence["loo_slope_min_symbol"]]
    elif influence["full_slope"] < 0.0:
        flippers = [influence["loo_slope_max_symbol"]]
    else:
        flippers = [influence["loo_slope_min_symbol"], influence["loo_slope_max_symbol"]]
    return (
        "The slope does **not** keep one sign under every single-symbol removal (it "
        f"reaches zero or flips when dropping {' and '.join(flippers)}), so the "
        "direction of the break depends on individual symbols."
    )


def _loo_r2_sentence(influence: dict) -> str:
    """Consequence of the drop-one-out R² range, computed from the range itself."""
    full = influence["full_r2"]
    swing = (influence["loo_r2_max"] - influence["loo_r2_min"]) / full if full > 0.0 else float("inf")
    if swing >= LOO_R2_SWING_LARGE:
        return (
            f"R² spans {swing:.0%} of its full-sample value across the drops (at or above "
            f"{LOO_R2_SWING_LARGE:.0%}), so the strength of the break is outlier-sensitive."
        )
    return (
        f"R² spans {swing:.0%} of its full-sample value across the drops (below "
        f"{LOO_R2_SWING_LARGE:.0%}), so no single symbol moves the strength of the break "
        "much."
    )


def _write_md(
    out_dir: Path,
    baseline_label: str,
    baseline_summary: dict,
    regime_summaries: dict[str, dict],
    survivorship_by_label: dict[str, dict],
    overlap_by_label: dict[str, dict],
    universe_accounting_by_label: dict[str, dict],
    rank_corr_by_label: dict[str, dict],
    law_stability: dict,
    ordered_regime_labels: list[str],
    native_regimes: set[str],
) -> None:
    lines: list[str] = []
    lines.append("# Q8: regime comparison, stability of the cross-sectional laws over time")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        f"I load `q4_cross_section.json` (required) and `q6_endogeneity.json` (optional) "
        f"from a baseline directory (`{baseline_label}`) and one or more regime "
        "directories. Each cross-sectional regression (γ̂, p_flip, and α̂_median vs. "
        "log10(activity), the last when Q6 is present) is recomputed from the per-symbol "
        "records with this module's `np.polyfit` OLS. The stored regression blocks in the "
        "upstream jsons are only cross-checked, and a mismatch beyond "
        f"{REGRESSION_MISMATCH_TOL:g} is reported as a warning below."
    )
    lines.append("")
    lines.append(
        "**Survivorship**: baseline symbols absent from a regime's successful set are "
        "non-survivors. Each gets a reason from that regime's Q4 `skips` (below "
        "`min_events`) and `failures` (missing parquet / other exception) when available."
    )
    lines.append("")
    lines.append(
        "**Rank correlation**: Spearman's rho on the symbol overlap for p_flip, γ̂ (and α̂ "
        "when both sides have a Q6 run), as the Pearson correlation of average ranks."
    )
    lines.append("")
    lines.append(
        "**Law-stability verdicts**: a same-sign check on the flip-law slope across the "
        "baseline and every regime, plus each regime's slope ratio to the baseline. "
        "γ-invariance holds iff every regime's (baseline included) γ-vs-activity R² is "
        f"below {GAMMA_FLAT_R2_THRESHOLD:g}. The verdict text is generated from these "
        "values."
    )
    lines.append("")

    lines.append("## Regime table")
    lines.append("")
    lines.append(
        "| regime | universe | n_success | flip slope | flip R² | γ slope | γ R² | γ median (IQR) | "
        "p_flip median | anti-persistent | α median (IQR) | α median, slow-mode fits | n̂_CV median | "
        "fast-mode share |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")

    def _row(label: str, s: dict) -> str:
        flip = s["flip_law"]
        gamma = s["gamma_law"]
        flip_slope = f"{flip['slope']:.4f}" if flip else "n/a"
        flip_r2 = f"{flip['r2']:.4f}" if flip else "n/a"
        gamma_slope = f"{gamma['slope']:.4f}" if gamma else "n/a"
        gamma_r2 = f"{gamma['r2']:.4f}" if gamma else "n/a"
        gamma_med = (
            f"{s['gamma_median']:.4f} ({s['gamma_iqr']:.4f})" if s["gamma_median"] is not None else "n/a"
        )
        p_flip_med = f"{s['p_flip_median']:.4f}" if s["p_flip_median"] is not None else "n/a"
        alpha_med = (
            f"{s['alpha_median']:.4f} ({s['alpha_iqr']:.4f})" if s["alpha_median"] is not None else "n/a"
        )
        cv_med = f"{s['alpha_cv_median']:.4f}" if s.get("alpha_cv_median") is not None else "n/a"
        fast = f"{s['fast_mode_fraction']:.2f}" if s.get("fast_mode_fraction") is not None else "n/a"
        slow = (
            f"{s['alpha_median_slow_mode']:.4f}"
            if s.get("alpha_median_slow_mode") is not None
            else "n/a"
        )
        return (
            f"| {label} | {s['universe']} | {s['n_success']} | {flip_slope} | {flip_r2} | {gamma_slope} | "
            f"{gamma_r2} | {gamma_med} | {p_flip_med} | {s['n_anti_persistent']} | {alpha_med} | "
            f"{slow} | {cv_med} | {fast} |"
        )

    lines.append(_row(baseline_label, baseline_summary))
    for label in ordered_regime_labels:
        lines.append(_row(label, regime_summaries[label]))
    lines.append("")
    lines.extend(_kernel_mode_lines(baseline_label, baseline_summary, regime_summaries, ordered_regime_labels))

    warnings = []
    ordered_labels_with_baseline = ["__baseline__", *ordered_regime_labels]
    for label in ordered_labels_with_baseline:
        s = baseline_summary if label == "__baseline__" else regime_summaries[label]
        display = baseline_label if label == "__baseline__" else label
        for key in ("flip_law_mismatch_warning", "gamma_law_mismatch_warning", "alpha_law_mismatch_warning"):
            w = s.get(key)
            if w:
                warnings.append(f"- **{display}** ({key}): {w}")
    if warnings:
        lines.append("## Regression cross-check warnings")
        lines.append("")
        lines.append(
            "These recomputed regressions disagreed with the stored json's own regression "
            "block beyond tolerance:"
        )
        lines.append("")
        lines.extend(warnings)
        lines.append("")

    lines.append("## Law-stability verdicts")
    lines.append("")
    same_sign = law_stability["flip_law_same_sign_all_regimes"]
    if same_sign is None:
        lines.append(
            "**Flip-law sign stability**: not evaluable (baseline flip-law slope is not "
            "estimable, zero, or no regime has an estimable flip-law slope)."
        )
    elif same_sign:
        lines.append(
            "**Flip-law sign stability**: the flip-law slope has the **same sign** in every "
            "regime as in the baseline, so the direction of the p_flip-vs-activity "
            "relationship is stable across regimes."
        )
        flat = law_stability.get("flip_law_flat_regimes") or []
        if flat:
            lines.append("")
            lines.append(
                f"The sign agreement is weaker than it looks. In {', '.join(flat)} the slope "
                f"is within {FLIP_SLOPE_MIN_SE:g} standard errors of zero, indistinguishable "
                "from zero, so its sign carries no information. The law is absent there, "
                "not confirmed."
            )
    else:
        flipped = [
            label
            for label, slope in law_stability["flip_law_slope_by_label"].items()
            if label != "__baseline__"
            and np.sign(slope) != np.sign(law_stability["flip_law_slope_by_label"]["__baseline__"])
        ]
        lines.append(
            "**Flip-law sign stability**: the flip-law slope **changes sign** relative to the "
            f"baseline in at least one regime ({', '.join(flipped) if flipped else 'see table'}). "
            "The direction of the p_flip-vs-activity relationship does not hold across "
            "regimes."
        )
    lines.append("")

    ratios = law_stability["flip_law_slope_ratio_vs_baseline"]
    if ratios:
        lines.append("Flip-law slope ratio vs. baseline, per regime:")
        lines.append("")
        for label in ordered_regime_labels:
            if label not in ratios:
                continue
            ratio = ratios[label]
            lines.append(f"- {label}: {ratio:.4f}x baseline slope" if ratio is not None else f"- {label}: n/a")
        lines.append("")

    gamma_inv = law_stability["gamma_invariant_all_regimes"]
    if gamma_inv is None:
        lines.append(
            "**γ invariance**: not evaluable (no regime has an estimable γ-vs-activity "
            "regression)."
        )
    elif gamma_inv:
        lines.append(
            f"**γ invariance**: every regime's γ-vs-activity R² is below "
            f"{GAMMA_FLAT_R2_THRESHOLD:g}, so γ shows **no detectable activity dependence in "
            "any regime**, consistent with liquidity-invariance holding across time."
        )
    else:
        above = [
            label for label, r2 in law_stability["gamma_r2_by_label"].items() if r2 >= GAMMA_FLAT_R2_THRESHOLD
        ]
        lines.append(
            f"**γ invariance**: at least one regime's γ-vs-activity R² is at or above "
            f"{GAMMA_FLAT_R2_THRESHOLD:g} ({', '.join(above)}), so γ's liquidity-invariance "
            "does **not** hold in every regime examined."
        )
    lines.append("")

    for label in ordered_regime_labels:
        if label not in native_regimes:
            continue
        display = label
        flip_slope = law_stability["flip_law_slope_by_label"].get(label)
        baseline_flip_slope = law_stability["flip_law_slope_by_label"].get("__baseline__")
        gamma_r2 = law_stability["gamma_r2_by_label"].get(label)
        lines.append(f"### Survivorship-free test: {display} (native universe)")
        lines.append("")
        lines.append(
            f"**{display}** was run on the market's own universe for that period, not the "
            "baseline's fixed list, so the verdicts below are not confounded by "
            "survivorship."
        )
        lines.append("")
        if flip_slope is None or baseline_flip_slope is None or baseline_flip_slope == 0.0:
            lines.append(
                f"- Flip-law slope for {display}: not evaluable against the baseline (one or "
                "both slopes not estimable)."
            )
        elif not law_stability["flip_law_distinguishable_by_label"].get(label, True):
            lines.append(
                f"- Flip-law slope for {display} ({flip_slope:.4f}) is within "
                f"{FLIP_SLOPE_MIN_SE:g} standard errors of zero, indistinguishable from zero. The "
                "flip law is **absent** in this survivorship-free test, so its direction "
                "is neither confirmed nor reversed."
            )
        elif np.sign(flip_slope) == np.sign(baseline_flip_slope):
            lines.append(
                f"- Flip-law slope for {display} ({flip_slope:.4f}) has the **same sign** as "
                f"the baseline ({baseline_flip_slope:.4f}), so the flip law's direction "
                "survives this survivorship-free test."
            )
        else:
            lines.append(
                f"- Flip-law slope for {display} ({flip_slope:.4f}) has the **opposite sign** "
                f"from the baseline ({baseline_flip_slope:.4f}), so the flip law's direction "
                "does **not** survive this survivorship-free test."
            )
        if gamma_r2 is None:
            lines.append(f"- γ-vs-activity R² for {display}: not evaluable.")
        elif gamma_r2 < GAMMA_FLAT_R2_THRESHOLD:
            g_law = regime_summaries[label]["gamma_law"]
            g_t = g_law["slope"] / g_law["stderr"] if g_law["stderr"] > 0 else float("inf")
            if abs(g_t) >= FLIP_SLOPE_MIN_SE:
                lines.append(
                    f"- γ-vs-activity R² for {display} ({gamma_r2:.4f}) is below "
                    f"{GAMMA_FLAT_R2_THRESHOLD:g}, but the slope ({g_law['slope']:.4f}, "
                    f"{g_t:.1f} standard errors) is distinguishable from zero. That is a "
                    "weak but nonzero activity dependence, not strict flatness."
                )
            else:
                lines.append(
                    f"- γ-vs-activity R² for {display} ({gamma_r2:.4f}) is below "
                    f"{GAMMA_FLAT_R2_THRESHOLD:g} and the slope is within "
                    f"{FLIP_SLOPE_MIN_SE:g} standard errors of zero. γ remains flat "
                    "(liquidity-invariant) in this survivorship-free test."
                )
        else:
            lines.append(
                f"- γ-vs-activity R² for {display} ({gamma_r2:.4f}) is at or above "
                f"{GAMMA_FLAT_R2_THRESHOLD:g}. γ shows detectable activity dependence in this "
                "survivorship-free test, so the liquidity-invariance finding breaks down here."
            )
        lines.append("")

    above_threshold = [
        label for label, r2 in law_stability["gamma_r2_by_label"].items() if r2 >= GAMMA_FLAT_R2_THRESHOLD
    ]
    if above_threshold:
        lines.append("### γ-break outlier sensitivity (drop-one-out)")
        lines.append("")
        for label in above_threshold:
            display = baseline_label if label == "__baseline__" else label
            summary = baseline_summary if label == "__baseline__" else regime_summaries[label]
            influence = summary.get("gamma_influence")
            if influence is None:
                continue
            top = influence["top_cooks_d"]
            top_desc = "; ".join(
                f"{t['symbol']} (Cook's D={t['cooks_d']:.3f}, leverage={t['leverage']:.3f})" for t in top
            )
            lines.append(
                f"For **{display}** (n={influence['n']}, full-sample slope="
                f"{influence['full_slope']:.4f}, R²={influence['full_r2']:.4f}), refitting γ "
                "vs. log10(activity) with each symbol removed in turn gives an **R² range of "
                f"[{influence['loo_r2_min']:.4f} (dropping {influence['loo_r2_min_symbol']}), "
                f"{influence['loo_r2_max']:.4f} (dropping {influence['loo_r2_max_symbol']})]** "
                f"and a **slope range of [{influence['loo_slope_min']:.4f} (dropping "
                f"{influence['loo_slope_min_symbol']}), {influence['loo_slope_max']:.4f} "
                f"(dropping {influence['loo_slope_max_symbol']})]**. The highest-influence "
                f"points by Cook's distance are {top_desc}. "
                f"{_loo_slope_sentence(influence)} {_loo_r2_sentence(influence)}"
            )
            lines.append("")

    if survivorship_by_label:
        lines.append("## Survivorship")
        lines.append("")
        lines.append(
            "Fixed-universe regimes only. A native-universe regime was run on its own "
            "requested universe, not the baseline's, so survivorship does not apply to it "
            "(see Overlap)."
        )
        lines.append("")
        for label in ordered_regime_labels:
            if label not in survivorship_by_label:
                continue
            surv = survivorship_by_label[label]
            lines.append(
                f"**{label}**: {surv['n_survivors']}/{surv['n_baseline']} baseline symbols survive "
                f"into this regime's successful set ({surv['n_regime']} symbols total in this "
                f"regime). {len(surv['non_survivors'])} non-survivor(s)."
            )
            lines.append("")
            if surv["non_survivors"]:
                lines.append("| symbol | reason |")
                lines.append("|---|---|")
                for ns in surv["non_survivors"]:
                    lines.append(f"| {ns['symbol']} | {ns['reason']} |")
                lines.append("")

    if overlap_by_label:
        lines.append("## Overlap (native-universe regimes)")
        lines.append("")
        lines.append(
            "Survivorship does not apply to a native-universe regime, since a symbol "
            "absent from it may not have existed yet. I report the overlap between the "
            "baseline's successful symbols and the regime's own, with Spearman rank "
            "correlation on that overlap."
        )
        lines.append("")
        lines.append(
            "| regime | n baseline | n regime | n overlap | baseline-only | regime-only | "
            "p_flip Spearman ρ | γ Spearman ρ |"
        )
        lines.append("|---|---|---|---|---|---|---|---|")
        for label in ordered_regime_labels:
            if label not in overlap_by_label:
                continue
            ov = overlap_by_label[label]
            lines.append(
                f"| {label} | {ov['n_baseline']} | {ov['n_regime']} | {ov['n_overlap']} | "
                f"{ov['n_baseline_only']} | {ov['n_regime_only']} | "
                f"{_fmt_corr(ov['p_flip_spearman'])} | {_fmt_corr(ov['gamma_spearman'])} |"
            )
        lines.append("")
        lines.extend(_cohort_split_lines(baseline_label, overlap_by_label, ordered_regime_labels))

    if universe_accounting_by_label:
        lines.append("### Universe accounting (own requested universe, per regime)")
        lines.append("")
        lines.append(
            "Each regime's full requested universe (the baseline's list for a "
            "fixed-universe regime, its own native universe otherwise) splits into "
            "successful (passed `min_events`), skipped (downloaded but below `min_events`), "
            "and failed (no data for that period). The three sum to that regime's requested "
            "universe size by construction of the Q4 run."
        )
        lines.append("")
        lines.append("| regime | requested | successful | skipped (below floor) | failed (no data) | reconciles |")
        lines.append("|---|---|---|---|---|---|")
        for label in ordered_regime_labels:
            if label not in universe_accounting_by_label:
                continue
            ua = universe_accounting_by_label[label]
            lines.append(
                f"| {label} | {ua['n_requested']} | {ua['n_successful']} | "
                f"{ua['n_skipped_below_floor']} | {ua['n_failed_no_data']} | "
                f"{'yes' if ua['reconciles'] else 'NO, see json'} |"
            )
        lines.append("")
        for label in ordered_regime_labels:
            ua = universe_accounting_by_label.get(label)
            if ua is None:
                continue
            if ua["download_missing_cross_check"] is not None:
                lines.append(f"- **{label}** download-missing cross-check: {ua['download_missing_cross_check']}")
            if ua["universe_mismatch_warning"] is not None:
                lines.append(f"- **{label}** WARNING: {ua['universe_mismatch_warning']}")
        lines.append("")

    lines.append("## Symbol-level rank correlation")
    lines.append("")
    lines.append("| regime | n overlap | p_flip Spearman ρ | γ Spearman ρ | α overlap n | α Spearman ρ |")
    lines.append("|---|---|---|---|---|---|")
    for label in ordered_regime_labels:
        rc = rank_corr_by_label[label]
        lines.append(
            f"| {label} | {rc['n_overlap']} | {_fmt_corr(rc['p_flip_spearman'])} | "
            f"{_fmt_corr(rc['gamma_spearman'])} | {rc['alpha_n_overlap']} | "
            f"{_fmt_corr(rc['alpha_spearman'])} |"
        )
    lines.append("")

    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "- **The `min_events` filter shifts membership across regimes**, so the "
        "successful set is not a fixed panel. Some non-survivors are below the activity "
        "bar in that regime, not delisted. The skip/failure reasons above say which."
    )
    if overlap_by_label:
        lines.append(
            "- **Fixed and native universes answer different questions**: fixed-universe "
            "regimes re-run the baseline's symbol list (`results/universe_2023-06.txt`) and "
            "track the original panel. "
            f"Native-universe regimes ({', '.join(sorted(overlap_by_label))}) include later "
            "listings, which differ in composition (new contract types as well as new "
            "coins). The cohort split above separates the two. Both apply the same "
            "min_events floor."
        )
    else:
        lines.append(
            "- **The regime universe is fixed to the baseline symbol list** (Q4/Q6 run "
            "against `results/universe_2023-06.txt`), so symbols listed after the baseline "
            "period are excluded. The survivorship analysis says nothing about new "
            "listings, only about the fate of the original panel."
        )
    lines.append(
        "- **Regression stderr and R² inherit the heteroskedasticity caveat** in "
        "`q4_cross_section.md` and `q6_endogeneity.md` and are descriptive, not "
        "confidence intervals."
    )
    lines.append(
        "- **Spearman rho on a possibly small overlap**: rank correlation is only as "
        "informative as the overlap allows. Weight a small `n_overlap` accordingly."
    )
    lines.append("")

    (out_dir / "q8_regimes.md").write_text("\n".join(lines))
