# Pre-registration: who is retail in crypto futures? Validating retail rules against Binance's RPI flag

**Status: DRAFT for review. Not locked. No analysis of the retail flag has been run.**
Items marked **DECISION** need the project owner's choice before the lock.
When approved, this file's sha256 is written into the analysis script, which refuses to run if
the file has changed (the pattern in `research/politics/c4_prepost_trading.py`).

Sources and their verification status are in `RESEARCH.md`. Citations below are short forms.

---

## 1. Question

Crypto research and data vendors commonly treat small trades as retail. Nobody has checked this
against ground truth. Binance's `isRPITrade` flag marks fills in which the taker used the app or
website and not the API, which gives confirmed retail trades for the first time.

1. **Validation.** How well do simple retail rules (small size, round size, round quantity, time
   of day, sweeps) pick out confirmed app and website orders? This is the crypto counterpart of
   Barber et al. (2024), who found that the standard equity rule identifies 35% of real retail
   trades.
2. **Model.** Does a machine-learning model built for labels of this kind do better than the best
   single rule, on days and on contracts it has not seen?

## 2. What the flag means

From Binance's FAQ (verified, see `RESEARCH.md` section 1):

- A flagged fill has an RPI order as maker. RPI orders match only app or website orders, so the
  taker of a flagged fill is an app or website user. We call such takers **retail** throughout.
  This is Binance's definition by channel. A professional clicking in the app counts as retail;
  a hobbyist running a bot does not.
- An unflagged fill is **unlabelled**: its taker may be an API user, or an app user who met
  ordinary liquidity.
- RPI orders are last in the queue at their price and may rest inside the visible spread.

So an app order is flagged through one of two routes:

- **Front route:** an RPI order had the best price on its own. Any app order is flagged,
  whatever its size.
- **Cleared-level route:** the RPI order shared its price with ordinary orders. Only an app order
  large enough to consume the ordinary size first is flagged.

Labels are therefore not a random sample of retail orders (Bekker and Davis 2020 call this
"selected at random", SAR, as opposed to "selected completely at random", SCAR). The cleared-level
route favours large orders mechanically. Section 6 is built around this.

Assumption A1 (no false flags): every flagged fill has an app or website taker. This rests on
Binance's documentation and cannot be tested with public data.

## 3. Disclosures

1. **Exploratory looks before any plan.** On 2026-11-22, a few probes of the latest 1,000 trades
   per contract suggested that flagged trades were often larger than typical trades (medians
   around $3,000 against about $16 on several coins) and that some flagged PEPE fills were under
   $1. These were informal looks at a few thousand rows, with no plan, no fixed sample and no
   test. They motivate hypothesis H1 and the concern about the cleared-level route. They are not
   evidence and will not be reported as results.
2. **Earlier scoping.** `research/memecoins/DATA.md` (branch `claude/memecoin-research`) records
   counts of flagged rows in single 1,000-trade samples (for example 8 and 2 for 1000PEPEUSDT,
   0 for BTC, DOGE, TRUMP, WIF).
3. **Pilot recording for data quality.** On 2026-11-22 the recorder was run for about 35 minutes
   from a development machine to test for gaps (see `DATA_QUALITY.md`). The checks did not relate
   the flag to any attribute. They confirmed only that the flag column contains both values.
   Pilot data are excluded from all analysis.
4. **Sources.** Most literature was verified through search-index text only, because publisher
   sites could not be opened. Each such item is marked in `RESEARCH.md`.

## 4. Data

- **Source.** `src/microstructure/rpi/recorder.py`, run by `.github/workflows/rpi-recorder.yml`,
  polling `https://www.binance.com/fapi/v1/trades`. Free and public.
- **Contracts (15, fixed).** BTCUSDC, ETHUSDC, SOLUSDC, DOGEUSDC, 1000PEPEUSDC, 1000SHIBUSDC,
  WIFUSDC, 1000BONKUSDC, TRUMPUSDC, PNUTUSDC, PENGUUSDC, ETHFIUSDC, 1000PEPEUSDT, DOGEUSDT,
  FARTCOINUSDT.
