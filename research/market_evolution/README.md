# How crypto futures markets change: why they got more predictable, and which coins die

A 10 to 12 week project in two parts that share one dataset and one theme: what changes in
a market over time, and how to tell real change from a measurement artifact.

## Why this project

Two earlier results leave open questions.

- **Q10** found that the next trade's direction became more predictable between 2023 and
  2025: a model retrained in July 2025 reaches about 66% accuracy, against 60% in June
  2023, on the same 10 contracts. Q10 measured this but did not explain it.
- **Q14** (survivorship study) found that 49 of the 188 contracts trading in June 2023
  stopped trading before July 2026. Some were renamed, most were delisted.

Part A asks **why the market got more predictable**. Part B asks **whether a coin's own
trading reveals that it is about to be delisted**. They connect: if weak coins die and
the survivors are the more predictable ones, part of Q10's rise could be composition,
not change, and the two parts together separate those.

## Ground rules (from the earlier work)

- Every result is checked against a baseline that needs no machine learning.
- Intervals come from resampling whole days, or whole coins when coins are the unit.
- Anything that sets a threshold, a scale or a model choice is fitted on training data
  only; one lock-box test at the end of each part.
- A surprising number is a bug until shown otherwise (the BTC tick-size bug in Q11 and
  the delisted-coin listing bug in Q14 were both found this way).

## Week 0 findings (already measured)

`e0_what_changed.py` on the 10 Q10 symbols x 5 months (`e0_what_changed.json`). Ten
symbols, so these are leads, not conclusions.

- **The change in accuracy moves with smaller trades.** Across 40 within-symbol changes
  from 2023-06, accuracy rises where the median trade size in USD falls (r = -0.41) and
  the share of trades under $1,000 rises (r = +0.40). It also moves with the sign repeat
  rate (r = +0.53), but that link is largely mechanical (a higher repeat rate makes the
  next sign easier to guess), so it describes the change rather than explaining it.
  Activity (r = +0.08) and raw prints per event (r = +0.13) barely matter.
- **Correction (week 0 rerun).** The first run read the monthly file and the daily files
  for some 2023 days, so those days counted twice. That inflated prints per event and
  trade size in 2023 and made prints per event look like a driver (r = +0.51). The
  corrected run reads one file per month; the numbers above are from it.
- **A possible measurement artifact to rule out first.** For SOL and DOGE the raw data
  changed shape: about 2.8 to 3 trades per aggTrade record in 2023 against about 6 in
  2025 to 2026, and far fewer records sharing a millisecond (SOL 27% to 3%). For BTC it
  barely moved. If Binance changed how trades are aggregated, part of the "rise" could
  be a change in what one event means. Week 1 starts by settling this.
- **A natural experiment found in the data.** SOLUSDT's price tick went from 0.001 to
  0.01 between August 2024 and July 2025 (relative tick 0.07 bps in 2024-07, 0.66 bps in
  2025-07); the other 9 contracts kept theirs. The exact date is being researched.
- **Relative tick size moves a lot without any exchange change**, because prices move:
  1000PEPE went from 0.85 bps in 2023-06 to 0.09 bps in 2024-07. That gives within-coin
  variation in a driver Q4b and Q8 already found important.

## Week 1 first pass: the proxy library on the 10 coins (e1_proxies.json)

Correlation of the within-coin change in each proxy, from 2023-06 to each later month,
with the change in fresh-model accuracy (40 changes, 10 coins; 95% intervals from
resampling coins). Descriptive only: 10 coins, and the 4 changes per coin share a base.

| proxy (what it stands for) | r | 95% interval |
|---|---|---|
| share of same-sign runs of 10 or more, sweeps merged (order splitting; partly mechanical) | +0.83 | +0.55 to +0.92 |
| activity in the first second of each minute vs uniform (scheduled algorithms) | +0.60 | +0.21 to +0.78 |
| share of events that are part of a same-millisecond sweep | +0.46 | +0.07 to +0.70 |
| relative tick (tick / price) | -0.42 | -0.64 to -0.07 |
| median trade size in USD | -0.41 | -0.64 to -0.02 |
| share of trades under $1,000 | +0.40 | +0.09 to +0.58 |
| identical consecutive sizes, round sizes, burstiness, activity | between -0.28 and +0.24 | all include 0 |

