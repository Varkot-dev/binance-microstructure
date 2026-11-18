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
