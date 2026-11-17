import numpy as np
import pytest

from microstructure.estimators.ofi import ofi_events
from microstructure.ml.l1_features import (
    L1_FEATURES,
    OFI_WINDOWS,
    build_l1_features,
    cumulative_quote_ofi,
    estimate_tick,
    fill_l1_columns,
)

TICK = 0.01


def _book(n: int, seed: int):
    """Per-event prior quotes on a 0.01 grid with random sizes and spreads."""
    rng = np.random.default_rng(seed)
    bid_ticks = 10_000 + np.cumsum(rng.integers(-1, 2, size=n))
    spread_ticks = rng.choice([1, 1, 1, 2, 3], size=n)
    bid_p = bid_ticks * TICK
    ask_p = (bid_ticks + spread_ticks) * TICK
    bid_q = rng.uniform(1.0, 100.0, size=n)
    ask_q = rng.uniform(1.0, 100.0, size=n)
    ofi_cum = np.cumsum(rng.normal(scale=50.0, size=n))
    return bid_p, bid_q, ask_p, ask_q, ofi_cum, spread_ticks


def _matrix(cols: dict[str, np.ndarray]) -> np.ndarray:
    return np.column_stack([cols[k] for k in L1_FEATURES])


def test_estimate_tick_ignores_float_noise():
    prices = np.array([17.384, 17.385, 17.387, 17.385, 17.39])
    assert estimate_tick(prices) == pytest.approx(0.001, rel=1e-9)
    with pytest.raises(ValueError):
        estimate_tick(np.array([1.0, 1.0]))


def test_estimate_tick_ignores_a_stray_off_grid_price():
    grid = 25_000.0 + 0.1 * np.arange(5_000)
    prices = np.concatenate([grid, [25_348.98]])
    assert estimate_tick(prices) == pytest.approx(0.1, rel=1e-9)
    # A sparse grid, where most gaps are several ticks, still finds the tick.
    rng = np.random.default_rng(0)
    sparse = 0.001 * np.unique(rng.integers(0, 20_000, size=4_000))
    assert estimate_tick(sparse) == pytest.approx(0.001, rel=1e-9)


def test_cumulative_ofi_differences_recover_window_sums():
    bid_p, bid_q, ask_p, ask_q, _, _ = _book(500, seed=0)
    c = cumulative_quote_ofi(bid_p, bid_q, ask_p, ask_q)
    e = ofi_events(bid_p, bid_q, ask_p, ask_q)
    assert c[0] == 0.0
    assert c[200] - c[120] == pytest.approx(e[120:200].sum())


def test_known_values_on_a_hand_built_book():
    n = 6000
    bid_p = np.full(n, 100.00)
    ask_p = np.full(n, 100.02)          # two ticks wide
    bid_q = np.full(n, 30.0)
    ask_q = np.full(n, 10.0)
    ofi_cum = 20.0 * np.arange(n)       # +20 units of buy pressure per trade
    cols = build_l1_features(bid_p, bid_q, ask_p, ask_q, ofi_cum, TICK)
    i = n - 1
    assert cols["queue_imb"][i] == pytest.approx(0.5)
    assert cols["spread_ticks"][i] == 2.0
    assert cols["one_tick"][i] == 0.0
    # microprice = (100.02*30 + 100.00*10)/40 = 100.015, mid = 100.01: half a tick.
    assert cols["micro_dev_ticks"][i] == pytest.approx(0.5)
    # Mean one-side depth is 20, so k trades carry k units of normalized flow.
    for k in OFI_WINDOWS:
        assert cols[f"ofi{k}"][i] == pytest.approx(np.log1p(k))
    # A constant mid has zero volatility; the scaled return must be 0, not NaN.
    assert cols["midret10"][i] == 0.0


def test_features_are_finite_and_complete():
    bid_p, bid_q, ask_p, ask_q, ofi_cum, spread = _book(8000, seed=1)
    cols = build_l1_features(bid_p, bid_q, ask_p, ask_q, ofi_cum, TICK)
    X = _matrix(cols)
    assert X.shape == (8000, len(L1_FEATURES))
    assert np.isfinite(X).all()
    assert np.array_equal(cols["one_tick"], (spread == 1).astype(float))
    assert np.abs(cols["queue_imb"]).max() < 1.0


def test_fill_matches_build_on_selected_rows():
    args = _book(3000, seed=4)[:5]
    rows = np.arange(100, 3000, 7)
    out = np.zeros((rows.size, 2 + len(L1_FEATURES)), dtype=np.float32)
    fill_l1_columns(out, rows, 2, *args, TICK)
    ref = _matrix(build_l1_features(*args, TICK))[rows].astype(np.float32)
    assert np.array_equal(out[:, 2:], ref)
    assert not out[:, :2].any()


def test_truncation_invariance_rows_do_not_see_the_future():
    """Rows before `cut` must be identical whether or not rows >= cut are corrupted.

    Row i holds the quote state before event i, so corrupting row `cut` itself
    (the quote that precedes event `cut`) may change row `cut` but nothing earlier.
    """
    bid_p, bid_q, ask_p, ask_q, ofi_cum, _ = _book(6000, seed=2)
    base = _matrix(build_l1_features(bid_p, bid_q, ask_p, ask_q, ofi_cum, TICK))
    cut = 4000
    b2, bq2, a2, aq2, o2 = (x.copy() for x in (bid_p, bid_q, ask_p, ask_q, ofi_cum))
    b2[cut:] += 5.0
    a2[cut:] += 5.07
    bq2[cut:] *= 1000.0
    aq2[cut:] *= 0.001
    o2[cut:] += 1e6
    changed = _matrix(build_l1_features(b2, bq2, a2, aq2, o2, TICK))
    assert np.array_equal(base[:cut], changed[:cut], equal_nan=True)
    assert not np.array_equal(base[cut:], changed[cut:], equal_nan=True)


def test_rejects_bad_inputs():
    bid_p, bid_q, ask_p, ask_q, ofi_cum, _ = _book(10, seed=3)
    with pytest.raises(ValueError):
        build_l1_features(bid_p, bid_q[:-1], ask_p, ask_q, ofi_cum, TICK)
    with pytest.raises(ValueError):
        build_l1_features(bid_p, bid_q, ask_p, ask_q, ofi_cum, 0.0)
