# How crypto futures markets actually work

[![CI](https://github.com/Varkot-dev/binance-microstructure/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Varkot-dev/binance-microstructure/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Varshith Kotagiri · University of Pennsylvania

I wanted to understand what happens inside a crypto exchange one trade at a time: who is
reacting to whom, how prices respond, whether any of it can be predicted, and whether anyone
trades on information they should not have. Everything here is built from Binance's free public
data: tick-by-tick trades for hundreds of futures contracts and daily data for all 900+
perpetual contracts from 2020 to 2026.

Before running each test, I wrote down exactly what it would check and committed that plan to
git, so I couldn't quietly adjust it after seeing the results. A few results that looked exciting
at first fell apart under stricter checks. I've kept those in and said so, because a clear "no"
is still an answer.

## Contents

- [The short version](#the-short-version)
- [1. How the market moves](#1-how-the-market-moves)
- [2. Can it be predicted?](#2-can-it-be-predicted)
- [3. How the market changed over time](#3-how-the-market-changed-over-time)
- [4. Politicians and insider trading](#4-politicians-and-insider-trading)
- [What's next](#whats-next)
- [How it's built](#how-its-built)
- [Run it yourself](#run-it-yourself)
- [Repo layout](#repo-layout)
- [Limitations](#limitations)
- [Licences](#licences)

## The short version

| Topic | What I asked | What I found |
|---|---|---|
| [How the market moves](#1-how-the-market-moves) | Is trading random, or does it follow patterns? | Buys follow buys for a long time, and about 70% of trades are reactions to earlier trades |
| [Prediction](#2-can-it-be-predicted) | Can machine learning predict the next move, and is that worth money? | The next trade's direction is about 60% predictable, but no strategy covers trading fees |
| [Change over time](#3-how-the-market-changed-over-time) | Why did the market get more predictable from 2023 to 2025? | Trades got much smaller, and changes to the minimum price step directly change behaviour |
| [Politicians](#4-politicians-and-insider-trading) | Do politicians' posts move Bitcoin? Did anyone trade before them? | No reliable effect, and no sign of unusual trading before Trump's tariff posts |

The full write-up of the first part, with methods and every number, is in
[docs/report.md](docs/report.md).

## 1. How the market moves

- **Buying and selling come in long streaks.** Whether a trade is a buy or a sell is
  predictable from the trades before it, and that memory fades very slowly. Surprisingly, it
  fades at the same rate whether a contract is heavily or lightly traded (121 contracts
  checked). ([details](results/q1_results.md), [cross-section](results/q4_cross_section.md))
- **Prices absorb those streaks in a balanced way.** The price response grows about 5.4 times
  before levelling off, inside the range theory predicts, so prices stay unpredictable even
  though order flow is not. ([details](results/q2_results.md),
  [16 contracts](results/q5_kernel_panel.md))
- **About 70% of trades are reactions to other trades** rather than fresh decisions, using a
  standard model of self-exciting activity. A model-free check puts it even higher, around
  95%. ([details](results/q6_endogeneity.md), [robustness](results/q6b_kernel_sensitivity.md))
- **Splitting a big order up front costs a bit more on average but is far more predictable.**
  On replayed real trading, buying early cost 2.1 basis points against 0.6 for spreading evenly,
  but its outcomes varied about 17 times less. ([details](results/q7_execution.md))
- **Some patterns from 2023 were gone by 2026.** A link between how busy a contract is and how
  often trades flip direction disappeared, while other patterns appeared, but only among older
  contracts. ([details](results/q8_regimes.md))
- **How you count trades changes the answer a lot.** One market order often shows up as many
  small prints. Counting each print separately inflates the measured streakiness by a large
  margin, and the wrong number still looks plausible next to published values.
  ([details](results/q0_aggregation_effect.md))

## 2. Can it be predicted?

- **The next trade's direction is right about 60% of the time,** but most of that comes from a
  simple rule based on the streaks above. Gradient-boosted trees only add about 3 points.
  ([details](results/q9_sign_prediction.md))
- **Short-term price direction is very predictable and still loses money.** The models score
  well (AUC up to 0.93 for Bitcoin), but the predicted moves cover at most a fifth of trading
  costs. Fees would need to be about ten times lower to break even.
  ([details](results/q11_mid_direction.md), [break-even fees](results/q13_break_even.md))
- **A neural network beats classic models at predicting when the next trade arrives,** on all
  10 contracts tested, but the best classic model already gets about 91% of the way there.
  ([details](results/q12_neural_ceiling.md))
- **A model trained in 2023 goes stale,** but in an unexpected direction: the market became more
  predictable, and the old model misses that. ([details](results/q10_drift.md))
- **Looking only at contracts that survived did not inflate the results.** Across 181 contracts,
  ones later delisted were, if anything, slightly more predictable.
  ([details](results/q14_survivorship.md))

## 3. How the market changed over time

- **Predictability rose within the same contracts from 2023 to 2025,** and it lines up with a
  big drop in trade size: the typical trade shrank by about two thirds while total volume held
  steady. That fits large orders being sliced into many small pieces by algorithms.
- **The minimum price step causes some of this.** Binance changed the tick size of 113
  contracts in 35 batches, which works like a natural experiment. When the step was cut, trades
  repeated direction 7.5 points more often; when it was raised, 5.6 points less.
  ([details](results/q15_market_evolution.md))
- **Very low volume is the best warning sign of a coming delisting.** A model does better on
  held-out 2026 data, but most of its edge comes from the month the delisting is announced.
  ([details](results/q16_delisting.md))

## 4. Politicians and insider trading

- **No politician's posts reliably move Bitcoin within five minutes.** At first, Trump's tariff
  posts seemed to. Once each post was compared only with the same time of week in nearby weeks,
  the effect disappeared. ([ranking of 24 people](research/politics/data/c2_ranking_local.md),
  [first Trump result](research/politics/data/c1_trump_posts.md),
  [Trump follow-up](research/politics/data/c3_trump_tariff_local.md))
- **No sign of anyone trading ahead of Trump's tariff posts.** Trading in the 10 minutes before
  178 tariff posts looks the same as before ordinary posts and at random times. The data is
  anonymous, so this can only show patterns, never who traded.
  ([details](research/politics/data/c4_prepost_trading.md))

## What's next

- **Trading before Binance announcements.** Do prices or volume move before Binance announces
  a listing or delisting? The data is ready and the plan is drafted in
  [research/announcements](research/announcements/).
- **Skill or luck on Hyperliquid.** Every trader's history on Hyperliquid is public. Do any of
  them win more than chance would explain?

Before each project, I check whether someone has already done it. Those reviews are in
[research/novelty](research/novelty/).

## How it's built

Engineering problems I had to solve along the way:

- **Big data on a small disk.** More than 20 GB of extra trade data went through a machine
  with about 7 GB free. Each file is downloaded, checked against Binance's published checksum,
  processed and deleted, and the pipeline picks up where it left off after a crash.
- **Memory.** Months with 90 million trades crashed the standard loader, so the data is now
  processed one day at a time, with tests showing the output is byte-for-byte identical.
- **Locked plans.** Each test's analysis code checks the fingerprint of its written plan and
  refuses to run if the plan was edited.
- **Tests.** About 660 tests. Every estimator is first checked on synthetic data where the
  right answer is known. Linting and the test suite run on every push.
- **Messy real data.** One stray Bitcoin quote that broke a calculation, files counted twice,
  files published after a contract had already closed, and an order book feed that froze
  during the October 2025 crash were all found and handled.

What's in the code:

| Folder | What it does |
|---|---|
| `src/microstructure/data/` | Downloads Binance's files, verifies checksums, converts to Parquet, merges prints from one order into a single trade |
| `src/microstructure/signals/` | Loads data, lines trades up with quotes, adjusts for busy and quiet hours |
| `src/microstructure/estimators/` | The statistical models: trade-direction memory, price response, order-flow imbalance, self-exciting (Hawkes) models |
| `src/microstructure/execution/` | Simulates the cost of buying or selling a large order |
| `src/microstructure/ml/` | Features, models from simple baselines to LightGBM, and a PyTorch neural network |
| `src/microstructure/analyses/` | One script per analysis; each writes a chart, a write-up and the raw numbers to `results/` |
| `research/` | The later projects: market changes, delistings, politicians, announcements |

Built with Python 3.12, Polars, NumPy, PyTorch, LightGBM, Matplotlib, pytest, ruff, uv and
GitHub Actions.

## Run it yourself

```bash
git clone https://github.com/Varkot-dev/binance-microstructure.git
```

```bash
cd binance-microstructure && uv sync
```

Run the tests (no internet needed):

```bash
uv run pytest -m "not network" -q
```

Download one month of Bitcoin trades and run one analysis:

```bash
uv run python -c "
from pathlib import Path
from microstructure.data.catalog import sync
sync(Path('data'), 'BTCUSDT', 'aggTrades', '2023-06', '2023-06')
"
```

```bash
uv run python -m microstructure.analyses.q1_orderflow_memory \
    --root data --out results --symbols BTCUSDT --periods 2023-06 --max-lag 1000
```

Commands for every analysis are in
[docs/report.md](docs/report.md#reproducing-from-a-fresh-clone).

## Repo layout

```
docs/       full write-up of part 1
src/        the pipeline, models and analysis scripts
research/   later projects and the prior-work reviews
results/    charts, write-ups and numbers for each analysis
tests/      the test suite
site/       a small static results page
qfa/        notes from the Penn quant club sessions
```

## Limitations

- Several analyses use a single short window of one to two weeks. Only a few were repeated
  across years.
- Some error bars are too narrow because nearby measurements are correlated. Better intervals
  were computed for one analysis only.
- The self-exciting model gives a lower bound on how much trading is reactive. About half of
  the gap to the model-free estimate is explained; the rest is not.
- The order execution simulation has no queues, delays or partial fills, and the replayed
  market cannot react to the simulated order.
- Only contracts with at least a million trades a month are included, and the 2026 market
  contains different kinds of contracts than 2023 did.

## Licences

- **Code:** MIT (see [LICENSE](LICENSE)).
- **Data from Binance:** comes from data.binance.vision under
  [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Data files here that
  are derived from it are shared under the same licence: credit Binance, non-commercial use
  only, share alike.
- **Politicians' posts:** the text of posts is not stored here, only post IDs, times and topic
  labels.
