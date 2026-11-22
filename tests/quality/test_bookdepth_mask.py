from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from microstructure.quality import bookdepth as bd

DAY0 = int(dt.datetime(2024, 1, 10, tzinfo=dt.UTC).timestamp())


def _csv(ts: np.ndarray, depth: np.ndarray, notional: np.ndarray, float_bands: bool = False,
         header: bool = True, extra: list[str] | None = None) -> bytes:
    lines = ["timestamp,percentage,depth,notional"] if header else []
    for i, t in enumerate(ts):
        stamp = dt.datetime.fromtimestamp(int(t), dt.UTC).strftime("%Y-%m-%d %H:%M:%S")
        for j, p in enumerate(bd.CORE):
            pct = f"{p:.2f}" if float_bands else f"{int(p)}"
            lines.append(f"{stamp},{pct},{depth[i, j]:.8f},{notional[i, j]:.8f}")
    lines += extra or []
    return ("\n".join(lines) + "\n").encode()


def _book(n: int, mid: float = 100.0, seed: int = 0, t0: int = DAY0):
    """n clean snapshots 30 s apart: cumulative depth growing outward, VWAPs on the right
    side of mid, values jittered so no two snapshots repeat."""
    rng = np.random.default_rng(seed)
    ts = t0 + 30 * np.arange(n, dtype=np.int64) + 5
    steps = np.abs(np.array([5, 4, 3, 2, 1, 1, 2, 3, 4, 5], float))
    depth = np.empty((n, 10))
    notional = np.empty((n, 10))
    for i in range(n):
        base = 10 + rng.random(10)
        cum_bid = np.cumsum(base[:5])  # -1 .. -5
        cum_ask = np.cumsum(base[5:])
        depth[i, :5] = cum_bid[::-1]
        depth[i, 5:] = cum_ask
        vw = mid * (1 + np.sign(np.array(bd.CORE)) * steps / 200)
        notional[i] = depth[i] * vw
    return ts, depth, notional


def _klines(t0: int, n_min: int, mid: float = 100.0) -> bd.Klines:
    o = t0 + 60 * np.arange(n_min, dtype=np.int64)
    z = np.full(n_min, mid)
    return bd.Klines(o, z * 0.999, z * 1.001, z, np.full(n_min, 5.0), np.full(n_min, 10.0))


def _mask(ts, depth, notional, kl=None, symbol="TESTUSDT", **kw) -> bd.SymbolMask:
    book = bd.parse_bookdepth_csv(_csv(ts, depth, notional))
    kl = kl or _klines(DAY0, 1440 * 2)
    return bd.SymbolMask.from_days(symbol, [bd.day_features(book, kl, None)], **kw)


# ------------------------------------------------------------------------- parsing

def test_parse_int_and_float_bands_agree_and_drop_02_bands():
    ts, d, n = _book(5)
    a = bd.parse_bookdepth_csv(_csv(ts, d, n))
    b = bd.parse_bookdepth_csv(_csv(ts, d, n, float_bands=True, header=False,
                                    extra=["2024-01-10 00:00:05,-0.20,1.0,100.0"]))
    assert np.array_equal(a.ts, b.ts)
    assert np.allclose(a.depth, b.depth)
    assert not a.conflict.any() and not b.conflict.any()


def test_parse_conflicting_duplicate_marks_s0_identical_duplicate_does_not():
    ts, d, n = _book(3)
    stamp = "2024-01-10 00:00:35"
    raw = _csv(ts, d, n, extra=[f"{stamp},-1,{d[1, 4]:.8f},{n[1, 4]:.8f}"])
    assert not bd.parse_bookdepth_csv(raw).conflict.any()
    raw = _csv(ts, d, n, extra=[f"{stamp},-1,{d[1, 4] + 1:.8f},{n[1, 4]:.8f}"])
    book = bd.parse_bookdepth_csv(raw)
    assert book.conflict.tolist() == [False, True, False]
    m = bd.SymbolMask.from_days("X", [bd.day_features(book, _klines(DAY0, 10), None)])
    assert m.flags["S0"].tolist() == [False, True, False]


# --------------------------------------------------------------- single-snapshot rules

def test_clean_book_has_no_flags():
    ts, d, n = _book(100)
    m = _mask(ts, d, n)
    assert not m.invalid.any()


def test_s0_missing_band_and_zero_depth():
    ts, d, n = _book(10)
    d[3, 2] = 0.0
    n[6, 7] = np.nan
    m = _mask(ts, d, n)
    assert np.flatnonzero(m.flags["S0"]).tolist() == [3, 6]


