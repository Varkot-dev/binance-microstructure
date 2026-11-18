# E3: does a tick-size cut cause a change in trade-sign predictability?

Script: `../e3_event_study.py` (tests: `tests/research/test_e3_event_study.py`). Plot:
`e3_event_study.png`. Numbers: `data/event_study/e3_results.json` (per contract-day
summaries in `data/event_study/<event>/<symbol>/<date>.json`). Run on 2026-11-18.

## Question and the prediction fixed in advance

Weeks 0 to 1 found that, across contracts and over time within a contract, a smaller
relative tick goes with HIGHER next-sign predictability. A tick CUT lowers the relative
tick about 10x overnight while the coin's price, trader population and listing stay the
same. If the cross-sectional link is causal, predictability should rise after the cut
relative to untouched contracts. Expected signs, written into the script before any
data were read:

| outcome | expected after a cut |
|---|---|
| accuracy (frozen model, same-day refit), excess over persistence | up |
| lag-1 sign autocorrelation, sign repeat rate (descriptive, near-circular) | up |
| share of same-sign runs of 10 or more, sweeps merged | up |
| median trade size in USD | down |
| unchanged-price share | down (partly mechanical: a finer grid) |
| relative tick | down (this is the treatment itself) |
| events per day | no prediction |

## Design

- **Primary event: 2026-03-05 07:00 UTC.** 10x tick cut on 12 contracts (4, A2Z, A,
  DRIFT, GRIFFAIN, HEI, LAYER, LISTA, MIRA, MYX, SCRT, ZKC), verified in the trades to the
  half hour (`tick_events.md`). Controls: all 62 distinct matched controls in
  `tick_event_controls.csv` (ranks 1 to 6; no tick change within +/- 30 days, pre-event
  activity within 2x). The notice was published 2026-03-02 06:00 (day -3).
- **Replication: 2024-09-20 06:30 UTC**, 10x cut. To stay inside the 3 GB download
  budget, the two largest treated contracts (APT, TURBO) were left out, and each of the
  other 10 kept only its rank-1 control (9 distinct controls). RPLUSDT has no archive
  files for days -21 to -12, so it has no frozen model (its other outcomes are used).
- **Not run: SOLUSDT 2024-10-14 (tick increase).** The 7 contracts needed about 1.7 GB
  (0.5 GB even with one control), and after the two cut events only 0.07 GB of budget
  was left. The script supports it (`run --event 2024-10-14`; with one treated contract
  the permutation test enumerates all 7 assignments, so its smallest p-value is 1/7).
