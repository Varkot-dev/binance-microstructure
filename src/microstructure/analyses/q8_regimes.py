"""Q8: regime comparator, does the cross-sectional law hold across time?

Tests whether the Q4/Q6 cross-sectional findings from a single month (June
2023, the baseline) survive in other market regimes. This module never
touches raw data or `data/`: it is a downstream comparator that loads
already-computed `q4_cross_section.json` (required) and
`q6_endogeneity.json` (optional; a regime dir may have no Q6 run) from a
baseline directory and one or more regime directories, then:

1. Recomputes every cross-sectional regression (γ̂ vs log10(activity), p_flip
   vs log10(activity), and α̂_median vs log10(activity) when Q6 is present)
   from the per-symbol records with its own numpy OLS. The upstream json's
   stored `regressions` / `activity_regression` blocks are not trusted: the
   recomputed numbers are cross-checked against them and any material
   mismatch becomes an explicit warning in the output json (it would mean the
   OLS implementations disagree or the upstream json was edited or produced
   by a different code version).
2. Cross-regime comparison: symbol-overlap sets (baseline ∩ each regime),
   survivorship (baseline symbols absent from a regime, split into "skipped
   below min_events" vs "failed/missing" using that regime's own q4
   `skips`/`failures` lists), Spearman rank correlation of p_flip / γ / α
   across each regime pair on the overlap (numpy average ranks, no scipy),
   and a law-stability table: same-sign check on the flip-law slope across
   regimes, slope ratio vs. baseline, and a γ-invariance verdict (flat in
   every regime iff every regime's γ-vs-activity R² < 0.05).
3. Outputs `q8_regimes.{md,json,png}`; the png has three panels (flip-law
   overlay across regimes, γ-vs-activity overlay, and a symbol-level p_flip
   baseline-vs-regime scatter with a y=x line for the first non-baseline
   regime, if any).

The law-stability verdicts in the md are phrased from the recomputed numbers
(f-strings driven by sign/ratio/R² comparisons); the template does not
hardcode which conclusion ("law holds" vs "law breaks down") is correct.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from microstructure.analyses.q8_common import (
    FAST_MODE_BETA,
    FLIP_SLOPE_MIN_SE,
    GAMMA_FLAT_R2_THRESHOLD,
    REGRESSION_MISMATCH_TOL,
    _average_ranks,  # noqa: F401 - re-exported; tests import it from here
    _chrono_key,
    _ols_with_intercept,
    spearman_corr,
)
from microstructure.analyses.q8_report import (
    _loo_r2_sentence,  # noqa: F401 - re-exported; tests import it from here
    _loo_slope_sentence,  # noqa: F401 - re-exported; tests import it from here
    _write_md,
)
from microstructure.analyses.q8_report import _plot as _plot_figure

# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_regime(regime_dir: Path) -> dict:
    """Load a regime's q4 (required) and q6 (optional) json.

    Returns {"q4": <dict>, "q6": <dict | None>}. Raises FileNotFoundError
    with a clear message if q4_cross_section.json is absent — a regime
    dir with no Q4 run is not a valid input to this comparator at all,
    unlike Q6, which is optional.
    """
    q4_path = regime_dir / "q4_cross_section.json"
    if not q4_path.exists():
        raise FileNotFoundError(f"required q4_cross_section.json not found in {regime_dir}")
    q6_path = regime_dir / "q6_endogeneity.json"
    q6 = _load_json(q6_path) if q6_path.exists() else None
    return {"q4": _load_json(q4_path), "q6": q6}


# ---------------------------------------------------------------------------
# OLS (own implementation — never trust the upstream jsons' regression blocks)
# ---------------------------------------------------------------------------


def _recompute_q4_regressions(q4_records: list[dict]) -> dict:
    """Recompute gamma_vs_activity and p_flip_vs_activity from raw records."""
    if not q4_records:
        return {"gamma_vs_activity": None, "p_flip_vs_activity": None}
    log_n = np.array([np.log10(r["n_events"]) for r in q4_records])
    gamma = np.array([r["gamma"] for r in q4_records])
    p_flip = np.array([r["p_flip"] for r in q4_records])
    return {
        "gamma_vs_activity": _ols_with_intercept(log_n, gamma),
        "p_flip_vs_activity": _ols_with_intercept(log_n, p_flip),
    }


def _gamma_influence(q4_records: list[dict]) -> dict | None:
    """Drop-one-out + Cook's distance for the γ-vs-log10(activity) regression.

    Quantifies how outlier-sensitive a regime's γ law is. For each symbol, refits the regression with that
    symbol removed and records the resulting slope/R², plus each point's
    Cook's distance (leverage-weighted squared residual) on the full fit.
    Returns None if fewer than 4 records (need >=3 after one drop).
    """
    if len(q4_records) < 4:
        return None
    names = [r["symbol"] for r in q4_records]
    x = np.array([np.log10(r["n_events"]) for r in q4_records])
    y = np.array([r["gamma"] for r in q4_records])
    n = x.size

    full = _ols_with_intercept(x, y)
    if full is None:
        return None

    design = np.column_stack([np.ones(n), x])
    hat = design @ np.linalg.inv(design.T @ design) @ design.T
    leverage = np.diag(hat)
    resid = y - (full["intercept"] + full["slope"] * x)
    p_params = 2
    mse = float(resid @ resid) / (n - p_params)
    cook_d = (resid**2 / (p_params * mse)) * (leverage / (1.0 - leverage) ** 2)

    per_symbol = []
    for i in range(n):
        keep = np.ones(n, dtype=bool)
        keep[i] = False
        refit = _ols_with_intercept(x[keep], y[keep])
        per_symbol.append(
            {
                "symbol": names[i],
                "cooks_d": float(cook_d[i]),
                "leverage": float(leverage[i]),
                "loo_slope": refit["slope"] if refit else None,
                "loo_r2": refit["r2"] if refit else None,
                "delta_r2": (refit["r2"] - full["r2"]) if refit else None,
            }
        )

    loo_slope = [p["loo_slope"] for p in per_symbol if p["loo_slope"] is not None]
    by_cook = sorted(per_symbol, key=lambda p: -p["cooks_d"])
    min_r2_entry = min(per_symbol, key=lambda p: p["loo_r2"])
    max_r2_entry = max(per_symbol, key=lambda p: p["loo_r2"])
    min_slope_entry = min(per_symbol, key=lambda p: p["loo_slope"])
    max_slope_entry = max(per_symbol, key=lambda p: p["loo_slope"])

    return {
        "full_slope": full["slope"],
        "full_r2": full["r2"],
        "n": n,
        "loo_r2_min": min_r2_entry["loo_r2"],
        "loo_r2_min_symbol": min_r2_entry["symbol"],
        "loo_r2_max": max_r2_entry["loo_r2"],
        "loo_r2_max_symbol": max_r2_entry["symbol"],
        "loo_slope_min": min_slope_entry["loo_slope"],
        "loo_slope_min_symbol": min_slope_entry["symbol"],
        "loo_slope_max": max_slope_entry["loo_slope"],
        "loo_slope_max_symbol": max_slope_entry["symbol"],
        "slope_stays_positive_every_drop": bool(all(s > 0 for s in loo_slope)) if loo_slope else None,
        "top_cooks_d": by_cook[:3],
        "per_symbol": per_symbol,
    }


def _recompute_q6_regression(q6_records: list[dict]) -> dict | None:
    if not q6_records:
        return None
    log_n = np.array([np.log10(r["n_events"]) for r in q6_records])
    alpha_med = np.array([r["alpha_median"] for r in q6_records])
    return _ols_with_intercept(log_n, alpha_med)


def _reg_mismatch(recomputed: dict | None, stored: dict | None) -> str | None:
    """Compare a recomputed regression dict to the stored one; return a warning string or None.

    Both None -> no mismatch (both agree nothing was estimable). One None
    and the other not -> mismatch (estimability itself disagrees). Both
    present -> compare slope/intercept/r2 within REGRESSION_MISMATCH_TOL.
    """
    if recomputed is None and stored is None:
        return None
    if recomputed is None or stored is None:
        return (
            f"estimability mismatch: recomputed={'present' if recomputed else 'None'}, "
            f"stored={'present' if stored else 'None'}"
        )
    diffs = {
        k: abs(recomputed[k] - stored[k])
        for k in ("slope", "intercept", "r2", "n")
        if k in stored
    }
    bad = {k: v for k, v in diffs.items() if v > REGRESSION_MISMATCH_TOL}
    if not bad:
        return None
    parts = ", ".join(f"{k} differs by {v:.6g}" for k, v in bad.items())
    return f"recomputed regression disagrees with stored json: {parts}"


# ---------------------------------------------------------------------------
# Spearman rank correlation (own implementation, no scipy)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Cross-regime comparison
# ---------------------------------------------------------------------------


def _symbol_set(q4: dict) -> set[str]:
    return {r["symbol"] for r in q4["symbols"]}


def _skip_fail_reason(q4: dict, symbol: str) -> str:
    """Look up why `symbol` is absent from a regime's successful q4 set.

    Checks that regime's own `skips` (below min_events) and `failures`
    (missing parquet / other exception) lists for a reason string. Falls
    back to a generic "absent, no reason recorded" if the symbol appears
    in neither list (e.g. it was never in that regime's requested
    universe at all).
    """
    for s in q4.get("skips", []):
        if s["symbol"] == symbol:
            return f"skipped below min_events (n_events={s.get('n_events', '?')})"
    for f in q4.get("failures", []):
        if f["symbol"] == symbol:
            return f"failed/missing ({f.get('reason', 'no reason recorded')})"
    return "absent from regime universe (no skip/failure record found)"


def _universe_accounting(
    regime_q4: dict,
    download_missing_symbols: set[str] | None,
    *,
    is_native: bool = False,
    baseline_n_requested: int | None = None,
) -> dict:
    """Three-bucket breakdown of the regime's requested universe.

    Buckets: successful (passes min_events and was analyzed), skipped
    (downloaded but below the min_events floor), failed (not downloaded /
    parquet missing). They are read from the regime's own q4 json
    (`n_symbols_successful` / `n_symbols_skipped` / `n_symbols_failed` and the
    `failures` list) and sum to that regime's own `n_symbols_requested`, for a
    fixed-universe and a native-universe regime alike, never to the
    baseline's.

    `download_missing_symbols` is an optional external list of symbols known to
    have no downloadable data for this period (e.g. a
    `nonsurvivors_*_download.txt` file). It is cross-checked against the
    regime's `failures` symbols and a mismatch becomes a warning.

    `is_native` / `baseline_n_requested`: if the regime is not flagged native
    and its `n_symbols_requested` differs from the baseline's, the caller
    probably meant a fixed universe or forgot the native flag; this is
    surfaced as `universe_mismatch_warning` instead of silently driving the
    survivorship math against a differently-sized universe.
    """
    n_requested = regime_q4.get("n_symbols_requested")
    n_successful = regime_q4.get("n_symbols_successful")
    n_skipped = regime_q4.get("n_symbols_skipped")
    n_failed = regime_q4.get("n_symbols_failed")
    reconciles = (
        n_requested is not None
        and n_successful is not None
        and n_skipped is not None
        and n_failed is not None
        and n_successful + n_skipped + n_failed == n_requested
    )

    universe_mismatch_warning = None
    if (
        not is_native
        and baseline_n_requested is not None
        and n_requested is not None
        and n_requested != baseline_n_requested
    ):
        universe_mismatch_warning = (
            "universe mismatch without native flag: this regime's n_symbols_requested "
            f"({n_requested}) differs from the baseline's ({baseline_n_requested}) but the "
            "regime was not passed in native_regimes — survivorship is still being computed "
            "against the baseline's symbol set; pass this label in native_regimes if this "
            "regime was actually run on its own, different universe."
        )

    accounting = {
        "n_requested": n_requested,
        "n_successful": n_successful,
        "n_skipped_below_floor": n_skipped,
        "n_failed_no_data": n_failed,
        "reconciles": reconciles,
        "download_missing_cross_check": None,
        "universe_mismatch_warning": universe_mismatch_warning,
    }

    if download_missing_symbols is not None:
        failure_symbols = {f["symbol"] for f in regime_q4.get("failures", [])}
        if failure_symbols == download_missing_symbols:
            accounting["download_missing_cross_check"] = (
                f"matches: {len(failure_symbols)} symbols in both the q4 `failures` list "
                "and the external download-missing file"
            )
        else:
            only_in_json = sorted(failure_symbols - download_missing_symbols)
            only_in_file = sorted(download_missing_symbols - failure_symbols)
            accounting["download_missing_cross_check"] = (
                "MISMATCH between q4 `failures` "
                f"({len(failure_symbols)} symbols) and the external download-missing file "
                f"({len(download_missing_symbols)} symbols): "
                f"{len(only_in_json)} only in failures ({', '.join(only_in_json[:10])}"
                f"{'...' if len(only_in_json) > 10 else ''}), "
                f"{len(only_in_file)} only in the download-missing file "
                f"({', '.join(only_in_file[:10])}{'...' if len(only_in_file) > 10 else ''})"
            )

    return accounting


def _survivorship(baseline_q4: dict, regime_q4: dict) -> dict:
    """Baseline successful symbols minus this regime's successful symbols."""
    baseline_symbols = _symbol_set(baseline_q4)
    regime_symbols = _symbol_set(regime_q4)
    survivors = sorted(baseline_symbols & regime_symbols)
    non_survivors = sorted(baseline_symbols - regime_symbols)
    return {
        "n_baseline": len(baseline_symbols),
        "n_regime": len(regime_symbols),
        "n_survivors": len(survivors),
        "survivors": survivors,
        "non_survivors": [
            {"symbol": sym, "reason": _skip_fail_reason(regime_q4, sym)}
            for sym in non_survivors
        ],
    }


