# Memecoins: why people buy them, and who makes money

Status: scoping note, 2026-11-20. No outcome has been computed. Every project below must be pre-registered (plan written and hash-locked) before any memecoin return, flow or PnL statistic is looked at.

Companion files:
- `LITERATURE.md`: annotated references grouped by theme.
- `DATA.md`: free data sources with exact endpoints, file names, coverage, known traps, and what costs money.
- `IDEAS.md`: each project in depth, with the machine-learning angle and the pre-registration outline.

Framing rule for this folder: we measure behaviour, explain it, and detect harm. Nothing here gives guidance on launching, pumping, sniping or rugging a token, and no detector is published as a real-time trading signal.

## 1. The question in plain English

Most memecoins collapse. Studies of token launches find that about 60% of Ethereum and BSC tokens were active for less than a day (Cernera et al. 2023), and under 2% of pump.fun tokens launched in Q4 2024 reached a major exchange (Mancino 2025, preprint). The repo's own HIP-1 desk research found the median Hyperliquid spot token at about 3% of its peak close. Yet millions of people keep buying. Two questions follow:

1. Why do people buy an asset they can see usually goes to zero?
2. When it does go to zero, where did the money go?

## 2. What research says about why people buy

The evidence points to four overlapping reasons. None is enough alone.

**A lottery ticket is what they are buying.** In cumulative prospect theory people overweight small probabilities, so an asset with a small chance of a 100x payoff can be overpriced and earn a negative average return even when buyers know the odds (Barberis and Huang 2008). In stocks, the lottery signature is the MAX effect: stocks with the largest recent one-day jump earn more than 1% a month less afterwards (Bali, Cakici and Whitelaw 2011). Lottery-type stocks (low price, high idiosyncratic volatility and skewness) attract the same people who buy state lottery tickets (Kumar 2009). In crypto the sign of the MAX effect is disputed: Grobys and Junttila (2021) find high-MAX coins underperform, Ozdamar, Akdeniz and Sensoy (2021) and Li, Urquhart, Wang and Zhang (2021) find they outperform at a weekly horizon, and an hourly study finds a small reversal (Yadav 2025). That makes it an open question, not a settled one.

**Trading is entertainment and a substitute for gambling.** Investors who say they enjoy gambling turn over their portfolios twice as fast (Dorn and Sengmueller 2009). Large lottery jackpots pull small trades out of lottery-like stocks (Gao and Lin 2015 in Taiwan; Dorn, Dorn and Sengmueller 2015 in the US). National football matches cut stock trading volume by up to 48% (Ehrmann and Jansen 2017). Legal sports betting lowers household investment, crypto included (Baker et al., NBER WP 33108). Pump participants on Telegram usually know it is a pump and join anyway, which Dhawan and Putnins (2023) attribute to gambling preference and overconfidence.

**Attention and social contagion.** Individual investors buy what grabs their attention (Barber and Odean 2008). The stocks Robinhood users herd into earn about -4.7% over the next 20 days (Barber, Huang, Odean and Schwarz 2022). Attention proxies predict crypto returns (Liu and Tsyvinski 2021), and Musk's posts move DOGE within minutes (Ante 2023). Socially, winners talk and losers stay quiet, which spreads high-variance strategies (Han, Hirshleifer and Walden 2022; Hirshleifer 2020), and beliefs passed through a network can produce bubbles, volume bursts and reversal (Pedersen 2022). Bullish echo chambers are followed by low returns (Cookson, Engelberg and Mullins 2023).

**Crypto may be different.** Kogan, Makarov, Niessner and Schoar (2024) show the same eToro traders are contrarian in stocks but momentum traders in crypto, and that lottery preference does not explain the gap. Their conjecture is that price moves change beliefs about future adoption. Every test here should include this adoption-belief channel as a competing explanation.

## 3. What research says about who makes money

The answer depends on the layer of the market.

