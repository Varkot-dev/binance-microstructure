"""Tests for business-time rescaling (seasonality-robust Hawkes fitting).

These tests justify the deseasonalization. Group 3's two `_amplitude_*` tests
parallel the regime-switching trap in
tests/estimators/test_hawkes.py::test_regime_switching_poisson_produces_spurious_endogeneity_trap:
a non-stationary intraday rate profile, left in clock time, inflates a Hawkes
fit's alpha even though (in Group 3, via `simulate_seasonal_hawkes_exp`) there
is real self-excitation with its true alpha obscured by seasonality.
Rescaling to business time before fitting recovers the true alpha. A separate
test documents a measured downward bias in the rejected alternative
construction (post-hoc thinning of an unseasonal Hawkes simulation).
"""
from __future__ import annotations

import numpy as np
import pytest

from microstructure.estimators.hawkes import (
    fit_hawkes_exp,
    simulate_hawkes_exp,
    simulate_seasonal_hawkes_exp,
)
from microstructure.signals.eventtime import (
    MS_PER_DAY,
    intraday_rate_profile,
    rescale_to_business_time,
)

# ---------------------------------------------------------------------------
# Shared synthetic data helpers.
# ---------------------------------------------------------------------------

_DAY_MS = MS_PER_DAY


def _planted_daily_shape(n_bins: int, amplitude: float = 1.05) -> np.ndarray:
    """A 2-cycle-per-day sinusoidal shape, normalized to mean 1, strictly positive.

    2 full cosine cycles across the 24h period (period = 12h). `amplitude`
    controls trough depth (raw = amplitude + cos(...), so a smaller amplitude
    gives a deeper, narrower trough relative to the mean). The default (1.05)
    is used for the profile-recovery and CV-flattening tests (groups 1-2),
    where a deep trough gives a more distinctive shape. Group 3 also runs a
    shallower amplitude=1.4.
    """
    bin_centers = (np.arange(n_bins) + 0.5) / n_bins  # in [0, 1), fraction of day
    raw = amplitude + np.cos(2 * 2 * np.pi * bin_centers)  # 2 cycles/day
    return raw / raw.mean()


def _simulate_inhomogeneous_poisson(
    shape: np.ndarray, mean_rate_per_ms: float, t_end_ms: float, seed: int
) -> np.ndarray:
    """Thinning-based simulation of a Poisson process with rate mean_rate_per_ms * shape(tod).

    `shape` is piecewise-constant over `len(shape)` time-of-day bins,
    period 24h, mean 1. Uses simple rejection (thinning) against the
    max of `shape` as the bounding constant.
    """
    rng = np.random.default_rng(seed)
    n_bins = shape.size
    bin_width_ms = _DAY_MS / n_bins
    shape_max = shape.max()
    lambda_bar = mean_rate_per_ms * shape_max

    events: list[float] = []
    t = 0.0
    while t < t_end_ms:
        t += rng.exponential(1.0 / lambda_bar)
        if t >= t_end_ms:
            break
        tod_ms = t % _DAY_MS
        bin_idx = min(int(tod_ms / bin_width_ms), n_bins - 1)
        accept_prob = (mean_rate_per_ms * shape[bin_idx]) / lambda_bar
        if rng.random() <= accept_prob:
            events.append(t)
    return np.asarray(events, dtype=np.int64)


# ---------------------------------------------------------------------------
# Group 1: profile recovery.
# ---------------------------------------------------------------------------


def test_intraday_rate_profile_recovers_planted_2cycle_shape():
    n_bins = 48
    true_shape = _planted_daily_shape(n_bins)
    # 20 days, mean rate high enough for a clean per-bin recovery.
    t_end_ms = 20 * _DAY_MS
    mean_rate_per_ms = 2000.0 / _DAY_MS  # ~2000 events/day
    ts = _simulate_inhomogeneous_poisson(true_shape, mean_rate_per_ms, t_end_ms, seed=1)

    profile = intraday_rate_profile(ts, n_bins=n_bins)

    assert profile.mean() == pytest.approx(1.0, abs=1e-9)
    corr = np.corrcoef(profile, true_shape)[0, 1]
    assert corr > 0.95, f"expected profile-shape correlation > 0.95, got {corr}"


