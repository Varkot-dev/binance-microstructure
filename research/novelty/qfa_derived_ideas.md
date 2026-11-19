# Novelty and prior-art check: project ideas derived from the QFA papers

Checked 2026-11-19. Scope: four ideas that combine the Penn QFA readings in `qfa/` (Dou,
Goldstein and Ji on AI collusion and AI-planning fragility; Fu, Li, Musto and Pearson on 0DTE
limit orders; Dieckmann on yield-curve PCA) with this repo's Binance USD-M futures work. Read
alongside `qfa/NOTES.md`, which ranks project ideas; this file asks whether each idea is already
done and what would make it new.

## Evidence tags and access limits

- **[V]** verified by me in this session: a file I opened, an S3 listing I parsed, or a number I
  computed from downloaded data.
- **[S]** stated in a web search result (snippet or search-tool summary). The page itself was not
  opened, so wording, numbers and author lists should be checked before citing.
- **[I]** my inference or judgement.

Access limits in this session: WebFetch could not reach arxiv.org or blog.amberdata.io, and the
proxy refused www.deribit.com, history.deribit.com and datasets.tardis.dev. So every claim about
an outside paper or report is at best [S]. Nothing here was invented; where a search could not
confirm something (for example the full author list of the 2026 Finance Research Letters paper),
the text says so.

## Summary

| idea | prior-art status | closest prior work | novelty for this student | free-data feasibility |
|---|---|---|---|---|
| 1. Algorithmic / AI collusion in crypto market making | **Open empirically, crowded in theory** | Theory and simulation: Calvano et al. (AER 2020), Colliard, Foucault and Lovo (2022 to 2025), Cont and Xiong (Math Finance 2024), Cartea, Chang and Penalva (tick size), Dou, Goldstein and Ji (NBER w34054, 2025). Empirical non-crypto: Assad et al. (JPE 2024), Christie and Schultz (1994). No empirical crypto study found. [S] | High if framed as "competition among liquidity providers" tests, not as proof of collusion | Medium-low: no trader IDs; free top-of-book quotes only 2023-05 to 2024-04 [V] |
| 2. Fragility in the algorithmic era: depth before cascades | **Partly done** (event studies of 2025-10-10 exist; long-run link to algorithmic participation does not) | arXiv 2607.27070 (Garcia Seuma, seven BTC cascades 2022 to 2025), arXiv 2608.03616, arXiv 2512.01112 (ADL), Kaiko, Amberdata, FTI on 10/10. [S] | Medium-high for a 2023 to 2026 panel linking the repo's slicing proxies to depth resilience | High for 2023 to 2026 (bookDepth from 2023-01-01 [V]); 2022 events have no free depth [V] |
| 3. Crypto 0DTE options and spot/futures volatility | **Partly done** | Finance Research Letters vol. 107 (2026) on Deribit expiry-day reversals and gamma; Lachowicz (SSRN) finds gamma walls negligible; Glassnode GEX; equity 0DTE papers (Brogaard, Han and Won; Dim, Eraker and Vilkov). [S] | Medium if done on Binance with hourly greeks; low if it repeats the Deribit study | Low: Binance option files cover only 2023-05-18 to 2023-10-23 and are tiny [V]; Deribit history not free beyond Tardis first-of-month days [S] |
| 4. FOMC, CPI and yield-curve events at intraday frequency | **Largely done for prices and volatility; open for order-flow and liquidity** | Johansson and Vilhelmsson (SSRN 4478184), Karau (JIMF 2023), FRL 2026 hourly FOMC study, a Fed Board paper on crypto and macro news, ECB WP 3280, NY Fed SR 1052, BIS WP 1219. [S] | Medium: depth withdrawal, order-sign memory and Hawkes endogeneity around releases, plus PCA level vs slope surprise decomposition | High for crypto side; intraday Treasury yields are not free [I] |

Short version [I]: idea 2 is the strongest combination of novelty and feasibility, idea 1 is the
most novel but the hardest to make convincing, idea 4 needs a microstructure twist to be new, and
idea 3 is not feasible at a useful scale on free data.

---

## Idea 1. Algorithmic or AI-agent collusion in crypto markets

### Academic prior art

