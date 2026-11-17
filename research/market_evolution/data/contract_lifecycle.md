# Contract lifecycle table (`contract_lifecycle.csv`)

One row per **life** of every USDT-M perpetual (symbol ends in `USDT`, no underscore) that
has a daily aggTrades file in the data.binance.vision `futures/um` archive. Built by
`research/market_evolution/build_lifecycle.py` on 2026-11-17 from the S3 listing; the
archive's latest day is **2026-11-16**. 924 symbols, 935 rows (11 symbols have two lives).

## Columns

| column | meaning |
|---|---|
| symbol | ticker, e.g. `RNDRUSDT` |
| life | 1 for the first life of the ticker, 2 for a later one (see symbol reuse) |
| n_lives | number of lives of the ticker |
| first_trade_day, last_trade_day | first and last day of the life with a daily aggTrades file |
| n_trading_days | days with a file in the life |
| calendar_days, missing_days | last minus first plus 1, and the days without a file inside the life (at most 26) |
| alive_at_end | 1 if last_trade_day is within 3 days of 2026-11-16 |
| status | alive, delisted, renamed, merged, index, reused-symbol |
| successor | new ticker for renamed and merged; the same ticker for reused-symbol |
| gap_days | successor's first trade day minus this life's last trade day (negative: the successor was already trading) |
| rename_candidates | contracts that pass the price rule below; for review, not asserted |
| last_day_zip_bytes | zip size of the last-day aggTrades file |
| last_day_rows | row count of the last-day file, for the sample that was downloaded |
| evidence | the reason for the status, plus notes (ignored artifact files, prices at a reuse) |

## Rules

- **Dates come from daily aggTrades only.** aggTrades stops on the last trading day; klines,
  metrics and funding keep publishing empty ghost files after death and are never used for
  dates. Check: 12 randomly drawn last-day files of dead contracts (zip under 3 MB) all
  have rows (3,012 to 59,840 aggTrades). The monthly aggTrades inventory never starts
  before the daily one.
- **Artifact days.** Every file under 1 KB is opened. Two are dropped: AI16ZUSDT and
  KDAUSDT each have a single row at price 0.0 on 2025-12-10, 34 days after their last real
  trading day (2025-11-06). Without this rule they would look like reused symbols.
- **alive_at_end:** last trading day at or after 2026-11-13 (3 days before the archive
  end). No contract falls between 3 and 19 days; the most recent death is VELODROMEUSDT on
  2026-10-28.
- **Status**, in this order:
  1. an earlier life of a ticker that trades again later is `reused-symbol`;
  2. Q14's classification of the 2023 cohort (`q14_survivorship.py`) for the ticker's
     last life: `index` (BLUEBIRD, FOOTBALL, DEFI), `renamed` (RNDR to RENDER, MATIC to
     POL, GAL to G, FTM to S, MKR to SKY, EOS to A, DAR to D, BNX to FORM, FXS to FRAX,
     KLAY to KAIA), `merged` (AGIX and OCEAN into FET);
  3. otherwise `alive` if alive_at_end, else `delisted`.
- **Symbol reuse:** a gap of more than 30 days between consecutive trading days (dates
  more than 30 days apart) starts a new life.
- **Rename candidates** (dead lives outside the merged and index lists): another contract
  whose first trading day is within 14 days of this one's last trading day (either side),
  whose first daily close agrees with this one's last daily close within 10 % after a
  ratio of 1, 1000 or 1,000,000, **and** where that ratio is the one the tickers imply
  (1 for two plain tickers, 1000 for `X` to `1000X`, 1e6 for a `1000000` or `1M` prefix).
  Closes are from the daily (else monthly) 1d kline file of that exact day. Without the
  ticker condition, 71 pairs match, most of them coincidences with 2026 stock-token
  listings near $1 to $100 against dead coins near $0.001 to $0.1.

## Counts

By status (rows): alive 758, delisted 151, reused-symbol 11, renamed 10, index 3,
merged 2.

Deaths by year of last_trade_day (rows with alive_at_end = 0):

| year | delisted | renamed | merged | index | reused-symbol (first life) | total |
|---|---|---|---|---|---|---|
| 2020 | 1 | | | | | 1 |
| 2021 | 3 | | | | | 3 |
| 2022 | 13 | | | | 4 | 17 |
| 2023 | 3 | | | | | 3 |
| 2024 | 20 | 5 | 2 | 2 | 5 | 34 |
| 2025 | 42 | 4 | | 1 | 2 | 49 |
| 2026 | 69 | 1 | | | | 70 |

## Symbol reuse (11 tickers, first life ended, ticker trades again)

Price at the end of life 1 against the start of life 2 tells a relisting of the same coin
from a different asset on the old ticker:

- Probably the same coin relisted (ratio near 1 to 3): ICP (2022-06-10 to 2022-09-27,
  ratio 1.06), TLM, SLP, CVC, CTK, CVX, MAVIA, AIA (40-day gap).
- Probably a different asset (ratio far from 1): MDTUSDT (0.063 in 2024, 93.3 from
  2026-10-21) and NUUSDT (0.53 in 2022, 12.29 from 2026-11-12) look like the 2026
  stock-token listings reusing old crypto tickers; LITUSDT (0.59 in 2025-01, 3.63 from
  2025-12-23) is a new token on the old ticker.
- LUNA is **not** a futures reuse: LUNAUSDT ends 2022-05-12 with one life and LUNA 2.0
  trades as LUNA2USDT from 2022-09-10. The LUNA reuse is on spot only.

## Rename candidates found by the rule

Of the 10 known renames, the rule recovers 4 (RNDR, MATIC, FTM, EOS); it misses GAL (35-day
gap, no close on its last day), KLAY (43-day gap), MKR to SKY (1:24,000 conversion), BNX,
DAR and FXS (price moved more than 10 % across the gap). Beyond the known list, 16 dead
lives have at least one candidate. Most look coincidental (generic new listings at a
similar price) and need checking against announcements; the ones worth a look first are
TONUSDT to GRAMUSDT (2026-06-23, ratio 0.95), IPUSDT to DATAIPUSDT (2026-06-28, ratio
0.996) and TOMOUSDT to TWTUSDT (unlikely; Q14 found TOMO's real successor VIC 15 months
later). None of them changes `status`.
