# Why order-flow sign predictability changes: mechanisms, evidence, and aggTrades proxies

Background notes for Part A of the market evolution project (why the next trade's sign became
more predictable on Binance USDT-M perpetuals between 2023-06 and 2025-07).

**Tags.** [V] verified from the source or its abstract this session. [S] from a secondary
source or a search-result snippet. [I] my inference.

**Important limitation of this session.** Every page fetch failed: the session's network proxy
refused arxiv.org, ar5iv, econpapers, hal, phys.org, binance.com, emergentmind and the other
hosts tried (HTTP 403 on CONNECT). All claims below therefore come from web-search result
snippets and summaries, and are tagged [S] at best. Nothing here is [V]. Before any of these
numbers goes into the write-up, open the paper and check it. Allowing arxiv.org and
www.binance.com in the session network settings would let a later pass upgrade tags to [V].

## Summary

The standard account is that order signs are persistent mainly because large parent orders
(metaorders) are split into many same-sign child trades, with herding across traders a
secondary effect on intraday horizons; the Lillo, Mike and Farmer (2005) model links the tail
exponent alpha of the metaorder size distribution to the sign ACF exponent gamma through
gamma = alpha - 1, and Sato and Kanazawa (2023) report the first quantitative confirmation on
nine years of account-level Tokyo data [S]. This gives three levers through which
predictability can change over time: the share of flow that is split, how heavy-tailed the
metaorder sizes are, and how many metaorders run at once (Primicerio and Challet report that
more concurrent large-trader metaorders weaken sign memory) [S]. Market structure enters
through relative tick size (large-tick assets have compact books, are easier for deep models to
forecast, and push some traders towards market orders) and through fees, rebate programs and
algorithmic participation [S]. Direct evidence on how gamma moves over the years is thin: an
unreviewed write-up on equities reports that after 2010 the sign ACF splits into two power laws
with a weaker short-lag part [S], and I found no peer-reviewed study of sign-ACF trends on
crypto venues for 2018 to 2026 [S]. Crypto-specific work that does exist shows sign ACF
exponents near 0.4 on early Bitcoin data (Donier and Bonart) and, very recently, clock-periodic
algorithmic order flow on six Binance USDT-M perpetuals concentrated at quarter-hour boundaries
(arXiv 2607.09426, July 2026) [S]. Binance itself changed several things that could move these
levers between mid-2023 and late 2025: a Liquidity Provider program change (2023-06-05), a new
Taker Program with fee discounts for large takers (2023-10-31), LP upgrades (2024-01-03 and
2024-06-03), a revised Taker Program (2025-08-12), RPI orders (from 2025-11-20) and many
per-contract tick-size changes [S]. All mechanisms can be proxied from aggTrades alone, with one
caveat that matters a lot: one aggTrade is one taker order filled at one price, so a single
sweep produces several same-sign records in the same millisecond [S].

## 1. Why order signs are persistent: theory

### 1.1 Order splitting (metaorders) and the LMF exponent relation

- Lillo, Mike and Farmer (2005, Phys. Rev. E 71, 066122) propose that long memory in order flow
  comes from a delay in market clearing: large orders are split into small pieces executed over
  time, and if the size of these large orders is power-law distributed, the order execution
  process has power-law decaying autocorrelation [S].
- The exponent relation tested later is gamma = alpha - 1 (written alpha = gamma + 1), where
  C(tau) ~ tau^(-gamma) is the sign ACF and alpha is the tail exponent of the metaorder size (or
  length) distribution [S]. Consequence for this project: a falling gamma means heavier-tailed
  metaorders or more of the flow coming from long metaorders [I].
- Sato and Kanazawa (2023, Phys. Rev. Lett. 131, 197401; arXiv 2301.13505) use Tokyo Stock
  Exchange data with coded trader accounts, 2012 to 2020, classify accounts as splitting or not,
  measure metaorder length distributions and find the LMF prediction holds "even at the
  quantitative level" [S]. A companion paper in Phys. Rev. Research 5, 043131 (2023) studies
  order-splitting behaviour of individual accounts over nine years and reports power-law
  metaorder lengths [S]. Lillo's Physics Viewpoint (Physics 16, 192) calls it the first
  quantitative evidence for the model [S].
- Sato and Kanazawa (arXiv 2502.17906, 2025) ask why prices stay diffusive despite predictable
  order flow and argue the square-root impact law keeps persistent flow from making prices
  predictable [S]. This matters here because sign predictability can rise without any rise in
  return predictability [I].
