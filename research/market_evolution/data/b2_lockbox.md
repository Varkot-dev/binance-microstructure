# B2: lock-box test of the frozen delisting candidates

Built by `research/market_evolution/b2_lockbox.py lockbox` from `delisting_panel.parquet`.
Run time 4 s, LightGBM on 2 threads.

<!-- b2 lock-box result -->
Lock-box runs: first run on 2026-11-18.

## 1. Frozen configuration (written before scoring)

Code and data come from commit `b3571a691e6cfb52cea23c8d875c163e0b7e39a8` (HEAD when the lock-box was run); last
commits touching the frozen files: `b0_baselines.py` d82639d, `b1_models.py` b2f99de, `delisting_panel.parquet` d82639d. Uncommitted changes to them:
none. `delisting_panel.parquet` sha256
`47084640e4cef695...`. b2 imports b0 and b1 and calls their functions; it sets
no modelling option of its own.

- **(a) falling volume** (b0): score = -dlog_qv_3m (null ranks last). No fitted part.
- **(b) lowest volume rank** (b0): score = -qv_rank_pct, the within-month percentile rank of
  log quote volume among live contracts. No fitted part. This is the bar.
- **Logistic, full features** (b1 `fit_logit_tuned`), 35 features:
  - volume level: log_qv, qv_rank_pct, log_trades, trades_rank_pct, log_qv_median, log_avg_trade
  - volume trend: dlog_qv_3m, dlog_qv_6m, dlog_trades_3m, dlog_trades_6m, log_qv_rel_peak, log_trades_rel_peak, dlog_qv_3m_rank
  - age: log_age
  - price and drawdown: ret_month, ret_3m, ret_6m, ret_3m_rank, dd_life_month_end, max_dd_life, log_price
  - volatility: realized_vol, mean_range
  - open interest: log_oi, oi_rank_pct, log_oi_to_qv, dlog_oi_3m, ls_account_month_end, ls_toptrader_account_month_end
  - funding: funding_mean, funding_abs_mean, funding_interval_min_h, funding_interval_shortened
  - other activity: taker_buy_share, zero_volume_days
  Preprocessing fitted on the training rows only: median imputation plus a missing
  indicator per column with some (not all) missing values, winsorizing at the 1st and 99th
  percentiles, standardizing. L2 penalty, no class weights, lbfgs, max_iter 3000. C chosen
  from [0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0] by PR-AUC on the inner split (validation = the last
  12 training months; inner-train rows have t + 3 < its first month; ties
  go to the smaller C), then refit on all training rows.
- **LightGBM, full features** (b1 `fit_gbm_tuned`): objective=binary, learning_rate=0.03, num_leaves=15, max_depth=-1, min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, n_estimators=1000, num_threads=2, random_state=0; no class weights, missing
  values native. Trees chosen by early stopping on inner-split average precision (patience
  50, at least 20 trees, 200 if the inner block has no
  positive), then refit on all training rows with that number of trees.
- **Alert rule** (b0): each month flag the top max(1, round(0.05 x live contracts)) by
  score; ties by row order (month, life id). No other threshold enters the headline.
- **Training rows:** every labelled row with t + 3 < 2026-01 (t <= 2025-09), so no label
  window reaches 2026-01; origins 2025-10 to 2025-12 are purged. The sensitivity run also
  drops `final_full_month` rows from training and lock-box rows, as b0 and b1 do.
- **Intervals:** b0's moving-block bootstrap of lock-box months (blocks of
  3, 2000 replicates, seed 0); paired differences use the
  same replicates.

Choices the frozen inner procedures made on the training rows (before scoring):

| run | train rows | train positives | last train month | inner validation | inner val positives | C (logistic) | trees (LightGBM) | training base rate |
|---|---|---|---|---|---|---|---|---|
| main | 13,002 | 244 | 2025-09 | 2024-10 to 2025-09 | 119 | 0.03 | 20 | 0.0188 |
| drop final full month | 12,930 | 172 | 2025-09 | 2024-10 to 2025-09 | 87 | 0.01 | 36 | 0.0133 |