def _overlap_comparison(baseline_q4: dict, regime_q4: dict) -> dict:
    """Baseline-vs-regime overlap block for a native-universe regime.

    Used instead of survivorship (which assumes a shared requested universe)
    when the regime ran on its own market-native universe. Counting absent
    baseline symbols would conflate delistings with symbols never requested, so
    this reports the three-way split (n_overlap, baseline-only, regime-only)
    plus Spearman rank correlation of p_flip/gamma on the overlap, the
    survivorship-free comparison.
    """
    baseline_symbols = _symbol_set(baseline_q4)
    regime_symbols = _symbol_set(regime_q4)
    overlap = sorted(baseline_symbols & regime_symbols)
    baseline_only = sorted(baseline_symbols - regime_symbols)
    regime_only = sorted(regime_symbols - baseline_symbols)

    base_records, regime_records = _overlap_records(baseline_q4, regime_q4)
    p_flip_spearman = None
    gamma_spearman = None
    if overlap:
        base_p_flip = np.array([r["p_flip"] for r in base_records])
        regime_p_flip = np.array([r["p_flip"] for r in regime_records])
        base_gamma = np.array([r["gamma"] for r in base_records])
        regime_gamma = np.array([r["gamma"] for r in regime_records])
        p_flip_spearman = spearman_corr(base_p_flip, regime_p_flip)
        gamma_spearman = spearman_corr(base_gamma, regime_gamma)

    return {
        "n_baseline": len(baseline_symbols),
        "n_regime": len(regime_symbols),
        "n_overlap": len(overlap),
        "n_baseline_only": len(baseline_only),
        "n_regime_only": len(regime_only),
        "overlap_symbols": overlap,
        "baseline_only_symbols": baseline_only,
        "regime_only_symbols": regime_only,
        "p_flip_spearman": p_flip_spearman,
        "gamma_spearman": gamma_spearman,
        "cohort_laws": {
            "baseline_on_overlap": _recompute_q4_regressions(base_records),
            "regime_on_overlap": _recompute_q4_regressions(regime_records),
            "regime_only": _recompute_q4_regressions(
                [r for r in regime_q4["symbols"] if r["symbol"] in set(regime_only)]
            ),
        },
    }


