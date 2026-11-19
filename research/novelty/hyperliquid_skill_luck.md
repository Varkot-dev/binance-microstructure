# Hyperliquid wallets: skill or luck? Novelty and prior-art scan

Compiled 2026-11-19. Scope: the planned project that (1) tests whether top Hyperliquid wallets show skill or luck using mutual-fund methods (Berk and van Binsbergen value added; Kosowski, Timmermann, Wermers and White bootstrap; Fama and French luck versus skill; Barras, Scaillet and Wermers false discovery rate), (2) flags wallets that trade unusually well just before market-moving events, and (3) publishes a "skill or luck" leaderboard.

## Evidence tags and caveats

- **[V]** verified: a primary source was read, or the item is a standard published reference whose bibliographic details are long established (the classic mutual-fund papers).
- **[S]** from search-engine snippets or secondary summaries only. arxiv.org and several vendor sites could not be fetched from this machine (DNS blocked), so almost every 2025 to 2026 item below is [S]. Check before citing.
- **[I]** my inference or judgement.

No paper, company, number or URL here was invented. Where sources disagreed (for example the profit on the 2025-10-10 short), the range is reported.

## Summary

1. **Academic work on Hyperliquid has exploded in 2026, but none of it applies the mutual-fund luck-versus-skill toolkit to wallet PnL.** The closest paper is Zhai (2026), "Public Trader Identity", which ranks 147,113 wallets by toxicity (short-horizon markouts), finds rank persistence (rho = 0.52 across adjacent ten-day windows) and shows identity improves 1-second return prediction [S]. That is skill at the microstructure horizon, measured as adverse selection, not luck-adjusted PnL alpha with a bootstrap or FDR. Barone and Lillo (2026) study TWAP visibility and impact on Hyperliquid, not trader skill [S]. Several papers study the 2025-10-10 cascade (ADL, liquidity recovery), not who was positioned before it [S].
2. **The method has been applied to on-chain bettors, not to perp traders.** Polymarket now has a dense literature: Gómez-Cram, Guo, Jensen and Kung use a sign-randomization test to separate skilled from lucky traders (about 3% skilled, 44% of those stay classified as skilled out of sample) [S]; Akey, Grégoire, Harvie and Martineau document concentration and modest persistence [S]; Reichenbach and Walther find skill beyond chance [S]; Mitts and Ofir flag informed wallet-market pairs with a permutation test [S]. For crypto funds, Bianchi and Babiak (JBF 2022) run a KTWW-style bootstrap and find skill evidence weakens once cross-sectional correlation is handled [S]. The direct off-chain analogue is Barber, Lee, Liu and Odean (JFM 2014) on Taiwanese day traders: under 1% reliably earn positive abnormal returns net of fees [S].
3. **Industry has already done crude persistence and "skill score" work on Hyperliquid.** A Tessera blog post on about 100,000 wallets reports top-decile monthly PnL wallets are almost as likely to fall to the bottom decile as to stay [S]; a blog by Saulius fits a hierarchical Bayesian skill model on 7.6M Hyperliquid fills [S]; Graph Advocate offers a 0-100 skill score that shrinks small-sample wallets toward neutral [S]. LiquidWhales, HyperDash (Copy Score), VortX, HyperSonnar, Hyperlens and Copin rank on Sharpe, drawdown, win rate or proprietary scores [S]. None found reports a p-value, bootstrap null, or false discovery rate across the wallet universe [S/I].
4. **Event-driven "insider" wallets on Hyperliquid are covered by journalism case by case, not systematically.** The 2025-10-10 short (reports range from about $150M to $200M profit, with the last add about one minute to an hour before the 20:50 UTC tariff post) was traced by on-chain sleuths and Arkham, drew a House Oversight letter, and remains unproven [S]. The 2025-03-02 50x long before the crypto reserve post (about $6.8M) is a second case [S]. DOJ charged two former Robinhood engineers in 2026 for trading Hyperliquid perps ahead of Robinhood listings; one pleaded guilty on 2026-11-16 [S]. No academic event study of pre-announcement wallet positioning on Hyperliquid was found [S/I].
5. **Data is mostly free but needs work.** Public info API (1200 weight per minute per IP, extra weight per 20 items on fill endpoints) [S]; requester-pays S3 node fills (`hl-mainnet-node-data`, node_fills from about 2025-05-25, node_fills_by_block from 2025-07-27) [S]; Allium has fills back to 2023-11-24 but with a 10k-fill cap for about 4,000 heavy traders before March 2025 [S]; Dune's Hyperliquid tables are enterprise or trial only [S].

