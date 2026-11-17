"""Tests for Q13: break-even fee and order timing from Q11's cached predictions.

Contract under test, on synthetic prediction caches with a planted answer:

1. A predictor that always calls the right side of a known mean move gives the
   break-even fee (mean move - spread cost) / 2 exactly.
2. A useless predictor saves about 0 per order with a day-block interval
   containing 0; perfect foresight saves half the mean absolute move.
3. The report builds from a synthetic result and the verdict sentence flips
   between "pays at the assumed fee", "pays only below X bps" and "does not
   pay even at zero fee".
4. The Markdown has no em or en dashes, and a missing current cache key is
   skipped with a reason that lists the stale keys.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from microstructure.analyses import q11_mid_direction as q11
from microstructure.analyses import q13_break_even as q13
from microstructure.analyses.q13_report import break_even_lines, markdown
from microstructure.ml.evaluate import MS_PER_DAY

DAY0 = 19_500 * MS_PER_DAY  # an arbitrary UTC midnight


def _arrays(n: int, n_days: int, move: np.ndarray, spread: float,
            p_move: np.ndarray, p_up: np.ndarray, h: int = 10) -> dict[str, np.ndarray]:
    ts = DAY0 + (np.arange(n) * n_days // n) * MS_PER_DAY + 1000
    out = {"ts": ts, "label": np.sign(move).astype(np.int8),
           "move_bps": move.astype(np.float32),
           "spread_bps": np.full(n, spread, dtype=np.float32)}
    for m in q11.MODELS:
        out[f"{m}_move"] = p_move.astype(np.float32)
        out[f"{m}_up"] = p_up.astype(np.float32)
    return {f"h{h}_{k}": v for k, v in out.items()}


def _meta(thresholds: dict[str, float] | None = None, h: int = 10) -> dict:
    th = thresholds or {f"{q:g}": 0.0 for q in q11.TOP_FRACTIONS}
    return {"symbol": "SYNUSDT", "tick": 0.01, "spread": {"one_tick_time_share": 0.99},
            "test_days": [], "valid_days": [],
            "horizons": {str(h): {"thresholds": {m: dict(th) for m in q11.LEARNED}}}}


def test_known_edge_gives_the_analytic_break_even_fee():
    rng = np.random.default_rng(0)
    n, spread, edge = 20_000, 0.4, 1.6
    # The mid always moves up, by edge on average; the model always says up.
    move = np.abs(rng.normal(edge, 0.3, n))
    ones = np.ones(n)
    sym = q13.score_symbol(_meta(), _arrays(n, 10, move, spread, ones, ones), fee_bps=5.0,
                           n_boot=200)
    for r in sym["horizons"]["10"]["break_even"]["gbm_all"]:
        expected = (move.astype(np.float32).astype(np.float64).mean() - spread) / 2
        assert r["break_even_fee_bps"] == pytest.approx(expected, abs=1e-6)
        assert r["break_even_fee_ci95"][0] <= r["break_even_fee_bps"] <= r["break_even_fee_ci95"][1]
        assert r["pays_at_zero_fee"] and not r["pays_at_fee"]
        assert r["category"] == "pays_below_fee"
        assert r["required_multiple"] == pytest.approx(r["cost_bps"] / r["gross_bps"])
    # A cut-off above every score fires nothing and yields an empty cell.
    meta = _meta({"1": 0.0, "0.5": 0.0, "0.2": 0.0, "0.05": 2.0})
    sym = q13.score_symbol(meta, _arrays(n, 10, move, spread, ones, ones), 5.0, n_boot=50)
    assert sym["horizons"]["10"]["break_even"]["gbm_all"][-1]["n"] == 0


def test_useless_predictor_saves_nothing_and_perfect_foresight_hits_the_bound():
    rng = np.random.default_rng(1)
    n = 40_000
    move = rng.choice([-1.0, 0.0, 1.0], size=n, p=[0.4, 0.2, 0.4]) * rng.uniform(0.5, 1.5, n)
    # Scores carry no information about the move.
    p_move, p_up = rng.uniform(0.2, 0.9, n), rng.uniform(0.0, 1.0, n)
    sym = q13.score_symbol(_meta(), _arrays(n, 14, move, 0.3, p_move, p_up), 5.0, n_boot=500)
    t = sym["horizons"]["10"]["timing"]
    for r in t["models"]["gbm_all"]:
        lo, hi = r["saving"]["ci95"]
        assert lo <= 0 <= hi and abs(r["saving"]["estimate"]) < 0.01
        rlo, rhi = r["random"]["saving"]["ci95"]
        assert rlo <= 0 <= rhi
    mv = move.astype(np.float32).astype(np.float64)
    pf = t["perfect_foresight"]
    assert pf["saving"]["estimate"] == pytest.approx(0.5 * np.abs(mv).mean())
    assert pf["share_delayed"] == pytest.approx(0.5 * (mv != 0).mean())
    assert pf["share_worse_when_delayed"] == 0.0
    # A model that is told the sign reaches the bound exactly.
    oracle = np.where(move > 0, 1.0, 0.0)
    sym = q13.score_symbol(_meta(), _arrays(n, 14, move, 0.3, (move != 0) * 1.0, oracle), 5.0,
                           n_boot=100)
    best = sym["horizons"]["10"]["timing"]["models"]["gbm_all"][0]
    assert best["share_of_perfect"] == pytest.approx(1.0)


def _summary(gross: float, spread: float, fee: float = 5.0) -> dict:
    be = (gross - spread) / 2
    cell = {"top_fraction": 0.05, "threshold": 0.9, "n": 1000, "share_of_test": 0.05,
            "gross_bps": gross, "gross_ci95": [gross - 0.1, gross + 0.1],
            "spread_cost_bps": spread, "cost_bps": spread + 2 * fee, "hit_rate": 0.6,
            "net_bps": gross - spread - 2 * fee,
            "net_ci95": [gross - spread - 2 * fee - 0.2, gross - spread - 2 * fee + 0.2],
            "break_even_fee_bps": be, "break_even_fee_ci95": [be - 0.1, be + 0.1],
            "pays_at_zero_fee": gross > spread, "pays_at_fee": be > fee,
            "required_multiple": (spread + 2 * fee) / gross if gross > 0 else None,
            "required_multiple_zero_fee": spread / gross if gross > 0 else None,
            "category": q13.classify(be, fee)}
    saving = {"estimate": 0.05, "ci95": [0.01, 0.09], "n_days": 14}
    timing_row = {"top_fraction": 1.0, "threshold": 0.0, "share_delayed": 0.5, "n_delayed": 900,
                  "saving": saving, "sd_per_order": 1.0, "saving_when_delayed": 0.1,
                  "sd_when_delayed": 1.4, "share_worse_when_delayed": 0.4,
                  "saving_over_half_spread": 0.5, "share_of_perfect": 0.1,
                  "random": {"share_delayed": 0.5, "sd_per_order": 1.0,
                             "saving": {"estimate": 0.0, "ci95": [-0.02, 0.02], "n_days": 14}}}
    perfect = {**timing_row, "saving": {"estimate": 0.5, "ci95": [0.45, 0.55], "n_days": 14},
               "share_worse_when_delayed": 0.0}
    perfect.pop("random")
    sym = {"symbol": "SYNUSDT", "tick": 0.01, "one_tick_time_share": 0.99, "test_days": [],
           "valid_days": [],
           "horizons": {"10": {"n_test": 1000, "n_test_days": 14,
                               "break_even": {m: [cell] for m in q11.LEARNED},
                               "timing": {"mean_half_spread_bps": 0.1,
                                          "perfect_foresight": perfect,
                                          "models": {m: [timing_row] for m in q11.LEARNED}}}}}
    return {
        "config": {"taker_fee_bps": fee, "n_boot": 100, "q11_config": q13.Q11_DEFAULT_CONFIG,
                   "q11_cache_key": "abc", "horizons": [10], "models": list(q11.LEARNED),
                   "top_fractions": list(q11.TOP_FRACTIONS)},
        "symbols": [sym], "skipped": [{"symbol": "GONEUSDT", "reason": "no Q11 predictions"}],
        "q11_check": {"status": "not_checked", "reason": "Q11 JSON not found",
                      "by_model": {}, "mismatches": []},
        "verdict": q13.verdict([sym], fee), "q7": None,
    }


def test_report_verdict_flips_with_the_break_even_fee(tmp_path: Path):
    pays = " ".join(break_even_lines(_summary(gross=14.0, spread=1.0)))
    assert "pays at the assumed fee" in pays and "3 pay at the assumed" in pays
    below = " ".join(break_even_lines(_summary(gross=3.0, spread=1.0)))
    assert "pays only below 1.000 bps per side" in below and "0 pay at the assumed" in below
    none = " ".join(break_even_lines(_summary(gross=0.5, spread=1.0)))
    assert "does not pay even at zero fee" in none and "0 have a gross edge" in none

    s = _summary(gross=3.0, spread=1.0)
    md = markdown(s)
    assert "## Verdict" in md and "GONEUSDT" in md and "not** checked" in md
    assert chr(0x2014) not in md and chr(0x2013) not in md
    from microstructure.analyses.q13_report import write_outputs
    write_outputs(s, tmp_path)
    for ext in ("json", "md", "png"):
        assert (tmp_path / f"q13_break_even.{ext}").stat().st_size > 0


def test_run_q13_skips_a_symbol_without_the_current_key_and_checks_q11(tmp_path: Path):
    root, out = tmp_path / "data", tmp_path / "results"
    cache = root / "ml_cache" / "q11"
    cfg = q13.Q11_DEFAULT_CONFIG
    key = q11.config_key(cfg)
    rng = np.random.default_rng(2)
    n = 3000
    move = rng.normal(0, 1, n)
    meta = {**_meta(), "horizons": {str(h): _meta(h=h)["horizons"][str(h)]
                                    for h in cfg["horizons"]}}
    arrays = {}
    for h in cfg["horizons"]:
        arrays.update(_arrays(n, 7, move, 0.5, rng.uniform(0, 1, n), rng.uniform(0, 1, n), h))
    (cache / "SYNUSDT").mkdir(parents=True)
    np.savez(cache / "SYNUSDT" / f"pred_{key}.npz", **arrays)
    (cache / "SYNUSDT" / f"meta_{key}.json").write_text(json.dumps(meta))
    (cache / "OLDUSDT").mkdir(parents=True)
    np.savez(cache / "OLDUSDT" / "pred_deadbeef0000.npz", x=np.zeros(1))
    summary = q13.run_q13(root, out, ["SYNUSDT", "OLDUSDT"], n_boot=50)
    assert [s["symbol"] for s in summary["symbols"]] == ["SYNUSDT"]
    reason = summary["skipped"][0]["reason"]
    assert key in reason and "deadbeef0000" in reason
    assert summary["q11_check"]["status"] == "not_checked"
    md = (out / "q13_break_even.md").read_text()
    assert chr(0x2014) not in md and chr(0x2013) not in md

    # A Q11 JSON that disagrees with the cache stops the run.
    sym = summary["symbols"][0]
    fake = {"config": {"taker_fee_bps": 5.0, "n_boot": 50},
            "symbols": [{"symbol": "SYNUSDT", "horizons": {
                h: {"economics": {m: [{**r, "gross_bps": (r.get("gross_bps") or 0) + 1.0}
                                      for r in res["break_even"][m]] for m in q11.LEARNED}}
                for h, res in sym["horizons"].items()}}]}
    (out / "q11_mid_direction.json").write_text(json.dumps(fake))
    with pytest.raises(RuntimeError, match="does not reproduce"):
        q13.run_q13(root, out, ["SYNUSDT"], n_boot=50)
    # The same JSON with the true numbers matches.
    for h, res in sym["horizons"].items():
        for m in q11.LEARNED:
            fake["symbols"][0]["horizons"][h]["economics"][m] = res["break_even"][m]
    (out / "q11_mid_direction.json").write_text(json.dumps(fake))
    assert q13.run_q13(root, out, ["SYNUSDT"], n_boot=50)["q11_check"]["status"] == "matched"
