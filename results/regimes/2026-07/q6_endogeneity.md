# Q6: branching-ratio panel, Hawkes endogeneity cross-section

## Method

**Symbol selection**: the 41-symbol union of (a) the fixed 16-symbol panel (`results/panel_2023-06.txt`) and (b) the top `--top-n` (default 40) symbols by June-2023 `n_events` within the 207-symbol universe (`results/universe_2023-06.txt`), ranked with the activity column in `results/q4_cross_section.parquet`. The union is deduplicated (`results/q6_symbols_2023-06.txt`). The panel was chosen to be liquid, so the two sets overlap 15/16 and the union has 41 symbols, not the ~50-56 a naive 16+40 sum suggests.

For each symbol I load one month (2026-07) of aggTrades and collapse it to aggressor-level events (`load_events`). A per-symbol exception (missing parquet, too few events for the window/guard requirements) is logged in `failures` and does not abort the run.

**Business time first.** Timestamps are rescaled to business time (`intraday_rate_profile`, 48 bins, then `rescale_to_business_time`) before any Hawkes fitting. On clock time, neither the Hawkes MLE nor the count-variance estimator can separate self-excitation from a time-varying baseline rate. A synthetic trap test (`test_regime_switching_poisson_produces_spurious_endogeneity_trap`) shows a regime-switching Poisson process with no self-excitation yields a spurious count-variance n̂ > 0.2 and a spurious MLE alpha > 0.5 (Filimonov & Sornette 2015). Crypto flow has at least that strong an intraday U-shape and funding-hour clustering. The `raw_delta` column measures the bias per symbol.

**Sub-windows**: the business-time series is split into 6 equal contiguous sub-windows, each fit with `fit_hawkes_exp` on (business_time − window_start). **Runtime cap**: a sub-window with more than 250,000 events is fit on its first 250,000 only, to bound the O(N log N) MLE cost. Multi-seed synthetic tests give a fitted-alpha sampling sd of ~0.004-0.02 at comparable sizes, small next to the spread from having only 6 windows per symbol. That sd comes from well-specified-kernel data. It does not cover exponential-kernel misspecification against a true power-law kernel (see the kernel caveat).

**alpha_median / alpha_iqr**: median and IQR of the 6 per-window alphas. **n_converged**: how many of the 6 fits reported `converged=True`. The flag means the optimizer settled, not that the parameters are well identified, especially near alpha≈1 (see the `fit_hawkes_exp` docstring).

**raw_delta**: one extra fit on the first sub-window using raw clock time, same events and cap. `raw_delta = alpha_raw − alpha_rescaled_window1`. A positive value means the clock-time fit overstates endogeneity.

**alpha_cv (count-variance n̂)**: `branching_count_variance` on the full business-time series, with window_bt = 200 business-time seconds by default. The window must be much larger than the kernel decay timescale 1/beta (typically ~0.1-2s for liquid crypto flow), or the estimator truncates the kernel's memory and biases n̂ toward 0. When 200s does not clear 20/median_beta for a symbol, the window widens to 100/median_beta.

**Cross-section**: OLS (`np.polyfit`, with intercept) of alpha_median on log10(n_events). **MLE-vs-CV agreement**: median absolute difference and Pearson correlation between alpha_median and alpha_cv.

## Run summary

Requested: 41. Successful: 32. Failed: 9.

## Panel table (sorted by n_events)