**Bottom line [I]:** sub-idea 1 is *partly done* (persistence and shrinkage exist informally; the formal KTWW plus FDR treatment on perp wallets, with leverage, funding and survivorship handled, is open). Sub-idea 2 is *partly done* (journalism on single cases, Polymarket academics have the template; a systematic Hyperliquid event study is open). Sub-idea 3 is *partly done commercially* (many skill scores exist) but a leaderboard that publishes luck-adjusted significance and FDR q-values appears new.

## Prior-art table

### A. Academic

| Work | Year, venue | Data | Key finding | Relevance | Tag |
|---|---|---|---|---|---|
| Zhai, "Public Trader Identity: Adverse Selection and Return Predictability" | 2026, arXiv 2608.04373, SSRN 7234658 | Hyperliquid full-depth book rebuilt from 17.1B messages; 14.3M aggressive orders by 147,113 wallets; $84.3B taker notional; December 2025 replication | Wallet toxicity rank persists (rho 0.52, adjacent ten-day windows); identity features add 13.2% to 1-second out-of-sample R2 vs anonymous benchmark; beats 200 activity-matched placebo cohorts by about 1.6x | Closest prior work for sub-idea 1. Short horizon, markout based, no PnL alpha, no FDR | [S] |
| Barone and Lillo, "Trading in the Sunshine or in the Shade" | 2026, arXiv 2606.15715, SSRN 6944480 | Hyperliquid, about 4.3M hidden metaorders vs about 465k visible TWAPs, 201 perps, 2025-07-28 to 2026-03-23 | Visible TWAPs cost less and leave smaller permanent impact; tests Admati-Pfleiderer sunshine trading | Shows wallet-level attribution is publishable; not about skill | [S] |
| "Herding or Racing? Decomposing Cross-Account Order-Flow Persistence in On-Chain Markets" | 2026, arXiv 2611.02616 | Appears to use on-chain account IDs (title only seen) | Not verified | Adjacent; authors and content unverified | [S] |
| Risk-Based Auto-Deleveraging; Autodeleveraging: Impossibilities and Optimization | 2025 to 2026, arXiv 2603.15963, 2512.01112 | Hyperliquid fill log, ADL on 2025-10-10 (one reports 34,983 ADL executions across 19,337 wallets); Allium account data | Mechanism design of ADL | Data precedent for 2025-10-10 wallet-level work | [S] |
| Lim, "Anatomy of a Crypto Cascade"; "Two-Regime Liquidity Recovery ... Hyperliquid and the October 10, 2025 Event" | 2026, SSRN 6579278, 6636998 | Minute-level Binance and Hyperliquid | BTC fell 12.6% in ten minutes on Binance; Hyperliquid depth stayed below pre-event levels for weeks | Crash microstructure, not pre-event positioning | [S] |
| Slippage-at-Risk (SaR) | 2026, arXiv 2603.09164 | 5-minute Hyperliquid books, 184 perps, 2025-10-09 to 2025-11-03 | Liquidity risk framework | Context | [S] |
| "Perpetual Futures in Decentralised Finance" | 2026, MDPI IJFS 14(7):178 | Hyperliquid, EdgeX, Lighter, 17 assets, 2025-07 to 2026-02 | Volume drivers | Context | [S] |
| Gómez-Cram, Guo, Jensen, Kung, "Prediction Market Accuracy: Crowd Wisdom or Informed Minority?" | 2025 to 2026, SSRN 6687418 (working paper) | Polymarket trades 2023 to 2025, about 1.72M accounts | Sign-randomization test: about 3% skilled traders drive price discovery; 44% of in-sample skilled remain skilled out of sample (vs about 10% persistence often cited for mutual funds); 1,950 accounts flagged as candidates for non-public information | Methodological template for sub-ideas 1 and 2 on another on-chain venue | [S] |
| Akey, Grégoire, Harvie, Martineau, "Who Wins and Who Loses in Prediction Markets? Evidence from Polymarket" | 2026, SSRN 6443103 | Polymarket | Top 1% of profitable users take 76.5% of profits; winners often supply liquidity with limit orders; modest monthly persistence | Template for distributional and persistence analysis | [S] |
| Reichenbach and Walther, "Exploring Decentralized Prediction Markets: Accuracy, Skill, and Bias on Polymarket" | 2025, SSRN 5910522 | Polymarket | Under a third earn positive profits; evidence of skill beyond chance | Luck vs skill on on-chain bettors | [S] |
| Mitts and Ofir, "From Iran to Taylor Swift: Informed Trading in Prediction Markets" | 2026, working paper (HLS Forum summary) | Polymarket, 2024-02 to 2026-02 | 210,718 flagged wallet-market pairs win 69.9%, over 60 SD above a permutation null; about $143M anomalous profit | Template for sub-idea 2 (wallet-market unit, permutation null). Critics: screen conditions on ex-post profitability | [S] |
| Follow-up arXiv papers on Polymarket leakage (2605.00459, 2605.02286, 2605.02287) | 2026, arXiv | Polymarket | Compare and critique the above detection methods | Shows referee-style pushback a Hyperliquid version would face | [S] |
| Bianchi and Babiak, "On the Performance of Cryptocurrency Funds" | 2022, Journal of Banking and Finance | 200+ crypto funds | Panel bootstrap: top-fund alphas unlikely to be luck, but skill evidence weak after cross-sectional correlation | Closest crypto use of KTWW bootstrap (funds, not wallets) | [S] |
| Barber, Lee, Liu, Odean, "The Cross-Section of Speculator Skill: Evidence from Day Trading" | 2014, Journal of Financial Markets 18:1-24 | Taiwan day traders 1992 to 2006 | Under 1% predictably earn positive abnormal returns net of fees; prior-year top traders keep earning | Best off-chain analogue for retail leveraged speculators | [S] |
| Apesteguia, Oechssler, Weidenholzer, "Copy Trading" | Management Science (2020) | Lab experiment | Copy access raises risk-taking | Copy-trading risk channel | [S] |
| Kosowski, Timmermann, Wermers, White | 2006, Journal of Finance | US mutual funds | Bootstrap of alphas and t-stats; top-decile alphas not all luck | Method | [V] |
| Barras, Scaillet, Wermers | 2010, Journal of Finance | US mutual funds | FDR: about 75% zero-alpha, small skilled share | Method | [V] |
| Fama and French, "Luck versus Skill in the Cross-Section of Mutual Fund Returns" | 2010, Journal of Finance | US mutual funds | Simulation of t(alpha) distribution; little net skill | Method | [V] |
| Berk and van Binsbergen, "Measuring Skill in the Mutual Fund Industry" | 2015, Journal of Financial Economics | US mutual funds | Value added (dollar alpha times size) is persistent | Method; maps naturally to dollar PnL on perps | [V] |
| Harvey, Liu, Zhu, "...and the Cross-Section of Expected Returns" | 2016, Review of Financial Studies | Factor zoo | Multiple-testing thresholds | Method for FDR framing | [V] |

