from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "c3_trump_tariff_local", ROOT / "research" / "politics" / "c3_trump_tariff_local.py")
c3 = importlib.util.module_from_spec(_spec)
sys.modules["c3_trump_tariff_local"] = c3
_spec.loader.exec_module(c3)
c1 = c3.c1
WEEK = c1.WEEK


def _fake_arr(n: int, seed: int = 0) -> tuple:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 1e-4, n)))
    vol = rng.uniform(1, 2, n)
    return c1.minute_arrays(close, vol, vol / 2), c1.valid_mask(close)


# ---------------------------------------------------------------- controls

def test_controls_stay_within_four_weeks_same_minute_of_week():
    n = 30 * WEEK
    arr, valid = _fake_arr(n)
    ev = np.array([10 * WEEK + 777, 15 * WEEK + 123, 20 * WEEK + 5000])
    run = c3.run_symbol(arr, valid, ev, np.array([], dtype=np.int64), None)
    assert run["ok"].all()
    ctrl = run["ctrl"]
    for i, m in enumerate(ev):
        c = ctrl[i][ctrl[i] >= 0]
        assert c.size == 8
        d = c - m
        assert (d % WEEK == 0).all()
        assert (np.abs(d) <= 4 * WEEK).all() and (d != 0).all()


def test_event_dropped_with_fewer_than_six_controls():
    n = 30 * WEEK
    arr, valid = _fake_arr(n)
    m = 10 * WEEK + 777
    # Trump posts near 3 of the 8 candidate weeks: only 5 remain, so the event is dropped
    own = np.array([m + j * WEEK + 30 for j in (-4, -1, 2)])
    run = c3.run_symbol(arr, valid, np.array([m]), own, None)
    assert run["win_ok"][0] and not run["ok"][0]
    own2 = own[:2]  # 6 remain: kept
    run2 = c3.run_symbol(arr, valid, np.array([m]), own2, None)
    assert run2["ok"][0]
    assert (run2["ctrl"][0] >= 0).sum() == 6


def test_only_trumps_own_posts_exclude_controls():
    n = 12 * WEEK
    valid = np.ones(n, bool)
    trump = np.array([5 * WEEK])
    elig = c3.control_eligible(valid, trump)
    assert not elig[5 * WEEK + 60] and elig[5 * WEEK + 61]
    assert not elig[5 * WEEK - 60] and elig[5 * WEEK - 61]
    # the function has no way to receive other people's posts: its only post input is
    # Trump's; an other-politician minute stays eligible
    other_minute = 7 * WEEK
    assert elig[other_minute]
    import inspect
    params = list(inspect.signature(c3.control_eligible).parameters)
    assert params == ["valid", "own_post_min", "barred"]


def test_trump_events_ignore_other_people(tmp_path):
    t0 = c3.c2.T0
    posts = [{"ts": t0 + dt.timedelta(days=10, minutes=k), "kind": "original",
              "text": "TARIFFS on everything" if k == 0 else "hello", "post_id": str(k)}
             for k in (0, 120)]
    for p in posts:
        p["minute"] = c3.c2.minute_of(p["ts"])
    ev = c3.trump_events(posts)
    assert [e["topic"] for e in ev] == ["tariffs", "other"]
    assert all(e["clean"] and e["in_period"] for e in ev)
    assert "overlap" not in ev[0]


def test_barred_span_removes_events_and_controls():
    n = 30 * WEEK
    arr, valid = _fake_arr(n)
    m = 10 * WEEK + 777
    barred = np.zeros(n, bool)
    barred[m - 10:m + 10] = True
    run = c3.run_symbol(arr, valid, np.array([m, m + WEEK]), np.array([], dtype=np.int64),
                        None, barred)
    assert not run["ok"][0] and run["ok"][1]
    assert m not in run["ctrl"][1]
    assert (run["ctrl"][1] >= 0).sum() == 7


# ---------------------------------------------------------------- decision rule

@pytest.mark.parametrize("diff,pmp,label", [
    ((1.0, 0.2, 2.0), (1.0, 0.1, 2.0), "supports an effect"),
    ((1.0, -0.2, 2.0), (1.0, 0.1, 2.0), "does not support an effect"),
    ((1.0, 0.2, 2.0), (1.0, -0.1, 2.0), "does not support an effect"),
    ((-1.0, -2.0, -0.2), (-1.0, -2.0, -0.1), "supports an effect"),
    ((1.0, None, None), (1.0, 0.1, 2.0), "does not support an effect"),
])
def test_decision_rule_wording_flips(diff, pmp, label):
    d = dict(zip(("mean", "lo", "hi"), diff, strict=True))
    p = dict(zip(("mean", "lo", "hi"), pmp, strict=True))
    v = c3.verdict(d, p)
    assert v["label"] == label
    assert f"**{label}**" in v["sentence"]
    if label == "supports an effect":
        assert "includes zero" not in v["sentence"]
    else:
        assert "includes zero" in v["sentence"] or "too few" in v["sentence"]


def test_refuses_when_followup_hash_changes(tmp_path):
    f = tmp_path / "FOLLOWUP.md"
    f.write_text("design", encoding="utf-8")
    with pytest.raises(SystemExit, match="refusing to run"):
        c3.check_inputs(f, "0" * 64, tmp_path, files={})
    ok = c3.c2.sha256(f)
    assert c3.check_inputs(f, ok, tmp_path, files={})[f.name] == ok


def test_followup_file_matches_frozen_hash():
    assert c3.c2.sha256(c3.FOLLOWUP) == c3.FOLLOWUP_SHA
