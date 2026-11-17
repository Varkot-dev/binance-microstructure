# What data.binance.vision offers for USDT-M futures (survey of 2026-11-17)

Tags: [V] verified this session by S3 listing or by opening a downloaded file;
[S] from Binance documentation or common knowledge, not checked here; [I] my inference.

Method: S3 listing of `data/` on `s3-ap-northeast-1.amazonaws.com/data.binance.vision`
(paginated, each `<Contents>` parsed separately), one sample file per type unzipped in
the session scratchpad (zips deleted afterwards, about 30 MB downloaded in total).
Sample contracts: BTCUSDT (large, alive), ALPHAUSDT (small, delisted 2025-09),
HNTUSDT (small, delisted 2023-03), FTTUSDT (delisted 2022-11), plus a few others.
Inventory used for counts: `data/universe/aggtrades_monthly_inventory.json` (923 symbols
ending in USDT, 21,232 contract-months).

## Verification pass (2026-11-17, second session)

Checked: the spot timestamp switch date, against the binance-public-data README (raw GitHub,
reachable) [V, upgraded from S]. Not checked: the REST API statements below (fapi.binance.com
and developers.binance.com were refused by the proxy for the whole pass), so they stay [S].
Nothing else changed in this note.

## Summary

1. **Order-book depth exists for 2023 to today.** `futures/um/daily/bookDepth` runs from
   2023-01-01 to 2026-11-16 (yesterday) for BTCUSDT [V], with a snapshot every ~30 s of
   cumulative depth (base qty and USD notional) within +-1, 2, 3, 4, 5 % of the mid
   price, plus +-0.2 % from **2026-01-15** onward [V]. It covers 905 of the 923 USDT
   perps: every contract alive on or after 2023-01-01, delisted ones included [V]; the
   18 missing all stopped trading before 2023 [V]. This is the only depth or top-of-book
   source for 2024 to 2026.
2. **bookTicker ends on 2024-04-01 at about 06:46 UTC**, not in 2023 [V]. It starts
   2023-05-16 11:50 UTC [V]. Daily files: 2023-05-16 to 2024-03-30 with no gaps
   (BTCUSDT) [V]; the monthly 2024-04 file holds only the first ~7 hours of 2024-04-01
   [V]. 270 USDT perps have it [V]. So top of book covers 2023-05-16 to 2024-04-01 only.
3. **`metrics` (daily, 5-minute rows)** gives open interest, three long/short ratios and
   the taker buy/sell volume ratio, from 2021-12-01 for almost all contracts (29 of a
   random 30 old contracts start exactly then; BTCUSDT from 2020-09-01) [V]. 921 of 923
   USDT perps are covered [V]. No OI history before 2021-12 except BTCUSDT [V].
4. **Monthly `klines/1mo` stop at 2023-12** for every contract checked [V]. Use
   `monthly/klines/{SYM}/1d/` (to 2026-10) and aggregate; each 1d file already has
   volume, quote volume, number of trades and taker-buy volume per day [V].
5. **Ghost rows after delisting.** klines, markPriceKlines, indexPriceKlines,
   premiumIndexKlines, fundingRate and metrics keep producing files after a contract
   stops trading: FTTUSDT 1d klines for 2024-01 are flat at 1.59 with volume 0 and
   count 0 [V]; FTTUSDT metrics on 2024-07-15 have open interest 0 and empty ratios [V];
   HNTUSDT funding in 2024-01 is a constant 0.0001 [V]. aggTrades, trades and bookDepth
   stop on the last trading day [V]. **Do not take "last file in klines/funding/metrics"
   as the delisting date**; use aggTrades (as Q14 did) or the last day with count > 0.
6. No `liquidationSnapshot` for USDT-M: it exists only under `futures/cm/daily`
   (coin-margined, 2023-06-25 to 2024-10-14 for BTCUSD_PERP) [V]. `BVOLIndex` and
   `EOHSummary` exist only under `option/daily` (BTC/ETH vol index 2023-06-20 to today;
   EOHSummary 2023-05-18 to 2023-10-23 for a handful of underlyings) [V]. Neither helps
   per-contract work.
