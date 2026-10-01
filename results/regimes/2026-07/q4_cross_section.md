# Q4: trades-side cross-section — results

## Methodology

For each symbol in the requested universe, one month (2026-07) of aggTrades is loaded and collapsed into aggressor-level events (`load_events`), producing a ±1 sign series per symbol. Symbols are processed one at a time and their frames released (`del`) before moving to the next symbol, bounding peak memory across the full universe. Symbols with fewer than `min_events` = 1,000,000 events are **skipped** (logged, reason "below min_events") rather than analyzed; any other per-symbol failure (missing parquet, malformed data, or any other exception) is caught and logged into `failures` with the symbol and the exception, and never aborts the run for the remaining symbols.

Per successful symbol, five statistics are computed on the sign series:

- **n_events**: activity, the number of aggressor events in the period.
- **γ̂ + OLS stderr**: sign-ACF power-law exponent, fit the same way as Q1 (`fit_power_law(sign_acf(signs, max_lag), lo=10, hi=max_lag//2)`).
- **lag-1 ACF**: `sign_acf(signs, max_lag)[1]`.
- **p_flip**: `P(sign_{t+1} != sign_t)`, the empirical fraction of consecutive sign flips — 0.5 is the no-persistence benchmark (independent coin flips).
- **zigzag amplitude**: Phase-1.5's definition (Q1b) — mean ACF at even lags 2,4,6,8,10 minus mean ACF at odd lags 1,3,5,7,9.
- **total_qty**: sum of aggressor-event quantity over the period.

**Cross-sectional regressions**: on the successful set, ordinary least squares (`np.polyfit`, degree 1, with intercept — not through-origin, since there is no reason to expect γ̂ or p_flip to vanish at zero activity) is used to regress (a) γ̂ on log10(n_events) and (b) p_flip on log10(n_events).

**Heteroskedasticity caveat**: each symbol's own γ̂ stderr comes from `fit_power_law`'s i.i.d.-residual OLS assumption applied to autocorrelated ACF values, which already understates that symbol's true uncertainty (documented in Q1). That understatement is *not* uniform across symbols — it scales with each symbol's own n_events and ACF shape — so per-symbol γ̂ noise is heteroskedastic across the cross-section. The cross-sectional regressions above therefore also violate the homoskedastic-residual assumption behind their own OLS stderr; the reported regression stderr/R² should be read as descriptive, not as a valid confidence interval on the true relationship.

## Run summary

Requested: 207. Successful: 46. Skipped (below min_events): 93. Failed: 68.

## Highest activity (10 by n_events)

| symbol | n_events | γ̂ | stderr | acf1 | p_flip | zigzag | total_qty |
|---|---|---|---|---|---|---|---|
| ETHUSDT | 15,881,884 | 0.4164 | 0.0026 | 0.0764 | 0.4618 | 0.0400 | 117,588,875.54 |
| BTCUSDT | 14,577,970 | 0.4513 | 0.0012 | 0.0235 | 0.4882 | 0.0535 | 4,297,823.62 |
| ZECUSDT | 10,743,966 | 0.2566 | 0.0041 | 0.3387 | 0.3306 | -0.0278 | 31,937,947.34 |
| LITUSDT | 6,633,120 | 0.2012 | 0.0028 | 0.3419 | 0.3289 | -0.0296 | 798,652,948.80 |
| SOLUSDT | 6,549,774 | 0.2895 | 0.0022 | -0.0856 | 0.5428 | 0.0530 | 507,701,204.66 |
| TLMUSDT | 6,477,040 | 0.2376 | 0.0019 | -0.0315 | 0.5157 | 0.0241 | 1,262,150,872,420.00 |
| COTIUSDT | 5,823,097 | 0.1970 | 0.0042 | 0.1956 | 0.4022 | -0.0152 | 153,294,814,873.00 |
| 1000PEPEUSDT | 5,365,105 | 0.2888 | 0.0044 | 0.3487 | 0.3256 | -0.0325 | 1,762,483,270,627.00 |
| BNBUSDT | 4,812,418 | 0.3062 | 0.0013 | 0.1886 | 0.4052 | -0.0048 | 11,612,418.68 |
| XRPUSDT | 4,561,673 | 0.2217 | 0.0011 | 0.0519 | 0.4730 | 0.0160 | 12,187,396,796.30 |

