# Q6: branching-ratio panel — Hawkes endogeneity cross-section

## Methodology

**Symbol selection**: the requested panel is the 41-symbol union of (a) the fixed 16-symbol panel (`results/panel_2023-06.txt`) and (b) the top `--top-n` (default 40) most-active symbols by June-2023 `n_events`, restricted to the 207-symbol universe (`results/universe_2023-06.txt`) and ranked using the already-computed activity column in `results/q4_cross_section.parquet` (Q4's cross-section, not a fresh count — the universe file itself is not activity-ranked). The union is deduplicated (`results/q6_symbols_2023-06.txt`, one entry per symbol, order preserving first occurrence). In this run the two source sets overlap 15/16 — nearly every panel symbol is ALSO one of the 40 most-active universe symbols — so the deduplicated union lands at 41 symbols, not the ~50-56 a naive 16+40 sum would suggest. This is reported honestly here rather than padded to hit a round number: the panel and "most active" sets are highly correlated by construction (the panel was itself chosen to include liquid, well-known symbols), so their union is smaller than the sum of their sizes.

For each symbol, one month (2025-07) of aggTrades is loaded and collapsed to aggressor-level events (`load_events`). Symbols are processed one at a time; any per-symbol exception (missing parquet, too few events for the window/guard requirements) is caught and logged into `failures` without aborting the run.

**Business time first, and why.** Event timestamps are converted to a normalized intraday rate profile (`intraday_rate_profile`, 48 bins) and rescaled to business time (`rescale_to_business_time`) BEFORE any Hawkes fitting is attempted. This step is not optional — fitting a Hawkes MLE (or the model-free count-variance estimator) directly on clock time cannot distinguish genuine self-excitation from a merely time-varying, non-self-exciting baseline rate. This repo's own synthetic trap test (`test_regime_switching_poisson_produces_spurious_endogeneity_trap`) shows a regime-switching Poisson process — NO self-excitation anywhere, just a rate that alternates on a fixed clock — produces a spurious count-variance n̂ > 0.2 and a spurious fitted MLE alpha > 0.5 (Filimonov & Sornette 2015). Every crypto symbol's aggressor flow has at least that strong an intraday U-shape / funding-hour clustering pattern, so any clock-time endogeneity estimate on this data would be unable to separate real branching from that artifact. The `raw_delta` column below quantifies the actual size of this bias, per symbol, rather than merely asserting the fix is needed.

**Sub-windows**: the full-month business-time series is split into 6 equal contiguous sub-windows. Each is fit independently via `fit_hawkes_exp` on (business_time − window_start). **Runtime cap**: a sub-window with more than 250,000 events is fit on only the FIRST 250,000 of that window's events — this bounds the O(N log N) per-fit MLE cost. Per this repo's own multi-seed synthetic tests, fitted-alpha sampling sd at comparable sample sizes is ~0.004-0.02, so subsampling this large does not materially widen the uncertainty already present from having only 6 windows per symbol. That sd figure was measured on well-specified-kernel synthetic data; it bounds sampling noise from the truncation itself, not the separate, larger effect of exponential-kernel misspecification against a true power-law kernel (see the kernel caveat below), which this sd transfer does not speak to.

**alpha_median / alpha_iqr**: the median and interquartile range of the 6 per-window fitted alphas — the panel's primary point estimate and its within-symbol dispersion. **n_converged**: how many of the 6 window fits reported `converged=True` (see `fit_hawkes_exp`'s docstring on what that flag does and does NOT mean — it reflects the optimizer settling, not that the parameters are well identified, especially near alpha≈1).

**raw_delta (seasonality-bias measurement)**: ONE additional fit is run on the first sub-window's events using RAW clock time (no business-time rescaling), same event subset and same runtime cap. `raw_delta = alpha_raw − alpha_rescaled_window1` is the per-symbol, empirically measured size of the seasonality bias this whole analysis is designed to avoid — a positive raw_delta means the naive clock-time fit would have overstated endogeneity relative to the business-time-corrected estimate.

