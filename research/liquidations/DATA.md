# Free data for liquidation cascades

All sources here are free. Paid sources met during the review, and not used: Hyperliquid
requester-pays S3 buckets `s3://hyperliquid-archive` (us-east-1, asset contexts with OI history and L2
books) and `s3://hl-mainnet-node-data` (ap-northeast-1, node fills, about USD 27 egress); CoinGlass,
Hyblock and similar paid API tiers; SQD paid tiers.

Facts below were probed with curl on 2026-11-20 unless marked otherwise. Listing endpoint for any
prefix: `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=<prefix>&delimiter=/`.
Every zip has a `.CHECKSUM` (SHA256) file beside it. Files are mutable (see section 11), so store the
hash and download date of every file used. Licence: CC BY-NC-SA 4.0.

## 1. bookDepth (USDT-M) - depth within plus or minus 1 to 5% of mid

- **Path.** `data/futures/um/daily/bookDepth/<SYM>/<SYM>-bookDepth-YYYY-MM-DD.zip`
- **Example.** https://data.binance.vision/data/futures/um/daily/bookDepth/BTCUSDT/BTCUSDT-bookDepth-2025-10-10.zip
- **Schema.** `timestamp` (UTC string), `percentage` (band: -5..-1, +1..+5; -0.2 and +0.2 added on or
  just before 2026-01-15; integer in 2025 files, float such as -5.0 in 2026 files), `depth` (cumulative
  base quantity from mid to the band edge), `notional` (cumulative quote). Band VWAP = notional / depth.
- **Frequency.** About every 30 s (median 2,880 snapshots per day; 2,879 on 2025-10-10). Gaps up to
  24,937 s (2023-02-22) occur on all symbols at once.
- **Coverage.** 2023-01-01 (most symbols; 1000PEPE from 2023-05-05) to 2026-11-18. 579,545 files for
  1,022 symbols (253.3 GB); USDT perps are 905 symbols and 534,084 files. 0.3 to 0.6 MB per
  symbol-day. Stream and discard; do not store the panel.
