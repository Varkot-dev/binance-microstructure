# Q4: trades-side cross-section — results

## Methodology

For each symbol in the requested universe, one month (2023-07) of aggTrades is loaded and collapsed into aggressor-level events (`load_events`), producing a ±1 sign series per symbol. Symbols are processed one at a time and their frames released (`del`) before moving to the next symbol, bounding peak memory across the full universe. Symbols with fewer than `min_events` = 1,000,000 events are **skipped** (logged, reason "below min_events") rather than analyzed; any other per-symbol failure (missing parquet, malformed data, or any other exception) is caught and logged into `failures` with the symbol and the exception, and never aborts the run for the remaining symbols.

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

Requested: 207. Successful: 117. Skipped (below min_events): 87. Failed: 3.

## Highest activity (10 by n_events)

| symbol | n_events | γ̂ | stderr | acf1 | p_flip | zigzag | total_qty |
|---|---|---|---|---|---|---|---|
| BTCUSDT | 16,229,472 | 0.3260 | 0.0010 | -0.1032 | 0.5516 | 0.1035 | 9,227,366.90 |
| ETHUSDT | 11,534,367 | 0.2055 | 0.0013 | 0.0917 | 0.4541 | 0.0373 | 63,619,667.03 |
| XRPUSDT | 11,469,421 | 0.3453 | 0.0027 | -0.2845 | 0.6421 | 0.1334 | 78,793,696,398.70 |
| BCHUSDT | 10,973,795 | 0.3536 | 0.0033 | 0.0325 | 0.4837 | 0.0135 | 134,309,424.36 |
| SOLUSDT | 10,311,844 | 0.3315 | 0.0041 | 0.0626 | 0.4687 | 0.0085 | 1,431,249,624.00 |
| COMPUSDT | 8,909,411 | 0.2243 | 0.0013 | -0.0578 | 0.5288 | 0.0314 | 233,073,571.85 |
| XLMUSDT | 7,055,933 | 0.3170 | 0.0038 | 0.0738 | 0.4631 | 0.0032 | 81,165,111,484.00 |
| 1000PEPEUSDT | 7,038,264 | 0.3880 | 0.0050 | 0.0905 | 0.4546 | -0.0010 | 7,992,909,253,108.00 |
| LTCUSDT | 6,117,351 | 0.3876 | 0.0027 | -0.0403 | 0.5198 | 0.0291 | 225,022,508.20 |
| MKRUSDT | 5,918,218 | 0.2785 | 0.0027 | 0.0651 | 0.4674 | 0.0033 | 8,137,499.12 |

## Lowest activity (10 by n_events)

| symbol | n_events | γ̂ | stderr | acf1 | p_flip | zigzag | total_qty |
|---|---|---|---|---|---|---|---|
| UNFIUSDT | 1,053,444 | 0.2984 | 0.0019 | 0.1170 | 0.4415 | -0.0015 | 206,534,388.20 |
| ICPUSDT | 1,045,769 | 0.3265 | 0.0020 | 0.1492 | 0.4254 | -0.0054 | 201,102,292.00 |
| MINAUSDT | 1,031,969 | 0.3884 | 0.0036 | 0.1483 | 0.4258 | -0.0097 | 1,466,585,686.00 |
| XEMUSDT | 1,026,881 | 0.4064 | 0.0037 | 0.0839 | 0.4581 | 0.0283 | 66,214,397,106.00 |
| ZILUSDT | 1,016,982 | 0.3564 | 0.0034 | 0.0860 | 0.4568 | 0.0051 | 49,441,614,106.00 |
| ZECUSDT | 1,011,901 | 0.3154 | 0.0021 | 0.1543 | 0.4225 | -0.0049 | 25,179,698.25 |
| ONTUSDT | 1,007,661 | 0.3101 | 0.0020 | 0.0984 | 0.4506 | 0.0063 | 5,562,340,520.30 |
| ROSEUSDT | 1,007,042 | 0.3411 | 0.0030 | 0.1959 | 0.4019 | -0.0126 | 10,832,433,187.00 |
| FOOTBALLUSDT | 1,004,138 | 0.3719 | 0.0030 | 0.1930 | 0.4034 | -0.0167 | 867,511.58 |
| ALGOUSDT | 1,002,507 | 0.3024 | 0.0018 | 0.1153 | 0.4418 | 0.0029 | 13,127,531,856.80 |

## Cross-sectional regressions

**γ̂ on log10(n_events)**: slope = **-0.0225** (stderr 0.0225), intercept = 0.4637, R² = 0.0086, n = 117

**p_flip on log10(n_events)**: slope = **0.0920** (stderr 0.0156), intercept = -0.1314, R² = 0.2328, n = 117

## Findings

The fitted order-flow memory exponent γ̂ **decreases** with log-activity across the 117-symbol successful set (slope -0.0225, R² 0.0086), i.e. more actively traded symbols in this sample tend to show weaker long-memory decay than less actively traded ones.

The sign-flip probability p_flip **increases** with log-activity (slope 0.0920, R² 0.2328); since p_flip = 0.5 corresponds to no persistence, this indicates that persistence weakens as activity increases (a slope above zero means p_flip rises toward more anti-persistent behavior at higher activity).

## Failures

| symbol | reason |
|---|---|
| BTCUSDT_230630 | parquet not found: data/parquet/aggTrades/BTCUSDT_230630/2023-07.parquet |
| ETHUSDT_230630 | parquet not found: data/parquet/aggTrades/ETHUSDT_230630/2023-07.parquet |
| 1000LUNCBUSD | parquet not found: data/parquet/aggTrades/1000LUNCBUSD/2023-07.parquet |

