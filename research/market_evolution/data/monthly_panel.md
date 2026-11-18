# Monthly contract panel (Part B)

Built by `research/market_evolution/build_monthly_panel.py`; the parquet is `data/panels/monthly_panel.parquet` (git-ignored). One row per USDT-M perpetual (symbol ends in USDT, no underscore) per calendar month with any 1d kline, fundingRate or metrics file. No labels: join the lifecycle table later. Features use only that month's data, except the running peak close behind the drawdowns (history up to and including the month).

Metrics are subsampled: ONE daily metrics file per contract-month, the last available day of that month. Month-end OI and long/short ratios come from its last 5-minute row with a non-null OI. Metrics start 2021-12 for most contracts (BTCUSDT 2020-09); earlier months have nulls, not zeros.

Ghost rows: klines, funding and metrics keep publishing files after a contract stops trading (flat prices, volume 0, OI 0, funding 0.0001). They are kept and flagged with `ghost_month`; do not use the last file as the delisting date.

## Build

- Built 2026-11-18 00:21 UTC, panel end month 2026-10.
- Rows: 23,356; contracts: 924; months: 2020-01 to 2026-10 (82 months).
- Ghost months: 2,126 (9.1% of rows); rows with klines but no trading: 1,914; rows without any kline file: 212.
- Rows trading again after a ghost month (`resumed_after_ghost`, relistings or reused symbols): 14: BNTUSDT 2023-08, BZUSDT 2026-04, CLUSDT 2026-04, CTKUSDT 2025-04, CVCUSDT 2025-05, CVXUSDT 2025-07, FOOTBALLUSDT 2022-09, ICPUSDT 2022-09, LITUSDT 2025-12, MAVIAUSDT 2025-03, MDTUSDT 2026-10, NATGASUSDT 2026-04, SLPUSDT 2025-07, TLMUSDT 2023-03.
- Rows with metrics: 20,301; metrics day is the calendar month-end in 19,817 of them.
- Downloaded: 65,305 zips, 272.8 MB (klines 23,144, funding 21,860, metrics 20,301); each checked against its published SHA-256, zips deleted after parsing.
- Build time: fetch 91 min wall clock over 3 run(s) with up to 8 concurrent downloads (11.6 worker-hours), aggregation 3.4 s. Disk: about 57 MB of per-contract parquet under data/raw_panel/.
- Download errors: 0.
- 0 contracts have 1d klines but are absent from the aggTrades inventory (`data/universe/aggtrades_monthly_inventory.json`).
- 1 contracts have funding or metrics files but no 1d klines: GAIBUSDT.
- 1 symbols have no file up to 2026-10 (listed later, no panel rows): FRHCUSDT.
- Cross-check with the aggTrades inventory: 0 trading (non-ghost) months have no aggTrades file; 2 ghost months do have one (AI16ZUSDT 2025-12, KDAUSDT 2025-12).

## Columns

