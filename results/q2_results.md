# Q2: Response function

## Method

Aggressor events for ETHUSDT come from the monthly aggTrades period `2023-06`, filtered to the timestamp span of the daily bookTicker periods 2023-06-01, 2023-06-02, 2023-06-03, 2023-06-04, 2023-06-05, 2023-06-06, 2023-06-07, 2023-06-08, 2023-06-09, 2023-06-10, 2023-06-11, 2023-06-12, 2023-06-13, 2023-06-14. Each event is joined to the mid price prevailing strictly before its timestamp (`events_with_prior_mid`, ms resolution). I compute the average response R(ℓ) = E[sign_t * (m_{t+ℓ} - m_t)] with `response_function` out to `max_lag` events, then fit two decay shapes over ℓ ∈ [10, 200]: a power law R(ℓ) ~ ℓ^(-γ) (OLS on log R vs log ℓ) and an exponential R(ℓ) ~ A·exp(-λℓ) (OLS on log R vs ℓ). Both use positive R values only. The shape with the lower log-scale residual sum of squares (RSS) is the better fit.

Events after joining to prior mid: 6,396,387 (dropped 0, 0.0000%).

## Results

Both fitted parameters are negative: R(ℓ) grows with lag over the fit window instead of decaying. A negative γ̂ means R(ℓ) ~ ℓ^{+0.0831} and a negative λ̂ means R(ℓ) ~ exp(+0.0009·ℓ). Read the sign before the magnitude. Growth is the expected shape under long-memory order flow (R ≈ G + Σ G·C, see Caveats).

| quantity | value |
|---|---|
| R(1) | 0.010402 |
| R(500) | 0.056107 |
| R(500)/R(1) | 5.3939 |
| power-law exponent γ̂ (R ~ ℓ^-γ̂) | -0.0831 |
| power-law OLS stderr | 0.0034 |
| exponential rate λ̂ (R ~ exp(-λ̂ℓ)) | -0.0009 |
| exponential OLS stderr | 0.0001 |

## Fit comparison (log-scale RSS, lags 10-200)

| shape | log-scale RSS |
|---|---|
| power law | 0.2161 |
| exponential | 0.4718 |

**Verdict:** the power-law form has the lower log-scale RSS over lags 10-200 and is the better fit for ETHUSDT's response function in this sample, which is growing over lags 1-200.

## Benchmark vs. literature

Bouchaud et al. (2004) report that the bare impact kernel G(l) decays slowly, roughly as a power law, over hundreds to thousands of trades. Price impact is therefore not an exponentially forgotten single-event shock; it reflects long-range order-flow correlation. The measured response R(l) is a different object: it mixes G with order-flow memory C. Bouchaud's equity data shows R(l) rising to a maximum around 10^2-10^3 trades before any slow decline, the same rise measured here.

## Caveats

- The OLS standard errors on γ̂ and λ̂ assume i.i.d. residuals. R(ℓ) at nearby lags is autocorrelated (through the impact kernel and order-flow memory), so they understate the uncertainty.
- Order flow is not i.i.d. (Q1 finds long-memory signs), so R(ℓ) mixes the bare impact kernel with sign autocorrelation. It is not a clean kernel estimate.
- One 14-day window (2023-06-01..2023-06-14) and one symbol (ETHUSDT); the fitted shape and rate may not carry over to other periods, regimes, or symbols.
- The RSS comparison is on the log scale over a fixed window. A different window or a linear-scale comparison could favor the other shape, since the two often diverge only at large lag.
- A growing R(ℓ) over lags 1-200 is the expected shape under long-memory order flow and is consistent with Bouchaud (2004). The measured response mixes the decaying bare kernel G with the sign autocorrelation C: R(ℓ) ≈ G(ℓ) + Σ_{n<ℓ} G(ℓ-n)·C(n). With Q1's sign-ACF exponent γ≈0.24 for ETH, the accumulation term Σ G·C dominates G, so R keeps climbing well past where G alone would have decayed. Bouchaud's equity response functions show the same rise-then-slow-decline shape, peaking around 10^2-10^3 trades. R(500)/R(1) = 5.39x here. A toy transient-impact calculation with γ≈0.24 and kernel exponent β=(1-γ)/2≈0.38 predicts R(500)/R(1) in roughly 3.5-6.9x (for lag-1 sign autocorrelation in 0.2-0.4), and the measured 5.39x falls inside it. What decays in the literature is the kernel G(ℓ), not R(ℓ). This analysis measures R only; separating G from C needs propagator deconvolution, which I did not do.
- R(ℓ) plateaus around ℓ≈300-500 (see the response array in `q2_results.json`), outside the fitted window [10, 200]. The fits describe only the rising portion and say nothing about behavior at or past the plateau.
