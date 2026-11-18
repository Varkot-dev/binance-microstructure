# B0: baselines for delisting prediction

Built by `research/market_evolution/b0_baselines.py eval` from `delisting_panel.parquet`
(see `delisting_panel.md` for the label, censoring and exclusion rules). Run time
39 s.

## Dataset

- 18,329 rows (life x month), 686 lives,
  465 positive rows from
  161 event lives; base rate
  0.0254.
- Pre-lock-box rows (t <= 2025-12): 14,599, positive rows
  320.
- **Lock-box: origins 2026-01 to 2026-07 (3,730 rows) are
  reserved and NOT scored.** Note: origins 2025-10 to 2025-12 have label windows that reach
  2026-01 to 2026-03, so deaths in early 2026 already appear as positives in the last
  pre-lock-box test block.

Base rate by year of t (pre-lock-box):

| year | rows | positive rows | event lives | base rate |
|---|---|---|---|---|
| 2020 | 502 | 3 | 1 | 0.0060 |
| 2021 | 1,380 | 11 | 5 | 0.0080 |
| 2022 | 1,689 | 44 | 17 | 0.0261 |
| 2023 | 2,294 | 9 | 4 | 0.0039 |
| 2024 | 3,339 | 89 | 32 | 0.0267 |
| 2025 | 5,395 | 164 | 65 | 0.0304 |

## Validation

Expanding window, monthly origins, 6-month test blocks starting 2023-01 (6 folds, the
last ending 2025-12). Purge: a training row must have t + 3 < T, the first test month, so
no training label window (t+1..t+3) reaches into the test block. This is one month
stricter than the note's `train_end = T - horizon`, whose last training row has a window
ending in month T. Thresholds, scalers and coefficients come from training rows only.
Censored rows were dropped when the panel was built, so the test set leaves out the last
2 months of lives that are later renamed or merged.

## main

Test rows 11,028 over 36 origin months (2023-01 to 2025-12),
262 positive rows from 96 event lives; 32
of the 36 months have at least one positive row. Base rate
0.0238 (0.0129 to 0.0322).
Intervals: 95% percentile intervals from a moving-block bootstrap of test months (blocks
of 3 consecutive months, 2000 replicates).

Top 5% alert rate per month (n alerts = max(1, round(0.05 x live contracts))):

| baseline | precision | recall | hits/alerts | PR-AUC |
|---|---|---|---|---|
| (a) falling volume: score = -dlog_qv_3m | 0.027 (0.008 to 0.052) | 0.057 (0.026 to 0.112) | 15/552 | 0.028 (0.014 to 0.043) |
| (b) lowest volume rank: score = -qv_rank_pct | 0.083 (0.031 to 0.133) | 0.176 (0.094 to 0.258) | 46/552 | 0.056 (0.023 to 0.086) |
| (c) logistic: dlog_qv_3m, qv_rank_pct, log_age | 0.053 (0.021 to 0.075) | 0.111 (0.061 to 0.144) | 29/552 | 0.045 (0.019 to 0.064) |

Paired differences (same bootstrap months): precision (c) - (a)
0.025 (-0.014 to 0.047); (b) - (a) 0.056 (0.002 to 0.103); PR-AUC (c) - (a)
0.017 (0.002 to 0.028).

Rule (a) as a fixed threshold (flag dlog_qv_3m < thr, thr = training quantile with the
best training F1, chosen per fold on training rows only): precision
0.025 (0.010 to 0.039), recall 0.229 (0.117 to 0.328), alert rate
0.217 (0.136 to 0.320).

Calibration of (c): Brier 0.02308 against 0.02325 for predicting
the training base rate; Brier skill 0.007 (-0.000 to 0.011).

Reliability of (c), deciles of the predicted probability (pooled test rows):

| predicted range | rows | positives | mean predicted | observed rate |
|---|---|---|---|---|
| 0.0018 to 0.0044 | 1103 | 5 | 0.0036 | 0.0045 |
| 0.0044 to 0.0058 | 1103 | 12 | 0.0051 | 0.0109 |
| 0.0058 to 0.0074 | 1103 | 11 | 0.0066 | 0.0100 |
| 0.0074 to 0.0094 | 1103 | 13 | 0.0084 | 0.0118 |
| 0.0094 to 0.0117 | 1103 | 30 | 0.0105 | 0.0272 |
| 0.0117 to 0.0146 | 1103 | 18 | 0.0132 | 0.0163 |
| 0.0146 to 0.0184 | 1103 | 32 | 0.0164 | 0.0290 |
| 0.0184 to 0.0236 | 1103 | 45 | 0.0208 | 0.0408 |
| 0.0236 to 0.0311 | 1102 | 35 | 0.0270 | 0.0318 |
| 0.0311 to 0.0570 | 1102 | 61 | 0.0382 | 0.0554 |

Folds (training rows have t + 3 < test start; rows purged per fold:
433, 541, 688, 784, 958, 1258):

| test block | last train month | train rows | train positives | test rows | test positives | thr (a) | coef (c) per raw unit |
|---|---|---|---|---|---|---|---|
| 2023-01 to 2023-06 | 2022-09 | 3,138 | 53 | 1,019 | 5 | -0.07 | -0.07, -2.08, +0.00 |
| 2023-07 to 2023-12 | 2023-03 | 4,049 | 62 | 1,275 | 4 | -1.27 | -0.20, -1.92, -0.15 |
| 2024-01 to 2024-06 | 2023-09 | 5,177 | 65 | 1,553 | 46 | -1.38 | -0.16, -1.54, -0.22 |
| 2024-07 to 2024-12 | 2024-03 | 6,634 | 99 | 1,786 | 43 | -0.07 | +0.04, -2.59, -0.10 |
| 2025-01 to 2025-06 | 2024-09 | 8,246 | 125 | 2,356 | 35 | -1.27 | +0.15, -2.72, -0.07 |
| 2025-07 to 2025-12 | 2025-03 | 10,302 | 180 | 3,039 | 129 | -1.26 | +0.17, -2.95, +0.07 |

