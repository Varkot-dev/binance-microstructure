"""Tests for microstructure.ml.tpp: censored scoring and the neural point process.

Contract under test:
1. Censoring cells: the business-time mapping of the 1 ms clock cell, the tie
   truncation, and causality (later events never change earlier cells/inputs).
2. Hawkes censored scoring: the state recursion matches the repo's exact
   log-likelihood, the cell probability matches a brute-force O(n^2)
   computation, and on simulated rounded data the true parameters beat
   Poisson and wrong parameters, with well-calibrated residuals. The censored
   score stays finite and at most 0 on tied data while the naive density is
   inflated without bound.
3. Log-normal mixture: density integrates to 1, CDF matches numerical
   integration and sampling.
4. Neural model: no skill manufactured on Poisson data, self-excitation found
   on Hawkes data, and scores of event i unchanged when later events change.

The Poisson/Hawkes tests run without PyTorch; the others skip if it is absent.
"""
from __future__ import annotations

import numpy as np
import pytest

from microstructure.estimators.hawkes import hawkes_multiexp_loglik, simulate_hawkes_exp
from microstructure.ml import tpp

T0_MS = 1_685_577_600_000  # 2023-06-01 00:00 UTC
FLAT = np.ones(48)
MU, ALPHA, BETA = 1.0, 0.6, 2.0
FIRST = 300  # events fed but not scored in the synthetic blocks

# Tiny network for the behavioural tests: a few seconds of single-thread CPU.
TINY = tpp.TPPConfig(
    hidden=16, n_components=4, horizons_s=(1.0, 10.0), window=64, window_burn=16,
    batch_size=32, max_windows_per_epoch=384, epochs=6, patience=2, lr=3e-3,
)
# Stated tolerances (nats per event) for the tiny network trained on ~12k events.
POISSON_TOL = 0.02       # |neural - Poisson| on Poisson data
HAWKES_SHORTFALL = 0.035  # neural may fall this far short of the true-parameter Hawkes


def _ms(times_s: np.ndarray, grid_ms: int = 1) -> np.ndarray:
    return T0_MS + (np.floor(times_s * 1000.0 / grid_ms) * grid_ms).astype(np.int64)


@pytest.fixture(scope="module")
def hawkes_ts() -> np.ndarray:
    return _ms(simulate_hawkes_exp(MU, ALPHA, BETA, 8000.0, seed=1))


# ---------------------------------------------------------------------------
# Censoring cells.
# ---------------------------------------------------------------------------


def test_cells_map_one_clock_millisecond_through_the_local_rate() -> None:
    profile = np.linspace(0.5, 1.5, 48)
    profile /= profile.mean()
    half_hour = 1_800_000
    # Events in bins 0, 0, 3, and one cell that straddles the bin 3/4 boundary.
    ts = T0_MS + np.array([1000, 1250, 3 * half_hour + 10, 4 * half_hour - 1, 4 * half_hour + 7])
    cen = tpp.censor_intervals(ts, profile)
    width = cen.hi[1:] - cen.lo[1:]
    assert width[0] == pytest.approx(profile[0] * 1e-3, rel=1e-6)
    assert width[1] == pytest.approx(profile[3] * 1e-3, rel=1e-6)
    assert width[2] == pytest.approx(profile[3] * 1e-3, rel=1e-6)  # ends exactly at the boundary
    assert width[3] == pytest.approx(profile[4] * 1e-3, rel=1e-6)
    np.testing.assert_allclose(cen.lo[1:], np.diff(cen.tau))
    # A gap that crosses three bin boundaries integrates the profile piecewise.
    assert cen.lo[2] == pytest.approx(profile[0] * (1800.0 - 1.25)
                                      + (profile[1] + profile[2]) * 1800.0 + profile[3] * 0.010)
    assert (cen.lo[0], cen.hi[0]) == (0.0, np.inf)


def test_tie_truncation_and_contract() -> None:
    ts = T0_MS + np.array([0, 5, 5, 9, 9, 30])
    cen = tpp.censor_intervals(ts, FLAT)
    # Events after a tied event (indices 3 and 5) cannot share its millisecond.
    np.testing.assert_allclose(cen.floor, [0, 0, 0, 1e-3, 0, 1e-3], atol=1e-12)
    rate = 40.0
    s = tpp.poisson_censored(rate, cen)
    expect = np.log((np.exp(-rate * cen.lo[3]) - np.exp(-rate * cen.hi[3])) / np.exp(-rate * 1e-3))
    assert s.loglik[3] == pytest.approx(expect, rel=1e-9)
    # Conditional on gap >= 1 ms the cells d = 1, 2, ... still sum to one.
    cells = np.exp(-rate * 1e-3 * np.arange(0, 2000)) - np.exp(-rate * 1e-3 * np.arange(1, 2001))
    assert cells[1:].sum() / np.exp(-rate * 1e-3) == pytest.approx(1.0, abs=1e-9)
    with pytest.raises(ValueError, match="three events"):
        tpp.censor_intervals(T0_MS + np.array([0, 5, 5, 5, 9]), FLAT)
    with pytest.raises(ValueError, match="sorted"):
        tpp.censor_intervals(T0_MS + np.array([0, 5, 4]), FLAT)


