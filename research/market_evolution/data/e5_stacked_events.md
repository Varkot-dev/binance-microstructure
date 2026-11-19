# E5: a stacked event study of tick-size changes, cuts and increases

Script: `../e5_stacked_events.py` (tests: `tests/research/test_e5_stacked.py`). Plot:
`e5_stacked_events.png`. Numbers: `data/event_study/e5/e5_results.json`; the fixed design
(arms, contracts, controls, dropped contracts and why): `data/event_study/e5/e5_plan.json`.
Run on 2026-11-18.

## Question

e3 found that two 10x tick CUTS (2026-03-05, 2024-09-20) made trade signs more persistent.
Does this hold across every usable batch, does a tick INCREASE do the opposite, and how
much does predictability change per log point of relative tick?

## Fixed before any new result was looked at

- **Lock-box: 2026-08-06 (8 cuts) and 2026-10-15 (7 cuts) are reserved** for a final
  replication. Their files were not downloaded or read. Their treated contracts are also
  kept out of every other sub-panel whose days come within 21 days of the reserved date.
  The code refuses to load or fetch either date (`guard`, tested).
- **Primary outcome:** sign repeat rate, with lag-1 sign autocorrelation in the same family.
  **Secondary:** the e3 same-day refit accuracy and refit minus persistence. They are
  secondary because e3 added them after its first result. **Mechanisms:** unchanged-price
  share, same-sign runs of 10 or more (sweeps merged), median trade size, aggressor events
  per day. **First stage:** log relative tick.
- **Expected signs:** a cut raises the repeat rate and an increase lowers it. In the pooled
  model the treatment is signed by the log tick change (a 10x cut is -2.30), so the
  coefficient should be **negative**.

## Design

- **Batches** are change dates from `tick_events.csv` (detected date, which is the key of
  `tick_event_controls.csv`).
- **A treated contract is eligible when:**
  - its status is `verified`;
  - it has no other tick change within 21 days;
  - it has at least 3 matched controls left after removing controls treated in the same
    batch or in a reserved window.
- **A batch is eligible** with at least 3 eligible treated contracts, or with any increase.
- **Contracts dropped** (36 in all): 24 had fewer than 3 valid controls, 6 had another
  change within 21 days, and 6 were in batches that failed the batch rule. That leaves
  60 eligible batches (349 eligible cuts, 51 eligible increases).
- **Controls:** the first 3 valid ranks per treated contract. SOLUSDT 2024-10-14 keeps all 6.
- **Budget rule.** The full design (all eligible contracts, every day of -21..+21) would be
  about 110 GB against a 4 GB budget, so these rules were fixed in advance:
  - **Days:** every third relative day, -19, -16, ..., -1 and +1, +4, ..., +19 (14 days; the
    event day is never used).
  - **Cut arms:**
    - each batch keeps the 3 eligible cut contracts with the smallest PRE-event archive
      size (never post-event size, which moves with events per day, an outcome);
    - arms are taken cheapest first, round-robin over years, up to 1.75 GB.
  - **Increases:** taken one contract at a time, cheapest first, up to 1.40 GB, with SOL
    always included.
  - **The two e3 batches** reuse the e3 cache: all their cached treated contracts are kept,
    and only missing control-days were downloaded (ranks 2 to 3 for 2024-09-20).
- **Stacked model:**
  - `y = batch x contract FE + batch x relative-day FE + b * D * post`;
  - CR1 standard errors clustered by contract (G - 1 degrees of freedom; a contract in
    several batches is one cluster);
  - D is the treated indicator in the cut and increase models, and the signed log tick
    change (+/-2.30, or +/-4.61 for 100x) in the pooled model;
  - each sub-panel holds only its own treated contracts and their own controls, so no
    already-treated contract is a control (methods note 2.3);
  - the cut model drops increase-treated contracts and vice versa.
- **Inference:**
  - CR1 intervals;
  - e3's restricted wild cluster bootstrap (Webb weights, 4,999 draws, on the stacked
    FWL data);
  - a permutation test that permutes treatment (or dose) across contracts **within each
    batch** (2,999 draws), with a CI from test inversion;
  - pre-trends: e3's dispersion statistic on pre-event days with treatment permuted within
    batches, plus a clustered linear pre-trend slope.
  - Per-batch estimates use e3's single-event DiD and its permutation test (999 draws, or
    all assignments). With one treated contract and 3 controls the smallest possible
    p-value is 0.25 (1/7 for SOL with 6 controls).
