# Project designs

This file expands the seven ranked projects in `README.md`. Each has hypotheses, data, variables, equations, the machine-learning angle (if any), threats, and a pre-registration outline. The six scout tracks produced 71 ideas; the novelty review collapsed them into about 12 clusters, and this file keeps the seven with the best mix of free data, identification and novelty.

## Pre-registration template (applies to every project)

1. `PREREGISTRATION.md` in the project subfolder states the question, hypotheses with signs (or explicitly two-sided), sample, variables, primary test, multiple-testing correction, robustness list, stopping rule and a disclosure of outcomes already seen (including anything in this scoping file and in the scout reports, for example the pilot correlations in P1 and P5 notes).
2. Freeze inputs before outcomes: the memecoin label list (written rule plus hand-coded list), symbol list, event list and windows, written as CSV.
3. Hash the plan and the frozen inputs (sha256) and record the hashes in the plan's header and a commit message before any outcome is computed. Downloaded archive files are hashed too, because Binance re-uploads.
4. Hold out a lockbox: the final 6 months of data (2026-05 to 2026-10) are not opened until the main analysis is final.
5. Inference: block bootstrap by date or clustering by coin and date; a common meme factor in cross-sectional tests; Holm across the primary family, Romano-Wolf or Benjamini-Hochberg for secondary families.
6. Report nulls. Report harm-detection results in aggregate and with a delay; never publish real-time signals.

---

## P1. Positioning-metrics audit and crowd count recovery

**Why first.** Every positioning study rests on the 5-minute metrics file, and that file has a year-long hole in 2022, re-uploads, unsorted days and a precision change. There is no outcome variable, so this can start before any lock.

**Part A: audit.**
- Inputs: every `metrics` key for about 29 memecoin perps plus BTCUSDT and ETHUSDT, S3 `LastModified`, `.CHECKSUM`.
- Outputs: `metrics_mask.csv` (symbol, start, end, column, reason), `metrics_manifest.csv` (key, sha256, LastModified, rows, first and last create_time). Monthly re-download and diff to detect value revisions.

**Part B: account counts.** Before 2023-07-10 the ratios are full doubles. For each row find the smallest-denominator fraction p/q with |p/q - r| below 1e-12 (Stern-Brocot or continued fractions). Then N_min = p + q is a lower bound on accounts holding the symbol; the true count is k(p+q) for an unknown integer k >= 1. Example: 1000PEPEUSDT 2023-05-06 00:00 gives 4701/3586 (N_min 8,287) and at 00:05 3165/2429 (N_min 5,594), so k must vary. Estimate a smooth count path by choosing k_t that minimises sum_t (log N_t - log N_{t-1})^2 subject to N_t = k_t(p_t+q_t) and to consistency between the top-trader and global series (top-trader count must not exceed the global count).
- Validation: N_t should co-move with open interest and trade counts; at listing it should start near zero.

**ML angle:** none needed. **Threats:** k ambiguity; the definition of an account "holding" a symbol is Binance's. **Deliverable:** a reusable mask and a lower-bound crowd-size series for 2021-12 to 2023-07 listings (1000PEPE, 1000FLOKI, PEOPLE, 1000LUNC).

---

## P2. Survival and listing-day losses of memecoin perps

**Questions.** H1: memecoin perps have a higher 12-month delisting hazard than other perps listed in the same period. H2: buy-and-hold abnormal return from the first trade to day 30, 90 and 180 is negative for memecoin perps and more negative than for other perps (two-sided for the difference).

**Sample.** All lives in `contract_lifecycle.csv` with first trade from 2023-01-01 (766 lives); memecoin flag frozen in advance. Delisting date and last trade day from the lifecycle file, cross-checked against catalog 161 notices; never from file existence.