Searches found **no** academic paper on trader skill or luck for dYdX, GMX, Drift or Aevo, and no peer-reviewed memecoin or Solana trader luck-versus-skill test [S/I]. GMX is peer-to-pool, so trader PnL is borne by the GLP pool, which changes what "skill" means there [S].

### B. Industry research and blogs on Hyperliquid wallet skill

| Item | What it does | Luck adjustment? | Tag |
|---|---|---|---|
| Tessera blog "Smart money doesn't stay smart" (tesseralytics.dev) | About 100,000 wallets, monthly decile transition of realized PnL; top decile nearly as likely to drop to bottom as to stay ("forms an X"); win rate persists as style | Persistence matrix only, no bootstrap or FDR | [S] |
| Saulius, "A Hierarchical Bayesian Model for Separating Trader Skill from Luck" (saulius.io) | 7.6M Hyperliquid fills; ranking by posterior skill beat ranking by PnL in one walk-forward copy test (77% vs 54% winning copies); author concedes concentration in one trending asset | Yes, Bayesian shrinkage; single blog, no FDR | [S] |
| Envy Protocol, "I Analyzed 10,000 Hyperliquid Traders" (Medium) | 30 days, Nov 2024: 16.5% profitable; profitability rises with account size | No | [S] |
| gwrx2005 Medium posts on whale trading and ML | Following wallets of $5M+ gave about +11% over about 2.5 months | No, self-published | [S] |
| Renesis, "Why Most Hyperliquid PnL Leaderboard Rankings Are Wrong" | Argues ROI is distorted by top-ups; risk-adjusted reorders ranking | Risk adjustment, no significance | [S] |
| CoinMarketMan blogs | PnL-based cohorts; cohort drift as warning sign | No | [S] |