- **Window.** Day 1 is the first full UTC day after the recorder's first scheduled run on the
  `main` branch. The study uses days 1 to 56 and stops there whatever the results look like.
  Data recorded before the lock are excluded.
- **Rows.** symbol, id, time (ms), price, qty, quoteQty, isBuyerMaker, isRPITrade. Rows recorded
  by two overlapping runs are de-duplicated by (symbol, id). Notional is computed as price times
  qty, because the pilot showed that `quoteQty` is truncated.
- **Lot and tick sizes** come from `exchangeInfo` as saved by the recorder at each run start.
- **DECISION D1: record the order books as well.** `GET /fapi/v1/rpiDepth` (book including RPI
  orders) and `GET /fapi/v1/depth` (book without them) are free. Recording both lets us measure
  when RPI liquidity is at the front, which (a) measures labelling opportunity directly and
  (b) yields confirmed non-retail trades (section 6.4). Recommended. It requires extending the
  recorder before day 1.
- **DECISION D2: backfill with `historicalTrades`.** Needs a free API key stored as a repository
  secret. Recommended as a repair tool for gaps only.

### 4.1 Exclusions (fixed before seeing flags)

- A **recorder gap** is a run of trade ids that are present in the daily archive on
  data.binance.vision but missing from the recording. Ids absent from both are not gaps: the
  pilot showed that Binance's feed itself skips single ids (see `DATA_QUALITY.md`).
- Trades within 2 seconds either side of a recorder gap that has not been backfilled.
- A contract-day with more than 1% of archived trades missing from the recording after backfill.
- A contract-day on which `exchangeInfo` shows the contract was not RPI-enabled.
- Nothing is excluded for looking unusual. No outlier trimming.

### 4.2 Unit of analysis: the reconstructed taker order

One taker order can produce several rows. Rows are grouped into one **order** when they are
consecutive in trade id within a contract and share the same millisecond timestamp and the same
taker side. Order quantity and notional are sums over its rows.

- `L_any` = 1 if any row of the order is flagged. All its rows then belong to a retail order.
- `L_front` = 1 if the order's first row (lowest id) is flagged. This is the front route.

Two takers in the same millisecond on the same side would be merged wrongly. This cannot be
measured from public data and is a stated limitation. All main results are repeated at row level
as a robustness check (section 8.5).

## 5. The retail rules to be tested

All thresholds are fixed here. "Notional" is order notional in USD (USDC and USDT taken as $1).

| Rule | Definition | Hypothesised direction | Why this rule |
|---|---|---|---|
| R1a | notional < $100 | not enriched | Vendor and research practice of treating small trades as retail (BGeometrics; P7 in this repository) |
| R1b | notional < $1,000 | not enriched | Kaiko reports venue averages of $1,000 to $4,000 |
| R1c | notional < $10,000 | not enriched | Chainalysis and CryptoQuant retail threshold; Lee and Radhakrishna (2000) for dollar cut-offs |
| R2 | round notional: within 0.5% of one of $5, 10, 20, 25, 50, 100, 200, 250, 500, 1,000, 2,000, 2,500, 5,000, 10,000. Evaluated only where one lot step is worth less than 0.5% of the target | enriched | Divakaruni and Zimmerman (2024); Bartlett et al. (2024) on dollar-based order entry |
| R3a | round quantity: order quantity has at most 2 significant digits and is at least 10 lot steps | enriched | Cong et al. (2023); Kuo et al. (2015); against: Alexander and Peterson (2007) |
| R3b | full-precision quantity: the last decimal place the lot step allows is non-zero, and the quantity has 4 or more significant digits | depleted | Same sources; algorithms computing a size produce unrounded numbers |
| R4a | weekend (Saturday or Sunday UTC) | enriched | No verified source; tested as common belief |
| R4b | off-clock: timestamp not within the first 1,000 ms of a minute | enriched | "The Quarter-Hour Effect" (2026): scheduled algorithms fire at boundaries |
| R4c | hour of day (24 UTC hours) | descriptive, two-sided | No verified source |
| R5 | sweep: the order fills at 2 or more distinct prices | two-sided | Chakravarty et al. (2012) find sweeps are institutional in equities |
| R6 | R1b and (R2 or R3a) | enriched | The composite a practitioner would build |
| R7 | split pattern: at least 3 earlier orders on the same side of the same contract in the previous 60 seconds have exactly this order's quantity | depleted | Order splitting by execution algorithms makes pieces of large orders look small (O'Hara et al. 2014; Alexander and Peterson 2007 on stealth trading) |

