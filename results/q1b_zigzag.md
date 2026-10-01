# Q1b: short-lag ACF zigzag and the tie-break

## Method

Aggressor events for BTCUSDT 2023-06 come from `load_events`, sorted by `(ts, sign)`: within a millisecond, sells precede buys. I compare three sign series on the same FFT sign ACF (`sign_acf`) at lags 1-10:

- **A (baseline):** the series as `load_events` produces it, with the deterministic `(ts, sign)` tie-break.
- **B (randomized tie-break):** same-timestamp adjacent pairs (after aggregation always one sell and one buy, since `to_aggressor_events` never emits two same-(ts, side) rows) are swapped with p=0.5 using a fixed-seed RNG (`numpy.random.default_rng(0)`). Every other event is untouched.
- **C (netted):** each same-timestamp group of opposite-signed events collapses into one event with sign = sign(sum(sign * qty)). Groups whose signed notional nets to exactly zero are dropped (undefined sign).

The zigzag amplitude is `mean(ACF at lags 2,4,6,8,10) - mean(ACF at lags 1,3,5,7,9)`. It is large and positive when even lags run higher than odd lags, the pattern visible in Q1's log-log ACF plot at short lags.

## Results

n_events = 21,816,890.

Fraction of consecutive event pairs sharing a millisecond timestamp: 1.1987% (261,515 same-ts pairs). Among those, 100.00% are opposite-signed by construction: `to_aggressor_events` produces at most one buy and one sell per millisecond, so the maximum same-ts group size is 2. Variant B is a random 50/50 swap of 131,032 of those pairs, not a general permutation.

| lag | A: baseline | B: randomized tie-break | C: netted |
|---|---|---|---|
| 1 | -0.167615 | -0.166886 | -0.153383 |
| 2 | 0.268342 | 0.267467 | 0.271401 |
| 3 | 0.019937 | 0.020082 | 0.027652 |
| 4 | 0.153220 | 0.153224 | 0.151183 |
| 5 | 0.045971 | 0.045934 | 0.054323 |
| 6 | 0.109750 | 0.109815 | 0.107009 |
| 7 | 0.051406 | 0.051379 | 0.058521 |
| 8 | 0.087315 | 0.087359 | 0.085164 |
| 9 | 0.051650 | 0.051615 | 0.057827 |
| 10 | 0.073590 | 0.073620 | 0.071857 |

| variant | zigzag amplitude | relative change vs. A |
|---|---|---|
| A: baseline | 0.138174 | -- |
| B: randomized tie-break | 0.137872 | 0.22% |
| C: netted (21,550,823 events, 4,552 zero-net groups dropped) | 0.128335 | 7.12% |

## Verdict

**The zigzag survives both perturbations, so it is not a tie-break artifact.** I count a variant as surviving if its amplitude keeps the baseline's sign and moves by at most 25%. The amplitude barely moves under the randomized tie-break (0.138174 -> 0.137872, a 0.22% change) and stays large under netting (0.128335, a 7.12% change). Only 1.20% of consecutive event pairs share a timestamp, so the tie-break touches too few adjacent pairs to produce an alternation this size. The most likely explanation is market structure, such as bid-ask bounce or interleaved liquidity-taking reversals.

This suggests Q1's gamma fits are unaffected, but I did not measure that. Q1's power-law fit window starts at lag 10 (`fit_power_law(..., lo=10, ...)`), and the zigzag here is measured over lags 1-10, at or before the start of the window. Whether the alternation persists past lag 10 is not established, because I only computed lags 1-10. Settling it needs the same three-way comparison at lags 11+.

## Caveats

- Single symbol-month (BTCUSDT 2023-06), not repeated on other symbols or periods.
- Among same-ts adjacent pairs, 100% are opposite-signed by construction (post-aggregation each timestamp holds at most one buy and one sell), so variant B reduces to random pair swaps. This is equivalent to a permutation here since groups never exceed size 2.
- `sign_acf` uses the unbiased normalization (divide by n-lag). At lags <=10 with n in the tens of millions the difference is negligible.
- Netting (C) dampens the zigzag amplitude relative to baseline, so same-ts buy/sell pairs contribute some of it. The dominant odd/even pattern (negative ACF(1), large positive ACF(2)) persists through both perturbations.
- Timestamps have millisecond resolution and finer ordering is unrecoverable. "Real structure" means real at the millisecond-aggregated event level, not within a millisecond.
- Nothing past lag 10 is computed, so this cannot confirm or rule out zigzag-driven distortion of Q1's [10, 500] fit window (see Verdict).