## Lowest activity (10 by n_events)

| symbol | n_events | γ̂ | stderr | acf1 | p_flip | zigzag | total_qty |
|---|---|---|---|---|---|---|---|
| LDOUSDT | 1,404,621 | 0.2019 | 0.0014 | 0.1575 | 0.4211 | -0.0096 | 2,178,125,129.00 |
| IDUSDT | 1,322,588 | 0.1132 | 0.0010 | 0.1754 | 0.4121 | -0.0115 | 8,685,146,578.00 |
| CHRUSDT | 1,297,094 | 0.0277 | 0.0002 | 0.2559 | 0.2035 | 0.0061 | 3,907,423,119.00 |
| FETUSDT | 1,268,156 | 0.1163 | 0.0006 | 0.1685 | 0.4153 | 0.0034 | 4,283,503,385.00 |
| LTCUSDT | 1,262,846 | 0.3571 | 0.0018 | 0.1455 | 0.4256 | -0.0019 | 34,048,810.89 |
| DASHUSDT | 1,214,246 | 0.1303 | 0.0007 | 0.1641 | 0.4177 | 0.0014 | 13,859,220.61 |
| OPUSDT | 1,124,589 | 0.0549 | 0.0004 | 0.1720 | 0.4139 | 0.0042 | 6,300,857,668.40 |
| ARPAUSDT | 1,107,056 | 0.1342 | 0.0017 | -0.0183 | 0.5091 | 0.0364 | 43,515,897,039.00 |
| ETCUSDT | 1,009,838 | 0.1215 | 0.0009 | 0.2366 | 0.3817 | -0.0144 | 78,099,559.52 |
| YFIUSDT | 1,001,164 | 0.3201 | 0.0041 | 0.0184 | 0.4908 | 0.0135 | 233,071.32 |

## Cross-sectional regressions

**γ̂ on log10(n_events)**: slope = **0.1683** (stderr 0.0447), intercept = -0.8614, R² = 0.2441, n = 46

**p_flip on log10(n_events)**: slope = **0.0230** (stderr 0.0325), intercept = 0.2677, R² = 0.0113, n = 46

## Findings

The fitted order-flow memory exponent γ̂ **increases** with log-activity across the 46-symbol successful set (slope 0.1683, R² 0.2441), i.e. more actively traded symbols in this sample tend to show stronger long-memory decay than less actively traded ones.

The sign-flip probability p_flip **increases** with log-activity (slope 0.0230, R² 0.0113); since p_flip = 0.5 corresponds to no persistence, this indicates that persistence weakens as activity increases (a slope above zero means p_flip rises toward more anti-persistent behavior at higher activity).

## Failures