def _overlap_records(baseline_q4: dict, regime_q4: dict) -> tuple[list[dict], list[dict]]:
    """Per-symbol q4 records for the baseline and regime, restricted to the overlap, symbol-sorted identically."""
    baseline_by_symbol = {r["symbol"]: r for r in baseline_q4["symbols"]}
    regime_by_symbol = {r["symbol"]: r for r in regime_q4["symbols"]}
    overlap = sorted(set(baseline_by_symbol) & set(regime_by_symbol))
    return (
        [baseline_by_symbol[s] for s in overlap],
        [regime_by_symbol[s] for s in overlap],
    )


def _q6_overlap_alpha(baseline_q6: dict | None, regime_q6: dict | None) -> tuple[list[str], np.ndarray, np.ndarray] | None:
    if baseline_q6 is None or regime_q6 is None:
        return None
    baseline_by_symbol = {r["symbol"]: r["alpha_median"] for r in baseline_q6["records"]}
    regime_by_symbol = {r["symbol"]: r["alpha_median"] for r in regime_q6["records"]}
    overlap = sorted(set(baseline_by_symbol) & set(regime_by_symbol))
    if not overlap:
        return None
    base_arr = np.array([baseline_by_symbol[s] for s in overlap])
    regime_arr = np.array([regime_by_symbol[s] for s in overlap])
    return overlap, base_arr, regime_arr


