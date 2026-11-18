"""Offline synthetic tests for the panel regressions and composition split (e4)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_PATH = (Path(__file__).resolve().parents[2] / "research" / "market_evolution"
         / "e4_panel_regressions.py")
_spec = importlib.util.spec_from_file_location("e4_panel_regressions", _PATH)
e4 = importlib.util.module_from_spec(_spec)
sys.modules["e4_panel_regressions"] = e4
_spec.loader.exec_module(e4)


def _panel(n=80, t=4, beta=2.0, seed=0, shock=0.0, x_common=0.0):
    """Contract x month panel; the contract effect is correlated with the driver."""
    rng = np.random.default_rng(seed)
    a = rng.normal(0, 1, n)
    ids = np.repeat(np.arange(n), t)
    month = np.tile(np.arange(t), n)
    late = (month == t - 1).astype(float)
    x = 0.8 * a[ids] + x_common * late + rng.normal(0, 1, n * t)
    y = a[ids] + beta * x + shock * late + rng.normal(0, 0.5, n * t)
    return ids, month, late, x, y


def _dummies(v):
    u = np.unique(v)
    return (v[:, None] == u[None, :]).astype(float)


def test_contract_fe_recovers_planted_driver_and_matches_dummy_regression():
    ids, _month, _late, x, y = _panel(beta=2.0)
    fe = e4.fit(y, x, ids, fe=ids)
    assert abs(fe["b"][0] - 2.0) < 0.1
    assert fe["lo"][0] < 2.0 < fe["hi"][0]
    # the pooled estimate is biased by the contract effect correlated with x
    pooled = e4.fit(y, x, ids, add_const=True)
    assert pooled["b"][1] - 2.0 > 0.2
    # identical coefficient to a least-squares dummy-variable regression
    D = np.column_stack([x, _dummies(ids)])
    b_dummy = np.linalg.lstsq(D, y, rcond=None)[0][0]
    assert fe["b"][0] == pytest.approx(b_dummy, abs=1e-10)


def test_two_way_fe_matches_dummy_regression():
    ids, month, _late, x, y = _panel(shock=1.0)
    md = _dummies(month)[:, 1:]
    twfe = e4.fit(y, np.column_stack([x, md]), ids, fe=ids)
    D = np.column_stack([x, md, _dummies(ids)])
    b = np.linalg.lstsq(D, y, rcond=None)[0]
    assert np.allclose(twfe["b"], b[: 1 + md.shape[1]], atol=1e-10)


def test_composition_split_sums_to_total_and_matches_note_formula():
    rng = np.random.default_rng(1)
    ids0 = np.array([f"c{i}" for i in range(60)])
    ids1 = np.array([f"c{i}" for i in range(15, 60)] + [f"n{i}" for i in range(40)])
    y0 = rng.normal(60, 2, ids0.size)
    y1 = rng.normal(63, 2, ids1.size)
    for stat in (np.mean, np.median):
        r = e4.composition_split(ids0, y0, ids1, y1, stat)
        assert r["exit"] + r["within"] + r["entry"] == pytest.approx(r["total"], abs=1e-12)
        assert r["total"] == pytest.approx(stat(y1) - stat(y0))
    # the methods note (section 6) formula, term for term, for the mean
    r = e4.composition_split(ids0, y0, ids1, y1, np.mean)
    s0, s1 = np.isin(ids0, ids1), np.isin(ids1, ids0)
    exit_note = -(~s0).mean() * (y0[~s0].mean() - y0[s0].mean())
    entry_note = (~s1).mean() * (y1[~s1].mean() - y1[s1].mean())
    assert r["exit"] == pytest.approx(exit_note)
    assert r["entry"] == pytest.approx(entry_note)
    assert (r["n_survivors"], r["n_exit"], r["n_entry"]) == (45, 15, 40)


def test_composition_detects_pure_survivorship():
    """Weak coins die, nobody changes: all of the rise is the exit term."""
    ids0 = np.array([f"c{i}" for i in range(10)])
    y0 = np.arange(10, dtype=float)
    ids1, y1 = ids0[5:], y0[5:]
    r = e4.composition_split(ids0, y0, ids1, y1)
    assert r["within"] == 0 and r["entry"] == 0
    assert r["exit"] == pytest.approx(r["total"]) and r["total"] > 0
    b = e4.bootstrap_composition(ids0, y0, ids1, y1, np.mean, n_boot=200)
    assert b["within"][0] == b["within"][1] == 0


def test_month_fixed_effects_absorb_a_market_wide_rise():
    """Methods note 1.4: a common rise goes into the month effects, not the drivers."""
    ids, _month, late, x, y = _panel(beta=0.0, shock=3.0, t=2)
    # contract FE plus a late dummy sees the rise
    short = e4.fit(y, late, ids, fe=ids)
    assert abs(short["b"][0] - 3.0) < 0.2
    # two-way FE: the month effect takes all of it, the (irrelevant) driver nothing,
    # and after removing contract and month means no common change is left to explain
    twfe = e4.fit(y, np.column_stack([x, late]), ids, fe=ids)
    assert abs(twfe["b"][1] - 3.0) < 0.2 and abs(twfe["b"][0]) < 0.15
    yt, Xt, _ = twfe["data"]
    resid = yt - Xt[:, 1] * (np.linalg.lstsq(Xt[:, 1:], yt, rcond=None)[0][0])
    assert resid[late == 1].mean() - resid[late == 0].mean() == pytest.approx(0, abs=1e-10)
    # a driver whose change is purely market-wide cannot be told apart from the month
    # effect: two-way FE is not identified for it
    ids2, _, late2, _, _ = _panel(t=2)
    x_common = np.random.default_rng(3).normal(0, 1, ids2.max() + 1)[ids2] + late2
    with pytest.raises(ValueError, match="collinear"):
        e4.fit(y, np.column_stack([x_common, late2]), ids2, fe=ids2)


def test_gelbach_attributes_the_rise_to_the_driver_that_caused_it():
    ids, _month, late, x, y = _panel(beta=0.5, x_common=2.0, t=2, n=200)
    yt, Xt, _cl = e4.prepare(y, np.column_stack([late, x]), ids, fe=ids)
    g = e4.gelbach(yt, Xt[:, :1], Xt[:, 1:])
    assert g["short"][0] - g["long"][0] == pytest.approx(g["delta"][0].sum(), abs=1e-10)
    assert abs(g["short"][0] - 1.0) < 0.15        # 0.5 x the common shift of 2
    assert abs(g["delta"][0, 0] - 1.0) < 0.15
    assert abs(g["long"][0]) < 0.15


def test_wild_bootstrap_with_few_clusters():
    ids, _month, _late, x, y = _panel(n=10, t=5, beta=0.0, seed=4)
    yt, Xt, cl = e4.prepare(y, x, ids, fe=ids)
    assert e4.wild_p(yt, Xt, cl, 0) > 0.05
    ids, _month, _late, x, y = _panel(n=10, t=5, beta=1.0, seed=4)
    yt, Xt, cl = e4.prepare(y, x, ids, fe=ids)
    assert e4.wild_p(yt, Xt, cl, 0) < 0.01
    lo, hi = e4.wild_ci(yt, Xt, cl, 0, n_grid=61)
    assert lo < 1.0 < hi