**alpha_cv (count-variance n̂)**: `branching_count_variance` on the FULL business-time series (not per-window), with window_bt = 200 business-time seconds by default. This must be ≫ the kernel decay timescale 1/beta (typically ~0.1-2s for liquid crypto aggressor flow) for the estimator's large-window asymptotic to hold — short windows truncate the kernel's memory and bias n̂ toward 0. A sanity assertion widens the window to 100/median_beta whenever 200s does not clear the 20/median_beta threshold for that symbol's own fitted decay rate, so the window scales up automatically for unusually slow-decaying symbols instead of silently understating their n̂.

**Cross-section**: OLS (`np.polyfit`, with intercept) of alpha_median on log10(n_events) across the successful symbols. **MLE-vs-CV agreement**: median absolute difference and Pearson correlation between alpha_median (MLE) and alpha_cv (count-variance) — an honesty check on whether the two independent estimators agree.

## Run summary

Requested: 41. Successful: 33. Failed: 8.

## Panel table (sorted by n_events)

| symbol | n_events | α̂_median | α̂ IQR | n_converged/6 | n̂_CV | raw_delta | median β̂ | median μ̂ |
|---|---|---|---|---|---|---|---|---|
| ETHUSDT | 27,033,493 | 0.4447 | 0.1318 | 6/6 | 0.9676 | +0.0147 | 40.8971 | 6.6439 |
| 1000PEPEUSDT | 17,375,967 | 0.3556 | 0.0714 | 6/6 | 0.9532 | +0.0055 | 104.5913 | 3.9252 |
| XRPUSDT | 17,100,486 | 0.6647 | 0.1133 | 6/6 | 0.9643 | +0.0120 | 1.4623 | 1.7799 |
| BTCUSDT | 15,781,891 | 0.6349 | 0.0728 | 6/6 | 0.9577 | +0.0910 | 2.3213 | 2.2200 |
| DOGEUSDT | 14,092,473 | 0.5426 | 0.2474 | 6/6 | 0.9624 | +0.0405 | 5.8773 | 1.9886 |
| SOLUSDT | 13,330,644 | 0.7959 | 0.1174 | 6/6 | 0.9453 | +0.0339 | 0.3982 | 0.9540 |
| SUIUSDT | 11,473,438 | 0.2444 | 0.0713 | 6/6 | 0.9452 | +0.0037 | 94.9805 | 3.4405 |
| CFXUSDT | 8,653,445 | 0.4415 | 0.0746 | 6/6 | 0.9796 | +0.0152 | 15.0117 | 0.6851 |
| ADAUSDT | 6,948,051 | 0.7433 | 0.0962 | 6/6 | 0.9329 | +0.0504 | 0.4314 | 0.6675 |
| BNBUSDT | 6,442,325 | 0.2924 | 0.2140 | 6/6 | 0.9341 | +0.0251 | 47.2851 | 1.4789 |
| AVAXUSDT | 5,796,364 | 0.3638 | 0.0364 | 6/6 | 0.9281 | +0.0647 | 14.2313 | 1.4724 |
| APTUSDT | 5,714,882 | 0.2837 | 0.0806 | 6/6 | 0.9215 | +0.0017 | 72.1465 | 1.3903 |
| LINKUSDT | 5,519,189 | 0.4668 | 0.1057 | 6/6 | 0.9249 | +0.0591 | 4.2252 | 1.1230 |
| BCHUSDT | 5,073,613 | 0.2902 | 0.0596 | 6/6 | 0.9310 | +0.0020 | 64.1977 | 1.4504 |
| INJUSDT | 4,420,282 | 0.3664 | 0.0380 | 6/6 | 0.9051 | +0.0214 | 13.6249 | 1.0584 |
| 1000SHIBUSDT | 4,340,698 | 0.5277 | 0.1497 | 6/6 | 0.9220 | +0.0752 | 1.6921 | 0.6957 |
| OPUSDT | 4,307,562 | 0.5615 | 0.0752 | 6/6 | 0.9391 | +0.0426 | 0.8972 | 0.5175 |
| ETCUSDT | 4,271,209 | 0.3978 | 0.0440 | 6/6 | 0.9449 | +0.0412 | 8.6119 | 0.7996 |
| LTCUSDT | 4,168,321 | 0.5903 | 0.1084 | 6/6 | 0.9329 | +0.0293 | 0.7502 | 0.5517 |
| LDOUSDT | 3,932,443 | 0.4321 | 0.0479 | 6/6 | 0.9378 | +0.0396 | 5.3004 | 0.7152 |
| ARBUSDT | 3,626,948 | 0.6523 | 0.0875 | 6/6 | 0.8911 | +0.0174 | 0.3620 | 0.4789 |
| SANDUSDT | 3,069,181 | 0.3921 | 0.0456 | 6/6 | 0.9297 | +0.0196 | 18.8457 | 0.6880 |
| APEUSDT | 1,856,130 | 0.5794 | 0.0488 | 6/6 | 0.9041 | +0.0190 | 1.0499 | 0.2771 |
| COMPUSDT | 1,833,683 | 0.8053 | 0.1843 | 6/6 | 0.9197 | +0.0342 | 0.2098 | 0.1540 |
| STXUSDT | 1,815,760 | 0.4210 | 0.0433 | 6/6 | 0.8740 | +0.0145 | 4.0194 | 0.4027 |
| ATOMUSDT | 1,426,964 | 0.4847 | 0.0481 | 6/6 | 0.8546 | +0.0280 | 0.7666 | 0.2829 |
| IDUSDT | 1,315,618 | 0.3481 | 0.0526 | 6/6 | 0.8586 | +0.0039 | 12.7638 | 0.3211 |
| ALPHAUSDT | 1,230,554 | 0.5741 | 0.2307 | 6/6 | 0.9372 | +0.0020 | 1.3456 | 0.1571 |
| ARPAUSDT | 998,723 | 0.8455 | 0.1169 | 6/6 | 0.9732 | -0.0009 | 0.0755 | 0.0547 |
| 1000LUNCUSDT | 950,125 | 0.8346 | 0.1229 | 6/6 | 0.9422 | +0.0205 | 0.0767 | 0.0614 |
| KAVAUSDT | 914,392 | 0.6582 | 0.2613 | 6/6 | 0.8990 | +0.0226 | 0.3239 | 0.1137 |
| MTLUSDT | 784,129 | 0.3437 | 0.1063 | 6/6 | 0.8642 | +0.0061 | 3.1710 | 0.1986 |
| EDUUSDT | 528,579 | 0.7781 | 0.0738 | 6/6 | 0.9351 | +0.0068 | 0.0396 | 0.0380 |

