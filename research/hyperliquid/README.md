# Hyperliquid: skill or luck?

> **Status (2026-11-22):** Project 1's plan is locked in
> [PREREGISTRATION_P1.md](PREREGISTRATION_P1.md) (sha256 and lock time in
> [P1_LOCK.txt](P1_LOCK.txt)). The out-of-sample window runs from 2026-11-23 to 2027-01-18,
> and the weekly wallet crawl (`.github/workflows/hl-p1-crawl.yml`) collects its data.

Written 2026-11-19 from one day of desk research and live API probes. This is the starting brief
for the new guiding question of the repo. Read this file first, then `DATA.md`, `LITERATURE.md`
and `ML_IDEAS.md` in this folder.

> **Guiding question.** On Hyperliquid, where every trader's history is public, does anyone
> have real skill, or are the winners just lucky?

Sub-question the owner cares about: **memecoins and rug pulls.** Who profits when a token
launches or collapses, and can warning signs be detected early? All of that work is framed as
detection, measurement and avoiding becoming the victim. It is never a guide to running a
squeeze, a rug or wash trading.

Evidence tags used below: **[V]** checked by us live on 2026-11-19 or a long-established
published reference; **[S]** seen only in search snippets or secondary write-ups (arxiv.org,
hyperliquid.gitbook.io and portal.sqd.dev were blocked from the research machine), so verify
before citing publicly; **[I]** our inference.

---

## 1. Why this question matters

- **It is the mutual-fund question on a new kind of data.** Finance spent 30 years asking
  whether fund managers have skill (Berk and van Binsbergen; Kosowski, Timmermann, Wermers and
  White; Fama and French; Barras, Scaillet and Wermers). Those studies only ever saw monthly
  returns of a few thousand funds. Hyperliquid shows every fill, deposit, withdrawal and
  liquidation for tens of thousands of wallets, for free.
- **Retail cares.** Copy-trading tools (HyperDash, Copin, LiquidWhales) rank wallets by PnL or
  proprietary scores and sell "follow the winners". If most winners are lucky, those rankings
  mislead people. A luck-adjusted answer is useful to anyone deciding whom to copy.
- **Memecoins are where retail loses most.** Of 280 ordinary HIP-1 spot tokens with 60+ days of
  history, the median now trades at about 3% of its peak close, and about two thirds are below
  10% of peak [V, own computation]. Knowing which signs show up early helps people avoid being
  exit liquidity.
- **It suits the repo's culture.** Pre-registration and hash-locking matter more here than
  usual, because with 48k wallets you are guaranteed to find spectacular "winners" by chance.

## 2. What is known and what is open

This uses the skeptic review's verdicts, not the scouts' first impressions.

### Known (do not claim these as new)

| What | Who | Result |
|---|---|---|
| Pre-registered luck test on Hyperliquid wallets | **Placebo** (github.com/cyberhooman/placebo, results pulled 2026-10-05) | Permutation "timing placebo" null with Benjamini-Hochberg q=0.10 on the top 500 leaderboard accounts and top 100 vaults. 4 of 216 testable accounts pass, 0 of 52 vaults pass, timing skill does not persist (Spearman rho -0.09). Hash-locked method. **This is the closest prior work and every skill project must cite it.** [S, repo read by the skeptic] |
| Small pre-registered persistence test | Dennim89/hyperliquid-copytrade-study (2026-09-25) | Leaderboard ROI rank correlation between 4-week blocks swings from -0.44 to +0.54 with market phase; NO-GO. [S] |
| Wallet "toxicity" persists | Zhai 2026, arXiv 2608.04373 | 147,113 wallets, rank correlation 0.52 between adjacent ten-day windows at the seconds horizon. Adverse selection, not luck-adjusted PnL. [S] |
| Industry skill scores | Saulius (hierarchical Bayes), Tessera (decile transitions), HyperDash, Graph Advocate | No significance testing, no FDR. [S] |
| Wallet-type labels | Arrakis (HIP-3 and Trade.xyz, 79,622 wallets) | Maker, HFT, arbitrage, retail labels from maker share, tif, cancels. About 70% left unclassified. [S] |
| Luck vs skill on Polymarket | Gomez-Cram, Guo, Jensen, Kung (SSRN 6687418) | Sign-randomization: about 3% skilled; 44% of them stay skilled out of sample. [S] |
| pump.fun creators and snipers | SBFC 2025 paper | Creators (19.2%) and snipers (16.0%) are over-represented among wallets with significant PnL t-stats. So "nobody tests luck on launches" is wrong. [S] |
| Rug-pull classifiers elsewhere | MemeTrans, Catching the Rug, TON study, Mazorra et al. | Exist for Uniswap, Solana, TON. None for HyperCore. [S] |
| Incidents | Journalism | JELLY (2025-03-26), XPL pre-market (2025-08-26), POPCAT (2025-11-12), FARTCOIN (2026-04-08), XPL (2026-11-01). Press numbers conflict, often by 2x. [S, partly V] |

