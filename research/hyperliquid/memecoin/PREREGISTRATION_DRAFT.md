# Project 2 pre-registration (DRAFT, NOT LOCKED): HIP-1 spot token launch census

> **Status: DRAFT. Not locked, not hashed.** No survival, collapse, return or "who received
> value" statistic may be computed until this file has been reviewed, renamed to
> `PREREGISTRATION.md`, and its sha256 recorded. The analysis script (`survival.py`, not yet
> written) will refuse to run when the file's hash differs from the recorded one, in the same
> way `research/politics/c4_prepost_trading.py` checks `PREREGISTRATION_PREPOST.md`. Anything
> reported that is not specified here will be labelled **exploratory**.

Drafted 2026-11-20. Framing: detection and measurement only. The goal is to describe how
often Hyperliquid spot tokens collapse, which facts visible at launch go with collapse, and
who ends up holding value, so that buyers can avoid being exit liquidity. Nothing here is,
or may be turned into, guidance on deploying, pumping or rugging a token.

## 0. Disclosure of prior exposure to outcomes

Honest pre-registration requires saying what has already been seen.

- `research/hyperliquid/README.md` (written 2026-11-19) already reports two descriptive
  outcome numbers computed during desk research: of 280 ordinary HIP-1 tokens with 60+ days
  of history, the median trades at about 3% of its peak close and about two thirds are below
  10% of peak; and of 40 tokens deployed December 2024 to February 2025, 39 trade below 10%
  of peak. Those numbers informed the choice of a 10% threshold below. They are a reason to
  keep the threshold fixed now and to report the sensitivity labels in section 3.4 next to
  the primary one, not after. Consequences fixed here: (i) every collapse rate estimated on
  tokens listed before the lock is labelled "threshold informed by prior look" and is not
  called confirmatory; (ii) labels L2 to L5 are co-reported in the headline table with the
  primary label; (iii) a confirmatory check (section 5.4) uses only tokens whose first bar
  with volume falls after the lock date.
- The census crawl (`census.py`, report in `CRAWL_REPORT.md`) has downloaded the daily
  candles to disk. No price, drawdown, volume level or survival quantity has been computed
  from them. The only things computed are coverage counts (number of bars, first and last
  bar with volume above zero).
- `spotMeta` names, `fullName` and `deployerTradingFeeShare` fields were read to draft the
  exclusion list (Appendix A). These are not outcomes.

## 1. Question

On Hyperliquid's HIP-1 spot market, (a) what fraction of tokens collapse and how fast, by
launch cohort; (b) do facts measurable at launch (deploy gas in USD, genesis supply
concentration, deployer trading-fee share, seeded liquidity, deployer history) predict the
hazard of collapse; and (c) who received the value that was created and lost: the deployer,
genesis holders, the Hyperliquidity reserve, or later buyers.

Prior work answers versions of (a) and (b) on other chains (Uniswap: Xia et al. 2021,
Mazorra, Adan and Daza 2022, Cernera et al. 2023; Solana: Hu et al. 2026, Li et al. 2026;
multi-chain memecoins: Mongardini and Mei 2025; cryptocurrency "death" in general: Feder et
al. 2018, Gandal et al. 2021, Gatabazi et al. 2022, Fantazzini 2022). We found no survival
analysis of HyperCore spot tokens (only descriptive dashboards; see
`research/hyperliquid/LITERATURE.md` section 7). What is new here is the venue, and that
HyperCore exposes deployer identity, deploy gas and the full genesis allocation natively in
`tokenDetails`, so launch-time covariates do not have to be reverse-engineered from
contracts.

## 2. Data (all free; see `CRAWL_REPORT.md`)

One crawl, identified by its `crawl_id`, stored under
`data/hyperliquid/memecoin/raw/<crawl_id>/` with a sha256 manifest:

- `spotMeta.json.gz`: tokens and pairs.
- `tokenDetails/<index>_<tokenId>.json.gz`: launch facts per token; per-attempt HTTP status
  in `status_tokenDetails.jsonl`.
- `spotMetaAndAssetCtxs.json.gz`: current supply, prices, 24h notional.
- `candles_1d/<pair>.json.gz`: daily candles per pair, `startTime` 0 to the crawl's fixed
  `end_ms`.

Before locking, one re-crawl pass of failed `tokenDetails` will be run at least 24 hours
after the first pass (same `crawl_id`, cache keeps successes). Failures after that pass are
final and are part of the reported selection set (section 6).

For part (c) only, per-wallet data for deployer and genesis addresses (`userFillsByTime`,
`userNonFundingLedgerUpdates`) will be crawled after locking, with the completeness flag of
`research/hyperliquid/DATA.md` section 5 (earliest retrievable fill, left-censored or not).

## 3. Event definitions

### 3.1 Unit and universe

