# Background research for the RPI retail-identification project

Compiled 2026-11-22, before any analysis of the retail flag.

## How to read the status labels

- **[V]** Verified: a primary source was opened, or a live API response was observed from this
  repository's environment on 2026-11-22.
- **[S]** Search snippet only: the text came from a search index entry for the official page. The
  page itself could not be opened (developers.binance.com, arxiv.org, SSRN, journal sites and
  several others are outside this session's allowed network hosts). Wording may be approximate.
  Every [S] item must be checked by hand at its URL before it is quoted in a paper.
- **[U]** Unverified, or an inference of ours that no source states.

Nothing in the pre-registration depends on a [U] item without saying so.

---

## 1. Binance RPI rules

Sources: Binance FAQ "What Is an RPI Order?" (published 2025-11-17, updated 2026-01-05),
https://www.binance.com/en/support/faq/detail/92c83c53173947c4a44f9a7277c3b9ce and the launch
announcement "Binance Futures Launches Retail Price Improvement (RPI) Orders" (2025-11-18),
https://www.binance.com/en/support/announcement/detail/d0ed1c8add7848c8b3e5a87bbabf6300.

| # | Fact | Source text | Status |
|---|---|---|---|
| 1 | Launched on USD-M futures on 2025-11-20, on selected symbols. No symbol list is published. | "Binance Futures will introduce the Retail Price Improvement (RPI) Order feature on 2025-11-20." | [V] |
| 2 | Anyone can post RPI orders through the API. There is no approved market-maker programme. | "All users can place RPI orders." | [V] |
| 3 | RPI orders are post-only limit orders (time in force `RPI`). | "Post-Only: Passive maker order execution, never match with orders already on the book." | [V] |
| 4 | They match only orders from the app or website. | "Match exclusively with non-algorithmic orders, and don't match with any orders submitted via API." and "Orders submitted through website and App are non-algorithmic orders." | [V] |
| 5 | They are last in the queue at their price. | "RPI orders are filled only after all non-RPI orders at the same price level have been executed." | [V] |
| 6 | They cannot cross ordinary orders but can sit inside the spread that the API shows, and RPI bids and asks may cross each other. | "RPI orders cannot cross non-RPI orders on the other side." and "When there are only RPI orders on the other side, cross is allowed while they won't be matched against each other." | [V]; "can sit inside the spread" is our inference [U] |
| 7 | They are hidden from ordinary API book data and shown on the trading page. | "In order book data/stream in API, all RPI orders are excluded." | [V] |
| 8 | A separate book including RPI orders exists: `GET /fapi/v1/rpiDepth`. | Live call on 2026-11-22 returned a book whose best levels differ from `/fapi/v1/depth`; only `limit=1000` was accepted. Docs: "RPI orders are included and aggregated in the response message. Crossed price levels are hidden and invisible." | [V] for the endpoint, [S] for the doc text |
| 9 | Fees: a dedicated RPI commission is added to the maker fee. No rate is published. One worked example implies +0.005%, which cancels a -0.005% rebate. | "RPI orders are subject to a dedicated RPI commission rate." | [V] for structure, [U] for the rate |
| 10 | The app user's taker fee: the documents do not mention any change. | (silence) | [U] |
| 11 | `GET /fapi/v1/trades` carries `isRPITrade`. | Live response on 2026-11-22. | [V] |
| 12 | `GET /fapi/v1/historicalTrades` also carries `isRPITrade`. It needs an API key: without one it returns HTTP 401, code -2014. | FAQ response example; live 401 on 2026-11-22. | [V] flag per FAQ; [V] key needed |
| 13 | `historicalTrades` look-back: reportedly cut "from the last 3 months to the last 1 month" on 2026-03-19. Weight 20, at most 500 rows per call. | Changelog snippet. | [S] |
| 14 | `aggTrades` includes RPI fills without a flag, but returns `nq`, the quantity excluding RPI fills. So RPI quantity per aggregate is `q - nq`. | Live response on 2026-11-22 contained `nq`; FAQ: "RPI trades are aggregated, but no special tag". | [V] |
| 15 | The data.binance.vision archive has neither the flag nor `nq`. | Headers of the 2026-11-19 daily trades and aggTrades files. | [V] |
| 16 | RPI is enabled per symbol through `permissionSets` in `exchangeInfo`. All 15 recorded contracts had it on 2026-11-22 (373 symbols in total). | Live `exchangeInfo`. | [V] |

### What the documents do not settle

1. **Stop, take-profit, TWAP and liquidation orders.** The FAQ says "RPI orders are not available
   to algo or strategy orders, including conditional, stop orders etc." It is unclear whether an
   app user's triggered stop order can take RPI liquidity. If it cannot, such orders are retail
   but can never be flagged. Liquidations are not mentioned. [U]
2. **Whether one app order produces several flagged rows.** No document defines a trade row.
   Binance describes aggregate trades as fills from the same taker order at the same price and
   time, which implies one row per resting order matched. Combined with fact 5, one app order
   that clears a price level should print unflagged rows first and flagged rows after them, all
   with the same timestamp and side. This is inference [U]. It is deliberately **not** checked
   against data here, because doing so means looking at flagged rows before the plan is locked.
   It is the first pre-registered descriptive step (M1 in the pre-registration).
3. **Whether trade ids of RPI fills share the ordinary sequence.** The pilot recording has no
   missing ids on any contract while containing both flag values, so yes in practice. [V] for
   the pilot window only.

### Why these rules matter for the study (our reading)

Facts 5 and 6 mean an app order is flagged in only two situations:

- **Front of book.** An RPI order sits at a better price than every ordinary order, inside the
  visible spread. Any app order arriving then hits it first, whatever its size.
- **Level cleared.** The RPI order shares a price with ordinary orders. An app order reaches it
  only after it has consumed all ordinary size at that price, so only larger orders are flagged.

The second route makes flags more likely for large orders for a purely mechanical reason. The
exploratory observation that flagged trades looked larger than typical trades (see the
disclosure in the pre-registration) could therefore be produced by the matching rule alone. The
design has to separate these two routes.

A second consequence: when RPI liquidity is known to be at the front of the book, an app order
on that side must be flagged, so an unflagged trade at that moment is very likely an API order.
That would give confirmed negatives as well as positives, but it requires recording both books.

### Backfilling gaps with historicalTrades

Feasible in principle: the endpoint returns the flag and accepts `fromId`, and a key costs
nothing. Limits: the look-back is reportedly one month [S], each call returns at most 500 rows at
weight 20 (about 60,000 trades a minute within the 2,400 weight budget), and the key must be
stored as a GitHub Actions secret. It can repair gaps of minutes to hours. It cannot recover the
year since launch. Not yet tested with a real key. [U]

### Other venues (context only)

Bybit reportedly marks RPI fills in its public trade feed (`isRPITrade` on REST, `RPI` on the
websocket) since February 2025; OKX has an RPI programme without a public fill marker. [S]. No
Binance Spot RPI exists in the spot API documentation. [V]

---

## 2. Retail identification: prior work

### 2.1 The equities template

- **Boehmer, E., Jones, C. M., Zhang, X. and Zhang, X. (2021).** Tracking retail investor
  activity. *Journal of Finance* 76(5), 2249-2305. https://doi.org/10.1111/jofi.13033. Off-exchange
  prints with subpenny price improvement are classed as retail. [S]
- **Barber, B. M., Huang, X., Jorion, P., Odean, T. and Schwarz, C. (2024).** A (sub)penny for your
  thoughts: tracking retail investor activity in TAQ. *Journal of Finance* 79(4), 2403-2427.
  https://doi.org/10.1111/jofi.13334. Abstract as returned by search: "We placed 85,000 retail
  trades in six retail brokerage accounts from December 2021 to June 2022 ... The algorithm
  identifies 35% of our trades as retail, incorrectly signs 28% of identified trades, and yields
  uninformative order imbalance measures for 30% of stocks." Signing at the quote midpoint cuts
  the signing error to 5%. The numbers in the project brief are confirmed. [S]
- **Battalio, R. H., Jennings, R. H., Saglam, M. and Wu, J. (2023).** Identifying market maker
  trades as "retail" from TAQ: no shortage of false negatives and false positives. Working paper,
  SSRN 4579159. With proprietary retail trades, under 28% are identified; institutional trades
  also print at subpenny prices. Note this 28% is an identification rate, not Barber et al.'s
  signing error. [S]
- **Barber, B. M., Odean, T. and Zhu, N. (2009).** Do retail trades move markets? *Review of
  Financial Studies* 22(1), 151-186. Small-trade imbalance checked against brokerage data: the
  historical precedent for validating a size proxy against ground truth. [S]
- **Lee, C. M. C. and Radhakrishna, B. (2000).** Inferring investor behavior: evidence from TORQ
  data. *Journal of Financial Markets* 3(2), 83-111. Dollar cut-off rules. [S]
- **O'Hara, M., Yao, C. and Ye, M. (2014).** What's not there: odd lots and market data. *Journal
  of Finance* 69(5), 2199-2236. Small trades are heavily used by high-frequency traders, so small
  does not mean retail once orders are split by algorithms. [S]

### 2.2 Round numbers, sweeps, order type

- **Kuo, W.-Y., Lin, T.-C. and Zhao, J. (2015).** Cognitive limitation and investment performance:
  evidence from limit order clustering. *Review of Financial Studies* 28(3), 838-875. Individuals
  cluster on round prices. [S]
- **Alexander, G. J. and Peterson, M. A. (2007).** An analysis of trade-size clustering and its
  relation to stealth trading. *Journal of Financial Economics* 84(2), 435-471. Round trade sizes
  are also used by informed institutions: evidence against "round means retail". [S]
- **Cong, L. W., Li, X., Tang, K. and Yang, Y. (2023).** Crypto wash trading. *Management Science*
  69(11), 6427-6454. Authentic trading shows round-size clustering; its absence signals
  fabricated volume. [S]
- **Aloosh, A. and Li, J. (2024).** Direct evidence of bitcoin wash trading. *Management Science*
  70(12), 8875-8921. Validates size-clustering statistics against leaked account data. [S]
- **Divakaruni, A. and Zimmerman, P. (2024).** Uncovering retail trading in bitcoin: the impact of
  COVID-19 stimulus checks. *Management Science* 70(4), 2066-2085. Buy trades of exactly $1,200:
  the best precedent for round dollar size as a retail fingerprint in crypto. [S]
- **Bartlett, R. P., McCrary, J. and O'Hara, M. (2024).** Tiny trades, big questions: fractional
  shares. *Journal of Financial Economics* 157, 103836. Dollar-based order entry by retail. [S]
- **"The Quarter-Hour Effect" (2026).** arXiv:2607.09426, authors not retrieved. Round-size share
  on Binance perpetuals falls at minute and hour boundaries, read as scheduled algorithms. No
  ground truth. Closest neighbour for our round-size and clock rules. [S, partial]
- **Chakravarty, S., Jain, P., Upson, J. and Wood, R. (2012).** Clean sweep: informed trading
  through intermarket sweep orders. *JFQA* 47(2), 415-435. Sweeps are mainly institutional. [S]
- **Kelley, E. K. and Tetlock, P. C. (2013).** How wise are crowds? *Journal of Finance* 68(3),
  1229-1265. Retail use both market and limit orders. [S]
- No verified paper establishes time of day as a retail marker. [gap]

### 2.3 Retail in crypto

- **Kogan, S., Makarov, I., Niessner, M. and Schoar, A. (2024).** Are cryptos different? *Journal of
  Financial Economics* 159, 103897. Account data from eToro; no proxy needed. [S]
- **Auer, R., Cornelli, G., Doerr, S., Frost, J. and Gambacorta, L. (2022).** BIS Working Paper 1049.
  Retail measured by exchange app downloads. [S]
- **Jia, R., Moallemi, C. C., Wang, S. and Zeng, X. (2026).** Who loses and why? Market
  microstructure of perpetual futures. AFT 2026. Hyperliquid wallets trading through the front
  end are treated as retail: the nearest analogue to Binance's app-or-website rule. [S]
- **Vendors.** Chainalysis defines retail as transfers under $10,000; CryptoQuant's "retail
  investor demand" uses transfers under $10,000; Glassnode uses wallet balances (under 1 BTC);
  Kaiko, K33 and The Block use venue-level average trade size with no fixed threshold;
  BGeometrics buckets Binance perpetual taker volume by size and calls the small bucket retail.
  [S]. The $10,000 convention is for on-chain transfers, not exchange trades.
- **No validation found.** Searches found no paper or vendor that tests any crypto retail rule
  against ground truth, and no paper that uses the Binance or Bybit RPI flag. This is absence
  from our searches only.

---

## 3. Positive-unlabelled learning

Notation: y = 1 if the taker is an app or website user, s = 1 if the order is flagged,
e(x) = P(s = 1 | y = 1, x) is the labelling propensity.

- **Elkan, C. and Noto, K. (2008).** Learning classifiers from only positive and unlabeled data.
  KDD, 213-220. If labels are selected completely at random (SCAR), P(s=1|x) = c P(y=1|x), so a
  classifier trained on the flag ranks trades correctly. [S]
- **Bekker, J. and Davis, J. (2020).** Learning from positive and unlabeled data: a survey.
  *Machine Learning* 109, 719-760. Defines SCAR, selected at random (SAR) and the propensity
  score; the class prior is not identifiable without further assumptions. [S]
- **Bekker, J., Robberechts, P. and Davis, J. (2019).** Beyond the selected completely at random
  assumption for learning from positive and unlabeled data. ECML PKDD, 71-85. Propensity-weighted
  risk and SAR-EM, assuming the propensity depends on a known subset of attributes. [S]
- **Kato, M., Teshima, T. and Honda, J. (2019).** Learning from positive and unlabeled data with a
  selection bias. ICLR. Ranking is recoverable if P(s=1|x) is ordered like P(y=1|x). [S]
- **Gerych, W. et al. (2022).** Recovering the propensity score from biased positive unlabeled
  data. AAAI 36(6), 6694-6702. The propensity is not identifiable under standard assumptions. [S]
- **Kiryo, R., Niu, G., du Plessis, M. C. and Sugiyama, M. (2017).** Positive-unlabeled learning
  with non-negative risk estimator. NeurIPS. Needs SCAR and a known class prior. [S]
- **Teisseyre, P., Furmańczyk, K. and Mielniczuk, J. (2024).** Verifying the selected completely
  at random assumption in positive-unlabeled learning. arXiv:2404.00145. A test of SCAR. [S]
- **Phillips, S. J. et al. (2009).** Sample selection bias and presence-only distribution models.
  *Ecological Applications* 19(1), 181-197. Under biased sampling, compare presences with
  background drawn under the same bias. Our analogue: compare within the same labelling
  opportunity. [S]
- **Ward, G. et al. (2009).** Presence-only data and the EM algorithm. *Biometrics* 65(2), 554-563;
  **Hastie, T. and Fithian, W. (2013).** Inference from presence-only data; the ongoing
  controversy. *Ecography* 36(8), 864-867. Prevalence is not identifiable from presence-only data
  without strong assumptions. [S]
- **Hsieh, Y.-G., Niu, G. and Sugiyama, M. (2019).** Classification from positive, unlabeled and
  biased negative data. ICML. Relevant if book data give us confirmed negatives. [S]
- **Evaluation.** Claesen, M. et al. (2015), arXiv:1504.06837; Jain, S., White, M. and Radivojac,
  P. (2017), AAAI 31(1); Ramola, R., Jain, S. and Radivojac, P. (2019), PSB 24, 124-135; Menon,
  A. K. et al. (2015), ICML. Metrics computed with unlabelled treated as negative understate
  true performance and can be corrected only with the class prior. [S]
- **Inference and splits.** Field, C. A. and Welsh, A. H. (2007), *JRSS-B* 69(3), 369-390 (cluster
  bootstrap); Cameron, A. C., Gelbach, J. B. and Miller, D. L. (2008), *REStat* 90(3), 414-427;
  López de Prado, M. (2018), *Advances in Financial Machine Learning*, ch. 7 (purging and
  embargo); Roberts, D. R. et al. (2017), *Ecography* 40(8), 913-929 (blocked validation). [S]

### What the flag can and cannot tell us (our derivation, elementary)

For any rule or model that selects a set of orders f:

| Quantity measured against the flag | Relation to the truth |
|---|---|
| Flagged share of selected orders, P(s=1 \| f) | Always a **lower bound** on the true retail share, provided flags are never wrong. |
| Lift, P(s=1 \| f) / P(s=1) | Equals true lift only if propensity is the same inside and outside f. Otherwise it mixes "more retail" with "more often labelled". |
| Share of flagged orders the rule catches, P(f \| s=1) | Equals true recall only under SCAR. Otherwise it is recall among retail orders that met RPI liquidity. |
| True retail share of all trades | Not identified. Only bounds and sensitivity ranges can be reported. |

No paper was found that gives sharp bounds under unrestricted SAR, and none applies PU learning
to trade classification.
