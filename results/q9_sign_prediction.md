# Q9: next-trade-sign prediction

## Question

How much of the next trade's sign can be predicted, and how much does a learned model add over what the measured autocorrelation already implies?

## Method

1. **Data and split.** For each symbol, the 2023-06 aggressor events are split on whole UTC days: 20 train, 2 validation, 1 embargo, the rest test. Features for event i read only events before i; the first 5,120 events and every event tied in time with its predecessor are not scored.
2. **Ladder.** `majority` (training buy share), `persistence` (last sign), `linear` (Yule-Walker filter of order 1000 from the training sign autocorrelation), `logit_signs` and `gbm_signs` (logistic regression and LightGBM on sign-history features), `logit_all` and `gbm_all` (the same on sign history plus size, timing and trade-price moves).
3. **Increments.** (a) linear minus persistence: what the long memory adds; (b) gbm_signs minus linear: what nonlinearity adds on the same sign information; (c) gbm_all minus gbm_signs: what size, timing and price-move features add. Gains are signed so that positive is better: accuracy gained, or bits of log loss removed.
4. **Intervals.** 95% percentile intervals from 2000 resamples of whole UTC days, paired across rungs. The pooled interval sums each day's sums across symbols so a calendar day is one block.
5. **Lock-box.** The saved ladder is applied unchanged to every scoreable event of 2023-07.

## Run summary

Symbols with a fit cache: 10 (BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, BNBUSDT, LINKUSDT, LTCUSDT, AVAXUSDT, 1000PEPEUSDT). Without: none. Next-month caches: 10.

| symbol | events | train rows used | test rows | test days | tie share | gbm_all rounds | gamma (train days) |
|---|---|---|---|---|---|---|---|
| BTCUSDT | 21,816,890 | 2,000,000 | 5,099,820 | 7 | 0.0120 | 400 | 0.4001 |
| ETHUSDT | 14,239,099 | 2,000,000 | 3,487,710 | 7 | 0.0082 | 400 | 0.2678 |
| SOLUSDT | 6,820,337 | 2,000,000 | 1,790,548 | 7 | 0.0076 | 206 | 0.3254 |
| XRPUSDT | 7,617,768 | 2,000,000 | 979,337 | 7 | 0.0220 | 400 | 0.3349 |
| DOGEUSDT | 3,605,236 | 2,000,000 | 746,057 | 7 | 0.0079 | 366 | 0.2594 |
| BNBUSDT | 6,122,425 | 2,000,000 | 1,155,519 | 7 | 0.0067 | 143 | 0.3273 |
| LINKUSDT | 2,627,039 | 1,553,911 | 708,741 | 7 | 0.0049 | 218 | 0.4089 |
| LTCUSDT | 5,400,099 | 2,000,000 | 1,615,782 | 7 | 0.0093 | 336 | 0.4593 |
| AVAXUSDT | 2,458,978 | 1,508,038 | 637,745 | 7 | 0.0040 | 199 | 0.4129 |
| 1000PEPEUSDT | 12,675,042 | 2,000,000 | 3,434,842 | 7 | 0.0161 | 192 | 0.4932 |

## Results

### Accuracy by rung (within-month test)

