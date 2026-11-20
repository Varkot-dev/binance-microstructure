# Data for memecoin research: what is free, where it is, and what costs money

Probed 2026-11-20 unless stated. "Reachable" means it answered from this sandbox. Everything in sections 1 to 4 is free.

## 1. Binance public archive (data.binance.vision)

Base: `https://data.binance.vision/`. Directory listings via S3: `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/daily/`.

### 1.1 USD-M futures datasets
Under `data/futures/um/{daily|monthly}/` the datasets are: `aggTrades`, `bookDepth`, `bookTicker`, `indexPriceKlines`, `klines`, `markPriceKlines`, `metrics` (daily only), `premiumIndexKlines`, `trades`, and monthly `fundingRate`. There is **no liquidation dataset** (`liquidationSnapshot` returns 404).

File pattern examples:
- `data/futures/um/daily/aggTrades/TRUMPUSDT/TRUMPUSDT-aggTrades-2025-01-19.zip`
- `data/futures/um/monthly/klines/1000PEPEUSDT/1m/1000PEPEUSDT-1m-2023-05.zip`
- `data/futures/um/monthly/fundingRate/1000PEPEUSDT/1000PEPEUSDT-fundingRate-2023-05.zip`
- `data/futures/um/daily/metrics/WIFUSDT/WIFUSDT-metrics-2024-03-05.zip`
- Each zip has a `.CHECKSUM` (sha256) sibling.

Columns: aggTrades and trades carry price, quantity, time and taker side (`is_buyer_maker`) but **no account ID**. The trades file has `id, price, qty, quote_qty, time, is_buyer_maker`; it lacks the `isRPITrade` field that the REST endpoint returns.

### 1.2 First monthly files for memecoin perps
DOGEUSDT 2020-07 (first trade 2020-07-10); 1000SHIBUSDT 2021-05 (2021-05-10); 1000PEPEUSDT and 1000FLOKIUSDT 2023-05 (2023-05-05 and 05-06); 1000BONKUSDT 2023-11 (2023-11-22); WIFUSDT 2024-01 (2024-01-18); BOMEUSDT 2024-03; POPCATUSDT 2024-08; PNUTUSDT 2024-11; PENGUUSDT and FARTCOINUSDT 2024-12; TRUMPUSDT 2025-01 (2025-01-18 13:00 UTC); MELANIAUSDT 2025-01 (2025-01-20). All run to 2026-10. Spot archives: DOGEUSDT from 2019-07, PEPEUSDT from 2023-05, TRUMPUSDT from 2025-01.

### 1.3 The 5-minute metrics file
Columns: `create_time, symbol, sum_open_interest, sum_open_interest_value, count_toptrader_long_short_ratio, sum_toptrader_long_short_ratio, count_long_short_ratio, sum_taker_long_short_vol_ratio`. 288 rows a day.

Mapping verified against the live REST endpoints for 1000PEPEUSDT on 2026-11-18 (288 of 288 rows matched):
| Archive column | REST endpoint (`www.binance.com/futures/data/...`) | Type |
|---|---|---|
| sum_open_interest, sum_open_interest_value | openInterestHist | snapshot at create_time |
| count_toptrader_long_short_ratio | topLongShortAccountRatio | snapshot |
| sum_toptrader_long_short_ratio | topLongShortPositionRatio | snapshot |
| count_long_short_ratio | globalLongShortAccountRatio | snapshot |
| sum_taker_long_short_vol_ratio | takerlongshortRatio | **flow over [t-5m, t)** |

The REST endpoints keep only the last 30 days, so the archive is the only history. "Top trader" is described by Binance as the top 20% of users by margin balance (from memory; unverified because developers.binance.com is blocked). It appears to be ranked platform-wide: in December 2021 DOGE files, top-trader accounts were about 61% of all DOGE accounts. Account ratios count accounts, not size, and include top traders, so `count_long_short_ratio` is **not** a retail measure.

Earliest metrics file per symbol: 2021-12-01 at the earliest (DOGEUSDT, 1000SHIBUSDT), otherwise the listing day (1000PEPEUSDT 2023-05-05 16:35, WIFUSDT 2024-01-18 14:20, TRUMPUSDT 2025-01-18 13:00). No missing daily files.

