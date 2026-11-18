# Order-flow proxies on the Q14 cross-sections (`proxies_cross_section.parquet`)

Built by `research/market_evolution/e2_proxies_cross_section.py`. One row per Q14 unit: `set`, `symbol`, `period`, `status` (ok or failed, with `reason`), Q14's status label (`q14_status`), the Q14 metrics (`q14_gbm_all`, `q14_linear`, `q14_persistence`, `q14_majority`, `q14_lift`, `q14_log10_events`, `q14_n_events`, from `results/q14_survivorship.json`), the lifecycle status of the life trading in that month (`lifecycle_*`, from `contract_lifecycle.csv`), and every proxy of `contract_month_proxies` (definitions in `microstructure.evolution.proxies.PROXY_DOCS`) plus `n_raw`. The near-circular proxies `sign_repeat_rate`, `sign_acf_lag1` are kept under those names; they are nearly the outcome and are descriptive only.

## Coverage

| set | units | ok | failed | local Q9 parquet | downloaded |
|---|---|---|---|---|---|
| cross_2023 | 181 | 181 | 0 | 10 | 171 |
| cross_2026 | 251 | 251 | 0 | 10 | 241 |

By Q14 status label:

| set | q14_status | ok | not ok |
|---|---|---|---|
| cross_2023 | delisted | 33 | 0 |
| cross_2023 | merged | 2 | 0 |
| cross_2023 | renamed | 10 | 0 |
| cross_2023 | survivor | 133 | 0 |
| cross_2023 | survivor_gap | 3 | 0 |
| cross_2026 | new_listing | 113 | 0 |
| cross_2026 | survivor | 135 | 0 |
| cross_2026 | survivor_gap | 3 | 0 |

### Failures

None.

### Excluded (Q14 labels them stock, ETF or commodity; not measured)

37 cross_2026 units: EWZUSDT (ETF (Brazil); Q14 skipped), COSTUSDT (stock (Costco); Q14 skipped), UBERUSDT (stock (Uber); Q14 skipped), SONYUSDT (stock (Sony); Q14 skipped), IWMUSDT (ETF (Russell 2000); Q14 skipped), URNMUSDT (ETF (uranium miners); Q14 skipped), VUSDT (stock (Visa); Q14 skipped), CIENUSDT (stock (Ciena); Q14 skipped), BRKBUSDT (stock (Berkshire Hathaway B); Q14 skipped), HPEUSDT (stock (Hewlett Packard Enterprise); Q14 ok), JPMUSDT (stock (JPMorgan Chase); Q14 skipped), FLNCUSDT (stock (Fluence Energy); Q14 ok), ALABUSDT (stock (Astera Labs); Q14 ok), ASMLUSDT (stock (ASML); Q14 ok), CRDOUSDT (stock (Credo Technology); Q14 ok), SQQQUSDT (ETF (inverse Nasdaq-100); Q14 ok), ASTSUSDT (stock (AST SpaceMobile); Q14 ok), XPTUSDT (commodity (platinum); Q14 ok), CRWVUSDT (stock (CoreWeave); Q14 ok), AVGOUSDT (stock (Broadcom); Q14 ok), AMATUSDT (stock (Applied Materials); Q14 ok), QCOMUSDT (stock (Qualcomm); Q14 ok), MVLLUSDT (timing screen (US-equity trading hours); Q14 ok), GOOGLUSDT (stock (Alphabet); Q14 ok), PAXGUSDT (gold-backed token; Q14 ok), METAUSDT (stock (Meta Platforms); Q14 ok), QQQUSDT (ETF (Nasdaq-100); Q14 ok), BEUSDT (timing screen (US-equity trading hours); Q14 ok), TSLAUSDT (stock (Tesla); Q14 ok), CRCLUSDT (stock (Circle); Q14 ok), ARMUSDT (stock (Arm Holdings); Q14 ok), DRAMUSDT (timing screen (US-equity trading hours); Q14 ok), AMDUSDT (stock (AMD); Q14 ok), EWYUSDT (ETF (South Korea); Q14 ok), XAUUSDT (commodity (gold); Q14 ok), SKHYNIXUSDT (stock (SK hynix); Q14 ok), SNDKUSDT (stock (SanDisk); Q14 ok).

Q14's other non-fitted units (incomplete months in 2023-06, too-thin units) have no Q14 metrics and are outside this table, as in Q14.

## Runtime and disk