def test_cells_and_features_do_not_read_the_future(hawkes_ts: np.ndarray) -> None:
    ts = hawkes_ts[:3000]
    cut = 2000
    corrupt = ts.copy()
    corrupt[cut + 1 :] = corrupt[cut] + 50 + 3 * np.arange(ts.size - cut - 1)
    a = tpp.censor_intervals(ts, FLAT, tie_truncation=False)
    b = tpp.censor_intervals(corrupt, FLAT, tie_truncation=False)
    for name in ("tau", "lo", "hi", "floor"):
        np.testing.assert_array_equal(getattr(a, name)[: cut + 1], getattr(b, name)[: cut + 1])
    fa, fb = (tpp.tpp_features(c, (1.0, 10.0, 100.0)) for c in (a, b))
    np.testing.assert_array_equal(fa[: cut + 1], fb[: cut + 1])
    assert not np.array_equal(fa[cut + 1 :], fb[cut + 1 :])
    assert np.all(np.isfinite(fa[1:]))


# ---------------------------------------------------------------------------
# Hawkes and Poisson censored scoring.
# ---------------------------------------------------------------------------


def test_state_recursion_matches_repo_loglik() -> None:
    t = simulate_hawkes_exp(MU, ALPHA, BETA, 2000.0, seed=3)
    tau = t - t[0]
    alphas, betas = np.array([0.3, 0.25]), np.array([4.0, 0.3])
    mine = tpp.hawkes_density_loglik(0.7, alphas, betas, tau).sum() + np.log(0.7)
    repo = hawkes_multiexp_loglik(tau, float(tau[-1]), 0.7, alphas, betas)
    assert mine == pytest.approx(repo, rel=1e-10)


def test_cell_probability_matches_brute_force() -> None:
    t = simulate_hawkes_exp(MU, ALPHA, BETA, 40.0, seed=5)
    ts = _ms(t, grid_ms=100)  # coarse grid so cells are wide and ties occur
    cen = tpp.censor_intervals(ts, FLAT, tie_truncation=False)
    mu, alphas, betas = 0.8, np.array([0.3, 0.2]), np.array([3.0, 0.4])
    got = tpp.hawkes_censored(mu, alphas, betas, cen)

    def compensator(i: int, x: float) -> float:
        past = cen.tau[i - 1] - cen.tau[:i]  # ages of all earlier events at event i-1
        return mu * x + sum(a * np.sum(np.exp(-b * past) * (1 - np.exp(-b * x)))
                            for a, b in zip(alphas, betas, strict=True))

    assert (cen.gap_ms == 0).any()
    for i in range(1, cen.n):
        cell = np.exp(-compensator(i, cen.lo[i])) - np.exp(-compensator(i, cen.hi[i]))
        assert got.loglik[i] == pytest.approx(np.log(cell), rel=1e-9, abs=1e-12)
        assert got.log_surv_lo[i] == pytest.approx(-compensator(i, cen.lo[i]), abs=1e-10)