Known defects (all symbols checked):
- Both top-trader ratios empty 2021-12-30 14:35 to 2022-12-14 15:30, except 2022-01-30, 2022-05-27 to 2022-06-24 and a few hours.
- Taker ratio empty 2021-12-30 14:35 to 2022-05-09 05:05; all-account ratio empty 2021-12-30 to 2022-01-19.
- 2024-02-16 ends at 13:30; missing 5-minute slots on 2023-09-12, 2024-10-28 and 2025-08-29.
- Rows out of order on about 220 days: always sort by create_time.
- Empty cells are the quoted string `""`.
- Precision: account ratios are full doubles until 2023-07-09, rounded to 8 decimals from 2023-07-10. Full precision allows account-count recovery (P1).
- Re-uploads: most files modified long after their data date (DOGE 2021-2023 uploaded 2023-06; mass re-uploads 2026-07, 2026-08 and 2026-11). Hash files at download.
- The repo's `monthly_panel` field `ls_toptrader_account_month_end` is null for 2022-01 to 2022-11 although `has_oi` is true.

### 1.4 Archive traps
- **Placeholder files after delisting.** MEMEFIUSDT last traded 2025-08-11 but has monthly 1d kline zips through 2026-10 (548 bytes against 1,919 for a live month). 1000XUSDT 1-minute files continue at about 8 KB a day after 2025-11-14. Use `contract_lifecycle.csv` or row counts, never file existence.
- **Symbols.** 1000x and 1M multipliers (1000PEPEUSDT, 1MBABYDOGEUSDT, 1000000MOGUSDT); reused or renamed symbols (PENGUSDT from 2026-07-21 is not PENGUUSDT); 18 prefixed symbols in exchangeInfo.
- **Size.** TRUMPUSDT aggTrades for 2025-01-19 is 363,813,894 bytes and 28,255,187 rows. Stream; use aggTrades only inside event windows.
- **Exchange rules.** Spot PEPEUSDT tick 1e-8 at about 3.7e-6 (0.27% relative tick) against 1000PEPEUSDT tick 1e-7 at about 0.0037 (0.0027%); minNotional 1 USDT spot vs 5 USDT perp. Funding interval varies by symbol and time (8h, 4h, 1h) and is capped.

## 2. Binance live endpoints (www.binance.com)

`fapi.binance.com` is refused by the sandbox proxy; the same paths work under `https://www.binance.com/fapi/...`. The endpoints are undocumented for this route and could change: crawl once, slowly (1 request per second), and save a sha256 manifest.

- **Announcements:** `https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId={id}&pageNo={n}&pageSize=50`. Article body: `.../cms/article/detail/query?articleCode={code}`. Catalog totals on 2026-11-20: 48 New Cryptocurrency Listing 2,299 (oldest 2017-07-21 00:06:19 UTC), 49 Latest Binance News 4,516, 93 Latest Activities 3,251, 161 Delisting 447, 157 Maintenance 616, 51 API Updates 81, 128 Crypto Airdrop 53. Release times to the millisecond. This host was refused on 2026-11-19 (`research/announcements/README.md`) and worked on 2026-11-20.
- **Trades with RPI flag:** `https://www.binance.com/fapi/v1/trades?symbol=1000PEPEUSDT&limit=1000` returns `id, price, qty, quoteQty, time, isBuyerMaker, isRPITrade` (RPI live since 2025-11-20). RPI is enabled on 374 of 953 USD-M symbols. One 1,000-trade sample: 1000PEPEUSDT 8 RPI trades in one probe and 2 in another; BTC, DOGE, TRUMP, WIF 0. A busy symbol prints 1,000 trades in under a minute (BTC in 16 seconds), so poll often and check id continuity. Whether `historicalTrades` needs an API key is unverified.
- **exchangeInfo:** `https://www.binance.com/fapi/v1/exchangeInfo` for onboard dates, tick and lot sizes, `permissionSets` (contains "RPI").
- **Binance Square feed:** `https://www.binance.com/bapi/composite/v3/friendly/pgc/content/article/list?pageIndex=N&pageSize=20&type=1&scene=web-homepage`. Only about 5 pages (1 to 2 days) deep; forward collection only; terms on automated collection not checked.
- **Copy-trading leaders:** public list of 9,087 lead portfolios with 30-day PnL, ROI and AUM; per-portfolio history returned empty in a test. Old futures leaderboard endpoint returns 404.

## 3. Hyperliquid (free)

