# QFA session notes and project ideas

> **Correction (from `research/novelty/qfa_derived_ideas.md`):** the Binance option files
> do contain same-day expiries on 85 of 147 BTC days in 2023-05-18 to 2023-10-23, but total
> volume is only about $4M, so the conclusion stands: a crypto 0DTE study is not feasible
> on free Binance data. Statements below that there are "no daily expiries" are wrong on
> that point.


Notes on the Quant Finance Academy (QFA) materials in `qfa/`, written 2026-11-19. Numbers are
quoted as they appear in the documents. There are five session folders, not four:
2026-10-21, 2026-10-28, 2026-11-04, 2026-11-11 and 2026-11-18.

---

## Part 1. Sessions

### 2026-10-21: From Yield Curves to Trading (Dieckmann), slides plus dataset

**Slides (`From_Yield_Curves_To_Trading.pdf`, 20 pages).** Question: can a few factors summarize
the movements of Treasury yields across maturities, and can one factor be turned into a trade?
Method: principal component analysis (PCA) of monthly yield changes. PCA takes the covariance
matrix of yield changes; its eigenvectors are the factor loadings, the projections of each month
onto them are the factor scores, and the eigenvalues rank the factors by variance explained.
Finding: the first three factors are level, slope and curvature (the Litterman and Scheinkman
(1991) result) and "explain 98.7% of the variation in monthly yield changes." The slides then
regress the factors on economic variables (sample February 1990 to December 2025, 431
observations): the change in CPI year-over-year inflation loads 22.56 (t 3.36) on PC1 and 4.66
(t 1.57) on PC2; the change in VIX loads -2.84 (t -4.31) on PC1 and 0.71 (t 2.44) on PC2. Last,
a steepener: zero exposure to PC1, unit exposure to PC2, using only the 2Y and 10Y. With DV01s of
$190 (2Y) and $800 (10Y) per bp per $1 million face, the slide's trade is long $11,060 face of the
2Y and short $2,910 face of the 10Y, $8,150 net cash. Because prices move opposite to yields, a
long-PC2 (steepening) view means long the 2Y and short the 10Y.

**Dataset (`Yield_Curves_Data_Set.xlsx`).** Two sheets. "Updated Data": 516 monthly rows,
1983-01 to 2025-12, columns GS3M, GS6M, GS1, GS2, GS3, GS5, GS7, GS10, GS30 (FRED constant
maturity yields), plus VIXCLS and CPIYOY (VIX and CPI begin later than the yields). "Source":
FRED series names and URLs. It is monthly, so it is right for replicating the slides but too
coarse for event studies; the daily FRED series (DGS3MO ... DGS30) are the free daily equivalent.

Concepts worth learning:
- PCA as an eigen-decomposition of a covariance matrix, and the difference between loadings
  (shape of a factor across maturities) and scores (its realization each period).
- Factor-neutral hedging: solving a small linear system so a portfolio has zero exposure to one
  factor and unit exposure to another, then converting yield exposures to positions with DV01.
- Level, slope, curvature as the standard language of rates moves (useful for reading any FOMC
  reaction).

### 2026-10-28: What Investment Data Implies about the AI Transition (J. A. Wachter and J. D. Wachter, 2026)

