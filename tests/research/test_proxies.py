"""Synthetic streams with known answers for every proxy in evolution.proxies."""
from datetime import UTC, datetime

import numpy as np
import polars as pl
import pytest

from microstructure.data.events import to_aggressor_events
from microstructure.evolution.proxies import (
    NEAR_CIRCULAR,
    PROXY_DOCS,
    burstiness,
    contract_month_proxies,
    detect_lot,
    is_round,
    near_circular,
    relative_tick,
    run_lengths,
    sign_runs,
    size_clustering,
    trade_size,
)

T0 = int(datetime(2023, 6, 1, tzinfo=UTC).timestamp() * 1000)
DAY = 86_400_000


def _events(ts_ms, sign, qty=None, price=None, n_prints=None) -> pl.DataFrame:
    n = len(ts_ms)
    return pl.DataFrame({
        "ts": pl.Series(np.asarray(ts_ms, dtype=np.int64)).cast(pl.Datetime("ms", "UTC")),
        "sign": pl.Series(np.asarray(sign), dtype=pl.Int8),
        "qty": np.ones(n) if qty is None else np.asarray(qty, dtype=float),
        "price": np.full(n, 100.0) if price is None else np.asarray(price, dtype=float),
        "n_prints": pl.Series(np.ones(n, dtype=np.uint32) if n_prints is None
                              else np.asarray(n_prints, dtype=np.uint32)),
    })


def _random_raw(t0: int, days: int, n: int, seed: int) -> pl.DataFrame:
    """Raw aggTrades-like records on a 0.01 price grid and a 0.001 qty grid."""
    rng = np.random.default_rng(seed)
    ts = np.sort(t0 + rng.integers(0, days * DAY, size=n))
    ts[1::7] = ts[0::7][: ts[1::7].size]  # some same-ms prints
    ts = np.sort(ts)
    price = np.round(100 + 0.01 * np.cumsum(rng.integers(-2, 3, size=n)), 2)
    first = np.arange(n) * 3
    return pl.DataFrame({
        "agg_trade_id": np.arange(n),
        "price": price,
        "qty": rng.integers(1, 2000, size=n) * 0.001,
        "first_trade_id": first,
        "last_trade_id": first + rng.integers(0, 3, size=n),
        "ts": pl.Series(ts).cast(pl.Datetime("ms", "UTC")),
        "is_buyer_maker": rng.random(n) < 0.5,
    })


# ---------------------------------------------------------------- sign runs

def test_run_lengths_basic():
    assert run_lengths(np.array([1, 1, -1, 1, 1, 1])).tolist() == [2, 1, 3]
    assert run_lengths(np.array([])).tolist() == []


def test_sign_runs_planted_runs_and_sweeps():
    # run A: +1 x3, 100 ms apart; run B: -1 x12 as 4 sweeps of 3 (1 ms inside, 100 ms
    # between); run C: +1 x10, all 1 ms apart (one sweep).
    gaps, sign = [], []
    gaps += [100] * 3
    sign += [1] * 3
    for _ in range(4):
        gaps += [100, 1, 1]
        sign += [-1] * 3
    gaps += [100] + [1] * 9
    sign += [1] * 10
    ts = T0 + np.cumsum(gaps)
    r = sign_runs(_events(ts, sign))
    assert r["run_mean"] == pytest.approx(25 / 3)
    assert r["run_share_ge10"] == pytest.approx(2 / 3)
    assert r["run_mean_sweeps_merged"] == pytest.approx((3 + 4 + 1) / 3)
    assert r["run_share_ge10_sweeps_merged"] == 0.0
    assert r["sweep_share"] == pytest.approx((8 + 9) / 24)


def test_sweep_needs_same_sign():
    ts = T0 + np.arange(6)  # all 1 ms apart, alternating signs: no sweeps
    r = sign_runs(_events(ts, [1, -1] * 3))
    assert r["sweep_share"] == 0.0
    assert r["run_mean"] == r["run_mean_sweeps_merged"] == 1.0


# ---------------------------------------------------------------- sizes

@pytest.mark.parametrize("lot", [0.001, 0.1, 1.0, 10.0])
def test_detect_lot_from_qty_grid(lot):
    rng = np.random.default_rng(0)
    assert detect_lot(rng.integers(1, 3000, size=5000) * lot) == pytest.approx(lot)


