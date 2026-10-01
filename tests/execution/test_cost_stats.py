import numpy as np
import pytest

from microstructure.execution.cost_stats import (
    paired_difference,
    sd_ratio,
    summarize,
    summarize_per_symbol,
)


def _row(symbol, day, side, qty, schedule, value):
    return {
        "symbol": symbol, "day": day, "side": side, "parent_qty_events": qty,
        "schedule": schedule, "shortfall_bps": value,
    }


def _rows():
    rows = []
    twap = [1.0, 2.0, 3.0, 4.0]
    reactive = [1.5, 2.5, 3.5, 4.5]
    for i, (t, r) in enumerate(zip(twap, reactive, strict=True)):
        rows.append(_row("A", f"d{i}", 1, 2.0, "twap", t))
        rows.append(_row("A", f"d{i}", 1, 2.0, "reactive", r))
        rows.append(_row("A", f"d{i}", 1, 2.0, "frontloaded", 2.0))
    return rows


def test_summarize_reports_mean_sd_and_n_per_schedule():
    out = summarize(_rows())
    assert out["twap"]["mean_shortfall"] == pytest.approx(2.5)
    assert out["twap"]["sd_shortfall"] == pytest.approx(np.std([1, 2, 3, 4]))
    assert out["twap"]["n"] == 4


def test_summarize_empty_schedule_is_nan_with_zero_n():
    out = summarize([])
    assert out["twap"]["n"] == 0 and np.isnan(out["twap"]["mean_shortfall"])


def test_per_symbol_summary_keeps_symbols_separate():
    rows = _rows() + [_row("B", "d0", 1, 2.0, "twap", 100.0)]
    out = {p["symbol"]: p for p in summarize_per_symbol(rows, ["A", "B"])}
    assert out["A"]["twap"]["n"] == 4 and out["B"]["twap"]["n"] == 1


def test_paired_difference_uses_matched_cells_and_ddof_one_se():
    paired = paired_difference(_rows(), "reactive", "twap")
    assert paired["n"] == 4
    assert paired["mean"] == pytest.approx(0.5)
    # constant difference: SE is exactly 0, so z is undefined
    assert paired["se"] == 0.0 and paired["z"] is None


def test_paired_difference_se_matches_hand_computation():
    rows = []
    for i, diff in enumerate([0.0, 1.0, 2.0, 3.0]):
        rows.append(_row("A", f"d{i}", 1, 2.0, "twap", 10.0))
        rows.append(_row("A", f"d{i}", 1, 2.0, "reactive", 10.0 + diff))
    paired = paired_difference(rows, "reactive", "twap")
    expected_se = np.std([0.0, 1.0, 2.0, 3.0], ddof=1) / 2.0
    assert paired["mean"] == pytest.approx(1.5)
    assert paired["se"] == pytest.approx(expected_se)
    assert paired["z"] == pytest.approx(1.5 / expected_se)


def test_paired_difference_ignores_unmatched_cells_and_needs_two():
    rows = [_row("A", "d0", 1, 2.0, "twap", 1.0), _row("A", "d0", 1, 2.0, "reactive", 2.0)]
    rows.append(_row("A", "d1", 1, 2.0, "twap", 5.0))  # no reactive partner
    paired = paired_difference(rows, "reactive", "twap")
    assert paired == {"mean": None, "se": None, "z": None, "n": 1}


def test_sd_ratio_is_frontloaded_over_twap_or_none():
    assert sd_ratio(summarize(_rows())) == pytest.approx(0.0)
    assert sd_ratio(summarize([])) is None