| paper | year, venue | data | frequency | finding | tag |
|---|---|---|---|---|---|
| Calvano, Calzolari, Denicolo, Pastorello, "Artificial Intelligence, Algorithmic Pricing, and Collusion" | 2020, AER 110(10) 3267-97 | Simulated Q-learning pricing agents in oligopoly | Simulation | Agents learn supra-competitive prices sustained by punishment phases; collusion weakens with more firms | [S] |
| Dou, Goldstein, Ji, "AI-Powered Trading, Algorithmic Collusion, and Price Efficiency" | 2025, NBER WP 34054 (QFA reading) | Model plus RL simulations of informed speculators | Simulation | RL speculators sustain collusive supra-competitive profits without communication; two mechanisms; lower price efficiency and liquidity | [V] (PDF in `qfa/2026-11-11/`), [S] (NBER listing) |
| Colliard, Foucault, Lovo, "Algorithmic Pricing and Liquidity in Securities Markets" | 2022 CEPR DP 17606; revised 2025 | Q-learning market makers in a Glosten-Milgrom game | Simulation | Algorithmic market makers charge a markup over the competitive price; the markup rises when adverse selection falls (opposite of Nash), declines with the number of market makers | [S] |
| Cont, Xiong, "Dynamics of market making algorithms in dealer markets: learning and tacit collusion" | 2024, Mathematical Finance 34(2) 467-521 | Multi-agent deep RL market makers | Simulation | Spreads strictly above the competitive level without information sharing | [S] |
| Cartea, Chang, Penalva, "Algorithmic Collusion in Electronic Markets: The Impact of Tick Size" | SSRN 4105954 | Evolutionary game theory, Q-learning in a limit order book | Theory/simulation | Large tick obstructs competition; smaller tick lowers costs for takers | [S] |
| Cartea, Chang, Mroczka, Oomen, "AI-driven liquidity provision in OTC financial markets" | 2022, Quantitative Finance | Bandit algorithms setting spreads | Simulation | Collusive outcomes are fragile and unlikely in practice | [S] |
| "Cooperation between Independent Market Makers" | arXiv 2206.05410 | Q-learning market makers | Simulation | Stag-hunt payoffs let market makers learn supra-competitive spreads; more agents does not necessarily remove it | [S] |
| Assad, Clark, Ershov, Xu, "Algorithmic Pricing and Competition: Empirical Evidence from the German Retail Gasoline Market" | 2024, JPE 132(3) 723-771 | Station prices, adoption inferred from structural breaks | High-frequency retail prices | Adoption raises margins only in non-monopoly markets, and in duopolies only if both adopt | [S] |
| Christie, Schultz | 1994, J. Finance | Nasdaq quotes | Quotes | Market makers avoided odd-eighth quotes in 70 of 100 stocks, read as implicit collusion | [S] |
| Han, price clustering in crypto order books | 2024, J. Behavioral and Experimental Finance | One US crypto exchange | Order book | Orders cluster on round numbers; no collusion test seen in the snippet | [S] |
| Tick-size event study, seven crypto exchanges | Auckland ACFR paper (title not confirmed) | 420 tick increases, 434 decreases | Intraday | Market quality and order-flow migration after tick changes; no collusion measure in the snippet | [S] |

Search conclusion [S]: three separate searches found no empirical paper that tests for collusion
among crypto market makers using exchange data. The literature is theory and simulation plus
equity and gasoline precedents. A Wharton WIFPR blog post proposes a way to tackle algorithmic
collusion "in cryptocurrencies and beyond", which is policy, not measurement.

### Industry research

- Kaiko: liquidity concentration reports (8 exchanges hold over 90% of depth, 2023) and the
  "Alameda gap" after FTX, naming a handful of dominant market makers (Wintermute, Amber, B2C2,
  Genesis, Cumberland, Alameda). No competition or collusion study found. [S]
- No Glassnode, Amberdata, Galaxy or exchange research on collusion was found. [S]

### What the student could do with free Binance data, and whether it is done

| angle | status | what would make it new |
|---|---|---|
| Christie-Schultz grid test after tick cuts: do quotes and trades keep using the old coarse grid after Binance shrinks a tick (or stop using new fine ticks)? | **Open** in crypto [S, no prior found] | Binance changes ticks often; the SOLUSDT tick change (0.001 to 0.01, 2024-08 to 2025-07, see `research/market_evolution/README.md`) and others give many events. It is the empirical test of Cartea, Chang and Penalva's tick-size prediction. `qfa/NOTES.md` idea 3 proposes this. |
| Spreads relative to the competitive benchmark: decompose effective spread into adverse selection (price impact) and realized spread; test Colliard, Foucault and Lovo's sign prediction that algorithmic markups rise when adverse selection falls | **Open** for crypto [I] | A cross-section of 100+ symbols over 2023 to 2026, with symbol-level adverse selection measured from the repo's impact work (q2, q5). A positive realized-spread response to falling adverse selection is the theory's fingerprint, not a proof. |
| Structural breaks in quoting behaviour, Assad-style: detect when a symbol's liquidity provision starts to look algorithmic (minute-boundary bunching, small identical child orders, the Part A proxies) and test whether spreads then rise | **Open** [I] | Uses Part A's proxies as the "adoption" marker. Requires a credible control group and an instrument; hard. |

Hard limits [V]: free Binance futures `bookTicker` exists only from 2023-05-16 to 2024-03-30
(daily) and 2023-05 to 2024-04 (monthly) for BTCUSDT, so quoted spreads for 2024-05 onward must be
inferred from trades (effective spreads from aggTrades against bookDepth, or Roll-type
estimators). There are no trader or market-maker identifiers, so "collusion" cannot be shown
directly; the defensible claim is "behaviour consistent or inconsistent with competitive
liquidity provision" [I].

