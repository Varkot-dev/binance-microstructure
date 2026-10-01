# Q6: branching-ratio panel — Hawkes endogeneity cross-section

## Methodology

**Symbol selection**: the requested panel is the 41-symbol union of (a) the fixed 16-symbol panel (`results/panel_2023-06.txt`) and (b) the top `--top-n` (default 40) most-active symbols by June-2023 `n_events`, restricted to the 207-symbol universe (`results/universe_2023-06.txt`) and ranked using the already-computed activity column in `results/q4_cross_section.parquet` (Q4's cross-section, not a fresh count — the universe file itself is not activity-ranked). The union is deduplicated (`results/q6_symbols_2023-06.txt`, one entry per symbol, order preserving first occurrence). In this run the two source sets overlap 15/16 — nearly every panel symbol is ALSO one of the 40 most-active universe symbols — so the deduplicated union lands at 41 symbols, not the ~50-56 a naive 16+40 sum would suggest. This is reported honestly here rather than padded to hit a round number: the panel and "most active" sets are highly correlated by construction (the panel was itself chosen to include liquid, well-known symbols), so their union is smaller than the sum of their sizes.

For each symbol, one month (2024-07) of aggTrades is loaded and collapsed to aggressor-level events (`load_events`). Symbols are processed one at a time; any per-symbol exception (missing parquet, too few events for the window/guard requirements) is caught and logged into `failures` without aborting the run.

**Business time first, and why.** Event timestamps are converted to a normalized intraday rate profile (`intraday_rate_profile`, 48 bins) and rescaled to business time (`rescale_to_business_time`) BEFORE any Hawkes fitting is attempted. This step is not optional — fitting a Hawkes MLE (or the model-free count-variance estimator) directly on clock time cannot distinguish genuine self-excitation from a merely time-varying, non-self-exciting baseline rate. This repo's own synthetic trap test (`test_regime_switching_poisson_produces_spurious_endogeneity_trap`) shows a regime-switching Poisson process — NO self-excitation anywhere, just a rate that alternates on a fixed clock — produces a spurious count-variance n̂ > 0.2 and a spurious fitted MLE alpha > 0.5 (Filimonov & Sornette 2015). Every crypto symbol's aggressor flow has at least that strong an intraday U-shape / funding-hour clustering pattern, so any clock-time endogeneity estimate on this data would be unable to separate real branching from that artifact. The `raw_delta` column below quantifies the actual size of this bias, per symbol, rather than merely asserting the fix is needed.

**Sub-windows**: the full-month business-time series is split into 6 equal contiguous sub-windows. Each is fit independently via `fit_hawkes_exp` on (business_time − window_start). **Runtime cap**: a sub-window with more than 250,000 events is fit on only the FIRST 250,000 of that window's events — this bounds the O(N log N) per-fit MLE cost. Per this repo's own multi-seed synthetic tests, fitted-alpha sampling sd at comparable sample sizes is ~0.004-0.02, so subsampling this large does not materially widen the uncertainty already present from having only 6 windows per symbol. That sd figure was measured on well-specified-kernel synthetic data; it bounds sampling noise from the truncation itself, not the separate, larger effect of exponential-kernel misspecification against a true power-law kernel (see the kernel caveat below), which this sd transfer does not speak to.

**alpha_median / alpha_iqr**: the median and interquartile range of the 6 per-window fitted alphas — the panel's primary point estimate and its within-symbol dispersion. **n_converged**: how many of the 6 window fits reported `converged=True` (see `fit_hawkes_exp`'s docstring on what that flag does and does NOT mean — it reflects the optimizer settling, not that the parameters are well identified, especially near alpha≈1).

**raw_delta (seasonality-bias measurement)**: ONE additional fit is run on the first sub-window's events using RAW clock time (no business-time rescaling), same event subset and same runtime cap. `raw_delta = alpha_raw − alpha_rescaled_window1` is the per-symbol, empirically measured size of the seasonality bias this whole analysis is designed to avoid — a positive raw_delta means the naive clock-time fit would have overstated endogeneity relative to the business-time-corrected estimate.

**alpha_cv (count-variance n̂)**: `branching_count_variance` on the FULL business-time series (not per-window), with window_bt = 200 business-time seconds by default. This must be ≫ the kernel decay timescale 1/beta (typically ~0.1-2s for liquid crypto aggressor flow) for the estimator's large-window asymptotic to hold — short windows truncate the kernel's memory and bias n̂ toward 0. A sanity assertion widens the window to 100/median_beta whenever 200s does not clear the 20/median_beta threshold for that symbol's own fitted decay rate, so the window scales up automatically for unusually slow-decaying symbols instead of silently understating their n̂.

**Cross-section**: OLS (`np.polyfit`, with intercept) of alpha_median on log10(n_events) across the successful symbols. **MLE-vs-CV agreement**: median absolute difference and Pearson correlation between alpha_median (MLE) and alpha_cv (count-variance) — an honesty check on whether the two independent estimators agree.

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