### Open (where this repo can add something)

1. **Full-universe, PnL-based luck test with a proper null.** Placebo covers the top 500 and
   tests timing only. Nobody has run KTWW bootstrap + Barras-Scaillet-Wermers FDR on dollar
   PnL across a frozen, survivorship-aware cohort, with deposits netted out and one-person
   multi-wallet entities merged, and then checked persistence on a genuinely future window.
   Verdict: **partly done**, but the increment is clear and defensible.
2. **HIP-1 launch census.** No survival study of Hyperliquid spot tokens found. Verdict: **open**.
3. **Incident catalogue rebuilt from on-chain records**, with signing-time evidence (withdrawal
   nonces) and a press-vs-chain reconciliation. Verdict: **partly done** (journalism only).
4. **Repeat-winner persistence across launches** with FDR, on Hyperliquid. Verdict: **open**
   (the pump.fun work tests significance, not persistence across launches).
5. **Early-warning classifier for HIP-1 collapse.** Verdict: **open**, but the sample is small.

### Claims from the scouts that turned out wrong or overstated

- "Fill history is capped at 10,000 fills." **False as stated.** The skeptic retrieved 66,754,
  67,046 and at least 160,000 fills for three wallets. Best current hypothesis: retention is
  about 10,000 *orders* (distinct `oid`), not fills, so heavy bots lose history within hours
  while most retail wallets are complete. Treat this as a hypothesis to test. [V partly, I]
- "Only 15% of wallets are positive this month." Misleading: 58.7% of leaderboard rows have
  exactly zero monthly PnL. Of wallets with non-zero monthly PnL, 37.3% are positive. [V]
- "`portfolio` gives weekly returns." It gives **irregular** points: around weekly for many
  wallets' `allTime`, but some wallets have hourly gaps early on. Resolution varies by wallet. [V]
- "`tokenDetails` covers every token." It fails (HTTP 500 or null) for roughly 30 to 40% of
  tokens, clustered in mid-2025 deployments, and 820 token indices are absent from `spotMeta`. [V]
- "Historical open interest can show warning signs before delistings." **Not free.** Historical
  asset contexts live in requester-pays S3. OI features only exist if you record them from now. [V]
- "The 56 delisted perps are a memecoin event set." About 15 to 20 are memecoins; the rest are
  rebrands (MATIC, RNDR, FTM, MKR) and illiquid cleanups. [V]
- Power arithmetic: a Bonferroni 5% threshold over 48,000 wallets needs |t| of about 4.75
  (one-sided) to 4.88 (two-sided), not 4.6. Since t is roughly annualized Sharpe times the
  square root of years, that needs a Sharpe of about 4.75 over 1 year or about 2.1 over 5
  years. Hardly any wallet will clear it alone. Hence FDR, shrinkage and out-of-sample tests. [V]

## 3. Free data in one page

Full reference with curl examples is in `DATA.md`. All of this was probed live on 2026-11-19.