**Rating:** novelty high, feasibility medium-low, risk of an ambiguous result high [I].

---

## Idea 2. Market fragility in the era of algorithmic and AI trading

### Academic prior art

| paper | year, venue | data | frequency | finding | tag |
|---|---|---|---|---|---|
| Dou, Goldstein, Ji, "Financial Market Fragility in the Era of AI Planning" | Sept 2026 draft (QFA reading) | Model plus RL simulations with planning modules | Simulation | AI speculators coordinate intertemporally, create and exploit bubbles when feedback trading is strong, amplify fragility | [V] (PDF) |
| Kirilenko, Kyle, Samadi, Tuzun, "The Flash Crash: High-Frequency Trading in an Electronic Market" | 2017, J. Finance 72(3) | CME E-mini audit trail, 2010-05-06 | Trade-level, trader IDs | HFTs did not trigger the crash but exacerbated volatility | [S] |
| Brogaard, Carrion, Moyaert, Riordan, Shkilko, Sokolov, "High frequency trading and extreme price movements" | 2018, JFE 128(2) 253-265 | Equity data with HFT flags | Intraday | HFTs supply liquidity in single-stock extreme moves, but demand dominates when many stocks move together | [S] |
| Donier, Bouchaud, "Why Do Markets Crash? Bitcoin Data Offers Unprecedented Insights" | arXiv 1503.06704 (2015) | Full Bitcoin order book 2011 to 2014 | Order book | April 2013 crash came from scarce buy-side liquidity; latent liquidity measurable | [S] |
| Baumgartner, Guettler, Kim, "Bitcoin Flash Crash on May 19, 2021: What did really happen on Binance?" | 2022 working paper | Binance trades | Tick | Binance outage, apparent back-filled trades, price divergence about 7x the normal gap | [S] |
| Garcia Seuma, "Where does the criticality live? Early-warning signals are event-heterogeneous across seven crypto-perpetual liquidation cascades" | arXiv 2607.27070 (2026) | Minute price and 5-minute leverage/order-flow data, seven BTC cascades 2022 to 2025 incl. 2025-10-10 | 1 to 5 minutes | Critical-slowing-down signal in price in 5 of 7 events, absent in the two tariff-news shocks; single-event early-warning claims are fragile | [S] |
| "Measuring the engine of a liquidation cascade: subcritical branching inside a first-order transition" | arXiv 2608.03616 (2026) | Hyperliquid fill log, seven cascades | Fill-level | Oct 2025 cascade was subcritical, front-loaded, backstop-absorbed; about 63% of forced selling absorbed off-book; severity driven by liquidity withdrawal; no scalar pre-state (leverage, book fragility) grades severity | [S] |
| "Autodeleveraging: Impossibilities and Optimization" | arXiv 2512.01112 | Hyperliquid ADL on 2025-10-10 | Event | ADL cost to winners about $660m to $2.1bn depending on version; queue used ADL about 8x more than an optimal policy | [S] |
| "Explainable Patterns in Cryptocurrency Microstructure" | arXiv 2602.00776 | Binance Futures order book, 1-second, 2022 to 2025 | 1 second | Predictive models stress-tested on the 2025-10-10 crash | [S] |
| "When Does Order Flow Matter? State-Dependent L2 Liquidity-State Transitions in Crypto Futures" | arXiv 2607.09230 | Crypto futures L2 | Intraday | Liquidity-state transitions (details not seen) | [S] |
| CeFi vs DeFi on 2025-10-10, "Same Shock, Same Assets, Different Microstructure" | ResearchGate preprint | Venue comparison | Event | Hyperliquid stayed up, processed about $10.3B of liquidations, triggered ADL | [S] |
| AEA 2026 paper, "Perpetual Futures and Basis Risk: Evidence from Cryptocurrency" | 2026 ASSA, preliminary | Perps vs quarterlies | Daily/intraday | Liquidations migrated to perps; perps' liquidity advantage partly reflects that | [S] |

### Industry research

- Kaiko on 2025-10-10: "voluntary liquidity gap", books on major BTC venues near empty for
  minutes; BTC 1% depth from about $8M to about $3M at trough, about $6M later; six months later
  liquidity for BTC, ETH, XRP, SOL still impaired. [S]
- Amberdata: 10 bp depth from $48M to $26M, a "40% depth collapse", not restored three months
  later. [S]
- FTI Consulting: top-of-book depth down more than 90% on key venues; spreads from single-digit
  bp to double-digit percent at extremes. [S]
- Kaiko on FTX (Nov 2022): BTC depth down 57% on Kraken, 32% Bitstamp, 25% Binance, 18%
  Coinbase from Nov 5; SOL depth under half. [S]
- August 5, 2024: Binance Research reports about $819M liquidations (about $688M longs);
  CoinDesk about $1B; Amberdata's volatility report covers Binance ETH-USDT 1% and 5% depth. [S]
- BIS commentary (secondhand) calls perpetual leverage strongly procyclical without clearing
  safeguards. [S]