def test_s1_crossed_side_and_s6_buffer():
    ts, d, n = _book(100)
    # stale bid far above the market: inner bid VWAP 103 > inner ask VWAP ~100.5
    n[50, 4] = d[50, 4] * 103.0
    m = _mask(ts, d, n)
    assert np.flatnonzero(m.flags["S1"]).tolist() == [50]
    assert m.s1_side[50] == -1
    buf = np.flatnonzero(m.flags["S6"])
    assert buf.tolist() == list(range(30, 50)) + list(range(51, 71))
    assert m.invalid.sum() == 41


def test_s4_non_monotone():
    ts, d, n = _book(10)
    d[4, 0] = d[4, 1] - 1  # -5 band below -4 band
    d[7, 9] = d[7, 8] - 1  # +5 band below +4 band
    m = _mask(ts, d, n)
    assert np.flatnonzero(m.flags["S4"]).tolist() == [4, 7]


def test_s5_off_price_and_missing_kline():
    ts, d, n = _book(10)
    kl = _klines(DAY0, 1440)
    kl.low[0] = kl.high[0] = 200.0  # minute 0 trades at 200; book mid ~100 is off-price
    kl2 = bd.Klines(*(np.delete(a, 3) for a in (kl.open_s, kl.low, kl.high, kl.close,
                                                kl.taker_buy, kl.volume)))
    m = _mask(ts, d, n, kl=kl2)
    # snapshots 0, 1 sit in minute 0; snapshots 6, 7 in the missing minute 3
    assert np.flatnonzero(m.flags["S5"]).tolist() == [0, 1, 6, 7]
    assert np.flatnonzero(m.s5_nokline).tolist() == [6, 7]


# ------------------------------------------------------------------------ run rules

def test_true_runs_and_repeat_runs():
    x = np.array([0, 1, 1, 0, 1, 0, 0, 1], bool)
    assert bd.true_runs(x).tolist() == [[1, 2], [4, 4], [7, 7]]
    # same_as_prev True at 1,2 -> snapshots 0..2 identical (3); at 4 -> 3..4 (2)
    assert bd.repeat_runs(x, 3).tolist() == [[0, 2]]
    assert bd.repeat_runs(x, 2).tolist() == [[0, 2], [3, 4], [6, 7]]


def test_s2_needs_three_identical_snapshots():
    ts, d, n = _book(60)
    d[11], n[11] = d[10], n[10]  # pair only: not S2
    d[31] = d[32] = d[30]
    n[31] = n[32] = n[30]
    m = _mask(ts, d, n)
    assert np.flatnonzero(m.flags["S2"]).tolist() == [30, 31, 32]
    assert m.s2_runs.tolist() == [[30, 32]]


def test_s3_band_freeze_threshold_and_sensitivity():
    ts, d, n = _book(200)
    d[50:69, 4] = d[50, 4]  # 19 snapshots frozen in the -1 band: not S3 at 20
    d[100:120, 6] = d[100, 6]  # 20 snapshots frozen in +2: S3
    m = _mask(ts, d, n)
    assert np.flatnonzero(m.flags["S3"]).tolist() == list(range(100, 120))
    assert [(b, r.tolist()) for b, r in m.s3_runs] == [(6, [[100, 119]])]
    m10 = _mask(ts, d, n, s3_min_run=10)
    assert m10.flags["S3"][50:69].all()


def test_runs_continue_across_midnight():
    t1 = DAY0 + 86_400
    ts0, d0, n0 = _book(2880, seed=1)
    ts1, d1, n1 = _book(2880, seed=2, t0=t1)
    d0[-10:, 4] = d0[-10, 4]
    d1[:10, 4] = d0[-10, 4]  # 20 frozen snapshots split over two files
    n0[-10:, 4] = d0[-10:, 4] * 99.5  # keep the inner bid VWAP where it was
    n1[:10, 4] = d1[:10, 4] * 99.5
    kl0, kl1 = _klines(DAY0, 1440), _klines(t1, 1440)
    f0 = bd.day_features(bd.parse_bookdepth_csv(_csv(ts0, d0, n0)), kl0, None)
    f1 = bd.day_features(bd.parse_bookdepth_csv(_csv(ts1, d1, n1)), kl1, f0.last_depth)
    m = bd.SymbolMask.from_days("X", [f0, f1])
    assert m.flags["S3"].sum() == 20
    tab = m.day_table()
    assert tab.height == 2
    assert tab["n_S3"].to_list() == [10, 10]
    assert tab["n_S6"].to_list() == [20, 20]


