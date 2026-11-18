# Q15: why next-trade signs became more predictable, and what tick size does

## Question

Why did next-trade-sign predictability rise from 2023 to 2025 (Q10), and does tick size cause sign persistence? Q10 found that a freshly trained model predicts the next trade's sign better in 2025-07 than in 2023-06 on the same 10 contracts. Part A of `research/market_evolution` asked whether that rise is composition or change within contracts, which measured drivers move with it, and whether one of them, relative tick size, causes sign persistence in natural experiments.

## Method

This report fits nothing new except descriptive cross-sectional regressions; it assembles the Part A outputs (`q15_market_evolution.py`):

- `research/market_evolution/e0_what_changed.json` and `research/market_evolution/e1_proxies.json`: Q10's 10 coins x 5 months.
- `research/market_evolution/data/proxies_cross_section.parquet` (e2): 181 contracts in 2023-06 and 251 in 2026-07 (Q14 cross-sections), with Q14 accuracy and the order-flow proxies.
- `research/market_evolution/data/e4_panel_regressions.md`: composition split, fixed-effects regressions and Gelbach decomposition (parsed from its tables; e4 writes no JSON).
- `data/event_study/e3_results.json` and `data/event_study/e5/e5_results.json`: the two-batch event study and the stacked event study over 35 batches.
- `data/event_study/e5/lockbox`: one run of the frozen e5 design on the two reserved batches.

Intervals are 95%: contract-resampling percentiles (2000 draws) for changes and cross-sectional slopes, CR1 clustered by contract with t(G-1) for the event studies, plus e5's within-batch permutation test. The tick accounting multiplies a mean change in log relative tick by the e5 pooled slope per log point.

## Verdict

Across the Q14 cross-sections, mean accuracy rose +2.75 (+2.07 to +3.49) pp from 2023-06 to 2026-07. Contracts present in both months rose +3.41 (+2.59 to +4.27) pp; exits contributed -0.17 (-0.41 to +0.07) and new listings -0.48 (-1.04 to +0.07). So the rise is not composition: the two composition terms sum to -0.65 pp and pull the average down, and the whole rise happens inside contracts (one-month noise floor +0.55 (-0.12 to +1.23) pp). Median trade size in USD fell in 98% of the 136 survivors, by -1.83 (-1.97 to -1.68) log points on average (about 84% smaller). With contract fixed effects, accuracy moves -3.37 (-4.31 to -2.43) pp per log point of trade size, and in the Gelbach split trade size accounts for +7.80 (+5.81 to +9.59) pp of the +3.41 pp within-contract rise. That is more than the whole rise, so the cross-contract slope does not carry over one for one to a market-wide shift this large; it is an accounting identity, not a causal attribution. Across contracts at equal activity and trade size, the repeat rate changes by -3.91 (-4.78 to -3.01) pp in 2023 and -2.61 (-4.07 to -1.42) pp in 2026 per log point of relative tick, below zero in 2 of 2 months (descriptive). In the stacked event study (e5, 35 batches, 97 cuts and 16 increases), a 10x cut raises the repeat rate by +7.52 (+6.52 to +8.52) pp and an increase lowers it by -5.63 (-7.38 to -3.88) pp; pooled, -3.15 (-3.55 to -2.76) pp per log point of tick. Both prespecified signs hold, with intervals that exclude zero. The lock-box (2 reserved batches, 6 treated contracts, run once with the frozen e5 code) gives: sign repeat rate (primary) -1.55 (-3.33 to +0.23) per log point against e5's -3.15 (permutation p 0.085): weakens; lag-1 sign autocorrelation, x100 (primary) -5.06 (-8.16 to -1.96) per log point against e5's -6.72 (permutation p <0.001): confirms; same-day refit accuracy (secondary, post hoc in e3) +0.28 (-2.58 to +3.14) per log point against e5's -2.51 (permutation p 0.838): weakens; refit minus persistence (secondary, post hoc in e3) +1.45 (+0.72 to +2.18) per log point against e5's +0.84 (permutation p 0.002): confirms. The primary family is mixed: the direction agrees with e5 but not every primary outcome is decisive on this small sample, so the lock-box weakens rather than confirms. The e5 point estimate lies inside the lock-box interval for 2 of 2 primary outcomes, so the lock-box does not contradict its size. Per log point of relative tick, the cross-sectional repeat-rate slope at equal activity is -3.87 to -1.91 pp and the experimental one -3.15 (-3.55 to -2.76) pp (lock-box -1.55 (-3.33 to +0.23)). The experiment lies inside the cross-sectional range, so the across-contract pattern has about the causal size. What tick explains: across the 136 survivors, log relative tick changed by +0.10 (-0.07 to +0.29) from 2023-06 to 2026-07, which at the experimental slope implies -0.26 (-0.75 to +0.18) pp of accuracy against a rise of +3.41 pp, so tick explains essentially none of that rise. On Q10's 10 coins from 2023-06 to 2025-07, prices rose and log relative tick fell by -1.05 (-1.46 to -0.64), which implies +2.63 (+1.61 to +3.83) pp against their rise of +4.72 (+2.69 to +7.06) pp, about 56% of it, while their log trade size moved -0.05 (-0.46 to +0.38). That extrapolates a slope measured on small contracts and on a same-day refit model to large coins and a month-long boosted model, so it is a rough share. Answer. The rise in next-sign predictability happened inside contracts, not through which coins survived. Tick size very likely causes sign persistence (35 batches in both directions), and the untouched lock-box points the same way but is weaker and not decisive on every primary outcome. Through falling relative ticks as prices rose, it can account for roughly 56% of Q10's 2023-06 to 2025-07 rise on its 10 coins, but for none of the 2023 to 2026 rise across the cross-section, where relative ticks did not shrink on average. The 2023 to 2026 within-contract rise lines up instead with much smaller trades (-1.83 log points), consistent with algorithmic slicing but a correlation without an experiment; on Q10's coins trade size had not yet moved by 2025-07, so it does not explain the part of their rise that tick leaves. All of this is sign persistence, not price predictability.