### What the student could do, and whether it is done

| angle | status | what would make it new |
|---|---|---|
| Depth path around 2025-10-10, 2024-08-05 on Binance perps | **Done** at the event level by Kaiko, Amberdata, FTI and the arXiv cascade papers [S] | Not new by itself. |
| Long-run panel: does depth resilience (time for bookDepth at plus/minus 1% to recover after a shock) fall as the algorithmic-slicing proxies from Part A rise, across 100+ symbols, 2023 to 2026? | **Open** [I; no prior found] | This links the repo's unique finding (the shift to tiny sliced trades) to fragility, which no cited paper does. It tests the Dou, Goldstein and Ji mechanism empirically: fragility should rise with algorithmic participation interacted with positive-feedback strength (proxied by funding, open-interest growth, and the Hawkes branching ratio from q6). |
| Pre-cascade withdrawal: did depth thin before the price fell (fragility building) or only after? | **Partly done**: 2608.03616 says the signature is in the liquidity sector, 2607.27070 says early warning is event-specific [S] | Doing it on Binance bookDepth across all perps and many smaller shocks (not just seven big events) gives the sample size those papers lack. |
| 2022 events (LUNA May 2022, FTX Nov 2022) | **Not feasible with free depth** [V] | bookDepth starts 2023-01-01 and bookTicker 2023-05; for 2022 only trades, klines and metrics (open interest from 2020-09) are free. |

Data facts [V]: `data/futures/um/daily/bookDepth/BTCUSDT/` runs 2023-01-01 to 2026-11-17; each file
holds snapshots about every 30 seconds (2,879 on 2025-10-10) of cumulative depth and notional at
-5..-1 and 1..5 percent from mid. `metrics` (open interest, long/short ratios) runs 2020-09-01 to
2026-11-17. There is no free liquidation feed.

**Data-quality warning [V]:** on BTCUSDT the bid side of bookDepth is frozen at exactly
17.654 BTC ($2,142,547) in every band from -1% to -3% (sometimes to -4%) from 2025-10-10 19:15:32
UTC, before the 21:00 crash, through at least 2025-10-15 (440 frozen snapshots on 10-10, 2,812 on
10-12, 1,542 on 10-15; none on 10-25). A near-identical value appears at 15:30:42. The ask side
looks normal. This is almost certainly an artifact of Binance's snapshot process, not real depth,
and naive use would "show" a 99% bid-depth collapse hours before the crash. Any fragility study
must screen for identical consecutive band values.

**Rating:** novelty medium-high for the panel angle, feasibility high, closest prior work arXiv
2607.27070 and 2608.03616 [I].

---

## Idea 3. 0DTE options in crypto and spot or futures volatility

### Academic prior art

| paper | year, venue | data | frequency | finding | tag |
|---|---|---|---|---|---|
| "Bitcoin option expiration, gamma exposure, and intraday price reversals" (Dustin Weiss et al.; full list not confirmed) | 2026, Finance Research Letters 107, 110340 | 1,059 Deribit expiry days, Jan 2021 to Dec 2023 | 5 minutes | Dip before expiry and recovery after when ATM open interest is top-decile; strongest with negative reconstructed gamma; about $50M a year transferred between writers and holders | [S] |
| Lachowicz, "Do Gamma Walls Actually Move Bitcoin Prices at Deribit?" | SSRN 5782822 | Deribit | Not confirmed | Gamma walls do not meaningfully move BTC; gamma small relative to spot and options volume | [S] (from one search summary; a second search could not find it) |
| Brogaard, Han, Won, "How Does Zero-Day-to-Expiry Options Trading Affect the Volatility of Underlying Assets?" | Working paper | S&P 500, about 10 years | 5 minutes | One-SD rise in 0DTE volume associated with almost 14% higher daily volatility | [S] |
| Dim, Eraker, Vilkov, "0DTEs: Trading, Gamma Risk and Volatility Propagation" | SSRN 4692190 | SPX 0DTE | Intraday | No evidence that 0DTE open-interest gamma raises index volatility | [S] |
| Beckmeyer, Branger, Gayda, "Retail Traders Love 0DTE Options... But Should They?" | 2023 working paper | SPX options | Intraday | Retail loses; about 60% of losses from transaction costs; about 75% of retail SPX option trades are 0DTE | [S] |
| Bandi, Fusari (with Reno) | Working papers | SPX intraday options 2014 to 2023 | Intraday | Valuation and hedging framework for 0DTE | [S] |
| Fu, Li, Musto, Pearson, "Hope at a Reasonable Price: Customer Use of Limit Orders in the 0DTE Market" | 2026, SEC DERA WP (QFA reading) | OPRA, resequenced | Tick | Many customers supply liquidity in 0DTE via limit orders | [V] (PDF) |

No academic study of daily-expiry crypto options and realized spot volatility was found beyond
the FRL paper. [S]

### Industry research

- Glassnode: taker-flow-based gamma exposure and a strike-level GEX heatmap (launched Feb 2026);
  not split by 0DTE. [S]
