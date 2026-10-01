"""Tests for the execution-cost replay simulator.

Contract under test:
1. `replay_day` builds a `ReplayData` from events + bookTicker: event ts,
   signs, qtys, prior-mids, half-spreads (asof from bt, "strictly before"
   convention matching `events_with_prior_mid`), and typical_event_qty
   (median qty).
2. `simulate_schedule` costs each child at
   (mid_at_child - arrival_mid)*side + half_spread_at_child + temp_impact(q),
   temp_impact(q) = G[1] * (q / typical_event_qty) (linear scaling of the
   lag-1 kernel value; see the sqrt-law caveat in the simulator docstring).
   shortfall_per_unit = sum(cost_i * q_i) / sum(q_i). Verified by hand for a
   2-child case (exact equality, see below).
3. Schedule generators are pure and satisfy invariants: child sizes sum to
   the parent qty, indices lie in [0, horizon_events), indices non-decreasing
   (children never reordered).
4. Planted-advantage test: a replay where a burst of sell flow precedes a
   price drop right after each TWAP slot (and buy bursts precede price jumps)
   -> a buyer that defers behind opposing flow lands after the drop and comes
   out ahead of TWAP. The same prices with the signs shuffled carry no signal:
   there the reactive schedule has no systematic edge over TWAP and loses to
   reactive-with-signal.

Hand-computed 2-child shortfall (exact equality):
    side=+1, typical_event_qty=10, G=[0.0, 2.0], arrival_mid=100.0
    child 1: q=10 (1x typical) @ mid=100.0, half_spread=0.5
        cost = (100.0-100.0)*1 + 0.5 + 2.0*(10/10) = 0.0 + 0.5 + 2.0 = 2.5
    child 2: q=20 (2x typical) @ mid=101.0, half_spread=0.3
        cost = (101.0-100.0)*1 + 0.3 + 2.0*(20/10) = 1.0 + 0.3 + 4.0 = 5.3
    shortfall_per_unit = (2.5*10 + 5.3*20) / (10+20) = (25 + 106) / 30
                        = 131/30 = 4.366666...
"""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from microstructure.data.catalog import parquet_path
from microstructure.execution.simulator import (
    ReplayData,
    ScheduleResult,
    frontloaded_schedule,
    kernel_half_life_lag,
    reactive_schedule,
    replay_day,
    simulate_schedule,
    twap_schedule,
)

FRACTION_TOLERANCE = 1e-9


# --------------------------------------------------------------------------
# replay_day
# --------------------------------------------------------------------------


def _write_day_parquets(root: Path, symbol: str, month: str, day: str) -> None:
    """5 aggTrades prints -> 3 aggressor events, plus matching bookTicker quotes."""
    t0 = datetime(2023, 6, 1, 0, 0, 0, tzinfo=UTC)
    raw = pl.DataFrame(
        {
            "agg_trade_id": [1, 2, 3, 4, 5],
            "price": [100.0, 100.0, 100.5, 100.5, 101.0],
            "qty": [1.0, 1.0, 2.0, 1.0, 3.0],
            "first_trade_id": [1, 2, 3, 4, 5],
            "last_trade_id": [1, 2, 3, 4, 5],
            "ts": [
                t0,
                t0,
                t0 + timedelta(milliseconds=10),
                t0 + timedelta(milliseconds=10),
                t0 + timedelta(milliseconds=20),
            ],
            # buyer-taker (+1): rows 0,1 -> merge to sign +1 qty=2 @ ts=t0
            # buyer-taker (+1): rows 2,3 -> merge to sign +1 qty=3 @ ts=t0+10
            # seller-taker (-1): row 4 -> sign -1 qty=3 @ ts=t0+20
            "is_buyer_maker": [False, False, False, False, True],
        },
        schema_overrides={"ts": pl.Datetime("ms", "UTC")},
    )
    agg_path = parquet_path(root, symbol, "aggTrades", month)
    agg_path.parent.mkdir(parents=True, exist_ok=True)
    raw.write_parquet(agg_path)

    bt = pl.DataFrame(
        {
            "update_id": [1, 2, 3],
            "bid_price": [99.9, 100.4, 100.8],
            "bid_qty": [1.0, 1.0, 1.0],
            "ask_price": [100.1, 100.6, 101.2],
            "ask_qty": [1.0, 1.0, 1.0],
            "ts": [
                t0 - timedelta(milliseconds=1),
                t0 + timedelta(milliseconds=9),
                t0 + timedelta(milliseconds=19),
            ],
        },
        schema_overrides={"ts": pl.Datetime("ms", "UTC")},
    )
    bt_path = parquet_path(root, symbol, "bookTicker", day)
    bt_path.parent.mkdir(parents=True, exist_ok=True)
    bt.write_parquet(bt_path)