Unit: one HIP-1 token listed in the crawl's `spotMeta.tokens`, analysed through its
**reference pair**: the spot pair whose quote token is USDC (token index 0). If a token has
more than one USDC pair, the lowest pair index is used. Tokens with no USDC pair are
excluded and counted.

Exclusions (each counted in the flow table, section 6):

1. Stablecoins, fiat-pegged tokens and wrapped fiat (Appendix A, class S).
2. Bridged or wrapped external assets, including Unit (`U...`), HyBridge (`...0`) and
   tokenised stocks (`...X`, "xStock") (Appendix A, class B).
3. Staked, liquid-staking or vault receipt tokens whose price is tied to HYPE or HLP
   (Appendix A, class R).
4. HYPE itself (native gas and staking token; not a launch in the sense studied here).
5. Tokens whose reference pair has no daily bar with volume above zero (no `t0`).

Tokens with 1 or 2 traded days are **not** excluded, because excluding them would select on
the outcome (they include the fastest collapses). They stay in the Kaplan-Meier sample under
the peak rule of section 3.3 and are also reported as a separate row, "fewer than 3 traded
days", in the Kaplan-Meier and flow tables.

Reason: the question is about launches whose value depends on demand for the token itself.
Pegged and bridged assets collapse only if a peg or bridge fails, which is a different
event. The exclusion list is built from `spotMeta` fields only (name, `fullName`), never
from prices; ambiguous cases are listed as "review" in Appendix A and resolved before
locking with the rule "exclude only when the token's own `fullName` or its project's
documentation states that it is a claim on, or pegged to, an external asset".

### 3.2 Launch time (time origin)

`t0` = UTC date of the first daily bar with `v > 0` on the reference pair. Pre-listing bars
are back-filled with `v = 0` by the API (`DATA.md` section 4), so they are skipped.

`deployTime` from `tokenDetails` is used for the covariates and for a sensitivity cohort
(section 4), but not as the time origin or for the primary cohort, because (i) it is missing for every token whose
`tokenDetails` failed and for early tokens, and (ii) the survival clock is about trading,
which starts when the pair trades. Using a time origin available for all tokens keeps the
Kaplan-Meier analysis free of the `tokenDetails` selection (section 6), and for the same
reason the primary cohort is assigned from `t0` for every token. The gap `t0 - deployTime`
is reported descriptively.

The Kaplan-Meier estimator requires a well-defined origin and independent censoring (Kaplan
and Meier 1958; section pointers not given because the text was not read). Measuring token lifetime in calendar time from listing follows the
general approach of Gatabazi et al. (2022), who fit Kaplan-Meier, Cox and Aalen models to
coin lifetimes; that they use the first observed trading date as origin is unverified (only
the abstract and a search summary of the method were read).

### 3.3 Collapse label (primary)

Daily close `c_d`, daily base volume `v_d`, daily notional proxy `n_d = v_d * c_d` in USDC.
(Before locking, the units of `v` are checked by comparing `v * c` on the last complete
day with `dayNtlVlm` from `spotMetaAndAssetCtxs` for a handful of pairs; this is a units
check, not an outcome. If `v` turns out to be quote notional, `n_d = v_d`.)

Running peak, skipping the opening wicks: `P(d) = max(c_s : t0 + 3 <= s <= d)` over dates
with a bar, defined for `d >= t0 + 3` (days counted as UTC dates, `t0` is day 0, so days 0,
1, 2 do not set the peak). If a token has no bar on any date `s` with `t0 + 3 <= s <= d`,
`P(d)` is the maximum close over days 0 to 2. On a date without a bar, `c_d` is the last
close carried forward.

**Collapse date** = the first date `d >= t0 + 29` such that both

- (price) `c_d <= 0.10 * P(d)`, and
- (inactivity) the mean of `n_s` over the 30 dates `d-29 ... d` is below **1,000 USDC**,
  with days without a bar counted as `n_s = 0`.

**Dark rule.** If none of the 30 dates `d-29 ... d` has a bar with volume above zero, the
price condition is treated as met, so a token that stops trading altogether (including one
with only 1 or 2 traded days) collapses at the first such `d >= t0 + 29` rather than being
censored at a carried-forward price. This rule is a project choice; the number of collapses
that rely on it is reported.

This is a first-passage definition that uses only data up to `d`, so the label at `d` does
not depend on the future. The 10% threshold, the 1,000 USDC floor and the 30-day window are
this project's choices. In spirit the label combines a sharp price drop with inactivity, the
two ingredients that the abstract of Mazorra, Adan and Daza (2022) names for its scam label
(their exact thresholds are not known to us and are not attributed to them), with the
peak-relative logic of Feder et al. (2018), who, as described second-hand by Fantazzini
(2022), call a coin abandoned when its average daily volume in a month is at most 1% of its
volume at a price-defined peak. The 72-hour peak delay is ours (README Project 2): it removes the opening
auction wick, which on HIP-1 can be set by a handful of trades.