- Galaxy (quoted in search results): Deribit dealer gamma about $15M per 1% BTC move vs about
  $14B per 1% of BTC market value, i.e. small. [S]
- Amberdata / Deribit Insights Q1 2023 report: 0DTE backtest; selling BTC and ETH 0DTEs in
  high-vol bull runs unprofitable. [S]
- Deribit: daily expiries at 08:00 UTC, up to 4 daily expiries for BTC and ETH. Coinbase closed its
  $2.9B acquisition of Deribit on 2025-08-14. Deribit's options open-interest share was about 90% in
  mid-2025 by one account, under 39% in early 2026 by another. [S]
- Binance Options: BTCUSDT and ETHUSDT daily European options, 2 to 3 day life, expire 08:00 UTC. [S]

### Free crypto options data [V unless noted]

S3 listing of `data/option/` parsed block by block: only `daily/`, with two datasets.

| dataset | symbols | dates | files | content |
|---|---|---|---|---|
| EOHSummary | BTCUSDT, ETHUSDT (147 days each), BNBUSDT (121), XRPUSDT (99), DOGEUSDT (31) | 2023-05-18 to 2023-10-23, with gaps | one zip per day | hourly row per option: OHLC, volume, best bid/ask and sizes, bid/ask IV, mark price and IV, delta, gamma, vega, theta, open interest |
| BVOLIndex | BTCBVOLUSDT, ETHBVOLUSDT | 2023-06-20 to 2026-11-17 | 2,442 keys for BTC including checksums | Binance implied-vol index, one row per second |

My own count on all 147 BTCUSDT EOHSummary days: **85 days carry a series that expires that
day** (including Mon to Thu and weekends, so true dailies, not only Friday weeklies); same-day
series appear only in hours 00 to 07 (expiry 08:00 UTC); they account for 12.3% of the summed
`volume_usdt`, but that column sums to only about $4M over all 147 days, so Binance options were
very thin. Note: `qfa/NOTES.md` says EOHSummary lists no daily expiries; that was based on four
sampled days and is contradicted by this full count.

Deribit: public history endpoints and Tardis could not be reached from this session. Search
results say Tardis gives the first day of each month free for every exchange and data type,
including Deribit options since 2019-03-30, and Deribit's own private trade-history endpoints
cover only the user's own trades. [S] Whether `history.deribit.com` public market trades are
free and complete was not verified [I: worth checking from a machine with access].

### Feasibility verdict for idea 3

Not feasible at a useful scale for free [I]. Free Binance data gives about 85 expiry mornings
of hourly greeks in 2023 on a market that traded a few million dollars in total; there is no
trade side, so dealer gamma sign cannot be inferred the way Glassnode does it. Tardis first-day
files give about 12 Deribit days a year. A minimal free study is possible: same-day open interest
and gamma on Binance vs Binance futures 00:00 to 08:00 UTC realized volatility and the
BTCBVOL index on expiry vs non-expiry mornings. That would be a replication-in-miniature of the
FRL paper on a much thinner venue, so novelty is low.

**Rating:** partly done; novelty low to medium; free feasibility low [I].

---

## Idea 4. FOMC, CPI and yield-curve events and crypto at intraday frequency

### Academic prior art

| paper | year, venue | data | frequency | finding | tag |
|---|---|---|---|---|---|
| Johansson, Vilhelmsson, "Bitcoin's Price Alchemy: Unraveling the Influence of Macro Announcements on Volatility and Trading Volume in an Era of Rising Inflation" | SSRN 4478184 | Several large exchanges | High-frequency | FOMC and CPI have a large effect on BTC realized volatility and volume, starting in 2021; FOMC-day abnormal returns reverse within about 4 hours | [S] |
| Karau, "Monetary policy and Bitcoin" | 2023, J. International Money and Finance | Event study, high-frequency | Intraday | No systematic response before late 2020; response since then, like other risky assets | [S] |
| "Scheduled FOMC statements and intraday macro event risk in cryptocurrency markets" | 2026, Finance Research Letters | 41 FOMC statements 2021-01 to 2026-01, hourly Coinbase BTC and ETH | Hourly | BTC mean absolute hourly return from 0.66% to 1.25%, volume 2.54x in the post-statement hour | [S] |
| Federal Reserve paper on crypto and macro news (title, authors not confirmed) | reported 2025 | Intraday CoinDesk prices 2015 to 2025 | Intraday | Since 2021 BTC and ETH react to FOMC, CPI, payrolls; one-SD CPI upside surprise about -30 bp BTC, -45 bp ETH; non-yield monetary shocks matter | [S] |
| ECB WP 3280, "DeFi-ying the Fed? Monetary policy..." | ECB | 2021 to 2026 | High-frequency surprises | Strong impact of monetary surprises on Bitcoin | [S] |
| Benigno et al., "The Bitcoin-Macro Disconnect" | NY Fed Staff Report 1052 | Intraday | Intraday | Bitcoin orthogonal to monetary and macro news | [S] |
| Aldasoro et al. | BIS WP 1219 | Crypto shock series | Daily | US monetary shocks drive crypto; stablecoin cap falls after tightening | [S] |
| Springer article using Jarocinski-Karadi shock split | DOI 10.1007/s10436-023-00432-3 | Fed and ECB surprises, 2-year yields | High-frequency | Claims of a strong BTC response to pure policy shocks not supported | [S] |
| SSRN 4910537 (via Quantpedia) | | Structural VAR with 2-year yield | Daily | Crypto demand shocks explain over 80% of BTC daily variance | [S] |
| "Returns and Order Flow Imbalances: Intraday Dynamics and Macroeconomic News Effects" | arXiv 2508.06788 | Not confirmed whether crypto | Intraday | Announcements temporarily raise price impact and dampen flow impact | [S] |