def test_replay_day_builds_expected_arrays(tmp_path: Path):
    symbol = "TESTUSDT"
    _write_day_parquets(tmp_path, symbol, "2023-06", "2023-06-01")

    from microstructure.signals.load import load_book_ticker, load_events

    events = load_events(tmp_path, symbol, ["2023-06"])
    bt = load_book_ticker(tmp_path, symbol, ["2023-06-01"])

    rd = replay_day(events, bt)

    assert isinstance(rd, ReplayData)
    assert rd.signs.tolist() == [1, 1, -1]
    assert rd.qtys.tolist() == [2.0, 3.0, 3.0]
    # prior mids: event 0 -> bt row 0 mid=(99.9+100.1)/2=100.0
    #             event 1 -> bt row 1 mid=(100.4+100.6)/2=100.5
    #             event 2 -> bt row 2 mid=(100.8+101.2)/2=101.0
    np.testing.assert_allclose(rd.prior_mids, [100.0, 100.5, 101.0])
    # half-spreads: (ask-bid)/2 = 0.1, 0.1, 0.2
    np.testing.assert_allclose(rd.half_spreads, [0.1, 0.1, 0.2])
    # typical_event_qty = median([2.0, 3.0, 3.0]) = 3.0
    assert rd.typical_event_qty == pytest.approx(3.0)
    assert rd.ts.dtype == np.int64


def test_replay_day_frozen_dataclass_is_immutable(tmp_path: Path):
    symbol = "TESTUSDT"
    _write_day_parquets(tmp_path, symbol, "2023-06", "2023-06-01")
    from microstructure.signals.load import load_book_ticker, load_events

    events = load_events(tmp_path, symbol, ["2023-06"])
    bt = load_book_ticker(tmp_path, symbol, ["2023-06-01"])
    rd = replay_day(events, bt)

    with pytest.raises(Exception):  # noqa: B017 - dataclass(frozen=True) raises FrozenInstanceError
        rd.typical_event_qty = 99.0


# --------------------------------------------------------------------------
# simulate_schedule: hand-verified exact arithmetic
# --------------------------------------------------------------------------


def _tiny_replay(n: int = 5) -> ReplayData:
    """5-event replay: prior_mids rise by 1.0 per event, half_spread alternates."""
    return ReplayData(
        ts=np.arange(n, dtype=np.int64) * 10,
        signs=np.array([1, 1, -1, 1, -1][:n], dtype=np.int8),
        qtys=np.full(n, 10.0),
        prior_mids=100.0 + np.arange(n, dtype=np.float64),
        half_spreads=np.array([0.5, 0.3, 0.5, 0.3, 0.5][:n]),
        typical_event_qty=10.0,
    )


def test_simulate_schedule_two_child_exact_shortfall():
    rd = _tiny_replay(n=5)
    kernel_g = np.array([0.0, 2.0, 2.0, 2.0])  # G[1] = 2.0

    # Parent = 3.0 typical-event-units = 30 units total (typical_event_qty=10).
    # Two children as fractions of the parent: 1/3 (-> 10 units) at event
    # index 0 (mid=100.0, half_spread=0.5), 2/3 (-> 20 units) at event index 1
    # (mid=101.0, half_spread=0.3).
    child_times = np.array([0, 1])
    child_sizes = np.array([1.0 / 3.0, 2.0 / 3.0])

    result = simulate_schedule(
        rd, side=1, parent_qty_events=3.0, horizon_events=5,
        child_times=child_times, child_sizes=child_sizes, kernel_g=kernel_g,
        schedule_name="hand_check",
    )

    assert isinstance(result, ScheduleResult)
    expected = 131.0 / 30.0
    assert result.shortfall_per_unit == pytest.approx(expected, abs=1e-6)
    assert result.n_children == 2
    assert result.filled is True
    assert result.schedule_name == "hand_check"


