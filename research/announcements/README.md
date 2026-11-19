# D1: did prices or volume move before Binance announced a listing or delisting?

Status 2026-11-19: **data and plan only.** No pre-announcement price or volume statistic
has been computed or looked at. The script in this folder reads file listings and dates,
never a price.

## What exists

| item | where | state |
|---|---|---|
| Announcement title lists (catalogId 49, about 4,000 titles; catalogId 161 "Delisting", 446 titles) | downloaded in the 2026-11-17 verification pass | **not saved anywhere.** Searched the repo, `data/` and `/tmp` for `articleCode`, `catalogId` and `cms/article`: only the three notes under `research/market_evolution/notes/` mention them. The lists must be fetched again. |
| Individual notices with codes and dates | `research/market_evolution/notes/binance_events.md`, `notes/delisting_prediction.md` | about 50 tick, funding and program notices and 4 futures delisting notices (dates, mostly day precision). Copied as example rows into `MANUAL_TEMPLATE.csv`. |
| Contract lives (first and last trade day per USDT-M perpetual) | `research/market_evolution/data/contract_lifecycle.csv` | 935 lives, archive end 2026-11-16, day precision |
| Daily aggTrades day listing per contract | `data/universe/lifecycle_cache/daily_aggtrades/` (git-ignored) | used for availability checks |
| Monthly panel (month-end OI and others) | `data/panels/monthly_panel.parquet` | context for delistings only |
| Candidate events with data availability | `research/announcements/data/event_inventory.csv` | built by `d1_inventory.py events` (this phase) |

## Network check (2026-11-19)

- `www.binance.com` (announcement list endpoint `bapi/composite/v1/public/cms/article/list/query`):
  **refused** by the network proxy (HTTP 403 on CONNECT; proxy status log shows
  `connect_rejected` for www.binance.com:443). Also refused: `fapi.binance.com`,
  `api.binance.com`, `public.bybit.com`, `www.okx.com`, `api.gateio.ws`.
- `data.binance.vision` and its S3 listing: reachable.
- So **no announcement was collected in this phase** and `data/announcements.csv` does not
  exist yet. `d1_inventory.py collect` is ready for when the host is allowed (1 request per
  second, stops on the first refusal, raw JSON into `data/announcements/raw/`, git-ignored),
  and `ingest` turns the pages into `data/announcements.csv` (code, UTC release time to the
  second, type, market, symbols, title; no bodies).

## Candidate events from the archive (no announcement needed for this part)

From `d1_inventory.py events` (S3 listings only):

**Futures listings, first trade day 2023-01-01 to 2026-10-31: 766 lives** (new 746,
relisting of an old ticker 9, rename successor 11; index contracts excluded). By year
2023: 100, 2024: 131, 2025: 248, 2026: 287. Whether a pre-announcement price exists in the
Binance archive (Binance spot pair `X` or, for `1000X` style contracts, `X`):

| Binance spot status at the futures first trade day D | lives |
|---|---|
| spot trading on D-1 and on D-35 (enough for a 30-day baseline plus the 72h window) | 115 |
| spot trading on D-1 but not on D-35 | 25 |
| spot first day on or after D (futures came first, often pre-market style) | 186 |
| no Binance spot pair at all | 438 |
| spot existed but not trading on D-1 | 2 |

New listings with a usable Binance spot history: 2023: 59, 2024: 37, 2025: 13, **2026: 0**.
The usable set is mostly older coins added to futures years after spot (median spot lead
980 days). Since 2025 almost every new perpetual has no prior Binance spot price; a price
from another venue (Bybit, OKX, Gate) would be needed, and those hosts are refused now.

**Futures delistings, last trade day 2023-01-01 to 2026-11-16: 141 lives** (delisted 134,
first life of a reused ticker 7; renamed 10 and merged 2 are excluded as non-events). By
year 2023: 3, 2024: 25, 2025: 44, 2026: 69. Data: all 141 have daily futures aggTrades on
at least 47 of the 49 days before the last trade day, a contract age of at least 84 days,
and a 1m kline file 14 days before the last trade day (spot check of one day per contract).
Binance spot pair still trading on the last futures day: 79; spot pair existed but already
gone: 15; never a Binance spot pair: 47. BTCUSDT (futures and spot) covers every date.

## Matching (step 2)