### Industry research

- Kaiko: BTC absolute hourly moves larger around CPI since 2022; weaker for FOMC. Kaiko collects
  two order-book snapshots per minute but no published CPI/FOMC depth event study was found. [S]
- Interdax (blog): abnormal BTC volatility in the hour before and during FOMC. [S]

### What the student could do, and whether it is done

| angle | status | what would make it new |
|---|---|---|
| Price, volatility and volume response of BTC/ETH to FOMC and CPI | **Done** [S] | Not new. |
| Liquidity around releases on Binance perps: bookDepth withdrawal in the minutes before, refill speed after, effective spreads by trade size | **Open** as far as searches show [S, I] | No crypto study of depth around scheduled releases was found. Binance bookDepth (30 s) from 2023 gives about 30 FOMC and 46 CPI events. |
| Order-flow structure around events: order-sign memory, Hawkes branching ratio and algorithmic-slicing proxies in event windows vs matched non-event windows | **Open** [I] | Unique to this repo's tooling (q1, q6, Part A proxies). Tests whether event trading is more endogenous or more sliced. |
| Yield-curve PCA (Dieckmann QFA session): does crypto respond to the level or the slope component of the announcement surprise? | **Partly done**: studies use 2-year yields or shock splits, not PCA factors [S] | Using level/slope/curvature from the QFA dataset is new in framing, but intraday Treasury yields are not free; daily curve changes on event days only allow a daily-level test [I]. `qfa/NOTES.md` idea 4 covers this. |
| Funding and open interest around releases | **Little found** [S] | `metrics` gives 5-minute open interest from 2020-09 [V]. |

**Rating:** done for prices; open for the microstructure angle; feasibility high [I].

---

## Startup opportunities

All competitor facts are [S] from search results unless marked; market sizing was not checked.

### A. Fragility and liquidity-risk monitor (from idea 2)

- **Product:** cross-venue depth resilience score, depth-withdrawal alerts, leverage (open
  interest, funding) vs depth "fuel vs fire" dashboard, with artifact screening of exchange depth
  feeds (the frozen bookDepth bug above is a concrete example of why clean data has value [V]).
- **Customers [I]:** market makers and prop desks (risk limits), crypto lenders and prime brokers
  (margin setting), exchanges and perp DEX risk teams (leverage caps, ADL policy), funds holding
  crypto ETFs, regulators.
- **Competitors:** Kaiko (liquidity metrics, S&P-backed), Amberdata, Coin Metrics, Glassnode;
  retail liquidation-heatmap tools (CoinGlass, Hyblock, Coinank, Velo, Laevitas) whose maps are
  modelled estimates, not observed positions. [S] DeFi risk firms (Chaos Labs, Gauntlet) were not
  confirmed by search. [I]
- **Defensibility:** low on raw data (commodity); moderate on validated models and an audited
  track record of alerts [I].
- **Risks:** the science says early warning is event-specific (2607.27070) and no scalar pre-state
  grades severity (2608.03616) [S], so false alarms are likely; incumbents can add a feature.

### B. Market-quality and liquidity-provider competition surveillance (from idea 1)

- **Product:** market-maker performance auditing for token issuers and exchanges (uptime,
  spread and depth obligations), plus competition diagnostics (Christie-Schultz grid tests,
  realized-spread markups, coordinated withdrawal).
- **Customers [I]:** token foundations paying market makers, exchanges listing tokens,
  MiCA-regulated venues and national competent authorities.
- **Competitors:** Solidus Labs (HALO; selected by ESMA under MiCA in 2025), Nasdaq SMARTS, Eventus,
  NICE Actimize, Chainalysis and others in the Datos Insights matrix. [S]
- **Defensibility:** proprietary labelled cases and exchange integrations [I].
- **Risks:** needs account-level data that only exchanges hold; long sales cycles; "collusion"
  findings are legally sensitive [I].

### C. Crypto options and 0DTE analytics (from idea 3)

- **Product:** same-day gamma and pin-risk analytics across Deribit, Binance, OKX, Bybit and CME.
- **Customers [I]:** options market makers, vol funds, retail options traders.
- **Competitors:** Amberdata Derivatives (ex Genesis Volatility), Laevitas, Block Scholes,
  Greeks.live, Glassnode GEX, Delphi Digital's free options dashboard, Sharpe Terminal. [S]
