from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl

from microstructure.quality import metrics as mt
from microstructure.quality.bookdepth import Klines

DAY0 = int(dt.datetime(2025, 3, 1, tzinfo=dt.UTC).timestamp())


def _frame(oi: np.ndarray, ratio: np.ndarray | None = None, t0: int = DAY0) -> pl.DataFrame:
    n = oi.size
    rng = np.random.default_rng(0)
    ratio = ratio if ratio is not None else np.exp(rng.normal(0, 0.3, n))
    return pl.DataFrame({
        "ts": t0 + mt.STEP_S * np.arange(n, dtype=np.int64),
        "sum_open_interest": oi, "sum_open_interest_value": oi * 100.0,
        "count_toptrader_long_short_ratio": 1 + rng.random(n),
        "sum_toptrader_long_short_ratio": 1 + rng.random(n),
        "count_long_short_ratio": 1 + rng.random(n),
        "sum_taker_long_short_vol_ratio": ratio,
    })


def _walk(n: int, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 1e5 + np.cumsum(rng.normal(0, 50, n))


def test_parse_metrics_csv_header_and_empty_cells():
    raw = (b"create_time,symbol,sum_open_interest,sum_open_interest_value,"
           b"count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,"
           b"count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
           b"2025-03-01 00:00:00,BTCUSDT,1.5,2.5,1,1,1,1\n"
           b"2025-03-01 00:05:00,BTCUSDT,,,,,,\n")
    df = mt.parse_metrics_csv(raw)
    assert df["ts"].to_list() == [DAY0, DAY0 + 300]
    s = mt.screen(df)
    assert s.rows["m0"].to_list() == [False, True]


def test_m2_flags_isolated_spike_not_real_move():
    oi = _walk(200)
    oi[100] += 0.08 * oi[99]  # phantom: up 8% and straight back
    oi[150:] -= 0.05 * oi[149]  # genuine drop that stays
    s = mt.screen(_frame(oi))
    assert np.flatnonzero(s.rows["m2"].to_numpy()).tolist() == [100]


def test_m2_needs_one_percent_and_full_reversal():
    oi = _walk(200)
    oi[80] += 0.004 * oi[79]  # large relative to noise but under 1%
    oi[120] += 0.05 * oi[119]
    oi[121] = oi[119] + 0.5 * (oi[120] - oi[119])  # only half reversed
    s = mt.screen(_frame(oi))
    assert not s.rows["m2"].any()


def test_m2_requires_regular_spacing():
    oi = _walk(100)
    oi[50] += 0.1 * oi[49]
    df = _frame(oi).filter(pl.col("ts") != DAY0 + 49 * 300)  # row before spike missing
    assert not mt.screen(df).rows["m2"].any()


def test_m1_duplicates_and_m3_ghost_run():
    oi = _walk(60)
    df = _frame(oi)
    ghost = df.slice(30, 1).select(pl.exclude("ts"))
    rows = []
    for i in range(60):
        r = df.row(i, named=True)
        if 30 <= i < 45:
            r |= ghost.row(0, named=True)
        rows.append(r)
    df = pl.DataFrame(rows)
    dup_same = df.slice(5, 1)
    dup_diff = df.slice(7, 1).with_columns(pl.col("sum_open_interest") + 1)
    s = mt.screen(pl.concat([df, dup_same, dup_diff]))
    assert s.n_dup_identical == 1 and s.n_dup_conflict == 2
    assert DAY0 + 7 * 300 not in s.rows["ts"].to_list()
    flagged = s.rows.filter(pl.col("m3"))["ts"].to_list()
    assert flagged == [DAY0 + i * 300 for i in range(30, 45)]


def test_missing_labels():
    ts = DAY0 + 300 * np.r_[0:100, 105:288]
    assert mt.missing_labels(ts, DAY0) == 5


def _klines_from_blocks(lr: np.ndarray, t0: int = DAY0) -> Klines:
    """1-minute klines whose 5-minute taker buy/sell log ratio is lr per block."""
    n = lr.size * 5
    vol = np.full(n, 10.0)
    p = np.repeat(np.exp(lr) / (1 + np.exp(lr)), 5)
    o = t0 + 60 * np.arange(n, dtype=np.int64)
    z = np.ones(n)
    return Klines(o, z, z, z, vol * p, vol)


def test_label_convention_detects_start_end_and_noise():
    rng = np.random.default_rng(3)
    lr = rng.normal(0, 0.4, 288)
    kl = _klines_from_blocks(lr)
    start = _frame(_walk(288), ratio=np.exp(lr))
    assert mt.label_convention(start, kl)["convention"] == "start"
    end = _frame(_walk(287), ratio=np.exp(lr[:-1]), t0=DAY0 + 300)
    assert mt.label_convention(end, kl)["convention"] == "end"
    noise = _frame(_walk(288), ratio=np.exp(rng.normal(0, 0.4, 288)))
    assert mt.label_convention(noise, kl)["convention"] == "undetermined"
    short = _frame(_walk(50), ratio=np.exp(lr[:50]))
    assert mt.label_convention(short, kl)["convention"] == "undetermined"
