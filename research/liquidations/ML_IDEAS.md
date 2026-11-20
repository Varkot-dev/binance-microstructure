# Machine learning for cascade early warning

Bottom line: the binding constraint is the number of independent events, not the model. A solo
project can honestly test whether 3 to 6 interpretable, pre-registered signals beat a volatility plus
volume baseline at a fixed alarm budget. It cannot credibly train a deep model to predict individual
cascades from free Binance data.

## 1. How rare are the events?

Exploratory count (BTCUSDT 1h klines, 2023-01 to 2026-10, 33,600 hours; label = low over the next 4
bars at least k below the open, declustered to one event per 24 hours):

| Drop within 4 h | Episodes | Share of hours |
|---|---|---|
| 3% | 200 | 2.16% |
| 5% | 52 | 0.48% |
| 8% | 10 | 0.10% |

A panel of hundreds of perps adds rows but few independent events, because large cascades are
market-wide (on 2025-10-10, 98% of contracts were hit within the 21:00 UTC hour). Effective sample size
is the number of distinct market-wide clusters, likely 5 to 15 large ones for 2023 to 2026, plus
contract-specific events that are more numerous but smaller.

## 2. Labels

- Primary label: onset of an event from the locked rule in
  [EVENT_DEFINITION_DRAFT.md](EVENT_DEFINITION_DRAFT.md) within `(t + g, t + H]`, with `g = 15 min` and
  `H` in {1 h, 6 h}. Predictions are made at each contract-hour `t`.
- Secondary label: vol-scaled drawdown, `min(low over (t, t+4h]) / close_t - 1 <= -k sigma_i,t`,
  where `sigma_i,t` is trailing 30-day hourly volatility.
- Optional label for COIN-M 2023-06 to 2024-10 only: top-1% hours of deduplicated liquidationSnapshot
  notional (a lower bound, throttled at 1 per symbol-second).
- Never use the OI-drop or volume parts of the label as features inside the label window. Never use
  smoothed or forward-averaged labels of the FI-2010 or DeepLOB kind; the repo's q11 showed they are
  partly computable from the inputs.

## 3. Features (pre-registered list, all measured strictly before `t`)

Each feature is standardized within contract over a trailing 30-day window ending at `t - 6h`.

| Group | Feature | Source | Theory |
|---|---|---|---|
| Baseline | Realized volatility (1h, 6h), log quote volume (1h, 6h), BTC realized volatility | klines | Volatility clustering |
| Leverage | OI value growth over 24 h; OI value / 30-day volume; OI / depth at -2% | metrics, bookDepth | Geanakoplos 2010; Brunnermeier and Pedersen 2009 |
| Positioning | Top-trader position ratio, all-account ratio, taker buy/sell ratio | metrics | One-sided crowding |
| Carry | Premium index (1m, averaged), last funding rate, 1h-interval flag dated before the window | premiumIndexKlines, fundingRate | He et al. 2022 |
| Depth | Log depth within plus or minus 1% and 2%, bid/ask log ratio, 6h change | bookDepth after mask v1 | Donier and Bouchaud 2015 |
| Flow persistence | Sign repeat rate, share of same-sign runs of 10 or more (merged sweeps), true-sign VPIN | aggTrades | Brunnermeier and Pedersen 2005; Easley et al. 2012 |
| Impact | Slope of 1m return on signed notional | klines, aggTrades | Kyle 1985 |
| Reflexivity | Hawkes n (K = 2 sum of alphas) on equal-length windows; count-variance n | aggTrades, repo estimators | Filimonov and Sornette 2012 |
| Critical slowing down | Variance and lag-1 autocorrelation of detrended 1m returns | klines | Scheffer et al. 2009 |
| Structure | LPPLS confidence indicator at 1h scale (BTC, ETH, SOL only) | 1h klines | Shu and Zhu 2020 |

Notes:

- Depth features are missing-not-at-random (mask onsets follow same-direction moves). Use a
  "depth unavailable" indicator plus a robustness run that drops masked contract-windows entirely;
  never impute.
- Hawkes n on short stress windows is biased upward by non-stationarity (Filimonov and Sornette 2015;
  repo q6b), and 31 of 738 repo fits already sit at n = 1. Pre-register the baseline drift control as
  an exclusion rule.
- Kyle lambda from 1m klines fell in the busy hours before the 2025-10-10 crash (2.9 to 3.9 bp per 100
  BTC at 14:00 to 20:00 versus 6 to 10 in the morning) and rose after, so it is not a monotone warning.
- True-sign VPIN on 2025-10-10 rose from about 0.08 to 0.16 around 20:55 to 21:19 UTC, but that run used
  same-day volume normalization (look-ahead) and VPIN tracks volume mechanically. It is a timing-audit
  case, not evidence.

## 4. Models

