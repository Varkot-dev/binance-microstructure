# P1 pre-registration (DRAFT): a luck-adjusted Hyperliquid leaderboard

> **DRAFT, NOT LOCKED.** This plan is waiting for the owner's review. It has no force until
> the word DRAFT is removed, the file is renamed `PREREGISTRATION_P1.md`, and its sha256 is
> written on the line below and fixed in the analysis script. Until then no return, alpha,
> t-statistic, p-value, ranking or portfolio statistic of any cohort wallet may be computed,
> for the formation window or for the holding window.
>
> sha256 of the locked file (a file cannot contain its own hash, so at the lock this line is
> replaced by the sentence "recorded in `p1_skill.py` and `P1_LOCK.txt`", and the hash of the
> file as it then stands is written in those two places):

Written 2026-11-20, the day after the formation snapshot, **before any wallet return or
performance statistic was computed**. The 200-wallet pilot (`pilot/PILOT_REPORT.md`) measured
only data coverage, spacing, retention, consistency and cost; it computed no return, skill or
ranking statistic. Once locked, the analysis script `research/hyperliquid/p1_skill.py` will
hold this file's sha256 and refuse to run if the file has changed, the same pattern as
`research/politics/c4_prepost_trading.py` and `PREREGISTRATION_PREPOST.md`. Anything reported
that is not specified here is labelled **exploratory**.

Guiding question: *On Hyperliquid, where every trader's history is public, does anyone have
real skill, or are the winners just lucky?*

Citation tags. Every method choice cites its source inline as (author, year). In the
reference list each source carries a status tag: **[V]** read in full by this project;
**[R]** standard published reference whose method is described here from knowledge of the
paper, with section and table numbers still to be checked against the text before locking;
**[S]** non-peer-reviewed public work (GitHub) known to this project only through a summary
(the skeptic agent's notes in `LITERATURE.md`), not read in full; **unverified** marks a
record whose authors, title or identifier could not be confirmed at all. Section 13 lists the
checks that must be done before the lock. Note on `LITERATURE.md`: its [V] tag means
"standard published reference with long-established details, or a source we read", which is
broader than [V] here. Apart from the notes on Berk and van Binsbergen (2015, 2017) in
`qfa/NOTES.md`, none of the papers tagged [V] in `LITERATURE.md` has been read in full by this
project, so they are [R] here, and the two files do not conflict once the definitions are
read side by side.

---

## Methods in plain English

- **The problem.** Out of 48,035 wallets, some will have spectacular records purely by chance,
  the same way some people in a large coin-tossing contest throw ten heads in a row. A
  leaderboard sorted by profit cannot tell lucky wallets from skilled ones.
- **Freeze the contestants first.** We use a copy of the public leaderboard saved on
  2026-11-19 at 23:58:51 UTC, fixed by its sha256 fingerprint. Every wallet on it stays in the
  study, including those that later lose everything.
- **Measure returns fairly.** A wallet that deposits $1M has not "made" $1M. We remove deposits
  and withdrawals and measure the profit earned on the money that was actually at work, every
  two weeks before the snapshot and every day after it.
- **Compare with doing nothing clever.** Holding Bitcoin in a rising market is not skill. We
  measure each wallet's profit after subtracting what a simple Bitcoin position (and, as
  checks, other simple positions) would have earned. What is left is called alpha.
- **Ask how much alpha luck alone would produce.** We build thousands of imaginary histories
  in which no wallet has any skill, by reshuffling the real calendar periods (all wallets on
  the same reshuffled dates, so market crashes still hit everyone at once). If the real best
  wallets are much better than the best wallets in these no-skill worlds, some skill exists.
- **Count the skilled, without naming them.** A standard method estimates the share of wallets
  with zero skill, positive skill and negative skill, while controlling the expected share of
  false "discoveries" among the wallets flagged.
- **Test on the future.** The real test is a period that had not happened when the plan was
  locked: the 56 days that start at 00:00 UTC on the day after the lock (section 7.1). Any days
  between the snapshot and that start are reported only as exploratory. We compare three ways
  of picking 500 wallets to follow:
  the statistically skilled ones, the biggest past earners, and a simple prediction model.
  If the statistical pick does not beat the others on the future, the "skill" was not useful.
- **What we publish.** Only totals and shares. We never publish a list that calls a named
  address skilled, unskilled or suspicious.

---

## 1. Question, hypotheses and stated prior

**Question.** In a cohort of Hyperliquid wallets frozen before outcomes are known, how much of
the cross-section of past performance would luck alone produce, what share of wallets shows
real positive or negative skill once multiple testing is controlled, and does selecting
wallets on statistical skill beat selecting them on past dollar profit over a future window?

Hypotheses (each tested at the primary benchmark rung R1, section 4):

- **H1 (right tail, formation window).** The right tail of the cross-section of alpha
  t-statistics is thicker than luck produces, and the skilled share pi_A+ is above zero.
- **H2 (left tail, formation window).** The left tail is thicker than luck produces, and the
  unskilled share pi_A- is above zero.
- **H3 (out of sample).** Over the holding window, the 500 wallets with the best formation
  q-values earn positive alpha and beat the 500 wallets with the highest formation dollar PnL.
- **H4 (persistence).** Formation and holding-window alpha t-statistics are positively rank
  correlated.

**Stated prior, written before any outcome.**

- Retail speculators: fewer than 1% of Taiwanese day traders predictably earn positive
  abnormal returns net of fees, although the top group by past return keeps earning the next
  year (Barber, Lee, Liu and Odean, 2014); losers quit slowly and much volume comes from
  traders with a history of losses (Barber, Lee, Liu, Odean and Zhang, 2020); about 97% of
  day traders who persisted for more than 300 days lost money, among individuals who started
  day trading Brazilian mini-index futures in 2013 to 2015 (Chague, De-Losso and Giovannetti,
  2019). Mutual funds net of costs: about 75% zero alpha, 24%
  unskilled and 0.6% skilled (Barras, Scaillet and Wermers, 2010).
- Hyperliquid: in the closest prior work, 4 of 216 top accounts pass a timing placebo at
  Benjamini-Hochberg q = 0.10 (in-sample, including the window that selected them, under the
  amended z-based p-values), 0 of 52 vaults pass, and timing does not persist (Spearman
  rho = -0.09) (Placebo, 2026). Leaderboard ROI rank correlations between adjacent 30-day
  blocks swing from -0.44 to +0.54 with the market phase (Dennim89, 2026).