## Estimator-agreement honesty table

| symbol | α̂_median (MLE) | n̂_CV (count-variance) | |diff| |
|---|---|---|---|
| ETHUSDT | 0.4447 | 0.9676 | 0.5229 |
| 1000PEPEUSDT | 0.3556 | 0.9532 | 0.5976 |
| XRPUSDT | 0.6647 | 0.9643 | 0.2996 |
| BTCUSDT | 0.6349 | 0.9577 | 0.3228 |
| DOGEUSDT | 0.5426 | 0.9624 | 0.4198 |
| SOLUSDT | 0.7959 | 0.9453 | 0.1494 |
| SUIUSDT | 0.2444 | 0.9452 | 0.7008 |
| CFXUSDT | 0.4415 | 0.9796 | 0.5381 |
| ADAUSDT | 0.7433 | 0.9329 | 0.1896 |
| BNBUSDT | 0.2924 | 0.9341 | 0.6417 |
| AVAXUSDT | 0.3638 | 0.9281 | 0.5643 |
| APTUSDT | 0.2837 | 0.9215 | 0.6378 |
| LINKUSDT | 0.4668 | 0.9249 | 0.4581 |
| BCHUSDT | 0.2902 | 0.9310 | 0.6408 |
| INJUSDT | 0.3664 | 0.9051 | 0.5387 |
| 1000SHIBUSDT | 0.5277 | 0.9220 | 0.3943 |
| OPUSDT | 0.5615 | 0.9391 | 0.3776 |
| ETCUSDT | 0.3978 | 0.9449 | 0.5471 |
| LTCUSDT | 0.5903 | 0.9329 | 0.3426 |
| LDOUSDT | 0.4321 | 0.9378 | 0.5057 |
| ARBUSDT | 0.6523 | 0.8911 | 0.2388 |
| SANDUSDT | 0.3921 | 0.9297 | 0.5376 |
| APEUSDT | 0.5794 | 0.9041 | 0.3247 |
| COMPUSDT | 0.8053 | 0.9197 | 0.1144 |
| STXUSDT | 0.4210 | 0.8740 | 0.4531 |
| ATOMUSDT | 0.4847 | 0.8546 | 0.3699 |
| IDUSDT | 0.3481 | 0.8586 | 0.5105 |
| ALPHAUSDT | 0.5741 | 0.9372 | 0.3631 |
| ARPAUSDT | 0.8455 | 0.9732 | 0.1276 |
| 1000LUNCUSDT | 0.8346 | 0.9422 | 0.1075 |
| KAVAUSDT | 0.6582 | 0.8990 | 0.2408 |
| MTLUSDT | 0.3437 | 0.8642 | 0.5205 |
| EDUUSDT | 0.7781 | 0.9351 | 0.1570 |