**Censoring.** Tokens not collapsed by the last complete UTC date before the crawl's
`end_ms` are right-censored at that date. A token whose reference pair stops producing bars
is not censored at that point: missing days count as zero notional, so it can collapse.

**Known blind spot.** With daily bars and a 30-day inactivity window, the earliest possible
collapse is day 29. Cernera et al. (2023) identify a large class of 1-day rug pulls on
Ethereum and BNB Smart Chain (token lifetime under one day, a single liquidity provider
removes all liquidity); no share of all rug pulls is quoted here, because the full text was
not read. Fast rugs will appear here as early collapses at day 29 or later, never as day-1
events. Intraday timing is only
available for launches captured by the websocket recorder going forward (Project 5).

### 3.4 Sensitivity labels (reported next to the primary, not instead of it)

- L2 price only: first `d >= t0 + 3` with `c_d <= 0.10 * P(d)`.
- L3 deep drop: as primary with 0.01 instead of 0.10.
- L4 short window: as primary with a 7-day inactivity window (earliest collapse day 9).
- L5 volume-relative, an adaptation of Feder et al. (2018): first `d >= t0 + 29` such that
  the mean notional over `d-29 ... d` is at most 1% of the maximum 30-day mean notional
  observed on any 30-day window ending in `[t0+29, d]`. It differs from their rule, which (as
  described by Fantazzini 2022; second-hand) compares a month's average daily volume with the
  coin's volume on a peak day defined by price, not with a maximum 30-day mean.
- L6 permanence, an adaptation: among primary collapses, the share whose close later exceeds
  `0.25 * P(d)`. Feder et al. (2018) define "resurrection" by volume recovering to at least
  10% of peak (second-hand, through Fantazzini 2022), and Gandal et al. (2021) also report
  resurrections; L6 uses price instead. Descriptive only, because it looks into the future.

## 4. Covariates measured at launch

All from `tokenDetails` unless stated. Tokens whose `tokenDetails` failed have none of
these and enter only the Kaplan-Meier analysis and the selection diagnostics.

| Covariate | Definition | Paper behind it |
|---|---|---|
| `gas_usd` | `deployGas` in USD at deploy date: USDC until 2025-05-22, HYPE afterwards, converted with the HYPE/USDC (`@107`) daily close on the `deployTime` date. Model uses `log(1 + gas_usd)`. `deployGas = 0` (early tokens) kept as 0 with an indicator. | None found for HIP-1. Treated as a costly signal of commitment; direction left two-sided. |
| `genesis_hhi` | Herfindahl-Hirschman index of genesis allocations among identified addresses (`genesis.userBalances`), excluding the Hyperliquidity reserve `0xffff...ffff`, normalised to their sum. Each anchor-token allocation (`existingTokenBalances`, distributed pro rata to holders of another token) is treated as one block; a sensitivity treats it as fully dispersed. | Mazorra, Adan and Daza (2022), HHI of token distribution among holders as a main feature [abstract]. Sun et al. (2024) list token-distribution problems among their 34 rug-pull root causes [abstract]. |
| `top1_share`, `deployer_share` | Largest identified genesis allocation, and the deployer address's own allocation, as a share of `maxSupply`. | Same as above. |
| `hl_share` | Hyperliquidity reserve allocation as a share of `maxSupply` (supply placed on the protocol-run order book). | HIP-1 and HIP-2 specifications (official docs, seen via search only; unverified). |
| `seeded_usdc` | `seededUsdc`; model uses `log(1 + seeded_usdc)`. | Mazorra, Adan and Daza (2022) use pool liquidity state as a feature; seeded USDC is the HIP-2 analogue. |
| `fee_share` | `deployerTradingFeeShare` from `spotMeta`, as a binary `fee_share = 1.0`. **Measured at the crawl, after the outcome**, so it may be partly caused by the outcome. It is **not** in the primary Cox model or the IPW model; it enters only a sensitivity model labelled "post-outcome covariate". Before 2025-01-27 non-USDC fees were burned (community docs; unverified), so it is also confounded with cohort. | HIP-1 specification (deployer fee share defaults to 100%; unverified). |
| `prior_deploys` | A **lower bound**: number of tokens in the crawl with a known `deployer` equal to this token's and an earlier `deployTime`, counting excluded classes (stablecoins, bridged assets, receipts) too; coded 0, 1, 2 or more. Deployers of failed `tokenDetails` and of missing indices are unknown, so the count is undercounted in a way that varies by index band. Sensitivity: the Cox model restricted to index bands of 100 indices with less than 20% `tokenDetails` failure. Deployer entity linking (funding-address clustering) is deferred. | Cernera et al. (2023): a small set of serial deployers ("token spammers", about 1% of addresses creating more than 20% of tokens, per a search summary of the paper) [abstract]. |
| `cohort` | Launch cohort from `t0` for every token (primary, used in Kaplan-Meier and as the Cox stratum). Sensitivity: cohort from `deployTime` when present, as an alternative Cox stratum; the number of tokens whose cohort differs between the two rules is reported. Boundaries: A before 2024-12-01; B 2024-12-01 to 2025-02-28 (post-airdrop gas mania); C 2025-03-01 to 2025-05-21; D 2025-05-22 (gas paid in HYPE) to 2025-12-31; E 2026-01-01 onward. | Cohort boundaries are set by HIP-1 rule changes, not by outcomes. |

