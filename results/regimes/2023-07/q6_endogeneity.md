# Q6: branching-ratio panel, Hawkes endogeneity cross-section

## Method

**Symbol selection**: the 41-symbol union of (a) the fixed 16-symbol panel (`results/panel_2023-06.txt`) and (b) the top `--top-n` (default 40) symbols by June-2023 `n_events` within the 207-symbol universe (`results/universe_2023-06.txt`), ranked with the activity column in `results/q4_cross_section.parquet`. The union is deduplicated (`results/q6_symbols_2023-06.txt`). The panel was chosen to be liquid, so the two sets overlap 15/16 and the union has 41 symbols, not the ~50-56 a naive 16+40 sum suggests.

For each symbol I load one month (2023-07) of aggTrades and collapse it to aggressor-level events (`load_events`). A per-symbol exception (missing parquet, too few events for the window/guard requirements) is logged in `failures` and does not abort the run.

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
| BTCUSDT | 16,229,472 | 0.7990 | 0.0658 | 6/6 | 0.9634 | -0.0129 | 0.8459 | 1.3748 |
| ETHUSDT | 11,534,367 | 0.6793 | 0.0851 | 6/6 | 0.9523 | -0.0482 | 1.1835 | 1.3727 |
| XRPUSDT | 11,469,421 | 0.8805 | 0.0650 | 6/6 | 0.9828 | -0.0290 | 0.3011 | 0.3453 |
| BCHUSDT | 10,973,795 | 0.6248 | 0.1160 | 6/6 | 0.9697 | +0.0317 | 2.1466 | 1.0974 |
| SOLUSDT | 10,311,844 | 0.5053 | 0.1699 | 6/6 | 0.9693 | -0.0213 | 6.7389 | 1.5190 |
| COMPUSDT | 8,909,411 | 0.6891 | 0.1779 | 6/6 | 0.9596 | +0.0363 | 0.8193 | 0.9479 |
| 1000PEPEUSDT | 7,038,264 | 0.5494 | 0.1467 | 6/6 | 0.9614 | -0.0056 | 5.2384 | 1.2029 |
| LTCUSDT | 6,117,351 | 0.8149 | 0.0581 | 6/6 | 0.9616 | +0.0320 | 0.3062 | 0.3395 |
| DOGEUSDT | 5,748,952 | 0.8422 | 0.0335 | 6/6 | 0.9689 | -0.0087 | 0.3553 | 0.2349 |
| WAVESUSDT | 5,644,586 | 0.4039 | 0.1140 | 6/6 | 0.9678 | +0.0172 | 14.7105 | 1.1122 |
| TOMOUSDT | 5,481,857 | 0.3158 | 0.0234 | 6/6 | 0.9472 | +0.0129 | 24.6434 | 1.1370 |
| OPUSDT | 5,289,742 | 0.5640 | 0.2658 | 6/6 | 0.9565 | +0.0060 | 3.6719 | 0.6723 |
| LINKUSDT | 4,577,423 | 0.8330 | 0.0443 | 6/6 | 0.9597 | -0.0115 | 0.3285 | 0.2423 |
| BNBUSDT | 4,130,431 | 0.7522 | 0.0253 | 6/6 | 0.9425 | +0.0240 | 0.3958 | 0.4187 |
| MATICUSDT | 4,084,127 | 0.8403 | 0.0168 | 6/6 | 0.9495 | -0.0197 | 0.2207 | 0.2233 |
| INJUSDT | 3,725,554 | 0.5521 | 0.1651 | 6/6 | 0.9292 | +0.0343 | 1.2820 | 0.6053 |
| ETCUSDT | 3,550,241 | 0.6925 | 0.0521 | 6/6 | 0.9561 | +0.0841 | 1.0299 | 0.3242 |
| LDOUSDT | 3,302,484 | 0.4187 | 0.0360 | 6/6 | 0.9393 | -0.0026 | 13.3556 | 0.6032 |
| SUIUSDT | 3,273,722 | 0.7702 | 0.1298 | 6/6 | 0.9440 | +0.0238 | 0.4939 | 0.2450 |
| ARBUSDT | 3,217,588 | 0.7013 | 0.0674 | 6/6 | 0.9360 | -0.0147 | 0.5517 | 0.3054 |
| AVAXUSDT | 3,103,771 | 0.5416 | 0.1921 | 6/6 | 0.9440 | -0.0066 | 1.4758 | 0.3154 |
| ADAUSDT | 2,906,251 | 0.7793 | 0.0616 | 6/6 | 0.9378 | -0.0083 | 0.2374 | 0.1902 |
| 1000SHIBUSDT | 2,899,748 | 0.8637 | 0.0611 | 6/6 | 0.9465 | -0.0148 | 0.1607 | 0.1157 |
| MTLUSDT | 2,878,868 | 0.3796 | 0.0381 | 6/6 | 0.9380 | +0.0112 | 13.1668 | 0.4917 |
| APEUSDT | 2,843,777 | 0.8806 | 0.0408 | 6/6 | 0.9488 | -0.0003 | 0.1645 | 0.1254 |
| APTUSDT | 2,580,709 | 0.7214 | 0.1456 | 6/6 | 0.9366 | +0.0163 | 0.4868 | 0.2158 |
| RNDRUSDT | 2,353,073 | 0.3271 | 0.0139 | 6/6 | 0.9092 | +0.0063 | 23.8940 | 0.6173 |
| EDUUSDT | 2,273,531 | 0.3871 | 0.2178 | 6/6 | 0.9428 | +0.0116 | 9.9799 | 0.4637 |
| BTCBUSD | 2,144,423 | 0.5425 | 0.1694 | 6/6 | 0.9195 | +0.0130 | 2.4835 | 0.3611 |
| ATOMUSDT | 2,074,235 | 0.7232 | 0.1028 | 6/6 | 0.9220 | +0.0026 | 0.4094 | 0.1910 |
| KAVAUSDT | 1,987,466 | 0.3647 | 0.0856 | 6/6 | 0.9220 | +0.0024 | 7.4572 | 0.3798 |
| 1000LUNCUSDT | 1,959,853 | 0.7840 | 0.0638 | 6/6 | 0.9363 | +0.0078 | 0.2471 | 0.1342 |
| CFXUSDT | 1,941,907 | 0.7921 | 0.0892 | 6/6 | 0.9242 | +0.0092 | 0.1576 | 0.1162 |
| STXUSDT | 1,723,987 | 0.6426 | 0.1058 | 6/6 | 0.9210 | +0.0307 | 0.7103 | 0.2148 |
| SANDUSDT | 1,640,825 | 0.7933 | 0.0433 | 6/6 | 0.9266 | +0.0063 | 0.1869 | 0.1146 |
| LINAUSDT | 1,575,973 | 0.8032 | 0.0503 | 6/6 | 0.8920 | +0.0025 | 0.1294 | 0.1219 |
| ETHBUSD | 1,550,851 | 0.4956 | 0.0408 | 6/6 | 0.9079 | -0.0112 | 1.8875 | 0.2891 |
| ALPHAUSDT | 1,502,381 | 0.3922 | 0.0765 | 6/6 | 0.9058 | +0.0079 | 8.5342 | 0.4018 |
| ARPAUSDT | 1,423,308 | 0.7780 | 0.1058 | 6/6 | 0.9059 | +0.0084 | 0.2232 | 0.1306 |
| IDUSDT | 1,254,453 | 0.7532 | 0.1531 | 6/6 | 0.9066 | +0.0513 | 0.1543 | 0.1091 |
| KEYUSDT | 1,142,503 | 0.6722 | 0.1591 | 6/6 | 0.9378 | +0.0048 | 0.3449 | 0.0999 |

