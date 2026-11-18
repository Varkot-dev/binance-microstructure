from __future__ import annotations

import csv
import datetime as dt
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "c2_ranking", ROOT / "research" / "politics" / "c2_ranking.py")
c2 = importlib.util.module_from_spec(_spec)
sys.modules["c2_ranking"] = c2
_spec.loader.exec_module(c2)

B_TEST = 400


def _pool(seed: int = 1, n: int = 5000, sd: float = 5.0) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, sd, n)


# ---------------------------------------------------------------- shrinkage

def test_shrinkage_pulls_few_post_person_toward_mean():
    rng = np.random.default_rng(3)
    samples = {f"big{i}": rng.normal(mu, 5.0, 400) for i, mu in enumerate((0.0, 0.5, 1.0, 1.5))}
    samples["few"] = rng.normal(0.0, 5.0, 12) + 6.0  # 12 events, large raw mean
    pools = {k: _pool() for k in samples}
    res = c2.rank_people(samples, pools, B=B_TEST)
    rows, m = res["people"], res["prior"]["m"]
    assert res["prior"]["applied"]
    few = rows["few"]
    assert abs(few["shrunk"] - m) < 0.6 * abs(few["raw"] - m)
    assert few["factor"] < min(rows[k]["factor"] for k in rows if k != "few")
    for k in rows:  # every shrunken effect lies between the raw value and the prior mean
        lo, hi = sorted((rows[k]["raw"], m))
        assert lo - 1e-9 <= rows[k]["shrunk"] <= hi + 1e-9


def test_eb_fit_vectorised_matches_scalar_and_skips_small_j():
    b = np.array([[1.0, 2.0, 5.0], [0.0, 0.0, 3.0]])
    s = np.array([[0.5, 0.5, 2.0], [1.0, 1.0, 1.0]])
    both = c2.eb_fit(b, s)["shrunk"]
    for i in range(2):
        np.testing.assert_allclose(both[i], c2.eb_fit(b[i], s[i])["shrunk"])
    two = c2.eb_fit(np.array([1.0, 3.0]), np.array([1.0, 1.0]))
    assert not two["applied"]
    np.testing.assert_allclose(two["shrunk"], [1.0, 3.0])


# ---------------------------------------------------------------- ranking, FDR

def test_planted_effect_ranks_first_and_null_person_not_significant():
    rng = np.random.default_rng(8)
    samples = {"planted": rng.normal(8.0, 5.0, 300)}
    for i in range(4):
        samples[f"null{i}"] = rng.normal(0.0, 5.0, 300)
    pools = {k: _pool(seed=11) for k in samples}
    res = c2.rank_people(samples, pools, B=B_TEST)
    p = res["people"]["planted"]
    assert p["rank"] == 1 and p["rank_lo"] == 1 and p["rank_hi"] == 1
    assert p["q"] < 0.05
    for i in range(4):
        assert res["people"][f"null{i}"]["q"] > 0.05
    assert c2.answer(res, {}).startswith("planted moves crypto the most")


def test_no_effect_everywhere_gives_the_null_sentence():
    rng = np.random.default_rng(5)
    samples = {f"p{i}": rng.normal(0.0, 5.0, 200) for i in range(3)}
    res = c2.rank_people(samples, {k: _pool(seed=2) for k in samples}, B=B_TEST)
    assert all(r["q"] > 0.05 for r in res["people"].values())
    assert c2.answer(res, {}).startswith("No politician's posts are distinguishable")


def test_bh_matches_hand_computation():
    q = c2.bh([0.01, 0.04, 0.03, 0.5])
    np.testing.assert_allclose(q, [0.04, 0.16 / 3, 0.16 / 3, 0.5])


# ---------------------------------------------------------------- overlap rule