No covariate in a primary model uses information after `t0`; `fee_share` is used only in
its labelled sensitivity model.

## 5. Analysis

### 5.1 Kaplan-Meier by cohort (all eligible tokens)

Product-limit estimator of the survival function `S(t)` of time from `t0` to collapse
(Kaplan and Meier 1958; section pointers unverified, record only). Pointwise 95% intervals
use Greenwood's variance formula (Greenwood 1926) with the interval built on the log-log
(complementary log-log) scale (Kalbfleisch and Prentice 1980). Report `S(30)`,
`S(90)`, `S(180)`, `S(365)` and the median time to collapse per cohort, with the number at
risk. Equality of cohort curves: log-rank test (Mantel 1966), one test, 5 groups.

### 5.2 Cox proportional hazards model (tokens with `tokenDetails`)

`h(t | x) = h0_cohort(t) exp(x' beta)` stratified by cohort, partial likelihood of Cox
(1972; section and equation pointers not given because the text was not read) with Efron's (1977)
approximation for tied daily event times (many tokens share collapse dates at daily
resolution). Covariates: `log(1 + gas_usd)`, gas-zero indicator, `genesis_hhi`,
`hl_share`, `log(1 + seeded_usdc)`, `prior_deploys` (dummies). `fee_share` is not in the
primary model (section 4). Robust sandwich standard errors (Lin and Wei 1989) clustered by
deployer address, because tokens from one deployer are not independent (cluster-robust
variance for correlated failure times: Wei, Lin and Weissfeld 1989; Lee, Wei and Amato 1992).

Primary hypotheses: Wald tests, two-sided, Holm-adjusted across the three at family-wise 5%.
H1 and H2 are supported only by a significant coefficient of the stated sign; a significant
coefficient of the opposite sign is reported as "contrary", and anything else as "not
supported".

- H1: higher `genesis_hhi` raises the collapse hazard.
- H2: `prior_deploys >= 1` raises the collapse hazard.
- H3: `log(1 + gas_usd)` is associated with the hazard (no sign predicted).

Other coefficients are reported with 95% intervals and called secondary. Proportional
hazards are checked with scaled Schoenfeld residuals and the Grambsch and Therneau (1994)
global and per-covariate tests (section pointer unverified); a violated covariate is reported with a
time interaction (`x * log t`) as a sensitivity, not by dropping it. Harrell's concordance
is reported as a descriptive fit measure only (Harrell, Califf, Pryor, Lee and Rosati 1982). No
prediction claims: the classifier version is Project 5.

Implementation: `lifelines` (Davidson-Pilon 2019) `KaplanMeierFitter`, `CoxPHFitter` with
`strata`, `cluster_col` and Efron ties, or an equivalent numpy implementation tested against
it.

### 5.3 "Who received value" (descriptive accounting, no test)

For each eligible token with `tokenDetails`, in USDC:

1. **Paid at launch:** `gas_usd` (paid to the protocol).
2. **Genesis allocation** to the deployer, to the top 10 identified genesis addresses, to
   anchor-token holders (as blocks), and to the Hyperliquidity reserve, as shares of
   `maxSupply`.
3. **Realised trading proceeds** of the deployer and the top 10 genesis addresses on the
   reference pair: sum of USDC received on sells minus USDC paid on buys from
   `userFillsByTime`, plus token transfers out from `userNonFundingLedgerUpdates`
   (`spotTransfer`, counted in tokens, not valued). Each wallet carries a completeness flag;
   totals are reported separately for complete and left-censored wallets.
4. **Deployer fee income (estimate):** `sum_d n_d * f * fee_share` with `f` the lowest and
   highest spot fee rate in Hyperliquid's schedule as a range, from 2025-01-27 only.
   Labelled an estimate because per-trade fees of counterparties are not public.
5. **Later buyers:** not identifiable for past launches from free data (no historical trade
   tape with addresses). Reported as a stated gap; for launches captured by the recorder
   (`src/microstructure/hyperliquid/recorder.py`, websocket trades carry `users`) the same
   accounting is done for the first 7 days of buyers.

Mongardini and Mei (2025) count victim addresses
and realised losses for memecoin manipulation; our accounting counts the other side (what
insiders realised). The SBFC 2025 pump.fun study (unverified; LITERATURE.md section 7) found
creators over-represented among high-PnL wallets, which is the comparison point.

### 5.4 Confirmatory check on tokens listed after the lock