| symbol | n scored | majority | persistence | linear | logit_signs | gbm_signs | logit_all | gbm_all |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 5,099,820 | 0.5046 | 0.5603 | 0.6541 | 0.6545 | 0.6611 | 0.6705 | 0.6878 |
| ETHUSDT | 3,487,710 | 0.5023 | 0.5160 | 0.6418 | 0.6422 | 0.6458 | 0.6593 | 0.6783 |
| SOLUSDT | 1,790,548 | 0.5011 | 0.5379 | 0.5621 | 0.5624 | 0.5633 | 0.5913 | 0.6062 |
| XRPUSDT | 979,337 | 0.4815 | 0.5157 | 0.5725 | 0.5764 | 0.5873 | 0.5763 | 0.5930 |
| DOGEUSDT | 746,057 | 0.5050 | 0.5329 | 0.5922 | 0.5935 | 0.5961 | 0.5976 | 0.6123 |
| BNBUSDT | 1,155,519 | 0.4934 | 0.5436 | 0.5615 | 0.5611 | 0.5635 | 0.5839 | 0.5940 |
| LINKUSDT | 708,741 | 0.4959 | 0.5265 | 0.5643 | 0.5653 | 0.5664 | 0.5733 | 0.5864 |
| LTCUSDT | 1,615,782 | 0.4978 | 0.5416 | 0.5676 | 0.5688 | 0.5701 | 0.5794 | 0.5928 |
| AVAXUSDT | 637,745 | 0.5037 | 0.6058 | 0.6021 | 0.6033 | 0.6044 | 0.6141 | 0.6243 |
| 1000PEPEUSDT | 3,434,842 | 0.4963 | 0.4694 | 0.5464 | 0.5479 | 0.5492 | 0.5808 | 0.5908 |
| **median** | | 0.4995 | 0.5354 | 0.5700 | 0.5726 | 0.5787 | 0.5876 | 0.6001 |

### Log loss in bits by rung (within-month test; 1.0 is a coin flip)

| symbol | n scored | majority | persistence | linear | logit_signs | gbm_signs | logit_all | gbm_all |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 5,099,820 | 0.9999 | 0.9904 | 0.9028 | 0.9012 | 0.8945 | 0.8811 | 0.8501 |
| ETHUSDT | 3,487,710 | 1.0000 | 0.9993 | 0.9214 | 0.9208 | 0.9149 | 0.9016 | 0.8661 |
| SOLUSDT | 1,790,548 | 1.0000 | 0.9959 | 0.9841 | 0.9835 | 0.9828 | 0.9660 | 0.9502 |
| XRPUSDT | 979,337 | 1.0002 | 1.0513 | 1.0040 | 0.9931 | 0.9756 | 0.9947 | 0.9670 |
| DOGEUSDT | 746,057 | 1.0002 | 1.0013 | 0.9678 | 0.9656 | 0.9506 | 0.9586 | 0.9271 |
| BNBUSDT | 1,155,519 | 1.0000 | 0.9988 | 0.9843 | 0.9834 | 0.9827 | 0.9699 | 0.9593 |
| LINKUSDT | 708,741 | 1.0002 | 0.9980 | 0.9811 | 0.9805 | 0.9795 | 0.9752 | 0.9652 |
| LTCUSDT | 1,615,782 | 1.0001 | 0.9965 | 0.9831 | 0.9816 | 0.9822 | 0.9710 | 0.9606 |
| AVAXUSDT | 637,745 | 1.0000 | 0.9700 | 0.9568 | 0.9557 | 0.9552 | 0.9464 | 0.9364 |
| 1000PEPEUSDT | 3,434,842 | 1.0001 | 1.0001 | 0.9919 | 0.9903 | 0.9901 | 0.9729 | 0.9626 |
| **median** | | 1.0000 | 0.9984 | 0.9821 | 0.9810 | 0.9776 | 0.9680 | 0.9547 |

### Log-loss skill relative to persistence

Fraction of the persistence rung's log loss removed; negative is worse than persistence.

| symbol | n scored | majority | persistence | linear | logit_signs | gbm_signs | logit_all | gbm_all |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 5,099,820 | -0.0096 | 0.0000 | 0.0884 | 0.0900 | 0.0968 | 0.1104 | 0.1417 |
| ETHUSDT | 3,487,710 | -0.0007 | 0.0000 | 0.0779 | 0.0786 | 0.0845 | 0.0977 | 0.1333 |
| SOLUSDT | 1,790,548 | -0.0042 | 0.0000 | 0.0118 | 0.0124 | 0.0131 | 0.0300 | 0.0459 |
| XRPUSDT | 979,337 | 0.0486 | 0.0000 | 0.0449 | 0.0553 | 0.0719 | 0.0538 | 0.0802 |
| DOGEUSDT | 746,057 | 0.0011 | 0.0000 | 0.0334 | 0.0356 | 0.0506 | 0.0426 | 0.0740 |
| BNBUSDT | 1,155,519 | -0.0013 | 0.0000 | 0.0145 | 0.0154 | 0.0161 | 0.0289 | 0.0395 |
| LINKUSDT | 708,741 | -0.0022 | 0.0000 | 0.0170 | 0.0176 | 0.0185 | 0.0229 | 0.0329 |
| LTCUSDT | 1,615,782 | -0.0036 | 0.0000 | 0.0134 | 0.0150 | 0.0144 | 0.0256 | 0.0360 |
| AVAXUSDT | 637,745 | -0.0310 | 0.0000 | 0.0136 | 0.0147 | 0.0152 | 0.0243 | 0.0346 |
| 1000PEPEUSDT | 3,434,842 | -0.0000 | 0.0000 | 0.0081 | 0.0098 | 0.0100 | 0.0272 | 0.0375 |
| **median** | | -0.0017 | 0.0000 | 0.0157 | 0.0165 | 0.0173 | 0.0294 | 0.0427 |