- Lillo and Farmer (2004, "The long memory of the efficient market", Stud. Nonlinear Dyn.
  Econom.) report LSE order-sign ACF decaying as tau^(-0.6) (Hurst about 0.7), with per-stock
  exponents from 0.36 to 0.77, and show that sign persistence is offset by anti-correlated
  fluctuations in size and liquidity, which keeps returns close to white [S]. They also report
  that some institutions show long memory and others do not [S].
- Bouchaud, Farmer and Lillo (2008, "How markets slowly digest changes in supply and demand",
  arXiv 0809.0822) review the evidence and name incremental execution of large hidden orders as
  the primary cause [S].

### 1.2 Splitting versus herding

- Toth, Palit, Lillo and Farmer ("Why is order flow so persistent?", arXiv 1108.1632; J. Econ.
  Dyn. Control 51, 2015, 218 to 239) use LSE data with member identifiers and find that on
  horizons of a few hours or less persistence is overwhelmingly due to splitting rather than
  herding; at longer horizons different investors are anti-correlated [S].
- Herding (different traders choosing the same side) remains the alternative explanation, and
  self-exciting (Hawkes) descriptions are used for the clustering part; a single exponential
  kernel gives short memory only, so long memory needs a power-law or multi-scale kernel [S]
  (the latter is search-tool background, not checked against a paper).
- Crypto perpetuals add a herding-like channel the equity literature lacks: forced
  liquidations, where clustered liquidation thresholds generate one-sided market orders that
  trigger further liquidations [S] (Glassnode and practitioner sources). Two 2026 arXiv
  preprints (2607.27070, 2608.03616) study Binance USDT-M liquidation cascades from 2022 to 2025
  and note that Binance's per-event liquidation snapshot files are no longer served [S].

### 1.3 What weakens memory

- Primicerio and Challet ("Large large-trader activity weakens the long memory of limit order
  markets", arXiv 1803.08390; Market Microstructure and Liquidity, 2019) combine more than 6.7
  billion trades with quarterly fund holdings. Sign memory is noticeably weaker when large funds
  trade directionally and when their participation ratio is high; between a higher number of
  active metaorders and a change in the metaorder size distribution, the evidence favours the
  number of active metaorders [S].
- [I] Implication: the next-sign accuracy and gamma need not move together. Many small
  concurrent algorithmic metaorders can raise short-lag predictability (lag 1 to 10) while the
  long-lag tail flattens or steepens. Q8's falling gamma median (0.327 in 2023-06 to 0.187 in
  2025-07) and Q10's rising accuracy should be read as separate facts until the short-lag and
  long-lag parts of the ACF are measured separately.

## 2. Evidence that persistence changes over time or across markets

- Equities, 2000 to 2013 (unreviewed project write-up, surfaced by search): gamma about 0.28 to
  0.38 up to 2009; from 2010 the ACF is better described by two successive power laws with a
  break near lag 10 (about 0.50 to 0.60 below, 0.17 to 0.20 above); lag-10 ACF about 0.05 in
  2010 to 2013 against about 0.1 in 2000 to 2009; long-lag ACF roughly stable [S]. I could not
  identify the authors, so treat this as indicative only.
- Mike and Farmer (2008, J. Econ. Dyn. Control 32, 200 to 234): order signs of 25 LSE stocks,
  2000 to 2002, Hurst about 0.75 to 0.88 (mean about 0.83) via DFA; their behavioural model
  works best for low-volatility, small-tick stocks [S].
- FX: Gould, Porter and Howison (arXiv 1504.04354; Market Microstructure and Liquidity 2, 2016)
  find long memory with Hurst about 0.7 on three currency pairs on a large electronic FX spot
  platform, on every day, and reject structural breaks as the cause [S]. A separate FX study of
  a tick-size reduction (arXiv 1307.5440) reports a market-order ACF that is null after about 2
  minutes on that venue [S], which shows persistence can differ strongly across venues.
- HFT era: one study of 14 US stocks, 2002 to 2009, finds the Hurst exponent of dollar volume
  rising after about 2005 and links it to HFT onset (arXiv 1006.5490) [S]; this is volume, not
  signs.
