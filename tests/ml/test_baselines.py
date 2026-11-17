import numpy as np

from microstructure.ml.baselines import (
    fit_linear_predictor,
    linear_predictor_proba,
    persistence_proba,
    repeat_probability,
    yule_walker_weights,
)
from microstructure.ml.evaluate import day_block_ci, log_loss_bits, mcc, score, skill
from microstructure.synthetic import fractional_signs, iid_signs, markov_signs


def test_yule_walker_recovers_ar1():
    rho = 0.5
    acf = rho ** np.arange(11)
    w = yule_walker_weights(acf, 10)
    assert abs(w[0] - rho) < 1e-9
    assert np.all(np.abs(w[1:]) < 1e-9)


def test_markov_chain_linear_predictor_equals_persistence():
    """For a Markov chain the past beyond lag 1 carries nothing, so the long
    linear filter must match the persistence forecast and its known accuracy."""
    p_repeat = 0.7
    s = markov_signs(400_000, p_repeat=p_repeat, seed=1)
    train, test = s[:200_000], s[200_000:]
    w, m = fit_linear_predictor(train, 50)
    y = (test > 0).astype(float)
    lin = score(y[50:], linear_predictor_proba(test, w, m)[50:])
    per = score(y[50:], persistence_proba(test, repeat_probability(train))[50:])
    assert abs(per.accuracy - p_repeat) < 0.005
    assert abs(lin.accuracy - per.accuracy) < 0.002
    assert abs(lin.log_loss_bits - per.log_loss_bits) < 0.002


def test_long_memory_linear_predictor_beats_persistence_in_log_loss():
    s = fractional_signs(600_000, d=0.3, seed=2)
    train, test = s[:300_000], s[300_000:]
    w, m = fit_linear_predictor(train, 500)
    y = (test > 0).astype(float)[500:]
    lin = score(y, linear_predictor_proba(test, w, m)[500:])
    per = score(y, persistence_proba(test, repeat_probability(train))[500:])
    assert lin.log_loss_bits < per.log_loss_bits - 0.005
    assert lin.accuracy >= per.accuracy


def test_iid_signs_are_unpredictable():
    s = iid_signs(300_000, seed=3)
    w, m = fit_linear_predictor(s[:150_000], 20)
    test = s[150_000:]
    sc = score((test > 0).astype(float)[20:], linear_predictor_proba(test, w, m)[20:])
    assert abs(sc.accuracy - 0.5) < 0.005
    assert abs(sc.log_loss_bits - 1.0) < 0.001


def test_linear_predictor_is_causal():
    s = markov_signs(5000, p_repeat=0.7, seed=4)
    w, m = fit_linear_predictor(s, 20)
    a = linear_predictor_proba(s, w, m)
    s2 = s.copy()
    s2[3000:] = -s2[3000:]
    b = linear_predictor_proba(s2, w, m)
    assert np.array_equal(a[:3001], b[:3001])


def test_metrics_known_values():
    y = np.array([1.0, 0.0, 1.0, 0.0])
    assert np.allclose(log_loss_bits(y, np.full(4, 0.5)), 1.0)
    assert mcc(y, np.array([0.9, 0.1, 0.8, 0.2])) == 1.0
    assert mcc(y, np.array([0.1, 0.9, 0.2, 0.8])) == -1.0
    assert skill(0.9, 1.0) == 1.0 - 0.9


def test_day_block_ci_covers_true_difference():
    rng = np.random.default_rng(5)
    ts = np.sort(rng.integers(0, 20 * 86_400_000, size=40_000))
    a = (rng.random(40_000) < 0.60).astype(float)
    b = (rng.random(40_000) < 0.55).astype(float)
    ci = day_block_ci(a, b, ts)
    assert ci.n_days == 20
    assert ci.lo < 0.05 < ci.hi
    assert ci.lo > 0.0
