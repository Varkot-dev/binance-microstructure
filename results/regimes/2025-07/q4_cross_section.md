# Q4: trades-side cross-section

## Method

For each symbol in the universe I load one month (2025-07) of aggTrades and collapse it into aggressor-level events (`load_events`), giving a ±1 sign series. Symbols are processed one at a time to bound peak memory. Symbols with fewer than `min_events` = 1,000,000 events are skipped ("below min_events"). Any other per-symbol failure is logged in `failures` and does not abort the run.

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

Requested: 207. Successful: 94. Skipped (below min_events): 62. Failed: 51.

## Highest activity (10 by n_events)

| symbol | n_events | γ̂ | stderr | acf1 | p_flip | zigzag | total_qty |
|---|---|---|---|---|---|---|---|
| ETHUSDT | 27,033,493 | 0.5769 | 0.0031 | -0.0532 | 0.5266 | 0.0996 | 189,218,354.97 |
| 1000PEPEUSDT | 17,375,967 | 0.4826 | 0.0060 | 0.3372 | 0.3313 | -0.0264 | 3,342,826,799,751.00 |
| XRPUSDT | 17,100,486 | 0.2953 | 0.0015 | 0.0156 | 0.4921 | 0.0354 | 34,759,454,337.50 |
| BTCUSDT | 15,781,891 | 0.4593 | 0.0009 | -0.0642 | 0.5321 | 0.0870 | 4,220,063.72 |
| DOGEUSDT | 14,092,473 | 0.3083 | 0.0026 | 0.1082 | 0.4458 | 0.0086 | 286,483,805,743.00 |
| SOLUSDT | 13,330,644 | 0.3040 | 0.0016 | -0.1038 | 0.5518 | 0.0599 | 764,723,875.12 |
| SUIUSDT | 11,473,438 | 0.3205 | 0.0035 | 0.2307 | 0.3846 | -0.0135 | 8,259,804,189.30 |
| XLMUSDT | 9,983,112 | 0.3513 | 0.0062 | 0.3141 | 0.3429 | -0.0282 | 30,795,547,602.00 |
| CFXUSDT | 8,653,445 | 0.2428 | 0.0043 | 0.2205 | 0.3897 | -0.0183 | 38,997,280,364.00 |
| HBARUSDT | 7,669,067 | 0.2713 | 0.0046 | 0.3388 | 0.3305 | -0.0344 | 33,194,597,672.00 |

## Lowest activity (10 by n_events)

| symbol | n_events | γ̂ | stderr | acf1 | p_flip | zigzag | total_qty |
|---|---|---|---|---|---|---|---|
| BTCDOMUSDT | 1,060,568 | 0.7827 | 0.0089 | 0.2684 | 0.3654 | -0.0173 | 119,613.25 |
| AXSUSDT | 1,055,536 | 0.1458 | 0.0026 | 0.1741 | 0.4126 | -0.0121 | 273,676,376.00 |
| DYDXUSDT | 1,052,200 | 0.1627 | 0.0020 | 0.2209 | 0.3895 | -0.0148 | 1,931,034,577.60 |
| JOEUSDT | 1,043,328 | 0.1583 | 0.0032 | 0.2984 | 0.3506 | -0.0357 | 869,728,864.00 |
| WOOUSDT | 1,038,171 | 0.0756 | 0.0012 | 0.2771 | 0.3609 | -0.0278 | 2,404,503,197.00 |
| IOTAUSDT | 1,033,426 | 0.2178 | 0.0019 | 0.1337 | 0.4331 | -0.0026 | 3,427,696,266.80 |
| UMAUSDT | 1,031,529 | 0.2474 | 0.0022 | -0.0025 | 0.5008 | 0.0273 | 565,681,597.00 |
| TRUUSDT | 1,028,703 | 0.1826 | 0.0022 | 0.2004 | 0.3997 | -0.0161 | 8,205,918,002.00 |
| TLMUSDT | 1,020,088 | 0.0666 | 0.0009 | 0.3055 | 0.3473 | -0.0226 | 22,049,143,313.00 |
| LRCUSDT | 1,013,440 | 0.1098 | 0.0028 | 0.3368 | 0.3315 | -0.0378 | 2,101,061,489.00 |

## Cross-sectional regressions

**γ̂ on log10(n_events)**: slope = **0.1588** (stderr 0.0286), intercept = -0.8103, R² = 0.2505, n = 94

**p_flip on log10(n_events)**: slope = **0.0463** (stderr 0.0190), intercept = 0.0830, R² = 0.0608, n = 94

## Findings

γ̂ increases log-activity across the 94-symbol successful set (slope 0.1588, R² 0.2505). More actively traded symbols in this sample show stronger long-memory decay than less actively traded ones.

p_flip increases log-activity (slope 0.0463, R² 0.0608). Since p_flip = 0.5 means no persistence, persistence weakens as activity increases.

## Failures

