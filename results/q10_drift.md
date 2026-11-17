# Q10: does a 2023 sign model go stale, and why

## Question

Q8 found that a cross-sectional sign-flip law present in June 2023 had faded by July 2026. Here I ask the same of a predictive model: if the next-trade-sign ladder is fitted on 2023-06 and never updated, how much worse is it on later months than a ladder refitted in that month, and is the loss because the inputs moved (covariate shift) or because the relationship between inputs and the next sign moved (concept shift)?

## Method

1. **Transfer matrix.** For each symbol and every ordered pair of periods, the ladder fitted on the train days of period i is scored on the held-out test block (the last days, after a one-day embargo) of period j. The diagonal is therefore a genuine out-of-sample number and every cell in a column uses identical test rows. Rungs: persistence, linear, logit_all, gbm_all. Events sharing a millisecond with the previous event are never scored.
2. **Decomposition.** With M the matrix and s = 2023-06: raw drop = M[s,s] - M[s,j]; staleness gap G_j = M[j,j] - M[s,j] (what retraining recovers); predictability change D_j = M[j,j] - M[s,s] (the period itself got easier or harder). Raw drop = G_j - D_j. For log loss all three are negated so that positive G still means retraining helps.
3. **Intervals.** 95% percentile intervals from 2000 resamples of whole UTC test days, one draw of days per period shared by all symbols. G_j is **paired**: both terms are means over the same test rows of period j and see the same resampled days. D_j and the raw drop are **differences of independent blocks**: the days of period j and of 2023-06 are resampled independently. "G minus yardstick G" is also a difference of independent blocks. Headline numbers are the median across the 10 symbols, with the symbol panel held fixed.
4. **Skill over the period's own baseline.** The accuracy of repeating the last sign moves between years, so I also report accuracy minus the accuracy of the period's own persistence rung (the best one-lag rule, fitted on that period's train days).
5. **Yardstick.** 2023-06 to 2023-07 is ordinary one-month drift. Multi-year gaps are judged against it.
6. **Covariate shift size.** A small LightGBM domain classifier is trained to tell the feature rows of two periods apart (equal-size random samples from each period's train days) and evaluated on samples from each period's test days. AUC 0.5 means indistinguishable. Per feature I report the standardized mean difference and the two-sample KS distance.
7. **Attribution.** The classifier's probability gives a density ratio w(x) = (n_src/n_tgt) pi/(1-pi), clipped at its 99% quantile. For the 2023-06 model's log loss: covariate part = E_src[w loss] - E_src[loss]; concept residual = E_tgt[loss] - E_src[w loss]. The split is flagged unreliable when the effective sample size of the weights falls below 10% of the rows (the reweighted mean then rests on less than one test day's worth of data).
8. **Per-period refits.** The logistic rung is refitted in each period on features standardized within that symbol and period, and the coefficients are compared. I do not compare SHAP values of the fixed 2023 model across periods: the model function is unchanged, so such a comparison can only show that inputs moved.

## Run summary

Periods: 2023-06, 2023-07, 2024-07, 2025-07, 2026-07. Symbols with a complete matrix: 10 (BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, BNBUSDT, LINKUSDT, LTCUSDT, AVAXUSDT, 1000PEPEUSDT).

## Results

### Transfer matrix, gbm_all accuracy (median across symbols)

| trained on \ tested on | 2023-06 | 2023-07 | 2024-07 | 2025-07 | 2026-07 |
|---|---|---|---|---|---|
| 2023-06 | 60.01% | 60.89% | 60.53% | 60.03% | 60.36% |
| 2023-07 | 60.49% | 61.04% | 60.73% | 60.91% | 62.11% |
| 2024-07 | 59.32% | 60.38% | 63.66% | 65.96% | 62.80% |
| 2025-07 | 58.68% | 58.70% | 63.42% | 66.16% | 62.74% |
| 2026-07 | 59.02% | 58.21% | 62.17% | 63.78% | 63.90% |

### Transfer matrix, gbm_all log loss in bits (median across symbols)

| trained on \ tested on | 2023-06 | 2023-07 | 2024-07 | 2025-07 | 2026-07 |
|---|---|---|---|---|---|
| 2023-06 | 0.9547 | 0.9452 | 0.9543 | 0.9582 | 0.9513 |
| 2023-07 | 0.9525 | 0.9424 | 0.9508 | 0.9542 | 0.9365 |
| 2024-07 | 0.9664 | 0.9590 | 0.9195 | 0.8986 | 0.9339 |
| 2025-07 | 0.9798 | 0.9723 | 0.9270 | 0.8933 | 0.9372 |
| 2026-07 | 0.9696 | 0.9726 | 0.9397 | 0.9286 | 0.9134 |

### Decomposition, gbm_all accuracy (percentage points)

| target | raw drop | staleness gap G (paired) | predictability change D (independent blocks) | G minus yardstick G | symbols with G above yardstick |
|---|---|---|---|---|---|
| 2023-07 | -0.28 pp [-0.95, +0.22] | +0.19 pp [+0.06, +0.26] | +0.90 pp [-0.06, +1.29] | yardstick | n/a |
| 2024-07 | +1.55 pp [+0.00, +1.79] | +2.42 pp [+2.18, +2.64] | +2.49 pp [+2.13, +3.62] | +2.09 pp [+1.86, +2.37] | 10 |
| 2025-07 | +1.15 pp [+0.48, +1.71] | +4.63 pp [+4.06, +5.18] | +4.42 pp [+3.76, +5.60] | +4.21 pp [+3.59, +4.84] | 10 |
| 2026-07 | -0.08 pp [-1.20, +0.39] | +1.63 pp [+1.42, +1.85] | +2.23 pp [+1.36, +3.21] | +1.03 pp [+0.83, +1.29] | 10 |

### Decomposition, logit_all accuracy (percentage points)

| target | raw drop | staleness gap G (paired) | predictability change D (independent blocks) | G minus yardstick G | symbols with G above yardstick |
|---|---|---|---|---|---|
| 2023-07 | -0.84 pp [-1.47, -0.15] | +0.18 pp [+0.12, +0.32] | +0.85 pp [+0.28, +1.83] | yardstick | n/a |
| 2024-07 | -0.03 pp [-0.98, +0.41] | +2.24 pp [+1.95, +2.58] | +2.93 pp [+2.52, +4.24] | +2.11 pp [+1.81, +2.46] | 9 |
| 2025-07 | -0.77 pp [-1.22, -0.20] | +4.50 pp [+3.71, +5.12] | +4.75 pp [+3.88, +5.87] | +3.85 pp [+3.09, +4.57] | 10 |
| 2026-07 | -0.50 pp [-2.15, +0.22] | +1.86 pp [+1.65, +2.14] | +2.88 pp [+2.05, +3.94] | +1.66 pp [+1.30, +2.00] | 10 |

### Decomposition, linear accuracy (percentage points)

| target | raw drop | staleness gap G (paired) | predictability change D (independent blocks) | G minus yardstick G | symbols with G above yardstick |
|---|---|---|---|---|---|
| 2023-07 | -1.06 pp [-1.83, -0.51] | +0.17 pp [+0.13, +0.22] | +1.30 pp [+0.69, +2.26] | yardstick | n/a |
| 2024-07 | -2.41 pp [-2.98, -1.68] | +1.99 pp [+1.59, +2.27] | +3.79 pp [+3.30, +4.83] | +1.62 pp [+1.28, +1.81] | 10 |
| 2025-07 | -1.12 pp [-1.47, -0.61] | +3.42 pp [+2.94, +3.88] | +3.88 pp [+3.02, +5.22] | +2.58 pp [+2.02, +3.17] | 10 |
| 2026-07 | -1.83 pp [-3.17, -1.13] | +1.30 pp [+1.13, +1.54] | +3.71 pp [+2.77, +4.80] | +1.65 pp [+1.12, +1.80] | 9 |

### Decomposition, gbm_all log loss

| target | raw drop | staleness gap G (paired) | predictability change D (independent blocks) | G minus yardstick G | symbols with G above yardstick |
|---|---|---|---|---|---|
| 2023-07 | -0.0045 bits [-0.0095, -0.0001] | +0.0017 bits [+0.0013, +0.0028] | +0.0058 bits [+0.0012, +0.0118] | yardstick | n/a |
| 2024-07 | +0.0122 bits [+0.0004, +0.0170] | +0.0293 bits [+0.0272, +0.0315] | +0.0294 bits [+0.0250, +0.0355] | +0.0233 bits [+0.0218, +0.0266] | 10 |
| 2025-07 | +0.0079 bits [+0.0006, +0.0107] | +0.0483 bits [+0.0425, +0.0554] | +0.0454 bits [+0.0391, +0.0537] | +0.0467 bits [+0.0398, +0.0537] | 10 |
| 2026-07 | -0.0061 bits [-0.0143, +0.0009] | +0.0217 bits [+0.0182, +0.0230] | +0.0245 bits [+0.0190, +0.0331] | +0.0191 bits [+0.0149, +0.0204] | 10 |

### Skill over each period's own one-lag baseline (accuracy points, gbm_all)

| target | repeat-last accuracy in target | stale model skill | fresh model skill | fresh skill in 2023-06 | change in fresh skill |
|---|---|---|---|---|---|
| 2023-07 | 52.48% | +5.67 pp [+4.86, +6.04] | +5.82 pp [+5.11, +6.30] | +7.28 pp | -0.30 pp [-1.89, +0.55] |
| 2024-07 | 58.29% | +1.89 pp [+1.29, +2.63] | +4.31 pp [+3.90, +4.83] | +7.28 pp | -1.83 pp [-3.18, -0.91] |
| 2025-07 | 59.44% | +1.03 pp [+0.13, +2.09] | +4.99 pp [+4.41, +5.61] | +7.28 pp | -0.46 pp [-1.20, +0.48] |
| 2026-07 | 55.78% | +6.21 pp [+4.96, +7.11] | +7.57 pp [+6.51, +8.53] | +7.28 pp | +0.89 pp [-0.56, +1.74] |

Repeat-last accuracy in 2023-06: 52.13%.

### Staleness gap by symbol, gbm_all accuracy (percentage points)

| symbol | 2023-07 | 2024-07 | 2025-07 | 2026-07 |
|---|---|---|---|---|
| BTCUSDT | +0.11 [+0.05, +0.17] | +0.51 [+0.37, +0.64] | +0.34 [+0.30, +0.39] | +0.52 [+0.41, +0.61] |
| ETHUSDT | +0.05 [-0.00, +0.10] | +0.71 [+0.57, +0.84] | +0.78 [+0.60, +0.90] | +0.51 [+0.36, +0.63] |
| SOLUSDT | -0.03 [-0.19, +0.12] | +2.76 [+2.51, +2.96] | +2.59 [+2.10, +3.13] | +4.21 [+3.67, +4.62] |
| XRPUSDT | -0.24 [-0.54, +0.00] | +1.40 [+1.15, +1.68] | +12.38 [+10.46, +13.91] | +2.15 [+1.76, +2.66] |
| DOGEUSDT | +0.87 [+0.64, +1.14] | +3.31 [+2.99, +3.63] | +10.75 [+9.70, +11.65] | +1.63 [+1.38, +1.92] |
| BNBUSDT | +0.33 [+0.24, +0.41] | +2.08 [+1.76, +2.40] | +2.33 [+1.85, +2.76] | +1.63 [+1.27, +1.98] |
| LINKUSDT | +0.87 [+0.45, +1.24] | +4.99 [+4.62, +5.25] | +6.67 [+5.84, +7.34] | +1.30 [+0.90, +1.64] |
| LTCUSDT | +0.42 [+0.22, +0.64] | +5.03 [+4.49, +5.60] | +8.28 [+6.79, +9.75] | +2.36 [+2.11, +2.62] |
| AVAXUSDT | -0.01 [-0.06, +0.05] | +1.29 [+1.18, +1.37] | +1.58 [+1.30, +1.89] | +0.60 [+0.48, +0.70] |
| 1000PEPEUSDT | +0.28 [+0.02, +0.54] | +8.27 [+7.53, +8.94] | +13.77 [+12.79, +14.50] | +9.18 [+8.16, +10.15] |

### Covariate shift: domain classifier AUC (0.5 = indistinguishable)

| pair | median AUC | min | max | symbols |
|---|---|---|---|---|
| 2023-06 vs 2023-07 | 0.477 | 0.385 | 0.765 | 10 |
| 2023-06 vs 2024-07 | 0.776 | 0.666 | 0.859 | 10 |
| 2023-06 vs 2025-07 | 0.821 | 0.684 | 0.905 | 10 |
| 2023-06 vs 2026-07 | 0.786 | 0.584 | 0.981 | 10 |
| 2023-07 vs 2024-07 | 0.785 | 0.750 | 0.879 | 10 |
| 2023-07 vs 2025-07 | 0.839 | 0.654 | 0.895 | 10 |
| 2023-07 vs 2026-07 | 0.820 | 0.716 | 0.978 | 10 |
| 2024-07 vs 2025-07 | 0.672 | 0.619 | 0.921 | 10 |
| 2024-07 vs 2026-07 | 0.742 | 0.654 | 0.991 | 10 |
| 2025-07 vs 2026-07 | 0.779 | 0.649 | 0.963 | 10 |

Features that moved most between 2023-06 and 2026-07 (median across symbols, ranked by KS distance):

| feature | KS distance | standardized mean difference | KS in the yardstick pair |
|---|---|---|---|
| sign_ewma1024 | 0.189 | +0.137 | 0.066 |
| sign_ewma256 | 0.160 | +0.100 | 0.053 |
| sign_ewma64 | 0.126 | +0.075 | 0.047 |
| sign_ewma16 | 0.092 | +0.053 | 0.038 |
| ret16 | 0.089 | +0.004 | 0.034 |
| ret64 | 0.086 | +0.007 | 0.026 |

### Attribution of the 2023-06 logit_all log loss change (bits)

| target | total change | covariate part (paired on source days) | concept residual (independent blocks) | symbols where concept is larger | median ESS share | symbols with reliable weights |
|---|---|---|---|---|---|---|
| 2023-07 | -0.0058 | +0.0038 bits [+0.0019, +0.0046] | -0.0129 bits [-0.0165, -0.0056] | 9 of 10 | 84% | 10 of 10 |
| 2024-07 | -0.0018 | +0.0067 bits [+0.0022, +0.0080] | -0.0112 bits [-0.0178, -0.0015] | 8 of 10 | 43% | 10 of 10 |
| 2025-07 | -0.0056 | +0.0041 bits [+0.0022, +0.0058] | -0.0026 bits [-0.0114, +0.0036] | 9 of 10 | 36% | 10 of 10 |
| 2026-07 | -0.0052 | -0.0045 bits [-0.0085, +0.0012] | -0.0068 bits [-0.0170, +0.0006] | 6 of 10 | 37% | 10 of 10 |

### Attribution of the 2023-06 gbm_all log loss change (bits)

| target | total change | covariate part (paired on source days) | concept residual (independent blocks) | symbols where concept is larger | median ESS share | symbols with reliable weights |
|---|---|---|---|---|---|---|
| 2023-07 | -0.0059 | +0.0040 bits [+0.0025, +0.0044] | -0.0092 bits [-0.0138, -0.0042] | 7 of 10 | 84% | 10 of 10 |
| 2024-07 | +0.0119 | +0.0036 bits [-0.0011, +0.0054] | -0.0011 bits [-0.0069, +0.0082] | 7 of 10 | 43% | 10 of 10 |
| 2025-07 | +0.0075 | +0.0023 bits [+0.0015, +0.0045] | +0.0104 bits [+0.0019, +0.0174] | 8 of 10 | 36% | 10 of 10 |
| 2026-07 | -0.0059 | -0.0090 bits [-0.0101, -0.0045] | -0.0000 bits [-0.0068, +0.0087] | 6 of 10 | 37% | 10 of 10 |

### Per-period logistic refits: standardized coefficients (median across symbols)

| feature | 2023-06 | 2023-07 | 2024-07 | 2025-07 | 2026-07 | verdict for 2026-07 |
|---|---|---|---|---|---|---|
| sign_lag1 | -0.429 | -0.438 | +0.013 | -0.059 | -0.103 | within the cross-symbol spread |
| run_length | +0.238 | +0.235 | +0.176 | +0.092 | +0.161 | within the cross-symbol spread |
| signed_rel_log_qty | +0.197 | +0.234 | +0.171 | +0.263 | +0.174 | within the cross-symbol spread |
| sign_ewma16 | +0.155 | +0.163 | +0.051 | +0.093 | +0.234 | within the cross-symbol spread |
| sign_ewma4 | +0.154 | +0.102 | +0.119 | +0.130 | +0.141 | within the cross-symbol spread |
| ret16 | -0.062 | -0.076 | -0.014 | -0.033 | -0.030 | within the cross-symbol spread |
| tick_dir | -0.053 | -0.035 | +0.118 | +0.217 | +0.040 | sign changed (6 of 10 symbols) |
| sign_ewma64 | +0.051 | +0.047 | +0.090 | +0.081 | +0.112 | moved +0.049, more than the cross-symbol SD 0.045 |

Of the 8 largest coefficients in 2023-06, 1 changed sign by 2026-07 (tick_dir) and 1 moved by more than the cross-symbol spread (sign_ewma64). Over the one-month yardstick 0 moved by that much.

### Share of events tied with the previous millisecond

| period | median | min | max |
|---|---|---|---|
| 2023-06 | 0.8% | 0.4% | 2.2% |
| 2023-07 | 0.8% | 0.5% | 2.2% |
| 2024-07 | 0.6% | 0.4% | 2.2% |
| 2025-07 | 0.7% | 0.2% | 1.4% |
| 2026-07 | 0.5% | 0.3% | 1.4% |

## Verdict

One month on (2023-06 model scored on 2023-07), the staleness gap of gbm_all is +0.19 pp [+0.06, +0.26] of accuracy (median of 10 symbols, 95% day-block interval), which is positive. This is the ordinary one-month drift yardstick. Yes. By 2026-07 the 2023-06 model is stale, and its staleness gap is larger than the one-month yardstick: G = +1.63 pp [+1.42, +1.85] against +0.19 pp, a difference of +1.03 pp [+0.83, +1.29] (8.5 times the yardstick). The gap is above the yardstick on 10 of 10 symbols and its own interval excludes zero from above on 10 of 10. Separately from staleness, the market itself became more predictable for a freshly trained model: D = +2.23 pp [+1.36, +3.21]. The raw drop of the old model, -0.08 pp, is G minus D, so retraining would recover +1.63 pp of it. Measured against each period's own one-lag baseline, fresh-model skill changed by +0.89 pp [-0.56, +1.74]. In log loss the staleness gap is +0.0217 bits [+0.0182, +0.0230]. Attribution of the 2023-06 model's log loss change to 2026-07 (-0.0059 bits; negative means the old model's loss fell): covariate part -0.0090 bits [-0.0101, -0.0045], concept residual -0.0000 bits [-0.0068, +0.0087]. No side dominates: by the cross-symbol median the larger side is the covariate part (the inputs moved), but the concept residual is the larger one on 6 of 10 symbols. Effective sample size is above the 10% threshold on 10 of 10 symbols (median share 37%). The weights are healthy on most symbols.

## Caveats

- **Snapshots, not a path.** Five snapshot months cannot distinguish gradual from abrupt change between them, cannot give a retraining cadence finer than a year, and cannot detect regimes that came and went between snapshots.
- **Survivors.** The 10 symbols are ones present in all the months studied. Symbols delisted or listed in between are absent, so this is drift within a surviving panel, not drift of the market's composition.
- **Timestamp resolution.** The raw dumps changed timestamp resolution across years. The ingest normalizes everything to milliseconds, but the share of events tied with the previous millisecond (table above) differs by period. Tied events are excluded from scoring, so a different tie share means a different scored population, and the `same_ts` feature moves with it.
- **Few day blocks.** Each test block is about a week, so the day-block intervals rest on seven or eight resampling units and are approximate. They hold the symbol panel fixed and say nothing about other symbols.
- **One source month.** 2023-06 followed regulatory actions against the exchange and may itself be an unusual regime; '2023 versus later' is not 'normal versus changed'.
- **Attribution limits.** The reweighting only speaks for inputs the source period covers, clipping the weights biases the covariate part toward zero, and 'concept' is relative to this feature set: a change in an omitted variable (tick size in basis points, participant mix) lands in the residual. In a sequence model the features are past signs, so a change in the sign dynamics also moves the feature distribution; the two kinds of shift are not independent causes.
- **Within-month drift.** The domain classifier and its weights are fitted on train days and the losses are measured on test days. Drift between the first three weeks and the last week of a month is therefore mixed into both parts; the one-month yardstick row shows how large that can be when little else changed.
- **Coefficients.** The sign-history features are strongly collinear, so single coefficients can trade off against each other without the fitted function changing much. The coefficient table is a description, not a test.
- **No trading claim.** Accuracy on the next aggressor sign is not profitability; no fees or execution are modelled.