## 2. Lock-box size

- Origins 2026-01 to 2026-07: 7 months,
  3,730 contract-months, 145 positive rows from 61
  event lives (main run). Those lives stopped trading on 23 distinct days in
  9 calendar months: Binance delists in batches, so the effective number
  of independent events is closer to the number of batches than to 61.
- The bootstrap resamples 7 months in blocks of 3:
  only 5 distinct blocks exist, so the intervals
  are rough and likely too narrow.
- Sensitivity run (final full month dropped): 3,677
  rows, 92 positive rows.

## 3. Results

### main

Lock-box rows 3,730 (574 lives) over 7 origin months
(2026-01 to 2026-07); 145 positive rows from
61 event lives; base rate 0.0389 (0.0241 to 0.0533).

| candidate | precision at top 5% | recall | hits/alerts | PR-AUC |
|---|---|---|---|---|
| (a) falling volume | 0.054 (0.016 to 0.090) | 0.069 (0.033 to 0.087) | 10/185 | 0.052 (0.020 to 0.082) |
| (b) lowest volume rank | 0.151 (0.066 to 0.243) | 0.193 (0.135 to 0.217) | 28/185 | 0.119 (0.046 to 0.196) |
| logistic, full features | 0.270 (0.187 to 0.356) | 0.345 (0.318 to 0.392) | 50/185 | 0.202 (0.119 to 0.312) |
| LightGBM, full features | 0.216 (0.148 to 0.309) | 0.276 (0.251 to 0.327) | 40/185 | 0.171 (0.123 to 0.245) |

Paired differences against (b), same bootstrap months:

| difference | precision | recall | PR-AUC |
|---|---|---|---|
| logistic, full features - (b) | 0.119 (0.097 to 0.145) | 0.152 (0.103 to 0.247) | 0.083 (0.061 to 0.151) |
| LightGBM, full features - (b) | 0.065 (0.038 to 0.124) | 0.083 (0.045 to 0.183) | 0.052 (0.033 to 0.119) |
| (a) falling volume - (b) | -0.097 (-0.148 to -0.044) | -0.124 (-0.149 to -0.083) | -0.067 (-0.113 to -0.025) |

Robustness (not a frozen metric): range of the precision difference against (b) when one
lock-box month is left out: logistic, full features +0.101 to +0.139; LightGBM, full features +0.044 to +0.095; (a) falling volume -0.119 to -0.076.

Brier score: logistic 0.03467, LightGBM 0.03658,
predicting the training base rate 0.03777. Brier skill: logistic
0.082 (0.041 to 0.102), LightGBM 0.031 (0.027 to 0.035). Mean predicted
probability: logistic 0.0300, LightGBM
0.0227, against an observed 0.0389.

By month (hits among the alerts):

| origin month | live rows | alerts | positive rows | event lives | (a) | (b) | logistic | LightGBM |
|---|---|---|---|---|---|---|---|---|
| 2026-01 | 543 | 27 | 34 | 34 | 3 | 9 | 13 | 6 |
| 2026-02 | 541 | 27 | 31 | 31 | 3 | 8 | 8 | 10 |
| 2026-03 | 539 | 27 | 28 | 28 | 2 | 4 | 10 | 9 |
| 2026-04 | 526 | 26 | 12 | 12 | 1 | 1 | 5 | 4 |
| 2026-05 | 526 | 26 | 15 | 15 | 0 | 4 | 5 | 5 |
| 2026-06 | 527 | 26 | 10 | 10 | 1 | 0 | 5 | 3 |
| 2026-07 | 528 | 26 | 15 | 15 | 0 | 2 | 4 | 3 |

### drop final full month

