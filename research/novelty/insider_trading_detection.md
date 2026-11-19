# Novelty and prior art: detecting informed trading before crypto announcements

Scope: pre-announcement trading around (1) exchange listings and delistings (Binance, Coinbase, Upbit, Bithumb), (2) political or official posts, (3) token launches, and (4) real-time monitoring of unusual pre-announcement flow. Compiled 2026-11-19 for the student's projects in this repository.

**Evidence tags.** [V] verified at the primary source from this machine. [S] taken from a search-engine snippet or secondary coverage (news, blog, aggregator), not opened at source. [I] my inference. From this session only GitHub search and data.binance.vision could be opened directly; SSRN, arXiv, sec.gov, publisher sites, news sites, kaiko.com, soliduslabs.com, thetie.io, cointelegraph.com and drops.dagstuhl.de did not resolve. So most claims below are [S]. Before citing any number in a paper or pitch, open the source.

**Absence claims.** "Not found" means not found in roughly 50 web searches (English and Korean) plus GitHub repository search. It is not proof that no such work exists. SSRN, Google Scholar, OSF and KCI/DBpia were not searchable directly.

---

## 1. Summary

1. **Pre-listing run-ups are documented, mostly for spot listings at hourly or daily frequency.** The anchor paper is Félez-Viñas, Johnson and Putniņš, "Insider trading in cryptocurrency markets" (SSRN working paper, 2022, revised Feb 2025). The 2022 version covered 146 Coinbase listing announcements with hourly prices from -300h to +100h and estimated insider trading in 10 to 25% of listings [S][1][2][4]. The revised SSRN abstract reportedly estimates 28 to 48% of listings and at least $30M in profits [S][1]. I found no evidence that it has been published in a journal [S]. Earlier event studies (Ante 2019; Ante and Meyer 2021) use daily data across 22 exchanges and read the pre-event drift as informed trading or leakage [S][5][6].
2. **No academic study found uses Binance USDT-M perpetual futures tick data (aggTrades) to test pre-announcement flow** before listings or delistings. None found is pre-registered [I, from search]. The closest industry work is Kaiko's May 2026 note on Robinhood listings. It used perp volume, open interest and funding in the hours before announcements, and its own analyst said the pattern could reflect public signals [S][20].
3. **Delistings are thinly studied in academia.** Existing work covers post-delisting returns (Ammann et al., survivorship and delisting bias) [S][8], prediction of Binance delistings from liquidity decline (Yang, Asia-Pacific Journal of Financial Studies, 2026) [S][9], and industry counts of 24h post-announcement drops (for example a secondary "CoinSight" figure of a -26.3% median over 24h across 101 Binance delistings, not traced to source) [S][49]. **I found no study of pre-announcement informed selling or shorting before delisting announcements.** That is the most open piece [I].
4. **Political posts.** Prior work is journalism (Hyperliquid whales before the March 2025 crypto-reserve post and the 10 Oct 2025 tariff post; Reuters/BBC/Unusual Whales on equity options before the 9 Apr 2025 tariff pause) [S][36][37][51]. The systematic academic work is on prediction markets: Mitts and Ofir 2026, about $143M of anomalous Polymarket profit [S][13]. The student's pre-registered c4 test (no evidence before tariff posts, BTCUSDT minute bars from aggTrades) has no direct academic equivalent that I found [I].
5. **Token launches (memecoins) are well covered on-chain.** Bubblemaps, Nansen, Lookonchain, Pine Analytics and academic papers (Kamat arXiv 2026, sniper cohorts on Pump.fun; Ding, Lin, Luo and Xu SSRN 2025) cover this [S][11][12][33][34][35][38]. CEX tick data adds little here [I].
6. **Commercial surveillance is private and sold to venues and regulators.** Solidus Labs HALO, Eventus Validus, Nasdaq SMARTS, Kaiko Market Surveyor, Elliptic and Chainalysis (custom work, for example Polymarket in 2026) are the main players. None publishes prices [S][39][40][41][42][43][44]. Public "insider" signals come from ad hoc X accounts and open-source Polymarket or Solana trackers [V][47]. **I found no public, statistically calibrated, announcement-anchored scorecard for CEX listings and delistings** [I].
7. **Licensing is a hard constraint for any product.** data.binance.vision datasets are licensed CC BY-NC-SA 4.0. Commercial use, paid newsletters and commercial products are excluded, and derived data inherits the terms [V][46].

---

## 2. What the student already has (context)