- 3 run(s), 0.52 h wall in total; per-unit time (download wait, ingest and proxies) median 2 s, max 180 s.
- Peak temporary disk (zips plus parquet under data/proxies_cs/tmp, sampled every 0.5 s): 2.57 GB (budget 3 GB).
- Ingest: `ingest_agg_trades` for CSVs up to 1.5 GB; above that, chunked parsing straight from the zip (same casts and schema as Q14's streaming ingest, which would have extracted a 4 to 5 GB CSV and broken the disk budget): AKEUSDT 2026-07, BANKUSDT 2026-07.
- Months over LEAN_ROWS raw records are measured by `month_proxies_lean` (events built one day at a time, raw reduced to the columns the proxies read; same result, checked on 1000PEPEUSDT 2023-06): AKEUSDT 2026-07 (65M records), BANKUSDT 2026-07 (93M records). Its peak memory was about 11 GB, mostly inside `relative_tick`.
- Run note: reconstructed from run.log: killed by the kernel (out of memory) on its last unit, BANKUSDT 2026-07, before the run log was written per unit; wall time is up to the last unit file plus about 60 s; tmp peak 2.57 GB as printed in run.log.

## First descriptive table: proxies against Q14 gbm_all accuracy

**Descriptive only.** Within each period, the Spearman correlation across contracts of each non-circular proxy with Q14's `gbm_all` accuracy, and the same after partialling out `log10_events` (ranks of both regressed on the rank of log10 events, residuals correlated). 95% intervals from 2000 bootstrap resamples of contracts. One cross-section per period, many proxies, no correction for multiple comparisons, no causal reading: these are leads for weeks 3 to 4. `lot` and `tick` are in coin and USDT units and are not comparable across contracts; they are shown for completeness. The run-length proxies are not in NEAR_CIRCULAR but are close to it: longer same-sign runs mean a higher sign repeat rate, so their large correlations are partly mechanical.

| proxy | 2023-06 rho | 2023-06 partial | 2026-07 rho | 2026-07 partial |
|---|---|---|---|---|
| events_per_day | -0.62 [-0.72, -0.50] | -0.00 [-0.14, +0.14] | +0.11 [-0.01, +0.24] | +0.01 [-0.12, +0.13] |
| run_mean | +0.74 [+0.64, +0.82] | +0.57 [+0.43, +0.69] | +0.60 [+0.49, +0.68] | +0.63 [+0.54, +0.72] |
| run_share_ge10 | +0.82 [+0.74, +0.88] | +0.69 [+0.58, +0.78] | +0.66 [+0.57, +0.73] | +0.68 [+0.59, +0.75] |
| run_mean_sweeps_merged | +0.75 [+0.64, +0.83] | +0.56 [+0.42, +0.70] | +0.57 [+0.47, +0.66] | +0.64 [+0.55, +0.72] |
| run_share_ge10_sweeps_merged | +0.81 [+0.72, +0.88] | +0.68 [+0.56, +0.78] | +0.62 [+0.53, +0.70] | +0.66 [+0.57, +0.74] |
| sweep_share | -0.30 [-0.43, -0.15] | +0.25 [+0.10, +0.40] | +0.16 [+0.02, +0.28] | +0.12 [-0.01, +0.25] |
| equal_size_repeat_share | +0.42 [+0.29, +0.54] | -0.05 [-0.19, +0.10] | +0.28 [+0.15, +0.40] | +0.37 [+0.25, +0.48] |
| lot | +0.01 [-0.14, +0.15] | -0.02 [-0.18, +0.14] | -0.13 [-0.25, -0.01] | -0.13 [-0.25, -0.01] |
| round_size_share | -0.13 [-0.29, +0.03] | +0.03 [-0.13, +0.17] | +0.07 [-0.05, +0.20] | +0.05 [-0.07, +0.17] |
| round10_share | -0.33 [-0.46, -0.18] | -0.21 [-0.36, -0.04] | -0.16 [-0.28, -0.03] | -0.18 [-0.31, -0.06] |
| share_gap_le_1ms | -0.50 [-0.62, -0.37] | +0.10 [-0.06, +0.25] | +0.10 [-0.03, +0.23] | +0.06 [-0.07, +0.19] |
| fano_1s | -0.65 [-0.74, -0.54] | -0.26 [-0.41, -0.11] | -0.04 [-0.18, +0.09] | -0.15 [-0.27, -0.03] |
| minute_open_ratio | +0.17 [+0.02, +0.32] | +0.06 [-0.10, +0.22] | -0.10 [-0.22, +0.01] | -0.04 [-0.17, +0.08] |
| quarter_open_ratio | +0.54 [+0.42, +0.65] | +0.12 [-0.03, +0.28] | -0.05 [-0.17, +0.08] | +0.02 [-0.11, +0.15] |
| median_notional_usd | -0.70 [-0.79, -0.59] | -0.42 [-0.56, -0.29] | -0.22 [-0.34, -0.10] | -0.40 [-0.50, -0.28] |
| share_under_1k_usd | +0.73 [+0.62, +0.81] | +0.53 [+0.39, +0.65] | +0.11 [-0.01, +0.23] | +0.21 [+0.09, +0.33] |
| tick | -0.04 [-0.19, +0.11] | -0.02 [-0.18, +0.14] | +0.04 [-0.08, +0.16] | +0.04 [-0.08, +0.16] |
| tick_changes | -0.13 [-0.23, +0.01] | -0.07 [-0.18, +0.04] | -0.08 [-0.24, +0.07] | -0.09 [-0.25, +0.07] |
| rel_tick_bps | +0.18 [+0.04, +0.33] | -0.32 [-0.48, -0.13] | -0.31 [-0.43, -0.18] | -0.29 [-0.41, -0.16] |
| unchanged_price_share | +0.25 [+0.09, +0.39] | -0.32 [-0.47, -0.16] | -0.06 [-0.19, +0.07] | -0.03 [-0.16, +0.10] |
| prints_per_event | -0.12 [-0.27, +0.03] | +0.29 [+0.12, +0.43] | +0.14 [+0.01, +0.27] | +0.11 [-0.01, +0.24] |
| fills_per_record | -0.50 [-0.60, -0.38] | -0.53 [-0.65, -0.40] | -0.18 [-0.29, -0.06] | -0.26 [-0.36, -0.14] |

n per period: 2023-06: 181, 2026-07: 251 (rows with a missing value for a proxy are dropped for that proxy).