| symbol | reason |
|---|---|
| TOMOUSDT | parquet not found: data/parquet/aggTrades/TOMOUSDT/2026-07.parquet |
| WAVESUSDT | parquet not found: data/parquet/aggTrades/WAVESUSDT/2026-07.parquet |
| LINAUSDT | parquet not found: data/parquet/aggTrades/LINAUSDT/2026-07.parquet |
| RNDRUSDT | parquet not found: data/parquet/aggTrades/RNDRUSDT/2026-07.parquet |
| ALPHAUSDT | parquet not found: data/parquet/aggTrades/ALPHAUSDT/2026-07.parquet |
| MATICUSDT | parquet not found: data/parquet/aggTrades/MATICUSDT/2026-07.parquet |
| BTCBUSD | parquet not found: data/parquet/aggTrades/BTCBUSD/2026-07.parquet |
| KEYUSDT | parquet not found: data/parquet/aggTrades/KEYUSDT/2026-07.parquet |
| ETHBUSD | parquet not found: data/parquet/aggTrades/ETHBUSD/2026-07.parquet |
| RENUSDT | parquet not found: data/parquet/aggTrades/RENUSDT/2026-07.parquet |
| NKNUSDT | parquet not found: data/parquet/aggTrades/NKNUSDT/2026-07.parquet |
| OMGUSDT | parquet not found: data/parquet/aggTrades/OMGUSDT/2026-07.parquet |
| COMBOUSDT | parquet not found: data/parquet/aggTrades/COMBOUSDT/2026-07.parquet |
| TRUUSDT | parquet not found: data/parquet/aggTrades/TRUUSDT/2026-07.parquet |
| AMBUSDT | parquet not found: data/parquet/aggTrades/AMBUSDT/2026-07.parquet |
| OCEANUSDT | parquet not found: data/parquet/aggTrades/OCEANUSDT/2026-07.parquet |
| SXPUSDT | parquet not found: data/parquet/aggTrades/SXPUSDT/2026-07.parquet |
| FTMUSDT | parquet not found: data/parquet/aggTrades/FTMUSDT/2026-07.parquet |
| GALUSDT | parquet not found: data/parquet/aggTrades/GALUSDT/2026-07.parquet |
| MKRUSDT | parquet not found: data/parquet/aggTrades/MKRUSDT/2026-07.parquet |
| ANTUSDT | parquet not found: data/parquet/aggTrades/ANTUSDT/2026-07.parquet |
| FLMUSDT | parquet not found: data/parquet/aggTrades/FLMUSDT/2026-07.parquet |
| SOLBUSD | parquet not found: data/parquet/aggTrades/SOLBUSD/2026-07.parquet |
| PHBUSDT | parquet not found: data/parquet/aggTrades/PHBUSDT/2026-07.parquet |
| EOSUSDT | parquet not found: data/parquet/aggTrades/EOSUSDT/2026-07.parquet |
| AGIXUSDT | parquet not found: data/parquet/aggTrades/AGIXUSDT/2026-07.parquet |
| RDNTUSDT | parquet not found: data/parquet/aggTrades/RDNTUSDT/2026-07.parquet |
| HIGHUSDT | parquet not found: data/parquet/aggTrades/HIGHUSDT/2026-07.parquet |
| LDOBUSD | parquet not found: data/parquet/aggTrades/LDOBUSD/2026-07.parquet |
| FXSUSDT | parquet not found: data/parquet/aggTrades/FXSUSDT/2026-07.parquet |
| GALABUSD | parquet not found: data/parquet/aggTrades/GALABUSD/2026-07.parquet |
| BNBBUSD | parquet not found: data/parquet/aggTrades/BNBBUSD/2026-07.parquet |
| BNXUSDT | parquet not found: data/parquet/aggTrades/BNXUSDT/2026-07.parquet |
| RADUSDT | parquet not found: data/parquet/aggTrades/RADUSDT/2026-07.parquet |
| IDEXUSDT | parquet not found: data/parquet/aggTrades/IDEXUSDT/2026-07.parquet |
| BLZUSDT | parquet not found: data/parquet/aggTrades/BLZUSDT/2026-07.parquet |
| XRPBUSD | parquet not found: data/parquet/aggTrades/XRPBUSD/2026-07.parquet |
| UNFIUSDT | parquet not found: data/parquet/aggTrades/UNFIUSDT/2026-07.parquet |
| LEVERUSDT | parquet not found: data/parquet/aggTrades/LEVERUSDT/2026-07.parquet |
| FOOTBALLUSDT | parquet not found: data/parquet/aggTrades/FOOTBALLUSDT/2026-07.parquet |
| HOOKUSDT | parquet not found: data/parquet/aggTrades/HOOKUSDT/2026-07.parquet |
| APTBUSD | parquet not found: data/parquet/aggTrades/APTBUSD/2026-07.parquet |
| AUDIOUSDT | parquet not found: data/parquet/aggTrades/AUDIOUSDT/2026-07.parquet |
| BALUSDT | parquet not found: data/parquet/aggTrades/BALUSDT/2026-07.parquet |
| MATICBUSD | parquet not found: data/parquet/aggTrades/MATICBUSD/2026-07.parquet |
| BTCUSDT_230630 | parquet not found: data/parquet/aggTrades/BTCUSDT_230630/2026-07.parquet |
| LRCUSDT | parquet not found: data/parquet/aggTrades/LRCUSDT/2026-07.parquet |
| LTCBUSD | parquet not found: data/parquet/aggTrades/LTCBUSD/2026-07.parquet |
| PERPUSDT | parquet not found: data/parquet/aggTrades/PERPUSDT/2026-07.parquet |
| XEMUSDT | parquet not found: data/parquet/aggTrades/XEMUSDT/2026-07.parquet |
| AGIXBUSD | parquet not found: data/parquet/aggTrades/AGIXBUSD/2026-07.parquet |
| BAKEUSDT | parquet not found: data/parquet/aggTrades/BAKEUSDT/2026-07.parquet |
| STMXUSDT | parquet not found: data/parquet/aggTrades/STMXUSDT/2026-07.parquet |
| REEFUSDT | parquet not found: data/parquet/aggTrades/REEFUSDT/2026-07.parquet |
| TRXBUSD | parquet not found: data/parquet/aggTrades/TRXBUSD/2026-07.parquet |
| DENTUSDT | parquet not found: data/parquet/aggTrades/DENTUSDT/2026-07.parquet |
| KLAYUSDT | parquet not found: data/parquet/aggTrades/KLAYUSDT/2026-07.parquet |
| DOGEBUSD | parquet not found: data/parquet/aggTrades/DOGEBUSD/2026-07.parquet |
| DARUSDT | parquet not found: data/parquet/aggTrades/DARUSDT/2026-07.parquet |
| ETHUSDT_230630 | parquet not found: data/parquet/aggTrades/ETHUSDT_230630/2026-07.parquet |
| ADABUSD | parquet not found: data/parquet/aggTrades/ADABUSD/2026-07.parquet |
| FTMBUSD | parquet not found: data/parquet/aggTrades/FTMBUSD/2026-07.parquet |
| DGBUSDT | parquet not found: data/parquet/aggTrades/DGBUSDT/2026-07.parquet |
| ATAUSDT | parquet not found: data/parquet/aggTrades/ATAUSDT/2026-07.parquet |
| BLUEBIRDUSDT | parquet not found: data/parquet/aggTrades/BLUEBIRDUSDT/2026-07.parquet |
| 1000LUNCBUSD | parquet not found: data/parquet/aggTrades/1000LUNCBUSD/2026-07.parquet |
| DEFIUSDT | parquet not found: data/parquet/aggTrades/DEFIUSDT/2026-07.parquet |
| DODOBUSD | parquet not found: data/parquet/aggTrades/DODOBUSD/2026-07.parquet |

