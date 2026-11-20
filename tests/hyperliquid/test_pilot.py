"""Offline tests for the pure parts of research/hyperliquid/pilot.py (no network)."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "hl_pilot", ROOT / "research" / "hyperliquid" / "pilot.py")
pilot = importlib.util.module_from_spec(_spec)
sys.modules["hl_pilot"] = pilot  # dataclasses look the module up by name
_spec.loader.exec_module(pilot)

ADDRS = [f"0x{i:040x}" for i in range(1000)]


# --- sampling ------------------------------------------------------------------------------

def test_sample_is_reproducible_and_order_independent():
    a = pilot.draw_sample(ADDRS, 50, seed=pilot.SEED)
    b = pilot.draw_sample(list(reversed(ADDRS)), 50, seed=pilot.SEED)
    assert a == b
    assert len(a) == len(set(a)) == 50
    assert set(a) <= set(ADDRS)


def test_sample_depends_on_seed_and_normalises_case():
    a = pilot.draw_sample(ADDRS, 50, seed=1)
    assert a != pilot.draw_sample(ADDRS, 50, seed=2)
    upper = [x.upper().replace("0X", "0x") for x in ADDRS] + ADDRS  # duplicates by case
    assert pilot.draw_sample(upper, 50, seed=1) == a


def test_sample_all_returns_sorted_pool():
    assert pilot.draw_sample(ADDRS[::-1], None) == ADDRS
    assert pilot.draw_sample(ADDRS, 5000) == ADDRS


def test_load_cohort_checks_hash(tmp_path):
    p = tmp_path / "lb.json.gz"
    rows = [{"ethAddress": "0xAB", "accountValue": "1.5",
             "windowPerformances": [["allTime", {"pnl": "2", "roi": "0", "vlm": "3"}]]}]
    p.write_bytes(gzip.compress(json.dumps({"leaderboardRows": rows}).encode(), mtime=0))
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    assert pilot.load_cohort(p, sha) == rows
    with pytest.raises(SystemExit):
        pilot.load_cohort(p, "0" * 64)
    assert pilot.cohort_table(rows) == {"0xab": {"accountValue": 1.5, "pnl": 2.0, "vlm": 3.0}}


def test_ks_statistic():
    assert pilot.ks_statistic([1, 2, 3], [1, 2, 3]) == 0.0
    assert pilot.ks_statistic([0, 0, 0], [5, 5, 5]) == 1.0


# --- weight and pacing ---------------------------------------------------------------------

def test_request_weight():
    assert pilot.request_weight("portfolio") == 20
    assert pilot.request_weight("userRole") == 60
    assert pilot.request_weight("userFillsByTime", 0) == 20
    assert pilot.request_weight("userFillsByTime", 2000) == 120
    assert pilot.request_weight("userFillsByTime", 21) == 22


def test_limiter_waits_when_budget_is_spent():
    t = [0.0]
    lim = pilot.WeightLimiter(100, clock=lambda: t[0],
                              sleep=lambda s: t.__setitem__(0, t[0] + s))
    lim.acquire(60)
    lim.acquire(40)  # exactly at budget, no wait
    assert t[0] == 0.0
    lim.acquire(10)  # must wait for the first event to leave the 60 s window
    assert t[0] >= 60.0
    assert lim.waited_s >= 60.0


# --- pagination and dedup ------------------------------------------------------------------

def _fills(times):
    return [{"tid": i, "oid": i // 3, "time": t, "px": "1", "sz": "1", "coin": "BTC"}
            for i, t in enumerate(times)]


def _server(rows, page_size):
    """Oldest-first endpoint that returns up to page_size rows with time >= start."""
    calls = []

    def fetch(start):
        calls.append(start)
        return [r for r in rows if r["time"] >= start][:page_size]
    return fetch, calls


def test_paginate_stitches_pages_and_drops_boundary_duplicates():
    # Several fills share a millisecond at each page boundary.
    times = sorted([t // 3 for t in range(25)])
    rows = _fills(times)
    fetch, calls = _server(rows, page_size=5)
    res = pilot.paginate(fetch, pilot.fill_key, page_size=5)
    assert [r["tid"] for r in res.rows] == [r["tid"] for r in rows]
    assert res.pages == len(calls) and not res.truncated
    assert calls[0] == 0 and calls == sorted(calls)


def test_paginate_bumps_start_when_a_full_page_is_one_millisecond():
    rows = _fills([7] * 5 + [8, 9])
    fetch, _ = _server(rows, page_size=5)
    res = pilot.paginate(fetch, pilot.fill_key, page_size=5)
    assert res.stuck_steps == 1
    assert [r["time"] for r in res.rows] == [7] * 5 + [8, 9]


def test_paginate_respects_page_cap():
    rows = _fills(range(100))
    fetch, _ = _server(rows, page_size=10)
    res = pilot.paginate(fetch, pilot.fill_key, page_size=10, max_pages=3)
    assert res.truncated and res.pages == 3
    assert len(res.rows) == 28  # 10 + 9 + 9 new rows (inclusive start repeats one)


def test_paginate_stops_on_short_and_empty_pages():
    fetch, calls = _server([], page_size=10)
    res = pilot.paginate(fetch, pilot.fill_key, page_size=10)
    assert res.rows == [] and res.pages == 1 and calls == [0]


def test_dedupe_by_tid_keeps_first_and_order():
    f = [{"tid": 1, "oid": 9, "x": "a"}, {"tid": 2, "oid": 9}, {"tid": 1, "oid": 9, "x": "b"}]
    out = pilot.dedupe(f, pilot.fill_key)
    assert [(r["tid"], r.get("x")) for r in out] == [(1, "a"), (2, None)]
    # Same tid on two different own orders (self-trade) is two fills, not a duplicate.
    assert len(pilot.dedupe([{"tid": 1, "oid": 1}, {"tid": 1, "oid": 2}], pilot.fill_key)) == 2


def test_ledger_key_distinguishes_deltas():
    a = {"time": 1, "hash": "0x0", "delta": {"type": "deposit", "usdc": "1"}}
    b = {"time": 1, "hash": "0x0", "delta": {"type": "deposit", "usdc": "2"}}
    assert len(pilot.dedupe([a, b, dict(a)], pilot.ledger_key)) == 2


# --- metric helpers ------------------------------------------------------------------------

def test_cache_name_is_deterministic():
    body = {"type": "userFillsByTime", "user": "0xa", "startTime": 5, "endTime": 9}
    assert pilot.cache_name(body) == "userFillsByTime_s5_e9.json.gz"
    assert pilot.cache_name({"type": "portfolio", "user": "0xa"}) == "portfolio.json.gz"


def test_window_spacing_and_gaps():
    h = 3_600_000
    win = {"accountValueHistory": [[0, "1"], [h, "1"], [5 * h, "1"]], "pnlHistory": [], "vlm": "2"}
    s = pilot.window_spacing(win)
    assert s["n_points"] == 3 and s["first_gap_h"] == 1 and s["max_gap_h"] == 4
    assert s["median_gap_h"] == 2.5 and s["vlm"] == 2.0


def test_first_inbound_and_classification():
    user = "0xaa"
    ledger = [
        {"time": 5, "delta": {"type": "send", "user": user, "destination": "0xbb"}},
        {"time": 9, "delta": {"type": "send", "user": "0xbb", "destination": user}},
        {"time": 20, "delta": {"type": "deposit", "usdc": "1"}},
    ]
    assert pilot.first_inbound_ms(ledger, user) == 9
    assert pilot.classify_fills(0, None, 0.0, 0) == "no_trading"
    assert pilot.classify_fills(10, 0.99, 1.0, 0) == "complete"
    assert pilot.classify_fills(10, 1.00, 1.0, 2) == "left_censored"
    assert pilot.classify_fills(0, 0.0, 5.0, 0) == "left_censored"
    assert pilot.classify_fills(10, 0.5, 1.0, 0) == "volume_gap"


def test_open_at_first_fill_uses_server_order_and_skips_spot():
    fills = [
        {"coin": "BTC", "startPosition": "0.0", "tid": 9},
        {"coin": "BTC", "startPosition": "1.0", "tid": 1},  # later fill, lower tid
        {"coin": "ETH", "startPosition": "-2.0", "tid": 5},
        {"coin": "@107", "startPosition": "3.0", "tid": 6},
        {"coin": "xyz:XYZ100", "startPosition": "1.0", "tid": 7},
    ]
    assert pilot.open_at_first_fill(fills) == ["ETH", "xyz:XYZ100"]


def test_fill_notional_splits_markets():
    f = [{"coin": "BTC", "px": "2", "sz": "3"}, {"coin": "@107", "px": "1", "sz": "-4"},
         {"coin": "xyz:XYZ100", "px": "1", "sz": "1"}]
    n = pilot.fill_notional(f)
    assert n == {"all": 11.0, "perp": 6.0, "spot": 4.0, "hip3": 1.0}