Because the threshold was informed by a prior look (section 0), the same frozen primary label
and the same Kaplan-Meier code are applied to tokens whose first bar with volume falls after
the lock date. Data come from `candleSnapshot` daily bars (and from the websocket recorder,
`src/microstructure/hyperliquid/recorder.py`, where available). The check reports `S(30)` and
`S(90)` with Greenwood intervals once every token of the first post-lock 90-day listing window
has reached day 90, and compares them with the historical estimates. Exclusions and the
reference-pair rule are as in section 3.1.

## 6. Data-availability selection and how it is reported

Three layers of missing data, each reported as a result, not a footnote:

1. **Missing token indices.** `spotMeta` lists token indices up to a maximum with many
   integers absent (`CRAWL_REPORT.md`). What they are (failed or abandoned deploys, removed
   tokens) is not documented. They cannot be analysed; we report the count and state that
   the census is "tokens that reached `spotMeta`", which is the survivorship problem of
   Brown, Goetzmann, Ibbotson and Ross (1992, sections 1 and 2): a sample truncated on
   survival can make outcomes look better or more predictable than they are. If any index
   appears without a USDC pair, it is counted separately. The same holds for pairs: in crawl
   `20261120T002608Z`, 820 of token indices 0 to 1338 and 839 of pair indices 0 to 1192 are
   absent from `spotMeta`, yet `spotMetaAndAssetCtxs` returns contexts for all 1,193 pair
   indices. Before locking, the rule for these unlisted pairs is fixed from metadata only
   (for example, whether their contexts carry any supply), and they are reported as a
   separate row of the flow table; their prices are not looked at.
2. **`tokenDetails` failures** (HTTP 500 after retries, or JSON `null`). Reported as a table
   by cohort and index band. Diagnostics: (a) compare failed and successful tokens on
   fields available without `tokenDetails` (`t0`, cohort, pair index, and, descriptively,
`fee_share`); (b)
   Kaplan-Meier curves for the two groups side by side, which tells the reader whether the
   Cox sample (complete cases) differs in outcomes from the whole universe.
3. **Complete-case Cox and its correction.** The primary Cox model is complete-case.
   Sensitivity: inverse probability weighting with weights `1 / P(tokenDetails ok | cohort,
   t0)` from a logistic model (`fee_share` is left out because it is measured after the
   outcome), following Seaman and White (2013, sections 2 and 3
   on how complete-case bias arises and how IPW removes it under missingness at random given
   the weighting variables). The assumption is untestable and is stated as such.

A flow table (spotMeta tokens -> excluded by class -> no USDC pair -> no traded day -> KM
sample, with "fewer than 3 traded days" shown as a row inside it -> `tokenDetails` ok -> Cox
sample) opens the results.

## 7. What would change the plan before locking

Allowed before locking: fixing errors in the units check of `v`, resolving "review" rows of
Appendix A by the stated rule, verifying the papers marked unverified, and adding a
competing-risk analysis (Fine and Gray 1999) only if a competing terminal event, such as a
pair removed from `spotMeta`, is actually observed in the crawl metadata. Not allowed: any
change motivated by looking at prices, drawdowns or survival curves.

## 8. References

Verification level, honestly stated: on 2026-11-20 the research machine could not open
arxiv.org, usenix.org, mdpi.com, eprint.iacr.org or the official Hyperliquid docs directly
(DNS blocked). Every entry below marked **[abstract]** was located through a web search
index that returned the bibliographic record and the abstract (or a faithful summary of
it); the method sections were **not** read in full. Section and equation pointers for
those entries come from the abstract, the standard structure of the paper, or the
secondary description named. They must be checked against the full text before locking.
Entries marked **unverified** could not be located with enough detail to confirm.

A second attempt on 2026-11-20 (Project 2 session) also failed for arxiv.org, usenix.net,
mdpi.com, repository.up.ac.za, api.crossref.org and api.semanticscholar.org (proxy refusal),
so no full text was read. A third pass on 2026-11-20 (verification) again found arxiv.org,
papers.ssrn.com, usenix.org and doi.org unreachable, but a web search index returned the
arXiv listing records of Hu et al. (2026) and the USENIX Security '26 program page of
Mongardini and Mei; what was learned is stated in each entry. Web search confirmed two
details used above: Cernera et al.
(2023) define a 1-day token by a lifetime (creation to last transfer) under one day, and a
1-day rug pull as a pool pairing such a token whose single liquidity provider withdraws all
liquidity; Gatabazi et al. (2022) use the Cox proportional hazards and Aalen additive models
with Kaplan-Meier curves. The Mazorra, Adan and Daza (2022) label thresholds remain
unverified.

