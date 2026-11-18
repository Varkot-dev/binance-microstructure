# B1: models against the delisting baselines

Built by `research/market_evolution/b1_models.py` from `delisting_panel.parquet`, reusing
the folds, purge, alert rule, PR-AUC and month block bootstrap of `b0_baselines.py`. Run
time 67 s, LightGBM on 2 threads.

**Lock-box: origins 2026-01 on are removed before any fit and are NOT scored.**
The bar to beat is b0's baseline (b), score = -qv_rank_pct: precision 8.3% at the top 5%,
PR-AUC 0.056 (main run).

Packages: lightgbm and scikit-learn are installed. **shap is not installed**: SHAP values
come from LightGBM's built-in TreeSHAP (`pred_contrib=True`), the algorithm that
`shap.TreeExplainer` uses. **lifelines is not installed, so the Cox time-varying model is
skipped**; the hazard view is a discrete-time logistic hazard with odds ratios instead
(for a monthly death rate of a few percent the odds ratio is close to the hazard ratio).

## Setup

- Features (35, month t and earlier only; within-month ranks use month t only):
  - volume level: log_qv, qv_rank_pct, log_trades, trades_rank_pct, log_qv_median, log_avg_trade
  - volume trend: dlog_qv_3m, dlog_qv_6m, dlog_trades_3m, dlog_trades_6m, log_qv_rel_peak, log_trades_rel_peak, dlog_qv_3m_rank
  - age: log_age
  - price and drawdown: ret_month, ret_3m, ret_6m, ret_3m_rank, dd_life_month_end, max_dd_life, log_price
  - volatility: realized_vol, mean_range
  - open interest: log_oi, oi_rank_pct, log_oi_to_qv, dlog_oi_3m, ls_account_month_end, ls_toptrader_account_month_end
  - funding: funding_mean, funding_abs_mean, funding_interval_min_h, funding_interval_shortened
  - other activity: taker_buy_share, zero_volume_days
- Logistic regression: median imputation and missing indicators, winsorizing at the 1st
  and 99th percentiles and standardizing, all fitted on the training rows of the fold;
  L2 penalty, no class weights; C from the inner split.
- LightGBM: objective=binary, learning_rate=0.03, num_leaves=15, max_depth=-1, min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, n_estimators=1000, num_threads=2, random_state=0;
  no class weights, missing values handled natively, early stopping on the inner split.
- Every model is fitted and scored on the same six folds as b0, then the sensitivity run
  drops `final_full_month` rows (the month before the last trading month, the one most
  likely to hold the announcement) from training and test rows, as b0 does.

## main

Test rows 11,028 over 36 origin months (2023-01 to 2025-12),
262 positive rows from 96 event lives; base rate
0.0238 (0.0129 to 0.0322). 95% intervals: b0's moving-block bootstrap of test months
(blocks of 3, 2000 replicates, seed 0: the same replicates
as b0, so the (b) row reproduces b0 exactly).

### Headline: top 5% of live contracts per month

| model | precision | recall | hits/alerts | PR-AUC |
|---|---|---|---|---|
| (b) lowest volume rank (bar) | 0.083 (0.031 to 0.133) | 0.176 (0.094 to 0.258) | 46/552 | 0.056 (0.023 to 0.086) |
| logistic, full features | 0.101 (0.038 to 0.153) | 0.214 (0.129 to 0.279) | 56/552 | 0.076 (0.027 to 0.120) |
| LightGBM, full features | 0.078 (0.031 to 0.114) | 0.164 (0.099 to 0.194) | 43/552 | 0.053 (0.017 to 0.087) |
| logistic, volume level + trend | 0.062 (0.026 to 0.089) | 0.130 (0.077 to 0.170) | 34/552 | 0.046 (0.016 to 0.074) |
| LightGBM, volume level + trend | 0.047 (0.027 to 0.066) | 0.099 (0.077 to 0.140) | 26/552 | 0.040 (0.020 to 0.056) |

Paired differences against (b), same bootstrap months:

| model | precision - (b) | recall - (b) | PR-AUC - (b) | beats (b), interval excludes 0 |
|---|---|---|---|---|
| logistic, full features | 0.018 (-0.008 to 0.042) | 0.038 (-0.023 to 0.083) | 0.020 (-0.019 to 0.055) | no |
| LightGBM, full features | -0.005 (-0.041 to 0.017) | -0.011 (-0.100 to 0.039) | -0.004 (-0.036 to 0.030) | no |
| logistic, volume level + trend | -0.022 (-0.056 to 0.003) | -0.046 (-0.125 to 0.010) | -0.011 (-0.038 to 0.013) | no |
| LightGBM, volume level + trend | -0.036 (-0.080 to 0.006) | -0.076 (-0.162 to 0.018) | -0.016 (-0.044 to 0.011) | no |

