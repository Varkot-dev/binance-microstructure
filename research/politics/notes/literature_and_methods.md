# Politicians' posts and crypto prices: what is known, and how to measure it credibly

Scope: literature and methods for a minute-level event study of posts by politicians
(Trump and family, other Republicans and Democrats, regulators) on Binance USDT-M
futures, 2020 to 2026. Written 2026-11-18.

Evidence tags:
- **[V]** verified at the primary source this session.
- **[S]** secondary: search-engine abstract, snippet, press report or working-paper summary.
- **[I]** my inference or recommendation.

Every publisher, repository and university host tried with WebFetch this session
(ideas.repec.org, bis.org, econ.jhu.edu, publikationen.ub.uni-frankfurt.de) failed DNS
resolution from this machine. As a result **nothing below is tagged [V]**. Every number
attributed to a paper comes from abstracts and snippets returned by web search, and
should be checked against the PDF before it goes into a write-up.

## 0. Summary

1. **Most posts do not move markets; a small, predictable subset does.** J.P. Morgan's
   Volfefe work (2019) is reported to have found that about 146 of roughly 4,000 Trump
   tweets sent during market hours moved Treasury yields in the following 5 minutes,
   and that the market-moving ones mostly contained a few words ("China", "billion",
   "products", "Democrats", "great") [S, ref 1, 2]. A 2025 J.P. Morgan note reportedly
   found that about 10% of 126 Truth Social posts on trade and economic policy had a
   clear FX impact. Tariff posts were the most influential, with nearly a third moving
   markets, and crypto was described as "largely unaffected" [S, ref 3, 4].
2. **Topic matters more than the person.** In equities the reactions concentrate in
   trade-war and tariff posts [S, ref 5, 6] and in Fed-criticism tweets (fed funds
   futures, 30-minute windows) [S, ref 7]. Company-specific tweets move the named stock
   briefly and then fade [S, ref 8, 9].
3. **Posts often follow the market.** Abdi et al. (SAFE WP 314, 2021), using
   minute-level SPY and VIX, report that most Trump tweets react to market moves that
   had already happened and carry little new information. Trade-war tweets are the
   exception, because the author controls the policy [S, ref 6]. This is the main
   identification threat for the project.
4. **Crypto evidence is thin and mostly about Musk.** Ante (TFSC 2023), with 47
   crypto-related Musk events, finds significant abnormal volume and, on average,
   significant price effects only for Dogecoin. Reported figures are about +1.46% in
   the event minute, with the spike lasting 2 to 3 minutes [S, ref 10, 11]. Huynh
   (Computational Economics) relates Musk's tweet tone to Bitcoin returns but not to
   volatility, at daily frequency [S, ref 12]. For Trump and crypto I found only theses
   and an SSRN paper reported in the press (daily or multi-day windows), plus press
   accounts of single events: the crypto-reserve posts (2025-03-02), the $TRUMP launch
   (2025-01-17/18), WLFI trading (2025-09-01) and the 100% China tariff post
   (2025-10-10) [S, ref 13 to 20]. **I found no peer-reviewed minute-level study that
   ranks politicians by their effect on crypto.** This project would fill that gap [I].
5. **Regulators are the most clearly price-relevant group in crypto.** Auer and Claessens
   (BIS 2018) report large reactions to news on bans and securities-law treatment, and
   little reaction to generic warnings [S, ref 21]. The hacked SEC X post of 2024-01-09
   (a fake spot-ETF approval, live about 15 minutes) is a clean natural experiment: the
   content was false, and BTC rose to about $47.6k and fell back to about $45.5k [S,
   ref 22].
6. **Recommended design** (section 6): (a) posts from archived sources with second-level
   UTC timestamps; (b) topic coded before any price data is opened; (c) per-post
   abnormal |return|, realized volatility, volume and taker order-flow imbalance at
   1 to 60 minutes, built from Binance 1-minute klines, each measured against matched
   control windows at the same minute of the week; (d) a stacked event panel with
   event and minute-of-window fixed effects and permutation inference over placebo
   times; (e) a pre-trend test; (f) empirical-Bayes shrunk per-post effects for the
   ranking, with rank confidence sets and Benjamini-Hochberg FDR control.