- **Window:** days -21 to +21. The event day is excluded (never downloaded).
- **Data:** daily aggTrades, SHA-256 checked against Binance's CHECKSUM files, ingested,
  turned into aggressor events (same ms and side merged), summarized, and deleted. Four
  downloads ran at a time, with one contract-day computed at a time. Downloaded: 2.93 GB
  in total, including 0.46 GB fetched twice after a mid-run change (see "Outcome
  added"). Kept: 17 MB of JSON.

### Outcomes per contract-day

- **Frozen logistic model (the planned outcome).** Features: the last 10 signs and sign
  EWMAs with half-lives 4, 16, 64 and 256 events. Features restart each day, and the
  first 1,024 events of a day are a warm-up and never scored. The model is fitted per
  contract on days -21 to -11 only (up to 40,000 events sampled per day), then frozen. It
  scores days -10 to -1 and +1 to +21. Events in the same millisecond as the previous
  event are never scored (as in Q9). Reported as accuracy, and as accuracy minus the
  persistence rule (next sign = last sign) on the same events.
- **Same-day refit (outcome added).** A logistic model with the same features, fitted on
  the scored events of UTC hours 0 to 12 of each day and scored on hours 12 to 24. It is
  computed identically for every contract and day, before and after the event, so it
  measures how predictable the signs are under the rules in force that day. It uses no
  later day, but after the event it does train on post-event data from earlier hours of
  the same day. That is why it is kept separate from the frozen outcome, which never
  sees a post-window day.
- **Descriptive:** lag-1 sign autocorrelation and sign repeat rate on all events.
- **Mechanisms (`microstructure.evolution.proxies`):** median trade size in USD, share
  of same-sign runs of 10 or more (sweeps merged), unchanged-price share (raw records in
  id order), aggressor events per day, relative tick (tick estimated from raw prices /
  median price).

**Outcome added.** On the first 900 contract-days the frozen model showed something
unexpected. The repeat rate and autocorrelation rose sharply after the cut, but
frozen-model accuracy did not move, and its excess over persistence fell by about 7 pp.
A model trained on pre-cut signs is stale once the sign process changes, so it measures
"how well do the old rules still work" rather than "how predictable are the signs". The
run was stopped, the same-day refit was added, and all days were recomputed. The frozen
outcome is reported as planned.

### Estimation

- **DiD:** `y = contract FE + day FE + b * treated x post`, with CR1 standard errors
  clustered by contract (G - 1 degrees of freedom). This is plain TWFE: all treated
  contracts share one date, so the staggered-timing problem (methods note 2.3) does not
  arise.
- **Wild cluster bootstrap:** restricted, Webb 6-point weights, 9,999 draws, run on the
  FWL-transformed data. The 95% CI comes from inverting the test.
- **Permutation test:** treatment is reassigned to random sets of 12 (10) contracts
  among all treated and control contracts, 4,999 draws. The CI comes from inverting the
  test under a constant effect. The smallest attainable p is 0.0002.
- **Pre-trends:**
  - An event study with day -1 as the reference.
  - A permutation test of the pre-period coefficients. The statistic is the dispersion
    of the daily treated-minus-control residual means; treatment is reassigned as above.
  - A linear pre-trend slope (treated x day on pre days, with FE).
- **Not used:** the cluster-robust joint F-test of the ~20 pre coefficients. With 12
  treated clusters its covariance is rank-deficient, and on synthetic panels with
  parallel trends it rejected 84% of the time at 5%. The permutation version rejected 3%
  of the time, and its power against a 0.03 per day pre-trend was 88%.
- **Software:** numpy and scipy only. pyfixest and pandas are not installed in this
  environment, so the two pyfixest bugs in the methods note do not apply. The estimators
  are checked against a dummy-variable regression and on synthetic panels in the tests.

## Coverage

| event | treated | controls | contract-days (of planned) | median scored events per day | frozen models |
|---|---|---|---|---|---|
| 2026-03-05 | 12 | 62 | 3,106 (3,108) | 15,233 | 74 of 74 |
| 2024-09-20 | 10 | 9 | 788 (798) | 22,819 | 18 of 19 |

Missing days: A2ZUSDT days +20 and +21 (no archive file), and RPLUSDT days -21 to -12.

## Pre-trend check

**2026-03-05.**
- Permutation p-values for the pre-period coefficients are above 0.05 for every outcome
  except relative tick (p = 0.018). Relative tick drifts up by 0.012 log points a day
  for treated contracts (their prices fell slightly faster than the controls'), which
  shows on the plot. The pre-period coefficients are 0 to -0.25, against a jump of
  -2.15 at the event.
- Two linear slopes exclude zero:
  - lag-1 autocorrelation: -0.23 x100 a day (-0.45 to -0.02). This pre-trend runs
    against the jump that follows.
  - same-day refit minus persistence: +0.09 pp a day (+0.001 to +0.19). This one runs
    against the post-event fall.
  Projected forward, both would shrink the measured effects rather than create them.
- Frozen-model excess accuracy sits about 1.5 pp above its day -1 value on every pre
  day, so day -1 is low. Dropping the three days after the notice (days -3 to -1) leaves
  every estimate essentially unchanged: excess -7.85 (-9.15 to -6.56), refit +3.85
  (+0.91 to +6.79), repeat rate +6.58 (+4.05 to +9.12). Anticipation does not drive the
  results.

**2024-09-20.** No pre-trend: every permutation p is 0.29 or more, and every slope
interval contains 0.

## Estimates

Effects in the units shown: pp = percentage points; log points = change in the natural log (0.49 is about +63%).
Three intervals per estimate: CR1 cluster-robust, wild cluster bootstrap and
permutation. p-values come from the bootstrap and the permutation test. "<0.001" means
the smallest attainable p.

### 2026-03-05 (12 treated, 62 controls)

| outcome | expected | effect | CR1 95% CI | wild CI (p) | permutation CI (p) | agrees? |
|---|---|---|---|---|---|---|
| accuracy, frozen model (pp) | up | -0.7 | -4.4 to +2.9 | -5.0 to +3.0 (0.75) | -2.9 to +1.4 (0.49) | no effect |
| frozen minus persistence (pp) | up | -7.7 | -9.0 to -6.4 | -9.1 to -6.3 (<0.001) | -8.4 to -7.0 (<0.001) | no (model is stale) |
| accuracy, same-day refit (pp) | up | **+3.9** | +1.0 to +6.9 | +0.6 to +7.2 (0.026) | +2.0 to +5.8 (<0.001) | **yes** |
| refit minus persistence (pp) | up | -3.2 | -4.2 to -2.2 | -4.2 to -2.1 (<0.001) | -4.0 to -2.4 (<0.001) | no |
| lag-1 sign autocorrelation (x100) | up | +15.7 | +11.7 to +19.6 | +11.2 to +20.1 (<0.001) | +13.1 to +18.2 (<0.001) | yes |
| sign repeat rate (pp) | up | +6.7 | +4.1 to +9.2 | +3.7 to +9.5 (<0.001) | +5.1 to +8.3 (<0.001) | yes |
| median trade size (log points) | down | -0.09 | -0.49 to +0.31 | -0.51 to +0.36 (0.68) | -0.34 to +0.17 (0.48) | no effect |
| long runs, sweeps merged (pp) | up | +1.1 | +0.0 to +2.1 | -0.1 to +2.2 (0.072) | +0.5 to +1.7 (0.002) | yes, weak |
| unchanged-price share (pp) | down | -34.4 | -39.1 to -29.7 | -39.2 to -29.3 (<0.001) | -37.0 to -31.8 (<0.001) | yes |
| events per day (log points) | none | +0.49 | +0.18 to +0.79 | +0.16 to +0.81 (0.007) | +0.19 to +0.78 (0.003) | (more events) |
| relative tick (log points) | down | -2.15 | -2.31 to -1.99 | -2.27 to -1.97 (<0.001) | -2.25 to -2.05 (<0.001) | yes (treatment) |

Levels, treated contracts, before and after (controls in brackets):
- same-day refit accuracy: 60.8% to 65.4% (62.0% to 62.7%)
- repeat rate: 57.8% to 64.9% (60.8% to 61.2%)
- unchanged-price share: 53% to 20% (36% to 37%)

Robustness with rank-1 controls only (10 controls): refit +3.9 (+0.5 to +7.2), repeat
rate +6.8 (+3.8 to +9.9), frozen model -1.1 (-5.2 to +3.0), trade size -0.25 (-0.75 to
+0.24).

Contract by contract (each treated contract's post-minus-pre change, minus the mean
change of the controls):
- lag-1 autocorrelation rises for all 12 contracts.
- the repeat rate rises for 11 (A2Z falls).
- same-day refit accuracy rises for 9 (A2Z falls by 6.6 pp; GRIFFAIN and MYX are flat).

Mechanism checks not in the plan: the share of events that continue a same-side sweep
within 1 ms rises by 1.8 pp (1.3 to 2.2), and mean run length with sweeps merged rises
by 0.39 events (0.17 to 0.61). Sweeps split across finer price levels therefore explain
only a small part of the +6.7 pp repeat rate.

### 2024-09-20 replication (10 treated, 9 controls)

| outcome | effect | CR1 95% CI | wild CI (p) | permutation CI (p) | agrees with primary? |
|---|---|---|---|---|---|
| accuracy, frozen model (pp) | +2.7 | -1.5 to +6.8 | -1.3 to +6.5 (0.19) | -1.5 to +6.6 (0.19) | yes (no clear effect) |
| frozen minus persistence (pp) | -6.2 | -12.6 to +0.3 | -12.4 to -0.4 (0.036) | -13.1 to -0.4 (0.002) | yes |
| accuracy, same-day refit (pp) | **+7.5** | +4.8 to +10.2 | +4.9 to +10.0 (<0.001) | +4.8 to +10.2 (<0.001) | **yes** |
| refit minus persistence (pp) | -1.6 | -3.5 to +0.3 | -3.4 to +0.1 (0.072) | -3.6 to +0.2 (0.10) | same sign, weaker |
| lag-1 sign autocorrelation (x100) | +18.1 | +11.4 to +24.7 | +11.7 to +24.5 (<0.001) | +11.3 to +24.9 (<0.001) | yes |
| sign repeat rate (pp) | +8.8 | +5.5 to +12.2 | +5.6 to +12.0 (<0.001) | +5.5 to +12.3 (<0.001) | yes |
| median trade size (log points) | -0.42 | -0.76 to -0.07 | -0.75 to -0.08 (0.016) | -0.76 to -0.08 (0.016) | expected sign here, not in primary |
| long runs, sweeps merged (pp) | +2.2 | +1.4 to +2.9 | +1.4 to +2.9 (<0.001) | +1.3 to +2.9 (<0.001) | yes |
| unchanged-price share (pp) | -27.3 | -34.3 to -20.2 | -34.1 to -20.7 (<0.001) | -34.6 to -20.3 (<0.001) | yes |
| events per day (log points) | +0.27 | -0.20 to +0.73 | -0.16 to +0.71 (0.24) | -0.22 to +0.73 (0.26) | same sign, not significant |
| relative tick (log points) | -2.30 | -2.42 to -2.17 | -2.42 to -2.17 (<0.001) | -2.40 to -2.19 (<0.001) | yes |

Same-day refit accuracy, the repeat rate and autocorrelation all rise for all 10
treated contracts.

## Conclusion in plain language

Cutting the tick 10x made the direction of the next trade more predictable, as the
cross-sectional pattern predicts:
- A model refitted on each day's own morning guesses the afternoon's trade signs 3.9
  points better after the 2026-03-05 cut (interval about +1 to +7), relative to similar
  untouched contracts.
- The 2024-09-20 cut, a different market regime two years earlier, gives +7.5 points
  (+4.8 to +10.2).
- Before the cut there was no comparable drift.

The rise comes almost entirely from **persistence**:
- After the cut, buys follow buys and sells follow sells much more often (repeat rate
  +7 to +9 points, lag-1 autocorrelation +0.16 to +0.18).
- Same-direction runs of 10 or more become more common.
- What a richer model adds beyond "the next sign equals the last one" does not grow. It
  shrinks a little: -3.2 points in 2026, -1.6 points (not significant) in 2024.

So the tick works through the plain persistence channel, not through some more complex
pattern. A plausible reading: with a 10x finer grid, liquidity sits at more price
levels in smaller queues, so one trader's order is filled as a series of small
same-side aggressor events, and trades stop bouncing between the bid and the ask on a
coarse grid. The other measures fit this:
- the unchanged-price share collapses (-27 to -34 points);
- events per day rise (+0.49 log points in 2026);
- runs lengthen.

Trade size in USD fell in the replication (-0.42 log points) but not in the primary
event, so smaller trades are not a consistent mechanism.

A model frozen on pre-cut data does not gain, and its edge over persistence falls by 6
to 8 points. Part of the Q10 drift ("a model retrained in 2025 beats one from 2023")
could be this kind of rule change, which only a retrained model picks up.

## Caveats

- **Binance may have changed other things at the same time.** No other change for
  these contracts on these dates was found in `notes/binance_events.md`, but the bodies
  of the 2026-03-05 notice and of nearby notices were not read. The two events, two
  years apart, agree, which makes a coincident change less likely as the explanation.
- **Cheap, volatile coins.** The 2026 contracts were chosen by Binance because their
  relative tick had become large (11 to 13 bps, MYX 24), presumably after their
  prices fell. Controls are matched on activity only, and the treated contracts' relative tick
  drifted slightly before the event (pre-trend p = 0.018). Results may not carry over to
  BTC-like contracts whose relative tick is already about 0.1 bps.
- **Sign predictability is not price predictability.** The outcome is the direction of
  the next aggressor event, not of the next price move. Higher sign persistence on a
  finer grid says nothing directly about mid-price predictability (which the
  large-tick literature links to a LARGER relative tick, the opposite direction). The
  two should not be conflated, and none of this implies a profit after fees.
- **Part mechanical.** A finer grid splits one taker order into more events at more
  prices. Sweeps within 1 ms explain little of the jump, but child orders spread over
  more than 1 ms are not separable from "real" persistence in aggTrades data.
- **Frozen versus refit.** The planned frozen-model outcome shows no effect on accuracy.
  The positive answer comes from the same-day refit, which was added after seeing the
  stale-model result in the first 900 contract-days (the descriptive repeat rate and
  autocorrelation were planned and point the same way). The refit trains on the first
  half of each day, so it is not a forecast across days.
- **Few treated contracts.** There are 12 and 10 treated contracts. The wild bootstrap
  and the permutation test agree with the clustered intervals in sign and significance,
  except for long runs in 2026 (wild p = 0.07).
- **Smaller replication.** The replication drops APT and TURBO and uses one control per
  treated contract. The SOL increase (opposite-direction test) was not run for budget
  reasons.
