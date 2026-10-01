# Q5: kernel panel, critical balance across the cross-section

## Method

For each symbol in the panel I load one week of aggTrades (2023-06-01..2023-06-07, from the monthly period `2023-06`) and join each event to the bookTicker mid strictly before it (`events_with_prior_mid`). A per-symbol failure (missing parquet, no events in range, or the n/L≥100 sample-sufficiency guard in `kernel_exponent_blocked`) is logged in `failures` and does not abort the run.

**gamma_week**: the sign-ACF power-law exponent over the same week (`fit_power_law(sign_acf(signs, 1000), lo=10, hi=500)`), the Q1 statistic.
**beta (deconvolved kernel exponent)**: `kernel_exponent_blocked` recovers the bare impact kernel by solving the Toeplitz system `sign_price_cross_cov = sign_ACF ⊛ kappa`, which separates the kernel from the order-flow memory that R(ℓ) mixes in. For uncertainty I use `beta_block_sd` (block-bootstrap sd over 5 contiguous blocks), not the fit's OLS stderr, which the `propagator.py` docstring measures as understating the uncertainty by roughly 6.8x on synthetic long-memory data.
**Critical balance**: the Bouchaud et al. (2004) propagator-diffusivity relation predicts beta = (1 - gamma_week) / 2 for a linear propagator whose accumulated response grows no faster than diffusively (dm[t] = sum_n kappa[n] * signs[t-n] + noise; see the `propagator.py` module docstring). balance_delta = beta - (1-gamma_week)/2 is the signed departure per symbol.

**Judgement rule**: |balance_delta| <= 2*max(beta_block_sd, 0.04) => "consistent", else "violated". The 0.04 floor is the finite-L bias of roughly +0.03 to +0.04 in the recovered beta at L=300 that the `kernel_exponent_blocked` docstring reports (20-seed Monte Carlo on `fractional_signs(d=0.35)`). Without the floor, a low-noise symbol with a truly zero balance_delta could be flagged "violated" by that bias alone. Departures smaller than the bias cannot be distinguished from zero.

## Run summary

Requested: 16. Successful: 16. Failed: 0. Of the successful symbols: **12 consistent**, **4 violated**.

## Panel table (sorted by n_events)

| symbol | n_events | γ̂_week | β̂ | β̂ block_sd | Δ (balance) | verdict | R(1) | drop_rate |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 4,703,378 | 0.3603 | 0.2399 | 0.0601 | -0.0799 | consistent | 1.121e-01 | 0.0000% |
| ETHUSDT | 3,112,419 | 0.2244 | 0.2895 | 0.0614 | -0.0983 | consistent | 1.075e-02 | 0.0000% |
| 1000PEPEUSDT | 2,060,998 | 0.4539 | 0.1625 | 0.0416 | -0.1106 | violated | 6.908e-08 | 0.0000% |
| XRPUSDT | 1,608,574 | 0.3524 | 0.3633 | 0.0615 | +0.0395 | consistent | 9.731e-06 | 0.0000% |
| LTCUSDT | 1,351,376 | 0.4184 | 0.3363 | 0.0706 | +0.0455 | consistent | 2.099e-03 | 0.0000% |
| OPUSDT | 1,279,604 | 0.4215 | 0.1343 | 0.0655 | -0.1549 | violated | 7.643e-05 | 0.0000% |
| SOLUSDT | 1,117,502 | 0.3038 | 0.2608 | 0.0218 | -0.0873 | violated | 6.460e-04 | 0.0000% |
| INJUSDT | 1,084,554 | 0.4282 | 0.2509 | 0.0493 | -0.0350 | consistent | 5.091e-04 | 0.0000% |
| SUIUSDT | 1,045,883 | 0.4433 | 0.2100 | 0.0370 | -0.0684 | consistent | 5.983e-05 | 0.0000% |
| ARBUSDT | 911,294 | 0.3436 | 0.2315 | 0.0346 | -0.0967 | violated | 5.182e-05 | 0.0000% |
| DOGEUSDT | 874,041 | 0.2109 | 0.4802 | 0.2025 | +0.0856 | consistent | 1.476e-06 | 0.0000% |
| EDUUSDT | 754,422 | 0.4326 | 0.1697 | 0.0571 | -0.1140 | consistent | 9.244e-05 | 0.0000% |
| APTUSDT | 667,892 | 0.5123 | 0.1911 | 0.0502 | -0.0527 | consistent | 4.884e-04 | 0.0000% |
| LINKUSDT | 514,284 | 0.3999 | 0.4183 | 0.0840 | +0.1183 | consistent | 1.660e-04 | 0.0000% |
| IDUSDT | 509,325 | 0.4837 | 0.2333 | 0.0508 | -0.0249 | consistent | 4.552e-05 | 0.0000% |
| BCHUSDT | 401,825 | 0.3565 | 0.3827 | 0.0412 | +0.0609 | consistent | 3.580e-03 | 0.0000% |

## Findings

12 of 16 symbols (75%) land within the balance band and 4 do not, so critical balance holds for some but not all of the panel. Whether the split tracks activity (n_events) or other symbol characteristics is visible in the panel table. I assert no such relation beyond the table, since 16 points are too few to fit a reliable trend.

## Caveats

- **7-day window** (2023-06-01..2023-06-07): one week in one market regime. Order-flow memory statistics are regime-dependent (see Q8), so these results may not carry over to other weeks or volatility regimes.
- **L1 mids only**: the mid is the best-bid/best-ask midpoint from bookTicker. No order-book depth is used, so impact through queue depletion or hidden liquidity is not captured.
- **Linear-propagator assumption**: the deconvolved beta relies on the model dm[t] = sum_n kappa[n]*signs[t-n] + noise, in which each signed event's impact superposes additively and linearly. If real impact is nonlinear (saturating, or dependent on spread or depth), beta is an artifact of the linear model. The critical-balance relation beta = (1-gamma)/2 is also a linear/diffusive prediction (Bouchaud et al. 2004). A "violated" verdict fits both (a) nonlinear true impact and (b) a linear model whose beta-gamma relationship differs from the diffusivity constraint. This analysis cannot tell them apart.
- **0.04 bias floor**: the measured finite-L deconvolution bias at L=300 from the synthetic validation. The bias at this panel's max_lag (300) may differ.
- **beta_block_sd** uses only 5 contiguous non-overlapping blocks per symbol. With so few blocks it is a noisy uncertainty estimate and not a formal confidence interval.