- Trade size: Kyle, Obizhaeva and Tuzun (TAQ 2001 to 2014) find trade-size distributions shift
  sharply downward over the period, with clustering at round lots, linked to splitting after
  decimalization and algorithmic trading [S]. O'Hara, Yao and Ye (J. Finance 69, 2014, 2199 to
  2236) report that odd lots are increasingly used by algorithmic and HFT traders, median 24% of
  trades (60% or more in some stocks), and contribute 35% of price discovery [S].
- Human versus machine: a Quantitative Brokers whitepaper on ES and ZN futures since 2012 treats
  round-lot trade sizes as a human footprint and non-round sizes as machine [S]; this is a
  vendor heuristic, not an established result.
- Tick-size natural experiments (SEC Tick Size Pilot, EBS FX tick change 2011 and 2012): the
  snippets found report effects on liquidity, market-order use and midpoint-return
  autocorrelation, but none measured order-sign persistence before and after [S]. I found no
  published event study of sign-ACF around a tick change [S]; this is a gap the project's weeks
  5 to 6 could fill [I].

## 3. Crypto-specific evidence

- Donier and Bonart ("A million metaorder analysis of market impact on the Bitcoin", arXiv
  1412.4503): full Bitcoin/USD exchange data (Mt.Gox era) with more than a million reconstructed
  metaorders; square-root impact holds over four decades despite little market making and
  statistical arbitrage; metaorder signs have ACF exponent around 0.4, similar to trade signs;
  metaorder size and duration distributions are not power laws [S]. [I] The last point means
  LMF's gamma = alpha - 1 should not be assumed to hold on crypto without checking.
- Schnaubelt, Rende and Krauss (J. Risk Financial Manag. 12(1), 2019): BTC/USD limit order books
  from major exchanges; most stylized facts carry over; books are shallow, which they link to a
  retail rather than institutional base; trade-size distributions are idiosyncratic; trade-size
  autocorrelation about 0.12 [S].
- Kononovicius and Ruseckas (arXiv 1809.02772) and a "route to maturity" paper (arXiv
  1804.05916) report Bitcoin return and volatility scaling moving towards stock-like values over
  time [S]; about returns, not signs.
- "The Quarter-Hour Effect" (arXiv 2607.09426, submitted July 2026): six Binance USDT-margined
  perpetuals; introduces a phase-resolved sign autocorrelation map; one-minute-lag order-flow
  persistence nearly vanishes just before the quarter hour, strong correlation appears at
  15-minute intervals, bursts are attributed to algorithmic participation, and trade-size
  roundness falls during them; quarter-hour imbalance is partly forecastable [S]. This is the
  closest existing work to this project; read it in full before week 3 [I].
- "Fundamentals of Perpetual Futures" (arXiv 2212.06888) signs Binance trades by taker side and
  finds taker imbalance moves against the perpetual's deviation from its no-arbitrage price [S].
- Coinbase versus Binance BTC books, Nov 2022 to Mar 2023 (SSRN, 2024): limit submissions and
  cancellations dominate price discovery over market orders [S].
- Tick size in crypto: Dyhrberg, Foley and Svec (JFQA 58(6), 2023) show that a near-zero tick
  invites costless undercutting that hurts market quality [S]; an AUT working paper studies 420
  tick-size increases and 434 decreases across seven crypto exchanges [S]. Binance BTCUSDT spot
  had a 0.01 tick against an average spread of about 0.44 in Dec 2022 (a small-tick book) [S];
  the futures contract uses 0.10 (repo Q4b, from testnet exchangeInfo).
- Bot share: I found no credible estimate of bot or retail share for Binance futures. Published
  figures (70% of stablecoin transfer volume, over 73% of Ethereum DEX volume) are on-chain and
  vendor-sourced [S], so they do not transfer [I].
- Competition: Binance held roughly 28 to 29% of crypto derivatives volume in 2025 while the
  Hyperliquid to Binance volume ratio rose from about 8% to about 13.6% during 2025 (The Block,
  CoinGlass, Kaiko coverage) [S]. [I] If retail or directional flow migrates to a DEX, the
  remaining Binance flow could become more algorithmic, a composition channel worth noting.

### 3.1 Binance events 2023 to 2026 usable as natural experiments

All dates from Binance announcement titles or snippets [S]; verify on binance.com before use.