- **At launch (on-chain):** creators, insiders and sniper bots. Organisers of "1-day rug pulls" took about $240M on Ethereum and BSC (Cernera et al. 2023). Scam tokens on Uniswap took at least $16M from 39,762 victim addresses (Xia et al. 2021). Most memecoin tokens with returns above 100% show signs of artificial growth (Mongardini and Mei 2025, preprint, about 82.6% to 82.9% depending on version). Careful recent work warns that apparent "smart money" or sniper edges often vanish under look-ahead controls (Gafarov 2026; Kamat 2026; both preprints, unverified).
- **Infrastructure:** the most reliable winners. Industry coverage of Galaxy Research reports about $120M of pump.fun fees in 30 days (news coverage, original not read). Sandwich bots on Solana ran more than 500,000 attacks costing victims over $7.7M in four months of 2025 (Gerzon et al. 2025, IMC, author list unverified).
- **Retail wallets:** industry dashboards put the profitable share of pump.fun wallets below 50% in most months from April 2024, with a low of 30.1% in June 2025 (CoinGecko, not peer reviewed, realised PnL only, bots not filtered). For $TRUMP, Nansen figures reported in the press count about 989,000 of 1.48M buyer wallets at a loss (industry estimate).
- **Exchange-listed perpetuals (this repo's comparative advantage):** no published estimate exists. On Binance the money flows we can measure are aggregate: funding from longs to shorts, fees to the exchange, and taker versus maker markouts. On Hyperliquid every trade carries both addresses, so wallet-level PnL is possible, with history limits.

## 4. Ranked projects on free data

Ranking uses the novelty review's verdicts, not the scouts' optimism. "Open" means no prior work was located; "partly done" means close prior work exists and our contribution is a specific extension. The reviewer's web search was exhausted, so every novelty verdict is provisional until a literature search runs.

| Rank | Project | Novelty | ML | Effort |
|---|---|---|---|---|
| 1 | P1 Positioning-metrics audit and crowd count recovery | open | no | 3 to 4 days |
| 2 | P2 Survival and listing-day buy-and-hold losses of memecoin perps | partly done | yes (survival model, secondary) | 6 days |
| 3 | P3 Funding transfers and the lottery premium | partly done | no | 5 days |
| 4 | P4 Who wins on Hyperliquid memecoin perps, by trader type | partly done | no | 7 days |
| 5 | P5 Binance memecoin perp listings, priced off Hyperliquid | partly done | no | 6 days |
| 6 | P6 Validating "retail" proxies with Binance RPI flags | open | yes (positive-unlabelled) | 10 days, forward collection |
| 7 | P7 Football matches as an outside gamble (Euro 2024) | partly done | no | 5 days |

### P1. Positioning-metrics audit and crowd count recovery
- **Question:** Are Binance's free 5-minute positioning metrics reliable enough to use, and how many accounts actually hold a memecoin perp in its first days?
- **Data:** `data.binance.vision/data/futures/um/daily/metrics/{SYMBOL}/` for about 29 memecoin perps plus BTCUSDT and ETHUSDT, 2021-12-01 to 2026-11, with S3 `LastModified` and `.CHECKSUM` files.
- **Method:** Build a missing-data mask (top-trader ratios empty 2021-12-30 to 2022-12-14 with short exceptions; taker ratio empty to 2022-05-09; 2024-02-16 truncated at 13:30; unsorted rows on about 220 days). Hash every file and re-download monthly to detect revisions. For files before 2023-07-10, where ratios are full-precision floats, recover the reduced fraction p/q of long to short accounts; p+q is a lower bound on the account count, identified only up to an integer multiple, so a consistency model across consecutive rows and the two ratio series is needed.
- **ML:** no.
- **Novelty:** open. No use of the full-precision fractions was located, and the repo's `monthly_panel` does not record the 2022 top-trader gap.
- **Effort:** 3 to 4 days.
- **What you learn:** whether every later positioning study (P3, crowd versus top traders) stands on solid data, and a free lower bound on how many accounts arrive at a memecoin listing.
- **First step:** list every metrics key for DOGEUSDT, 1000PEPEUSDT, WIFUSDT and TRUMPUSDT and write the mask as a CSV.

### P2. Survival and listing-day losses of memecoin perps
- **Question:** What share of Binance memecoin perps are delisted within 12 and 24 months, compared with other new perps, and what does a buyer at the first trade lose on average by day 30, 90 and 180?
- **Data:** `research/market_evolution/data/contract_lifecycle.csv` in the main repo (935 lives, 151 delisted, 108 of them first listed from 2023), Binance delisting notices (catalogId 161, 447 notices), daily klines, Hyperliquid `meta` (`isDelisted` flags).
- **Method:** Kaplan-Meier curves and a Cox model with pre-registered covariates (launch-to-listing lag, day-1 volume, day-1 to day-3 funding, spot listing status). Buy-and-hold abnormal returns against a BTC-beta benchmark, cut at `last_trade_day`. Memecoin label frozen and hashed before outcomes.
- **ML:** optional random survival forest as an exploratory comparison with a time-split holdout. Report lift over the base rate, since collapse may be the majority outcome.
- **Novelty:** partly done (dead-coin studies on spot exist); a survivorship-free census of exchange-listed memecoin derivatives was not located.
- **Effort:** 6 days.
- **What you learn:** whether even the memecoins that reach a top exchange mostly die, and the average cost of buying the listing.
- **First step:** hand-code and hash the memecoin flag list for all 935 lives with a written rule.

### P3. Funding transfers and the lottery premium
- **Question:** How much money flows from memecoin perp longs to shorts through funding, when is it concentrated (first weeks after listing, after high-MAX weeks), and do high-MAX memecoins earn lower returns net of funding?
- **Data:** `fundingRate` monthly files, `metrics` (open interest value), daily klines, all USDT-M perps.
- **Method:** Transfer = sum over settlements of rate times OI value at the nearest 5-minute row. Panel regressions of funding and of next-week funding-adjusted returns on MAX with a common meme factor, week fixed effects and two-way clustering. Pre-register a two-sided MAX test. Treat TK prospect-theory value and skewness only as robustness arms (they are collinear with MAX).
- **ML:** no.
- **Novelty:** partly done. "Crypto carry" (Schmeling, Schrimpf and Todorov 2023, BIS WP 1087, unverified) links funding to retail leverage demand; a memecoin cross-section net of funding was not located.
- **Effort:** 5 days.
- **What you learn:** the dollar price leveraged memecoin optimists pay. Caveat: the receivers are largely basis traders and market makers, not informed bears, and funding caps and interval changes (8h, 4h, 1h) partly shape the "premium".
- **First step:** tabulate the funding interval and cap per memecoin symbol over time from the files.

### P4. Who wins on Hyperliquid memecoin perps
- **Question:** On 13 or more Hyperliquid memecoin perps, what share of net PnL (closed PnL minus fees plus funding) goes to makers versus takers, large versus small accounts, and liquidated versus never-liquidated wallets, and is it more concentrated than on BTC and ETH?
- **Data:** `stats-data.hyperliquid.xyz/Mainnet/leaderboard` for the wallet universe, `userFillsByTime` and `userFunding` via `api.hyperliquid.xyz/info`, plus forward-recorded websocket trades (both addresses per trade).
- **Method:** stratified wallet sample, pre-registered. Gini, top-1% share, maker minus taker PnL per dollar of volume with block-bootstrap intervals. Main analysis only on wallets whose full history is retained (about 10,000 orders per wallet), the rest as sensitivity. Reuse the `research/hyperliquid/` skill-versus-luck pipeline for persistence.
- **ML:** no.
- **Novelty:** partly done (vendor dashboards, the repo's own skill-versus-luck work). Merges scout ideas 6, 27 and 58.
- **Effort:** 7 days.
- **What you learn:** the only free wallet-level answer to "who makes money" on memecoin perps. Retention truncates the most active wallets, which is exactly the group of interest, so the forward-recorded tape is the clean version.
- **First step:** start the websocket recorder for memecoin coins now; it costs nothing and history cannot be recovered later.

### P5. Binance memecoin perp listings, priced off Hyperliquid
- **Question:** When Binance announces a perpetual on a memecoin already trading on Hyperliquid, is there pre-announcement drift, an announcement jump, and a later reversal, compared with matched Hyperliquid memecoins not listed in the window?
- **Data:** Binance announcements (`catalogId=48`, 2,299 notices from 2017-07-21, millisecond release times), Hyperliquid `candleSnapshot` (daily full history; hourly only about the last 7 months; 1-minute only about 3.5 days), Binance klines from the first trade.
- **Method:** event study at daily resolution, abnormal return against an equal-weight Hyperliquid memecoin index, matched not-yet-listed controls (Binance lists after run-ups, so mean reversion alone predicts a decline). Leakage results reported only in aggregate.
- **ML:** no.
- **Novelty:** partly done. General listing studies exist (Ante 2019; Felez-Vinas, Johnson and Putnins on insider trading), but no study of memecoin perp listings was located.
- **Effort:** 6 days.
- **What you learn:** whether a Binance listing is an exit for early holders and a loss for perp longs.
- **First step:** crawl catalog 48 once at 1 request per second, save a sha256 manifest, and match perp notices to `contract_lifecycle.csv`.

### P6. Validating "retail" proxies with Binance RPI flags
- **Question:** Do trade-size, round-notional or timing proxies identify trades sent from the Binance app or website?
- **Data:** forward polling of `https://www.binance.com/fapi/v1/trades` (field `isRPITrade`, live since 2025-11-20) for about 20 RPI-enabled symbols for 4 to 8 weeks. The flag is not in the archive.
- **Method:** RPI-true trades are a positive label; RPI-false mixes app and API takers, so use positive-unlabelled evaluation (precision at k, lift) rather than accuracy. Check gaps by trade-id continuity.
- **ML:** yes.
- **Novelty:** open; the crypto counterpart of Barber, Huang, Jorion, Odean and Schwarz (2024).
- **Effort:** 10 days including collection.
- **What you learn:** whether any project in this folder may call small-trade share "retail". In one probe 82% of 1000PEPEUSDT fill rows were under 100 USDT, mostly algorithmic child fills, so the default answer is no.
- **First step:** a gap-checked poller for 1000PEPEUSDT, which had 8 RPI trades per 1,000 in one sample (zero for BTC, DOGE, TRUMP and WIF).

### P7. Football matches as an outside gamble
- **Question:** During Euro 2024 match minutes, does taker activity in memecoin perps fall more than in BTCUSDT and ETHUSDT?
- **Data:** daily aggTrades for 1000PEPEUSDT, DOGEUSDT, WIFUSDT, 1000BONKUSDT, BTCUSDT, ETHUSDT, 2024-06-14 to 2024-07-14 (51 matches); public kickoff times.
- **Method:** minute-level difference in differences against the same clock minutes on non-match days within plus or minus 14 days, clustered by match. World Cup 2022 only as secondary, because it starts nine days after the FTX bankruptcy.
- **ML:** no.
- **Novelty:** partly done; extends Ehrmann and Jansen (2017) to crypto, where no version was located.
- **Effort:** 5 days.
- **What you learn:** whether memecoin trading competes with live sport for the same attention, a direct test of the entertainment motive.
- **First step:** write the fixture list with UTC kickoff times and lock the plan before downloading any aggTrades.

**Deprioritised, with reasons from the review:** US lottery jackpots and Super Bowl tests (Binance.com excludes US residents, so a null is uninformative); Trump-post event studies on TRUMPUSDT (only 3 coin-specific posts after the perp listed); Musk-DOGE decay (from November 2024 "DOGE" mostly means the Department of Government Efficiency); spot PEPE versus 1000PEPE denomination tests (the relative tick is 0.27% on spot against 0.0027% on the perp, so differences are mechanical); Reddit, Wikipedia and Google Trends projects (hosts blocked, licences unclear, Wikipedia version largely done already).

## 5. Risks

- **Survivorship.** Binance lists only memecoins that already succeeded. Results describe the upper tail, not the typical launch.
- **No account IDs on Binance.** Only aggregate winners and losers can be measured there.
- **Retail proxies are unvalidated** (see P6). Avoid "retail" language until validated.
- **Archive traps.** Placeholder files after delisting (MEMEFIUSDT 548-byte zips through 2026-10; 1000XUSDT 1-minute files after 2025-11-14), metrics start 2021-12-01 at the earliest, 2022 gaps, precision changes, re-uploads.
- **Exchange-rule confounds.** Tick and lot size, minimum notional, funding caps and intervals, leverage caps at listing.
- **Common meme factor and low power.** About 50 to 65 meme perps co-move; cross-sectional tests need a meme factor and block bootstrap, and a power calculation.
- **Confounding windows.** FTX collapse 2022-11-11, the 2025-10-10 liquidation cascade, the TRUMP launch weekend, batched listing announcements.
- **Multiple testing.** One pre-registration per project cluster, with Holm or Romano-Wolf correction and a lockbox period.
- **Literature not read in full.** Paper hosts were blocked for every agent, so numbers come from abstracts and catalogue records. Check against PDFs before any number enters a pre-registration.
- **Ethics.** Measurement and harm detection only, aggregate and delayed reporting of leakage, no playbooks.

## 6. Start here

1. [ ] Read `DATA.md` sections 1 and 2 and confirm the endpoints still answer.
2. [ ] Start the Hyperliquid websocket trade recorder for memecoin coins (forward-only data; every day missed is lost).
3. [ ] Start the RPI poller for 1000PEPEUSDT and DOGEUSDT (forward-only).
4. [ ] Write and hash the memecoin flag list for all lives in `contract_lifecycle.csv`, with the rule, before any outcome is opened.
5. [ ] Run P1 (metrics audit). It has no outcome variable, so it needs no lock, and P3 and other positioning work depend on it.
6. [ ] Write the P2 pre-registration (hazard model and buy-and-hold losses), hash it, then run.
7. [ ] Ask for the blocked hosts (arxiv.org, doi.org, papers.ssrn.com, nber.org, developers.binance.com) to be allowed, then verify every citation marked unverified in `LITERATURE.md`.
8. [ ] Only then pre-register P3 to P5.