The persistence rung's own log loss is above the 1 bit of a coin flip for 3 of 10 symbols (XRPUSDT, DOGEUSDT, 1000PEPEUSDT). Where it is, the training repeat rate did not carry over to the test days and skill relative to persistence flatters every other rung; compare with the majority column.

### Increments in accuracy (estimate [95% CI], within-month test)

| symbol | days | (a) linear minus persistence | (b) gbm_signs minus linear | (c) gbm_all minus gbm_signs |
|---|---|---|---|---|
| BTCUSDT | 7 | +0.0938 [+0.0741, +0.1139] | +0.0070 [+0.0063, +0.0080] | +0.0267 [+0.0226, +0.0308] |
| ETHUSDT | 7 | +0.1258 [+0.1053, +0.1481] | +0.0040 [+0.0035, +0.0048] | +0.0324 [+0.0288, +0.0348] |
| SOLUSDT | 7 | +0.0242 [-0.0015, +0.0443] | +0.0012 [+0.0008, +0.0017] | +0.0429 [+0.0413, +0.0443] |
| XRPUSDT | 7 | +0.0569 [+0.0451, +0.0693] | +0.0148 [+0.0124, +0.0173] | +0.0056 [+0.0051, +0.0062] |
| DOGEUSDT | 7 | +0.0592 [+0.0456, +0.0785] | +0.0040 [+0.0031, +0.0048] | +0.0161 [+0.0131, +0.0191] |
| BNBUSDT | 7 | +0.0179 [+0.0060, +0.0281] | +0.0020 [+0.0015, +0.0026] | +0.0305 [+0.0264, +0.0337] |
| LINKUSDT | 7 | +0.0378 [+0.0245, +0.0479] | +0.0021 [+0.0013, +0.0027] | +0.0200 [+0.0167, +0.0227] |
| LTCUSDT | 7 | +0.0260 [+0.0084, +0.0636] | +0.0026 [+0.0020, +0.0041] | +0.0227 [+0.0214, +0.0260] |
| AVAXUSDT | 7 | -0.0037 [-0.0089, +0.0009] | +0.0023 [+0.0018, +0.0030] | +0.0198 [+0.0186, +0.0214] |
| 1000PEPEUSDT | 7 | +0.0770 [+0.0671, +0.0875] | +0.0028 [+0.0021, +0.0034] | +0.0416 [+0.0394, +0.0440] |
| **pooled** | 7 | +0.0718 [+0.0666, +0.0774] | +0.0045 [+0.0040, +0.0050] | +0.0298 [+0.0282, +0.0313] |
| symbols with CI off zero | | 8 above, 0 below | 10 above, 0 below | 10 above, 0 below |

### Increments in log loss removed, bits (estimate [95% CI], within-month test)