- **Missing or partial days (all symbols).** 2023-02-08/09, 2024-04-18, 2026-01-14, 2026-10-08
  (741 of 905 missing); partial 2023-01-09/15/16/21, 2023-02-07, 2023-03-17 (04:53 to 07:49 only),
  2024-06-12 (2 snapshots), 2026-10-07 (339 timestamps, to 02:49) and 2026-10-09 (2,389, from 04:05:31;
  issue #512). Backfills: 2023-01-01 to 07-11 written on 2023-07-11/12; 1,082 files rewritten on
  2026-04-16; 589 on 2024-06-20.
- **Known glitches (from our scan of 119,374 contract-days plus hourly scans of stress dates).**
  - *X1, whole-book freeze, all symbols:* 2025-04-16 10:30:49 (BTC 10:31:05) to 2025-05-19 11:12:02 UTC.
    One book repeats (BTC mid 83,821.61) while files keep normal row counts. Reported as issue #431
    ("deviates from mark prices"). No depth exists for the April 2025 tariff aftermath.
  - *X2, stale-level crossed books, October 2025:* a stale bid at 121,363.3 stays in the snapshot book
    after price falls through it. BTCUSDT shows 17.652 BTC in the -1% band from 15:30:42 UTC on
    2025-10-10, mixed with real snapshots (about 85% phantom to 19:15). The exact 17.654 appears first
    at 19:12:30 (-2%), then 19:15:32 (-1%), 21:08:33 (-3%), 21:25:01 (-5%, 15 snapshots). ETH from
    15:30:06 (130.97 ETH at 4,331.49), SOL 15:31:03 (322.62 at 220.71), DOGE 15:32:02. Market-wide from
    about 2025-10-09 09:00 UTC (15 contracts), about 20% by 10-09 16:00, 36 to 44% during 10-10 15:00 to
    23:00, 98% in the 21:00 crash hour, about 43% of snapshots invalid each day 10-11 to 10-14, ending
    for all symbols at 2025-10-15 13:12:02. Because the mid is pulled to the ghost price, every band on
    both sides is shifted, not just the bid. A screen for exact equal values misses 15:30 to 19:12;
    screen on implied price and crossing.
  - *Second wave:* 2025-10-29 and 10-30 (61% and 90% of the 31 most active contracts crossed).
    ETHUSDT phantom bid 105.435 ETH at 3,977.64 from 2025-10-29 18:36:33 to 2025-12-01 13:14:05.
  - *Single-symbol:* ETCUSDT bid frozen at 3.72 ETC from 2025-10-08 10:15:33 to 2025-12-28 15:51:32;
    XRPUSDT 2025-07-31 13:35:04 to 2025-08-05 06:47:32.
  - *X3, August 2025:* partial bid freezes 2025-08-19 to 08-22; whole-book freeze on all symbols
    2025-08-26 06:43:02 to 12:07:30; 2025-08-29 06:18:31 to 06:37:03.
  - *X4, ask-side, all USD-M:* inner ask bands (+0.2, +1, +2%) frozen and books crossed from 2026-09-03
    (ETH 14:31, BTC 14:25:32 crossed, 14:46:03 frozen) to 2026-09-11 05:54 UTC; 52 to 59% of the most
    active contracts. Reported as issue #496.
  - *Feb to Mar 2024:* isolated crossed snapshots (1 to 3% of snapshots, runs of at most 2) on almost
    all symbols, 2024-02-16 to 02-27 and 03-02/03. Drop as single snapshots.
  - *Short all-symbol whole-book repeats:* 2023-09-12 08:34 to 08:53, 2024-10-28 16:21 to 16:35,
    2025-02-10, 2025-07-23 07:36 to 08:10, 2026-03-20 01:44 to 04:26, 2026-04-22 06:34 to 09:25.
  - *Legitimate repeats:* TradFi, equity, commodity and pre-market perps have static books outside
    venue hours (5.6% to 19.4% of Sunday contracts in mid to late 2026).
  - *Structural zeros:* the +-0.2% band is zero for coarse-tick symbols (DENT, 1000SATS, 1000WHY, HOT,
    DOGS); use the +-1% band for the crossed test.
  - Never seen: monotonicity violations (0 of 119,374 contract-days). On clean days a band stays
    unchanged for at most 8 snapshots (one case of 11 in 49,410), so a 20-snapshot freeze rule
    separates artifacts. On flag-free days the implied mid is always inside the daily kline range.
- **Onsets are not random.** October 2025 bid-frozen onsets (n = 68) followed a median prior 1-hour
  return of -2.57% (99% negative); ask-frozen (n = 55) +0.84% (95% positive). September 2026 ask onsets
  were 25 of 25 positive. The mask is therefore missing-not-at-random.
- **Other stress dates are clean:** 2024-08-05, 2025-02-03 and 2025-04-07 (plus or minus 1 day) have
  100% usable windows.
- **Mask.** `bookdepth_mask_v1_DRAFT.txt` in this folder, sha256
  `61d003375266604e95b2d9ff66149b9f39d0eb03862c8a779f566c6abc4513f7`. Binance has published no
  announcement about bookDepth defects (search of 5,213 CMS article titles).
- **What it cannot do.** No top-of-book after March 2024; 30 s snapshots cannot resolve sub-minute
  resilience; bands move with the mid, so "depth within 1%" is not a fixed set of orders.

## 2. metrics (USDT-M and COIN-M) - OI and positioning, 5 minutes

- **Path.** `data/futures/um/daily/metrics/<SYM>/<SYM>-metrics-YYYY-MM-DD.zip` (also `cm/daily/metrics`).
- **Example.** https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-2025-10-10.zip
- **Schema.** `create_time, symbol, sum_open_interest` (base units), `sum_open_interest_value` (USD),
  `count_toptrader_long_short_ratio` (top-trader account ratio), `sum_toptrader_long_short_ratio`
  (top-trader position ratio), `count_long_short_ratio` (all-account ratio),
  `sum_taker_long_short_vol_ratio` (taker buy/sell volume).
- **Frequency.** 288 rows per day; about 11 KB per day.
- **Coverage.** BTCUSDT from 2020-09-01; ETH, SOL, DOGE from 2021-12-01; 1,061 symbols. COIN-M
  BTCUSD_PERP from 2021-07-08, but missing 2023-09-25, 2023-11-19 and 2024-03-04 to about 2024-06-08
  (97 days, includes the March 2024 sell-off).
- **Values on 2025-10-10 (current archive).** BTCUSDT OI value 10.810B USD at 20:00, 10.472B at 21:00,
  8.519B at 21:40; largest 5-minute drop -0.736B at the 21:15 label. Account ratio 1.048 (16:00),
  1.274 (19:00), 1.256 (21:00). OI 96,714.5 BTC at 00:00, 92,342 at 20:40, 72,613.8 at 23:55. An
  earlier scout's figures (10.51B to 8.73B; ratio down to 1.02) do not match the current file.
- **Known glitches.** Label convention changed silently from end-of-period to start-of-period on
  2026-06-25 (issue #491); pre-register which convention each lead-lag test assumes. Spike-and-reverse
  rows: BTCUSDT 2025-10-10 +736.4M USD at 21:45 then -717.1M at 21:50 (also 83,166 BTC between 76,547
  and 76,818); 28 such points in 10 symbols over 9 to 12 Oct 2025. Missing rows: 2023-09-12 BTCUSDT
  285 of 288 (issue #503); 2023-09-18 missing (issue #276); 2025-04-15 has 5 empty rows. The
  2025-10-10 BTCUSDT CSV has an internal mtime of 2026-08-07, so it was rewritten. Ghost rows after
  delisting (OI 0, constant values) look like leverage collapses; check against aggTrades activity.
  The repo's `data/raw_panel/contracts/*/metrics.parquet` keeps only month-end rows (BTCUSDT: 74 rows),
  so intraday work needs fresh downloads.
- **As a liquidation proxy.** Weak at 5 minutes (see section 6). REST `www.binance.com/futures/data/
  openInterestHist` serves only about the last 30 days.

## 3. aggTrades and trades (USDT-M and COIN-M)

- **Paths.** `data/futures/um/daily/aggTrades/<SYM>/<SYM>-aggTrades-YYYY-MM-DD.zip`,
  `.../trades/<SYM>/<SYM>-trades-YYYY-MM-DD.zip` (also monthly, and `cm/`).
- **Example.** https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2025-10-10.zip
- **Schemas.** aggTrades: `agg_trade_id, price, quantity, first_trade_id, last_trade_id,
  transact_time, is_buyer_maker`. trades: `id, price, qty, quote_qty, time, is_buyer_maker`.
- **Sizes.** BTCUSDT 2025-10-10: aggTrades 52 MB, trades 68 MB.
- **Exclusions by design.** Binance docs (official SDK docstrings): "Only market trades will be
  aggregated and returned, which means the insurance fund trades and ADL trades won't be aggregated."
  So trade IDs missing from aggTrades (gaps between `last_trade_id` and the next `first_trade_id`)
  mark insurance-fund takeovers and ADL. 1m kline volume and count also exclude them.
- **Known glitches.** BTCUSDT trades for 2025-10-10 lack 782,091 of 9,006,113 IDs (30.5% missing at
  22:00 UTC, 80.0% at 23:00); aggTrades lacks only 20,371. Use aggTrades. Issue #525 reports missing
  aggTrades and klines for 2026-10-28; #529 duplicated trade IDs on 2025-08-29. The aggregation rule
  text changed from "same order, same price" to "fill in 100ms with the same price and the same taking
  side" (date unknown). Merge same-millisecond same-side prints before counting runs (repo Q0).
- **ID-gap proxy facts.** COIN-M: every hour with a gap has a snapshot liquidation; 0 of 314 no-
  liquidation days have any gap; 96.5% of gap events within 1 s of a snapshot (median 76 ms); but only
  12.5% of liquidation hours show a gap. USDT-M: rare bursty gaps before about 2024-11, then a
  background of single-ID gaps; LINKUSDT steps up on 2025-08-06 about 15:00 UTC (3 gap events on
  2025-08-05, 435 single-ID gaps over 23 hours on calm 2025-08-07); BTCUSDT about 400 per hour on calm
  2025-10-01. Cascade hour 2025-10-10 21:00 UTC: BTCUSDT 11,088, DOGEUSDT 14,046, LINKUSDT 7,453. COIN-M
  LINKUSD_PERP stays at 0 on calm days through 2026-03.

## 4. klines, markPriceKlines, indexPriceKlines, premiumIndexKlines

- **Paths.** `data/futures/um/daily/{klines,markPriceKlines,indexPriceKlines,premiumIndexKlines}/<SYM>/1m/<SYM>-1m-YYYY-MM-DD.zip`
  (intervals 1m to 1mo; no 1s). Monthly versions exist.
- **Example.** https://data.binance.vision/data/futures/um/daily/markPriceKlines/BTCUSDT/1m/BTCUSDT-1m-2025-10-10.zip
- **Schema.** Standard klines (`open_time, open, high, low, close, volume, close_time, quote_volume,
  count, taker_buy_volume, taker_buy_quote_volume, ignore`). For mark, index and premium, volume is 0
  and `count` is the number of underlying updates (60 per minute mark and index, 12 premium).
- **Coverage.** BTC mark 1m from 2019-12-23 with gaps in 2019 to 2022.
- **Facts on 2025-10-10.** BTC lows at 21:20 UTC: last 101,516, mark 101,878 (101,877.69), index
  102,583, about -12.9% from 20:00. Mark did not cushion alts: ATOM -62.6/-61.5/-60.0% (last/mark/index),
  SUI -82.5/-82.1/-82.1%, IOTX -94.8/-94.8/-96.2%. Median |mark - last| in the crash window 1.9 bp
  (BTC) to 10.3 bp (IOTX).
- **Use.** Drawdowns on mark (what triggers liquidations). Jump detection on last-price klines or
  aggTrades, because mark is a smoothed composite that damps jumps.

## 5. fundingRate

- **Path.** `data/futures/um/monthly/fundingRate/<SYM>/<SYM>-fundingRate-YYYY-MM.zip` (monthly only).
- **Schema.** `calc_time, funding_interval_hours, last_funding_rate`.
- **Notes.** Interval differs by symbol (BTC 8 h, ENA 4 h). Since 2025-05-02 08:00 a contract
  switches to 1 h after a settlement at the cap or floor, so the switch is endogenous to prior
  one-sidedness. Example: ATOMUSDT -0.2183% at 2025-10-11 00:00. Funding at 8 h is too coarse for
  intraday warnings; use premiumIndexKlines.

## 6. liquidationSnapshot (COIN-M only) - the only free Binance liquidation ground truth

- **Path.** `data/futures/cm/daily/liquidationSnapshot/<SYM>/<SYM>-liquidationSnapshot-YYYY-MM-DD.zip`
- **Example.** https://data.binance.vision/data/futures/cm/daily/liquidationSnapshot/BTCUSD_PERP/BTCUSD_PERP-liquidationSnapshot-2024-08-05.zip
- **USDT-M.** No folder under `um/daily` or `um/monthly`. A USDT-M folder existed and was withdrawn;
  a maintainer wrote "this data is no longer provided" on 2024-10-15 (issue #361; also #420).
- **Schema.** `time` (ms), `side` (SELL = long liquidated, 74.3% of events), `order_type` (always LIMIT),
  `time_in_force` (always IOC), `original_quantity` (contracts: 100 USD for BTCUSD, 10 USD for others),
  `price` (order limit, near bankruptcy price), `average_price` (fill), `order_status` (always FILLED),
  `last_fill_quantity`, `accumulated_fill_quantity` (always equals original).
- **Coverage.** 118 symbol folders (45 perps, 73 quarterlies), 17,182 daily files, 11.35 MB of zips,
  2023-06-25 to 2024-10-14 for every symbol. BTCUSD_PERP 472 of 478 days, ETHUSD_PERP 474. A file
  exists only on days with liquidations.
- **Known glitches.** Every row appears exactly twice (543,618 rows, 271,793 unique); in
  2023-09-21 13:42:45 to 17:54:53 UTC every row appears four times. Deduplicate on all columns plus
  symbol. Throttled: at most one event per symbol per second (minimum gap 811 ms, 1% quantile 1,003
  ms), matching the stream rule "only the latest one liquidation order within 1000ms will be pushed";
  counts are lower bounds, with an estimated 28 to 32% of counts lost in the 20 busiest minutes.
  Outage days are not zero days: 2023-09-25 (5 rows across all symbols, all at 00:22) and BTCUSD_PERP
  2024-06-11 to 06-12 (no rows for 52 hours while BTCUSDT traded USD 21 to 23B per day). Rule: a
  symbol-day with an empty snapshot while same-coin USDT-M volume is above its median is an outage.
  49 files were re-uploaded on 2026-04-16.
- **Totals (deduplicated).** BTCUSD_PERP USD 949M (65.3% longs), ETHUSD_PERP 405M, SOLUSD_PERP 97M.
  2024-08-05 BTCUSD_PERP: 1,904 rows, 952 unique, about USD 37.3M. Largest hours: 2024-04-12 18h (BTC
  USD 17.3M), 2024-04-02 03h, 2024-03-11 13h, 2024-08-05 01h and 06h, 2023-08-17 21h.
- **Exploratory proxy validation (not pre-registered).** 5-minute bins, top 1% of liquidation bins:
  OI drop AUC 0.652 (BTC), 0.600 (ETH); absolute return 0.868/0.888; volume 0.948/0.960; R2 0.239 with
  volume and return, 0.240 adding OI drop; time split AUC 0.927 versus 0.928. In 34% (BTC) and 47% (ETH)
  of the top 0.1% bins OI rose. Hourly USDT-M quote volume for the same coin: AUC 0.975 (BTC), 0.961
  (ETH), 0.932 (SOL). The OI drop only helps summed over 1 h or more.
- **Fill-limit gap.** Median gap between fill and limit price 37 bp (BTC), 239 bp (SOL); this surplus
  goes to the insurance fund. It mainly reflects margin tier and leverage, so control for brackets.

## 7. bookTicker (USDT-M) - top of book, short window

- **Path.** `data/futures/um/daily/bookTicker/<SYM>/...`; 2023-05-16 to 2024-03-30 daily (monthly
  2023-05 to 2024-04), 315 symbols. BTCUSDT median 146 MB per day, max 474 MB; monthly up to 8.27 GB.
- **Schema.** `update_id, best_bid_price, best_bid_qty, best_ask_price, best_ask_qty, transaction_time,
  event_time`. Only window for spread and Cont-Kukanov-Stoikov OFI; no 2024-08 or later events.

## 8. Binance REST through www.binance.com (current state only)

`fapi.binance.com` does not resolve here; the same paths work through `www.binance.com/fapi/...`.

| Endpoint | Returns | History |
|---|---|---|
| `/fapi/v1/insuranceBalance` | 124 fund groups for 814 symbols; USDT 1.458B, USDC 404.0M total on 2026-11-20; BTCUSDT pool (shared with ETH, BNB) USDT 668.9M | none; collect forward |
| `/fapi/v1/symbolAdlRisk` | LOW/MIDDLE/HIGH/EXTREMELY_HIGH for 809 symbols (524/213/71/1) | none |
| `/fapi/v1/constituents`, `/fapi/v1/indexInfo`, `/fapi/v1/assetIndex` | Index weights (BTCUSDT: binance 0.4348, okex 0.1304, coinbase 0.1304, ...) | none |
| `/bapi/futures/v1/friendly/future/common/brackets` | Current leverage and maintenance brackets, 1,089 symbols (BTCUSDT bracket 1: 0 to 300k at MMR 0.004, 150x) | none; 782 of 927 USDT symbols changed after 2025-10-10, so not point-in-time |
| `/futures/data/openInterestHist`, `takerlongshortRatio` | 5-min series | about 30 days |
| `/fapi/v1/forceOrders`, `/fapi/v2/adlQuantile`, `/fapi/v1/leverageBracket` | caller's own data | API key required |
| `/fapi/v1/allForceOrders` | retired (404) | none |
| websocket `!forceOrder@arr` | live liquidations, 1 per symbol per second | forward only |

## 9. Hyperliquid (free info API)

- **Endpoint.** POST `https://api.hyperliquid.xyz/info`.
- `userFillsByTime`: fills carry `liquidation{liquidatedUser, markPx, method}`; `method` is `market`
  (into the book) or `backstop` (against the liquidator vault). ADL fills have `dir:
  "Auto-Deleveraging"`. At most 2,000 per call; documented as only the 10,000 most recent fills, applied
  unevenly in practice.
- `userNonFundingLedgerUpdates`: `liquidation` deltas with `liquidatedNtlPos`, `accountValue`,
  `leverageType`; not limited by the fill cap.
- `vaultDetails`: HLP parent has 7 children; liquidators 0x2e3d94f0562703b25c83308a05046ddaf9a8dd14
  (main), 0xb0a55f13d22f66e6d495ac98113841b2326e9540 (2), 0x5e177e5e...cb70 (3), 0x2ed5c448...8308 (4).
- `fundingHistory`: hourly funding and premium, BTC from 2023-05-12 00:00 UTC.
- `metaAndAssetCtxs`: current OI, mark, oracle only. `candleSnapshot`: last 5,000 bars only (1m for
  2025-10-10 returns empty).
- `https://stats-data.hyperliquid.xyz/Mainnet/leaderboard`: about 48,208 wallets (2026-11-20 snapshot;
  survivorship-biased for 2025 events). Other stats-data paths tried returned 403.
- **2025-10-10 coverage.** Main liquidator history starts 2025-10-10 21:33:26.888 UTC (after the peak);
  113,321 fills to 10-11 14:25:57, mostly Close Long unwinds, 94 backstop liquidations. Liquidators 2
  to 4 start 2025-11-19 to 11-21. In a random 1,500-wallet sample, 65 wallets had 78 ledger
  liquidations (USD 39.4M), 72 of them between 21:00 and 21:30 UTC; first ADL fill seen at 21:16:04.8.
  Scaled up this is about USD 1.3B, far below press totals, so use timing, not levels. An ADL fill
  against HLP Liquidator 2 at 21:17:47 UTC shows ADL hit the backstop vault itself.

## 10. Repo data to reuse

- `/home/user/binance-microstructure/research/market_evolution/data/proxies_cross_section.parquet`:
  432 contract-months of slicing proxies (median_notional_usd, sign_repeat_rate, run shares, etc.).
- `/home/user/binance-microstructure/research/market_evolution/data/tick_events.csv`: 459 tick changes;
  increases on HEMI, SOON, BLESS, COAI on 2025-10-10 04:00 to 08:00 UTC and AIA, BNT, DOOD, LIGHT on
  2025-10-08 confound those contracts.
- `/home/user/binance-microstructure/results/q6_endogeneity.md`, `q6b_kernel_sensitivity.md`: Hawkes
  estimates and their traps.
- Repo politics data: Trump posts on 2025-10-10 at 14:57:52Z and 20:50:01Z.

## 11. Cross-cutting hygiene

1. Hash every downloaded file and record the download date; the archive is rewritten.
2. Use aggTrades, not trades, after checking ID completeness.
3. Apply the bookDepth mask and the metrics screen before computing anything.
4. Treat missing snapshot days as outages unless proven quiet.
5. Do not store the full bookDepth panel (about 240 GB for USDT perps); sample pre-registered windows.