## Estimator-agreement honesty table

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

**Comparison to the literature**: Mark, Sila & Weber (2022, *European Journal of Finance*, docs/research/02 citation) find BTC's endogeneity level, fit with power-law kernels, comparable to fiat FX markets — i.e. crypto is not structurally different from mature, near-critical asset classes in that study. This panel's exponential-kernel median of 0.3874 is well below a near-critical regime at face value, but the exponential-kernel caveat below means this number is a LOWER bound on the true (power-law) endogeneity level, not a directly comparable point estimate to that literature's power-law fits.

Endogeneity **decreases** with log-activity across the panel (slope -0.0666, R² 0.0203, n=37).

**MLE-vs-CV disagreement is large and should not be papered over.** The two independent branching-ratio estimators disagree by a median of 0.4656 across the panel (Pearson correlation -0.1540 — weak negative, not a strong cross-check), and the disagreement is systematically ONE-DIRECTIONAL: count-variance reads higher than the MLE for 37/37 symbols (100%), not just on average (median n̂_CV ≈ 0.9299 vs. median α̂_median ≈ 0.3874). Two plausible, non-exclusive explanations for a gap in this direction: (1) **exponential-kernel MLE misspecification** — if the true kernel is a slowly-decaying power law, the exponential-kernel MLE truncates long-range excitation and understates alpha (see the exp-kernel caveat below), while `branching_count_variance` assumes no kernel shape at all and is free of that particular bias, so a gap in exactly this direction is consistent with real kernel misspecification, not just noise; (2) **count-variance window sensitivity** — n̂_CV uses one fixed 200s (business-time) window per symbol, and `branching_count_variance`'s own docstring warns that its large-window asymptotic is an approximation, not exact, at any finite window, so part of the gap could be window-choice artifact rather than a genuine kernel-shape signal. This analysis cannot cleanly separate the two explanations with the data collected here — a power-law-kernel MLE refit (out of scope for this task) and/or a window-sensitivity sweep on alpha_cv would be needed to attribute the gap with any confidence. Reporting both estimators side by side, disagreeing this much, is the honest result; averaging or picking whichever one looks more publishable would not be.

Median raw-vs-rescaled seasonality-bias delta across the panel: **+0.0093** (largest magnitude: 0.3541) — the typical amount by which a naive clock-time-only fit would have mismeasured endogeneity relative to the business-time-corrected estimate on this data.

## Failures

| symbol | reason |
|---|---|
| TOMOUSDT | parquet not found: data/parquet/aggTrades/TOMOUSDT/2024-07.parquet |
| WAVESUSDT | parquet not found: data/parquet/aggTrades/WAVESUSDT/2024-07.parquet |
| BTCBUSD | parquet not found: data/parquet/aggTrades/BTCBUSD/2024-07.parquet |
| ETHBUSD | parquet not found: data/parquet/aggTrades/ETHBUSD/2024-07.parquet |

## Caveats

- **Single month** (2024-07): one specific market regime; endogeneity levels are plausibly regime-dependent (activity, volatility) and may not generalize to other months.
- **Exponential kernel only**: per Hardiman & Bouchaud (2014) and the broader power-law-kernel literature this module's own research notes cite, fitting an exponential kernel to data whose TRUE kernel is a slowly-decaying power law systematically UNDERSTATES the branching ratio — the exponential kernel's finite memory truncates the long-range contribution a power-law kernel would capture. This panel's alpha estimates should therefore be read as a LOWER-bound-flavored estimate of true endogeneity, not an exact point estimate; a power-law-kernel refit would likely push every number in this table upward, potentially materially so.
- **convergence-flag semantics**: `n_converged` reflects only that a window's Nelder-Mead search stopped improving locally — it does NOT certify that mu/alpha are well identified. Near alpha≈1 the likelihood surface has a shallow mu-alpha ridge (`fit_hawkes_exp`'s docstring), so a `converged=True` window near the boundary of alpha is a weaker signal than the same flag away from it.
- **Runtime cap** (250,000 events/window): windows above this cap are fit on a truncated prefix, not the full window. This bounds cost but means those windows' alpha reflects only the earliest events in an otherwise larger window.
- **count-variance window (200s business-time default)**: a fixed, documented choice, not tuned per symbol beyond the 20/median_beta sanity widening described above; a different window choice could shift alpha_cv, particularly for symbols near the sanity threshold.
- **Heteroskedasticity in the activity regression**: as in Q4/Q5, per-symbol alpha_median dispersion (alpha_iqr) is not uniform across the cross-section, so the OLS regression's homoskedastic-residual assumption is almost certainly violated; the reported slope/R²/stderr are descriptive, not a formal confidence interval.
- **48-bin intraday profile**: `intraday_rate_profile` estimates the seasonal shape from the SAME month's data being fit, not an independent sample — any genuine self-excitation clustering at the same time-of-day scale (unlikely at 48-bin, ~30-minute resolution, but not provably absent) could partially leak into the profile and be removed along with the seasonal confound.
