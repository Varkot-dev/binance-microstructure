"""Q15 report on a synthetic result dict: it builds, verdict sentences follow the
numbers (lock-box confirms vs reverses), and the Markdown has no em or en dashes."""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from microstructure.analyses import q15_market_evolution as q15
from microstructure.analyses import q15_report as rep

REPO = Path(__file__).resolve().parents[2]
DASHES = (chr(0x2014), chr(0x2013))


def _iv(b, lo, hi, **kw):
    return {"b": b, "lo": lo, "hi": hi, **kw}


def _est(b, lo, hi, perm_p=0.001, treated=6, batches=2):
    return _iv(b, lo, hi, G=20, treated=treated, batches=batches, pre_p=0.5,
               perm={"p": perm_p, "lo": lo, "hi": hi}, wild={"p": perm_p, "lo": lo, "hi": hi})


def _models(scale: float, treated_inc: int = 16):
    """cut, increase and pooled estimates; scale multiplies every effect (sign flips)."""
    def m(base, w):
        b = scale * base
        return _est(b, b - w, b + w)
    cut = {"repeat_rate": m(7.5, 1.0), "sign_acf_lag1": m(16.0, 1.8), "acc_refit": m(5.9, 1.1),
           "refit_excess": m(-2.2, 0.4), "unchanged": m(-31.5, 1.7), "log_rel_tick": m(-2.26, 0.03)}
    inc = {k: {**v, "b": -v["b"] * 0.75, "lo": -v["hi"] * 0.75, "hi": -v["lo"] * 0.75,
               "treated": treated_inc} for k, v in cut.items()}
    pooled = {"repeat_rate": m(-3.15, 0.4), "sign_acf_lag1": m(-6.7, 0.7),
              "acc_refit": m(-2.5, 0.4), "refit_excess": m(0.84, 0.17),
              "unchanged": m(12.8, 0.8), "log_rel_tick": m(0.87, 0.05)}
    for d in (cut, pooled):
        for v in d.values():
            v.update(treated=113 if d is pooled else 97, batches=35)
    return {"cut": cut, "increase": inc, "pooled": pooled}


def _arm(batch, direction, b, treated=3):
    o = {"b": b, "lo": b - 4, "hi": b + 4, "perm_p": 0.03, "perm_lo": b - 5, "perm_hi": b + 5,
         "pre_p": 0.4}
    return {"batch": batch, "direction": direction, "treated": treated, "controls": 9,
            "dose": -2.3 if direction == "cut" else 2.3, "repeat_rate": o, "acc_refit": o}


