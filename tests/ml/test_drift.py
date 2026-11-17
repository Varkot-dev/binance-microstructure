"""Synthetic known-answer tests for the shift measurement and attribution tools.

Three worlds with a fixed, correct model p(y=1 | x) = sigmoid(2 * x0):
  (a) pure covariate shift: P(x) moves, P(y | x) does not;
  (b) pure concept shift: P(x) fixed, P(y | x) reversed;
  (c) no shift at all.
The attribution must put the loss change where it was planted.
"""
import numpy as np
import pytest

from microstructure.ml.drift import (
    aligned_day_sums,
    day_picks,
    density_ratio,
    domain_auc,
    effective_sample_size,
    equal_size,
    feature_shift,
    fit_domain_classifier,
    percentile_ci,
    resampled_means,
    reweighting_attribution,
    shift_decomposition,
)
from microstructure.ml.evaluate import log_loss_bits

N = 20_000
SLOPE = 2.0


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def _draw(seed: int, shift: float = 0.0, slope: float = SLOPE):
    """X with 3 features (only x0 matters), labels from sigmoid(slope * x0)."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(N, 3)).astype(np.float32)
    X[:, 0] += shift
    y = (rng.random(N) < _sigmoid(slope * X[:, 0])).astype(np.float64)
    return X, y


def _model_loss(X, y):
    """Loss of the fixed source-period model, which is the true source P(y | x)."""
    return log_loss_bits(y, _sigmoid(SLOPE * X[:, 0]))


def _attribute(shift: float, slope: float):
    Xs_fit, _ = _draw(1)
    Xt_fit, _ = _draw(2, shift, slope)
    Xs, ys = _draw(3)
    Xt, yt = _draw(4, shift, slope)
    clf = fit_domain_classifier(Xs_fit, Xt_fit)
    auc = domain_auc(clf, Xs, Xt)
    w = density_ratio(clf.predict(Xs), clf.n_src, clf.n_tgt)
    return auc, reweighting_attribution(_model_loss(Xs, ys), w, _model_loss(Xt, yt))


def test_pure_covariate_shift_is_attributed_to_the_covariate_part():
    auc, att = _attribute(shift=0.8, slope=SLOPE)
    assert auc > 0.65
    # The true model is more certain away from x0 = 0, so the loss falls.
    assert att["total"] < -0.03
    assert att["covariate"] == pytest.approx(att["total"], abs=0.25 * abs(att["total"]))
    assert abs(att["concept"]) < 0.25 * abs(att["total"])
    assert att["reliable"]


def test_pure_concept_shift_lands_in_the_concept_residual():
    auc, att = _attribute(shift=0.0, slope=-SLOPE)
    assert abs(auc - 0.5) < 0.03
    assert att["total"] > 0.5          # the old model is now confidently wrong
    assert abs(att["covariate"]) < 0.05 * att["total"]
    assert att["concept"] == pytest.approx(att["total"], rel=0.05)
    assert att["ess_share"] > 0.8


def test_no_shift_gives_chance_auc_and_two_null_parts():
    auc, att = _attribute(shift=0.0, slope=SLOPE)
    assert abs(auc - 0.5) < 0.03
    assert abs(att["covariate"]) < 0.02
    assert abs(att["concept"]) < 0.03
    assert att["covariate"] + att["concept"] == pytest.approx(att["total"])


def test_density_ratio_follows_bayes_rule_and_is_mean_one():
    pi = np.array([0.5, 0.75, 0.2])
    w = density_ratio(pi, n_src=100, n_tgt=100, clip_quantile=None)
    assert np.allclose(w / w[0], [1.0, 3.0, 0.25])
    assert w.mean() == pytest.approx(1.0)
    # Twice as many target rows in training doubles pi / (1 - pi) at equal density.
    w2 = density_ratio(np.array([2 / 3, 2 / 3]), n_src=100, n_tgt=200, clip_quantile=None)
    assert np.allclose(w2, 1.0)
    clipped = density_ratio(np.r_[np.full(99, 0.5), 0.9999], 1, 1, clip_quantile=0.5)
    assert np.allclose(clipped, 1.0)


def test_effective_sample_size_extremes_and_unreliable_flag():
    assert effective_sample_size(np.ones(50)) == pytest.approx(50.0)
    one_hot = np.zeros(50)
    one_hot[3] = 7.0
    assert effective_sample_size(one_hot) == pytest.approx(1.0)
    att = reweighting_attribution(np.ones(50), one_hot, np.ones(50))
    assert not att["reliable"]


def test_feature_shift_recovers_planted_mean_shift():
    rng = np.random.default_rng(0)
    a = rng.normal(size=(50_000, 2))
    b = rng.normal(size=(50_000, 2))
    b[:, 1] += 1.0
    out = feature_shift(a, b, ("same", "moved"))
    assert abs(out["same"]["smd"]) < 0.03 and out["same"]["ks"] < 0.02
    assert out["moved"]["smd"] == pytest.approx(1.0, abs=0.03)
    # KS between N(0,1) and N(1,1) is 2 * Phi(0.5) - 1 = 0.383.
    assert out["moved"]["ks"] == pytest.approx(0.383, abs=0.015)


def test_equal_size_subsamples_to_the_smaller_input():
    a, b = equal_size(np.arange(10).reshape(10, 1), np.arange(4).reshape(4, 1))
    assert a.shape == b.shape == (4, 1)


def test_shift_decomposition_identity_for_scores_and_losses():
    d = shift_decomposition(0.70, 0.55, 0.62)
    assert d["staleness_gap"] == pytest.approx(0.07)
    assert d["predictability_change"] == pytest.approx(-0.08)
    assert d["raw_drop"] == pytest.approx(d["staleness_gap"] - d["predictability_change"])
    # A loss: the stale model's loss is higher in j, a fresh model does better.
    loss = shift_decomposition(0.80, 0.95, 0.85, higher_is_better=False)
    assert loss["staleness_gap"] == pytest.approx(0.10)
    assert loss["predictability_change"] == pytest.approx(-0.05)
    assert loss["raw_drop"] == pytest.approx(0.15)


def test_day_bootstrap_alignment_and_coverage():
    union = np.array([10, 11, 12, 13])
    s, c = aligned_day_sums([11, 13], [5.0, 9.0], [10.0, 10.0], union)
    assert s.tolist() == [0.0, 5.0, 0.0, 9.0] and c.tolist() == [0.0, 10.0, 0.0, 10.0]

    rng = np.random.default_rng(0)
    n_days, per_day = 40, 500
    sums = rng.binomial(per_day, 0.6, size=n_days).astype(float)
    counts = np.full(n_days, float(per_day))
    reps = resampled_means(sums, counts, day_picks(n_days, 2000, rng))
    lo, hi = percentile_ci(reps)
    assert lo < 0.6 < hi and hi - lo < 0.03
    # A resample that only hits absent days is NaN, not a crash.
    empty = resampled_means(s, c, np.array([[0, 2, 0, 2]]))
    assert np.isnan(empty[0])