def test_true_hawkes_beats_poisson_and_wrong_hawkes_on_rounded_data() -> None:
    t = simulate_hawkes_exp(MU, ALPHA, BETA, 6000.0, seed=11)
    ts = _ms(t, grid_ms=20)  # 20 ms grid: many zero gaps
    cen = tpp.censor_intervals(ts, FLAT, tie_truncation=False)
    assert (cen.gap_ms == 0).mean() > 0.02
    rate = (cen.n - 1) / cen.tau[-1]
    true = tpp.hawkes_censored(MU, [ALPHA], [BETA], cen)
    pois = tpp.poisson_censored(rate, cen)
    wrong = tpp.hawkes_censored(1.5, [0.4], [0.2], cen)  # same mean rate, kernel 10x too slow
    spiky = tpp.hawkes_censored(MU, [ALPHA], [1e6], cen)
    means = {k: v.loglik[FIRST:].mean() for k, v in
             {"true": true, "pois": pois, "wrong": wrong, "spiky": spiky}.items()}
    assert all(np.isfinite(v.loglik).all() for v in (true, pois, wrong, spiky))
    assert all(np.all(v.loglik <= 1e-12) for v in (true, pois, wrong, spiky))
    assert means["true"] > means["pois"] + 0.05
    assert means["true"] > means["wrong"] + 0.02
    assert means["true"] > means["spiky"]

    # The naive density rewards the degenerate beta -> infinity kernel on the
    # tied events without bound; the censored score ranks it below the truth.
    tied = cen.gap_ms == 0
    naive_true = tpp.hawkes_density_loglik(MU, [ALPHA], [BETA], cen.tau)
    naive_spiky = tpp.hawkes_density_loglik(MU, [ALPHA], [1e6], cen.tau)
    assert naive_spiky[tied].mean() > naive_true[tied].mean() + 5.0
    assert naive_spiky[tied].mean() > 10.0

    # Calibration: randomized residuals are Exp(1) under the truth, not under Poisson.
    d_true = tpp.residual_diagnostics(tpp.rescaling_residuals(true, FIRST))
    d_pois = tpp.residual_diagnostics(tpp.rescaling_residuals(pois, FIRST))
    assert d_true["ks_distance"] < 2.0 * d_true["ks_5pct_critical_iid"]
    assert abs(d_true["lag1_autocorr_u"]) < 0.03
    assert d_pois["ks_distance"] > 0.05
    assert d_pois["lag1_autocorr_u"] > 0.05


def test_polished_fit_recovers_parameters_from_censored_score() -> None:
    from microstructure.analyses.q12_neural_ceiling import polish_hawkes

    ts = _ms(simulate_hawkes_exp(MU, ALPHA, BETA, 5000.0, seed=4), grid_ms=20)
    cen = tpp.censor_intervals(ts, FLAT, tie_truncation=False)
    start = {"mu": 2.0, "alphas": [0.3], "betas": [4.0]}
    fit = polish_hawkes(start, cen, 100, iters=200)
    before = tpp.hawkes_censored(2.0, [0.3], [4.0], cen).loglik[100:].mean()
    after = tpp.hawkes_censored(fit["mu"], fit["alphas"], fit["betas"], cen).loglik[100:].mean()
    assert after > before
    assert fit["n"] == pytest.approx(ALPHA, abs=0.08)
    assert fit["betas"][0] == pytest.approx(BETA, rel=0.3)


# ---------------------------------------------------------------------------
# Log-normal mixture and the neural model (PyTorch).
# ---------------------------------------------------------------------------


@pytest.fixture
def torch():
    t = pytest.importorskip("torch")
    t.set_num_threads(1)
    return t


def _mixture(torch):
    logw = torch.log(torch.tensor([0.5, 0.3, 0.2], dtype=torch.float64))
    mu = torch.tensor([-1.0, 0.4, 2.0], dtype=torch.float64)
    sigma = torch.tensor([0.3, 1.0, 0.6], dtype=torch.float64)
    return tpp.LogNormalMixture(logw, mu, sigma, shift=-2.0, scale=1.7)


def test_mixture_density_integrates_to_one_and_cdf_matches(torch) -> None:
    mix = _mixture(torch)
    x = torch.logspace(-12, 8, 400_001, dtype=torch.float64)
    pdf = mix.log_prob(x).exp()
    cum = torch.cumulative_trapezoid(pdf, x)
    assert float(cum[-1]) == pytest.approx(1.0, abs=1e-6)
    for i in (150_000, 200_000, 230_000, 260_000):
        assert float(mix.cdf(x[i + 1])) == pytest.approx(float(cum[i]), abs=1e-6)
    assert float(mix.cdf(torch.tensor(0.0))) == 0.0
    # Cell probability = CDF difference, including a cell that starts at 0.
    lo = torch.tensor([0.0, 0.01, 3.0])
    hi = torch.tensor([0.01, 0.02, 4.0])
    cell = mix.cell_prob_y(mix.standardize(lo), mix.standardize(hi))
    np.testing.assert_allclose(cell.numpy(), (mix.cdf(hi) - mix.cdf(lo)).numpy(), atol=1e-12)
    # Sampling agrees with the CDF.
    draws = mix.sample(200_000, generator=torch.Generator().manual_seed(0))
    for q in (0.02, 0.2, 2.0):
        assert float((draws < q).double().mean()) == pytest.approx(float(mix.cdf(torch.tensor(q))),
                                                                  abs=0.005)


