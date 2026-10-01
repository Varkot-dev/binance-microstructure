# Q6: branching-ratio panel, Hawkes endogeneity cross-section

## Method

**Symbol selection**: the 41 symbols listed in the file passed as `--symbols-file`. The committed list, `results/q6_symbols_2023-06.txt`, is the deduplicated union of (a) the fixed 16-symbol panel (`results/panel_2023-06.txt`) and (b) the 40 most active symbols by June-2023 `n_events` within the 207-symbol universe (`results/universe_2023-06.txt`), ranked with the activity column in `results/q4_cross_section.parquet`. The panel was chosen to be liquid, so the two sets overlap 15/16 and the union has 41 symbols, not the ~50-56 a naive 16+40 sum suggests.

For each symbol I load one month (2023-06) of aggTrades and collapse it to aggressor-level events (`load_events`). A per-symbol exception (missing parquet, too few events for the window/guard requirements) is logged in `failures` and does not abort the run.

**Business time first.** Timestamps are rescaled to business time (`intraday_rate_profile`, 48 bins, then `rescale_to_business_time`) before any Hawkes fitting. On clock time, neither the Hawkes MLE nor the count-variance estimator can separate self-excitation from a time-varying baseline rate. A synthetic trap test (`test_regime_switching_poisson_produces_spurious_endogeneity_trap`) shows a regime-switching Poisson process with no self-excitation yields a spurious count-variance n̂ > 0.2 and a spurious MLE alpha > 0.5 (Filimonov & Sornette 2015). Crypto flow has at least that strong an intraday U-shape and funding-hour clustering. The `raw_delta` column measures the bias per symbol.

**Sub-windows**: the business-time series is split into 6 equal contiguous sub-windows, each fit with `fit_hawkes_exp` on (business_time − window_start). **Runtime cap**: a sub-window with more than 250,000 events is fit on its first 250,000 only, to bound the O(N log N) MLE cost. Multi-seed synthetic tests give a fitted-alpha sampling sd of ~0.004-0.02 at comparable sizes, small next to the spread from having only 6 windows per symbol. That sd comes from well-specified-kernel data. It does not cover exponential-kernel misspecification against a true power-law kernel (see the kernel caveat).

**alpha_median / alpha_iqr**: median and IQR of the 6 per-window alphas. **n_converged**: how many of the 6 fits reported `converged=True`. The flag means the optimizer settled, not that the parameters are well identified, especially near alpha≈1 (see the `fit_hawkes_exp` docstring).

**raw_delta**: one extra fit on the first sub-window using raw clock time, same events and cap. `raw_delta = alpha_raw − alpha_rescaled_window1`. A positive value means the clock-time fit overstates endogeneity.

**alpha_cv (count-variance n̂)**: `branching_count_variance` on the full business-time series, with window_bt = 200 business-time seconds by default. The window must be much larger than the kernel decay timescale 1/beta (typically ~0.1-2s for liquid crypto flow), or the estimator truncates the kernel's memory and biases n̂ toward 0. When 200s does not clear 20/median_beta for a symbol, the window widens to 100/median_beta.

**Cross-section**: OLS (`np.polyfit`, with intercept) of alpha_median on log10(n_events). **MLE-vs-CV agreement**: median absolute difference and Pearson correlation between alpha_median and alpha_cv.

## Run summary

Requested: 41. Successful: 41. Failed: 0.

## Panel table (sorted by n_events)

