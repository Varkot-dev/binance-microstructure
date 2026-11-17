"""Week 0 look: what changed alongside the rise in sign predictability (Q10)?

For each of the 10 Q10 symbols and 5 periods, collect the fresh-model accuracy
(the diagonal of Q10's transfer matrix) and candidate drivers measured from the
raw trades of the same month: activity, typical trade size in USD, the share of
small trades, the share of events in same-millisecond bursts, and the repeat
rate of the trade sign. Then ask, within each symbol, which driver's change
moves with the change in accuracy. Ten symbols, so this is descriptive only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

from microstructure.data.events import to_aggressor_events

PERIODS = ["2023-06", "2023-07", "2024-07", "2025-07", "2026-07"]
ROOT = Path("data")


def drivers(symbol: str, period: str) -> dict:
    raw = pl.scan_parquet(ROOT / "parquet" / "aggTrades" / symbol / f"{period}*.parquet")
    raw = raw.select("ts", "price", "qty", "is_buyer_maker").collect()
    ev = to_aggressor_events(raw)
    notional = (ev["price"] * ev["qty"]).to_numpy() if "price" in ev.columns else None
    days = raw["ts"].dt.date().n_unique()
    sign = np.where(ev["is_buyer_maker"].to_numpy(), -1, 1) if "is_buyer_maker" in ev.columns \
        else ev["sign"].to_numpy()
    ts = ev["ts"].dt.epoch("ms").to_numpy()
    gap = np.diff(ts)
    out = {
        "symbol": symbol, "period": period, "days": days,
        "events_per_day": ev.height / days,
        "prints_per_event": raw.height / ev.height,
        "repeat_rate": float((sign[1:] == sign[:-1]).mean()),
        "share_gap_le_1ms": float((gap <= 1).mean()),
        "median_gap_ms": float(np.median(gap)),
    }
    if notional is not None:
        out |= {"median_notional_usd": float(np.median(notional)),
                "share_under_1k_usd": float((notional < 1_000).mean())}
    return out


def main() -> None:
    q10 = json.loads(Path("results/q10_drift.json").read_text())
    acc = q10["transfer"]["accuracy"]
    rows = []
    for s in q10["symbols"]:
        for i, p in enumerate(PERIODS):
            r = drivers(s, p)
            r["acc_gbm_all"] = acc["gbm_all"]["per_symbol"][s][i][i]
            r["acc_linear"] = acc["linear"]["per_symbol"][s][i][i]
            r["acc_persistence"] = acc["persistence"]["per_symbol"][s][i][i]
            rows.append(r)
            print(s, p, {k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()
                         if k not in ("symbol", "period")}, flush=True)
    df = pl.DataFrame(rows)
    df.write_json(sys.argv[1] if len(sys.argv) > 1 else "e0_what_changed.json")
    # Within-symbol changes from 2023-06: which driver moves with accuracy?
    base = df.filter(pl.col("period") == "2023-06")
    ch = df.filter(pl.col("period") != "2023-06").join(base, on="symbol", suffix="_0")
    cols = [c for c in df.columns if c not in ("symbol", "period", "days") and not c.startswith("acc")]
    y = (ch["acc_gbm_all"] - ch["acc_gbm_all_0"]).to_numpy()
    print("\nCorrelation of the change in gbm_all accuracy with the change in each driver "
          f"(n = {len(y)} symbol-periods, 10 symbols):")
    for c in cols:
        x = ch[c].to_numpy() - ch[f"{c}_0"].to_numpy()
        if "per_day" in c or "notional" in c or "gap_ms" in c:
            x = np.log(ch[c].to_numpy()) - np.log(ch[f"{c}_0"].to_numpy())
        print(f"  {c:22s} r = {np.corrcoef(x, y)[0, 1]:+.2f}")


if __name__ == "__main__":
    main()