### C. Products

| Product | What it shows | Risk or luck adjustment / significance | Monetisation (public) | Tag |
|---|---|---|---|---|
| Hyperliquid official leaderboard (stats API) | Account value; PnL, ROI, volume over day, week, month, all-time; about 32k opted-in traders | None | Free | [S] |
| HyperDash (now part of pvp.trade) | Leaderboards by realized PnL, ROI, win rate, account value, volume; Cohorts view; trader equity curves; liquidation heatmaps; copy trading with sizing, SL, TP; proprietary Copy Score weighting consistency, drawdown, frequency | Proprietary score, no significance | Dashboard free, fees on executed trades; Data API from $24.75 per 1M credits (Starter) down to $13.33 (Scale) | [S] |
| CoinMarketMan HyperTracker | 16 cohorts (8 by perp equity, 8 by all-time PnL), refreshed every 5 minutes; API | No | Free 100 req/day; Pulse $179/mo; Surge $499/mo; Flow $1,159/mo; Stream $2,399/mo (another post says $1,999) | [S] |
| Nansen (Hyperliquid perps) | Smart Money Perp Trades, Hyperliquid leaderboard API; in-app perps trading since 2026-06-09; Smart Money label historically needs about $1.5M cumulative realized profit | Label threshold, not statistical | Subscriptions (Pro about $49/mo annual per a competitor post) plus builder fee 0.08% down to 0.01% by points tier | [S] |
| Arkham | Entity labels (labelled the 2025-10-10 wallet "Trump insider whale"); launched accuracy-first ranking for prediction-market traders | Accuracy ranking for prediction markets only | Freemium | [S] |
| Lookonchain | X/Telegram alerts on whale moves, cited by press for the 2025-03-02 trade | No | Free media | [S] |
| CoinGlass Hyperliquid pages | Whale positions over $1M, whale alerts, liquidation map, long/short ratio, HLP and vault pages; API | No | Paid API tiers (not checked) | [S] |
| Hypurrscan | Explorer for addresses and transactions | No | Free | [S] |
| Copin | Filters by win rate, PnL, drawdown, Sharpe, frequency; copy trading across perp DEXs | Sharpe only | Copy-trading fees (not checked) | [S] |
| LiquidWhales | 0-100 score from Sharpe, win rate, max drawdown, longevity, PnL, net of fees; S to F grades; copy trading | Risk-adjusted, no significance | Not checked | [S] |
| Graph Advocate | API with 0-100 composite skill score; confidence weighting shrinks 50-trade wallets toward neutral | Shrinkage (closest commercial idea to luck adjustment) | API | [S] |
| VortX, HyperSonnar, Hyperlens, HyprSwarm, whale.ag | Copy or copiability scores; screens (30+ trades, edge survives copying); HyprSwarm per-wallet skill rating, publicly reported its copy strategy losing at one point | Heuristic | Mostly copy-trading fees | [S] |
| Hydromancer Reservoir, Dwellir, GoldRush, SQD, Bitquery, Allium, Dune | Data infrastructure | n/a | Hydromancer Starter about $300/mo; Allium and Dune enterprise | [S] |
| Polysights (Polymarket) | Insider Finder flags suspicious accounts on prediction markets; raised $1.5M (reported 2026-06) | Heuristic flags | VC funded | [S] |
| Solidus Labs HALO; Chainalysis | Market-abuse surveillance; reported deals with Polymarket and Kalshi in 2026 (accounts conflict) | Rule-based surveillance | Enterprise | [S] |