def test_simulate_schedule_sell_side_flips_sign_of_drift_and_impact():
    """side=-1: only the drift term flips sign vs. the side=+1 hand-check.

    The spread and the impact stay costs for a seller too."""
    rd = _tiny_replay(n=5)
    kernel_g = np.array([0.0, 2.0, 2.0, 2.0])

    child_times = np.array([0, 1])
    child_sizes = np.array([1.0 / 3.0, 2.0 / 3.0])

    result = simulate_schedule(
        rd, side=-1, parent_qty_events=3.0, horizon_events=5,
        child_times=child_times, child_sizes=child_sizes, kernel_g=kernel_g,
        schedule_name="sell_check",
    )
    # child 1: (100-100)*-1 + 0.5 + 2.0*(10/10) = 0.0 + 0.5 + 2.0 = 2.5
    #   (drift is zero here regardless of side; impact always costs the trader)
    # child 2: (101-100)*-1 + 0.3 + 2.0*(20/10) = -1.0 + 0.3 + 4.0 = 3.3
    expected = (2.5 * 10 + 3.3 * 20) / 30.0
    assert result.shortfall_per_unit == pytest.approx(expected, abs=1e-6)


# --------------------------------------------------------------------------
# kernel_half_life_lag
# --------------------------------------------------------------------------


def test_kernel_half_life_lag_finds_post_peak_half_decay():
    # peak=10.0 at lag 3; decays to <=5.0 at lag 6 -> half-life = 6
    g = np.array([0.0, 4.0, 8.0, 10.0, 9.0, 6.0, 4.0, 2.0])
    assert kernel_half_life_lag(g) == 6


def test_kernel_half_life_lag_falls_back_when_monotone_increasing():
    # never decays within recorded lags -> defensive fallback: len // 4
    g = np.arange(20, dtype=np.float64)
    assert kernel_half_life_lag(g) == 5


# --------------------------------------------------------------------------
# Schedule generator invariants
# --------------------------------------------------------------------------


@pytest.mark.parametrize("horizon,n_children", [(2000, 20), (100, 5)])
def test_twap_schedule_invariants(horizon, n_children):
    times, sizes = twap_schedule(horizon, n_children)
    assert len(times) == n_children
    assert len(sizes) == n_children
    assert np.all(times >= 0) and np.all(times < horizon)
    assert np.all(np.diff(times) >= 0)  # monotone non-decreasing
    assert np.all(sizes >= 0)
    # sizes are fractions of the parent order, summing to 1.0
    assert sizes.sum() == pytest.approx(1.0)


@pytest.mark.parametrize("decay", [0.1, 0.5, 2.0])
def test_frontloaded_schedule_invariants(decay):
    horizon, n_children = 2000, 20
    times, sizes = frontloaded_schedule(horizon, n_children, decay=decay)
    assert len(times) == n_children
    assert len(sizes) == n_children
    assert np.all(times >= 0) and np.all(times < horizon)
    assert np.all(np.diff(times) >= 0)
    assert np.all(sizes >= 0)
    assert sizes.sum() == pytest.approx(1.0)


def test_frontloaded_schedule_puts_more_size_early():
    horizon, n_children = 2000, 20
    _times, sizes = frontloaded_schedule(horizon, n_children, decay=1.0)
    first_half = sizes[: n_children // 2].sum()
    second_half = sizes[n_children // 2 :].sum()
    assert first_half > second_half


def test_reactive_schedule_invariants():
    rd = _make_flow_replay(n_events=2200, seed=1)
    times, sizes, n_deferrals = reactive_schedule(
        rd, side=1, horizon_events=2000, n_children=20, lookback=50, pause_threshold=0.2
    )
    assert len(times) == 20
    assert len(sizes) == 20
    assert np.all(times >= 0) and np.all(times < 2000)
    assert np.all(np.diff(times) >= 0)
    assert n_deferrals >= 0
    # all must fill by horizon end -> last child forced at/near horizon-1 at worst
    assert times[-1] <= 1999
    assert sizes.sum() == pytest.approx(1.0)


def _make_flow_replay(n_events: int, seed: int) -> ReplayData:
    """I.i.d. random-sign replay with flat mids and spreads."""
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1, 1], dtype=np.int8), size=n_events)
    return ReplayData(
        ts=np.arange(n_events, dtype=np.int64) * 10,
        signs=signs,
        qtys=np.full(n_events, 10.0),
        prior_mids=np.full(n_events, 100.0),
        half_spreads=np.full(n_events, 0.05),
        typical_event_qty=10.0,
    )


