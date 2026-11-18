# E4: panel regressions and the composition split (Part A, weeks 3 to 4)

Script: `../e4_panel_regressions.py` (tests: `tests/research/test_e4_panel.py`). Figure: `e4_panel_regressions.png`. Inputs: `proxies_cross_section.parquet` (Q14 cross-sections, 181 contracts in 2023-06 and 251 in 2026-07) and `../e1_proxies.json` (the 10 Q10 coins x 5 months). Outcome: fresh-model accuracy (`gbm_all`, fitted within each contract-month, Q9 protocol), in percent; robustness outcome: lift over the majority-class rule (Q14 `lift`, cross-sections only, because Q10 did not store the majority rule for 2023-07 to 2025-07). The 10 coins' 2023-06 and 2026-07 rows are identical in both files (checked in the script), so the panels can be stacked.

**Software.** pyfixest, linearmodels, statsmodels and pandas are not installed (checked with `import`; nothing was installed). The estimators are written in numpy and scipy: contract fixed effects by demeaning, CRV1 errors clustered by contract (factor G/(G-1) x (N-1)/(N-K), K = slope coefficients), t(G-1) intervals, a restricted wild cluster bootstrap (Rademacher, all 1,024 sign vectors for 10 coins, CI by test inversion), percentile intervals from 2000 resamples of whole contracts, and the Gelbach decomposition written out (pyfixest `decompose` computes the same quantity). The tests check them against dummy-variable regressions. The pyfixest dtype bugs do not arise.

## 1. Composition split, 2023-06 to 2026-07

Groups: 136 contracts in both months, 45 exits (delisted, renamed or merged before 2026-07), 113 entries (new listings in the 2026-07 sample). 2 survivors fitted only in 2026-07 (MAVUSDT, NMRUSDT: their 2023-06 month was incomplete) are left out. Chain: all 2023 -> survivors 2023 (exit term) -> survivors 2026 (within term) -> all 2026 (entry term); the terms sum exactly to the total. For the mean this is the methods-note formula term for term. Accuracy in percentage points (pp), 95% intervals from 2000 resamples of contracts within each group.

| outcome, statistic | 2023-06 | 2026-07 | total change | exits | within | entries |
|---|---|---|---|---|---|---|
| accuracy, mean | 61.69 | 64.44 | +2.75 (+2.07 to +3.49) | -0.17 (-0.41 to +0.07) | +3.41 (+2.59 to +4.27) | -0.48 (-1.04 to +0.07) |
| accuracy, median | 61.46 | 63.78 | +2.32 (+1.40 to +2.98) | -0.23 (-0.59 to +0.14) | +2.83 (+1.74 to +3.53) | -0.28 (-0.92 to +0.23) |
| lift over majority, mean | 10.87 | 14.34 | +3.47 (+2.40 to +4.63) | -0.13 (-0.37 to +0.11) | +3.66 (+2.58 to +4.89) | -0.06 (-1.00 to +0.99) |
| lift over majority, median | 10.49 | 13.27 | +2.78 (+2.09 to +3.42) | -0.13 (-0.55 to +0.13) | +3.24 (+2.52 to +4.28) | -0.34 (-1.07 to +0.05) |

Shares of the change in mean accuracy: within 124%, exits -6%, entries -18% (median: within 122%, exits -10%, entries -12%).

Checks on the split:
- **Noise floor.** On the 10 coins, 2023-06 to 2023-07 moves mean accuracy by +0.55 pp (-0.12 to +1.23), with a coin-level standard deviation of 1.13 pp. The same coins from 2023-06 to 2026-07: +2.77 pp (+1.23 to +4.58). If a one-month change of that spread were pure noise, the mean of 136 survivor changes would carry a noise of about 0.10 pp, small against the within term of +3.41 pp. 101 of 136 survivors rose.
- **Renames linked.** Linking the 3 renamed contracts whose successor is in the 2026 sample (BNXUSDT to FORMUSDT, KLAYUSDT to KAIAUSDT, MATICUSDT to POLUSDT) as one unit: within +3.36, exits -0.17, entries -0.44 (mean, pp). Essentially unchanged.
- **Entries at their population share.** The 2026 sample holds 113 entries next to 136 survivors (45% entries), but the 2026-07 population has about 376 crypto new listings (499 in the frame x 113/150 fitted), so about 73%. With that weight the entry term would be -0.78 pp instead of -0.48 pp. The sample is stratified by zip-size decile, so the entrants' mean is close to representative; only their weight is off.