- **Data.** Each daily aggTrades file was SHA-256 checked, turned into aggressor events by
  e3's `day_stats` (same seeds and code as e3, without the frozen model), summarized, and
  deleted. Four downloads ran at a time and one contract-day was computed at a time.
  - **Downloaded: 3.28 GB** (e5's own ledger, `data/event_study/e5_ledger.json`). The e3
    cache was not re-downloaded.
  - No day file was over 300 MB (largest estimate about 35 MB), so none was skipped.
  - The temporary folder was empty at the end.

## Batches used and reserved

**Reserved (not analysed): 2026-08-06, 2026-10-15.**

**Used: 35 batches, 36 arms, 113 treated contract-events, 290 distinct contracts.**

- **27 cut arms (97 treated):** 2023-06-05, 2023-08-29, 2024-02-05, 2024-03-19,
  2024-04-11, 2024-07-25, 2024-09-20 (10, e3 cache), 2024-11-04, 2024-11-28, 2025-04-17,
  2025-06-12, 2025-08-25, 2025-10-27, 2025-10-31, 2025-11-07, 2025-11-27, 2025-12-15,
  2025-12-22, 2026-02-27, 2026-03-05 (12, e3 cache), 2026-04-22, 2026-06-08, 2026-06-12,
  2026-07-08, 2026-07-30, 2026-08-24, 2026-09-17. All have 3 treated except the two e3
  batches.
- **9 increase arms (16 treated):**
  - 2024-10-14 SOL (6 controls);
  - 2025-09-03 (6: AWE, XVG, BANK, A, NXPC, B);
  - 2026-06-13 (3: KGEN, AT, TAG);
  - one contract each: 2025-10-08 BNT, 2026-02-09 IRYS, 2026-03-18 JST, 2026-04-15 GUA,
    2026-04-21 ESPORTS, 2026-07-30 TST.
- **Not used for budget:**
  - 25 eligible batches;
  - the remaining cuts of the batches above;
  - 35 eligible increases, mostly large contracts: 2023-02-10 APT and OCEAN, BAS, BEAT,
    AKE, and others.

## Coverage

| | value |
|---|---|
| contract-days analysed (of planned) | 5,877 (5,894) |
| batch-contract units | 421 |
| median scored events per contract-day | 16,131 |
| short units | LSKUSDT 2024-02-05, RPLUSDT 2024-09-20, LOOMUSDT 2024-11-28 (11 of 14 days each) |

## Pre-trends

Stacked pre-trend permutation p-values (within-batch reassignment):

| outcome | cuts | increases | pooled |
|---|---|---|---|
| repeat rate (primary) | 0.29 | 0.85 | 0.27 |
| lag-1 autocorrelation (primary) | 0.36 | 0.58 | 0.18 |
| same-day refit accuracy | 0.98 | 0.83 | 0.95 |
| refit minus persistence | **0.021** | 0.86 | 0.073 |
| unchanged-price share | 0.70 | 0.94 | 0.72 |
| long runs | 0.85 | 0.96 | 0.78 |
| median trade size | 0.092 | 0.98 | 0.17 |
| events per day | 0.88 | 0.40 | 0.86 |
| relative tick | 0.082 | **0.024** | 0.76 |

- **No pre-trend in the primary outcomes.** Their linear pre-trend slopes all contain zero.
  For example, cuts: -0.06 pp a day (-0.14 to +0.01).
- **Two flags, neither in the primary outcomes:**
  - Refit minus persistence for cuts sits about 1 pp below its day -1 value on every
    pre-day (plot). This is the same kind of "day -1 is unusual" pattern e3 saw.
  - Relative tick for increases moves a little before the event (prices drifting).
- Two slopes exclude zero, both tiny: trade size for cuts (+0.013 log points a day) and
  relative tick for increases (-0.007 a day).
- By batch, the repeat-rate pre-trend p is below 0.05 in 3 of 36 arms (2024-03-19,
  2025-11-07, 2026-09-17), about what chance gives.

## Estimates

Effects in pp (percentage points), x100 for autocorrelation, or log points. Three 95%
intervals: CR1 clustered by contract, wild cluster bootstrap and within-batch
permutation. Every permutation and wild p is at its floor (<0.001) unless shown.

### Cuts (27 batches, 97 treated, 245 clusters)

| outcome | role | effect | CR1 | wild | permutation |
|---|---|---|---|---|---|
| repeat rate | primary | **+7.5** | +6.5 to +8.5 | +6.6 to +8.4 | +6.8 to +8.2 |
| lag-1 autocorrelation | primary | **+16.1** | +14.3 to +17.9 | +14.4 to +17.8 | +14.7 to +17.6 |
| same-day refit accuracy | secondary | +5.9 | +4.8 to +7.0 | +4.8 to +7.0 | +5.0 to +6.8 |
| refit minus persistence | secondary | -2.2 | -2.6 to -1.7 | -2.5 to -1.8 | -2.5 to -1.8 |
| unchanged-price share | mechanism | -31.5 | -33.2 to -29.8 | -33.1 to -29.8 | -32.4 to -30.6 |
| long runs | mechanism | +1.7 | +1.4 to +2.1 | +1.4 to +2.1 | +1.4 to +2.0 |
| median trade size | mechanism | -0.18 | -0.30 to -0.07 | -0.30 to -0.08 (p 0.002) | -0.28 to -0.08 |
| events per day | mechanism | +0.54 | +0.45 to +0.64 | +0.46 to +0.63 | +0.45 to +0.63 |
| relative tick | first stage | -2.26 | -2.29 to -2.23 | -2.29 to -2.24 | about -2.26 (inversion grid too coarse) |

### Increases (9 batches, 16 treated, 62 clusters)

| outcome | role | effect | CR1 | wild (p) | permutation (p) |
|---|---|---|---|---|---|
| repeat rate | primary | **-5.6** | -7.4 to -3.9 | -7.3 to -3.9 | -7.2 to -4.1 |
| lag-1 autocorrelation | primary | **-11.6** | -15.5 to -7.8 | -15.4 to -7.9 | -14.6 to -8.7 |
| same-day refit accuracy | secondary | -5.1 | -6.9 to -3.2 | -6.9 to -3.3 | -6.5 to -3.6 |
| refit minus persistence | secondary | +0.7 | -0.0 to +1.5 | +0.0 to +1.4 (0.048) | -0.1 to +1.5 (0.079) |
| unchanged-price share | mechanism | +17.9 | +13.3 to +22.4 | +13.6 to +22.3 | +13.9 to +21.9 |
| long runs | mechanism | -2.0 | -2.9 to -1.2 | -2.8 to -1.2 | -2.7 to -1.3 |
| median trade size | mechanism | +0.20 | -0.01 to +0.41 | +0.02 to +0.39 (0.041) | -0.05 to +0.45 (0.12) |
| events per day | mechanism | -0.22 | -0.48 to +0.05 | -0.47 to +0.03 (0.083) | -0.49 to +0.05 (0.12) |
| relative tick | first stage | +0.59 | +0.25 to +0.94 | +0.27 to +0.93 | +0.38 to +0.82 |

The measured first stage for increases (+0.59, against a design +2.30) is low because of
how relative tick is measured. Resting orders keep printing on the old, finer grid for
days after an increase, and the tick estimator reads the smallest recurring increment. So
the measured tick rises gradually (plot), even though the grid changed at one minute.

### Pooled, per log point of tick change (35 batches, 113 treated, 290 clusters)

| outcome | role | effect per log point | CR1 | wild | permutation |
|---|---|---|---|---|---|
| repeat rate | primary | **-3.15** | -3.55 to -2.76 | -3.53 to -2.78 | -3.44 to -2.87 |
| lag-1 autocorrelation | primary | **-6.72** | -7.45 to -5.99 | -7.42 to -6.02 | -7.23 to -6.22 |
| same-day refit accuracy | secondary | **-2.51** | -2.95 to -2.08 | -2.91 to -2.10 | -2.85 to -2.17 |
| refit minus persistence | secondary | +0.84 | +0.67 to +1.00 | +0.68 to +0.99 | +0.71 to +0.97 |
| unchanged-price share | mechanism | +12.8 | +12.0 to +13.6 | +12.0 to +13.5 | +12.2 to +13.4 |
| long runs | mechanism | -0.76 | -0.91 to -0.62 | -0.90 to -0.63 | -0.88 to -0.65 |
| median trade size | mechanism | +0.083 | +0.038 to +0.129 | +0.040 to +0.127 | +0.043 to +0.124 |
| events per day | mechanism | -0.21 | -0.26 to -0.17 | -0.25 to -0.17 | -0.25 to -0.18 |
| relative tick | first stage | +0.87 | +0.82 to +0.92 | +0.82 to +0.92 | +0.85 to +0.90 |

- **Symmetry.** Per design log point, cuts give -3.27 pp of repeat rate (7.52 / -2.30)
  and increases give -2.44 (-5.63 / 2.30). The direction is the same and the size is
  similar; the increase is somewhat smaller, partly because its grid phases in.
- **Without the two e3 batches** (33 batches, 91 treated, all new data), the pooled
  estimates barely move:
  - repeat rate -3.09 (-3.51 to -2.66);
  - autocorrelation -6.55 (-7.36 to -5.75);
  - refit accuracy -2.52 (-2.99 to -2.04).
- **SOLUSDT 2024-10-14 alone** (one treated contract, 6 controls):
  - repeat rate -11.1, autocorrelation -22.2 and refit accuracy -8.9.
  - SOL has the largest fall of all 7 contracts on each of these, so p = 1/7 = 0.14, the
    smallest possible.
  - Its unchanged-price share rises the most (+19.3).
  - It agrees with the stacked increase estimate in sign, but alone it cannot be
    significant.

## Heterogeneity

**Forest plot (right panel of the PNG).** It shows the repeat-rate DiD for each arm,
sorted by direction and date, with the stacked estimates at the bottom.
- **Cuts:** 26 of 27 arm estimates are positive, and 19 have a clustered interval above 0.
- **The exceptions:**
  - 2023-06-05 is the only negative one (-2.5, -5.5 to +0.5);
  - 2025-04-17 is near zero (+0.8, -3.3 to +4.9);
  - 2023-08-29, 2024-07-25, 2026-04-22, 2026-07-30, 2026-08-24 and 2026-09-17 are
    positive with clustered intervals that touch 0. The permutation p is below 0.05 for
    2023-08-29, 2026-07-30 and 2026-08-24.
- **Size:** the largest cut effects (+13 to +15 pp) are 2024-02-05, 2024-11-04,
  2024-11-28 and 2025-11-27.
- **Increases:** 8 of 9 are negative. 2025-10-08 BNT (+0.4) is the exception. The
  multi-contract arms 2025-09-03 (-5.7, -8.6 to -2.8) and 2026-06-13 (-5.6, -10.1 to -1.1)
  are both clearly negative.

**By year (repeat rate; permutation p in brackets):**

| year | cuts | increases | pooled per log point |
|---|---|---|---|
| 2023 (2 batches, 6 treated) | +0.7 (-2.5 to +3.9) [0.55] | none | -0.29 (-1.67 to +1.10) |
| 2024 (8 batches) | +9.9 (+8.2 to +11.6) | SOL only: -11.1 [0.15] | -4.31 (-5.04 to -3.59) |
| 2025 (11 batches) | +8.5 (+6.8 to +10.2) | -4.8 (-7.7 to -2.0) [0.003] | -3.36 (-4.01 to -2.72) |
| 2026 (14 batches) | +6.2 (+4.5 to +7.8) | -5.6 (-7.7 to -3.4) | -2.66 (-3.26 to -2.05) |

- 2024 to 2026 agree.
- **2023 shows no effect.** Only 2 batches and 6 contracts, and 2023-06-05 goes the
  wrong way. The 2023 pre-trend p is 0.039, so the 2023 comparison is also the least
  clean.
- The effect per log point shrinks a little from 2024 to 2026. Treated contracts in
  later batches are cheaper and thinner, so this may be composition.

## Comparison with the cross-section

OLS slope across contracts of Q14 accuracy (gbm, pp) and of the repeat rate on ln(relative
tick), from `proxies_cross_section.parquet` (the same data as
`proxies_cross_section.md`). 95% intervals from resampling contracts.

| | 2023-06 raw | 2023-06, activity held fixed | 2026-07 raw | 2026-07, activity held fixed | event study, per log point |
|---|---|---|---|---|---|
| accuracy | +0.08 (-0.62 to +0.86) | **-1.22** (-1.99 to -0.40) | -0.69 (-1.33 to -0.03) | **-0.86** (-1.65 to -0.06) | **-2.51** (-2.95 to -2.08), refit accuracy |
| repeat rate | -0.22 (-1.59 to +0.94) | **-3.87** (-4.76 to -2.84) | -0.77 (-1.98 to +0.12) | **-1.91** (-3.69 to -0.66) | **-3.15** (-3.55 to -2.76) |

- **Sign: agrees.** At equal activity, a larger relative tick goes with lower
  predictability across contracts, and changing the tick causes the same direction
  within a contract.
- **Size:**
  - For the repeat rate, the causal slope (-3.2) lies between the two cross-sectional
    slopes (-1.9 and -3.9), so roughly the same size.
  - For accuracy, the causal slope (-2.5) is about 2 to 3 times the cross-sectional one
    (-0.9 to -1.2). The outcomes differ, though: Q14 fits a gradient-boosting model on a
    whole month, while e5 refits a logistic model on each day's first half. So the size
    comparison is only rough.
  - Raw (no activity control), the cross-sectional slopes are near zero. Relative tick
    across contracts is tangled with activity, which is why the earlier work reported the
    partial correlation.

## Conclusion in plain language

Across 35 tick changes from 2023 to 2026, making the price grid finer makes the direction
of the next trade more predictable, and making it coarser makes it less predictable.
- **Cuts (10x finer, 97 contracts):** the chance that a trade has the same direction as
  the one before rises by 7.5 points relative to matched contracts (6.5 to 8.5).
- **Increases (10x coarser, 16 contracts):** it falls by 5.6 points (3.9 to 7.4).
- **Per log point:** each log point of relative tick costs about 3.2 points of repeat rate
  and 2.5 points of same-day refit accuracy.
- **Pre-trends:** none before the change in the primary outcomes.
- **Holds:** in 2024, 2025 and 2026, without the two e3 batches, and for the one large
  liquid increase (SOL).

**Mechanism.** As in e3, the gain is persistence:
- **Cuts:** trades stop bouncing between bid and ask on a coarse grid, and orders walk the
  book in more, smaller same-side steps.
  - The unchanged-price share falls 31 points.
  - Events per day rise 0.54 log points.
  - Long runs rise.
  - Trade size falls a little (-0.18 log points).
- **Increases:** the mirror image.
- **Beyond persistence:** what a model adds falls slightly after a cut (-2.2 points) and
  rises slightly after an increase (+0.7 points).

The cross-sectional pattern (smaller relative tick, more predictable, at equal activity)
has the same sign as this causal effect and a roughly similar size. So relative tick is a
real driver of the predictability differences across coins and over time. It is not
merely a proxy for something else.

## Caveats

- **Main caveat: this is sign persistence, not price predictability or profit.** The
  outcome is the direction of the next aggressor event. Part of the effect is mechanical
  (a finer grid splits the same taker flow into more same-side events), and aggTrades
  cannot separate that from changed behaviour.
- **A budget-driven subset.**
  - Within each batch the cheapest (smallest pre-event) cut contracts were used, and
    cheap increases one at a time.
  - Every third day of the window was used.
  - The results describe small and mid-sized contracts. Large increases (APT, OCEAN in
    2023; BAS, BEAT, AKE) were not run.
  - 25 eligible batches were not run.
  - The selection used only pre-event size, never an outcome.
- **Few increase contracts** (16 in 9 batches; 6 batches with one contract). Clustered,
  wild and permutation intervals agree, but the increase estimate rests mostly on
  2025-09-03 and 2026-06-13.
- **The increase grid phases in** (resting orders on the old grid). So the dose per
  contract is not exactly ln 10, and the pooled per-log-point slope uses the design dose.
  Against the measured first stage (+0.87 pooled), the effect per measured log point would
  be about 15% larger.
- **2023 does not replicate** (2 batches, 6 contracts, pre-trend p 0.039), so the effect
  is established for 2024 to 2026.
- **Controls are matched on activity only,** not on price trend. Binance cuts the tick
  because a price fell, so selection on a price move is possible. Pre-trends are flat in
  the primary outcomes.
- **Other changes on the same day cannot be ruled out batch by batch.** But 35 dates
  spread over three years, in both directions, all pointing the same way, make a
  coincidence an unlikely explanation.
- **Some 2026 cut arms include stock-linked perpetuals** (2026-08-24, 2026-09-17: for
  example KUAISHOU, DJT, ONDS, SKDD). Their estimates are in line with the rest.
- **The refit accuracy outcome is secondary** (added during e3). The primary repeat-rate
  and autocorrelation results were stated in advance and are not affected.
- **Lock-box still to do:** the reserved 2026-08-06 and 2026-10-15 batches remain to be
  run once, with this script's rules unchanged.
