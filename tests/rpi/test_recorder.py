import csv
import gzip
import json
from datetime import UTC, datetime

import pytest

from microstructure.rpi import recorder as rec


def test_slot_end_is_next_slot_plus_overlap():
    # slots start at 00:23, 04:23, 08:23 ... UTC (cron "23 */4 * * *")
    assert rec.slot_end(datetime(2026, 11, 22, 3, 0, tzinfo=UTC)) == \
        datetime(2026, 11, 22, 5, 38, tzinfo=UTC)
    assert rec.slot_end(datetime(2026, 11, 22, 4, 23, tzinfo=UTC)) == \
        datetime(2026, 11, 22, 9, 38, tzinfo=UTC)
    assert rec.slot_end(datetime(2026, 11, 22, 0, 10, tzinfo=UTC)) == \
        datetime(2026, 11, 22, 1, 38, tzinfo=UTC)  # still in the 20:23 slot


def test_next_interval():
    assert rec.next_interval(1000, 10_000, True, 5) == rec.MIN_INTERVAL_S
    # 35 trades/s -> 0.07 * 1000 / 35 = 2 s
    assert rec.next_interval(350, 10_000, False, 5) == pytest.approx(2)
    assert rec.next_interval(0, 0, False, 50) == rec.MAX_INTERVAL_S


def _t(i, rpi=False):
    return {"id": i, "time": 1000 * i, "price": "1", "qty": "1", "quoteQty": "1",
            "isBuyerMaker": i % 2 == 0, "isRPITrade": rpi}


def test_absorb_dedupes_and_detects_gaps():
    st = rec.SymbolState("X")
    assert [t["id"] for t in st.absorb([_t(1), _t(2), _t(3)], 0)] == [1, 2, 3]
    assert [t["id"] for t in st.absorb([_t(2), _t(3), _t(4, True)], 0)] == [4]
    assert st.gaps == [] and st.rpi == 1 and st.trades == 4
    st.absorb([_t(10), _t(11)], 0)
    assert st.gaps[0]["missing"] == 5 and st.gaps[0]["after_id"] == 4


class FakeClock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += max(s, 0.01)


def test_record_writes_csv_and_summary(tmp_path):
    clock = FakeClock()
    next_id = {"A": 0, "B": 0}

    def get(path, params):
        clock.t += 0.05
        if path == "exchangeInfo":
            return 200, {"symbols": [{"symbol": "A", "status": "TRADING",
                                      "permissionSets": [["GRID", "RPI"]]}]}, {}
        s = params["symbol"]
        next_id[s] += 3  # three new trades per call
        hi = next_id[s]
        return 200, [_t(i, rpi=(i % 3 == 0)) for i in range(max(1, hi - 5), hi + 1)], \
            {"x-mbx-used-weight-1m": "10"}

    api = rec.Api(get=get, sleep=clock.sleep)
    s = rec.record(api, ["A", "B"], tmp_path, int((clock.t + 60) * 1000), clock=clock,
                   sleep=clock.sleep, log=lambda m: None, run_id="test")
    assert s["rpi_enabled_at_start"] == ["A"]
    assert s["symbols"]["A"]["rpi_enabled"] and not s["symbols"]["B"]["rpi_enabled"]
    assert all(v["gap_free"] for v in s["symbols"].values())
    with gzip.open(tmp_path / "rpi_trades_test.csv.gz", "rt") as f:
        rows = list(csv.DictReader(f))
    ids_a = [int(r["id"]) for r in rows if r["symbol"] == "A"]
    assert ids_a == sorted(set(ids_a)) and ids_a[0] == 1
    assert len(rows) == sum(v["trades"] for v in s["symbols"].values())
    assert json.loads((tmp_path / "rpi_run_test.json").read_text())["run_id"] == "test"


def test_api_backs_off_on_rate_limit():
    calls = []
    slept = []

    def get(path, params):
        calls.append(path)
        if len(calls) == 1:
            return 429, "slow down", {"Retry-After": "7"}
        return 200, [], {}

    api = rec.Api(get=get, sleep=slept.append)
    assert api.get("trades", {}) == [] and slept == [7.0] and api.n_429 == 1