# --------------------------------------------------------------------------
# Planted-advantage test, with a shuffled-signs control
# --------------------------------------------------------------------------

HORIZON = 2000
N_CHILDREN = 20
LOOKBACK = 50
PAUSE_THRESHOLD = 0.2
PLANTED_STEP = 0.5
N_SEEDS = 30


def _planted_replay(seed: int) -> ReplayData:
    """Noisy mids with flow that leads price after each TWAP slot.

    Before every TWAP slot t_k (k >= 1) a 30-event burst of one sign d_k fills
    events [t_k-40, t_k-10). The mid steps by PLANTED_STEP * d_k at t_k + 20, so
    a TWAP child at t_k trades before the step. Directions d_k are random, so
    there is no net drift. A buyer that defers behind a sell burst (d_k = -1)
    lands after the price drop, which is favorable for a buyer. After a buy
    burst the reactive schedule does not defer, so it matches TWAP.
    """
    rng = np.random.default_rng(seed)
    n_events = HORIZON + 200
    signs = rng.choice(np.array([-1, 1], dtype=np.int8), size=n_events)
    mids = 100.0 + np.cumsum(rng.normal(0.0, 0.01, size=n_events))
    twap_times, _ = twap_schedule(HORIZON, N_CHILDREN)
    for t in twap_times[1:]:
        direction = int(rng.choice([-1, 1]))
        signs[t - 40 : t - 10] = direction
        mids[t + 20 :] += PLANTED_STEP * direction
    return ReplayData(
        ts=np.arange(n_events, dtype=np.int64) * 10,
        signs=signs,
        qtys=np.full(n_events, 10.0),
        prior_mids=mids,
        half_spreads=np.full(n_events, 0.05),
        typical_event_qty=10.0,
    )


def _shuffled_signs(rd: ReplayData, seed: int) -> ReplayData:
    """Same prices, signs permuted: flow no longer leads price."""
    rng = np.random.default_rng(10_000 + seed)
    return replace(rd, signs=rng.permutation(rd.signs))


def _buyer_shortfalls(rd: ReplayData) -> tuple[float, float]:
    """(TWAP, reactive) buy-side shortfall on one replay."""
    kernel_g = np.array([0.0] + [0.001] * 50)  # tiny impact so drift dominates
    kwargs = {
        "side": 1, "parent_qty_events": N_CHILDREN * 1.0, "horizon_events": HORIZON,
        "kernel_g": kernel_g,
    }
    t_times, t_sizes = twap_schedule(HORIZON, N_CHILDREN)
    twap = simulate_schedule(rd, child_times=t_times, child_sizes=t_sizes, **kwargs)
    r_times, r_sizes, _ = reactive_schedule(
        rd, side=1, horizon_events=HORIZON, n_children=N_CHILDREN,
        lookback=LOOKBACK, pause_threshold=PAUSE_THRESHOLD,
    )
    reactive = simulate_schedule(rd, child_times=r_times, child_sizes=r_sizes, **kwargs)
    return twap.shortfall_per_unit, reactive.shortfall_per_unit


def _paired_advantage(replays: list[ReplayData]) -> np.ndarray:
    """TWAP minus reactive shortfall per replay; positive means reactive is cheaper."""
    pairs = np.array([_buyer_shortfalls(rd) for rd in replays])
    return pairs[:, 0] - pairs[:, 1]


def test_reactive_schedule_beats_twap_when_flow_leads_price():
    replays = [_planted_replay(seed) for seed in range(N_SEEDS)]
    advantage = _paired_advantage(replays)
    # About half the slots follow a sell burst and gain PLANTED_STEP; ~0.2 expected.
    assert advantage.mean() > 0.1, advantage.mean()
    assert np.mean(advantage > 0) > 0.9