- Prior expectations, therefore: pi_A+ between 0% and 2%; pi_A- between 10% and 40%;
  pi0 above 50%; H1 likely to show at most a weak right tail; H2 likely to hold; H3 the top
  q-value group's holding alpha positive but not significant, and not significantly better
  than the top-PnL group; H4 rho between 0 and 0.2. Our subjective probability of a
  **positive** out-of-sample verdict (section 9) is about 15%. A top-500 holding return near
  the 37.9 bp per day after fees that `LITERATURE.md` records for the top Taiwanese day
  traders (Barber, Lee, Liu and Odean, 2014; the figure and its fee basis are still to be
  checked against the paper's table, section 13) would be a large and surprising result and
  would be checked for data errors first. Holding returns here are after Hyperliquid trading
  fees and funding, so the comparison is net to net if the figure is confirmed as after fees.

---

## 2. Frozen cohort and data

### 2.1 Formation snapshot

- File: `data/hyperliquid/formation/leaderboard_20261119T235851Z.json.gz`.
- sha256: `ac669f966b7ddbd4a4e5aa8ac50781c9a8d9f51a071ac3c062812046217c1a37`.
- Public copy: release `hl-snapshots-2026-11`,
  https://github.com/Varkot-dev/binance-microstructure/releases/tag/hl-snapshots-2026-11.
- Formation time T0 = 2026-11-19T23:58:51Z = 1,795,132,731,000 ms (`FORMATION_MS` in
  `pilot.py`).
- Rows: **48,035** in `leaderboardRows`, all with distinct addresses (the pilot counted
  them; an earlier brief said 48,003, but the hash matches and 48,035 is correct).
- The leaderboard is used **only as the universe list** and for descriptive accountValue and
  volume. Its `pnl` and `roi` fields are never used as an outcome or ranking variable, because
  the pilot found they match neither portfolio pnl definition for 11% of wallets.

The cohort's inclusion rule is undocumented and covered only about 22% of live trading
addresses in one small sample (README section 5). Results describe this cohort, not all
Hyperliquid traders, and the number of tests understates the number of addresses that could
have been examined (Harvey, Liu and Zhu, 2016, on unobserved tests).

### 2.2 Data pulled per wallet (free endpoints only)

Formation pass, for all 48,035 addresses plus every sub-account listed by `subAccounts`:
`portfolio`, `userNonFundingLedgerUpdates` (paged forward from `startTime = 0`) and
`subAccounts`. Vault status comes from the `stats-data` vault list saved by the recorder on
2026-11-19 only (the list dated at or before T0), with `userRole` called only for addresses
not resolved by that list.
Pilot projection: about 62 h at 780 weight per minute, one IP, paced at 65% of the documented
budget, backing off on HTTP 429.

- **Timing requirement.** Every formation value is the value at T0, read as the last native
  point at or before T0. Points after T0 are discarded. For the endpoint value at T0 the
  finest window that contains a point at or before T0 is used: `day`/`perpDay` if the wallet
  was fetched within 24 h of T0, else `week`/`perpWeek` (2.3 to 3.0 h spacing, covers 7 days),
  else `month`/`perpMonth` (9 to 24 h spacing). The gap between that point and T0 is recorded
  per wallet. A wallet whose nearest point before T0 is more than 24 h before T0 is flagged;
  the share flagged is reported. This replaces the pilot's day-window rollback, which only
  works when the whole pass finishes within a day. The `pnlHistory` of the day, week and month
  windows is cumulative within the window and is not on the allTime scale, so only
  within-window differences of P are used, and the level at T0 is
  P_allTime(last) - (P_win(last) - P_win(last point <= T0)), the formula of `at_formation` in
  `pilot.py`, with the matching perp windows for `perpAllTime`.
- **Post-T0 points are not opened before the lock.** The formation pass returns points dated
  after T0. They enter only as the differencing anchor P_win(last) in the formula above; no
  return, PnL change or ranking over any period after T0 is computed, printed or inspected
  before the lock, and the same holds for the recorder's daily leaderboard snapshots after
  T0. `P1_LOCK.txt` states this.
- **Forward recording for the holding window.** From the end of the formation pass until 7
  days after the end of the secondary holding window (section 7.1), poll `portfolio` and `userNonFundingLedgerUpdates` for every cohort address and
  sub-account **every 7 days** (about 42 h of crawl per pass, plus about 20% for
  sub-accounts). The `month` windows of successive passes overlap, so each pass must start
  within 21 days of the previous one; if any gap exceeds 21 days, the uncovered days are
  missing for every wallet and are reported. The first forward pass must begin no later than
  2026-12-10 so that its month window reaches back to 2026-11-20.
- **Stitching forward passes.** Within one pass, only differences of P and AV between points
  of the same window are used. Consecutive passes are chained at the latest timestamp present
  in both passes' `perpMonth` (or `month`) windows: the later pass's differences are added to
  the chained level at that timestamp. Where two passes overlap, the later pass's points are
  used. A disagreement between the two passes' P or AV changes over the overlap larger than
  max($1, 1% of AV) is counted per unit and the share of units with any such disagreement is
  reported.
- **Benchmarks.** `candleSnapshot` 1d for BTC, ETH, HYPE and every perp in `meta` (formation
  window), 1h for BTC, ETH and HYPE saved during the holding window (1h reaches back about 7
  months, so a save at the end of the window covers it); `fundingHistory` hourly for every
  perp; `vaultDetails` for HLP (`0xdfc24b077bc1425ad1dea75bcb6f8158e10df303`) at every poll.
- **Fills** (`userFillsByTime`) are not used in any primary test. Fill-based analyses
  (section 8, item 11) use a seeded random sample of 5,000 eligible units.
- Raw responses are stored gzipped under `data/hyperliquid/p1/` (git-ignored) with a sha256
  manifest, and are never committed.

Any address whose calls still fail after retries is kept in the cohort with status "fetch
failed" and counted in every exclusion table.

---

## 3. Units, inclusion rules and returns

### 3.1 Outcome series (fixed in advance)

- **Primary series: `perpAllTime`** (`pnlHistory` P and `accountValueHistory` AV) for the
  formation window, and `perpMonth` for the holding window. Reason: the benchmark ladder is
  built from perp returns with funding, and the perp series excludes spot airdrops such as
  the HYPE genesis distribution, whose later price change is a windfall rather than trading
  skill. The same choice applies in formation and holding windows (pilot restriction 1).
- **Robustness series: `allTime` and `month`** (total account, spot included), with HYPE spot
  added to the benchmark (section 8, item 1).

### 3.2 Entities (merging wallets that belong to one owner)

- **Primary entity rule: declared sub-accounts.** A master address and every sub-account it
  lists in `subAccounts` form one entity. The entity's cumulative PnL and account value are the
  sums over its members at each grid time; transfers between members (`subAccountTransfer`)
  cancel inside the entity. Sub-accounts not on the leaderboard are fetched and added to their
  master's entity. This addresses the risk that one person splits opposite bets across wallets
  and manufactures a lucky winner (README risk 4). Barras, Scaillet and Wermers (2010) and
  Berk and van Binsbergen (2015) both measure skill at the fund level, combining share classes
  of one portfolio (Berk and van Binsbergen, 2015). Merging sub-accounts into one entity is the
  analogous step here.
- **Entity membership over time.** For the formation window, membership is frozen as listed by
  `subAccounts` in the formation pass. For the holding window, a sub-account of a cohort master
  first listed in any forward poll is added to its master's entity from its creation, so that
  `subAccountTransfer` into it cancels and PnL moved into it stays in the entity's return. The
  number of sub-accounts added this way is reported. Sub-accounts never change formation-window
  statistics or the selection sets.
- **Robustness entity rule: funding links.** Two cohort addresses are also linked when the
  ledger shows a direct `send`, `internalTransfer` or `spotTransfer` of at least $1,000
  between them, before T0. This direct-transfer rule is this project's own heuristic; Victor
  (2020) is cited only as the general reference for address clustering on account-based
  chains, and none of its three heuristics (exchange deposit-address reuse, airdrop
  multi-participation, self-authorization) is this rule. Links are combined by connected components; a component with more than 20
  addresses is treated as a hub (an exchange, bridge or OTC desk) and is not merged. The
  number and size distribution of components are reported.
- Correlated-timing links need fills and are exploratory only.
- All counts below are in units = entities (an unmerged wallet is a unit of one).

### 3.3 Vaults

Vault addresses (from the 2026-11-19 vault list or `userRole = vault`, about 4% in the pilot)
are removed from the trader family and tested as a **separate family** with the same pipeline
(section 10), because a vault's series mixes the leader's skill with depositor flows and the profit
share (Berk and Green, 2004; Berk and van Binsbergen, 2017).

### 3.4 Formation grid and returns

- **Grid.** Calendar blocks of 14 days anchored at T0: block k covers (T0 - 14k days,
  T0 - 14(k-1) days], for k = 1, ..., K, with K the first block that starts before the
  earliest point of any unit (about 80 blocks). Two weeks is the finest grid every wallet
  supports: the pilot found allTime spacing of 168 h up to about 700 days of age and 336 h
  beyond (26% of wallets) (pilot restriction 2).
- **Reading the series.** For each unit and block boundary, P and AV are read at the last
  native point at or before the boundary. The actual span of block k for a unit is between the
  native timestamps s_(k-1) and s_k that were used; staleness (boundary minus native
  timestamp) is recorded. The benchmark return for that unit and block is computed over
  exactly [s_(k-1), s_k], so stale reads shift both sides equally. The block label k is used
  only to align units in time for the joint resampling in section 5.
- **Flows.** Because `pnlHistory` excludes deposits (DATA.md section 5), the net flow over a
  span is defined as F = (AV_k - AV_(k-1)) - (P_k - P_(k-1)). The ledger is used to time the
  flows inside the span and as a consistency check: the share of spans in which F differs from
  the sum of ledger flows by more than max($1, 1% of AV_(k-1)) is reported.
- **Return (Modified Dietz).** r_k = (P_k - P_(k-1)) / (AV_(k-1) + sum_j w_j F_j), where the
  F_j are the timed ledger flows in the span and w_j is the fraction of the span remaining
  after flow j; any part of F not matched by ledger rows is given w = 0.5 (Dietz, 1966). Returns
  are truncated at -100%; the number truncated is reported.
- **Alive spans.** A span counts in return statistics only if its Dietz denominator is at
  least **$100** (the cohort median accountValue is about $349, so a higher floor would drop
  most of the cohort; $1,000, the scaled analogue of the $5M size floor of Berk and van
  Binsbergen, 2015, is a robustness check; the section pointer for that floor is still to be
  checked). Dollar PnL of non-alive spans is kept
  in all dollar statistics.
- **Death.** A loss that takes equity from at least $100 to near zero is a return of about
  -100% in that span, never missing data (README Project 1). After death the unit is not alive
  until a new deposit brings the denominator back above the floor.
- **Holding-window returns** use the same formulas on a daily 00:00 UTC grid built from the
  `perpMonth` points of the weekly polls (9 to 24 h spacing), chained across passes by the
  stitching rule of section 2.2. Staleness per unit and day is
  recorded. If a unit has no point within 72 h of a grid time, its daily returns over the gap
  are missing and the dollar PnL of the whole gap is booked on the day the gap ends.

### 3.5 Inclusion rules for the trader family

All rules use only data dated at or before T0. A unit is **eligible** if all of these hold:

1. Not a vault (section 3.3) and fetched successfully.
2. First `perpAllTime` point at least **182 days** before T0 (88% of pilot wallets). The
   stricter **365 days** (70%) is a robustness check, not a second primary test (pilot
   restriction 3).
3. At least one alive span with a non-zero change in `perpAllTime` P before T0 (wallets with
   no trading have no skill to test; the 12 of 200 pilot wallets without fills are expected to
   fall here). The scalar `vlm` field is not used, because it is read at fetch time, after T0.
4. At least **13 alive 14-day spans** (182 days of alive history).
5. Non-zero variance of alive span returns, and fewer than 50% of alive spans with exactly
   zero PnL, so that null p-values are not piled up at 1 (Storey, 2002, assumes uniform null
   p-values). The minimum-history rule 4 is a precision filter, in the spirit of the
   60-observation minimum of Barras, Scaillet and Wermers (2010), which serves to estimate
   alpha precisely.

Accounts with zero equity at T0 (14.5% of the pilot sample) stay eligible if they meet these
rules, because their past record is part of the cross-section and dropping them would select
on outcome (README risk 1). They cannot be copied, so they are excluded from the holding-window
**selection sets** (section 7.2), but they remain in the dollar-PnL distributions.

The exclusion count for each rule, in this order, is reported, together with m, the number of
eligible units. The minimum-history filter is itself a selection on survival, so the
characteristics of excluded units are reported too.

---

## 4. Benchmark ladder

The benchmark B is a set of returns of positions the wallet could have held passively, net of
their own costs, which is the investable-alternative principle of Berk and van Binsbergen
(2015; the section pointers to that paper in this plan are still to be checked, section 13). Each rung gives its own alpha and its own skilled share, and the shrinkage of
the skilled share up the ladder is reported (README Project 1).

- **R0, raw.** B = 0 (idle USDC earns nothing on the venue).
- **R1, BTC perp with funding (primary rung).** B = r_BTC, the return of a 1x long BTC perp
  over the span: mark close at the end over mark close at the start, minus 1, minus the sum of
  the hourly funding rates a long pays over the span. Formation spans use 1d closes, so span
  endpoints are rounded to the nearest 00:00 UTC for the benchmark (up to 12 h of
  misalignment on a 14-day span); funding before 2023-05-12 (start of `fundingHistory`) is set
  to zero and those spans are flagged. R1 is primary because most units have 13 to 40
  two-weekly observations, and every extra regressor costs a degree of freedom.
- **R2, investable on-venue set.** Long BTC, ETH and HYPE perps with funding (HYPE from its
  listing) and an HLP deposit (flow-adjusted from `vaultDetails`). Assets that start later
  are handled with the orthogonal "augmented basis" of Berk and van Binsbergen (2015).
  Betas are unrestricted in sign. Estimated only for units with at least 26 alive
  spans. **R2 without HLP** separates liquidity-provision exposure from other skill (a project
  choice; whether it mirrors a specific comparison in Berk and van Binsbergen, 2015, is still
  to be checked).
- **R3, crypto factor model.** CMKT, CSIZE and CMOM built from the Hyperliquid perp universe
  with funding (Liu, Tsyvinski and Wu, 2022), with 30-day dollar volume in place of market
  capitalization for the size sort and 3-week past return for momentum, plus a funding-carry
  factor (Schmeling, Schrimpf and Todorov, 2023). Delisted perps stay in the factor universe
  until delisting. Factor portfolios are not investable and carry hindsight (Berk and van
  Binsbergen, 2015), and the repo's own versions were insignificant over 146 weeks
  (LITERATURE.md section 4), so R3 is a robustness rung only. Estimated only for units with at
  least 26 alive spans.

**Model and statistic.** For unit i and alive span k:
r_ik = alpha_i + beta_i' B_ik + e_ik, by OLS. The test statistic is the alpha t-statistic
t_i with Newey-West standard errors (Newey and West, 1987) and lag floor(4 (T_i / 100)^(2/9))
(Newey and West, 1994). The t-statistic, not raw alpha, is the ranking and testing statistic
because alpha scales with leverage, while t(alpha) scales out residual volatility and
penalizes short, noisy histories (Kosowski, Timmermann, Wermers and White, 2006; Fama and
French, 2010). Raw alpha is reported but not used for inference.

**Dollar value added** is also reported at every rung: V_ik = (P_k - P_(k-1)) -
AV_(k-1) * beta_i' B_ik, with skill S_i = mean_k V_ik and the cross-sectional ex ante mean
S = (1/m) sum_i S_i (Berk and van Binsbergen, 2015; section and equation numbers still to be
checked), plus its median and quantiles, because the dollar mean is dominated by the largest
units. Two differences from Berk and van Binsbergen are stated in advance: they compute value
added from gross returns and lagged assets under management in real (inflation-adjusted)
dollars, while here P is after trading fees and funding and all dollar values are nominal
USDC.

---

## 5. Luck nulls (formation window)

All randomness uses `numpy.random.default_rng` with base seed 20261119; each component below
uses seed 20261119 + its number (1 for 5.1, 2 for 5.2, and so on), so results can be
reproduced exactly.

### 5.1 Headline: joint calendar-block bootstrap (cross-section test)

Following Fama and French (2010, section II):

1. Impose the null on each unit: r0_ik = r_ik - alpha_hat_i, so every unit has zero in-sample
   alpha while keeping its betas, volatility, skewness and fat tails.
2. One run draws K calendar blocks with replacement. **The same drawn blocks are used for every
   unit and for the benchmark series**, which keeps common shocks such as 2025-10-10, when
   every wallet moved at once, inside the null (README risk 6; Fama and French, 2010).
3. In each run, re-estimate t_i for every unit that has at least 8 alive spans among the drawn
   blocks (the analogue of the 8-month minimum of Fama and French, 2010).
4. **B = 10,000 runs.**
5. Report, for the cross-section of t_i, at the percentiles 0.1, 1, 5, 10, 25, 50, 75, 90, 95,
   99 and 99.9, plus the minimum and maximum: the actual value, the mean simulated value, and
   "% < Act", the share of runs whose simulated percentile is below the actual one (Fama and
   French, 2010, tables of simulated percentiles). Also report the right-tail p-value of each
   upper order statistic as the share of runs at or above the actual value, and the mirror for
   the lower tail (Kosowski, Timmermann, Wermers and White, 2006, section I), computed as
   (1 + count) / (B + 1) (Phipson and Smyth, 2010).
6. **Dispersion of true alpha.** Re-run with injected true alphas alpha_i ~ N(0, sigma) per
   unit, sigma on the grid {0, 0.25, 0.5, 1, 2, 4, 8}% per 14-day span, 1,000 runs per grid
   value. Following Fama and French (2010), report the likelihood table: for each sigma and
   each of the 11 percentiles, "% < Act", the share of runs whose simulated percentile is below
   the actual one. In addition, report the sigma whose mean simulated percentiles are closest
   to the actual ones in squared distance over the 11 percentiles. This selection rule is this
   project's own adaptation: Fama and French judge informally which sigma values fit from the
   likelihoods, and their grid is stated as annual alpha (0 to 2% per year). The per-14-day
   grid used here is a project choice, because leveraged wallets have far larger alpha
   dispersion than mutual funds.

Selection note. The cohort was listed on the leaderboard on 2026-11-19, which may depend on
past activity or balances. The formation-window test is therefore evidence about this cohort's
past, not a clean forward test; the clean test is section 7, which uses only days after the
lock.

### 5.2 Per-unit p-values without the permutation floor

The run-level p-values in 5.1 cannot feed FDR: their floor is 1/(B + 1), and the first
Benjamini-Hochberg rejection needs p(1) <= q/m, which for q = 0.10 and m near 48,000 is about
2.1e-6 (Benjamini and Hochberg, 1995; Phipson and Smyth, 2010). Placebo hit exactly this trap
and had to amend its p-value rule after the first run (Placebo, 2026). Per-unit p-values are
therefore computed as a **two-stage bootstrap-t** under the null. The bootstrap-t (pivotal)
statistic and the resampling of null-imposed series follow the two guidelines of Hall and
Wilson (1991). The two-stage rule below is this project's own; it is related to the sequential
Monte Carlo p-values of Besag and Clifford (1991), which neither Hall and Wilson nor Phipson and
Smyth (2010) cover.

- The null series r0_ik is resampled with the joint calendar-block draws of 5.1 (so each
  unit's null distribution keeps the same dates as every other unit's), and t*_ib is
  re-estimated. Two-sided p_i = (1 + #{b : |t*_ib| >= |t_i|}) / (B + 1) (Phipson and Smyth,
  2010).
- **Invalid draws.** A joint draw in which unit i has fewer than 8 alive spans, or zero
  residual variance, is not counted for unit i. It is redrawn for that unit only, from a
  separate fixed seed stream (seed 20261119 + 2, then a per-unit `SeedSequence` spawn indexed
  by the unit's position in the sorted address list), until B1 (or B2) valid draws exist. The
  redrawn calendar blocks are used for that unit and the benchmark only. The share of redraws
  per unit is reported (median, 90th and 99th percentiles across units).
- **Stage 1:** B1 = 9,999 for every unit.
- **Stage 2:** every unit with stage-1 p_i <= 10 / (B1 + 1) = 0.001 gets
  B2 = max(1,999,999, ceil(2m / q) - 1) fresh draws, and its final p-value comes from the
  stage-2 draws only. With m <= 48,035 and q = 0.10 the floor 1/(B2 + 1) is at most 5e-7,
  about four times below q/m. The stage-2 rule is fixed here, before any p-value is seen.
  Validity argument: the stage-2 draws are independent of the stage-1 draws, so for any a,
  P(final p <= a) <= P(stage-2 p <= a), which is about a (at most a up to the Monte Carlo
  rounding of the (1 + count)/(B + 1) rule, Phipson and Smyth, 2010) for units that enter
  stage 2, and units that do not enter stage 2 keep a p-value above 0.001. The scheme is
  therefore conservative.
- **What this guarantees and what it does not.** The stage-2 rule controls Monte Carlo error
  only. It does not remove bootstrap approximation error: a bootstrap-t built from 13 to 40
  two-weekly observations has no known accuracy at the 1e-6 level where Benjamini-Hochberg
  rejections are decided. Discovery counts (section 6, item 5) are therefore secondary to
  pi0, pi_A+ and pi_A-, which use gamma >= 0.2, and the synthetic gate (section 6, item 7)
  checks the extreme tail directly.
- Robustness column: analytic Student-t p-values with T_i - (number of parameters) degrees of
  freedom, never primary, because t(alpha) from short samples of skewed, fat-tailed returns
  is far from its normal or Student-t approximation in the tails, the motivation for the
  bootstrap in Kosowski, Timmermann, Wermers and White (2006).

### 5.3 Pre-registered robustness nulls

- (a) **Stationary block bootstrap** of calendar blocks with mean block length 2 blocks
  (28 days), the same block sequence for all units and the benchmark, B = 10,000, which keeps
  serial dependence from positions held across blocks (Politis and Romano, 1994).
- (b) **Unit-by-unit residual bootstrap**, B = 1,000, drawing dates independently per unit
  (Kosowski, Timmermann, Wermers and White, 2006, section I), reported only to show how much
  ignoring cross-unit correlation inflates the apparent skill.
- (c) **Joint wild bootstrap with Rademacher signs**: restricted residuals multiplied by one
  random sign per calendar block, the same sign for every unit, holding the benchmark path
  fixed, B = 10,000 (wild bootstrap: Wu, 1986; Rademacher two-point weights: Liu, 1988,
  Mammen, 1993, and Davidson and Flachaire, 2008). This null is robust to volatility that changes with leverage
  but assumes residuals are symmetric, which short-volatility payoffs violate, so it is never
  the headline.

The trade-level sign-randomization described in `LITERATURE.md` for a Polymarket working paper
listed as SSRN 6687418 (authors given there as Gomez-Cram, Guo, Jensen and Kung; **unverified**:
the record could not be opened, two authors' first names and the year are unknown) is **not
part of this plan**. Its procedure will not be pre-registered until the paper has been found
and read.

---

## 6. Multiple testing and what is reported (formation window)

One test family per benchmark rung; the primary family is R1 on the trader units.

1. **Zero-alpha share.** pi0_hat(lambda) = #{p_i > lambda} / (m (1 - lambda)), truncated at 1
   (Storey, 2002). Primary lambda: the lambda in {0.05, 0.10, ..., 0.95} that minimizes the
   bootstrap mean squared error of pi0_hat(lambda), with min over lambda of pi0_hat(lambda)
   as the plug-in reference value, from 1,000 bootstrap resamples of the p-value vector
   (Storey, Taylor and Siegmund, 2004). Storey (2002) instead minimizes the bootstrap MSE of
   the pFDR estimate at a fixed rejection region; that rule is not used. Whether Barras,
   Scaillet and Wermers (2010) use exactly this objective and grid is still to be checked in
   their appendix (section 13); the rule above is fixed whatever that check shows. Robustness:
   fixed lambda = 0.5 (Storey, 2002). Because lambda is far from the stage-1 floor, the floor does
   not affect pi0.
2. **Skilled and unskilled shares** (Barras, Scaillet and Wermers, 2010, section I). With S+
   and S- the shares of units with p_i <= gamma and t_i > 0 or t_i < 0:
   pi_A+ = S+(gamma*) - pi0_hat gamma*/2 and pi_A- = S-(gamma*) - pi0_hat gamma*/2.
   gamma* is chosen over the grid {0.20, 0.25, ..., 0.50} as the value that minimizes the
   bootstrap MSE of pi_A+(gamma), with the maximum over the grid of pi_A+(gamma) as the
   plug-in reference (the mirror rule is applied separately for pi_A-), from the same 1,000
   resamples. The grid and this target are this project's choices, modelled on the gamma*
   procedure of Barras, Scaillet and Wermers (2010), whose exact grid and target have not yet
   been checked against their Section I and Appendix (section 13); fixed
   gamma* = 0.35 and 0.50 are robustness checks. Shares are truncated at 0 and truncation is
   reported.
3. **Standard errors** for pi0, pi_A+ and pi_A- come from 500 outer joint calendar-block
   bootstrap replications of the whole pipeline (steps 5.2 stage 1 with B1 = 999, then
   steps 1 and 2 here).
4. **Tail FDR** (Barras, Scaillet and Wermers, 2010): FDR+(gamma) = (pi0_hat gamma / 2) /
   S+(gamma) and T+(gamma) = S+(gamma) - pi0_hat gamma / 2, and the mirror for the left tail,
   at gamma in {0.01, 0.05, 0.10, 0.20}.
5. **Discovery counts, aggregates only.** Primary: number of units with Storey q-value
   <= 0.10 in each tail (Storey, 2002; Storey, 2003; Storey and Tibshirani, 2003), at the same
   level as Placebo (2026) so the two are comparable. The q-values are computed once per
   family from the two-sided p_i over all m units, with the primary pi0_hat of item 1; the
   tail counts (and set A in section 7.2) split the units by the sign of t_i. These counts are
   secondary to items 1 and 2 (section 5.2). Conservative: Benjamini-Yekutieli at
   q = 0.10 with c(m) = sum_(j=1..m) 1/j, valid under arbitrary dependence (Benjamini and
   Yekutieli, 2001). Descriptive hurdles: |t| > 3.0, Bonferroni and Holm at 0.05 (Dunn, 1961;
   Holm, 1979), and BHY at q = 0.01 (Harvey, Liu and Zhu, 2016, section 4).
6. **Missed discoveries.** Double bootstrap of Harvey and Liu (2020), with assumed null shares
   p0 in {pi0_hat - 2 SE, pi0_hat, pi0_hat + 2 SE, 0.90, 0.95, 0.99} and 200 outer by 200
   inner joint calendar-block draws: report the t-threshold giving FDR = 10% and the Type II
   rate at that threshold and at |t| = 3.0.
7. **Calibration gates, run first and reported whatever they show.**
   - *Synthetic gate (before any real data are analysed):* R = 100 replicated null panels
     (seed 20261119 + 10), each with m units carrying the cohort's alive-span counts, zero
     true alpha, a common factor and cross-unit residual dependence matched to the cohort's
     span structure. The pipeline must give all of: (i) pi0_hat within 2 SE of 1 in at least
     95 of the R panels; (ii) the share of panels with **any** unit at q <= 0.10 at most 0.10
     plus a one-sided 95% binomial margin (at most 15 of 100 panels), since under the complete
     null the Benjamini-Hochberg and Storey procedures at q = 0.10 should give no discovery in
     about 90% of datasets; (iii) the pooled empirical rates of p <= 1e-3 and p <= 1e-4 among
     null units within two-sided 99% binomial bounds of 1e-3 and 1e-4; (iv) a
     Kolmogorov-Smirnov p >= 0.01 for uniform p-values on all of [0, 1] (Massey, 1951). This
     strengthens the gate design of Placebo (2026).
   - *Placebo panel:* the real panel with every unit's alpha removed; criteria (i), (iii) and
     (iv) on the single panel, and the number of units with q <= 0.10, which should be 0.
   - *Injection:* true alphas injected into 1% and 5% of units; report recovered pi_A+.
   If a gate fails, the results are still reported, labelled "calibration failed", and no
   method is changed; a corrected method would be a new, separately locked plan.
8. **Limitation stated in advance.** pi0_hat is biased upward and pi_A+ downward when true
   alphas are small relative to noise and histories are short (Andrikogiannopoulou and
   Papakonstantinou, 2019), so pi_A+ is read as a lower bound.

**Headline sentence template, fixed in advance:** "At the [rung] benchmark, an estimated X%
(SE) of the m frozen-cohort units have zero alpha, Y% (SE) are unskilled and Z% (SE) are
skilled (Barras, Scaillet and Wermers, 2010, with lambda chosen as in Storey, Taylor and
Siegmund, 2004); N units
have Storey q <= 0.10, of which about FDR+ x N are expected to be false; the missed-discovery
rate at that threshold is W% (Harvey and Liu, 2020)." It is reported for every rung.

---

## 7. Out-of-sample test

### 7.1 Windows

- **Formation window:** everything at or before T0 = 2026-11-19T23:58:51Z.
- **Primary holding window:** 2026-11-20 00:00:00 UTC to 2027-01-14 23:59:59 UTC (56 days, the
  8-week horizon). The 69 seconds between T0 and the window start are ignored.
- **Secondary holding window:** 2026-11-20 00:00:00 UTC to 2027-05-20 23:59:59 UTC (182 days),
  reported separately with the same code.
- **Sub-blocks:** the primary window split into 2026-11-20 to 2026-12-17 and 2026-12-18 to
  2027-01-14 (28 days each), reported separately, because rank correlations swing with the
  market phase (Dennim89, 2026).
- Holding-window data are recorded from 2026-11-20 but no holding-window statistic may be
  computed before the lock; the lock must happen before 2026-12-04, and the lock date is
  printed in the output.

### 7.2 Selection sets (computed only from formation data)

Among eligible trader units with equity of at least $100 at T0 (a copier can only follow an
account that holds capital):

- **A, top q-value:** the 500 units with the smallest R1 Storey q-values among those with
  t_i > 0 (ties broken by larger t_i). The number of A units with q <= 0.10 is reported.
- **B, top PnL:** the 500 units with the highest formation dollar PnL, P(T0) - P(first point),
  from `perpAllTime`. Secondary: the trailing 30-day PnL, which is what public leaderboards
  sort on by default.
- **C, elastic-net baseline** (Zou and Hastie, 2005), the bar that machine-learning fund
  selection must beat (DeMiguel, Gil-Bazo, Nogales and Santos, 2023). Features, all computed
  at a cutoff time: formation R1 t-statistic, R1 alpha, total dollar PnL, PnL over the last
  30, 90 and 180 days, mean and standard deviation of span returns, maximum drawdown, account
  value, account age, `perpAllTime` volume, share of zero-PnL spans, R1 beta and the number
  of members in the entity. Training: features at T0 - 56 days, target = the unit's R1 alpha
  return over (T0 - 56 days, T0] (four spans), winsorized at the 1st and 99th percentiles;
  training units are those meeting section 3.5 at T0 - 56 days. Mixing parameter in
  {0.1, 0.5, 0.9, 1.0} and penalty path of 100 values chosen by 5-fold cross-validation with
  folds split by entity (Friedman, Hastie and Tibshirani, 2010), seed 20261119 + 7. The fitted
  model is applied to features at T0 and C is the top 500 predictions.
- **D, random control:** 500 units drawn with seed 20261119 + 8.
- **Deciles** of all selection-eligible units by formation R1 t_i.

Overlaps between A, B and C are reported. Every unit in a set stays in it for the whole window
whether it trades, quits, withdraws or is liquidated (intention to treat, following the
everyone-who-starts design of Chague, De-Losso and Giovannetti, 2019, and treating quitting as
an outcome as in Barber, Lee, Liu, Odean and Zhang, 2020). No holding-window capital floor is
applied, which avoids the survivorship that removed 114 of 190 leaders in Dennim89 (2026).

### 7.3 Holding-window measures

- **Primary group return (copier's return):** each unit in a set gets equal capital at the
  window start and is held: group value V_t = mean_i prod_(s <= t) (1 + r_is), with r_is = 0
  on days the unit is not alive (cash) and a liquidated unit's value staying at zero. The daily
  group return is V_t / V_(t-1) - 1.
- **Secondary group return:** the calendar-time ratio of summed daily dollar PnL to summed
  start-of-day equity of the set (Barber, Lee, Liu and Odean, 2014).
- **Value added:** each unit's daily V against R1 with beta estimated **only from
  holding-window data**, to avoid false persistence from shared beta estimation error (Berk and
  van Binsbergen, 2015, section 7.1); daily average across units of each set and decile.

### 7.4 Tests

Primary, both one-sided at 0.05, and H3 holds only if **both** pass (an intersection-union
test, which needs no multiplicity adjustment; Berger, 1982):

- **T1.** Mean daily return of A minus B > 0. p-value from a stationary bootstrap of days
  (mean block 5 days, B = 10,000; Politis and Romano, 1994) with the (1 + count)/(B + 1) rule
  (Phipson and Smyth, 2010); Newey-West t with 5 lags beside it (Newey and West, 1987).
- **T2.** The alpha of A's daily group return against R1 (daily BTC perp return with hourly
  funding) > 0, same p-value method.

Secondary, reported in full:

- A minus C and A minus D, and B minus D, with the same method.
- Top-minus-bottom decile spread and its R1 and R2 alpha (Carhart, 1997, decile-portfolio
  design, adapted to t-statistic sorts because return sorts are sorts on leverage).
- BvB order statistics: the number of days the top decile's value added beats the bottom
  decile's, and the number of days it is in the top half, each against Binomial(56, 1/2) with
  exact p-values, plus the adjacent-decile monotonicity count (Berk and van Binsbergen, 2015,
  section 7.1). The skewness of daily decile-mean value added is reported because the binomial
  test needs symmetry.
- **H4.** Spearman rank correlation (Spearman, 1904) between formation t_i and holding-window
  t_i (R1, holding-window beta, daily Newey-West) over eligible units with at least 30 alive
  days in the holding window, with a 95% stationary-bootstrap interval of days. Compared with
  Placebo (rho = -0.09) and Dennim89 (-0.44 to +0.54).
- Full distribution of holding-window dollar PnL for every eligible unit: shares above $0,
  above $10k and above $50k, annualized (Chague, De-Losso and Giovannetti, 2019).
- Quit hazard by formation-PnL quintile (no trading volume and no change in perp account value
  apart from funding for 14 or more consecutive days that do not end before the window ends),
  and the share of holding-window volume from units with negative formation PnL (Barber, Lee,
  Liu, Odean and Zhang, 2020).

**Minimum detectable effect.** After the lock and before any holding-window outcome is opened,
the MDE of T1 and T2 at 80% power is computed from the formation-window volatility of the A and
B group returns and printed. It is a power statement only; it does not change any test.

---

## 8. Robustness checks (all pre-registered, none primary)

1. `allTime`/`month` series instead of `perpAllTime`/`perpMonth`, with HYPE spot added to R2.
2. 365-day minimum history instead of 182 days.
3. $1,000 alive floor instead of $100.
4. Weekly (7-day) blocks for the subset of units whose whole history is on the 168 h grid (age
   under about 700 days).
5. Nulls 5.3 (a), (b) and (c); fixed lambda = 0.5; fixed gamma* = 0.35 and 0.50; analytic
   t p-values.
6. Every rung R0, R1, R2, R2 without HLP, R3, for both the formation shares and the holding
   tests.
7. Without entity merging, and with the funding-link entity rule.
8. Dropping the calendar block that contains 2025-10-10 and 2025-10-11 from the formation
   window.
9. Short-volatility check: R1 with a squared BTC return term (Treynor and Mazuy, 1966) and
   reporting the skewness and maximum drawdown of the A set, because wallets that sell
   volatility or harvest liquidations look skilled until the blow-up (Agarwal and Naik, 2004).
10. Secondary holding window (182 days) and the two 28-day sub-blocks.
11. **Fill-based subset (descriptive).** For a seeded random sample of 5,000 eligible units
    (seed 20261119 + 9), pull fills and keep units whose retrieved fill notional covers at
    least 99% of portfolio volume and which have no open position at their first fill. On this
    subset, report pi_A+ and pi_A- separately for gross and net-of-fee returns and for maker-
    and taker-dominated units. This subset **under-represents heavy traders** (in the pilot,
    11 of 27 wallets with $100M to $1B volume and 2 of 3 above $1B were cut off), so it is never
    used to state the headline share (pilot restriction 6).

---

## 9. What counts as a positive, negative or null result

**Data gates.** At least 2,000 eligible trader units (the analogue of Placebo's gate), and in
the holding window at least 90% of selection-set units with a point within 48 h of at least 90%
of grid times. If a gate fails, the results are reported as descriptive with the reason, and no
verdict is given. Gates are not relaxed after outcomes are seen.

**Formation window (cross-section), at R1:**

- **Positive (skill in the right tail):** "% < Act" at least 95% at both the 99th and 99.9th
  percentiles (section 5.1) **and** the lower 95% bound of pi_A+ (estimate minus 1.96 SE)
  above zero.
- **Negative tail (unskilled wallets exist):** "% < Act" at most 5% at both the 1st and 0.1st
  percentiles **and** the lower 95% bound of pi_A- above zero.
- **Luck explains the winners:** "% < Act" below 95% at the 99th percentile **and** the upper
  95% bound of pi_A+ below 1%.
- **Null (inconclusive):** anything else.

**Holding window (out of sample):**

- **Positive (skill is identifiable and useful):** T1 and T2 both pass (section 7.4).
- **Negative (statistical selection does not help):** the upper 95% bound of A's daily R1
  alpha is below 5 bp per day (about 20% a year, the minimum effect of interest fixed here),
  **or** B beats A with one-sided p < 0.05.
- **Null (inconclusive):** anything else; the interval is reported to show which effect sizes
  the data can rule out.

A positive formation result with a negative or null holding result is reported as "the
cross-section looks unlike luck, but the skill could not be used to pick future winners", and
is not summarized as evidence of skill.

---

## 10. Vault family (secondary)

Vault units go through sections 3 to 6 as their own family (with the same rules) if at least
300 vaults are eligible; otherwise only descriptive. Reported: pi0, pi_A+, pi_A- at R1 and R2
on the vault series, and the depositors' net alpha after the profit share, which competitive
equilibrium predicts to be about zero even when the leader adds value (Berk and Green, 2004;
Berk and van Binsbergen, 2017). This is a test of equilibrium, not of skill, and ordinary
wallets are not interpreted this way.

---

## 11. Ethics

- Only aggregates are published: shares, counts, distributions, portfolio returns and code. No
  table, figure or text names an address as skilled, unskilled, lucky or suspicious, and no
  per-address q-value or label is published or written on-chain (unlike Placebo, 2026).
  `displayName` is never used.
- Selection sets A to D and per-unit statistics stay under `data/` (git-ignored). Anyone can
  rebuild them from the public data and the code.
- A low q-value is a statistical statement about a return series, not a claim about a person's
  conduct; a negative alpha is not an accusation. Entities merged by funding links are
  inferences, not identifications.
- Raw API responses are not republished in bulk.
- The results are not investment advice. The study is framed as measurement for people deciding
  whether to trust PnL leaderboards (README section 1).

---

## 12. Changes after locking

No change after the lock. A change made later is written as a dated amendment in a separate
file, labelled as such, and every result is also reported under the original plan.

---

## 13. Checklist before locking (owner)

1. Read and check the section, table and equation numbers cited for every [R] reference, in
   particular Kosowski et al. (2006), Fama and French (2010), Barras et al. (2010), Storey
   (2002), Harvey and Liu (2020), Carhart (1997), Liu et al. (2022), Barber et al. (2014,
   2020) and Chague et al. (2019); update their tags in `LITERATURE.md`.
2. Confirm the formation pass schedule (section 2.2) and that weekly forward polling is
   running.
3. Confirm that no cohort return or performance statistic has been computed.
4. Remove the DRAFT banner, rename the file to `PREREGISTRATION_P1.md`, replace the hash line
   as described at the top, compute the sha256 of the final file, write it to
   `research/hyperliquid/P1_LOCK.txt` with the UTC lock time, and fix it as a constant in
   `p1_skill.py`, which refuses to run on a mismatch and prints the hash in every output (the
   pattern of `c4_prepost_trading.py`).

---

## References

Status tags: [V] read in full by this project; [R] standard published reference, method
described from knowledge of the paper, section numbers to be checked before locking;
[W] non-peer-reviewed public work read by this project.

- Agarwal, V. and Naik, N. Y. (2004). Risks and portfolio decisions involving hedge funds.
  *Review of Financial Studies* 17(1), 63-98. https://doi.org/10.1093/rfs/hhg044 [R]
- Andrikogiannopoulou, A. and Papakonstantinou, F. (2019). Reassessing false discoveries in
  mutual fund performance: Skill, luck, or lack of power? *Journal of Finance* 74(5),
  2667-2688. https://doi.org/10.1111/jofi.12798 [R]
- Barber, B. M., Lee, Y.-T., Liu, Y.-J. and Odean, T. (2014). The cross-section of speculator
  skill: Evidence from day trading. *Journal of Financial Markets* 18, 1-24.
  https://doi.org/10.1016/j.finmar.2013.05.006 [R]
- Barber, B. M., Lee, Y.-T., Liu, Y.-J., Odean, T. and Zhang, K. (2020). Learning, fast or
  slow. *Review of Asset Pricing Studies* 10(1), 61-93. https://doi.org/10.1093/rapstu/raz006
  [R]
- Barras, L., Scaillet, O. and Wermers, R. (2010). False discoveries in mutual fund
  performance: Measuring luck in estimated alphas. *Journal of Finance* 65(1), 179-216.
  https://doi.org/10.1111/j.1540-6261.2009.01527.x [R]
- Benjamini, Y. and Hochberg, Y. (1995). Controlling the false discovery rate: A practical and
  powerful approach to multiple testing. *Journal of the Royal Statistical Society, Series B*
  57(1), 289-300. https://doi.org/10.1111/j.2517-6161.1995.tb02031.x [R]
- Benjamini, Y. and Yekutieli, D. (2001). The control of the false discovery rate in multiple
  testing under dependency. *Annals of Statistics* 29(4), 1165-1188.
  https://doi.org/10.1214/aos/1013699998 [R]
- Berger, R. L. (1982). Multiparameter hypothesis testing and acceptance sampling.
  *Technometrics* 24(4), 295-300. https://doi.org/10.1080/00401706.1982.10487790 [R]
- Berk, J. B. and Green, R. C. (2004). Mutual fund flows and performance in rational markets.
  *Journal of Political Economy* 112(6), 1269-1295. https://doi.org/10.1086/424739 [R]
- Berk, J. B. and van Binsbergen, J. H. (2015). Measuring skill in the mutual fund industry.
  *Journal of Financial Economics* 118(1), 1-20.
  https://doi.org/10.1016/j.jfineco.2015.05.002 [V]
- Berk, J. B. and van Binsbergen, J. H. (2017). Mutual funds in equilibrium. *Annual Review of
  Financial Economics* 9, 147-167. https://doi.org/10.1146/annurev-financial-110716-032454 [V]
- Carhart, M. M. (1997). On persistence in mutual fund performance. *Journal of Finance* 52(1),
  57-82. https://doi.org/10.1111/j.1540-6261.1997.tb03808.x [R]
- Chague, F., De-Losso, R. and Giovannetti, B. (2019). Day trading for a living? Working paper,
  SSRN 3423101. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101 [R, working
  paper]
- DeMiguel, V., Gil-Bazo, J., Nogales, F. J. and Santos, A. A. P. (2023). Machine learning and
  fund characteristics help to select mutual funds with positive alpha. *Journal of Financial
  Economics* 150(3), 103737. https://doi.org/10.1016/j.jfineco.2023.103737 [R]
- Dennim89 (2026). hyperliquid-copytrade-study. GitHub repository, results dated 2026-09-25.
  https://github.com/Dennim89/hyperliquid-copytrade-study [W]
- Dietz, P. O. (1966). *Pension Funds: Measuring Investment Performance.* New York: Free
  Press. (Book; the Modified Dietz return is standard performance-measurement practice.) [R]
- Dunn, O. J. (1961). Multiple comparisons among means. *Journal of the American Statistical
  Association* 56(293), 52-64. https://doi.org/10.1080/01621459.1961.10482090 [R]
- Fama, E. F. and French, K. R. (2010). Luck versus skill in the cross-section of mutual fund
  returns. *Journal of Finance* 65(5), 1915-1947.
  https://doi.org/10.1111/j.1540-6261.2010.01598.x [R]
- Friedman, J., Hastie, T. and Tibshirani, R. (2010). Regularization paths for generalized
  linear models via coordinate descent. *Journal of Statistical Software* 33(1), 1-22.
  https://doi.org/10.18637/jss.v033.i01 [R]
- Hall, P. and Wilson, S. R. (1991). Two guidelines for bootstrap hypothesis testing.
  *Biometrics* 47(2), 757-762. https://doi.org/10.2307/2532163 [R]
- Harvey, C. R. and Liu, Y. (2020). False (and missed) discoveries in financial economics.
  *Journal of Finance* 75(5), 2503-2553. https://doi.org/10.1111/jofi.12951 [R]
- Harvey, C. R., Liu, Y. and Zhu, H. (2016). ... and the cross-section of expected returns.
  *Review of Financial Studies* 29(1), 5-68. https://doi.org/10.1093/rfs/hhv059 [R]
- Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian
  Journal of Statistics* 6(2), 65-70. https://www.jstor.org/stable/4615733 [R]
- Kosowski, R., Timmermann, A., Wermers, R. and White, H. (2006). Can mutual fund "stars" really
  pick stocks? New evidence from a bootstrap analysis. *Journal of Finance* 61(6), 2551-2595.
  https://doi.org/10.1111/j.1540-6261.2006.01015.x [R]
- Liu, Y., Tsyvinski, A. and Wu, X. (2022). Common risk factors in cryptocurrency. *Journal of
  Finance* 77(2), 1133-1177. https://doi.org/10.1111/jofi.13119 [R]
- Massey, F. J. (1951). The Kolmogorov-Smirnov test for goodness of fit. *Journal of the
  American Statistical Association* 46(253), 68-78.
  https://doi.org/10.1080/01621459.1951.10500769 [R]
- Newey, W. K. and West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and
  autocorrelation consistent covariance matrix. *Econometrica* 55(3), 703-708.
  https://doi.org/10.2307/1913610 [R]
- Newey, W. K. and West, K. D. (1994). Automatic lag selection in covariance matrix
  estimation. *Review of Economic Studies* 61(4), 631-653. https://doi.org/10.2307/2297912
  [R]
- Phipson, B. and Smyth, G. K. (2010). Permutation p-values should never be zero: Calculating
  exact p-values when permutations are randomly drawn. *Statistical Applications in Genetics
  and Molecular Biology* 9(1), Article 39. https://doi.org/10.2202/1544-6115.1585 [R]
- Placebo (cyberhooman) (2026). Hyperliquid timing placebo test. GitHub repository, results
  dated 2026-10-05 (README.md and PREREGISTRATION.md). https://github.com/cyberhooman/placebo
  [W]
- Politis, D. N. and Romano, J. P. (1994). The stationary bootstrap. *Journal of the American
  Statistical Association* 89(428), 1303-1313.
  https://doi.org/10.1080/01621459.1994.10476870 [R]
- Schmeling, M., Schrimpf, A. and Todorov, K. (2023). Crypto carry. BIS Working Paper 1087.
  https://www.bis.org/publ/work1087.pdf [R, working paper]
- Spearman, C. (1904). The proof and measurement of association between two things. *American
  Journal of Psychology* 15(1), 72-101. https://doi.org/10.2307/1412159 [R]
- Storey, J. D. (2002). A direct approach to false discovery rates. *Journal of the Royal
  Statistical Society, Series B* 64(3), 479-498. https://doi.org/10.1111/1467-9868.00346 [R]
- Storey, J. D. (2003). The positive false discovery rate: A Bayesian interpretation and the
  q-value. *Annals of Statistics* 31(6), 2013-2035. https://doi.org/10.1214/aos/1074290335 [R]
- Storey, J. D. and Tibshirani, R. (2003). Statistical significance for genomewide studies.
  *Proceedings of the National Academy of Sciences* 100(16), 9440-9445.
  https://doi.org/10.1073/pnas.1530509100 [R]
- Treynor, J. L. and Mazuy, K. K. (1966). Can mutual funds outguess the market? *Harvard
  Business Review* 44(4), 131-136. [R]
- Victor, F. (2020). Address clustering heuristics for Ethereum. In *Financial Cryptography and
  Data Security 2020*, Lecture Notes in Computer Science 12059, 617-633. Springer.
  https://doi.org/10.1007/978-3-030-51280-4_33 [R]
- Wu, C. F. J. (1986). Jackknife, bootstrap and other resampling methods in regression
  analysis. *Annals of Statistics* 14(4), 1261-1295. https://doi.org/10.1214/aos/1176350142
  [R]
- Zou, H. and Hastie, T. (2005). Regularization and variable selection via the elastic net.
  *Journal of the Royal Statistical Society, Series B* 67(2), 301-320.
  https://doi.org/10.1111/j.1467-9868.2005.00503.x [R]

Mentioned but deliberately not used until read: Gomez-Cram, R., Guo, ?, Jensen, ? and Kung, H.
Prediction market accuracy: Crowd wisdom or informed minority? Working paper, SSRN 6687418.
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6687418 (unread; author first names not
confirmed).
