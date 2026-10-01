import numpy as np

from microstructure.estimators.ofi import OLSFit, ofi_events, ols_through_origin


def test_ofi_hand_computed_cases():
    # update 1: bid price rises (add q^b_n), ask unchanged (both ask terms fire: -q^a_n + q^a_{n-1} = 0)
    bid_p = np.array([100.0, 100.1, 100.1, 100.0])
    bid_q = np.array([5.0, 3.0, 7.0, 2.0])
    ask_p = np.array([100.2, 100.2, 100.3, 100.2])
    ask_q = np.array([4.0, 4.0, 6.0, 9.0])
    e = ofi_events(bid_p, bid_q, ask_p, ask_q)
    # n=1: b up: +3; a equal: -4+4=0                       -> 3
    # n=2: b equal: +7-3=4; a up: +4 (only q^a_{n-1} term) -> 8
    # n=3: b down: -7; a down: -9 (only -q^a_n term)       -> -16
    assert np.allclose(e, [3.0, 8.0, -16.0])


def test_ols_through_origin_recovers_slope():
    rng = np.random.default_rng(7)
    x = rng.normal(0, 50, 20_000)
    y = 0.003 * x + rng.normal(0, 0.02, x.size)
    fit = ols_through_origin(x, y)
    assert isinstance(fit, OLSFit)
    assert abs(fit.slope - 0.003) < 2e-4
    assert fit.r2 > 0.9


def test_ols_pure_noise_r2_near_zero():
    rng = np.random.default_rng(8)
    fit = ols_through_origin(rng.normal(size=10_000), rng.normal(size=10_000))
    assert abs(fit.slope) < 0.05
    assert fit.r2 < 0.01


def test_ofi_events_empty_input_raises_clear_error():
    import pytest

    empty = np.array([])
    with pytest.raises(ValueError, match="empty"):
        ofi_events(empty, empty, empty, empty)


def test_ofi_events_single_quote_has_no_updates():
    one = np.array([1.0])
    assert ofi_events(one, one, one, one).size == 0


def test_ols_through_origin_rejects_bad_shapes():
    import pytest

    with pytest.raises(ValueError, match="shape"):
        ols_through_origin(np.ones(5), np.ones(4))
    with pytest.raises(ValueError, match="1-D"):
        ols_through_origin(np.ones((3, 2)), np.ones((3, 2)))
    with pytest.raises(ValueError, match="empty"):
        ols_through_origin(np.array([]), np.array([]))


def test_ols_through_origin_r2_is_centered_and_can_be_negative():
    # y sits near 5 and x is balanced around 0, so a line through the origin
    # explains less than the mean of y does: centered R^2 < 0.
    x = np.array([1.0, -1.0, 1.0, -1.0])
    y = np.array([5.0, 5.2, 4.8, 5.0])
    fit = ols_through_origin(x, y)
    assert fit.r2 < 0.0