| symbol | days | (a) linear minus persistence | (b) gbm_signs minus linear | (c) gbm_all minus gbm_signs |
|---|---|---|---|---|
| BTCUSDT | 7 | +0.0876 [+0.0761, +0.0983] | +0.0083 [+0.0071, +0.0095] | +0.0444 [+0.0395, +0.0488] |
| ETHUSDT | 7 | +0.0779 [+0.0737, +0.0829] | +0.0065 [+0.0056, +0.0074] | +0.0488 [+0.0444, +0.0522] |
| SOLUSDT | 7 | +0.0117 [+0.0086, +0.0136] | +0.0013 [+0.0011, +0.0015] | +0.0326 [+0.0307, +0.0341] |
| XRPUSDT | 7 | +0.0472 [+0.0386, +0.0565] | +0.0284 [+0.0237, +0.0330] | +0.0086 [+0.0065, +0.0106] |
| DOGEUSDT | 7 | +0.0335 [+0.0192, +0.0527] | +0.0172 [+0.0117, +0.0242] | +0.0235 [+0.0132, +0.0384] |
| BNBUSDT | 7 | +0.0145 [+0.0124, +0.0167] | +0.0016 [+0.0012, +0.0021] | +0.0234 [+0.0199, +0.0261] |
| LINKUSDT | 7 | +0.0169 [+0.0136, +0.0202] | +0.0016 [+0.0014, +0.0018] | +0.0144 [+0.0126, +0.0158] |
| LTCUSDT | 7 | +0.0134 [+0.0101, +0.0221] | +0.0009 [-0.0036, +0.0101] | +0.0215 [+0.0121, +0.0261] |
| AVAXUSDT | 7 | +0.0132 [+0.0113, +0.0154] | +0.0016 [+0.0014, +0.0019] | +0.0188 [+0.0170, +0.0207] |
| 1000PEPEUSDT | 7 | +0.0081 [+0.0065, +0.0096] | +0.0019 [+0.0016, +0.0021] | +0.0275 [+0.0267, +0.0284] |
| **pooled** | 7 | +0.0456 [+0.0395, +0.0521] | +0.0061 [+0.0052, +0.0070] | +0.0335 [+0.0315, +0.0353] |
| symbols with CI off zero | | 10 above, 0 below | 9 above, 0 below | 10 above, 0 below |

### Within-month versus next month (2023-07)

| symbol | linear acc (within) | linear acc (next) | gbm_all acc (within) | gbm_all acc (next) | linear loss (within) | linear loss (next) | gbm_all loss (within) | gbm_all loss (next) |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 0.6541 | 0.6492 | 0.6878 | 0.6829 | 0.9028 | 0.9105 | 0.8501 | 0.8588 |
| ETHUSDT | 0.6418 | 0.6616 | 0.6783 | 0.6893 | 0.9214 | 0.8962 | 0.8661 | 0.8531 |
| SOLUSDT | 0.5621 | 0.5679 | 0.6062 | 0.6069 | 0.9841 | 0.9807 | 0.9502 | 0.9477 |
| XRPUSDT | 0.5725 | 0.6460 | 0.5930 | 0.6532 | 1.0040 | 0.9302 | 0.9670 | 0.9055 |
| DOGEUSDT | 0.5922 | 0.5879 | 0.6123 | 0.6062 | 0.9678 | 0.9735 | 0.9271 | 0.9466 |
| BNBUSDT | 0.5615 | 0.5778 | 0.5940 | 0.5984 | 0.9843 | 0.9716 | 0.9593 | 0.9551 |
| LINKUSDT | 0.5643 | 0.5624 | 0.5864 | 0.5905 | 0.9811 | 0.9812 | 0.9652 | 0.9613 |
| LTCUSDT | 0.5676 | 0.5557 | 0.5928 | 0.5785 | 0.9831 | 0.9899 | 0.9606 | 0.9703 |
| AVAXUSDT | 0.6021 | 0.5849 | 0.6243 | 0.6061 | 0.9568 | 0.9690 | 0.9364 | 0.9503 |
| 1000PEPEUSDT | 0.5464 | 0.5528 | 0.5908 | 0.5924 | 0.9919 | 0.9888 | 0.9626 | 0.9611 |

Increments on the next month, accuracy:

