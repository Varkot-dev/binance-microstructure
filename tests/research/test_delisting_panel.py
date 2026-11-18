"""Offline tests of research/market_evolution/b0_baselines.py on synthetic data with
planted answers (no network, no archive files)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import polars as pl
import pytest

PATH = Path(__file__).resolve().parents[2] / "research" / "market_evolution" / "b0_baselines.py"


@pytest.fixture(scope="module")
def b0():
    spec = importlib.util.spec_from_file_location("b0_baselines", PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _life(life_id: str, first: int, last: int, outcome: str, end: int) -> pl.DataFrame:
    """Grid rows t = first..min(last, end) of one life, as the build makes them."""
    ts = list(range(first, min(last, end) + 1))
    return pl.DataFrame({"life_id": [life_id] * len(ts), "t": ts, "last_t": [last] * len(ts),
                         "outcome": [outcome] * len(ts)})


def _labels(b0, frames, end, horizon=3):
    out = b0.assign_labels(pl.concat(frames), horizon=horizon, obs_end=end)
    return {(r["life_id"], r["t"]): (r["y3"], r["drop_reason"]) for r in out.iter_rows(named=True)}


def test_month_index_roundtrip(b0):
    assert b0.midx("2026-01") == 2026 * 12
    assert b0.mstr(b0.midx("2025-12")) == "2025-12"
    assert b0.midx("2026-01") - b0.midx("2025-10") == 3


def test_event_label_window_is_exactly_t_plus_1_to_t_plus_3(b0):
    end = 100
    lab = _labels(b0, [_life("D#1", 0, 20, "event", end)], end)
    for t in range(20):
        y, reason = lab[("D#1", t)]
        assert reason is None
        assert y == (1 if 17 <= t <= 19 else 0), t
    # The final, partial trading month is never a feature row.
    assert lab[("D#1", 20)] == (None, "final_trading_month")


def test_labels_do_not_see_beyond_the_horizon(b0):
    """Two event lives that are identical up to month 30 and die at 35 and at 50: every row
    whose window t+1..t+3 ends before both deaths must get the same label (0)."""
    end = 100
    lab = _labels(b0, [_life("A#1", 0, 35, "event", end), _life("B#1", 0, 50, "event", end)],
                  end)
    for t in range(32):  # t + 3 < 35
        assert lab[("A#1", t)] == lab[("B#1", t)] == (0, None)
    assert lab[("A#1", 32)][0] == 1 and lab[("B#1", 32)][0] == 0


def test_features_use_only_months_up_to_t(b0):
    """Changing every month after t must leave the features at t unchanged."""
    rng = np.random.default_rng(1)
    n = 24
    base = pl.DataFrame({
        "life_id": ["X#1"] * n, "t": list(range(n)),
        "log_qv": rng.normal(20, 1, n), "log_trades": rng.normal(12, 1, n),
        "close_last": rng.uniform(1, 2, n), "log_oi": rng.normal(15, 1, n),
        "funding_interval_min_h": [8.0] * n,
    })
    t_cut = 11
    fut = base.with_columns([
        pl.when(pl.col("t") > t_cut).then(pl.col(c) * 3.7 + 5).otherwise(pl.col(c)).alias(c)
        for c in ("log_qv", "log_trades", "close_last", "log_oi", "funding_interval_min_h")])
    a = b0.add_trailing_features(base).filter(pl.col("t") <= t_cut).sort("t")
    b = b0.add_trailing_features(fut).filter(pl.col("t") <= t_cut).sort("t")
    assert a.equals(b)
    # Planted values: 3-month change and running peak.
    a_full = b0.add_trailing_features(base).sort("t")
    q = base["log_qv"].to_numpy()
    assert a_full["dlog_qv_3m"][5] == pytest.approx(q[5] - q[2])
    assert a_full["dlog_qv_3m"][2] is None
    assert a_full["log_qv_rel_peak"][7] == pytest.approx(q[7] - q[:8].max())


def test_lags_are_by_calendar_month_not_by_row(b0):
    """A missing month inside a life gives a null lag, never the row three positions back."""
    df = pl.DataFrame({"life_id": ["G#1"] * 5, "t": [0, 1, 2, 4, 5],
                       "log_qv": [1.0, 2.0, 3.0, 5.0, 6.0], "log_trades": [1.0] * 5,
                       "close_last": [1.0] * 5, "log_oi": [1.0] * 5,
                       "funding_interval_min_h": [8.0] * 5})
    out = b0.add_trailing_features(df).sort("t")
    d = dict(zip(out["t"].to_list(), out["dlog_qv_3m"].to_list(), strict=True))
    assert d[4] == pytest.approx(5.0 - 2.0)   # t - 3 = 1
    assert d[5] == pytest.approx(6.0 - 3.0)   # t - 3 = 2
    assert d[2] is None


def test_censored_rows_are_dropped_not_zeroed(b0):
    end = 30
    lab = _labels(b0, [_life("ALIVE#1", 0, 31, "censored", end)], end)
    for t in range(28):
        assert lab[("ALIVE#1", t)] == (0, None)
    for t in (28, 29, 30):  # window reaches past the data end
        y, reason = lab[("ALIVE#1", t)]
        assert y is None and reason is not None
    out = b0.assign_labels(_life("ALIVE#1", 0, 31, "censored", end), obs_end=end)
    kept = out.filter(pl.col("drop_reason").is_null())
    assert kept["t"].max() == 27 and kept["y3"].null_count() == 0


def test_label_end_is_common_to_events_and_survivors(b0):
    """An event life is not kept past the common label end: otherwise the last months would
    hold dying contracts only."""
    end = 30
    lab = _labels(b0, [_life("D#1", 0, 30, "event", end), _life("S#1", 0, 31, "censored", end)],
                  end)
    assert lab[("D#1", 27)] == (1, None)
    assert lab[("D#1", 28)][0] is None and lab[("S#1", 28)][0] is None


def test_renames_are_not_events(b0):
    end = 100
    assert b0.life_outcome("renamed") == "censored"
    assert b0.life_outcome("merged") == "censored"
    assert b0.life_outcome("delisted") == "event"
    assert b0.life_outcome("index") == "excluded"
    lab = _labels(b0, [_life("R#1", 0, 20, "censored", end)], end)
    assert all(v[0] != 1 for v in lab.values())
    for t in range(18):  # t + 3 <= 20
        assert lab[("R#1", t)] == (0, None)
    for t in (18, 19):  # window passes the rename: censored, dropped
        assert lab[("R#1", t)] == (None, "censored_label_unknown")
    assert lab[("R#1", 20)] == (None, "final_trading_month")


def test_purge_removes_exactly_overlapping_rows(b0):
    rng = np.random.default_rng(0)
    t = np.sort(rng.integers(0, 60, 3000))
    folds = b0.purged_expanding_folds(t, first_test=24, test_len=6, horizon=3, end=60)
    assert [f["test_start"] for f in folds] == [24, 30, 36, 42, 48, 54]
    for f in folds:
        T, stop = f["test_start"], f["test_stop"]
        tr = set(f["train"].tolist())
        before = set(np.flatnonzero(t < T).tolist())
        overlap = {i for i in before if t[i] + 3 >= T}  # window t+1..t+3 touches [T, stop)
        assert before - tr == overlap == set(f["purged"].tolist())
        assert t[f["train"]].max() == T - 4
        assert np.all(t[f["train"]] + 3 < T)
        assert set(f["test"].tolist()) == set(np.flatnonzero((t >= T) & (t < stop)).tolist())
    # Test blocks never reach the lock-box.
    folds = b0.purged_expanding_folds(t, first_test=24, test_len=6, horizon=3, end=40)
    assert folds[-1]["test_stop"] == 40 and t[folds[-1]["test"]].max() < 40


def test_threshold_is_chosen_on_training_rows_only(b0):
    """Planted: in training, deaths have dlog near -2 (best threshold near -1.5); test rows
    are rigged so that a threshold fitted on them would be very different. The per-fold
    threshold must equal choose_threshold on the training rows and ignore the test rows."""
    rng = np.random.default_rng(3)
    rows = []
    for t in range(40):
        for j in range(50):
            dead = j < 2
            if t < 30:
                x = rng.normal(-2.0, 0.2) if dead else rng.normal(0.0, 0.3)
            else:
                x = rng.normal(3.0, 0.2) if dead else rng.normal(-4.0, 0.3)
            rows.append({"life_id": f"C{j}#1", "t": t, "y3": int(dead), "dlog_qv_3m": x,
                         "qv_rank_pct": (j + 1) / 50, "log_age": float(np.log1p(t))})
    d = pl.DataFrame(rows).sort("t", "life_id")
    tt = d["t"].to_numpy()
    folds = b0.purged_expanding_folds(tt, first_test=34, test_len=6, horizon=3, end=40)
    sc = b0.score_folds(d, folds)
    tr = folds[0]["train"]
    y = d["y3"].to_numpy()
    x = d["dlog_qv_3m"].to_numpy()
    thr = sc["per_fold"][0]["threshold_a"]
    assert thr == b0.choose_threshold(x[tr], y[tr])
    assert -2.0 < thr < 0.0
    # Rewrite the test block: the chosen threshold does not move.
    d2 = d.with_columns(pl.when(pl.col("t") >= 34).then(pl.col("dlog_qv_3m") * -10.0)
                        .otherwise(pl.col("dlog_qv_3m")).alias("dlog_qv_3m"))
    assert b0.score_folds(d2, folds)["per_fold"][0]["threshold_a"] == thr
    # Training rows inside the purge gap (t = 31..33) are not used either.
    d3 = d.with_columns(pl.when(pl.col("t").is_between(31, 33)).then(pl.lit(-50.0))
                        .otherwise(pl.col("dlog_qv_3m")).alias("dlog_qv_3m"))
    assert b0.score_folds(d3, folds)["per_fold"][0]["threshold_a"] == thr


def test_alert_counts_top_share_and_nan_last(b0):
    month = np.array([0] * 40 + [1] * 10)
    y = np.zeros(50, dtype=int)
    y[[0, 1, 45]] = 1
    score = np.arange(50, dtype=float)[::-1].copy()  # row 0 has the highest score
    score[45] = np.nan
    a = b0.alert_counts(month, y, score, rate=0.05)
    assert a[0] == (40, 2, 2, 2)          # top 2 of 40 are rows 0 and 1
    assert a[1] == (10, 1, 0, 1)          # NaN score is never flagged


def test_block_bootstrap_uses_whole_month_runs(b0):
    months = np.arange(36) + 1000
    reps = b0.block_bootstrap_months(months, n_boot=50, block=3, seed=1)
    for r in reps:
        assert len(r) == 36
        for i in range(0, 36, 3):
            assert r[i + 1] == r[i] + 1 and r[i + 2] == r[i] + 2


def test_ranks_use_only_the_live_universe(b0):
    df = pl.DataFrame({"life_id": ["A", "B", "C", "D"], "t": [5, 5, 5, 5],
                       "log_qv": [1.0, 2.0, 3.0, 100.0], "log_trades": [1.0, 2.0, 3.0, 4.0],
                       "log_oi": [None, 1.0, 2.0, 3.0],
                       "in_universe": [True, True, True, False]})
    out = b0.add_cross_section_ranks(df).sort("life_id")
    assert out["qv_rank_pct"].to_list()[:3] == pytest.approx([1 / 3, 2 / 3, 1.0])
    assert out["qv_rank_pct"][3] is None
    assert out["oi_rank_pct"].to_list()[:3] == [None, 0.5, 1.0]
    assert out["n_live_month"][0] == 3