No product found reports bootstrap p-values, FDR q-values, or a "probability this is luck" for Hyperliquid wallets [S/I].

### D. Journalism and investigations

| Case | What happened | How analysed | Tag |
|---|---|---|---|
| 2025-10-10 tariff short | Wallet held about 3,600 BTC (~$735M) and 91,000 ETH (~$380M) short when Trump posted the 100% China tariff at 20:50 UTC; reported profit $150M to $200M; timing of last add reported as about one minute (The Block, Investing.com) to about an hour before | Hand tracing of wallet history; investigator "Eye" linked it via a $40k USDT transfer to Garrett Jin (ex-BitForex CEO), who denied Trump links and said he traded for a client; Arkham label; later a new $163M BTC short | [S] |
| Congressional follow-up | House Oversight chair Comer wrote to Hyperliquid CEO Jeff Yan (reported 2026-09), widening a prediction-market insider-trading probe; letter does not name the trader or claim proof | Letter cites public on-chain timing | [S] |
| 2025-03-02 crypto reserve long | About $200M 50x BTC and ETH longs opened about 35 minutes before Trump's reserve post; about $6.8M profit; Hyperliquid cut max leverage afterwards | Lookonchain and HyperDash timelines | [S] |
| Robinhood listing front-running | DOJ charged Hefu Chai and Huaisong Xiang (2026-09) over Hyperliquid perps traded ahead of Robinhood listings, each over $50k profit; Xiang pleaded guilty 2026-11-16 and forfeited $125,523 | Prosecutors used private Slack access plus on-chain trades | [S] |
| Polymarket comparison cases | Military-information wallets (152 wallets, about $8M, Anti-Corruption Data Collective); Israel election bets; about $200M flagged in H1 2026 (Bloomberg using Polysights); Polymarket referred about 100 wallets | Mix of heuristics and permutation tests; Bloomberg notes insider activity is hard to separate from research or luck | [S] |

## Novelty ratings

