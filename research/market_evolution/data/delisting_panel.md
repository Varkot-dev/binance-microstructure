# Delisting panel (`delisting_panel.parquet`)

Built by `research/market_evolution/b0_baselines.py build` from `contract_lifecycle.csv`,
`monthly_panel.parquet` and the per-contract daily klines under `data/raw_panel/`.
Person-period layout: one row per contract life per month t, a prediction made at the end
of month t. Horizon H = 3. Last complete month: 2026-10 (archive ends 2026-11-16).
Build time 2.5 s.

## Size

- Rows: 18,329; lives: 686; months: 2020-01 to
  2026-07.
- Positive rows (y3 = 1): 465; base rate 0.0254.
- Event lives (included): 162 (delisted 151, reused-symbol 11); 161 of them have at
  least one positive row (without one: BTCSTUSDT#1).
- Included lives by status: alive 523, delisted 151, merged 2, renamed 10, reused-symbol 11.
- Lock-box rows (t >= 2026-01): 3,730 rows, months 2026-01 to
  2026-07. Reserved: not scored in b0.
- Sensitivity panel (drop t = L - 1 of event lives): 18,176 rows,
  312 positive rows.
- Rows dropped before writing: censored_label_unknown 24, final_trading_month 174, label_window_past_data_end 1,573;
  life months with no panel row at all: 3.

## By year of t

| year | rows | lives | positive rows | event lives with a positive row | base rate |
|---|---|---|---|---|---|
| 2020 | 502 | 80 | 3 | 1 | 0.0060 |
| 2021 | 1380 | 137 | 11 | 5 | 0.0080 |
| 2022 | 1689 | 159 | 44 | 17 | 0.0261 |
| 2023 | 2294 | 243 | 9 | 4 | 0.0039 |
| 2024 | 3339 | 371 | 89 | 32 | 0.0267 |
| 2025 | 5395 | 580 | 164 | 65 | 0.0304 |
| 2026 | 3730 | 574 | 145 | 61 | 0.0389 |

Event lives by year of the last trading day: 2020 delisted 1; 2021 delisted 3; 2022 delisted 13; 2022 reused-symbol 4; 2023 delisted 3; 2024 delisted 20; 2024 reused-symbol 5; 2025 delisted 42; 2025 reused-symbol 2; 2026 delisted 69.

## Rules

- **Lives.** From `contract_lifecycle.csv`: a gap of more than 30 days between trading days
  starts a new life, so the 11 reused tickers (ICP, TLM, SLP, CVC, CTK, CVX, MAVIA, AIA,
  MDT, NU, LIT) give two lives each. Age, running peaks, drawdowns and lags restart in each
  life. The monthly panel's `resumed_after_ghost` rows are the second-life starts, plus
  pre-listing funding or metrics files (BNT, BZ, CL, NATGAS, FOOTBALL), which fall outside
  the life and are dropped.
- **Dates from aggTrades.** The last trading month L is the month of the lifecycle
  `last_trade_day` (daily aggTrades), never the last kline, funding or metrics file (ghost
  files continue after death).
- **Event.** Status `delisted`, or `reused-symbol` (a first life that stopped trading for
  more than 30 days before the ticker came back: a delisting followed by a relisting, as for
  ICP in 2022). `renamed` (10) and `merged` (2) lives are censored at L: not events, not
  negatives near the end. `alive` lives are censored at 2026-10.
- **Label.** y3 = 1 if L is in t+1..t+3. Event lives: every row t < L has a known label.
  Censored lives (C = min(L, 2026-10)): y3 = 0 only when t + 3 <= C; rows with
  t + 3 > C are dropped (censored), never set to 0.
- **Common label end.** Rows with t + 3 > 2026-10 are dropped for every life, events
  included, so the last labelled month is 2026-07. Keeping the event rows
  there (their labels are known) would leave months 2026-08 to
  2026-09 with dying contracts only.
- **No final month.** The row t = L (partial month, often post-announcement trading) is never
  a feature row. Rows after 2026-10 do not exist.
- **Features** use months up to and including t only: month-t panel values, lags by
  calendar month inside the life (join on t - k, never a row shift), running maxima up to
  t, and within-month ranks among contracts live at the end of t (included lives with
  t < L). Columns marked LABEL SIDE must never enter a model.
- **Exclusions** (listed below): index contracts (3), and non-crypto underlyings: Q14's
  name list and timing screen, plus every life first trading on or after
  2025-12-01 whose median weekend-day quote volume is under
  0.60 of the median weekday (crypto contracts sit near 0.6 to 1.1) or
  which has under 14 trading days. Every flagged life was checked by name; five
  crypto lives under the cut are kept: CFGUSDT life 1, GRVTUSDT life 1, LITUSDT life 2, MOONSHOTUSDT life 1, PREDICTUSDT life 1. No excluded life is an event (all are alive, or index contracts).

## Announcement leakage (limitation)

Binance announces a futures delisting about 5 to 10 days before settlement (verified
notices: XEM/ORBS/LOOM, REEF, DEFI/MEMEFI, the 2025-12-05 batch), and the announcement moves
prices and volume (XEMUSDT quote volume went from about $5M a day to $47M to $90M on the
announcement days). The panel has **no announcement date per contract**. The final trading
month L is already excluded. When settlement falls early in month L, the announcement and
its spike fall in month L - 1, which is a positive row. `final_full_month` marks those rows,
and `b0_baselines.py` reports every result with and without them. Of the event lives with
a positive row, 39 settled on day 10 or earlier of month L, so for them month L - 1
very likely contains the announcement. Collecting the true announcement times (bapi list
endpoint, notes section 9) would replace this crude drop with a cut at the announcement.

## Data problems found

- AERGOUSDT: daily klines stop on 2026-06-30, but daily aggTrades has a file on 2026-07-23
  (lifecycle last day). L is taken from the lifecycle (2026-07), so the 2026-07 row is the
  final month and is dropped; features are unaffected.
- KEEPUSDT and NUUSDT (life 1) both stopped on 2022-02-15, when the tokens merged into
  Threshold; TUSDT only listed on 2023-02-01. The lifecycle counts them as a delisting and
  a reused-symbol life, so they are events here; the notes call them a merger [I]. Two of
  the 2022 events may therefore be token migrations.
- The listing month is partial, so a 3-month volume change measured from age 3 compares
  against a short month and reads too positive. Rule (a) treats young lives (age < 3,
  `dlog_qv_3m` null) as never flagged.
- Metrics (OI, long/short) start 2021-12 for most contracts: `has_oi` is false before.
  The weekend screen and Q14's list cover non-crypto lives; contracts first trading before
  2025-12-01 were only checked through Q14 (PAXG is the one excluded).

## Excluded lives (238)

- AAOIUSDT (life 1, from 2026-06-08): weekend screen (ratio 0.06), non-crypto by name
- AAPLUSDT (life 1, from 2026-04-06): weekend screen (ratio 0.15), non-crypto by name
- ABBVUSDT (life 1, from 2026-10-26): non-crypto by name; under 14 trading days to screen
- ACNUSDT (life 1, from 2026-09-29): weekend screen (ratio 0.23), non-crypto by name
- ADBEUSDT (life 1, from 2026-06-11): weekend screen (ratio 0.24), non-crypto by name
- AGPUUSDT (life 1, from 2026-09-18): weekend screen (ratio 0.15), non-crypto by name
- AKAMUSDT (life 1, from 2026-10-06): weekend screen (ratio 0.17), non-crypto by name
- ALABUSDT (life 1, from 2026-06-22): Q14 name review: stock (Astera Labs)
- AMATUSDT (life 1, from 2026-06-08): Q14 name review: stock (Applied Materials)
- AMCUSDT (life 1, from 2026-09-18): weekend screen (ratio 0.16), non-crypto by name
- AMDUSDT (life 1, from 2026-05-06): Q14 name review: stock (AMD)
- AMGNUSDT (life 1, from 2026-10-29): non-crypto by name; under 14 trading days to screen
- AMZNUSDT (life 1, from 2026-02-09): weekend screen (ratio 0.14), non-crypto by name
- ANETUSDT (life 1, from 2026-09-18): weekend screen (ratio 0.18), non-crypto by name
- ANTHROPICUSDT (life 1, from 2026-06-02): weekend screen (ratio 0.53), non-crypto by name
- APLDUSDT (life 1, from 2026-09-18): weekend screen (ratio 0.14), non-crypto by name
- APPUSDT (life 1, from 2026-07-10): weekend screen (ratio 0.14), non-crypto by name
- ARMUSDT (life 1, from 2026-05-26): Q14 name review: stock (Arm Holdings)
- ASMLUSDT (life 1, from 2026-06-11): Q14 name review: stock (ASML)
- ASTSUSDT (life 1, from 2026-06-01): Q14 name review: stock (AST SpaceMobile)
- AVGOUSDT (life 1, from 2026-04-20): Q14 name review: stock (Broadcom)
- AXTIUSDT (life 1, from 2026-06-08): weekend screen (ratio 0.08), non-crypto by name
- BABAUSDT (life 1, from 2026-04-20): weekend screen (ratio 0.09), non-crypto by name
- BACUSDT (life 1, from 2026-10-21): non-crypto by name; under 14 trading days to screen
- BBXUSDT (life 1, from 2026-06-01): weekend screen (ratio 0.21), non-crypto by name
- BEUSDT (life 1, from 2026-05-26): Q14 timing screen
- BITOUSDT (life 1, from 2026-07-27): weekend screen (ratio 0.53), non-crypto by name
- BLUEBIRDUSDT (life 1, from 2022-11-02): index contract
- BMNRUSDT (life 1, from 2026-06-11): weekend screen (ratio 0.13), non-crypto by name
- BNCUSDT (life 1, from 2026-07-09): weekend screen (ratio 0.29), non-crypto by name
- BOTUSDT (life 1, from 2026-07-09): weekend screen (ratio 0.14), non-crypto by name
- BRKBUSDT (life 1, from 2026-05-18): Q14 name review: stock (Berkshire Hathaway B)
- BSPUSDT (life 1, from 2026-07-02): weekend screen (ratio 0.21), non-crypto by name
- BWETUSDT (life 1, from 2026-09-29): weekend screen (ratio 0.15), non-crypto by name
- BXUSDT (life 1, from 2026-06-08): weekend screen (ratio 0.40), non-crypto by name
- BYDUSDT (life 1, from 2026-09-07): weekend screen (ratio 0.11), non-crypto by name
- BZUSDT (life 1, from 2026-04-01): weekend screen (ratio 0.24), non-crypto by name
- CATUSDT (life 1, from 2026-07-02): weekend screen (ratio 0.40), non-crypto by name
- CBRSUSDT (life 1, from 2026-05-19): weekend screen (ratio 0.06), non-crypto by name
- CEGUSDT (life 1, from 2026-10-21): non-crypto by name; under 14 trading days to screen
- CIENUSDT (life 1, from 2026-06-22): Q14 name review: stock (Ciena)
- CLUSDT (life 1, from 2026-04-01): weekend screen (ratio 0.21), non-crypto by name
- COHRUSDT (life 1, from 2026-05-26): weekend screen (ratio 0.08), non-crypto by name
- COINUSDT (life 1, from 2026-02-09): weekend screen (ratio 0.15), non-crypto by name
- COPPERUSDT (life 1, from 2026-03-06): weekend screen (ratio 0.26), non-crypto by name
- COSTUSDT (life 1, from 2026-06-09): Q14 name review: stock (Costco)
- CRCLUSDT (life 1, from 2026-02-09): Q14 name review: stock (Circle)
- CRDOUSDT (life 1, from 2026-06-08): Q14 name review: stock (Credo Technology)
- CRMLUSDT (life 1, from 2026-09-29): weekend screen (ratio 0.07), non-crypto by name
- CRMUSDT (life 1, from 2026-06-03): weekend screen (ratio 0.33), non-crypto by name
- CRWDUSDT (life 1, from 2026-06-08): weekend screen (ratio 0.20), non-crypto by name
- CRWVUSDT (life 1, from 2026-05-18): Q14 name review: stock (CoreWeave)
- CSCOUSDT (life 1, from 2026-05-15): weekend screen (ratio 0.42), non-crypto by name
- CSOPSAMSUNG2LUSDT (life 1, from 2026-08-11): weekend screen (ratio 0.13), non-crypto by name
- CSOPSKHYNIX2LUSDT (life 1, from 2026-08-11): weekend screen (ratio 0.10), non-crypto by name
- CVNAUSDT (life 1, from 2026-09-28): weekend screen (ratio 0.13), non-crypto by name
- CXMTUSDT (life 1, from 2026-08-18): weekend screen (ratio 0.13), non-crypto by name
- CYPHUSDT (life 1, from 2026-09-18): weekend screen (ratio 0.11), non-crypto by name
- DDOGUSDT (life 1, from 2026-09-02): weekend screen (ratio 0.16), non-crypto by name
- DEFIUSDT (life 1, from 2020-08-28): index contract
- DELLUSDT (life 1, from 2026-06-03): weekend screen (ratio 0.07), non-crypto by name
- DISUSDT (life 1, from 2026-05-15): weekend screen (ratio 0.29), non-crypto by name
- DJTUSDT (life 1, from 2026-08-25): weekend screen (ratio 0.14), non-crypto by name
- DKNGUSDT (life 1, from 2026-06-10): weekend screen (ratio 0.35), non-crypto by name
- DRAMUSDT (life 1, from 2026-05-18): Q14 timing screen
- EBAYUSDT (life 1, from 2026-06-09): weekend screen (ratio 0.19), non-crypto by name
- EIDOUSDT (life 1, from 2026-10-26): non-crypto by name; under 14 trading days to screen
- EQTUSDT (life 1, from 2026-10-26): non-crypto by name; under 14 trading days to screen
- EWJUSDT (life 1, from 2026-03-19): weekend screen (ratio 0.28), non-crypto by name
- EWTUSDT (life 1, from 2026-06-01): weekend screen (ratio 0.32), non-crypto by name
- EWYUSDT (life 1, from 2026-03-16): Q14 name review: ETF (South Korea)
- EWZSUSDT (life 1, from 2026-10-29): non-crypto by name; under 14 trading days to screen
- EWZUSDT (life 1, from 2026-06-10): Q14 name review: ETF (Brazil)
- FLEXUSDT (life 1, from 2026-07-02): weekend screen (ratio 0.19), non-crypto by name
- FLNCUSDT (life 1, from 2026-05-18): Q14 name review: stock (Fluence Energy)
- FOOTBALLUSDT (life 1, from 2022-09-01): index contract
- FRHCUSDT (life 1, from 2026-11-12): non-crypto by name; under 14 trading days to screen
- FWDIUSDT (life 1, from 2026-07-09): weekend screen (ratio 0.26), non-crypto by name
- GDXUSDT (life 1, from 2026-08-17): weekend screen (ratio 0.14), non-crypto by name
- GEVUSDT (life 1, from 2026-07-10): weekend screen (ratio 0.15), non-crypto by name
- GIGADEVUSDT (life 1, from 2026-08-03): weekend screen (ratio 0.11), non-crypto by name
- GLWUSDT (life 1, from 2026-06-11): weekend screen (ratio 0.07), non-crypto by name
- GMEUSDT (life 1, from 2026-06-10): weekend screen (ratio 0.32), non-crypto by name
- GOOGLUSDT (life 1, from 2026-03-26): Q14 name review: stock (Alphabet)
- GPROUSDT (life 1, from 2026-09-03): weekend screen (ratio 0.30), non-crypto by name
- GSUSDT (life 1, from 2026-07-29): weekend screen (ratio 0.26), non-crypto by name
- GTLBUSDT (life 1, from 2026-09-02): weekend screen (ratio 0.12), non-crypto by name
- HANMIUSDT (life 1, from 2026-08-14): weekend screen (ratio 0.27), non-crypto by name
- HDUSDT (life 1, from 2026-05-15): weekend screen (ratio 0.39), non-crypto by name
- HIMSUSDT (life 1, from 2026-06-09): weekend screen (ratio 0.09), non-crypto by name
- HK0625USDT (life 1, from 2026-09-01): weekend screen (ratio 0.19), non-crypto by name
- HK0700USDT (life 1, from 2026-07-22): weekend screen (ratio 0.11), non-crypto by name
- HK0992USDT (life 1, from 2026-09-07): weekend screen (ratio 0.07), non-crypto by name
- HK1810USDT (life 1, from 2026-07-22): weekend screen (ratio 0.11), non-crypto by name
- HOODUSDT (life 1, from 2026-02-02): weekend screen (ratio 0.10), non-crypto by name
- HPEUSDT (life 1, from 2026-06-08): Q14 name review: stock (Hewlett Packard Enterprise)
- HUTUSDT (life 1, from 2026-09-18): weekend screen (ratio 0.22), non-crypto by name
- HYUNDAIUSDT (life 1, from 2026-06-02): weekend screen (ratio 0.19), non-crypto by name
- IBKRUSDT (life 1, from 2026-10-21): non-crypto by name; under 14 trading days to screen
- IBMUSDT (life 1, from 2026-06-03): weekend screen (ratio 0.15), non-crypto by name
- INTCUSDT (life 1, from 2026-02-02): weekend screen (ratio 0.09), non-crypto by name
- INTWUSDT (life 1, from 2026-07-09): weekend screen (ratio 0.15), non-crypto by name
- IONQUSDT (life 1, from 2026-08-28): weekend screen (ratio 0.14), non-crypto by name
- IRENUSDT (life 1, from 2026-06-03): weekend screen (ratio 0.10), non-crypto by name
- IWMUSDT (life 1, from 2026-06-08): Q14 name review: ETF (Russell 2000)
- JPMUSDT (life 1, from 2026-05-18): Q14 name review: stock (JPMorgan Chase)
- KLACUSDT (life 1, from 2026-06-22): weekend screen (ratio 0.21), non-crypto by name
- KODEX200USDT (life 1, from 2026-08-14): weekend screen (ratio 0.34), non-crypto by name
- KORUUSDT (life 1, from 2026-06-22): weekend screen (ratio 0.07), non-crypto by name
- KOUSDT (life 1, from 2026-08-06): weekend screen (ratio 0.28), non-crypto by name
- KSTRUSDT (life 1, from 2026-07-02): weekend screen (ratio 0.11), non-crypto by name
- KUAISHOUUSDT (life 1, from 2026-08-11): weekend screen (ratio 0.12), non-crypto by name
- LGELECTRONICSUSDT (life 1, from 2026-08-14): weekend screen (ratio 0.28), non-crypto by name
- LITEUSDT (life 1, from 2026-05-15): weekend screen (ratio 0.06), non-crypto by name
- LLYUSDT (life 1, from 2026-06-01): weekend screen (ratio 0.19), non-crypto by name
- LRCXUSDT (life 1, from 2026-06-22): weekend screen (ratio 0.12), non-crypto by name
- LYTEUSDT (life 1, from 2026-08-17): weekend screen (ratio 0.15), non-crypto by name
- MARAUSDT (life 1, from 2026-08-28): weekend screen (ratio 0.12), non-crypto by name
- MCDUSDT (life 1, from 2026-10-06): weekend screen (ratio 0.19), non-crypto by name
- MDBUSDT (life 1, from 2026-09-02): weekend screen (ratio 0.11), non-crypto by name
- MDTUSDT (life 2, from 2026-10-21): non-crypto by name; under 14 trading days to screen
- MEITUANUSDT (life 1, from 2026-08-11): weekend screen (ratio 0.13), non-crypto by name
- MELIUSDT (life 1, from 2026-10-29): non-crypto by name; under 14 trading days to screen
- METAUSDT (life 1, from 2026-03-26): Q14 name review: stock (Meta Platforms)
- MINIMAXUSDT (life 1, from 2026-07-17): weekend screen (ratio 0.07), non-crypto by name
- MPUSDT (life 1, from 2026-09-29): weekend screen (ratio 0.11), non-crypto by name
- MRKUSDT (life 1, from 2026-08-28): weekend screen (ratio 0.19), non-crypto by name
- MRNAUSDT (life 1, from 2026-08-25): weekend screen (ratio 0.09), non-crypto by name
- MRVLUSDT (life 1, from 2026-05-15): weekend screen (ratio 0.08), non-crypto by name
- MSFTUSDT (life 1, from 2026-04-20): weekend screen (ratio 0.12), non-crypto by name
- MSTRUSDT (life 1, from 2026-02-09): weekend screen (ratio 0.20), non-crypto by name
- MSTUUSDT (life 1, from 2026-10-12): weekend screen (ratio 0.39), non-crypto by name
- MUUSDT (life 1, from 2026-04-07): weekend screen (ratio 0.11), non-crypto by name
- MUUUSDT (life 1, from 2026-07-16): weekend screen (ratio 0.06), non-crypto by name
- MVLLUSDT (life 1, from 2026-06-29): Q14 timing screen
- NATGASUSDT (life 1, from 2026-04-01): weekend screen (ratio 0.16), non-crypto by name
- NAVERUSDT (life 1, from 2026-08-14): weekend screen (ratio 0.44), non-crypto by name
- NBISUSDT (life 1, from 2026-05-26): weekend screen (ratio 0.08), non-crypto by name
- NETUSDT (life 1, from 2026-08-17): weekend screen (ratio 0.19), non-crypto by name
- NFLXUSDT (life 1, from 2026-06-09): weekend screen (ratio 0.20), non-crypto by name
- NKEUSDT (life 1, from 2026-09-29): weekend screen (ratio 0.18), non-crypto by name
- NOKUSDT (life 1, from 2026-06-01): weekend screen (ratio 0.11), non-crypto by name
- NOWUSDT (life 1, from 2026-06-03): weekend screen (ratio 0.16), non-crypto by name
- NUUSDT (life 2, from 2026-11-12): non-crypto by name; under 14 trading days to screen
- NVDAUSDT (life 1, from 2026-03-26): weekend screen (ratio 0.12), non-crypto by name
- NVDLUSDT (life 1, from 2026-09-02): weekend screen (ratio 0.24), non-crypto by name
- NVOUSDT (life 1, from 2026-06-01): weekend screen (ratio 0.26), non-crypto by name
- OKLOUSDT (life 1, from 2026-09-28): weekend screen (ratio 0.13), non-crypto by name
- ONDSUSDT (life 1, from 2026-06-03): weekend screen (ratio 0.16), non-crypto by name
- OPENAIUSDT (life 1, from 2026-05-26): weekend screen (ratio 0.54), non-crypto by name
- ORCLUSDT (life 1, from 2026-05-15): weekend screen (ratio 0.09), non-crypto by name
- OXYUSDT (life 1, from 2026-10-29): non-crypto by name; under 14 trading days to screen
- PANWUSDT (life 1, from 2026-07-21): weekend screen (ratio 0.13), non-crypto by name
- PATHUSDT (life 1, from 2026-09-18): weekend screen (ratio 0.26), non-crypto by name
- PAXGUSDT (life 1, from 2025-03-27): Q14 name review: gold-backed token
- PAYPUSDT (life 1, from 2026-03-23): weekend screen (ratio 0.28), non-crypto by name
- PDDUSDT (life 1, from 2026-08-28): weekend screen (ratio 0.21), non-crypto by name
- PENGUSDT (life 1, from 2026-07-21): weekend screen (ratio 0.23), non-crypto by name
- PFEUSDT (life 1, from 2026-10-29): non-crypto by name; under 14 trading days to screen
- PLTRUSDT (life 1, from 2026-02-09): weekend screen (ratio 0.10), non-crypto by name
- POPMARTUSDT (life 1, from 2026-07-23): weekend screen (ratio 0.17), non-crypto by name
- PYPLUSDT (life 1, from 2026-07-29): weekend screen (ratio 0.20), non-crypto by name
- QCOMUSDT (life 1, from 2026-05-06): Q14 name review: stock (Qualcomm)
- QNTXUSDT (life 1, from 2026-05-29): weekend screen (ratio 0.17), non-crypto by name
- QQQUSDT (life 1, from 2026-04-06): Q14 name review: ETF (Nasdaq-100)
- RAMUSDT (life 1, from 2026-08-25): weekend screen (ratio 0.20), non-crypto by name
- RDDTUSDT (life 1, from 2026-08-06): weekend screen (ratio 0.24), non-crypto by name
- RDWUSDT (life 1, from 2026-10-12): weekend screen (ratio 0.17), non-crypto by name
- RIVNUSDT (life 1, from 2026-06-10): weekend screen (ratio 0.33), non-crypto by name
- RKLBUSDT (life 1, from 2026-05-18): weekend screen (ratio 0.07), non-crypto by name
- RUMUSDT (life 1, from 2026-09-28): weekend screen (ratio 0.10), non-crypto by name
- SAMSUNGEMUSDT (life 1, from 2026-08-14): weekend screen (ratio 0.32), non-crypto by name
- SAMSUNGUSDT (life 1, from 2026-06-02): weekend screen (ratio 0.07), non-crypto by name
- SECZUSDT (life 1, from 2026-09-29): weekend screen (ratio 0.23), non-crypto by name
- SHAZUSDT (life 1, from 2026-07-21): weekend screen (ratio 0.14), non-crypto by name
- SHOPUSDT (life 1, from 2026-08-17): weekend screen (ratio 0.17), non-crypto by name
- SKDDUSDT (life 1, from 2026-08-25): weekend screen (ratio 0.25), non-crypto by name
- SKHYNIXUSDT (life 1, from 2026-06-02): Q14 name review: stock (SK hynix)
- SKHYUSDT (life 1, from 2026-07-10): weekend screen (ratio 0.08), non-crypto by name
- SKUUUSDT (life 1, from 2026-08-25): weekend screen (ratio 0.19), non-crypto by name
- SMCIUSDT (life 1, from 2026-06-22): weekend screen (ratio 0.24), non-crypto by name
- SMHUSDT (life 1, from 2026-07-29): weekend screen (ratio 0.33), non-crypto by name
- SMRUSDT (life 1, from 2026-10-29): non-crypto by name; under 14 trading days to screen
- SNDKUSDT (life 1, from 2026-04-07): Q14 name review: stock (SanDisk)
- SNOWUSDT (life 1, from 2026-07-10): weekend screen (ratio 0.21), non-crypto by name
- SNPSUSDT (life 1, from 2026-10-12): weekend screen (ratio 0.21), non-crypto by name
- SNXXUSDT (life 1, from 2026-07-09): weekend screen (ratio 0.09), non-crypto by name
- SOFIUSDT (life 1, from 2026-07-21): weekend screen (ratio 0.16), non-crypto by name
- SONYUSDT (life 1, from 2026-06-22): Q14 name review: stock (Sony)
- SOXLUSDT (life 1, from 2026-05-15): weekend screen (ratio 0.07), non-crypto by name
- SOXSUSDT (life 1, from 2026-07-16): weekend screen (ratio 0.10), non-crypto by name
- SPCXUSDT (life 1, from 2026-05-21): weekend screen (ratio 0.07), non-crypto by name
- SPYUSDT (life 1, from 2026-04-06): weekend screen (ratio 0.32), non-crypto by name
- SQQQUSDT (life 1, from 2026-06-29): Q14 name review: ETF (inverse Nasdaq-100)
- STMUSDT (life 1, from 2026-10-26): non-crypto by name; under 14 trading days to screen
- STRCUSDT (life 1, from 2026-07-02): weekend screen (ratio 0.19), non-crypto by name
- STXXUSDT (life 1, from 2026-06-11): weekend screen (ratio 0.14), non-crypto by name
- TBTUSDT (life 1, from 2026-07-27): weekend screen (ratio 0.28), non-crypto by name
- TEAMUSDT (life 1, from 2026-09-02): weekend screen (ratio 0.21), non-crypto by name
- TEMUSDT (life 1, from 2026-08-28): weekend screen (ratio 0.12), non-crypto by name
- TENCENTUSDT (life 1, from 2026-07-22): weekend screen (ratio 0.17), non-crypto by name
- TERUSDT (life 1, from 2026-07-02): weekend screen (ratio 0.17), non-crypto by name
- TMFUSDT (life 1, from 2026-07-27): weekend screen (ratio 0.18), non-crypto by name
- TQQQUSDT (life 1, from 2026-06-29): weekend screen (ratio 0.11), non-crypto by name
- TSLAUSDT (life 1, from 2026-01-28): Q14 name review: stock (Tesla)
- TSLLUSDT (life 1, from 2026-09-02): weekend screen (ratio 0.15), non-crypto by name
- TSMUSDT (life 1, from 2026-04-06): weekend screen (ratio 0.12), non-crypto by name
- TTWOUSDT (life 1, from 2026-07-02): weekend screen (ratio 0.23), non-crypto by name
- TWSTUSDT (life 1, from 2026-09-28): weekend screen (ratio 0.08), non-crypto by name
- TXNUSDT (life 1, from 2026-07-02): weekend screen (ratio 0.22), non-crypto by name
- TZAUSDT (life 1, from 2026-07-16): weekend screen (ratio 0.41), non-crypto by name
- UBERUSDT (life 1, from 2026-05-15): Q14 name review: stock (Uber)
- UNHUSDT (life 1, from 2026-09-29): weekend screen (ratio 0.16), non-crypto by name
- UNITREEUSDT (life 1, from 2026-08-19): weekend screen (ratio 0.09), non-crypto by name
- URNMUSDT (life 1, from 2026-06-09): Q14 name review: ETF (uranium miners)
- USARUSDT (life 1, from 2026-05-06): weekend screen (ratio 0.11), non-crypto by name
- USDBRLUSDT (life 1, from 2026-09-21): weekend screen (ratio 0.56), non-crypto by name
- USDEXUSDT (life 1, from 2026-10-06): weekend screen (ratio 0.24), non-crypto by name
- UVXYUSDT (life 1, from 2026-06-11): weekend screen (ratio 0.21), non-crypto by name
- VKTXUSDT (life 1, from 2026-10-06): weekend screen (ratio 0.11), non-crypto by name
- VRTUSDT (life 1, from 2026-07-10): weekend screen (ratio 0.15), non-crypto by name
- VSTUSDT (life 1, from 2026-08-17): weekend screen (ratio 0.29), non-crypto by name
- VUSDT (life 1, from 2026-05-18): Q14 name review: stock (Visa)
- WDCUSDT (life 1, from 2026-05-26): weekend screen (ratio 0.06), non-crypto by name
- WENUSDT (life 1, from 2026-07-09): weekend screen (ratio 0.26), non-crypto by name
- WMTUSDT (life 1, from 2026-05-18): weekend screen (ratio 0.24), non-crypto by name
- XAGUSDT (life 1, from 2026-01-07): weekend screen (ratio 0.12), non-crypto by name
- XAUTUSDT (life 1, from 2026-03-26): weekend screen (ratio 0.27), non-crypto by name
- XAUUSDT (life 1, from 2025-12-11): Q14 name review: commodity (gold)
- XBIUSDT (life 1, from 2026-07-09): weekend screen (ratio 0.46), non-crypto by name
- XLEUSDT (life 1, from 2026-06-10): weekend screen (ratio 0.51), non-crypto by name
- XOMUSDT (life 1, from 2026-09-28): weekend screen (ratio 0.17), non-crypto by name
- XPDUSDT (life 1, from 2026-01-30): weekend screen (ratio 0.23), non-crypto by name
- XPTUSDT (life 1, from 2026-01-30): Q14 name review: commodity (platinum)
- ZHIPUUSDT (life 1, from 2026-07-17): weekend screen (ratio 0.07), non-crypto by name
- ZHONGJIUSDT (life 1, from 2026-08-14): weekend screen (ratio 0.09), non-crypto by name
- ZMUSDT (life 1, from 2026-06-10): weekend screen (ratio 0.47), non-crypto by name
- ZSUSDT (life 1, from 2026-09-02): weekend screen (ratio 0.23), non-crypto by name

## Columns

| column | type | definition |
|---|---|---|
| `life_id` | String | SYMBOL#life (life 2 = the ticker trading again after a gap over 30 days) |
| `symbol` | String | contract ticker |
| `life` | Int64 | life number from the lifecycle table |
| `month` | String | month t (YYYY-MM): the row is a prediction made at the end of month t |
| `t` | Int64 | month index year * 12 + month - 1 (for arithmetic) |
| `y3` | Int8 | 1 if the life's last trading month L is in t+1..t+3 and the life is an event |
| `event` | Boolean | the life ends in a delisting (status delisted, or reused-symbol first life) |
| `status` | String | lifecycle status of the life (delisted, reused-symbol, renamed, merged, alive) |
| `outcome` | String | event or censored |
| `last_trade_day` | Date | last day with a daily aggTrades file (lifecycle table). LABEL SIDE |
| `last_trade_month` | String | L, month of last_trade_day. LABEL SIDE, never a feature |
| `months_to_last` | Int32 | L - t (>= 1). LABEL SIDE, never a feature |
| `last_trade_dom` | Int8 | day of month of last_trade_day. LABEL SIDE, never a feature |
| `final_full_month` | Boolean | event life and t = L - 1 (the month most exposed to the announcement); the sensitivity run drops these rows. LABEL SIDE |
| `lockbox` | Boolean | t >= 2026-01: reserved lock-box origin, not scored in b0 |
| `first_trade_day` | Date | first day of the life (aggTrades) |
| `successor` | String | new ticker for renamed and merged lives (information only) |
| `age_months` | Int32 | months since the life's first trading month (0 = listing month) |
| `log_age` | Float64 | ln(1 + age_months) |
| `has_klines` | Boolean | a 1d kline file exists for month t |
| `has_funding` | Boolean | a fundingRate file exists for month t |
| `has_metrics` | Boolean | a metrics file exists for month t (most contracts from 2021-12) |
| `ghost_month` | Boolean | files but no day with volume > 0 in month t (only possible inside a life if trading paused a whole month; 0 rows in the kept panel) |
| `resumed_after_ghost` | Boolean | monthly panel flag, kept for audit; the life split already resets age and peaks |
| `days_in_month` | Int32 | calendar days |
| `n_kline_days` | UInt32 | daily kline rows in month t |
| `missing_kline_days` | Int64 | days_in_month - n_kline_days (listing month, gaps) |
| `trading_days` | Int32 | daily kline rows with volume > 0 |
| `zero_volume_days` | Int32 | n_kline_days - trading_days (ghost-like days inside month t) |
| `quote_volume` | Float64 | USDT quote volume summed over month t |
| `quote_volume_median` | Float64 | median daily quote volume in month t (zero days included) |
| `n_trades` | Int64 | trades in month t (sum of daily count) |
| `avg_trade_usd` | Float64 | quote_volume / n_trades |
| `taker_buy_share` | Float64 | taker buy quote volume / quote volume |
| `close_last` | Float64 | close of the last kline day of month t |
| `ret_month` | Float64 | close_last / first open of month t - 1 |
| `realized_vol` | Float64 | std of daily log returns in month t (trading days) |
| `mean_range` | Float64 | mean (high - low) / close on trading days of month t |
| `dd_life_month_end` | Float64 | close at the last trading day of month t / running max daily close since the life's first day - 1 (per life, so a second life does not inherit the first life's peak) |
| `max_dd_life` | Float64 | worst daily close / running max since the life's first day - 1, within month t |
| `oi_usd_month_end` | Float64 | open interest value (USDT) at the last 5-minute row of the last metrics day of month t; null without metrics |
| `has_oi` | Boolean | oi_usd_month_end is present and > 0 |
| `log_oi` | Float64 | ln(1 + oi_usd_month_end) when > 0, else null |
| `log_oi_to_qv` | Float64 | log_oi - log_qv (OI relative to monthly volume) |
| `ls_account_month_end` | Float64 | all-account long/short ratio, same metrics row |
| `ls_toptrader_account_month_end` | Float64 | top-trader account long/short ratio, same row |
| `metrics_is_last_day` | Boolean | the metrics day is the calendar month-end |
| `n_funding` | UInt32 | funding events in month t |
| `funding_mean` | Float64 | mean funding rate per interval in month t |
| `funding_abs_mean` | Float64 | mean absolute funding rate |
| `funding_interval_min_h` | Float64 | shortest funding interval (hours) seen in month t |
| `log_qv` | Float64 | ln(1 + quote_volume) |
| `log_trades` | Float64 | ln(1 + n_trades) |
| `dlog_qv_3m` | Float64 | log_qv(t) - log_qv(t-3), same life; null if t-3 is before the life |
| `dlog_qv_6m` | Float64 | log_qv(t) - log_qv(t-6), same life |
| `dlog_trades_3m` | Float64 | log_trades(t) - log_trades(t-3), same life |
| `dlog_trades_6m` | Float64 | log_trades(t) - log_trades(t-6), same life |
| `log_qv_rel_peak` | Float64 | log_qv(t) - max over the life's months up to t of log_qv (<= 0; -4.6 is the Feder 1%-of-peak rule) |
| `log_trades_rel_peak` | Float64 | same for log_trades |
| `ret_3m` | Float64 | close_last(t) / close_last(t-3) - 1, same life |
| `ret_6m` | Float64 | close_last(t) / close_last(t-6) - 1, same life |
| `dlog_oi_3m` | Float64 | log_oi(t) - log_oi(t-3), same life |
| `funding_interval_shortened` | Boolean | funding_interval_min_h(t) < its value at t-1 |
| `qv_rank_pct` | Float64 | percentile rank of log_qv within month t among live contracts (1 = largest); live = included lives still trading after month t |
| `trades_rank_pct` | Float64 | same for log_trades |
| `oi_rank_pct` | Float64 | same for log_oi (among live contracts with OI) |
| `n_live_month` | Int32 | number of live contracts in month t (rank denominator) |
