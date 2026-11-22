import csv
import gzip
import json

import polars as pl
import pytest

from microstructure.rpi import quality as q


def _row(sym, i, time=None, price="2", qty="3", quote="6", maker=0, rpi=0):
    return (sym, i, 1000 * i if time is None else time, price, qty, quote, maker, rpi)


def _write_run(tmp_path, run, rows, summary_trades=None, **summary):
    with gzip.open(tmp_path / f"rpi_trades_{run}.csv.gz", "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(q.COLUMNS)
        w.writerows(rows)
    n = {}
    for r in rows:
        n[r[0]] = n.get(r[0], 0) + 1
    s = {"run_id": run, "started": "2026-11-22T00:23:00+00:00",
         "ended": "2026-11-22T05:38:00+00:00", "planned_end": "2026-11-22T05:38:00+00:00",
         "http_429_or_418": 0,
         "symbols": {k: {"rpi_enabled": True, "trades": (summary_trades or n)[k], "errors": 0,
                         "gaps": []} for k in n}}
    s.update(summary)
    (tmp_path / f"rpi_run_{run}.json").write_text(json.dumps(s))


def test_run_id_of(tmp_path):
    assert q.run_id_of(tmp_path / "rpi_trades_20261122T231400Z.csv.gz") == "20261122T231400Z"


def test_find_gaps():
    assert q.find_gaps([1, 2, 3], [10, 20, 30]) == []
    assert q.find_gaps([1, 2, 6, 7, 9], [10, 20, 60, 70, 90]) == [
        {"after_id": 2, "before_id": 6, "missing": 3, "after_time": 20, "before_time": 60},
        {"after_id": 7, "before_id": 9, "missing": 1, "after_time": 70, "before_time": 90}]


def test_clean_overlapping_runs_have_no_problems(tmp_path):
    _write_run(tmp_path, "A", [_row("X", i, rpi=i % 2) for i in range(1, 6)])
    _write_run(tmp_path, "B", [_row("X", i) if i != 5 else _row("X", 5, rpi=1)
                               for i in range(4, 9)])
    rep = q.report_from_dirs([tmp_path])
    x = rep["symbols"]["X"]
    assert rep["problems"] == []
    assert (x["rows"], x["unique_trades"], x["missing_ids"]) == (10, 8, 0)
    assert x["ids_in_two_or_more_runs"] == 2 and x["conflicting_ids"] == 0
    assert rep["rpi_flag_takes_both_values"]
    assert "problems: none" in q.format_report(rep)


def test_gap_conflict_and_backwards_time_are_reported(tmp_path):
    rows = [_row("X", 1), _row("X", 2, rpi=1), _row("X", 5, time=1500), _row("X", 6)]
    _write_run(tmp_path, "A", rows)
    _write_run(tmp_path, "B", [_row("X", 6, price="9")])  # same id, different price
    rep = q.report_from_dirs([tmp_path])
    x = rep["symbols"]["X"]
    assert x["missing_ids"] == 2 and x["n_gaps"] == 1
    assert x["gaps"][0]["after_id"] == 2 and x["gaps"][0]["before_id"] == 5
    assert x["conflicting_ids"] == 1
    assert x["time_goes_backwards"] == 1
    assert {p.split(" = ")[0] for p in rep["problems"]} == {
        "X: missing_ids", "X: conflicting_ids", "X: time_goes_backwards"}


def test_bad_values_and_single_valued_flag(tmp_path):
    _write_run(tmp_path, "A", [_row("X", 1, price="0"), _row("X", 2, qty="abc"),
                               _row("X", 3, maker=2), _row("X", 4, quote="6.6")])
    rep = q.report_from_dirs([tmp_path])
    x = rep["symbols"]["X"]
    assert x["non_positive_price_or_qty"] == 1
    assert x["unparsable_numbers"] == 1
    assert x["flags_not_0_or_1"] == 1
    assert x["quote_qty_max_rel_diff"] == pytest.approx(0.1)
    assert not rep["rpi_flag_takes_both_values"]
    assert any("isRPITrade takes values [0]" in p for p in rep["problems"])


def test_summary_disagreeing_with_data_is_reported(tmp_path):
    _write_run(tmp_path, "A", [_row("X", 1), _row("X", 2, rpi=1), _row("Y", 1)],
               summary_trades={"X": 3, "Y": 1}, http_429_or_418=2,
               ended="2026-11-22T03:00:00+00:00")
    run = q.report_from_dirs([tmp_path])["runs"][0]
    assert run["row_count_mismatch"] == ["X"]
    assert run["rate_limit_responses"] == 2 and run["ended_early"]


def test_wrong_columns_are_rejected(tmp_path):
    with gzip.open(tmp_path / "rpi_trades_A.csv.gz", "wt") as fh:
        fh.write("symbol,id,time\nX,1,2\n")
    with pytest.raises(ValueError, match="columns"):
        q.load_runs([tmp_path / "rpi_trades_A.csv.gz"])
    with pytest.raises(ValueError, match="no rpi_trades"):
        q.load_runs([])


def test_no_per_attribute_flag_counts_in_report(tmp_path):
    # the report must not break the retail flag down by symbol or anything else
    _write_run(tmp_path, "A", [_row("X", 1, rpi=1), _row("X", 2)])
    rep = q.report_from_dirs([tmp_path])
    assert not any("rpi" in k.lower() for k in rep["symbols"]["X"])
    assert isinstance(pl.DataFrame(rep["runs"]), pl.DataFrame)