| Source | What you get | Key limit |
|---|---|---|
| `GET stats-data.hyperliquid.xyz/Mainnet/leaderboard` | ~48.2k wallets (count changes daily), 39 MB JSON: accountValue, pnl/roi/vlm for day, week, month, allTime | One snapshot, no history, inclusion rule undocumented, totals sometimes disagree with per-wallet endpoints. **Archive it daily from day 1.** |
| `GET stats-data.hyperliquid.xyz/Mainnet/vaults` | 9,478 vaults (6,432 closed), leader, TVL, create time | Undocumented; snapshot it. |
| `POST /info portfolio` | Equity and cumulative PnL curve per wallet back to account start | Irregular spacing (often ~weekly for allTime). Weight 20. |
| `POST /info userNonFundingLedgerUpdates` | Deposits, withdrawals, sends, vault flows, **liquidations** | 2,000 rows per call. Needed to net out flows. |
| `POST /info userFillsByTime` | Fills with closedPnl, fee, crossed (taker flag), startPosition, optional liquidation object | 2,000 per page, page forward only. Retention cut for very active wallets (see above). |
| `POST /info candleSnapshot` | OHLCV plus trade count `n` | Most recent 5,000 bars per interval. 1d reaches listing; 1h ~7 months; 1m ~3.5 days. Delisted coins keep their last 5,000 bars. |
| `POST /info fundingHistory` | Hourly funding per perp back to 2023-05-12 | 500 rows per call. |
| `POST /info tokenDetails` | Per HIP-1 token: deployer, deployTime, deployGas, seededUsdc, genesis balances | ~30 to 40% of tokens fail. |
| `POST /info meta`, `spotMeta`, `perpDexs` | Universe lists; `isDelisted` flag for perps | No delisting timestamp. |
| Websocket `trades` | Every trade with `users: [buyer, seller]` | Forward only. ~3M main-perp trades/day, ~150 MB/day as zstd Parquet. |

Rate limit: documented 1,200 weight per minute per IP, fill endpoints add weight per 20 items.
In practice the limit looked looser (34 full pages in 20 s, no 429), but pace at about 70% of
the documented budget anyway and measure.

**Costs money (do not use without saying so):** S3 `hl-mainnet-node-data` and
`hyperliquid-archive` (requester-pays; about 295 GB of `node_fills_by_block`, roughly $27 of
AWS egress); Dune Hyperliquid tables (enterprise); Allium (enterprise); Hydromancer (~$300/mo);
GoldRush (paid credits); Nansen (paid).

**Unverified free bulk source:** SQD portal `hyperliquid-fills` (claims free for development,
no key). Starts at block 750,000,000, about 2025-10-01 (so it misses JELLY). It drops the
`liquidation` field. Blocked from this machine; test from your laptop.

## 4. Ranked projects

Effort is in focused working days for one person, after the data recorder is running.

### Project 1 (flagship): A luck-adjusted Hyperliquid leaderboard

- **Question.** In a cohort of wallets frozen before outcomes are known, how many winners would
  luck alone produce, what share shows real skill (FDR), and does the statistically skilled set
  beat the PnL-ranked set on a future window?
- **Data (free).** Frozen leaderboard snapshot (hashed) plus addresses seen on the websocket in
  week 0; `portfolio` for each wallet; `userNonFundingLedgerUpdates` for flows;
  `userFillsByTime` for a stratified subsample of ~3,000 to 5,000 wallets; `subAccounts` and
  `userRole` to merge entities and separate vaults; BTC/ETH candles and funding for benchmarks;
  HLP vault series as an investable benchmark.