- Tick-level Binance USDT-M work (aggTrades, bookTicker) and a pre-registered pre-post test: `research/politics/data/c4_prepost_trading.md` reports no evidence of unusual aligned taker imbalance in minutes -10..-1 before Trump tariff posts (D = +0.011, 95% CI -0.025 to +0.046, one-sided permutation p 0.277, 178 tariff events) [V, repo].
- `research/announcements/d1_inventory.py` and `data/event_inventory.csv`: 907 candidate futures events from 2023-01 to 2026-10 (766 futures listings, 141 futures delistings), with archive availability. It holds no price statistics yet, and Binance CMS announcement timestamps still need collecting [V, repo].

---

## 3. Prior-art table

### 3a. Academic and quasi-academic

| # | Work | Venue / status | Events, data, frequency | Listings / delistings | Pre-reg or natural experiment | Key finding | Tag |
|---|---|---|---|---|---|---|---|
| 1 | Félez-Viñas, Johnson, Putniņš, "Insider trading in cryptocurrency markets" (2022, rev. 2025) | SSRN WP 4184367; no journal version found | 2022 version: 146 Coinbase listing announcements, Sep 2018 to May 2022; hourly prices -300h to +100h; announcement hour validated via web archive; on-chain wallet tracing | Listings only | Neither; benchmark is listings where insider trading is unlikely | Run-ups resembling prosecuted equity insider cases; 10 to 25% of listings (2022), 28 to 48% and at least $30M (revised abstract); 4 linked wallets earned about $1.5M | [S] [1][2][3][4] |
| 2 | Ante, "Market reaction to exchange listings of cryptocurrencies" (2019) | Blockchain Research Lab WP 3 | 327 listings, 180 coins, 22 exchanges; daily | Listings | No | Listing-day AR up to 25.5% on some exchanges, 5.7% average; CAAR 1.6% at t = -1; positions entered 2 days before positive events; Upbit 73% negative reactions; read as informed trading or manipulation | [S] [5] |
| 3 | Ante and Meyer, "Cross-listings of blockchain-based tokens issued through ICOs" (2021) | Decisions in Economics and Finance 44(2) | 250 cross-listings, 135 ICO tokens, 22 exchanges; daily | Listings | No | +6.5% listing day, about +10% over 7 days; positive pre-listing returns read as leakage; authors note announcement times are unknown | [S] [6] |
| 4 | Li, Luo, Wang, Wei, "Cryptocurrency Exchange Listings" | AFT 2025 extended abstract; SSRN 4715718 | Coinbase vs Binance listings; 80-exchange regulation index; daily (as far as snippets show) | Listings | No | Positive short-run ARs on both; Coinbase higher; Binance-venture-backed tokens weaker | [S] [7] |
| 5 | Ammann et al., "Survivorship and Delisting Bias in Cryptocurrency Markets" | Working paper (Univ. St. Gallen repository) | Hand-collected delisting returns and reasons | Delistings (post-event returns) | No | Large negative delisting returns (snippets give both -77.8% and -29% for different subsets) | [S] [8] |
| 6 | Yang, "Developing Predictive and Explainable Models for Cryptocurrency Delistings: A Case Study of Binance" | Asia-Pacific J. Financial Studies (2026) | Binance delistings | Delisting prediction | No | Sustained liquidity contraction is an early warning of delisting (a public-information confound for any pre-delisting drift test) | [S] [9] |
| 7 | Ruan and Streltsov, "Perpetual Futures Contracts and Cryptocurrency Market Quality" | SSRN WP 4218907 | 95 staggered perpetual introductions | Perp listings (effect on spot quality, not pre-announcement) | Staggered introduction design | Spot volume up, quoted spreads wider after perp introduction | [S] [10] |
| 8 | Kamat, "Coordinated Sniper Cohorts on Pump.fun" | arXiv 2607.02795 (2026) | 1.58M buyer observations, 166,098 launches, 12 to 26 Jun 2026 | Token launches | No | 1,012 persistent wallet cohorts | [S] [11] |
| 9 | Ding, Lin, Luo, Xu, "Decompose Market Manipulation Strategies: Evidence from On-chain Meme Coin Market" | SSRN 5953738 (2025) | On-chain memecoin trades | Token launches | No | Outperformers are disproportionately creators and snipers | [S] [12] |
| 10 | Mitts and Ofir, "From Iran to Taylor Swift: Informed Trading in Prediction Markets" | HLS Forum post Mar 2026; working paper | All Polymarket markets Feb 2024 to Feb 2026 (more than 93k markets, about 50k wallets) | Political and official events | No (screening rule) | About $143M anomalous profit (lower bound); methodology criticised by Harry Crane | [S] [13] |
| 11 | Anti-Corruption Data Collective, "Insider Risks in Polymarket Political Markets" | NGO brief, Apr 2026 | Polymarket political markets | Political | No | Military and defense markets stand out (52% longshot success) | [S] [14] |
| 12 | Dissensus AI WP, arXiv 2602.07046 | arXiv WP 2026 | Crypto event-study methods | General | Explicitly exploratory | 24/7 trading, fragmentation and no DMMs complicate crypto event studies | [S] [15] |

