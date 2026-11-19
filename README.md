# Binance market microstructure

[![CI](https://github.com/Varkot-dev/binance-microstructure/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Varkot-dev/binance-microstructure/actions/workflows/ci.yml)
[![Results site](https://img.shields.io/badge/results-varkot--dev.github.io-blue)](https://varkot-dev.github.io/binance-microstructure/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Varshith Kotagiri · University of Pennsylvania

A study of how crypto futures markets work trade by trade, built entirely from Binance's
public data (data.binance.vision): tick-level trades for hundreds of contracts and daily
data for all 900+ USDT-M perpetual contracts, 2020 to 2026. It runs in four parts, each one asking a sharper question than the last.

| Part | Question | Headline answer |
|---|---|---|
| **1. Market mechanics** (Q0 to Q8) | How predictable is order flow, how do prices respond, how much trading reacts to other trading? | Long memory in trade signs; about 70% of trades are reactions to other trades |
| **2. Prediction** (Q9 to Q14) | How much can machine learning predict, and does it pay? | Direction is about 60% predictable; no strategy covers trading costs |
| **3. How the market changed** (Q15, Q16) | Why did predictability rise from 2023 to 2025? What warns of a delisting? | Smaller trades; tick size causes persistence (35 natural experiments); low volume flags delistings |
| **4. Politicians and insider trading** (C1 to C4) | Do politicians' posts move crypto? Did anyone trade before them? | Not robustly, and no evidence of unusual trading before Trump's tariff posts |

Every test that could be tuned to the data was written down and fingerprinted (sha256) in git
**before** the data was opened, and several first results that looked positive were overturned
by stricter checks. Those reversals are reported, not hidden.

[Summary of every result](#results-index) · [Engineering](#engineering-highlights) ·
[Full write-up of part 1](docs/report.md) · [Per-question results](results/)

## Key findings

### Part 1: market mechanics

- **Order flow has long memory, and its exponent does not depend on liquidity.** BTC γ̂ = 0.3803,
  ETH γ̂ = 0.2380. Across 121 symbols, γ̂ against log-activity has slope −0.0112 and R² 0.0003.
  [q1](results/q1_results.md), [q4](results/q4_cross_section.md)
- **The price response rises 5.39× before plateauing,** inside the 3.5 to 6.9× band predicted from
  the memory exponent, and 12 of 16 deconvolved impact kernels satisfy the critical-balance
  condition that keeps prices diffusive. [q2](results/q2_results.md),
  [q5](results/q5_kernel_panel.md)
- **About 70% of trades are reactions to other trades.** The median Hawkes branching ratio is
  0.7070 from the exponential-kernel MLE (a lower bound) and 0.959 from the model-free
  count-variance estimator, which reads higher on 41 of 41 symbols. Adding a second kernel
  timescale raises the MLE median to 0.854 (beyond simulation noise on 39 of 41 symbols) and
  closes a median 54% of that gap; the extra component decays in about 7 seconds.
  [q6](results/q6_endogeneity.md),
  [q6b](results/q6b_kernel_sensitivity.md)
- **Front-loading an order trades a stochastic cost for a deterministic one.** On replayed flow
  for 6 symbols, front-loading costs more on average (2.11 vs 0.55 bps of arrival mid for TWAP)
  but its standard deviation is 1.75 bps against 29.3 for TWAP, about 17× lower, and lower on
  every symbol. This is a cost model, not a backtest.
  [q7](results/q7_execution.md)
- **The sign-flip law fades by 2026.** The slope of flip probability on log-activity is +0.1114
  (R² 0.2632) in June 2023 and +0.0006 (stderr 0.0126, n = 231) on the July 2026 market's own
  symbol list. On the 39 contracts present in both periods, its t-statistic fell from 4.0 to 1.1.
  [q8](results/q8_regimes.md)
- **The memory exponent later starts depending on liquidity, but only for older contracts.**
  On the same 39 contracts, γ̂ went from no activity dependence (t 1.0) to a clear one (t 3.6);
  the 192 contracts listed since show little. [q8](results/q8_regimes.md)
- **Measurement choices move the answers a lot.** Computing statistics on raw prints instead of
  aggressor events inflates γ̂ by 0.29 to 0.50. Exponential Hawkes fits that lock onto a fast
  kernel mode understate the branching ratio, which made 2024 look like a collapse in
  endogeneity (0.71 to 0.39) that the kernel-free estimator does not show (0.96 to 0.93).
  [q0](results/q0_aggregation_effect.md), [q8](results/q8_regimes.md)


### Part 2: prediction with machine learning

- **The next trade's direction is about 60% predictable,** but three quarters of that edge is
  already in a linear predictor built from the measured memory; gradient-boosted trees add about
  3 points, mostly from trade size and timing. [q9](results/q9_sign_prediction.md)
- **Short-horizon price direction is very predictable (AUC up to 0.93 for BTC) but never pays a
  taker:** the predicted move covers at most about a fifth of round-trip cost in 0 of 144 cells,
  and would need fees about ten times lower. [q11](results/q11_mid_direction.md),
  [q13](results/q13_break_even.md)
- **A neural point process beats Hawkes models for trade timing on 10 of 10 contracts, but the
  best Hawkes model already captures about 91% of its gain.** [q12](results/q12_neural_ceiling.md)
- **Studying only survivors did not bias the headline:** across 181 contracts, those later
  delisted were if anything slightly more predictable at equal activity.
  [q14](results/q14_survivorship.md)

### Part 3: how the market changed

- **Predictability rose from 2023 to 2025 inside contracts, not through which contracts
  survived, and it lines up with much smaller trades** (the median exchange fill fell by about
  two thirds while daily volume held), consistent with algorithmic order slicing.
- **Tick size causes trade-sign persistence, in both directions:** across 35 Binance tick-change
  batches (113 contracts, matched controls, no pre-trends), cuts raise the repeat rate by 7.5
  points and increases lower it by 5.6. Held-out batches point the same way, more weakly.
  [q15](results/q15_market_evolution.md)
- **Very low volume flags coming delistings;** a model beats the volume rule on held-out 2026
  data, but more than half of its edge comes from the month that holds the announcement.
  [q16](results/q16_delisting.md)

### Part 4: politicians and insider trading

- **No politician's posts reliably move Bitcoin within five minutes** once each post is compared
  only with nearby weeks. An early "Trump's tariff posts move Bitcoin" result did not survive
  that comparison. [ranking](research/politics/data/c2_ranking_local.md),
  [Trump](research/politics/data/c3_trump_tariff_local.md)
- **No evidence of unusual trading before Trump's tariff posts:** order flow in the 10 minutes
  before 178 posts looks like order flow before ordinary posts and at random times. The data
  is anonymous, so this can show patterns, never who traded.
  [investigation](research/politics/data/c4_prepost_trading.md)

## Engineering highlights

- **Disk-bounded streaming pipeline.** More than 20 GB of extra tick data streamed through a
  machine with about 7 GB free: download, verify the published SHA-256 checksum, ingest,
  compute, delete, with resumable per-unit caches so crashes and restarts lose nothing.
- **Memory under control.** 90-million-record months crashed the standard loader; events are now
  built one day at a time and large archives parsed in chunks straight from the zip, with tests
  proving byte-identical output.
- **Locked analyses.** Each pre-registration's sha256 is checked by the analysis code, which
  refuses to run if the plan changed; plans are committed before any result exists.
- **Tests and CI.** About 660 tests (estimators against synthetic data with known answers,
  analyses on fixtures); ruff and the offline suite run on every push.
- **Real-data debugging.** A single stray off-grid BTC quote that broke tick estimation,
  double-counted daily and monthly files, "ghost" files published after contracts die, and a
  frozen order-book depth series around the 2025-10-10 crash were each found and handled.

## What I built

**Data pipeline** (`src/microstructure/data/`). Downloads Binance's monthly and daily dumps,
verifies every file against its published SHA-256 checksum, and converts zipped CSVs to Parquet
with a normalized schema (the dumps differ across years in whether they have a header row and
whether timestamps are in milliseconds or microseconds). `events.py` collapses same-millisecond,
same-side prints into one aggressor event, which turned out to matter more than anything else
downstream (Q0).

**Signals** (`src/microstructure/signals/`). Lazy Polars loaders, trade-to-quote alignment (each
trade gets the mid strictly before it), and a business-time transform that rescales event times
by the intraday activity profile so that seasonality is not mistaken for self-excitation.

**Estimators** (`src/microstructure/estimators/`), each tested against synthetic data with a
known answer before touching real data:
- `acf.py`: FFT sign autocorrelation and log-log power-law fits for the memory exponent γ.
- `response.py`: the response function R(ℓ) (Bouchaud et al. 2004).
- `propagator.py`: deconvolution of the impact kernel G(ℓ) from R(ℓ) and the sign ACF.
- `ofi.py`: order-flow imbalance and its price regression (Cont, Kukanov & Stoikov 2014).
- `hawkes.py`: Hawkes simulation, exponential and sum-of-exponentials MLE, the count-variance
  branching estimator, and a piecewise-baseline fit that separates slow baseline drift from
  long memory.

**Execution simulator** (`src/microstructure/execution/`). Replays recorded flow and charges a
parent order for adverse drift, half-spread and its own impact under three schedules: TWAP,
front-loaded and flow-reactive.

**Machine learning** (`src/microstructure/ml/`, `src/microstructure/evolution/`). Causal trade
and quote features, a model ladder from majority class to LightGBM, a neural temporal point
process (PyTorch), drift attribution, and a library of order-flow proxies (order splitting, size
clustering, burstiness, relative tick).

**Research projects** (`research/`). Market evolution (panel regressions, a contract lifecycle
table for every Binance USDT-M perpetual, a monthly panel, stacked event studies of tick
changes), politicians and crypto (pre-registered event studies and a ranking), the delisting
model, and prior-art reviews of each idea in `research/novelty/`.

**Analyses** (`src/microstructure/analyses/`). One script per question, Q0 to Q16. Each writes a
figure, a Markdown write-up and a JSON/Parquet artifact to `results/`. Q8 compares six regimes
from the saved artifacts alone, refits every regression independently, and checks slope
significance, survivorship, kernel mode and cohort composition.

**Results site** (`site/`). A static page with interactive Plotly charts built from the result
JSON, deployed with GitHub Pages.

Stack: Python 3.12, Polars, NumPy, Matplotlib, pytest, ruff, uv, GitHub Actions.

## Results index

| Question | What it measures | Result |
|---|---|---|
| Q0 | Raw prints vs aggressor events | [raw γ̂ inflated by 0.29 to 0.50](results/q0_aggregation_effect.md) |
| Q1 | Sign autocorrelation, BTC and ETH | [long memory, BTC γ̂ 0.3803, ETH 0.2380](results/q1_results.md) |
| Q1b | Short-lag zigzag in the ACF | [real structure, not a tie-break artifact](results/q1b_zigzag.md) |
| Q2 | Response function R(ℓ) | [rises 5.39×, inside the predicted 3.5 to 6.9×](results/q2_results.md) |
| Q3 | Price change vs order-flow imbalance | [linear, R² 0.40 vs 65 to 70% in equities](results/q3_results.md) |
| Q4 | 121-symbol cross-section, 2023-06 | [γ̂ flat in activity (R² 0.0003), flip probability not (R² 0.2632)](results/q4_cross_section.md) |
| Q4b | Tick-size confound for flip probability | [activity dominates; tick size borderline (t 2.09)](results/q4b_tick_confound.md) |
| Q5 | Deconvolved impact kernel, 16 symbols | [critical balance holds for 12 of 16](results/q5_kernel_panel.md) |
| Q6 | Hawkes branching ratio, 41 symbols | [median 0.7070, MLE lower bound](results/q6_endogeneity.md) |
| Q6b | Two- and three-timescale Hawkes kernels | [K=2 lifts n̂ 0.707 → 0.854, closes 54% of the estimator gap](results/q6b_kernel_sensitivity.md) |
| Q7 | Execution schedules on replayed flow | [front-loaded: higher mean, 17× lower sd](results/q7_execution.md) |
| Q8 | Six regimes, 2023-06 to 2026-07 | [flip law gone by 2026; γ̂ break within the 2023 cohort](results/q8_regimes.md) |
| Q9 | Next-trade-sign prediction, 10 contracts | [about 60%; 74% of the gain is the linear memory predictor](results/q9_sign_prediction.md) |
| Q10 | Does a 2023 model go stale? | [yes, by missing a gain: the market became more predictable](results/q10_drift.md) |
| Q11 | Mid-price direction from quotes, and cost | [AUC up to 0.93; edge covers cost in 0 of 144 cells](results/q11_mid_direction.md) |
| Q12 | Neural point process vs Hawkes for timing | [network wins 10 of 10; Hawkes gets about 91% of the way](results/q12_neural_ceiling.md) |
| Q13 | Break-even fee and timing value | [needs fees under about 0.5 bps per side](results/q13_break_even.md) |
| Q14 | Survivorship across 181 contracts | [little bias; the 60% headline is if anything low](results/q14_survivorship.md) |
| Q15 | Why predictability rose; tick size as a cause | [smaller trades; 35 natural experiments both ways](results/q15_market_evolution.md) |
| Q16 | Predicting delistings | [low volume flags them; model edge is mostly the announcement month](results/q16_delisting.md) |
| C1 | Trump's Truth Social posts and BTC, pre-registered | [tariff posts looked positive at first](research/politics/data/c1_trump_posts.md) |
| C2 | Politician ranking (24 people, 2020 to 2023) | [no one survives time-local controls](research/politics/data/c2_ranking_local.md) |
| C3 | Trump-only tariff follow-up | [does not support an effect](research/politics/data/c3_trump_tariff_local.md) |
| C4 | Trading before Trump's tariff posts | [no evidence](research/politics/data/c4_prepost_trading.md) |

## Method notes

- **Aggressor events.** Prints from one market order are merged before any statistic is
  computed. Skipping this inflates lag-1 sign autocorrelation about 15×, and the inflated number
  still falls inside the published range, so a literature check alone would not catch it (Q0).
- **Business time.** On a regime-switching Poisson process with no self-excitation at all, both
  branching-ratio estimators report near-criticality (n̂ = 0.934, α̂ = 0.976) unless event times
  are deseasonalized first. On the real panel the correction is small (median −0.0003), because
  crypto trades around the clock.
- **Fixed vs native universe.** The later regimes are run on the 2023 symbol list, to follow what
  happened to that panel, and July 2026 is also run on that month's own symbol list (371
  symbols, 231 above the one-million-event floor), which takes the 2023 panel's survivorship out
  of the comparison.
- **Kernel mode.** In later months many exponential Hawkes fits lock onto the fast component of
  a multi-timescale kernel and understate the branching ratio. Regimes are compared on slow-mode
  fits, the kernel-free count-variance estimator, and symbols paired across months.
- **Cohort split.** The 2026 universe is split into contracts shared with 2023 and those listed
  since, which separates a change within the same contracts from a change in composition.
- **Slope significance.** A cross-regime "same sign" verdict only counts slopes at least two
  standard errors from zero.

## Reproduce

```bash
git clone https://github.com/Varkot-dev/binance-microstructure.git
cd binance-microstructure
uv sync

# Offline test suite (estimators against synthetic ground truth, analyses on fixtures)
uv run pytest -m "not network" -q
uv run ruff check src/ tests/

# Download and ingest one month of one symbol (checksum-verified)
uv run python -c "
from pathlib import Path
from microstructure.data.catalog import sync
sync(Path('data'), 'BTCUSDT', 'aggTrades', '2023-06', '2023-06')
"

# Run one analysis (writes results/q1_*.png/.md/.json)
uv run python -m microstructure.analyses.q1_orderflow_memory \
    --root data --out results --symbols BTCUSDT --periods 2023-06 --max-lag 1000
```

Commands for every question, including the regime runs and the Q8 comparator, are in
[docs/report.md](docs/report.md#reproducing-from-a-fresh-clone). Q8 only reads committed results
and runs in seconds. CI runs ruff and the offline suite on every push; the Pages workflow
rebuilds `site/data/*.json` from `results/` and fails if the committed copies are stale.

## Repo layout

```
docs/report.md   full write-up: methods, numbers, caveats, reproduction
src/microstructure/
  data/          download, checksum, Parquet ingest, aggressor-event collapse
  signals/       loaders, trade/quote alignment, business-time transform
  estimators/    ACF and γ, response, propagator, OFI, Hawkes
  execution/     execution-cost replay simulator
  ml/            features, model ladder, drift, neural point process
  evolution/     order-flow proxy library
  analyses/      one script per question, Q0 to Q16
  synthetic.py   generators with known answers for the tests
research/
  market_evolution/  why predictability changed: data, regressions, event studies
  politics/          politicians' posts and crypto (pre-registered)
  announcements/     trading before listing and delisting announcements (in progress)
  novelty/           prior-art reviews: which ideas are new
qfa/             Penn quant club session materials and notes
tests/           estimator tests on synthetic data, analysis tests on fixtures
results/         figures, per-question write-ups, JSON/Parquet artifacts
site/            static results site; build_data.py derives site/data/*.json
```

## Limitations

- Q2, Q3, Q5 and Q7 each use one short window (14, 14, 7 days and a 4-day evaluation window).
  Only Q4 and Q6 were repeated across regimes, with one month per year after 2023.
- Q1 to Q3 standard errors are OLS and too small, since ACF values at adjacent lags are correlated.
  Block-bootstrap intervals are done for Q5 only.
- Every exponential-kernel branching ratio is a lower bound. A second kernel timescale explains
  about half of the MLE vs count-variance gap; the rest is unattributed. A likelihood-ratio test
  meant to tell slow baseline drift from long memory was inconclusive on all 41 symbols.
- Q7 has no queue, latency or partial fills, and replayed flow cannot react to the simulated
  order. The impact kernels it uses were estimated on the same week it evaluates; only the
  reactive schedule's parameters are held out.
- The cross-section only includes symbols above one million aggressor events a month, and the
  2026 universe differs in composition from 2023 (tokenized-equity perpetuals, USDC-margined
  pairs). The shared cohort is 39 contracts.