- Brown, S. J., Goetzmann, W. N., Ibbotson, R. G. and Ross, S. A. (1992). "Survivorship bias
  in performance studies." *Review of Financial Studies* 5(4), 553-580.
  https://doi.org/10.1093/rfs/5.4.553 ;
  https://ideas.repec.org/a/oup/rfinst/v5y1992i4p553-80.html (standard DOI for this article;
  doi.org could not be reached this session, so confirm it resolves before locking).
  [abstract]
- Cernera, F., La Morgia, M., Mei, A. and Sassi, F. (2023). "Token spammers, rug pulls, and
  sniper bots: An analysis of the ecosystem of tokens in Ethereum and in the Binance Smart
  Chain (BNB)." *32nd USENIX Security Symposium*, 3349-3366.
  https://www.usenix.org/conference/usenixsecurity23/presentation/cernera ; arXiv
  2206.08202. [abstract and slides summary: 1-day tokens, 1-day rug pull definition as a
  pool whose single liquidity provider removes all liquidity, token spammers]
- Cox, D. R. (1972). "Regression models and life-tables." *Journal of the Royal Statistical
  Society, Series B* 34(2), 187-220. https://doi.org/10.1111/j.2517-6161.1972.tb00899.x ;
  https://www.jstor.org/stable/2985181 [abstract]
- Davidson-Pilon, C. (2019). "lifelines: survival analysis in Python." *Journal of Open
  Source Software* 4(40), 1317. https://doi.org/10.21105/joss.01317 [abstract]
- Efron, B. (1977). "The efficiency of Cox's likelihood function for censored data."
  *Journal of the American Statistical Association* 72(359), 557-565.
  https://doi.org/10.1080/01621459.1977.10480613 [record only; tie approximation attributed
  by later literature]
- Fantazzini, D. (2022). "Crypto-coins and credit risk: Modelling and forecasting their
  probability of death." *Journal of Risk and Financial Management* 15(7), 304.
  https://doi.org/10.3390/jrfm15070304 [abstract and summary of its review of dead-coin
  definitions, including Feder et al. 2018]
- Feder, A., Gandal, N., Hamrick, J. T., Moore, T. and Vasek, M. (2018). "The rise and fall of
  cryptocurrencies." *Workshop on the Economics of Information Security (WEIS 2018)*.
  https://par.nsf.gov/biblio/10066236-rise-fall-cryptocurrencies [abstract; abandonment rule
  (candidate peak, month average volume at most 1% of peak volume) taken from Fantazzini
  2022's description]
- Fine, J. P. and Gray, R. J. (1999). "A proportional hazards model for the subdistribution
  of a competing risk." *Journal of the American Statistical Association* 94(446), 496-509.
  https://doi.org/10.1080/01621459.1999.10474144 [record only; contingent use]
- Gandal, N., Hamrick, J. T., Moore, T. and Vasek, M. (2021). "The rise and fall of
  cryptocurrency coins and tokens." *Decisions in Economics and Finance* 44, 981-1014.
  https://doi.org/10.1007/s10203-021-00329-8 [abstract]
- Gatabazi, P., Kabera, G., Mba, J. C., Pindza, E. and Melesse, S. F. (2022).
  "Cryptocurrencies and tokens lifetime analysis from 2009 to 2021." *Economies* 10(3), 60.
  https://doi.org/10.3390/economies10030060 [abstract: Cox and Aalen models of coin death]
- Grambsch, P. M. and Therneau, T. M. (1994). "Proportional hazards tests and diagnostics
  based on weighted residuals." *Biometrika* 81(3), 515-526.
  https://doi.org/10.1093/biomet/81.3.515 [record only]
- Hu, S., Tekin, S. F., Xu, Y. and Liu, L. (2026). "MemeTrans: A dataset for detecting
  high-risk memecoin launches on Solana." arXiv 2602.13480 (v1, 13 February 2026; v2 of
  21 May 2026 is retitled "MELT: A behavioral trace dataset for high-risk memecoin launch
  detection"). https://arxiv.org/abs/2602.13480 [abstract via search index: authors Sihao Hu,
  Selim Furkan Tekin, Yichang Xu and Ling Liu; 41,470 memecoins that completed their
  launchpad sale and migrated to a DEX; 122 features in five groups. The arXiv page itself
  could not be opened.]
- Kaplan, E. L. and Meier, P. (1958). "Nonparametric estimation from incomplete
  observations." *Journal of the American Statistical Association* 53(282), 457-481.
  https://doi.org/10.1080/01621459.1958.10501452 [record only]
- Li, J., Kuznetsov, P., Yanovich, Y., Nott-Whaley, K. and Vodolazov, I. (2026). "Catching
  the rug: Early prediction of fraudulent memecoins on Solana via machine learning." arXiv
  2608.20271 (20 August 2026). https://arxiv.org/abs/2608.20271 **[unverified]**: title and
  identifier seen in search results; the author list comes from a secondary summary site
  only, and the arXiv record could not be opened. Cited only as background in section 1; no
  detail of its method is used.
