# Liquidation cascades: does the market warn you before it breaks?

Status: literature and data review done (2026-11-20). P1 pre-registration, mask v2 and metrics
screen reviewed and locked (2026-11-22); the full P1 scan is running.
Everything numeric below that comes from our own probes is exploratory: it was seen before any plan
was locked, and every pre-registration must say so.

Companion files in this folder:

| File | Contents |
|---|---|
| [LITERATURE.md](LITERATURE.md) | Annotated references by topic, with what each means for this project and its verification status |
| [DATA.md](DATA.md) | Every relevant free file: schema, frequency, coverage, size, known glitches, example URL |
| [EVENT_DEFINITION_DRAFT.md](EVENT_DEFINITION_DRAFT.md) | DRAFT cascade definition and matched control periods |
| [ML_IDEAS.md](ML_IDEAS.md) | Early-warning models: features, labels, rare-event validation, baselines |
| [bookdepth_mask_v1_DRAFT.txt](bookdepth_mask_v1_DRAFT.txt) | Drafted bookDepth quality mask, sha256 `61d003375266604e95b2d9ff66149b9f39d0eb03862c8a779f566c6abc4513f7` (committed unchanged in 69ebe50; approval pending in PREREGISTRATION_P1.md) |
| [bookdepth_mask_v2.txt](bookdepth_mask_v2.txt) | Primary mask: v1 except that isolated crossings (1 or 2 snapshots) get no 10-minute buffer |
| [metrics_screen_v1.txt](metrics_screen_v1.txt) | Metrics screen (spike-and-reverse, ghost rows, per-file label convention), locked |
| [PREREGISTRATION_P1.md](PREREGISTRATION_P1.md) | Locked P1 plan: scope, interpretation notes, onset test T1, review decisions |
| [p1_scan.py](p1_scan.py) | P1 scanner; refuses to run until the plan is hashed. Library code in `src/microstructure/quality/` |
| [data/p1/](data/p1/) | `universe.csv` (scope) and `validation.md` (acceptance checks run before locking) |

## 1. The question

Crypto perpetual futures let traders borrow heavily. When the price moves against a leveraged
position, the exchange closes it by force. That forced selling pushes the price further and can
liquidate the next trader: a cascade. On 10 October 2025 the BTCUSDT mark price fell from about
117,800 (17:40 UTC) to 101,877.7 (21:20 UTC), and BTCUSDT open interest (OI) fell from 96,714 BTC at
00:00 to 72,613 BTC at 23:55 (-24.9%).

Two questions:

1. **Is there a warning?** In the hours before a cascade, do order books thin, does leveraged
   positioning become one-sided, and does order flow keep pushing the same way, by more than plain
   volatility and volume would predict?
2. **Where does it hurt?** Across contracts hit by the same market-wide shock, do crashes run deeper
   where leverage was higher, and does book depth come back more slowly where orders are sliced more?

## 2. Why it matters

- The closest prior work (two 2026 arXiv preprints, see LITERATURE.md section 1, not yet read in
  full) studies about seven hand-picked BTC events. Conclusions from N = 7 cannot separate "no warning
  exists" from "no power".
- The main repo has already measured, per contract, the variables theory says should matter:
  trade-sign memory, Hawkes branching (about 70% of trades are reactions), order slicing (median trade
  size fell about two thirds, 1.83 log points on 136 survivors), and 35 tick-change batches as natural
  experiments. Linking them to fragility is new.
- Practical: exchanges, market makers and risk managers want to know whether fragility can be seen
  before the break, or only during it.

## 3. What is known and what is open

Verdicts are the novelty reviewer's, not the scouts'.

