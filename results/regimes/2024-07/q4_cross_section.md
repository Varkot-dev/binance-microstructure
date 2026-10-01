# Q4: trades-side cross-section

## Method

For each symbol in the universe I load one month (2024-07) of aggTrades and collapse it into aggressor-level events (`load_events`), giving a ±1 sign series. Symbols are processed one at a time to bound peak memory. Symbols with fewer than `min_events` = 1,000,000 events are skipped ("below min_events"). Any other per-symbol failure is logged in `failures` and does not abort the run.

Per symbol I compute:

- **n_events**: the number of aggressor events (activity).
- **γ̂ + OLS stderr**: sign-ACF power-law exponent, fit as in Q1 (`fit_power_law(sign_acf(signs, max_lag), lo=10, hi=max_lag//2)`).
- **lag-1 ACF**: `sign_acf(signs, max_lag)[1]`.
- **p_flip**: `P(sign_{t+1} != sign_t)`, the fraction of consecutive sign flips. 0.5 is the no-persistence benchmark.
- **zigzag amplitude**: as in Q1b, mean ACF at lags 2,4,6,8,10 minus mean ACF at lags 1,3,5,7,9.
- **total_qty**: summed aggressor-event quantity.

**Cross-sectional regressions**: OLS (`np.polyfit`, degree 1, with intercept) of (a) γ̂ and (b) p_flip on log10(n_events).

**Heteroskedasticity caveat**: each symbol's γ̂ stderr comes from `fit_power_law`'s i.i.d.-residual OLS on autocorrelated ACF values, which understates its uncertainty (see Q1) by an amount that varies with n_events and ACF shape. γ̂ noise is therefore heteroskedastic across symbols, and the regression stderr and R² are descriptive, not a valid confidence interval.

## Run summary

Requested: 207. Successful: 95. Skipped (below min_events): 80. Failed: 32.

## Highest activity (10 by n_events)

| symbol | n_events | γ̂ | stderr | acf1 | p_flip | zigzag | total_qty |
|---|---|---|---|---|---|---|---|
| BTCUSDT | 19,778,926 | 0.4906 | 0.0016 | -0.0644 | 0.5322 | 0.0786 | 8,346,286.88 |
| ETHUSDT | 16,822,580 | 0.4274 | 0.0045 | 0.0826 | 0.4586 | 0.0282 | 74,400,185.05 |
| 1000PEPEUSDT | 16,506,240 | 0.5642 | 0.0113 | 0.2429 | 0.3785 | -0.0184 | 3,135,527,168,084.00 |
| SOLUSDT | 11,732,154 | 0.6149 | 0.0065 | 0.1817 | 0.4091 | -0.0069 | 505,496,444.00 |
| PEOPLEUSDT | 8,152,037 | 0.1116 | 0.0014 | 0.0548 | 0.4726 | 0.0055 | 158,300,249,695.00 |
| ENSUSDT | 7,465,103 | 0.1797 | 0.0055 | 0.2758 | 0.3621 | -0.0266 | 235,825,026.80 |
| DOGEUSDT | 7,228,607 | 0.1590 | 0.0008 | 0.1078 | 0.4461 | 0.0045 | 119,988,930,361.00 |
| XRPUSDT | 7,169,683 | 0.1013 | 0.0010 | -0.0205 | 0.5102 | 0.0376 | 43,227,934,612.50 |
| BNXUSDT | 6,361,080 | 0.1428 | 0.0020 | 0.1684 | 0.4155 | -0.0127 | 3,977,662,661.30 |
| 1000FLOKIUSDT | 5,950,573 | 0.2383 | 0.0085 | 0.3053 | 0.3473 | -0.0348 | 33,215,502,787.00 |

## Lowest activity (10 by n_events)

| symbol | n_events | γ̂ | stderr | acf1 | p_flip | zigzag | total_qty |
|---|---|---|---|---|---|---|---|
| ENJUSDT | 1,126,657 | 0.1939 | 0.0045 | 0.3438 | 0.3281 | -0.0405 | 1,289,837,012.00 |
| MTLUSDT | 1,110,311 | 0.2102 | 0.0052 | 0.3372 | 0.3313 | -0.0408 | 372,271,016.00 |
| UMAUSDT | 1,095,783 | 0.3369 | 0.0047 | 0.0231 | 0.4884 | 0.0072 | 352,863,311.00 |
| RSRUSDT | 1,093,642 | 0.1774 | 0.0037 | 0.2360 | 0.3819 | -0.0284 | 85,544,252,875.00 |
| SANDUSDT | 1,089,634 | 0.2209 | 0.0031 | 0.1039 | 0.4480 | -0.0067 | 3,134,710,756.00 |
| GMXUSDT | 1,075,861 | 0.4409 | 0.0095 | 0.3297 | 0.3351 | -0.0380 | 10,877,893.79 |
| DYDXUSDT | 1,073,717 | 0.2197 | 0.0021 | 0.0930 | 0.4533 | 0.0028 | 994,129,879.00 |
| ASTRUSDT | 1,038,753 | 0.3791 | 0.0119 | 0.2961 | 0.3520 | -0.0364 | 6,179,446,756.00 |
| EOSUSDT | 1,032,832 | 0.2395 | 0.0024 | 0.1287 | 0.4355 | -0.0054 | 4,872,640,687.20 |
| COMPUSDT | 1,016,100 | 0.3352 | 0.0052 | 0.1300 | 0.4350 | -0.0122 | 11,287,354.75 |

