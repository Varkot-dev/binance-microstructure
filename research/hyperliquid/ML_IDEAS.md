# Machine learning angles, ranked

Short answer to "does this have ML in it?": **yes, but ML is not the headline.** The headline
is a statistical luck test (bootstrap, permutation, false discovery rate). ML adds value in
three roles: **prediction** (who keeps winning), **structure** (wallet types and linked
wallets) and **detection** (memecoin collapse early warning). It misleads whenever it is
scored on labels defined with hindsight or on a universe chosen with today's knowledge.

Ranking weighs how much it answers the guiding question, how impressive it is in a portfolio,
and how doable it is on free data.

## Rules that apply to every idea

1. **Pre-register and hash-lock** features, label, model family, hyperparameter grid, split
   dates and the primary metric before the test data exists. One primary specification;
   everything else is labelled exploratory.
2. **Time-ordered splits only**, with a purge gap at least as long as the label horizon.
3. **Freeze the universe at time t**, including wallets that later die or go idle.
4. **Split folds by entity** (master account and linked wallets), never by row.
5. **Baselines:** the base rate, a one-line rule, past-PnL rank, and a **regularized linear
   model (elastic net or L1 logistic)**. The Fausch et al. 2025 correction of a JFE fund-ML
   paper showed elastic net matched the fancy models once a look-ahead bug was fixed.
6. **A luck null for the model itself:** shuffle features across wallets within each date and
   refit, to get the distribution of the metric under no signal.
7. Report confidence intervals (bootstrap), calibration, and how many models were tried.

---

## Rank 1. Pre-registered skill predictor: does a model pick future winners?

- **Question.** Using features known at t, does a model select wallets whose next-period
  flow-adjusted returns beat past-PnL rank, elastic net, Bayesian shrinkage and a permutation
  null, in a window that did not exist when the plan was locked?
- **Unit.** Wallet (or merged entity) at each formation date (weekly or every 4 weeks).
- **Features (as of t only).**
  - Performance: past PnL and ROI by window, past t-stat, Sharpe, max drawdown, hit rate,
    luck-adjusted q-value from Project 1.
  - Style: maker share (`crossed=false`), rebate sign, turnover (vlm / accountValue), fills per
    hour, median holding time, `tif` mix from `historicalOrders` (Alo, Ioc, Gtc), TWAP share,
    `cloid` usage (bot signal).
  - Exposure: coin concentration (HHI), memecoin share, HIP-3 share, average leverage, net
    long/short bias, funding received share of PnL (`userFunding`).
  - Account: age, number of sub-accounts, deposit and withdrawal frequency, account value
    (log), vault leader flag (`userRole`).
  - Wallet type from Rank 2.
- **Label.** Primary: rank (or sign) of flow-adjusted return over t+1 to t+4 weeks, from
  `portfolio` pnlHistory over prior equity. Secondary: dollar value added over a BTC-with-funding
  benchmark.
- **Models.** Elastic net (primary benchmark), then LightGBM. Bayesian shrinkage (Saulius-style
  hierarchical model) as an extra baseline.
- **Validation.** Expanding-window walk-forward, purge gap = 4 weeks, entity-grouped folds.
  Final test window is genuinely in the future relative to the hash. Metrics: rank IC
  (Spearman), top-decile minus median spread, share of picks above median, and a simulated
  copy portfolio net of copy slippage. Permutation null by shuffling features within date.
  Evaluate within wallet type so "market makers win" is not mistaken for predictable skill.
- **Baselines.** Past-PnL rank, past t-stat rank, elastic net, shrinkage, random selection.
- **Prior to state.** Placebo found timing skill does not persist (rho -0.09). Expect a weak
  signal; a well-measured null is a fine result.
- **Data.** Free: `portfolio`, ledger, fills for a stratified sample. Panel must accumulate
  forward (4 to 8 weeks minimum); `month` windows give about 30 days of backfill.
- **Effort.** 7 days after the Project 1 panel exists.

## Rank 2. Wallet typology (unsupervised clustering)

- **Question.** What kinds of traders exist (market makers, HFT bots, TWAP users, directional
  whales, memecoin gamblers, retail), and does skill live in one type?
- **Features.** Maker share, rebate sign, turnover, fills per hour, median gap between fills,
  holding time, coin HHI, memecoin share, long/short balance, time-of-day entropy, `cloid` share,
  TWAP share, `tif` mix, log account value. Robust-scale, log heavy-tailed ones.
- **Method.** PCA or UMAP for pictures; Gaussian mixture or HDBSCAN for clusters.
- **Validation.** Stability across two disjoint time windows (adjusted Rand index), bootstrap
  stability, sanity anchors (HLP and known market-maker vaults must land in a maker cluster).
- **Baseline.** A 4-rule hand typology (for example maker share > 0.7 and turnover > 1,000 means
  market maker). If clusters add nothing beyond the rules, say so.
- **Prior work.** Arrakis classifier (HIP-3, 79,622 wallets, ~70% unclassified). The increment
  is main-dex coverage, stability checks and the link to luck-adjusted skill.
