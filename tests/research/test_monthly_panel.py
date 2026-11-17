"""Offline tests for the Part B monthly panel aggregation (no network)."""
from __future__ import annotations

import datetime as dt
import importlib.util
import math
import sys
import zipfile
from pathlib import Path

import polars as pl
import pytest

PATH = (Path(__file__).resolve().parents[2] / "research" / "market_evolution"
        / "build_monthly_panel.py")


@pytest.fixture(scope="module")
def mp():
    spec = importlib.util.spec_from_file_location("build_monthly_panel", PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses look the module up here
    spec.loader.exec_module(mod)
    return mod


def _ts(values: list[str]) -> pl.Series:
    return pl.Series(values).str.to_datetime(time_unit="ms")


def _daily(symbol: str, start: str, closes: list[float], volume: float = 10.0,
           skip: set[int] | None = None) -> pl.DataFrame:
    d0 = dt.date.fromisoformat(start)
    rows = []
    prev = closes[0]
    for i, c in enumerate(closes):
        if skip and i in skip:
            prev = c
            continue
        rows.append({
            "symbol": symbol, "date": d0 + dt.timedelta(days=i), "open": prev,
            "high": max(prev, c), "low": min(prev, c), "close": c, "volume": volume,
            "quote_volume": volume * c, "count": int(volume),
            "taker_buy_quote_volume": 0.5 * volume * c,
        })
        prev = c
    return pl.DataFrame(rows)


def test_running_drawdown_uses_no_future_data(mp):
    # Jan rises to 10, Feb falls to 5; March spikes to 100.
    jan = [float(x) for x in range(1, 11)] + [10.0] * 21
    feb = [8.0] * 14 + [5.0] * 15  # 2024 is a leap year
    mar = [100.0] * 31
    full = _daily("X", "2024-01-01", jan + feb + mar)
    past = full.filter(pl.col("date") < dt.date(2024, 3, 1))
    f_full = mp.kline_month_features(full)
    f_past = mp.kline_month_features(past)
    cols = ["dd_month_end", "max_dd"]
    a = f_full.filter(pl.col("month") <= "2024-02").select("month", *cols)
    b = f_past.select("month", *cols)
    assert a.equals(b), "adding March changed earlier drawdowns"
    feb_row = f_full.filter(pl.col("month") == "2024-02").row(0, named=True)
    assert feb_row["dd_month_end"] == pytest.approx(5 / 10 - 1)
    assert feb_row["max_dd"] == pytest.approx(-0.5)
    jan_row = f_full.filter(pl.col("month") == "2024-01").row(0, named=True)
    assert jan_row["dd_month_end"] == pytest.approx(0.0)
    assert f_full.filter(pl.col("month") == "2024-03")["dd_month_end"][0] == 0.0


def test_month_features_do_not_reach_into_previous_month(mp):
    # Same March bars, very different February: March statistics must not change.
    mar = _daily("X", "2024-03-01", [10.0, 11.0, 9.0, 12.0] + [12.0] * 27)
    a = pl.concat([_daily("X", "2024-02-01", [1.0] * 29), mar])
    b = pl.concat([_daily("X", "2024-02-01", [50.0] * 29), mar])
    cols = ["ret_month", "realized_vol", "mean_range", "quote_volume", "trading_days"]
    ra = mp.kline_month_features(a).filter(pl.col("month") == "2024-03").select(cols)
    rb = mp.kline_month_features(b).filter(pl.col("month") == "2024-03").select(cols)
    assert ra.equals(rb)


def test_ghost_month_flag(mp):
    live = _daily("G", "2024-01-01", [2.0] * 31)
    ghost = _daily("G", "2024-02-01", [2.0] * 29, volume=0.0)
    kl = mp.kline_month_features(pl.concat([live, ghost]))
    fu = mp.funding_month_features(pl.DataFrame({
        "symbol": ["G", "G", "G"],
        "time": _ts(["2024-01-05", "2024-02-05", "2024-03-05"]),
        "funding_interval_hours": [8.0, 8.0, 8.0],
        "rate": [0.0002, 0.0001, 0.0001],
    }))
    me = mp.metrics_month_features(pl.DataFrame(
        schema={"symbol": pl.Utf8, "metrics_date": pl.Date, "metrics_rows": pl.Int32,
                "ts": pl.Datetime("us"), "oi_usd": pl.Float64, "ls_account": pl.Float64,
                "ls_toptrader_account": pl.Float64}))
    p = mp.assemble_panel(kl, fu, me).sort("month")
    assert p["month"].to_list() == ["2024-01", "2024-02", "2024-03"]
    assert p["ghost_month"].to_list() == [False, True, True]
    assert p["has_klines"].to_list() == [True, True, False]
    assert p["trading_days"].to_list() == [31, 0, 0]
    assert p["age_months"].to_list() == [0, 1, 2]
    feb = p.row(1, named=True)
    assert feb["quote_volume"] == 0.0
    assert feb["taker_buy_share"] is None
    assert feb["last_trading_day"] is None


def test_month_with_missing_days(mp):
    closes = [10.0 + i for i in range(31)]
    d = _daily("M", "2024-03-01", closes, skip={3, 4, 5, 20})
    f = mp.kline_month_features(d).row(0, named=True)
    assert f["n_kline_days"] == 27
    assert f["trading_days"] == 27
    assert f["close_last"] == 40.0
    assert f["ret_month"] == pytest.approx(40.0 / 10.0 - 1)
    assert f["quote_volume"] == pytest.approx(sum(10.0 * c for i, c in enumerate(closes)
                                                  if i not in {3, 4, 5, 20}))
    assert f["taker_buy_share"] == pytest.approx(0.5)
    assert not math.isnan(f["realized_vol"])
    fu = mp.funding_month_features(pl.DataFrame(
        schema={"symbol": pl.Utf8, "time": pl.Datetime("ms"),
                "funding_interval_hours": pl.Float64, "rate": pl.Float64}))
    me = mp.metrics_month_features(pl.DataFrame(
        schema={"symbol": pl.Utf8, "metrics_date": pl.Date, "metrics_rows": pl.Int32,
                "ts": pl.Datetime("us"), "oi_usd": pl.Float64, "ls_account": pl.Float64,
                "ls_toptrader_account": pl.Float64}))
    p = mp.assemble_panel(mp.kline_month_features(d), fu, me).row(0, named=True)
    assert p["days_in_month"] == 31
    assert p["missing_kline_days"] == 4
    assert p["ghost_month"] is False


def test_funding_features(mp):
    fu = pl.DataFrame({
        "symbol": ["F"] * 3,
        "time": _ts(["2024-05-01 00:00", "2024-05-01 08:00", "2024-05-01 16:00"]),
        "funding_interval_hours": [8.0, 4.0, 4.0],
        "rate": [0.001, -0.003, 0.0005],
    })
    r = mp.funding_month_features(fu).row(0, named=True)
    assert r["n_funding"] == 3
    assert r["funding_mean"] == pytest.approx((0.001 - 0.003 + 0.0005) / 3)
    assert r["funding_abs_mean"] == pytest.approx((0.001 + 0.003 + 0.0005) / 3)
    assert r["funding_interval_min_h"] == 4.0


def _zip(tmp: Path, text: str) -> Path:
    p = tmp / "f.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("f.csv", text)
    return p


def test_parse_klines_with_and_without_header(mp, tmp_path):
    row = "1733011200000,1,2,0.5,1.5,100,1733097599999,150,7,40,60,0\n"
    hdr = ",".join(mp.KLINE_COLS) + "\n"
    a = mp.parse_klines(mp.read_zip_csv(_zip(tmp_path, hdr + row), mp.KLINE_COLS), "S")
    b = mp.parse_klines(mp.read_zip_csv(_zip(tmp_path, row), mp.KLINE_COLS), "S")
    assert a.equals(b)
    assert a["date"][0] == dt.date(2024, 12, 1)
    assert a["count"][0] == 7


def test_metrics_snapshot_takes_last_row_with_oi(mp, tmp_path):
    hdr = ",".join(mp.METRIC_COLS) + "\n"
    body = (
        "2024-05-31 23:50:00,S,10,1000,1.2,1.1,1.3,0.9\n"
        "2024-05-31 23:55:00,S,11,1100,1.4,1.1,1.5,0.9\n"
        "2024-05-31 23:56:00,S,,,,,,\n"
    )
    df = mp.read_zip_csv(_zip(tmp_path, hdr + body), mp.METRIC_COLS)
    snap = mp.parse_metrics_last(df, "S", "2024-05-31")
    r = mp.metrics_month_features(snap).row(0, named=True)
    assert r["oi_usd_month_end"] == 1100.0
    assert r["ls_account_month_end"] == 1.5
    assert r["metrics_rows"] == 3
    empty = mp.parse_metrics_last(
        mp.read_zip_csv(_zip(tmp_path, hdr + "2024-06-30 00:00:00,S,,,,,,\n"),
                        mp.METRIC_COLS), "S", "2024-06-30")
    assert empty.height == 1 and empty["oi_usd"][0] is None


def test_months_in_keys_drops_stray_files(mp):
    keys = [
        ("data/futures/um/monthly/klines/S/1d/S-1d-2024-01.zip", 10),
        ("data/futures/um/monthly/klines/S/1d/S-1d-2024-01.zip.CHECKSUM", 1),
        ("data/futures/um/monthly/klines/S/1d/part-00000-abc-c000.zip", 99),
    ]
    assert mp.months_in_keys(keys, r"/S-1d-(\d{4}-\d{2})\.zip$") == {"2024-01": 10}


def test_last_complete_month(mp):
    assert mp.last_complete_month(dt.date(2026, 11, 17)) == "2026-10"
    assert mp.last_complete_month(dt.date(2026, 1, 1)) == "2025-12"