def synthetic(lockbox_scale: float | None = 1.0) -> dict:
    cs = {}
    for per, held in (("cross_2023", -3.9), ("cross_2026", -1.9)):
        for name, raw in (("repeat_rate", -0.2), ("acc_gbm", -0.5)):
            cs[f"{per}|{name}|raw"] = _iv(raw, raw - 1, raw + 1, n=200)
            cs[f"{per}|{name}|activity held fixed"] = _iv(held, held - 1, held + 1, n=200)
    r = {
        "question": "Why did predictability rise, and does tick size cause sign persistence?",
        "inputs": {k: f"path/{k}" for k in ("e0", "e1", "e2", "e3", "e4", "e5", "lockbox")},
        "q10": {"n": 10, "months": ["2023-06", "2025-07"],
                "mean_acc_pp": {"2023-06": 61.7, "2025-07": 66.4}, "from": "2023-06",
                "to": "2025-07", "d_acc": _iv(4.7, 2.7, 7.1), "d_log_rel_tick": _iv(-1.0, -1.4, -0.6),
                "d_log_size": _iv(-0.05, -0.4, 0.4)},
        "survivors": {"n": 136, **{k: {**_iv(b, b - 0.2, b + 0.2), "share_down": s}
                                   for k, b, s in (("acc", 3.4, 0.26), ("rep", 4.7, 0.2),
                                                   ("lsize", -1.83, 0.98),
                                                   ("ltick", 0.1, 0.48))}},
        "cross_section": {f"{p}|{y}": {"n": 200, "log_size": _iv(-3.0, -4.0, -2.0),
                                       "log_rel_tick": _iv(-2.0, -3.0, -1.0)}
                          for p in ("cross_2023", "cross_2026") for y in ("acc", "rep")},
        "e4": {"composition": {"acc_2023": 61.69, "acc_2026": 64.44, "total": _iv(2.75, 2.07, 3.49),
                               "exits": _iv(-0.17, -0.41, 0.07), "within": _iv(3.41, 2.59, 4.27),
                               "entries": _iv(-0.48, -1.04, 0.07)},
               "noise_floor": _iv(0.55, -0.12, 1.23),
               "regression": {k: {m: _iv(-1.0, -2.0, -0.5) for m in (
                   "a1_pooled", "a2_pooled_month", "b1_contract_fe", "b2_two_way_fe",
                   "b3_ten_coins")} for k in ("log_size", "log_rel_tick")},
               "gelbach": {"rise": _iv(3.41, 2.5, 4.33), "unexplained": _iv(-2.95, -4.8, -0.96),
                           "trade_size": _iv(7.8, 5.81, 9.59), "rel_tick": _iv(-0.06, -0.37, 0.08)},
               "implied_10x_cut": {"total": _iv(0.43, -1.75, 2.62),
                                   "partial": _iv(1.26, -1.46, 3.98)}},
        "e3": {"2026-03-05": {"label": "x", "treated": 12, "controls": 62,
                              "repeat_rate": _iv(6.7, 4.1, 9.2), "acc_logit": _iv(-0.7, -4.4, 2.9),
                              "acc_refit": _iv(3.9, 1.0, 6.9)}},
        "e5": {"models": _models(1.0), "cross_section": cs,
               "arms": [_arm("2024-02-05", "cut", 14.0), _arm("2025-09-03", "increase", -5.7),
                        _arm("2024-10-14", "increase", -11.0, treated=1)]},
        "tick_accounting": {g: {"repeat_rate": _iv(b * 1.2, b - 1, b + 1),
                                "acc_refit": _iv(b, b - 1, b + 1)}
                            for g, b in (("survivors", -0.26), ("q10", 2.6))},
    }
    if lockbox_scale is not None:
        lb_models = _models(lockbox_scale)
        lb_models.pop("increase")
        fin = {"run": 1, "rerun_reason": None, "frozen_commit": "abc1234", "head": "def5678abc",
               "models": lb_models, "coverage": {"rows": 320, "expected": 322, "contracts": 23,
                                                 "scored_median": 6450.0},
               "arms": [_arm("2026-08-06", "cut", 3.0 * lockbox_scale),
                        _arm("2026-10-15", "cut", 4.0 * lockbox_scale)],
               "plan_arms": [{"batch": "2026-08-06", "treated": ["A", "B", "C"],
                              "controls": ["D"] * 9, "n_eligible": 8}]}
        r["lockbox"] = {"runs": [fin], "final": fin, "downloaded_bytes": 7e7}
    else:
        r["lockbox"] = {}
    return r


def _build(tmp_path: Path, r: dict) -> str:
    r = copy.deepcopy(r)
    r["verdict"] = rep.verdict_paragraph(r)
    md = tmp_path / "q15.md"
    rep.write_markdown(md, r)
    rep.plot(tmp_path / "q15.png", r)
    assert (tmp_path / "q15.png").stat().st_size > 10_000
    return md.read_text()


def test_report_builds_from_synthetic_dict(tmp_path):
    text = _build(tmp_path, synthetic(1.0))
    for h in ("## Question", "## Method", "## Verdict", "## Results", "### 4. Lock-box",
              "### 5. Cross-sectional versus experimental slope",
              "### 6. What is and is not explained", "## Caveats"):
        assert h in text
    assert "is not price predictability" in text
    assert not any(d in text for d in DASHES)


def test_lockbox_confirm_vs_reverse_flips_verdict(tmp_path):
    conf, rev = synthetic(1.0), synthetic(-1.0)
    assert rep.lockbox_overall(conf) == "confirm"
    assert rep.lockbox_overall(rev) == "reverse"
    t_conf, t_rev = rep.verdict_paragraph(conf), rep.verdict_paragraph(rev)
    assert "Both primary outcomes confirm e5 out of sample" in t_conf
    assert "Tick size does cause sign persistence" in t_conf
    assert "reverses the e5 estimate out of sample" in t_rev
    assert "is not established" in t_rev and "Tick size does cause" not in t_rev
    # the markdown reports the rule's word per outcome
    assert "| confirm |" in _build(tmp_path, conf)
    md_rev = _build(tmp_path, rev)
    assert "| reverse |" in md_rev
    assert not any(d in md_rev for d in DASHES)


