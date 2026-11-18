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