The leads that point to a mechanism: accuracy rose where trading became more like
scheduled algorithmic execution (activity bunched at the start of each minute, small
child orders, long same-direction runs). That is the order-splitting story in
`notes/predictability_mechanisms.md`. Long runs are close to the outcome itself, so the
minute-boundary and trade-size results are the cleaner evidence. A smaller relative tick
goes with higher accuracy, the opposite sign to the large-tick price-predictability
literature; that is worth a closer look in weeks 3 to 4, because relative tick moves with
price and price moved a lot between snapshots.

## Week 1 second pass: the same proxies across ~430 contract-months (e2)

`data/proxies_cross_section.md` measures every proxy on the Q14 cross-sections (181
contracts in 2023-06, 251 in 2026-07) and correlates it with fresh-model accuracy across
contracts, raw and after partialling out activity (log events). Spearman, 95% intervals
from resampling contracts, descriptive.

| proxy | 2023-06, activity held fixed | 2026-07, activity held fixed | agrees with the 10-coin trend? |
|---|---|---|---|
| median trade size (USD) | -0.42 (-0.56 to -0.29) | -0.40 (-0.50 to -0.28) | yes |
| relative tick | -0.32 (-0.48 to -0.13) | -0.29 (-0.41 to -0.16) | yes |
| long same-sign runs (partly mechanical) | +0.69 (+0.58 to +0.78) | +0.68 (+0.59 to +0.75) | yes |
| activity in the first second of each minute | +0.06 (-0.10 to +0.22) | -0.04 (-0.17 to +0.08) | **no** |

What this means:
- **Smaller trades and a smaller relative tick go with higher predictability both over
  time within a coin and across coins at equal activity.** Two independent views agree,
  so these are the strongest leads for weeks 3 to 4.
- **The minute-boundary pattern does not hold across coins.** Within the 10 coins its
  rise moved with accuracy (+0.60), but at equal activity, coins with more minute-start
  bunching are not more predictable. Either it is a market-wide trend that happened to
  coincide with the rise, or it matters only for the largest coins. This is the
  within-versus-between distinction in `notes/panel_and_causal_methods.md` section 1.2,
  and a good first exercise for the fixed-effects regressions.

## Week 1 third pass: a natural experiment (e3, tick cuts)

`data/e3_event_study.md`: Binance cut the tick 10x on 12 contracts at 2026-03-05 07:00 UTC
(replicated on the 2024-09-20 batch, 10 of 12 contracts), compared with activity-matched
contracts whose tick did not change, 21 days either side.

- **Trade signs became more persistent after the cut, sharply and in both events.**
  Repeat rate +6.7 pp (+4.1 to +9.2) and +8.8 pp; lag-1 sign autocorrelation +0.16 and
  +0.18. No pre-trends by a permutation test. This matches the cross-sectional lead
  (smaller relative tick, more predictable), now with a before-and-after design.
- **The extra predictability is almost all simple persistence.** The prespecified
  outcome (a model frozen on pre-cut days) shows no change (-0.7 pp, -4.4 to +2.9), and a
  model refit each day gains (+3.9 pp, +1.0 to +6.9), but that refit outcome was added
  after seeing the first result, so treat it as exploratory. Either way, the model's edge
  over "repeat the last sign" shrinks after the cut.
- **The mechanism looks like finer price steps letting orders walk the book in more,
  smaller same-side steps:** the share of trades at an unchanged price falls by about
  30 pp, long same-sign runs rise, and trade size falls in the 2024 event.
- **Caveats:** sign persistence is not price predictability; part of the effect may be
  mechanical (a finer grid splits the same order into more same-side events); other
  changes Binance made the same day cannot be ruled out.

## Weeks 3 to 4: panel regressions and the composition split (e4)