- **Use.** Conditioning variable for Rank 1 and Project 1.
- **Effort.** 5 days.

## Rank 3. Linked-wallet detection (one person, many wallets)

- **Question.** How many apparent skilled wallets are one entity, and how much does merging
  shrink the skill count?
- **Pair features.** Direct transfers, shared funding or withdrawal counterparties, deposit
  timing correlation, same-millisecond co-trading in the same coin and direction, daily PnL
  correlation, behavioural-feature similarity.
- **Labels.** Positives from `subAccounts` (declared master-sub pairs). `subAccounts` returns
  null for non-masters, so negatives are unlabeled: treat as positive-unlabeled learning, with
  random pairs plus hard negatives.
- **Model.** Logistic regression, then gradient boosting.
- **Validation.** Split by master account; precision at k; manual review of a sample.
- **Baseline.** Connected components of the direct-transfer graph (Victor 2020 heuristic).
- **Threat.** Label shift: declared sub-accounts behave unlike hidden ones (POPCAT's linked
  wallets were funded from one exchange withdrawal and used no sub-accounts).
- **Output.** Aggregate effect on the skilled share only. No named entity claims.
- **Effort.** 6 days.

## Rank 4. HIP-1 memecoin collapse early warning (detection, victim-avoidance)

- **Question.** Using only deploy-time facts and the first 24 to 72 hours, can we rank new spot
  tokens by risk of losing over 90% within 30 days, better than one rule?
- **Features at the cutoff.**
  - From `tokenDetails`: top-1 and top-5 genesis share (excluding `0xffff...ffff`), number of
    genesis holders, airdrop flag (`existingTokenBalances`), `seededUsdc`, deploy gas in USD at
    deploy date, `nonCirculatingUserBalances`, `futureEmissions`, freeze privilege status.
  - From `spotMeta`: `deployerTradingFeeShare`.
  - Deployer history: number of prior tokens, fate of prior tokens (as of cutoff only).
  - Early market: first-day return, range, volume and trade count `n` (1d candles; 1h only for
    launches in the last ~7 months).
  - For launches recorded by the websocket: buyer HHI, top-5 wallets' volume share, share of
    volume from wallets funded by the deployer or genesis wallets, wallet age, whether deployer
    or genesis wallets sold.
- **Label (lock first).** Day-30 close below 10% of the peak measured after the first 72 hours,
  plus a second label "genesis holders sold over 50% within 7 days". Exclude bridged assets and
  stablecoins with a hand list.
- **Models.** L1 logistic regression, then a shallow tree or small gradient boosting.
- **Validation.** Time split by deploy date (train 2024, test 2025 to 2026), bootstrap CIs,
  calibration plot, precision at a fixed alert rate.
- **Baselines.** Base rate (high: about two thirds of tokens collapse); rule "top genesis holder
  above 50%". Note the raw concentration signal points the wrong way because bridged and
  treasury tokens dominate the concentrated group.
- **Data limits.** About 300 to 360 usable tokens; `tokenDetails` fails for about 30 to 40%
  (clustered in mid-2025); 820 token indices missing from `spotMeta`. Report as selection.
- **Prior work.** MemeTrans, Catching the Rug, TON study, Mazorra et al. None on HyperCore.
- **Effort.** 4 to 5 days after the census (README Project 2).

## Rank 5. ML as the hardest benchmark (robustness rung)

- **Question.** Does wallet alpha survive a flexible model of the same exposures?
- **Method.** Fit IPCA or gradient boosting on lagged coin characteristics (momentum, funding,
  liquidity, volatility, days since listing) to predict coin returns. Benchmark return =
  predicted return on the wallet's lagged holdings (from fills). Wallet alpha = actual minus
  predicted.
- **Validation.** Time-split, pre-registered.
- **Use.** Last rung of the Project 1 benchmark ladder. Limited to wallets with reconstructable
  holdings.
- **Effort.** 6 days. Stretch goal.

## Not recommended as ML

- **Manipulation anomaly scan on thin perps.** About 3 to 5 labelled events (JELLY, POPCAT,
  FARTCOIN, two XPL episodes). Cannot be validated; historical OI is not free. Keep as case
  studies and a forward-only dashboard.
- **Fresh-wallet cluster early warning for HLP attacks.** Same small-N problem. Case study.
- **Vault picking.** Placebo found 0 of 52 top vaults beat placebo; vault closure within 90 days
  is a more promising label if attempted later.

## Common pitfalls checklist

- Universe built from today's leaderboard leaks the future.
- Deposits and top-ups distort ROI; use pnlHistory and the ledger.
- Censored fills (heavy wallets) are not missing at random.
- Many models x horizons x wallet types = multiple testing. One primary spec.
- Near-perfect accuracy in rug papers usually means post-event information in features.
- Small samples: prefer regularized linear models; gradient boosting will overfit.
- Cluster names like "bot" are interpretations, not ground truth.
- Publish aggregates; never per-address "unskilled" or "suspicious" labels.
