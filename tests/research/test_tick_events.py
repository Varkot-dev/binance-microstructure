"""Offline synthetic tests for the tick-change detection in build_tick_events.py."""
from __future__ import annotations

import datetime as dt
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

_PATH = Path(__file__).resolve().parents[2] / "research" / "market_evolution" / "build_tick_events.py"
_spec = importlib.util.spec_from_file_location("build_tick_events", _PATH)
bte = importlib.util.module_from_spec(_spec)
sys.modules["build_tick_events"] = bte
_spec.loader.exec_module(bte)


def _walk(rng, n, start, tick, residual_tick=None, residual_share=0.0):
    """Prices of a random walk on a tick grid; a share of prints on a finer old grid."""
    steps = rng.integers(-3, 4, size=n).cumsum()
    p = start + steps * tick
    if residual_tick is not None:
        m = rng.random(n) < residual_share
        p[m] = p[m] + rng.integers(1, 9, size=m.sum()) * residual_tick
    return np.round(p / (residual_tick or tick)) * (residual_tick or tick)


def _hist(p):
    return bte.level_histogram(bte.price_levels(p))


def test_price_levels_decimal_grids():
    lv = bte.price_levels(np.array([1.234, 1.23, 1.2, 1.0, 10.0, 0.30000000000000004]))
    assert lv.tolist()[:5] == [-3, -2, -1, 0, 1]
    assert lv[5] == -1  # float noise does not move 0.3 off the 0.1 grid
    tiny = bte.price_levels(np.array([0.0001234, 0.000124]))
    assert tiny.tolist() == [-7, -6]


@pytest.mark.parametrize("tick_exp", [-6, -4, -2, 0])
def test_tick_exp_recovers_tick(tick_exp):
    rng = np.random.default_rng(1)
    tick = 10.0 ** tick_exp
    p = _walk(rng, 5000, 3000 * tick, tick)
    assert bte.tick_exp(_hist(p)) == tick_exp


def test_increase_with_residual_old_grid_prints():
    rng = np.random.default_rng(2)
    before = _walk(rng, 4000, 1.5, 0.001)
    after = _walk(rng, 4000, 1.5, 0.01, residual_tick=0.001, residual_share=0.12)
    assert bte.tick_exp(_hist(before)) == -3
    assert bte.tick_exp(_hist(after)) == -2
    assert bte.grid_share(_hist(before), -2) < 0.2
    assert bte.grid_share(_hist(after), -2) > 0.85


def test_cut_keeps_clustering_on_old_grid_below_threshold():
    rng = np.random.default_rng(3)
    after = _walk(rng, 4000, 0.25, 0.0001)
    m = rng.random(after.size) < 0.25  # clustering on round old-grid prices
    after[m] = np.round(after[m], 3)
    h = _hist(after)
    assert bte.tick_exp(h) == -4
    assert 0.25 < bte.grid_share(h, -3) < 0.5


def test_best_split_and_segments():
    labels = [-3] * 10 + [-2] * 10
    assert bte.best_split(labels)[:3] == (10, -3, -2)
    assert bte.best_split([-3] * 20) is None
    # a single odd day is noise, not a change
    assert bte.best_split([-3] * 9 + [-2] + [-3] * 10) is None
    # one noisy day on each side does not move the split
    noisy = [-3] * 5 + [-4] + [-3] * 4 + [-2] * 4 + [-3] + [-2] * 5
    assert bte.best_split(noisy)[:3] == (10, -3, -2)
    # a change on the last day only is not enough evidence
    assert bte.best_split([-3] * 19 + [-2]) is None
    two = [-3] * 10 + [-4] * 10 + [-3] * 10
    assert bte.segment_changes(two) == [(10, -3, -4), (20, -4, -3)]
    assert bte.segment_changes(noisy) == [(10, -3, -2)]
    assert bte.segment_changes([-3] * 19 + [-2]) == []
    assert bte.segment_changes([-3] * 9 + [-2] + [-3] * 10) == []
    assert bte.segment_changes([-3, -4] * 10) in ([], [(1, -3, -4)], [(2, -3, -4)])
    # a mixed event day labelled either way moves the change by at most that day
    assert bte.segment_changes([-3] * 10 + [-4] * 11) == [(10, -3, -4)]


def test_binomial_changepoint():
    n = np.full(48, 100)
    k = np.r_[np.full(13, 11), np.full(35, 86)]  # SOL-like increase at bin 13 (06:30)
    assert bte.binomial_changepoint(n, k) == 13
    assert bte.binomial_changepoint(n, np.full(48, 50)) == 0
    # empty bins carry no weight
    n2 = n.copy()
    n2[10:13] = 0
    assert bte.binomial_changepoint(n2, np.where(n2 == 0, 0, k)) in (10, 11, 12, 13)


def _day_bins(rng, change_bin, old_tick, new_tick, per_bin=200):
    bins = []
    for i in range(48):
        if i < change_bin:
            p = _walk(rng, per_bin, 0.5, old_tick)
        elif new_tick > old_tick:
            p = _walk(rng, per_bin, 0.5, new_tick, residual_tick=old_tick, residual_share=0.1)
        else:
            p = _walk(rng, per_bin, 0.5, new_tick)
        bins.append(_hist(p))
    return bins


@pytest.mark.parametrize("old,new", [(-3, -4), (-4, -3)])
def test_change_bin_locates_half_hour(old, new):
    rng = np.random.default_rng(4)
    bins = _day_bins(rng, 14, 10.0 ** old, 10.0 ** new)  # 07:00
    assert bte.change_bin(bins, old, new) == 14
    ticks = [bte.tick_exp(h) for h in bins]
    assert ticks[:14] == [old] * 14 and ticks[14:] == [new] * 34


def test_direction_rel_tick_status_factor():
    assert bte.direction(-3, -2) == "increase"
    assert bte.direction(-3, -4) == "cut"
    assert bte.direction(-3, -3) == "none"
    assert math.isclose(bte.rel_tick_bps(-3, 150.0), 0.0666666, rel_tol=1e-4)
    d = dt.date(2024, 10, 14)
    assert bte.status_for(d, d) == "verified"
    assert bte.status_for(d, d + dt.timedelta(1)) == "date-differs"
    assert bte.status_for(d, None) == "no-change"
    assert bte.within_factor(150, 100) and not bte.within_factor(250, 100)
    assert not bte.within_factor(0, 100)
    assert bte.fmt_tick(-4) == "0.0001" and bte.fmt_tick(1) == "10"


def test_waterfill_and_plan_days():
    cap = bte.waterfill_cap([10, 50, 100], 90)
    assert math.isclose(10 + 2 * cap, 90, rel_tol=1e-6)
    assert bte.waterfill_cap([1, 2], 10) == math.inf
    sizes = {o: 10.0 for o in range(-10, 11)}
    assert bte.plan_days(sizes, 35, bte.DAY_PRIORITY) == [0, -1, 1]
    assert bte.plan_days(sizes, 5, bte.DAY_PRIORITY, min_days=(0, -1)) == [0, -1]
    assert sorted(bte.plan_days(sizes, math.inf, bte.DAY_PRIORITY)) == list(range(-10, 11))


def test_regimes_match_rejects_a_split_without_a_change():
    rng = np.random.default_rng(5)
    bins = _day_bins(rng, 14, 1e-3, 1e-4)
    assert bte.regimes_match(bins, 14, -3, -4)
    flat = _day_bins(rng, 48, 1e-3, 1e-4)  # old tick all day
    cp = bte.change_bin(flat, -3, -4)
    assert not (0 < cp < 48 and bte.regimes_match(flat, cp, -3, -4))