Lock-box rows 3,677 (567 lives) over 7 origin months
(2026-01 to 2026-07); 92 positive rows from
54 event lives; base rate 0.0250 (0.0159 to 0.0343).

| candidate | precision at top 5% | recall | hits/alerts | PR-AUC |
|---|---|---|---|---|
| (a) falling volume | 0.038 (0.011 to 0.059) | 0.076 (0.032 to 0.090) | 7/184 | 0.037 (0.014 to 0.056) |
| (b) lowest volume rank | 0.125 (0.066 to 0.188) | 0.250 (0.207 to 0.303) | 23/184 | 0.092 (0.044 to 0.142) |
| logistic, full features | 0.174 (0.077 to 0.258) | 0.348 (0.237 to 0.381) | 32/184 | 0.133 (0.056 to 0.233) |
| LightGBM, full features | 0.125 (0.066 to 0.188) | 0.250 (0.207 to 0.338) | 23/184 | 0.085 (0.060 to 0.141) |

Paired differences against (b), same bootstrap months:

| difference | precision | recall | PR-AUC |
|---|---|---|---|
| logistic, full features - (b) | 0.049 (-0.016 to 0.081) | 0.098 (-0.049 to 0.126) | 0.041 (0.002 to 0.092) |
| LightGBM, full features - (b) | 0.000 (-0.005 to 0.022) | 0.000 (-0.014 to 0.052) | -0.007 (-0.022 to 0.040) |
| (a) falling volume - (b) | -0.087 (-0.134 to -0.044) | -0.174 (-0.262 to -0.138) | -0.056 (-0.089 to -0.027) |

Robustness (not a frozen metric): range of the precision difference against (b) when one
lock-box month is left out: logistic, full features +0.019 to +0.076; LightGBM, full features -0.013 to +0.006; (a) falling volume -0.108 to -0.070.

Brier score: logistic 0.02337, LightGBM 0.02388,
predicting the training base rate 0.02453. Brier skill: logistic
0.047 (0.013 to 0.062), LightGBM 0.027 (0.019 to 0.033). Mean predicted
probability: logistic 0.0213, LightGBM
0.0185, against an observed 0.0250.

By month (hits among the alerts):

| origin month | live rows | alerts | positive rows | event lives | (a) | (b) | logistic | LightGBM |
|---|---|---|---|---|---|---|---|---|
| 2026-01 | 536 | 27 | 27 | 27 | 3 | 6 | 12 | 5 |
| 2026-02 | 532 | 27 | 22 | 22 | 2 | 7 | 7 | 6 |
| 2026-03 | 521 | 26 | 10 | 10 | 0 | 3 | 4 | 5 |
| 2026-04 | 522 | 26 | 8 | 8 | 1 | 1 | 2 | 1 |
| 2026-05 | 520 | 26 | 9 | 9 | 0 | 4 | 1 | 3 |
| 2026-06 | 525 | 26 | 8 | 8 | 1 | 0 | 3 | 1 |
| 2026-07 | 521 | 26 | 8 | 8 | 0 | 2 | 3 | 2 |

## 4. Comparison with the cross-validation estimates

CV = 36 test months 2023-01 to 2025-12 (b0 and b1, same metrics and bootstrap). The
verdict column applies only to the paired differences against (b).