Not found: any study using Binance USDT-M aggTrades or bookTicker around listing or delisting announcements; any pre-registered crypto announcement study; any Upbit or Bithumb event study with announcement-minute timestamps in the peer-reviewed literature (Korean-language search found only regulatory and case analyses) [I].

### 3b. Industry research and journalism

| Who | What | Data / frequency | Listings / delistings / other | Tag |
|---|---|---|---|---|
| Kaiko (May 2026) | Perp volume, OI and funding rose hours before Robinhood listing announcements (LIT, ZEC, SNX, NEAR); no allegation of leaks; analyst says public signals are possible | Perps (incl. Hyperliquid) and on-chain, intraday | Listings (Robinhood) | [S] [20] |
| The Tie (Jul 2026) | Listing gains front-loaded into pre-announcement run-ups; post-listing drift fades in about 2 weeks; Binance lead time about 48 to 72h; run-up muted for tokens already on 3+ venues | CCData prices, daily/hourly | Listings | [S] [21][22] |
| RockawayX | Binance listings bullish 1 to 2 days, fading in 7; little pre-trend on Binance unlike Bybit | Daily | Listings | [S] [23] |
| Wu Blockchain (2022) | Week-before-listing returns Nov 2017 to Feb 2022: Coinbase +24.3%, Binance +5.6% average (ex outliers) | Daily | Listings | [S] [18] |
| Argus via WSJ (2022) | 46 wallets bought GNO ($17.3M) before listings and sold after; repeated pre-listing patterns Feb 2021 to Apr 2022; Binance and FTX said no policy breach | On-chain | Listings | [S] [19] |
| Coin Metrics / Messari (2020) | "Coinbase effect": Messari 91% average 5-day return (outlier driven), Coin Metrics -1% to +14% | Daily | Listings | [S] [16][17] |
| Lookonchain (2023 to 2024) | Wallets buying before Binance listings or perp announcements: BOME (Binance denied staff link, offered up to $5M bounty), WIF ($1M bought 16h before the perp pair announcement), GNS, a $100k-in-seconds trader | On-chain | Spot and futures listings | [S] [24][25][26] |
| Binance internal (2025) | Mar 2025: employee suspended for front-running a TGE with BNB Chain info, $100k to 4 whistleblowers. Dec 2025: Futures employee used official X account to pump a token | Internal | Token launch, promotion | [S] [27][28] |
| Upbit (Jun 2026) | Seoul Economic Daily: wallet bought WIF about 3h before Upbit's 2 p.m. notice and sold about 10 min after; Upbit denied | On-chain | Listings | [S] [29] |
| SEC v. Wahi / US v. Wahi (2022 to 2024) | Coinbase PM tipped brother and friend about 55 assets, about $1.1M to $1.5M profit; Ishan 24 months, Nikhil 10 months; Ramani default judgment Mar 2024 ($817,602 disgorgement, $1,635,204 penalty) | Exchange records, subpoenas | Listings | [S] [30][31] |
| Coinbase response (2022) | Published then dropped an "asset roadmap"; Armstrong promised changes "to prevent on-chain data giving signal" | n/a | Listings | [S] [32] |
| Bubblemaps, Nansen, Lookonchain (2025) | TRUMP: wallet 6QSc2 turned about $1.09M into about $109M (bought about 30s after announcement, not before). LIBRA: 86% of traders lost $251M; about 8 insider wallets cashed out about $107M | On-chain | Token launches tied to political figures | [S] [33][34][35] |
| HyperDash / Lookonchain / Arkham (2025) | About $200M 50x BTC/ETH longs opened about 35 min before the 2 Mar 2025 reserve post (+$6.8M); short opened before the 10 Oct 2025 tariff post (about $150M to $200M); Arkham's "Trump insider whale" label; alleged owner denies | Hyperliquid on-chain perps | Political posts | [S] [36][37] |
| Pine Analytics (2025) | More than 50% of Pump.fun tokens sniped in the creation block; deployer-to-sniper SOL transfers | On-chain | Token launches | [S] [38] |
| cryptolisting.ws, newcoinlistings.com | Post-announcement moves (5 min, 1h, 24h, 7d) for Binance, Upbit, Coinbase etc.; Upbit 62 listings since Apr 2026 | Minute to daily | Listings and delistings (post only) | [S] [48]; dataset mirror [V][47] |

### 3c. Surveillance products (who pays, pricing)