def test_intraday_rate_profile_floors_empty_bins():
    # All events land in bin 0 only (time-of-day 0..bin_width); other bins
    # must be floored, not zero, to keep rescale_to_business_time invertible.
    # The floor is applied before renormalizing to mean 1, so the floored bins
    # land very close to, but not exactly at, the raw 0.01 floor constant.
    n_bins = 48
    bin_width_ms = _DAY_MS / n_bins
    ts = np.arange(0, 100) * _DAY_MS + 10  # every event at ~10ms into the day
    assert (ts % _DAY_MS < bin_width_ms).all()

    profile = intraday_rate_profile(ts, n_bins=n_bins)

    assert np.all(profile > 0.0)
    assert profile[1:].min() == pytest.approx(0.01, rel=0.02)
    assert profile.mean() == pytest.approx(1.0, abs=1e-9)


def test_intraday_rate_profile_floor_preserves_exact_mean_one():
    """The floor is applied before renormalizing, so the mean stays exactly 1
    even with several empty bins, and a full 24h cycle's business-time integral
    (see test_rescale_to_business_time_full_day_integrates_to_exact_86400s)
    stays exactly 86400 seconds.
    """
    n_bins = 48
    bin_width_ms = _DAY_MS / n_bins
    # Force events into only the first 36 of 48 bins, leaving 12 bins
    # (indices 36-47) with zero observed events.
    active_bins = np.arange(36)
    rng = np.random.default_rng(3)
    bin_choices = rng.choice(active_bins, size=2000)
    offsets_ms = rng.integers(0, int(bin_width_ms), size=2000)
    ts = (bin_choices * bin_width_ms + offsets_ms).astype(np.int64)

    profile = intraday_rate_profile(ts, n_bins=n_bins)

    assert profile.mean() == pytest.approx(1.0, abs=1e-12)
    assert np.all(profile[36:] > 0.0)
    assert np.all(profile[36:] < profile[:36].min())  # floored bins are still the smallest


def test_intraday_rate_profile_rejects_empty_input():
    with pytest.raises(ValueError):
        intraday_rate_profile(np.array([], dtype=np.int64))


def test_intraday_rate_profile_rejects_non_positive_n_bins():
    with pytest.raises(ValueError):
        intraday_rate_profile(np.array([0, 1000], dtype=np.int64), n_bins=0)


# ---------------------------------------------------------------------------
# Group 2: rescaling flattens the inter-event-time distribution.
# ---------------------------------------------------------------------------


def _coefficient_of_variation(x: np.ndarray) -> float:
    return float(np.std(x, ddof=1) / np.mean(x))


def _max_ks_deviation_from_exponential(gaps: np.ndarray) -> float:
    """Max |empirical CDF - exponential CDF| for inter-event gaps (KS-style).

    Compares the empirical CDF of `gaps` against 1 - exp(-x/mean(gaps)), the
    CDF of an Exp(1/mean) distribution, the inter-event-gap distribution of a
    homogeneous Poisson process, which business-time-rescaled events from a
    deseasonalized Poisson-like process should follow. Uses a sorted
    empirical CDF.
    """
    sorted_gaps = np.sort(gaps)
    n = sorted_gaps.size
    empirical_cdf = (np.arange(1, n + 1)) / n
    mean_gap = sorted_gaps.mean()
    theoretical_cdf = 1.0 - np.exp(-sorted_gaps / mean_gap)
    return float(np.max(np.abs(empirical_cdf - theoretical_cdf)))


def test_rescale_to_business_time_flattens_cv_to_near_one():
    n_bins = 48
    true_shape = _planted_daily_shape(n_bins)
    t_end_ms = 20 * _DAY_MS
    mean_rate_per_ms = 2000.0 / _DAY_MS
    ts = _simulate_inhomogeneous_poisson(true_shape, mean_rate_per_ms, t_end_ms, seed=2)

    raw_gaps = np.diff(ts.astype(np.float64))
    raw_cv = _coefficient_of_variation(raw_gaps)
    # Inhomogeneous-rate Poisson clumps into high/low periods, pushing the CV
    # of raw clock-time gaps well above the CV=1 of a homogeneous Poisson process.
    assert raw_cv > 1.15, f"expected raw clock-time CV > 1.15, got {raw_cv}"

    profile = intraday_rate_profile(ts, n_bins=n_bins)
    tau = rescale_to_business_time(ts, profile)
    tau_gaps = np.diff(tau)
    tau_cv = _coefficient_of_variation(tau_gaps)

    assert abs(tau_cv - 1.0) < 0.05, f"expected business-time CV within 5% of 1.0, got {tau_cv}"

    # KS-style distribution check: business-time gaps should look
    # exponentially distributed, not just have CV~1 (which does not rule out
    # non-exponential shapes with the same second moment).
    max_dev = _max_ks_deviation_from_exponential(tau_gaps)
    assert max_dev < 0.02, f"expected max KS deviation from Exp(1/mean) < 0.02, got {max_dev}"