**Variables.** Day-0 price = first 1-minute close after the first trade. BHAR_i(h) = prod_{d=1..h}(1+r_{i,d}) - prod_{d=1..h}(1+beta_i r_{BTC,d}), with beta_i fixed at 1 in the primary spec (new listings have no pre-period) and estimated on days 31 to 120 in a robustness run. Returns end at last_trade_day with the last traded price. Covariates: launch-to-listing lag (from the token's first on-chain or Hyperliquid date where known), day-1 quote volume, mean funding days 1 to 3, spot listing status at day 0, listing month.

**Models.** Kaplan-Meier by group with log-rank test; Cox h(t|x) = h0(t) exp(b'x) with listing-quarter strata. Cross-sectional regression BHAR_i = a + b Meme_i + c'x_i + e_i with month-of-listing clustering.

**ML angle.** A random survival forest or gradient-boosted survival model as an exploratory comparison: train on listings before 2025-07, test after; report concordance and integrated Brier score against the Cox baseline and against the base-rate-only model. Framed as a consumer-risk indicator, not a short signal.

**Threats.** Small N (about 65 memecoin lives). Delisting depends on liquidity rules, so "death" partly measures Binance policy. Collapse may be the majority outcome, so accuracy is meaningless; report lift.

---

## P3. Funding transfers and the lottery premium

**Questions.** H1: average funding on memecoin perps exceeds BTCUSDT and ETHUSDT funding over the same settlements. H2 (two-sided): weekly MAX predicts next-week funding-adjusted returns within all USDT-M perps, with a meme interaction. H3: funding rises after high-MAX weeks.

**Variables.**
- Transfer_{i,t} = f_{i,t} x OIvalue_{i,t}, with OI value from the 5-minute metrics row nearest settlement t. Cumulative transfer by coin, by listing age (weeks 0 to 4, 5 to 12, 13+), and by MAX regime.
- MAX_{i,w} = max over days d in the prior 7 days of r_{i,d} (log close-to-close, UTC days). Robustness: average of the top 3 days; 28-day window; hourly MAX for an intraday reversal check.
- Funding-adjusted long return R_{i,w+1} = sum of log price returns minus sum of funding paid by longs.

**Models.** Panel R_{i,w+1} = a + b MAX_{i,w} + g MAX_{i,w} x Meme_i + c'X_{i,w} + week FE + e, with X = log OI value, prior 4-week return, prior-week return (reversal), realised volatility, Amihud illiquidity, and a common meme factor loading. Two-way clustering by coin and week. Tercile sorts as a secondary check. Prospect-theory value (TK 1992 parameters, past 30 daily returns) and skewness only as robustness, since they are collinear with MAX.

**ML angle:** none. **Threats.** Funding caps and interval changes shape the premium (tabulate them first); receivers are mostly hedged arbitrageurs, so "who collects" is "liquidity providers", not informed bears; power is low within about 50 meme perps (about 180 weeks from 2023), so a power calculation goes in the plan.

---

## P4. Who wins on Hyperliquid memecoin perps

**Questions.** H1: net PnL on memecoin perps is more concentrated (Gini, top-1% share) than on BTC and ETH perps for the same wallets. H2: takers lose to makers per dollar of volume, more so on memecoins. H3: high-turnover wallets have lower PnL per dollar of capital (Barber-Odean). H4: profits of the top memecoin wallets do not persist beyond a luck null.

**Sample.** Two arms. (a) Historical: wallets from the leaderboard stratified by account value and volume, plus addresses seen on the live tape; pull `userFillsByTime` and `userFunding`; keep only wallets whose earliest retained fill is at or before their first deposit (complete history) for the main analysis. (b) Forward: all addresses on the websocket tape for memecoin coins from the recorder start date; this arm is free of retention truncation and is the primary test once 8 weeks are collected.

**Variables.** Net PnL_i = sum closedPnl - sum fee + sum funding, by coin group; maker flag from `crossed`; liquidation flag from fill fields; turnover = notional / average account value.

**Models.** Lorenz curves, Gini and top-1% share with wallet bootstrap; taker-minus-maker PnL per $ volume; turnover quintile sort; persistence via the `research/hyperliquid/` skill-versus-luck bootstrap (out-of-sample month split, FDR).

**ML angle:** optional clustering of wallets into behavioural types (k-means on turnover, leverage, holding time, maker share) as description, not inference. **Threats.** Address is not person; vaults and market makers dominate the top; leaderboard survivorship; rate limits (weight 20 per 2,000 fills) make large pulls take days, so stratification is fixed before sampling.

---

## P5. Binance memecoin perp listings, priced off Hyperliquid

**Questions.** H1: memecoins listed by Binance show positive abnormal returns on Hyperliquid from day -10 to day -1 before the announcement (leakage or anticipation). H2: day 0 to +1 abnormal return is positive. H3: day +2 to +30 abnormal return is negative (reversal).

**Sample.** Catalog 48 notices titled as Binance Futures perpetual launches whose coin traded on Hyperliquid at least 30 days before the announcement. Controls: Hyperliquid memecoins not listed on Binance within plus or minus 60 days, matched on Hyperliquid age, volume and prior 30-day return (selection on run-ups).

**Variables.** AR_{i,d} = r^{HL}_{i,d} - r^{HL}_{memeindex,d} (equal-weight index excluding i); CAR over the windows above, aligned to the UTC day of releaseDate. Hourly windows only for events inside Hyperliquid's hourly candle history (about the last 7 months) or recorded forward.

**Models.** Stacked event study with date-clustered bootstrap; difference against matched controls. Leakage results reported only in aggregate, as in `research/politics` C4.

**ML angle:** none. **Threats.** HL perp is not spot; Binance often batches several meme listings in one notice; small N (count to be fixed in the plan after matching, before any return is computed).

---

## P6. Validating "retail" proxies with Binance RPI flags

**Questions.** Which public-trade features have lift for identifying app or website takers?

**Collection.** Poll `https://www.binance.com/fapi/v1/trades?limit=1000` for about 20 RPI-enabled symbols (memecoins plus BTC and ETH), interval adapted per symbol so trade ids are continuous; log gaps. Run 4 to 8 weeks. Store id, time, price, qty, quoteQty, isBuyerMaker, isRPITrade.

**Features (pre-registered).** Notional bucket; distance to round USDT notional ($10, $20, $50, $100, $500, $1,000); contract-quantity roundness; decimal precision of qty; hour of day and weekend; inter-trade gap; same-millisecond sibling count (sweep indicator).

**ML angle.** Positive-unlabelled learning: RPI-true is a sample of app-taker trades, RPI-false is unlabelled. Report for each feature and for a gradient-boosted combination the lift and precision at k against the RPI base rate, with symbol-day clustered bootstrap. Because RPI fills receive price improvement by design, do not use RPI trades for markout studies without adjustment.

**Threats.** Selection: only app takers who hit an RPI maker are labelled, and RPI maker liquidity varies by symbol and time. Rare positives (zero in several samples). App UI may size orders in USDT or as a percentage of balance, which changes what "round" means.

---

## P7. Football matches as an outside gamble

**Questions.** H1: during Euro 2024 match minutes, log small-notional taker trade counts in memecoin perps fall relative to the same clock minutes on non-match days, by more than in BTCUSDT and ETHUSDT. H2: the effect is larger for matches involving countries with large Binance user bases (list frozen in advance from public Binance traffic statements, or dropped if no source exists). H3 (attention returns): half-time minutes show a rebound.

**Data.** Daily aggTrades 2024-05-31 to 2024-07-28 for 1000PEPEUSDT, DOGEUSDT, WIFUSDT, 1000BONKUSDT, BTCUSDT, ETHUSDT; fixture list with UTC kickoff, half-time, full time.

**Model.** log(1 + N^{small}_{i,m}) = a_{i, minute-of-week} + b Match_m + g Match_m x Meme_i + h log RV^{BTC}_m + e, controls from the same clock minutes on non-match days within plus or minus 14 days, standard errors clustered by match. "Small" defined in USDT notional before download (for example under $100), with total counts and notional as co-primary outcomes because small-size share is not a validated retail proxy (P6).

**ML angle (secondary).** A gradient-boosted expected-volume model trained on non-event days (clock time, weekday, BTC volatility, lagged volume), with abnormal volume compared against the same windows on 200 placebo days.

**Threats.** 24/7 market with strong BTC-driven volume; European evening slots overlap US afternoon; World Cup 2022 overlaps the FTX collapse (2022-11-11) and is used only as a secondary sample.

---

## Clusters considered and set aside

| Cluster | Reason (from the novelty review and deep dives) |
|---|---|
| US lottery jackpots, Super Bowl, March Madness, state sports-betting DiD | Binance.com excludes US residents; Hyperliquid's terms reportedly restrict US persons; Google Trends blocked and noisy. Revisit with a US-heavy venue. |
| Trump-family posts on TRUMPUSDT | Only 3 coin-specific posts after the perp listed. Widening to crypto posts makes the shock macro. |
| Musk-DOGE saturation | From November 2024 "DOGE" often means the Department of Government Efficiency; growing market cap confounds decay; post dump unlicensed. |
| Spot PEPE vs perp 1000PEPE denomination | Relative tick 100 times finer on the perp and different minimum notional: differences are mechanical. |
| Crowd vs top-trader gap as "retail vs smart money" | Account ratios include top traders and count accounts, not size; Hyperliquid top accounts are structurally short (market makers, basis traders). Revisit after P1 and P6. |
| Rush-order pump detector, frenzy classifier | No clean ground truth for crowd pumps on large-cap perps; monitoring-tag and delisting labels lag by months. |
| Reddit, Wikipedia, Binance Square text | Hosts blocked, Reddit dumps unlicensed and taken down at Reddit's request, Wikipedia version largely done, Square forward-only. A validated memecoin mention index and sentiment benchmark remain open contributions once data access is settled. |
| Re-derive the $TRUMP loss headline | Needs Solana data that is blocked or paid (BigQuery scans exceed the free quota). |
| Pump.fun public datasets re-analysis | Free, but GitHub, Zenodo and Hugging Face are blocked; worth doing once allowed, using the skill-versus-luck FDR tools. |
