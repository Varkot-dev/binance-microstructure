# Q6b: kernel-K sensitivity panel, does n̂ rise with K, and why?

## Method

For each symbol I load one month (2023-06) of aggTrades (`load_events`), rescale to business time as in Q6 (`intraday_rate_profile` + `rescale_to_business_time`, 48 bins), and split it into 6 equal contiguous sub-windows. Each sub-window is refit at every K in [1, 2, 3] with `fit_hawkes_multiexp` (a sum-of-K-exponentials Hawkes MLE), where Q6 used a single K=1 fit. For every K I record, per symbol and sub-window, n̂_K = sum(alpha_k) and β_slow_K = min(betas_K), the rate of the slowest-decaying component.

**Runtime cap**: a sub-window with more than 250,000 events is fit on its first 250,000 only, the same cap as Q6, applied at each K.

**Per-symbol summary**: the median across sub-windows of n̂_1, n̂_2, n̂_3, and Δ21 = median(n̂_2) − median(n̂_1), the K=1→K=2 branching-ratio jump. I also report the median across sub-windows of 1/β_slow at K=2 (the slower component's timescale in business-time seconds), as two ratios: against the deseasonalization bin width (1800.0s = 86400/48) and against the sub-window length.

## The confound Δ21 alone does not resolve

**A K=1→K=2 rise in n̂ together with a slow kernel component can also come from residual baseline non-stationarity, not only from a long-memory kernel.** A synthetic control in this repo's tests ("Case A") shows it: a true n=0.4 single-exponential process with a ±30% baseline-rate wobble that survives imperfect deseasonalization fits at K=1 with n̂≈0.46 and at K=2 with n̂≈0.83. That is a large, spurious Δ21 with no long-memory kernel in the generating model. A second exponential with a very slow beta is flexible enough to absorb a slow drift in the baseline rate and inflate the K=2 branching-ratio sum. Filimonov & Sornette (2015) document the same mechanism for the count-variance estimator's regime-switching trap. Here it also affects the sum-of-exponentials MLE.

**Why I report 1/β_slow vs. bin width and not Δ21 alone.** A slow component decaying on a timescale comparable to or longer than the deseasonalization bin width is the shape a residual seasonality artifact at that scale would produce. The 48-bin intraday profile cannot resolve structure finer than one bin, so leftover non-stationarity at or above that scale could generate a slow K=2 component. Symbols whose median 1/β_slow (K=2) exceeds 10x the bin width are flagged **drift-suspect** in the panel table. For those, a large Δ21 is ambiguous between long memory and residual non-stationarity.

**The decisive control runs on one window per symbol** (see "Is the K=2 rise drift or memory?" below): K=1 is refit with a block-wise (piecewise-constant) mu and compared with the K=2 gain. It is a heuristic screen with a stated resolution limit, so Δ21 and the drift-suspect flag remain triage quantities.

## Run summary

Requested: 41. Successful: 41. Failed: 0.

## Panel table (sorted by n_events)

| symbol | n_events | n̂_1 | n̂_2 | n̂_3 | Δ21 | 1/β_slow (K=2, s) | ÷ bin width | ÷ window length | drift-suspect | within null | drift verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 21,816,890 | 0.7933 | 0.8572 | 0.8781 | +0.0639 | 2.26 | 0.00x | 0.00x | no | NO | inconclusive |
| ETHUSDT | 14,239,099 | 0.6456 | 0.7878 | 0.8419 | +0.1422 | 1.82 | 0.00x | 0.00x | no | NO | inconclusive |
| 1000PEPEUSDT | 12,675,042 | 0.6924 | 0.8508 | 0.8834 | +0.1584 | 2.56 | 0.00x | 0.00x | no | NO | inconclusive |
| BCHUSDT | 10,755,244 | 0.7888 | 0.8618 | 0.8963 | +0.0730 | 8.89 | 0.00x | 0.00x | no | NO | inconclusive |
| TOMOUSDT | 9,258,867 | 0.4069 | 0.8385 | 0.8785 | +0.4316 | 4.49 | 0.00x | 0.00x | no | NO | inconclusive |
| LINAUSDT | 8,757,826 | 0.8790 | 0.9750 | 0.9984 | +0.0960 | 1020.16 | 0.57x | 0.00x | no | NO | inconclusive |
| MTLUSDT | 8,611,397 | 0.5802 | 0.8815 | 0.8949 | +0.3012 | 6.25 | 0.00x | 0.00x | no | NO | inconclusive |
| XRPUSDT | 7,617,768 | 0.8325 | 0.8801 | 0.9062 | +0.0475 | 5.60 | 0.00x | 0.00x | no | NO | inconclusive |
| SOLUSDT | 6,820,337 | 0.5708 | 0.8502 | 0.8881 | +0.2794 | 4.93 | 0.00x | 0.00x | no | NO | inconclusive |
| WAVESUSDT | 6,269,680 | 0.5762 | 0.8423 | 0.8736 | +0.2661 | 10.37 | 0.01x | 0.00x | no | NO | inconclusive |
| BNBUSDT | 6,122,425 | 0.7542 | 0.8487 | 0.8885 | +0.0945 | 5.15 | 0.00x | 0.00x | no | NO | inconclusive |
| SUIUSDT | 6,074,349 | 0.6570 | 0.8415 | 0.8779 | +0.1845 | 5.35 | 0.00x | 0.00x | no | NO | inconclusive |
| LTCUSDT | 5,400,099 | 0.8456 | 0.8659 | 0.9256 | +0.0202 | 5.87 | 0.00x | 0.00x | no | NO | inconclusive |
| OPUSDT | 5,208,936 | 0.4571 | 0.8485 | 0.8758 | +0.3914 | 5.21 | 0.00x | 0.00x | no | NO | inconclusive |
| MATICUSDT | 5,163,143 | 0.8476 | 0.8690 | 0.8985 | +0.0215 | 5.46 | 0.00x | 0.00x | no | NO | inconclusive |
| RNDRUSDT | 5,054,960 | 0.3925 | 0.8343 | 0.8735 | +0.4418 | 4.26 | 0.00x | 0.00x | no | NO | inconclusive |
| ALPHAUSDT | 4,736,244 | 0.4161 | 0.8698 | 0.8899 | +0.4537 | 8.65 | 0.00x | 0.00x | no | NO | inconclusive |
| INJUSDT | 4,557,308 | 0.6102 | 0.8417 | 0.9007 | +0.2315 | 5.70 | 0.00x | 0.00x | no | NO | inconclusive |
| ADAUSDT | 4,406,216 | 0.8010 | 0.8685 | 0.8951 | +0.0675 | 11.81 | 0.01x | 0.00x | no | NO | inconclusive |
| ARBUSDT | 4,308,450 | 0.7070 | 0.8603 | 0.8917 | +0.1533 | 6.32 | 0.00x | 0.00x | no | NO | inconclusive |
| 1000LUNCUSDT | 4,196,777 | 0.6214 | 0.8540 | 0.8793 | +0.2326 | 10.37 | 0.01x | 0.00x | no | NO | inconclusive |
| STXUSDT | 4,075,254 | 0.7726 | 0.8637 | 0.8917 | +0.0911 | 7.91 | 0.00x | 0.00x | no | NO | inconclusive |
| ARPAUSDT | 3,793,737 | 0.6451 | 0.8259 | 0.8523 | +0.1808 | 7.04 | 0.00x | 0.00x | no | NO | inconclusive |
| LDOUSDT | 3,762,036 | 0.4260 | 0.8594 | 0.8882 | +0.4334 | 7.23 | 0.00x | 0.00x | no | NO | inconclusive |
| APEUSDT | 3,687,286 | 0.8790 | 0.9160 | 0.9646 | +0.0370 | 10.90 | 0.01x | 0.00x | no | NO | inconclusive |
| ETCUSDT | 3,656,191 | 0.7265 | 0.8541 | 0.8938 | +0.1276 | 6.86 | 0.00x | 0.00x | no | NO | inconclusive |
| DOGEUSDT | 3,605,236 | 0.8182 | 0.8569 | 0.8761 | +0.0387 | 9.33 | 0.01x | 0.00x | no | NO | inconclusive |
| CFXUSDT | 3,540,863 | 0.8273 | 0.8586 | 0.8784 | +0.0313 | 8.99 | 0.00x | 0.00x | no | NO | inconclusive |
| KAVAUSDT | 3,391,557 | 0.5372 | 0.8366 | 0.8711 | +0.2993 | 6.66 | 0.00x | 0.00x | no | NO | inconclusive |
| APTUSDT | 3,361,904 | 0.7696 | 0.8514 | 0.8755 | +0.0818 | 7.03 | 0.00x | 0.00x | no | NO | inconclusive |
| BTCBUSD | 3,259,833 | 0.5666 | 0.8184 | 0.8711 | +0.2518 | 3.74 | 0.00x | 0.00x | no | NO | inconclusive |
| COMPUSDT | 3,070,323 | 0.7705 | 0.8427 | 0.8663 | +0.0723 | 8.34 | 0.00x | 0.00x | no | NO | inconclusive |
| 1000SHIBUSDT | 3,031,796 | 0.8695 | 0.8950 | 0.9242 | +0.0256 | 9.50 | 0.01x | 0.00x | no | NO | inconclusive |
| EDUUSDT | 2,940,081 | 0.3719 | 0.8446 | 0.8674 | +0.4727 | 10.55 | 0.01x | 0.00x | no | NO | inconclusive |
| KEYUSDT | 2,889,130 | 0.3699 | 0.8593 | 0.8730 | +0.4894 | 7.15 | 0.00x | 0.00x | no | NO | inconclusive |
| SANDUSDT | 2,732,112 | 0.8193 | 0.8659 | 0.8781 | +0.0467 | 9.33 | 0.01x | 0.00x | no | NO | inconclusive |
| ETHBUSD | 2,661,029 | 0.5477 | 0.7257 | 0.7551 | +0.1780 | 3.84 | 0.00x | 0.00x | no | NO | inconclusive |
| LINKUSDT | 2,627,039 | 0.7948 | 0.8614 | 0.8735 | +0.0667 | 10.45 | 0.01x | 0.00x | no | NO | inconclusive |
| AVAXUSDT | 2,458,978 | 0.6058 | 0.8361 | 0.8746 | +0.2303 | 7.22 | 0.00x | 0.00x | no | NO | inconclusive |
| ATOMUSDT | 2,456,324 | 0.7510 | 0.8410 | 0.8950 | +0.0900 | 6.21 | 0.00x | 0.00x | no | NO | inconclusive |
| IDUSDT | 2,144,610 | 0.7634 | 0.8461 | 0.8629 | +0.0828 | 11.23 | 0.01x | 0.00x | no | NO | inconclusive |

## Cross-section

**Δ21 distribution** across 41 symbols: median = **0.1422**, mean = 0.1824, sd = 0.1454, range = [0.0202, 0.4894].

**Null floor for Δ21**, computed at the panel's per-window event count (699,462 events) from 5 simulated well-specified K=1 processes with alpha=0.7070 (this panel's median n̂_1) and beta=2.0 (see `spurious_delta21_null`). The null's 90th percentile is **0.0093** (median 0.0073). Symbols whose Δ21 does not exceed it are labeled **"within finite-sample null"** in the panel table (0/41 symbols). Their Δ21 is no larger than a well-specified, non-long-memory K=1 process of this size would produce from sampling noise alone, so it is not evidence of long-memory kernel structure on its own.