| symbol | n_events | α̂_median | α̂ IQR | n_converged/6 | n̂_CV | raw_delta | median β̂ | median μ̂ |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 21,816,890 | 0.7933 | 0.1275 | 6/6 | 0.9722 | +0.0013 | 1.2689 | 2.1440 |
| ETHUSDT | 14,239,099 | 0.6456 | 0.1146 | 6/6 | 0.9644 | -0.0069 | 2.8111 | 1.8829 |
| 1000PEPEUSDT | 12,675,042 | 0.6924 | 0.1471 | 6/6 | 0.9733 | +0.0089 | 3.2168 | 1.1404 |
| BCHUSDT | 10,755,244 | 0.7888 | 0.0774 | 6/6 | 0.9831 | -0.0006 | 0.3448 | 0.1575 |
| TOMOUSDT | 9,258,867 | 0.4069 | 0.0811 | 6/6 | 0.9669 | +0.0023 | 17.1733 | 1.8010 |
| LINAUSDT | 8,757,826 | 0.8790 | 0.0844 | 6/6 | 0.9694 | -0.0014 | 0.2710 | 0.2453 |
| MTLUSDT | 8,611,397 | 0.5802 | 0.2896 | 6/6 | 0.9786 | -0.0020 | 5.3623 | 0.6755 |
| XRPUSDT | 7,617,768 | 0.8325 | 0.3307 | 6/6 | 0.9604 | -0.0180 | 0.4510 | 0.4725 |
| SOLUSDT | 6,820,337 | 0.5708 | 0.2195 | 6/6 | 0.9662 | +0.0289 | 3.3037 | 0.9253 |
| WAVESUSDT | 6,269,680 | 0.5762 | 0.0803 | 6/6 | 0.9829 | -0.0016 | 3.7447 | 0.2714 |
| BNBUSDT | 6,122,425 | 0.7542 | 0.0732 | 6/6 | 0.9610 | +0.0024 | 0.5686 | 0.4536 |
| SUIUSDT | 6,074,349 | 0.6570 | 0.1476 | 6/6 | 0.9534 | +0.0285 | 1.6332 | 0.6392 |
| LTCUSDT | 5,400,099 | 0.8456 | 0.0307 | 6/6 | 0.9652 | +0.0146 | 0.3215 | 0.3532 |
| OPUSDT | 5,208,936 | 0.4571 | 0.1975 | 6/6 | 0.9540 | +0.0039 | 5.7358 | 1.0332 |
| MATICUSDT | 5,163,143 | 0.8476 | 0.0593 | 6/6 | 0.9600 | -0.0066 | 0.2822 | 0.2730 |
| RNDRUSDT | 5,054,960 | 0.3925 | 0.0253 | 6/6 | 0.9411 | +0.0108 | 30.1101 | 1.2860 |
| ALPHAUSDT | 4,736,244 | 0.4161 | 0.1443 | 6/6 | 0.9642 | +0.0064 | 14.8681 | 0.6145 |
| INJUSDT | 4,557,308 | 0.6102 | 0.1638 | 6/6 | 0.9382 | +0.0086 | 1.9615 | 0.7639 |
| ADAUSDT | 4,406,216 | 0.8010 | 0.0768 | 6/6 | 0.9570 | +0.0012 | 0.3273 | 0.2367 |
| ARBUSDT | 4,308,450 | 0.7070 | 0.1362 | 6/6 | 0.9465 | +0.0118 | 1.0243 | 0.5972 |
| 1000LUNCUSDT | 4,196,777 | 0.6214 | 0.2170 | 6/6 | 0.9589 | -0.0011 | 1.9625 | 0.3672 |
| STXUSDT | 4,075,254 | 0.7726 | 0.1623 | 6/6 | 0.9587 | +0.0130 | 0.5303 | 0.2134 |
| ARPAUSDT | 3,793,737 | 0.6451 | 0.0529 | 6/6 | 0.9526 | -0.0091 | 1.0991 | 0.4399 |
| LDOUSDT | 3,762,036 | 0.4260 | 0.0401 | 6/6 | 0.9367 | +0.0484 | 11.0647 | 0.8119 |
| APEUSDT | 3,687,286 | 0.8790 | 0.1104 | 6/6 | 0.9594 | +0.0006 | 0.1996 | 0.1646 |
| ETCUSDT | 3,656,191 | 0.7265 | 0.1339 | 6/6 | 0.9629 | -0.0003 | 0.6768 | 0.2425 |
| DOGEUSDT | 3,605,236 | 0.8182 | 0.1036 | 6/6 | 0.9597 | -0.0084 | 0.2378 | 0.1959 |
| CFXUSDT | 3,540,863 | 0.8273 | 0.0251 | 6/6 | 0.9448 | -0.0078 | 0.1944 | 0.1863 |
| KAVAUSDT | 3,391,557 | 0.5372 | 0.1210 | 6/6 | 0.9504 | -0.0083 | 3.4624 | 0.5089 |
| APTUSDT | 3,361,904 | 0.7696 | 0.1178 | 6/6 | 0.9420 | +0.0156 | 0.4709 | 0.2757 |
| BTCBUSD | 3,259,833 | 0.5666 | 0.0885 | 6/6 | 0.9357 | -0.0078 | 4.4147 | 0.6000 |
| COMPUSDT | 3,070,323 | 0.7705 | 0.0570 | 6/6 | 0.9724 | -0.0317 | 0.2634 | 0.0730 |
| 1000SHIBUSDT | 3,031,796 | 0.8695 | 0.0339 | 6/6 | 0.9594 | -0.0034 | 0.2190 | 0.1245 |
| EDUUSDT | 2,940,081 | 0.3719 | 0.0312 | 6/6 | 0.9304 | +0.0005 | 13.1391 | 0.6154 |
| KEYUSDT | 2,889,130 | 0.3699 | 0.3570 | 6/6 | 0.9579 | +0.0003 | 7.0978 | 0.4117 |
| SANDUSDT | 2,732,112 | 0.8193 | 0.0896 | 6/6 | 0.9541 | +0.0005 | 0.2779 | 0.1571 |
| ETHBUSD | 2,661,029 | 0.5477 | 0.1155 | 6/6 | 0.9161 | -0.0189 | 1.8750 | 0.4448 |
| LINKUSDT | 2,627,039 | 0.7948 | 0.0451 | 6/6 | 0.9420 | -0.0037 | 0.2544 | 0.1831 |
| AVAXUSDT | 2,458,978 | 0.6058 | 0.1622 | 6/6 | 0.9441 | -0.0022 | 1.4237 | 0.2963 |
| ATOMUSDT | 2,456,324 | 0.7510 | 0.0539 | 6/6 | 0.9436 | -0.0031 | 0.4176 | 0.1967 |
| IDUSDT | 2,144,610 | 0.7634 | 0.0433 | 6/6 | 0.9414 | -0.0030 | 0.2751 | 0.1900 |