## Cross-sectional regressions

**γ̂ on log10(n_events)**: slope = **0.0126** (stderr 0.0363), intercept = 0.1724, R² = 0.0013, n = 95

**p_flip on log10(n_events)**: slope = **0.0448** (stderr 0.0199), intercept = 0.1034, R² = 0.0520, n = 95

## Findings

The slope of γ̂ on log-activity across the 95-symbol successful set (slope 0.0126, stderr 0.0363, |t| = 0.3, R² 0.0013) is within 2 standard errors of zero, so it is indistinguishable from no relationship with activity.

p_flip increases with log-activity (slope 0.0448, R² 0.0520). Since p_flip = 0.5 means no persistence, persistence weakens as activity increases.

## Failures

| symbol | reason |
|---|---|
| TOMOUSDT | parquet not found: data/parquet/aggTrades/TOMOUSDT/2024-07.parquet |
| WAVESUSDT | parquet not found: data/parquet/aggTrades/WAVESUSDT/2024-07.parquet |
| BTCBUSD | parquet not found: data/parquet/aggTrades/BTCBUSD/2024-07.parquet |
| ETHBUSD | parquet not found: data/parquet/aggTrades/ETHBUSD/2024-07.parquet |
| OCEANUSDT | parquet not found: data/parquet/aggTrades/OCEANUSDT/2024-07.parquet |
| ANTUSDT | parquet not found: data/parquet/aggTrades/ANTUSDT/2024-07.parquet |
| SOLBUSD | parquet not found: data/parquet/aggTrades/SOLBUSD/2024-07.parquet |
| AGIXUSDT | parquet not found: data/parquet/aggTrades/AGIXUSDT/2024-07.parquet |
| LDOBUSD | parquet not found: data/parquet/aggTrades/LDOBUSD/2024-07.parquet |
| GALABUSD | parquet not found: data/parquet/aggTrades/GALABUSD/2024-07.parquet |
| BNBBUSD | parquet not found: data/parquet/aggTrades/BNBBUSD/2024-07.parquet |
| RADUSDT | parquet not found: data/parquet/aggTrades/RADUSDT/2024-07.parquet |
| IDEXUSDT | parquet not found: data/parquet/aggTrades/IDEXUSDT/2024-07.parquet |
| XRPBUSD | parquet not found: data/parquet/aggTrades/XRPBUSD/2024-07.parquet |
| FOOTBALLUSDT | parquet not found: data/parquet/aggTrades/FOOTBALLUSDT/2024-07.parquet |
| APTBUSD | parquet not found: data/parquet/aggTrades/APTBUSD/2024-07.parquet |
| AUDIOUSDT | parquet not found: data/parquet/aggTrades/AUDIOUSDT/2024-07.parquet |
| MATICBUSD | parquet not found: data/parquet/aggTrades/MATICBUSD/2024-07.parquet |
| BTCUSDT_230630 | parquet not found: data/parquet/aggTrades/BTCUSDT_230630/2024-07.parquet |
| LTCBUSD | parquet not found: data/parquet/aggTrades/LTCBUSD/2024-07.parquet |
| AGIXBUSD | parquet not found: data/parquet/aggTrades/AGIXBUSD/2024-07.parquet |
| TRXBUSD | parquet not found: data/parquet/aggTrades/TRXBUSD/2024-07.parquet |
| CTKUSDT | parquet not found: data/parquet/aggTrades/CTKUSDT/2024-07.parquet |
| DOGEBUSD | parquet not found: data/parquet/aggTrades/DOGEBUSD/2024-07.parquet |
| ETHUSDT_230630 | parquet not found: data/parquet/aggTrades/ETHUSDT_230630/2024-07.parquet |
| ADABUSD | parquet not found: data/parquet/aggTrades/ADABUSD/2024-07.parquet |
| CVXUSDT | parquet not found: data/parquet/aggTrades/CVXUSDT/2024-07.parquet |
| FTMBUSD | parquet not found: data/parquet/aggTrades/FTMBUSD/2024-07.parquet |
| DGBUSDT | parquet not found: data/parquet/aggTrades/DGBUSDT/2024-07.parquet |
| BLUEBIRDUSDT | parquet not found: data/parquet/aggTrades/BLUEBIRDUSDT/2024-07.parquet |
| 1000LUNCBUSD | parquet not found: data/parquet/aggTrades/1000LUNCBUSD/2024-07.parquet |
| DODOBUSD | parquet not found: data/parquet/aggTrades/DODOBUSD/2024-07.parquet |