## Results

### 1. Composition versus within-contract change

Q10's 10 coins, mean fresh-model accuracy (pp, `research/market_evolution/e0_what_changed.json`):

| 2023-06 | 2023-07 | 2024-07 | 2025-07 | 2026-07 |
| --- | --- | --- | --- | --- |
| 61.66 | 62.21 | 63.91 | 66.38 | 64.43 |

Q14 cross-sections, mean accuracy (pp), split as in e4 (exits, within, entries sum to the total):

| 2023-06 | 2026-07 | total | exits | within (survivors) | entries |
| --- | --- | --- | --- | --- | --- |
| 61.69 | 64.44 | +2.75 (+2.07 to +3.49) | -0.17 (-0.41 to +0.07) | +3.41 (+2.59 to +4.27) | -0.48 (-1.04 to +0.07) |

Across the Q14 cross-sections, mean accuracy rose +2.75 (+2.07 to +3.49) pp from 2023-06 to 2026-07. Contracts present in both months rose +3.41 (+2.59 to +4.27) pp; exits contributed -0.17 (-0.41 to +0.07) and new listings -0.48 (-1.04 to +0.07). So the rise is not composition: the two composition terms sum to -0.65 pp and pull the average down, and the whole rise happens inside contracts (one-month noise floor +0.55 (-0.12 to +1.23) pp).

### 2. Trade size and relative tick: cross-section and panel

Within-contract change, 2026-07 minus 2023-06, 136 survivors:

| quantity | mean change | share of contracts that fell |
| --- | --- | --- |
| accuracy (pp) | +3.41 (+2.56 to +4.29) | 26% |
| sign repeat rate (pp) | +4.73 (+3.55 to +5.83) | 20% |
| log median trade size (USD) | -1.83 (-1.97 to -1.68) | 98% |
| log relative tick | +0.10 (-0.07 to +0.29) | 48% |

Cross-section, OLS per month of the outcome on log trade size, log relative tick and log events (descriptive; per log point):

| month, outcome | n | log trade size | log relative tick |
| --- | --- | --- | --- |
| 2023, accuracy (pp) | 181 | -3.57 (-4.42 to -2.61) | -1.29 (-1.84 to -0.65) |
| 2023, repeat rate (pp) | 181 | -2.07 (-3.85 to -0.10) | -3.91 (-4.78 to -3.01) |
| 2026, accuracy (pp) | 251 | -4.86 (-5.80 to -3.40) | -1.53 (-2.22 to -0.86) |
| 2026, repeat rate (pp) | 251 | -5.06 (-5.66 to -4.53) | -2.61 (-4.07 to -1.42) |

Panel regressions of accuracy (e4, pp per log point, CRV1 by contract):

| driver | pooled | contract FE | two-way FE | 10 coins, contract FE |
| --- | --- | --- | --- | --- |
| log median trade size | -4.36 (-5.28 to -3.45) | -3.37 (-4.31 to -2.43) | -3.91 (-4.85 to -2.98) | -1.42 (-7.18 to +4.34) |
| log relative tick | -1.57 (-2.02 to -1.12) | -0.94 (-2.10 to +0.22) | -0.50 (-1.58 to +0.59) | -1.27 (-2.33 to -0.21) |