### Does anything beyond volume level and trend help?

Volume features alone (13: log_qv, qv_rank_pct, log_trades, trades_rank_pct, log_qv_median, log_avg_trade, dlog_qv_3m, dlog_qv_6m, dlog_trades_3m, dlog_trades_6m, log_qv_rel_peak, log_trades_rel_peak, dlog_qv_3m_rank), plus one group at a time. The
change columns are the point change against the same model on volume features only.

| model | precision | change vs volume only | PR-AUC | change vs volume only | PR-AUC - (b) |
|---|---|---|---|---|---|
| logistic, volume + age | 0.045 (0.025 to 0.067) | -0.016 | 0.045 (0.018 to 0.066) | -0.000 | -0.011 (-0.039 to 0.013) |
| logistic, volume + price and drawdown | 0.080 (0.039 to 0.110) | +0.018 | 0.054 (0.024 to 0.078) | +0.009 | -0.002 (-0.031 to 0.020) |
| logistic, volume + volatility | 0.062 (0.026 to 0.089) | +0.000 | 0.050 (0.017 to 0.080) | +0.005 | -0.006 (-0.035 to 0.019) |
| logistic, volume + open interest | 0.083 (0.036 to 0.121) | +0.022 | 0.053 (0.022 to 0.085) | +0.007 | -0.003 (-0.030 to 0.022) |
| logistic, volume + funding | 0.051 (0.025 to 0.075) | -0.011 | 0.049 (0.025 to 0.072) | +0.004 | -0.007 (-0.035 to 0.025) |
| logistic, volume + other activity | 0.063 (0.028 to 0.090) | +0.002 | 0.046 (0.016 to 0.071) | +0.000 | -0.010 (-0.038 to 0.011) |
| LightGBM, volume + age | 0.047 (0.024 to 0.070) | +0.000 | 0.042 (0.023 to 0.057) | +0.002 | -0.014 (-0.043 to 0.015) |
| LightGBM, volume + price and drawdown | 0.051 (0.023 to 0.071) | +0.004 | 0.041 (0.016 to 0.061) | +0.001 | -0.015 (-0.045 to 0.012) |
| LightGBM, volume + volatility | 0.058 (0.031 to 0.081) | +0.011 | 0.045 (0.020 to 0.059) | +0.005 | -0.011 (-0.040 to 0.014) |
| LightGBM, volume + open interest | 0.083 (0.029 to 0.125) | +0.036 | 0.050 (0.020 to 0.078) | +0.010 | -0.007 (-0.031 to 0.018) |
| LightGBM, volume + funding | 0.047 (0.024 to 0.070) | +0.000 | 0.050 (0.023 to 0.069) | +0.009 | -0.007 (-0.039 to 0.024) |
| LightGBM, volume + other activity | 0.051 (0.029 to 0.074) | +0.004 | 0.040 (0.021 to 0.051) | -0.001 | -0.017 (-0.044 to 0.007) |

### SHAP importance, LightGBM full model, last fold (test block 2025-07 to 2025-12)

Mean absolute TreeSHAP value (mean abs SHAP) on the test rows (log-odds), share of the total, and the
correlation between a feature's value and its SHAP value (sign = direction of the effect).

| feature | mean abs SHAP | share | corr(value, SHAP) |
|---|---|---|---|
| oi_rank_pct | 0.193 | 25% | -0.90 |
| funding_interval_min_h | 0.068 | 9% | -0.73 |
| funding_abs_mean | 0.050 | 7% | +0.58 |
| trades_rank_pct | 0.041 | 5% | -0.60 |
| max_dd_life | 0.036 | 5% | -0.37 |
| log_oi | 0.036 | 5% | -0.68 |
| ret_6m | 0.032 | 4% | -0.29 |
| ls_toptrader_account_month_end | 0.032 | 4% | +0.62 |
| log_avg_trade | 0.028 | 4% | -0.52 |
| log_price | 0.027 | 4% | -0.63 |
| dlog_oi_3m | 0.024 | 3% | +0.55 |
| log_age | 0.023 | 3% | +0.11 |
| log_qv_median | 0.018 | 2% | -0.55 |
| realized_vol | 0.018 | 2% | +0.24 |
| ret_3m | 0.016 | 2% | +0.13 |
| dlog_qv_3m_rank | 0.014 | 2% | +0.49 |
| ret_3m_rank | 0.012 | 2% | -0.02 |
| funding_mean | 0.011 | 1% | +0.09 |
| ls_account_month_end | 0.009 | 1% | +0.63 |
| log_oi_to_qv | 0.009 | 1% | +0.01 |
| log_trades_rel_peak | 0.008 | 1% | +0.41 |
| qv_rank_pct | 0.008 | 1% | -0.16 |
| dd_life_month_end | 0.007 | 1% | -0.29 |
| dlog_trades_3m | 0.007 | 1% | +0.28 |
| ret_month | 0.007 | 1% | +0.35 |
| log_trades | 0.006 | 1% | +0.21 |
| dlog_qv_3m | 0.005 | 1% | +0.32 |
| mean_range | 0.005 | 1% | +0.12 |
| taker_buy_share | 0.004 | 1% | +0.49 |
| dlog_trades_6m | 0.004 | 1% | -0.21 |
| dlog_qv_6m | 0.003 | 0% | +0.49 |
| log_qv_rel_peak | 0.002 | 0% | -0.07 |
| log_qv | 0.001 | 0% | +0.02 |
| funding_interval_shortened | 0.000 | 0% | nan |
| zero_volume_days | 0.000 | 0% | nan |