| symbol | reason |
|---|---|
| TOMOUSDT | parquet not found: data/parquet/aggTrades/TOMOUSDT/2025-07.parquet |
| WAVESUSDT | parquet not found: data/parquet/aggTrades/WAVESUSDT/2025-07.parquet |
| LINAUSDT | parquet not found: data/parquet/aggTrades/LINAUSDT/2025-07.parquet |
| RNDRUSDT | parquet not found: data/parquet/aggTrades/RNDRUSDT/2025-07.parquet |
| MATICUSDT | parquet not found: data/parquet/aggTrades/MATICUSDT/2025-07.parquet |
| BTCBUSD | parquet not found: data/parquet/aggTrades/BTCBUSD/2025-07.parquet |
| KEYUSDT | parquet not found: data/parquet/aggTrades/KEYUSDT/2025-07.parquet |
| ETHBUSD | parquet not found: data/parquet/aggTrades/ETHBUSD/2025-07.parquet |
| RENUSDT | parquet not found: data/parquet/aggTrades/RENUSDT/2025-07.parquet |
| OMGUSDT | parquet not found: data/parquet/aggTrades/OMGUSDT/2025-07.parquet |
| COMBOUSDT | parquet not found: data/parquet/aggTrades/COMBOUSDT/2025-07.parquet |
| AMBUSDT | parquet not found: data/parquet/aggTrades/AMBUSDT/2025-07.parquet |
| OCEANUSDT | parquet not found: data/parquet/aggTrades/OCEANUSDT/2025-07.parquet |
| FTMUSDT | parquet not found: data/parquet/aggTrades/FTMUSDT/2025-07.parquet |
| GALUSDT | parquet not found: data/parquet/aggTrades/GALUSDT/2025-07.parquet |
| ANTUSDT | parquet not found: data/parquet/aggTrades/ANTUSDT/2025-07.parquet |
| SOLBUSD | parquet not found: data/parquet/aggTrades/SOLBUSD/2025-07.parquet |
| EOSUSDT | parquet not found: data/parquet/aggTrades/EOSUSDT/2025-07.parquet |
| AGIXUSDT | parquet not found: data/parquet/aggTrades/AGIXUSDT/2025-07.parquet |
| LDOBUSD | parquet not found: data/parquet/aggTrades/LDOBUSD/2025-07.parquet |
| GALABUSD | parquet not found: data/parquet/aggTrades/GALABUSD/2025-07.parquet |
| BNBBUSD | parquet not found: data/parquet/aggTrades/BNBBUSD/2025-07.parquet |
| BNXUSDT | parquet not found: data/parquet/aggTrades/BNXUSDT/2025-07.parquet |
| RADUSDT | parquet not found: data/parquet/aggTrades/RADUSDT/2025-07.parquet |
| IDEXUSDT | parquet not found: data/parquet/aggTrades/IDEXUSDT/2025-07.parquet |
| BLZUSDT | parquet not found: data/parquet/aggTrades/BLZUSDT/2025-07.parquet |
| XRPBUSD | parquet not found: data/parquet/aggTrades/XRPBUSD/2025-07.parquet |
| UNFIUSDT | parquet not found: data/parquet/aggTrades/UNFIUSDT/2025-07.parquet |
| FOOTBALLUSDT | parquet not found: data/parquet/aggTrades/FOOTBALLUSDT/2025-07.parquet |
| APTBUSD | parquet not found: data/parquet/aggTrades/APTBUSD/2025-07.parquet |
| AUDIOUSDT | parquet not found: data/parquet/aggTrades/AUDIOUSDT/2025-07.parquet |
| BALUSDT | parquet not found: data/parquet/aggTrades/BALUSDT/2025-07.parquet |
| MATICBUSD | parquet not found: data/parquet/aggTrades/MATICBUSD/2025-07.parquet |
| BTCUSDT_230630 | parquet not found: data/parquet/aggTrades/BTCUSDT_230630/2025-07.parquet |
| LTCBUSD | parquet not found: data/parquet/aggTrades/LTCBUSD/2025-07.parquet |
| XEMUSDT | parquet not found: data/parquet/aggTrades/XEMUSDT/2025-07.parquet |
| AGIXBUSD | parquet not found: data/parquet/aggTrades/AGIXBUSD/2025-07.parquet |
| LITUSDT | parquet not found: data/parquet/aggTrades/LITUSDT/2025-07.parquet |
| STMXUSDT | parquet not found: data/parquet/aggTrades/STMXUSDT/2025-07.parquet |
| REEFUSDT | parquet not found: data/parquet/aggTrades/REEFUSDT/2025-07.parquet |
| TRXBUSD | parquet not found: data/parquet/aggTrades/TRXBUSD/2025-07.parquet |
| KLAYUSDT | parquet not found: data/parquet/aggTrades/KLAYUSDT/2025-07.parquet |
| DOGEBUSD | parquet not found: data/parquet/aggTrades/DOGEBUSD/2025-07.parquet |
| DARUSDT | parquet not found: data/parquet/aggTrades/DARUSDT/2025-07.parquet |
| ETHUSDT_230630 | parquet not found: data/parquet/aggTrades/ETHUSDT_230630/2025-07.parquet |
| ADABUSD | parquet not found: data/parquet/aggTrades/ADABUSD/2025-07.parquet |
| FTMBUSD | parquet not found: data/parquet/aggTrades/FTMBUSD/2025-07.parquet |
| DGBUSDT | parquet not found: data/parquet/aggTrades/DGBUSDT/2025-07.parquet |
| BLUEBIRDUSDT | parquet not found: data/parquet/aggTrades/BLUEBIRDUSDT/2025-07.parquet |
| 1000LUNCBUSD | parquet not found: data/parquet/aggTrades/1000LUNCBUSD/2025-07.parquet |
| DODOBUSD | parquet not found: data/parquet/aggTrades/DODOBUSD/2025-07.parquet |

