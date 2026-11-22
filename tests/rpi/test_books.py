import gzip
import json

from microstructure.rpi import books
from microstructure.rpi import recorder as rec


class FakeClock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += max(s, 0.01)


def _book(n, shift=0):
    return {"lastUpdateId": 7, "E": 1, "T": 2,
            "bids": [[str(100 - i + shift), "1"] for i in range(n)],
            "asks": [[str(101 + i), "1"] for i in range(n)]}


def _api(clock, weight="10", fail=()):
    def get(path, params):
        clock.t += 0.01
        if params["symbol"] in fail and path == "rpiDepth":
            return 400, {"code": -4021}, {}
        assert params["limit"] == (books.DEPTH_LIMIT if path == "depth"
                                   else books.RPI_DEPTH_LIMIT)
        return 200, _book(30, shift=1 if path == "rpiDepth" else 0), \
            {"x-mbx-used-weight-1m": weight}
    return rec.Api(get=get, sleep=clock.sleep)


def test_trim_keeps_top_levels_and_ids():
    t = books.trim(_book(30), levels=3)
    assert t["u"] == 7 and t["E"] == 1 and t["T"] == 2
    assert [b[0] for b in t["bids"]] == ["100", "99", "98"] and len(t["asks"]) == 3
    assert books.trim({}) == {"u": None, "E": None, "T": None, "bids": [], "asks": []}


def test_snapshot_calls_ordinary_book_then_rpi_book():
    clock = FakeClock()
    s = books.snapshot(_api(clock), "A", clock)
    assert s["symbol"] == "A" and s["local_ms"] == sorted(s["local_ms"])
    assert s["depth"]["bids"][0][0] == "100" and s["rpi"]["bids"][0][0] == "101"
    assert len(s["rpi"]["bids"]) == books.LEVELS


def test_record_sweeps_every_symbol_and_writes_summary(tmp_path):
    clock = FakeClock()
    s = books.record(_api(clock, fail=("B",)), ["A", "B"], tmp_path,
                     int((clock.t + 95) * 1000), clock=clock, sleep=clock.sleep,
                     log=lambda m: None, run_id="t", sweep_s=30)
    assert s["sweeps"] == 4 and s["sweeps_skipped"] == 0
    assert s["symbols"]["A"] == {"snapshots": 4, "errors": 0}
    assert s["symbols"]["B"] == {"snapshots": 0, "errors": 4}
    with gzip.open(tmp_path / "rpi_books_t.jsonl.gz", "rt") as fh:
        rows = [json.loads(line) for line in fh]
    assert [r["symbol"] for r in rows] == ["A"] * 4
    assert json.loads((tmp_path / "rpi_books_run_t.json").read_text())["run_id"] == "t"


def test_record_yields_when_the_weight_budget_is_busy(tmp_path):
    clock = FakeClock()
    s = books.record(_api(clock, weight=str(books.WEIGHT_YIELD + 1)), ["A"], tmp_path,
                     int((clock.t + 95) * 1000), clock=clock, sleep=clock.sleep,
                     log=lambda m: None, run_id="t", sweep_s=30)
    # sweeps alternate: a sweep reads a busy header, the next one is skipped
    assert s["sweeps"] == 2 and s["sweeps_skipped"] == 2