## drop final full month

Test rows 10,948 over 36 origin months (2023-01 to 2025-12),
182 positive rows from 96 event lives; 29
of the 36 months have at least one positive row. Base rate
0.0166 (0.0087 to 0.0227).
Intervals: 95% percentile intervals from a moving-block bootstrap of test months (blocks
of 3 consecutive months, 2000 replicates).

Top 5% alert rate per month (n alerts = max(1, round(0.05 x live contracts))):

| baseline | precision | recall | hits/alerts | PR-AUC |
|---|---|---|---|---|
| (a) falling volume: score = -dlog_qv_3m | 0.016 (0.003 to 0.032) | 0.049 (0.011 to 0.090) | 9/550 | 0.019 (0.009 to 0.031) |
| (b) lowest volume rank: score = -qv_rank_pct | 0.055 (0.021 to 0.082) | 0.165 (0.093 to 0.225) | 30/550 | 0.040 (0.014 to 0.060) |
| (c) logistic: dlog_qv_3m, qv_rank_pct, log_age | 0.029 (0.008 to 0.044) | 0.088 (0.036 to 0.126) | 16/550 | 0.028 (0.013 to 0.040) |

Paired differences (same bootstrap months): precision (c) - (a)
0.013 (-0.008 to 0.024); (b) - (a) 0.038 (0.008 to 0.060); PR-AUC (c) - (a)
0.009 (0.001 to 0.015).

Rule (a) as a fixed threshold (flag dlog_qv_3m < thr, thr = training quantile with the
best training F1, chosen per fold on training rows only): precision
0.013 (0.004 to 0.021), recall 0.170 (0.070 to 0.303), alert rate
0.227 (0.143 to 0.347).

Calibration of (c): Brier 0.01632 against 0.01638 for predicting
the training base rate; Brier skill 0.004 (-0.001 to 0.006).

Reliability of (c), deciles of the predicted probability (pooled test rows):

| predicted range | rows | positives | mean predicted | observed rate |
|---|---|---|---|---|
| 0.0013 to 0.0030 | 1095 | 2 | 0.0025 | 0.0018 |
| 0.0030 to 0.0040 | 1095 | 11 | 0.0035 | 0.0100 |
| 0.0040 to 0.0051 | 1095 | 7 | 0.0045 | 0.0064 |
| 0.0051 to 0.0063 | 1095 | 10 | 0.0057 | 0.0091 |
| 0.0063 to 0.0079 | 1095 | 17 | 0.0071 | 0.0155 |
| 0.0079 to 0.0098 | 1095 | 19 | 0.0088 | 0.0174 |
| 0.0098 to 0.0121 | 1095 | 26 | 0.0109 | 0.0237 |
| 0.0121 to 0.0156 | 1095 | 29 | 0.0137 | 0.0265 |
| 0.0156 to 0.0208 | 1094 | 23 | 0.0179 | 0.0210 |
| 0.0208 to 0.0411 | 1094 | 38 | 0.0258 | 0.0347 |

Folds (training rows have t + 3 < test start; rows purged per fold:
429, 540, 687, 773, 947, 1257):

| test block | last train month | train rows | train positives | test rows | test positives | thr (a) | coef (c) per raw unit |
|---|---|---|---|---|---|---|---|
| 2023-01 to 2023-06 | 2022-09 | 3,122 | 37 | 1,017 | 3 | -0.26 | -0.04, -2.37, +0.06 |
| 2023-07 to 2023-12 | 2023-03 | 4,028 | 41 | 1,274 | 3 | -0.25 | -0.17, -1.89, -0.19 |
| 2024-01 to 2024-06 | 2023-09 | 5,155 | 43 | 1,538 | 31 | -1.38 | -0.14, -1.52, -0.23 |
| 2024-07 to 2024-12 | 2024-03 | 6,607 | 72 | 1,773 | 30 | -0.07 | +0.13, -2.80, -0.10 |
| 2025-01 to 2025-06 | 2024-09 | 8,206 | 85 | 2,345 | 24 | -1.41 | +0.23, -2.52, -0.08 |
| 2025-07 to 2025-12 | 2025-03 | 10,241 | 119 | 3,001 | 91 | -1.57 | +0.25, -2.84, +0.04 |

## What a model must beat (plain language)

- The base rate is about 2.4% per contract-month on the scored origins: a random
  5% alert list would be right about 2.4% of the time.
- Ranking by the lowest volume rank alone (b) gives precision 8.3% and catches
  18% of the contract-months that die within 3 months; the falling-volume
  rule (a) gives 2.7% and 6%; the 3-feature logistic (c) gives
  5.3% and 11%. The best of these, at the top-5% alert rate and
  in PR-AUC, is the bar for LightGBM and for any trade-level feature.
- Without the final full month before the last trading month (the month most likely to
  contain the announcement), precision moves to 1.6% (a), 5.5%
  (b), 2.9% (c). The drop shows how much of the score could come from
  post-announcement trading, which a live model would not have in time to act on.
- Small coins die: the level of volume (rank) matters at least as much as its recent fall.
  A model that adds only volume transforms is unlikely to clear the bar by much.
- Intervals are wide because events come in batches: one delisting wave decides a 6-month
  block. Differences between methods should be judged with the paired intervals, not by
  comparing two separate intervals.
