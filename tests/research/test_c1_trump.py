from __future__ import annotations

import datetime as dt
import importlib.util
import inspect
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "c1_trump_posts", ROOT / "research" / "politics" / "c1_trump_posts.py")
c1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c1)


def _post(minutes: float, kind: str = "original", text: str = "hello", pid: int = 0) -> dict:
    ts = c1.T0 + dt.timedelta(minutes=minutes)
    return {"ts": ts, "minute": int(minutes // 1), "kind": kind, "text": text,
            "post_id": str(pid or int(minutes * 1000) + 1)}


# ---------------------------------------------------------------- event merging

def test_merge_chains_within_five_minutes_and_keeps_first_time():
    posts = [_post(1000), _post(1003), _post(1007.5), _post(1030), _post(1200)]
    ev = c1.build_events(posts)
    assert len(ev) == 3
    assert ev[0]["minute"] == 1000 and ev[0]["n_posts"] == 3  # chained 0, +3, +7.5
    assert ev[1]["minute"] == 1030 and not ev[1]["clean"]  # 22.5 min after last post
    assert ev[2]["minute"] == 1200 and ev[2]["clean"]  # 170 min later
    assert ev[0]["clean"]


def test_gap_just_over_five_minutes_splits():
    ev = c1.build_events([_post(100), _post(105.02)])
    assert len(ev) == 2


def test_reposts_are_not_events_and_quotes_are():
    posts = [_post(100, "repost"), _post(300, "quote"), _post(500, "reply")]
    ev = c1.build_events(posts)
    assert [e["minute"] for e in ev] == [300]


def test_event_topic_is_first_in_priority_among_merged_posts():
    posts = [_post(100, text="big tariffs"), _post(102, text="Bitcoin is great")]
    assert c1.build_events(posts)[0]["topic"] == "crypto"


# ---------------------------------------------------------------- control windows

def test_controls_never_within_sixty_minutes_of_any_post():
    rng = np.random.default_rng(0)
    n = 40 * c1.WEEK
    post_min = np.sort(rng.integers(0, n, 3000))
    close = np.exp(np.cumsum(rng.normal(0, 1e-3, n)))
    close[rng.integers(0, n, 200)] = np.nan
    elig = c1.valid_mask(close) & ~c1.busy_mask(post_min, n)
    anchors = rng.choice(post_min[(post_min > 10) & (post_min < n - 100)], 300)
    ctrl = c1.pick_controls(anchors, elig)
    used = ctrl[ctrl >= 0]
    assert used.size > 1000
    d = np.abs(used[:, None] - post_min[None, :]).min(axis=1)
    assert (d > c1.BUSY_MIN).all()
    assert elig[used].all()
    # every control is a whole number of weeks from its anchor, never the anchor itself
    off = ctrl - anchors[:, None]
    assert ((off[ctrl >= 0] % c1.WEEK) == 0).all() and (off[ctrl >= 0] != 0).all()


def test_busy_mask_edges():
    m = c1.busy_mask(np.array([100]), 300)
    assert m[40] and m[160] and not m[39] and not m[161]


# ---------------------------------------------------------------- planted effect

def _synthetic(effect: float, seed: int):
    rng = np.random.default_rng(seed)
    n = 30 * c1.WEEK
    r = rng.normal(0, 5e-4, n)
    vol = rng.gamma(2.0, 50.0, n)
    tb = vol * rng.uniform(0.3, 0.7, n)
    ev = np.sort(rng.choice(np.arange(20 * 1440, n - 20 * 1440, 400), 250, replace=False))
    for m in ev:
        r[m + 1:m + 6] *= effect
    close = 100 * np.exp(np.cumsum(r))
    arr = c1.minute_arrays(close, vol, tb)
    elig = c1.valid_mask(close) & ~c1.busy_mask(ev, n)
    ctrl = c1.pick_controls(ev, elig)
    return c1.abnormal(arr, ev, ctrl)


def test_planted_effect_is_recovered():
    ab = _synthetic(effect=4.0, seed=1)
    x = ab["post5"]["rv"]
    lo, _hi = c1.boot_mean(x, B=2000)
    # true rv over 5 minutes is about sqrt(5)*5 bps = 11.2 bps; x4 raises it by ~33.5 bps
    assert lo > 20 and 25 < np.nanmean(x) < 45
    lo_pre, hi_pre = c1.boot_mean(ab["pre5"]["rv"], B=2000)
    assert lo_pre < 0 < hi_pre


def test_no_effect_gives_interval_containing_zero():
    ab = _synthetic(effect=1.0, seed=2)
    for k in ("rv", "absret", "ret"):
        lo, hi = c1.boot_mean(ab["post5"][k], B=2000)
        assert lo < 0 < hi, k


def test_placebo_p_flags_shift_and_not_null():
    rng = np.random.default_rng(3)
    pool = rng.normal(0, 1, 5000)
    assert c1.placebo_p(0.0, pool, 100, B=2000)["p"] > 0.5
    assert c1.placebo_p(0.5, pool, 100, B=2000)["p"] < 0.01


# ---------------------------------------------------------------- topic rules

def test_topic_rules_use_text_only():
    params = list(inspect.signature(c1.topic_of).parameters)
    assert params == ["text"]
    text = "We will put Tariffs on China"
    a = c1.build_events([_post(100, "original", text)])[0]["topic"]
    b = c1.build_events([_post(90_000, "quote", text)])[0]["topic"]
    assert a == b == "tariffs"


def test_topic_examples():
    assert c1.topic_of("THANK YOU, BITCOIN 2024!") == "crypto"
    assert c1.topic_of("My NEW Official $TRUMP Meme") == "crypto"
    assert c1.topic_of("Crypto and tariffs together") == "crypto"
    assert c1.topic_of("Jerome \"Too Late\" Powell must cut") == "fed"
    assert c1.topic_of("before it is too late!") == "other"
    assert c1.topic_of("DOGE is cutting waste") == "other"
    assert c1.topic_of("a 25% TARIFF on steel") == "tariffs"
    assert c1.topic_of("") == "other"
    assert c1.topic_of("sbitcoinx") == "other"  # word boundaries


def test_kind_mapping():
    known = {"realDonaldTrump", "RSBN"}
    assert c1.classify_kind("RT @realDonaldTrumpThe Senate must", known) == (
        "repost", "realDonaldTrump")
    assert c1.classify_kind(
        "RT: https://truthsocial.com/users/RSBN/statuses/1", known) == ("repost", "RSBN")
    assert c1.classify_kind("wow https://truthsocial.com/@catturd2/113907502782417492",
                            known) == ("quote", "catturd2")
    assert c1.classify_kind("Hello America", known) == ("original", "")
    assert c1.fix_mojibake("â\u0080\u009cHiâ\u0080\u009d") == "“Hi”"