| symbol | days | (a) linear minus persistence | (b) gbm_signs minus linear | (c) gbm_all minus gbm_signs |
|---|---|---|---|---|
| BTCUSDT | 31 | +0.1011 [+0.0899, +0.1136] | +0.0097 [+0.0088, +0.0107] | +0.0240 [+0.0214, +0.0264] |
| ETHUSDT | 31 | +0.1128 [+0.1035, +0.1232] | +0.0053 [+0.0049, +0.0057] | +0.0224 [+0.0200, +0.0248] |
| SOLUSDT | 31 | +0.0315 [+0.0248, +0.0378] | +0.0007 [+0.0004, +0.0010] | +0.0384 [+0.0367, +0.0402] |
| XRPUSDT | 31 | +0.0119 [+0.0073, +0.0204] | +0.0029 [+0.0015, +0.0054] | +0.0042 [+0.0037, +0.0051] |
| DOGEUSDT | 31 | +0.0386 [+0.0231, +0.0582] | +0.0051 [+0.0034, +0.0068] | +0.0131 [+0.0118, +0.0148] |
| BNBUSDT | 31 | +0.0475 [+0.0406, +0.0547] | +0.0011 [+0.0006, +0.0016] | +0.0195 [+0.0164, +0.0225] |
| LINKUSDT | 31 | +0.0955 [+0.0622, +0.1271] | +0.0089 [+0.0038, +0.0143] | +0.0191 [+0.0140, +0.0238] |
| LTCUSDT | 31 | +0.0401 [+0.0316, +0.0526] | +0.0021 [+0.0014, +0.0029] | +0.0207 [+0.0189, +0.0222] |
| AVAXUSDT | 31 | +0.0084 [+0.0022, +0.0146] | +0.0013 [+0.0009, +0.0017] | +0.0200 [+0.0186, +0.0211] |
| 1000PEPEUSDT | 31 | +0.1033 [+0.0960, +0.1103] | +0.0039 [+0.0033, +0.0044] | +0.0357 [+0.0332, +0.0380] |
| **pooled** | 31 | +0.0656 [+0.0612, +0.0702] | +0.0047 [+0.0041, +0.0054] | +0.0222 [+0.0206, +0.0237] |
| symbols with CI off zero | | 10 above, 0 below | 10 above, 0 below | 10 above, 0 below |

Increments on the next month, log loss removed (bits):

| symbol | days | (a) linear minus persistence | (b) gbm_signs minus linear | (c) gbm_all minus gbm_signs |
|---|---|---|---|---|
| BTCUSDT | 31 | +0.0855 [+0.0818, +0.0898] | +0.0131 [+0.0119, +0.0144] | +0.0385 [+0.0341, +0.0427] |
| ETHUSDT | 31 | +0.0997 [+0.0923, +0.1078] | +0.0076 [+0.0068, +0.0083] | +0.0355 [+0.0326, +0.0384] |
| SOLUSDT | 31 | +0.0155 [+0.0147, +0.0163] | +0.0010 [+0.0009, +0.0012] | +0.0320 [+0.0303, +0.0337] |
| XRPUSDT | 31 | +0.0178 [+0.0149, +0.0230] | +0.0112 [+0.0082, +0.0145] | +0.0135 [+0.0111, +0.0151] |
| DOGEUSDT | 31 | +0.0209 [+0.0172, +0.0258] | +0.0101 [+0.0080, +0.0128] | +0.0168 [+0.0132, +0.0199] |
| BNBUSDT | 31 | +0.0276 [+0.0234, +0.0328] | +0.0007 [+0.0004, +0.0009] | +0.0158 [+0.0138, +0.0176] |
| LINKUSDT | 31 | +0.0275 [+0.0226, +0.0318] | +0.0044 [+0.0024, +0.0064] | +0.0155 [+0.0119, +0.0194] |
| LTCUSDT | 31 | +0.0162 [+0.0133, +0.0202] | +0.0044 [+0.0028, +0.0063] | +0.0152 [+0.0133, +0.0168] |
| AVAXUSDT | 31 | +0.0141 [+0.0122, +0.0161] | +0.0014 [+0.0012, +0.0015] | +0.0173 [+0.0165, +0.0181] |
| 1000PEPEUSDT | 31 | +0.0113 [+0.0101, +0.0126] | +0.0022 [+0.0019, +0.0025] | +0.0255 [+0.0242, +0.0268] |
| **pooled** | 31 | +0.0435 [+0.0402, +0.0469] | +0.0071 [+0.0065, +0.0077] | +0.0259 [+0.0241, +0.0275] |
| symbols with CI off zero | | 10 above, 0 below | 10 above, 0 below | 10 above, 0 below |