def test_unordered_days_raise():
    ts0, d0, n0 = _book(5)
    f = bd.day_features(bd.parse_bookdepth_csv(_csv(ts0, d0, n0)), _klines(DAY0, 10), None)
    with pytest.raises(ValueError):
        bd.SymbolMask.from_days("X", [f, f])


# ------------------------------------------------------------------- day and window rules

def test_d1_valid_count_and_gap():
    ts, d, n = _book(2880)
    m = _mask(ts, d, n)
    row = m.day_table().row(0, named=True)
    assert row["n_valid_s"] == 2880 and row["d1_s"]
    keep = np.r_[0:1000, 1031:2880]  # 31 missing snapshots: 960 s gap
    m = _mask(ts[keep], d[keep], n[keep])
    row = m.day_table().row(0, named=True)
    assert row["max_gap_s"] == 960 and not row["d1_s"]
    keep = np.r_[0:2591]
    row = _mask(ts[keep], d[keep], n[keep]).day_table().row(0, named=True)
    assert row["n_valid_s"] == 2591 and not row["d1_s"]


def test_calendar_exclusion_counts_and_eth_extension():
    t = int(dt.datetime(2025, 11, 5, tzinfo=dt.UTC).timestamp())
    ts, d, n = _book(10, t0=t)
    kl = _klines(t, 20)
    eth = _mask(ts, d, n, kl=kl, symbol="ETHUSDT").day_table().row(0, named=True)
    btc = _mask(ts, d, n, kl=kl, symbol="BTCUSDT").day_table().row(0, named=True)
    assert eth["n_calendar"] == 10 and btc["n_calendar"] == 0
    assert eth["n_valid_sx"] == 0 and btc["n_valid_sx"] == 10


def test_intervals_cover_exactly_the_invalid_snapshots():
    ts, d, n = _book(300)
    n[50, 4] = d[50, 4] * 103.0
    d[200:225, 6] = d[200, 6]
    d[100, 2] = 0
    m = _mask(ts, d, n)
    iv = m.intervals()
    covered = np.zeros(ts.size, bool)
    for s, e in iv.select("start_ts", "end_ts").iter_rows():
        covered |= (m.ts >= s) & (m.ts <= e)
    assert np.array_equal(covered, m.invalid)
    # the zero -3 band is also below the -2 band, so S4 fires with S0
    assert set(iv["rule"]) == {"S0", "S1", "S3", "S4", "S6"}


def test_d2_window():
    grid = np.arange(0, 3600, 30)
    assert bd.d2_usable(grid, 0, 3600)
    holes = grid[(grid < 1000) | (grid > 1400)]  # 420 s hole
    assert not bd.d2_usable(holes, 0, 3600)
    assert bd.d2_usable(grid[::3], 0, 3600)  # 90 s apart: every point within 45 s
    sparse = grid[::5]  # 150 s apart: 2 of every 5 grid points uncovered
    assert not bd.d2_usable(sparse, 0, 3600)


def test_d3_drops_dates_over_20_percent():
    import polars as pl

    days = pl.DataFrame({"date": [1, 1, 1, 1, 1, 2, 2, 2, 2, 2],
                         "d1_s": [True, True, True, True, False,
                                  True, True, True, False, False]})
    out = bd.d3_dropped_dates(days)
    assert out["d3_dropped"].to_list() == [False, True]


def test_x6():
    assert bd.x6_excluded({"underlyingType": "EQUITY", "underlyingSubType": ["TradFi"]})
    assert bd.x6_excluded({"underlyingType": "COIN", "underlyingSubType": ["Pre-Market"]})
    assert bd.x6_excluded({"underlyingType": "INDEX", "underlyingSubType": []})
    assert not bd.x6_excluded({"underlyingType": "COIN", "underlyingSubType": ["DEFI"]})


# --------------------------------------------------------------------------- onsets

def test_onsets_side_decluster_and_s2_exclusion():
    ts, d, n = _book(2880)
    n[100, 4] = d[100, 4] * 103.0  # bid-stale crossing at snapshot 100
    n[200, 4] = d[200, 4] * 103.0  # within 6 h of the first: declustered
    d[1500:1530, 7] = d[1500, 7]  # ask band freeze
    d[2000:2010] = d[2000]  # whole-book repeat: every band freezes...
    d[2000:2030, 2] = d[2000, 2]  # ...and one bid band keeps going, but starts inside S2
    n[2000:2010] = n[2000]
    m = _mask(ts, d, n)
    on = bd.onsets(m)
    assert on.select("side", "rule").rows() == [("bid", "S1"), ("ask", "S3")]
    assert on["ts"].to_list() == [int(ts[100]), int(ts[1500])]
