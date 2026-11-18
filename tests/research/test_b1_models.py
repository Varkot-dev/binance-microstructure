"""Offline tests of research/market_evolution/b1_models.py on synthetic panels (no archive
files): the inner validation split never reaches test-block or lock-box rows, calibration
is fitted on training rows only, a planted signal is found and pure noise is not."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import polars as pl
import pytest

PATH = Path(__file__).resolve().parents[2] / "research" / "market_evolution" / "b1_models.py"
FEATS = ["x", "noise"]
SPECS = {"logit_full": ("logit", FEATS), "gbm_full": ("gbm", FEATS)}


@pytest.fixture(scope="module")
def b1():
    spec = importlib.util.spec_from_file_location("b1_models", PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def synthetic_panel(b1, signal: float, n_lives: int = 260, seed: int = 0) -> pl.DataFrame:
    """Person-period rows from 2020-01 to 2026-06 with the panel's label rules.

    Each life has a persistent trait; the monthly death hazard is 0.012 * exp(signal * x),
    where x is the trait plus noise. `noise` and qv_rank_pct carry no information.
    """
    rng = np.random.default_rng(seed)
    t_lo, t_end = b1.b0.midx("2020-01"), b1.b0.midx("2026-06")
    rows = []
    for i in range(n_lives):
        start = int(rng.integers(t_lo, t_end - 6))
        trait = rng.normal()
        xs, t, last = [], start, None
        while t <= t_end:
            x = trait + 0.5 * rng.normal()
            xs.append((t, x))
            if rng.random() < 0.012 * np.exp(signal * x):
                last = t + 1          # last trading month: the next month
                break
            t += 1
        for t, x in xs:
            if last is None and t + b1.H > t_end:
                continue              # censored: label unknown, dropped (never set to 0)
            gap = (last - t) if last is not None else 99
            rows.append({"life_id": f"L{i}", "t": t, "x": x, "noise": rng.normal(),
                         "qv_rank_pct": rng.random(), "y3": int(1 <= gap <= b1.H),
                         "event": last is not None, "months_to_last": gap,
                         "final_full_month": last is not None and gap == 1})
    return pl.DataFrame(rows).sort("t", "life_id")


def _folds(b1, d):
    return b1.b0.purged_expanding_folds(d["t"].to_numpy(), b1.FIRST_TEST_T, end=b1.LOCKBOX_T)


def test_inner_split_purged_and_inside_training(b1):
    t = np.repeat(np.arange(100, 140), 5)
    itr, iva = b1.inner_split(t)
    assert len(np.intersect1d(itr, iva)) == 0
    v0 = t[iva].min()
    assert t[iva].max() == t.max() and v0 == t.max() - b1.INNER_VAL_LEN + 1
    assert np.all(t[itr] + b1.H < v0)


def test_inner_validation_never_sees_test_or_lockbox_rows(b1, monkeypatch):
    df = synthetic_panel(b1, signal=1.0)
    assert df["t"].max() >= b1.LOCKBOX_T  # the synthetic panel does have lock-box rows
    d = b1.pre_lockbox(df, drop_final_full=False)
    assert d["t"].max() < b1.LOCKBOX_T
    folds = _folds(b1, d)
    seen = []
    real = b1.inner_split

    def spy(t_train, *a, **k):
        seen.append(np.asarray(t_train).copy())
        return real(t_train, *a, **k)

    monkeypatch.setattr(b1, "inner_split", spy)
    b1.run_folds(d, folds, SPECS, shap_last=False)
    assert len(seen) == len(folds) * len(SPECS)
    for i, f in enumerate(folds):
        for t_train in seen[i * len(SPECS):(i + 1) * len(SPECS)]:
            assert t_train.max() + b1.H < f["test_start"]
            assert t_train.max() < b1.LOCKBOX_T


def test_scores_and_calibration_ignore_test_labels(b1, monkeypatch):
    """Scrambling the labels of the last test block changes no out-of-fold score and no
    calibrated probability, so neither the models nor the calibrators saw those labels."""
    d = b1.pre_lockbox(synthetic_panel(b1, signal=1.0, seed=1), drop_final_full=False)
    folds = _folds(b1, d)
    cal_sizes = []
    real = b1.fit_calibrators

    def spy(score, y):
        cal_sizes.append(len(y))
        return real(score, y)

    monkeypatch.setattr(b1, "fit_calibrators", spy)
    a = b1.run_folds(d, folds, SPECS, shap_last=False)
    last = folds[-1]["test"]
    y = d["y3"].to_numpy().copy()
    y[last] = 1 - y[last]
    d2 = d.with_columns(y3=pl.Series(y))
    b = b1.run_folds(d2, folds, SPECS, shap_last=False)
    for k in a["scores"]:
        np.testing.assert_array_equal(a["scores"][k], b["scores"][k])
    for k in a["cal"]:
        np.testing.assert_array_equal(a["cal"][k], b["cal"][k])
    # each calibrator was fitted on an inner-validation block of training rows only
    t = d["t"].to_numpy()
    for i, f in enumerate(folds):
        _, iva = b1.inner_split(t[f["train"]])
        assert cal_sizes[2 * i] == len(iva) < len(f["train"])


def test_calibrators_map_to_rates(b1):
    rng = np.random.default_rng(3)
    s = rng.random(4000)
    y = (rng.random(4000) < 0.02 + 0.1 * s).astype(int)
    cal = b1.fit_calibrators(s, y)
    for fn in cal.values():
        p = fn(s)
        assert abs(p.mean() - y.mean()) < 0.01
        assert np.all((p >= 0) & (p <= 1))


def test_weighted_ap_matches_sklearn(b1):
    from sklearn.metrics import average_precision_score
    rng = np.random.default_rng(2)
    y = (rng.random(2000) < 0.05).astype(int)
    s = np.round(rng.random(2000) + 0.4 * y, 2)
    w = rng.integers(0, 3, 2000)
    idx = np.repeat(np.arange(2000), w)
    got = b1.weighted_ap(b1.ap_prepare(y, s), w.astype(float))
    assert got == pytest.approx(average_precision_score(y[idx], s[idx]))


def _evaluate(b1, signal: float, seed: int) -> dict:
    d = b1.pre_lockbox(synthetic_panel(b1, signal=signal, seed=seed), drop_final_full=False)
    folds = _folds(b1, d)
    res = b1.run_folds(d, folds, SPECS, shap_last=False)
    test = np.concatenate([f["test"] for f in folds])
    sc = {k: v[test] for k, v in res["scores"].items()}
    return b1.evaluate_scores(d["t"].to_numpy()[test], d["y3"].to_numpy()[test], sc,
                              n_boot=300)


def test_planted_signal_is_detected(b1):
    ev = _evaluate(b1, signal=1.5, seed=4)
    for k in ("logit_full", "gbm_full"):
        assert ev["ci"][f"ap_{k}_minus_b"][0] > 0
        assert ev["ci"][f"prec_{k}_minus_b"][0] > 0


def test_pure_noise_is_not_detected(b1):
    ev = _evaluate(b1, signal=0.0, seed=5)
    for k in ("logit_full", "gbm_full"):
        lo, hi = ev["ci"][f"ap_{k}_minus_b"]
        assert lo <= 0 <= hi
        lo, hi = ev["ci"][f"prec_{k}_minus_b"]
        assert lo <= 0 <= hi