`data/e4_panel_regressions.md`. Mean accuracy rose +2.75 pp (+2.07 to +3.49) from
2023-06 to 2026-07 across the cross-section; the one-month noise floor is +0.55.

- **It is not composition.** Contracts present in both months rose +3.41 pp; exits
  (-0.17) and new listings (-0.48) both pulled the average down slightly. Survivorship
  does not create the rise.
- **Trade size is the driver that holds up.** Log median trade size is negative in
  every model (contract fixed effects -3.4 pp per log point, -4.3 to -2.4) and is the
  only driver that survives a Bonferroni correction. In a Gelbach decomposition it
  accounts for more than the whole within-contract rise, because USD trade sizes fell
  by about 84% for nearly all survivors, a shift far outside the cross-sectional range.
- **Relative tick has the right sign but explains none of the rise**, because it did
  not shrink on average between the two snapshots. Its implied effect of a 10x tick cut
  (+0.4 to +1.3 pp on 136 contracts, +2.9 on the 10 coins) has the same sign as the e3
  experiment and is smaller.
- **The fall in trade size is real, not a change in the record format.** Checked on
  DOGE, LINK, AVAX and BTC, 2023-06 vs 2026-07: the median USD size of an individual
  exchange fill (the atomic match, below the aggTrade level) fell by about as much as the
  median aggTrade (DOGE fill $147 to $50, aggTrade $238 to $94; BTC fill $353 to $126,
  aggTrade $686 to $195), while USD volume per day stayed in the same range. Trading
  shifted toward many very small orders on top of the same total volume, which fits
  algorithmic slicing and small automated orders, the order-splitting mechanism.

## Part B weeks 8 to 9: models against the baseline (b1)

`data/b1_models.md`, same six folds and bootstrap as the baselines; the 2026 lock-box was
not touched.

- **Nothing beats the lowest-volume-rank rule with an interval that excludes zero.**
  Full-feature logistic regression: precision at the top 5% 0.101 (0.038 to 0.153)
  against 0.083 for the rule, paired difference +0.018 (-0.008 to +0.042). LightGBM:
  0.078, no better than the rule; early stopping keeps it to 20 to 41 trees, so what it
  learns from earlier years does not carry forward.
- **Open interest is the only extra signal**, the largest share of the tree model's
  attributions and the only feature group that helps both models, though never by a
  significant margin over the rule.
- **The frozen candidates for the lock-box are the full logistic model and the
  lowest-volume-rank rule**, scored once each on 2026.
- Scores are for ranking, not probabilities: calibration did not improve the Brier score.

## Part B lock-box (b2): one run on 2026

`data/b2_lockbox.md`. Frozen configurations from commit b3571a6, scored once on 2026-01 to
2026-07 (3,730 contract-months, 61 delisted contracts, base rate 3.9%).

- **The logistic model beats the lowest-volume rule on the lock-box:** precision at the
  top 5% 0.270 (0.187 to 0.356) against 0.151, paired difference +0.119 (+0.097 to
  +0.145). The direction matches cross-validation and the interval now excludes zero.
- **But more than half of that edge comes from the month that likely contains the
  delisting announcement.** Without it, the gain is +0.049 (-0.016 to +0.081): ahead, not
  decisively. That is the fairer test of predicting a delisting before it is announced.
- **Caveats:** 2026 delistings came in batches (23 distinct stop days), so the intervals
  rest on few independent months; and 16 of the 61 lock-box delistings already appeared
  as positives in the last cross-validation block that informed which model to freeze.

## Weeks 5 to 6: stacked event study over 35 tick-change batches (e5)

`data/e5_stacked_events.md`. 113 treated contract-events in 35 batches (97 cuts, 16
increases including SOLUSDT 2024-10-14), each with its own controls; the 2026-08-06 and
2026-10-15 batches are reserved as the lock-box and were not loaded.

- **Both prespecified predictions hold.** Cuts raise the sign repeat rate by +7.5 pp
  (+6.5 to +8.5); increases lower it by -5.6 pp (-7.4 to -3.9). Pooled, the repeat rate
  changes by -3.15 pp per log point of relative tick (-3.55 to -2.76). No pre-trends in
  the primary outcomes.