| Sub-idea | Rating | Closest prior work | What would make the student's version new [I] |
|---|---|---|---|
| 1. Skill vs luck of top wallets with KTWW bootstrap, Fama-French simulation, BSW FDR, Berk-van Binsbergen value added | **Partly done** | Zhai 2026 (markout persistence, Hyperliquid); Tessera decile transitions; Saulius Bayesian model; Gómez-Cram et al. (Polymarket); Bianchi and Babiak (crypto funds) | First formal application of the full mutual-fund toolkit to perp wallets: daily wallet returns on equity net of fees and funding, factor-adjusted alpha (BTC/ETH market, momentum, funding carry), cross-sectionally resampled bootstrap that preserves common shocks (the point Bianchi and Babiak show matters), FDR pi0 estimate of the skilled share, and dollar value added. Must handle survivorship (wallets are free to abandon), multi-wallet entities, vaults and market makers separately, leverage-driven variance, and the short sample. Out-of-sample persistence of the "skilled" set vs the PnL-ranked set is the headline test. |
| 2. Wallets that trade unusually well before market-moving events | **Partly done** | Case journalism (2025-10-10, 2025-03-02); DOJ Robinhood case; Mitts and Ofir and Gómez-Cram et al. on Polymarket; no Hyperliquid event study found | Systematic event study over a dated catalogue of posts and announcements (Truth Social, listings, macro releases) with a permutation or placebo-time null, at the wallet-event level, reporting how many "suspicious" hits luck alone would produce across thousands of wallets and events. Pair with sub-idea 1 (is the wallet skilled in normal times, or only before events?). Report in aggregate or with heavy caveats; avoid naming owners. |
| 3. Public "skill or luck" leaderboard | **Partly done (commercially)** | HyperDash Copy Score, Graph Advocate shrinkage score, LiquidWhales grades, Hyperliquid official leaderboard | A leaderboard that shows bootstrap p-value, FDR q-value and a shrunk alpha with uncertainty band, plus an out-of-sample track record of its own rankings, appears not to exist. Novel as transparent methodology rather than as a product category. |

## Startup opportunities

