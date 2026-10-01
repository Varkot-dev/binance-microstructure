from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from microstructure.data.catalog import parquet_path
from microstructure.signals.load import events_with_prior_mid, load_events


def _write_agg(root: Path, symbol: str, period: str, rows):
    p = parquet_path(root, symbol, "aggTrades", period)
    p.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        rows,
        schema={
            "agg_trade_id": pl.Int64, "price": pl.Float64, "qty": pl.Float64,
            "first_trade_id": pl.Int64, "last_trade_id": pl.Int64,
            "ts": pl.Datetime("ms", "UTC"), "is_buyer_maker": pl.Boolean,
        },
        orient="row",
    ).write_parquet(p)


def _ts(ms: int):
    return datetime(2023, 6, 1, 0, 0, 0, ms * 1000, tzinfo=UTC)


def test_load_events_concats_periods_in_order(tmp_path: Path):
    _write_agg(tmp_path, "BTCUSDT", "2023-06", [[1, 100.0, 1.0, 1, 1, _ts(1), False]])
    _write_agg(tmp_path, "BTCUSDT", "2023-07", [[2, 101.0, 1.0, 2, 2, _ts(2), True]])
    ev = load_events(tmp_path, "BTCUSDT", ["2023-06", "2023-07"])
    assert ev.height == 2
    assert ev["sign"].to_list() == [1, -1]


def test_load_events_missing_period_raises_naming_all(tmp_path: Path):
    _write_agg(tmp_path, "BTCUSDT", "2023-06", [[1, 100.0, 1.0, 1, 1, _ts(1), False]])
    with pytest.raises(FileNotFoundError) as ei:
        load_events(tmp_path, "BTCUSDT", ["2023-06", "2023-07", "2023-08"])
    assert "2023-07" in str(ei.value) and "2023-08" in str(ei.value)


def test_events_with_prior_mid_strictly_before(tmp_path: Path):
    events = pl.DataFrame(
        {"ts": [_ts(5), _ts(10)], "sign": [1, -1], "qty": [1.0, 1.0],
         "price": [100.0, 100.0], "n_prints": [1, 1]},
        schema_overrides={"ts": pl.Datetime("ms", "UTC"), "sign": pl.Int8, "n_prints": pl.UInt32},
    )
    # The ms-10 quote has mid 100.0; the ms-3 quote has mid 90.0. A look-ahead
    # (non-strict) join would hand the ms-10 event the ms-10 mid of 100.0.
    bt = pl.DataFrame(
        {"update_id": [1, 2], "bid_price": [89.0, 99.0], "bid_qty": [1.0, 1.0],
         "ask_price": [91.0, 101.0], "ask_qty": [1.0, 1.0], "ts": [_ts(3), _ts(10)]},
        schema_overrides={"ts": pl.Datetime("ms", "UTC")},
    ).with_columns(((pl.col("bid_price") + pl.col("ask_price")) / 2).alias("mid"))
    out, n_dropped = events_with_prior_mid(events, bt)
    # Both events must see the ms-3 quote: ms 5 is after it, and ms 10 is the
    # same instant as the second quote, which is not strictly before.
    assert out["mid"].to_list() == [90.0, 90.0]
    assert n_dropped == 0


def test_events_with_prior_mid_tied_quote_timestamps_use_input_order(tmp_path: Path):
    events = pl.DataFrame(
        {"ts": [_ts(10)], "sign": [1], "qty": [1.0], "price": [100.0], "n_prints": [1]},
        schema_overrides={"ts": pl.Datetime("ms", "UTC"), "sign": pl.Int8, "n_prints": pl.UInt32},
    )
    # Two quotes share ms 5; the later one in input order (mid 102) prevails.
    bt = pl.DataFrame(
        {"update_id": [1, 2], "bid_price": [98.0, 101.0], "bid_qty": [1.0, 1.0],
         "ask_price": [100.0, 103.0], "ask_qty": [1.0, 1.0], "ts": [_ts(5), _ts(5)]},
        schema_overrides={"ts": pl.Datetime("ms", "UTC")},
    ).with_columns(((pl.col("bid_price") + pl.col("ask_price")) / 2).alias("mid"))
    out, _ = events_with_prior_mid(events, bt)
    assert out["mid"].to_list() == [102.0]


def test_events_with_prior_mid_drops_events_before_first_quote(tmp_path: Path):
    events = pl.DataFrame(
        {"ts": [_ts(1)], "sign": [1], "qty": [1.0], "price": [100.0], "n_prints": [1]},
        schema_overrides={"ts": pl.Datetime("ms", "UTC"), "sign": pl.Int8, "n_prints": pl.UInt32},
    )
    bt = pl.DataFrame(
        {"update_id": [1], "bid_price": [99.0], "bid_qty": [1.0],
         "ask_price": [101.0], "ask_qty": [1.0], "ts": [_ts(2)]},
        schema_overrides={"ts": pl.Datetime("ms", "UTC")},
    ).with_columns(((pl.col("bid_price") + pl.col("ask_price")) / 2).alias("mid"))
    out, n_dropped = events_with_prior_mid(events, bt)
    assert out.height == 0
    assert n_dropped == 1


def test_events_with_prior_mid_rejects_non_ms_timestamps():
    events = pl.DataFrame(
        {"ts": [_ts(5)], "sign": [1], "qty": [1.0],
         "price": [100.0], "n_prints": [1]},
        schema_overrides={"ts": pl.Datetime("us", "UTC"), "sign": pl.Int8, "n_prints": pl.UInt32},
    )
    bt = pl.DataFrame(
        {"update_id": [1], "bid_price": [99.0], "bid_qty": [1.0],
         "ask_price": [101.0], "ask_qty": [1.0], "ts": [_ts(3)]},
        schema_overrides={"ts": pl.Datetime("ms", "UTC")},
    ).with_columns(((pl.col("bid_price") + pl.col("ask_price")) / 2).alias("mid"))
    with pytest.raises(ValueError) as ei:
        events_with_prior_mid(events, bt)
    assert "events ts must be Datetime('ms', 'UTC')" in str(ei.value)
