"""Offline tests for the pure helpers of the HIP-1 launch census crawler."""
from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "census", ROOT / "research" / "hyperliquid" / "memecoin" / "census.py")
census = importlib.util.module_from_spec(_spec)
sys.modules["census"] = census  # dataclasses look the module up by name
_spec.loader.exec_module(census)


def test_classify_outcomes():
    assert census.classify(200, b'{"name":"X"}') == "ok"
    assert census.classify(200, b"null") == "null"
    assert census.classify(200, b"<html>") == "bad_json"
    assert census.classify(500, b"") == "http_500"
    assert census.classify(None, None) == "network"


def test_retryable():
    assert census.is_retryable("http_500")
    assert census.is_retryable("http_429")
    assert census.is_retryable("network")
    assert not census.is_retryable("http_422")
    assert not census.is_retryable("ok")
    assert not census.is_retryable("null")


def test_backoff_grows_and_429_waits_longer():
    w = [census.backoff_s(k, 500, base=1.0) for k in (1, 2, 3)]
    assert w == [1.0, 2.0, 4.0]
    assert census.backoff_s(2, 429, base=1.0) == 4.0


def test_pair_coin_and_safe_name():
    assert census.pair_coin({"name": "PURR/USDC", "index": 0}) == "PURR/USDC"
    assert census.pair_coin({"name": "@107", "index": 107}) == "@107"
    assert census.pair_coin({"name": "@5", "index": 5}) == "@5"
    assert census.safe_name("@107") == "at107"
    assert census.safe_name("PURR/USDC") == "PURR_USDC"


def test_missing_indices():
    assert census.missing_indices([0, 1, 4]) == [2, 3]
    assert census.missing_indices([]) == []
    assert census.missing_indices([2]) == [0, 1]


def test_candle_span_ignores_backfilled_zero_volume():
    bars = [{"t": 100, "v": "0"}, {"t": 200, "v": "0.0"}, {"t": 300, "v": "5"},
            {"t": 400, "v": "1.5"}, {"t": 500, "v": "0"}]
    s = census.candle_span(bars)
    assert s == {"n_bars": 5, "n_traded": 2, "first_t": 100, "last_t": 500,
                 "first_traded_t": 300, "last_traded_t": 400}
    empty = census.candle_span([])
    assert empty["n_bars"] == 0 and empty["first_traded_t"] is None


def test_summarize_status():
    rows = [{"final": "ok", "attempts": [{}]}, {"final": "ok", "attempts": [{}, {}]},
            {"final": "http_500", "attempts": [{}] * 4}, {"final": "null", "attempts": [{}]}]
    s = census.summarize_status(rows)
    assert s["n"] == 4
    assert s["final"] == {"http_500": 1, "null": 1, "ok": 2}
    assert s["attempts_for_ok"] == {"1": 1, "2": 1}


def test_dates():
    assert census.crawl_id_now(0) == "19700101T000000Z"
    assert census.ms_to_date(86_400_000) == "1970-01-02"
    assert census.ms_to_date(None) is None


def test_fetch_caches_and_records_failures(tmp_path, monkeypatch):
    c = census.Client(tmp_path, min_interval=0.0)
    answers = iter([(500, b"", None), (200, b'{"a":1}', None)])
    monkeypatch.setattr(c, "post", lambda body: next(answers))
    monkeypatch.setattr(census.time, "sleep", lambda s: None)
    row = c.fetch("x/a.json.gz", {"type": "t"})
    assert row["final"] == "ok"
    assert [a["outcome"] for a in row["attempts"]] == ["http_500", "ok"]
    assert json.loads(gzip.decompress((tmp_path / "x/a.json.gz").read_bytes())) == {"a": 1}
    man = [json.loads(x) for x in (tmp_path / "manifest.jsonl").read_text().splitlines()]
    assert man[0]["sha256"] == census.sha256_bytes(b'{"a":1}')
    # second call is served from cache without any request
    monkeypatch.setattr(c, "post", lambda body: (_ for _ in ()).throw(AssertionError))
    again = c.fetch("x/a.json.gz", {"type": "t"})
    assert again["cached"] and again["final"] == "ok"


def test_fetch_gives_up_and_writes_nothing(tmp_path, monkeypatch):
    c = census.Client(tmp_path, min_interval=0.0)
    monkeypatch.setattr(c, "post", lambda body: (500, b"", None))
    monkeypatch.setattr(census.time, "sleep", lambda s: None)
    row = c.fetch("b.json.gz", {"type": "t"})
    assert row["final"] == "http_500"
    assert len(row["attempts"]) == census.MAX_ATTEMPTS
    assert not (tmp_path / "b.json.gz").exists()


def test_merge_status_keeps_history(tmp_path):
    p = tmp_path / "s.jsonl"
    census._merge_status(p, [{"file": "a", "final": "http_500", "cached": False,
                              "attempts": [{"outcome": "http_500"}]}])
    census._merge_status(p, [{"file": "a", "final": "ok", "cached": False,
                              "attempts": [{"outcome": "ok"}]}])
    r = json.loads(p.read_text())
    assert [a["outcome"] for a in r["attempts"]] == ["http_500", "ok"]
