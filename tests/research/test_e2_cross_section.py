"""Offline tests of research/market_evolution/e2_proxies_cross_section.py: the unit
list from Q14's JSON, the join with lifecycle and proxy records, and the partial
Spearman helper (synthetic data with a planted answer). No network."""
from __future__ import annotations

import importlib.util
import io
import zipfile
from pathlib import Path

import numpy as np
import polars as pl
import pytest

_PATH = (Path(__file__).resolve().parents[2] / "research" / "market_evolution"
         / "e2_proxies_cross_section.py")
_spec = importlib.util.spec_from_file_location("e2_proxies_cross_section", _PATH)
e2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e2)


def _metrics(acc: float, n: int) -> dict:
    return {"majority": 0.5, "persistence": 0.55, "linear": acc - 0.02, "gbm_all": acc,
            "n_events": n, "log10_events": float(np.log10(n)), "n_test_rows": n // 4,
            "lift": acc - 0.5, "linear_share": 0.8, "gbm_minus_linear": 0.02}


def _q14() -> dict:
    units = [
        {"set": "cross_2023", "symbol": "AAAUSDT", "period": "2023-06", "status_2023": "survivor",
         "outcome": "ok", "q9_symbol": False, "metrics": _metrics(0.60, 10**6)},
        {"set": "cross_2023", "symbol": "BBBUSDT", "period": "2023-06", "status_2023": "delisted",
         "outcome": "ok", "q9_symbol": False, "metrics": _metrics(0.58, 10**5)},
        {"set": "cross_2023", "symbol": "CCCUSDT", "period": "2023-06", "status_2023": "survivor",
         "outcome": "partial", "q9_symbol": False},
        {"set": "last_month", "symbol": "BBBUSDT", "period": "2025-01", "status_2023": "delisted",
         "outcome": "ok", "q9_symbol": False, "metrics": _metrics(0.57, 10**5)},
        {"set": "cross_2026", "symbol": "AAAUSDT", "period": "2026-07", "status_2023": "survivor",
         "outcome": "ok", "q9_symbol": False, "metrics": _metrics(0.64, 10**6)},
        {"set": "cross_2026", "symbol": "TSLAUSDT", "period": "2026-07",
         "status_2023": "new_listing_equity", "outcome": "ok", "q9_symbol": False,
         "metrics": _metrics(0.70, 10**6)},
        {"set": "cross_2026", "symbol": "NEWUSDT", "period": "2026-07",
         "status_2023": "new_listing", "outcome": "ok", "q9_symbol": False,
         "metrics": _metrics(0.62, 10**5)},
    ]
    zb = {"AAAUSDT": {"2023-06": 10, "2026-07": 20}, "BBBUSDT": {"2023-06": 5},
          "NEWUSDT": {"2026-07": 7}}
    return {"units": units, "universe": {"zip_bytes": zb}}


def _lifecycle() -> pl.DataFrame:
    csv = ("symbol,life,n_lives,first_trade_day,last_trade_day,alive_at_end,status,successor\n"
           "AAAUSDT,1,1,2020-01-01,2026-11-16,1,alive,\n"
           "BBBUSDT,1,1,2021-01-01,2025-01-20,0,delisted,\n"
           "NEWUSDT,1,2,2024-01-01,2024-05-01,0,reused-symbol,NEWUSDT\n"
           "NEWUSDT,2,2,2025-03-01,2026-11-16,1,alive,\n")
    return pl.read_csv(io.StringIO(csv), infer_schema=False).with_columns(
        pl.col("successor").fill_null(""))


def test_q14_units_keeps_fitted_and_lists_equity():
    units, excluded = e2.q14_units(_q14())
    assert [(u["set"], u["symbol"]) for u in units] == [
        ("cross_2023", "AAAUSDT"), ("cross_2023", "BBBUSDT"), ("cross_2026", "AAAUSDT"),
        ("cross_2026", "NEWUSDT")]
    assert [e["symbol"] for e in excluded] == ["TSLAUSDT"]
    assert excluded[0]["label"].startswith("stock")
    assert units[0]["zip_bytes"] == 10 and units[2]["zip_bytes"] == 20
    assert units[1]["metrics"]["gbm_all"] == 0.58