def test_reactive_with_signal_beats_reactive_with_shuffled_signs():
    replays = [_planted_replay(seed) for seed in range(N_SEEDS)]
    shuffled = [_shuffled_signs(rd, seed) for seed, rd in enumerate(replays)]
    reactive_signal = np.array([_buyer_shortfalls(rd)[1] for rd in replays])
    reactive_shuffled = np.array([_buyer_shortfalls(rd)[1] for rd in shuffled])
    assert (reactive_shuffled - reactive_signal).mean() > 0.1


def test_reactive_has_no_systematic_edge_over_twap_when_signs_are_shuffled():
    """Control: prices as planted, but flow independent of them. The mean paired
    advantage must be statistically indistinguishable from zero and a small
    fraction of the planted advantage."""
    replays = [_planted_replay(seed) for seed in range(N_SEEDS)]
    planted = _paired_advantage(replays).mean()
    shuffled = [_shuffled_signs(rd, seed) for seed, rd in enumerate(replays)]
    advantage = _paired_advantage(shuffled)
    standard_error = advantage.std(ddof=1) / np.sqrt(advantage.size)
    assert abs(advantage.mean()) < 3 * standard_error, (advantage.mean(), standard_error)
    assert abs(advantage.mean()) < 0.25 * planted


# --------------------------------------------------------------------------
# reactive_schedule: pause/defer behavior in isolation
# --------------------------------------------------------------------------


def test_reactive_schedule_defers_on_opposing_flow():
    """Construct a replay where the lookback window immediately before the
    SECOND TWAP slot has strongly opposing flow (all -1 signs against a +1
    parent) -> that child slot must be deferred later than its TWAP
    counterpart. (Slot 0's lookback window is empty -- there is nothing
    before event index 0 -- so it can never trigger a deferral; slot 1, at
    t=100 for this horizon/n_children grid, has a full lookback window and
    is the one this test targets.)"""
    horizon, n_children, lookback = 2000, 20, 50
    n = horizon + 100
    signs = np.ones(n, dtype=np.int8)
    twap_times, _ = twap_schedule(horizon, n_children)
    slot1 = int(twap_times[1])
    signs[slot1 - lookback : slot1] = -1  # opposing flow right before slot 1
    rd = ReplayData(
        ts=np.arange(n, dtype=np.int64) * 10,
        signs=signs,
        qtys=np.full(n, 10.0),
        prior_mids=np.full(n, 100.0),
        half_spreads=np.full(n, 0.05),
        typical_event_qty=10.0,
    )
    r_times, _r_sizes, n_deferrals = reactive_schedule(
        rd, side=1, horizon_events=horizon, n_children=n_children,
        lookback=lookback, pause_threshold=0.5,
    )
    assert n_deferrals >= 1
    assert r_times[1] > twap_times[1]
    assert np.all(r_times < horizon)
    assert np.all(np.diff(r_times) >= 0)


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------


def _call_sim(**overrides):
    rd = _tiny_replay(n=5)
    args = {
        "rd": rd, "side": 1, "parent_qty_events": 3.0, "horizon_events": 5,
        "child_times": np.array([0, 1]), "child_sizes": np.array([0.5, 0.5]),
        "kernel_g": np.array([0.0, 2.0, 2.0]),
    }
    args.update(overrides)
    return simulate_schedule(**args)


@pytest.mark.parametrize("side", [0, 2, -3])
def test_simulate_schedule_rejects_side_other_than_plus_minus_one(side):
    with pytest.raises(ValueError, match="side"):
        _call_sim(side=side)


def test_simulate_schedule_rejects_negative_child_times():
    with pytest.raises(ValueError, match="child_times"):
        _call_sim(child_times=np.array([-1, 1]))


def test_simulate_schedule_rejects_mismatched_child_sizes():
    with pytest.raises(ValueError, match="child_sizes"):
        _call_sim(child_sizes=np.array([1.0]))


def test_simulate_schedule_rejects_negative_lag_one_kernel():
    with pytest.raises(ValueError, match="G\\[1\\]"):
        _call_sim(kernel_g=np.array([0.0, -0.5, 1.0]))


@pytest.mark.parametrize("n_children", [0, -1])
def test_twap_schedule_rejects_non_positive_n_children(n_children):
    with pytest.raises(ValueError, match="n_children"):
        twap_schedule(100, n_children)


def test_twap_schedule_rejects_non_positive_horizon():
    with pytest.raises(ValueError, match="horizon_events"):
        twap_schedule(0, 5)
