# Q6: branching-ratio panel, Hawkes endogeneity cross-section

## Method

**Symbol selection**: the 41 symbols listed in the file passed as `--symbols-file`. The committed list, `results/q6_symbols_2023-06.txt`, is the deduplicated union of (a) the fixed 16-symbol panel (`results/panel_2023-06.txt`) and (b) the 40 most active symbols by June-2023 `n_events` within the 207-symbol universe (`results/universe_2023-06.txt`), ranked with the activity column in `results/q4_cross_section.parquet`. The panel was chosen to be liquid, so the two sets overlap 15/16 and the union has 41 symbols, not the ~50-56 a naive 16+40 sum suggests.

For each symbol I load one month (2024-07) of aggTrades and collapse it to aggressor-level events (`load_events`). A per-symbol exception (missing parquet, too few events for the window/guard requirements) is logged in `failures` and does not abort the run.

**Business time first.** Timestamps are rescaled to business time (`intraday_rate_profile`, 48 bins, then `rescale_to_business_time`) before any Hawkes fitting. On clock time, neither the Hawkes MLE nor the count-variance estimator can separate self-excitation from a time-varying baseline rate. A synthetic trap test (`test_regime_switching_poisson_produces_spurious_endogeneity_trap`) shows a regime-switching Poisson process with no self-excitation yields a spurious count-variance n̂ > 0.2 and a spurious MLE alpha > 0.5 (Filimonov & Sornette 2015). Crypto flow has at least that strong an intraday U-shape and funding-hour clustering. The `raw_delta` column measures the bias per symbol.

**Sub-windows**: the business-time series is split into 6 equal contiguous sub-windows, each fit with `fit_hawkes_exp` on (business_time − window_start). **Runtime cap**: a sub-window with more than 250,000 events is fit on its first 250,000 only, to bound the O(N log N) MLE cost. Multi-seed synthetic tests give a fitted-alpha sampling sd of ~0.004-0.02 at comparable sizes, small next to the spread from having only 6 windows per symbol. That sd comes from well-specified-kernel data. It does not cover exponential-kernel misspecification against a true power-law kernel (see the kernel caveat).

**alpha_median / alpha_iqr**: median and IQR of the 6 per-window alphas. **n_converged**: how many of the 6 fits reported `converged=True`. The flag means the optimizer settled, not that the parameters are well identified, especially near alpha≈1 (see the `fit_hawkes_exp` docstring).

**raw_delta**: one extra fit on the first sub-window using raw clock time, same events and cap. `raw_delta = alpha_raw − alpha_rescaled_window1`. A positive value means the clock-time fit overstates endogeneity.

**alpha_cv (count-variance n̂)**: `branching_count_variance` on the full business-time series, with window_bt = 200 business-time seconds by default. The window must be much larger than the kernel decay timescale 1/beta (typically ~0.1-2s for liquid crypto flow), or the estimator truncates the kernel's memory and biases n̂ toward 0. When 200s does not clear 20/median_beta for a symbol, the window widens to 100/median_beta.

**Cross-section**: OLS (`np.polyfit`, with intercept) of alpha_median on log10(n_events). **MLE-vs-CV agreement**: median absolute difference and Pearson correlation between alpha_median and alpha_cv.

## Run summary

Requested: 41. Successful: 37. Failed: 4.

## Panel table (sorted by n_events)

