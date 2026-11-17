import numpy as np
import pytest

from microstructure.ml.features import FEATURE_NAMES, WARMUP, build_features, ewma, feature_matrix
from microstructure.synthetic import markov_signs


def _events(n: int, seed: int):
    rng = np.random.default_rng(seed)
    ts = np.cumsum(rng.integers(0, 50, size=n)).astype(np.int64)
    signs = markov_signs(n, p_repeat=0.6, seed=seed)
    qty = np.exp(rng.normal(size=n))
    price = 100.0 * np.exp(np.cumsum(rng.normal(scale=1e-4, size=n)))
    n_prints = rng.integers(1, 5, size=n)
    return ts, signs, qty, price, n_prints


def test_ewma_matches_recursion():
    x = np.random.default_rng(0).normal(size=200)
    a = 1 - 0.5 ** (1 / 8)
    y = np.empty_like(x)
    prev = x[0]
    for i, v in enumerate(x):
        prev = a * v + (1 - a) * prev
        y[i] = prev
    assert np.allclose(ewma(x, 8), y)


def test_all_named_features_present_and_finite_after_warmup():
    cols = build_features(*_events(WARMUP + 2000, seed=1))
    X = feature_matrix(cols, FEATURE_NAMES)
    assert X.shape == (WARMUP + 2000, len(FEATURE_NAMES))
    assert np.isfinite(X[WARMUP:]).all()


def test_truncation_invariance_rows_do_not_see_the_future():
    """Row i must be identical whether or not events i, i+1, ... are corrupted."""
    ts, signs, qty, price, n_prints = _events(6000, seed=2)
    base = feature_matrix(build_features(ts, signs, qty, price, n_prints), FEATURE_NAMES)
    cut = 4000
    ts2, signs2, qty2, price2, np2 = ts.copy(), signs.copy(), qty.copy(), price.copy(), n_prints.copy()
    ts2[cut:] += 10_000_000
    signs2[cut:] = -signs2[cut:]
    qty2[cut:] *= 1000.0
    price2[cut:] *= 2.0
    np2[cut:] += 7
    changed = feature_matrix(build_features(ts2, signs2, qty2, price2, np2), FEATURE_NAMES)
    # Rows 0..cut read events 0..cut-1 only, so row `cut` itself must also match.
    assert np.array_equal(base[: cut + 1], changed[: cut + 1], equal_nan=True)
    assert not np.array_equal(base[cut + 1 :], changed[cut + 1 :], equal_nan=True)


def test_sign_lag1_is_previous_sign():
    ts, signs, qty, price, n_prints = _events(500, seed=3)
    cols = build_features(ts, signs, qty, price, n_prints)
    assert np.array_equal(cols["sign_lag1"][1:], signs[:-1].astype(float))
    assert np.isnan(cols["sign_lag1"][0])


def test_features_are_scale_free():
    """Rescaling price and lot size must leave every feature unchanged."""
    ts, signs, qty, price, n_prints = _events(WARMUP + 500, seed=4)
    a = feature_matrix(build_features(ts, signs, qty, price, n_prints), FEATURE_NAMES)
    b = feature_matrix(build_features(ts, signs, qty * 1e4, price * 1e-3, n_prints), FEATURE_NAMES)
    assert np.allclose(a[WARMUP:], b[WARMUP:], atol=1e-4)


def test_length_mismatch_raises():
    ts, signs, qty, price, n_prints = _events(100, seed=5)
    with pytest.raises(ValueError):
        build_features(ts[:-1], signs, qty, price, n_prints)


def test_matrix_builder_matches_dict_builder():
    from microstructure.ml.features import build_feature_matrix

    ev = _events(WARMUP + 300, seed=6)
    a = feature_matrix(build_features(*ev), FEATURE_NAMES)
    assert np.array_equal(a, build_feature_matrix(*ev), equal_nan=True)