Question: how much will AI raise GDP, judged from what firms are actually spending? Method:
revealed preference plus a two-sector (AI and non-AI) Cobb-Douglas production model with rare
productivity booms (built on the rare-disaster production models of Gourio (2012) and the rare
boom model of Tsai and Wachter (2016)). If the marginal investment is zero net present value, the
capital stock firms choose reveals the productivity jump they expect; under the open-economy
assumption the required return cancels from the capital ratio (Proposition 3.1), so the boom
size is identified from investment alone. Data: capital expenditure of Amazon, Alphabet,
Microsoft, Meta and Oracle plus xAI, CoreWeave, IREN, Applied Digital and Hut 8, from 10-Ks,
10-Qs, an S-1, earnings calls and management forecasts. In 2022 dollars the total is $156 billion
in 2022, $255 billion in 2024, $427 billion in 2025 and a forecast $782 billion in 2026; as a share
of U.S. private fixed investment it rises from 3.3% (2022) to a projected 15.5% (2026). Findings:
the capital stock entering 2028 is $2,048B against $624B initially, so e^xi is about 3.28: AI-sector
productivity roughly tripled. That boom alone (the "moderate" scenario) raises the level of GDP
by about 5.6%. Adding a 2028 to 2030 window with a 50% annual chance of another such boom gives
"transformative" and "singularity" scenarios; the conclusion states GDP by 2030 about 23% and 53%
above its initial level, and Table 2 gives post-window steady-state GDP gains of 5.6%, 23.7% and
83.2% with AI shares of 7.5%, 21.1% and 46.7%. (The abstract's ranges, "7% to 53%" for GDP and
"8% to 36%" for the AI share, do not match the body's figures exactly; read the body.) Booms after
2030 are capped at p* = 0.035 so firm values stay finite. Closing line: if the boom fails, the
buildout "will be the largest misallocation of capital in history."

Concepts worth learning:
- Revealed preference: backing a belief out of a costly action (investment) instead of a
  forecast.
- Rare-event (jump) models and option value: Omega(p) = (1 - p) + p e^((1 - alpha) xi) is why a
  small boom probability can justify a large capital stock.
- Calibration versus estimation: every number rests on a few assumptions (zero NPV at the margin,
  8% required return, 25% depreciation); Appendix C varies them.

### 2026-11-04: Berk and van Binsbergen, three papers

**Measuring skill in the mutual fund industry (JFE 2015).** Question: do active fund managers
have skill? Method: measure skill as *value added*, the fund's gross excess return over a
benchmark times its assets under management (dollars, not a return), with the benchmark being
the net returns of Vanguard index funds, a tradable alternative that existed at the time (11
Vanguard funds), and also the Fama-French-Carhart factors. Persistence is tested out of sample:
each month funds are sorted into deciles by the *skill ratio* (essentially the t-statistic of
value added up to that date), and the future value added of each decile is tracked over 36 to 120
month horizons, counting how often the top decile beats the bottom. Data: the CRSP
survivorship-bias-free mutual fund database, January 1962 to March 2011, cross-checked and filled
with Morningstar (3.3% of CRSP returns differed from Morningstar by more than 10 bp), covering all
actively managed U.S. funds including those holding non-U.S. stocks. Findings: the average fund
adds about $3.2 million per year; cross-sectional differences in skill persist for as long as ten
years; better funds collect higher aggregate fees and current compensation (fee times AUM)
predicts future value added better than past value added does. About half of the mean fund's
value added is diversification services and half is stock picking and timing. The net alpha to
investors is close to zero, as Berk and Green (2004) predict. Peter Lynch example: 2% monthly
gross alpha on about $40 million early versus 20 bp on over $10 billion later, while his value
added rose from under $1 million to over $20 million a month.

**Mutual Funds in Equilibrium (Annual Review of Financial Economics 2017).** Question: why did
the fund literature conclude that managers are unskilled and investors naive, when the same
people are treated as rational in stock markets? Argument: apply rational expectations
consistently. With decreasing returns to scale, competition among investors drives net alpha to
zero, so returns cannot reveal skill; skill shows up in fund size, just as a successful firm shows
up in market capitalization, not in its future returns. Evidence (review of Berk and van
Binsbergen 2015): Table 4 net alphas against the Vanguard benchmark are 2.74 bp/month (t 0.73)
equally weighted and -0.95 (t -0.31) value weighted on the full data set; they become
significantly negative only when funds are benchmarked to non-investable factor portfolios and
international funds are dropped (value weighted, U.S. equity, FFC: -8.34, t -3.70). Skill-ratio
deciles predict future value added but not future net alpha. The authors count 59 papers since
1995 in the top three journals that use alpha to assess skill. Conclusion: net alpha measures
investor rationality and market competitiveness, not skill.

**The impact of impact investing (JFE 2025).** Question: does divesting from "dirty" firms raise
their cost of capital enough to change real investment? Method: a mean-variance equilibrium in
which the change in cost of capital is approximately MRP x (socially conscious wealth / rest of
wealth) x f x (1 - rho^2), where f is the targeted firms' share of the market and rho their
correlation with the rest of the market; then an empirical test on inclusions in and exclusions
from the FTSE USA 4 Good Select Index (tracked by the Vanguard FTSE Social Index Fund), which does
not require measuring risk correctly. Data: ESG mutual fund holdings give f = 27% and rho = 0.93;
socially conscious wealth is under 2% of U.S. stock market wealth. Findings: the implied change
is 0.44 basis points with a 6% MRP, too small to matter; empirically the cost-of-capital
difference between targeted and untargeted firms is small and not statistically different from
zero. A 1% change would need impact investors to hold more than 80% of investable wealth (or 98%
of investors to be passive buy-and-hold). Recommendation: invest and use control rights, or fund
negative-NPV projects in primary markets, instead of divesting in secondary markets. The reason is
substitutability: when stocks are close substitutes, whoever buys the divested shares needs very
little extra return to hold them.

Concepts worth learning (session):
- Value added versus alpha: a return measure ignores scale; dollars extracted from markets do
  not. Directly reusable for any trader whose capital changes over time.
- Equilibrium thinking: when capital flows toward good managers, net returns to investors are
  driven to zero, so "investors earn nothing" is evidence of competition, not of no skill.
- Out-of-sample persistence of a sorted ranking (skill-ratio deciles) as the test of skill versus
  luck, and the role of a tradable benchmark.

### 2026-11-11: Dou, Goldstein and Ji on AI trading (two papers and a deck)

**AI-Powered Trading, Algorithmic Collusion, and Price Efficiency (July 2025).** Question: can
reinforcement-learning (RL) traders collude without agreement, communication or intent? Method:
a Kyle (1985) style model extended with oligopolistic informed speculators trading repeatedly in
short-lived assets, information-insensitive investors with a downward-sloping demand, noise
traders, and a market maker who weighs inventory cost against pricing error; theory gives the
non-collusive Nash and perfect-cartel benchmarks. Then simulation: the speculators are replaced by
Q-learning agents whose state is the lagged price and the lagged and current fundamental. Data:
none (simulation). Findings: AI collusion with supra-competitive profits arises across a wide
range of parameters, through two mechanisms. "Artificial intelligence": price-trigger strategies
(trade conservatively, punish with aggressive trading after a large price response), which needs
informative prices, so it appears with low noise-trading risk and many information-insensitive
investors. "Artificial stupidity": with high noise-trading risk, aggressive strategies suffer
large losses when noise trades go the wrong way, their Q-values are cut and never revisited, so
the agents over-prune aggression and end up collectively conservative. Either way, more collusion
means lower liquidity, lower price informativeness and more mispricing.

**Financial Market Fragility in the Era of AI Planning (September 2026).** Question: does AI
*planning* (RL that anticipates how current actions move future payoff-relevant states, the core
of agentic AI) make markets fragile? Method: a dynamic model with episodes of several subperiods,
oligopolistic informed speculators, positive-feedback (momentum) investors, constrained
arbitrageurs and low-frequency investors who pin prices to fundamentals at the start and end of
each episode. Coordinated pump-and-dump faces two obstacles: time inconsistency (once a bubble
exists each speculator wants to unwind first) and weak punishment (free-riding on bubble creation
leaves little surplus to destroy). A compounded price-trigger ("stick and carrot") strategy
overcomes both. Simulations use coupled Q-learning (one Q-matrix per subperiod linked by backward
induction) against reactive Q-learning. Data for calibration: 254 after-close earnings
announcements of 10 large tech stocks (AAPL, AMAT, AMD, AMZN, AVGO, GOOGL, MSFT, MU, NVDA, TSLA),
January 2020 to June 2026, from I/B/E/S, RavenPack, TAQ and CRSP. Findings: AI planners discover
compounded price triggers on their own; with strong feedback trading they create and exploit
bubbles. Baseline: collusion profitability Delta = 0.57, bubble fragility S^b = 1.80, h0 to h1
return volatility 7.90%, "81% higher than the 4.38% volatility in the noncollusive benchmark",
profit per speculator $1.48 million versus $0.89 million. Without feedback trading (mu/xi = 0)
coordination is static Cournot-style restraint and S^b = 0.93 < 1: collusion then stabilizes.
Bubble fragility S^b is the expected percentage price move over the information event relative to
the non-collusive equilibrium.

**Decks (`Wharton_AI_Planning_Reasoning.pdf` and
`Financial_Markets_in_the_Era_of_AI_Autonomy_Planning_and_Reasoning.pdf`, 58 pages each).** The two
files differ in bytes but their extracted text is identical: one 33-slide talk (Dou, November
2026). It walks through Q-learning, the case that AI collusion falls outside Sherman Act Section 1
(which needs an agreement), AI planning versus reactive learning, the episodic model (noting that
"the cryptocurrency case is captured by setting d0 = d-bar = sigma_v = 0", an intrinsically
worthless storable asset, and that information events can be earnings or FOMC announcements), the
calibration (rho 0.95, xi 86.167, mu 75.411, alpha 0.05, beta 1e-9), compute (1,000 sessions,
convergence when strategies are unchanged for 1,000,000,000 periods, C++, 512 cores, 3 to 48
hours), and the conclusion that "AI planning roughly doubles fragility and raises price volatility
by 80%." The last slides sketch LLM training (SFT, reward model, PPO) and external tree-of-thought
reasoning.

Concepts worth learning:
- Q-learning: the Bellman recursion, the update Q <- alpha (reward + rho max Q') + (1 - alpha) Q,
  and exploration versus exploitation; why exploitation creates asymmetric value updates.
- Tacit collusion through trigger strategies (folk theorem logic), and Abreu-style "stick and
  carrot" punishments that are themselves credible.
- Positive-feedback trading as the amplifier that turns coordination into fragility (De Long et
  al. 1990), and measuring fragility relative to a non-collusive benchmark.

### 2026-11-18: Trading zero-date (0DTE) options (Musto)

**Paper: Hope at a Reasonable Price: Customer Use of Limit Orders in the 0DTE Market (Fu, Li,
Musto, Pearson, November 2026, SEC DERA working paper).** Question: do customers trading
same-day-expiry SPXW options pay large spreads to market makers, as wide spreads and lottery-like
out-of-the-money strikes suggest? Method: three keys. (1) SPXW trades only on Cboe with no hidden
limit orders, so every limit-order-book trade interacts with the observed BBO. (2) A correction to
OPRA data, where a trade that consumes depth is stamped *after* the new BBO it causes, so naive
comparisons measure trades against the post-trade quote; trades must be resequenced first. (3)
Quote condition codes reveal customer interest at the BBO, which identifies when a customer is
first in line: market-turning orders (MTOs) that improve the BBO, pick-off orders (POs, the last
contract standing), and non-marketable limit orders filled in price improvement auctions
(a-NMLOs). Costs are measured as effective spreads (versus the midpoint at submission, with an
upper bound on non-execution cost: switch to a marketable order after one second) and realized
spreads (versus the midpoint one second and one minute later). Data: OPRA SPXW trades and quotes,
July 1, 2020 to September 28, 2023, split at April 25, 2022 (Tuesday and Thursday expirations).
Findings: around 1% OTM, customers are at the best bid more than half the time; well-OTM options
have customer interest at the best offer more than 80% of the time; 39% to 48% of LOB 0DTE trades
are filled customer MTOs and POs, mostly retail sized. With a two-tick spread, 48% of customer
MTOs fill early and 60% later, all-in expected cost $0.028 early and $0.022 late versus $0.05 for
a marketable order. a-NMLO realized spreads are negative (for example -1.4 cents early, -2.2 cents
late after a second). Conclusion: customers may lose money on 0DTE trades, "but this is not
because they have to pay big spreads to trade."

**Slides (40 pages).** Builds intuition from Akerlof's lemons to a Glosten-Milgrom style
market maker: with probability f an order is informed, break-even ask = 1/2 + f/2, bid = 1/2 - f/2,
so the spread equals f. Then payment for order flow, call options, market versus limit orders
(immediacy and certainty versus patience and risk), and effective versus realized spread, before
the paper's question.

Concepts worth learning:
- Adverse selection as the source of the bid-ask spread (spread = probability of informed flow in
  the toy model).
- Effective versus realized spread, and the cost of non-execution when you post a limit order.
- Data forensics: event ordering in a consolidated feed can silently bias every cost estimate,
  which is the same lesson as this repo's Q0 (aggressor-event collapse).

---

## Part 2. What exists on data.binance.vision for options (checked 2026-11-19)

S3 listing of `data/option/` (paginated, every `<Contents>` block parsed): only a `daily/` folder
with two datasets.

| dataset | symbols | first | last | files | zipped size | content |
|---|---|---|---|---|---|---|
| BVOLIndex | BTCBVOLUSDT, ETHBVOLUSDT | 2023-06-20 | 2026-11-17 | 1,221 each (one gap, 2025-12-14 to 2026-01-05) | about 538 MB and 547 MB | Binance implied-volatility index, one row per second (`calc_time, symbol, base_asset, quote_asset, index_value`) |
| EOHSummary | BTCUSDT, ETHUSDT | 2023-05-18 | 2023-10-23 | 147 each | 56 MB, 69 MB | hourly per-option row: OHLC, volume, best bid/ask price and size, bid/ask IV, mark price and IV, delta, gamma, vega, theta, open interest |
| EOHSummary | BNBUSDT, XRPUSDT, DOGEUSDT | 2023-05-18 / 2023-05-19 / 2023-08-30 | 2023-10-20 to 2023-10-23 | 121, 99, 31 | small | same, with several multi-week gaps |

What this means for a 0DTE project: EOHSummary covers only about five months of 2023 and, on the
days sampled (2023-05-18, 2023-08-15, 2023-08-18, 2023-10-23), lists only weekly, monthly and
quarterly expiries, no daily ones. The nearest thing to 0DTE is the Friday weekly on its expiry
morning (expiry 08:00 UTC): on 2023-08-18 the expiring 230818 series appears in hours 01 to 08 with
12,515 contracts of volume. That is roughly 20 expiry mornings per underlying, hourly bars, no
trades, no order types, no customer codes. The paper's method (resequencing trades and quotes,
quote condition codes, MTO/PO/a-NMLO inference) cannot be reproduced. BVOLIndex is a good, long,
free implied-volatility series for event studies, but it is not a same-day-options dataset. The
futures `daily/` folder has no liquidation data (`liquidationSnapshot` returns nothing for BTCUSDT);
it has aggTrades, bookDepth, bookTicker, klines (index, mark, premium too), metrics and trades.
`bookDepth` for BTCUSDT runs 2023-01-01 to 2026-11-17 (1,413 files, 667 MB zipped); each file holds
snapshots about every 30 seconds of cumulative depth and notional at -5% to +5% of mid in 1% steps
(2,879 snapshots on 2025-10-10).

A quick check run while writing these notes: the OPRA misordering the 0DTE paper corrects does not
appear to be endemic on Binance. On BTCUSDT 2023-06-05 (1,670,206 aggTrades), aligning each trade to
the last bookTicker strictly before it, as `signals/load.py` does, only 0.76% of buys print below
the prior ask and 0.62% of sells above the prior bid; requiring the quote to be older raises those
shares steadily (7.3% and 6.9% at 20 ms), as stale quotes should. One day, one symbol; a lead, not
a test.

Hyperliquid hosts (`api.hyperliquid.xyz`, `stats-data.hyperliquid.xyz`) are refused by this
sandbox's network proxy (HTTP 403 on CONNECT, 2026-11-19), so any Hyperliquid work first needs
those hosts allowed.

---

## Part 3. Project ideas, ranked

Each idea uses one QFA paper's method and one thing this repo has already found. Ranking weighs
how interesting the answer is, how likely the free data can answer it, and how much existing code
it reuses.

### 1. Liquidation cascades as positive-feedback fragility: depth before, during and after (fragility paper + Hawkes, C4)

- **Question.** In liquidation cascades such as 2025-10-10, does visible depth withdraw before the
  price falls (fragility building) or only after (a consequence)? Is the overshoot and reversal
  larger where positive-feedback pressure (leveraged open interest relative to volume, extreme
  funding) was larger beforehand?
- **Why interesting.** Dou, Goldstein and Ji make fragility depend on positive-feedback trading;
  forced liquidations are mechanical positive feedback (the paper itself notes that binding margin
  constraints force losers to sell). The repo already found that about 70% or more of trades are
  reactions to other trades (count-variance branching ratio 0.959) and treated 2025-10-10 and
  2025-10-11 as an outlier window to drop in C3 and C4. Here the outlier becomes the object of study.
- **Borrowed method.** The paper's fragility measure (price move relative to a benchmark, S^b) and
  its feedback-strength comparative static (mu/xi), applied empirically: a reversal ratio around
  each cascade, regressed on pre-event feedback proxies.
- **Data.** `data/futures/um/daily/bookDepth/` (30-second depth at plus or minus 1% to 5%, 2023-01
  to 2026-11, not on disk); `data/futures/um/daily/metrics/` (5-minute open interest and
  long/short ratios, not on disk at that resolution: `data/raw_panel` holds a coarse sample); 1-minute
  klines for BTC, ETH, SOL already on disk (`data/politics/klines`, 2020-01 to 2026-10); aggTrades
  for the Hawkes windows (download per day, the existing checksum-verified pipeline). No liquidation
  feed exists in the archive, so a cascade is defined from data: a pre-registered threshold on
  5-minute open-interest drops together with a price move.
- **First step.** Download BTCUSDT and ETHUSDT bookDepth and metrics for 2025-10-01 to 2025-10-20,
  locate the 5-minute bar with the largest open-interest drop, and plot depth at plus or minus 1%
  against price and open interest. Then write the event definition into a pre-registration (as in
  `research/politics/PREREGISTRATION*.md`) before scanning 2023 to 2026 for all events.
- **Result.** A stacked event study over all qualifying cascades (many contracts, 2023 to 2026)
  with matched control times: (a) the timing of depth withdrawal relative to the price low with
  intervals, (b) the slope of the reversal ratio on pre-event feedback proxies, (c) the branching
  ratio inside cascade windows versus matched quiet windows. A clean null (depth falls only after
  price) is also a result.
- **Time.** 3 to 4 weeks.
- **Google systems angle.** A resumable, checksum-verified ingest of hundreds of contracts times
  about 1,400 days of 30-second order-book snapshots, joined on time with trades and open interest,
  with an event scanner that runs in minutes, not hours.

### 2. Skill versus luck for Hyperliquid vaults and wallets, and who the small traders are (Berk and van Binsbergen + Part A)

- **Question.** Do Hyperliquid traders have persistent skill once measured as dollar value added
  rather than return, and do vault depositors still earn about zero, as the equilibrium view
  predicts? Second, are the wallets that trade in tiny sizes (the shift Part A found on Binance,
  where median USD trade size fell about 84% for survivors and fills shrank too) a few automated
  wallets, and are they the skilled ones?
- **Why interesting.** Binance is anonymous, so Part A could only say the drop in trade size is
  "consistent with algorithmic slicing." Hyperliquid shows positions and fills per wallet, so the
  same question can be asked about identified traders. Hyperliquid vaults are a close analogue of
  mutual funds: a manager, outside depositors, a profit share, and flows that can chase
  performance.
- **Borrowed method.** Value added (excess return over a tradable benchmark, here a beta-matched
  BTC or ETH perpetual position, times capital); skill-ratio decile sorts with out-of-sample
  future value added at several horizons; the flow-performance and net-return tests from Mutual
  Funds in Equilibrium; and a bootstrap of cross-sectional t-statistics in the style of Fama and
  French (2010), which the session papers cite, to ask how many wallets beat luck.
- **Data.** Hyperliquid public info API (vault details, user fills by time, ledger updates for
  deposits and withdrawals, funding); public leaderboard. Not on disk. Verify first: how far back
  per-wallet fills go through the free API, and whether the bulk historical archives are
  requester-pays (if so they are not free). Network access to both hosts must be granted first (see
  Part 2).
- **First step.** Once the hosts are allowed, pull the full vault list and each vault's equity and
  flow history, compute monthly value added against a BTC benchmark, and check for survivorship:
  closed vaults must be included or the sort is biased.
- **Result.** A top-minus-bottom skill-decile spread in future value added with an interval that
  excludes zero (or does not), net-return-to-depositors near zero or not, and the share of tiny-size
  volume coming from the top 1% of wallets.
- **Main risks.** Survivorship in any leaderboard-based universe; one trader running many wallets;
  deposits and withdrawals that look like returns if not removed; short history (a few years).
- **Time.** 4 to 6 weeks, mostly data collection.
- **Google systems angle.** A rate-limited, idempotent crawler that rebuilds per-wallet equity
  curves from an event log (fills, funding, transfers) and reconciles them against reported
  account values.

### 3. A Christie-Schultz test after tick cuts: do traders keep using the old coarse grid? (collusion literature + e3/e5)

- **Question.** After Binance cuts a contract's tick 10x, how quickly do trade prices stop
  clustering on multiples of the old tick? Lasting clustering is the empirical fingerprint of tacit
  coordination on a coarse grid that Christie and Schultz (1994) found among Nasdaq dealers (cited
  in the fragility paper); a fast move to about 10% (uniform use of the new grid) is the competitive
  outcome.
- **Why interesting.** It is the one testable trace of algorithmic collusion this repo can measure
  without trader identities. The repo already has 35 tick-change batches with matched controls
  (e5), found that cuts raise sign persistence by +7.5 pp, and saw the share of trades at an
  unchanged price fall about 30 pp in e3, which already hints the finer grid gets used.
- **Borrowed method.** Christie and Schultz's odd-tick share, inside the e5 stacked
  difference-in-differences. The collusion paper supplies the prediction to pre-register: if
  coordination persists, effective liquidity should not improve.
- **Data.** On disk: `data/tick_events` and the e5 event panel; aggTrades from the existing
  pipeline. The two reserved lock-box batches (2026-08-06 and 2026-10-15) are already used by Q15,
  so a fresh holdout must come from batches after 2026-10.
- **First step.** For the 2026-03-05 batch (12 contracts), compute the daily share of trades on
  old-tick multiples for 21 days before and after, against controls' share on a hypothetical grid
  10x their tick.
- **Result.** The half-life of old-grid clustering with intervals, pooled over batches. Caveat: round
  numbers attract orders for reasons other than collusion (retail habits, resting orders placed
  before the cut), so persistence is necessary, not sufficient, evidence.
- **Time.** 1 to 2 weeks.
- **Google systems angle.** Reusing a stacked event-study engine with a new outcome in a day,
  because the outcome is a plug-in over a columnar store.

### 4. FOMC days through yield-curve factors: does crypto react to the level or the slope? (Dieckmann PCA + C3/C4 event tools)

- **Question.** On FOMC announcement days, do BTC, ETH and SOL returns and realized volatility load
  on the level or the slope surprise in Treasuries, and does Binance's implied-volatility index show
  a pre-announcement run-up and post-announcement drop?
- **Why interesting.** It turns the session's PCA into an event study, and the Dou deck names FOMC as
  the macro information event in its model. The repo's politics work found no effect of tariff posts
  (C3: +1.32 bps [-1.80, 4.60]; C4: no evidence of pre-post trading), so a scheduled macro event is
  a good positive control for the same tooling.
- **Borrowed method.** PCA on daily yield changes, fitted on non-FOMC days, then FOMC-day changes
  projected on level and slope; C3's matched same-minute-of-week controls and permutation tests.
- **Data.** FRED daily DGS3MO, DGS6MO, DGS1, DGS2, DGS3, DGS5, DGS7, DGS10, DGS30 (free; the daily
  versions of the session dataset); FOMC statement times from federalreserve.gov; 1-minute klines on
  disk for BTC, ETH, SOL (2020-01 to 2026-10); BVOLIndex 1-second (2023-06-20 to 2026-11-17, not on
  disk).
- **First step.** Replicate the slides' 98.7% and loadings from `Yield_Curves_Data_Set.xlsx`, then
  refit on daily FRED data and list the FOMC statements from 2020 to 2026.
- **Result.** Betas of announcement-window crypto returns on level and slope surprises with
  intervals, and the size of the BVOL change around the statement. Limits: about 55 meetings, and
  daily yield changes mix the announcement with the rest of the day (intraday Treasury data is not
  free).
- **Time.** 2 to 3 weeks.
- **Google systems angle.** A small, typed pipeline joining three clocks (daily yields, minute bars,
  second-level index) with explicit time-zone handling and tests on known dates.

### 5. Delisting announcements as forced divestment (impact investing + Q16 and the planned announcement test)

- **Question.** When Binance announces a futures delisting, how large is the price effect, and does
  it scale the way Berk and van Binsbergen's formula says divestment should: with the share of
  capital forced out and with (1 - rho^2), so that coins highly correlated with BTC barely move?
- **Why interesting.** Q16 found the announcement month carries most of the models' edge (59% of the
  lock-box gain disappears when that month is dropped), and the announcement study (`d1_inventory.py`,
  907 candidate events in `event_inventory.csv`) is the next step anyway. This adds a theory-based
  cross-sectional prediction to it.
