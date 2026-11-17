"""Month 0 audit: what does a resting quote at the best price actually earn?

For every aggregated trade print, the passive side was filled at the print
price. Its markout after tau is the passive side's gain against the mid at
t + tau, in bps of the mid before the trade. Averaged over prints this is the
classic realized spread: half the spread earned minus the adverse move that
follows. A market maker pays the maker fee out of it, so the realized spread is
the break-even maker fee for a naive quote that is always at the best price.

Uses training-window days only (2023-06-05..11), never Q11's July test days.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path("data/parquet")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]
DAYS = [f"2023-06-{d:02d}" for d in range(5, 12)]
TAUS_MS = [100, 1_000, 10_000, 60_000]


def one_day(symbol: str, day: str) -> pl.DataFrame:
    q = (pl.read_parquet(ROOT / "bookTicker" / symbol / f"{day}.parquet",
                         columns=["ts", "bid_price", "ask_price", "bid_qty", "ask_qty"])
         .filter((pl.col("ask_price") > pl.col("bid_price")) & (pl.col("bid_qty") > 0))
         .sort("ts")
         .with_columns(mid=(pl.col("bid_price") + pl.col("ask_price")) / 2))
    t = (pl.read_parquet(ROOT / "aggTrades" / symbol / f"{day}.parquet",
                         columns=["ts", "price", "qty", "is_buyer_maker"]).sort("ts"))
    # Quote strictly before the trade: shift the trade key back 1 ms for the asof match.
    t = t.with_columns(key=pl.col("ts") - pl.duration(milliseconds=1))
    t = t.join_asof(q.select("ts", "bid_price", "ask_price", "mid", "bid_qty", "ask_qty")
                    .rename({"ts": "key"}), on="key", strategy="backward")
    for tau in TAUS_MS:
        fut = q.select(pl.col("ts").alias(f"k{tau}"), pl.col("mid").alias(f"mid_{tau}"))
        t = (t.with_columns((pl.col("ts") + pl.duration(milliseconds=tau)).alias(f"k{tau}"))
              .join_asof(fut, on=f"k{tau}", strategy="backward"))
    # passive buyer (maker bought) when the buyer is the maker
    side = pl.when(pl.col("is_buyer_maker")).then(1.0).otherwise(-1.0)
    passive_best = pl.when(pl.col("is_buyer_maker")).then(pl.col("bid_price")).otherwise(pl.col("ask_price"))
    out = t.drop_nulls().with_columns(
        half_spread_bps=(pl.col("ask_price") - pl.col("bid_price")) / 2 / pl.col("mid") * 1e4,
        at_best=(pl.col("price") == passive_best),
        queue=pl.when(pl.col("is_buyer_maker")).then(pl.col("bid_qty")).otherwise(pl.col("ask_qty")),
        **{f"mo_{tau}": side * (pl.col(f"mid_{tau}") - pl.col("price")) / pl.col("mid") * 1e4
           for tau in TAUS_MS},
    )
    return out.select("ts", "qty", "half_spread_bps", "at_best", "queue",
                      *[f"mo_{tau}" for tau in TAUS_MS]).with_columns(day=pl.lit(day))


def main() -> None:
    rows = []
    for s in SYMBOLS:
        d = pl.concat([one_day(s, day) for day in DAYS])
        best = d.filter("at_best")
        r = {"symbol": s, "prints": d.height, "at_best_share": float(d["at_best"].mean()),
             "half_spread_bps": float(best["half_spread_bps"].mean()),
             "queue_over_trade": float((best["queue"] / best["qty"]).median())}
        for tau in TAUS_MS:
            per_day = best.group_by("day").agg(pl.col(f"mo_{tau}").mean()).sort("day")[f"mo_{tau}"].to_numpy()
            r[f"realized_{tau}"] = float(best[f"mo_{tau}"].mean())
            r[f"day_sd_{tau}"] = float(np.std(per_day, ddof=1))
        rows.append(r)
    df = pl.DataFrame(rows)
    with pl.Config(tbl_cols=-1, tbl_width_chars=250, float_precision=3):
        print(df)
    df.write_json(sys.argv[1] if len(sys.argv) > 1 else "m0_markouts.json")


if __name__ == "__main__":
    main()
