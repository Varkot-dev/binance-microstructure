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

Requested: 371. Successful: 231. Skipped (below min_events): 138. Failed: 2.

## Highest activity (10 by n_events)

| symbol | n_events | γ̂ | stderr | acf1 | p_flip | zigzag | total_qty |
|---|---|---|---|---|---|---|---|
| BANKUSDT | 32,898,387 | 0.2173 | 0.0054 | 0.1582 | 0.4209 | -0.0081 | 89,701,825,749.00 |
| SNDKUSDT | 27,279,429 | 0.1880 | 0.0096 | 0.2761 | 0.3619 | -0.0083 | 52,815,771.38 |
| SKHYNIXUSDT | 24,951,484 | 0.3161 | 0.0052 | 0.3505 | 0.3247 | -0.0161 | 44,565,626.57 |
| LABUSDT | 23,902,396 | 0.2141 | 0.0054 | 0.0996 | 0.4502 | 0.0014 | 16,093,992,606.00 |
| AKEUSDT | 21,209,407 | 0.2376 | 0.0035 | 0.1734 | 0.4133 | -0.0066 | 5,668,378,742,671.00 |
| SOXLUSDT | 19,377,268 | 0.1938 | 0.0100 | 0.1961 | 0.4020 | -0.0099 | 331,885,415.75 |
| MUUSDT | 16,103,431 | 0.2619 | 0.0100 | 0.3193 | 0.3403 | -0.0178 | 40,422,924.48 |
| ETHUSDT | 15,881,884 | 0.4164 | 0.0026 | 0.0764 | 0.4618 | 0.0400 | 117,588,875.54 |
| EVAAUSDT | 15,784,562 | 0.1991 | 0.0054 | 0.2360 | 0.3820 | -0.0198 | 3,577,012,792.70 |
| BTCUSDT | 14,577,970 | 0.4513 | 0.0012 | 0.0235 | 0.4882 | 0.0535 | 4,297,823.62 |

## Lowest activity (10 by n_events)

| symbol | n_events | γ̂ | stderr | acf1 | p_flip | zigzag | total_qty |
|---|---|---|---|---|---|---|---|
| NOMUSDT | 1,043,577 | 0.3539 | 0.0046 | 0.0931 | 0.4532 | -0.0021 | 151,714,219,538.00 |
| AGLDUSDT | 1,042,817 | 0.1386 | 0.0016 | 0.0964 | 0.4518 | -0.0006 | 1,615,003,566.00 |
| AAPLUSDT | 1,037,826 | 0.2818 | 0.0070 | 0.2974 | 0.3512 | 0.0162 | 2,686,391.36 |
| RPLUSDT | 1,032,909 | 0.1605 | 0.0015 | 0.0981 | 0.4506 | 0.0006 | 127,638,615.90 |
| XRPUSDC | 1,017,998 | 0.5741 | 0.0190 | 0.2968 | 0.3516 | -0.0348 | 1,203,092,425.20 |
| KATUSDT | 1,014,675 | 0.1766 | 0.0026 | 0.2518 | 0.3741 | -0.0247 | 32,482,259,912.00 |
| ETCUSDT | 1,009,838 | 0.1215 | 0.0009 | 0.2366 | 0.3817 | -0.0144 | 78,099,559.52 |
| XAUTUSDT | 1,008,105 | 0.1495 | 0.0015 | 0.2434 | 0.3777 | -0.0071 | 199,679.91 |
| AIOUSDT | 1,001,329 | 0.0936 | 0.0006 | 0.2790 | 0.3591 | -0.0160 | 1,668,226,603.00 |
| YFIUSDT | 1,001,164 | 0.3201 | 0.0041 | 0.0184 | 0.4908 | 0.0135 | 233,071.32 |

## Cross-sectional regressions

**γ̂ on log10(n_events)**: slope = **0.0612** (stderr 0.0286), intercept = -0.1520, R² = 0.0196, n = 231

**p_flip on log10(n_events)**: slope = **0.0006** (stderr 0.0126), intercept = 0.3917, R² = 0.0000, n = 231

## Findings

The fitted order-flow memory exponent γ̂ **increases** with log-activity across the 231-symbol successful set (slope 0.0612, R² 0.0196), i.e. more actively traded symbols in this sample tend to show stronger long-memory decay than less actively traded ones.

