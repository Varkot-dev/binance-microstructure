"""Weeks 1 to 2: order-flow proxies for the 10 Q10 symbols x 5 periods.

Applies `microstructure.evolution.proxies.contract_month_proxies` to each
contract-month of local aggTrades (data/parquet/aggTrades/<SYMBOL>/<YYYY-MM>.parquet),
one month at a time (BTC months are about 20M events), and joins the fresh-model
accuracies from e0_what_changed.json (which come from Q10's transfer matrix).

Only the monthly file is read. The daily files for 2023-06-05..18 and 2023-07-03..16
duplicate days of the monthly file, so a "<period>*.parquet" glob (as in
e0_what_changed.py) would read those days twice.

Run from the repository root:
    PYTHONPATH=src .venv/bin/python research/market_evolution/e1_proxies.py \
        [--symbols DOGEUSDT ...] [--periods 2023-06 ...] [--out PATH]
The output is rewritten after every contract-month, so a partial run keeps its rows.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import polars as pl

from microstructure.data.events import to_aggressor_events
from microstructure.evolution.proxies import NEAR_CIRCULAR, PROXY_DOCS, contract_month_proxies

HERE = Path(__file__).resolve().parent
ROOT = Path("data") / "parquet" / "aggTrades"
PERIODS = ["2023-06", "2023-07", "2024-07", "2025-07", "2026-07"]
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT", "LINKUSDT",
           "LTCUSDT", "AVAXUSDT", "1000PEPEUSDT"]
RAW_COLS = ["agg_trade_id", "ts", "price", "qty", "first_trade_id", "last_trade_id",
            "is_buyer_maker"]
ACC_COLS = ["acc_gbm_all", "acc_linear", "acc_persistence"]


def month_proxies(symbol: str, period: str) -> dict:
    raw = pl.read_parquet(ROOT / symbol / f"{period}.parquet", columns=RAW_COLS)
    raw = raw.filter(pl.col("ts").dt.strftime("%Y-%m") == period)
    if not raw["agg_trade_id"].is_sorted():
        raw = raw.sort("agg_trade_id")
    events = to_aggressor_events(raw)
    out = {"symbol": symbol, "period": period} | contract_month_proxies(events, raw)
    out["n_raw"] = raw.height
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=SYMBOLS)
    ap.add_argument("--periods", nargs="+", default=PERIODS)
    ap.add_argument("--out", default=str(HERE / "e1_proxies.json"))
    args = ap.parse_args()

    e0 = {(r["symbol"], r["period"]): r
          for r in json.loads((HERE / "e0_what_changed.json").read_text())}
    rows = []
    for s in args.symbols:
        for p in args.periods:
            t = time.time()
            r = month_proxies(s, p)
            for c in ACC_COLS:
                r[c] = e0.get((s, p), {}).get(c)
            rows.append(r)
            Path(args.out).write_text(json.dumps({
                "description": "order-flow proxies per contract-month (see docs); accuracies "
                               "joined from e0_what_changed.json (Q10 fresh-model diagonal)",
                "near_circular": list(NEAR_CIRCULAR),
                "docs": PROXY_DOCS,
                "rows": rows,
            }, indent=1))
            show = {k: float(f"{v:.4g}") if isinstance(v, float) else v for k, v in r.items()
                    if k not in ("symbol", "period")}
            print(s, p, f"{time.time() - t:.0f}s", show, flush=True)


if __name__ == "__main__":
    main()