| Vendor | Product | Customers (named publicly) | Insider / pre-announcement angle | Pricing | Tag |
|---|---|---|---|---|---|
| Solidus Labs | HALO: trade surveillance, transaction monitoring, case management; cross-account, cross-symbol correlation | FalconX, HashKey, BitMEX, Luno, Amber, EDX, One Trading, CoinDCX, B2C2 (2026), Kalshi | Behavioural detection on venue account data | Not public (demo only) | [S] [39] |
| Eventus | Validus: real-time surveillance for crypto venues since 2018 | Cboe Digital, ErisX, Gemini (2020), FTX (pre-collapse); majority investment by Terminus Capital (Feb 2026) | Venue order and trade data | Not public | [S] [41] |
| Nasdaq | SMARTS market surveillance; Nasdaq Digital Assets | Gemini (2018), SBI VC; reports of 35+ crypto venues | Venue data | Not public | [S] [42] |
| Kaiko | Market Surveyor; regulator use cases; data across 100+ CEX/DEX | Regulators, market participants (unnamed) | Explicitly lists insider trading; the Robinhood note is an example | Not public | [S] [43] |
| Chainalysis | Custom on-chain market-integrity model (Polymarket, Apr 2026) | Polymarket | Insider trading on prediction markets | Not public | [S] [40] |
| Elliptic | Manipulation detection (wash trading, pump-and-dump) | Not named | On-chain plus CEX | Not public | [S] [44] |
| Nansen / Arkham | Wallet analytics and alerts (retail and pro) | Retail, funds | Users self-detect "smart money"; Arkham labels such as "insider whale" | Nansen Pro about $49 to $69 per month (aggregator); Arkham freemium, enterprise unpublished | [S] [45] |
| Exchange-internal | Binance and Coinbase internal audit, bounties; Korea's Virtual Asset User Protection Act (in force Jul 2024) requires exchanges to monitor abnormal trading and notify authorities | n/a | Account-level data | n/a | [S] [27][32]; Korea law [S] from Korean press search |

Who pays today: venues (to meet licensing duties, for example MiCA market-abuse provisions in the EU [I]), regulators, prediction markets under CFTC pressure, and funds that buy data. Retail pays only for wallet analytics.

### 3d. Open-source tools and public dashboards (GitHub search results [V][47])

| Repo | What | Stars / last push |
|---|---|---|
| pselamy/polymarket-insider-tracker | Flags fresh wallets, unusual sizing, niche markets on Polymarket | 209 / 2026-11 |
| NickNaskida/polymarket-insider-bot; suislanchez/polymarket-insider-detector | Polymarket insider screens (p-values, pre-resolution timing, clustering) | 50; 32 |
| AccursedGalaxy/Insider-Monitor; karidasd/find-the-insiders | Solana wallet and block-0 insider-cluster tracking | 41; 2 |
| Asalio123/binance-listing-study | Death-inclusive, turnover-weighted event study of every Binance USDT spot listing 2021 to 2026 (post-listing underperformance, anchored at listing-day close, not pre-announcement) | 0 / 2026-09 |
| pianist161/crypto-exchange-listings | CSV of listings and delistings on 10 exchanges since Nov 2024 with price at +5 min, 1h, 24h, 7d (from newcoinlistings.com) | 0 / 2026-11 |
| CyberPunkMetalHead/binance-trading-bot-new-coins; sueun-dev/exchange-listing-sniper | Bots that trade on listing announcements (speed, not surveillance) | 1504; 1 |
| danielmchristian/MarketGeek; FreeAiHub/binance-delisting-monitor | Live Binance anomaly flags (wash, volume spikes); delisting monitor skeleton | 2; 0 |

Public whale-alert services (Coinglass Hyperliquid whale alerts API, Buildix "Insider" wallet labels, Apify listing monitors) give raw alerts with no statistical baseline [S][54][55][56].

---

## 4. Novelty ratings for the student's candidate ideas

### (a) Pre-announcement test on Binance USDT-M futures listings and delistings, tick data: **PARTLY DONE (listings) / OPEN (delistings)**

Closest prior work:
- Félez-Viñas et al. [1] for the concept and benchmark design: hourly, Coinbase spot, on-chain.
- Kaiko [20] for the perp-based signal: OI, funding and volume before Robinhood listings. Industry note, no stated test or pre-registration.
- The Tie [21] for Binance pre-announcement front-loading (daily, industry).
- For delistings, only post-event returns [8][49] and delisting prediction [9].