| metric | CV (b0/b1) | lock-box | lock-box vs CV |
|---|---|---|---|
| main: base rate | 0.0238 | 0.0389 | |
| main: prec_base_a | 0.027 (0.008 to 0.052) | 0.054 (0.016 to 0.090) |  |
| main: prec_base_b | 0.083 (0.031 to 0.133) | 0.151 (0.066 to 0.243) |  |
| main: prec_logit_full | 0.101 (0.038 to 0.153) | 0.270 (0.187 to 0.356) |  |
| main: prec_gbm_full | 0.078 (0.031 to 0.114) | 0.216 (0.148 to 0.309) |  |
| main: ap_base_b | 0.056 (0.023 to 0.086) | 0.119 (0.046 to 0.196) |  |
| main: ap_logit_full | 0.076 (0.027 to 0.120) | 0.202 (0.119 to 0.312) |  |
| main: ap_gbm_full | 0.053 (0.017 to 0.087) | 0.171 (0.123 to 0.245) |  |
| main: prec_logit_full_minus_b | 0.018 (-0.008 to 0.042) | 0.119 (0.097 to 0.145) | strengthens: positive, interval now excludes 0 |
| main: ap_logit_full_minus_b | 0.020 (-0.019 to 0.055) | 0.083 (0.061 to 0.151) | strengthens: positive, interval now excludes 0 |
| main: prec_gbm_full_minus_b | -0.005 (-0.041 to 0.017) | 0.065 (0.038 to 0.124) | reverses: positive, interval excludes 0 |
| main: ap_gbm_full_minus_b | -0.004 (-0.036 to 0.030) | 0.052 (0.033 to 0.119) | reverses: positive, interval excludes 0 |
| main: bss_logit_full | 0.021 (-0.006 to 0.038) | 0.082 (0.041 to 0.102) |  |
| drop final full month: base rate | 0.0166 | 0.0250 | |
| drop final full month: prec_base_a | 0.016 (0.003 to 0.032) | 0.038 (0.011 to 0.059) |  |
| drop final full month: prec_base_b | 0.055 (0.021 to 0.082) | 0.125 (0.066 to 0.188) |  |
| drop final full month: prec_logit_full | 0.062 (0.017 to 0.094) | 0.174 (0.077 to 0.258) |  |
| drop final full month: prec_gbm_full | 0.045 (0.015 to 0.070) | 0.125 (0.066 to 0.188) |  |
| drop final full month: ap_base_b | 0.040 (0.014 to 0.060) | 0.092 (0.044 to 0.142) |  |
| drop final full month: ap_logit_full | 0.060 (0.020 to 0.092) | 0.133 (0.056 to 0.233) |  |
| drop final full month: ap_gbm_full | 0.033 (0.012 to 0.055) | 0.085 (0.060 to 0.141) |  |
| drop final full month: prec_logit_full_minus_b | 0.007 (-0.019 to 0.022) | 0.049 (-0.016 to 0.081) | confirms the sign, interval includes 0 |
| drop final full month: ap_logit_full_minus_b | 0.020 (-0.004 to 0.045) | 0.041 (0.002 to 0.092) | strengthens: positive, interval now excludes 0 |
| drop final full month: prec_gbm_full_minus_b | -0.009 (-0.023 to 0.004) | 0.000 (-0.005 to 0.022) | confirms the sign, interval includes 0 |
| drop final full month: ap_gbm_full_minus_b | -0.008 (-0.023 to 0.012) | -0.007 (-0.022 to 0.040) | confirms the sign, interval includes 0 |
| drop final full month: bss_logit_full | 0.017 (-0.006 to 0.029) | 0.047 (0.013 to 0.062) |  |

## 5. Conclusion (plain language)

- **The lock-box confirms the direction of the CV result for the logistic model, and is
  stronger than CV.** Main run, top 5% of live contracts per month: logistic on all
  features 27.0% precision (18.7 to 35.6), rule (b) 15.1% (6.6 to 24.3), base rate 3.9%.
  Paired difference logistic minus (b): +0.119 (+0.097 to +0.145), and it stays positive
  when any one month is left out (+0.101 to +0.139). PR-AUC difference +0.083 (+0.061 to
  +0.151). In CV the same difference was +0.018 (-0.008 to +0.042): same sign, now with an
  interval clear of zero.
- **Without the final full month before the last trading month** (the fairer number,
  since that month often holds the announcement) the gain shrinks to +0.049 (-0.016 to
  +0.081) in precision, interval including zero, and +0.041 (+0.002 to +0.092) in PR-AUC.
  Logistic 17.4% against (b) 12.5%, base rate 2.5%. So more than half of the main-run gain
  comes from the announcement month, which a live user would reach too late; on the fair
  version the logistic model is ahead of the volume rank but not decisively.