## Skipped (below min_events)

| symbol | n_events | reason |
|---|---|---|
| COMBOUSDT | 880,918 | below min_events |
| TRUUSDT | 737,950 | below min_events |
| SFPUSDT | 831,726 | below min_events |
| AMBUSDT | 556,865 | below min_events |
| GALUSDT | 936,924 | below min_events |
| FLMUSDT | 684,050 | below min_events |
| JOEUSDT | 877,303 | below min_events |
| HIGHUSDT | 619,327 | below min_events |
| LDOBUSD | 752,586 | below min_events |
| QNTUSDT | 941,058 | below min_events |
| TUSDT | 959,631 | below min_events |
| GALABUSD | 713,883 | below min_events |
| BNBBUSD | 596,471 | below min_events |
| ACHUSDT | 748,120 | below min_events |
| BNXUSDT | 653,211 | below min_events |
| 1000FLOKIUSDT | 747,701 | below min_events |
| COTIUSDT | 962,970 | below min_events |
| VETUSDT | 796,364 | below min_events |
| RADUSDT | 497,135 | below min_events |
| DASHUSDT | 823,758 | below min_events |
| LPTUSDT | 782,640 | below min_events |
| ENSUSDT | 947,834 | below min_events |
| IDEXUSDT | 629,342 | below min_events |
| BLZUSDT | 796,741 | below min_events |
| PEOPLEUSDT | 567,299 | below min_events |
| LEVERUSDT | 407,629 | below min_events |
| SSVUSDT | 697,506 | below min_events |
| RSRUSDT | 761,239 | below min_events |
| ARUSDT | 970,960 | below min_events |
| IOSTUSDT | 863,125 | below min_events |
| SPELLUSDT | 764,962 | below min_events |
| ENJUSDT | 916,708 | below min_events |
| HOOKUSDT | 773,562 | below min_events |
| SKLUSDT | 678,820 | below min_events |
| APTBUSD | 603,883 | below min_events |
| ICXUSDT | 769,148 | below min_events |
| GMXUSDT | 781,830 | below min_events |
| AUDIOUSDT | 609,904 | below min_events |
| EGLDUSDT | 746,594 | below min_events |
| RVNUSDT | 657,858 | below min_events |
| CELRUSDT | 624,330 | below min_events |
| BALUSDT | 673,584 | below min_events |
| IOTAUSDT | 628,838 | below min_events |
| MATICBUSD | 559,771 | below min_events |
| C98USDT | 589,009 | below min_events |
| LRCUSDT | 683,036 | below min_events |
| ONEUSDT | 705,085 | below min_events |
| LTCBUSD | 726,310 | below min_events |
| HFTUSDT | 559,892 | below min_events |
| KSMUSDT | 561,151 | below min_events |
| XTZUSDT | 636,782 | below min_events |
| CKBUSDT | 536,563 | below min_events |
| PERPUSDT | 596,076 | below min_events |
| AGIXBUSD | 501,304 | below min_events |
| CHRUSDT | 571,981 | below min_events |
| BAKEUSDT | 586,423 | below min_events |
| LITUSDT | 467,131 | below min_events |
| REEFUSDT | 716,760 | below min_events |
| TRXBUSD | 464,017 | below min_events |
| HOTUSDT | 580,921 | below min_events |
| IOTXUSDT | 497,203 | below min_events |
| CTKUSDT | 540,022 | below min_events |
| DENTUSDT | 594,172 | below min_events |
| RUNEUSDT | 517,982 | below min_events |
| XVSUSDT | 787,476 | below min_events |
| KLAYUSDT | 480,637 | below min_events |
| BATUSDT | 701,571 | below min_events |
| GTCUSDT | 639,465 | below min_events |
| ALICEUSDT | 559,247 | below min_events |
| DOGEBUSD | 762,297 | below min_events |
| DARUSDT | 582,761 | below min_events |
| ADABUSD | 385,580 | below min_events |
| CVXUSDT | 711,254 | below min_events |
| TRBUSDT | 690,891 | below min_events |
| UMAUSDT | 590,009 | below min_events |
| USDCUSDT | 230,975 | below min_events |
| FTMBUSD | 421,297 | below min_events |
| DGBUSDT | 750,097 | below min_events |
| API3USDT | 469,046 | below min_events |
| BTCDOMUSDT | 274,221 | below min_events |
| TLMUSDT | 395,822 | below min_events |
| ATAUSDT | 410,395 | below min_events |
| BLUEBIRDUSDT | 406,616 | below min_events |
| DEFIUSDT | 405,225 | below min_events |
| DODOBUSD | 222,123 | below min_events |
| ETHBTC | 87,272 | below min_events |
| NMRUSDT | 516,636 | below min_events |

## Caveats

- Single month (2023-07); this is one specific market regime, and per Phase 1.5 diagnostics, order-flow memory statistics are regime-dependent — these results may not generalize to other months or volatility regimes.
- Each symbol's γ̂ OLS stderr understates true uncertainty (autocorrelated ACF values violate the i.i.d.-residual assumption, same caveat as Q1), and this understatement is heteroskedastic across the cross-section (see Methodology); the cross-sectional regression stderr/R² inherit this problem and should be read as descriptive summaries, not as valid confidence intervals.
- `q4_gamma_vs_activity.png` deliberately omits per-symbol error bars on γ̂: plotting the OLS stderr would imply a precision the estimate does not have, for the same heteroskedasticity/understatement reason given above.
- Symbols are only included in the regressions if they clear `min_events`; the cross-section is therefore a survivorship-filtered subset of the requested universe, not the full universe.