- **Borrowed method.** The impact paper's cost-of-capital approximation as the prediction, tested
  with an event study instead of a calibration.
- **Data.** On disk: daily klines, funding and open interest for about 920 contracts
  (`data/raw_panel/contracts`), the event inventory; spot klines (free) for the spot pair; the
  announcement times still being collected.
- **First step.** After announcement times are matched, compute each coin's correlation with BTC over
  the prior 90 days and its futures open interest relative to market cap, and pre-register the sign.
- **Result.** The slope of announcement abnormal returns on (1 - rho^2) times the forced-out share.
  Caveat: a delisting also carries bad news about the project, which pure divestment does not, so a
  steep slope cannot be read only as a substitutability effect.
- **Time.** About 2 weeks once announcement times exist.
- **Google systems angle.** A reproducible join of a scraped announcement feed with an archive whose
  files keep appearing after a contract dies (Q16's ghost months).

### 6. Who pays when trades got small: effective and realized spreads by trade size (0DTE paper + Part A)

- **Question.** Do the tiny taker trades that now dominate pay more or less than larger ones, in
  effective spread and in realized spread at 1 second and 1 minute?
- **Borrowed method.** The 0DTE paper's effective versus realized spread split, after first checking
  trade and quote order (done on one day above: misordering appears rare).
- **Data.** bookTicker exists only 2023-05 to 2024-04, so this cannot span the 2023 to 2026 trade-size
  shift; on disk for BTC, ETH, SOL, DOGE (June and July 2023).
- **Verdict.** Feasible and quick (about 1 week) but it cannot answer the time-trend question, so it
  ranks last.

### Considered and dropped

- **0DTE on Binance options.** No daily expiries, five months of hourly bars, no trades or order
  types (Part 2). Not feasible. A same-day-options study on crypto would need another venue's data;
  check whether any is free before planning.
- **Directly detecting AI collusion in Binance data.** The models' predictions (lower liquidity and
  informativeness) are also predicted by many non-collusive changes, and the data has no trader
  identities, so a market-wide trend cannot be attributed to AI agents. Idea 3 is the narrow,
  testable piece; Idea 2 is the route with identities.
- **AI transition and crypto.** The paper's link (bitcoin miners IREN and Hut 8 turning into AI data
  centers) is interesting but does not touch this repo's data or findings.