| symbol | n_events | α̂_median | α̂ IQR | n_converged/6 | n̂_CV | raw_delta | median β̂ | median μ̂ |
|---|---|---|---|---|---|---|---|---|
| ETHUSDT | 15,881,884 | 0.3040 | 0.0423 | 6/6 | 0.9587 | +0.0031 | 146.5841 | 4.4306 |
| BTCUSDT | 14,577,970 | 0.2536 | 0.0746 | 6/6 | 0.9517 | +0.0069 | 112.3620 | 3.8930 |
| SOLUSDT | 6,549,774 | 0.8235 | 0.0478 | 6/6 | 0.9168 | +0.0382 | 0.2174 | 0.4263 |
| 1000PEPEUSDT | 5,365,105 | 0.3665 | 0.0389 | 6/6 | 0.9373 | +0.0105 | 116.6136 | 1.1750 |
| BNBUSDT | 4,812,418 | 0.1696 | 0.0644 | 6/6 | 0.8965 | +0.0061 | 118.3102 | 1.5755 |
| XRPUSDT | 4,561,673 | 0.7929 | 0.0205 | 6/6 | 0.8996 | +0.0252 | 0.2192 | 0.3764 |
| DOGEUSDT | 3,576,542 | 0.7462 | 0.0463 | 6/6 | 0.8918 | +0.0631 | 0.2587 | 0.3403 |
| BCHUSDT | 3,266,519 | 0.2771 | 0.0925 | 6/6 | 0.9260 | +0.0045 | 106.7218 | 0.8098 |
| AVAXUSDT | 2,595,579 | 0.6708 | 0.0698 | 6/6 | 0.8826 | +0.0359 | 0.3061 | 0.3250 |
| SUIUSDT | 2,557,444 | 0.6739 | 0.0676 | 6/6 | 0.8793 | +0.0880 | 0.3059 | 0.2963 |
| ADAUSDT | 2,556,427 | 0.7729 | 0.0203 | 6/6 | 0.8737 | +0.0132 | 0.1392 | 0.2149 |
| ARBUSDT | 2,487,974 | 0.2312 | 0.3190 | 6/6 | 0.9107 | +0.1639 | 26.3252 | 0.5741 |
| 1000SHIBUSDT | 2,476,365 | 0.6214 | 0.0459 | 6/6 | 0.9424 | +0.0079 | 0.8554 | 0.2758 |
| INJUSDT | 2,072,492 | 0.1115 | 0.0228 | 6/6 | 0.8571 | +0.0009 | 124.5835 | 0.6360 |
| LINKUSDT | 1,730,243 | 0.6674 | 0.0619 | 6/6 | 0.8889 | +0.0198 | 0.3561 | 0.2206 |
| APTUSDT | 1,688,194 | 0.5794 | 0.1009 | 6/6 | 0.8479 | +0.0264 | 0.3681 | 0.2622 |
| LDOUSDT | 1,404,621 | 0.2203 | 0.2305 | 6/6 | 0.8846 | +0.0242 | 37.7869 | 0.4384 |
| IDUSDT | 1,322,588 | 0.1710 | 0.0818 | 6/6 | 0.9073 | +0.1355 | 115.1341 | 0.3602 |
| LTCUSDT | 1,262,846 | 0.5877 | 0.1185 | 6/6 | 0.8251 | +0.0742 | 0.3074 | 0.2052 |
| OPUSDT | 1,124,589 | 0.7593 | 0.1381 | 6/6 | 0.9220 | +0.0028 | 0.0556 | 0.1006 |
| ARPAUSDT | 1,107,056 | 0.7268 | 0.4569 | 6/6 | 0.9583 | -0.0021 | 0.1675 | 0.0558 |
| ETCUSDT | 1,009,838 | 0.5738 | 0.0782 | 6/6 | 0.8483 | +0.0813 | 0.3637 | 0.1551 |
| 1000LUNCUSDT | 919,921 | 0.6516 | 0.1450 | 6/6 | 0.8701 | +0.0068 | 0.2891 | 0.1057 |
| ATOMUSDT | 837,588 | 0.7794 | 0.0121 | 6/6 | 0.9081 | +0.0165 | 0.0555 | 0.0676 |
| STXUSDT | 756,215 | 0.8538 | 0.1279 | 6/6 | 0.9651 | -0.0217 | 0.0604 | 0.0281 |
| SANDUSDT | 727,999 | 0.6312 | 0.1339 | 6/6 | 0.8689 | +0.0232 | 0.2834 | 0.0916 |
| APEUSDT | 667,991 | 0.4796 | 0.1059 | 6/6 | 0.8771 | +0.0022 | 0.5864 | 0.1058 |
| CFXUSDT | 642,676 | 0.5239 | 0.3458 | 6/6 | 0.9474 | -0.0615 | 0.9657 | 0.0779 |
| EDUUSDT | 438,257 | 0.2188 | 0.0404 | 6/6 | 0.8404 | +0.0024 | 57.2965 | 0.1366 |
| KAVAUSDT | 271,865 | 0.4138 | 0.2313 | 6/6 | 0.8537 | +0.0078 | 0.8275 | 0.0471 |
| COMPUSDT | 252,556 | 0.3770 | 0.1290 | 6/6 | 0.8040 | +0.0065 | 0.7458 | 0.0514 |
| MTLUSDT | 178,253 | 0.2355 | 0.1031 | 6/6 | 0.7239 | +0.0351 | 1.9989 | 0.0490 |

