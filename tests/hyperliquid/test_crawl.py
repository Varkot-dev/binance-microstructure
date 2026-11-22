import gzip
import hashlib
import json
from datetime import UTC, datetime

import pytest

from microstructure.hyperliquid import crawl


def test_pass_id_is_monday_of_iso_week():
    assert crawl.pass_id(datetime(2026, 11, 22, 23, 0, tzinfo=UTC)) == "20261116"  # Sunday
    assert crawl.pass_id(datetime(2026, 11, 23, 0, 0, tzinfo=UTC)) == "20261123"  # Monday


def test_shards_partition_the_cohort():
    items = list(range(103))
    parts = [crawl.shard_of(items, i, 7) for i in range(7)]
    assert sorted(x for p in parts for x in p) == items
    assert max(map(len, parts)) - min(map(len, parts)) <= 1
    with pytest.raises(ValueError):
        crawl.shard_of(items, 7, 7)


def test_load_cohort_checks_hash(tmp_path):
    raw = gzip.compress(json.dumps({"leaderboardRows": [
        {"ethAddress": "0xB"}, {"ethAddress": "0xa"}, {"ethAddress": "0xb"}]}).encode())
    p = tmp_path / "lb.json.gz"
    p.write_bytes(raw)
    assert crawl.load_cohort(p, hashlib.sha256(raw).hexdigest()) == ["0xa", "0xb"]
    with pytest.raises(SystemExit):
        crawl.load_cohort(p, "0" * 64)


def test_paginate_stitches_pages_and_drops_boundary_duplicates():
    rows = [{"time": t, "hash": str(t), "delta": {}} for t in [1, 2, 2, 3, 4, 5, 6]]
    rows[2]["hash"] = "2b"

    def fetch(start):
        return [r for r in rows if r["time"] >= start][:3]

    res = crawl.paginate(fetch, crawl.ledger_key, page_size=3)
    assert [r["hash"] for r in res.rows] == ["1", "2", "2b", "3", "4", "5", "6"]
    assert res.stuck_steps == 0


def test_paginate_steps_past_a_full_page_in_one_millisecond():
    rows = [{"time": 5, "hash": str(i), "delta": {}} for i in range(3)] + [
        {"time": 9, "hash": "x", "delta": {}}]

    def fetch(start):
        return [r for r in rows if r["time"] >= start][:3]

    res = crawl.paginate(fetch, crawl.ledger_key, page_size=3, start_ms=5)
    assert res.stuck_steps == 1 and len(res.rows) == 4


def test_limiter_waits_when_the_window_is_full():
    t = [0.0]
    slept = []

    def sleep(s):
        slept.append(s)
        t[0] += s

    lim = crawl.WeightLimiter(budget=40, clock=lambda: t[0], sleep=sleep)
    for _ in range(3):
        lim.acquire(20)
    assert len(slept) == 1 and slept[0] == pytest.approx(60.01)


class FakeAPI:
    """Two cohort wallets; 0xa lists a sub-account 0xs; ledger of 0xa spans two pages."""

    def __init__(self, fail=()):
        self.calls = []
        self.fail = set(fail)

    def __call__(self, body):
        self.calls.append(body)
        t, user = body["type"], body.get("user")
        if user in self.fail:
            return 400, "bad"
        if t == "portfolio":
            return 200, [["allTime", {"pnlHistory": [], "accountValueHistory": []}]]
        if t == "subAccounts":
            return 200, ([{"subAccountUser": "0xS", "name": "s"}] if user == "0xa" else None)
        if t == "userNonFundingLedgerUpdates":
            rows = ([{"time": i, "hash": f"h{i}", "delta": {}} for i in range(3000)]
                    if user == "0xa" else [])
            return 200, [r for r in rows if r["time"] >= body["startTime"]][:2000]
        if t == "candleSnapshot":
            return 200, [{"t": 0, "c": "1"}]
        if t == "fundingHistory":
            return 200, [{"coin": body["coin"], "time": 1, "fundingRate": "0"}]
        if t == "vaultDetails":
            return 200, {"name": "HLP"}
        raise AssertionError(body)


def _client(api):
    return crawl.Client(limiter=crawl.WeightLimiter(budget=1e9), post=api, sleep=lambda s: None)


def test_run_shard_fetches_wallets_subaccounts_and_benchmarks(tmp_path):
    api = FakeAPI()
    st = crawl.run_shard(_client(api), ["0xa", "0xb"], ["BTC", "ETH"], 0, 1, tmp_path,
                         "20261116", budget_s=1e9, log=lambda m: None)
    assert st["complete"] and st["pending"] == 0 and st["failed"] == 0
    assert st["wallets_ok"] == 3 and st["sub_accounts_ok"] == 1
    assert st["bench_ok"] == 2 + 2 + 3 + 1  # candles, funding, hourly, HLP
    recs = crawl.ShardState.load(tmp_path / "shard_00.jsonl.gz").records
    assert len(recs["wallet:0xa"]["data"]["ledger"]) == 3000
    assert recs["wallet:0xs"]["master"] == "0xa"
    # a rerun of the same pass fetches nothing
    api2 = FakeAPI()
    st2 = crawl.run_shard(_client(api2), ["0xa", "0xb"], ["BTC", "ETH"], 0, 1, tmp_path,
                          "20261116", budget_s=1e9, log=lambda m: None)
    assert api2.calls == [] and st2["complete"] and st2["data_sha256"] == st["data_sha256"]


def test_run_shard_stops_at_budget_and_resumes(tmp_path):
    clock = [0.0]

    def now():
        clock[0] += 1.0
        return clock[0]

    st = crawl.run_shard(_client(FakeAPI()), ["0xa", "0xb"], [], 0, 1, tmp_path, "p",
                         budget_s=2.5, now=now, log=lambda m: None)
    assert not st["complete"] and st["pending"] > 0
    st2 = crawl.run_shard(_client(FakeAPI()), ["0xa", "0xb"], [], 0, 1, tmp_path, "p",
                          budget_s=1e9, log=lambda m: None)
    assert st2["complete"] and st2["wallets_ok"] == 3


def test_failures_are_retried_until_max_tries(tmp_path):
    for k in range(crawl.MAX_TRIES):
        st = crawl.run_shard(_client(FakeAPI(fail={"0xb"})), ["0xb"], [], 0, 1, tmp_path, "p",
                             budget_s=1e9, log=lambda m: None)
        assert st["failed"] == 1
        assert st["complete"] == (k == crawl.MAX_TRIES - 1)
    rec = crawl.ShardState.load(tmp_path / "shard_00.jsonl.gz").records["wallet:0xb"]
    assert rec["tries"] == crawl.MAX_TRIES and "status 400" in rec["error"]