- **Info API:** `POST https://api.hyperliquid.xyz/info` with JSON body.
  - `{"type":"meta"}`: 235 perps, 56 flagged `isDelisted`. Memecoins include DOGE, kPEPE, kSHIB, kBONK, WIF, kFLOKI, BOME, POPCAT, MOODENG, PNUT, PENGU, FARTCOIN, SPX, TRUMP, MELANIA, PUMP and others.
  - `{"type":"recentTrades","coin":"kPEPE"}`: only 10 trades, but each has `users: [buyer, seller]`.
  - `{"type":"userFillsByTime","user":"0x...","startTime":0}`: 2,000 fills per call with `closedPnl, fee, dir, crossed, startPosition, tid, oid` and liquidation fields. Retention about the 10,000 most recent orders per wallet; market makers keep only hours.
  - `{"type":"userFunding",...}`, `{"type":"clearinghouseState","user":...}`, `{"type":"fundingHistory","coin":"TRUMP","startTime":...}` (TRUMP from 1737180000140 ms, 2025-01-18, 500 rows a page).
  - `{"type":"candleSnapshot","req":{"coin":"kPEPE","interval":"1d","startTime":0,"endTime":...}}`: daily full history (kPEPE from 2023-05-05, 1,296 bars); 1h about the last 5,000 bars (about 7 months); 1m about 3.5 days.
  - `{"type":"spotMeta"}`: 519 tokens, 354 pairs.
- **Websocket:** `wss://api.hyperliquid.xyz/ws`, subscription type `trades`, both addresses per trade. Forward recording only (about 150 MB a day across all perps per the repo's `research/hyperliquid/DATA.md`).
- **Leaderboard:** `https://stats-data.hyperliquid.xyz/Mainnet/leaderboard` (200, 39.5 MB, about 48,000 wallets; pnl, roi, vlm by day, week, month, allTime; not by coin; survivorship-biased). `/Mainnet/vaults` 200. `/Mainnet/fills`, `/Mainnet/trades`, `/Mainnet/leaderboard/history` 403.

## 4. Repo files to reuse (main repo, `/home/user/binance-microstructure`)

- `research/market_evolution/data/contract_lifecycle.csv`: 935 contract lives (758 alive, 151 delisted, 10 renamed, 11 reused-symbol, 3 index, 2 merged); 766 lives first trading 2023-01-01 to 2026-10-31. About 65 memecoin lives (count not verified).
- `research/announcements/` (D1 plan, `event_inventory.csv`).
- `research/hyperliquid/` (DATA.md, LITERATURE.md, skill-versus-luck pipeline) and the HIP-1 census `research/hyperliquid/memecoin/` on another branch.
- `research/politics/posts/truth_realDonaldTrump.csv` (38,075 rows, 2022-02 to 2026-11; 7 posts match $TRUMP or "Trump Meme", only 3 after TRUMPUSDT listed).

## 5. Free but blocked from this sandbox

Need the host allowed, or a run on the owner's machine:
- Wikimedia pageviews (`wikimedia.org`, `dumps.wikimedia.org`): free, open, daily from 2015-07-01.
- Google Trends (`trends.google.com`): no official free history API (official API is a gated alpha); pytrends is unofficial and archived 2025-04-17; values sampled and rescaled.
- GDELT (`api.gdeltproject.org`, `data.gdeltproject.org`): free news, not social.
- Reddit: Arctic Shift API `https://arctic-shift.photon-reddit.com/api/posts/search/aggregate?subreddit=...&aggregate=created_utc&frequency=month` and monthly `RC_YYYY-MM.zst` / `RS_YYYY-MM.zst` dumps (full archive about 3.8 TB). Watchful1's per-subreddit torrents were removed at Reddit's request around 2026-09. No licence; legal and ethical risk.
- Telegram: `t.me/s/<channel>` previews; Telethon needs a personal phone-number account and api_id/api_hash (ban risk).
- Solana public RPC (`api.mainnet-beta.solana.com`).
- GitHub, Zenodo, Hugging Face for public datasets: SystemsLab-Sapienza pump dataset (MIT), MemeTrans, SolRPDS, RED-COHORT, Mongardini and Mei Zenodo 15697524.
- Paper hosts: arxiv.org, doi.org, papers.ssrn.com, nber.org, developers.binance.com.
- Lottery data: `data.ny.gov` (Powerball d6yy-54nr, Mega Millions 5xaw-6ayf; appear to have no jackpot amounts) and Texas Lottery HTML tables (estimated jackpot per draw; CSV omits it).

## 6. What costs money

- **Hyperliquid full fill archive:** S3 bucket `hl-mainnet-node-data` is requester-pays, about 295 GB, about $27 of egress; coverage starts 2025-03-22, so it misses the TRUMP launch.
- **X (Twitter) API:** pay-per-use, about $0.005 per post read (repo politics notes).
- **Dune** (Hyperliquid tables enterprise or trial; free tier has credit limits), **Allium**, **Hydromancer** (about $300 a month), **GoldRush**, **Nansen**, **Birdeye**, **Bitquery** paid tiers.
- **BigQuery:** about 1 TiB a month of free query processing; full Solana or GDELT scans exceed it and cost money. No credentials in this sandbox.
- **LunarCrush, Santiment, Kaito, CryptoCompare social history:** paid.
- **CoinGecko:** free Demo tier is rate-limited with limited history.
