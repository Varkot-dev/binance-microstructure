from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "p1_scan", ROOT / "research" / "liquidations" / "p1_scan.py")
p1 = importlib.util.module_from_spec(_spec)
sys.modules["p1_scan"] = p1  # dataclasses look their module up here
_spec.loader.exec_module(p1)


# --------------------------------------------------------------------------- locks

def test_mask_hashes_match_committed_texts():
    assert p1.sha256_file(p1.MASK) == p1.MASK_SHA
    assert p1.sha256_file(p1.MASK_V1) == p1.MASK_V1_SHA


def test_plan_and_screen_are_locked():
    p1.check_locks()  # raises SystemExit if any locked text changed


def test_refuses_without_plan_lock(monkeypatch):
    monkeypatch.setattr(p1, "PREREG_SHA", None)
    with pytest.raises(SystemExit, match="not locked"):
        p1.check_locks()
    p1.check_locks(require_plan=False)  # validate may run before the lock


def test_refuses_when_plan_changed(monkeypatch, tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text("v1")
    monkeypatch.setattr(p1, "PREREG", plan)
    monkeypatch.setattr(p1, "PREREG_SHA", hashlib.sha256(b"v1").hexdigest())
    monkeypatch.setattr(p1, "SCREEN_SHA", p1.sha256_file(p1.SCREEN))
    p1.check_locks()
    plan.write_text("v2")
    with pytest.raises(SystemExit, match="changed"):
        p1.check_locks()


def test_refuses_when_mask_changed(monkeypatch):
    monkeypatch.setattr(p1, "MASK_SHA", "0" * 64)
    with pytest.raises(SystemExit, match="changed"):
        p1.check_locks(require_plan=False)


# ------------------------------------------------------------------- test machinery

def test_shift_test_detects_prior_drop_and_not_noise():
    rng = np.random.default_rng(0)
    n, k = 300, 400
    null = rng.normal(0, 0.01, (n, k))
    r = np.column_stack([rng.normal(-0.01, 0.01, n), null])
    out = p1.shift_test(r, "bid")
    assert out["p"] < 0.01 and out["median"] < out["null_median"]
    assert p1.shift_test(r, "ask")["p"] > 0.9
    r0 = np.column_stack([rng.normal(0, 0.01, n), null])
    assert 0.02 < p1.shift_test(r0, "bid")["p"] < 0.98
    assert p1.shift_test(np.empty((0, k + 1)), "bid")["n"] == 0


def test_shift_test_p_never_zero():
    r = np.column_stack([np.full(10, -1.0), np.zeros((10, 99))])
    assert p1.shift_test(r, "bid")["p"] == pytest.approx(1 / 100)


def test_shift_test_cluster_statistic_downweights_one_big_wave():
    rng = np.random.default_rng(1)
    big = np.column_stack([np.full(100, -0.05), rng.normal(0, 0.01, (100, 200))])
    small = np.column_stack([rng.normal(0, 0.01, 20), rng.normal(0, 0.01, (20, 200))])
    r = np.vstack([big, small])
    cl = np.r_[np.zeros(100, int), np.arange(1, 21)]
    pooled = p1.shift_test(r, "bid")
    clustered = p1.shift_test(r, "bid", cluster=cl)
    assert pooled["p"] < 0.01 < clustered["p"]


def test_holm():
    assert p1.holm({"a": 0.01, "b": 0.04}) == {"a": True, "b": True}
    assert p1.holm({"a": 0.03, "b": 0.04}) == {"a": False, "b": False}
    assert p1.holm({"a": 0.02, "b": 0.5}) == {"a": True, "b": False}
    assert p1.holm({"a": float("nan"), "b": 0.01}) == {"a": False, "b": True}


def test_prior_returns_use_minutes_strictly_before_onset():
    t0 = 1_700_000_040 - 1_700_000_040 % 60
    close = np.exp(np.arange(500) / 100.0)  # log close rises 0.01 per minute
    m = np.array([t0 + 200 * 60 + 17])  # onset 17 s into minute 200
    r = p1.prior_returns(t0, close, m, 60)
    assert r[0] == pytest.approx(0.60)  # close of 199 vs close of 139
    assert np.isnan(p1.prior_returns(t0, close, np.array([t0 + 30 * 60]), 60))[0]


def test_shards_partition_the_symbols():
    syms = [f"S{i}USDT" for i in range(10)]
    parts = [p1.shard_symbols(syms, f"{i}/3") for i in range(3)]
    assert sorted(s for part in parts for s in part) == sorted(syms)
    assert parts[0] == ["S0USDT", "S3USDT", "S6USDT", "S9USDT"]
    with pytest.raises(ValueError):
        p1.shard_symbols(syms, "3/3")


def test_is_usdt_perp():
    assert p1.is_usdt_perp("BTCUSDT") and p1.is_usdt_perp("1000PEPEUSDT")
    assert not p1.is_usdt_perp("BTCUSDT_250328") and not p1.is_usdt_perp("BTCUSDC")


# ------------------------------------------------------------- end to end, offline

def _zip(name: str, body: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(zipfile.ZipInfo(name.replace(".zip", ".csv"), (2026, 1, 1, 0, 0, 0)), body)
    return buf.getvalue()


def _day_files(d: dt.date, crossed_at: int | None) -> dict[str, str]:
    day0 = int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.UTC).timestamp())
    book = ["timestamp,percentage,depth,notional"]
    for i in range(2880):
        t = dt.datetime.fromtimestamp(day0 + 30 * i + 3, dt.UTC).strftime("%Y-%m-%d %H:%M:%S")
        for j, pct in enumerate(p1.bd.CORE):
            dep = 10 * abs(pct) + (i % 7) * 0.01 + j * 0.001
            vw = 100 * (1 + pct / 200)
            if crossed_at is not None and i == crossed_at and pct == -1:
                vw = 103.0
            book.append(f"{t},{int(pct)},{dep:.6f},{dep * vw:.6f}")
    kl = [("open_time,open,high,low,close,volume,close_time,quote_volume,count,"
           "taker_buy_volume,taker_buy_quote_volume,ignore")]
    for m in range(1440):
        o = (day0 + 60 * m) * 1000
        kl.append(f"{o},100,100.1,99.9,100,10,{o + 59999},1000,5,{4 + ((m // 5) % 7) * 0.3},400,0")
    met = [("create_time,symbol,sum_open_interest,sum_open_interest_value,"
            "count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,"
            "count_long_short_ratio,sum_taker_long_short_vol_ratio")]
    for r in range(288):
        t = dt.datetime.fromtimestamp(day0 + 300 * r, dt.UTC).strftime("%Y-%m-%d %H:%M:%S")
        buy = 5 * (4 + (r % 7) * 0.3)  # taker buy of the block starting at the label
        met.append(f"{t},TESTUSDT,{1000 + r},{100000 + r},1,1,1,{buy / (50 - buy):.6f}")
    return {"bookDepth": "\n".join(book), "klines": "\n".join(kl), "metrics": "\n".join(met)}