def test_equal_size_repeats_planted():
    lot = 0.001
    n = np.array([5, 5, 7, 3, 3, 3])
    sign = [1, 1, 1, -1, -1, 1]
    # same-sign pairs: (0,1) equal, (1,2) not, (3,4) equal -> 2/3
    r = size_clustering(_events(T0 + np.arange(6) * 10, sign, qty=n * lot), lot=lot)
    assert r["equal_size_repeat_share"] == pytest.approx(2 / 3)


def test_round_sizes_relative_to_lot():
    n = np.array([10, 20, 100, 150, 7, 1000, 1200, 30])
    assert is_round(n).tolist() == [True, True, True, False, False, True, False, True]
    for lot in (0.001, 1.0):
        r = size_clustering(_events(T0 + np.arange(8) * 10, [1] * 8, qty=n * lot), lot=lot)
        assert r["round_size_share"] == pytest.approx(5 / 8)
        assert r["round10_share"] == pytest.approx(7 / 8)


def test_size_clustering_detects_lot_itself():
    rng = np.random.default_rng(1)
    n = rng.integers(1, 500, size=3000)
    n[:2] = [40, 40]  # one planted equal pair among random sizes
    ev = _events(T0 + np.arange(n.size) * 10, np.ones(n.size, dtype=int), qty=n * 0.001)
    r = size_clustering(ev)
    assert r["lot"] == pytest.approx(0.001)
    assert r["equal_size_repeat_share"] == pytest.approx(np.mean(n[1:] == n[:-1]))


# ---------------------------------------------------------------- burstiness

@pytest.mark.parametrize("k", [0, 3, 10])
def test_burstiness_planted_minute_bursts(k):
    # one event at ms 500 of every second for one hour, plus k events at ms 0..k-1 of
    # second 0 of every minute
    base = T0 + np.arange(3600) * 1000 + 500
    burst = (T0 + np.arange(60)[:, None] * 60_000 + np.arange(k)[None, :]).ravel()
    ts = np.sort(np.r_[base, burst])
    n = ts.size
    r = burstiness(_events(ts, np.ones(n, dtype=int)))
    assert r["minute_open_ratio"] == pytest.approx((60 + 60 * k) / n * 60)
    assert r["quarter_open_ratio"] == pytest.approx((4 + 4 * k) / n * 900)
    assert r["share_gap_le_1ms"] == pytest.approx(60 * max(k - 1, 0) / (n - 1))
    m = 1 + k / 60
    var = k**2 * (1 / 60) * (59 / 60)
    assert r["fano_1s"] == pytest.approx(var / m)


def test_uniform_stream_has_ratio_one():
    ts = T0 + np.arange(900 * 4) * 1000  # one event per second, one hour
    r = burstiness(_events(ts, np.ones(ts.size, dtype=int)))
    assert r["minute_open_ratio"] == pytest.approx(1.0)
    assert r["quarter_open_ratio"] == pytest.approx(1.0)
    assert r["fano_1s"] == 0.0


# ---------------------------------------------------------------- trade size

def test_trade_size_known_notional():
    notional = np.array([500, 900, 1500, 2000, 10_000.0])
    price = np.array([10, 30, 50, 100, 1000.0])
    r = trade_size(_events(T0 + np.arange(5), [1] * 5, qty=notional / price, price=price))
    assert r["median_notional_usd"] == pytest.approx(1500)
    assert r["share_under_1k_usd"] == pytest.approx(0.4)


# ---------------------------------------------------------------- tick

def _grid_days(t0, ticks, mid=150.0, seed=0):
    """201 events per day at prices mid + k * tick_day, k a permutation of -100..100."""
    rng = np.random.default_rng(seed)
    ts, price = [], []
    for d, tick in enumerate(ticks):
        ts.append(t0 + d * DAY + np.sort(rng.integers(0, DAY, size=201)))
        price.append(mid + rng.permutation(np.arange(-100, 101)) * tick)
    return np.concatenate(ts), np.concatenate(price)


def test_relative_tick_constant():
    ts, price = _grid_days(T0, [0.001] * 30)
    r = relative_tick(_events(ts, np.ones(ts.size, dtype=int), price=price))
    assert r["tick"] == pytest.approx(0.001)
    assert r["tick_changes"] == 0
    assert r["rel_tick_bps"] == pytest.approx(0.001 / 150 * 1e4)


def test_relative_tick_mid_month_change():
    t0 = int(datetime(2024, 10, 1, tzinfo=UTC).timestamp() * 1000)
    ts, price = _grid_days(t0, [0.001] * 13 + [0.01] * 18)
    r = relative_tick(_events(ts, np.ones(ts.size, dtype=int), price=price))
    assert r["tick_changes"] == 1
    assert r["tick"] == pytest.approx(0.01)
    expected = (13 * 0.001 + 18 * 0.01) / 31 / 150 * 1e4
    assert r["rel_tick_bps"] == pytest.approx(expected)