## 1. Prior evidence: Trump posts and traditional markets

| Study | Market, frequency | Events | Main result | Tag |
|---|---|---|---|---|
| J.P. Morgan "Volfefe" (2019) [1, 2] | US Treasury yields / implied vol, 5 min after tweet | ~14,000 tweets; ~4,000 during market hours | ~146 market-moving; keywords China, billion, products, Democrats, great; explains a "measurable fraction" of implied-vol moves | [S] |
| "Measuring Trump", FRL 38 (2021) 101447 [23] | European stock indices, monthly/daily predictive regressions | Volfefe index | Volfefe adds predictive power after macro controls; time-varying across markets. Author names not confirmed by snippet | [S] |
| Gjerstad, Meyn, Molnar, Naess, DSS 147 (2021) 113577 [5] | US stocks, intraday | All Trump tweets, LDA topics | After tweets: more uncertainty, more trading, a small decline. Only "trade war" topic matters; China stocks fall, gold rises | [S] |
| Abdi, Kormanyos, Pelizzon, Getmansky, Simon, SAFE WP 314 (2021) [6] | SPY, VIX, minute level | Trump tweets classified by ML (topic, tone) | Most tweets react to prior moves; trade-war tweets the exception | [S] |
| Bianchi, Gomez-Cram, Kind, Kung, JME (2023); NBER w26308 [7] | Fed funds futures, 30-min window | Tweets criticizing the Fed | Expected policy rate lowered; drafts report about 10 bp in total, press about 0.3 bp per tweet | [S] |
| Ge, Kurov, Wolfe, J. Financial Research 42(2) (2019) [8] | Named stocks, intraday | Company-specific tweets, Nov 2016 to Jul 2017 | Move price, volume, volatility; stronger before inauguration; fade over days | [S] |
| Born, Myers, Clark, Algorithmic Finance 6 (2017) [9] | Named stocks | 15 posts about 10 firms, pre-inauguration | Transitory; consistent with noise traders | [S] |
| Brans and Scholtens, PLOS ONE (2020) [24] | Named stocks | Company tweets | Only strongly negative tweets lower value | [S] |
| J.P. Morgan (2025) on Truth Social [3, 4] | G10 FX, 5 to 180 min | 126 policy posts | ~10% moved FX; ~1/3 of tariff posts; trading the signal returned little | [S] |

Takeaways [I]:
- Effects are rare, concentrated by topic and short-lived (minutes). Short-window
  designs (5 to 30 minutes) are the norm, at minute or second resolution.
- Studies that control for prior market moves (Abdi et al.) find much smaller effects
  than those that do not. This study must report both.
- The effect of one person changes over time (pre versus post inauguration in [8];
  2019 versus 2025 in [3, 13]). Rankings should be estimated by period.

## 2. Prior evidence: crypto

### 2.1 Musk (the closest methodological template)

- **Ante, "How Elon Musk's Twitter activity moves cryptocurrency markets",
  Technological Forecasting and Social Change 186 (2023)** [10, 11]. The early
  working-paper version had 6 events: the Bitcoin bio change gave CAR of 6.31% at
  30 min, 13.19% at 1 h, and a peak of 18.99% (sources disagree on whether the peak
  came at 4 or 7 hours); "One word: Doge" gave 8.17% at 5 min [S]. The final version
  has 47 events. Abnormal volume is significant; average price effects are
  significant only for DOGE; and for BTC, positive and negative tweets cancel, while
  non-negative tweets alone give positive abnormal returns [S]. Minute-level
  reporting: about 1.46% in the event minute, 83% of events positive, the spike
  lasting about 2 to 3 minutes [S].
  - Lessons [I]: (a) average sign-agnostic returns hide the effect, so measure
    |return| and volatility, or sign the effect by tone; (b) volume reacts more
    reliably than price; (c) the action happens in the first 1 to 5 minutes.
