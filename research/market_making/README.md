# Can prediction pay a market maker? A 12-week project

## Why this project, in one paragraph

Q11 showed that the next mid-price move is predictable (AUC up to 0.93) but that the
predicted move never covers a taker's cost (0 of 144 cells). Q13 put a number on the gap:
the break-even taker fee is about 0.5 bps per side, against 5 assumed. A taker pays the
spread; a market maker earns it, and pays a lower fee. So the obvious next question is
whether the same predictions help the other side of the trade. A maker's main cost is
adverse selection: being filled just before the price moves against them. That cost is
exactly what Q11's models predict. This project asks whether those predictions let a
maker avoid the fills that lose money, and at what fee that becomes profitable.

## What the first measurement says (week 0, already done)

`m0_maker_markouts.py` measures, for every trade on 7 training days (2023-06-05 to 11),
what the resting order on the other side earned against the mid price a moment later.
The average is the *realized spread*: half the spread earned, minus the adverse move.
A naive maker that always quotes at the best price breaks even only if the maker fee is
below this number.

| symbol | half spread (bps) | realized spread after 1 s | after 60 s | day-to-day sd (60 s) |
|---|---|---|---|---|
| BTCUSDT | 0.036 | -0.077 | -0.122 | 0.041 |
| ETHUSDT | 0.054 | -0.110 | -0.195 | 0.053 |
| SOLUSDT | 0.470 | -0.337 | -0.534 | 0.206 |
| DOGEUSDT | 0.913 | +0.597 | +0.641 | 0.085 |

- On BTC, ETH and SOL, passive fills lose money **before any fee**. Adverse selection is
  larger than the half spread.
- On DOGE, where the tick is large relative to the price, passive fills earn about
  +0.6 bps before fees. That is still below Binance's regular maker fee (about 2 bps,
  not verified at the source), so a naive DOGE maker also loses at retail fees.
- These numbers are **optimistic** for a real maker. They average over every print at the
  best price, but a new order joins the back of the queue (the queue at the best price
  is about 65 times the typical trade on BTC, ETH and DOGE) and tends to be filled last,
  when the queue is being eaten through, which is when adverse selection is worst.
  Measuring that properly is weeks 2 to 4.

So the project has a sharp, testable question:

> Using only information available at the time, can a maker who skips the fills Q11's
> models flag as toxic turn the realized spread positive, and what fee tier would that
> need?

The likely honest answer is "only at fee tiers far below retail, if at all." Getting a
trustworthy number either way is the point, and the methods are what you learn.

## Data limits that shape the design

- Top-of-book quotes (`bookTicker`) exist for 2023 only, so this is a 2023 study on the
  four symbols with quotes (BTC, ETH, SOL, DOGE). Deeper book levels are not available.
- No queue position is published. Fills must be simulated with an explicit queue model,
  and every result must be shown under a conservative and an optimistic model.
- Timestamps are milliseconds; the order inside one millisecond is unknown.
- Fees vary by account tier and are not verified at the source. They are a parameter,
  swept across a range, never a single assumed number.
- Test days stay untouched until the final weeks. Exploration uses June training days
  only, as Q11 did; Q11's July test window is the lock-box.

## Plan

Each block has something to learn, something to build, and a checkpoint question that
you should be able to answer in your own words before moving on.

### Weeks 1 to 2: the economics of making markets

- **Learn:** bid-ask spread decomposition (order processing, inventory, adverse
  selection); effective vs realized spread; markouts; why market makers lose to informed
  traders (Glosten and Milgrom 1985; Kyle 1985); maker and taker fee structures.
- **Build:** extend the week 0 audit to all 14 June training days, split markouts by
  trade size, by time of day, and by whether the queue was nearly empty. Add day-block
  intervals with `microstructure.ml.evaluate.day_block_ci`.
- **Checkpoint:** why can BTC's realized spread be negative when its spread never
  collapses below one tick?

### Weeks 3 to 4: a queue and fill simulator

- **Learn:** price-time priority; queue position; why ignoring queue position makes
  every backtest look profitable; standard queue models (risk-averse back-of-queue, and
  probabilistic models that assume some cancellations happen ahead of you).
- **Build:** an event-driven simulator for one resting order at the best bid or ask.
  It joins the back of the displayed queue, advances only when trades print at its
  price, cancels or reprices when the best price moves, and records fills with their
  markouts. Two queue models: conservative (no cancellations ahead) and optimistic
  (cancellations ahead are spread pro rata). Test it on synthetic books with known fills.
- **Checkpoint:** how much does the realized spread fall when fills come from the back
  of the queue rather than from every print?

### Weeks 5 to 6: a naive market maker, with inventory

- **Learn:** inventory risk; the Avellaneda-Stoikov model (reservation price and optimal
  spread); position limits; P&L attribution into spread captured, adverse selection,
  inventory drift and fees.
- **Build:** a two-sided maker in the simulator with a position limit and a simple skew
  rule. Report P&L per unit traded and its attribution, across a fee sweep.
- **Checkpoint:** which of the four P&L parts dominates on each symbol, and why does it
  differ between DOGE and BTC?

### Weeks 7 to 9: signals that avoid toxic fills

- **Learn:** probability calibration (reliability curves, isotonic regression), because a
  cut-off on a badly calibrated score is meaningless; precision and recall trade-offs
  when skipping a fill costs spread; feature importance and leakage checks.
- **Build:** a "toxicity" classifier that predicts, at the moment an order would be
  filled, whether its markout will be negative. Start from Q11's L1 features and Q9's
  trade features; add the Q12 timing model's predicted intensity as a feature. Train on
  June training days with Q11's split. Plug it into the maker: pull or skew quotes when
  predicted toxicity is high.
- **Checkpoint:** is the classifier's gain coming from the queue-imbalance feature alone,
  which Q11 showed carries most of the direction signal?

### Weeks 10 to 11: the honest evaluation

- **Learn:** why one lock-box test beats many looks; multiple-testing corrections; how
  to report a null result convincingly.
- **Build:** freeze every choice, then run once on the July 2023 test window. Report P&L
  per unit with day-block intervals under both queue models, for the naive maker and the
  signal maker, across the fee sweep, and the break-even maker fee for each.
- **Checkpoint:** state in two sentences what fee tier, if any, makes this work, and how
  sure you are.

### Week 12: write-up

- A Q15 report in the same format as Q9 to Q13, a section on the results page, and a
  short post explaining the finding to a non-specialist.

## Stretch goals, if time allows

- Learn the quoting policy with reinforcement learning instead of rules, and compare it
  honestly with the rule-based maker.
- Repeat the week 0 audit across the 2026 symbols that have trades only, using the
  trade-price tick as a crude spread proxy, to see how the maker's economics changed.

## Files

- `m0_maker_markouts.py`: the week 0 audit (run from the repository root).
- `m0_maker_markouts.json`: its output for the table above.