### Feature importance

Mean across symbols of each feature's share of total split gain in `gbm_all`, and the mean standardized coefficient in `logit_all`.

| feature | mean gain share | mean logit coef | mean abs logit coef |
|---|---|---|---|
| sign_ewma4 | 0.1286 | +0.1562 | 0.1562 |
| sign_lag2 | 0.1262 | +0.0797 | 0.1357 |
| signed_rel_log_qty | 0.1194 | +0.1839 | 0.1839 |
| sign_ewma16 | 0.1174 | +0.1636 | 0.1636 |
| sign_lag1 | 0.0753 | -0.4888 | 0.4888 |
| sign_ewma64 | 0.0563 | +0.0588 | 0.0588 |
| rel_log_dt | 0.0463 | +0.0059 | 0.0075 |
| rel_log_qty | 0.0411 | -0.0030 | 0.0090 |
| ret16 | 0.0410 | -0.0663 | 0.0663 |
| log_n_prints | 0.0408 | -0.0092 | 0.0107 |
| tick_dir | 0.0380 | +0.0357 | 0.1674 |
| run_length | 0.0361 | +0.2647 | 0.2647 |
| burst | 0.0340 | +0.0163 | 0.0163 |
| ret64 | 0.0230 | -0.0356 | 0.0429 |
| sign_ewma256 | 0.0205 | +0.0434 | 0.0434 |
| sign_ewma1024 | 0.0195 | +0.0283 | 0.0283 |
| signed_tick_dir | 0.0180 | +0.0015 | 0.0030 |
| sign_lag3 | 0.0063 | -0.0199 | 0.0358 |
| sign_lag4 | 0.0056 | +0.0163 | 0.0169 |
| same_ts | 0.0040 | +0.0279 | 0.0311 |
| sign_lag5 | 0.0024 | -0.0120 | 0.0128 |

### Memory strength and the linear rung

