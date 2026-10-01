# Q1: Order-flow memory

## Method

For each symbol, Binance aggTrades prints for the given periods are collapsed into aggressor-level events (same-millisecond, same-side prints merged into one taker decision, see `to_aggressor_events`). The result is a ±1 sign series: +1 for a taker buy, -1 for a taker sell. I compute the sample ACF of the signs by FFT (Wiener-Khinchin) out to `max_lag` events, then fit ACF(lag) ~ lag^(-γ) by OLS on log(ACF) vs log(lag) over [10, max_lag // 2], skipping non-positive ACF values. γ̂ is the estimate of the order-flow memory decay rate.

Periods analyzed: 2023-06, 2023-07.

## Results

| symbol | n_events | γ̂ | OLS stderr |
|---|---|---|---|
| BTCUSDT | 38,046,362 | 0.3803 | 0.0010 |
| ETHUSDT | 25,773,466 | 0.2380 | 0.0015 |

## Benchmark vs. literature

Literature range (equities/futures sign-ACF exponent, Bouchaud et al. 2004): γ ≈ 0.3–0.7, with persistence horizons of thousands of trades.

| symbol | γ̂ | literature range | in range? |
|---|---|---|---|
| BTCUSDT | 0.3803 | 0.3–0.7 | yes |
| ETHUSDT | 0.2380 | 0.3–0.7 | no |

Landing inside or outside this range is a result, not a pass/fail test.

## Caveats

- The OLS standard error on γ̂ assumes i.i.d. errors in the log-log regression. ACF values at nearby lags are autocorrelated, so it **understates** the uncertainty in γ̂.
- Same-millisecond, same-side prints are merged before signing, so the event count is below the raw aggTrades row count and lag-1 structure reflects aggressor decisions, not raw prints.
- The sample is 2 months of one market regime per symbol, so γ̂ may not carry over to other periods, volatility regimes, or symbols.