| Claim or question | What we know | Verdict |
|---|---|---|
| Theory predicts liquidity spirals, leverage cycles, fire-sale discounts and reversals, endogenous correlation, predatory selling | Brunnermeier and Pedersen 2009, Geanakoplos 2010, Shleifer and Vishny 1992, Cont and Wagalath 2016, Brunnermeier and Pedersen 2005 | Known (theory) |
| Early-warning signals before crypto cascades | Repo notes on arXiv 2607.27070 say a critical-slowing-down signal appears in 5 of 7 BTC events and not in the two tariff-news shocks, i.e. event-specific, not absent. Unread in full | Partly done, unverified |
| Pre-event leverage grades crash severity | Repo notes on arXiv 2608.03616 (Hyperliquid) say no scalar pre-state grades severity. Unread | Partly done; a Binance cross-section over many episodes is open |
| VPIN-style order-flow warnings | Andersen and Bondarenko 2014: VPIN's content is mostly mechanical via volume; Abad et al. 2018: weak after volatility controls | Known negative; any new signal must beat a volume plus volatility baseline |
| Depth recovery after a cascade | Lim SSRN 6636998 (Hyperliquid, one event): spreads recover within a day, depth stays low for weeks. Unverified | Partly done; Binance and many contracts open |
| Order slicing versus depth resilience | No prior test found (theory: Foucault, Kadan and Kandel 2005; Obizhaeva and Wang 2013) | Open |
| Free USDT-M liquidation history | Does not exist; COIN-M liquidationSnapshot only, 2023-06-25 to 2024-10-14 | Known constraint |
| Validated free liquidation proxy | Our COIN-M probe: volume AUC 0.95 to 0.96, 5-min OI drop 0.60 to 0.65; aggTrades ID gaps perfectly specific but 12.5% sensitive. Not published anywhere we found | Open |
| bookDepth data quality | GitHub binance-public-data issues #431 and #496 report single episodes; no systematic screen published. Our scan found five large episodes, two of them market-wide | Partly done (issues), full mask open |
| Margin spiral "muted" on Binance because brackets are fixed | Refuted as stated: on 10-10 collateral (USDe, wBETH, BNSOL) was valued on Binance's own books, which is a margin channel even with fixed brackets | Treat margin channel as live |
| 2025-10-10 as a pure exogenous shock | Refuted as stated: two Trump posts (14:57:52Z and 20:50:01Z) with a build-up between them (long/short account ratio 1.048 at 16:00 to 1.274 at 19:00) | Mixed event; pre-register as its own class |

## 4. Free data, exact files

Full details in [DATA.md](DATA.md). All are free. The only paid sources we met are Hyperliquid's
requester-pays S3 buckets (`s3://hyperliquid-archive`, `s3://hl-mainnet-node-data`, about USD 27
egress for node fills) and CoinGlass-type APIs; this project uses neither.