| column | unit | definition |
|---|---|---|
| `symbol` |  | contract, ends in USDT, no underscore |
| `month` | YYYY-MM | calendar month (UTC) |
| `age_months` | months | months since the contract's first panel row (0 = first) |
| `has_klines / has_funding / has_metrics` | bool | a file of that type exists |
| `ghost_month` | bool | files exist but no day with volume > 0 (incl. no kline file) |
| `resumed_after_ghost` | bool | trades this month after a ghost month (relisting or reused symbol: running peak and age then mix two lives) |
| `days_in_month` | days | calendar days |
| `n_kline_days` | days | daily kline rows in the month |
| `missing_kline_days` | days | days_in_month minus n_kline_days (listing, gaps, end) |
| `trading_days` | days | daily rows with volume > 0 |
| `first_day, last_day, last_trading_day` | date | first/last kline day; last day with volume > 0 |
| `quote_volume` | USDT | sum of daily quote volume |
| `quote_volume_median` | USDT/day | median over the month's kline days (zero days included) |
| `n_trades` | trades | sum of daily `count` |
| `avg_trade_usd` | USDT | quote_volume / n_trades |
| `taker_buy_share` | fraction | taker buy quote volume / quote volume |
| `open_first, close_last` | USDT | open of the first kline day, close of the last |
| `ret_month` | fraction | close_last / open_first - 1 (the first day's open is the previous close on a continuous contract) |
| `realized_vol` | log return/day | std (ddof 1) of daily close-to-close log returns on days with volume > 0; the month's first day uses its own open, so no prior-month data |
| `mean_range` | fraction | mean (high - low) / close on days with volume > 0 |
| `dd_month_end` | fraction <= 0 | month-end close / running peak close - 1; the running peak is the max daily close from the first kline day up to that day |
| `max_dd` | fraction <= 0 | worst daily close / running peak - 1 within the month |
| `oi_usd_month_end` | USDT | sum_open_interest_value, last 5-min row with OI of the metrics day used (0 in ghost months) |
| `ls_account_month_end` | ratio | count_long_short_ratio (all accounts), same row |
| `ls_toptrader_account_month_end` | ratio | count_toptrader_long_short_ratio, same row |
| `metrics_date, metrics_ts, metrics_rows` | date, datetime, rows | metrics day used (last available day of the month), its row time, rows in that file |
| `metrics_is_last_day` | bool | metrics_date is the calendar month-end |
| `n_funding` | events | funding events in the month |
| `funding_mean, funding_abs_mean` | rate per interval | mean and mean absolute `last_funding_rate` (0.0001 = 1 bp; ghost months show the constant default) |
| `funding_interval_min_h` | hours | shortest funding interval seen in the month |

## Coverage by month

| month | contracts | trading | ghost | with metrics | with funding |
|---|---|---|---|---|---|
| 2020-01 | 11 | 11 | 0 | 0 | 11 |
| 2020-02 | 24 | 24 | 0 | 0 | 23 |
| 2020-03 | 24 | 24 | 0 | 0 | 24 |
| 2020-04 | 24 | 24 | 0 | 0 | 24 |
| 2020-05 | 25 | 25 | 0 | 0 | 25 |
| 2020-06 | 30 | 30 | 0 | 0 | 30 |
| 2020-07 | 37 | 37 | 0 | 0 | 37 |
| 2020-08 | 43 | 43 | 0 | 0 | 43 |
| 2020-09 | 62 | 62 | 0 | 1 | 62 |
| 2020-10 | 71 | 71 | 0 | 1 | 71 |
| 2020-11 | 78 | 77 | 1 | 1 | 77 |
| 2020-12 | 80 | 80 | 0 | 1 | 80 |
| 2021-01 | 87 | 86 | 1 | 1 | 87 |
| 2021-02 | 94 | 93 | 1 | 1 | 94 |
| 2021-03 | 108 | 106 | 2 | 1 | 108 |
| 2021-04 | 112 | 110 | 2 | 1 | 112 |
| 2021-05 | 114 | 113 | 1 | 1 | 113 |
| 2021-06 | 117 | 116 | 1 | 1 | 116 |
| 2021-07 | 118 | 117 | 1 | 1 | 116 |
| 2021-08 | 124 | 123 | 1 | 1 | 122 |
| 2021-09 | 129 | 128 | 1 | 1 | 127 |
| 2021-10 | 133 | 132 | 1 | 1 | 131 |
| 2021-11 | 135 | 134 | 1 | 1 | 133 |
| 2021-12 | 138 | 137 | 1 | 138 | 136 |
| 2022-01 | 139 | 138 | 1 | 138 | 136 |
| 2022-02 | 141 | 140 | 1 | 139 | 139 |
| 2022-03 | 142 | 141 | 1 | 140 | 140 |
| 2022-04 | 147 | 146 | 1 | 145 | 144 |
| 2022-05 | 146 | 145 | 1 | 145 | 143 |
| 2022-06 | 151 | 142 | 9 | 150 | 140 |
| 2022-07 | 143 | 139 | 4 | 139 | 140 |
| 2022-08 | 146 | 141 | 5 | 144 | 143 |
| 2022-09 | 158 | 147 | 11 | 157 | 149 |
| 2022-10 | 160 | 149 | 11 | 158 | 151 |
| 2022-11 | 161 | 150 | 11 | 160 | 152 |
| 2022-12 | 161 | 146 | 15 | 160 | 152 |
| 2023-01 | 164 | 150 | 14 | 163 | 156 |
| 2023-02 | 177 | 164 | 13 | 176 | 171 |
| 2023-03 | 185 | 174 | 11 | 183 | 181 |
| 2023-04 | 191 | 178 | 13 | 189 | 186 |
| 2023-05 | 199 | 185 | 14 | 196 | 193 |
| 2023-06 | 198 | 188 | 10 | 194 | 197 |
| 2023-07 | 203 | 193 | 10 | 194 | 202 |
| 2023-08 | 208 | 199 | 9 | 199 | 208 |
| 2023-09 | 214 | 204 | 10 | 205 | 213 |
| 2023-10 | 228 | 218 | 10 | 219 | 227 |
| 2023-11 | 247 | 237 | 10 | 238 | 246 |
| 2023-12 | 254 | 243 | 11 | 245 | 253 |
| 2024-01 | 263 | 251 | 12 | 253 | 260 |
| 2024-02 | 277 | 260 | 17 | 267 | 270 |
| 2024-03 | 282 | 268 | 14 | 272 | 278 |
| 2024-04 | 290 | 272 | 18 | 280 | 285 |
| 2024-05 | 291 | 272 | 19 | 281 | 288 |
| 2024-06 | 294 | 267 | 27 | 284 | 293 |
| 2024-07 | 294 | 265 | 29 | 284 | 294 |
| 2024-08 | 302 | 278 | 24 | 281 | 302 |
| 2024-09 | 317 | 296 | 21 | 301 | 316 |
| 2024-10 | 326 | 304 | 22 | 309 | 325 |
| 2024-11 | 348 | 323 | 25 | 331 | 346 |
| 2024-12 | 374 | 349 | 25 | 357 | 372 |
| 2025-01 | 395 | 361 | 34 | 378 | 393 |
| 2025-02 | 404 | 366 | 38 | 386 | 402 |
| 2025-03 | 426 | 387 | 39 | 408 | 424 |
| 2025-04 | 445 | 406 | 39 | 417 | 445 |
| 2025-05 | 468 | 424 | 44 | 440 | 468 |
| 2025-06 | 488 | 442 | 46 | 458 | 487 |
| 2025-07 | 507 | 464 | 43 | 468 | 468 |
| 2025-08 | 526 | 482 | 44 | 486 | 486 |
| 2025-09 | 558 | 512 | 46 | 518 | 516 |
| 2025-10 | 587 | 534 | 53 | 548 | 538 |
| 2025-11 | 601 | 544 | 57 | 559 | 549 |
| 2025-12 | 615 | 548 | 67 | 575 | 553 |
| 2026-01 | 633 | 558 | 75 | 593 | 563 |
| 2026-02 | 645 | 561 | 84 | 584 | 566 |
| 2026-03 | 663 | 569 | 94 | 587 | 577 |
| 2026-04 | 677 | 577 | 100 | 602 | 582 |
| 2026-05 | 707 | 591 | 116 | 634 | 595 |
| 2026-06 | 764 | 645 | 119 | 693 | 649 |
| 2026-07 | 805 | 680 | 125 | 734 | 683 |
| 2026-08 | 836 | 711 | 125 | 764 | 714 |
| 2026-09 | 872 | 740 | 132 | 801 | 743 |
| 2026-10 | 895 | 763 | 132 | 839 | 766 |