| symbol | n_events | α̂_median | α̂ IQR | n_converged/6 | n̂_CV | raw_delta | median β̂ | median μ̂ |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 19,778,926 | 0.7024 | 0.1101 | 6/6 | 0.9645 | +0.0562 | 2.2520 | 1.9684 |
| ETHUSDT | 16,822,580 | 0.3874 | 0.3574 | 6/6 | 0.9642 | +0.3541 | 43.8334 | 3.5550 |
| 1000PEPEUSDT | 16,506,240 | 0.3629 | 0.0830 | 6/6 | 0.9646 | +0.0063 | 97.4531 | 3.5654 |
| SOLUSDT | 11,732,154 | 0.2994 | 0.1754 | 6/6 | 0.9558 | +0.0072 | 72.0070 | 2.8820 |
| DOGEUSDT | 7,228,607 | 0.7528 | 0.0891 | 6/6 | 0.9460 | +0.0324 | 0.3954 | 0.6139 |
| XRPUSDT | 7,169,683 | 0.7609 | 0.1370 | 6/6 | 0.9374 | +0.0207 | 0.3876 | 0.6086 |
| BNBUSDT | 5,855,297 | 0.3518 | 0.4299 | 6/6 | 0.9419 | +0.0057 | 42.4413 | 1.0657 |
| AVAXUSDT | 5,370,146 | 0.2675 | 0.0648 | 6/6 | 0.9367 | +0.0021 | 69.6392 | 1.2831 |
| 1000SHIBUSDT | 5,251,131 | 0.2622 | 0.1490 | 6/6 | 0.9477 | +0.0018 | 86.6292 | 1.2476 |
| BCHUSDT | 4,708,401 | 0.3077 | 0.0596 | 6/6 | 0.9417 | +0.0023 | 67.4915 | 1.0846 |
| LDOUSDT | 4,340,832 | 0.3286 | 0.0666 | 6/6 | 0.9399 | +0.0019 | 49.7262 | 1.0230 |
| INJUSDT | 4,320,486 | 0.2741 | 0.0367 | 6/6 | 0.9290 | +0.0013 | 75.6899 | 0.9797 |
| OPUSDT | 4,068,054 | 0.2491 | 0.1322 | 6/6 | 0.9358 | +0.0013 | 74.2189 | 1.0840 |
| STXUSDT | 3,587,265 | 0.2948 | 0.0513 | 6/6 | 0.9299 | +0.0101 | 51.7130 | 0.7727 |
| LINKUSDT | 3,461,497 | 0.5389 | 0.1604 | 6/6 | 0.9309 | +0.1831 | 1.9775 | 0.5974 |
| ADAUSDT | 3,150,409 | 0.7444 | 0.0412 | 6/6 | 0.9074 | +0.0178 | 0.2254 | 0.2996 |
| ARBUSDT | 2,845,513 | 0.7610 | 0.0509 | 6/6 | 0.9359 | +0.0060 | 0.2773 | 0.2241 |
| ETCUSDT | 2,736,088 | 0.3004 | 0.1025 | 6/6 | 0.9356 | +0.0539 | 31.5347 | 0.6308 |
| CFXUSDT | 2,515,259 | 0.2930 | 0.0442 | 6/6 | 0.9181 | +0.0046 | 31.2900 | 0.6230 |
| RNDRUSDT | 2,482,363 | 0.3112 | 0.0266 | 6/6 | 0.9357 | +0.0028 | 92.7517 | 1.0974 |
| MATICUSDT | 2,472,575 | 0.7903 | 0.0639 | 6/6 | 0.9214 | +0.0108 | 0.1907 | 0.1997 |
| SUIUSDT | 2,465,133 | 0.4998 | 0.2744 | 6/6 | 0.9222 | +0.0132 | 2.2091 | 0.4840 |
| LTCUSDT | 2,029,268 | 0.7278 | 0.0473 | 6/6 | 0.9206 | +0.0032 | 0.2689 | 0.2042 |
| APEUSDT | 2,004,938 | 0.4847 | 0.0737 | 6/6 | 0.9179 | +0.0619 | 2.0644 | 0.3413 |
| APTUSDT | 1,906,979 | 0.6160 | 0.1624 | 6/6 | 0.9119 | +0.0224 | 0.4533 | 0.2517 |
| 1000LUNCUSDT | 1,735,389 | 0.2778 | 0.0896 | 6/6 | 0.9389 | +0.0050 | 27.5902 | 0.4067 |
| EDUUSDT | 1,689,691 | 0.2289 | 0.3026 | 6/6 | 0.9370 | +0.0073 | 25.4639 | 0.3269 |
| ATOMUSDT | 1,567,380 | 0.7052 | 0.0967 | 6/6 | 0.9187 | +0.0093 | 0.2459 | 0.1641 |
| IDUSDT | 1,535,068 | 0.3741 | 0.0639 | 6/6 | 0.9085 | +0.0119 | 13.7640 | 0.3376 |
| MTLUSDT | 1,110,311 | 0.3564 | 0.0309 | 6/6 | 0.8953 | +0.0483 | 13.8554 | 0.2258 |
| SANDUSDT | 1,089,634 | 0.6661 | 0.0868 | 6/6 | 0.8956 | +0.0066 | 0.2406 | 0.1205 |
| COMPUSDT | 1,016,100 | 0.7095 | 0.1186 | 6/6 | 0.9037 | +0.0022 | 0.1500 | 0.0853 |
| ALPHAUSDT | 721,547 | 0.3860 | 0.2426 | 6/6 | 0.8516 | +0.0430 | 1.7983 | 0.1480 |
| ARPAUSDT | 700,331 | 0.7092 | 0.0906 | 6/6 | 0.9142 | +0.0024 | 0.1102 | 0.0591 |
| KEYUSDT | 641,600 | 0.4845 | 0.2666 | 6/6 | 0.8770 | +0.0147 | 0.6716 | 0.1045 |
| KAVAUSDT | 627,946 | 0.5999 | 0.2842 | 6/6 | 0.8724 | +0.0113 | 0.2173 | 0.0821 |
| LINAUSDT | 467,389 | 0.4267 | 0.2241 | 6/6 | 0.8231 | +0.0181 | 0.4394 | 0.0881 |