## 2. Regressions

Coefficients in pp of accuracy per step of the driver (step in the second column). Brackets: 95% interval, CRV1 clustered by contract, t(G-1). Models:
- (a1) pooled OLS on all 462 contract-months (cross-sections plus the 10 coins' middle months), no time effects; (a2) the same with month intercepts.
- (b1) contract fixed effects on the 136 contracts present in both cross-sections plus the 10-coin middle months (302 rows, 136 contracts); identified from within-contract changes, including the common rise.
- (b2) the same with month fixed effects (two-way): identified only from contracts whose driver moved more or less than the market in that month (section 1.4: the month effects absorb the common rise).
- (b3) contract fixed effects on the 10-coin 5-month panel (50 rows, 10 contracts); brackets are CRV1, the wild cluster bootstrap result is in the next table.

| driver | step | (a1) pooled | (a2) pooled + month | (b1) contract FE | (b2) two-way FE | (b3) 10 coins, contract FE |
|---|---|---|---|---|---|---|
| log median trade size | per +1 log point | -4.36 (-5.28 to -3.45) | -5.35 (-6.22 to -4.48) | -3.37 (-4.31 to -2.43) | -3.91 (-4.85 to -2.98) | -1.42 (-7.18 to +4.34) |
| log relative tick | per +1 log point | -1.57 (-2.02 to -1.12) | -1.53 (-2.03 to -1.02) | -0.94 (-2.10 to +0.22) | -0.50 (-1.58 to +0.59) | -1.27 (-2.33 to -0.21) |
| share of trades under $1k | per +10 pp | -1.80 (-2.54 to -1.07) | -1.64 (-2.47 to -0.81) | -0.35 (-1.44 to +0.74) | +0.16 (-0.95 to +1.27) | +0.58 (-4.55 to +5.71) |
| sweep share | per +1 pp | +0.32 (+0.05 to +0.59) | +0.44 (+0.17 to +0.71) | +0.13 (-0.47 to +0.73) | +0.41 (-0.24 to +1.07) | +0.19 (-0.17 to +0.55) |
| minute-open ratio | per +1 | -1.95 (-2.42 to -1.47) | -1.52 (-2.00 to -1.04) | -1.00 (-1.80 to -0.21) | -0.80 (-1.61 to -0.00) | +4.62 (+2.56 to +6.68) |
| log events per day | per +1 log point | -0.92 (-1.58 to -0.25) | -0.59 (-1.32 to +0.15) | +1.12 (-0.14 to +2.39) | +0.99 (-0.25 to +2.23) | +1.50 (-0.17 to +3.16) |
| R2 (within for FE) | | 0.50 | 0.55 | 0.52 | 0.57 | 0.69 |

Contract FE model (b1), second opinions: contract-resampling percentile intervals (2000 draws) and Bonferroni p-values for 6 drivers; the 10-coin model (b3) with the restricted wild cluster bootstrap (Rademacher, all 1,024 sign vectors, CI by test inversion):

| driver | (b1) CRV1 p | (b1) Bonferroni p | (b1) contract-resampling 95% | (b3) wild p | (b3) wild 95% |
|---|---|---|---|---|---|
| log median trade size | <0.001 | <0.001 | -4.28 to -2.17 | 0.777 | -8.48 to +4.69 |
| log relative tick | 0.113 | 0.679 | -2.01 to +0.32 | 0.016 | -2.53 to -0.32 |
| share of trades under $1k | 0.524 | 1.000 | -1.51 to +0.88 | 0.814 | -5.37 to +5.51 |
| sweep share | 0.675 | 1.000 | -0.43 to +0.75 | 0.275 | -0.17 to +0.57 |
| minute-open ratio | 0.014 | 0.084 | -1.74 to -0.18 | 0.055 | -0.09 to +6.46 |
| log events per day | 0.082 | 0.491 | -0.20 to +2.50 | 0.115 | -0.49 to +3.26 |

**Mechanical model, not an explanation.** Adding long same-sign runs (share of runs of 10 or more, sweeps merged) to (b1): its coefficient is +1.82 pp per +1 pp (+1.23 to +2.41), and the within R2 goes from 0.52 to 0.68. Long runs are almost the outcome restated (a run of 10 is 9 correct persistence guesses), so this measures how the rise shows up, not why.

Within versus between spread of each driver (survivors, two months; the within standard deviation is scaled to the size of a two-month change):

| driver | SD of contract means | SD within contract |
|---|---|---|
| log median trade size | 0.64 | 1.43 |
| log relative tick | 0.95 | 0.77 |
| share of trades under $1k | 0.81 | 1.09 |
| sweep share | 1.30 | 1.90 |
| minute-open ratio | 0.52 | 1.16 |
| log events per day | 0.77 | 0.81 |

### The 2026 effect and what accounts for it (Gelbach decomposition)

Model: accuracy ~ 2026 dummy | contract (short), then + the six drivers (long). The 2026 coefficient in the short model is the mean within-contract rise (it equals the within term of the composition split). The Gelbach decomposition splits the fall from the short to the long coefficient into one exact, order-free piece per driver: (how much the driver moved within contracts) x (its coefficient in the long model). Intervals: 2000 resamples of contracts. With two months, contract fixed effects are first differences. A month fixed effect cannot be added here: it would be the 2026 dummy itself (section 1.4).

**Main: survivors, 2023-06 vs 2026-07, accuracy** (272 rows, 136 contracts)

| term | pp | 95% (resampling contracts) | share of the 2026 coefficient |
|---|---|---|---|
| 2026 coefficient, no drivers | +3.41 | +2.50 to +4.33 | 100% |
| 2026 coefficient, with drivers (unexplained) | -2.95 | -4.80 to -0.96 | -86% |
| explained by log median trade size | +7.29 | +4.77 to +9.55 | 214% |
| explained by log relative tick | -0.06 | -0.37 to +0.08 | -2% |
| explained by share of trades under $1k | +0.52 | -1.21 to +2.10 | 15% |
| explained by sweep share | +0.34 | -0.34 to +1.20 | 10% |
| explained by minute-open ratio | -0.93 | -2.05 to +0.15 | -27% |
| explained by log events per day | -0.81 | -1.75 to +0.15 | -24% |
| group: trade size (log size + under $1k) | +7.80 | +5.81 to +9.59 | 229% |
| group: relative tick | -0.06 | -0.37 to +0.08 | -2% |
| group: sweeps | +0.34 | -0.34 to +1.20 | 10% |
| group: minute-open bunching | -0.93 | -2.05 to +0.15 | -27% |
| group: activity | -0.81 | -1.75 to +0.15 | -24% |

Mean within-contract change of each driver on these survivors (the first factor of each Gelbach piece):

| driver | mean change | 95% |
|---|---|---|
| log median trade size (per +1 log point) | -1.828 | -1.981 to -1.680 |
| log relative tick (per +1 log point) | +0.104 | -0.087 to +0.294 |
| share of trades under $1k (per +10 pp) | +1.317 | +1.186 to +1.455 |
| sweep share (per +1 pp) | +1.154 | +0.758 to +1.578 |
| minute-open ratio (per +1) | +1.256 | +1.092 to +1.433 |
| log events per day (per +1 log point) | -0.665 | -0.820 to -0.511 |
| long same-sign runs (MECHANICAL) (per +1 pp) | +0.736 | +0.437 to +1.033 |

**Robustness outcome: lift over the majority rule, same survivors** (272 rows, 136 contracts)

| term | pp | 95% (resampling contracts) | share of the 2026 coefficient |
|---|---|---|---|
| 2026 coefficient, no drivers | +3.66 | +2.61 to +4.98 | 100% |
| 2026 coefficient, with drivers (unexplained) | -0.62 | -5.70 to +3.18 | -17% |
| explained by log median trade size | +1.70 | -4.56 to +13.12 | 47% |
| explained by log relative tick | +0.16 | -0.21 to +0.67 | 4% |
| explained by share of trades under $1k | +2.56 | -1.59 to +5.11 | 70% |
| explained by sweep share | +0.75 | -0.26 to +1.77 | 20% |
| explained by minute-open ratio | -0.02 | -2.04 to +1.95 | -1% |
| explained by log events per day | -0.86 | -3.09 to +0.64 | -23% |
| group: trade size (log size + under $1k) | +4.26 | -0.64 to +12.02 | 116% |
| group: relative tick | +0.16 | -0.21 to +0.67 | 4% |
| group: sweeps | +0.75 | -0.26 to +1.77 | 20% |
| group: minute-open bunching | -0.02 | -2.04 to +1.95 | -1% |
| group: activity | -0.86 | -3.09 to +0.64 | -23% |

**Robustness: drop the smallest decile of survivors by 2023-06 events** (244 rows, 122 contracts)

| term | pp | 95% (resampling contracts) | share of the 2026 coefficient |
|---|---|---|---|
| 2026 coefficient, no drivers | +3.72 | +2.85 to +4.61 | 100% |
| 2026 coefficient, with drivers (unexplained) | -2.41 | -4.38 to -0.09 | -65% |
| explained by log median trade size | +6.85 | +3.49 to +9.15 | 184% |
| explained by log relative tick | -0.11 | -0.53 to +0.10 | -3% |
| explained by share of trades under $1k | +0.85 | -1.00 to +2.67 | 23% |
| explained by sweep share | +0.19 | -0.57 to +1.00 | 5% |
| explained by minute-open ratio | -0.56 | -1.90 to +0.60 | -15% |
| explained by log events per day | -1.09 | -2.23 to +0.35 | -29% |
| group: trade size (log size + under $1k) | +7.70 | +5.02 to +9.63 | 207% |
| group: relative tick | -0.11 | -0.53 to +0.10 | -3% |
| group: sweeps | +0.19 | -0.57 to +1.00 | 5% |
| group: minute-open bunching | -0.56 | -1.90 to +0.60 | -15% |
| group: activity | -1.09 | -2.23 to +0.35 | -29% |

**10 coins, 5 months (2026-07 dummy; 2023-07, 2024-07, 2025-07 dummies in both models)** (50 rows, 10 contracts)

| term | pp | 95% (resampling contracts) | share of the 2026 coefficient |
|---|---|---|---|
| 2026 coefficient, no drivers | +2.77 | +1.25 to +4.55 | 100% |
| 2026 coefficient, with drivers (unexplained) | -0.87 | -2.64 to +1.80 | -32% |
| explained by log median trade size | +2.86 | -2.35 to +9.71 | 103% |
| explained by log relative tick | -0.06 | -0.67 to +0.19 | -2% |
| explained by share of trades under $1k | -0.08 | -5.87 to +4.03 | -3% |
| explained by sweep share | +0.38 | -0.48 to +2.07 | 14% |
| explained by minute-open ratio | +0.42 | -0.79 to +1.15 | 15% |
| explained by log events per day | +0.12 | -0.91 to +0.99 | 4% |
| group: trade size (log size + under $1k) | +2.78 | +0.64 to +4.50 | 100% |
| group: relative tick | -0.06 | -0.67 to +0.19 | -2% |
| group: sweeps | +0.38 | -0.48 to +2.07 | 14% |
| group: minute-open bunching | +0.42 | -0.79 to +1.15 | 15% |
| group: activity | +0.12 | -0.91 to +0.99 | 4% |

10 coins, restricted wild cluster bootstrap on the 2026-07 coefficient: no drivers +0.92 to +4.91, with drivers -3.07 to +2.08. With 10 contracts the contract-resampling intervals above are rough.

**Mechanical, labelled separately: main model plus long runs** (272 rows, 136 contracts)

| term | pp | 95% (resampling contracts) | share of the 2026 coefficient |
|---|---|---|---|
| 2026 coefficient, no drivers | +3.41 | +2.50 to +4.33 | 100% |
| 2026 coefficient, with drivers (unexplained) | +1.15 | -0.74 to +2.88 | 34% |
| explained by log median trade size | +1.53 | -1.42 to +4.45 | 45% |
| explained by log relative tick | +0.03 | -0.13 to +0.29 | 1% |
| explained by share of trades under $1k | +0.46 | -1.04 to +1.84 | 14% |
| explained by sweep share | -0.01 | -0.54 to +0.59 | -0% |
| explained by minute-open ratio | -0.07 | -1.00 to +1.13 | -2% |
| explained by log events per day | -1.08 | -2.42 to -0.21 | -32% |
| explained by long same-sign runs (MECHANICAL) | +1.39 | +0.72 to +2.46 | 41% |
| group: trade size (log size + under $1k) | +1.99 | -0.39 to +4.28 | 58% |
| group: relative tick | +0.03 | -0.13 to +0.29 | 1% |
| group: sweeps | -0.01 | -0.54 to +0.59 | -0% |
| group: minute-open bunching | -0.07 | -1.00 to +1.13 | -2% |
| group: activity | -1.08 | -2.42 to -0.21 | -32% |

## 3. Agreement with the e3 natural experiment

e3 cut the tick 10x (log relative tick -2.15 to -2.30) and found same-day refit accuracy +3.9 pp (+1.0 to +6.9) in 2026 and +7.5 pp (+4.8 to +10.2) in 2024 against matched controls, with a frozen pre-cut model showing no change (-0.7 pp). The `gbm_all` outcome here is fitted on each contract-month's own data, so the refit number is the comparable one. A 10x cut implied by the regressions (coefficient on log relative tick x -ln 10):

| model | implied effect of a 10x cut (pp) | 95% |
|---|---|---|
| survivors, contract FE + 2026 dummy, relative tick only (total effect) | +0.43 | -1.75 to +2.62 |
| panel (b1 sample), contract FE + month dummies, relative tick only | +0.53 | -1.50 to +2.56 |
| survivors, all six drivers (partial: trade size etc. held fixed) | +1.26 | -1.46 to +3.98 |
| (b2) two-way FE, all drivers | +1.15 | -1.35 to +3.64 |
| e3 2026-03-05 event, same-day refit | +3.9 | +1.0 to +6.9 |
| e3 2024-09-20 event, same-day refit | +7.5 | +4.8 to +10.2 |

The 10-coin model (b3) gives +2.93 pp (+0.75 to +5.83, wild bootstrap) for a 10x cut.

## 4. What explains the rise? (plain language)

- **Not composition.** Mean accuracy across the cross-section rose +2.75 pp (+2.07 to +3.49). Contracts present in both months rose by more, +3.41 pp (+2.59 to +4.27). The coins that died were slightly below the survivors, but removing them adds only +0.17 pp; the new listings are slightly less predictable than the survivors and pull the 2026 average down by 0.48 pp (more, 0.78 pp, at their population weight). Both composition terms are small and of opposite sign to the survivorship story; the whole rise, and a bit more, happens inside contracts. The median and the lift outcome say the same. The noise floor (one month on 10 coins, +0.55 pp) is far below the within change.
- **Trade size accounts for all of the within-contract rise, and more.** Survivors' median trade size fell in 98% of contracts, by -1.83 log points on average (about 84% smaller). Contracts whose trades shrank more became more predictable (about 3.99 pp per log point, holding the other drivers fixed; similar in pooled, contract FE and two-way FE models). Multiplied out, the size group accounts for +7.80 pp (+5.81 to +9.59) of the +3.41 pp rise, so the remaining 2026 effect turns negative (-2.95, -4.80 to -0.96). On the 10-coin 5-month panel the size group accounts for +2.78 pp (+0.64 to +4.50) of +2.77 pp, leaving -0.87. Read as: the fall in trade size is more than enough, in an accounting sense, to explain the rise; the overshoot says the cross-contract slope does not carry over one-for-one to a market-wide shift of this size (or that something else pushed accuracy down at the same time). With the lift outcome the size group is +4.26 pp (-0.64 to +12.02): same direction, much wider.
- **Relative tick explains none of the rise** (-0.06 pp, -0.37 to +0.08), not because it does not matter but because it did not move on average: survivors' log relative tick changed by +0.10 (-0.09 to +0.29); about half the coins' ticks got relatively larger as prices fell, half smaller.
- **Other drivers.** Minute-open bunching and activity rose or fell in ways that point the wrong way (they subtract from the explained part, intervals include 0); sweep share adds a little. The minute-open coefficient flips sign between the 10 coins (+) and the 136-contract panel (-), the within versus between warning from weeks 1 to 2. Long same-sign runs (mechanical) absorb part of the effect once added, as expected of a near-restatement of the outcome.
- **Agreement with e3.** Same sign: within contracts, a smaller relative tick goes with higher accuracy, and the implied effect of a 10x cut is +0.43 to +1.26 pp on the 136-contract panel and +2.93 pp on the 10 coins, against e3's +3.9 and +7.5 pp. The estimates on the 136 contracts are smaller and their intervals include 0; they overlap the 2026 event's interval but not the 2024 one (the 10-coin interval overlaps both). Smaller is expected: relative tick is measured with noise and moves gradually with price (attenuation), and e3's treated coins had large ticks (11 to 13 bps) where a cut bites most. So the experiment and the regression agree that a finer relative tick raises predictability, and the regression adds that this channel cannot be what lifted the market from 2023 to 2026, because relative ticks did not shrink on average.

## 5. Caveats

- **Noisy outcome.** Each accuracy comes from one month (at least 10,000 test events, binomial SE up to 0.5 pp); with only two snapshots per contract, contract fixed effects keep that noise and attenuate noisy drivers. Dropping the smallest decile by activity changes little.
- **Few snapshots.** The panel has two cross-section months (plus three middle months for 10 coins), so the 2026 dummy is one market-wide contrast, and everything else that changed between 2023 and 2026 is in it. The Gelbach split is an accounting identity given a linear model, not a causal attribution; the trade-size piece extrapolates a cross-contract slope to a common shift.
- **Trade size may partly be a change in what an event is.** Median notional per aggressor event fell about 84% within survivors. Week 0 flagged a change in aggregation shape for some coins (more fills per record); if the exchange's matching or reporting changed, part of the size fall, and of the accuracy rise, could be measurement. Not settled here.
- **Survivorship and sampling.** Survivors are contracts trading in both months; the 2026 entries are a decile-stratified sample of new listings (113 of 150 drawn were crypto and fitted), so the entry term uses the sample weight unless reweighted (both reported). Renames are separate units in the main split; linking the 3 that are in the sample changes nothing.
- **Multiple drivers tested.** Six drivers, four models, two outcomes. In the contract FE model only trade size survives a Bonferroni correction for six drivers. Treat the others as leads.
- **Few clusters for the 10-coin panel.** Reported with the wild cluster bootstrap; its intervals are wide.
- **Software.** Estimators written by hand (no pyfixest, linearmodels or statsmodels installed); checked against dummy-variable regressions in the tests.