## Skipped (below min_events)

| symbol | n_events | reason |
|---|---|---|
| MTLUSDT | 178,253 | below min_events |
| 1000LUNCUSDT | 919,921 | below min_events |
| STXUSDT | 756,215 | below min_events |
| KAVAUSDT | 271,865 | below min_events |
| COMPUSDT | 252,556 | below min_events |
| EDUUSDT | 438,257 | below min_events |
| CFXUSDT | 642,676 | below min_events |
| APEUSDT | 667,991 | below min_events |
| WOOUSDT | 246,613 | below min_events |
| GRTUSDT | 293,204 | below min_events |
| SANDUSDT | 727,999 | below min_events |
| MAGICUSDT | 406,652 | below min_events |
| ATOMUSDT | 837,588 | below min_events |
| CHZUSDT | 763,155 | below min_events |
| BANDUSDT | 258,105 | below min_events |
| SFPUSDT | 231,105 | below min_events |
| MASKUSDT | 360,294 | below min_events |
| LUNA2USDT | 369,214 | below min_events |
| GALAUSDT | 849,002 | below min_events |
| AXSUSDT | 487,196 | below min_events |
| STORJUSDT | 697,656 | below min_events |
| NEOUSDT | 342,698 | below min_events |
| IMXUSDT | 345,265 | below min_events |
| DUSKUSDT | 457,845 | below min_events |
| RLCUSDT | 358,385 | below min_events |
| LQTYUSDT | 301,348 | below min_events |
| JOEUSDT | 261,908 | below min_events |
| JASMYUSDT | 546,964 | below min_events |
| MANAUSDT | 719,991 | below min_events |
| SUSHIUSDT | 281,617 | below min_events |
| QNTUSDT | 400,838 | below min_events |
| THETAUSDT | 423,345 | below min_events |
| CRVUSDT | 718,109 | below min_events |
| ZENUSDT | 587,443 | below min_events |
| ROSEUSDT | 531,017 | below min_events |
| KNCUSDT | 175,561 | below min_events |
| ACHUSDT | 920,286 | below min_events |
| MINAUSDT | 489,846 | below min_events |
| GMTUSDT | 360,680 | below min_events |
| ICPUSDT | 994,228 | below min_events |
| 1000FLOKIUSDT | 589,155 | below min_events |
| SNXUSDT | 602,240 | below min_events |
| STGUSDT | 830,723 | below min_events |
| ANKRUSDT | 533,868 | below min_events |
| VETUSDT | 497,001 | below min_events |
| LPTUSDT | 410,648 | below min_events |
| ENSUSDT | 574,194 | below min_events |
| PEOPLEUSDT | 983,649 | below min_events |
| 1INCHUSDT | 462,887 | below min_events |
| CTSIUSDT | 286,784 | below min_events |
| ZILUSDT | 890,921 | below min_events |
| SSVUSDT | 229,511 | below min_events |
| RSRUSDT | 268,529 | below min_events |
| ARUSDT | 354,017 | below min_events |
| IOSTUSDT | 434,230 | below min_events |
| SPELLUSDT | 994,093 | below min_events |
| ONTUSDT | 339,660 | below min_events |
| ENJUSDT | 501,690 | below min_events |
| ALGOUSDT | 670,866 | below min_events |
| ASTRUSDT | 240,509 | below min_events |
| ICXUSDT | 227,240 | below min_events |
| GMXUSDT | 380,199 | below min_events |
| EGLDUSDT | 633,139 | below min_events |
| FLOWUSDT | 381,150 | below min_events |
| RVNUSDT | 418,651 | below min_events |
| CELRUSDT | 267,653 | below min_events |
| IOTAUSDT | 623,810 | below min_events |
| C98USDT | 337,784 | below min_events |
| QTUMUSDT | 495,422 | below min_events |
| ONEUSDT | 745,972 | below min_events |
| HFTUSDT | 361,980 | below min_events |
| KSMUSDT | 316,150 | below min_events |
| XTZUSDT | 409,962 | below min_events |
| CKBUSDT | 181,212 | below min_events |
| CELOUSDT | 803,131 | below min_events |
| ZRXUSDT | 178,269 | below min_events |
| HOTUSDT | 947,496 | below min_events |
| IOTXUSDT | 347,226 | below min_events |
| CTKUSDT | 275,273 | below min_events |
| RUNEUSDT | 382,080 | below min_events |
| XVSUSDT | 209,490 | below min_events |
| BATUSDT | 232,569 | below min_events |
| GTCUSDT | 435,934 | below min_events |
| ALICEUSDT | 696,119 | below min_events |
| CVXUSDT | 219,682 | below min_events |
| UMAUSDT | 313,914 | below min_events |
| USDCUSDT | 664,009 | below min_events |
| OGNUSDT | 958,354 | below min_events |
| API3USDT | 584,072 | below min_events |
| BTCDOMUSDT | 323,670 | below min_events |
| MAVUSDT | 345,837 | below min_events |
| ETHBTC | 92,449 | below min_events |
| NMRUSDT | 460,929 | below min_events |

## Caveats

- Single month (2026-07); this is one specific market regime, and per Phase 1.5 diagnostics, order-flow memory statistics are regime-dependent — these results may not generalize to other months or volatility regimes.
- Each symbol's γ̂ OLS stderr understates true uncertainty (autocorrelated ACF values violate the i.i.d.-residual assumption, same caveat as Q1), and this understatement is heteroskedastic across the cross-section (see Methodology); the cross-sectional regression stderr/R² inherit this problem and should be read as descriptive summaries, not as valid confidence intervals.
- `q4_gamma_vs_activity.png` deliberately omits per-symbol error bars on γ̂: plotting the OLS stderr would imply a precision the estimate does not have, for the same heteroskedasticity/understatement reason given above.
- Symbols are only included in the regressions if they clear `min_events`; the cross-section is therefore a survivorship-filtered subset of the requested universe, not the full universe.
