"""Business-time rescaling: seasonality-robust event-time deseasonalization.

Motivation (Filimonov & Sornette 2015; the regime-switching trap test in
tests/estimators/test_hawkes.py,
`test_regime_switching_poisson_produces_spurious_endogeneity_trap`): fitting
a Hawkes model directly on clock-time event data cannot separate
self-excitation from a time-varying, non-self-exciting baseline rate mu(t),
such as the intraday U-shape or funding-hour clustering common in
crypto/equity data. Both a likelihood fit and the count-variance estimator
report spurious positive endogeneity on a non-stationary-rate Poisson
process.

The fix is a deterministic time change to "business time" (operational time)
that flattens the known intraday seasonality before any Hawkes fit. Given a
piecewise-constant intraday rate profile rate(s) (period 24h, repeating
across days, mean 1), business time is

    tau(t) = integral_0^t rate(s) ds

Under tau, a Poisson process with rate mu(t) = mu_bar * rate(time_of_day(t))
becomes homogeneous with rate mu_bar (random time-change theorem for point
processes), so a Hawkes fit on tau(events) is not confounded by the daily
cycle.

Usage: estimate the profile from a longer or representative sample with
`intraday_rate_profile`, then rescale the event times with
`rescale_to_business_time` before calling `fit_hawkes_exp` /
`branching_count_variance` from microstructure.estimators.hawkes.
"""
from __future__ import annotations

import numpy as np

MS_PER_DAY = 86_400_000
_EMPTY_BIN_FLOOR = 0.01


def intraday_rate_profile(ts: np.ndarray, n_bins: int = 48) -> np.ndarray:
    """Estimate the normalized intraday event-rate profile from event times.

    `ts` is a 1-D array of int64 epoch-milliseconds (UTC). If timestamps
    originate from a polars `Datetime` series, the caller is responsible for
    converting first, e.g. `df["ts"].dt.epoch("ms").to_numpy()`.

    Each event is assigned to one of `n_bins` equal-width bins covering the
    24h UTC time-of-day cycle (bin width = 86_400_000 / n_bins ms), by
    `(ts % MS_PER_DAY) // bin_width_ms`. The profile is the per-bin event
    count divided by the mean per-bin count (total_events / n_bins), so it has
    mean 1: a value of 2.0 means events are twice as frequent in that bin as
    the all-day average.

    Empty bins are floored at `_EMPTY_BIN_FLOOR` (0.01) so the business clock
    in `rescale_to_business_time` never freezes. This assumes an empty bin is
    sampling noise rather than a dead trading period, and can distort empty
    hours when the profile is estimated from very short or intermittent
    samples. The floor is applied before normalizing by the floored array's
    own mean, so the profile mean is exactly 1 and one full day integrates to
    exactly 86400 seconds in `rescale_to_business_time`.

    Raises ValueError if `ts` is empty or `n_bins` is not a positive
    integer.
    """
    if n_bins <= 0:
        raise ValueError("n_bins must be positive")
    ts = np.asarray(ts, dtype=np.int64)
    if ts.size == 0:
        raise ValueError("ts must not be empty")

    bin_width_ms = MS_PER_DAY / n_bins
    time_of_day_ms = ts % MS_PER_DAY
    bin_idx = np.minimum((time_of_day_ms / bin_width_ms).astype(np.int64), n_bins - 1)

    counts = np.bincount(bin_idx, minlength=n_bins).astype(np.float64)
    mean_count = ts.size / n_bins
    profile = counts / mean_count
    profile = np.maximum(profile, _EMPTY_BIN_FLOOR)
    profile = profile / profile.mean()
    return profile


def rescale_to_business_time(ts: np.ndarray, profile: np.ndarray) -> np.ndarray:
    """Deterministic time-change from clock time to business (operational) time.

    `ts` is a 1-D array of int64 epoch-milliseconds (UTC), and `profile` is
    an `n_bins`-length normalized rate profile as returned by
    `intraday_rate_profile` (piecewise-constant over time-of-day, period
    24h, repeating across days). Returns a float64 array (same length as
    `ts`) of business-time coordinates in seconds:

        tau(t) = integral_0^t rate(s) ds,  anchored so tau(ts[0]) == 0.

    The integral is exact for a piecewise-constant rate: a query time t splits
    into n_full_days * 86400s + within_day_seconds. Each full day contributes
    `sum(profile) * bin_width_seconds` (86400 seconds, since the profile has
    mean 1). The partial day contributes the cumulative integral over whole
    bins before the query's bin plus `profile[bin_idx]` times the time elapsed
    within that bin. Fully vectorized.

    Raises ValueError if `ts` has fewer than 2 events (no inter-event
    structure to rescale), if `ts` is not sorted in non-decreasing order (the
    `tau - tau[0]` anchor assumes `ts[0]` is earliest, and an unsorted input
    would give a nonsensical or negative business-time axis), or if `profile`
    is empty, non-1-D, non-finite or non-positive.
    """
    ts = np.asarray(ts, dtype=np.int64)
    profile = np.asarray(profile, dtype=np.float64)

    if ts.size == 0:
        raise ValueError("ts must not be empty")
    if ts.size < 2:
        raise ValueError("need at least 2 events to rescale to business time")
    if np.any(np.diff(ts) < 0):
        raise ValueError("ts must be sorted in non-decreasing order")
    if profile.ndim != 1 or profile.size == 0:
        raise ValueError("profile must be a non-empty 1-D array")
    if not np.all(np.isfinite(profile)) or np.any(profile <= 0.0):
        raise ValueError("profile must be finite and strictly positive everywhere")

    n_bins = profile.size
    bin_width_ms = MS_PER_DAY / n_bins
    bin_width_s = bin_width_ms / 1000.0

    # cum_profile_s[k] = integral of rate(s) ds over time-of-day bins [0, k).
    cum_profile_s = np.concatenate(([0.0], np.cumsum(profile))) * bin_width_s
    day_integral_s = cum_profile_s[-1]  # integral over one full 24h cycle

    day_idx = ts // MS_PER_DAY
    time_of_day_ms = ts - day_idx * MS_PER_DAY
    bin_idx = np.minimum((time_of_day_ms / bin_width_ms).astype(np.int64), n_bins - 1)
    within_bin_ms = time_of_day_ms - bin_idx * bin_width_ms

    tau = (
        day_idx.astype(np.float64) * day_integral_s
        + cum_profile_s[bin_idx]
        + profile[bin_idx] * (within_bin_ms / 1000.0)
    )

    return tau - tau[0]
