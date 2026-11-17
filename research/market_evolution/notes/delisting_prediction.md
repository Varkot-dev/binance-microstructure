# Delisting prediction: background notes for Part B

Written 2026-11-17 as background for Part B (README section "Can you tell a dying coin from its
trading?").

Tags: **[V]** verified at the source this session; **[S]** secondary (search snippet, news
rewrite or abstract seen only through a search engine); **[I]** my inference.

**Access caveat.** In this session, binance.com, developers.binance.com, arxiv.org, SSRN,
ScienceDirect, MDPI, RePEc/MPRA and the university repositories were all blocked by the network
proxy. The only sources I could open directly were `data.binance.vision` (the archive and its S3
listing) and `raw.githubusercontent.com` (the binance-public-data README). Everything on
Binance policy and on the academic papers below is therefore **[S]**. Before any of it goes
into the Q15/Q16 write-up, check the quoted wording against the original page. The archive
facts in section 6 are **[V]**: I computed them from the archive this session.

## Summary

- Binance's stated delisting criteria are qualitative and the same for every token: team
  commitment, development activity, trading volume and liquidity, network stability and
  security, responsiveness to due diligence, regulation, and evidence of fraud or negligence
  [S]. Futures notices name a smaller set (trading volume and liquidity, network safety,
  regulation, fraud), and some 2026 notices add "extreme volatility" and a lack of insurance
  fund support [S]. Binance publishes no numeric thresholds [S].
- A visible warning layer exists. The **Monitoring Tag** (since 2023-07-26) marks tokens "at
  risk" of no longer meeting the listing criteria. **Vote to Delist** (since March 2025) lets
  users vote on tagged tokens [S]. Being tagged does not mean a token will be delisted, and
  there is no fixed timeline [S].
- **Futures usually die before spot, not after.** I matched the 160 dead USDT-M symbols in
  the local aggTrades inventory to Binance spot USDT pairs [V]. Where the spot USDT pair was
  delisted too, the perpetual's last trading day came 2 to 13 days *before* the spot pair's
  last day in 79 of 100 cases, typically 6 to 8 days before. In 6 cases the two ended within
  a day of each other, and in 15 cases spot died first, with the perpetual following a median
  81 days later. A further 45 dead perpetuals had no Binance spot USDT pair at all, and 13
  were delisted while their spot pair is still trading. So a spot delisting is rarely a
  usable advance signal for the futures contract. It is mostly the same event.
- The literature agrees that **falling trading volume** is the core signal. It is the
  definition of death in Feder et al. / Gandal et al. (volume below 1% of its prior peak) and
  the best short-horizon predictor in Fantazzini's work (lagged volume plus online search
  interest) [S]. Other recurring predictors are price decline, volatility or daily range,
  small market cap, coin age and the cohort a coin was listed in [S].
- Price reaction to a delisting announcement is large and fast. News coverage reports drops
  of about 8% to 25% within hours for the April 2026 batch [S], and a secondary summary
  reports a median 24-hour drop of 26.3% across 101 Binance delistings [S, unconfirmed]. A
  model must therefore not see data from after the announcement.
- Label traps, covered in section 7: (1) the archive keeps publishing zero-volume "ghost"
  klines, and in some cases funding and metrics files, long after settlement; (2) the
  announcement comes several days before settlement, and post-announcement data leaks the
  label; (3) renames, mergers and symbol reuse (LUNA) are not deaths; (4) coins still alive
  at the end are censored, not negatives.

## 1. Binance's official criteria (spot and general)

All wording here comes from search snippets of Binance pages that I could not open [S].