R7 can also fire by coincidence on busy contracts, where many unrelated orders share a common
quantity such as the minimum lot. It is therefore reported twice: for all orders, and for orders
of at least 10 lot steps.

R5 is **mechanism-exposed**: an RPI fill at an improved price adds a price level to a flagged
order. R5 is reported with that caveat and is never used as a model feature.

## 6. Method

### 6.1 Notation and what is identified

y = 1 for a retail taker, s the label, e(x) = P(s=1 | y=1, x) the propensity.
P(s=1 | x) = e(x) P(y=1 | x). Without assumptions neither factor is identified (Gerych et al.
2022; Hastie and Fithian 2013). We therefore never report "the retail share of trading" as a
point estimate.

### 6.2 Identifying assumption

**A2 (conditional SCAR for front labels).** Within a contract and a short time bucket, whether an
app order meets RPI liquidity at the front depends on the state of the book, not on the order's
own size, roundness or precision. Under A2, within a stratum, P(L_front=1 | x) is proportional to
P(y=1 | x), so a classifier trained on `L_front` ranks orders by their probability of being
retail (Elkan and Noto 2008, applied within strata; this is SAR with propensity depending on a
known subset of attributes, Bekker et al. 2019; the stratified comparison follows Phillips et al.
2009).

A2 is not assumed for `L_any`, which is size-biased by the cleared-level route.

A2 could fail if RPI makers quote at the front selectively at moments when a particular kind of
retail order is likely. Section 8.4 tests what can be tested.

### 6.3 Labels used for each purpose

| Purpose | Label | Reason |
|---|---|---|
| Lower bound on the retail share of a rule's orders | `L_any` | Any flagged order is confirmed retail; needs only A1 |
| Lift, recall and model training | `L_front` | Size-neutral under A2 |
| Sensitivity | `L_any` for everything | Shows how much the choice matters |

### 6.4 Confirmed negatives (only if D1 is approved)

A sell (buy) order is a **confirmed non-retail** order if it is unflagged and the book snapshots
immediately before and after it, no more than 2 seconds apart, both show RPI liquidity strictly
better than the best ordinary bid (ask). An app order would have hit that RPI liquidity. With
positives and negatives inside these "RPI-at-front" windows, rules and the model are also
evaluated as an ordinary labelled problem (Hsieh et al. 2019 for learning with biased negatives).
Limitations stated in advance: snapshots are not continuous, and it is undocumented whether app
stop orders and liquidations can take RPI liquidity.

### 6.5 Mechanism checks, run first on training data only

- M1: within orders with both flagged and unflagged rows at one price, do flagged rows come last?
  (Checks the queue rule and the order reconstruction.)
- M2: the share of `L_any` orders that are `L_front`, by contract.
- M3: if D1 is approved, the share of flagged orders arriving when the recorded books show RPI
  liquidity at the front.

If M1 fails in more than 5% of such orders, order reconstruction is judged unreliable and the
row-level analysis becomes primary. This switch is decided by that number alone.

### 6.6 Features (order level, known at the moment of the order)

Order features:
1. log10 notional
2. log10 quantity in lot steps
3. number of significant digits of the quantity
4. trailing zeros of the quantity in lot steps
5. distance, in percent, to the nearest round notional of R2
6. indicator that the quantity is full precision (R3b)
7. taker side

Timing features:
8. hour of day (UTC), 9. day of week, 10. millisecond within the second,
11. second within the minute, 12. time since the previous order in the contract (log ms),
13. time since the previous order on the same side (log ms)