## Estimator agreement

| symbol | α̂_median (MLE) | n̂_CV (count-variance) | |diff| |
|---|---|---|---|
| BTCUSDT | 0.7990 | 0.9634 | 0.1644 |
| ETHUSDT | 0.6793 | 0.9523 | 0.2729 |
| XRPUSDT | 0.8805 | 0.9828 | 0.1023 |
| BCHUSDT | 0.6248 | 0.9697 | 0.3448 |
| SOLUSDT | 0.5053 | 0.9693 | 0.4641 |
| COMPUSDT | 0.6891 | 0.9596 | 0.2705 |
| 1000PEPEUSDT | 0.5494 | 0.9614 | 0.4120 |
| LTCUSDT | 0.8149 | 0.9616 | 0.1467 |
| DOGEUSDT | 0.8422 | 0.9689 | 0.1267 |
| WAVESUSDT | 0.4039 | 0.9678 | 0.5639 |
| TOMOUSDT | 0.3158 | 0.9472 | 0.6314 |
| OPUSDT | 0.5640 | 0.9565 | 0.3925 |
| LINKUSDT | 0.8330 | 0.9597 | 0.1266 |
| BNBUSDT | 0.7522 | 0.9425 | 0.1903 |
| MATICUSDT | 0.8403 | 0.9495 | 0.1093 |
| INJUSDT | 0.5521 | 0.9292 | 0.3771 |
| ETCUSDT | 0.6925 | 0.9561 | 0.2636 |
| LDOUSDT | 0.4187 | 0.9393 | 0.5205 |
| SUIUSDT | 0.7702 | 0.9440 | 0.1738 |
| ARBUSDT | 0.7013 | 0.9360 | 0.2347 |
| AVAXUSDT | 0.5416 | 0.9440 | 0.4024 |
| ADAUSDT | 0.7793 | 0.9378 | 0.1585 |
| 1000SHIBUSDT | 0.8637 | 0.9465 | 0.0828 |
| MTLUSDT | 0.3796 | 0.9380 | 0.5583 |
| APEUSDT | 0.8806 | 0.9488 | 0.0682 |
| APTUSDT | 0.7214 | 0.9366 | 0.2151 |
| RNDRUSDT | 0.3271 | 0.9092 | 0.5821 |
| EDUUSDT | 0.3871 | 0.9428 | 0.5557 |
| BTCBUSD | 0.5425 | 0.9195 | 0.3771 |
| ATOMUSDT | 0.7232 | 0.9220 | 0.1988 |
| KAVAUSDT | 0.3647 | 0.9220 | 0.5573 |
| 1000LUNCUSDT | 0.7840 | 0.9363 | 0.1523 |
| CFXUSDT | 0.7921 | 0.9242 | 0.1321 |
| STXUSDT | 0.6426 | 0.9210 | 0.2784 |
| SANDUSDT | 0.7933 | 0.9266 | 0.1332 |
| LINAUSDT | 0.8032 | 0.8920 | 0.0889 |
| ETHBUSD | 0.4956 | 0.9079 | 0.4124 |
| ALPHAUSDT | 0.3922 | 0.9058 | 0.5135 |
| ARPAUSDT | 0.7780 | 0.9059 | 0.1279 |
| IDUSDT | 0.7532 | 0.9066 | 0.1535 |
| KEYUSDT | 0.6722 | 0.9378 | 0.2656 |