def test_naive_density_fails_on_lattice_gaps_but_cell_score_does_not(torch) -> None:
    mix = _mixture(torch)
    assert float(mix.log_prob(torch.tensor(0.0))) == -np.inf  # a zero gap has density 0
    y0 = mix.standardize(torch.tensor(0.0))
    ll, _ = mix.log_cell_y(y0, mix.standardize(torch.tensor(1e-3)), y0)
    assert np.isfinite(float(ll)) and float(ll) <= 0.0
    # A component collapsed onto a lattice value: unbounded density, bounded cell score.
    spike = tpp.LogNormalMixture(torch.zeros(1, dtype=torch.float64),
                                 torch.tensor([np.log(2e-3)]), torch.tensor([1e-6]))
    assert float(spike.log_prob(torch.tensor(2e-3))) > 15.0
    ll, _ = spike.log_cell_y(spike.standardize(torch.tensor(2e-3)),
                             spike.standardize(torch.tensor(3e-3)), y0)
    assert float(ll) <= 0.0


def _blocks(ts: np.ndarray, cfg: tpp.TPPConfig):
    """60/20/20 contiguous split of a synthetic stream, scaler from the training part."""
    n = ts.size
    cuts = [(0, int(0.6 * n)), (int(0.6 * n), int(0.8 * n)), (int(0.8 * n), n)]
    cens = [tpp.censor_intervals(ts[a:b], FLAT, tie_truncation=False) for a, b in cuts]
    scaler = tpp.fit_scaler(tpp.tpp_features(cens[0], cfg.horizons_s), FIRST)
    return cens, [tpp.prepare_block(c, scaler, cfg.horizons_s, FIRST) for c in cens]


def test_neural_model_manufactures_no_skill_on_poisson_data(torch) -> None:
    rng = np.random.default_rng(0)
    ts = _ms(np.cumsum(rng.exponential(0.4, 20_000)))
    cens, blocks = _blocks(ts, TINY)
    model, history = tpp.train_tpp(blocks[0], blocks[1], TINY)
    rate = (cens[0].n - 1) / cens[0].tau[-1]
    pois = tpp.poisson_censored(rate, cens[2]).loglik[FIRST:].mean()
    neural = tpp.score_tpp(model, blocks[2], TINY).loglik[FIRST:].mean()
    assert abs(neural - pois) < POISSON_TOL
    assert len(history) >= 1


def test_neural_model_finds_self_excitation_and_is_causal(torch, hawkes_ts: np.ndarray) -> None:
    cens, blocks = _blocks(hawkes_ts, TINY)
    model, _ = tpp.train_tpp(blocks[0], blocks[1], TINY)
    rate = (cens[0].n - 1) / cens[0].tau[-1]
    pois = tpp.poisson_censored(rate, cens[2]).loglik[FIRST:].mean()
    true = tpp.hawkes_censored(MU, [ALPHA], [BETA], cens[2]).loglik[FIRST:].mean()
    scored = tpp.score_tpp(model, blocks[2], TINY)
    neural = scored.loglik[FIRST:].mean()
    assert true - pois > 0.1  # the planted structure is worth this much
    assert neural > pois + 0.08
    assert neural > true - HAWKES_SHORTFALL
    assert np.all(scored.loglik[:FIRST] == 0.0) and np.all(scored.loglik[FIRST:] < 0.0)
    resid = tpp.residual_diagnostics(tpp.rescaling_residuals(scored, FIRST))
    assert resid["ks_distance"] < 0.06

    # Causality: alter every event after `cut` (and, separately, drop them);
    # scores up to `cut` must be bit-identical.
    n0 = int(0.8 * hawkes_ts.size)
    test_ts = hawkes_ts[n0:]
    cut = FIRST + 517
    altered = test_ts.copy()
    altered[cut + 1 :] = altered[cut] + 7 + 11 * np.arange(test_ts.size - cut - 1)
    scaler = tpp.fit_scaler(tpp.tpp_features(cens[0], TINY.horizons_s), FIRST)
    for other in (altered, test_ts[: cut + 1]):
        cen = tpp.censor_intervals(other, FLAT, tie_truncation=False)
        got = tpp.score_tpp(model, tpp.prepare_block(cen, scaler, TINY.horizons_s, FIRST), TINY)
        np.testing.assert_array_equal(got.loglik[: cut + 1], scored.loglik[: cut + 1])
        np.testing.assert_array_equal(got.log_surv_lo[: cut + 1], scored.log_surv_lo[: cut + 1])
    assert not np.array_equal(
        tpp.score_tpp(model, tpp.prepare_block(
            tpp.censor_intervals(altered, FLAT, tie_truncation=False), scaler,
            TINY.horizons_s, FIRST), TINY).loglik[cut + 1 :],
        scored.loglik[cut + 1 :])