- **Defensibility:** low; crowded, and data depends on venue licensing (Deribit now owned by
  Coinbase) [S, I].
- **Risks:** academic evidence that crypto dealer gamma is small (Galaxy estimate, Lachowicz) [S]
  undercuts the product thesis.

### D. Event-aware crypto execution (from idea 4 and repo q7)

- **Product:** schedules for large perp or spot orders that avoid pre-release depth troughs and
  price the cost of trading through CPI/FOMC, using the q7 cost model.
- **Customers [I]:** funds and treasuries executing size, OTC desks.
- **Competitors:** execution management systems such as Talos (named in search results in a
  Nasdaq partnership) [S]; broker algos [I].
- **Risks:** narrow wedge; incumbents own order routing [I].

### E. Pre-deployment audit of RL and agentic trading systems (from the Dou, Goldstein and Ji papers)

- **Product:** sandbox that stress-tests a client's RL or LLM trading agent against copies of
  itself and other agents, flagging tacit-collusion or bubble-riding behaviour before launch.
- **Customers [I]:** funds deploying RL execution or market-making agents, exchanges, regulators
  writing AI rules.
- **Competitors:** nascent; Solidus has announced "agentic" compliance tooling [S].
- **Risks:** market may not exist yet; hard to sell "your bot might collude" [I].

Best fit for a student founder [I]: A or D, because both reuse this repo's measured strengths
(depth, impact, execution cost) and need only public data to prototype.

---

## References (URLs as returned by search; [S] unless noted)

QFA readings (local, [V]): `qfa/2026-11-11/AI-Powered_Trading_Algorithmic_Collusion.pdf`,
`qfa/2026-11-11/Financial_Market_Fragility_in_the_Era_of_AI_Planning.pdf`,
`qfa/2026-11-18/0dte_options_paper.pdf`, `qfa/2026-10-21/From_Yield_Curves_To_Trading.pdf`.

Collusion
- Calvano et al. 2020, AER: https://www.aeaweb.org/doi/10.1257/aer.20190623
- Dou, Goldstein, Ji, NBER w34054: https://www.nber.org/papers/w34054
- Colliard, Foucault, Lovo, CEPR DP17606: https://repec.cepr.org/repec/cpr/ceprdp/DP17606.pdf ; 2025 draft: https://www.iese.edu/wp-content/uploads/2025/01/2.-paper-Colliard-et-al.pdf
- Cont, Xiong, Math Finance 2024: https://spiral.imperial.ac.uk/entities/publication/06e8645b-bef9-494f-a459-b1c083b33dc9
- Cartea, Chang, Penalva, tick size: https://smallake.kr/wp-content/uploads/2022/12/SSRN-id4105954.pdf
- Cartea, Chang, Mroczka, Oomen, QF 2022: https://ideas.repec.org/a/taf/quantf/v22y2022i12p2171-2204.html
- Cooperation between Independent Market Makers: https://arxiv.org/pdf/2206.05410
- Assad, Clark, Ershov, Xu, JPE 2024: https://econpapers.repec.org/RePEc:ucp:jpolec:doi:10.1086/726906
- Han 2024, crypto price clustering: https://ideas.repec.org/a/eee/beexfi/v41y2024ics221463502400008x.html
- Crypto tick-size event study: https://acfr.aut.ac.nz/__data/assets/pdf_file/0008/926567/Tick-size-paper.pdf
- WIFPR blog on crypto collusion: https://wifpr.wharton.upenn.edu/blog/a-proposal-to-tackle-algorithmic-collusion-in-cryptocurrencies-and-beyond/
- Kaiko liquidity concentration: https://research.kaiko.com/insights/the-crypto-liquidity-concentration-report