**Fraction of symbols with n̂_2 ≥ 0.9** (near-critical at K=2): **4.9%**.

**Against Q6's count-variance n̂** (n=41): the median gap is 0.2395 at K=1 and 0.1026 at K=2, and the median share of the gap closed by K=2 is 54%. Across symbols, corr(n̂_2, count-variance n̂) = 0.4490. Δ21 is not correlated with the K=1 gap directly: both contain −n̂_1, so that correlation is high by construction.

## Is the K=2 rise drift or memory?

**Most symbols show no material K=1→K=2 rise in this window — there is no apparent near-criticality for the control to explain (41 of 41 requested symbols assessed; failed, errored and not-run excluded).**

Verdict counts over 41 symbols with results: drift = 0, long_memory_candidate = 0, inconclusive = 41 (no_rise = 25, k2_insignificant = 0, mixed = 16), not run = 0, errored = 0.

Per symbol, on the first business-time window only (to bound cost; that window is capped at 250,000 events), I compare K=1 with one constant baseline against K=1 with a piecewise-constant baseline over 12 equal blocks, and against the window's K=2 fit. Median block width: 6.3 business-time hours (22562 business-time seconds). `dll_pw` and `dll_k2` are the log-likelihood gains over constant-baseline K=1 from the block baseline and from the second kernel component. `threshold` is chi-square(0.95, blocks−1)/2.