def _regime_summary(q4: dict, q6: dict | None, *, universe: str = "fixed") -> dict:
    """Per-regime stats: n_success, recomputed regressions (+ mismatch warnings), medians/IQRs.

    `universe` is "fixed" (run on the baseline's requested universe) or
    "native" (run on the market's own universe for that period); it is carried
    into the regime and law-stability tables.
    """
    records = q4["symbols"]
    recomputed = _recompute_q4_regressions(records)
    gamma_mismatch = _reg_mismatch(
        recomputed["gamma_vs_activity"], q4.get("regressions", {}).get("gamma_vs_activity")
    )
    flip_mismatch = _reg_mismatch(
        recomputed["p_flip_vs_activity"], q4.get("regressions", {}).get("p_flip_vs_activity")
    )

    gamma_vals = np.array([r["gamma"] for r in records]) if records else np.array([])
    p_flip_vals = np.array([r["p_flip"] for r in records]) if records else np.array([])
    n_anti_persistent = int(np.sum(p_flip_vals > 0.5)) if records else 0

    summary = {
        "period": q4.get("period"),
        "universe": universe,
        "n_success": len(records),
        "n_skipped": q4.get("n_symbols_skipped"),
        "n_failed": q4.get("n_symbols_failed"),
        "flip_law": recomputed["p_flip_vs_activity"],
        "flip_law_mismatch_warning": flip_mismatch,
        "gamma_law": recomputed["gamma_vs_activity"],
        "gamma_law_mismatch_warning": gamma_mismatch,
        "gamma_influence": _gamma_influence(records),
        "gamma_median": float(np.median(gamma_vals)) if gamma_vals.size else None,
        "gamma_iqr": (
            float(np.percentile(gamma_vals, 75) - np.percentile(gamma_vals, 25))
            if gamma_vals.size
            else None
        ),
        "p_flip_median": float(np.median(p_flip_vals)) if p_flip_vals.size else None,
        "n_anti_persistent": n_anti_persistent,
    }

    if q6 is not None:
        q6_records = q6["records"]
        recomputed_q6 = _recompute_q6_regression(q6_records)
        alpha_mismatch = _reg_mismatch(recomputed_q6, q6.get("activity_regression"))
        alpha_vals = np.array([r["alpha_median"] for r in q6_records]) if q6_records else np.array([])
        summary["alpha_law"] = recomputed_q6
        summary["alpha_law_mismatch_warning"] = alpha_mismatch
        summary["alpha_median"] = float(np.median(alpha_vals)) if alpha_vals.size else None
        summary["alpha_iqr"] = (
            float(np.percentile(alpha_vals, 75) - np.percentile(alpha_vals, 25))
            if alpha_vals.size
            else None
        )
        cv_vals = np.array([r["alpha_cv"] for r in q6_records]) if q6_records else np.array([])
        beta_vals = np.array([r["median_beta"] for r in q6_records]) if q6_records else np.array([])
        summary["alpha_cv_median"] = float(np.median(cv_vals)) if cv_vals.size else None
        summary["fast_mode_fraction"] = (
            float(np.mean(beta_vals > FAST_MODE_BETA)) if beta_vals.size else None
        )
        slow_alpha = alpha_vals[beta_vals <= FAST_MODE_BETA] if beta_vals.size else np.array([])
        summary["alpha_median_slow_mode"] = float(np.median(slow_alpha)) if slow_alpha.size else None
    else:
        summary["alpha_law"] = None
        summary["alpha_law_mismatch_warning"] = None
        summary["alpha_median"] = None
        summary["alpha_iqr"] = None
        summary["alpha_cv_median"] = None
        summary["fast_mode_fraction"] = None
        summary["alpha_median_slow_mode"] = None

    return summary