def test_lockbox_weaken_when_not_decisive_and_when_absent(tmp_path):
    r = synthetic(1.0)
    rr = r["lockbox"]["final"]["models"]["pooled"]["repeat_rate"]
    rr.update(b=-1.5, lo=-3.3, hi=0.2)
    rr["perm"]["p"] = 0.085
    assert rep.lockbox_overall(r) == "weaken"
    assert "weakens rather than confirms" in rep.lockbox_sentence(r)
    assert "very likely causes" in rep.answer_sentence(r)
    none = synthetic(None)
    assert rep.lockbox_overall(none) == "not run"
    assert "has not been run" in rep.verdict_paragraph(none)
    assert not any(d in _build(tmp_path, none) for d in DASHES)


def test_classify_matches_e5_rule():
    path = REPO / "research" / "market_evolution" / "e5_stacked_events.py"
    if not path.exists():
        pytest.skip("e5 not present")
    spec = importlib.util.spec_from_file_location("e5_for_test", path)
    e5 = importlib.util.module_from_spec(spec)
    sys.modules["e5_for_test"] = e5
    spec.loader.exec_module(e5)
    ref = {"b": -3.0}
    cases = [(_est(-2, -3, -1), "confirm"), (_est(-2, -3, -1, perm_p=0.2), "weaken"),
             (_est(-1, -3, 1), "weaken"), (_est(2, 1, 3), "reverse"), (_est(1, -1, 3), "weaken")]
    for lb, want in cases:
        assert rep.classify(lb, ref) == want
        assert e5.lockbox_verdict(lb, ref)["verdict"] == want
    assert rep.classify({}, ref) == "not estimable"


def test_parse_e4_reads_tables():
    md = "## 1. Composition split\n\n| outcome, statistic | 2023-06 | 2026-07 | total change | exits | within | entries |\n|---|---|---|---|---|---|---|\n| accuracy, mean | 61.69 | 64.44 | +2.75 (+2.07 to +3.49) | -0.17 (-0.41 to +0.07) | +3.41 (+2.59 to +4.27) | -0.48 (-1.04 to +0.07) |\n\nOn the 10 coins, 2023-06 to 2023-07 moves mean accuracy by +0.55 pp (-0.12 to +1.23).\n\n| driver | step | (a1) pooled | (a2) | (b1) | (b2) | (b3) |\n|---|---|---|---|---|---|---|\n| log median trade size | per | -4.36 (-5.28 to -3.45) | -5.35 (-6.22 to -4.48) | -3.37 (-4.31 to -2.43) | -3.91 (-4.85 to -2.98) | -1.42 (-7.18 to +4.34) |\n| log relative tick | per | -1.57 (-2.02 to -1.12) | -1.53 (-2.03 to -1.02) | -0.94 (-2.10 to +0.22) | -0.50 (-1.58 to +0.59) | -1.27 (-2.33 to -0.21) |\n\n**Main: survivors** (272 rows)\n\n| term | pp | 95% | share |\n|---|---|---|---|\n| 2026 coefficient, no drivers | +3.41 | +2.50 to +4.33 | 100% |\n| 2026 coefficient, with drivers (unexplained) | -2.95 | -4.80 to -0.96 | -86% |\n| group: trade size (log size + under $1k) | +7.80 | +5.81 to +9.59 | 229% |\n| group: relative tick | -0.06 | -0.37 to +0.08 | -2% |\n\n| model | implied effect of a 10x cut (pp) | 95% |\n|---|---|---|\n| survivors, contract FE + 2026 dummy, relative tick only (total effect) | +0.43 | -1.75 to +2.62 |\n| survivors, all six drivers (partial: trade size etc. held fixed) | +1.26 | -1.46 to +3.98 |\n"
    e4 = q15.parse_e4(md)
    assert e4["composition"]["within"] == {"b": 3.41, "lo": 2.59, "hi": 4.27}
    assert e4["noise_floor"]["b"] == 0.55
    assert e4["regression"]["log_size"]["b1_contract_fe"]["b"] == -3.37
    assert e4["gelbach"]["trade_size"]["lo"] == 5.81
    assert e4["implied_10x_cut"]["partial"]["hi"] == 3.98


def test_tick_accounting_is_change_times_slope():
    rng = np.random.default_rng(0)
    d = q15._boot_mean(rng.normal(-1.0, 0.3, 50), rng)
    out = q15.tick_accounting(d, {"b": -2.5, "lo": -2.9, "hi": -2.1})
    assert out["b"] == pytest.approx(d["b"] * -2.5)
    assert out["lo"] < out["b"] < out["hi"]