By group:

| group | mean abs SHAP summed | share |
|---|---|---|
| open interest | 0.303 | 40% |
| price and drawdown | 0.138 | 18% |
| funding | 0.130 | 17% |
| volume level | 0.102 | 13% |
| volume trend | 0.045 | 6% |
| volatility | 0.023 | 3% |
| age | 0.023 | 3% |
| other activity | 0.004 | 1% |

### Discrete-time hazard: odds ratios per 1 SD

Logistic hazard on all 14,599 pre-lock-box rows of this variant, label = the
life's last trading month is t + 1 (100 events). Odds ratio per 1 training SD (raw SD given), all
features in one model, missing values set to the median with an indicator; 95% intervals
from resampling contract lives (200 replicates). For rare events the odds ratio
is close to the hazard ratio. Interpretation only: this fit is not scored.

| feature | SD | odds ratio | 95% interval | excludes 1 |
|---|---|---|---|---|
| qv_rank_pct | 0.288 | 0.24 | 0.16 to 0.31 | yes |
| dlog_qv_3m | 1 | 0.96 | 0.72 to 1.25 | no |
| log_qv_rel_peak | 1.26 | 1.01 | 0.73 to 1.44 | no |
| log_age | 1.08 | 0.99 | 0.67 to 1.60 | no |
| dd_life_month_end | 0.27 | 0.85 | 0.55 to 1.45 | no |
| ret_3m | 0.65 | 0.82 | 0.60 to 1.10 | no |
| realized_vol | 0.0306 | 2.06 | 1.56 to 2.76 | yes |
| log_oi_to_qv | 0.647 | 0.75 | 0.56 to 1.04 | no |
| funding_abs_mean | 0.000229 | 1.37 | 1.08 to 1.65 | yes |

### Calibration

Calibration maps are fitted per fold on the inner validation block (the last
12 training months, scored by the model fitted on the inner-train rows) and
applied to the test scores of that inner model (the refitted model has a different score
range, so a map fitted on the inner model does not transfer to it). Brier skill =
1 - Brier / Brier of predicting the training base rate.

| scores | Brier | Brier skill (95%) |
|---|---|---|
| training base rate (reference) | 0.02325 |  |
| logit full | 0.02275 | 0.021 (-0.006 to 0.038) |
| gbm full | 0.02305 | 0.009 (-0.006 to 0.015) |
| logit full platt | 0.02314 | 0.005 (-0.009 to 0.012) |
| logit full isotonic | 0.02320 | 0.002 (-0.015 to 0.010) |
| gbm full platt | 0.02322 | 0.001 (-0.010 to 0.008) |
| gbm full isotonic | 0.02310 | 0.006 (-0.015 to 0.017) |

Reliability, best calibrated scores by Brier (gbm full isotonic), deciles:

| predicted range | rows | positives | mean predicted | observed rate |
|---|---|---|---|---|
| 0.0000 to 0.0041 | 1103 | 11 | 0.0031 | 0.0100 |
| 0.0041 to 0.0068 | 1103 | 22 | 0.0046 | 0.0199 |
| 0.0068 to 0.0103 | 1103 | 39 | 0.0091 | 0.0354 |
| 0.0103 to 0.0124 | 1103 | 13 | 0.0109 | 0.0118 |
| 0.0124 to 0.0124 | 1103 | 28 | 0.0124 | 0.0254 |
| 0.0124 to 0.0147 | 1103 | 10 | 0.0135 | 0.0091 |
| 0.0147 to 0.0258 | 1103 | 21 | 0.0183 | 0.0190 |
| 0.0258 to 0.0266 | 1103 | 6 | 0.0262 | 0.0054 |
| 0.0266 to 0.0304 | 1102 | 54 | 0.0290 | 0.0490 |
| 0.0304 to 0.5000 | 1102 | 58 | 0.0470 | 0.0526 |

