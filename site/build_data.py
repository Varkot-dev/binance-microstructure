"""Derive the site's data slices from the committed results/ artifacts.

Stdlib only. Run from the repo root:

    python site/build_data.py

Writes site/data/*.json. The page loads only those files (plus the figures
copied into site/assets/), never results/ directly, so the deployed site is a
self-contained static bundle and the numbers on it are traceable to exactly one
committed source artifact each.

Every value written here is copied or arithmetically derived from
results/*.json. Nothing is invented, rounded for presentation, or
hand-entered.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
OUT = Path(__file__).resolve().parent / "data"

# The 0.04 floor on the critical-balance band is the measured finite-L
# deconvolution bias at L=300 (results/q5_kernel_panel.md, Methodology). This
# script is stdlib-only, so the value is duplicated from
# microstructure.analyses.q5_kernel_panel.BALANCE_BIAS_FLOOR;
# tests/analyses/test_build_data.py asserts the two stay equal.
BALANCE_BAND_FLOOR = 0.04


def read_result(name: str) -> dict:
    with (RESULTS / name).open() as fh:
        return json.load(fh)


def write_slice(name: str, payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    # Serialize before opening the file so a NaN/inf raises without leaving a truncated slice.
    text = json.dumps(payload, separators=(",", ":"), sort_keys=True, allow_nan=False)
    with path.open("w") as fh:
        fh.write(text + "\n")
    print(f"  {path.relative_to(REPO_ROOT)}  {path.stat().st_size:,} bytes")


def build_cross_section(q5_symbols: set[str]) -> None:
    """Q4: 121-symbol scatter, its two regressions, and the panel overlap."""
    src = read_result("q4_cross_section.json")

    symbols = [
        {
            "symbol": rec["symbol"],
            "n_events": rec["n_events"],
            "log_n": math.log10(rec["n_events"]),
            "gamma": rec["gamma"],
            "stderr": rec["stderr"],
            "acf1": rec["acf1"],
            "p_flip": rec["p_flip"],
            "zigzag_amplitude": rec["zigzag_amplitude"],
            "in_kernel_panel": rec["symbol"] in q5_symbols,
        }
        for rec in src["symbols"]
    ]
    symbols.sort(key=lambda r: r["n_events"], reverse=True)

    # Anti-persistent = p_flip > 0.5 (flips more often than a fair coin).
    by_activity = sorted(symbols, key=lambda r: r["n_events"], reverse=True)
    most_active_20 = by_activity[:20]
    least_active_20 = by_activity[-20:]

    write_slice(
        "cross_section.json",
        {
            "period": src["period"],
            "min_events": src["min_events"],
            "n_requested": src["n_symbols_requested"],
            "n_successful": src["n_symbols_successful"],
            "n_skipped": src["n_symbols_skipped"],
            "symbols": symbols,
            "regressions": src["regressions"],
            "tails": {
                "most_active_anti_persistent": sum(
                    1 for r in most_active_20 if r["p_flip"] > 0.5
                ),
                "least_active_anti_persistent": sum(
                    1 for r in least_active_20 if r["p_flip"] > 0.5
                ),
                "tail_size": 20,
            },
        },
    )


def build_kernels() -> set[str]:
    """Q5: 16 G(l) curves, balance deltas, verdicts."""
    src = read_result("q5_kernel_panel.json")

    records = []
    for rec in src["records"]:
        band = 2 * max(rec["beta_block_sd"], BALANCE_BAND_FLOOR)
        records.append(
            {
                "symbol": rec["symbol"],
                "n_events": rec["n_events"],
                "gamma_week": rec["gamma_week"],
                "beta": rec["beta"],
                "beta_block_sd": rec["beta_block_sd"],
                "balance_delta": rec["balance_delta"],
                "band": band,
                "verdict": rec["verdict"],
                "R1": rec["R1"],
                "G": rec["G"],
                "response": rec["response"],
            }
        )
    records.sort(key=lambda r: r["n_events"], reverse=True)

    write_slice(
        "kernels.json",
        {
            "month": src["month"],
            "start_day": src["start_day"],
            "end_day": src["end_day"],
            "max_lag": src["max_lag"],
            "n_successful": src["n_symbols_successful"],
            "n_consistent": src["n_consistent"],
            "n_violated": src["n_violated"],
            "band_floor": BALANCE_BAND_FLOOR,
            "records": records,
        },
    )
    return {r["symbol"] for r in records}


def build_endogeneity() -> None:
    """Q6: 41-symbol alpha vs activity, and the MLE-vs-CV disagreement."""
    src = read_result("q6_endogeneity.json")

    records = [
        {
            "symbol": rec["symbol"],
            "n_events": rec["n_events"],
            "log_n": math.log10(rec["n_events"]),
            "alpha_median": rec["alpha_median"],
            "alpha_iqr": rec["alpha_iqr"],
            "alpha_cv": rec["alpha_cv"],
            "n_converged": rec["n_converged"],
            "raw_delta": rec["raw_delta"],
            "abs_diff": abs(rec["alpha_cv"] - rec["alpha_median"]),
            "cv_exceeds_mle": rec["alpha_cv"] > rec["alpha_median"],
        }
        for rec in src["records"]
    ]
    records.sort(key=lambda r: r["n_events"], reverse=True)

    alphas = sorted(r["alpha_median"] for r in records)
    cvs = sorted(r["alpha_cv"] for r in records)
    raws = sorted(r["raw_delta"] for r in records)

    write_slice(
        "endogeneity.json",
        {
            "month": src["month"],
            "windows": src["windows"],
            "n_successful": src["n_symbols_successful"],
            "records": records,
            "activity_regression": src["activity_regression"],
            "agreement": src["agreement"],
            "summary": {
                "alpha_median_of_medians": statistics.median(alphas),
                "alpha_min": alphas[0],
                "alpha_max": alphas[-1],
                "cv_median": statistics.median(cvs),
                "n_cv_exceeds_mle": sum(1 for r in records if r["cv_exceeds_mle"]),
                "n_total": len(records),
                "raw_delta_median": statistics.median(raws),
                "raw_delta_max_abs": max(abs(r) for r in raws),
                "distance_from_criticality": 1.0 - statistics.median(alphas),
            },
        },
    )


def build_execution() -> None:
    """Q7: schedule costs with dispersion, calibration grid, per symbol."""
    src = read_result("q7_execution.json")
    ev = src["evaluation"]

    write_slice(
        "execution.json",
        {
            "month": src["month"],
            "horizon_events": src["horizon_events"],
            "n_children": src["n_children"],
            "parent_qty_events_list": src["parent_qty_events_list"],
            "panel_symbols": src["panel_symbols"],
            "calibration": {
                "days": src["calibration"]["days"],
                "grid": src["calibration"]["grid"],
                "scores": src["calibration"]["scores"],
                "chosen_params": src["calibration"]["chosen_params"],
            },
            "evaluation": {
                "days": ev["days"],
                "summary": ev["summary"],
                "per_symbol": ev["per_symbol"],
            },
            "shortfall_unit": src["shortfall_unit"],
            "derived": {
                # Same quantities as results/q7_execution.md Findings: the paired
                # reactive-minus-twap difference and the dispersion ratio.
                "reactive_minus_twap": ev["summary"]["reactive_minus_twap"],
                "sd_ratio_frontloaded_vs_twap": ev["summary"]["sd_ratio_frontloaded_vs_twap"],
                "z_cutoff": 2.0,
            },
        },
    )


def build_regimes() -> None:
    """Q8: the regime table (fixed + native universes), accounting, stability verdicts."""
    src = read_result("q8_regimes.json")

    summaries = {src["baseline_label"]: src["baseline_summary"]}
    summaries.update(src["regime_summaries"])

    stability = src["law_stability"]
    accounting = src["universe_accounting"]
    ranks = src["rank_correlations"]

    def alpha_n(s: dict) -> int | None:
        # Regimes with no Q6 Hawkes run (the native 2026 universe) carry a null
        # alpha_law; emit null rather than a fabricated zero.
        law = s.get("alpha_law")
        return law["n"] if law else None

    def alpha_r2(s: dict) -> float | None:
        law = s.get("alpha_law")
        return law["r2"] if law else None

    distinguishable = stability["flip_law_distinguishable_by_label"]

    def row(label: str) -> dict:
        s = summaries[label]
        stab_key = "__baseline__" if label == src["baseline_label"] else label
        acct = accounting.get(label)
        rank = ranks.get(label)
        return {
            "label": label,
            "is_baseline": label == src["baseline_label"],
            "universe": s.get("universe"),
            "n_success": s["n_success"],
            "flip_slope": s["flip_law"]["slope"],
            "flip_stderr": s["flip_law"]["stderr"],
            "flip_r2": s["flip_law"]["r2"],
            "flip_slope_ratio": stability["flip_law_slope_ratio_vs_baseline"].get(label),
            "gamma_slope": s["gamma_law"]["slope"],
            "gamma_r2": s["gamma_law"]["r2"],
            "gamma_median": s["gamma_median"],
            "p_flip_median": s["p_flip_median"],
            "n_anti_persistent": s["n_anti_persistent"],
            "flip_distinguishable": distinguishable.get(stab_key),
            "alpha_median": s.get("alpha_median"),
            "alpha_n": alpha_n(s),
            "alpha_r2": alpha_r2(s),
            "alpha_cv_median": s.get("alpha_cv_median"),
            "fast_mode_fraction": s.get("fast_mode_fraction"),
            "alpha_median_slow_mode": s.get("alpha_median_slow_mode"),
            # None for the baseline: it is the frame of reference, not a regime
            # measured against one, so it has no accounting or overlap row.
            "requested": acct["n_requested"] if acct else None,
            "n_below_floor": acct["n_skipped_below_floor"] if acct else None,
            "n_no_data": acct["n_failed_no_data"] if acct else None,
            "n_overlap": rank["n_overlap"] if rank else None,
            "p_flip_spearman": rank["p_flip_spearman"] if rank else None,
            # Drop-one-out γ-break sensitivity, present for every regime with at
            # least 4 symbols (the site callout shows it only for regimes above the
            # γ-flat R² threshold); trimmed to what the callout needs, not the
            # full per-symbol array.
            "gamma_influence": (
                {
                    "loo_r2_min": s["gamma_influence"]["loo_r2_min"],
                    "loo_r2_min_symbol": s["gamma_influence"]["loo_r2_min_symbol"],
                    "loo_r2_max": s["gamma_influence"]["loo_r2_max"],
                    "loo_r2_max_symbol": s["gamma_influence"]["loo_r2_max_symbol"],
                    "loo_slope_min": s["gamma_influence"]["loo_slope_min"],
                    "loo_slope_min_symbol": s["gamma_influence"]["loo_slope_min_symbol"],
                    "loo_slope_max": s["gamma_influence"]["loo_slope_max"],
                    "loo_slope_max_symbol": s["gamma_influence"]["loo_slope_max_symbol"],
                    "slope_stays_positive_every_drop": s["gamma_influence"][
                        "slope_stays_positive_every_drop"
                    ],
                    "top_cooks_d_symbols": [
                        t["symbol"] for t in s["gamma_influence"]["top_cooks_d"]
                    ],
                }
                if s.get("gamma_influence")
                else None
            ),
        }

    # regime_labels_ordered lists fixed-universe regimes chronologically followed
    # by native-universe ones; fall back to regime_labels for older artifacts.
    ordered = src.get("regime_labels_ordered") or src["regime_labels"]
    labels = [src["baseline_label"], *ordered]
    write_slice(
        "regimes.json",
        {
            "baseline_label": src["baseline_label"],
            "labels": labels,
            "rows": [row(label) for label in labels],
            "gamma_flat_r2_threshold": stability["gamma_flat_r2_threshold"],
            "flip_same_sign_all_regimes": stability["flip_law_same_sign_all_regimes"],
            "flip_flat_regimes": stability["flip_law_flat_regimes"],
            "native_regimes": src.get("native_regimes", []),
            "gamma_invariant_all_regimes": stability["gamma_invariant_all_regimes"],
        },
    )


def main() -> None:
    print(f"Building site data from {RESULTS.relative_to(REPO_ROOT)}/ ...")
    panel_symbols = build_kernels()
    build_cross_section(panel_symbols)
    build_endogeneity()
    build_execution()
    build_regimes()
    print("Done.")


if __name__ == "__main__":
    main()