def _law_stability(baseline_summary: dict, regime_summaries: dict[str, dict]) -> dict:
    """Same-sign / slope-ratio / gamma-invariance verdicts across baseline + all regimes."""
    all_summaries = {"__baseline__": baseline_summary, **regime_summaries}

    flip_slopes = {
        label: s["flip_law"]["slope"] for label, s in all_summaries.items() if s["flip_law"] is not None
    }
    baseline_flip_slope = baseline_summary["flip_law"]["slope"] if baseline_summary["flip_law"] else None

    same_sign = None
    slope_ratios: dict[str, float | None] = {}
    if baseline_flip_slope is not None and baseline_flip_slope != 0.0 and flip_slopes:
        baseline_sign = np.sign(baseline_flip_slope)
        same_sign = all(np.sign(v) == baseline_sign for v in flip_slopes.values())
        for label, slope in flip_slopes.items():
            slope_ratios[label] = slope / baseline_flip_slope if label != "__baseline__" else 1.0

    gamma_r2_values = {
        label: s["gamma_law"]["r2"] for label, s in all_summaries.items() if s["gamma_law"] is not None
    }
    gamma_invariant = (
        all(r2 < GAMMA_FLAT_R2_THRESHOLD for r2 in gamma_r2_values.values())
        if gamma_r2_values
        else None
    )

    universe_by_label = {label: s["universe"] for label, s in all_summaries.items()}

    distinguishable = {
        label: bool(abs(s["flip_law"]["slope"]) >= FLIP_SLOPE_MIN_SE * s["flip_law"]["stderr"])
        for label, s in all_summaries.items()
        if s["flip_law"] is not None
    }
    flat_regimes = [
        label for label, ok in distinguishable.items() if label != "__baseline__" and not ok
    ]

    return {
        "flip_law_same_sign_all_regimes": same_sign,
        "flip_law_distinguishable_by_label": distinguishable,
        "flip_law_flat_regimes": flat_regimes,
        "flip_law_slope_by_label": {k: v for k, v in flip_slopes.items()},
        "flip_law_slope_ratio_vs_baseline": {k: v for k, v in slope_ratios.items() if k != "__baseline__"},
        "gamma_invariant_all_regimes": gamma_invariant,
        "gamma_r2_by_label": gamma_r2_values,
        "gamma_flat_r2_threshold": GAMMA_FLAT_R2_THRESHOLD,
        "universe_by_label": universe_by_label,
    }