| Idea | Customers | Competitors | Defensibility | Key risks |
|---|---|---|---|---|
| Luck-adjusted trader analytics (skill score with significance and out-of-sample audit) | Copy traders, Hyperliquid front-ends and builders (builder-fee economics), funds hunting for talent to back, vault depositors | HyperDash/pvp.trade, Nansen, CoinMarketMan, Copin, LiquidWhales, Graph Advocate, many small copy apps | Weak on data (public), moderate on methodology and a published live track record; network effects only if integrated into an execution venue | Free alternatives; scores that underperform publicly; Hyperliquid or HyperDash adding similar features; short history limits power |
| Copy-trading risk scoring (is this leader's record luck, leverage, or a few trades? capacity and slippage when copied) | Copy-trading platforms, vault curators, wallets offering copy features | Built-in Copy Scores at HyperDash, VortX "edge survives copying" screen | Integration as a B2B API; data on copy slippage across many followers | Liability if followers lose; regulation of investment advice and copy trading (EU MiFID, US CFTC/SEC treatment of signals) [I] |
| Surveillance for event-driven insider bets on perp DEXs | Hyperliquid and other venues, regulators and congressional staff, journalists, compliance teams at funds and exchanges whose employees trade on-chain (Robinhood case), prediction markets | Solidus HALO, Chainalysis, Elliptic, Polysights (prediction markets), in-house venue teams | Event catalogue plus calibrated false-positive rates; entity clustering; trust with enforcement | Defamation and harassment risk from naming wallets (Garrett Jin denial shows contested attribution; wrench-attack risk for exposed whales is discussed by vendors); ex-post profitability screens are criticised as biased; venue may not want to be policed; jurisdiction for decentralised venues unclear [I] |

General risks [I]: (a) accusing pseudonymous owners on statistical evidence; publish aggregates, frame flags as "unusual relative to a null", not as wrongdoing; (b) data quality: two fills per trade (SQD notes duplicate tid rows), API caps on history for heavy traders (Allium 10k cap), missing deposits and transfers needed for returns on equity, sub-accounts and vaults; (c) regulation: US status of Hyperliquid access, investment-advice rules for leaderboards that recommend copying, and data-protection questions if wallets are de-anonymised.

## Data access (what is reachable without paying)

| Source | Coverage | Cost | Tag |
|---|---|---|---|
| Hyperliquid info API (`userFills`, `userFillsByTime`, `clearinghouseState`, `portfolio`, leaderboard stats) | Recent history per wallet; one third-party doc says userFills returns up to 2,000 most recent fills; a 10k fill cap is cited by Allium for history | Free; 1200 weight per minute per IP, fill endpoints add weight per 20 items | [S] |
| S3 `hl-mainnet-node-data` (`node_fills` 2025-05-25 to 2025-07-27; `node_fills_by_block` 2025-07-27 onward, hourly lz4); `hyperliquid-archive` (L2 books, asset contexts, roughly monthly; no trades) | All fills with wallet addresses from mid 2025 | Requester pays: needs AWS billing; egress cost is the only charge | [S] |
| Hydromancer Reservoir | Complete from 2025-07-28, 350+ perps | Requester pays | [S] |
| Allium `hyperliquid.raw.fills` | From 2023-11-24, capped for about 4,000 heavy traders before March 2025 | Commercial (terms not found) | [S] |
| Dune Hyperliquid tables (from January 2025) | Decoded fills with PnL | Enterprise or trial only | [S] |
| SQD hyperliquid-fills | Every fill from block 750,000,000 to head, filter by user or coin | Public API (limits not checked) | [S] |
| BigQuery public dataset | None found | n/a | [S] |

Implication [I]: a clean, free full-universe panel realistically starts mid 2025 (S3 node fills), which covers 2025-10-10 but gives about 16 months, short for persistence tests on monthly data; daily returns and block bootstrap are needed.

## References

Academic
- Zhai, Public Trader Identity: https://arxiv.org/abs/2608.04373 ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7234658
- Barone and Lillo, Trading in the Sunshine or in the Shade: https://arxiv.org/abs/2606.15715 ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6944480
- Herding or Racing?: https://arxiv.org/html/2611.02616
- Risk-Based Auto-Deleveraging: https://arxiv.org/pdf/2603.15963
- Autodeleveraging: Impossibilities and Optimization: https://arxiv.org/html/2512.01112v2
- Slippage-at-Risk: https://arxiv.org/pdf/2603.09164
- Lim, Anatomy of a Crypto Cascade: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6579278
- Lim, Two-Regime Liquidity Recovery: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6636998
- Perpetual Futures in DeFi (MDPI): https://www.mdpi.com/2227-7072/14/7/178
- Gómez-Cram, Guo, Jensen, Kung: https://papers.ssrn.com/abstract=6687418 ; Yale summary https://insights.som.yale.edu/insights/wisdom-of-the-few-prediction-markets-are-driven-by-small-number-of-skilled-traders
- Akey, Grégoire, Harvie, Martineau: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6443103
- Reichenbach and Walther: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5910522
- Mitts and Ofir summary: https://corpgov.law.harvard.edu/2026/03/25/from-iran-to-taylor-swift-informed-trading-in-prediction-markets/
- Polymarket leakage papers: https://arxiv.org/pdf/2605.00459 ; https://arxiv.org/pdf/2605.02286 ; https://arxiv.org/pdf/2605.02287
- Bianchi and Babiak: https://eprints.lancs.ac.uk/id/eprint/169953
- Barber, Lee, Liu, Odean (2014): https://ideas.repec.org/a/eee/finmar/v18y2014icp1-24.html
- Apesteguia, Oechssler, Weidenholzer, Copy Trading: https://jose-apesteguia.github.io/CopyTrading.pdf
- Kosowski, Timmermann, Wermers, White (2006), Journal of Finance 61(6); Barras, Scaillet, Wermers (2010), Journal of Finance 65(1); Fama and French (2010), Journal of Finance 65(5); Berk and van Binsbergen (2015), Journal of Financial Economics 118(1); Harvey, Liu, Zhu (2016), Review of Financial Studies 29(1)

Industry research
- Tessera: https://tesseralytics.dev/blog/wallet-behaviour
- Saulius, Bayesian skill model: https://saulius.io/blog/bayesian-hierarchical-model-trader-skill
- Envy Protocol, 10,000 traders: https://medium.com/@envyprotocol/i-analyzed-10-000-hyperliquid-traders-the-results-are-brutal-a29adcca8c2a
- gwrx2005 whale study: https://medium.com/@gwrx2005/combining-simulation-and-machine-learning-analysis-of-whale-trading-on-hyperliquid-93f10d96941b
- Renesis leaderboard critique: https://renesis.fi/articles/the-hyperliquid-leaderboard-illusion-why-most-pnl-rankings-are-wrong
- CoinMarketMan PnL classification: https://coinmarketman.com/blog/pnl-based-trader-classification-why-performance-matters-more-than-size-on-hyperliquid--en/

Products
- HyperDash pricing: https://hyperdash.com/pricing ; Bankless review: https://www.bankless.com/read/trading-perps-in-style
- CoinMarketMan provider comparison and pricing: https://coinmarketman.com/blog/hyperliquid-data-providers-compared ; docs https://docs.coinmarketman.com/
- Nansen Hyperliquid perps: https://academy.nansen.ai/help/articles/9884236-hyperliquid-perps-trading ; leaderboard API https://docs.nansen.ai/api/hyperliquid-apis/hyperliquid-leaderboard
- CoinGlass Hyperliquid: https://www.coinglass.com/hyperliquid ; API https://docs.coinglass.com/v3.0/reference/hyperliquid-whale-position
- LiquidWhales: https://liquidwhales.com/ ; Graph Advocate: https://docs.graphadvocate.com/hyperliquid ; VortX: https://vortx.trade/ ; HyperSonnar: https://hypersonnar.fr/ ; Hyperlens: https://hyperlens.io/smart-money/ ; HyprSwarm: https://hyprswarm.com/ ; Copin guide: https://hyperliquidguide.com/guides/trading/copy-trading-guide
- Arkham prediction-market ranking: https://www.theblock.co/amp/post/406604/arkham-launches-ranking-system-for-prediction-market-traders
- Polysights coverage: https://gizmodo.com/tracking-insider-trading-on-polymarket-is-turning-into-a-business-of-its-own-2000709286 ; Solidus report: https://www.soliduslabs.com/reports/polymarket-under-the-polygraph

Journalism
- 2025-10-10 short: https://cointelegraph.com/news/garrett-jin-whale-denies-allegations-shorting-bitcoin ; https://cointelegraph.com/news/mystery-insider-whale-opens-massive-new-bitcoin-short-after-bagging-192m-profits ; https://coincentral.com/how-one-trader-made-160-million-shorting-crypto-before-trumps-china-tariff-bombshell/
- House Oversight: https://unchainedcrypto.com/house-oversight-targets-hyperliquid-crypto-com-and-predictit-in-insider-trading-probe/ ; https://www.benzinga.com/markets/prediction-markets/26/09/62061946/hyperliquid-insider-trading-probe-crypto-short
- 2025-03-02 reserve long: https://www.coindesk.com/markets/2025/03/03/one-trader-made-millions-betting-usd200m-on-btc-just-before-trump-s-crypto-reserve-news ; https://www.theblock.co/post/344105/trader-makes-7-million-in-one-day-going-50x-long-bitcoin-ether-ahead-of-trumps-crypto-reserve-announcement
- Robinhood engineers: https://www.theblock.co/news/regulation/2026-09-15-doj-charges-robinhood-former-engineers-front-running-crypto-listings-hyperliquid-414865 ; https://cryptobriefing.com/robinhood-engineer-guilty-hyperliquid-insider-trades/
- Polymarket insider coverage: https://www.bloomberg.com/graphics/2026-polymarket-traders-who-knew-the-future/ ; https://crypto.news/polymarket-refers-nearly-100-wallets-amid-200m-insider-trade-concerns/

Data
- Hyperliquid historical data: https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data
- Hyperliquid rate limits: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits
- Dwellir fills catalogue: https://www.dwellir.com/docs/hyperliquid/data-catalog/node-feeds/fills
- Hydromancer Reservoir: https://docs.hydromancer.xyz/reservoir/hyperliquid
- Allium fills: https://docs.allium.so/historical-data/supported-blockchains/hyperliquid/raw/fills
- Dune Hyperliquid catalogue: https://docs.dune.com/data-catalog/community/hyperliquid/overview
- SQD fills: https://docs.sqd.dev/en/portal/hyperliquid/networks/hypercore-fills
