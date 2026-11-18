"""Offline synthetic tests for the tick-change event study (e3_event_study.py)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_PATH = Path(__file__).resolve().parents[2] / "research" / "market_evolution" / "e3_event_study.py"
_spec = importlib.util.spec_from_file_location("e3_event_study", _PATH)
e3 = importlib.util.module_from_spec(_spec)
sys.modules["e3_event_study"] = e3
_spec.loader.exec_module(e3)


def _panel(effect: float, n_treated=12, n_control=40, seed=0, pre_trend=0.0):
    """Contract x day panel: unit and day effects, noise, a step effect after day 0."""
    rng = np.random.default_rng(seed)
    days = [r for r in range(-21, 22) if r != 0]
    units = [f"T{i}" for i in range(n_treated)] + [f"C{i}" for i in range(n_control)]
    a = rng.normal(0, 2, len(units))
    g = {d: rng.normal(0, 1) for d in days}
    rows = []
    for i, u in enumerate(units):
        tr = int(u.startswith("T"))
        for d in days:
            y = a[i] + g[d] + rng.normal(0, 0.5)
            y += tr * (effect * (d > 0) + pre_trend * d)
            rows.append((u, tr, d, y))
    u, tr, d, y = (np.array(c) for c in zip(*rows, strict=True))
    return u, tr, d, y


def test_did_recovers_planted_effect():
    u, tr, d, y = _panel(effect=1.5)
    fit = e3.did(y, tr, d > 0, u, d)
    assert abs(fit["b"] - 1.5) < 0.15
    assert fit["lo"] < 1.5 < fit["hi"]
    assert fit["lo"] > 0
    w = e3.wild_bootstrap(fit, B=999)
    assert w["p"] < 0.01 and w["lo"] < 1.5 < w["hi"]
    perm = e3.permutation_test(y, tr, d > 0, u, d, B=999)
    assert perm["p"] < 0.01
    assert perm["lo"] < 1.5 < perm["hi"]


def test_no_effect_interval_contains_zero():
    covered = 0
    for seed in range(20):
        u, tr, d, y = _panel(effect=0.0, seed=100 + seed)
        fit = e3.did(y, tr, d > 0, u, d)
        covered += fit["lo"] < 0 < fit["hi"]
    assert covered >= 17  # nominal 95%: 19 of 20 expected
    u, tr, d, y = _panel(effect=0.0, seed=4)
    fit = e3.did(y, tr, d > 0, u, d)
    assert fit["lo"] < 0 < fit["hi"]
    w = e3.wild_bootstrap(fit, B=999)
    assert w["lo"] < 0 < w["hi"] and w["p"] > 0.05
    perm = e3.permutation_test(y, tr, d > 0, u, d, B=999)
    assert perm["lo"] < 0 < perm["hi"] and perm["p"] > 0.05


def test_event_study_flags_pre_trend_only_when_present():
    u, tr, d, y = _panel(effect=1.0, seed=5)
    es = e3.event_study(y, tr, d, u, B=999)
    assert es["pre_p"] > 0.05
    assert es["slope_lo"] < 0 < es["slope_hi"]
    post = [b for day, b in zip(es["days"], es["b"], strict=True) if day > 0]
    assert abs(np.mean(post) - 1.0) < 0.2
    u, tr, d, y = _panel(effect=0.0, seed=5, pre_trend=0.1)
    es = e3.event_study(y, tr, d, u, B=999)
    assert es["slope_lo"] > 0.05
    assert es["pre_p"] < 0.01


def test_did_handles_unbalanced_panel():
    u, tr, d, y = _panel(effect=0.8, seed=7)
    keep = np.random.default_rng(1).random(y.size) > 0.2
    y = np.where(keep, y, np.nan)
    fit = e3.did(y, tr, d > 0, u, d)
    assert fit["n"] == keep.sum()
    assert abs(fit["b"] - 0.8) < 0.2


def test_permutation_single_treated_enumerates():
    u, tr, d, y = _panel(effect=0.0, n_treated=1, n_control=6, seed=2)
    perm = e3.permutation_test(y, tr, d > 0, u, d)
    assert perm["n_assign"] == 7
    assert perm["min_p"] == pytest.approx(1 / 7)


def test_demean_matches_dummy_regression():
    rng = np.random.default_rng(0)
    g1, g2 = rng.integers(0, 8, 300), rng.integers(0, 5, 300)
    x = rng.normal(size=300)
    D = np.column_stack([np.eye(8)[g1], np.eye(5)[g2][:, 1:]])
    resid = x - D @ np.linalg.lstsq(D, x, rcond=None)[0]
    assert np.allclose(e3.demean2(x, g1, g2), resid, atol=1e-8)


def _signs(rng, n, p_repeat):
    s = np.empty(n, dtype=np.int64)
    s[0] = 1
    flip = rng.random(n) > p_repeat
    for i in range(1, n):
        s[i] = -s[i - 1] if flip[i] else s[i - 1]
    return s


def _xy(signs):
    X = e3.sign_features(signs)
    m = e3.scoreable_mask(np.arange(signs.size, dtype=np.int64) * 10)
    return X[m], (signs[m] > 0).astype(np.int64)


def test_logistic_never_trains_on_post_window_days():
    rng = np.random.default_rng(0)
    train = {r: _xy(_signs(rng, 6000, 0.7)) for r in e3.TRAIN_REL}
    poison = {r: (x, 1 - y) for r, (x, y) in
              ((r, _xy(_signs(rng, 6000, 0.2))) for r in (-10, -1, 1, 5, 21))}
    m_clean = e3.fit_contract_model(train)
    m_mixed = e3.fit_contract_model(train | poison)
    assert m_mixed["train_days"] == sorted(e3.TRAIN_REL)
    assert np.allclose(m_clean["coef"], m_mixed["coef"])
    assert all(r <= -11 for r in m_mixed["train_days"])
    assert e3.fit_contract_model(poison) is None  # no training day: no model
    # design: training days precede every scored day, and the event day is never used
    assert max(e3.TRAIN_REL) < min(e3.SCORE_REL)
    assert 0 not in e3.SCORE_REL and 0 not in e3.rel_dates("2026-03-05")
    assert {e3.role_of(r) for r in range(1, 22)} == {"score"}
    # the persistent model predicts persistent signs
    x, y = _xy(_signs(rng, 6000, 0.7))
    assert e3.model_accuracy(m_clean, x, y) > 0.65


def test_features_are_causal_and_ties_unscored():
    rng = np.random.default_rng(1)
    s = _signs(rng, 3000, 0.6)
    X = e3.sign_features(s)
    s2 = s.copy()
    s2[2000:] *= -1
    X2 = e3.sign_features(s2)
    assert np.array_equal(X[:2001], X2[:2001], equal_nan=True)
    assert X[1500, 0] == s[1499] and X[1500, 9] == s[1490]
    ts = np.arange(3000, dtype=np.int64)
    ts[2500] = ts[2499]
    m = e3.scoreable_mask(ts)
    assert not m[: e3.WARMUP].any() and not m[2500] and m[2501]