## Estimator agreement

| symbol | α̂_median (MLE) | n̂_CV (count-variance) | |diff| |
|---|---|---|---|
| BTCUSDT | 0.7933 | 0.9722 | 0.1789 |
| ETHUSDT | 0.6456 | 0.9644 | 0.3189 |
| 1000PEPEUSDT | 0.6924 | 0.9733 | 0.2809 |
| BCHUSDT | 0.7888 | 0.9831 | 0.1943 |
| TOMOUSDT | 0.4069 | 0.9669 | 0.5601 |
| LINAUSDT | 0.8790 | 0.9694 | 0.0903 |
| MTLUSDT | 0.5802 | 0.9786 | 0.3984 |
| XRPUSDT | 0.8325 | 0.9604 | 0.1279 |
| SOLUSDT | 0.5708 | 0.9662 | 0.3955 |
| WAVESUSDT | 0.5762 | 0.9829 | 0.4067 |
| BNBUSDT | 0.7542 | 0.9610 | 0.2069 |
| SUIUSDT | 0.6570 | 0.9534 | 0.2963 |
| LTCUSDT | 0.8456 | 0.9652 | 0.1196 |
| OPUSDT | 0.4571 | 0.9540 | 0.4969 |
| MATICUSDT | 0.8476 | 0.9600 | 0.1124 |
| RNDRUSDT | 0.3925 | 0.9411 | 0.5486 |
| ALPHAUSDT | 0.4161 | 0.9642 | 0.5481 |
| INJUSDT | 0.6102 | 0.9382 | 0.3280 |
| ADAUSDT | 0.8010 | 0.9570 | 0.1561 |
| ARBUSDT | 0.7070 | 0.9465 | 0.2395 |
| 1000LUNCUSDT | 0.6214 | 0.9589 | 0.3375 |
| STXUSDT | 0.7726 | 0.9587 | 0.1861 |
| ARPAUSDT | 0.6451 | 0.9526 | 0.3075 |
| LDOUSDT | 0.4260 | 0.9367 | 0.5108 |
| APEUSDT | 0.8790 | 0.9594 | 0.0804 |
| ETCUSDT | 0.7265 | 0.9629 | 0.2364 |
| DOGEUSDT | 0.8182 | 0.9597 | 0.1416 |
| CFXUSDT | 0.8273 | 0.9448 | 0.1175 |
| KAVAUSDT | 0.5372 | 0.9504 | 0.4132 |
| APTUSDT | 0.7696 | 0.9420 | 0.1724 |
| BTCBUSD | 0.5666 | 0.9357 | 0.3691 |
| COMPUSDT | 0.7705 | 0.9724 | 0.2020 |
| 1000SHIBUSDT | 0.8695 | 0.9594 | 0.0899 |
| EDUUSDT | 0.3719 | 0.9304 | 0.5585 |
| KEYUSDT | 0.3699 | 0.9579 | 0.5881 |
| SANDUSDT | 0.8193 | 0.9541 | 0.1349 |
| ETHBUSD | 0.5477 | 0.9161 | 0.3685 |
| LINKUSDT | 0.7948 | 0.9420 | 0.1473 |
| AVAXUSDT | 0.6058 | 0.9441 | 0.3383 |
| ATOMUSDT | 0.7510 | 0.9436 | 0.1927 |
| IDUSDT | 0.7634 | 0.9414 | 0.1780 |

