from __future__ import annotations

import csv
import importlib.util
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "validate_posts", ROOT / "research" / "politics" / "validate_posts.py")
vp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vp)

NOW = datetime(2026, 11, 18, tzinfo=UTC)


def _row(**kw) -> dict:
    row = {
        "platform": "x", "handle": "EricTrump", "post_id": "1896234567890123456",
        "url": "https://x.com/EricTrump/status/1896234567890123456",
        "created_at_utc": "2025-03-02T15:24:07Z", "text": "Bitcoin", "kind": "original",
        "quoted_or_reposted_handle": "", "has_media": "false",
        "collected_at_utc": "2026-11-18T00:00:00Z",
    }
    row.update(kw)
    return row


def test_valid_row_passes():
    assert vp.check_rows("x_EricTrump.csv", vp.COLUMNS, [_row()], NOW) == []


def test_header_must_match_exactly():
    assert vp.check_rows("x_EricTrump.csv", vp.COLUMNS[::-1], [], NOW)


def test_relative_or_local_timestamps_are_rejected():
    for bad in ("3h", "2025-03-02 15:24:07", "2025-03-02T15:24:07+00:00", "2025-03-02T15:24Z"):
        problems = vp.check_rows("x_EricTrump.csv", vp.COLUMNS, [_row(created_at_utc=bad)], NOW)
        assert any("created_at_utc" in p for p in problems), bad


def test_duplicates_and_url_mismatch_are_caught():
    rows = [_row(), _row()]
    assert any("duplicate" in p for p in vp.check_rows("x_EricTrump.csv", vp.COLUMNS, rows, NOW))
    mism = _row(url="https://x.com/EricTrump/status/111")
    assert any("differs" in p for p in vp.check_rows("x_EricTrump.csv", vp.COLUMNS, [mism], NOW))


def test_file_name_must_match_handle():
    problems = vp.check_rows("x_SenWarren.csv", vp.COLUMNS, [_row()], NOW)
    assert any("file name" in p for p in problems)


def test_repost_needs_source_and_truth_urls_work():
    assert vp.check_rows("x_EricTrump.csv", vp.COLUMNS, [_row(kind="repost", text="")], NOW)
    truth = _row(platform="truth", handle="realDonaldTrump", post_id="114093745562108574",
                 url="https://truthsocial.com/@realDonaldTrump/114093745562108574")
    assert vp.check_rows("truth_realDonaldTrump.csv", vp.COLUMNS, [truth], NOW) == []


def test_check_file_round_trip(tmp_path):
    path = tmp_path / "x_EricTrump.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=vp.COLUMNS)
        w.writeheader()
        w.writerow(_row(text='He said "buy"\\nnow'))
    assert vp.check_file(path, now=NOW) == []