class FakeArchive:
    def __init__(self, days: dict[dt.date, int | None]):
        self.files: dict[str, bytes] = {}
        for d, crossed in days.items():
            for kind, body in _day_files(d, crossed).items():
                path = p1._path(kind, "TESTUSDT", d)
                self.files[path] = _zip(path.rsplit("/", 1)[-1], body)

    def list_dir(self, prefix: str):
        keys = [p1.Key(p.rsplit("/", 1)[-1], "2026-01-01T00:00:00.000Z", "etag", len(b))
                for p, b in self.files.items() if p.startswith(prefix)
                and "/" not in p[len(prefix):]]
        return [], keys

    def fetch(self, path: str):
        b = self.files.get(path)
        return None if b is None else (b, hashlib.sha256(b).hexdigest())


def test_scan_symbol_end_to_end_offline():
    d0, d1 = dt.date(2024, 3, 10), dt.date(2024, 3, 11)
    arch = FakeArchive({d0: None, d1: 1500})
    res = p1.scan_symbol("TESTUSDT", arch, d0, d1, workers=2, log=lambda s: None)
    days = res["days"]
    assert days["n_snap"].to_list() == [2880, 2880]
    assert days["n_S1"].to_list() == [0, 1]
    # v2 (primary): an isolated crossing removes only itself
    assert days["n_S6"].to_list() == [0, 0]
    assert days["d1_s"].to_list() == [True, True]
    # v1: the crossing plus its S6 buffer removes 41 snapshots, a 1,260 s gap between
    # valid ones, over D1's 900 s limit, so one glitch fails the contract-day
    assert days["n_S6_v1"].to_list() == [0, 40]
    assert days["d1_s_v1"].to_list() == [True, False]
    assert days["max_gap_s_v1"].to_list()[1] == 1260
    rules = set(res["intervals"]["rule"])
    assert "S6_v1" in rules and "S6" not in rules
    assert {"d1_s_s3_10", "d1_s_s3_40"} <= set(days.columns)
    assert res["manifest"].height == 6 and res["manifest"]["error"].null_count() == 6
    assert res["manifest"]["zip_member_mtime"].to_list()[0] == "2026-01-01T00:00:00"
    assert res["metric_days"]["convention"].to_list() == ["start", "start"]
    on = res["onsets"]
    assert on.height == 1 and on["side"][0] == "bid"
    r60 = res["r60"]
    assert r60.shape == (1, 1 + p1.SHIFT_HOURS.size)
    assert r60[0, 0] == pytest.approx(0.0)  # flat synthetic price
    # only shifts landing on day one with a full prior hour have data: -24 h to -35 h
    finite = p1.SHIFT_HOURS[np.isfinite(r60[0, 1:])]
    assert sorted(finite.tolist()) == list(range(-35, -23))