Reliability, LightGBM full model before calibration, deciles:

| predicted range | rows | positives | mean predicted | observed rate |
|---|---|---|---|---|
| 0.0066 to 0.0085 | 1103 | 9 | 0.0076 | 0.0082 |
| 0.0085 to 0.0101 | 1103 | 19 | 0.0093 | 0.0172 |
| 0.0101 to 0.0110 | 1103 | 17 | 0.0105 | 0.0154 |
| 0.0110 to 0.0119 | 1103 | 14 | 0.0116 | 0.0127 |
| 0.0119 to 0.0128 | 1103 | 15 | 0.0123 | 0.0136 |
| 0.0129 to 0.0143 | 1103 | 14 | 0.0135 | 0.0127 |
| 0.0143 to 0.0165 | 1103 | 22 | 0.0153 | 0.0199 |
| 0.0165 to 0.0200 | 1103 | 24 | 0.0181 | 0.0218 |
| 0.0200 to 0.0267 | 1102 | 50 | 0.0229 | 0.0454 |
| 0.0267 to 0.1504 | 1102 | 78 | 0.0402 | 0.0708 |

### Folds

Training rows have t + 3 < test start (b0's folds). Inner split inside the training rows:
validation = the last 12 training months; inner-train rows have t + 3 < its
first month. C chosen by inner PR-AUC from [0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0]; LightGBM trees by early stopping
on inner average precision (patience 50; 200 trees when the inner block
has no positive row).

| test block | train rows | train pos | inner validation | inner val pos | C (logistic full) | trees (LightGBM full) | test rows | test pos |
|---|---|---|---|---|---|---|---|---|
| 2023-01 to 2023-06 | 3,138 | 53 | 2021-10 to 2022-09 | 48 | 0.003 | 20 | 1,019 | 5 |
| 2023-07 to 2023-12 | 4,049 | 62 | 2022-04 to 2023-03 | 30 | 0.01 | 20 | 1,275 | 4 |
| 2024-01 to 2024-06 | 5,177 | 65 | 2022-10 to 2023-09 | 12 | 1.0 | 20 | 1,553 | 46 |
| 2024-07 to 2024-12 | 6,634 | 99 | 2023-04 to 2024-03 | 37 | 3.0 | 36 | 1,786 | 43 |
| 2025-01 to 2025-06 | 8,246 | 125 | 2023-10 to 2024-09 | 60 | 1.0 | 20 | 2,356 | 35 |
| 2025-07 to 2025-12 | 10,302 | 180 | 2024-04 to 2025-03 | 81 | 1.0 | 20 | 3,039 | 129 |

## drop final full month

Test rows 10,948 over 36 origin months (2023-01 to 2025-12),
182 positive rows from 96 event lives; base rate
0.0166 (0.0087 to 0.0227). 95% intervals: b0's moving-block bootstrap of test months
(blocks of 3, 2000 replicates, seed 0: the same replicates
as b0, so the (b) row reproduces b0 exactly).

### Headline: top 5% of live contracts per month

| model | precision | recall | hits/alerts | PR-AUC |
|---|---|---|---|---|
| (b) lowest volume rank (bar) | 0.055 (0.021 to 0.082) | 0.165 (0.093 to 0.225) | 30/550 | 0.040 (0.014 to 0.060) |
| logistic, full features | 0.062 (0.017 to 0.094) | 0.187 (0.081 to 0.234) | 34/550 | 0.060 (0.020 to 0.092) |
| LightGBM, full features | 0.045 (0.015 to 0.070) | 0.137 (0.069 to 0.181) | 25/550 | 0.033 (0.012 to 0.055) |
| logistic, volume level + trend | 0.047 (0.022 to 0.067) | 0.143 (0.090 to 0.195) | 26/550 | 0.029 (0.012 to 0.046) |
| LightGBM, volume level + trend | 0.031 (0.016 to 0.047) | 0.093 (0.050 to 0.183) | 17/550 | 0.028 (0.016 to 0.042) |

Paired differences against (b), same bootstrap months:

| model | precision - (b) | recall - (b) | PR-AUC - (b) | beats (b), interval excludes 0 |
|---|---|---|---|---|
| logistic, full features | 0.007 (-0.019 to 0.022) | 0.022 (-0.080 to 0.063) | 0.020 (-0.004 to 0.045) | no |
| LightGBM, full features | -0.009 (-0.023 to 0.004) | -0.027 (-0.081 to 0.015) | -0.008 (-0.023 to 0.012) | no |
| logistic, volume level + trend | -0.007 (-0.022 to 0.008) | -0.022 (-0.062 to 0.034) | -0.012 (-0.024 to 0.006) | no |
| LightGBM, volume level + trend | -0.024 (-0.050 to 0.006) | -0.071 (-0.124 to 0.029) | -0.012 (-0.029 to 0.013) | no |

### Does anything beyond volume level and trend help?

Volume features alone (13: log_qv, qv_rank_pct, log_trades, trades_rank_pct, log_qv_median, log_avg_trade, dlog_qv_3m, dlog_qv_6m, dlog_trades_3m, dlog_trades_6m, log_qv_rel_peak, log_trades_rel_peak, dlog_qv_3m_rank), plus one group at a time. The
change columns are the point change against the same model on volume features only.

| model | precision | change vs volume only | PR-AUC | change vs volume only | PR-AUC - (b) |
|---|---|---|---|---|---|
| logistic, volume + age | 0.045 (0.021 to 0.063) | -0.002 | 0.029 (0.012 to 0.046) | +0.000 | -0.011 (-0.025 to 0.007) |
| logistic, volume + price and drawdown | 0.053 (0.024 to 0.079) | +0.005 | 0.035 (0.014 to 0.055) | +0.006 | -0.005 (-0.020 to 0.018) |
| logistic, volume + volatility | 0.045 (0.018 to 0.068) | -0.002 | 0.029 (0.012 to 0.048) | +0.001 | -0.011 (-0.023 to 0.006) |
| logistic, volume + open interest | 0.056 (0.020 to 0.082) | +0.009 | 0.043 (0.014 to 0.072) | +0.014 | 0.003 (-0.013 to 0.025) |
| logistic, volume + funding | 0.042 (0.018 to 0.063) | -0.005 | 0.032 (0.015 to 0.049) | +0.004 | -0.008 (-0.023 to 0.011) |
| logistic, volume + other activity | 0.045 (0.020 to 0.067) | -0.002 | 0.028 (0.012 to 0.046) | -0.001 | -0.012 (-0.026 to 0.006) |
| LightGBM, volume + age | 0.022 (0.007 to 0.036) | -0.009 | 0.026 (0.014 to 0.038) | -0.002 | -0.014 (-0.031 to 0.010) |
| LightGBM, volume + price and drawdown | 0.031 (0.014 to 0.048) | +0.000 | 0.027 (0.013 to 0.043) | -0.001 | -0.013 (-0.029 to 0.010) |
| LightGBM, volume + volatility | 0.027 (0.013 to 0.042) | -0.004 | 0.028 (0.015 to 0.043) | +0.000 | -0.012 (-0.030 to 0.013) |
| LightGBM, volume + open interest | 0.053 (0.020 to 0.079) | +0.022 | 0.038 (0.016 to 0.061) | +0.009 | -0.003 (-0.017 to 0.021) |
| LightGBM, volume + funding | 0.025 (0.013 to 0.039) | -0.005 | 0.029 (0.015 to 0.041) | +0.001 | -0.011 (-0.028 to 0.011) |
| LightGBM, volume + other activity | 0.025 (0.012 to 0.039) | -0.005 | 0.026 (0.014 to 0.035) | -0.003 | -0.015 (-0.032 to 0.008) |

### SHAP importance, LightGBM full model, last fold (test block 2025-07 to 2025-12)

Mean absolute TreeSHAP value (mean abs SHAP) on the test rows (log-odds), share of the total, and the
correlation between a feature's value and its SHAP value (sign = direction of the effect).

| feature | mean abs SHAP | share | corr(value, SHAP) |
|---|---|---|---|
| oi_rank_pct | 0.158 | 22% | -0.88 |
| log_oi | 0.053 | 7% | -0.70 |
| funding_abs_mean | 0.048 | 7% | +0.32 |
| funding_interval_min_h | 0.047 | 7% | -0.56 |
| ret_6m | 0.043 | 6% | -0.23 |
| ret_3m | 0.042 | 6% | +0.10 |
| log_price | 0.038 | 5% | -0.64 |
| ls_toptrader_account_month_end | 0.034 | 5% | +0.63 |
| trades_rank_pct | 0.032 | 5% | -0.50 |
| dd_life_month_end | 0.024 | 3% | -0.38 |
| dlog_qv_3m_rank | 0.021 | 3% | +0.62 |
| dlog_oi_3m | 0.019 | 3% | +0.63 |
| dlog_trades_3m | 0.016 | 2% | +0.41 |
| ls_account_month_end | 0.016 | 2% | +0.64 |
| dlog_trades_6m | 0.015 | 2% | -0.38 |
| log_trades_rel_peak | 0.014 | 2% | +0.32 |
| max_dd_life | 0.014 | 2% | -0.34 |
| ret_month | 0.012 | 2% | +0.37 |
| log_age | 0.010 | 1% | -0.45 |
| funding_mean | 0.010 | 1% | +0.07 |
| dlog_qv_3m | 0.009 | 1% | +0.37 |
| log_oi_to_qv | 0.007 | 1% | +0.38 |
| qv_rank_pct | 0.006 | 1% | -0.28 |
| ret_3m_rank | 0.005 | 1% | -0.33 |
| log_qv_rel_peak | 0.005 | 1% | -0.13 |
| taker_buy_share | 0.004 | 1% | -0.46 |
| realized_vol | 0.003 | 0% | -0.04 |
| mean_range | 0.003 | 0% | -0.20 |
| dlog_qv_6m | 0.002 | 0% | -0.02 |
| log_avg_trade | 0.002 | 0% | +0.28 |
| log_trades | 0.002 | 0% | -0.50 |
| log_qv_median | 0.001 | 0% | -0.30 |
| log_qv | 0.001 | 0% | +0.28 |
| funding_interval_shortened | 0.000 | 0% | nan |
| zero_volume_days | 0.000 | 0% | nan |

By group:

| group | mean abs SHAP summed | share |
|---|---|---|
| open interest | 0.287 | 40% |
| price and drawdown | 0.178 | 25% |
| funding | 0.105 | 15% |
| volume trend | 0.082 | 11% |
| volume level | 0.045 | 6% |
| age | 0.010 | 1% |
| volatility | 0.006 | 1% |
| other activity | 0.004 | 1% |

### Discrete-time hazard: odds ratios per 1 SD

Logistic hazard on all 14,499 pre-lock-box rows of this variant, label = the
life's last trading month is t + 2 (106 events) (t + 1 rows are the dropped final full months, so the hazard is shifted by one month). Odds ratio per 1 training SD (raw SD given), all
features in one model, missing values set to the median with an indicator; 95% intervals
from resampling contract lives (200 replicates). For rare events the odds ratio
is close to the hazard ratio. Interpretation only: this fit is not scored.

| feature | SD | odds ratio | 95% interval | excludes 1 |
|---|---|---|---|---|
| qv_rank_pct | 0.288 | 0.35 | 0.25 to 0.45 | yes |
| dlog_qv_3m | 1 | 0.94 | 0.72 to 1.18 | no |
| log_qv_rel_peak | 1.26 | 1.10 | 0.81 to 1.51 | no |
| log_age | 1.08 | 0.82 | 0.59 to 1.16 | no |
| dd_life_month_end | 0.271 | 0.89 | 0.59 to 1.28 | no |
| ret_3m | 0.654 | 1.04 | 0.83 to 1.37 | no |
| realized_vol | 0.0305 | 1.43 | 1.13 to 1.81 | yes |
| log_oi_to_qv | 0.646 | 0.83 | 0.65 to 1.03 | no |
| funding_abs_mean | 0.000229 | 1.25 | 1.06 to 1.47 | yes |

### Calibration

Calibration maps are fitted per fold on the inner validation block (the last
12 training months, scored by the model fitted on the inner-train rows) and
applied to the test scores of that inner model (the refitted model has a different score
range, so a map fitted on the inner model does not transfer to it). Brier skill =
1 - Brier / Brier of predicting the training base rate.

| scores | Brier | Brier skill (95%) |
|---|---|---|
| training base rate (reference) | 0.01638 |  |
| logit full | 0.01610 | 0.017 (-0.006 to 0.029) |
| gbm full | 0.01632 | 0.004 (-0.006 to 0.008) |
| logit full platt | 0.01634 | 0.003 (-0.008 to 0.008) |
| logit full isotonic | 0.01639 | -0.000 (-0.019 to 0.007) |
| gbm full platt | 0.01641 | -0.002 (-0.010 to 0.004) |
| gbm full isotonic | 0.01640 | -0.001 (-0.017 to 0.006) |

Reliability, best calibrated scores by Brier (logit full platt), deciles:

| predicted range | rows | positives | mean predicted | observed rate |
|---|---|---|---|---|
| 0.0003 to 0.0023 | 1095 | 27 | 0.0015 | 0.0247 |
| 0.0023 to 0.0041 | 1095 | 4 | 0.0032 | 0.0037 |
| 0.0041 to 0.0060 | 1095 | 12 | 0.0050 | 0.0110 |
| 0.0060 to 0.0078 | 1095 | 11 | 0.0069 | 0.0100 |
| 0.0078 to 0.0094 | 1095 | 6 | 0.0086 | 0.0055 |
| 0.0094 to 0.0107 | 1095 | 15 | 0.0101 | 0.0137 |
| 0.0107 to 0.0127 | 1095 | 14 | 0.0115 | 0.0128 |
| 0.0127 to 0.0178 | 1095 | 29 | 0.0149 | 0.0265 |
| 0.0178 to 0.0204 | 1094 | 22 | 0.0198 | 0.0201 |
| 0.0204 to 0.1038 | 1094 | 42 | 0.0281 | 0.0384 |

Reliability, LightGBM full model before calibration, deciles:

| predicted range | rows | positives | mean predicted | observed rate |
|---|---|---|---|---|
| 0.0034 to 0.0060 | 1095 | 8 | 0.0050 | 0.0073 |
| 0.0060 to 0.0069 | 1095 | 5 | 0.0066 | 0.0046 |
| 0.0069 to 0.0075 | 1095 | 14 | 0.0072 | 0.0128 |
| 0.0075 to 0.0078 | 1095 | 6 | 0.0077 | 0.0055 |
| 0.0078 to 0.0084 | 1095 | 14 | 0.0081 | 0.0128 |
| 0.0084 to 0.0092 | 1095 | 16 | 0.0088 | 0.0146 |
| 0.0092 to 0.0107 | 1095 | 19 | 0.0099 | 0.0174 |
| 0.0107 to 0.0129 | 1095 | 24 | 0.0117 | 0.0219 |
| 0.0129 to 0.0169 | 1094 | 29 | 0.0146 | 0.0265 |
| 0.0169 to 0.1464 | 1094 | 47 | 0.0276 | 0.0430 |

### Folds

Training rows have t + 3 < test start (b0's folds). Inner split inside the training rows:
validation = the last 12 training months; inner-train rows have t + 3 < its
first month. C chosen by inner PR-AUC from [0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0]; LightGBM trees by early stopping
on inner average precision (patience 50; 200 trees when the inner block
has no positive row).

| test block | train rows | train pos | inner validation | inner val pos | C (logistic full) | trees (LightGBM full) | test rows | test pos |
|---|---|---|---|---|---|---|---|---|
| 2023-01 to 2023-06 | 3,122 | 37 | 2021-10 to 2022-09 | 34 | 0.003 | 22 | 1,017 | 3 |
| 2023-07 to 2023-12 | 4,028 | 41 | 2022-04 to 2023-03 | 17 | 0.003 | 41 | 1,274 | 3 |
| 2024-01 to 2024-06 | 5,155 | 43 | 2022-10 to 2023-09 | 6 | 3.0 | 20 | 1,538 | 31 |
| 2024-07 to 2024-12 | 6,607 | 72 | 2023-04 to 2024-03 | 31 | 3.0 | 20 | 1,773 | 30 |
| 2025-01 to 2025-06 | 8,206 | 85 | 2023-10 to 2024-09 | 42 | 1.0 | 20 | 2,345 | 24 |
| 2025-07 to 2025-12 | 10,241 | 119 | 2024-04 to 2025-03 | 47 | 0.03 | 20 | 3,001 | 91 |

## Conclusion (plain language)

- **Nothing beats the volume-rank rule (b) with an interval that excludes zero.** Main
  run, precision at the top 5%: logistic on all features
  10.1%, LightGBM 7.8%, rule (b)
  8.3%. Paired differences against (b): logistic
  0.018 (-0.008 to 0.042), LightGBM -0.005 (-0.041 to 0.017); PR-AUC
  logistic 0.020 (-0.019 to 0.055), LightGBM -0.004 (-0.036 to 0.030).
  Verdict, main run: no model beats (b) on precision at 5% with an interval excluding zero; none on PR-AUC either. Without the final full month: no model beats (b) on precision at 5% with an interval excluding zero; none on PR-AUC either.
- The full logistic model is the best candidate: its point estimates are above (b) in both
  runs (+0.018 and
  +0.007 in precision,
  +0.020 and +0.020
  in PR-AUC), but 36 test months with clustered delistings cannot tell that from noise. It
  is the natural model to freeze for the lock-box, with (b) scored alongside it.
- LightGBM does not help. On the inner time split its validation score is best after 1 to
  36 trees in every fold, under both log loss and average precision, so the model is close
  to a few shallow trees: what it learns from earlier years does not carry forward. It
  lands at or below (b).
- Fitted models on the volume features alone do worse than the raw volume rank
  (logistic -0.022 (-0.056 to 0.003), LightGBM -0.036 (-0.080 to 0.006)
  in precision). Fitting weights to volume level and trend on earlier years adds drift, not
  signal; the rank alone is the robust part.
- **What carries the signal beyond volume:** open interest is the only group that lifts
  both models in both runs (precision at 5%
  +0.022 logistic,
  +0.036 LightGBM over
  volume only, main run), and in the LightGBM SHAP values of the last fold the groups rank
  open interest 40%, price and drawdown 18%, funding 17%, volume level 13%, volume trend 6%, volatility 3%, age 3%, other activity 1%: a low open-interest rank (little
  leverage held relative to other contracts) is the strongest single feature, followed by
  funding (short funding intervals, large absolute funding) and price (low price, falls
  over 6 months). Price and drawdown add a little to the logistic model; age, volatility,
  funding and the other-activity group add nothing measurable to the top-5% precision on
  their own. None of the single-group gains has a paired interval clear of zero against
  (b).
- The hazard view agrees: per 1 SD, a higher volume rank cuts the monthly hazard
  (odds ratio about 0.24 main, 0.35 with the one-month shift), higher realized volatility
  and higher absolute funding raise it (about 2.1 and 1.4 main, 1.4 and 1.25 shifted), and
  volume change, drawdown from the peak, age and 3-month return have intervals covering 1
  once rank is in the model. Volatility's odds ratio falls from about 2.1 to 1.4 when the
  month before the last trading month is removed, so part of it is the announcement month.
- Calibration: no class weights were used, so raw probabilities are already close to the
  base rate. The full logistic model has the best Brier skill
  (0.021 (-0.006 to 0.038)); Platt and isotonic maps fitted on the inner block do not
  improve it: they are fitted on a 12-month block whose delisting rate differs from the
  next test block (2023 had almost no delistings, 2025 many), and isotonic maps from about
  30 to 80 events are coarse. The top deciles are under-predicted: use the scores for
  ranking, not as probabilities.

## Caveats

- **No announcement dates.** Binance announces a futures delisting about 5 to 10 days
  before settlement and the announcement moves price and volume. The panel has no
  announcement date per contract, so the sensitivity run drops the whole final full month
  instead. Part of the main-run score can come from announcement crashes that a live user
  would see too late; the sensitivity run is the fairer number.
- **Correlated delisting batches.** Binance delists in batches after review rounds, so
  positives cluster in a few months and one wave decides a 6-month block (the two 2023
  blocks have 9 positive rows in all). Intervals resample blocks of 3 months, and model
  comparisons use paired differences on the same replicates; separate intervals overlap far
  more than the paired ones suggest. With so few independent batches even a real gain of
  2 points of precision would be hard to confirm.
- The base rate drifts upward (2023 0.4%, 2025 3.0%), so every probability fitted on
  earlier years under-predicts; this hurts Brier scores but not the top-5% ranking.
- Many models and ablations were compared on the same 36 test months; the largest of
  several noisy differences is biased upward, so the open-interest gain is a lead to
  confirm on the lock-box, not a finding.
- Choices made after a first run, on these folds: the LightGBM early-stopping metric was
  changed from log loss to average precision (the four headline LightGBM results moved
  by at most 0.004 in precision at 5% and 0.003 in PR-AUC), and the calibration maps were first applied to the
  refitted model instead of the inner model they were fitted on (a bug: Brier skill was far
  below zero). No feature, hyperparameter or threshold was changed after seeing test
  results, and the lock-box is untouched.
- The `final_full_month` rows are also dropped from training in the sensitivity run, so
  the two runs differ in their training data as well as their test rows (as in b0).
- Open interest and long/short ratios start around 2021-12, so early training rows rely
  on missing indicators; the first two folds train mostly on 2021 to 2022 deaths.
- `oi_rank_pct` is ranked among contracts with open-interest data only; contracts without
  it get a missing value (and a missing indicator in the logistic model).
- Trade-level features (predictability, trade size from aggTrades) are not in this panel;
  the README checkpoint on them needs the Q14 subset.
- SHAP values explain one fitted model on one fold (2025-07 to 2025-12); correlated
  features (OI rank, OI level, trade rank, volume rank) share credit arbitrarily.
- The hazard odds ratios come from one model with correlated features (volume rank,
  peak drawdown, volume change); read them as conditional on the others. The Cox model
  was not fitted (lifelines missing).