- **Huynh, "When Elon Musk changes his tone, does bitcoin adjust its tune?",
  Computational Economics** [12]. 10,850 tweets, Dec 2017 to May 2021, tone vs BTC.
  Granger causality for returns (with reversal after positive tone), none for
  volatility. Daily-type frequency [S].
- University of Kent undergraduate study (2022): high-frequency DOGE data, abnormal
  volume and price for at least 60 minutes after tweets [S, ref 25]. Student work;
  low weight.

### 2.2 Trump and family, and political news

- **Theses at daily frequency.** A Lund thesis (2025, VADER sentiment, daily OLS)
  finds tweet sentiment predicts BTC in 2019 but 2024 campaign posts do not [S, ref
  13]. An NCCU thesis aggregates 4,131 election-period Truth Social posts into 170
  daily observations; crypto-referencing posts go with higher BTC returns [S, ref 14].
- **Krause (SSRN, reported by Block Media).** Over 9-day windows around Trump
  crypto-related events, BTC excess return 0.94% vs -0.04% otherwise, p = 0.0498;
  nothing for ETH [S, ref 15]. A marginal result with wide windows.
- **Ben Jabeur et al. (2025)** report political news affects crypto returns at 2 to 4
  month horizons [S, ref 26]. Not comparable to minutes.
- **$TRUMP memecoin.** Perdichizzi and Galati study spillovers from the launch
  (volatility spillovers and information cascades) [S, ref 16]. Press: the
  token fell about 38 to 48% after the MELANIA launch; sources disagree on whether the
  wider market was affected [S, ref 17]. Launch dates disagree between 17 and 18
  January 2025 across sources, which is a timestamp warning [S].
- **Crypto reserve, 2025-03-02.** Two Truth Social posts about an hour apart: the first
  named XRP, SOL and ADA, the second added BTC and ETH. Reported Sunday gains:
  ADA +50 to +70%, XRP about +30%, SOL about +20%, BTC about +10%; most of it gone by
  Monday [S, ref 18]. Useful as a showcase case, but a weekend with thin liquidity (see
  pitfalls).
- **WLFI, 2025-09-01.** Trading debut swung more than 40% peak to trough; it fell about
  12 to 20% on day one [S, ref 19]. This is a listing event, not a post.
- **China tariff, 2025-10-10.** Followed by about $19 billion of liquidations in 24h
  (CoinGlass) [S, ref 20]. Reported post times conflict: 10:57 ET, 13:00 ET (17:00
  UTC), 14:00 ET, with a second post at 16:50 ET (20:50 UTC). One account says large
  holders sold more than an hour before the first post [S, ref 20]. A textbook case of
  why timestamps and pre-trends matter.

### 2.3 Regulators

- **Auer and Claessens, BIS Quarterly Review, Sept 2018** [21]. Event study of
  regulatory news: bans and securities-law treatment have the largest negative
  effects; AML news and limits on access to regulated markets are also negative; news
  of legal frameworks goes with gains; general warnings have little effect. VoxEU
  example: the March 2017 SEC rejection of a bitcoin ETF was followed by a fall of
  about 16% within five minutes [S].
- **SEC hack, 2024-01-09** [22]: described in the summary [S]. It is a rare case where
  the "news" was false, so any move is pure reaction to the post, not to the
  underlying event [I].

## 3. What is measured, and at what horizon