| date | event | lever it moves |
|---|---|---|
| 2023-06-05 | USDT-M Liquidity Provider program adds weekly maker-volume qualification with negative maker fees | maker competition, quoting |
| 2023-08-29 | tick-size update, multiple USDT-M perpetuals | relative tick |
| 2023-10-31 | Futures Taker Program launched, up to 25% taker discount by volume | cost of aggressive splitting |
| 2024-01-03 | LP program upgrade, USDC-margined maker volume counts | maker competition |
| 2024-06-03 | LP program update, threshold 0.20% weekly maker share, quoting-ranking stream removed | maker competition |
| 2024-09-20 | tick-size update, seven contracts | relative tick |
| 2025-01-28, 2025-08-12 | Taker Program updates (2025-08-12: 10/14/18% tiers) | taker costs |
| 2025-10-17, 2025-12-15, 2025-12-22 | tick-size updates, several small-cap contracts | relative tick |
| 2025-11-20 | RPI (Retail Price Improvement) orders on selected USDT-M symbols; RPI orders match only non-algorithmic orders; RPI trades are not tagged in trade data | retail versus algo segmentation |

[I] The Taker Program (between the 2023-07 and 2024-07 snapshots) is the single event whose
timing best matches the big jump in Q10's D. It lowers the cost of trading aggressively for
large takers, which should increase taker-side algorithmic splitting. It applies to all
contracts at once, so it offers no untreated control group; tick-size changes are per contract
and are the better difference-in-differences design.

## 4. Relative tick size as a driver

- Large-tick assets (spread almost always one tick, price rarely moves) are a distinct class;
  models for small-tick books fit them poorly (arXiv 1310.4539) [S].
- Eisler, Bouchaud and Kockelkoren ("The price impact of order book events", arXiv 0904.0900;
  Quantitative Finance 2012): for large-tick stocks a model with permanent, non-fluctuating
  impact of every event fits; small-tick stocks need a history-dependent part [S].
- Dayri and Rosenbaum ("Large tick assets: implicit spread and optimal tick size", arXiv
  1207.6325; Market Microstructure and Liquidity 2015): the implicit spread replaces the quoted
  spread for large-tick assets and restores the spread-volatility relation; an optimal tick
  corresponds to eta = 1/2 [S].
- Briola, Bartolucci and Aste ("Deep Limit Order Book Forecasting", arXiv 2403.09267; HLOB,
  arXiv 2405.18938, Expert Systems with Applications 2024): on 15 NASDAQ stocks, forecastability
  depends on microstructure; large-tick stocks have compact books that deep models exploit,
  small-tick books are sparse and hard to model; high forecast accuracy need not be tradable [S].
- Garèche, Disdier, Kockelkoren and Bouchaud (arXiv 1304.6819) model the best-queue dynamics of
  large-tick NASDAQ stocks (2010) with a 2D Fokker-Planck equation [S].
- A tick-size and time-priority study reports non-HFTs submit more market orders as relative
  tick rises, because queue priority is hard to win [S] (unverified copy).
- [I] Mechanisms by which a larger relative tick could raise next-sign predictability on
  aggTrades: (a) queue depletion: when the best queue is thick, many takers hit the same price
  in sequence, and the queue size becomes a visible state that predicts the next sign; (b)
  fewer price levels per move, so trade-price changes are informative (Q9's gbm_all gain over
  gbm_signs comes from price-move features); (c) bid-ask bounce dominates for small-tick
  assets, pushing sign flips. Coins whose price fell between 2023 and 2025 at a fixed tick
  became larger-tick without any exchange action, which is the confound Q4b flagged.

## 5. Proxies computable from aggTrades alone

Fields assumed: agg_trade_id, price, quantity, first_trade_id, last_trade_id, transact_time
(ms), is_buyer_maker. Binance defines an aggTrade as fills from the same taker order at the same
price at the same time [S]; the futures WebSocket stream groups by price and side per 100 ms
[S], and whether the archive files follow the spot or the stream rule should be checked on the
data [I].

1. **Sweep share.** Share of aggTrades sharing a ms timestamp and sign with the previous one
   (one taker order walking the book). Mechanical, not splitting; always report it so other
   proxies can be computed with sweeps collapsed to one event [I].
2. **Fills per aggTrade.** last_trade_id minus first_trade_id plus 1: how many maker orders one
   taker hit at one price; a direct proxy of queue fragmentation and maker count [I].