def test_rescale_to_business_time_full_day_integrates_to_exact_86400s():
    """Since intraday_rate_profile floors then renormalizes (exact mean 1 even
    with floored bins), one full 24h cycle integrates to exactly 86400.0
    seconds in business time, including when some bins were floored.
    """
    n_bins = 48
    bin_width_ms = _DAY_MS / n_bins
    # Force 12 empty bins (as in the floor test above) so the floor is exercised.
    active_bins = np.arange(36)
    rng = np.random.default_rng(5)
    bin_choices = rng.choice(active_bins, size=2000)
    offsets_ms = rng.integers(0, int(bin_width_ms), size=2000)
    ts_for_profile = (bin_choices * bin_width_ms + offsets_ms).astype(np.int64)
    profile = intraday_rate_profile(ts_for_profile, n_bins=n_bins)

    # Two events exactly one full day apart, at the same time-of-day.
    ts = np.array([0, _DAY_MS], dtype=np.int64)
    tau = rescale_to_business_time(ts, profile)
    assert tau[1] - tau[0] == pytest.approx(86_400.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Group 3: seasonality inflates a Hawkes fit's alpha in clock time;
# business-time rescaling recovers the true alpha.
#
# Analogue of
# tests/estimators/test_hawkes.py::test_regime_switching_poisson_produces_spurious_endogeneity_trap
# (Filimonov & Sornette 2015), where a non-self-exciting but non-stationary
# process fools both the MLE and the count-variance estimator. Here a Hawkes
# process with real self-excitation (known alpha) has a seasonal baseline,
# simulated directly via `simulate_seasonal_hawkes_exp` rather than by
# post-hoc thinning (see the construction-bias test below). A raw clock-time
# fit conflates the seasonality-driven clustering with self-excitation and
# reports an inflated alpha; rescaling to business time first recovers alpha
# close to its planted value. This is the reason the eventtime module exists.
#
# Run at a shallow-trough amplitude (1.4) and a deep-trough amplitude (1.05).
# At 1.05 the raw fit lands near a high alpha (~0.90), a large
# seasonality-driven inflation and not a Nelder-Mead degenerate-optimum
# artifact (see the amplitude-1.05 test). Both amplitudes recover alpha within
# +/-0.06 of the true value after rescaling.
# ---------------------------------------------------------------------------


def test_business_time_rescaling_corrects_seasonality_inflated_alpha_amplitude_1_4():
    _run_seasonal_justification_case(amplitude=1.4, seed=7)


def test_business_time_rescaling_corrects_seasonality_inflated_alpha_amplitude_1_05_deep_trough():
    """Deep-trough case (amplitude=1.05): a shallow daily swing could
    understate how badly clock-time Hawkes fitting is fooled by deep, sharp
    intraday seasonality. With the seasonal-baseline simulator the raw fit
    lands at a large but non-degenerate alpha (~0.90, beta near the true kernel
    timescale), not the degenerate near-alpha=1/near-beta=0 Nelder-Mead optimum
    that a thinning-based construction hits at this amplitude. Business-time
    rescaling recovers the true alpha within +/-0.06.
    """
    _run_seasonal_justification_case(amplitude=1.05, seed=7)


def _run_seasonal_justification_case(amplitude: float, seed: int) -> None:
    true_mu, true_alpha, true_beta = 0.4, 0.35, 1.5
    t_end_s = 10 * 24 * 3600.0  # ~10 days, in seconds (Hawkes sim uses float seconds)
    n_bins = 48

    shape = _planted_daily_shape(n_bins, amplitude=amplitude)
    hawkes_times_s = simulate_seasonal_hawkes_exp(
        true_mu, true_alpha, true_beta, t_end_s, shape, seed=seed
    )
    assert hawkes_times_s.size > 100, "need enough events for a stable fit"

    # --- Raw clock-time fit: seasonality inflates alpha. ---
    raw_t_end_s = float(hawkes_times_s[-1]) + 1.0
    raw_fit = fit_hawkes_exp(hawkes_times_s, raw_t_end_s)

    assert raw_fit.alpha > true_alpha + 0.08, (
        f"amplitude={amplitude}: expected seasonality to inflate raw-fit alpha above "
        f"true+0.08={true_alpha + 0.08}, got {raw_fit.alpha}"
    )

    # --- Business-time fit: rescaling removes the seasonality confound. ---
    # Convert to int64 epoch-ms so eventtime's ms-based API applies, anchored
    # at an arbitrary epoch far from 0 so day boundaries are non-trivial.
    epoch_anchor_ms = 1_700_000_000_000
    ts_ms = (epoch_anchor_ms + hawkes_times_s * 1000.0).astype(np.int64)
    profile = intraday_rate_profile(ts_ms, n_bins=n_bins)
    tau_s = rescale_to_business_time(ts_ms, profile)
    tau_t_end_s = float(tau_s[-1]) + 1.0
    rescaled_fit = fit_hawkes_exp(tau_s, tau_t_end_s)

    assert abs(rescaled_fit.alpha - true_alpha) < 0.06, (
        f"amplitude={amplitude}: expected business-time fit alpha within +/-0.06 of "
        f"true alpha={true_alpha}, got {rescaled_fit.alpha}"
    )


# ---------------------------------------------------------------------------
# Secondary control test: post-hoc thinning by a daily profile, kept to
# document construction bias, not as the justification test.
#
# Approximating "a Hawkes process with seasonal baseline" by simulating a
# constant-mu Hawkes process and thinning its realized events by an
# independent time-of-day acceptance probability is systematically biased:
# thinning discards excited child events along with baseline events, which
# depresses a branching-ratio estimate on its own, independent of any
# seasonality confound. The test records the measured numbers, to discourage
# using thinning as a shortcut.
# ---------------------------------------------------------------------------


def _thin_by_daily_profile(ts: np.ndarray, shape: np.ndarray, seed: int) -> np.ndarray:
    """Thin a Hawkes event-time array by the (normalized) daily shape.

    Thinning by an independent time-of-day acceptance probability only
    approximates a Hawkes process with seasonal baseline mu(t): it modulates
    event density by time of day but removes some excited children along with
    baseline events. See `test_thinning_construction_has_documented_downward_bias`
    for the measured bias.
    """
    rng = np.random.default_rng(seed)
    n_bins = shape.size
    bin_width_ms = _DAY_MS / n_bins
    shape_norm = shape / shape.max()  # in (0, 1], so it's a valid acceptance prob

    tod_ms = ts % _DAY_MS
    bin_idx = np.minimum((tod_ms / bin_width_ms).astype(np.int64), n_bins - 1)
    accept_prob = shape_norm[bin_idx]
    accept = rng.random(ts.size) <= accept_prob
    return ts[accept]


def test_thinning_construction_has_documented_downward_bias():
    """Construction-bias documentation, not the justification test.

    Thinning an unseasonal Hawkes simulation by a daily profile (amplitude=1.4,
    thinning seed=8) gives a business-time-rescaled fit of alpha ~ 0.28-0.29
    against true_alpha=0.35: a reproducible ~0.06-0.07 downward bias (std
    ~0.001 across 5 thinning seeds). A control confirms the source: uniform
    (non-seasonal) random thinning of the same series at the same keep-fraction
    drops fitted alpha to ~0.25 with no seasonality present. The bias comes
    from thinning removing excited child events, not from
    `rescale_to_business_time`. The justification test therefore uses
    `simulate_seasonal_hawkes_exp`.
    """
    true_mu, true_alpha, true_beta = 0.4, 0.35, 1.5
    t_end_s = 10 * 24 * 3600.0
    n_bins = 48

    hawkes_times_s = simulate_hawkes_exp(true_mu, true_alpha, true_beta, t_end_s, seed=7)
    epoch_anchor_ms = 1_700_000_000_000
    ts_ms = (epoch_anchor_ms + hawkes_times_s * 1000.0).astype(np.int64)

    shape = _planted_daily_shape(n_bins, amplitude=1.4)
    thinned_ts_ms = _thin_by_daily_profile(ts_ms, shape, seed=8)
    assert thinned_ts_ms.size > 100, "need enough events left after thinning for a stable fit"

    profile = intraday_rate_profile(thinned_ts_ms, n_bins=n_bins)
    tau_s = rescale_to_business_time(thinned_ts_ms, profile)
    tau_t_end_s = float(tau_s[-1]) + 1.0
    rescaled_fit = fit_hawkes_exp(tau_s, tau_t_end_s)

    # Rescaled alpha lands well below true_alpha because thinning loses
    # excited children, not because rescaling failed to remove seasonality.
    assert 0.20 < rescaled_fit.alpha < 0.32, (
        f"expected the thinning construction's documented downward bias "
        f"(alpha in (0.20, 0.32) vs true_alpha={true_alpha}), got {rescaled_fit.alpha}"
    )


# ---------------------------------------------------------------------------
# Group 4: determinism + edge cases.
# ---------------------------------------------------------------------------


def test_intraday_rate_profile_is_deterministic():
    ts = np.array([0, 1000, 90_000, _DAY_MS + 500, 2 * _DAY_MS + 12_345], dtype=np.int64)
    p1 = intraday_rate_profile(ts, n_bins=48)
    p2 = intraday_rate_profile(ts, n_bins=48)
    np.testing.assert_array_equal(p1, p2)


def test_rescale_to_business_time_is_deterministic():
    ts = np.array([0, 1000, 90_000, _DAY_MS + 500, 2 * _DAY_MS + 12_345], dtype=np.int64)
    profile = intraday_rate_profile(ts, n_bins=48)
    tau1 = rescale_to_business_time(ts, profile)
    tau2 = rescale_to_business_time(ts, profile)
    np.testing.assert_array_equal(tau1, tau2)


def test_rescale_to_business_time_anchors_first_event_at_zero():
    ts = np.array([12_345, 90_000, _DAY_MS + 500], dtype=np.int64)
    profile = intraday_rate_profile(ts, n_bins=48)
    tau = rescale_to_business_time(ts, profile)
    assert tau[0] == 0.0


def test_intraday_rate_profile_rejects_empty_array():
    with pytest.raises(ValueError):
        intraday_rate_profile(np.array([], dtype=np.int64))


def test_rescale_to_business_time_rejects_empty_array():
    with pytest.raises(ValueError):
        rescale_to_business_time(np.array([], dtype=np.int64), np.ones(48))


def test_rescale_to_business_time_rejects_single_event():
    with pytest.raises(ValueError):
        rescale_to_business_time(np.array([1000], dtype=np.int64), np.ones(48))


def test_rescale_to_business_time_rejects_non_positive_profile():
    ts = np.array([0, 1000], dtype=np.int64)
    bad_profile = np.ones(48)
    bad_profile[3] = 0.0
    with pytest.raises(ValueError):
        rescale_to_business_time(ts, bad_profile)


def test_rescale_to_business_time_rejects_empty_profile():
    ts = np.array([0, 1000], dtype=np.int64)
    with pytest.raises(ValueError):
        rescale_to_business_time(ts, np.array([]))


def test_rescale_to_business_time_rejects_nan_in_profile():
    """Non-finite profile values are rejected rather than propagating NaN
    through the integral."""
    ts = np.array([0, 1000], dtype=np.int64)
    bad_profile = np.ones(48)
    bad_profile[5] = np.nan
    with pytest.raises(ValueError):
        rescale_to_business_time(ts, bad_profile)


def test_rescale_to_business_time_rejects_inf_in_profile():
    ts = np.array([0, 1000], dtype=np.int64)
    bad_profile = np.ones(48)
    bad_profile[5] = np.inf
    with pytest.raises(ValueError):
        rescale_to_business_time(ts, bad_profile)


def test_rescale_to_business_time_rejects_unsorted_ts():
    """Unsorted ts is rejected: the day/bin decomposition and the tau[0] anchor
    assume ts[0] is the earliest event, so unsorted input would silently give
    a nonsensical business-time axis."""
    ts = np.array([2000, 1000, 3000], dtype=np.int64)
    profile = np.ones(48)
    with pytest.raises(ValueError):
        rescale_to_business_time(ts, profile)


def test_rescale_to_business_time_keeps_millisecond_precision_at_epoch_2024():
    """Summing day_idx * 86400 first would put ~1.7e9 s in a float64 and lose
    ~2e-7 s per timestamp, which is 1e-4 of a 1 ms gap. With a flat profile the
    business-time gaps must equal the clock gaps to well under that."""
    start_ms = 1_704_067_200_000 + 13 * 3_600_000 + 17  # 2024-01-01 13:00:00.017 UTC
    ts = start_ms + np.arange(2000, dtype=np.int64)  # 1 ms spacing
    tau = rescale_to_business_time(ts, np.ones(48))
    np.testing.assert_allclose(np.diff(tau), 0.001, rtol=0, atol=1e-10)