7. The Binance REST API (fapi.binance.com, including /futures/data/) is **blocked from
   this machine** (proxy CONNECT 403) [V], so nothing below about it was checked.

## What exists

Types under `futures/um/monthly/` [V]: aggTrades, bookTicker, fundingRate,
indexPriceKlines, klines, markPriceKlines, premiumIndexKlines, trades.
Types under `futures/um/daily/` [V]: aggTrades, bookDepth, bookTicker, indexPriceKlines,
klines, markPriceKlines, metrics, premiumIndexKlines, trades.
(fundingRate is monthly only; bookDepth and metrics are daily only.) Kline types use an
interval subfolder: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1mo [V].
Path pattern: `data/futures/um/{monthly|daily}/{type}/{SYMBOL}/[{interval}/]{SYMBOL}-{type or interval}-{YYYY-MM[-DD]}.zip`
plus a `.CHECKSUM` file next to each zip [V]. Timestamps are milliseconds in all USDT-M
files checked, including 2026 [V]; bookDepth and metrics use text `YYYY-MM-DD HH:MM:SS`
[V]. Spot klines are in **microseconds** in 2026 files [V] (spot switched on 2025-01-01 [V:
the binance-public-data README says "The timestamp for SPOT Data from January 1st 2025
onwards will be in microseconds",
https://raw.githubusercontent.com/binance/binance-public-data/master/README.md]).

## Table

Sizes are zip sizes from the listing. "Contract-month" for daily-only types is about 30
daily files.

| data type | path | columns | coverage (first/last) | delisted contracts included? | size per contract-month | useful for |
|---|---|---|---|---|---|---|
| aggTrades | monthly/aggTrades, daily/aggTrades | agg_trade_id, price, quantity, first_trade_id, last_trade_id, transact_time, is_buyer_maker | BTCUSDT 2020-01 to 2026-10 monthly, daily 2019-12-31 to 2026-11-16; ALPHAUSDT 2020-11 to 2025-09 [V] | yes, ends on last trading day [V] | BTC ~500 MB, small coins 20 to 40 MB [V] | already used; trade-level features; delisting date |
| trades | monthly/trades, daily/trades | id, price, qty, quote_qty, time, is_buyer_maker | BTCUSDT 2019-09 to 2026-10 monthly, daily 2019-09-08 to 2026-11-16 [V] | yes [V] | BTC ~870 MB, small 25 to 55 MB [V] | individual fills (an aggTrade can contain several); fill-size distribution, order splitting |
| bookTicker | monthly/bookTicker, daily/bookTicker | update_id, best_bid_price, best_bid_qty, best_ask_price, best_ask_qty, transaction_time, event_time | 2023-05-16 11:50 to 2024-04-01 06:46 UTC [V] | only contracts alive in that window (270 USDT) [V] | BTC ~4.2 GB, small ~250 MB; ~1.2 M rows/day for ALPHAUSDT [V] | spread, top-of-book queue; only 2023-05 to 2024-03 |
| bookDepth | daily/bookDepth | timestamp, percentage, depth, notional | 2023-01-01 to 2026-11-16 (BTCUSDT; 3 gaps: 2023-02-08/09, 2024-04-18, 2026-10-08) [V] | yes, every USDT perp alive on or after 2023-01-01; ends on last trading day [V] | ~470 KB/day BTC, ~335 KB/day HNT, so 10 to 14 MB [V] | depth at +-1..5 % (+-0.2 % from 2026-01-15), every ~30 s; the only depth for 2024 to 2026 |
| metrics | daily/metrics | create_time, symbol, sum_open_interest, sum_open_interest_value, count_toptrader_long_short_ratio, sum_toptrader_long_short_ratio, count_long_short_ratio, sum_taker_long_short_vol_ratio | BTCUSDT 2020-09-01 to 2026-11-16, no gaps; others from 2021-12-01 or listing day [V] | yes, but with ghost rows (OI 0, empty ratios) for months after delisting [V] | ~10 KB/day, ~300 KB [V] | open interest, top-trader and global long/short ratios, taker buy/sell volume ratio, 5-min. 2020-09 BTC file has every row twice [V] |
| klines | monthly/klines/{SYM}/{iv}, daily/klines/... | open_time, open, high, low, close, volume, close_time, quote_volume, count, taker_buy_volume, taker_buy_quote_volume, ignore | 1d and 1h: BTCUSDT 2020-01 to 2026-10 monthly, daily to 2026-11-16; **1mo only to 2023-12** [V] | yes, plus ghost flat zero-volume rows after delisting [V] | 1d: 1.3 to 2 KB; 1h: 30 to 40 KB; 1mo: 0.3 KB [V] | monthly volume, USD volume, number of trades, taker-buy share, returns, volatility |
| markPriceKlines | monthly/..., daily/... | same 12 columns; volume fields 0, count = seconds | BTCUSDT 2020-01 to 2026-10 [V] | yes, with ghost rows [V] | 1d ~1.5 KB, 1h ~15 to 20 KB [V] | mark price; mark vs last for stress |
| indexPriceKlines | monthly/..., daily/... | same; volume 0 | BTCUSDT 2020-01 to 2026-10; 918 of 923 USDT perps [V] | yes, ghost rows [V] | similar to mark [V] | spot index; perp-spot basis |
| premiumIndexKlines | monthly/..., daily/... | same; OHLC is the premium index (perp vs index) | BTCUSDT 2020-01 to 2026-10 [V] | yes [V] | 1h ~15 KB [V] | basis, funding driver |
| fundingRate | monthly/fundingRate only | calc_time, funding_interval_hours, last_funding_rate | BTCUSDT 2020-01 to 2026-10 [V] | yes, ghost constant 0.0001 after delisting [V] | ~0.8 KB [V] | funding level and interval (interval changes from 8 h to 4 h or 1 h flag stressed coins [S]) |
| liquidationSnapshot | futures/**cm**/daily only | not opened | BTCUSD_PERP 2023-06-25 to 2024-10-14 [V] | n/a for USDT-M | ~2 KB/day [V] | not available for USDT-M |
| BVOLIndex, EOHSummary | option/daily only | not opened | BVOL 2023-06-20 to 2026-11-16; EOH 2023-05-18 to 2023-10-23 [V] | n/a | 0.4 MB/day [V] | market-wide BTC/ETH implied vol as a control at most |
| spot aggTrades, trades, klines | spot/monthly, spot/daily | klines same 12 columns (microsecond times in 2026) [V] | BTCUSDT 1d 2017-08 to 2026-10; 3,767 spot symbols [V] | yes [S] | 1d ~1 to 2 KB [V] | spot volume and spot delisting of the same coin (a likely leading signal for Part B [I]) |

Oddities [V]: `monthly/aggTrades/BTCUSDT/` contains a stray `part-00000-...-c000.zip`
(417 MB, written 2023-12-14) that does not follow the naming pattern; there is an empty
`daily/klines/BTCUSDT//` prefix; listing contains non-USDT symbols (USDC, BUSD,
`...SETTLED`, `ETHBTC`, `BTCDOMUSDT`), filter by suffix.

## Which type gives what

| feature | source | per contract, all 6 years? |
|---|---|---|
| monthly volume, USD volume | klines 1d (sum) | yes [V] |
| number of trades | klines `count` | yes [V] |
| taker buy / sell volume | klines `taker_buy_volume`, `taker_buy_quote_volume`; metrics 5-min ratio | klines yes; metrics from 2021-12 [V] |
| open interest | metrics | from 2021-12 (BTC 2020-09) [V] |
| funding rate | fundingRate monthly; premiumIndexKlines | yes [V] |
| long/short ratios | metrics (top-trader accounts, top-trader positions, all accounts) | from 2021-12 [V] |
| basis to spot | indexPriceKlines vs klines | yes, 918 of 923 [V] |
| top of book | bookTicker | 2023-05-16 to 2024-04-01 only [V] |
| depth at several levels | bookDepth (+-1..5 %, +-0.2 % from 2026-01-15) | 2023-01-01 to now [V] |

## REST API (not reachable here)

- fapi.binance.com and data-api.binance.vision return proxy CONNECT 403 from this
  machine [V].
- `/fapi/v1/exchangeInfo` lists `onboardDate` and `deliveryDate` per symbol [S], but
  only for symbols still listed or in settlement; fully delisted contracts disappear, so
  it cannot give historical delisting dates [S]. The archive (last aggTrades day) remains
  the best source, with exchangeInfo `onboardDate` as a cross-check for live ones [I].
- `/futures/data/openInterestHist`, `topLongShortAccountRatio`,
  `topLongShortPositionRatio`, `globalLongShortAccountRatio`, `takerlongshortRatio` only
  return the latest 30 days [S]. The archive `metrics` files are the historical version
  of exactly these endpoints [I, column names match].
- `/fapi/v1/fundingRate` and `/fapi/v1/klines` have full history [S], but the archive
  already has the same data.

## Recommendations

### Part B: cheapest complete-coverage set

1. **klines 1d, monthly files** for all 923 USDT perps: ~21k files, about 36 MB [V
   sizes, I total]. Gives daily volume, USD volume, trades, taker-buy share, return,
   high-low range, all back to each listing. Drop rows with count 0 (ghost rows).
2. **fundingRate monthly**: ~21k files, about 17 MB [I]. Mean, max, share of negative
   funding, and changes in `funding_interval_hours`.
3. **indexPriceKlines and premiumIndexKlines 1d monthly**: same scale, ~30 MB each [I].
   Basis and premium volatility; index disappearing can mark loss of spot support [I].
4. **metrics, subsampled**: one daily file per contract-month (for example the last day
   of the month) is ~19.5k files, ~200 MB [I], and gives month-end OI, OI in USD,
   long/short ratios. A full download would be ~5.8 GB and ~585k requests [I]. Coverage
   starts 2021-12 (so features exist for ~92 % of contract-months [I]); treat earlier
   months as missing, not zero.
5. Spot 1d klines for the same base asset (cheap) to flag "spot pair delisted or volume
   collapsed" [I].
6. Labels: delisting month from aggTrades, never from klines/funding/metrics (ghost
   rows). The stray `part-00000` file must not be parsed as a month.

### Part A: drivers that need data beyond aggTrades

1. **bookDepth is the key new source for 2023 to 2026.** For each contract-month,
   depth within 1 % and 2 % of mid (USD notional, bid and ask), its imbalance and its
   intraday variation directly test "thicker or thinner books made the next trade more
   predictable". At ~30 s resolution it can be aligned with trades. Full coverage since
   2023 is ~180 to 250 GB [I], so sample: one day per week per contract is ~30 GB, one
   day per month ~7 GB, and Q10's 10 contracts in full are only ~5 GB [I].
2. Caveats for bookDepth: the 1 % band is wide for BTC/ETH (depth inside 0.2 % only
   from 2026-01-15), so for large coins it measures deep liquidity, not the touch [I];
   the level set change on 2026-01-15 must be handled; the 2023-01-01 file starts at
   00:06 (slightly fewer snapshots) [V].
3. **bookTicker overlaps bookDepth from 2023-05-16 to 2024-04-01.** Use that window to
   calibrate how well bookDepth's 1 % and 0.2 % levels proxy spread and touch depth,
   then use bookDepth alone for 2024-04 onward [I].
4. metrics (OI, taker ratio, long/short) and fundingRate are cheap extra controls for
   the Part A regression: leverage and crowding may also have risen [I].
5. `trades` (individual fills) versus `aggTrades` gives fills per aggregated trade, a
   direct measure of how often one taker order sweeps several makers; it is already
   in the archive for all years [V], but at ~1.7x aggTrades size.
6. A tick-size history is not on the archive; it can be reconstructed from price
   increments in aggTrades or klines [I].