**Method caveats.**
- This is a heuristic likelihood-ratio screen, not a formal test. The fits are Nelder-Mead optima, the chi-square calibration is only approximate for Hawkes likelihoods, and the half-of-`dll_k2` cut-off is a convention.
- Resolution limit: a block baseline absorbs only drift slower than the block width (median 6.3 business-time hours (22562 business-time seconds)). Faster baseline wobble averages out inside a block and looks like long memory, so `long_memory_candidate` means something only for drift slower than that width.
- Misspecification: when K=1 is wrong (real long memory), block counts are more dispersed than K=1 predicts, which inflates `dll_pw`. That can push a symbol with real long memory to `inconclusive` OR across the drift threshold into `drift`. A `drift` label means only that the block baseline recovers at least half of the K=2 gain. It does not exclude long memory.
- `inconclusive` is split by reason: `no_rise` (K=2 n̂ − K=1 n̂ ≤ 0.1, so there is nothing to explain), `k2_insignificant` (the K=2 gain `dll_k2` is below 3.00 nats = chi-square(0.95, 2)/2), and `mixed` (a material, significant K=2 gain that the block baseline recovers significantly but by less than half).
- Business-time rescaling has already removed the 48-bin periodic intraday profile, so the control targets aperiodic drift.

| symbol | verdict | inconclusive reason | n̂_1 (const) | n̂_2 | n̂_1 (piecewise) | dll_pw | dll_k2 | threshold | block width (business-time h) |
|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | inconclusive | no_rise | 0.8273 | 0.8540 | 0.7845 | 213.54 | 7553.80 | 9.84 | 0.62 |
| ETHUSDT | inconclusive | no_rise | 0.7418 | 0.7966 | 0.6863 | 547.14 | 10686.01 | 9.84 | 1.13 |
| 1000PEPEUSDT | inconclusive | mixed | 0.6831 | 0.8160 | 0.6065 | 1702.07 | 14913.48 | 9.84 | 1.91 |
| BCHUSDT | inconclusive | no_rise | 0.8092 | 0.8603 | 0.7581 | 842.38 | 8106.02 | 9.84 | 10.00 |
| TOMOUSDT | inconclusive | mixed | 0.3535 | 0.8010 | 0.3374 | 2677.32 | 29594.61 | 9.84 | 4.98 |
| LINAUSDT | inconclusive | mixed | 0.8646 | 1.0000 | 0.8489 | 61.28 | 1754929.77 | 9.84 | 0.90 |
| MTLUSDT | inconclusive | no_rise | 0.8734 | 0.9311 | 0.6576 | 3504.67 | 24987.43 | 9.84 | 5.97 |
| XRPUSDT | inconclusive | no_rise | 0.8285 | 0.8911 | 0.7825 | 294.96 | 1430.02 | 9.84 | 3.19 |
| SOLUSDT | inconclusive | mixed | 0.6201 | 0.8268 | 0.5071 | 1940.83 | 27768.12 | 9.84 | 4.68 |
| WAVESUSDT | inconclusive | mixed | 0.4800 | 0.8163 | 0.4399 | 5244.16 | 29297.13 | 9.84 | 10.00 |
| BNBUSDT | inconclusive | no_rise | 0.6607 | 0.7172 | 0.6294 | 385.94 | 6892.18 | 9.84 | 6.74 |
| SUIUSDT | inconclusive | mixed | 0.5243 | 0.7999 | 0.4600 | 1906.88 | 22146.29 | 9.84 | 4.59 |
| LTCUSDT | inconclusive | no_rise | 0.8725 | 0.8855 | 0.8524 | 113.72 | 3822.37 | 9.84 | 1.96 |
| OPUSDT | inconclusive | mixed | 0.4196 | 0.8252 | 0.3780 | 3001.22 | 23832.19 | 9.84 | 2.74 |
| MATICUSDT | inconclusive | no_rise | 0.7864 | 0.8546 | 0.7599 | 325.80 | 4157.35 | 9.84 | 8.02 |
| RNDRUSDT | inconclusive | mixed | 0.3668 | 0.8096 | 0.3623 | 1705.85 | 21757.07 | 9.84 | 2.98 |
| ALPHAUSDT | inconclusive | mixed | 0.4274 | 0.8676 | 0.3908 | 12166.88 | 37481.60 | 9.84 | 6.45 |
| INJUSDT | inconclusive | no_rise | 0.7960 | 0.8854 | 0.6536 | 1505.99 | 18108.43 | 9.84 | 2.71 |
| ADAUSDT | inconclusive | no_rise | 0.8292 | 0.9142 | 0.7989 | 310.96 | 2708.32 | 9.84 | 6.49 |
| ARBUSDT | inconclusive | no_rise | 0.7859 | 0.8739 | 0.6704 | 1719.88 | 18852.70 | 9.84 | 4.05 |
| 1000LUNCUSDT | inconclusive | no_rise | 0.9434 | 0.9705 | 0.8787 | 525.06 | 2419.46 | 9.84 | 7.28 |
| STXUSDT | inconclusive | mixed | 0.6747 | 0.8225 | 0.6183 | 949.20 | 14943.71 | 9.84 | 10.00 |
| ARPAUSDT | inconclusive | mixed | 0.6572 | 0.7978 | 0.6006 | 657.20 | 19414.38 | 9.84 | 4.11 |
| LDOUSDT | inconclusive | mixed | 0.4924 | 0.8931 | 0.3707 | 15243.62 | 32462.62 | 9.84 | 3.68 |
| APEUSDT | inconclusive | no_rise | 0.8931 | 0.9333 | 0.8864 | 90.44 | 3131.67 | 9.84 | 7.90 |
| ETCUSDT | inconclusive | no_rise | 0.7685 | 0.8386 | 0.7522 | 331.43 | 13644.41 | 9.84 | 9.38 |
| DOGEUSDT | inconclusive | no_rise | 0.7600 | 0.8477 | 0.7481 | 172.09 | 4678.37 | 9.84 | 8.72 |
| CFXUSDT | inconclusive | no_rise | 0.8180 | 0.8391 | 0.7810 | 352.81 | 5636.82 | 9.84 | 5.54 |
| KAVAUSDT | inconclusive | mixed | 0.6691 | 0.8421 | 0.5413 | 3880.31 | 27897.15 | 9.84 | 9.17 |
| APTUSDT | inconclusive | mixed | 0.6970 | 0.8272 | 0.6132 | 1478.93 | 18570.80 | 9.84 | 6.32 |
| BTCBUSD | inconclusive | mixed | 0.6341 | 0.7861 | 0.5546 | 2600.47 | 25442.97 | 9.84 | 6.27 |
| COMPUSDT | inconclusive | no_rise | 0.6782 | 0.7710 | 0.6397 | 456.13 | 5565.18 | 9.84 | 10.00 |
| 1000SHIBUSDT | inconclusive | no_rise | 0.8717 | 0.8959 | 0.8626 | 94.22 | 7678.24 | 9.84 | 7.83 |
| EDUUSDT | inconclusive | mixed | 0.2983 | 0.8270 | 0.2771 | 6572.00 | 26708.69 | 9.84 | 6.54 |
| KEYUSDT | inconclusive | no_rise | 0.8305 | 0.9106 | 0.7114 | 1170.00 | 11814.26 | 9.84 | 0.92 |
| SANDUSDT | inconclusive | no_rise | 0.8949 | 0.9184 | 0.8711 | 246.57 | 6002.90 | 9.84 | 3.90 |
| ETHBUSD | inconclusive | no_rise | 0.7075 | 0.7303 | 0.6796 | 389.16 | 8024.64 | 9.84 | 5.18 |
| LINKUSDT | inconclusive | no_rise | 0.8042 | 0.8763 | 0.7842 | 276.63 | 3454.17 | 9.84 | 9.33 |
| AVAXUSDT | inconclusive | no_rise | 0.7400 | 0.8127 | 0.7166 | 597.85 | 16385.40 | 9.84 | 9.26 |
| ATOMUSDT | inconclusive | no_rise | 0.7904 | 0.8642 | 0.7694 | 400.49 | 6878.17 | 9.84 | 9.28 |
| IDUSDT | inconclusive | no_rise | 0.8144 | 0.8822 | 0.7902 | 409.17 | 15339.96 | 9.84 | 9.52 |