## Skipped (below min_events)

| symbol | n_events | reason |
|---|---|---|
| MTLUSDT | 784,129 | below min_events |
| 1000LUNCUSDT | 950,125 | below min_events |
| KAVAUSDT | 914,392 | below min_events |
| ARPAUSDT | 998,723 | below min_events |
| EDUUSDT | 528,579 | below min_events |
| NKNUSDT | 770,668 | below min_events |
| CHZUSDT | 993,679 | below min_events |
| BANDUSDT | 879,850 | below min_events |
| SFPUSDT | 587,051 | below min_events |
| SXPUSDT | 625,145 | below min_events |
| LUNA2USDT | 519,850 | below min_events |
| STORJUSDT | 758,352 | below min_events |
| RLCUSDT | 906,571 | below min_events |
| FLMUSDT | 546,758 | below min_events |
| 1000XECUSDT | 473,102 | below min_events |
| RDNTUSDT | 838,543 | below min_events |
| HIGHUSDT | 739,147 | below min_events |
| ROSEUSDT | 961,562 | below min_events |
| TUSDT | 681,859 | below min_events |
| MINAUSDT | 821,373 | below min_events |
| SNXUSDT | 569,246 | below min_events |
| STGUSDT | 421,781 | below min_events |
| COTIUSDT | 926,791 | below min_events |
| ANKRUSDT | 564,241 | below min_events |
| DASHUSDT | 506,118 | below min_events |
| YFIUSDT | 734,925 | below min_events |
| ZECUSDT | 820,609 | below min_events |
| CTSIUSDT | 545,975 | below min_events |
| ZILUSDT | 696,726 | below min_events |
| IOSTUSDT | 834,085 | below min_events |
| SPELLUSDT | 715,168 | below min_events |
| ONTUSDT | 587,213 | below min_events |
| ENJUSDT | 953,398 | below min_events |
| ASTRUSDT | 702,624 | below min_events |
| SKLUSDT | 879,855 | below min_events |
| ICXUSDT | 507,523 | below min_events |
| FLOWUSDT | 495,460 | below min_events |
| RVNUSDT | 793,965 | below min_events |
| CELRUSDT | 610,098 | below min_events |
| C98USDT | 480,012 | below min_events |
| QTUMUSDT | 500,066 | below min_events |
| ONEUSDT | 705,565 | below min_events |
| CELOUSDT | 570,261 | below min_events |
| ZRXUSDT | 654,079 | below min_events |
| PERPUSDT | 819,142 | below min_events |
| CHRUSDT | 570,553 | below min_events |
| HOTUSDT | 690,676 | below min_events |
| IOTXUSDT | 709,389 | below min_events |
| CTKUSDT | 970,617 | below min_events |
| DENTUSDT | 553,136 | below min_events |
| RUNEUSDT | 835,291 | below min_events |
| XVSUSDT | 560,373 | below min_events |
| BATUSDT | 617,347 | below min_events |
| GTCUSDT | 600,972 | below min_events |
| ALICEUSDT | 614,638 | below min_events |
| CVXUSDT | 571,665 | below min_events |
| USDCUSDT | 620,574 | below min_events |
| OGNUSDT | 473,678 | below min_events |
| ATAUSDT | 504,678 | below min_events |
| DEFIUSDT | 387,981 | below min_events |
| ETHBTC | 483,843 | below min_events |
| NMRUSDT | 866,063 | below min_events |

## Caveats

- Single month (2025-07) in one market regime. Order-flow memory statistics are regime-dependent (see Q8), so these results may not carry over to other months or volatility regimes.
- Each symbol's γ̂ OLS stderr understates the uncertainty (autocorrelated ACF values, as in Q1), and the understatement is heteroskedastic across the cross-section. The regression stderr and R² inherit this and are descriptive only.
- `q4_gamma_vs_activity.png` omits per-symbol error bars on γ̂, because the OLS stderr would imply a precision the estimate lacks.
- Only symbols clearing `min_events` enter the regressions, so the cross-section is a survivorship-filtered subset of the requested universe.