## Estimator agreement

| symbol | α̂_median (MLE) | n̂_CV (count-variance) | |diff| |
|---|---|---|---|
| ETHUSDT | 0.3040 | 0.9587 | 0.6547 |
| BTCUSDT | 0.2536 | 0.9517 | 0.6981 |
| SOLUSDT | 0.8235 | 0.9168 | 0.0933 |
| 1000PEPEUSDT | 0.3665 | 0.9373 | 0.5708 |
| BNBUSDT | 0.1696 | 0.8965 | 0.7269 |
| XRPUSDT | 0.7929 | 0.8996 | 0.1067 |
| DOGEUSDT | 0.7462 | 0.8918 | 0.1455 |
| BCHUSDT | 0.2771 | 0.9260 | 0.6488 |
| AVAXUSDT | 0.6708 | 0.8826 | 0.2118 |
| SUIUSDT | 0.6739 | 0.8793 | 0.2054 |
| ADAUSDT | 0.7729 | 0.8737 | 0.1007 |
| ARBUSDT | 0.2312 | 0.9107 | 0.6795 |
| 1000SHIBUSDT | 0.6214 | 0.9424 | 0.3210 |
| INJUSDT | 0.1115 | 0.8571 | 0.7456 |
| LINKUSDT | 0.6674 | 0.8889 | 0.2215 |
| APTUSDT | 0.5794 | 0.8479 | 0.2685 |
| LDOUSDT | 0.2203 | 0.8846 | 0.6644 |
| IDUSDT | 0.1710 | 0.9073 | 0.7363 |
| LTCUSDT | 0.5877 | 0.8251 | 0.2374 |
| OPUSDT | 0.7593 | 0.9220 | 0.1627 |
| ARPAUSDT | 0.7268 | 0.9583 | 0.2315 |
| ETCUSDT | 0.5738 | 0.8483 | 0.2744 |
| 1000LUNCUSDT | 0.6516 | 0.8701 | 0.2184 |
| ATOMUSDT | 0.7794 | 0.9081 | 0.1287 |
| STXUSDT | 0.8538 | 0.9651 | 0.1113 |
| SANDUSDT | 0.6312 | 0.8689 | 0.2377 |
| APEUSDT | 0.4796 | 0.8771 | 0.3975 |
| CFXUSDT | 0.5239 | 0.9474 | 0.4235 |
| EDUUSDT | 0.2188 | 0.8404 | 0.6217 |
| KAVAUSDT | 0.4138 | 0.8537 | 0.4399 |
| COMPUSDT | 0.3770 | 0.8040 | 0.4269 |
| MTLUSDT | 0.2355 | 0.7239 | 0.4885 |

Median |α̂_median − n̂_CV| across 32 symbols: **0.2977**. Pearson correlation: **0.2166**.

## Activity regression

**α̂_median on log10(n_events)**: slope = **-0.0012** (stderr 0.0913), intercept = 0.5159, R² = 0.0000, n = 32

## Findings

Across the 32 successful symbols, the median endogeneity level (median of per-symbol alpha_median) is **0.5766**, ranging from 0.1115 to 0.8538. Distance from criticality (alpha=1): **0.4234**.