| Outcome | Used in | Notes for Binance [I] |
|---|---|---|
| Cumulative abnormal return, CAR (signed) | most studies | Needs a sign: tone or hawkish/dovish coding. Unsigned average cancels (Ante's BTC result) |
| Absolute abnormal return, abnormal realized volatility | Volfefe (yields, implied vol), Gjerstad (VIX), Abdi | Sign-free; the natural primary outcome for a ranking. Normalize by the same minute-of-week from control days (intraday periodicity, ref 27) |
| Abnormal volume | Ante, Ge et al., Born et al. | Most reliable reacting variable in crypto; log volume relative to matched controls |
| Order-flow imbalance | not used in this literature | Binance klines carry taker-buy volume, so (2 x taker buy - total)/total per minute is free; this repo already has OFI tools at tick level |
| Liquidity (spread, depth) | rare | bookTicker for a short list of top events only (size) |
| Horizons | 1 to 5 min (Ante, Volfefe), 30 min (Bianchi), 5 to 180 min (JPM FX), days (theses) | Use 1, 5, 15, 60 min; pre windows of -60 to -1 min |

## 4. The identification problem and the standard answers

Posts react to news, and the market reacts to the same news. Tools, in rough order of
value:

1. **Pre-trend check.** Measure the same outcomes in [-60, -1] minutes. If |return|
   and volume are already elevated before the post, the post is likely a reaction
   (Abdi et al.'s main point, ref 6). Report pre and post side by side in an
   event-time plot [I].
2. **Matched control windows.** For each post, controls at the same minute of the
   week in the surrounding weeks (for example 8 weeks either side, excluding weeks
   with that person's other posts). This removes intraday and weekly seasonality,
   which is strong in crypto volume and volatility (Andersen and Bollerslev 1997 for
   the general phenomenon, ref 27) [I].
3. **Placebo events.** Shift every post by a random offset (keeping its minute of
   week), recompute the statistic, repeat 1,000 or more times: the share of placebo
   statistics above the real one is a permutation p-value. Placebo times should be
   drawn by the same rules as controls [I].
4. **Content-based contrast.** Within one person, crypto or tariff posts against
   "other" posts from the same hours. The non-market posts serve as a control for
   "this person posts when markets are busy" [I]. Gjerstad and Abdi both find that
   topic is what separates movers from non-movers [S, ref 5, 6].
5. **Exclude posts during known news.** Drop posts within +/- 30 min of FOMC
   statements, CPI and NFP releases, US equity open and close, and major exchange or
   ETF news; or keep them and flag them. Report both [I].
6. **Market factor.** When CME equity futures trade, regress crypto minute returns on
   ES returns and use the residual. Data note: the repo has no equity data, so this
   is an extension, not the core. Within crypto, a BTC beta adjustment for altcoins
   is easy (abnormal = alt return minus beta times BTC return), but for a
   market-wide post BTC itself is treated, so the BTC-adjusted outcome only measures
   the coin-specific part [I].
7. **Truly exogenous cases as validation.** The false SEC post [22] and posts whose
   content is new by construction (an announcement only the poster can make, such as
   reserve inclusion or tariffs) are the strongest evidence [I].
8. **Second-level timing.** Bianchi et al. use second precision for identification
   [S, ref 7]. With 1-minute bars, the event minute is contaminated if the post comes
   late in the minute; the first full minute after the post is the cleanest "post"
   bar [I].

## 5. A fair influence ranking

Problem: Trump has posted tens of thousands of times; a senator may have 20 crypto
posts. A raw average puts the noisiest small samples at the top and bottom.

- **Two estimands, report both** [I]:
  - per-post effect: the average abnormal outcome per post (influence per message);
  - total effect: per-post effect times number of posts (or the sum of abnormal |return|
    minutes), which answers "who moved the market the most overall". Trump will
    dominate the total almost mechanically.
- **Empirical-Bayes shrinkage.** For person j with estimate b_j and standard error s_j,
  fit a prior across people (normal: mean m, variance tau^2 by method of moments) and
  report the posterior mean m + tau^2/(tau^2 + s_j^2) x (b_j - m). People with few
  posts are pulled toward the mean. This corrects the winner's curse in the top of a
  league table (Efron 2011, ref 28). Gu and Koenker (Econometrica 2023) give
  nonparametric EB ranking and selection rules [S, ref 29].
- **Rank uncertainty.** Report confidence sets for ranks (Mogstad, Romano, Shaikh,
  Wilhelm, NBER w26883) rather than a single ordering [S, ref 30]. In practice a simple
  version is enough: bootstrap posts within person, re-rank, report the 5th to 95th
  percentile of each person's rank [I].
- **Multiple testing.** With dozens of people x 4 topics x 4 horizons x 4 outcomes,
  fix one primary outcome and horizon in advance (for example abnormal log realized
  volatility, minutes 1 to 5), and control the false discovery rate with
  Benjamini-Hochberg across people for the rest [I].
- **Text classification.** Classify topics (crypto, tariffs/trade, Fed/rates, other)
  with keyword rules first, then an LLM as a second coder; hand-label 200 random posts
  to measure both against; use the LLM only where it agrees with the hand labels at
  an agreed level. Freeze labels before looking at any prices [I]. JP Morgan's
  keyword approach [1] and Abdi's ML classification [6] are the precedents [S].
- **Compare within topic.** "Who moves crypto most with crypto posts" is a fairer
  question than pooling all posts, because Trump's average is diluted by thousands of
  non-market posts [I].

## 6. Recommended design for this repo (sized for a few weeks)

**Week 1: events.**
- Sources: trumpstruth.org (includes deleted posts; timestamps in America/New_York) and
  a Truth Social ID-based dataset [S, ref 31, 32]; the Trump Twitter Archive for 2020 to
  Jan 2021; X archives for other accounts. Convert everything to UTC and keep
  second-level precision. Cross-check 50 posts against two sources; record the
  disagreement rate [I].
- People: Trump; family (Don Jr., Eric, Barron if any, Melania for the memecoin);
  about 10 Republicans and 10 Democrats active on crypto; regulators (SEC chairs and
  commissioners, CFTC, Treasury, Fed chair). Choose the list from a rule (for example
  every member of the banking and agriculture committees plus agency heads), not from
  famous moments, to avoid look-ahead [I].
- Code topics (section 5) and tone; freeze `events.parquet` with a hash before
  touching prices.

**Week 2: market data and outcomes.**
- Binance USDT-M 1-minute klines (data.binance.vision) for BTC, ETH, SOL, XRP, DOGE,
  plus coins named in posts (TRUMP from its listing date). Klines give returns,
  volume, trade count and taker-buy volume (order-flow imbalance) per minute. This is
  far smaller than aggTrades and fits the repo's download-and-delete pattern [I].
- Per event e and contract c, minutes k = -60 to +60, outcomes: log return, |return|,
  log volume, OFI. Abnormal outcome = value minus the median of 16 matched control
  windows (same minute of week, weeks -8 to +8, excluding windows within 2 hours of
  any listed post) [I].

**Week 3: estimation, reusing `e3_event_study.py` / `e5_stacked_events.py` [I].**
- Stacked panel: rows are (event, contract, minute k). Main regression:
  y = event-by-contract FE + minute-of-window FE + sum over horizon bins of b_h x
  1[k in bin] x post_dummy, or more simply the DiD between treated window and its
  matched control windows (treated = real window, controls = placebo windows,
  "post" = k >= 1). The existing `twfe`, `did`, `_cr1` and `demean2` do this
  directly with unit = event-contract-window and time = k.
- Clustering: by event (posts of one day overlap, so cluster by calendar day as a
  robustness check).
- Inference: replace the contract-reassignment permutation with **time-shift
  permutation**: keep the event set and reassign which window counts as "real" among
  the matched windows (an exact randomization test under the null that the post time
  is exchangeable with its controls). This is structurally the same as
  `stratified_permutation` in `e5_stacked_events.py` with stratum = event [I].
- Pre-trend: `pre_trend_permutation` on k = -60 to -1, plus a direct test that mean
  abnormal |return| in [-15, -1] is zero.

**Week 4: ranking and robustness.**
- Per person x topic: b_j, s_j from the stacked model with person interactions;
  EB shrinkage; bootstrap rank intervals; BH-adjusted p-values.
- Robustness: drop 2025-10-10 to 2025-10-11; drop weekends; drop posts near
  scheduled macro releases; first post only within a 2-hour cluster; BTC-beta-adjusted
  altcoin outcomes; split 2020 to 2024 versus 2025 to 2026.
- Validation cases: the SEC hack post and the 2025-03-02 reserve posts should show up
  clearly; if they do not, the pipeline is wrong (the repo's "a surprising number is a
  bug" rule).

Primary outcome fixed in advance [I]: abnormal log realized volatility of BTCUSDT over
minutes +1 to +5 (sum of squared 1-minute returns relative to matched controls), per
crypto-topic post. Everything else is secondary.

## 7. Pitfalls checklist

- [ ] **Timezones.** trumpstruth.org reports America/New_York [S, ref 31]; others use
      UTC or the scraper's local time. DST shifts move times by an hour twice a year.
      Verify on known events (the 2025-03-02 reserve post, the 2024-01-09 SEC post).
- [ ] **Timestamp precision.** Minute-rounded archives put the post in the wrong bar
      about half the time when effects last 2 to 3 minutes (Ante). Prefer
      second-level times or IDs that encode time.
- [ ] **Edits, deletions, reposts.** Deleted posts are missing from live scrapes but
      present in some archives (trumpstruth.org keeps them [S]). Reposts ("ReTruths")
      and quote posts need their own flag; keep originals as the main sample.
- [ ] **Cross-posting.** A post often appears on Truth Social, then X, then press. The
      first appearance is the event time.
- [ ] **Illiquid hours.** Weekends and Asian night hours have thin books; percentage
      moves are larger for the same information. Controls at the same minute of week
      handle this for the abnormal measure, but report weekend and weekday separately.
- [ ] **Overlapping events.** Trump posts many times a day (Roll Call reported more
      than 24 a day on average in 2024 [S, ref 33]). Merge posts within 30 minutes
      into one cluster or keep only the first; never let windows overlap within a
      person without saying so.
- [ ] **The October 2025 cascade.** About $19 billion liquidated around 2025-10-10
      [S, ref 20]. One event can dominate a mean of |returns|. Report with and
      without it; use medians or winsorized means as a check.
- [ ] **Look-ahead in event choice.** Picking "famous" posts selects on the outcome.
      Use rule-based samples (every post by a fixed list of accounts); showcase cases
      are illustrations, not evidence.
- [ ] **Winner's curse in the ranking.** The top-ranked person's raw effect is biased
      upward; shrink (section 5).
- [ ] **Posts that react to markets.** Always show the pre-window. A post that
      comments on a drop ("the market is doing great!") will show abnormal volatility
      without causing it.
- [ ] **Contract history.** Symbols listed after an event (TRUMPUSDT from January
      2025) cannot be in earlier events; 1000-prefixed contracts (for example
      1000PEPE) have scaled prices. Use the repo's lifecycle tables.
- [ ] **Leverage and liquidations.** Futures moves can overshoot spot because of
      liquidation cascades; a large effect on futures may be partly mechanical. A spot
      cross-check on BTC is cheap.
- [ ] **Survivorship of accounts.** Accounts that were suspended (Trump on Twitter from
      January 2021) create gaps; do not read a gap as "no effect".

## 8. References

1. Fortune, "JPMorgan builds index to measure Trump tweets' market impact" (2019-09-09). https://fortune.com/2019/09/09/jpmorgan-trump-tweet-market-impact-index/ [S]
2. Al Jazeera, "From 'covfefe' to 'Volfefe': New index tracks Trump volatility" (2019-09-09). https://www.aljazeera.com/economy/2019/9/9/from-covfefe-to-volfefe-new-index-tracks-trump-volatility [S]
3. Invezz, "Are President Trump's posts moving markets? Study shows not a lot" (2025-02-17), reporting J.P. Morgan research. https://invezz.com/news/2025/02/17/are-president-trumps-posts-moving-markets-study-shows-not-a-lot/ [S]
4. Bitcoin.com News, "JPMorgan: Trump's market influence diminishes but tariff tweets still rattle markets". https://news.bitcoin.com/jpmorgan-trumps-market-influence-diminishes-but-tariff-tweets-still-rattle-markets [S]
5. Gjerstad, P., Meyn, P. F., Molnar, P., Naess, T. D. (2021). "Do President Trump's tweets affect financial markets?" Decision Support Systems 147, 113577. https://uis.brage.unit.no/uis-xmlui/handle/11250/2980725 [S]
6. Abdi, F., Kormanyos, E., Pelizzon, L., Getmansky Sherman, M., Simon, Z. (2021). "A modern take on market efficiency: the impact of Trump's tweets on financial markets." SAFE Working Paper 314, SSRN 3840203. https://safe-frankfurt.de/publications/working-papers/details/publicationname/a-modern-take-on-market-efficiency-the-impact-of-trumps-tweets-on-financial-markets.html [S]
7. Bianchi, F., Gomez-Cram, R., Kind, T., Kung, H. (2023). "Threats to central bank independence: high-frequency identification with Twitter." Journal of Monetary Economics; NBER WP 26308. https://www.nber.org/system/files/working_papers/w26308/w26308.pdf [S]
8. Ge, Q., Kurov, A., Wolfe, M. H. (2019). "Do investors care about presidential company-specific tweets?" Journal of Financial Research 42(2), 213-242. https://econpapers.repec.org/RePEc:bla:jfnres:v:42:y:2019:i:2:p:213-242 [S]
9. Born, J. A., Myers, D. H., Clark, W. J. (2017). "Trump tweets and the efficient market hypothesis." Algorithmic Finance 6(3-4), 103-109. https://journals.sagepub.com/doi/10.3233/AF-170211 [S]
10. Ante, L. (2023). "How Elon Musk's Twitter activity moves cryptocurrency markets." Technological Forecasting and Social Change 186. https://ideas.repec.org/a/eee/tefoso/v186y2023ipas0040162522006333.html [S]
11. Blockchain Research Lab, "The Musk Effect" (2021-02-08) and "The Musk Effect: new research" (2022-01-13). https://www.blockchainresearchlab.org/2021/02/08/the-musk-effect-how-elon-musks-tweets-affect-the-cryptocurrency-market/ and https://www.blockchainresearchlab.org/2022/01/13/the-musk-effect-new-research-on-the-impact-of-elon-musks-twitter-activity-on-cryptocurrency-markets/ [S]
12. Huynh, T. L. D. "When Elon Musk changes his tone, does bitcoin adjust its tune?" Computational Economics. https://link.springer.com/article/10.1007/s10614-021-10230-6 [S]
13. Lund University student paper (2025), Trump posts sentiment and Bitcoin daily returns. https://lup.lub.lu.se/student-papers/record/9220074 [S]
14. National Chengchi University thesis, Truth Social posts and Bitcoin. https://thesis.lib.nccu.edu.tw/thesis/detail/ea105ef0b7e1d63fbdfebb63f4950617 [S]
15. Block Media, "Trump's crypto support yields significant Bitcoin gains, study finds" (reporting Krause, SSRN). https://www.blockmedia.co.kr/research-english/906186 [S]
16. Perdichizzi, S., Galati, L. "From zero to hero: Memecoins' spillover effects in cryptocurrency markets." Listed at https://www.economia.unipd.it/en/author-1 [S]
17. The Block, "Rapid insights: TRUMP and MELANIA memecoins impact onchain." https://www.theblock.co/research/blockchains/rapid-insights-trump-and-melania-memecoins-impact-onchain-335781 [S]
18. Fortune, crypto reserve post and prices (2025-03-02). https://fortune.com/crypto/2025/03/02/trump-bitcoin-crypto-reserve-xrp-sol-ada-btc-eth-prices/ ; Bloomberg Law, "Crypto prices sink on Trump reserve skepticism". https://news.bloomberglaw.com/crypto/trump-crypto-rally-fizzles-amid-skepticism-on-his-reserve-plan [S]
19. CoinMarketCap Academy, "WLFI token drops 12% in trading debut." https://coinmarketcap.com/academy/article/wlfi-token-drops-12percent-in-trading-debut-after-exchange-listing [S]
20. PYMNTS, "Tariff threat triggers record $19 billion in crypto liquidations." https://www.pymnts.com/cryptocurrency/2025/tariffs-trigger-record-19-billion-in-crypto-liquidations/ ; Axios (2025-10-14). https://www.axios.com/2025/10/14/trump-tariffs-china-crypto [S]
21. Auer, R., Claessens, S. (2018). "Regulating cryptocurrencies: assessing market reactions." BIS Quarterly Review, September, 51-65. https://www.bis.org/publ/qtrpdf/r_qt1809f.htm ; VoxEU column https://cepr.org/voxeu/columns/regulating-cryptocurrencies-assessing-market-reactions [S]
22. SiliconANGLE, "SEC's X account hacked: fake bitcoin ETF approval leads to market turbulence" (2024-01-09). https://siliconangle.com/2024/01/09/sec-x-account-hacked-fake-bitcoin-etf-approval-leads-market-turbulence/ [S]
23. "Measuring Trump: The Volfefe Index and its impact on European financial markets." Finance Research Letters 38 (2021) 101447, doi 10.1016/j.frl.2020.101447. https://fis.tu-dresden.de/portal/en/publications/measuring-trump(6c717170-8096-4740-b09b-6059db51da34).html (author list not confirmed this session) [S]
24. Brans, H., Scholtens, B. (2020). "Under his thumb: the effect of President Donald Trump's Twitter messages on the US stock market." PLOS ONE. https://pubmed.ncbi.nlm.nih.gov/32160241/ [S]
25. Kheireddine, Adeyemi, University of Kent, cryptocurrency impacts of tweeting. https://media.www.kent.ac.uk/se/29936/KheireddineAdeyemiCryptocurrancyimpactsofTweeting.pdf [S]
26. Ben Jabeur et al. (2025), political signals and cryptocurrency returns. https://ideas.repec.org/p/hal/journl/hal-05451354.html [S]
27. Andersen, T. G., Bollerslev, T. (1997). "Intraday periodicity and volatility persistence in financial markets." Journal of Empirical Finance 4(2-3), 115-158. https://scholars.duke.edu/publication/761297 [S]
28. Efron, B. (2011). "Tweedie's formula and selection bias." JASA 106, 1602-1614. https://academicnewsletter.sufe.edu.cn/info/445115 [S]
29. Gu, J., Koenker, R. (2023). "Invidious comparisons: ranking and selection as compound decisions." Econometrica 91(1), 1-41. https://arxiv.org/abs/2012.12550 [S]
30. Mogstad, M., Romano, J. P., Shaikh, A., Wilhelm, D. "Inference for ranks with applications to mobility across neighborhoods and academic achievement across countries." NBER WP 26883. https://www.nber.org/system/files/working_papers/w26883/w26883.pdf [S]
31. Trump's Truth archive, about page. https://trumpstruth.org/about [S]
32. Gerard, P., Botzer, N., Weninger, T. (2023). "Truth Social Dataset." ICWSM. https://ojs.aaai.org/index.php/ICWSM/article/view/22211 [S]
33. Roll Call, "Trump averages more than 24 Truth Social posts a day" (2024-10-02). https://rollcall.com/2024/10/02/trump-averages-more-than-24-truth-social-posts-a-day-and-he-was-even-busier-during-the-vp-debate/ [S]

Standard method not looked up this session: Benjamini, Y., Hochberg, Y. (1995),
"Controlling the false discovery rate", JRSS B 57(1), 289-300 [I: from background
knowledge, citation not re-checked].