Median |α̂_median − n̂_CV| across 33 symbols: **0.4198**. Pearson correlation: **0.2221**.

## Activity regression

**α̂_median on log10(n_events)**: slope = **-0.1063** (stderr 0.0683), intercept = 1.2206, R² = 0.0725, n = 33

## Findings

Across the 33 successful symbols, the median endogeneity level (median of per-symbol alpha_median) is **0.4847**, ranging from 0.2444 to 0.8455. Distance from criticality (alpha=1): **0.5153**.

**Comparison to the literature**: Mark, Sila & Weber (2022, *European Journal of Finance*, docs/research/02 citation) find BTC's endogeneity level, fit with power-law kernels, comparable to fiat FX markets — i.e. crypto is not structurally different from mature, near-critical asset classes in that study. This panel's exponential-kernel median of 0.4847 is well below a near-critical regime at face value, but the exponential-kernel caveat below means this number is a LOWER bound on the true (power-law) endogeneity level, not a directly comparable point estimate to that literature's power-law fits.

Endogeneity **decreases** with log-activity across the panel (slope -0.1063, R² 0.0725, n=33).

**MLE-vs-CV disagreement is large and should not be papered over.** The two independent branching-ratio estimators disagree by a median of 0.4198 across the panel (Pearson correlation 0.2221 — weak positive, not a strong cross-check), and the disagreement is systematically ONE-DIRECTIONAL: count-variance reads higher than the MLE for 33/33 symbols (100%), not just on average (median n̂_CV ≈ 0.9329 vs. median α̂_median ≈ 0.4847). Two plausible, non-exclusive explanations for a gap in this direction: (1) **exponential-kernel MLE misspecification** — if the true kernel is a slowly-decaying power law, the exponential-kernel MLE truncates long-range excitation and understates alpha (see the exp-kernel caveat below), while `branching_count_variance` assumes no kernel shape at all and is free of that particular bias, so a gap in exactly this direction is consistent with real kernel misspecification, not just noise; (2) **count-variance window sensitivity** — n̂_CV uses one fixed 200s (business-time) window per symbol, and `branching_count_variance`'s own docstring warns that its large-window asymptotic is an approximation, not exact, at any finite window, so part of the gap could be window-choice artifact rather than a genuine kernel-shape signal. This analysis cannot cleanly separate the two explanations with the data collected here — a power-law-kernel MLE refit (out of scope for this task) and/or a window-sensitivity sweep on alpha_cv would be needed to attribute the gap with any confidence. Reporting both estimators side by side, disagreeing this much, is the honest result; averaging or picking whichever one looks more publishable would not be.