What would make the student's version new [I]:
1. **Delistings with shorting.** Perps let informed sellers short. Spot and on-chain studies cannot see this. Pre-registered tests of aligned taker imbalance, OI and basis or funding in the hours before Binance futures delisting notices: I found no prior study.
2. **Tick resolution with aggressor side.** Minute-level taker imbalance from aggTrades and spread or depth from bookTicker, against placebo times, the same design as c4. Prior work is hourly or daily.
3. **Pre-registration and decision rule fixed before data**, with hashes, as in c4. Not found anywhere in this literature.
4. **Public-information controls.** The main threat is that the "drift" is public. Examples: Binance Monitoring Tags [S] before delistings, liquidity decay [9], perp listings on other venues first, Binance Alpha or roadmap signals [21], and on-chain deposits. A design that splits events by whether a public precursor existed (for example tagged vs untagged delistings, or futures-first vs spot-first listings) is a natural-experiment angle no one has used [I].
5. **Futures listings where the token already trades.** The pre-window can be measured on Binance spot or other venues' perps, so the perp listing itself is the news.

Practical caveats: for a new futures listing, the USDT-M contract does not exist before the announcement, so the pre-window must use Binance spot aggTrades (where spot exists) or other venues. Announcement timestamps must come from Binance CMS (catalogs 48 and 161), which the inventory script notes may be unreachable from this machine. A null result is publishable only with a stated power analysis.

### (b) Live public "unusual trading before announcements" monitor: **PARTLY DONE**

Closest prior work: private venue surveillance (Solidus, Eventus, Nasdaq, Kaiko) [39][41][42][43]; ad hoc public attributions (Lookonchain, Arkham, Bubblemaps) [24][33][37]; open-source Polymarket insider trackers [47]; post-announcement price trackers (cryptolisting.ws, pianist161 CSV) [47][48].

What would make it new [I]:
- Scoring **every** listing and delisting announcement across Binance, Coinbase, Upbit and Bithumb within minutes of publication. Each would get a pre-window abnormal flow score (returns, taker imbalance, OI, funding, volume) against that symbol's own placebo distribution, with a published false-positive rate, so that a 1-in-20 hit is expected by chance.
- Aggregate, anonymous, venue-level statistics only. No wallet attribution, and an explicit "not an accusation" framing like c4.
- Historical back-calibration published (the per-event scores for 2023 to 2026), so users can see base rates by exchange.

Note: a truly *pre*-announcement live alert cannot know which announcement is coming. Before publication it reduces to generic anomaly detection, which already exists as whale and OI alerts. The new product is announcement-anchored scoring at publication time plus calibrated history [I].

### Also rated briefly

- **(c) Political posts and crypto flow:** **PARTLY DONE.** Journalism and Polymarket academic work exist [13][36][37][51]. The student's pre-registered c4 test on Binance tick data is itself the closest crypto-CEX analogue I found [I].
- **(d) Token launches (memecoins):** **ALREADY DONE** on-chain [11][12][33][34][38]. Low marginal value from CEX tick data, except a narrow angle: flow before Binance *perp* listings of memecoins (the WIF case [25]).

---

## 5. Startup opportunities (gaps, payers, competitors, defensibility, risks)

| Gap | Who would pay | Competitors | Defensibility | Honest risks |
|---|---|---|---|---|
| **Cross-venue, announcement-anchored leak analytics.** Each venue sees only its own accounts; nobody sells a calibrated cross-exchange "did this listing leak?" score | Mid-tier exchanges proving listing integrity to licensors (MiCA, Korea VAUPA, Dubai VARA [I]); regulators (FSS, NCAs, CFTC) | Kaiko Market Surveyor, Solidus, Eventus | Low to medium: methodology, history, and trust; data is buyable by incumbents | Sales cycles of 6 to 18 months [I]; incumbents can add a module |
| **Issuer-side leak forensics.** Token projects whose listing leaked are victims and want evidence for the exchange or market maker | Token foundations, market makers, VCs | Bubblemaps, Arkham, freelance sleuths | Low | Small cheques; clients may want a clean bill, not truth (conflict of interest) |
| **Prediction-market integrity** (adjacent and hot) | Polymarket, Kalshi, regulators | Chainalysis, Solidus [39][40]; open-source trackers [47] | Low; crowded since 2026 | The student's CEX microstructure edge does not transfer much |
| **Research-grade announcement timestamp dataset** (ms-precision, edits and deletions, delistings, multi-exchange) | Quant funds, academics, data vendors | newcoinlistings.com, cryptolisting.ws, The Tie, Messari, news feeds | Low; scraping is easy | Exchange ToS on scraping; commoditised |
| **Public watchdog / scorecard** (media or nonprofit model) | Grants, journalists, donations; possibly regulators as citations | X accounts (Lookonchain, ZachXBT) | Reputation only | Defamation, non-commercial licence fits but cannot monetise Binance-derived data |