Fragility
- Kirilenko et al. 2017: https://papers.ssrn.com/ab_id=1686004
- Brogaard et al. 2018 JFE: https://econpapers.repec.org/RePEc:eee:jfinec:v:128:y:2018:i:2:p:253-265
- Donier, Bouchaud: https://arxiv.org/pdf/1503.06704
- Baumgartner, Guettler, Kim, May 19 2021: https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/686754/6b-Tim-Baumgartner-May19.pdf
- arXiv 2607.27070: https://arxiv.org/abs/2607.27070
- arXiv 2608.03616: https://arxiv.org/html/2608.03616
- arXiv 2512.01112 (ADL): https://arxiv.org/html/2512.01112v2
- arXiv 2602.00776: https://arxiv.org/html/2602.00776v1
- arXiv 2607.09230: https://arxiv.org/pdf/2607.09230
- CeFi vs DeFi on 10/10: https://www.researchgate.net/publication/404288266
- AEA 2026 perps paper: https://www.aeaweb.org/conference/2026/program/paper/ByyFEfr4
- Kaiko on 10/10: https://research.kaiko.com/insights/when-october-surprise-meets-crypto-liquidity-drought
- Kaiko six-month follow-up (via Whale Alert): https://whale-alert.io/stories/b3a4016c6bb5b0/Kaiko-Liquidity-for-BTC-ETH-XRP-and-SOL-still-impaired-six-months-after-Oct-10-flash-crash-XRP-liquidity-has-not-recovered-to-pre-crash-levels
- Amberdata depth collapse: https://blog.amberdata.io/the-liquidity-that-vanished-inside-octobers-40-depth-collapse
- FTI Consulting: https://www.fticonsulting.com/insights/articles/crypto-crash-october-2025-leverage-met-liquidity
- Kaiko FTX analysis: https://marketing.kaiko.com/the-ftx-collapse-a-market-analysis ; The Block: https://www.theblock.co/post/188845/crypto-market-liquidity-dries-up-following-alameda-and-ftx-collapse
- Binance Research on Aug 5 2024: https://www.binance.com/en/research/projects/the-market-downturn-what-happened-and-what-to-expect
- Amberdata volatility report: https://go.amberdata.io/hubfs/AmberdataDissectVolatility.pdf

0DTE and options
- FRL 2026 Bitcoin expiry reversals: https://www.sciencedirect.com/science/article/pii/S1544612326008688
- Lachowicz SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5782822
- Dim, Eraker, Vilkov: https://westernfinance-portal.org/viewpaper?n=950096
- Brogaard, Han, Won (Bloomberg coverage): https://www.bnnbloomberg.ca/zero-day-options-are-reordering-the-way-the-stock-market-behaves-1.1921930
- Beckmeyer, Branger, Gayda summary: https://www.cxoadvisory.com/individual-investing/retail-0dte-option-trader-performance
- Bandi, Fusari: https://carey.jhu.edu/articles/risk-reward-insights-0dte-option-trading
- Fu, Li, Musto, Pearson (SEC DERA): https://www.sec.gov/files/dera-hope-reasonable-prc-2503.pdf
- Glassnode GEX: https://research.glassnode.com/gamma-exposure/ ; heatmap: https://research.glassnode.com/gamma-exposure-heatmap/
- Deribit Insights Q1 2023 vol surface (0DTE backtest): https://insights.deribit.com/industry/the-btc-volatility-surface-q1-2023/
- Deribit daily expiries: https://support.deribit.com/hc/articles/25944688876957
- Coinbase completes Deribit acquisition: https://www.theblock.co/post/366957/coinbase-completes-2-9-billion-cash-and-stock-acquisition-of-deribit
- Binance daily options announcement: https://www.binance.com/en/support/announcement/15974bb3a80441e5bc7d6755e55512ec
- Tardis Deribit details: https://docs.tardis.dev/historical-data-details/deribit ; free first day of month: https://docs.tardis.dev/faq/billing-and-subscriptions
- Binance option S3 listing ([V]): https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/option/

Macro events
- Johansson, Vilhelmsson: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4478184
- Karau 2023: https://www.sciencedirect.com/science/article/abs/pii/S0261560623000815
- FRL 2026 FOMC hourly: https://www.sciencedirect.com/science/article/abs/pii/S1544612326006021
- Fed paper coverage (TokenPost): https://www.tokenpost.com/news/insights/19578
- Fed FEDS 2025-022 PDF (returned by search, contents not confirmed): https://www.federalreserve.gov/econres/feds/files/2025022pap.pdf
- ECB WP 3280: https://www.ecb.europa.eu/pub/pdf/scpwps/ecb.wp3280~503ba7d4b0.en.pdf
- NY Fed SR 1052: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1052.pdf
- BIS WP 1219: https://www.bis.org/publ/work1219.pdf
- Springer, Fed/ECB shocks and Bitcoin: https://link.springer.com/article/10.1007/s10436-023-00432-3
- Quantpedia on SSRN 4910537: https://quantpedia.com/what-drives-crypto-asset-prices/
- arXiv 2508.06788: https://arxiv.org/pdf/2508.06788
- Kaiko event volatility note: https://marketing.kaiko.com/apts-extraordinary-rally-examined

Startups and vendors
- Solidus Labs: https://www.soliduslabs.com/solutions/trade-surveillance
- Nasdaq market surveillance: https://www.nasdaq.com/solutions/nasdaq-market-surveillance/asset-coverage
- Datos Insights surveillance matrix: https://datos-insights.com/reports/trade-communication-crypto-and-commodities-surveillance-datos-insights-matrix-catch-the-bad-actors/
- Amberdata derivatives: https://amberdata.io/derivatives-info
- Block Scholes data: https://blockscholes.com/data
- Laevitas vs Block Scholes (CB Insights): https://www.cbinsights.com/compare/block-scholes-vs-laevitas
- Delphi options dashboard: https://cryptobriefing.com/delphi-options-dashboard-crypto-launch/
- Liquidation tracker roundup: https://www.quicknode.com/builders-guide/best/top-10-liquidation-trackers