def test_join_rows_matches_by_symbol_and_period():
    units, _ = e2.q14_units(_q14())
    records = {
        ("AAAUSDT", "2023-06"): {"status": "ok", "proxies": {"run_mean": 1.5, "tick": 0.1}},
        ("AAAUSDT", "2026-07"): {"status": "ok", "proxies": {"run_mean": 2.5, "tick": 0.01}},
        ("BBBUSDT", "2023-06"): {"status": "failed", "reason": "boom", "proxies": None},
    }
    df = e2.join_rows(units, records, _lifecycle())
    assert df.height == 4
    r = {(x["symbol"], x["period"]): x for x in df.iter_rows(named=True)}
    assert r[("AAAUSDT", "2023-06")]["run_mean"] == 1.5
    assert r[("AAAUSDT", "2026-07")]["run_mean"] == 2.5
    assert r[("AAAUSDT", "2026-07")]["q14_gbm_all"] == 0.64
    assert r[("AAAUSDT", "2023-06")]["q14_gbm_all"] == 0.60
    assert r[("BBBUSDT", "2023-06")]["status"] == "failed"
    assert r[("BBBUSDT", "2023-06")]["reason"] == "boom"
    assert r[("BBBUSDT", "2023-06")]["run_mean"] is None
    assert r[("BBBUSDT", "2023-06")]["lifecycle_status"] == "delisted"
    assert r[("NEWUSDT", "2026-07")]["status"] == "not_run"
    # The life trading in 2026-07 is the second one, not the reused first life.
    assert r[("NEWUSDT", "2026-07")]["lifecycle_life"] == 2
    assert r[("NEWUSDT", "2026-07")]["lifecycle_status"] == "alive"


def test_partial_spearman_removes_a_common_driver():
    # x and y both depend on z only: strong raw correlation, partial near zero.
    rng = np.random.default_rng(0)
    z = rng.normal(size=4000)
    x = z + 0.3 * rng.normal(size=z.size)
    y = z + 0.3 * rng.normal(size=z.size)
    assert e2.spearman(x, y) > 0.8
    assert abs(e2.partial_spearman(x, y, z)) < 0.05


def test_partial_spearman_keeps_a_direct_link():
    # y depends on x beyond z: the partial correlation stays clearly positive, and
    # a monotone transform of any input leaves both coefficients unchanged.
    rng = np.random.default_rng(1)
    z = rng.normal(size=4000)
    w = rng.normal(size=z.size)
    x = z + w
    y = z + w + 0.5 * rng.normal(size=z.size)
    p = e2.partial_spearman(x, y, z)
    assert p > 0.7
    assert e2.partial_spearman(np.exp(x), y ** 3, z) == pytest.approx(p, abs=1e-12)
    assert e2.spearman(np.exp(x), y) == pytest.approx(e2.spearman(x, y), abs=1e-12)


def test_boot_corrs_interval_covers_and_drops_nan():
    rng = np.random.default_rng(2)
    z = rng.normal(size=300)
    x = z + rng.normal(size=300)
    y = z + rng.normal(size=300)
    x[:3] = np.nan
    out = e2.boot_corrs(x, y, z, n_boot=300, seed=0)
    assert out["n"] == 297
    lo, hi = out["partial_ci"]
    assert lo < 0 < hi
    assert out["rho_ci"][0] > 0.2


def test_chunked_ingest_matches_whole_file(tmp_path):
    lines = [("agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,"
              "is_buyer_maker")]
    for i in range(500):
        lines.append(f"{i},{100 + i * 0.01:.2f},{0.001 * (i + 1):.3f},{2 * i},{2 * i + 1},"
                     f"{1782864000000 + i},{'true' if i % 3 else 'false'}")
    zp = tmp_path / "X-aggTrades-2026-07.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("X-aggTrades-2026-07.csv", "\n".join(lines) + "\n")
    from microstructure.data.ingest import ingest_agg_trades
    whole = pl.read_parquet(ingest_agg_trades(zp, tmp_path))
    parts = e2.ingest_zip_chunked(zp, tmp_path / "parts", chunk_bytes=1000)
    assert len(parts) > 5
    assert pl.read_parquet(parts).equals(whole)
