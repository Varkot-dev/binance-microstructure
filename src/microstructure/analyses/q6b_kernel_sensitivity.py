"""Q6b: kernel-K sensitivity panel — does n̂ rise with K because of long memory or drift?

Method: mirrors Q6's business-time pipeline exactly (load_events -> ts as
int64 epoch-ms -> intraday_rate_profile (48 bins) -> rescale_to_business_time
-> K equal-width contiguous sub-windows), but instead of fitting ONE
exponential-kernel Hawkes MLE per window, this module fits the
sum-of-exponentials MLE (`fit_hawkes_multiexp`) at K in {1, 2, 3} for EVERY
sub-window and records how the fitted branching ratio n̂_K moves across K.

Why this matters (docs/research/02-hawkes-processes.md §4 pitfall 3): a
single exponential kernel is too short-memoried to represent a true
long-memory/power-law-like kernel, so a K=1 MLE systematically underestimates
n = sum(alpha_k). Increasing K lets the mixture spread mass across widely
separated timescales and recover more of the long-lag kernel weight, pulling
n̂ up toward the true value — Q6's headline 41/41-symbol MLE-vs-count-variance
disagreement is consistent with exactly this kind of kernel misspecification.
Re-fitting the SAME data at K=1,2,3 and reporting the K=1->K=2 jump (Δ21) is
therefore the diagnostic this module exists to compute.

THE CONFOUND (must be read before trusting a large Δ21 as "kernel
misspecification confirmed"): a rising n̂(K) together with a slow-decaying
component is ALSO exactly what residual baseline non-stationarity produces,
even with a perfectly well-specified single-exponential TRUE kernel. Case A
(this repo's own synthetic control, see test_q6b.py):  a true n=0.4
single-exponential process with a ±30% baseline-rate wobble that survives
imperfect deseasonalization fits at K=1 n̂≈0.46 and at K=2 n̂≈0.83 — a large,
spurious Δ21 with NO long-memory kernel anywhere in the generative model. The
mechanism is the same one `branching_count_variance`'s regime-switching trap
documents for the model-free estimator (Filimonov & Sornette 2015): a
non-stationary mu(t) masquerades as self-excitation, and a second exponential
component with a very slow beta is a flexible enough shape to partially
absorb a slow drift in the baseline rate, inflating K=2's alpha sum without
any genuine long-range kernel mass being present.

This module's response to the confound is NOT to claim it can tell the two
apart from a single K-sweep — it explicitly cannot, with the tools built so
far. Instead, per symbol, it reports 1/β_slow (the slower component's decay
timescale, at K=2, converted to business-time SECONDS) against two
independent physical scales: the deseasonalization bin width (86400/48
seconds ≈ 1800s — a slow component decaying on a timescale comparable to or
longer than a deseasonalization bin is exactly what a residual bin-scale
drift would produce) and the sub-window length itself (a slow component
whose timescale approaches the window length is barely distinguishable from
a linear trend within that window). Symbols where 1/β_slow exceeds
DRIFT_SUSPECT_MULTIPLIER (10x) the bin width are flagged "drift-suspect" in
the per-symbol output — a large Δ21 on a drift-suspect symbol should be read
as ambiguous between genuine long-memory and residual non-stationarity, not
as confirmed endogeneity. The decisive control that WOULD separate the two
explanations — refitting K=1 with a block-wise (time-varying) mu instead of
a single constant mu — is run per symbol on the FIRST window only (to bound
cost) via `baseline_drift_control` (see `--drift-blocks`, 0 disables). It is a
heuristic likelihood-ratio screen whose block baseline can absorb only drift
slower than the block width; see its docstring and the markdown section
"Is the K=2 rise drift or memory?".

Symbols are processed one at a time; any per-symbol exception is caught and
logged into `failures`, and never aborts the run for the remaining symbols.

Outputs: q6b_kernel_sensitivity.{json,md,parquet,png}.
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

from microstructure.data.catalog import parquet_path
from microstructure.estimators.hawkes import (
    DRIFT_K2_RISE_MIN,
    K2_GAIN_MIN_DLL,
    MAX_PIECEWISE_BLOCKS,
    baseline_drift_control,
    fit_hawkes_exp,
    fit_hawkes_multiexp,
    spurious_delta21_null,
)
from microstructure.signals.eventtime import intraday_rate_profile, rescale_to_business_time
from microstructure.signals.load import load_events

N_BINS = 48  # intraday_rate_profile bin count, matches Q6

# Runtime cap on events per single sum-of-exponentials Hawkes MLE fit. Fitting
# at K=1,2,3 is strictly more expensive per event than Q6's single K=1 fit
# (K recursions per Nelder-Mead evaluation, dimension 1+2K instead of 3), so
# the same 250k-event cap Q6 uses per window is kept here rather than raised;
# see q6_endogeneity.py's MAX_FIT_EVENTS docstring for the sampling-noise
# justification, which applies unchanged to the K=1 fit and is, if anything,
# more conservative for K=2/K=3 since more parameters share the same sample.
MAX_FIT_EVENTS = 250_000

# Deseasonalization bin width in business-time SECONDS: one day (86400s) of
# business time, split into the same N_BINS=48 bins intraday_rate_profile
# uses. A slow kernel component decaying on a timescale comparable to (or
# longer than) this width is exactly the shape a residual bin-scale
# seasonality artifact (imperfect deseasonalization) would produce, since the
# profile cannot resolve structure finer than one bin.
DESEASON_BIN_WIDTH_S = 86_400.0 / N_BINS

# A symbol's median 1/beta_slow (at K=2) exceeding this multiple of the
# deseasonalization bin width is flagged "drift-suspect": the slow component
# is decaying on a timescale far longer than anything the deseasonalization
# step could have resolved, so it is at least as consistent with residual
# baseline drift leaking through deseasonalization as with a genuine
# long-memory kernel component. This is a flag for caution, not a verdict —
# seeing the module docstring's confound discussion for why a single K-sweep
# cannot settle the question on its own.
DRIFT_SUSPECT_MULTIPLIER = 10.0

DEFAULT_KS: tuple[int, ...] = (1, 2, 3)

# Default number of equal-width business-time blocks for the drift-vs-memory
# control (`baseline_drift_control`). 12 is the estimator's own cap
# (MAX_PIECEWISE_BLOCKS); 0 disables the control.
DEFAULT_DRIFT_BLOCKS = 12

DRIFT_VERDICTS: tuple[str, ...] = ("drift", "long_memory_candidate", "inconclusive")

# Per-symbol record keys produced by the drift control (all None when the
# control is disabled or could not run).
_DRIFT_KEYS: tuple[str, ...] = (
    "drift_verdict", "drift_inconclusive_reason", "dll_pw", "dll_k2", "dll_threshold",
    "drift_n_k1", "drift_n_k2", "n_k1_piecewise", "drift_block_width_s", "drift_error",
)

# Why a symbol's verdict is 'inconclusive' (derived here from the control's
# outputs; `_drift_verdict` itself only returns the bare label).
INCONCLUSIVE_REASONS: tuple[str, ...] = ("no_rise", "k2_insignificant", "mixed")
_REASON_PHRASES = {
    "no_rise": "show no K=2 rise at all",
    "k2_insignificant": "have a K=2 gain that is not significant",
    "mixed": "have a significant K=2 gain that the block baseline recovers only partly",
}


def _inconclusive_reason(n_k1: float, n_k2: float, dll_k2: float) -> str:
    """Reason for an 'inconclusive' verdict, mirroring `_drift_verdict`'s
    check order: no material rise, then insignificant K=2 gain, else mixed."""
    if n_k2 - n_k1 <= DRIFT_K2_RISE_MIN:
        return "no_rise"
    if dll_k2 < K2_GAIN_MIN_DLL:
        return "k2_insignificant"
    return "mixed"


def _cap_events(times: np.ndarray, t_end: float) -> tuple[np.ndarray, float]:
    """Truncate to the first MAX_FIT_EVENTS events (and the matching t_end)."""
    if times.size > MAX_FIT_EVENTS:
        times = times[:MAX_FIT_EVENTS]
        t_end = float(times[-1])
    return times, t_end


def _fit_capped_multiexp(times: np.ndarray, t_end: float, k: int) -> dict:
    """Fit the K-component sum-of-exponentials Hawkes MLE, capping events.

    Returns a dict with n, alphas, betas, beta_slow, inv_beta_slow,
    converged. `beta_slow` is min(betas) (the slowest-decaying component);
    `inv_beta_slow` is its timescale 1/beta_slow in business-time seconds
    (matching the units `times`/`t_end` are already expressed in, since this
    module always calls this AFTER business-time rescaling).
    """
    times, t_end = _cap_events(times, t_end)
    fit = fit_hawkes_multiexp(times, t_end, K=k)
    beta_slow = float(np.min(fit.betas))
    return {
        # Raw fit plus the exact (capped) sample it was fit on, so the drift
        # control can reuse the K=2 fit. Never copied into the JSON record.
        "_fit": fit,
        "_times": times,
        "_t_end": t_end,
        "n": float(fit.n),
        "alphas": [float(a) for a in fit.alphas],
        "betas": [float(b) for b in fit.betas],
        "beta_slow": beta_slow,
        "inv_beta_slow": float(1.0 / beta_slow) if beta_slow > 0.0 else float("inf"),
        # `fit.converged` is annotated `bool` but the Nelder-Mead simplex
        # comparison it ultimately comes from operates on numpy arrays, so
        # it can arrive as `numpy.bool_` rather than a Python bool. `bool()`
        # coerces it to a JSON-serializable Python bool at the source, so no
        # numpy scalar carrying `converged` propagates further downstream.
        "converged": bool(fit.converged),
    }


def _window_edges(bt: np.ndarray, windows: int) -> np.ndarray:
    """K+1 equal-width business-time edges spanning [bt[0], bt[-1]]. Same
    convention as q6_endogeneity._window_edges."""
    return np.linspace(bt[0], bt[-1], windows + 1)


def _fit_window_all_ks(window_times: np.ndarray, t_end: float, ks: tuple[int, ...]) -> dict:
    """Fit every K in `ks` on one sub-window's (already zero-anchored) times.

    Returns {k: {n, alphas, betas, beta_slow, inv_beta_slow, converged}}.
    """
    return {k: _fit_capped_multiexp(window_times, t_end, k) for k in ks}


def _fit_business_time_windows(
    bt: np.ndarray, windows: int, ks: tuple[int, ...]
) -> list[dict]:
    """Fit every K in `ks` independently on each of `windows` contiguous
    business-time sub-windows.

    Returns a list of length `windows`, each element the per-K fit dict from
    `_fit_window_all_ks` plus the sub-window's own `window_length_s`. Windows
    with fewer than 2 events raise (same as Q6), turned into a per-symbol
    failure by the caller.
    """
    edges = _window_edges(bt, windows)
    results: list[dict] = []

    for i in range(windows):
        lo, hi = edges[i], edges[i + 1]
        mask = (bt >= lo) & (bt <= hi) if i == windows - 1 else (bt >= lo) & (bt < hi)
        window_times = bt[mask] - lo
        if window_times.size < 2:
            raise ValueError(f"sub-window {i} has only {window_times.size} events, need >= 2")
        t_end = float(window_times[-1])
        if t_end <= 0.0:
            raise ValueError(f"sub-window {i} has zero-length business-time span")
        per_k = _fit_window_all_ks(window_times, t_end, ks)
        results.append({"per_k": per_k, "window_length_s": float(hi - lo)})

    return results


def _is_drift_suspect(median_inv_beta_slow_k2: float) -> bool:
    """True if the K=2 slow-component timescale exceeds DRIFT_SUSPECT_MULTIPLIER
    times the deseasonalization bin width. See module docstring."""
    if not np.isfinite(median_inv_beta_slow_k2):
        return True
    # `median_inv_beta_slow_k2` is frequently a numpy float64 (it comes from
    # np.median), so the comparison below yields numpy.bool_, not a Python
    # bool, despite this function's `-> bool` annotation. Coerce at the
    # source so callers (and json.dumps downstream) always see a Python bool.
    return bool(median_inv_beta_slow_k2 > DRIFT_SUSPECT_MULTIPLIER * DESEASON_BIN_WIDTH_S)


def _drift_control_fields(first_window_k2: dict | None, drift_blocks: int) -> dict:
    """Run `baseline_drift_control` on ONE window (the first) and return
    Python-native record fields.

    `first_window_k2` is that window's `_fit_capped_multiexp(..., 2)` dict; its
    K=2 fit is reused and the K=1 fit is computed on the same capped sample.
    All fields are None when the control is disabled (`drift_blocks == 0`) or
    K=2 was not fit. A failure inside the control is recorded under
    `drift_error` rather than discarding the symbol's K-sweep result.
    """
    empty = {key: None for key in _DRIFT_KEYS}
    if drift_blocks == 0 or first_window_k2 is None:
        return empty
    times, t_end = first_window_k2["_times"], first_window_k2["_t_end"]
    try:
        fit_k1 = fit_hawkes_exp(times, t_end)
        res = baseline_drift_control(
            times, t_end, n_blocks=drift_blocks, fit_k1=fit_k1, fit_k2=first_window_k2["_fit"]
        )
    except Exception as e:  # noqa: BLE001 - keep the symbol's K-sweep result
        return {**empty, "drift_error": f"{type(e).__name__}: {e}"}
    verdict = str(res["verdict"])
    n_k1, n_k2, dll_k2 = float(res["n_k1"]), float(res["n_k2"]), float(res["dll_k2"])
    return {
        **empty,
        "drift_verdict": verdict,
        "drift_inconclusive_reason": (
            _inconclusive_reason(n_k1, n_k2, dll_k2) if verdict == "inconclusive" else None
        ),
        "dll_pw": float(res["dll_pw"]),
        "dll_k2": dll_k2,
        "dll_threshold": float(res["dll_threshold"]),
        "drift_n_k1": n_k1,
        "drift_n_k2": n_k2,
        "n_k1_piecewise": float(res["n_k1_piecewise"]),
        "drift_block_width_s": float(t_end / drift_blocks),
    }


def _symbol_record(
    root: Path, symbol: str, month: str, windows: int, ks: tuple[int, ...],
    drift_blocks: int = DEFAULT_DRIFT_BLOCKS,
) -> dict:
    events = load_events(root, symbol, [month])
    n_events = events.height
    if n_events == 0:
        raise ValueError(f"no events for {symbol} in {month}")

    ts_ms = events["ts"].dt.epoch("ms").to_numpy().astype(np.int64)
    ts_ms.sort()

    profile = intraday_rate_profile(ts_ms, N_BINS)
    bt = rescale_to_business_time(ts_ms, profile)

    min_events_needed = 2 * windows
    if bt.size < min_events_needed:
        raise ValueError(
            f"{symbol}: only {bt.size} events, need >= {min_events_needed} for {windows} "
            "sub-windows with >= 2 events each"
        )

    window_fits = _fit_business_time_windows(bt, windows, ks)
    window_length_s = float(np.median([w["window_length_s"] for w in window_fits]))
    n_events_per_window = int(bt.size // windows)

    n_hat_by_k: dict[int, list[float]] = {k: [] for k in ks}
    converged_by_k: dict[int, list[bool]] = {k: [] for k in ks}
    inv_beta_slow_by_k: dict[int, list[float]] = {k: [] for k in ks}

    for w in window_fits:
        for k in ks:
            fit = w["per_k"][k]
            n_hat_by_k[k].append(fit["n"])
            converged_by_k[k].append(fit["converged"])
            inv_beta_slow_by_k[k].append(fit["inv_beta_slow"])

    n_median_by_k = {k: float(np.median(n_hat_by_k[k])) for k in ks}
    n_converged_by_k = {k: int(sum(converged_by_k[k])) for k in ks}

    median_inv_beta_slow_k2 = (
        float(np.median(inv_beta_slow_by_k[2])) if 2 in inv_beta_slow_by_k else float("nan")
    )
    drift_suspect = _is_drift_suspect(median_inv_beta_slow_k2)

    delta21 = (
        n_median_by_k[2] - n_median_by_k[1]
        if 1 in n_median_by_k and 2 in n_median_by_k
        else float("nan")
    )

    ratio_bin_width = (
        median_inv_beta_slow_k2 / DESEASON_BIN_WIDTH_S if np.isfinite(median_inv_beta_slow_k2) else float("nan")
    )
    ratio_window_length = (
        median_inv_beta_slow_k2 / window_length_s
        if np.isfinite(median_inv_beta_slow_k2) and window_length_s > 0.0
        else float("nan")
    )

    drift_fields = _drift_control_fields(window_fits[0]["per_k"].get(2), drift_blocks)

    return {
        "symbol": symbol,
        "n_events": n_events,
        "n_events_per_window": n_events_per_window,
        "windows": windows,
        "ks": list(ks),
        "n_median_by_k": n_median_by_k,
        "n_converged_by_k": n_converged_by_k,
        "delta21": delta21,
        "median_inv_beta_slow_k2_s": median_inv_beta_slow_k2,
        "window_length_s": window_length_s,
        "bin_width_s": DESEASON_BIN_WIDTH_S,
        "ratio_inv_beta_slow_to_bin_width": ratio_bin_width,
        "ratio_inv_beta_slow_to_window_length": ratio_window_length,
        "drift_suspect": drift_suspect,
        **drift_fields,
        "per_window": [
            {
                "n_by_k": {k: w["per_k"][k]["n"] for k in ks},
                "converged_by_k": {k: w["per_k"][k]["converged"] for k in ks},
                "inv_beta_slow_by_k": {k: w["per_k"][k]["inv_beta_slow"] for k in ks},
            }
            for w in window_fits
        ],
    }


def _load_q6_gap(q6_json: Path | None) -> dict[str, float]:
    """Load {symbol: alpha_cv - alpha_median} from a Q6 results JSON, if given.

    Returns an empty dict if `q6_json` is None or the file doesn't exist —
    the cross-section correlation with Δ21 is then simply skipped, not an
    error (this diagnostic is optional supplementary context, not a
    dependency Q6b requires to run).
    """
    if q6_json is None or not q6_json.exists():
        return {}
    data = json.loads(q6_json.read_text())
    gaps: dict[str, float] = {}
    for rec in data.get("records", []):
        symbol = rec.get("symbol")
        alpha_cv = rec.get("alpha_cv")
        alpha_median = rec.get("alpha_median")
        if symbol is None or alpha_cv is None or alpha_median is None:
            continue
        gaps[symbol] = float(alpha_cv) - float(alpha_median)
    return gaps


def _null_floor_p90(records: list[dict], null_sims: int, seed: int = 20240601) -> dict | None:
    """Finite-sample Delta21 null floor, calibrated at the panel's own median
    per-window event count (see `spurious_delta21_null`'s docstring for why
    this must be calibrated at the run's actual event count, not a fixed
    size). Representative single-exp parameters for the null simulation are
    taken FROM the panel itself, not hardcoded: `alpha` is the panel's median
    K=1 branching ratio (n_hat_k1) -- the panel's own typical "how much
    branching does a K=1 fit see" answer -- and `beta=2.0`, the same
    single-exponential decay rate this repo's own planted single-exp
    fixtures use throughout (test_hawkes.py, test_q6.py, test_q6b.py's
    ONEEXPUSDT), as a reasonable representative timescale absent any
    panel-wide way to estimate a "typical" beta from K=1 fits alone (K=1
    beta is only loosely identified per `fit_hawkes_exp`'s own docstring).
    `mu` is not a free choice here: `spurious_delta21_null` derives its own
    `t_end` from `n_events_per_window` and the stationary mean-rate identity
    `mu/(1-alpha)`, so only `alpha` and `beta` need to be supplied.

    Returns None if `null_sims <= 0` (an explicit opt-out for callers that
    do not need this diagnostic and want to skip its runtime cost -- e.g.
    tests exercising unrelated parts of the pipeline) or if no successful
    records have both K=1 fits and a recorded per-window event count
    (nothing to calibrate against).
    """
    if null_sims <= 0:
        return None

    per_window_counts = [
        r["n_events_per_window"] for r in records if r.get("n_events_per_window", 0) > 0
    ]
    alphas_k1 = [r["n_median_by_k"][1] for r in records if 1 in r["n_median_by_k"]]
    if not per_window_counts or not alphas_k1:
        return None

    n_events_per_window = int(np.median(per_window_counts))
    alpha = float(np.median(alphas_k1))
    beta = 2.0

    # Guard the same alpha<1 stationarity constraint spurious_delta21_null's
    # underlying simulator enforces -- a panel-wide median alpha at or above
    # 1 would itself be a red flag (near-critical/explosive panel), and the
    # null is not meaningful there.
    if not (0.0 < alpha < 1.0) or n_events_per_window <= 0:
        return None

    null = spurious_delta21_null(
        n_events_per_window, mu=1.0, alpha=alpha, beta=beta, n_sims=null_sims, seed=seed
    )
    return {
        "n_events_per_window": n_events_per_window,
        "alpha_used": alpha,
        "beta_used": beta,
        "n_sims": null_sims,
        "p90": float(np.percentile(null, 90)),
        "median": float(np.median(null)),
        "values": [float(v) for v in null],
    }


def _drift_verdict_counts(records: list[dict]) -> dict[str, int]:
    """Count of each drift verdict, plus `errored` (control raised) and
    `not_run` (control disabled / K=2 not fit)."""
    counts = {v: 0 for v in DRIFT_VERDICTS}
    counts["not_run"] = 0
    counts["errored"] = 0
    for r in records:
        verdict = r.get("drift_verdict")
        if verdict in DRIFT_VERDICTS:
            counts[verdict] += 1
        elif r.get("drift_error"):
            counts["errored"] += 1
        else:
            counts["not_run"] += 1
    return counts


def _inconclusive_reason_counts(records: list[dict]) -> dict[str, int]:
    counts = {reason: 0 for reason in INCONCLUSIVE_REASONS}
    for r in records:
        reason = r.get("drift_inconclusive_reason")
        if reason in counts:
            counts[reason] += 1
    return counts


def _cross_section(
    records: list[dict], q6_gaps: dict[str, float], null_sims: int = 5
) -> dict:
    if not records:
        return {
            "delta21_distribution": None,
            "frac_n2_at_least_0_9": None,
            "cv_gap_correlation": None,
            "null_floor_p90": None,
            "drift_verdict_counts": _drift_verdict_counts([]),
            "drift_inconclusive_reason_counts": _inconclusive_reason_counts([]),
        }

    delta21s = np.array([r["delta21"] for r in records if np.isfinite(r["delta21"])])
    delta21_distribution = (
        {
            "median": float(np.median(delta21s)),
            "mean": float(np.mean(delta21s)),
            "std": float(np.std(delta21s, ddof=1)) if delta21s.size >= 2 else 0.0,
            "min": float(np.min(delta21s)),
            "max": float(np.max(delta21s)),
            "n": int(delta21s.size),
        }
        if delta21s.size > 0
        else None
    )

    n2_values = [r["n_median_by_k"].get(2) for r in records if 2 in r["n_median_by_k"]]
    frac_n2_at_least_0_9 = (
        float(sum(1 for v in n2_values if v >= 0.9) / len(n2_values)) if n2_values else None
    )

    cv_gap_correlation = None
    if q6_gaps:
        paired = [
            (r["delta21"], q6_gaps[r["symbol"]])
            for r in records
            if r["symbol"] in q6_gaps and np.isfinite(r["delta21"])
        ]
        if len(paired) >= 2:
            delta_arr = np.array([p[0] for p in paired])
            gap_arr = np.array([p[1] for p in paired])
            if np.std(delta_arr) > 0 and np.std(gap_arr) > 0:
                cv_gap_correlation = {
                    "correlation": float(np.corrcoef(delta_arr, gap_arr)[0, 1]),
                    "n": len(paired),
                }
            else:
                cv_gap_correlation = {"correlation": None, "n": len(paired)}

    null_floor_p90 = _null_floor_p90(records, null_sims)

    return {
        "delta21_distribution": delta21_distribution,
        "frac_n2_at_least_0_9": frac_n2_at_least_0_9,
        "cv_gap_correlation": cv_gap_correlation,
        "null_floor_p90": null_floor_p90,
        "drift_verdict_counts": _drift_verdict_counts(records),
        "drift_inconclusive_reason_counts": _inconclusive_reason_counts(records),
    }


def run_q6b(
    root: Path,
    out_dir: Path,
    symbols: list[str],
    month: str = "2023-06",
    windows: int = 6,
    ks: tuple[int, ...] = DEFAULT_KS,
    q6_json: Path | None = None,
    null_sims: int = 5,
    drift_blocks: int = DEFAULT_DRIFT_BLOCKS,
) -> dict:
    if drift_blocks != 0 and not 2 <= drift_blocks <= MAX_PIECEWISE_BLOCKS:
        raise ValueError(
            f"drift_blocks must be 0 (disabled) or in [2, {MAX_PIECEWISE_BLOCKS}]; got {drift_blocks}"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    failures: list[dict] = []

    for symbol in symbols:
        p = parquet_path(root, symbol, "aggTrades", month)
        if not p.exists():
            failures.append({"symbol": symbol, "reason": f"parquet not found: {p}"})
            continue
        try:
            records.append(_symbol_record(root, symbol, month, windows, ks, drift_blocks))
        except Exception as e:  # noqa: BLE001 - per-symbol robustness is the point
            failures.append({"symbol": symbol, "reason": f"{type(e).__name__}: {e}"})

    q6_gaps = _load_q6_gap(q6_json)
    cross_section = _cross_section(records, q6_gaps, null_sims)

    null_floor_p90 = cross_section.get("null_floor_p90")
    if null_floor_p90 is not None:
        p90 = null_floor_p90["p90"]
        for r in records:
            # "within finite-sample null": this symbol's Delta21 does not
            # exceed the panel's own null 90th percentile (see
            # `_null_floor_p90`'s docstring) -- i.e. it is no more than what
            # a well-specified K=1 process of the panel's typical per-window
            # size would produce anyway, and should not be read as evidence
            # of genuine long-memory kernel structure on its own.
            r["within_finite_sample_null"] = bool(
                np.isfinite(r["delta21"]) and r["delta21"] <= p90
            )
    else:
        for r in records:
            r["within_finite_sample_null"] = None

    result = {
        "month": month,
        "windows": windows,
        "ks": list(ks),
        "drift_blocks": drift_blocks,
        "n_symbols_requested": len(symbols),
        "n_symbols_successful": len(records),
        "n_symbols_failed": len(failures),
        "records": records,
        "failures": failures,
        "cross_section": cross_section,
        "q6_json_used": str(q6_json) if q6_json is not None else None,
    }

    _plot(out_dir, records, cross_section)
    _write_results_parquet(out_dir, records)
    _write_results_md(out_dir, result)
    (out_dir / "q6b_kernel_sensitivity.json").write_text(json.dumps(result, indent=2))
    return result


def _parquet_rows(records: list[dict]) -> list[dict]:
    rows = []
    for r in records:
        row = {
            "symbol": r["symbol"],
            "n_events": r["n_events"],
            "n_hat_k1": r["n_median_by_k"].get(1),
            "n_hat_k2": r["n_median_by_k"].get(2),
            "n_hat_k3": r["n_median_by_k"].get(3),
            "delta21": r["delta21"],
            "median_inv_beta_slow_k2_s": r["median_inv_beta_slow_k2_s"],
            "ratio_inv_beta_slow_to_bin_width": r["ratio_inv_beta_slow_to_bin_width"],
            "ratio_inv_beta_slow_to_window_length": r["ratio_inv_beta_slow_to_window_length"],
            "drift_suspect": r["drift_suspect"],
            **{key: r.get(key) for key in _DRIFT_KEYS},
        }
        rows.append(row)
    return rows


_PARQUET_SCHEMA = {
    "symbol": pl.Utf8, "n_events": pl.Int64, "n_hat_k1": pl.Float64,
    "n_hat_k2": pl.Float64, "n_hat_k3": pl.Float64, "delta21": pl.Float64,
    "median_inv_beta_slow_k2_s": pl.Float64, "ratio_inv_beta_slow_to_bin_width": pl.Float64,
    "ratio_inv_beta_slow_to_window_length": pl.Float64, "drift_suspect": pl.Boolean,
    "drift_verdict": pl.Utf8, "drift_inconclusive_reason": pl.Utf8,
    "dll_pw": pl.Float64, "dll_k2": pl.Float64, "dll_threshold": pl.Float64,
    "drift_n_k1": pl.Float64, "drift_n_k2": pl.Float64, "n_k1_piecewise": pl.Float64,
    "drift_block_width_s": pl.Float64, "drift_error": pl.Utf8,
}


def _write_results_parquet(out_dir: Path, records: list[dict]) -> None:
    if records:
        df = pl.DataFrame(_parquet_rows(records), schema=_PARQUET_SCHEMA)
    else:
        df = pl.DataFrame(schema=_PARQUET_SCHEMA)
    df.write_parquet(out_dir / "q6b_kernel_sensitivity.parquet")


def _plot(out_dir: Path, records: list[dict], cross_section: dict) -> None:
    fig, (ax_delta, ax_slow) = plt.subplots(1, 2, figsize=(13, 5))

    if records:
        delta21s = np.array([r["delta21"] for r in records if np.isfinite(r["delta21"])])
        if delta21s.size > 0:
            ax_delta.hist(delta21s, bins=min(20, max(5, delta21s.size // 2)), color="steelblue", alpha=0.85)
            ax_delta.axvline(0.15, color="red", linestyle="--", linewidth=1.0, label="Δ21 = 0.15")
            ax_delta.legend()
        ax_delta.set_xlabel(r"$\Delta_{21} = \hat n_2 - \hat n_1$ (median across sub-windows)")
        ax_delta.set_ylabel("symbol count")
        ax_delta.set_title("Distribution of K=1→K=2 branching-ratio jump")

        drift_suspect = np.array([r["drift_suspect"] for r in records])
        ratios = np.array([r["ratio_inv_beta_slow_to_bin_width"] for r in records])
        deltas = np.array([r["delta21"] for r in records])
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


def _fmt_ratio(ratio: float) -> str:
    if not np.isfinite(ratio):
        return "n/a"
    return f"{ratio:.2f}x"


def _drift_headline(
    counts: dict[str, int],
    reason_counts: dict[str, int],
    width_hours: float | None,
    n_requested: int,
) -> str:
    """One-sentence headline from verdict counts (majority of ASSESSED symbols).

    The denominator is stated: assessed symbols are those with a verdict;
    failed, errored and not-run symbols are excluded.
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
            "Most symbols show no material K=1→K=2 rise in this window — there is no "
            "apparent near-criticality for the control to explain"
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
    return f"**{sentence} {denominator}.**"


def _drift_section_lines(result: dict) -> list[str]:
    """Markdown for 'Is the K=2 rise drift or memory?', templated from data."""
    lines = ["## Is the K=2 rise drift or memory?", ""]
    drift_blocks = result.get("drift_blocks", 0)
    if not drift_blocks:
        lines.append(
            "The block-wise-baseline control was disabled for this run (`--drift-blocks 0`); "
            "the K=1→K=2 rise is therefore not separated into drift and memory here."
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

    lines.append(_drift_headline(counts, reasons, width_hours, result["n_symbols_requested"]))
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
        f"Per symbol, on the FIRST business-time window only (to bound cost; that window is "
        f"capped at {MAX_FIT_EVENTS:,} events), K=1 with one constant baseline is compared "
        f"with K=1 using a piecewise-constant baseline over {drift_blocks} equal blocks, and "
        f"with the window's K=2 fit. Median block width: {width_txt}. `dll_pw` and `dll_k2` "
        "are the log-likelihood gains over constant-baseline K=1 from the block baseline and "
        "from the second kernel component; `threshold` is chi-square(0.95, blocks−1)/2."
    )
    lines.append("")
    lines.append("**Method caveats.**")
    lines.append(
        "- This is a heuristic likelihood-ratio screen, not a formal test: the fits are "
        "Nelder-Mead optima, the chi-square calibration is only approximate for Hawkes "
        "likelihoods, and the half-of-`dll_k2` cut-off is a convention."
    )
    lines.append(
        f"- Resolution limit: a block baseline absorbs only drift slower than the block "
        f"width (median {width_txt}). Faster baseline wobble averages out inside a block and "
        "is indistinguishable from long memory, so `long_memory_candidate` carries meaning "
        "only for drift slower than that width."
    )
    lines.append(
        "- Misspecification: when K=1 is wrong (genuine long memory) block counts are more "
        "dispersed than K=1 predicts, inflating `dll_pw`. That can push a symbol with real "
        "long memory to `inconclusive` OR across the drift threshold into `drift`. A `drift` "
        "label means only that the block baseline recovers at least half of the K=2 gain; it "
        "does not exclude long memory."
    )
    lines.append(
        f"- `inconclusive` is split by reason: `no_rise` (K=2 n̂ − K=1 n̂ ≤ "
        f"{DRIFT_K2_RISE_MIN:g}, so there is nothing to explain), `k2_insignificant` (the "
        f"K=2 gain `dll_k2` is below {K2_GAIN_MIN_DLL:.2f} nats = chi-square(0.95, 2)/2), "
        "`mixed` (a material, significant K=2 gain that the block baseline recovers "
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
                f"{r['drift_inconclusive_reason'] or '—'} | {r['drift_n_k1']:.4f} | "
                f"{r['drift_n_k2']:.4f} | {r['n_k1_piecewise']:.4f} | {r['dll_pw']:.2f} | "
                f"{r['dll_k2']:.2f} | {r['dll_threshold']:.2f} | "
                f"{r['drift_block_width_s'] / 3600.0:.2f} |"
            )
        lines.append("")
    errors = [r for r in records if r.get("drift_error")]
    for r in errors:
        lines.append(f"- {r['symbol']}: drift control errored ({r['drift_error']}).")
    if errors:
        lines.append("")
    return lines


def _write_results_md(out_dir: Path, result: dict) -> None:
    records = result["records"]
    month = result["month"]
    windows = result["windows"]
    ks = result["ks"]
    cross_section = result["cross_section"]

    lines: list[str] = []
    lines.append("# Q6b: kernel-K sensitivity panel — does n̂ rise with K, and why?")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        f"For each symbol, one month ({month}) of aggTrades is loaded (`load_events`), "
        "rescaled to business time (`intraday_rate_profile` + `rescale_to_business_time`, "
        f"{N_BINS} bins) exactly as in Q6, then split into {windows} equal contiguous "
        f"sub-windows. Each sub-window is refit at every K in {ks} via "
        "`fit_hawkes_multiexp` (sum-of-K-exponentials Hawkes MLE), instead of Q6's single "
        "K=1 fit. Per symbol, per sub-window, this records n̂_K = sum(alpha_k) and "
        "β_slow_K = min(betas_K) (the slowest-decaying component's rate) for every K."
    )
    lines.append("")
    lines.append(
        f"**Runtime cap**: a sub-window with more than {MAX_FIT_EVENTS:,} events is fit "
        f"on only the first {MAX_FIT_EVENTS:,} of that window's events (same cap and "
        "justification as Q6's MAX_FIT_EVENTS, applied per-K here)."
    )
    lines.append("")
    lines.append(
        "**Per-symbol summary**: the median across sub-windows of n̂_1, n̂_2, n̂_3, and "
        "Δ21 = median(n̂_2) − median(n̂_1) — the headline K=1→K=2 branching-ratio jump. "
        "Also reported: the median across sub-windows of 1/β_slow at K=2 (the slower "
        f"component's timescale, in business-time seconds), compared against the "
        f"deseasonalization bin width ({DESEASON_BIN_WIDTH_S:.1f}s = 86400/{N_BINS}) and "
        "against the sub-window length itself, as two independent ratios."
    )
    lines.append("")
    lines.append(
        "## The confound this analysis does NOT resolve on its own"
    )
    lines.append("")
    lines.append(
        "**A K=1→K=2 rise in n̂ together with a slow kernel component is also produced by "
        "residual baseline non-stationarity, not only by a genuine long-memory kernel.** "
        "This repo's own synthetic control (test_q6b.py, \"Case A\") demonstrates the "
        "trap directly: a TRUE n=0.4 single-exponential process with a ±30% baseline-rate "
        "wobble that survives imperfect deseasonalization fits at K=1 n̂≈0.46 and at K=2 "
        "n̂≈0.83 — a large, spurious Δ21 with no long-memory kernel anywhere in the "
        "generative model. A second exponential component with a very slow beta is "
        "flexible enough to partially absorb a slow drift in the baseline rate, inflating "
        "the K=2 branching-ratio sum without any genuine long-range kernel mass being "
        "present. This is the same mechanism Filimonov & Sornette (2015) document for the "
        "model-free count-variance estimator's regime-switching trap, now shown to affect "
        "the sum-of-exponentials MLE as well."
    )
    lines.append("")
    lines.append(
        "**Why this analysis reports 1/β_slow vs. bin width instead of trusting Δ21 "
        "alone.** A slow component decaying on a timescale comparable to or longer than "
        "the deseasonalization bin width is exactly the shape a residual bin-scale "
        "seasonality artifact would produce — the 48-bin intraday profile cannot resolve "
        "structure finer than one bin, so any leftover non-stationarity at or above that "
        "scale is a plausible source for a slow K=2 component, not necessarily a genuine "
        f"long-memory kernel. Symbols where the median 1/β_slow (K=2) exceeds "
        f"{DRIFT_SUSPECT_MULTIPLIER:.0f}x the bin width are flagged **drift-suspect** in "
        "the panel table below — a large Δ21 on a drift-suspect symbol should be read as "
        "ambiguous between genuine long-memory and residual non-stationarity, not as "
        "confirmed endogeneity."
    )
    lines.append("")
    if result.get("drift_blocks"):
        lines.append(
            "**The decisive control is run on one window per symbol** (see "
            "\"Is the K=2 rise drift or memory?\" below): K=1 is refit with a block-wise "
            "(piecewise-constant) mu and compared with the K=2 gain. It is a heuristic "
            "screen with a stated resolution limit, so the Δ21 and drift-suspect flag above "
            "remain triage quantities."
        )
    else:
        lines.append(
            "**The decisive control was not run** (`--drift-blocks 0`): refitting K=1 with "
            "a block-wise (time-varying, piecewise-constant) mu would separate these two "
            "explanations. Until it is run, this panel's Δ21 and drift-suspect flag should "
            "be read as a triage tool, not a final verdict on kernel misspecification vs. "
            "residual drift."
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
            n1s = f"{n1:.4f}" if n1 is not None else "n/a"
            n2s = f"{n2:.4f}" if n2 is not None else "n/a"
            n3s = f"{n3:.4f}" if n3 is not None else "n/a"
            within_null = r.get("within_finite_sample_null")
            within_null_s = "yes" if within_null else ("NO" if within_null is False else "n/a")
            lines.append(
                f"| {r['symbol']} | {r['n_events']:,} | {n1s} | {n2s} | {n3s} | "
                f"{r['delta21']:+.4f} | {r['median_inv_beta_slow_k2_s']:.2f} | "
                f"{_fmt_ratio(r['ratio_inv_beta_slow_to_bin_width'])} | "
                f"{_fmt_ratio(r['ratio_inv_beta_slow_to_window_length'])} | "
                f"{'YES' if r['drift_suspect'] else 'no'} | {within_null_s} | "
                f"{r.get('drift_verdict') or 'n/a'} |"
            )
        lines.append("")
    else:
        lines.append("No symbols produced usable results — no table to show.")
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
        lines.append(
            f"**Δ21 is reported alongside a null floor computed at the panel's per-window "
            f"event count** ({null_floor['n_events_per_window']:,} events, from "
            f"{null_floor['n_sims']} simulated well-specified K=1 processes with "
            f"alpha={null_floor['alpha_used']:.4f} (this panel's own median n̂_1), "
            f"beta={null_floor['beta_used']:.1f} — see `spurious_delta21_null`). The null's "
            f"90th percentile is **{null_floor['p90']:.4f}** (median {null_floor['median']:.4f}). "
            f"Symbols whose Δ21 does not exceed this null's 90th percentile are labeled "
            f"**\"within finite-sample null\"** in the panel table above ({n_within}/"
            f"{len(records)} symbols here) — their Δ21 is no larger than what a well-"
            "specified, non-long-memory K=1 process of this panel's typical per-window size "
            "would produce from sampling noise alone, so it should not be read as evidence "
            "of genuine long-memory kernel structure on its own."
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
    cv_corr = cross_section["cv_gap_correlation"]
    if cv_corr is not None and cv_corr.get("correlation") is not None:
        lines.append(
            f"**Correlation of Δ21 with the Q6 count-variance gap** (alpha_cv − "
            f"alpha_median, from `--q6-json`): **{cv_corr['correlation']:.4f}** "
            f"(n={cv_corr['n']}). A positive correlation is consistent with Q6's "
            "MLE-vs-count-variance disagreement being driven, at least partly, by the "
            "same K=1 exponential-kernel underestimation this module's Δ21 is designed "
            "to detect — but per the confound discussion above, is equally consistent "
            "with both estimators sharing exposure to the same residual baseline "
            "non-stationarity, and cannot on its own distinguish the two."
        )
    elif result.get("q6_json_used"):
        lines.append(
            "Correlation of Δ21 with the Q6 count-variance gap was requested "
            f"(`--q6-json {result['q6_json_used']}`) but not estimable (fewer than 2 "
            "overlapping symbols, or zero variance in one of the two series)."
        )
    else:
        lines.append(
            "No `--q6-json` supplied — correlation of Δ21 with the Q6 count-variance gap "
            "was skipped."
        )
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
            f"{DESEASON_BIN_WIDTH_S:.1f}s) — for these symbols, the Δ21 reported above "
            "should be treated as ambiguous between genuine long-memory kernel structure "
            "and residual baseline drift leaking through deseasonalization, per the "
            "confound discussion above."
        )
    else:
        lines.append("No successful symbols in this run — no finding to report.")
    lines.append("")

    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "- **The confound is only partly resolved.** A large Δ21 is consistent with BOTH "
        "genuine long-memory kernel structure and residual baseline non-stationarity "
        "surviving deseasonalization. The block-wise-baseline control (first window per "
        "symbol, heuristic, limited to drift slower than its block width) is reported in "
        "\"Is the K=2 rise drift or memory?\"; it is absent when `--drift-blocks 0`."
    )
    lines.append(
        f"- **Single month** ({month}): one specific market regime; results may not "
        "generalize to other months."
    )
    lines.append(
        "- **Higher-K identifiability**: per `fit_hawkes_multiexp`'s own docstring, "
        "individual alpha_k/beta_k components become less identified as K grows relative "
        "to what the sample size and window can resolve — n̂_K (the sum) is more "
        "trustworthy than any individual component, but β_slow (the min beta) can still "
        "be noisy at K=3 in particular."
    )
    lines.append(
        f"- **Runtime cap** ({MAX_FIT_EVENTS:,} events/window): windows above this cap "
        "are fit on a truncated prefix, applied independently at each K."
    )
    lines.append(
        "- **48-bin intraday profile**: same caveat as Q6 — the profile is estimated "
        "from the same month being fit, and any genuine excitation clustering at "
        "~30-minute resolution could leak into deseasonalization."
    )
    lines.append("")
    (out_dir / "q6b_kernel_sensitivity.md").write_text("\n".join(lines))