Median raw-vs-rescaled seasonality-bias delta across the panel: **+0.0205** (largest magnitude: 0.0910) — the typical amount by which a naive clock-time-only fit would have mismeasured endogeneity relative to the business-time-corrected estimate on this data.

## Failures

| symbol | reason |
|---|---|
| TOMOUSDT | parquet not found: data/parquet/aggTrades/TOMOUSDT/2025-07.parquet |
| LINAUSDT | parquet not found: data/parquet/aggTrades/LINAUSDT/2025-07.parquet |
| WAVESUSDT | parquet not found: data/parquet/aggTrades/WAVESUSDT/2025-07.parquet |
| MATICUSDT | parquet not found: data/parquet/aggTrades/MATICUSDT/2025-07.parquet |
| RNDRUSDT | parquet not found: data/parquet/aggTrades/RNDRUSDT/2025-07.parquet |
| BTCBUSD | parquet not found: data/parquet/aggTrades/BTCBUSD/2025-07.parquet |
| KEYUSDT | parquet not found: data/parquet/aggTrades/KEYUSDT/2025-07.parquet |
| ETHBUSD | parquet not found: data/parquet/aggTrades/ETHBUSD/2025-07.parquet |

## Caveats

- **Single month** (2025-07): one specific market regime; endogeneity levels are plausibly regime-dependent (activity, volatility) and may not generalize to other months.
- **Exponential kernel only**: per Hardiman & Bouchaud (2014) and the broader power-law-kernel literature this module's own research notes cite, fitting an exponential kernel to data whose TRUE kernel is a slowly-decaying power law systematically UNDERSTATES the branching ratio — the exponential kernel's finite memory truncates the long-range contribution a power-law kernel would capture. This panel's alpha estimates should therefore be read as a LOWER-bound-flavored estimate of true endogeneity, not an exact point estimate; a power-law-kernel refit would likely push every number in this table upward, potentially materially so.
- **convergence-flag semantics**: `n_converged` reflects only that a window's Nelder-Mead search stopped improving locally — it does NOT certify that mu/alpha are well identified. Near alpha≈1 the likelihood surface has a shallow mu-alpha ridge (`fit_hawkes_exp`'s docstring), so a `converged=True` window near the boundary of alpha is a weaker signal than the same flag away from it.
- **Runtime cap** (250,000 events/window): windows above this cap are fit on a truncated prefix, not the full window. This bounds cost but means those windows' alpha reflects only the earliest events in an otherwise larger window.
- **count-variance window (200s business-time default)**: a fixed, documented choice, not tuned per symbol beyond the 20/median_beta sanity widening described above; a different window choice could shift alpha_cv, particularly for symbols near the sanity threshold.
- **Heteroskedasticity in the activity regression**: as in Q4/Q5, per-symbol alpha_median dispersion (alpha_iqr) is not uniform across the cross-section, so the OLS regression's homoskedastic-residual assumption is almost certainly violated; the reported slope/R²/stderr are descriptive, not a formal confidence interval.
- **48-bin intraday profile**: `intraday_rate_profile` estimates the seasonal shape from the SAME month's data being fit, not an independent sample — any genuine self-excitation clustering at the same time-of-day scale (unlikely at 48-bin, ~30-minute resolution, but not provably absent) could partially leak into the profile and be removed along with the seasonal confound.
