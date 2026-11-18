"""Offline tests of the pure rules in research/market_evolution/build_lifecycle.py.

No network: only the rule functions are called."""
from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "research" / "market_evolution" / "build_lifecycle.py"
_spec = importlib.util.spec_from_file_location("build_lifecycle", _PATH)
bl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bl)


def _days(start: date, n: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


def test_is_usdt_perp():
    assert bl.is_usdt_perp("BTCUSDT")
    assert bl.is_usdt_perp("1000PEPEUSDT")
    assert not bl.is_usdt_perp("BTCUSDT_250328")
    assert not bl.is_usdt_perp("ETHBTC")
    assert not bl.is_usdt_perp("BTCUSDC")
    assert not bl.is_usdt_perp("USDT")


def test_split_lives_gap_rule():
    a = _days(date(2021, 1, 1), 100)
    # dates 30 days apart (gap_days = 30) stay one life
    b = _days(a[-1] + timedelta(days=30), 10)
    assert len(bl.split_lives(a + b)) == 1
    # 31 days apart starts a second life
    c = _days(a[-1] + timedelta(days=31), 10)
    lives = bl.split_lives(list(reversed(a + c)))
    assert [len(x) for x in lives] == [100, 10]
    assert lives[1][0] == a[-1] + timedelta(days=31)


def test_is_alive():
    end = date(2026, 11, 16)
    assert bl.is_alive(end, end)
    assert bl.is_alive(date(2026, 11, 13), end)
    assert not bl.is_alive(date(2026, 11, 12), end)


@pytest.mark.parametrize(("old", "new", "k"), [
    (1.00, 1.05, 1.0), (0.001, 1.02, 1e-3), (2.0e-6, 2.1, 1e-6), (1500.0, 1.48, 1e3),
    (1.0, 1.5, None), (0.0, 1.0, None), (None, 1.0, None), (1.0, 0.0, None),
])
def test_price_match(old, new, k):
    assert bl.price_match(old, new) == k


def test_denomination_consistent():
    assert bl.ticker_multiplier("1000PEPEUSDT") == 1e3
    assert bl.ticker_multiplier("1000000BOBUSDT") == 1e6
    assert bl.ticker_multiplier("1MBABYDOGEUSDT") == 1e6
    assert bl.ticker_multiplier("MAVIAUSDT") == 1.0
    assert bl.denomination_consistent("RNDRUSDT", "RENDERUSDT", 1.0)
    # PEPE to 1000PEPE: the new contract price is 1000 times the old one
    assert bl.denomination_consistent("PEPEUSDT", "1000PEPEUSDT", 1e-3)
    assert not bl.denomination_consistent("XEMUSDT", "VANAUSDT", 1e-3)
    assert not bl.denomination_consistent("1000XUSDT", "YUSDT", 1.0)


def test_drop_artifact_days():
    days = {"2025-11-05": 7_000_000, "2025-11-06": 1_500_000, "2025-12-10": 323,
            "2025-12-11": 500}
    keep, drop = bl.drop_artifact_days(days, {"2025-12-10": 0, "2025-12-11": 3})
    assert drop == ["2025-12-10"]
    assert keep == ["2025-11-05", "2025-11-06", "2025-12-11"]
    # an unchecked tiny file is kept
    keep, drop = bl.drop_artifact_days({"2025-12-10": 323}, {})
    assert keep == ["2025-12-10"] and drop == []


def test_window_candidates():
    end = date(2024, 7, 16)
    starts = {"RNDRUSDT#1": date(2020, 1, 1), "RENDERUSDT#1": date(2024, 7, 26),
              "EARLYUSDT#1": date(2024, 7, 2), "LATEUSDT#1": date(2024, 7, 31)}
    assert bl.window_candidates(end, starts, "RNDRUSDT#1") == ["EARLYUSDT#1", "RENDERUSDT#1"]


def test_classify():
    assert bl.classify("RNDRUSDT", 0, 1, False)[:2] == ("renamed", "RENDERUSDT")
    assert bl.classify("AGIXUSDT", 0, 1, False)[:2] == ("merged", "FETUSDT")
    assert bl.classify("DEFIUSDT", 0, 1, False)[0] == "index"
    assert bl.classify("BTCUSDT", 0, 1, True)[0] == "alive"
    assert bl.classify("XEMUSDT", 0, 1, False)[0] == "delisted"
    # earlier life of a reused symbol, then the last life by the normal rules
    assert bl.classify("CVCUSDT", 0, 2, False)[:2] == ("reused-symbol", "CVCUSDT")
    assert bl.classify("CVCUSDT", 1, 2, True)[0] == "alive"