def test_save_symbol_writes_resumable_outputs(tmp_path):
    d0 = dt.date(2024, 3, 10)
    res = p1.scan_symbol("TESTUSDT", FakeArchive({d0: 100}), d0, d0, workers=1,
                         log=lambda s: None)
    p1.save_symbol("TESTUSDT", res, root=tmp_path)
    out = tmp_path / "TESTUSDT"
    assert (out / "DONE").exists() and (out / "days.parquet").exists()
    z = np.load(out / "returns.npz")
    assert set(z.files) >= {"r15", "r60", "r240", "r60_s3_10", "r60_s3_40"}


def test_shifted_times_near_other_corruption_starts_are_excluded():
    d0, d1 = dt.date(2024, 3, 10), dt.date(2024, 3, 11)
    res = p1.scan_symbol("TESTUSDT", FakeArchive({d0: 1500, d1: 1500}), d0, d1, workers=2,
                         log=lambda s: None)
    assert res["onsets"].height == 2  # 24 h apart, so both survive declustering
    second = res["r60"][1, 1:]
    j = int(np.flatnonzero(p1.SHIFT_HOURS == -24)[0])
    assert np.isnan(second[j])  # lands exactly on the first onset
    k = int(np.flatnonzero(p1.SHIFT_HOURS == -30)[0])
    assert np.isfinite(second[k])  # 6 h away from it: allowed


def test_episodes_merge_runs_across_symbols():
    import polars as pl

    iv = pl.DataFrame({
        "symbol": ["A", "B", "C", "A"], "rule": ["S1", "S3", "S3", "S0"],
        "band": [None, -1.0, 1.0, None], "side": ["bid", "bid", "ask", "na"],
        "start_ts": [0, 1800, 20_000, 0], "end_ts": [7200, 9000, 30_000, 99_999],
        "n_snap": [1, 1, 1, 1]})
    ep = p1.episodes(iv)
    assert ep["n_symbols"].to_list() == [2, 1]  # A and B merged; C later; S0 ignored
    assert ep["rules"].to_list() == ["S1+S3", "S3"]


def test_write_report_runs_on_a_scan():
    import polars as pl

    d0 = dt.date(2024, 3, 10)
    res = p1.scan_symbol("TESTUSDT", FakeArchive({d0: 100}), d0, d0, workers=1,
                         log=lambda s: None)
    days = res["days"]
    d3 = p1.bd.d3_dropped_dates(days).join(
        p1.bd.d3_dropped_dates(days, col="d1_s_v1").select(
            "date", pl.col("d3_dropped").alias("d3_dropped_v1")), on="date")
    t1 = {"primary": {"bid": {"n": 1, "median": -0.01, "null_median": 0.0, "n_shifts": 9,
                              "p": 0.1, "share_predicted_sign": 1.0, "null_share": 0.5}},
          "holm_reject": {"bid": False}, "secondary": {"bid:h15": {"n": 1, "p": 0.5}}}
    md = p1.write_report(days, d3, res["intervals"], res["metric_days"], res["manifest"],
                         res.get("metric_flags", pl.DataFrame()), t1)
    assert "## 1. Share removed by each rule (D5)" in md
    assert "fails D1 (d1_s_v1)" in md and "Holm rejections" in md
