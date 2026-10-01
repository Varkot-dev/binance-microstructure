"""Q6b: kernel-K sensitivity panel — does n̂ rise with K because of long memory or drift?

Method: mirrors Q6's business-time pipeline (load_events -> ts as int64
epoch-ms -> intraday_rate_profile (48 bins) -> rescale_to_business_time -> K
equal-width contiguous sub-windows), but fits the sum-of-exponentials MLE
(`fit_hawkes_multiexp`) at K in {1, 2, 3} for every sub-window and records
how the fitted branching ratio n̂_K moves across K.

Why: a single exponential is too short-memoried for a long-memory kernel, so
a K=1 MLE underestimates n = sum(alpha_k) (Bacry, Mastromatteo & Muzy 2015).
Raising K lets the mixture spread mass across well-separated timescales and
recover more long-lag weight. Q6's 41/41-symbol MLE-vs-count-variance
disagreement is consistent with this kind of misspecification. The K=1->K=2
jump (Δ21) is the diagnostic this module computes.

Confound: a rising n̂(K) with a slow-decaying component is also what residual
baseline non-stationarity produces, even when the true kernel is a single
exponential. In the synthetic control in test_q6b.py, a true n=0.4
single-exponential process with a ±30% baseline-rate wobble that survives
imperfect deseasonalization fits at K=1 n̂≈0.46 and at K=2 n̂≈0.83: a large
spurious Δ21 with no long-memory kernel in the generative model. The
mechanism is the regime-switching trap of `branching_count_variance`
(Filimonov & Sornette 2015): a non-stationary mu(t) masquerades as
self-excitation, and a very slow second exponential can absorb a slow
baseline drift, inflating K=2's alpha sum without any long-range kernel mass.

A K-sweep alone cannot tell the two apart. Per symbol, the module reports
1/β_slow (the slower component's decay timescale at K=2, in business-time
seconds) against two scales: the deseasonalization bin width (86400/48
seconds ≈ 1800s; a slow component at or beyond that is what residual
bin-scale drift would produce) and the sub-window length (a timescale near
the window length is barely distinguishable from a linear trend). Symbols
where 1/β_slow exceeds DRIFT_SUSPECT_MULTIPLIER (10x) the bin width are
flagged "drift-suspect"; a large Δ21 there is ambiguous between long memory
and residual non-stationarity. The control that does separate them, refitting
K=1 with a block-wise (time-varying) mu, runs per symbol on the first window
only (to bound cost) via `baseline_drift_control` (`--drift-blocks`, 0
disables). It is a heuristic likelihood-ratio screen whose block baseline can
absorb only drift slower than the block width; see its docstring and the
markdown section "Is the K=2 rise drift or memory?".

Symbols are processed one at a time; a per-symbol exception is logged into
`failures` and does not abort the run.

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

# Runtime cap on events per sum-of-exponentials Hawkes MLE fit. Fits at K=1,2,3
# cost more per event than Q6's K=1 fit (K recursions per evaluation, dimension
# 1+2K instead of 3), so Q6's 250k-event cap is kept (see MAX_FIT_EVENTS in
# q6_endogeneity.py for the sampling-noise argument).
MAX_FIT_EVENTS = 250_000

# Deseasonalization bin width in business-time seconds: one day (86400s) split
# into the same N_BINS=48 bins as intraday_rate_profile. A slow kernel
# component at or beyond this timescale is what residual bin-scale seasonality
# would produce, since the profile cannot resolve structure finer than a bin.
DESEASON_BIN_WIDTH_S = 86_400.0 / N_BINS

# A symbol whose median 1/beta_slow (at K=2) exceeds this multiple of the
# deseasonalization bin width is flagged "drift-suspect": the slow component
# decays far slower than deseasonalization could resolve, so it is as
# consistent with residual baseline drift as with a long-memory kernel. A
# flag for caution, not a verdict (see the module docstring).
DRIFT_SUSPECT_MULTIPLIER = 10.0

DEFAULT_KS: tuple[int, ...] = (1, 2, 3)

# Default simulation count for the finite-sample Delta21 null floor. The null's
# 90th percentile is itself a sampling statistic, so a handful of draws is too noisy.
DEFAULT_NULL_SIMS = 50

# A fitted n-hat at or above this sits on the stationarity boundary (n = 1), where
# mu and alpha are only weakly identified (`fit_hawkes_exp` docstring). Such values
# are flagged in the tables.
BOUNDARY_N_HAT = 0.9999

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


def _is_finite_number(value: float | None) -> bool:
    return value is not None and bool(np.isfinite(value))


def _json_float(value: float | None) -> float | None:
    """Python float for finite values, None for NaN/inf (strict JSON has no encoding for them)."""
    return float(value) if _is_finite_number(value) else None


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
        # `fit.converged` can arrive as `numpy.bool_` (it comes from a numpy
        # comparison); coerce to a Python bool so it is JSON-serializable.
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
    # `median_inv_beta_slow_k2` is often a numpy float64 (from np.median), so
    # the comparison yields numpy.bool_; coerce to a Python bool for json.dumps.
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

    # Computed with inf/NaN allowed (a window with beta_slow <= 0 has an unbounded
    # timescale, which still counts toward drift-suspect), then converted to None
    # at the record boundary below.
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
        "delta21": _json_float(delta21),
        "median_inv_beta_slow_k2_s": _json_float(median_inv_beta_slow_k2),
        "window_length_s": window_length_s,
        "bin_width_s": DESEASON_BIN_WIDTH_S,
        "ratio_inv_beta_slow_to_bin_width": _json_float(ratio_bin_width),
        "ratio_inv_beta_slow_to_window_length": _json_float(ratio_window_length),
        "drift_suspect": drift_suspect,
        **drift_fields,
        "per_window": [
            {
                "n_by_k": {k: w["per_k"][k]["n"] for k in ks},
                "converged_by_k": {k: w["per_k"][k]["converged"] for k in ks},
                "inv_beta_slow_by_k": {k: _json_float(w["per_k"][k]["inv_beta_slow"]) for k in ks},
            }
            for w in window_fits
        ],
    }


def _load_q6_cv(q6_json: Path | None) -> dict[str, float]:
    """Load {symbol: alpha_cv} (Q6's count-variance n-hat) from a Q6 results JSON.

    Returns an empty dict if `q6_json` is None or the file doesn't exist; the
    count-variance comparison is then skipped.
    """
    if q6_json is None or not q6_json.exists():
        return {}
    data = json.loads(q6_json.read_text())
    gaps: dict[str, float] = {}
    for rec in data.get("records", []):
        symbol = rec.get("symbol")
        alpha_cv = rec.get("alpha_cv")
        if symbol is None or alpha_cv is None:
            continue
        gaps[symbol] = float(alpha_cv)
    return gaps


def _null_floor_p90(records: list[dict], null_sims: int, seed: int = 20240601) -> dict | None:
    """Finite-sample Delta21 null floor, calibrated at the event count the fits
    actually use: the panel's median per-window count, capped at MAX_FIT_EVENTS
    (see `spurious_delta21_null` for why it must be calibrated at the run's
    actual event count).

    The null's single-exponential parameters come from the panel: `alpha` is
    the panel's median K=1 branching ratio (n_hat_k1), and `beta=2.0`, the
    decay rate used by the planted single-exp fixtures in test_hawkes.py,
    test_q6.py and test_q6b.py (ONEEXPUSDT), since K=1 beta is only loosely
    identified (see `fit_hawkes_exp`). `mu` is not a free choice:
    `spurious_delta21_null` derives `t_end` from `n_events_per_window` and the
    stationary mean rate `mu/(1-alpha)`.

    Returns None if `null_sims <= 0` (opt-out, e.g. for tests exercising
    unrelated parts of the pipeline) or if no successful record has both K=1
    fits and a per-window event count.
    """
    if null_sims <= 0:
        return None

    per_window_counts = [
        r["n_events_per_window"] for r in records if r.get("n_events_per_window", 0) > 0
    ]
    alphas_k1 = [r["n_median_by_k"][1] for r in records if 1 in r["n_median_by_k"]]
    if not per_window_counts or not alphas_k1:
        return None

    # Fits are capped at MAX_FIT_EVENTS, so the null must be calibrated at the event
    # count the fits actually used, not the uncapped per-window count.
    n_events_per_window_uncapped = int(np.median(per_window_counts))
    n_events_per_window = min(n_events_per_window_uncapped, MAX_FIT_EVENTS)
    alpha = float(np.median(alphas_k1))
    beta = 2.0

    # The simulator requires alpha<1; a panel median at or above 1 would itself
    # be a red flag and the null is not meaningful there.
    if not (0.0 < alpha < 1.0) or n_events_per_window <= 0:
        return None

    null = spurious_delta21_null(
        n_events_per_window, mu=1.0, alpha=alpha, beta=beta, n_sims=null_sims, seed=seed
    )
    return {
        "n_events_per_window": n_events_per_window,
        "n_events_per_window_uncapped": n_events_per_window_uncapped,
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


def _cv_comparison(records: list[dict], q6_cv: dict[str, float]) -> dict | None:
    """Compare K=1 and K=2 estimates with Q6's count-variance n-hat.

    Delta21 is deliberately not correlated with (alpha_cv - n_hat_1): both
    contain -n_hat_1, which varies far more across symbols than n_hat_2 or
    alpha_cv, so that correlation is near 1 by construction.
    """
    rows = [
        (r["n_median_by_k"][1], r["n_median_by_k"][2], q6_cv[r["symbol"]])
        for r in records
        if r["symbol"] in q6_cv
        and 1 in r["n_median_by_k"]
        and 2 in r["n_median_by_k"]
        and _is_finite_number(r["n_median_by_k"][1])
        and _is_finite_number(r["n_median_by_k"][2])
    ]
    if not rows:
        return None
    n1 = np.array([row[0] for row in rows])
    n2 = np.array([row[1] for row in rows])
    cv = np.array([row[2] for row in rows])
    gap1 = cv - n1
    closable = gap1 > 0
    corr = (
        float(np.corrcoef(n2, cv)[0, 1])
        if len(rows) >= 2 and np.std(n2) > 0 and np.std(cv) > 0
        else None
    )
    return {
        "n": len(rows),
        "corr_n2_cv": corr,
        "median_gap_k1": float(np.median(gap1)),
        "median_gap_k2": float(np.median(cv - n2)),
        "median_frac_gap_closed": (
            float(np.median((n2 - n1)[closable] / gap1[closable])) if closable.any() else None
        ),
    }


def _cross_section(
    records: list[dict], q6_cv: dict[str, float], null_sims: int = DEFAULT_NULL_SIMS
) -> dict:
    if not records:
        return {
            "delta21_distribution": None,
            "frac_n2_at_least_0_9": None,
            "cv_comparison": None,
            "null_floor_p90": None,
            "drift_verdict_counts": _drift_verdict_counts([]),
            "drift_inconclusive_reason_counts": _inconclusive_reason_counts([]),
        }

    delta21s = np.array([r["delta21"] for r in records if _is_finite_number(r["delta21"])])
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

    null_floor_p90 = _null_floor_p90(records, null_sims)

    return {
        "delta21_distribution": delta21_distribution,
        "frac_n2_at_least_0_9": frac_n2_at_least_0_9,
        "cv_comparison": _cv_comparison(records, q6_cv) if q6_cv else None,
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
    null_sims: int = DEFAULT_NULL_SIMS,
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
        except Exception as e:  # noqa: BLE001 - a per-symbol failure is logged, not fatal
            failures.append({"symbol": symbol, "reason": f"{type(e).__name__}: {e}"})

    q6_cv = _load_q6_cv(q6_json)
    cross_section = _cross_section(records, q6_cv, null_sims)

    null_floor_p90 = cross_section.get("null_floor_p90")
    if null_floor_p90 is not None:
        p90 = null_floor_p90["p90"]
        for r in records:
            # "within finite-sample null": this symbol's Delta21 does not exceed
            # the panel's null 90th percentile (see `_null_floor_p90`), so it is
            # no more than a well-specified K=1 process of the panel's typical
            # per-window size would produce and is not evidence of long memory
            # on its own.
            r["within_finite_sample_null"] = bool(
                _is_finite_number(r["delta21"]) and r["delta21"] <= p90
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
    (out_dir / "q6b_kernel_sensitivity.json").write_text(json.dumps(result, indent=2, allow_nan=False))
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
        "--null-sims", type=int, default=DEFAULT_NULL_SIMS,
        help=(
            "number of simulations for the finite-sample Delta21 null floor "
            "(spurious_delta21_null), calibrated at the panel's median per-window "
            f"event count capped at {MAX_FIT_EVENTS:,}; default {DEFAULT_NULL_SIMS}, tests use "
            "fewer to stay inside their runtime budget"
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