The sign-flip probability p_flip **increases** with log-activity (slope 0.0006, R² 0.0000); since p_flip = 0.5 corresponds to no persistence, this indicates that persistence weakens as activity increases (a slope above zero means p_flip rises toward more anti-persistent behavior at higher activity).

## Failures

| symbol | reason |
|---|---|
| TREEUSDT | parquet not found: data/parquet/aggTrades/TREEUSDT/2026-07.parquet |
| FARTCOINUSDT | parquet not found: data/parquet/aggTrades/FARTCOINUSDT/2026-07.parquet |

## Skipped (below min_events)

| symbol | n_events | reason |
|---|---|---|
| GPSUSDT | 993,586 | below min_events |
| QUSDT | 799,458 | below min_events |
| TSMUSDT | 982,417 | below min_events |
| ZEREBROUSDT | 777,816 | below min_events |
| STARUSDT | 828,842 | below min_events |
| HANAUSDT | 948,189 | below min_events |
| DELLUSDT | 792,035 | below min_events |
| SCRTUSDT | 978,723 | below min_events |
| TRADOORUSDT | 949,059 | below min_events |
| HOTUSDT | 947,496 | below min_events |
| PEOPLEUSDT | 983,649 | below min_events |
| HOLOUSDT | 912,599 | below min_events |
| MANTRAUSDT | 954,566 | below min_events |
| AIOTUSDT | 777,762 | below min_events |
| IBMUSDT | 868,208 | below min_events |
| FFUSDT | 964,976 | below min_events |
| CHILLGUYUSDT | 719,447 | below min_events |
| NILUSDT | 898,527 | below min_events |
| PLAYUSDT | 853,371 | below min_events |
| ACHUSDT | 920,286 | below min_events |
| MEUSDT | 877,719 | below min_events |
| CATIUSDT | 876,818 | below min_events |
| SPELLUSDT | 994,093 | below min_events |
| ALCHUSDT | 902,495 | below min_events |
| MSFTUSDT | 757,268 | below min_events |
| YBUSDT | 761,377 | below min_events |
| ACTUSDT | 980,406 | below min_events |
| PIPPINUSDT | 969,779 | below min_events |
| TURBOUSDT | 779,113 | below min_events |
| OGNUSDT | 958,354 | below min_events |
| TNSRUSDT | 945,168 | below min_events |
| ELSAUSDT | 780,798 | below min_events |
| RKLBUSDT | 866,433 | below min_events |
| RESOLVUSDT | 954,000 | below min_events |
| XNYUSDT | 626,880 | below min_events |
| AXTIUSDT | 778,476 | below min_events |
| TSTUSDT | 656,249 | below min_events |
| ZILUSDT | 890,921 | below min_events |
| SENTUSDT | 979,353 | below min_events |
| CELOUSDT | 803,131 | below min_events |
| ORCLUSDT | 773,992 | below min_events |
| 1000LUNCUSDT | 919,921 | below min_events |
| BANANAS31USDT | 699,214 | below min_events |
| TQQQUSDT | 989,432 | below min_events |
| GUSDT | 790,807 | below min_events |
| GUNUSDT | 794,360 | below min_events |
| WIFUSDT | 965,574 | below min_events |
| SEIUSDT | 903,891 | below min_events |
| NEIROUSDT | 712,896 | below min_events |
| AIAUSDT | 678,804 | below min_events |
| POLUSDT | 853,554 | below min_events |
| CAKEUSDT | 762,005 | below min_events |
| AAVEUSDC | 947,454 | below min_events |
| QCOMUSDT | 668,171 | below min_events |
| ZESTUSDT | 543,592 | below min_events |
| SPACEUSDT | 739,562 | below min_events |
| GALAUSDT | 849,002 | below min_events |
| 1000CHEEMSUSDT | 772,150 | below min_events |
| ICPUSDT | 994,228 | below min_events |
| CROSSUSDT | 559,554 | below min_events |
| STABLEUSDT | 800,407 | below min_events |
| AMATUSDT | 609,932 | below min_events |
| KAITOUSDC | 783,652 | below min_events |
| SLPUSDT | 656,133 | below min_events |
| BICOUSDT | 836,834 | below min_events |
| JSTUSDT | 751,460 | below min_events |
| AUSDT | 664,788 | below min_events |
| JELLYJELLYUSDT | 717,130 | below min_events |
| STORJUSDT | 697,656 | below min_events |
| SAFEUSDT | 607,404 | below min_events |
| BIOUSDT | 815,799 | below min_events |
| CCUSDT | 668,254 | below min_events |
| COAIUSDT | 727,128 | below min_events |
| ENAUSDC | 814,105 | below min_events |
| ARIAUSDT | 718,404 | below min_events |
| ZORAUSDT | 683,031 | below min_events |
| NAORISUSDT | 665,194 | below min_events |
| SPXUSDT | 777,634 | below min_events |
| EDENUSDT | 699,682 | below min_events |
| HYPERUSDT | 647,460 | below min_events |
| ONEUSDT | 745,972 | below min_events |
| TOWNSUSDT | 695,752 | below min_events |
| SKYUSDT | 744,146 | below min_events |
| MANAUSDT | 719,991 | below min_events |
| APRUSDT | 729,909 | below min_events |
| ARCUSDT | 611,771 | below min_events |
| WLDUSDC | 788,207 | below min_events |
| PLTRUSDT | 631,092 | below min_events |
| TAKEUSDT | 677,295 | below min_events |
| STGUSDT | 830,723 | below min_events |
| LAYERUSDT | 679,832 | below min_events |
| ATOMUSDT | 837,588 | below min_events |
| GENIUSUSDT | 719,898 | below min_events |
| AVGOUSDT | 554,616 | below min_events |
| BRUSDT | 527,644 | below min_events |
| BCHUSDC | 677,867 | below min_events |
| SANDUSDT | 727,999 | below min_events |
| FLOCKUSDT | 626,153 | below min_events |
| CHZUSDT | 763,155 | below min_events |
| AWEUSDT | 606,078 | below min_events |
| DOGEUSDC | 716,261 | below min_events |
| LYNUSDT | 574,525 | below min_events |
| CRVUSDT | 718,109 | below min_events |
| AINUSDT | 514,126 | below min_events |
| CFXUSDT | 642,676 | below min_events |
| BANANAUSDT | 640,595 | below min_events |
| ZKCUSDT | 601,762 | below min_events |
| PRLUSDT | 653,582 | below min_events |
| IOTAUSDT | 623,810 | below min_events |
| ALICEUSDT | 696,119 | below min_events |
| MEMEUSDT | 550,355 | below min_events |
| BABAUSDT | 574,939 | below min_events |
| COLLECTUSDT | 454,313 | below min_events |
| ALGOUSDT | 670,866 | below min_events |
| ARBUSDC | 643,384 | below min_events |
| METUSDT | 681,683 | below min_events |
| ROBOUSDT | 676,942 | below min_events |
| SAGAUSDT | 692,311 | below min_events |
| PIXELUSDT | 546,789 | below min_events |
| SUIUSDC | 670,368 | below min_events |
| STXUSDT | 756,215 | below min_events |
| PNUTUSDT | 627,567 | below min_events |
| MITOUSDT | 584,491 | below min_events |
| NOTUSDT | 583,572 | below min_events |
| 0GUSDT | 667,157 | below min_events |
| EGLDUSDT | 633,139 | below min_events |
| SAPIENUSDT | 481,219 | below min_events |
| INXUSDT | 465,764 | below min_events |
| AMZNUSDT | 505,164 | below min_events |
| VANAUSDT | 676,571 | below min_events |
| APEUSDT | 667,991 | below min_events |
| ICNTUSDT | 647,883 | below min_events |
| BERAUSDT | 644,775 | below min_events |
| JASMYUSDT | 546,964 | below min_events |
| BTCUSD1 | 584,917 | below min_events |
| REZUSDT | 558,745 | below min_events |
| SPORTFUNUSDT | 539,814 | below min_events |
| CUSDT | 466,297 | below min_events |

## Caveats

- Single month (2026-07); this is one specific market regime, and per Phase 1.5 diagnostics, order-flow memory statistics are regime-dependent — these results may not generalize to other months or volatility regimes.
- Each symbol's γ̂ OLS stderr understates true uncertainty (autocorrelated ACF values violate the i.i.d.-residual assumption, same caveat as Q1), and this understatement is heteroskedastic across the cross-section (see Methodology); the cross-sectional regression stderr/R² inherit this problem and should be read as descriptive summaries, not as valid confidence intervals.
- `q4_gamma_vs_activity.png` deliberately omits per-symbol error bars on γ̂: plotting the OLS stderr would imply a precision the estimate does not have, for the same heteroskedasticity/understatement reason given above.
- Symbols are only included in the regressions if they clear `min_events`; the cross-section is therefore a survivorship-filtered subset of the requested universe, not the full universe.
