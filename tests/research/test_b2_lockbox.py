"""Offline tests of research/market_evolution/b2_lockbox.py on synthetic panels (no archive
files): training rows never have a label window reaching the lock-box, the scorer sees
lock-box rows only and never their labels, and a planted signal is found while pure noise
is not."""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import numpy as np
import polars as pl
import pytest

PATH = Path(__file__).resolve().parents[2] / "research" / "market_evolution" / "b2_lockbox.py"
FEATS = ["x", "noise"]


@pytest.fixture(scope="module")
def b2():
    spec = importlib.util.spec_from_file_location("b2_lockbox", PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def synthetic_panel(b2, signal: float, n_lives: int = 300, seed: int = 0) -> pl.DataFrame:
    """Person-period rows from 2020-01 to 2026-07 with the panel's label rules.

    Monthly death hazard 0.012 * exp(signal * x); x = persistent trait + noise. `noise`,
    `qv_rank_pct` and `dlog_qv_3m` carry no information.
    """
    b0 = b2.b0
    rng = np.random.default_rng(seed)
    t_lo, t_end = b0.midx("2020-01"), b0.midx("2026-07") + b2.H
    rows = []
    for i in range(n_lives):
        start = int(rng.integers(t_lo, t_end - 8))
        trait = rng.normal()
        xs, t, last = [], start, None
        while t <= t_end:
            xs.append((t, trait + 0.5 * rng.normal()))
            if rng.random() < 0.012 * np.exp(signal * xs[-1][1]):
                last = t + 1
                break
            t += 1
        for t, x in xs:
            if t + b2.H > t_end:
                continue              # common label end: dropped for every life
            gap = (last - t) if last is not None else 99
            ltd = (dt.date(last // 12, last % 12 + 1, 5) if last is not None
                   else dt.date(2026, 11, 1))
            rows.append({"life_id": f"L{i}", "t": t, "x": x, "noise": rng.normal(),
                         "qv_rank_pct": rng.random(), "dlog_qv_3m": rng.normal(),
                         "y3": int(1 <= gap <= b2.H), "final_full_month": gap == 1,
                         "last_trade_day": ltd})
    return pl.DataFrame(rows).sort("t", "life_id")


def test_masks(b2):
    t = np.arange(b2.b0.midx("2025-01"), b2.b0.midx("2026-08"))
    tr, lk = b2.train_mask(t), b2.lock_mask(t)
    assert b2.b0.mstr(int(t[tr].max())) == "2025-09"
    assert np.all(t[tr] + b2.H < b2.LOCKBOX_T)
    assert b2.b0.mstr(int(t[lk].min())) == "2026-01"
    purged = t[~tr & ~lk]
    assert [b2.b0.mstr(int(m)) for m in purged] == ["2025-10", "2025-11", "2025-12"]


@pytest.mark.parametrize("drop", [False, True])
def test_training_rows_never_reach_lockbox(b2, monkeypatch, drop):
    df = synthetic_panel(b2, signal=1.0)
    seen = {}
    real = b2.fit_frozen

    def spy(train, feats=None):
        seen["t"] = train["t"].to_numpy().copy()
        return real(train, feats)

    monkeypatch.setattr(b2, "fit_frozen", spy)
    train, lock = b2.split(df, drop)
    b2.fit_run(df, drop, feats=FEATS)
    # every training label window t+1..t+3 ends before 2026-01
    assert np.all(seen["t"] + b2.H < b2.LOCKBOX_T)
    assert np.all(train["t"].to_numpy() + b2.H < b2.LOCKBOX_T)
    assert len(seen["t"]) == train.height
    # nothing from the three purged months, nothing from the lock-box
    assert not set(train["t"].to_list()) & set(lock["t"].to_list())
    if drop:
        assert not train["final_full_month"].any() and not lock["final_full_month"].any()


def test_scorer_sees_lockbox_rows_only_and_not_labels(b2):
    df = synthetic_panel(b2, signal=1.0, seed=1)
    fr = b2.fit_run(df, False, feats=FEATS)
    lock = fr["lock"]
    assert lock["t"].min() == b2.LOCKBOX_T
    assert lock.height == df.filter(pl.col("t") >= b2.LOCKBOX_T).height
    # the scorer refuses any pre-lock-box row
    early = df.filter(pl.col("t") == b2.LOCKBOX_T - 1)
    with pytest.raises(AssertionError):
        b2.score(fr["fitted"], pl.concat([early, lock]))
    # scores do not depend on lock-box labels
    a = b2.score(fr["fitted"], lock)
    b = b2.score(fr["fitted"], lock.with_columns(y3=1 - pl.col("y3")))
    for k in a:
        np.testing.assert_array_equal(a[k], b[k])
    # and the fit does not depend on them either
    flipped = df.with_columns(y3=pl.when(pl.col("t") >= b2.LOCKBOX_T).then(1 - pl.col("y3"))
                              .otherwise(pl.col("y3")))
    fr2 = b2.fit_run(flipped, False, feats=FEATS)
    np.testing.assert_array_equal(b2.score(fr2["fitted"], fr2["lock"])["logit_full"],
                                  a["logit_full"])


def test_dev_mode_never_touches_lockbox(b2):
    df = synthetic_panel(b2, signal=1.0, seed=2)
    train, lock = b2.split(df, False, b2.DEV_START, b2.DEV_STOP)
    assert lock["t"].max() < b2.LOCKBOX_T and lock["t"].min() == b2.DEV_START
    assert train["t"].max() + b2.H < b2.DEV_START


def test_planted_signal_found(b2):
    r = b2.run(synthetic_panel(b2, signal=1.5, n_lives=500, seed=4), False, n_boot=300,
               feats=FEATS)
    ev = r["eval"]
    assert r["n_pos"] > 10
    for k in ("logit_full", "gbm_full"):
        assert ev["point"][f"prec_{k}"] > 2 * ev["point"]["base"]
        assert ev["point"][f"ap_{k}_minus_b"] > 0
    assert ev["point"]["bss_logit_full"] > 0


def test_pure_noise_not_found(b2):
    r = b2.run(synthetic_panel(b2, signal=0.0, n_lives=500, seed=5), False, n_boot=300,
               feats=FEATS)
    ev = r["eval"]
    lo, hi = ev["ci"]["prec_logit_full_minus_b"]
    assert lo <= 0 <= hi
    assert ev["point"]["ap_logit_full"] < 4 * ev["point"]["base"]


def test_verdict(b2):
    cv = (0.018, -0.008, 0.042)
    assert b2.verdict((0.03, 0.01, 0.05), cv).startswith("strengthens")
    assert b2.verdict((0.01, -0.01, 0.03), cv).startswith("confirms")
    assert b2.verdict((-0.01, -0.03, 0.01), cv).startswith("weakens")
    assert b2.verdict((-0.03, -0.05, -0.01), cv).startswith("reverses")
    neg = (-0.005, -0.041, 0.017)
    assert b2.verdict((-0.01, -0.03, 0.01), neg).startswith("confirms")
    assert b2.verdict((0.01, -0.01, 0.03), neg).startswith("weakens")


def test_leave_one_month_out(b2):
    months = [{"alerts": 10, "logit_full": 2, "base_b": 1},
              {"alerts": 10, "logit_full": 1, "base_b": 1},
              {"alerts": 10, "logit_full": 4, "base_b": 1}]
    lo, hi = b2.leave_one_month_out(months, "logit_full")
    assert lo == pytest.approx(1 / 20) and hi == pytest.approx(4 / 20)