## Estimator agreement

| symbol | α̂_median (MLE) | n̂_CV (count-variance) | |diff| |
|---|---|---|---|
| BTCUSDT | 0.7024 | 0.9645 | 0.2620 |
| ETHUSDT | 0.3874 | 0.9642 | 0.5768 |
| 1000PEPEUSDT | 0.3629 | 0.9646 | 0.6017 |
| SOLUSDT | 0.2994 | 0.9558 | 0.6564 |
| DOGEUSDT | 0.7528 | 0.9460 | 0.1931 |
| XRPUSDT | 0.7609 | 0.9374 | 0.1764 |
| BNBUSDT | 0.3518 | 0.9419 | 0.5900 |
| AVAXUSDT | 0.2675 | 0.9367 | 0.6691 |
| 1000SHIBUSDT | 0.2622 | 0.9477 | 0.6855 |
| BCHUSDT | 0.3077 | 0.9417 | 0.6341 |
| LDOUSDT | 0.3286 | 0.9399 | 0.6113 |
| INJUSDT | 0.2741 | 0.9290 | 0.6549 |
| OPUSDT | 0.2491 | 0.9358 | 0.6867 |
| STXUSDT | 0.2948 | 0.9299 | 0.6351 |
| LINKUSDT | 0.5389 | 0.9309 | 0.3920 |
| ADAUSDT | 0.7444 | 0.9074 | 0.1630 |
| ARBUSDT | 0.7610 | 0.9359 | 0.1749 |
| ETCUSDT | 0.3004 | 0.9356 | 0.6353 |
| CFXUSDT | 0.2930 | 0.9181 | 0.6252 |
| RNDRUSDT | 0.3112 | 0.9357 | 0.6245 |
| MATICUSDT | 0.7903 | 0.9214 | 0.1311 |
| SUIUSDT | 0.4998 | 0.9222 | 0.4224 |
| LTCUSDT | 0.7278 | 0.9206 | 0.1928 |
| APEUSDT | 0.4847 | 0.9179 | 0.4332 |
| APTUSDT | 0.6160 | 0.9119 | 0.2959 |
| 1000LUNCUSDT | 0.2778 | 0.9389 | 0.6612 |
| EDUUSDT | 0.2289 | 0.9370 | 0.7080 |
| ATOMUSDT | 0.7052 | 0.9187 | 0.2135 |
| IDUSDT | 0.3741 | 0.9085 | 0.5344 |
| MTLUSDT | 0.3564 | 0.8953 | 0.5389 |
| SANDUSDT | 0.6661 | 0.8956 | 0.2296 |
| COMPUSDT | 0.7095 | 0.9037 | 0.1942 |
| ALPHAUSDT | 0.3860 | 0.8516 | 0.4656 |
| ARPAUSDT | 0.7092 | 0.9142 | 0.2050 |
| KEYUSDT | 0.4845 | 0.8770 | 0.3925 |
| KAVAUSDT | 0.5999 | 0.8724 | 0.2726 |
| LINAUSDT | 0.4267 | 0.8231 | 0.3963 |