**Comparison to the literature**: Mark, Sila & Weber (2022, *European Journal of Finance*) find BTC's endogeneity level, fit with power-law kernels, comparable to fiat FX markets, so crypto is not structurally different from mature, near-critical asset classes in that study. This panel's exponential-kernel median of 0.5766 is well below a near-critical regime at face value. Given the exponential-kernel caveat below, it is a lower bound on the true (power-law) endogeneity level and not directly comparable to that literature's power-law fits.

Endogeneity decreases with log-activity across the panel (slope -0.0012, R² 0.0000, n=32).

**The two branching-ratio estimators disagree substantially.** The median absolute difference is 0.2977 (Pearson correlation 0.2166, weak positive, not a strong cross-check), and the gap is one-directional: count-variance reads higher than the MLE for 32/32 symbols (100%), not just on average (median n̂_CV ≈ 0.8903 vs. median α̂_median ≈ 0.5766). Two explanations, not mutually exclusive. (1) Exponential-kernel misspecification: if the true kernel is a slowly decaying power law, the exponential MLE truncates long-range excitation and understates alpha, while `branching_count_variance` assumes no kernel shape. A gap in this direction fits that, but not uniquely. (2) Window sensitivity: n̂_CV uses one fixed 200s window per symbol, and its large-window asymptotic is approximate at any finite window (see the `branching_count_variance` docstring). The data here cannot separate the two. A power-law-kernel MLE refit and a window sweep on alpha_cv would, and I did not run either.

Median raw-vs-rescaled seasonality-bias delta across the panel: **+0.0119** (largest magnitude: 0.1639), the typical amount by which a clock-time-only fit would have mismeasured endogeneity relative to the business-time estimate on this data.

## Failures

| symbol | reason |
|---|---|
| TOMOUSDT | parquet not found: data/parquet/aggTrades/TOMOUSDT/2026-07.parquet |
| LINAUSDT | parquet not found: data/parquet/aggTrades/LINAUSDT/2026-07.parquet |
| WAVESUSDT | parquet not found: data/parquet/aggTrades/WAVESUSDT/2026-07.parquet |
| MATICUSDT | parquet not found: data/parquet/aggTrades/MATICUSDT/2026-07.parquet |
| RNDRUSDT | parquet not found: data/parquet/aggTrades/RNDRUSDT/2026-07.parquet |
| ALPHAUSDT | parquet not found: data/parquet/aggTrades/ALPHAUSDT/2026-07.parquet |
| BTCBUSD | parquet not found: data/parquet/aggTrades/BTCBUSD/2026-07.parquet |
| KEYUSDT | parquet not found: data/parquet/aggTrades/KEYUSDT/2026-07.parquet |
| ETHBUSD | parquet not found: data/parquet/aggTrades/ETHBUSD/2026-07.parquet |

## Caveats

- **Single month** (2026-07): one market regime. Endogeneity levels are plausibly regime-dependent (activity, volatility) and may not carry over to other months.
- **Exponential kernel only**: per Hardiman & Bouchaud (2014) and the broader power-law-kernel literature, an exponential kernel fit to data with a true slowly decaying power-law kernel understates the branching ratio, because its finite memory truncates the long-range contribution. Read the alpha estimates as lower-bound-flavored, not exact. A power-law-kernel refit would likely push every number in the table up, possibly materially.
- **Convergence flag**: `n_converged` only says the Nelder-Mead search stopped improving locally. Near alpha≈1 the likelihood has a shallow mu-alpha ridge (`fit_hawkes_exp` docstring), so `converged=True` there is a weak signal.
- **Runtime cap** (250,000 events/window): windows above the cap are fit on a truncated prefix, so their alpha reflects only the earliest events of the window.
- **Count-variance window (200s default)**: fixed apart from the 20/median_beta widening. A different window could shift alpha_cv, especially near that threshold.
- **Heteroskedasticity in the activity regression**: alpha_iqr varies across the cross-section, so the OLS homoskedasticity assumption is almost certainly violated. The slope, R² and stderr are descriptive.
- **48-bin intraday profile**: it is estimated from the same month being fit, so real self-excitation clustering at the same time-of-day scale (unlikely at ~30-minute resolution, but not provably absent) could be removed with the seasonal confound.