- **It matches the cross-section.** At equal activity, the cross-sectional slope of the
  repeat rate on log relative tick is -1.9 to -3.9; the experiment gives -3.2.
- **Limits:** a budget rule kept mostly small contracts (the full design would have been
  about 110 GB); only 16 increases; 2023 batches show no effect; sign persistence is not
  price predictability, and part of it is mechanical.

## Part A: why did predictability rise? (weeks 1 to 6)

### Weeks 1 to 2: describe the change

- **Learn:** panel data (units observed over time); within-unit versus between-unit
  variation; why correlation across 10 coins is weak evidence.
- **Build:** `e0_what_changed.py` collects, for each of Q10's 10 symbols and 5 months,
  the fresh-model accuracy and candidate drivers measured from the raw trades: activity,
  trade size in USD, share of small trades, share of events within 1 ms of the previous
  one, and the sign repeat rate. Extend it to the 2023 and 2026 cross-sections from Q14
  (over 100 coins in both months), which turns 10 data points into a real panel.
- **Checkpoint:** does the accuracy rise happen inside each coin, or is it mostly coins
  with different traits being compared?

### Weeks 3 to 4: test candidate explanations

- **Learn:** regression with controls; fixed effects; omitted-variable bias; why the
  relative tick size (tick divided by price) changes when a coin's price moves even if
  the exchange changes nothing, and why Q4b and Q8 already found it matters.
- **Candidates to test:** more algorithmic order splitting (longer runs of same-sign
  trades of similar size); smaller typical trade size; more bursts of bot trading;
  activity; relative tick size; the mix of coins (composition, from Q14).
- **Build:** a fixed-effects regression of fresh-model accuracy on these drivers across
  coins and months, with intervals from resampling coins.
- **Checkpoint:** which driver survives once the others are controlled for, and which
  ones only looked important because they moved together?

### Weeks 5 to 6: a natural experiment

- **Learn:** event studies and difference-in-differences: comparing coins that were
  changed by an event with similar coins that were not, before and after.
- **Build:** find exchange-side events that changed one candidate driver for some coins
  only (tick-size changes on specific contracts, fee changes, contract migrations), and
  measure predictability before and after against untouched coins. Finding and verifying
  those event dates is part of the work.
- **Checkpoint:** is there an event where the explanation from weeks 3 to 4 predicts the
  outcome before you look?

## Part B: can you tell a dying coin from its trading? (weeks 7 to 11)

### Week 7: define the question without cheating

- **Learn:** look-ahead bias in labels; survival analysis basics (time to event,
  censoring: coins still alive at the end are not "never delisted").
- **Build:** a monthly panel of every USDT perpetual from the archive inventory
  (`data/universe/`), with the delisting month from the archive, renames and mergers
  separated using Q14's classification. At each month-end, the label is "stops trading
  within the next 3 months", using only data up to that month.

### Weeks 8 to 9: features and models

- **Learn:** class imbalance (few coins die in any month); time-based cross-validation;
  precision-recall curves; calibration; Kaplan-Meier curves and the Cox model.
- **Data:** monthly klines (price, volume, number of trades per month) are tiny files,
  so every coin can be covered cheaply; trade-level features (Q9's predictability,
  trade size) for the coins Q14 already processed.
- **Build:** a simple baseline (falling volume alone), then logistic regression and
  gradient boosting, then a Cox survival model. Each must beat the falling-volume rule
  to count.
- **Checkpoint:** does any trade-level feature (predictability, burstiness, trade size)
  add anything beyond volume and price?

### Weeks 10 to 11: lock-box test

- Freeze everything, then score once on the most recent delistings (2026), which were
  not used for any choice. Report precision at a fixed alert rate with intervals from
  resampling months.

## Week 12: write-up

A Q15 and Q16 report in the repository's format, a section on the results page, and a
short plain-language summary of what changed in the market and why.

## Files

- `e0_what_changed.py`: week 0 measurement for Part A (run from the repository root
  with `PYTHONPATH=src`).
- `e0_what_changed.json`: its output.