3. **Run lengths.** Distribution of same-sign run lengths after collapsing sweeps; tail exponent
   of run length as a crude alpha, compared with 1 + gamma (LMF) [I]. Proxy metaorder rules from
   the literature group same-sign trades with an inter-trade time cap (arXiv 2607.04280,
   2602.19590) [S].
4. **Equal-size repeats.** Share of consecutive same-sign events with identical quantity (or
   identical USD notional within 1%); slicing algorithms often use fixed child sizes [I].
5. **Size roundness.** Share of quantities that are round in coin units or USD notional (for
   example a multiple of 10, 100, 1000 USD); falling roundness is used as an algorithmic
   footprint (2607.09426; Quantitative Brokers) [S].
6. **Timing regularity.** Coefficient of variation of gaps within same-sign, same-size
   sequences; low values suggest TWAP-style slicing [I]. Clock-phase concentration: share of
   events and of sign persistence at second, minute and quarter-hour boundaries, following the
   phase-resolved ACF of 2607.09426 [S]; also around funding times.
7. **Short versus long ACF.** ACF at lags 1, 10, 100 and fitted gamma on lags above 100,
   reported separately, to test the two-power-law picture [S] and the Primicerio-Challet
   concurrency effect [I].
8. **Relative tick and tick constraint.** tick / price (tick from dated exchangeInfo snapshots
   or announcements, not the current value), and the share of consecutive events at an
   unchanged price, which measures how tick-bound the book is without needing quotes [I].
9. **Bounce share.** Share of sign flips with the price moving back to the previous level
   (bid-ask bounce), a small-tick signature [I].
10. **Liquidation-like bursts.** Same-sign bursts with large notional during a fast price move
    in one direction; a rough stand-in for forced liquidations given the missing liquidation
    files [I].