1. Unconditional base rate.
2. **Baseline:** logistic regression on the baseline group only (volatility and volume).
3. L2-regularized logit on baseline plus the pre-registered theory features.
4. LightGBM with monotone constraints where theory gives a sign, refit monthly.

Do not use DeepLOB-style models: they need 10-level books (free Binance data has only percentage bands
after March 2024), predict tick-horizon mid moves, and degrade on new data (Prata et al. 2024; Briola
et al. 2025). Engineered stationary features are the better bet (Kolm, Turiel and Westray 2023). With
few rare events a regularized logit is the honest default; ML beat logit in sample but lost out of
sample in banking-crisis early warning (Beutel, List and von Schweinitz 2019).

## 5. Validation for rare, clustered events

- **Split.** Expanding-window walk-forward, monthly refit; purge and embargo of at least `H` around each
  test fold (Lopez de Prado 2018, ch. 7). Lockbox: everything from 2026-07 onward, scored once.
- **Folds by episode.** A market-wide episode never spans train and test. Report leave-one-episode-out
  results as well.
- **Metrics (all pre-registered):**
  - Molchan diagram: miss rate `nu` against fraction of contract-hours under alarm `tau`; random
    forecasts lie on `nu + tau = 1`; skill `1 - nu - tau`, plus area skill score (Zechar and Jordan
    2008).
  - Event recall at fixed alarm budgets `tau` = 1%, 2%, 5%.
  - Alarm precision: alarms followed by an onset within `H`, over all alarms.
  - Lead time: onset minus first alarm in `[t0 - H, t0 - g]`, median and IQR.
  - PR-AUC reported next to the base rate (Saito and Rehmsmeier 2015); ROC-AUC only as secondary.
  - Brier score and reliability curve.
  - Noise-to-signal ratio per single indicator (Kaminsky, Lizondo and Reinhart 1998).
- **Uncertainty.** Block bootstrap over market-wide episodes (or UTC days); state `E`, the number of
  independent episodes in each fold.
- **Overfitting.** Small pre-declared hyperparameter grid; report the probability of backtest
  overfitting via CSCV (Bailey et al. 2017).
- **Classes.** Report endogenous, news-shock and mixed events separately (EVENT_DEFINITION_DRAFT.md
  section 8). Expected result: modest skill on build-up events and none on news shocks.
- **Non-stationarity.** The repo's q10 found a 2023-06 model about 6 points below a refit model in
  2025-07; trade sizes fell about two thirds over the period. Report results by year.

## 6. Timing audit (run before any model)

For each candidate signal, plot event-time profiles from -24 h to +6 h against matched controls, then
partial out log volume and realized volatility and re-plot. Report the peak lag with a bootstrap
interval. A signal that peaks after onset, or whose pre-onset rise disappears after the partialling, is
dropped. This is the Andersen and Bondarenko (2014) audit applied to Hawkes n, sign memory and depth.

## 7. Prior work and what it means here

| Work | Lesson |
|---|---|
| Garcia Seuma (2026), arXiv 2607.27070 [unverified] | Seven BTC events; reported event-specific warnings. Our panel must state power in episodes |
| Andersen and Bondarenko (2014), JFM 17, 1-46 | Volume baseline and timing audit are mandatory |
| Abad, Massot and Pascual (2018), JBF 86, 21-36 | Event test against a volatility-only baseline |
| Beutel, List and von Schweinitz (2019), JFS 45, 100693 | Logit first |
| Prata et al. (2024); Briola, Bartolucci and Aste (2025) | Deep LOB models do not travel |
| Makinen et al. (2019), QF 19(12) | Jump prediction works at 1 minute, too short to be a warning |
| Shu and Zhu (2020); Gerlach, Demos and Sornette (2019); Geraskin and Fantazzini (2013) | LPPLS is fragile; use as one feature |
| Liu, Shu and Zhu (2024), Stats 7(2) | Balanced accuracy without alarm budget overstates usefulness |
| Wheatley, Wehrli and Sornette (2019) | Branching ratios near 1 can be an artifact |
| King and Zeng (2001) | Prior correction for case-control samples |

Full references in [LITERATURE.md](LITERATURE.md).

## 8. Concrete ML projects (from the README ranking, P5)

1. **Alarm-budget benchmark** on the 50 to 100 most liquid perps, 2023-01 to 2026-10, using models 1
   to 4 above. Effort about 15 days after P1 and P2. Novelty: partly done; the contribution is the
   panel, the mask and the scoring.
2. **Class split**: re-score within endogenous, news and mixed classes with a permutation test of the
   skill difference. About 5 days.
3. **Gap-burst label** (COIN-M only, or USDT-M after the background model): predict aggTrades ID-gap
   bursts, which mark insurance-fund takeovers and ADL. Only after the proxy is validated.
4. Deferred: Hawkes jump contagion (mark-price smoothing damps jumps; few jumps per contract) and a
   trades-only liquidation classifier trained on COIN-M snapshots (possible, but the target is itself
   throttled).