def _rank_correlations(
    baseline_q4: dict, baseline_q6: dict | None, regime_q4: dict, regime_q6: dict | None
) -> dict:
    """Spearman rho of p_flip, gamma (and alpha, if both sides have q6) on the symbol overlap."""
    base_records, regime_records = _overlap_records(baseline_q4, regime_q4)
    overlap_symbols = [r["symbol"] for r in base_records]

    result: dict = {"n_overlap": len(overlap_symbols), "symbols": overlap_symbols}

    if overlap_symbols:
        base_p_flip = np.array([r["p_flip"] for r in base_records])
        regime_p_flip = np.array([r["p_flip"] for r in regime_records])
        base_gamma = np.array([r["gamma"] for r in base_records])
        regime_gamma = np.array([r["gamma"] for r in regime_records])
        result["p_flip_spearman"] = spearman_corr(base_p_flip, regime_p_flip)
        result["gamma_spearman"] = spearman_corr(base_gamma, regime_gamma)
    else:
        result["p_flip_spearman"] = None
        result["gamma_spearman"] = None

    alpha_overlap = _q6_overlap_alpha(baseline_q6, regime_q6)
    if alpha_overlap is not None:
        symbols, base_alpha, regime_alpha = alpha_overlap
        result["alpha_n_overlap"] = len(symbols)
        result["alpha_spearman"] = spearman_corr(base_alpha, regime_alpha)
    else:
        result["alpha_n_overlap"] = 0
        result["alpha_spearman"] = None

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _plot(
    out_dir: Path,
    baseline_label: str,
    baseline_q4: dict,
    regime_q4_by_label: dict[str, dict],
) -> None:
    """Render the three-panel figure; `_overlap_records` is passed in so the report module needs no compute import."""
    _plot_figure(out_dir, baseline_label, baseline_q4, regime_q4_by_label, _overlap_records)