Cross-cutting risks:
1. **Data licensing [V][46].** data.binance.vision is CC BY-NC-SA 4.0. Commercial use, paid newsletters, commercial products and "trading signals" are excluded, and derived data carries the same terms. A commercial product needs a Binance enterprise licence or a paid vendor (Kaiko, Tardis, CCData) with redistribution rights. The repo itself is MIT for code; any derived datasets it publishes should carry CC BY-NC-SA attribution [I].
2. **Liability for implying wrongdoing.** Anonymous aggregate data cannot identify anyone. Even the strong cases (Kaiko, Argus) explicitly allege nothing [19][20]. Sleuths have been sued (Huang v. ZachXBT, withdrawn 2023 after edits) [50]. Score events, never people; publish false-positive rates and innocent explanations.
3. **Accuracy and base rates.** Pre-announcement drift has public causes: monitoring tags, roadmaps, other venues listing first, deposits to exchange wallets, momentum. With hundreds of events a month, about 5% will look "unusual" by chance. Without per-event calibration a monitor mostly produces false alarms [I].
4. **Legal theory varies.** Wahi was prosecuted as wire fraud plus securities insider trading [30][31]. Commodity-style misappropriation and Korea's VAUPA differ. A product implying "insider trading" asserts a legal conclusion it cannot support [I].
5. **Reflexivity.** A live public score is itself a trading signal and could be gamed or front-run, which is the same problem Coinbase cited when it dropped its roadmap [32][I].
6. **Access.** Binance CMS endpoints and exchange sites may block scrapers (already seen in `d1_inventory.py`); Korean exchange notices need Korean-language parsing [V, repo].

---

## 6. References