- **Method.**
  1. Freeze the universe at a formation date. Keep wallets that later die; a liquidation to
     zero is -100%, not missing data.
  2. Build flow-adjusted returns: return = change in cumulative PnL / prior equity (pnlHistory
     already excludes deposits), checked against the ledger. Report dollar PnL too.
  3. Benchmark ladder: raw, then BTC perp including funding, then an investable projection on
     BTC, ETH, a volume-weighted perp index and HLP, then a factor model. Report how the
     "skilled share" shrinks at each rung.
  4. Luck nulls: (a) Fama-French style bootstrap resampling whole weeks jointly across all
     wallets (keeps common shocks like 2025-10-10); (b) sign-randomization on each sampled
     wallet's trades (Gomez-Cram et al.), which leverage does not affect.
  5. Barras-Scaillet-Wermers pi0 for the skilled share, plus Harvey-Liu for missed discoveries.
     Use bootstrap-t or analytic tail p-values: a permutation p-value has floor 1/(B+1), so with
     m = 48,000 tests at q = 0.10 you need B above m/q = 480,000 draws (the trap Placebo hit).
  6. Merge wallets into entities (sub-accounts, shared funding addresses) and rerun.
  7. Out-of-sample: the plan is hash-locked before the test window exists; then compare
     top-q-value wallets against top-PnL wallets and an elastic-net baseline.
- **ML?** Not in the core test. ML enters via Project 4 (prediction) and entity clustering.
- **Novelty verdict.** Partly done (Placebo, Saulius, Tessera). New: full frozen cohort, PnL
  alpha with investable benchmarks, entity merging, future window, correct p-value floors.
- **Effort.** 10 days, plus 4 to 8 weeks of calendar time waiting for the forward window.
- **First step.** Download today's leaderboard, sha256 it, and pull `portfolio` plus ledger
  for a random 200 wallets to measure point spacing, missing data and API cost per wallet.

### Project 2 (memecoin sub-project): HIP-1 launch census, survival and "who gets the supply"

- **Question.** What fraction of Hyperliquid spot tokens collapse, how fast, and do launch-time
  facts (deploy gas paid, genesis concentration, seeded liquidity, deployer history, deployer
  fee share) predict it? Who receives value: deployer (via genesis supply and the default 100%
  deployer trading-fee share), genesis holders, or early buyers?
- **Data (free).** `spotMeta` (518 tokens, 353 pairs), `tokenDetails` for every tokenId,
  daily `candleSnapshot` for every `@N` pair, `spotMetaAndAssetCtxs`, deployer and genesis
  wallets' ledgers and fills.
- **Method.** Pre-register the collapse label first, for example: close below 10% of the peak,
  peak measured after the first 72 hours (to skip opening wicks), and 30-day average notional
  under $1k. Exclude bridged assets (UBTC, UETH, USOL) and stablecoins with a hand list.
  Kaplan-Meier survival by cohort, then a Cox model. Convert gas to USD at deploy date (USDC
  until 2025-05-22, HYPE after). Report the tokenDetails failure set and the 820 missing token
  indices as a selection problem, not a footnote.
- **ML?** Optional; the classifier version is Project 5.
- **Novelty verdict.** Open (only descriptive dashboards: ASXN, hl.eco).
- **Effort.** 4 days.
- **First step.** Crawl `tokenDetails` for all 518 tokenIds at under 1 request per second with
  retries, and record which fail and with which status code.

A preview already exists: of 40 tokens deployed Dec 2024 to Feb 2025 (the post-airdrop gas
mania, GOD paid 975,747 USDC on 2024-12-16), 39 trade below 10% of peak and the median is at
0.23% of peak [V]. Check the denominator before quoting it.

### Project 3 (memecoin sub-project): Incident and delisting catalogue from on-chain records

- **Question.** For each manipulation or HLP-loss incident and each delisting, what exactly
  happened (timestamps, notionals, who absorbed losses, who was paid), using only free data?
  Which delistings were collapses rather than rebrands or cleanups?
- **Data (free).** `userNonFundingLedgerUpdates` (liquidation records, withdrawal nonces give
  signing time), `userFillsByTime` of HLP Liquidator vaults (the `liquidation` object lists
  every wallet HLP took over), 1m candles of delisted coins, `meta.isDelisted`, the leaderboard
  to resolve shortened addresses quoted in the press.