Median |α̂_median − n̂_CV| across 41 symbols: **0.2636**. Pearson correlation: **0.1762**.

## Activity regression

**α̂_median on log10(n_events)**: slope = **0.0438** (stderr 0.0931), intercept = 0.3640, R² = 0.0056, n = 41

## Findings

Across the 41 successful symbols, the median endogeneity level (median of per-symbol alpha_median) is **0.6925**, ranging from 0.3158 to 0.8806. Distance from criticality (alpha=1): **0.3075**.

**Comparison to the literature**: Mark, Sila & Weber (2022, *European Journal of Finance*) find BTC's endogeneity level, fit with power-law kernels, comparable to fiat FX markets, so crypto is not structurally different from mature, near-critical asset classes in that study. This panel's exponential-kernel median of 0.6925 is broadly consistent with a near-critical regime at face value. Given the exponential-kernel caveat below, it is a lower bound on the true (power-law) endogeneity level and not directly comparable to that literature's power-law fits.

Endogeneity increases with log-activity across the panel (slope 0.0438, R² 0.0056, n=41).

**The two branching-ratio estimators disagree substantially.** The median absolute difference is 0.2636 (Pearson correlation 0.1762, weak positive, not a strong cross-check), and the gap is one-directional: count-variance reads higher than the MLE for 41/41 symbols (100%), not just on average (median n̂_CV ≈ 0.9425 vs. median α̂_median ≈ 0.6925). Two explanations, not mutually exclusive. (1) Exponential-kernel misspecification: if the true kernel is a slowly decaying power law, the exponential MLE truncates long-range excitation and understates alpha, while `branching_count_variance` assumes no kernel shape. A gap in this direction fits that, but not uniquely. (2) Window sensitivity: n̂_CV uses one fixed 200s window per symbol, and its large-window asymptotic is approximate at any finite window (see the `branching_count_variance` docstring). The data here cannot separate the two. A power-law-kernel MLE refit and a window sweep on alpha_cv would, and I did not run either.

Median raw-vs-rescaled seasonality-bias delta across the panel: **+0.0063** (largest magnitude: 0.0841), the typical amount by which a clock-time-only fit would have mismeasured endogeneity relative to the business-time estimate on this data.

## Caveats

- **Single month** (2023-07): one market regime. Endogeneity levels are plausibly regime-dependent (activity, volatility) and may not carry over to other months.
- **Exponential kernel only**: per Hardiman & Bouchaud (2014) and the broader power-law-kernel literature, an exponential kernel fit to data with a true slowly decaying power-law kernel understates the branching ratio, because its finite memory truncates the long-range contribution. Read the alpha estimates as lower-bound-flavored, not exact. A power-law-kernel refit would likely push every number in the table up, possibly materially.
- **Convergence flag**: `n_converged` only says the Nelder-Mead search stopped improving locally. Near alpha≈1 the likelihood has a shallow mu-alpha ridge (`fit_hawkes_exp` docstring), so `converged=True` there is a weak signal.
- **Runtime cap** (250,000 events/window): windows above the cap are fit on a truncated prefix, so their alpha reflects only the earliest events of the window.
- **Count-variance window (200s default)**: fixed apart from the 20/median_beta widening. A different window could shift alpha_cv, especially near that threshold.
- **Heteroskedasticity in the activity regression**: alpha_iqr varies across the cross-section, so the OLS homoskedasticity assumption is almost certainly violated. The slope, R² and stderr are descriptive.
- **48-bin intraday profile**: it is estimated from the same month being fit, so real self-excitation clustering at the same time-of-day scale (unlikely at ~30-minute resolution, but not provably absent) could be removed with the seasonal confound.