11. **Size-sign coupling.** Correlation of trade size with run position (does size shrink
    along a run, as Lillo-Farmer's compensation suggests?) [I].

## 6. Candidate drivers table

| candidate driver | why it would raise predictability | proxy computable from aggTrades | key reference |
|---|---|---|---|
| more algorithmic order splitting | more child trades per metaorder means longer same-sign runs | run-length tail, equal-size repeat share, gap regularity | Lillo, Mike, Farmer 2005; Toth et al. 2015; Sato and Kanazawa 2023 |
| heavier-tailed metaorder sizes | LMF gives gamma = alpha - 1, so smaller alpha means slower ACF decay | run-length tail exponent vs 1 + gamma | Lillo, Mike, Farmer 2005; Sato and Kanazawa 2023 |
| fewer concurrent large metaorders | concurrency mixes signs and weakens memory; fewer means cleaner runs | ratio of lag-1 to lag-100 ACF; run purity | Primicerio and Challet 2019 |
| clock-periodic bots | scheduled flow makes sign and timing forecastable at fixed phases | phase-resolved ACF, minute and quarter-hour concentration, size roundness | arXiv 2607.09426 |
| cheaper aggressive trading for large takers | lowers cost of splitting via market orders | taker-side run lengths before vs after 2023-10-31 | Binance Taker Program 2023 [S] |
| maker competition and rebates | thicker, more stable queues make queue depletion predictable | fills per aggTrade, unchanged-price share | Binance LP program 2023, 2024 [S]; Eisler, Bouchaud, Kockelkoren 2012 |
| larger relative tick | tick-bound book with one-tick spread makes price moves and queue state informative, less bounce | tick / price, unchanged-price share, bounce share | Briola et al. 2024; Dayri and Rosenbaum 2015; Q4b |
| smaller trade sizes | more trades per unit of demand, so more same-sign repeats | median USD notional, small-trade share | Kyle, Obizhaeva, Tuzun; O'Hara, Yao, Ye 2014 |
| liquidation cascades | forced one-sided market orders cluster | same-sign high-notional bursts during fast moves | arXiv 2607.27070, 2608.03616 |
| flow composition (retail to DEX, or retail segmented by RPI) | remaining flow more algorithmic and regular | roundness share, size distribution shape | Kaiko / The Block coverage [S]; Binance RPI 2025 [S] |
| sweeps in aggregation | one taker order appears as several same-sign records | same-ms same-sign share | Binance API docs [S] |

## References

1. Lillo, F., Mike, S., Farmer, J. D. (2005). Theory for long memory in supply and demand. Phys. Rev. E 71, 066122. https://arxiv.org/abs/cond-mat/0412708 ; https://www.doi.org/10.1103/PHYSREVE.71.066122
2. Toth, B., Palit, I., Lillo, F., Farmer, J. D. (2015). Why is order flow so persistent? J. Econ. Dyn. Control 51, 218 to 239. https://arxiv.org/abs/1108.1632
3. Sato, Y., Kanazawa, K. (2023). Inferring microscopic financial information from the long memory in market-order flow: a quantitative test of the Lillo-Mike-Farmer model. Phys. Rev. Lett. 131, 197401. https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.131.197401 ; https://arxiv.org/abs/2301.13505
4. Sato, Y., Kanazawa, K. (2023). Quantitative statistical analysis of order-splitting behavior of individual trading accounts in the Japanese stock market over nine years. Phys. Rev. Research 5, 043131. https://physics.aps.org/featured-article-pdf/10.1103/PhysRevResearch.5.043131
5. Lillo, F. (2023). Physics Viewpoint on the LMF test. Physics 16, 192. https://physics.aps.org/articles/pdf/10.1103/Physics.16.192
6. Sato, Y., Kanazawa, K. (2025). Why do financial prices exhibit Brownian motion despite predictable order flow? https://arxiv.org/abs/2502.17906
7. Lillo, F., Farmer, J. D. (2004). The long memory of the efficient market. Stud. Nonlinear Dyn. Econom. 8. https://arxiv.org/abs/cond-mat/0311053
8. Bouchaud, J.-P., Farmer, J. D., Lillo, F. (2008). How markets slowly digest changes in supply and demand. https://arxiv.org/abs/0809.0822
9. Mike, S., Farmer, J. D. (2008). An empirical behavioral model of liquidity and volatility. J. Econ. Dyn. Control 32, 200 to 234. https://arxiv.org/abs/0709.0159
10. Primicerio, K., Challet, D. (2019). Large large-trader activity weakens the long memory of limit order markets. Market Microstructure and Liquidity. https://arxiv.org/abs/1803.08390
11. Gould, M. D., Porter, M. A., Howison, S. D. (2016). The long memory of order flow in the foreign exchange spot market. Market Microstructure and Liquidity 2. https://arxiv.org/abs/1504.04354
12. Tick size reduction and price clustering in a FX order book. https://arxiv.org/abs/1307.5440
13. Is high-frequency trading inducing changes in market microstructure and dynamics? https://arxiv.org/abs/1006.5490
14. Unreviewed write-up on equity trade-sign ACF 2000 to 2013 (authors not identified). https://terbium.io/2016/11/autocorrelation/
15. Kyle, A. S., Obizhaeva, A. A., Tuzun, T. Microstructure invariance in U.S. stock market trades. https://pages.nes.ru/aobizhaeva/Kyle_Obizhaeva_Tuzun.pdf
16. O'Hara, M., Yao, C., Ye, M. (2014). What's not there: odd lots and market data. J. Finance 69(5), 2199 to 2236. https://ideas.repec.org/a/bla/jfinan/v69y2014i5p2199-2236.html
17. Quantitative Brokers (2022). Human-to-machine trading: historical profiles for E-mini S&P 500 and 10-year futures since 2012. https://www.quantitativebrokers.com/whitepapers/2022-02b
18. Eisler, Z., Bouchaud, J.-P., Kockelkoren, J. (2012). The price impact of order book events: market orders, limit orders and cancellations. Quantitative Finance. https://arxiv.org/abs/0904.0900
19. Dayri, K., Rosenbaum, M. (2015). Large tick assets: implicit spread and optimal tick size. Market Microstructure and Liquidity 1(1). https://arxiv.org/abs/1207.6325
20. Gareche, A., Disdier, G., Kockelkoren, J., Bouchaud, J.-P. (2013). A Fokker-Planck description for the queue dynamics of large tick stocks. https://arxiv.org/abs/1304.6819
21. Modeling the coupled return-spread high frequency dynamics of large tick assets. https://arxiv.org/abs/1310.4539
22. Briola, A., Bartolucci, S., Aste, T. (2024). Deep limit order book forecasting. https://arxiv.org/abs/2403.09267
23. Briola, A., Bartolucci, S., Aste, T. (2024). HLOB: information persistence and structure in limit order books. Expert Systems with Applications. https://arxiv.org/abs/2405.18938
24. No tick-size too small: a general method for modelling small tick limit order books. https://arxiv.org/abs/2410.08744
25. Dyhrberg, A. H., Foley, S., Svec, J. (2023). When bigger is better: the impact of a tiny tick size on undercutting behavior. JFQA 58(6), 2387 to 2416. https://ideas.repec.org/a/cup/jfinqa/v58y2023i6p2387-2416_4.html
26. Tick size changes across seven crypto exchanges (AUT working paper). https://acfr.aut.ac.nz/__data/assets/pdf_file/0008/926567/Tick-size-paper.pdf
27. Donier, J., Bonart, J. (2015). A million metaorder analysis of market impact on the Bitcoin. https://arxiv.org/abs/1412.4503
28. Schnaubelt, M., Rende, J., Krauss, C. (2019). Testing stylized facts of Bitcoin limit order books. J. Risk Financial Manag. 12(1), 25. https://www.mdpi.com/1911-8074/12/1/25
29. Kononovicius, A., Ruseckas, J. Order book model with herd behavior exhibiting long-range memory. https://arxiv.org/abs/1809.02772
30. Bitcoin market route to maturity? Evidence from return fluctuations, temporal correlations and multiscaling effects. https://arxiv.org/abs/1804.05916
31. The quarter-hour effect: periodic algorithmic trading and return predictability in cryptocurrency futures (2026). https://arxiv.org/abs/2607.09426
32. Fundamentals of perpetual futures. https://arxiv.org/abs/2212.06888
33. Where does the criticality live? Early-warning signals across seven crypto-perpetual liquidation cascades (2026). https://arxiv.org/abs/2607.27070
34. Measuring the engine of a liquidation cascade: subcritical branching inside a first-order transition (2026). https://arxiv.org/abs/2608.03616
35. Metaorder identification with a time threshold (2026). https://arxiv.org/abs/2607.04280
36. Goliath and Gebbie (2026). Metaorder modelling and identification from public data. https://arxiv.org/abs/2602.19590
37. Binance. Aggregate trade definition (spot glossary). https://developers.binance.com/docs/binance-spot-api-docs/faqs/spot_glossary
38. Binance. USDT-M futures aggregate trade streams. https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Aggregate-Trade-Streams
39. Binance. Updates on tick size for multiple USDT-M perpetual futures contracts (2023-08-29). https://www.binance.com/en/support/announcement/updates-on-tick-size-for-multiple-usd%E2%93%A2-m-perpetual-futures-contracts-2023-08-29-8764f0d84e6b4c7abc97f036bb6f9ebc
40. Binance. Updates on tick size (2024-09-20). https://www.binance.com/en-AE/support/announcement/detail/fa192e78242d4d96be9562ab7d76a10a
41. Binance. Updates on tick size (2025-10-17). https://www.binance.com/en-AE/support/announcement/detail/fd11627dc39046b791b7504a2f08e3fc
42. Binance. Updates on tick size (2025-12-15). https://www.binance.com/en/support/announcement/baee5eb8aa8447c0810512b9da108f0a
43. Binance. Updates on tick size (2025-12-22). https://www.binance.com/en/support/announcement/1cd08ee9bafd40a2a94e8dfc58408f82
44. Binance. Futures Liquidity Provider program change effective 2023-06-05. https://www.binance.com/en/feed/post/583227
45. Binance. Futures Upgrades Taker Program (2023-10-31). https://www.binance.com/en/support/announcement/detail/143cee3a83944c4da2b1a53f302f45f0
46. Binance. USDT-M Futures Liquidity Provider Program upgrade (2024-01-03). https://www.binance.com/en/support/announcement/detail/f5d3200b65104308b8349cee59a2296e
47. Binance. LP program update (June 2024). https://www.binance.com/bg/square/post/7238586397249
48. Binance. Futures Updates Taker Program (2025-01-28). https://www.binance.com/en/support/announcement/1d115917f1e24f83b93c8adfc41708ef
49. Binance. Futures Updates Taker Program (2025-08-12). https://www.binance.com/support/announcement/detail/bec831262e4b4a49b021e6f4030921be
50. Binance. RPI order book (API docs). https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Order-Book-RPI
51. ChainCatcher. Binance futures to launch RPI orders (2025). https://www.chaincatcher.com/en/article/2221342
52. The Block. Hyperliquid chips away at Binance's derivatives dominance. https://www.theblock.co/post/368674/hyperliquid-captures-80-of-decentralized-perps-market-chipping-away-at-binance