Median |α̂_median − n̂_CV| across 37 symbols: **0.4656**. Pearson correlation: **-0.1540**.

## Activity regression

**α̂_median on log10(n_events)**: slope = **-0.0666** (stderr 0.0782), intercept = 0.9040, R² = 0.0203, n = 37

## Findings

Across the 37 successful symbols, the median endogeneity level (median of per-symbol alpha_median) is **0.3874**, ranging from 0.2289 to 0.7903. Distance from criticality (alpha=1): **0.6126**.

**Comparison to the literature**: Mark, Sila & Weber (2022, *European Journal of Finance*) find BTC's endogeneity level, fit with power-law kernels, comparable to fiat FX markets, so crypto is not structurally different from mature, near-critical asset classes in that study. This panel's exponential-kernel median of 0.3874 is well below a near-critical regime at face value. Given the exponential-kernel caveat below, it is a lower bound on the true (power-law) endogeneity level and not directly comparable to that literature's power-law fits.

The slope of α̂_median on log-activity across the panel (slope -0.0666, stderr 0.0782, |t| = 0.9, R² 0.0203, n=37) is within 2 standard errors of zero, so it is indistinguishable from no relationship with activity.

**The two branching-ratio estimators disagree substantially.** The median absolute difference is 0.4656 (Pearson correlation -0.1540, weak negative, not a strong cross-check), and the gap is one-directional: count-variance reads higher than the MLE for 37/37 symbols (100%), not just on average (median n̂_CV ≈ 0.9299 vs. median α̂_median ≈ 0.3874). Two explanations, not mutually exclusive. (1) Exponential-kernel misspecification: if the true kernel is a slowly decaying power law, the exponential MLE truncates long-range excitation and understates alpha, while `branching_count_variance` assumes no kernel shape. A gap in this direction fits that, but not uniquely. (2) Window sensitivity: n̂_CV uses one fixed 200s window per symbol, and its large-window asymptotic is approximate at any finite window (see the `branching_count_variance` docstring). The data here cannot separate the two. A power-law-kernel MLE refit and a window sweep on alpha_cv would, and I did not run either.

Median raw-vs-rescaled seasonality-bias delta across the panel: **+0.0093** (largest magnitude: 0.3541), the typical amount by which a clock-time-only fit would have mismeasured endogeneity relative to the business-time estimate on this data.

## Failures

| symbol | reason |
|---|---|
| TOMOUSDT | parquet not found: data/parquet/aggTrades/TOMOUSDT/2024-07.parquet |
| WAVESUSDT | parquet not found: data/parquet/aggTrades/WAVESUSDT/2024-07.parquet |
| BTCBUSD | parquet not found: data/parquet/aggTrades/BTCBUSD/2024-07.parquet |
| ETHBUSD | parquet not found: data/parquet/aggTrades/ETHBUSD/2024-07.parquet |

## Caveats

- **Single month** (2024-07): one market regime. Endogeneity levels are plausibly regime-dependent (activity, volatility) and may not carry over to other months.
- **Exponential kernel only**: per Hardiman & Bouchaud (2014) and the broader power-law-kernel literature, an exponential kernel fit to data with a true slowly decaying power-law kernel understates the branching ratio, because its finite memory truncates the long-range contribution. Read the alpha estimates as lower-bound-flavored, not exact. A power-law-kernel refit would likely push every number in the table up, possibly materially.
- **Convergence flag**: `n_converged` only says the Nelder-Mead search stopped improving locally. Near alpha≈1 the likelihood has a shallow mu-alpha ridge (`fit_hawkes_exp` docstring), so `converged=True` there is a weak signal.
- **Runtime cap** (250,000 events/window): windows above the cap are fit on a truncated prefix, so their alpha reflects only the earliest events of the window.
- **Count-variance window (200s default)**: fixed apart from the 20/median_beta widening. A different window could shift alpha_cv, especially near that threshold.
- **Heteroskedasticity in the activity regression**: alpha_iqr varies across the cross-section, so the OLS homoskedasticity assumption is almost certainly violated. The slope, R² and stderr are descriptive.
- **48-bin intraday profile**: it is estimated from the same month being fit, so real self-excitation clustering at the same time-of-day scale (unlikely at ~30-minute resolution, but not provably absent) could be removed with the seasonal confound.