- Kalbfleisch, J. D. and Prentice, R. L. (1980). *The Statistical Analysis of Failure Time
  Data.* New York: Wiley. [record only; log-log transformed interval for the Kaplan-Meier
  estimate]
- Lee, E. W., Wei, L. J. and Amato, D. A. (1992). "Cox-type regression analysis for large
  numbers of small groups of correlated failure time observations." In Klein, J. P. and
  Goel, P. K. (eds.), *Survival Analysis: State of the Art*, 237-247. Dordrecht: Kluwer.
  [record only, from knowledge; page range to be checked]
- Lin, D. Y. and Wei, L. J. (1989). "The robust inference for the Cox proportional hazards
  model." *Journal of the American Statistical Association* 84(408), 1074-1078.
  https://doi.org/10.1080/01621459.1989.10478874 [record only; DOI not confirmed at
  publisher]
- Mazorra, B., Adan, V. and Daza, V. (2022). "Do not rug on me: Leveraging machine learning
  techniques for automated scam detection." *Mathematics* 10(6), 949.
  https://doi.org/10.3390/math10060949 ; arXiv 2201.07220. [abstract: 27,588 Uniswap
  tokens, 26,957 labelled scams versus 631 non-malicious, HHI and transaction-graph
  features, malicious label = sharp drop in liquidity or price plus inactivity and no
  recovery]. Note: `LITERATURE.md` describes the label as "inactive over a month plus
  liquidity removed or price down 90%"; those exact thresholds could not be confirmed and
  are treated as unverified. The extreme class imbalance (631 negatives) is one more reason
  to read their 0.99 accuracy with caution.
- Mongardini, A. M. and Mei, A. (2025). "A midsummer meme's dream: Investigating market
  manipulations in the meme coin ecosystem." arXiv preprint 2507.01963.
  https://arxiv.org/abs/2507.01963 [abstract: 34,988 tokens on 4 chains, wash trading and
  liquidity-pool price inflation precede pump-and-dumps, 17,000+ victim addresses]. A
  presentation page in the USENIX Security '26 program was seen through a search index; the
  published proceedings and page range were not checked, so the venue is not cited.
- Seaman, S. R. and White, I. R. (2013). "Review of inverse probability weighting for dealing
  with missing data." *Statistical Methods in Medical Research* 22(3), 278-295.
  https://doi.org/10.1177/0962280210395740 [abstract]
- Sun, D., Ma, W., Nie, L. and Liu, Y. (2024). "SoK: Comprehensive analysis of rug pull
  causes, datasets, and detection tools in DeFi." arXiv 2403.16082.
  https://arxiv.org/abs/2403.16082 [abstract: 34 root causes, 14 tools evaluated]
- Wei, L. J., Lin, D. Y. and Weissfeld, L. (1989). "Regression analysis of multivariate
  incomplete failure time data by modeling marginal distributions." *Journal of the American
  Statistical Association* 84(408), 1065-1073. https://doi.org/10.1080/01621459.1989.10478873
  [record only, from knowledge; DOI not confirmed at publisher]
- Xia, P., Wang, H., Gao, B., Su, W., Yu, Z., Luo, X., Zhang, C., Xiao, X. and Xu, G.
  (2021). "Trade or trick? Detecting and characterizing scam tokens on Uniswap
  decentralized exchange." *Proceedings of the ACM on Measurement and Analysis of Computing
  Systems* 5(3), article 39 (SIGMETRICS 2022). https://doi.org/10.1145/3491051 ; arXiv
  2109.00229. [record; used as background for the scale of scam listings, not for a method
  choice]
- Cited for standard formulas only (bibliographic details from knowledge and the verifier,
  not checked at the publisher this session): Greenwood, M. (1926), "The natural duration of
  cancer", *Reports on Public Health and Medical Subjects* 33, 1-26; Mantel, N. (1966),
  "Evaluation of survival data and two new rank order statistics arising in its
  consideration", *Cancer Chemotherapy Reports* 50(3), 163-170; Harrell, F. E., Califf, R. M.,
  Pryor, D. B., Lee, K. L. and Rosati, R. A. (1982), "Evaluating the yield of medical tests",
  *JAMA* 247(18), 2543-2546. HIP-1 and HIP-2 official
  specifications: https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-1-native-token-standard
  (seen via search only).

## Appendix A. Exclusion list (draft, from `spotMeta` names only)

Class S (stablecoins, fiat-pegged, wrapped fiat): 0 USDC, 229 HUSD, 235 USDE, 239 USDXL,
241 FEUSD, 268 USDT0, 291 USDHL, 303 USDY, 309 DUSD, 329 HUSDE, 352 USDG, 360 USDH,
375 WUSDN, 377 USDN, 392 RLUSD, 448 USDV, 479 WARS, 481 WBRL, 1337 WCLP.