def _parse_ks(raw: str) -> tuple[int, ...]:
    return tuple(int(x.strip()) for x in raw.split(",") if x.strip())


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Q6b: kernel-K sensitivity panel")
    parser.add_argument("--root", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--symbols-file", type=Path, required=True, help="one symbol per line")
    parser.add_argument("--month", type=str, default="2023-06")
    parser.add_argument("--windows", type=int, default=6)
    parser.add_argument("--ks", type=str, default="1,2,3", help="comma-separated K values")
    parser.add_argument(
        "--q6-json", type=Path, default=None,
        help="path to a Q6 results JSON, for the Δ21-vs-count-variance-gap correlation",
    )
    parser.add_argument(
        "--null-sims", type=int, default=5,
        help=(
            "number of simulations for the finite-sample Delta21 null floor "
            "(spurious_delta21_null), calibrated at the panel's median per-window "
            "event count; default 5, tests use fewer to stay inside their runtime budget"
        ),
    )
    parser.add_argument(
        "--drift-blocks", type=int, default=DEFAULT_DRIFT_BLOCKS,
        help=(
            "number of equal business-time blocks for the piecewise-baseline drift "
            f"control on each symbol's first window (2..{MAX_PIECEWISE_BLOCKS}); "
            "0 disables the control"
        ),
    )
    return parser.parse_args(argv)


def _read_symbols_file(path: Path) -> list[str]:
    lines = path.read_text().splitlines()
    return [s.strip() for s in lines if s.strip()]


if __name__ == "__main__":
    args = _parse_args()
    symbols = _read_symbols_file(args.symbols_file)
    run_q6b(
        args.root, args.out, symbols=symbols, month=args.month,
        windows=args.windows, ks=_parse_ks(args.ks), q6_json=args.q6_json,
        null_sims=args.null_sims, drift_blocks=args.drift_blocks,
    )
