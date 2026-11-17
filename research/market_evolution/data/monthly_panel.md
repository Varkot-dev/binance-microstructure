# Monthly contract panel (Part B)

Built by `research/market_evolution/build_monthly_panel.py`; the parquet is `data/panels/monthly_panel.parquet` (git-ignored). One row per USDT-M perpetual (symbol ends in USDT, no underscore) per calendar month with any 1d kline, fundingRate or metrics file. No labels: join the lifecycle table later. Features use only that month's data, except the running peak close behind the drawdowns (history up to and including the month).

Metrics are subsampled: ONE daily metrics file per contract-month, the last available day of that month. Month-end OI and long/short ratios come from its last 5-minute row with a non-null OI. Metrics start 2021-12 for most contracts (BTCUSDT 2020-09); earlier months have nulls, not zeros.

Ghost rows: klines, funding and metrics keep publishing files after a contract stops trading (flat prices, volume 0, OI 0, funding 0.0001). They are kept and flagged with `ghost_month`; do not use the last file as the delisting date.

## Build

- Built 2026-11-17 22:51 UTC, panel end month 2026-10.
- Rows: 130; contracts: 3; months: 2020-09 to 2026-10 (74 months).
- Ghost months: 39 (30.0% of rows); rows with klines but no trading: 36; rows without any kline file: 3.
- Rows with metrics: 73; metrics day is the calendar month-end in 68 of them.
- Downloaded: 314 zips, 1.0 MB (klines 127, funding 114, metrics 73); each checked against its published SHA-256, zips deleted after parsing.
- Build time: fetch 3.7 min (summed over runs, 6 workers), aggregation 0.1 s.
- Download errors: 0.
- 0 contracts have 1d klines but are absent from the aggTrades inventory (`data/universe/aggtrades_monthly_inventory.json`).

## Columns

| column | unit | definition |
|---|---|---|
| `symbol` |  | contract, ends in USDT, no underscore |
| `month` | YYYY-MM | calendar month (UTC) |
| `age_months` | months | months since the contract's first panel row (0 = first) |
| `has_klines / has_funding / has_metrics` | bool | a file of that type exists |
| `ghost_month` | bool | files exist but no day with volume > 0 (incl. no kline file) |
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
| 2020-09 | 1 | 1 | 0 | 0 | 1 |
| 2020-10 | 1 | 1 | 0 | 0 | 1 |
| 2020-11 | 1 | 1 | 0 | 0 | 1 |
| 2020-12 | 1 | 1 | 0 | 0 | 1 |
| 2021-01 | 1 | 1 | 0 | 0 | 1 |
| 2021-02 | 1 | 1 | 0 | 0 | 1 |
| 2021-03 | 2 | 2 | 0 | 0 | 2 |
| 2021-04 | 2 | 2 | 0 | 0 | 2 |
| 2021-05 | 2 | 2 | 0 | 0 | 2 |
| 2021-06 | 2 | 2 | 0 | 0 | 2 |
| 2021-07 | 2 | 2 | 0 | 0 | 2 |
| 2021-08 | 2 | 2 | 0 | 0 | 2 |
| 2021-09 | 2 | 2 | 0 | 0 | 2 |
| 2021-10 | 2 | 2 | 0 | 0 | 2 |
| 2021-11 | 2 | 2 | 0 | 0 | 2 |
| 2021-12 | 2 | 2 | 0 | 2 | 2 |
| 2022-01 | 2 | 2 | 0 | 2 | 2 |
| 2022-02 | 2 | 2 | 0 | 2 | 2 |
| 2022-03 | 2 | 2 | 0 | 2 | 2 |
| 2022-04 | 2 | 2 | 0 | 2 | 2 |
| 2022-05 | 2 | 2 | 0 | 2 | 2 |
| 2022-06 | 2 | 2 | 0 | 2 | 2 |
| 2022-07 | 2 | 2 | 0 | 2 | 2 |
| 2022-08 | 2 | 2 | 0 | 2 | 2 |
| 2022-09 | 2 | 2 | 0 | 2 | 2 |
| 2022-10 | 2 | 2 | 0 | 2 | 2 |
| 2022-11 | 2 | 2 | 0 | 2 | 2 |
| 2022-12 | 2 | 2 | 0 | 2 | 2 |
| 2023-01 | 2 | 2 | 0 | 2 | 2 |
| 2023-02 | 2 | 2 | 0 | 2 | 2 |
| 2023-03 | 2 | 2 | 0 | 2 | 2 |
| 2023-04 | 2 | 1 | 1 | 2 | 2 |
| 2023-05 | 2 | 1 | 1 | 2 | 2 |
| 2023-06 | 2 | 1 | 1 | 2 | 2 |
| 2023-07 | 2 | 1 | 1 | 1 | 2 |
| 2023-08 | 2 | 1 | 1 | 1 | 2 |
| 2023-09 | 2 | 1 | 1 | 1 | 2 |
| 2023-10 | 2 | 1 | 1 | 1 | 2 |
| 2023-11 | 2 | 1 | 1 | 1 | 2 |
| 2023-12 | 2 | 1 | 1 | 1 | 2 |
| 2024-01 | 2 | 1 | 1 | 1 | 2 |
| 2024-02 | 2 | 1 | 1 | 1 | 2 |
| 2024-03 | 2 | 1 | 1 | 1 | 2 |
| 2024-04 | 2 | 1 | 1 | 1 | 2 |
| 2024-05 | 2 | 1 | 1 | 1 | 2 |
| 2024-06 | 2 | 1 | 1 | 1 | 2 |
| 2024-07 | 2 | 1 | 1 | 1 | 2 |
| 2024-08 | 2 | 1 | 1 | 1 | 2 |
| 2024-09 | 1 | 1 | 0 | 1 | 1 |
| 2024-10 | 1 | 1 | 0 | 1 | 1 |
| 2024-11 | 1 | 1 | 0 | 1 | 1 |
| 2024-12 | 1 | 1 | 0 | 1 | 1 |
| 2025-01 | 1 | 0 | 1 | 1 | 1 |
| 2025-02 | 1 | 0 | 1 | 1 | 1 |
| 2025-03 | 1 | 0 | 1 | 1 | 1 |
| 2025-04 | 1 | 0 | 1 | 0 | 1 |
| 2025-05 | 1 | 0 | 1 | 0 | 1 |
| 2025-06 | 1 | 0 | 1 | 0 | 1 |
| 2025-07 | 1 | 0 | 1 | 0 | 0 |
| 2025-08 | 1 | 0 | 1 | 0 | 0 |
| 2025-09 | 2 | 1 | 1 | 1 | 1 |
| 2025-10 | 2 | 1 | 1 | 1 | 1 |
| 2025-11 | 2 | 1 | 1 | 1 | 1 |
| 2025-12 | 2 | 1 | 1 | 1 | 1 |
| 2026-01 | 2 | 1 | 1 | 1 | 1 |
| 2026-02 | 2 | 1 | 1 | 1 | 1 |
| 2026-03 | 2 | 1 | 1 | 1 | 1 |
| 2026-04 | 2 | 1 | 1 | 1 | 1 |
| 2026-05 | 2 | 1 | 1 | 1 | 1 |
| 2026-06 | 2 | 1 | 1 | 1 | 1 |
| 2026-07 | 2 | 1 | 1 | 1 | 1 |
| 2026-08 | 2 | 1 | 1 | 1 | 1 |
| 2026-09 | 2 | 1 | 1 | 1 | 1 |
| 2026-10 | 2 | 1 | 1 | 1 | 1 |