def test_tick_ignores_vwap_of_merged_prints():
    ts, price = _grid_days(T0, [0.01] * 5)
    n_prints = np.ones(ts.size, dtype=int)
    n_prints[::3] = 2
    price = price.copy()
    price[::3] += 0.01 / 3  # VWAP of two prints lies off the grid
    r = relative_tick(_events(ts, np.ones(ts.size, dtype=int), price=price, n_prints=n_prints))
    assert r["tick"] == pytest.approx(0.01)
    assert r["tick_changes"] == 0


def test_unchanged_price_share_uses_raw_in_id_order():
    raw = pl.DataFrame({
        "agg_trade_id": [5, 0, 3, 1, 4, 2],
        "price": [3.0, 1.0, 2.0, 1.0, 2.0, 2.0],  # id order: 1 1 2 2 2 3
        "ts": pl.Series(T0 + np.array([5, 0, 3, 1, 4, 2])).cast(pl.Datetime("ms", "UTC")),
    })
    ev = _events(T0 + np.arange(6), [1] * 6, price=[1, 2, 3, 4, 5, 6.0])
    assert relative_tick(ev, raw)["unchanged_price_share"] == pytest.approx(3 / 5)
    assert relative_tick(ev)["unchanged_price_share"] == 0.0


# ---------------------------------------------------------------- near-circular

def test_near_circular_known_values_and_labels():
    s = np.array([1, 1, 1, 1, -1, -1, -1, -1])
    r = near_circular(_events(T0 + np.arange(8), s))
    assert r["sign_repeat_rate"] == pytest.approx(6 / 7)
    assert r["sign_acf_lag1"] == pytest.approx(np.corrcoef(s[1:], s[:-1])[0, 1])
    for k in NEAR_CIRCULAR:
        assert PROXY_DOCS[k]["status"] == "descriptive, near-circular"
        assert "near-circular" in PROXY_DOCS[k]["mechanism"]


# ---------------------------------------------------------------- full month

def test_contract_month_proxies_end_to_end_and_documented():
    raw = _random_raw(T0, 30, 20_000, seed=2)
    ev = to_aggressor_events(raw)
    out = contract_month_proxies(ev, raw)
    assert out["month"] == "2023-06"
    assert out["prints_per_event"] == pytest.approx(raw.height / ev.height)
    assert out["fills_per_record"] == pytest.approx(
        (raw["last_trade_id"] - raw["first_trade_id"] + 1).mean())
    assert out["tick"] == pytest.approx(0.01)
    assert out["lot"] == pytest.approx(0.001)
    bookkeeping = {"month", "n_events", "days", "events_per_day"}
    for k, v in out.items():
        if k in bookkeeping:
            continue
        assert k in PROXY_DOCS, k
        assert {"definition", "units", "mechanism"} <= PROXY_DOCS[k].keys()
        assert np.isfinite(v), k


def test_proxies_depend_only_on_the_month_given():
    june = _random_raw(T0, 30, 8_000, seed=3)
    t_jul = int(datetime(2023, 7, 1, tzinfo=UTC).timestamp() * 1000)
    july = _random_raw(t_jul, 31, 8_000, seed=4).with_columns(pl.col("agg_trade_id") + 8_000)
    alone = contract_month_proxies(to_aggressor_events(june), june)

    both = pl.concat([june, july])
    with pytest.raises(ValueError, match="one calendar month"):
        contract_month_proxies(to_aggressor_events(both), both)

    # June cut back out of a two-month stream, with July scrambled: identical answer
    july2 = july.with_columns(pl.col("price") * 3, pl.col("qty") * 7)
    for other in (july, july2):
        sliced = pl.concat([june, other]).filter(pl.col("ts").dt.month() == 6)
        assert contract_month_proxies(to_aggressor_events(sliced), sliced) == alone

    # a truncated month gives proxies of the truncated data, not of the full month
    half = june.filter(pl.col("ts").dt.day() <= 15)
    out_half = contract_month_proxies(to_aggressor_events(half), half)
    assert out_half["days"] == 15
    assert out_half["n_events"] < alone["n_events"]

    with pytest.raises(ValueError, match="different months"):
        contract_month_proxies(to_aggressor_events(june), july)
