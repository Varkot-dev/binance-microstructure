# Q3: OFI linearity

## Method

For ETHUSDT, I load daily bookTicker L1 snapshots and sort by timestamp. Per-update order-flow imbalance (OFI) follows Cont, Kukanov & Stoikov (2014) (`ofi_events`): each consecutive pair of L1 updates contributes a signed quantity from bid/ask price improvements and same-price size changes, stamped with the later update's time. Updates are bucketed into fixed `10s` bars via `pl.group_by_dynamic`. Within each bar, OFI is summed, delta_mid is the last mid minus the mid before the bar's first update, and mean depth is the bar average of (bid_qty + ask_qty)/2. Bars with fewer than 2 updates are dropped. The (summed OFI, delta_mid) pairs are regressed through the origin (`ols_through_origin`): delta_mid = beta * OFI_sum.

**Depth-scaling check**: bars are split into 5 depth quintiles by mean depth, a through-origin slope is fit per quintile, and log|slope| is regressed (OLS, not through origin) on log(mean depth) across quintiles. Cont's theory (slope ~ 1/depth) predicts a log-log slope near -1. Quintiles with a zero or negative slope are excluded from the log-log fit and listed below.

Periods analyzed: 2023-06-01, 2023-06-02, 2023-06-03, 2023-06-04, 2023-06-05, 2023-06-06, 2023-06-07, 2023-06-08, 2023-06-09, 2023-06-10, 2023-06-11, 2023-06-12, 2023-06-13, 2023-06-14.

## Results

| metric | value |
|---|---|
| slope (β̂) | 0.000169 |
| stderr | 0.000001 |
| R² | 0.4020 |
| n_windows | 120,960 |

### Depth-scaling check

| quintile | mean depth | slope | n_bars |
|---|---|---|---|
| 0 | 53.3304 | 0.000303 | 24,192 |
| 1 | 71.5005 | 0.000183 | 24,192 |
| 2 | 84.2402 | 0.000153 | 24,192 |
| 3 | 100.0455 | 0.000137 | 24,192 |
| 4 | 158.1181 | 0.000125 | 24,192 |

log|slope| vs log(mean depth) regression exponent: **-0.7738** (Cont theory predicts ≈ -1).

## Benchmark vs. literature

Cont, Kukanov & Stoikov (2014) report R² ≈ 65%–70% for OFI-vs-price-change regressions on equities. Silantyev (2019) found trade-flow imbalance (net signed trade volume) a stronger price-change predictor than book-based OFI on BitMEX.

| our R² | Cont equities R² | benchmark comparison |
|---|---|---|
| 0.4020 | 0.65–0.70 | below the Cont equities range |

## Caveats

- OFI uses L1 (best bid/ask) snapshots only. Deeper levels are not observed, so OFI understates order-flow pressure from them.
- The `ols_through_origin` stderr assumes i.i.d. residuals. Bar-level delta_mid and OFI sums are likely autocorrelated across adjacent bars, so it understates the uncertainty.
- The depth-scaling check regresses on 5 quintiles from a 14-day sample. Its exponent has wide, unreported uncertainty and is suggestive only.
- One symbol over 14 days of one market regime; results may not carry over to other symbols, venues, or volatility regimes.
