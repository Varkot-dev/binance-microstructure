import gzip
import json

from microstructure.hyperliquid.recorder import (
    HourlyWriter,
    builder_dexes,
    compact_ctxs,
    gzip_bytes,
    live_perps,
    sha256_file,
)

H0 = 1_763_596_800_000  # 2025-11-20T00:00:00Z


def test_gzip_is_deterministic(tmp_path):
    a, b = tmp_path / "a.gz", tmp_path / "b.gz"
    gzip_bytes(a, b'{"x":1}')
    gzip_bytes(b, b'{"x":1}')
    assert sha256_file(a) == sha256_file(b)
    assert gzip.decompress(a.read_bytes()) == b'{"x":1}'


def test_hourly_writer_rotates_and_reports(tmp_path):
    closed = []
    w = HourlyWriter(tmp_path, "run1", lambda p, n: closed.append((p.name, n)))
    w.write("trades", {"i": 1}, H0)
    w.write("trades", {"i": 2}, H0 + 59 * 60_000)
    first = w.write("trades", {"i": 3}, H0 + 60 * 60_000)
    assert first is not None and closed == [("trades_20251120T00_run1.jsonl.gz", 2)]
    w.close_all()
    assert closed[-1] == ("trades_20251120T01_run1.jsonl.gz", 1)
    lines = gzip.decompress(first.read_bytes()).decode().splitlines()
    assert [json.loads(x)["i"] for x in lines] == [1, 2]


def test_market_list_helpers():
    meta = {"universe": [{"name": "BTC"}, {"name": "MATIC", "isDelisted": True}, {"name": "ETH"}]}
    assert live_perps(meta) == ["BTC", "ETH"]
    assert builder_dexes([None, {"name": "xyz"}]) == ["xyz"]
    assert compact_ctxs([meta, [{"oi": "1"}] * 3]) == {"names": ["BTC", "MATIC", "ETH"], "ctxs": [{"oi": "1"}] * 3}