def _p(person_min: float, kind: str = "original", text: str = "hello") -> dict:
    ts = c2.T0 + dt.timedelta(minutes=person_min)
    return {"ts": ts, "minute": int(person_min // 1), "kind": kind, "text": text,
            "post_id": str(int(person_min * 1000) + 1)}


def test_cross_person_posts_within_five_minutes_are_excluded_for_both():
    people = {
        "A": {"group": "g", "posts": [_p(10_000), _p(20_000), _p(30_000)]},
        "B": {"group": "g", "posts": [_p(10_004), _p(20_006), _p(29_995, kind="repost")]},
    }
    ev = c2.build_person_events(people)
    a, b = ev["A"], ev["B"]
    assert a[0]["overlap"] and not a[0]["clean2"]  # B posted 4 minutes later
    assert b[0]["overlap"] and not b[0]["clean2"]
    assert not a[1]["overlap"] and a[1]["clean2"]  # 6 minutes apart: no overlap
    assert not b[1]["overlap"]
    assert not a[2]["overlap"]  # reposts never count
    assert len(b) == 2  # and are never events


def test_overlap_window_spans_the_whole_merged_event():
    people = {"A": {"group": "g", "posts": [_p(1000), _p(1004), _p(1008)]},
              "B": {"group": "g", "posts": [_p(1012.5)]}}
    ev = c2.build_person_events(people)
    assert ev["A"][0]["n_posts"] == 3 and ev["A"][0]["overlap"]  # 4.5 min after last post


# ---------------------------------------------------------------- index has no text

COLS = ["platform", "handle", "post_id", "url", "created_at_utc", "text", "kind",
        "quoted_or_reposted_handle", "has_media", "collected_at_utc"]


def test_index_never_contains_text(tmp_path):
    posts, out = tmp_path / "posts", tmp_path / "idx"
    posts.mkdir()
    secret = ["Bitcoin to the moon SECRETPHRASE1", "Tariffs on everything SECRETPHRASE2"]
    rows = [{"platform": "x", "handle": "Someone", "post_id": str(100 + i),
             "url": f"https://x.com/Someone/status/{100 + i}",
             "created_at_utc": f"2025-03-0{i + 1}T12:00:00Z", "text": t, "kind": "original",
             "quoted_or_reposted_handle": "", "has_media": "false",
             "collected_at_utc": "2026-11-01T00:00:00Z"} for i, t in enumerate(secret)]
    with (posts / "x_Someone.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    done, failed = c2.index_all(posts, out)
    assert not failed and len(done) == 1
    body = done[0].read_text(encoding="utf-8")
    assert "SECRETPHRASE" not in body and "moon" not in body
    with done[0].open(newline="", encoding="utf-8") as f:
        got = list(csv.DictReader(f))
    assert list(got[0]) == c2.INDEX_COLUMNS and "text" not in got[0]
    assert [r["topic"] for r in got] == ["crypto", "tariffs"]


def test_index_refuses_invalid_file(tmp_path):
    posts = tmp_path / "posts"
    posts.mkdir()
    (posts / "x_Bad.csv").write_text("not,the,header\n1,2,3\n", encoding="utf-8")
    done, failed = c2.index_all(posts, tmp_path / "idx")
    assert not done and len(failed) == 1


# ---------------------------------------------------------------- hash refusal

def test_refuses_when_preregistration_changed(tmp_path):
    f = tmp_path / "PREREGISTRATION_RANKING.md"
    f.write_text("original\n", encoding="utf-8")
    good = c2.sha256(f)
    assert c2.check_prereg(f, good) == good
    f.write_text("original, edited after looking\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        c2.check_prereg(f, good)


def test_committed_preregistration_matches_recorded_hash():
    assert c2.check_prereg() == c2.PREREG_SHA


def test_addenda_listed_with_hash(tmp_path):
    (tmp_path / "PREREGISTRATION_RANKING.md").write_text("main", encoding="utf-8")
    (tmp_path / "PREREGISTRATION_ADDENDUM_X.md").write_text("add", encoding="utf-8")
    got = c2.addenda(tmp_path)
    assert [a["file"] for a in got] == ["PREREGISTRATION_ADDENDUM_X.md"]
    assert got[0]["sha256"] == c2.sha256(tmp_path / "PREREGISTRATION_ADDENDUM_X.md")


# ---------------------------------------------------------------- local controls (deviation)

WEEK = 7 * 1440


def test_committed_deviation_matches_recorded_hash():
    assert c2.check_deviation() == c2.DEVIATION_SHA


def test_local_controls_never_leave_the_four_week_band():
    rng = np.random.default_rng(11)
    n = 30 * WEEK
    eligible = rng.random(n) < 0.7
    anchors = rng.integers(0, n, 5000)
    ctrl, enough = c2.pick_local_controls(anchors, eligible)
    assert ctrl.shape == (anchors.size, 8)
    has = ctrl >= 0
    d = ctrl - anchors[:, None]
    assert np.all(d[has] % WEEK == 0)
    assert np.all((np.abs(d[has]) >= WEEK) & (np.abs(d[has]) <= 4 * WEEK))
    assert np.all(eligible[ctrl[has]])
    np.testing.assert_array_equal(enough, has.sum(axis=1) >= 6)
    assert enough.any() and (~enough).any()
    # near the sample edges fewer candidates exist, so fewer than 6 can be eligible
    _, edge = c2.pick_local_controls(np.array([10, n - 10]), np.ones(n, bool))
    assert not edge.any()


def _prices(sd: np.ndarray, seed: int) -> tuple[dict, np.ndarray]:
    r = np.random.default_rng(seed).normal(0.0, 1.0, sd.size) * sd
    close = 100.0 * np.exp(np.cumsum(r) / 1e4)
    vol = np.ones(sd.size)
    arr = c2.c1.minute_arrays(close, vol, 0.5 * vol)
    return arr, c2.c1.valid_mask(close)


def _events(rng, lo_week: int, hi_week: int, k: int) -> np.ndarray:
    ev = np.sort(rng.choice(np.arange(lo_week * WEEK, hi_week * WEEK, 120), k, replace=False))
    return ev + rng.integers(0, 30, k)


def test_calm_year_person_is_zero_with_local_but_negative_with_global_controls():
    # calm weeks 0..11 (sd 2 bps per minute), volatile from week 12 (sd 10); the person
    # posts only in weeks 4..7 and has no effect at all
    n = 20 * WEEK
    sd = np.where(np.arange(n) < 12 * WEEK, 2.0, 10.0)
    arr, valid = _prices(sd, seed=5)
    rng = np.random.default_rng(6)
    ev = _events(rng, 4, 8, 150)
    g = c2.person_run(arr, valid, ev, ev, None, False)
    xg = g["ab"]["post5"]["rv"][g["ok"]]
    busy = c2.c1.busy_mask(ev, n)
    loc = c2.person_run_local(arr, valid, ev, busy, busy, None, False)
    xl = loc["ab"]["post5"]["rv"][loc["ok"]]
    assert xg.size > 100 and xl.size > 100
    se_l = xl.std(ddof=1) / np.sqrt(xl.size)
    assert xg.mean() < -3.0  # global controls reach into the volatile weeks
    assert abs(xl.mean()) < max(0.5, 3 * se_l)  # local controls stay in the calm weeks


def test_post_minus_pre_removes_a_planted_level_shift():
    n = 12 * WEEK
    base = np.full(n, 2.0)
    rng = np.random.default_rng(9)
    ev = _events(rng, 4, 8, 200)
    level = base.copy()  # volatility level raised from -20 to +20 minutes: no post effect
    for m in ev:
        level[m - 20:m + 21] = 6.0
    effect = level.copy()  # plus a real effect in minutes +1..+5 only
    for m in ev:
        effect[m + 1:m + 6] = 12.0
    busy = c2.c1.busy_mask(ev, n)
    out = {}
    for name, sd in (("level", level), ("effect", effect)):
        arr, valid = _prices(sd, seed=10)
        run = c2.person_run_local(arr, valid, ev, busy, busy, None, False)
        ab = {w: run["ab"][w]["rv"][run["ok"]] for w in ("post5", "pre5", "pmp")}
        np.testing.assert_allclose(ab["pmp"], ab["post5"] - ab["pre5"])
        out[name] = {w: (v.mean(), v.std(ddof=1) / np.sqrt(v.size)) for w, v in ab.items()}
    lv = out["level"]
    assert lv["post5"][0] > 5.0 and lv["pre5"][0] > 5.0  # the level shows up in both
    assert abs(lv["pmp"][0]) < max(0.5, 3 * lv["pmp"][1])  # and cancels in the difference
    assert out["effect"]["pmp"][0] > 5.0  # a real post effect survives