def _load_download_missing(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def run_q8(
    out_dir: Path,
    baseline_dir: Path,
    regime_dirs: dict[str, Path],
    baseline_label: str = "2023-06",
    download_missing_paths: dict[str, Path] | None = None,
    native_regimes: frozenset[str] | set[str] = frozenset(),
) -> dict:
    """Compare the Q4/Q6 cross-sectional laws between a baseline period and one or more regimes.

    `regime_dirs` maps a display label (e.g. "2023-07", "2026-07") to the
    directory holding that regime's q4_cross_section.json (+ optional
    q6_endogeneity.json). Only those two json files are read per directory.

    `download_missing_paths` optionally maps the same labels to a plain-text
    file (one symbol per line) of symbols with no downloadable raw data for
    that regime's period (as opposed to downloaded but below `min_events`). It
    is only a cross-check against the regime's q4 `failures` list; the
    universe accounting always comes from the q4 json.

    `native_regimes` is the set of labels (a subset of `regime_dirs`'s keys)
    run against the market's own requested universe for that period instead of
    the baseline's symbol list (e.g. a later-year regime run against that
    year's live listings). For these labels the survivorship block is replaced
    by an overlap block (symbol overlap + Spearman on the overlap), and
    universe accounting uses the regime's own `n_symbols_requested`. Other
    labels use fixed-universe behavior, with a warning when their
    `n_symbols_requested` differs from the baseline's without the native flag
    (see `_universe_accounting`).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline = _load_regime(baseline_dir)
    regimes = {label: _load_regime(path) for label, path in regime_dirs.items()}
    download_missing_paths = download_missing_paths or {}
    native_regimes = set(native_regimes)
    unknown_native = sorted(native_regimes - set(regime_dirs))
    if unknown_native:
        raise ValueError(
            f"native regime label(s) {unknown_native} not among the regime labels "
            f"{sorted(regime_dirs)}"
        )
    baseline_n_requested = baseline["q4"].get("n_symbols_requested")

    ordered_regime_labels = sorted(regime_dirs.keys(), key=_chrono_key)

    baseline_summary = _regime_summary(baseline["q4"], baseline["q6"], universe="fixed")
    regime_summaries = {
        label: _regime_summary(
            r["q4"], r["q6"], universe="native" if label in native_regimes else "fixed"
        )
        for label, r in regimes.items()
    }

    survivorship_by_label = {
        label: _survivorship(baseline["q4"], r["q4"])
        for label, r in regimes.items()
        if label not in native_regimes
    }

    overlap_by_label = {
        label: _overlap_comparison(baseline["q4"], r["q4"])
        for label, r in regimes.items()
        if label in native_regimes
    }

    universe_accounting_by_label = {
        label: _universe_accounting(
            r["q4"],
            _load_download_missing(download_missing_paths[label])
            if label in download_missing_paths
            else None,
            is_native=label in native_regimes,
            baseline_n_requested=baseline_n_requested,
        )
        for label, r in regimes.items()
    }

    rank_corr_by_label = {
        label: _rank_correlations(baseline["q4"], baseline["q6"], r["q4"], r["q6"])
        for label, r in regimes.items()
    }

    law_stability = _law_stability(baseline_summary, regime_summaries)

    result = {
        "baseline_label": baseline_label,
        "regime_labels": list(regime_dirs.keys()),
        "regime_labels_ordered": ordered_regime_labels,
        "native_regimes": sorted(native_regimes),
        "baseline_summary": baseline_summary,
        "regime_summaries": regime_summaries,
        "survivorship": survivorship_by_label,
        "overlap": overlap_by_label,
        "universe_accounting": universe_accounting_by_label,
        "rank_correlations": rank_corr_by_label,
        "law_stability": law_stability,
    }

    _plot(out_dir, baseline_label, baseline["q4"], {label: r["q4"] for label, r in regimes.items()})
    _write_md(
        out_dir,
        baseline_label,
        baseline_summary,
        regime_summaries,
        survivorship_by_label,
        overlap_by_label,
        universe_accounting_by_label,
        rank_corr_by_label,
        law_stability,
        ordered_regime_labels,
        native_regimes,
    )
    (out_dir / "q8_regimes.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Q8: regime comparator")
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--baseline-label", type=str, default="2023-06")
    parser.add_argument(
        "--regime",
        action="append",
        default=[],
        metavar="LABEL=DIR",
        help="a regime directory as LABEL=DIR; repeatable",
    )
    parser.add_argument(
        "--download-missing",
        action="append",
        default=[],
        metavar="LABEL=FILE",
        help=(
            "optional cross-check file of symbols with no downloadable data for that "
            "regime's period, as LABEL=FILE (one symbol per line); repeatable"
        ),
    )
    parser.add_argument(
        "--native",
        action="append",
        default=[],
        metavar="LABEL",
        help=(
            "mark a --regime LABEL as run on the market's own native universe for that "
            "period rather than the baseline's fixed symbol list; repeatable"
        ),
    )
    return parser.parse_args(argv)


def _parse_label_path_args(entries: list[str], flag_name: str) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"{flag_name} must be LABEL=PATH, got: {entry!r}")
        label, _, path_str = entry.partition("=")
        if label in parsed:
            raise ValueError(f"{flag_name} label {label!r} given more than once")
        parsed[label] = Path(path_str)
    return parsed


if __name__ == "__main__":
    args = _parse_args()
    run_q8(
        args.out,
        baseline_dir=args.baseline_dir,
        regime_dirs=_parse_label_path_args(args.regime, "--regime"),
        baseline_label=args.baseline_label,
        download_missing_paths=_parse_label_path_args(args.download_missing, "--download-missing"),
        native_regimes=set(args.native),
    )