- **Method.** One script per event that rebuilds it from raw, hashed API responses. Hand-code
  each of the 56 delisted perps as rebrand, illiquid cleanup or collapse/manipulation and hash
  the labels before any outcome analysis. Report a press-vs-chain reconciliation table. Already
  reconstructed by the deep dive: JELLY short account withdrew margin 2.7 minutes before its
  liquidation; POPCAT pushed 40 freshly funded accounts into HLP between 15:51:56 and 15:52:16
  UTC; FARTCOIN (2026-04-08) and XPL (2026-11-01) are additional incidents. "TST" and the "HYPE
  buy-wall" are not separate HLP incidents (the second is a mislabel of POPCAT).
- **ML?** No. About 5 positive events is a case study, not a training set.
- **Novelty verdict.** Partly done (journalism, rekt.news); a reproducible on-chain catalogue
  is new.
- **Effort.** 3 to 4 days.
- **First step.** Re-run the JELLY reconstruction (account `0xde9593fe...5c91`, Liquidator
  `0x2e3d94f0...dd14`) and save the raw JSON with hashes.
- **Ethics.** Describe accounts by behaviour, not identity. Do not repeat press attributions to
  named people.

### Project 4 (ML): Does a pre-registered model pick future winners better than past PnL?

- **Question.** Using only features known at time t, does a model choose wallets whose next
  4-week flow-adjusted returns beat (a) past-PnL rank, (b) an elastic-net model, (c) Bayesian
  shrinkage, and (d) a permutation null, on a window that did not exist when the plan was locked?
- **Data.** The Project 1 panel plus fill-based features for the subsample.
- **Method.** Wallet-type clustering first (maker share, turnover, holding time, memecoin share),
  then gradient boosting against elastic net. Walk-forward with a purge gap, folds split by
  entity. Details in `ML_IDEAS.md`.
- **ML?** Yes, this is the main ML piece.
- **Novelty verdict.** Partly done (Saulius single walk-forward; Placebo found no persistence,
  which is the prior). The fund literature (Kaniel et al. 2023; DeMiguel et al. 2023; the
  Fausch et al. 2025 correction) says elastic net is the bar to beat, not past PnL.
- **Effort.** 7 days after Project 1 data exists.
- **First step.** Write the feature list and the purge rule into the pre-registration now.

### Project 5 (ML): Early-warning classifier for HIP-1 collapse

- **Question.** Using only deploy-time facts and the first 24 to 72 hours, can we rank new
  tokens by collapse risk better than one rule ("top genesis holder above 50%")?
- **Data.** Project 2 dataset; for new launches, websocket trades (buyer concentration, wallet
  age, share of volume from deployer-funded wallets).
- **Method.** L1 logistic regression first, shallow gradient boosting second, time-ordered split
  (train on 2024 deploys, test 2025 to 2026), bootstrap confidence intervals, calibration plot,
  precision at a fixed alert rate. About 300 to 360 usable tokens, so keep models small.
- **ML?** Yes.
- **Novelty verdict.** Open for HyperCore; templates exist on Solana and Uniswap.
- **Effort.** 4 to 5 days after Project 2.
- **First step.** Freeze the label definition and feature cutoff time in the pre-registration.

### Does this project have machine learning in it?

Yes, in three honest places, none of which is the headline:

1. **Prediction** (Project 4): can a fixed model pick who keeps winning? This is the most
   impressive ML piece because it answers the guiding question directly.
2. **Structure** (inside Projects 1 and 4): clustering wallets into types, and linking wallets
   that belong to one person. Both change the skill count.
3. **Detection** (Project 5): early warning for memecoin collapse.

The headline luck test itself is statistics (bootstrap, permutation, FDR). ML misleads when it
is scored against labels defined with hindsight, so every ML piece is pre-registered,
time-split, and compared with a plain regularized linear baseline.

## 5. Risks and pitfalls