Median |α̂_median − n̂_CV| across 41 symbols: **0.2395**. Pearson correlation: **0.2597**.

## Activity regression

**α̂_median on log10(n_events)**: slope = **0.0286** (stderr 0.1094), intercept = 0.4803, R² = 0.0017, n = 41

## Findings

Across the 41 successful symbols, the median endogeneity level (median of per-symbol alpha_median) is **0.7070**, ranging from 0.3699 to 0.8790. Distance from criticality (alpha=1): **0.2930**.

**Comparison to the literature**: Mark, Sila & Weber (2022, *European Journal of Finance*) find BTC's endogeneity level, fit with power-law kernels, comparable to fiat FX markets, so crypto is not structurally different from mature, near-critical asset classes in that study. This panel's exponential-kernel median of 0.7070 is broadly consistent with a near-critical regime at face value. Given the exponential-kernel caveat below, it is a lower bound on the true (power-law) endogeneity level and not directly comparable to that literature's power-law fits.

The slope of α̂_median on log-activity across the panel (slope 0.0286, stderr 0.1094, |t| = 0.3, R² 0.0017, n=41) is within 2 standard errors of zero, so it is indistinguishable from no relationship with activity.

**The two branching-ratio estimators disagree substantially.** The median absolute difference is 0.2395 (Pearson correlation 0.2597, weak positive, not a strong cross-check), and the gap is one-directional: count-variance reads higher than the MLE for 41/41 symbols (100%), not just on average (median n̂_CV ≈ 0.9587 vs. median α̂_median ≈ 0.7070). Two explanations, not mutually exclusive. (1) Exponential-kernel misspecification: if the true kernel is a slowly decaying power law, the exponential MLE truncates long-range excitation and understates alpha, while `branching_count_variance` assumes no kernel shape. A gap in this direction fits that, but not uniquely. (2) Window sensitivity: n̂_CV uses one fixed 200s window per symbol, and its large-window asymptotic is approximate at any finite window (see the `branching_count_variance` docstring). The data here cannot separate the two. A power-law-kernel MLE refit and a window sweep on alpha_cv would, and I did not run either.

**The seasonality bias is near zero.** Median raw-vs-rescaled delta across the panel: **-0.0003** (largest magnitude across all symbols: 0.0484). A clock-time-only fit would have mismeasured alpha by only a small fraction of a unit. That reflects this market, not a redundant correction: crypto futures trade 24/7 with no open/close or dominant regional session, and the 48-bin `intraday_rate_profile` is close to flat, so `rescale_to_business_time` is close to the identity. By contrast, the synthetic seasonal-baseline Hawkes test in `test_eventtime.py` used a deep intraday trough (shape amplitude as low as 1.05x baseline). Its raw-fit alpha was inflated by +0.22 to +0.55 over truth, and this pipeline rescaled it back to within ~0.01. The fix works when the confound is large, and here the confound is small. I apply it to every symbol since the profile's flatness is not known in advance.

## Caveats

- **Single month** (2023-06): one market regime. Endogeneity levels are plausibly regime-dependent (activity, volatility) and may not carry over to other months.
- **Exponential kernel only**: per Hardiman & Bouchaud (2014) and the broader power-law-kernel literature, an exponential kernel fit to data with a true slowly decaying power-law kernel understates the branching ratio, because its finite memory truncates the long-range contribution. Read the alpha estimates as lower-bound-flavored, not exact. A power-law-kernel refit would likely push every number in the table up, possibly materially.
- **Convergence flag**: `n_converged` only says the Nelder-Mead search stopped improving locally. Near alpha≈1 the likelihood has a shallow mu-alpha ridge (`fit_hawkes_exp` docstring), so `converged=True` there is a weak signal.
- **Runtime cap** (250,000 events/window): windows above the cap are fit on a truncated prefix, so their alpha reflects only the earliest events of the window.
- **Count-variance window (200s default)**: fixed apart from the 20/median_beta widening. A different window could shift alpha_cv, especially near that threshold.
- **Heteroskedasticity in the activity regression**: alpha_iqr varies across the cross-section, so the OLS homoskedasticity assumption is almost certainly violated. The slope, R² and stderr are descriptive.
- **48-bin intraday profile**: it is estimated from the same month being fit, so real self-excitation clustering at the same time-of-day scale (unlikely at ~30-minute resolution, but not provably absent) could be removed with the seasonal confound.