Class B (bridged or wrapped external assets): 197 UBTC, 221 UETH, 254 USOL, 269 UFART,
299 UPUMP, 312 USPYX, 319 UUUSPX, 320 UBONK, 326 UMOG, 334 AURA (Unit AURA), 338 UENA,
343 UXPL, 344 TRX0, 347 AVAX0, 349 PEPE0, 358 UWLD, 361 UDZ, 365 UDOGE, 383 UMON,
403 UMEGA, 419 UZEC, 443 UVIRT, 451 UAVAX, 844 UANSEM, 845 NVDAX, 846 SPYX, 847 QQQX,
848 SKHYX, 849 MUX, 852 SNDKX, 853 SPCXX, 855 TSLAX, 856 AAPLX, 857 CRCLX, 1338 ANTX.

Class R (staked or vault receipt tokens): 119 STHYPE, 121 KHYPE, 230 DHYPE, 302 WHLP,
305 HWHLP, 308 THLP, 310 HWHYPE.

Native: 150 HYPE.

Review (resolve by the section 3.1 rule before locking): 169 ETHC, 188 SSS, 242 COOK
("mETH Protocol"), 369 MHYPE, 398 STABLE, 452 HTAO. Kept unless the rule says otherwise:
384 USDUC ("Unstable Coin", a memecoin by its own description), 191 UNIT (protocol token,
not a bridged asset), 1 PURR.

The list was drafted with a name and `fullName` pattern search over `spotMeta`
(USD, Unit, Wrapped, bridged, stable, xStock, BTC, ETH, SOL, HYPE); tokens not matching
any pattern were not reviewed by hand yet. A full hand pass over all names is a pre-lock
task.

## Verification (2026-11-20, DRAFT still not locked)

Checked against a verifier's list of findings. arxiv.org, papers.ssrn.com, usenix.org and
doi.org did not resolve from this session; a web search index was available.

Changed in this pass:

- Fewer-than-3-traded-days exclusion removed (3.1). Tokens with at least one traded day stay
  in the Kaplan-Meier sample; `P(d)` falls back to the maximum close of days 0 to 2, closes
  are carried forward on days without a bar, and a "dark rule" lets a token with no traded
  bar for 30 days collapse (3.3). The group is reported as its own row.
- `fee_share` removed from the primary Cox model and the IPW model; kept only in a
  sensitivity model labelled "post-outcome covariate" (sections 4, 5.2, 6).
- Primary cohort assigned from `t0` for every token; the `deployTime` cohort is a Cox
  stratum sensitivity, with the number of tokens that change cohort reported (3.2, 4).
- Threshold informed by a prior look: historical collapse rates are labelled so, L2 to L5
  are co-reported in the headline, and a confirmatory check on tokens listed after the lock
  is added (sections 0 and 5.4).
- H1 and H2: support requires a significant coefficient of the stated sign; the opposite sign
  is reported as "contrary".
- `prior_deploys` defined as a lower bound counting all crawl tokens with a known deployer,
  excluded classes included, with a sensitivity on low-failure index bands.
- Claims not backed by what was read were removed: Cernera et al.'s "most rug pulls within
  24 hours" and "about half of BNB Smart Chain spammers" figures, and Sun et al.'s ranking by
  damage. The Mazorra et al. thresholds are no longer attributed to them.
- Section and equation pointers removed or marked unverified for Kaplan and Meier, Cox,
  Grambsch and Therneau, Mazorra et al. and Mongardini and Mei. L5 and L6 are described as
  adaptations of Feder et al. (2018), with the differences stated and the source marked
  second-hand.
- Greenwood (1926) cited for the variance only, Kalbfleisch and Prentice (1980) for the
  log-log interval; Wei, Lin and Weissfeld (1989) and Lee, Wei and Amato (1992) added for
  clustering by deployer.
- References: Hu et al. (2026) authors, date and figures (41,470 memecoins, 122 features)
  confirmed through the arXiv listing in a search index, with the v2 retitle noted. Li et al.
  (2026) given a full author list from a secondary summary, marked unverified, and the "first
  five minutes" detail dropped. Mongardini and Mei cited as the arXiv preprint only. Brown et
  al. (1992) DOI given. Page ranges and full authors added for Greenwood, Mantel and
  Harrell et al.

Not resolved here:

- No full text was read. All section pointers, the Mazorra et al. label thresholds, the
  share of rug pulls that are 1-day rug pulls in Cernera et al., and the spammer statistics
  remain to be checked before locking.
- The arXiv records of Hu et al. and Li et al. could not be opened directly; the Li et al.
  author list rests on a secondary summary.
- Mongardini and Mei: the USENIX Security '26 proceedings and page range could not be
  checked.
- The DOIs of Brown et al. (1992), Lin and Wei (1989) and Wei, Lin and Weissfeld (1989), and
  the page range of Lee, Wei and Amato (1992), could not be confirmed (doi.org unreachable).
- The dark rule in section 3.3 is a new project choice made in this pass and should be
  reviewed by the owner.