1. **Survivorship.** The leaderboard is a current snapshot with an unknown inclusion rule. In
   one 90-second sample only about 22% of live trading addresses were in it (unverified, repeat
   it). Freeze the cohort before outcomes, include dead wallets, and add websocket addresses.
2. **Censored fill history.** Heavy wallets (often the most skilled) lose old fills. Record each
   wallet's earliest retrievable fill as a left-censoring date. Do not build the main sample
   from "wallets with complete fills".
3. **Deposits and withdrawals.** Raw accountValue changes mix flows with PnL. Use pnlHistory
   and the ledger. Watch spot, vault and staking balances: the top leaderboard wallet shows
   $109.4M accountValue but $1.64M in `clearinghouseState`.
4. **One person, many wallets.** Splitting opposite bets across wallets manufactures a lucky
   winner. Merge by `subAccounts`, shared funding and correlated timing. Note that the actors
   who most want to hide (POPCAT's linked wallets) do not use declared sub-accounts.
5. **Low power and p-value floors.** Most wallets have under a year of data. Use FDR and
   shrinkage; size permutation draws to B > m/q, or use analytic tails.
6. **Common shocks.** Days like 2025-10-10 move every wallet at once. Resample whole dates.
7. **Leverage.** Raw return alpha scales with leverage. Prefer t-stats, sign-randomization and
   dollar value added.
8. **Short-option payoffs.** Wallets that sell volatility or harvest liquidations look skilled
   until the blow-up. Use HLP as a benchmark and report skewness and drawdown.
9. **HIP-3 and spot.** 10 builder dexes exist. Check whether `portfolio` and the leaderboard
   include HIP-3 and spot PnL before attributing returns.
10. **Labels with hindsight.** "Rug" has no official definition; the 97%-of-Uniswap-tokens
    dispute shows definitions drive results. Lock labels before looking.
11. **Data that is not free.** Historical OI, order books and full fills cost money. Plan around
    forward recording, and say so explicitly if any paid source is ever used.
12. **Undocumented endpoints change.** stats-data files and retention rules can change without
    notice. Snapshot and hash everything.
13. **Unverified literature.** Many 2025 to 2026 sources are [S]. Read before citing.
14. **Ethics and defamation.** Publish aggregates and q-values. Never label a named wallet as
    unskilled, suspicious or a scammer. Placebo writes `isSkilled(address)` on-chain; do not
    copy that.

## 6. Start here tomorrow

1. **Start the recorders before anything else** (history lost to retention is gone for good).
   A small script that, every day, downloads `/Mainnet/leaderboard` and `/Mainnet/vaults`,
   gzips them and writes their sha256 to a log. A second long-running process that subscribes
   to websocket `trades` for all live perps and spot pairs, plus `metaAndAssetCtxs` every 5
   minutes (open interest is only free going forward). Store under `data/` (git-ignored).
2. **Freeze the cohort.** Save today's leaderboard as the formation snapshot, record its hash,
   and decide the stratified sample (for example all wallets with allTime volume above $1M plus
   a random 2,000 of the rest).
3. **Run the 200-wallet pilot.** Pull `portfolio`, `userNonFundingLedgerUpdates` and
   `userFillsByTime` for 200 random cohort wallets. Measure: point spacing, how many are
   complete back to first deposit, oids at the cut-off (tests the 10k-orders hypothesis),
   weight actually consumed, and how often accountValue disagrees with the leaderboard.
4. **Write and hash-lock the Project 1 pre-registration** (`research/hyperliquid/prereg_p1.md`):
   universe rule, return definition, benchmark ladder, nulls, B, FDR level, entity rule, test
   window dates, and the stated prior from Placebo (no persistence). Commit the hash before
   the test window opens.
5. **Crawl the HIP-1 census** (`spotMeta`, all `tokenDetails` with retries, daily `@N`
   candles) and draft the Project 2 label definition, then lock it before computing survival.

Also: try `portal.sqd.dev` from your own laptop once. If it works, it removes most of the
fill-retention problem from 2025-10 onward.