| Need | File (data.binance.vision) | Coverage | Caveat |
|---|---|---|---|
| Depth within plus or minus 1 to 5% | `futures/um/daily/bookDepth/<SYM>/<SYM>-bookDepth-YYYY-MM-DD.zip` | 2023-01-01 to 2026-11-18, about 30 s | Five corrupted episodes; mask first |
| OI, long/short ratios, taker ratio | `futures/um/daily/metrics/<SYM>/<SYM>-metrics-YYYY-MM-DD.zip` | BTC from 2020-09-01, 5 min | Label convention changed 2026-06-25 (issue #491); spike-and-reverse rows; files rewritten |
| Exact-sign trades | `futures/um/daily/aggTrades/...` | 2020 onward | Excludes insurance-fund and ADL trades by design; use instead of `trades` |
| Prices that trigger liquidations | `markPriceKlines`, `indexPriceKlines`, `premiumIndexKlines`, `klines` (1m) | 2019/2020 onward | Mark is a smoothed composite |
| Funding | `futures/um/monthly/fundingRate/...` | monthly files | Interval differs by symbol |
| Liquidation ground truth | `futures/cm/daily/liquidationSnapshot/<SYM>/...` | 2023-06-25 to 2024-10-14, 118 COIN-M contracts | Every row twice; 1 per symbol-second throttle; outage days |
| Wallet-level liquidations | `api.hyperliquid.xyz/info` (`userFillsByTime`, `userNonFundingLedgerUpdates`) | partial | Fill retention left-censors 2025-10-10 at 21:33:26 UTC |

## 5. Ranked projects

Ranking weighs: is it open, can free data answer it, and does it unblock the others. About 25 scout
ideas were near-duplicates and are merged into five.

### P1. Data foundation: bookDepth mask and metrics screen (do first)

- **Question.** Which contract-snapshots of bookDepth and which metrics rows are corrupted, and are
  the corruptions triggered by price moves?
- **Data.** bookDepth for 905 USDT perps (534,084 contract-days, about 240 GB, stream and discard),
  metrics (about 11 KB per day), 1m klines.
- **Method.** Apply the drafted mask v1 (rules S0 to S6, calendar exclusions X1 to X6, day rules D1
  to D5): crossed book (VWAP of inner bid band at or above inner ask), whole-book repeats of 3 or more,
  a band frozen for 20 or more snapshots, implied mid outside the 1m kline range by 2%. Flag on
  implied price, not exact depth equality: the BTCUSDT ghost bid showed 17.652 BTC from 15:30:42
  and the exact 17.654 only from 19:12:30 (-2% band) and 19:15:32 (-1%). For metrics, flag
  |dOI| > 3 x rolling 2-hour median |dOI| reversed within 10% next row (28 such points in 10 symbols
  over 9 to 12 Oct 2025). Then test whether onsets follow same-direction returns (percentile test
  against matched placebo times).
- **ML.** No.
- **Novelty verdict.** Partly done (GitHub issues #431, #496, #512 describe single episodes); the full
  ledger and the onset test are open.
- **Effort.** 3 to 5 days (scanner already about 22% through).
- **What you learn.** Which depth and OI data can be trusted, and whether masking is missing-not-at-
  random. Early evidence says it is: in Oct 2025, 68 bid-side onsets followed a median prior 1-hour
  return of -2.57% (99% negative); 55 ask-side onsets followed +0.84% (95% positive).
- **First step.** Commit `bookdepth_mask_v1_DRAFT.txt` unchanged (hash above), then resume the scanner.

### P2. Liquidation proxy validation and a locked cascade catalogue

- **Question.** Which free signal best tracks forced closures, at which horizon, and what event list
  does a locked rule produce for 2023-01 to 2026-11?
- **Data.** COIN-M liquidationSnapshot (45 perps, deduplicated, outage days masked), COIN-M metrics
  (missing 2024-03-04 to about 2024-06-08), COIN-M and USDT-M aggTrades and klines.
- **Method.** Lock the proxy list (absolute return, quote volume, taker imbalance, OI drop summed
  over 5m to 4h, aggTrades ID gaps), horizons, top-1% and top-0.1% targets and the split (train before
  2024-03-01, test after) before running; report AUC, precision at k, incremental R2. Because our
  probe already saw these numbers, also hold out a set of symbols that nobody has looked at. Build a
  USDT-M baseline for ID gaps (a background of single-ID gaps appears from about 2024-11 and steps
  up on 2025-08-06 about 15:00 UTC on LINKUSDT).
- **ML.** No (logistic and rank statistics).
- **Novelty verdict.** Open.
- **Effort.** 4 to 6 days.
- **What you learn.** Whether a cheap proxy exists and at what horizon; how many independent
  market-wide episodes there are, which sets the power of everything else.
- **First step.** Deduplicate all 17,182 COIN-M snapshot files and write the outage-day mask
  (2023-09-25 all symbols; BTCUSD_PERP 2024-06-11 and 06-12).

### P3. Leverage and crash depth across contracts on market-wide episodes

- **Question.** On each market-wide episode, do contracts with higher pre-event leverage (OI value over
  30-day volume, OI over depth at -2%, funding premium, top-trader position ratio) fall further on the
  mark price, after BTC beta?
- **Data.** metrics, bookDepth (masked), fundingRate, premiumIndexKlines, mark and index 1m klines.
- **Method.** Per-episode cross-section, then Fama-MacBeth across episodes:
  `DD_i = a + b log(OI_i / V_i) + c beta_i + d log depth2_i + e`, regressors dated before t0 - 1h,
  every live contract included (no truncation on the outcome), outcome on mark price, plus
  NCSKEW/DUVOL (Chen, Hong and Stein 2001). Drop contracts with tick changes within 48 h (8 contracts
  around 2025-10-08 and 10-10). Inference counts episodes, not contracts.
- **ML.** No.
- **Novelty verdict.** Partly done (Hyperliquid N = 7 negative result in repo notes, unverified).
- **Effort.** 6 days.
- **What you learn.** Whether leverage is the fuel in the cross-section even if it is not a timing
  signal.
- **First step.** From P2's catalogue, list episodes and check each for depth artifacts.
  2024-08-05, 2025-02-03 and 2025-04-07 are clean; on 2025-10-10 about 45% of contracts fail the mask.

### P4. Depth resilience half-life and order slicing

- **Question.** Does depth within plus or minus 1% recover more slowly after shocks in contract-months
  with more slicing, holding activity fixed and within contract?
- **Data.** bookDepth (masked) for the 432 contract-months in the repo's
  `research/market_evolution/data/proxies_cross_section.parquet`, 1m klines.
- **Method.** Shocks defined on price only (|1m return| > 5 x trailing MAD), never on the depth path.
  Fit `log D(t) - log D_pre = -A exp(-rho t)`, report half-life ln2/rho, censored at 6 h. Regress log
  half-life on log median notional and log event count; contract fixed effects across 2023-06 and
  2026-07. The 30 s snapshot grid cannot resolve sub-minute recovery.
- **ML.** No.
- **Novelty verdict.** Open.
- **Effort.** 7 to 8 days.
- **What you learn.** Whether the two-thirds fall in trade size made the market more or less resilient.
- **First step.** Pull bookDepth for 10 contract-months and check snapshot coverage after masking.

### P5. Pre-registered warning test with an alarm budget

- **Question.** Do depth thinning, OI build-up, funding, taker-imbalance persistence, Hawkes n and
  sign memory raise event recall at a fixed alarm budget above a volatility plus volume baseline, on
  periods the model never saw?
- **Data.** All of the above for the 50 to 100 most liquid perps; event list from P2; mask from P1.
- **Method.** See [ML_IDEAS.md](ML_IDEAS.md): stacked event study against matched calm windows, then
  walk-forward logit and monotone LightGBM, purged and embargoed, scored by Molchan diagram, recall at
  2% alarm time, lead time, PR-AUC next to base rate, block bootstrap by episode, endogenous and news
  classes reported separately. Include a VPIN-style timing audit (does each signal peak before or after
  onset once volume is partialled out?).
- **ML.** Yes, against a non-ML baseline.
- **Novelty verdict.** Partly done (7-event studies; VPIN literature). The panel, the mask and the
  alarm-budget scoring are the contribution.
- **Effort.** 10 to 15 days.
- **What you learn.** Whether any warning beats "volatility is already high". The likely answer is
  modest skill on build-up events and none on news shocks.
- **First step.** Only after P1 and P2 are locked: freeze the feature list and the lockbox period
  (from 2026-07).

Dropped or deferred: liquidation-band predatory-flow tests (liquidation prices not identified from free
data), Hyperliquid wallet panels for 10-10 (survivorship and retention bias), hourly cross-venue lead
and lag (Hyperliquid premium is hourly, cascades last minutes), Cont-Wagalath fire-sale forensics
(needs per-contract liquidation volumes), forward recorders (infrastructure; worth starting but yields
nothing until future events).

## 6. Risks

- **Few independent events.** Perhaps 5 to 15 market-wide episodes from 2023 to 2026. Hundreds of
  contracts per episode do not add independent observations for the timing question.
- **The flagship event is the dirtiest.** On 2025-10-10 the stale-bid artifact begins at 15:30:42 UTC
  for BTC (15:30:06 ETH, 15:31:03 SOL, 15:32:02 DOGE), market-wide from about 2025-10-09 09:00 UTC,
  98% of contracts in the 21:00 crash hour, ending at 2025-10-15 13:12:02. Any "depth vanished before
  the crash" result on raw data is an artifact.
- **Masking is endogenous.** Onsets follow same-direction moves, so dropping masked data biases toward
  calm periods, and keeping it fakes a collapse.
- **Proxy labels.** No USDT-M ground truth; the 5-minute OI drop is a poor timer, and on 10-10 the
  Binance OI decline lagged Hyperliquid liquidations by 20 to 50 minutes in one deep dive, while the
  novelty reviewer saw the largest BTCUSDT OI drop at the 21:15 label with the mark low at 21:20.
  Pre-register the OI timing convention and do not assume a lag.
- **Circularity.** If events are defined by volume or OI, those variables cannot also be warning
  features measured inside the event window. Event legs are measured at or after t0; warnings strictly
  before t0 - g; the baseline always includes pre-window volume and volatility.
- **Mutable archive.** The 2025-10-10 BTCUSDT metrics CSV has an mtime of 2026-08-07; 49 COIN-M
  snapshot files were re-uploaded on 2026-04-16. Hash every file and record download dates.
- **Literature unread.** arxiv.org, papers.ssrn.com and developers.binance.com were unreachable from
  every agent this round. Novelty claims rest on repo notes for the 2025 to 2026 preprints.

## 7. Start here

- [ ] Allow arxiv.org, export.arxiv.org, papers.ssrn.com and developers.binance.com in the
      environment's network settings, then read arXiv 2607.27070, 2608.03616, 2512.01112, 2602.15182,
      2603.09164, 2603.15963 and SSRN 6579278, 6636998 in full. Resolve the ADL figure conflict for
      2512.01112 (USD 45.0M to 51.7M versus 0.66 to 2.1B in repo notes) and the data-source conflict
      for 2608.03616 (Hyperliquid or Binance).
- [x] Commit `bookdepth_mask_v1_DRAFT.txt` unchanged and record its hash in the pre-registration log.
      State that the calendar exclusions were chosen from artifact data, not outcome data.
- [x] Write the metrics screen (spike-and-reverse, missing rows, label convention). Finding: the
      label convention follows whether Binance rewrote the file, not the 2026-06-25 date, so it
      is decided per file (rule M5).
- [x] Review PREREGISTRATION_P1.md (open questions Q1 to Q4), lock it and the screen by hash.
- [ ] Run the full bookDepth and metrics scan (rewritten from scratch: the earlier scanner was not
      in the repo) and publish the ledger and test T1.
- [ ] Deduplicate COIN-M liquidationSnapshot, apply the outage mask, and pre-register P2 with a
      held-out symbol set.
- [ ] Fix the cascade rule in [EVENT_DEFINITION_DRAFT.md](EVENT_DEFINITION_DRAFT.md), remove "DRAFT",
      hash it, and only then compute any warning feature on event windows.
- [ ] Count independent market-wide episodes and write the power statement for P3 and P5 in terms of
      that count.
- [ ] Start free forward collectors now (insuranceBalance, symbolAdlRisk, `!forceOrder@arr`), because
      no free history of these exists.