`d1_inventory.py match --file <csv>` matches each futures listing or delisting announcement
to the contract life by symbol: listings to a life whose first trade day is within -3 to
+60 days of the announcement date, delistings to a life whose last trade day is within 0
to +60 days. It reports lead times, unmatched symbol mentions, and contract lives with no
announcement in the table's span. The launch or settlement minute should later come from
the first or last 1m kline with volume (the lifecycle has day precision only).

Run now on the four example rows in `MANUAL_TEMPLATE.csv` (from the notes, day precision):
6 contract delistings matched, lead from announcement day to last trade day 5 to 10 days
(median 8.5), 0 unmatched (output `data/matches_manual_template.csv`). This only tests the
code: the full matching, counts, lead-time distribution and unmatched list wait for the
announcement table. Expectations from the notes [S/I]: futures delisting notices come 5 to
10 days before settlement; futures listing notices usually come minutes to a day before
launch, which is why the listing test needs a spot price.

## Manual collection (needed while www.binance.com is refused)

Two routes, the first much better:

**A. Save the JSON list pages from your own browser** (exact UTC time to the millisecond,
no transcription). Open each URL below in a browser, save the page as
`data/announcements/raw/cms_list_<catalog>_<page>.json` (three-digit page, e.g.
`cms_list_161_001.json`), then run `.venv/bin/python research/announcements/d1_inventory.py ingest`.

- Delisting: `https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId=161&pageNo=1&pageSize=50`,
  pages 1 to 9 (446 titles back to 2022-02; stop when `articles` is empty).
- New Cryptocurrency Listing (futures launches are posted here): same URL with
  `catalogId=48`, pages 1 until the release dates pass 2023-01-01 (roughly 30 to 50 pages;
  the catalog id 48 is from memory, check that `catalogName` reads "New Cryptocurrency
  Listing").
- Optional: `catalogId=49` (Latest Binance News, for Monitoring Tag, leverage and margin-tier
  notices used as exclusion rules).

**B. Transcribe by hand into `MANUAL_TEMPLATE.csv`** if the JSON route fails.

- Pages: https://www.binance.com/en/support/announcement, categories "New Cryptocurrency
  Listing" (keep titles "Binance Futures Will Launch USDⓈ-M ... Perpetual Contract" and
  spot titles "Binance Will List ...") and "Delisting" (keep "Binance Futures Will Delist
  ...", "Binance Will Delist ..." and notices that settle perpetuals). Date range: release
  dates 2023-01-01 to 2026-10-31.
- `article_code`: the 32-character id at the end of the notice URL.
- Time: the list and the notice page show the publication time in your browser's time zone.
  Copy it into `time_as_shown` and the zone into `shown_timezone` (e.g. `Europe/Berlin`),
  and give `release_time_utc` as `YYYY-MM-DD HH:MM` in UTC (minute precision;
  `time_precision` = `minute`). If only a date is visible, give the date and `day`.
- `type`: listing, delisting or other. `market`: futures, spot or both (both = a spot
  delisting notice that also settles the perpetual). `symbols`: contract tickers separated by
  `;` (e.g. `1000PEPEUSDT;ZKCUSDT`). `settlement_or_launch_utc`: the launch or settlement
  time stated in the title or body. `title`: the title verbatim. `source`: `manual`.
- Priority if time is short: all futures delisting notices (about 72 titles contain
  "Futures Will Delist", plus the combined spot notices), then futures listings of the 140
  contracts with Binance spot history (`spot_status` starting `spot_before` in
  `data/event_inventory.csv`).

## Plan

1. Get the title lists (route A, or `collect` if the host is allowed), `ingest`, `match`,
   and fill in this README's counts.
2. Review `PREREGISTRATION_DRAFT.md`; fix the open choices; freeze it with a sha256 before
   any 1m kline near an event is downloaded.
3. Only then download the 1m klines (Binance spot for listings, futures for delistings,
   BTCUSDT for both) and run the frozen analysis.

## Files

- `d1_inventory.py`: probe, collect, ingest, events, match (ruff clean).
- `data/event_inventory.csv`: candidate events and availability (committed).
- `data/matches_manual_template.csv`: code test on the example rows.
- `MANUAL_TEMPLATE.csv`: columns for hand collection, with 4 example rows.
- `PREREGISTRATION_DRAFT.md`: draft design, not frozen.
- `data/announcements/raw/` (repository root, git-ignored): raw pages and `s3_cache.json`.