## Skipped (below min_events)

| symbol | n_events | reason |
|---|---|---|
| LINAUSDT | 467,389 | below min_events |
| ALPHAUSDT | 721,547 | below min_events |
| KAVAUSDT | 627,946 | below min_events |
| ARPAUSDT | 700,331 | below min_events |
| KEYUSDT | 641,600 | below min_events |
| WOOUSDT | 989,604 | below min_events |
| RENUSDT | 720,502 | below min_events |
| NKNUSDT | 673,877 | below min_events |
| MAGICUSDT | 845,442 | below min_events |
| OMGUSDT | 595,144 | below min_events |
| COMBOUSDT | 569,402 | below min_events |
| BLURUSDT | 998,191 | below min_events |
| SFPUSDT | 810,036 | below min_events |
| MASKUSDT | 907,354 | below min_events |
| SXPUSDT | 539,925 | below min_events |
| XMRUSDT | 990,189 | below min_events |
| LUNA2USDT | 799,836 | below min_events |
| GALUSDT | 728,492 | below min_events |
| BELUSDT | 692,307 | below min_events |
| RLCUSDT | 831,637 | below min_events |
| LQTYUSDT | 854,451 | below min_events |
| FLMUSDT | 994,612 | below min_events |
| JOEUSDT | 649,055 | below min_events |
| MANAUSDT | 901,355 | below min_events |
| 1000XECUSDT | 876,001 | below min_events |
| QNTUSDT | 671,580 | below min_events |
| FXSUSDT | 901,620 | below min_events |
| KNCUSDT | 646,659 | below min_events |
| TUSDT | 529,551 | below min_events |
| MINAUSDT | 977,396 | below min_events |
| SNXUSDT | 579,750 | below min_events |
| STGUSDT | 692,043 | below min_events |
| ANKRUSDT | 711,127 | below min_events |
| DASHUSDT | 549,604 | below min_events |
| YFIUSDT | 784,627 | below min_events |
| 1INCHUSDT | 797,836 | below min_events |
| CTSIUSDT | 459,433 | below min_events |
| ZILUSDT | 537,277 | below min_events |
| IOSTUSDT | 779,668 | below min_events |
| SPELLUSDT | 823,302 | below min_events |
| ONTUSDT | 515,600 | below min_events |
| ALGOUSDT | 643,427 | below min_events |
| HOOKUSDT | 950,740 | below min_events |
| SKLUSDT | 853,581 | below min_events |
| ICXUSDT | 441,242 | below min_events |
| FLOWUSDT | 480,095 | below min_events |
| RVNUSDT | 416,687 | below min_events |
| CELRUSDT | 484,157 | below min_events |
| BALUSDT | 650,185 | below min_events |
| IOTAUSDT | 423,210 | below min_events |
| C98USDT | 439,797 | below min_events |
| LRCUSDT | 966,358 | below min_events |
| QTUMUSDT | 521,253 | below min_events |
| ONEUSDT | 483,442 | below min_events |
| HFTUSDT | 508,604 | below min_events |
| KSMUSDT | 836,642 | below min_events |
| XTZUSDT | 417,398 | below min_events |
| CELOUSDT | 313,069 | below min_events |
| ZRXUSDT | 773,625 | below min_events |
| PERPUSDT | 674,748 | below min_events |
| XEMUSDT | 575,494 | below min_events |
| LITUSDT | 381,248 | below min_events |
| REEFUSDT | 470,606 | below min_events |
| HOTUSDT | 446,510 | below min_events |
| IOTXUSDT | 804,144 | below min_events |
| DENTUSDT | 400,593 | below min_events |
| XVSUSDT | 631,284 | below min_events |
| KLAYUSDT | 379,670 | below min_events |
| BATUSDT | 445,385 | below min_events |
| GTCUSDT | 511,747 | below min_events |
| ALICEUSDT | 964,225 | below min_events |
| USDCUSDT | 291,782 | below min_events |
| OGNUSDT | 424,564 | below min_events |
| BTCDOMUSDT | 321,076 | below min_events |
| TLMUSDT | 972,120 | below min_events |
| ATAUSDT | 407,318 | below min_events |
| MAVUSDT | 740,719 | below min_events |
| DEFIUSDT | 310,024 | below min_events |
| ETHBTC | 562,097 | below min_events |
| NMRUSDT | 965,741 | below min_events |

## Caveats

- Single month (2024-07) in one market regime. Order-flow memory statistics are regime-dependent (see Q8), so these results may not carry over to other months or volatility regimes.
- Each symbol's γ̂ OLS stderr understates the uncertainty (autocorrelated ACF values, as in Q1), and the understatement is heteroskedastic across the cross-section. The regression stderr and R² inherit this and are descriptive only.
- `q4_gamma_vs_activity.png` omits per-symbol error bars on γ̂, because the OLS stderr would imply a precision the estimate lacks.
- Only symbols clearing `min_events` enter the regressions, so the cross-section is a survivorship-filtered subset of the requested universe.