- **Rule (b) holds up**: it beats chance by about 4 to 5 times in both runs, as in CV.
  **Rule (a)**, falling volume, stays near chance (5.4% against a 3.9% base rate main,
  3.8% against 2.5% without the final full month), as in CV.
- **LightGBM**: CV said no better than (b). The lock-box main run puts it above (b)
  (+0.065, +0.038 to +0.124), which reverses that, but without the final full month it
  ties (b) exactly (+0.000, -0.005 to +0.022), which confirms CV. Its gain is the
  announcement month again. It is below the logistic model in every comparison.
- **The size of the gain is not confirmed, only its sign.** Every metric is about twice
  its CV value, mostly because the 2026 base rate is higher and the early-2026 batches
  were large. The pseudo lock-box check on b1's last fold (origins 2025-07 to 2025-12, the
  same code, run before the lock-box) already gave logistic minus (b) +0.059 main and
  +0.040 without the final full month, so the logistic edge has grown over recent periods
  rather than appearing from nowhere in 2026. That, plus the scores reproducing b1
  exactly on that fold, is the evidence that the large number is not a bug.
- **Calibration:** the logistic model has positive Brier skill (0.082 main, 0.047
  without the final full month) but under-predicts (mean 3.0% against 3.9% observed), as
  expected when the delisting rate keeps rising. Use the scores for ranking.
- **Verdict:** the frozen full-feature logistic model is the better delisting ranker on
  the 2026 lock-box, clearly on the main run and probably (positive point, interval
  touching zero in precision, clear of zero in PR-AUC) on the announcement-free run. The
  lowest-volume-rank rule remains a strong, model-free baseline.

## 6. Caveats

- **Few effective months.** 7 origin months, 3,730 contract-months, 145 positive rows from
  61 event lives. Those lives stopped on 23 distinct days in 9 calendar months, and 93 of
  the 145 positive rows sit in origins 2026-01 to 2026-03 (the 2026-04 batch alone is 18
  lives). A life dying in month L is positive at L-3, L-2 and L-1, so rows are not
  independent events. The month block bootstrap has only 5 distinct 3-month blocks, so its
  intervals are rough and probably too narrow; the leave-one-month-out ranges are given as
  a check, not as a frozen metric.
- **Announcement leakage.** 53 of the 145 positive rows are final full months. The main
  run is optimistic; the sensitivity run drops the whole month rather than cutting at the
  true announcement time, which the panel does not have.
- **The lock-box is not perfectly untouched.** Origins 2025-10 to 2025-12 have label
  windows reaching 2026-01 to 2026-03, so 16 of the 61 lock-box event lives were already
  positives in b1's last CV block. No b2 training row includes them (training stops at
  t = 2025-09), but the choice of the logistic model as a candidate was made after seeing
  CV results that counted those deaths.
- **Exactly one lock-box run.** The code was built and checked on the pre-2026 pseudo
  lock-box and on synthetic panels first (`tests/research/test_b2_lockbox.py`), then run
  once on 2026. No bug was found after the run; nothing was changed or rerun. The
  leave-one-month-out line was added before the lock-box run.
- The inner procedures chose C = 0.03 (main) and 0.01 (sensitivity) for the logistic
  model and 20 and 36 trees for LightGBM; these come from the inner split on training rows
  only and differ from the CV folds' choices (C = 1.0 in the last fold), which is the
  frozen procedure working as designed, not a change.
- The non-crypto screen (stocks, ETFs) used each life's whole trading history; all
  excluded lives are alive, so it removes negatives only, and a live user would know the
  underlying at listing.
- Trade-level features (predictability, aggTrade sizes) are not in this panel; the
  lock-box says nothing about them.

