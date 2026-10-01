# Q0: Aggregation effect on order-flow memory

## Summary

If the pipeline skips aggressor aggregation, it can look like a successful replication. In every symbol-month tested, raw-print gamma is inflated by roughly +0.29 to +0.50 relative to the aggregated gamma from the same data. That puts it inside the equities/futures range (0.3-0.7, Bouchaud et al. 2004) in half the cells below and past it in the other half, while the aggregated gamma moves lower or further out of range in every cell. A check that gamma falls in the literature range cannot tell the two pipelines apart: both can pass, on different numbers, and the broken one more often looks like a clean replication.

## Method

For each (symbol, period) cell I load the same raw `aggTrades` parquet two ways. Raw: `is_buyer_maker` is read in on-disk (`agg_trade_id`) order and signed (+1 buyer-taker, -1 seller-taker), with no merging of same-(timestamp, side) prints, so one sign per print. Aggregated: `load_events` merges all same-millisecond, same-side prints into one aggressor decision via `to_aggressor_events` before signing. Both series get the same FFT sign ACF (`sign_acf`) and log-log power-law fit (`fit_power_law`, lags [10, 500]) used in Q1, so the gammas are comparable.

## Results

| symbol | period | raw n | raw acf(1) | raw γ̂ | agg n | agg acf(1) | agg γ̂ | prints/event | γ̂ inflation |
|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 2023-06 | 39,024,962 | 0.3413 | 0.9634 | 21,816,890 | -0.1676 | 0.4617 | 1.7888 | +0.5017 |
| BTCUSDT | 2023-07 | 24,963,535 | 0.2786 | 0.7871 | 16,229,472 | -0.1032 | 0.3260 | 1.5382 | +0.4611 |
| ETHUSDT | 2023-06 | 24,368,924 | 0.4290 | 0.7077 | 14,239,099 | 0.0284 | 0.2858 | 1.7114 | +0.4219 |
| ETHUSDT | 2023-07 | 16,789,675 | 0.3737 | 0.4983 | 11,534,367 | 0.0917 | 0.2055 | 1.4556 | +0.2928 |

## Literature-range check, both pipelines

Equities/futures sign-ACF exponent range (Bouchaud et al. 2004): γ ≈ 0.3–0.7.

| symbol | period | raw γ̂ | raw in range? | agg γ̂ | agg in range? |
|---|---|---|---|---|---|
| BTCUSDT | 2023-06 | 0.9634 | no | 0.4617 | yes |
| BTCUSDT | 2023-07 | 0.7871 | no | 0.3260 | yes |
| ETHUSDT | 2023-06 | 0.7077 | no | 0.2858 | no |
| ETHUSDT | 2023-07 | 0.4983 | yes | 0.2055 | no |

The direction is the same in every cell. Raw-print gamma exceeds aggregated gamma by roughly +0.29 to +0.50, and raw lag-1 ACF is strongly positive (about 0.28-0.43) because the matching engine walks the book within a single aggressor decision. Whether the raw γ̂ lands inside [0.3, 0.7] or overshoots 0.7 varies by symbol-month, so the table is the reference.

BTC shows a second effect: aggregation flips its lag-1 ACF from positive to negative, while ETH's aggregated lag-1 ACF stays small and positive.

## Caveats

- The aggregated arm is the same measurement Q1 uses. Q0 keeps the raw-vs-aggregated contrast as a re-runnable artifact.
- Gamma and its OLS stderr use the same fit window and normalization as Q1. The stderr assumes i.i.d. residuals and understates the uncertainty for autocorrelated ACF points.
- BTC's raw γ̂ can exceed 0.7, so the fragmentation artifact can overshoot the equity band entirely.
- The sample is the (symbols, periods) listed in the table.