- Delisting notices use a standard template. For example, "Binance Will Delist ALPHA, BSW,
  KMD, LEVER, LTO on 2025-07-04"
  (https://www.binance.com/en/support/articles/173b2a63c03141009029407ecfebd14a) says that
  when a coin or token no longer meets Binance's standards, or the industry changes, Binance
  conducts a more in-depth review and may delist it. The factors listed across notices are
  [S]:
  - "Commitment of team to project"
  - "Level and quality of development activity"
  - "Trading volume and liquidity"
  - "Stability and safety of network from attacks"
  - "Level of public communication"
  - "Responsiveness to periodic due diligence requests"
  - "Evidence of unethical/fraudulent conduct or negligence"
  - "New regulatory requirements"

  Cointelegraph's account of the April 2025 batch lists the same set
  (https://cointelegraph.com/news/binance-delists-14-tokens-vote-to-delist-process) [S].
- "Binance Delisting Guidelines & Frequently Asked Questions"
  (https://www.binance.com/au/support/faq/e5a9718ccb794acda1c48db5c71753e4) adds
  legal/compliance risk ("tokens under global/regional regulatory issues"). It also states
  that Binance "does not disclose any delisting decisions to external parties" before
  announcing them [S].
- "Important Notice on Binance Listing Information & Requirements"
  (https://www.binance.com/en/support/announcement/d378c2176ac841bb8eae68f63d4c4845) and a
  Binance blog guide on ongoing evaluation give categories for periodic review. They cover
  team and governance (abandoned development, weak updates, poor communication) and market
  health ("sustained low trading activity or repeated major price crashes without valid
  cause"), plus market-making balance, order book depth and price stability [S]. The
  "sustained low trading activity" and "repeated major price crashes" wording is the closest
  Binance comes to naming quantities a model can measure.

## 2. Monitoring Tag, Seed Tag, Vote to Delist

- **Introduction.** "Introducing Seed Tags & Monitoring Tags for Tokens with High Volatility
  and Risks" (https://www.binance.com/en/support/announcement/b0f241491d0e4d75aa2f8752b7bf8af5)
  launched both tags on 2023-07-26. The Seed Tag replaced the Innovation Zone, which dated
  from mid-2020. The first Monitoring Tag set included AKRO, AMB, CREAM, FTT and ARK [S].
  Before 2023-07-26 there was no tag history to use as a feature [I].
- **Monitoring Tag definition.** The Binance Academy glossary
  (https://www.binance.com/en/academy/glossary/monitoring-tag) describes tagged tokens as
  "subject to close observation by Binance and may face delisting if they fail to meet
  ongoing listing criteria". Binance "regularly conducts thorough reviews to determine
  whether a token should receive, maintain, or have its Monitoring Tag removed". The
  criteria include team commitment, fraud or negligence, regulatory compliance, unjustified
  supply changes, and ownership or core-team changes [S].
- **Seed Tag definition.** The glossary (https://www.binance.com/en/academy/glossary/seed-tag)
  describes Seed Tag tokens as usually "in their initial stages of development" that "may
  not yet have a working product or established user base". Users must pass a quiz every 90
  days to trade tagged tokens on Spot or Margin [S]. Seed Tag status measures how young a
  token is, not distress [I].
- **No fixed timeline.** No source gives a fixed time from tag to delisting, and the tag
  "does not automatically result in delisting" (BeInCrypto, Coinspeaker coverage) [S]. One
  well-reported case: Monero was tagged in early January 2024 and its delisting was announced
  about a month later (The Block,
  https://www.theblock.co/post/270282/binance-monitoring-tag-monero-zcash and
  https://www.theblock.co/post/276176/binance-delisting-monero) [S]. A "3 to 6 months from
  tag to delisting" figure circulates in an AI-generated Cryptorank summary. It is not
  supported anywhere and should not be used [S].
- **Vote to Delist.** The first campaign was launched on Binance Square on 2025-03-21, for
  Monitoring Tag tokens. It required a KYC'd account holding 0.01 BNB. Binance said the
  results "will not be the sole factor". The 14 tokens delisted on 2025-04-16 (BADGER, BAL,
  BETA, CREAM, CTXC, ELF, FIRO, HARD, NULS, PROS, SNT, TROY, UFT, VIDT) followed this round.
  A second round ran 2025-04-10 to 04-16 over 17 tokens, with FTT receiving the most votes
  (news.bitcoin.com, crypto.news, Cointelegraph) [S]. The archive agrees on the first batch:
  BADGERUSDT, BALUSDT, NULSUSDT, TROYUSDT and VIDTUSDT perpetuals last traded on 2025-04-14,
  two days before their spot pairs ended on 2025-04-16 [V].
- **Using the tag as a feature.** The tag status is public and dated, so in principle it is
  usable. It would have to be collected from announcements, because the data.binance.vision
  archive does not contain it [I].

## 3. Futures-specific criteria and mechanics

- One Binance notice (search snippet of a Binance Square repost,
  https://www.binance.com/square/post/379632888348519) says Binance Futures periodically
  reviews each futures contract based on a variety of factors. It lists "Trading volume and
  liquidity; Stability and safety of network from attacks; New regulatory requirements;
  Evidence of unethical/fraudulent conduct or negligence" [S]. I found no stated threshold
  on open interest.
- The January 2026 delisting of BID, DMC, ZRC and TANSSI was reported as citing "extreme
  volatility, reduced liquidity and lack of insurance-fund support", with final settlement
  on 2026-01-21 at 09:00 UTC (Whale Alert story,
  https://whale-alert.io/stories/8f7cb4659d85/) [S]. The archive confirms the dates: the
  last trading day was 2026-01-21 for these four symbols (in the dead list) [V for the date
  only].
- **Mechanics.** "Binance Futures will close all positions and conduct an automatic
  settlement" at a stated UTC time, and the contract is delisted after settlement. New
  positions are blocked shortly before; one notice blocked them 30 minutes before. The
  insurance fund is not used in the final hour, so auto-deleveraging may apply. Leverage and
  margin tiers are often cut before delisting. Sources: the XEM/ORBS/LOOM notice
  https://www.binance.com/en/support/articles/cfe97d52a8c840d3ba631835b637e9e7, the
  DEFIUSDT/MEMEFI notice
  https://www.binance.com/en-AE/support/announcement/detail/21e399dcea734230a3c181daf5407b64,
  and the REEFUSDT leverage-and-delist notice
  https://www.binance.com/en/support/announcement/detail/572715f2d96e47769ebbb967c2a6e445 [S].
  [I] A leverage or margin-tier cut announced in the weeks before a delisting is a possible
  leading indicator, if those announcements can be collected.
- **Regulatory and product delistings** are a separate class. Examples are the 2023 BUSD
  pair perpetuals (The Block,
  https://www.theblock.co/post/226425/binance-futures-delisting-stepn-near-avalanche-perps)
  and token migrations such as MATIC to POL (Binance swap notice
  https://www.binance.com/en/support/articles/6a6de383727f4659a3050f7982e1620f) [S]. These
  are not driven by the coin's own trading and should be labelled separately [I]. One
  discrepancy: secondary sources say the MATIC futures settled on 2024-09-09, but the archive
  shows MATICUSDT's last trading day as 2024-09-04 [V].

## 4. Sequence and lead times

- **Announcement to settlement.** Spot notices usually give about one to two weeks. For
  example, the ALPHA, BSW, KMD, LEVER and LTO notice was dated 2025-06-26 for a 2025-07-04
  delisting [S]. In combined notices, the futures settlement is set several days before the
  spot date. In the March 2026 batch (A2Z, FORTH, HOOK, IDEX, LRC, NTRN, RDNT, SXP), futures
  settled 2026-03-24 and spot ended 2026-04-01 (Cryptorank, CoinGape, BeInCrypto) [S]. The
  archive agrees that A2ZUSDT, FORTHUSDT, HOOKUSDT, LRCUSDT, NTRNUSDT and RDNTUSDT perpetuals
  last traded 2026-03-24, with spot ending 2026-04-01 [V]. Perpetual-only notices are often
  published only a few days before settlement [S]. A blog summary of a Yang and Kwon study
  claims about 3 days' average notice for spot delistings and "79% two days ahead". I could
  not trace these numbers to the paper and do not trust them [S].
- **Futures versus spot ordering.** I measured this from the archive [V]; the method and
  counts are in section 6. The usual case is one announcement covering both, with the
  futures settlement 6 to 8 days before the spot removal. The exceptions where spot died
  first are older, staggered cases with lags of 9 to 459 days (for example XEMUSDT: spot
  ended 2024-06-17, perpetual 2024-12-09; AERGOUSDT: 2025-03-28 vs 2026-06-30). In these
  cases the perpetual lived on after Binance spot had dropped the coin [V]. Those cases are
  the only ones where "spot already delisted" is a usable feature, and they are a minority
  [I].

## 5. Literature: death, survival and delisting prediction

| Study | Data and definition of death | Main findings | Tag |
|---|---|---|---|
| Feder, Gandal, Hamrick, Moore, Vasek, "The Rise and Fall of Cryptocurrencies" (WEIS 2018); published as Gandal, Hamrick, Moore, Vasek, "The rise and fall of cryptocurrency coins and tokens", *Decisions in Economics and Finance* 44(2), 2021 | About 1,082 coins, CoinMarketCap. A coin is "abandoned" when average daily volume in a month is at most 1% of its prior peak, and "resurrected" above 10% | 44% of publicly traded coins were abandoned at least once; 71% of those were later resurrected; about 18% failed permanently. Tokens were abandoned less often than coins | [S] |
| Grobys and Sapkota, "Predicting cryptocurrency defaults", *Applied Economics* 52(46):5060-5076, 2020, doi:10.1080/00036846.2020.1752903 | 146 proof-of-work coins listed before end-2014, followed to Dec 2018. About 60% defaulted | Linear discriminant analysis; press release claims 87% of defaults explained after one month of trading. I could not see the variable list | [S] |
| Fantazzini and Zimin, 2020, *J. Industrial and Business Economics* (multivariate market and credit risk for cryptocurrencies) | Probability of death through zero-price probability (ZPP) | Cited by later work as the first credit-risk models for coins, along with Grobys and Sapkota | [S] (citation details not opened) |
| Fantazzini, "Crypto-Coins and Credit Risk: Modelling and Forecasting Their Probability of Death", *JRFM* 15(7):304, 2022 | More than 2,000 coins, 2015 to 2020, several definitions of death | For new coins the cauchit model and ZPP (random walk or MS-GARCH) work best. For older coins, models with lagged trading volume and online searches work better. The choice of death definition was "not critical" | [S] |
| Fantazzini, "Assessing the Credit Risk of Crypto-Assets Using Daily Range Volatility Models", *Information* 14(5):254, 2023 | OHLC daily range combined with ZPP | Credit-scoring and machine-learning models with lagged volume and online searches are best up to 30 days ahead; daily-range time-series models are better up to one year ahead. The paper reports early warning on FTX | [S] |
| Gatabazi et al., "Cryptocurrencies and Tokens Lifetime Analysis from 2009 to 2021", *Economies* 10(3):60, 2022 | Cox proportional hazards and Aalen additive hazards models | Coins on their own standalone blockchain had higher hazard than tokens; the 2013 to 2017 release cohort had higher hazard than the 2009 to 2013 cohort | [S] |
| Ammann, Burdorf, Liebi, Stöckl, "Survivorship and Delisting Bias in Cryptocurrency Markets", working paper, 2022 (Univ. St. Gallen) | 3,904 coins, 2014 to 2021, CoinMarketCap including dead coins | Annualized survivorship bias of 0.93% (value-weighted) and 62.19% (equal-weighted); the size premium is overstated by about 50% in a survivor-only sample. Stöckl's `crypto2` R package retrieves delisted coins. The author list beyond Liebi and Stöckl was not confirmed in this session | [S] |
| Będowska-Sójka, Wójcik, Pele, "Early warning systems for cryptocurrency markets: Predicting 'zombie' assets using machine learning", 2025 (ScienceDirect, pii S1062940825001834) | "Zombie" = asset temporarily untradable, which can lead to permanent delisting; at least 210 days of history | Random forest best, about 84% out-of-time balanced accuracy for zombie status within 28 days. Features include volume, market cap, whether the coin has an X account, and whether it is mineable | [S] |
| Yang (and Kwon?), "Developing Predictive and Explainable Models for Cryptocurrency Delistings: A Case Study of Binance Exchange", *Asia-Pacific J. Financial Studies*, doi:10.1111/ajfs.70045 | Binance delistings; structured exchange data plus news and Reddit text | The abstract says research that models delisting directly is "extremely limited". A secondary summary says weaker liquidity, falling prices, higher volatility and negative project news predicted delisting. The year (2025 or 2026) and co-author are unconfirmed | [S] |
| Milunovich, "Cryptocurrency exchanges: Predicting which markets will remain active", *J. Forecasting*, 2022, doi:10.1002/for.2846 | 238 exchanges (exchange survival, not coin survival) | Random forest, 86.1% test accuracy; exchange lifetime and traded volume rank highly | [S] |
| Örget, 2022 (DergiPark), event study | Delisting, listing, airdrop and SEC announcements, window (-5, +10) | Delisting is treated as a negative event; many significant abnormal returns for negative events | [S] |
| Ante, "Market Reaction to Exchange Listings of Cryptocurrencies", BRL Working Paper, 2019 | Listings, not delistings | +5.7% abnormal return on listing day, +9.2% over (-3, +3). Useful as a template for a delisting event study | [S] |

**Price and volume around announcements [S].** News coverage of the March 2026 batch reports
drops of about 8% (SXP) to more than 25% (IDEX, LRC) within hours (BeInCrypto
https://beincrypto.com/binance-delists-eight-tokens-april-crash, CryptoPotato). Cointelegraph
reported a crash after the March 2025 five-token notice
(https://cointelegraph.com/news/binance-delist-five-tokens-triggers-price-crash). Volume can
spike after an announcement, as holders exit and speculators trade the move. XEMUSDT perpetual
daily quote volume was about $5M on 2024-11-01, $47M to $90M on 2024-11-29 and 11-30, and
$70M on 2024-12-05, before its 2024-12-09 settlement [V for the numbers; whether the spike is
from the announcement is I]. [I] A spike in the final month is therefore usually an effect of
the announcement, not an advance warning. Features must be cut at the announcement date, or
the model will learn "volume spike means death".

## 6. Archive facts checked this session [V]

Method: I took symbols in `data/universe/aggtrades_monthly_inventory.json` ending in USDT
whose last aggTrades month is before 2026-10 (160 symbols). For each, I found the last day
with `count > 0` in the futures monthly 1d klines, and the same for the Binance spot pair
with the same symbol (spot monthly 1d klines). The scratch script was not saved in the repo.

- Outcome of the 160 symbols:
  - 2 had no readable futures kline for the final month (AI16ZUSDT, KDAUSDT).
  - 45 had no spot USDT pair with the same symbol. These include futures-only listings,
    such as 1000-prefixed and many 2025 to 2026 listings.
  - 13 have a spot pair still trading in 2026-10. These are perpetual-only delistings,
    plus symbol-reuse cases.
  - 100 had a spot pair that ended:
    - In 79, the perpetual ended 2 to 13 days before the spot pair. The most common gaps
      were 8 days (21 cases) and 7 days (20 cases); a few gaps were hundreds of days.
    - In 6, the two ended within a day of each other.
    - In 15, spot ended first, and the perpetual followed a median of 81 days later
      (quartiles 16 and 157 days, range 9 to 459).
- **Ghost rows after death.**
  - Monthly futures 1d kline files keep being published after settlement. XEMUSDT has files
    through 2026-10, containing flat rows with OHLC 0.0338 and volume and count equal to 0
    from 2024-12-10 onward. Its last real trading day was 2024-12-09.
  - Monthly `fundingRate` files also continue. XEMUSDT 2025-06 has 56 rows at the default
    0.0001 rate.
  - Daily `metrics` files continue for months: XEMUSDT has them until 2025-03-10, MATICUSDT
    until 2025-01-22.
  - This is not consistent across symbols: MATICUSDT 1d klines stop at 2024-09. Death must
    therefore be defined as the last day with `count > 0`, never as "the last file exists".
    The aggTrades monthly inventory seems free of ghosts: XEMUSDT ends at 2024-12.
- **The `1mo` kline interval** stops at 2023-12 even for BTCUSDT, so it cannot be used for
  the panel. Monthly bars have to be built from `1d` monthly files.
- Columns, confirmed from downloaded files and the binance-public-data README:
  - klines: `open_time, open, high, low, close, volume, close_time, quote_volume, count,
    taker_buy_volume, taker_buy_quote_volume, ignore`.
  - fundingRate: `calc_time, funding_interval_hours, last_funding_rate`. The interval
    column matters because Binance moves some contracts from 8h to 4h funding [I].
  - metrics: 5-minute rows of `sum_open_interest, sum_open_interest_value,
    count_toptrader_long_short_ratio, sum_toptrader_long_short_ratio,
    count_long_short_ratio, sum_taker_long_short_vol_ratio`. History starts 2020-09-01 for
    BTCUSDT; for many symbols the archive starts around 2023-04.
  - UM monthly folders: aggTrades, bookTicker, fundingRate, indexPriceKlines, klines,
    markPriceKlines, premiumIndexKlines, trades. UM daily folders add bookDepth and metrics.
  - The README says new monthly files appear "at the first monday of the month".

## 7. Candidate features

All features are computed from data up to the month-end t, and ideally cut at the last
non-ghost day.

| candidate feature | rationale | data source | expected direction | reference |
|---|---|---|---|---|
| log quote volume, month t | "Trading volume and liquidity" is a stated criterion; volume is the core of every dead-coin definition | futures 1d klines (`quote_volume`), summed by month | lower volume, higher hazard | Binance notices [S]; Feder et al. 2018 [S] |
| volume relative to its own running peak (vol_t / max vol up to t) | Feder/Gandal "1% of prior peak" abandonment rule; this is the falling-volume baseline in the README | 1d klines | lower ratio, higher hazard | Feder et al. 2018; Gandal et al. 2021 [S] |
| 3-month volume change (log vol_t minus log vol_{t-3}) | Binance's "sustained low trading activity"; a decline in volume | 1d klines | more negative, higher hazard | Binance listing notice [S]; Fantazzini 2022 lagged volume [S] |
| volume rank in the cross-section (percentile among live USDT perps that month) | Binance judges coins relative to others; removes market-wide cycles | 1d klines | lower rank, higher hazard | [I] |
| number of trades (`count`) and average trade size | Liquidity and how many participants trade it; a cheap link to Q9-style trade-level features | 1d klines `count` | fewer trades, higher hazard; trade-size direction unclear | [I] |
| 3- and 6-month return, drawdown from running max | "Repeated major price crashes without valid cause"; price decline is a predictor in the literature | 1d klines close | larger drawdown, higher hazard | Binance notice [S]; Yang AJFS summary [S] |
| realized volatility / mean daily range (high-low)/close | Fantazzini's daily-range models; "extreme volatility" cited in 2026 futures notices | 1d klines | higher, higher hazard | Fantazzini 2023 [S]; Whale Alert 2026 [S] |
| price level / relative tick size | Very low-priced coins have coarse relative ticks and are often renamed with a 1000 prefix; links to Part A | 1d klines + exchangeInfo tick (Q4b/Q8) | unclear; probably higher hazard at sub-cent prices | [I] |
| open interest (mean, trend) and OI / volume | Liquidity and how much leverage traders hold. A stated futures concern (insurance fund support) relates to how deep the contract is | daily `metrics` (`sum_open_interest_value`), around 2023-04 onward for many symbols | lower or falling OI, higher hazard | [I]; Whale Alert 2026 [S] |
| funding rate mean, abs mean, share at the cap | Extreme or persistently capped funding signals an unbalanced, thin market. Mark the ghost rows | `fundingRate` monthly | higher abs funding, higher hazard | [I] |
| change in funding interval (8h to 4h or 1h) | Binance shortens funding intervals on volatile contracts; a risk-management action | `fundingRate.funding_interval_hours` | change, higher hazard | [I] |
| mark/index premium dispersion | Basis noise means the underlying spot is thin across exchanges | premiumIndexKlines | higher, higher hazard | [I] |
| age of the contract (months since first file) and listing cohort | Hazard varies with age and release cohort; new coins behave differently | inventory first month | early life and some cohorts have higher hazard | Gatabazi et al. 2022 [S]; Fantazzini 2022 [S] |
| has a Binance spot USDT pair; spot pair already gone | Futures-only listings die without a spot event; the "spot first" cases are a known risk group | spot 1d klines inventory | no spot pair or spot gone, higher hazard | section 6 [V for counts, I for direction] |
| Monitoring Tag status and months on tag (from 2023-07) | Binance's own public warning | announcements (manual or scraped) | tagged, higher hazard | Binance glossary [S] |
| leverage / margin-tier cut in the past month | Often accompanies or comes before delisting | announcements | cut, higher hazard | Binance REEFUSDT notice [S]; [I] |
| market-wide state (BTC 3-month return, count of delistings last quarter) | Binance delists in batches; review batches cluster in bear phases (news describes the 2026 batches as "crypto winter") | 1d klines BTC; own label history | bear phase, higher hazard | FXStreet 2026 [S]; [I] |
| trade-level predictability, burstiness, trade size (Q9/Q14) | The open question in the README: does anything add beyond volume? | aggTrades (processed coins only) | unknown | README |

## 8. Label design pitfalls

1. **Use settlement date or announcement date, not "last file".** Define the event day as
   the last day with `count > 0` [V: ghost rows exist]. Then decide whether the label
   horizon counts from the announcement or from the settlement.
   - The 3-month horizon is far longer than the typical 1 to 2 week gap between the two, so
     the label itself changes little.
   - The features are the problem. Data between the announcement and settlement contain the
     crash and volume spike caused by the announcement.
   - A coin announced on day 25 of month t and settled in month t+1 has month t's features
     contaminated. Cut each coin's features at the announcement date where it is known. If
     it is not known, drop the final month before settlement, or check sensitivity to doing
     so [I].
2. **Renames, migrations and mergers are not deaths.**
   - In the dead list: MATICUSDT (to POL) [S], RNDRUSDT, FTMUSDT, GALUSDT, LENDUSDT,
     BTTUSDT, TOMOUSDT, EOSUSDT, MKRUSDT [I: likely migrations, to confirm against Q14's
     classification]. Merged: AGIXUSDT and OCEANUSDT, KEEPUSDT and NUUSDT [I].
   - Q14 already separates 10 renames and 2 mergers in the June 2023 cohort. Either drop
     these from the event set, or model them as competing risks. They should not count as
     negatives or positives for "dies" [I].
3. **Symbol reuse.** LUNAUSDT futures ended 2022-05-12, but a spot LUNAUSDT exists in 2026,
   which is a different asset (LUNA 2.0) [V for dates, I for interpretation]. Join spot and
   futures by symbol only with a date check. A futures symbol can also come back under a
   new ticker after a gap (for example a RAY or DODO relaunch) [I: check].
4. **Censoring.** Coins alive at the end of data are censored, not negatives. For the last 3
   months before the data end, the 3-month label is not yet observable, so drop those
   month-ends from evaluation, or use a survival model. Kaplan-Meier and Cox handle this
   directly [I].
5. **Batch delistings are correlated.** Binance delists in batches, often after a review
   round (for example the 2025-04-16 batch of 14 tokens). Bootstrapping over individual coin
   events overstates precision. Resample months, as the README requires, or treat review
   rounds as clusters [I].
6. **Regime changes in the process.** Possible structure breaks [I]:
   - Monitoring Tag begins 2023-07-26.
   - Vote to Delist begins 2025-03.
   - Futures-only listings (no spot pair) grow a lot after 2024: 45 of 160 deaths had no spot
     USDT pair [V].
   - Settlement now comes days before spot removal.

   A model trained on 2021 to 2023 deaths, which were dominated by regulatory events (FTX,
   LUNA, BUSD) and staggered spot-first deaths, may not transfer to 2025 to 2026. The lock-box
   on 2026 is the right test [I].
7. **Different causes of death.** Index contracts (DEFIUSDT, FOOTBALLUSDT, BLUEBIRDUSDT) are
   dropped for product reasons, and regulatory or stablecoin events have nothing to do with
   the coin's own trading. Report results with these included and excluded [I].
8. **Archive coverage differs by feature.** Metrics history starts around 2023-04 for many
   symbols, and the `1mo` interval stops at 2023-12. If a feature is missing for earlier
   years, missingness becomes correlated with time and label. Add explicit missing
   indicators, or restrict the model that uses metrics to 2023-05 onward [V for coverage, I
   for consequence].
9. **Late publication.** Monthly files appear on the first Monday after the month [V,
   README]. This is not a look-ahead issue for a backtest, but a live month-end prediction
   would have to use daily files [I].

## 9. Can announcement dates be collected systematically?

- Binance publishes delisting notices in the "Delisting" category of its announcement
  center, and reposts them on Binance Square [S]. A public JSON endpoint behind the
  announcement list exists (widely used by scrapers) [I: not tested; binance.com was
  blocked]. Notice titles carry the settlement date in brackets, for example "(2025-12-05)",
  but the publication timestamp is what is needed for feature cut-offs [S, I].
- Practical fallbacks:
  - Use the settlement day from the archive [V], then assume the announcement came 7 to 14
    days earlier for the feature cut [I].
  - For the 2026 lock-box, collect the true announcement dates by hand from Binance's
    announcement pages. That is a few dozen notices.
  - Monitoring Tag additions and removals can be collected the same way, from 2023-07
    onward [I].
- Network note: to scrape announcements, `www.binance.com` must be allowed in this cloud
  environment's network settings. It is blocked now.

## References

Binance (all opened only through search snippets in this session) [S]:

- Introducing Seed Tags & Monitoring Tags (2023-07):
  https://www.binance.com/en/support/announcement/b0f241491d0e4d75aa2f8752b7bf8af5
- Monitoring Tag glossary: https://www.binance.com/en/academy/glossary/monitoring-tag
- Seed Tag glossary: https://www.binance.com/en/academy/glossary/seed-tag
- Delisting Guidelines & FAQ: https://www.binance.com/au/support/faq/e5a9718ccb794acda1c48db5c71753e4
- Listing Information & Requirements notice:
  https://www.binance.com/en/support/announcement/d378c2176ac841bb8eae68f63d4c4845
- Binance Will Delist ALPHA, BSW, KMD, LEVER, LTO on 2025-07-04:
  https://www.binance.com/en/support/articles/173b2a63c03141009029407ecfebd14a
- Futures delist XEMUSDT, ORBSUSDT, LOOMUSDT (2024-12-09):
  https://www.binance.com/en/support/articles/cfe97d52a8c840d3ba631835b637e9e7
- Futures delist multiple perpetuals (2025-12-05):
  https://www.binance.com/en/support/announcement/746056ce732d43dda12c1e5ae1b7a059
- Futures delist DEFIUSDT and MEMEFI (2025-08-11):
  https://www.binance.com/en-AE/support/announcement/detail/21e399dcea734230a3c181daf5407b64
- Futures delist and margin tier update REEFUSDT (2025-01-22):
  https://www.binance.com/en/support/announcement/detail/572715f2d96e47769ebbb967c2a6e445
- Futures review criteria repost: https://www.binance.com/square/post/379632888348519
- MATIC to POL swap: https://www.binance.com/en/support/articles/6a6de383727f4659a3050f7982e1620f

News (all [S]):

- Cointelegraph, 14 tokens and Vote to Delist:
  https://cointelegraph.com/news/binance-delists-14-tokens-vote-to-delist-process
- Cointelegraph, five-token crash:
  https://cointelegraph.com/news/binance-delist-five-tokens-triggers-price-crash
- news.bitcoin.com, Vote to Delist results:
  https://news.bitcoin.com/binance-unveils-first-vote-to-delist-results-14-crypto-tokens-set-for-full-shutdown
- crypto.news, second round:
  https://crypto.news/binance-adds-17-tokens-to-its-second-vote-to-delist-round-featuring-jasmy-ftt-voxel-and-gps/
- The Block, Monero tag: https://www.theblock.co/post/270282/binance-monitoring-tag-monero-zcash
- The Block, Monero delisting: https://www.theblock.co/post/276176/binance-delisting-monero
- The Block, BUSD perps: https://www.theblock.co/post/226425/binance-futures-delisting-stepn-near-avalanche-perps
- Whale Alert, BID/DMC/ZRC/TANSSI: https://whale-alert.io/stories/8f7cb4659d85/
- BeInCrypto, April 2026 batch: https://beincrypto.com/binance-delists-eight-tokens-april-crash
- Cryptorank, April 2026 batch:
  https://cryptorank.io/news/feed/a883d-binance-to-delist-8-tokens-on-april-1-including-rdnt-hook-and-lrc-affected
- Blockonomi summary of the Yang/Kwon figures (low confidence):
  https://blockonomi.com/what-happens-when-a-cryptocurrency-gets-delisted-from-an-exchange/

Academic (all [S], seen as abstracts or snippets):

- Gandal, Hamrick, Moore, Vasek (2021), Decisions in Economics and Finance 44(2):
  https://ideas.repec.org/a/spr/decfin/v44y2021i2d10.1007_s10203-021-00329-8.html. WEIS 2018
  version: https://www.readkong.com/page/the-rise-and-fall-of-cryptocurrencies-3894550
- Grobys and Sapkota (2020), Applied Economics 52(46):
  https://econpapers.repec.org/RePEc:taf:applec:v:52:y:2020:i:46:p:5060-5076. Open copy:
  https://osuva.uwasa.fi/handle/10024/11740
- Fantazzini (2022), JRFM 15(7):304: https://www.mdpi.com/1911-8074/15/7/304
- Fantazzini (2023), Information 14(5):254: https://mdpi.com/2078-2489/14/5/254/html
- Gatabazi et al. (2022), Economies 10(3):60: https://doi.org/10.3390/economies10030060
- Ammann et al. / Liebi and Stöckl (2022), working paper:
  https://alexandria.unisg.ch/handle/20.500.14171/108037. crypto2 data:
  https://sstoeckl.github.io/post/crypto_download
- Stablecoin survivorship and ZPP: https://arxiv.org/pdf/2201.01392 ;
  https://mpra.ub.uni-muenchen.de/122951/1
- Będowska-Sójka, Wójcik, Pele (2025), zombie assets:
  https://www.sciencedirect.com/science/article/pii/S1062940825001834
- Yang et al., AJFS, Binance delistings: https://onlinelibrary.wiley.com/doi/10.1111/ajfs.70045
- Milunovich (2022), J. Forecasting: https://onlinelibrary.wiley.com/doi/10.1002/for.2846
- Örget (2022), event study: https://dergipark.org.tr/en/download/article-file/2032416
- Ante (2019), listings event study:
  https://www.blockchainresearchlab.org/wp-content/uploads/2020/02/BRL-Working-Paper-5.pdf

Data (verified [V]):

- Binance public data README: https://github.com/binance/binance-public-data
- Archive: https://data.binance.vision/ (S3 listing at
  https://s3-ap-northeast-1.amazonaws.com/data.binance.vision)