1. Félez-Viñas, E., Johnson, L., Putniņš, T. J. "Insider trading in cryptocurrency markets." SSRN WP 4184367 (2022, rev. 2025). https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4184367 [S]
2. UTS news, "Insider trading in crypto markets" (Aug 2022). https://www.uts.edu.au/news/2022/08/insider-trading-crypto-markets [S]
3. CLS Blue Sky Blog, "Insider Traders Have Found Their Way to Cryptocurrency Markets" (26 Aug 2022). https://clsbluesky.law.columbia.edu/2022/08/26/insider-traders-have-found-their-way-to-cryptocurrency-markets/ [S]
4. Decrypt, "Coinbase has a serious insider trading problem, study claims" (2022). https://decrypt.co/107671/coinbase-insider-trading-problem-study [S]
5. Ante, L. "Market Reaction to Exchange Listings of Cryptocurrencies." BRL Working Paper (2019). https://www.blockchainresearchlab.org/wp-content/uploads/2019/10/Exploring-Market-Reactions-to-Exchange-Listings-of-Cryptocurrencies-BRL-working-paper3.pdf [S]
6. Ante, L., Meyer, A. "Cross-listings of blockchain-based tokens issued through initial coin offerings." Decisions in Economics and Finance 44(2), 2021. https://ideas.repec.org/a/spr/decfin/v44y2021i2d10.1007_s10203-021-00323-0.html [S]
7. Li, J., Luo, M., Wang, M., Wei, Z. "Cryptocurrency Exchange Listings." AFT 2025 (LIPIcs vol. 354). https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.AFT.2025.11 [S]
8. Ammann et al. "Survivorship and Delisting Bias in Cryptocurrency Markets." https://www.alexandria.unisg.ch/bitstreams/2bc8397d-47dd-4f66-8467-9004b2c9d212/download [S]
9. Yang. "Developing Predictive and Explainable Models for Cryptocurrency Delistings: A Case Study of Binance Exchange." Asia-Pacific Journal of Financial Studies. https://onlinelibrary.wiley.com/doi/10.1111/ajfs.70045 [S]
10. Ruan, Q., Streltsov, A. "Perpetual Futures Contracts and Cryptocurrency Market Quality." SSRN 4218907. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4218907 [S]
11. Kamat, A. "Coordinated Sniper Cohorts on Pump.fun." arXiv 2607.02795 (2026). https://arxiv.org/abs/2607.02795 [S]
12. Ding, Lin, Luo, Xu. "Decompose Market Manipulation Strategies: Evidence from On-chain Meme Coin Market." SSRN 5953738 (2025). https://papers.ssrn.com/abstract=5953738 [S]
13. Mitts, J., Ofir, M. "From Iran to Taylor Swift: Informed Trading in Prediction Markets." Harvard Law School Forum (25 Mar 2026). https://corpgov.law.harvard.edu/2026/03/25/from-iran-to-taylor-swift-informed-trading-in-prediction-markets [S]
14. Anti-Corruption Data Collective. "Insider Risks in Polymarket Political Markets" (Apr 2026). https://acdatacollective.org/wp-content/uploads/2026/04/Insider_Risks_in_Polymarket_Political_Markets_ACDC.pdf [S]
15. Dissensus AI Working Paper, arXiv 2602.07046. https://arxiv.org/abs/2602.07046 [S]
16. Cointelegraph on Coin Metrics, "Coinbase effect is actually pretty lame" (2020). https://cointelegraph.com/news/coinmetrics-finds-the-coinbase-effect-is-actually-pretty-lame [S]
17. Cointelegraph on Messari, "New Coinbase listings really do outperform" (2020). https://cointelegraph.com/news/messari-new-coinbase-listings-really-do-outperform-rival-exchanges [S]
18. Wu Blockchain, "Investigation report: Is there insider trading in Binance and Coinbase's new listing." https://wublock.substack.com/p/investigation-reportis-there-insider [S]
19. ForkLog on WSJ/Argus, "WSJ analysts detect signs of insider trading in crypto markets" (2022). https://forklog.com/en/news/wsj-analysts-detect-signs-of-insider-trading-in-crypto-markets [S]
20. Cointelegraph, "Crypto perps volume points to traders front-running Robinhood listings: Kaiko" (5 May 2026). https://cointelegraph.com/news/crypto-perps-volume-points-to-traders-front-running-robinhood-listings-kaiko [S]
21. The Tie, "What Does an Exchange Listing Actually Deliver in 2026?" (13 Jul 2026). https://www.thetie.io/insights/what-does-an-exchange-listing-actually-deliver-in-2026 [S]
22. The Tie, "What Does a Binance Listing Deliver When You're Already on Three or More Major Exchanges?" https://www.thetie.io/insights/what-a-binance-listing-delivers-for-already-listed-tokens [S]
23. RockawayX, "Bullish or bearish: what really happens when tokens list on a CEX." https://rockawayx.com/insights/bullish-or-bearish-what-really-happens-when-tokens-list-on-a-cex [S]
24. The Block, "Binance refutes insider trading concerns amid BOME frenzy" (18 Mar 2024). https://www.theblock.co/news/markets/2024-03-18-binance-bome-insider-trading-283027 [S]
25. Investing.com, "Did WIF insider buy before Binance listing?" https://ng.investing.com/news/cryptocurrency-news/did-wif-insider-buy-before-binance-listing-here-are-the-details-1192715 [S]
26. Decrypt, "Trader makes $100K in seconds front-running token listing on Binance." https://decrypt.co/121651/trader-makes-100k-front-running-token-listing-binance [S]
27. The Block, "Binance suspends employee for allegedly profiting off of insider information" (Mar 2025). https://www.theblock.co/post/347890/binance-suspends-employee-for-allegedly-profiting-off-of-insider-information [S]
28. The Block, "Binance post confirming insider trading sends 'year of the yellow fruit' meme token even higher" (8 Dec 2025). https://www.theblock.co/news/markets/2025-12-08-binance-confirm-insider-trading-year-yellow-fruit-meme-token-higher-381752 [S]
29. Seoul Economic Daily, "Did information leak early? Upbit faces listing controversy" (7 Jun 2026). https://en.sedaily.com/finance/2026/06/07/did-information-leak-early-upbit-faces-listing-controversy [S]
30. SEC Litigation Release LR-25947 (SEC v. Wahi, Ramani judgment). https://www.sec.gov/litigation/litreleases/lr-25947 [S]
31. Blockworks, "Former Coinbase manager sentenced to 2 years in prison" (May 2023). https://blockworks.co/news/former-coinbase-manager-sentenced [S]
32. The Block, "Despite new listing procedure, Coinbase faces fresh questions over frontrunning claims." https://www.theblock.co/post/142025/despite-new-listing-procedure-coinbase-faces-fresh-questions-over-frontrunning-claims ; Blockworks, "Following insider trading accusations, Coinbase moves to more stringent review system." https://blockworks.co/news/following-insider-trading-accusations-coinbase-moves-to-more-stringent-review-system [S]
33. The Block, "Bubblemaps claims one trader turned $1 million into $109 million trading Trump memecoin" (18 Feb 2025). https://www.theblock.co/news/web3/2025-02-18-crypto-analytics-platform-bubblemaps-claims-one-trader-turned-1-million-into-109-million-trading-trump-memecoin-341664 [S]
34. Bubblemaps, "How Hayden Davis rugged $LIBRA for $100M with President Milei." https://blog.bubblemaps.io/how-hayden-davis-rugged-libra-for-100m-with-president-milei/ [S]
35. The Block, "Traders of Solana-based LIBRA memecoin lost $251 million: Nansen" (19 Feb 2025). https://www.theblock.co/post/342266/traders-of-solana-based-libra-memecoin-lost-251-million-nansen [S]
36. CoinDesk, "One trader made millions betting $200M on BTC just before Trump's crypto reserve news" (3 Mar 2025). https://www.coindesk.com/markets/2025/03/03/one-trader-made-millions-betting-usd200m-on-btc-just-before-trump-s-crypto-reserve-news [S]
37. Decrypt, "Alleged 'Trump insider whale' denies insider trading, opens new $340M short" (Oct 2025). https://decrypt.co/344137/alleged-trump-insider-whale-denies-insider-trading-opens-new-340m-short [S]
38. Pine Analytics, "Exit Liquidity Machines." https://pineanalytics.substack.com/p/exit-liquidity-machines [S]
39. Solidus Labs, product and clients pages. https://soliduslabs.com/product ; https://www.soliduslabs.com/clients/digital-assets [S]
40. Invezz, "Polymarket taps blockchain data firm Chainalysis to curb insider trading" (30 Apr 2026). https://invezz.com/news/2026/04/30/polymarket-taps-blockchain-data-firm-chainalysis-to-curb-insider-trading/ [S]
41. Eventus, digital asset venues page. https://www.eventus.com/digital-asset-venues/ ; Mondo Visione, Terminus majority investment in Eventus (Feb 2026). https://mondovisione.com/media-and-resources/news/terminus-capital-partners-makes-majority-investment-in-eventus-fueling-firms-c-2026226 [S]
42. Bloomberg, "Winklevoss twins hire Nasdaq to keep cheaters off crypto market" (25 Apr 2018). https://www.bloomberg.com/news/articles/2018-04-25/winklevoss-twins-hire-nasdaq-to-keep-cheaters-off-crypto-market ; The Block, "7 cryptocurrency exchanges are now using Nasdaq's surveillance technology." https://www.theblock.co/linked/9865/7-cryptocurrency-exchanges-are-now-using-nasdaqs-surveillance-technology [S]
43. Kaiko, Market Surveyor. https://www.kaiko.com/products/market-surveyor [S]
44. Elliptic, manipulation detection. https://www.elliptic.co/manipulation-detection.html [S]
45. Costbench, Nansen plans and pricing (third-party aggregator). https://www.costbench.com/software/onchain-analytics/nansen/ [S]
46. Binance Vision Terms of Use (CC BY-NC-SA 4.0, commercial use excluded). https://data.binance.vision/Binance_Vision-Terms_of_Use.pdf [V]
47. GitHub repositories (metadata verified via GitHub search API, READMEs not opened): https://github.com/pselamy/polymarket-insider-tracker ; https://github.com/NickNaskida/polymarket-insider-bot ; https://github.com/suislanchez/polymarket-insider-detector ; https://github.com/AccursedGalaxy/Insider-Monitor ; https://github.com/karidasd/find-the-insiders ; https://github.com/Asalio123/binance-listing-study ; https://github.com/pianist161/crypto-exchange-listings ; https://github.com/CyberPunkMetalHead/binance-trading-bot-new-coins ; https://github.com/sueun-dev/exchange-listing-sniper ; https://github.com/danielmchristian/MarketGeek ; https://github.com/FreeAiHub/binance-delisting-monitor [V]
48. CryptoListing.ws, "Crypto listing price reaction 2026." https://cryptolisting.ws/listing-price-reaction/ [S]
49. Blockonomi, "What happens when a cryptocurrency gets delisted from an exchange" (cites a CoinSight study of 101 Binance delistings; original not located). https://blockonomi.com/what-happens-when-a-cryptocurrency-gets-delisted-from-an-exchange/ [S]
50. The Block, "Jeffrey 'Machi Big Brother' Huang drops defamation suit against crypto sleuth ZachXBT" (14 Aug 2023). https://www.theblock.co/news/regulation/2023-08-14-jeffrey-machi-big-brother-huang-drops-defamation-suit-against-crypto-sleuth-zachxbt-244776 [S]
51. Unusual Whales, "Unusual options trading before Trump's tariff announcement pause." https://unusualwhales.substack.com/p/unusual-options-trading-before-trumps [S]
52. Rep. Ritchie Torres, letter on oil futures before a Trump Iran announcement. https://ritchietorres.house.gov/posts/rep-torres-demands-sec-and-cftc-investigate-suspicious-oil-futures-trade-made-ahead-of-trump-iran-announcement [S]
53. The Block Research, "A look at Binance delistings." https://www.theblock.co/research/institutional/a-look-at-binance-delistings-37582 [S] (findings not visible in snippet)
54. Apify, Exchange Listing Monitor. https://apify.com/datadeltas/exchange-listing-monitor [S]
55. Buildix, "Whale tracker: live insider moves on Hyperliquid 2026." https://www.buildix.trade/blog/whale-tracker-live-insider-moves-hyperliquid-2026 [S]
56. Coinglass API, Hyperliquid whale alert. https://docs.coinglass.com/reference/hyperliquid-whale-alert [S]