## Findings

Across 41 successful symbols, the median K=1→K=2 branching-ratio jump is **+0.1422**. 0/41 symbols are flagged drift-suspect (median 1/β_slow at K=2 exceeds 10x the deseasonalization bin width of 1800.0s). The second kernel component decays inside one deseasonalization bin for every symbol, so Δ21 is not explained by intraday seasonality that the rescaling missed.

## Caveats

- **The confound is only partly resolved.** A large Δ21 fits both long-memory kernel structure and residual baseline non-stationarity that survives deseasonalization. The block-wise-baseline control (first window per symbol, heuristic, limited to drift slower than its block width) is reported in "Is the K=2 rise drift or memory?" and is absent when `--drift-blocks 0`.
- **Single month** (2023-06): one market regime; results may not carry over to other months.
- **Higher-K identifiability**: per the `fit_hawkes_multiexp` docstring, individual alpha_k and beta_k become less identified as K grows relative to what the sample can resolve. n̂_K (the sum) is more trustworthy than any single component, but β_slow (the min beta) can still be noisy, at K=3 in particular.
- **Runtime cap** (250,000 events/window): windows above the cap are fit on a truncated prefix, applied independently at each K.
- **48-bin intraday profile**: as in Q6, the profile is estimated from the same month being fit, and real excitation clustering at ~30-minute resolution could leak into the deseasonalization.