Gelbach split of the within-contract rise (e4, survivors, pp):

| term | pp |
| --- | --- |
| rise, no drivers | +3.41 (+2.50 to +4.33) |
| explained by trade size (log size and share under $1k) | +7.80 (+5.81 to +9.59) |
| explained by relative tick | -0.06 (-0.37 to +0.08) |
| unexplained, with all six drivers | -2.95 (-4.80 to -0.96) |

Median trade size in USD fell in 98% of the 136 survivors, by -1.83 (-1.97 to -1.68) log points on average (about 84% smaller). With contract fixed effects, accuracy moves -3.37 (-4.31 to -2.43) pp per log point of trade size, and in the Gelbach split trade size accounts for +7.80 (+5.81 to +9.59) pp of the +3.41 pp within-contract rise. That is more than the whole rise, so the cross-contract slope does not carry over one for one to a market-wide shift this large; it is an accounting identity, not a causal attribution.

Across contracts at equal activity and trade size, the repeat rate changes by -3.91 (-4.78 to -3.01) pp in 2023 and -2.61 (-4.07 to -1.42) pp in 2026 per log point of relative tick, below zero in 2 of 2 months (descriptive).

### 3. Natural experiments

e3, two 10x cuts (pp; CR1 clustered):

| event | treated / controls | sign repeat rate (primary) | frozen-model accuracy (e3's prespecified outcome) | same-day refit accuracy (secondary, post hoc in e3) |
| --- | --- | --- | --- | --- |
| 2026-03-05 | 12 / 62 | +6.68 (+4.12 to +9.23) | -0.73 (-4.40 to +2.94) | +3.93 (+0.96 to +6.90) |
| 2024-09-20 | 10 / 9 | +8.84 (+5.52 to +12.17) | +2.66 (-1.49 to +6.82) | +7.49 (+4.81 to +10.18) |

e5, stacked over 35 batches (cut and increase: treated minus controls; pooled: per log point of signed tick change):

| outcome | cut (CR1) | increase (CR1) | pooled (CR1) | pooled permutation | pooled pre-trend p |
| --- | --- | --- | --- | --- | --- |
| sign repeat rate (primary) | +7.52 (+6.52 to +8.52) | -5.63 (-7.38 to -3.88) | -3.15 (-3.55 to -2.76) | -3.44 to -2.87 | 0.272 |
| lag-1 sign autocorrelation, x100 (primary) | +16.11 (+14.31 to +17.92) | -11.62 (-15.45 to -7.79) | -6.72 (-7.45 to -5.99) | -7.22 to -6.22 | 0.184 |
| same-day refit accuracy (secondary, post hoc in e3) | +5.90 (+4.78 to +7.02) | -5.08 (-6.94 to -3.21) | -2.51 (-2.95 to -2.08) | -2.85 to -2.17 | 0.950 |
| refit minus persistence (secondary, post hoc in e3) | -2.16 (-2.57 to -1.74) | +0.72 (-0.01 to +1.46) | +0.84 (+0.67 to +1.00) | +0.71 to +0.97 | 0.073 |
| unchanged-price share (mechanism) | -31.50 (-33.22 to -29.78) | +17.89 (+13.35 to +22.43) | +12.78 (+11.98 to +13.57) | +12.20 to +13.35 | 0.719 |
| relative tick, log points (first stage) | -2.26 (-2.29 to -2.23) | +0.59 (+0.25 to +0.94) | +0.87 (+0.82 to +0.92) | +0.85 to +0.90 | 0.761 |

In the stacked event study (e5, 35 batches, 97 cuts and 16 increases), a 10x cut raises the repeat rate by +7.52 (+6.52 to +8.52) pp and an increase lowers it by -5.63 (-7.38 to -3.88) pp; pooled, -3.15 (-3.55 to -2.76) pp per log point of tick. Both prespecified signs hold, with intervals that exclude zero.

### 4. Lock-box

Frozen code: commit `ba1ae1c` (e5 unchanged since; the only edit is the `--lockbox` switch, the only path allowed to load the reserved dates). HEAD at analysis `87db3ba`. Runs: 1. No bug was found when the per-contract changes were checked after the run, so there is no second run. Design written down before any download: per reserved batch, the 3 eligible cut contracts with the smallest pre-event archive size, their first 3 valid controls, every third relative day.

| batch | treated | controls |
| --- | --- | --- |
| 2026-08-06 | CKBUSDT, VANAUSDT, AXSUSDT (3 of 8 eligible) | 9 |
| 2026-10-15 | RUMUSDT, FLNCUSDT, CSOPSAMSUNG2LUSDT (3 of 7 eligible) | 8 |

Coverage: 320 of 322 contract-days, 23 contracts, median 6,450 scored events per contract-day; downloaded 0.07 GB.

Lock-box estimates next to e5 (pp; CR1):

| outcome | lock-box cut | lock-box pooled | lock-box permutation p | lock-box pre-trend p | e5 pooled | rule |
| --- | --- | --- | --- | --- | --- | --- |
| sign repeat rate (primary) | +3.56 (-0.54 to +7.66) | -1.55 (-3.33 to +0.23) | 0.085 | 0.751 | -3.15 (-3.55 to -2.76) | weaken |
| lag-1 sign autocorrelation, x100 (primary) | +11.65 (+4.51 to +18.79) | -5.06 (-8.16 to -1.96) | <0.001 | 0.292 | -6.72 (-7.45 to -5.99) | confirm |
| same-day refit accuracy (secondary, post hoc in e3) | -0.64 (-7.23 to +5.95) | +0.28 (-2.58 to +3.14) | 0.838 | 0.328 | -2.51 (-2.95 to -2.08) | weaken |
| refit minus persistence (secondary, post hoc in e3) | -3.34 (-5.03 to -1.65) | +1.45 (+0.72 to +2.18) | 0.002 | 0.307 | +0.84 (+0.67 to +1.00) | confirm |
| unchanged-price share (mechanism) | -35.52 (-40.04 to -31.00) | +15.43 (+13.46 to +17.39) | <0.001 | 0.564 | +12.78 (+11.98 to +13.57) | not tested |
| relative tick, log points (first stage) | -2.13 (-2.25 to -2.00) | +0.92 (+0.87 to +0.98) | <0.001 | 0.004 | +0.87 (+0.82 to +0.92) | not tested |

Per batch (e3's single-event DiD; repeat rate, pp):

| batch | treated / controls | repeat rate | permutation p | pre-trend p |
| --- | --- | --- | --- | --- |
| 2026-08-06 | 3 / 9 | +3.19 (-3.54 to +9.91) | 0.282 | 0.164 |
| 2026-10-15 | 3 / 8 | +3.95 (-1.82 to +9.73) | 0.176 | 0.855 |

Rule, fixed in e5 before the run: confirm when the sign matches e5, the CR1 interval excludes zero and the permutation p is below 0.05; reverse when the sign is opposite and the interval excludes zero; weaken otherwise.

The lock-box (2 reserved batches, 6 treated contracts, run once with the frozen e5 code) gives: sign repeat rate (primary) -1.55 (-3.33 to +0.23) per log point against e5's -3.15 (permutation p 0.085): weakens; lag-1 sign autocorrelation, x100 (primary) -5.06 (-8.16 to -1.96) per log point against e5's -6.72 (permutation p <0.001): confirms; same-day refit accuracy (secondary, post hoc in e3) +0.28 (-2.58 to +3.14) per log point against e5's -2.51 (permutation p 0.838): weakens; refit minus persistence (secondary, post hoc in e3) +1.45 (+0.72 to +2.18) per log point against e5's +0.84 (permutation p 0.002): confirms. The primary family is mixed: the direction agrees with e5 but not every primary outcome is decisive on this small sample, so the lock-box weakens rather than confirms. The e5 point estimate lies inside the lock-box interval for 2 of 2 primary outcomes, so the lock-box does not contradict its size.

### 5. Cross-sectional versus experimental slope

Per log point of relative tick (pp). Cross-section: OLS across contracts, raw and with log events (from e5, same parquet).

| estimate | repeat rate | accuracy |
| --- | --- | --- |
| cross-section 2023, raw | -0.22 (-1.59 to +0.94) | +0.08 (-0.62 to +0.86) (gbm, month) |
| cross-section 2023, activity held fixed | -3.87 (-4.76 to -2.84) | -1.22 (-1.99 to -0.40) (gbm, month) |
| cross-section 2026, raw | -0.77 (-1.98 to +0.12) | -0.69 (-1.33 to -0.03) (gbm, month) |
| cross-section 2026, activity held fixed | -1.91 (-3.69 to -0.66) | -0.86 (-1.65 to -0.06) (gbm, month) |
| e5 stacked event study | -3.15 (-3.55 to -2.76) | -2.51 (-2.95 to -2.08) (same-day refit) |
| lock-box | -1.55 (-3.33 to +0.23) | +0.28 (-2.58 to +3.14) (same-day refit) |

Per log point of relative tick, the cross-sectional repeat-rate slope at equal activity is -3.87 to -1.91 pp and the experimental one -3.15 (-3.55 to -2.76) pp (lock-box -1.55 (-3.33 to +0.23)). The experiment lies inside the cross-sectional range, so the across-contract pattern has about the causal size.

### 6. What is and is not explained

| sample, period | change in log relative tick | implied repeat rate (pp) | implied accuracy (pp) | observed accuracy change (pp) |
| --- | --- | --- | --- | --- |
| 136 survivors, 2023-06 to 2026-07 | +0.10 (-0.07 to +0.29) | -0.33 (-0.94 to +0.23) | -0.26 (-0.75 to +0.18) | +3.41 (+2.56 to +4.29) |
| Q10's 10 coins, 2023-06 to 2025-07 | -1.05 (-1.46 to -0.64) | +3.30 (+2.05 to +4.72) | +2.63 (+1.61 to +3.83) | +4.72 (+2.69 to +7.06) |

What tick explains: across the 136 survivors, log relative tick changed by +0.10 (-0.07 to +0.29) from 2023-06 to 2026-07, which at the experimental slope implies -0.26 (-0.75 to +0.18) pp of accuracy against a rise of +3.41 pp, so tick explains essentially none of that rise. On Q10's 10 coins from 2023-06 to 2025-07, prices rose and log relative tick fell by -1.05 (-1.46 to -0.64), which implies +2.63 (+1.61 to +3.83) pp against their rise of +4.72 (+2.69 to +7.06) pp, about 56% of it, while their log trade size moved -0.05 (-0.46 to +0.38). That extrapolates a slope measured on small contracts and on a same-day refit model to large coins and a month-long boosted model, so it is a rough share.

- **Explained, with an experiment:** relative tick moves sign persistence in the predicted direction, both ways.
- **Explained only as an accounting identity:** the 2023 to 2026 within-contract rise lines up with a 84% fall in median trade size; there is no experiment for trade size.
- **Not explained:** why trades shrank (algorithmic slicing is the leading story), why the Gelbach split overshoots, why the 2023 batches show no tick effect, and whether any of this makes prices, rather than signs, more predictable.

## Caveats

- **Sign persistence is not price predictability.** Every outcome here is about the direction of the next aggressor event. Q2 and Q5 show that price impact adjusts to order-flow memory, so a more predictable sign is not a more predictable price, and no outcome here measures spreads, fees or profit.
- **Part of the tick effect is mechanical.** A finer grid splits the same taker flow into more same-side events at new prices (the unchanged-price share changes by -31.5 pp after a cut in e5), and aggTrades cannot separate that from changed trader behaviour.
- **Budget-limited contract selection.** e5 and the lock-box keep, per batch, the 3 cut contracts with the smallest pre-event archive size, every third day of the window, and cheap increases one at a time. The rule uses pre-event size only, but the results describe small and mid-sized contracts, not the largest coins whose rise Q10 measured.
- **Few increases.** e5 has 16 increase contracts; the lock-box batches contain 0. The coarser-grid direction rests mostly on two multi-contract batches and SOLUSDT.
- **Post-hoc outcomes are labelled.** Same-day refit accuracy and refit minus persistence were added in e3 after its first result and are secondary. The prespecified frozen-model accuracy in e3 did not move. Combining the two primary lock-box outcomes into one word (confirm only if both confirm) was decided after the run; the per-outcome rule was fixed before it.
- **Correlations are descriptive.** The cross-sectional slopes, the panel regressions and the Gelbach split are associations; the trade-size story has no experiment, and the tick accounting for Q10's coins carries a slope from small contracts and a different outcome to large coins.
- **The lock-box is small.** 23 contracts in 2 batches; 10 of them are stock-linked perpetuals (2026-10-15 especially), which trade mostly in US hours, so same-day refit accuracy (fitted on UTC hours 0 to 12) is missing for the thinnest of them.
- **Controls are matched on activity only**, not on price trend; Binance cuts a tick after a price fall, and the first-stage relative tick drifts before some events.

## Files

- `src/microstructure/analyses/q15_market_evolution.py` builds the result dict; `q15_report.py` writes this file and the figure.
- `results/q15_market_evolution.json` holds every number above.
- `research/market_evolution/e5_stacked_events.py --lockbox` ran the lock-box.

