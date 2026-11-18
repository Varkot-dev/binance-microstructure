"""Offline synthetic tests for the stacked tick-change event study (e5_stacked_events.py)."""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

_DIR = Path(__file__).resolve().parents[2] / "research" / "market_evolution"
_spec = importlib.util.spec_from_file_location("e5_stacked_events", _DIR / "e5_stacked_events.py")
e5 = importlib.util.module_from_spec(_spec)
sys.modules["e5_stacked_events"] = e5
_spec.loader.exec_module(e5)

LN10 = math.log(10)


def _stacked(beta: float, batches, seed=0, n_control=6, noise=0.5):
    """batches: list of (name, [dose of each treated contract]); per-log-point effect beta.

    Controls are shared across batches by name (C0, C1, ...) so clustering by contract
    matters; each batch has its own contract and day effects.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for b, doses in batches:
        units = [(f"T{b}_{i}", d) for i, d in enumerate(doses)]
        units += [(f"C{i}", 0.0) for i in range(n_control)]
        g = {r: rng.normal(0, 1) for r in e5.GRID}
        for s, d in units:
            a = rng.normal(0, 2)
            for r in e5.GRID:
                y = a + g[r] + beta * d * (r > 0) + rng.normal(0, noise)
                rows.append({"batch": b, "symbol": s, "rel": r, "year": int(b[:4]),
                             "treated": int(d != 0), "dose": d,
                             "cut_arm": int(any(x < 0 for x in doses)),
                             "inc_arm": int(any(x > 0 for x in doses)), "repeat_rate": y})
    return e5.columns(rows)


BATCHES = [("2024-01-01", [-LN10] * 4), ("2024-03-01", [-LN10] * 3),
           ("2025-01-01", [LN10] * 3), ("2025-05-01", [-LN10, -LN10, LN10]),
           ("2026-01-01", [LN10, LN10, -LN10, -LN10])]


def test_pooled_recovers_planted_signed_effect():
    beta = -1.5  # pp per log point of relative tick: a cut (dose -2.30) adds +3.45 pp
    col = _stacked(beta, BATCHES, seed=1)
    o = e5.estimate(col, "pooled", "repeat_rate", B=299, wild=False)
    assert abs(o["b"] - beta) < 0.15
    assert o["lo"] < beta < o["hi"] and o["hi"] < 0
    assert o["perm"]["p"] < 0.02 and o["perm"]["lo"] < beta < o["perm"]["hi"]
    assert o["pre_p"] > 0.01
    cut = e5.estimate(col, "cut", "repeat_rate", B=199, wild=False, es=False)
    inc = e5.estimate(col, "increase", "repeat_rate", B=199, wild=False, es=False)
    assert abs(cut["b"] - beta * -LN10) < 0.4 and cut["lo"] > 0
    assert abs(inc["b"] - beta * LN10) < 0.4 and inc["hi"] < 0
    # the cut model never uses an increase-treated contract, and vice versa
    m = e5.subpanel(col, "cut")
    assert not (col["dose"][m] > 0).any()
    m = e5.subpanel(col, "increase")
    assert not (col["dose"][m] < 0).any()


def test_placebo_batch_interval_contains_zero():
    col = _stacked(-1.5, BATCHES, seed=2)
    plac = _stacked(0.0, [("2026-05-01", [-LN10] * 4)], seed=3)
    o = e5.estimate(plac, "pooled", "repeat_rate", B=299, wild=False, es=False)
    assert o["lo"] < 0 < o["hi"] and o["perm"]["lo"] < 0 < o["perm"]["hi"]
    # stacked with the real batches, the placebo batch's own per-batch estimate is ~0
    both = {k: np.concatenate([col[k], plac[k]]) for k in col}
    m = both["batch"] == "2026-05-01"
    sub = {k: v[m] for k, v in both.items()}
    o2 = e5.estimate(sub, "cut", "repeat_rate", B=199, wild=False, es=False)
    assert o2["lo"] < 0 < o2["hi"]


def test_no_effect_coverage():
    covered = 0
    for s in range(15):
        o = e5.estimate(_stacked(0.0, BATCHES, seed=100 + s), "pooled", "repeat_rate",
                        B=99, wild=False, es=False)
        covered += o["lo"] < 0 < o["hi"]
    assert covered >= 12


def test_permutation_stays_within_batches():
    strata = np.array([0, 0, 0, 1, 1, 1, 1])
    dose = np.array([-2.3, 0, 0, 2.3, 2.3, 0, 0])
    A = e5._within_assignments(strata, dose, 50, seed=0)
    for s in (0, 1):
        assert np.allclose(np.sort(A[strata == s], axis=0),
                           np.sort(dose[strata == s])[:, None])


def test_pre_trend_flagged_only_when_present():
    col = _stacked(-1.5, BATCHES, seed=4)
    assert e5.estimate(col, "pooled", "repeat_rate", B=199, wild=False)["pre_p"] > 0.05
    trend = col["treated"] * np.where(col["rel"] < 0, 0.25 * col["rel"], 0.0)
    col2 = dict(col, repeat_rate=col["repeat_rate"] + trend)
    o = e5.estimate(col2, "pooled", "repeat_rate", B=199, wild=False)
    assert o["pre_p"] < 0.05 and o["es"]["slope_lo"] > 0


def _events():
    def ev(sym, date, direction="cut", status="verified"):
        new, old = ("0.001", "0.01") if direction == "cut" else ("0.01", "0.001")
        return {"symbol": sym, "detected_time": f"{date} 06:30", "status": status,
                "direction": direction, "old_tick": old, "new_tick": new}
    rows = [ev(f"A{i}", "2026-07-01") for i in range(3)]
    rows += [ev(f"R{i}", "2026-08-06") for i in range(4)]  # reserved
    rows += [ev(f"Q{i}", "2026-10-15") for i in range(3)]  # reserved
    rows += [ev("INC", "2025-05-01", "increase")]
    ctrls = []
    for date, syms in (("2026-07-01", ["A0", "A1", "A2"]), ("2026-08-06", ["R0", "R1", "R2",
                                                                            "R3"]),
                       ("2026-10-15", ["Q0", "Q1", "Q2"]), ("2025-05-01", ["INC"])):
        for s in syms:
            pool = ["R0", "C1", "C2", "C3", "C4"] if date == "2026-07-01" else \
                ["C1", "C2", "C3", "C4"]
            for k, c in enumerate(pool):
                ctrls.append({"event_date": date, "treated_symbol": s, "control_symbol": c,
                              "rank": str(k + 1)})
    return rows, ctrls


def test_reserved_batches_are_never_loaded(monkeypatch):
    ev, ct = _events()
    monkeypatch.setattr(e5, "pre_cost", lambda s, b: 1.0)
    plan = e5.design(ev, ct, budget_cut=1e9, budget_inc=1e9, cached={})
    batches = {a["batch"] for a in plan["arms"]}
    assert batches == {"2026-07-01", "2025-05-01"}
    assert set(plan["reserved"]) == {"2026-08-06", "2026-10-15"}
    assert not set(plan["eligible"]) & set(e5.RESERVED)
    # R0 is treated in the reserved 2026-08-06 batch and its days around 07-01 fall in
    # that batch's window, so it is never used as a control
    for a in plan["arms"]:
        assert "R0" not in e5.arm_symbols(a)[1]
    # downloads and loading never touch a reserved batch
    asked = []

    def summary(b, s, d):
        asked.append(b)
        e5.guard(b)
        return {"present": False}

    e5.load_panel(plan, summary=summary)
    assert asked and not set(asked) & set(e5.RESERVED)
    for b in e5.RESERVED:
        with pytest.raises(e5.ReservedBatchError):
            e5._cached_summary(b, "X", b)
        bad = {"arms": [{"batch": b, "direction": "cut", "treated": [
            {"symbol": "X", "dose": -LN10, "controls": ["C1", "C2", "C3"]}]}]}
        with pytest.raises(e5.ReservedBatchError):
            e5.downloads(bad)
        with pytest.raises(e5.ReservedBatchError):
            e5.load_panel(bad, summary=lambda *a: None)


def test_real_design_excludes_reserved():
    if not (e5.OUT / "tick_events.csv").exists():
        pytest.skip("tick_events.csv not present")
    plan = e5.design(cached={})
    assert not {a["batch"] for a in plan["arms"]} & set(e5.RESERVED)
    for a in plan["arms"]:
        assert all(len(t["controls"]) >= 3 for t in a["treated"])