Context features, from the 60 seconds before the order, excluding the order itself:
14. order count, 15. total notional, 16. signed order-flow imbalance, 17. realised volatility of
trade prices, 18. last price change in ticks, 19. median order notional

Splitting features, from earlier orders on the same side of the same contract, excluding the
order itself. They target execution algorithms that cut a large order into equal pieces
(O'Hara et al. 2014; Alexander and Peterson 2007):
20. same-size count: number of such orders in the previous 60 seconds with exactly this order's
    quantity
21. same-size share: feature 20 divided by the number of same-side orders in the previous 60
    seconds (0 if there are none)
22. spacing regularity: take this order and the same-side orders of exactly its quantity in the
    previous 300 seconds; if there are at least 4 in total, the coefficient of variation of the
    gaps between consecutive ones (low means evenly spaced, as a timer would produce);
    otherwise missing

These use quantities and times only, never other orders' flags.

Excluded on purpose because the matching rule affects them for flagged orders: number of rows,
number of price levels, the order's execution price relative to earlier prices, row sizes, and
anything computed from other orders' flags.

### 6.7 Model

- **Primary.** Gradient-boosted trees (LightGBM) trained to predict `L_front` from features 1 to
  22 plus contract and UTC-hour identifiers as controls: the "non-traditional classifier" of
  Elkan and Noto (2008). The score is used only to rank orders within a contract-day.
- **Robustness 1.** SAR-EM (Bekker et al. 2019), with the propensity model restricted to contract,
  timing and context features and the class model restricted to order and splitting features. This is an
  exclusion restriction and is reported as one.
- **Robustness 2.** The same primary model trained on `L_any`, and a non-negative PU risk model
  (Kiryo et al. 2017) over an assumed class-prior grid of 5, 10, 20, 40 and 60%, as the benchmark
  that ignores selection.
- **Tuning.** On the validation period only, over a fixed grid: learning rate {0.03, 0.1}, leaves
  {31, 127}, minimum rows per leaf {200, 2,000}, rounds chosen by early stopping. Selection
  metric: mean within contract-day precision in the top 5%. Seed 20261122.

## 7. Split

| Part | Days | Use |
|---|---|---|
| Train | 1 to 28 | Fit models; mechanism checks M1 to M3 |
| Validation | 29 to 35 | Tuning and model choice |
| Embargo | 36 | Dropped (López de Prado 2018) |
| Test | 37 to 56 | Opened once, after models are frozen and committed |

**Held-out contracts.** BTCUSDC, 1000PEPEUSDT and PNUTUSDC are removed from training and
validation and used only for testing transfer (blocked validation, Roberts et al. 2017). They
were chosen by a fixed rule before any data: sort by sha256 of the symbol name, take the first
major (BTC, ETH, SOL) and the first two others with different base coins.

The rules of section 5 have no parameters to fit. They are evaluated on the test period for the
headline numbers and on the full window as a supplement.

## 8. Evaluation

### 8.1 Measures, for each rule and for the model

Computed within each contract-day, then averaged over contract-days weighted by order count.

- **Base rate:** share of orders with the label.
- **Coverage:** share of orders the rule selects.
- **Flagged share (precision against the flag):** share of selected orders that are labelled. With
  `L_any` this is a lower bound on the true retail share of the selected orders under A1.
- **Lift:** flagged share divided by the base rate. Above 1 means the rule concentrates confirmed
  retail orders.
- **Recall of flagged orders:** share of labelled orders the rule selects. This is the analogue of
  Barber et al.'s 35%, with the caveat that it is recall among retail orders that met RPI
  liquidity.
- **Precision at k and lift at k** for the model: top 1%, 5% and 10% of orders by score within the
  contract-day. For a fair comparison with a rule, the model is also evaluated at k equal to that
  rule's coverage.
- Each measure is reported by order count and by notional.

### 8.2 Uncertainty

Cluster bootstrap that resamples whole contract-days, 2,000 draws, percentile 95% intervals
(Field and Welsh 2007). Because contracts move together on a given day, the same bootstrap
resampling whole days is reported alongside; if the two disagree on significance, the day-level
result is the one stated (Cameron, Gelbach and Miller 2008 on few clusters: the test period has
only 20 days, which is noted wherever the day-level interval is used).

### 8.3 Hypotheses and how each is decided

Test period, label `L_front`, order level, contract-day bootstrap.

- **H1 (size rules fail).** For each of R1a, R1b, R1c, lift is at most 1. Decision: H1 holds for a
  rule if the upper end of the 95% interval for lift is below 1; it is rejected if the lower end
  is above 1; otherwise inconclusive. Disclosure 1 in section 3 motivated this hypothesis.
- **H2 (round and precise sizes carry signal).** Lift above 1 for R2 and R3a, below 1 for R3b.
- **H3 (the model beats the best rule).** Let R* be the rule with the highest lift on the
  validation period among those with coverage of at least 1%. On the test period, the model's
  precision at k = coverage(R*) exceeds R*'s flagged share, and the 95% interval of the
  difference excludes zero.
- **H4 (transfer).** On the three held-out contracts, the model's lift in the top 5% has a 95%
  interval above 1.

R4a, R4b, R5, R6 and R7 are reported with intervals as secondary. R4c is descriptive.
Multiple testing: the eight confirmatory tests (three in H1, three in H2, H3, H4) are corrected
with Holm's method at 5% (Holm 1979, *Scandinavian Journal of Statistics* 6, 65-70).

### 8.4 Checks on the assumptions

- **SCAR test.** The test of Teisseyre et al. (2024) on the training data, for `L_any` and
  `L_front`. Expected: rejected for `L_any`. Reported whatever it shows.
- **Stratum robustness.** Repeat 8.1 within contract-hour instead of contract-day.
- **Availability matching.** Repeat 8.1 using only orders that have a flagged row from a different
  order in the same contract within 60 seconds either side: moments when RPI liquidity was
  demonstrably active (Phillips et al. 2009). The order's own flags do not count, to avoid
  selecting on the outcome.
- **Tick-constraint split.** Repeat by contract. Where the spread is usually one tick, RPI orders
  cannot rest inside it, so `L_front` should be rare (M2); a large difference in conclusions
  between such contracts and the others is reported as evidence about A2.
- **Confirmed negatives** (if D1): ordinary precision, recall and AUC inside RPI-at-front windows.

### 8.5 Robustness reported in every case

Row-level unit instead of orders; `L_any` instead of `L_front`; notional weighting; full window
instead of test period for the rules.

## 9. What will and will not be claimed

Will be claimed, if the data support it:
- Lower bounds on the retail share of orders selected by each rule.
- Whether each rule concentrates or dilutes confirmed retail orders, under A2.
- Whether the model ranks confirmed retail orders better than the best rule, on unseen days and
  unseen contracts.

Will not be claimed:
- The share of all trading that is retail, or a calibrated probability that a given trade is
  retail. Reported only as ranges under stated class priors.
- Anything about retail traders' profits. Flagged fills receive price improvement by design, so
  they are unsuitable for markout studies without adjustment.
- That results carry over to retail users of the API, to other venues, or to contracts without
  RPI liquidity.

Known threats: the two-route selection (section 2); undocumented treatment of stop orders and
liquidations; order reconstruction errors; RPI maker behaviour changing over time; the app's
percentage-of-balance slider producing unrounded sizes; a one-month test period; splitting
detection that only catches equal-sized pieces, so algorithms that randomise piece sizes are
missed.

## 10. Deviations and lock

- Any departure from this plan is listed in a `DEVIATIONS.md` file with date and reason, and the
  affected result is labelled exploratory.
- Analyses not listed here are labelled exploratory.
- Lock procedure: after approval, commit this file, record its sha256 in the analysis script as
  `PREREG_SHA`, and have the script exit if the hash differs. The lock commit precedes day 1.
- Results are reported whether or not the hypotheses hold.