Across 10 symbols, the correlation between the training-day sign-ACF exponent gamma (lags 10 to 500, Q4's window) and the linear rung's test accuracy is -0.33 (Pearson) and -0.28 (Spearman); with the gain of linear over persistence it is -0.24 and -0.19. A smaller gamma means slower decay, so a negative correlation means stronger memory goes with a better linear forecast. With 10 points this is descriptive only.

### Trial log

1 distinct configuration(s) were run, each fitting 5 models per symbol (linear, logit_signs, gbm_signs, logit_all, gbm_all), 50 model fits in total. No hyperparameter grid was searched; the only quantity tuned on validation data is the LightGBM boosting round count (early stopping). Fixed LightGBM parameters: `objective=binary`, `learning_rate=0.1`, `num_leaves=63`, `min_data_in_leaf=500`, `feature_fraction=0.8`, `bagging_fraction=0.8`, `bagging_freq=1`, `lambda_l2=1.0`, `max_bin=63`, `verbose=-1`, `num_threads=4`, `seed=0`. Logistic regression: L2, C = 1.0, standardized inputs. The full configuration is in the JSON under `trial_log`.

## Verdict

Across 10 symbols (2023-06, within-month test days), median accuracy is 0.4995 for the majority rule, 0.5354 for persistence, 0.5700 for the linear filter implied by the autocorrelation and 0.6001 for boosted trees on all features. The median lift over the majority rule is +0.0784 for the linear rung and +0.1062 for gbm_all, so the learned model adds a median +0.0289 in accuracy over what the measured autocorrelation already implies (74% of the gbm_all lift is already in the linear rung). In log loss, the median skill relative to persistence is 0.0157 for linear and 0.0427 for gbm_all. (a) What the long memory adds (linear minus persistence): pooled accuracy gain +0.0718 [+0.0666, +0.0774], the interval excludes zero on the positive side; per symbol the interval lies above zero for 8 of 10 and below zero for 0, with a median gain of +0.0473. Pooled log loss removed +0.0456 [+0.0395, +0.0521] bits, the interval excludes zero on the positive side; above zero for 10 of 10 symbols, below zero for 0, median +0.0157 bits. (b) What nonlinearity adds on the same sign information (gbm_signs minus linear): pooled accuracy gain +0.0045 [+0.0040, +0.0050], the interval excludes zero on the positive side; per symbol the interval lies above zero for 10 of 10 and below zero for 0, with a median gain of +0.0027. Pooled log loss removed +0.0061 [+0.0052, +0.0070] bits, the interval excludes zero on the positive side; above zero for 9 of 10 symbols, below zero for 0, median +0.0017 bits. (c) What size, timing and price-move features add (gbm_all minus gbm_signs): pooled accuracy gain +0.0298 [+0.0282, +0.0313], the interval excludes zero on the positive side; per symbol the interval lies above zero for 10 of 10 and below zero for 0, with a median gain of +0.0247. Pooled log loss removed +0.0335 [+0.0315, +0.0353] bits, the interval excludes zero on the positive side; above zero for 10 of 10 symbols, below zero for 0, median +0.0234 bits. Out of month (2023-07, the frozen 2023-06 ladder, 10 symbols, 31 day blocks), median accuracy is linear 0.5700 within the month and 0.5813 in the next (+0.0113); gbm_all 0.6001 within the month and 0.6062 in the next (+0.0060). There the pooled gain of gbm_all over the linear rung is +0.0269 in accuracy and +0.0330 bits of log loss, and 2 of the 2 learned increments (b, c) have a pooled accuracy interval above zero. None of this is a trading result. The best accuracy in any cell is 0.6893, which still leaves 0.3107 of next signs called wrong, and what was scored is 99,085,438 sign calls, not returns: the 21 inputs are built from trade signs, sizes, times and trade-price moves, and the analysis measures no quotes, no spreads, no fees and no profit and loss. The repo's Q2 and Q5 show that price impact adjusts to the memory of order flow so that predictable signs do not make prices predictable, so a predictable sign is not a predictable return.

## Caveats

- **One training month per symbol.** Each ladder is fitted on the first 20 days of 2023-06 only. The within-month test block has 7 days, so each per-symbol interval rests on that many day blocks and is coarse; a percentile bootstrap over so few blocks tends to be too narrow. The next-month block has more days and is the stronger test.
- **Survivor symbols.** The symbols are liquid contracts chosen because they exist in all five downloaded months. Contracts that were delisted or listed later are absent, so nothing here speaks for thin or short-lived markets.
- **Hyperparameters fixed in advance.** The LightGBM settings, the feature list and the linear order (1000) are the fixed values in `microstructure.ml` and were not varied in this analysis. Only the boosting round count is tuned, by early stopping on the 2 validation days (patience 30, at most 400 rounds). The trial log lists every configuration run. A pilot on SOLUSDT 2023-06 was run while the ladder was being built, so that symbol's within-month test block is not untouched.
- **Training subsample cap.** The learned rungs train on a random subsample of at most 2,000,000 scoreable training rows (validation at most 500,000); the cap was binding for 8 of 10 symbols. The linear rung uses every training-day sign, which favors it slightly.
- **Tie exclusion.** An event that shares a millisecond with the previous event is never scored, because the order inside a tied millisecond is fixed by the sort (sells first), not by the market. Tied events are 0.4 to 2.2% of events here. They still feed the features of later rows, and the scores describe untied events only.
- **Millisecond timestamps.** Timestamps are in milliseconds, so the true order of events inside one millisecond is unknown, and prints with the same millisecond and side are merged into one event. "The next trade" means the next such event.
- **Pooled intervals are event-weighted.** The pooled estimate sums each day's sums across symbols, so the busiest symbols dominate it; the per-symbol median is given alongside for that reason.
- **Trades only.** No quote data enters the features (quotes exist for 2023 only), so a model with the order book could do better or worse than these numbers.
