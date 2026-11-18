# Q14: survivorship in next-trade-sign prediction

## Question

Is next-trade-sign predictability different for contracts that were later delisted, and for contracts listed after 2023, once trading activity is controlled for? How unrepresentative are Q9's 10 symbols?

## Universe

From the archive inventory (USDT-M monthly aggTrades, months up to 2026-10), 923 perpetuals (tickers ending in USDT without an underscore). 188 have a 2023-06 file; 541 first appear after 2023-06 and are alive in 2026-07.

| status in 2023-06 universe | contracts |
|---|---|
| survivor (all five study months) | 135 |
| survivor with a gap (alive in 2026-07, misses a middle study month) | 3 |
| relisted (no 2026-07 file, a later one) | 1 |
| renamed or migrated | 10 |
| merged into another token | 2 |
| delisted | 34 |
| index contract (not a coin, not fitted) | 3 |

Survivors with a gap: CTKUSDT (missing 2024-07); CVXUSDT (missing 2024-07); LITUSDT (missing 2025-07).

Relisted: MDTUSDT (last file 2024-05, back in 2026-10). The brief listed MDTUSDT as alive in 2026-07 with a gap; the inventory has no 2026-07 file for it, so it is treated as a contract that stopped and came back and is left out of both comparison groups.

Renamed or migrated (successor verified in the inventory):

| contract | last file | successor | successor first file | lag (months) |
|---|---|---|---|---|
| BNXUSDT | 2025-03 | FORMUSDT | 2025-03 | 0 |
| DARUSDT | 2024-12 | DUSDT | 2025-01 | 1 |
| EOSUSDT | 2025-05 | AUSDT | 2025-05 | 0 |
| FTMUSDT | 2025-01 | SUSDT | 2025-01 | 0 |
| FXSUSDT | 2026-01 | FRAXUSDT | 2026-01 | 0 |
| GALUSDT | 2024-07 | GUSDT | 2024-08 | 1 |
| KLAYUSDT | 2024-10 | KAIAUSDT | 2024-12 | 2 |
| MATICUSDT | 2024-09 | POLUSDT | 2024-09 | 0 |
| MKRUSDT | 2025-09 | SKYUSDT | 2025-09 | 0 |
| RNDRUSDT | 2024-07 | RENDERUSDT | 2024-07 | 0 |

Merged: AGIXUSDT into FETUSDT (last file 2024-06); OCEANUSDT into FETUSDT (last file 2024-06).

Index contracts (listed, not fitted): BLUEBIRDUSDT (last file 2024-03), DEFIUSDT (last file 2025-08), FOOTBALLUSDT (last file 2024-03).

Delisted (last archive file): ALPHAUSDT (2025-09), AMBUSDT (2025-02), ANTUSDT (2024-04), ATAUSDT (2026-05), AUDIOUSDT (2024-05), BAKEUSDT (2025-10), BALUSDT (2025-04), BLZUSDT (2024-12), COMBOUSDT (2025-03), DENTUSDT (2026-04), DGBUSDT (2024-04), FLMUSDT (2025-11), HIGHUSDT (2026-06), HOOKUSDT (2026-03), IDEXUSDT (2024-05), KEYUSDT (2024-12), LEVERUSDT (2025-09), LINAUSDT (2025-03), LRCUSDT (2026-03), NKNUSDT (2026-02), OMGUSDT (2025-01), PERPUSDT (2025-11), PHBUSDT (2026-05), RADUSDT (2024-05), RDNTUSDT (2026-03), REEFUSDT (2025-01), RENUSDT (2024-12), STMXUSDT (2025-02), SXPUSDT (2025-12), TOMOUSDT (2023-11), TRUUSDT (2026-04), UNFIUSDT (2024-10), WAVESUSDT (2024-06), XEMUSDT (2024-12).

New-listing sample: the frame is the 499 new listings with a complete 2026-07 (18.7 GB of zips); 42 first listed in 2026-07 are outside it. 15 were drawn from each decile of 2026-07 zip size with seed 0 (150 in all; the list is in the JSON under `universe.new_listings.sample`). Decile edges in MB: 0.6, 3.8, 5.2, 7.0, 9.4, 12.7, 16.5, 23.7, 35.8, 71.9, 1170.0.

## Method

1. **Units.** A unit is one symbol-month. Q9's within-month ladder (fit stage only) is fitted on each with Q9's defaults: 20 train days, 2 validation, 1 embargo, the rest test; train cap 2,000,000 rows; linear order 1000; LightGBM settings as in Q9. Three sets: every 2023-06 coin; the last complete month of every contract that stopped trading; and 2026-07 for the 2023 contracts alive then plus the new-listing sample.
2. **Complete month.** A month is complete when the contract traded on its first and last UTC day and on all days in between but at most 1. A 2023-06 or 2026-07 unit that is not complete is skipped and listed.
3. **Last complete month.** Starting from the contract's last archive month, walk back until a complete month is found, trying at most 3 months. A delisting usually happens mid-month, so the last archive file is typically partial; the zip size of each candidate is reported next to its coverage, but the decision uses the trading days in the data, not the size.
4. **Minimum activity.** A complete unit is fitted only with at least 50,000 scoreable train rows (LightGBM with 63 leaves of at least 500 rows needs about 31,500 to grow a full tree), 5,000 validation rows and 10,000 test rows (a binomial standard error of at most 0.005 on one unit's accuracy). Units below that are skipped and listed.
5. **Comparisons.** Symbols are the resampling unit. Raw differences are differences of group medians with a 2000-resample bootstrap of symbols within each group. The activity-controlled difference is the dummy coefficient in an OLS of the metric on log10 events and a group dummy, with an HC1 interval. The matched difference pairs each group contract with the control contract with the nearest log10 events, with replacement, and averages the differences; its interval resamples both groups and rematches each time. The paired last-month change uses the same contracts' 2023-06 fits, with the intercept of the change on the change in log10 events as the change at equal activity.

## Run summary

| set | status | outcomes |
|---|---|---|
| cross_2023 | survivor | ok 133, partial 2 |
| cross_2023 | merged | ok 2 |
| cross_2023 | delisted | ok 33, partial 1 |
| cross_2023 | renamed | ok 10 |
| cross_2023 | survivor_gap | ok 3 |
| cross_2023 | relisted | partial 1 |
| last_month | merged | ok 2 |
| last_month | delisted | ok 34 |
| last_month | renamed | ok 10 |
| cross_2026 | survivor | ok 135 |
| cross_2026 | survivor_gap | ok 3 |
| cross_2026 | new_listing_equity | ok 27, skipped 10 |
| cross_2026 | new_listing | ok 113 |

Q9's own fit caches reused: 10.

## Results

### 2023-06 cross-section

| group | n | median events | majority | persistence | linear | gbm_all | lift over majority | share of lift in linear | gbm_all minus linear |
|---|---|---|---|---|---|---|---|---|---|
| survivors | 136 | 1,277,820 | 0.5071 | 0.5745 | 0.5939 | 0.6123 | +0.1037 | 0.82 | +0.0191 |
| delisted | 33 | 1,177,447 | 0.5095 | 0.5945 | 0.6026 | 0.6248 | +0.1102 | 0.85 | +0.0170 |
| renamed_merged | 12 | 1,651,426 | 0.5082 | 0.5793 | 0.5908 | 0.6151 | +0.1064 | 0.84 | +0.0166 |
| ended | 45 | 1,436,761 | 0.5088 | 0.5945 | 0.6003 | 0.6191 | +0.1102 | 0.85 | +0.0170 |
| full universe (all fitted coins) | 181 | 1,311,302 | 0.5075 | 0.5781 | 0.5968 | 0.6146 | +0.1049 | 0.82 | +0.0187 |
| Q9's 10 symbols | 10 | 6,471,381 | 0.4995 | 0.5354 | 0.5700 | 0.6001 | +0.1062 | 0.77 | +0.0289 |

### Last complete month of ended contracts

| group | n | median events | majority | persistence | linear | gbm_all | lift over majority | share of lift in linear | gbm_all minus linear |
|---|---|---|---|---|---|---|---|---|---|
| delisted | 34 | 886,508 | 0.5024 | 0.5920 | 0.6126 | 0.6225 | +0.1282 | 0.95 | +0.0075 |
| renamed_merged | 12 | 2,558,976 | 0.5034 | 0.6211 | 0.6406 | 0.6469 | +0.1384 | 0.95 | +0.0073 |
| ended | 46 | 982,023 | 0.5024 | 0.5951 | 0.6171 | 0.6318 | +0.1294 | 0.95 | +0.0075 |

### 2026-07 cross-section

| group | n | median events | majority | persistence | linear | gbm_all | lift over majority | share of lift in linear | gbm_all minus linear |
|---|---|---|---|---|---|---|---|---|---|
| survivors_2023 | 138 | 653,342 | 0.5001 | 0.6076 | 0.6310 | 0.6406 | +0.1357 | 0.95 | +0.0075 |
| new_listings | 113 | 678,804 | 0.5045 | 0.6144 | 0.6239 | 0.6309 | +0.1252 | 0.92 | +0.0101 |
| new_listings_equity | 27 | 1,090,575 | 0.5052 | 0.6570 | 0.6589 | 0.6704 | +0.1641 | 0.94 | +0.0094 |

### Equity-perpetual screen (2026-07)

Binance listed perpetuals on stock tokens in 2026, some on reused crypto tickers. A unit is flagged as equity-like when its median UTC weekend day has fewer than 0.25 times the events of its median weekday, or when on the median weekday at least 0.60 of the day's events fall in the US cash session (13:30 to 20:00 UTC; a flat round-the-clock day puts 0.27 there). Medians over days keep a few burst days from deciding it: COTIUSDT, a crypto coin, had 5 pump weekdays in 2026-07 that pushed its plain monthly weekend share to 0.01. Screened: 288 of 288 2026-07 units. Timing alone does not separate the groups (BTCUSDT has a weekend ratio of 0.53; thin ETF contracts such as EWZUSDT reach 0.85), so the primary label is a review of the ticker names for stocks, ETFs and commodities, and the strict timing cuts above, which flag no known crypto contract, are a cross-check for names the review did not recognise. A unit is excluded if either label flags it. flagged: 37. Flagged units are summarised as their own row and left out of every comparison.

- 2023 survivors, not flagged: weekend ratio 0.445 to 2.878 (median 0.817); median-weekday US-session share 0.220 to 0.370 (median 0.294).
- crypto new listings: weekend ratio 0.495 to 3.513 (median 0.846); median-weekday US-session share 0.205 to 0.350 (median 0.278).
- flagged contracts: weekend ratio 0.100 to 0.849 (median 0.218); median-weekday US-session share 0.259 to 0.626 (median 0.466).

| contract | outcome | weekend ratio | US-session share (median weekday) | flagged by timing screen | identified by name |
|---|---|---|---|---|---|
| EWZUSDT | skipped | 0.849 | 0.367 | no | ETF (Brazil) |
| COSTUSDT | skipped | 0.419 | 0.466 | no | stock (Costco) |
| UBERUSDT | skipped | 0.218 | 0.603 | yes | stock (Uber) |
| SONYUSDT | skipped | 0.401 | 0.259 | no | stock (Sony) |
| IWMUSDT | skipped | 0.688 | 0.347 | no | ETF (Russell 2000) |
| URNMUSDT | skipped | 0.381 | 0.447 | no | ETF (uranium miners) |
| VUSDT | skipped | 0.426 | 0.453 | no | stock (Visa) |
| CIENUSDT | skipped | 0.150 | 0.376 | yes | stock (Ciena) |
| BRKBUSDT | skipped | 0.321 | 0.408 | no | stock (Berkshire Hathaway B) |
| HPEUSDT | ok | 0.353 | 0.477 | no | stock (Hewlett Packard Enterprise) |
| JPMUSDT | skipped | 0.293 | 0.545 | no | stock (JPMorgan Chase) |
| FLNCUSDT | ok | 0.114 | 0.626 | yes | stock (Fluence Energy) |
| ALABUSDT | ok | 0.149 | 0.489 | yes | stock (Astera Labs) |
| ASMLUSDT | ok | 0.243 | 0.383 | yes | stock (ASML) |
| CRDOUSDT | ok | 0.221 | 0.463 | yes | stock (Credo Technology) |
| SQQQUSDT | ok | 0.291 | 0.449 | no | ETF (inverse Nasdaq-100) |
| ASTSUSDT | ok | 0.264 | 0.553 | no | stock (AST SpaceMobile) |
| XPTUSDT | ok | 0.163 | 0.316 | yes | commodity (platinum) |
| CRWVUSDT | ok | 0.115 | 0.582 | yes | stock (CoreWeave) |
| AVGOUSDT | ok | 0.121 | 0.524 | yes | stock (Broadcom) |
| AMATUSDT | ok | 0.264 | 0.410 | no | stock (Applied Materials) |
| QCOMUSDT | ok | 0.183 | 0.511 | yes | stock (Qualcomm) |
| MVLLUSDT | ok | 0.133 | 0.482 | yes | no |
| GOOGLUSDT | ok | 0.206 | 0.478 | yes | stock (Alphabet) |
| PAXGUSDT | ok | 0.390 | 0.326 | no | gold-backed token |
| METAUSDT | ok | 0.177 | 0.543 | yes | stock (Meta Platforms) |
| QQQUSDT | ok | 0.321 | 0.465 | no | ETF (Nasdaq-100) |
| BEUSDT | ok | 0.142 | 0.545 | yes | no |
| TSLAUSDT | ok | 0.130 | 0.602 | yes | stock (Tesla) |
| CRCLUSDT | ok | 0.288 | 0.556 | no | stock (Circle) |
| ARMUSDT | ok | 0.100 | 0.494 | yes | stock (Arm Holdings) |
| DRAMUSDT | ok | 0.188 | 0.398 | yes | no |
| AMDUSDT | ok | 0.130 | 0.527 | yes | stock (AMD) |
| EWYUSDT | ok | 0.155 | 0.324 | yes | ETF (South Korea) |
| XAUUSDT | ok | 0.266 | 0.323 | no | commodity (gold) |
| SKHYNIXUSDT | ok | 0.126 | 0.271 | yes | stock (SK hynix) |
| SNDKUSDT | ok | 0.118 | 0.496 | yes | stock (SanDisk) |

### Group comparisons

Positive means the first group is more predictable (accuracy) or has the larger lift. Accuracy differences are in accuracy units (0.01 is one percentage point).

| comparison | metric | n (group, control) | median group | median control | raw median difference [95% CI] | activity-controlled OLS [95% CI] | matched on log events [95% CI] |
|---|---|---|---|---|---|---|---|
| delisted vs survivors, 2023-06 | gbm_all accuracy | 33, 136 | 0.6248 | 0.6123 | +0.0125 [-0.0044, +0.0272] | +0.0084 [+0.0006, +0.0162] | +0.0105 [+0.0021, +0.0214] |
| delisted vs survivors, 2023-06 | lift of gbm_all over majority | 33, 136 | 0.1102 | 0.1037 | +0.0065 [-0.0039, +0.0175] | +0.0060 [-0.0036, +0.0157] | +0.0113 [+0.0009, +0.0249] |
| delisted vs survivors, 2023-06 | gbm_all minus linear | 33, 136 | 0.0170 | 0.0191 | -0.0020 [-0.0042, +0.0028] | -0.0009 [-0.0036, +0.0019] | -0.0009 [-0.0048, +0.0029] |
| delisted vs survivors, 2023-06 | linear accuracy | 33, 136 | 0.6026 | 0.5939 | +0.0087 [-0.0049, +0.0281] | +0.0093 [+0.0004, +0.0181] | +0.0114 [+0.0015, +0.0231] |
| renamed or merged vs survivors, 2023-06 | gbm_all accuracy | 12, 136 | 0.6151 | 0.6123 | +0.0028 [-0.0309, +0.0228] | -0.0003 [-0.0154, +0.0147] | +0.0019 [-0.0111, +0.0144] |
| renamed or merged vs survivors, 2023-06 | lift of gbm_all over majority | 12, 136 | 0.1064 | 0.1037 | +0.0027 [-0.0234, +0.0290] | +0.0010 [-0.0131, +0.0152] | +0.0066 [-0.0084, +0.0204] |
| renamed or merged vs survivors, 2023-06 | gbm_all minus linear | 12, 136 | 0.0166 | 0.0191 | -0.0025 [-0.0052, +0.0068] | -0.0026 [-0.0075, +0.0023] | -0.0012 [-0.0071, +0.0048] |
| renamed or merged vs survivors, 2023-06 | linear accuracy | 12, 136 | 0.5908 | 0.5939 | -0.0031 [-0.0398, +0.0291] | +0.0023 [-0.0151, +0.0198] | +0.0030 [-0.0126, +0.0200] |
| all ended vs survivors, 2023-06 | gbm_all accuracy | 45, 136 | 0.6191 | 0.6123 | +0.0068 [-0.0047, +0.0232] | +0.0061 [-0.0015, +0.0137] | +0.0082 [+0.0010, +0.0171] |
| all ended vs survivors, 2023-06 | lift of gbm_all over majority | 45, 136 | 0.1102 | 0.1037 | +0.0065 [-0.0044, +0.0177] | +0.0047 [-0.0040, +0.0134] | +0.0100 [+0.0016, +0.0206] |
| all ended vs survivors, 2023-06 | gbm_all minus linear | 45, 136 | 0.0170 | 0.0191 | -0.0020 [-0.0041, +0.0021] | -0.0013 [-0.0039, +0.0012] | -0.0010 [-0.0044, +0.0023] |
| all ended vs survivors, 2023-06 | linear accuracy | 45, 136 | 0.6003 | 0.5939 | +0.0064 [-0.0065, +0.0243] | +0.0074 [-0.0012, +0.0160] | +0.0092 [+0.0002, +0.0193] |
| new listings vs 2023 survivors, 2026-07 | gbm_all accuracy | 113, 138 | 0.6309 | 0.6406 | -0.0097 [-0.0201, +0.0045] | -0.0105 [-0.0230, +0.0020] | +0.0005 [-0.0247, +0.0105] |
| new listings vs 2023 survivors, 2026-07 | lift of gbm_all over majority | 113, 138 | 0.1252 | 0.1357 | -0.0105 [-0.0209, +0.0023] | -0.0009 [-0.0229, +0.0212] | +0.0058 [-0.0265, +0.0269] |
| new listings vs 2023 survivors, 2026-07 | gbm_all minus linear | 113, 138 | 0.0101 | 0.0075 | +0.0026 [+0.0014, +0.0037] | +0.0019 [+0.0001, +0.0037] | +0.0024 [+0.0002, +0.0047] |
| new listings vs 2023 survivors, 2026-07 | linear accuracy | 113, 138 | 0.6239 | 0.6310 | -0.0071 [-0.0222, +0.0034] | -0.0124 [-0.0253, +0.0006] | -0.0019 [-0.0257, +0.0091] |

### Last complete month against 2023-06, same contracts

| metric | n | median change [95% CI] | mean change [95% CI] | change at equal activity [95% CI] | slope per decade of events | up, down |
|---|---|---|---|---|---|---|
| gbm_all accuracy | 45 | +0.0058 [-0.0049, +0.0318] | +0.0096 [-0.0045, +0.0244] | +0.0073 [-0.0076, +0.0221] | -0.0333 | 23, 22 |
| lift of gbm_all over majority | 45 | +0.0159 [+0.0045, +0.0400] | +0.0227 [+0.0055, +0.0401] | +0.0200 [+0.0038, +0.0362] | -0.0384 | 30, 15 |
| gbm_all minus linear | 45 | -0.0097 [-0.0124, -0.0072] | -0.0104 [-0.0137, -0.0069] | -0.0097 [-0.0129, -0.0065] | +0.0102 | 4, 41 |
| linear accuracy | 45 | +0.0198 [-0.0017, +0.0444] | +0.0200 [+0.0041, +0.0363] | +0.0170 [+0.0005, +0.0335] | -0.0436 | 27, 18 |
| gbm_all accuracy, delisted only | 33 | -0.0031 [-0.0165, +0.0139] | +0.0009 [-0.0151, +0.0181] | -0.0075 [-0.0215, +0.0065] | -0.0591 | 14, 19 |
| gbm_all accuracy, renamed_merged only | 12 | +0.0525 [+0.0139, +0.0694] | +0.0336 [+0.0042, +0.0609] | +0.0350 [+0.0003, +0.0696] | -0.0106 | 9, 3 |

| contract | last complete month | events 2023-06 | events last month | gbm_all 2023-06 | gbm_all last | lift 2023-06 | lift last |
|---|---|---|---|---|---|---|---|
| AGIXUSDT | 2024-05 | 1,526,175 | 2,822,017 | 0.5748 | 0.6439 | +0.0813 | +0.1389 |
| ALPHAUSDT | 2025-08 | 4,736,244 | 703,719 | 0.6103 | 0.6252 | +0.1102 | +0.1100 |
| AMBUSDT | 2025-01 | 2,302,744 | 1,047,441 | 0.6357 | 0.6415 | +0.1194 | +0.1239 |
| ANTUSDT | 2024-03 | 1,698,405 | 884,156 | 0.6063 | 0.6356 | +0.0721 | +0.1270 |
| ATAUSDT | 2026-04 | 451,152 | 531,987 | 0.6452 | 0.6128 | +0.1273 | +0.0828 |
| AUDIOUSDT | 2024-04 | 809,732 | 888,860 | 0.6096 | 0.5991 | +0.0907 | +0.0869 |
| BAKEUSDT | 2025-09 | 670,939 | 5,167,475 | 0.6546 | 0.5930 | +0.1591 | +0.1047 |
| BALUSDT | 2025-03 | 736,383 | 463,243 | 0.6407 | 0.6197 | +0.1131 | +0.1496 |
| BLZUSDT | 2024-11 | 875,652 | 1,656,931 | 0.6389 | 0.6951 | +0.1434 | +0.1859 |
| BNXUSDT | 2025-02 | 1,156,585 | 12,406,229 | 0.6151 | 0.6111 | +0.1017 | +0.1235 |
| DARUSDT | 2024-11 | 537,583 | 798,187 | 0.6695 | 0.5916 | +0.1493 | +0.0810 |
| DENTUSDT | 2026-03 | 574,735 | 1,446,680 | 0.6747 | 0.6716 | +0.1611 | +0.1837 |
| DGBUSDT | 2024-03 | 475,555 | 944,512 | 0.6552 | 0.5792 | +0.1518 | +0.0797 |
| EOSUSDT | 2025-04 | 1,740,775 | 3,357,680 | 0.6001 | 0.6321 | +0.1110 | +0.1211 |
| FLMUSDT | 2025-10 | 1,792,306 | 903,965 | 0.6058 | 0.5673 | +0.0982 | +0.0609 |
| FTMUSDT | 2024-12 | 2,063,610 | 8,939,384 | 0.5756 | 0.6322 | +0.0807 | +0.1380 |
| FXSUSDT | 2025-12 | 1,163,246 | 528,538 | 0.6336 | 0.6655 | +0.1260 | +0.1748 |
| GALUSDT | 2024-06 | 1,571,861 | 1,019,534 | 0.6317 | 0.6837 | +0.1337 | +0.1756 |
| HIGHUSDT | 2026-05 | 1,511,544 | 1,408,233 | 0.6092 | 0.6061 | +0.1019 | +0.1177 |
| HOOKUSDT | 2026-02 | 869,362 | 425,826 | 0.6116 | 0.6105 | +0.1001 | +0.1033 |
| IDEXUSDT | 2024-04 | 911,298 | 1,423,149 | 0.6309 | 0.6398 | +0.1392 | +0.1332 |
| KEYUSDT | 2024-11 | 2,889,130 | 2,369,599 | 0.6095 | 0.6413 | +0.1031 | +0.1376 |
| KLAYUSDT | 2024-09 | 548,117 | 343,523 | 0.6504 | 0.5931 | +0.1314 | +0.0914 |
| LEVERUSDT | 2025-08 | 903,468 | 1,355,790 | 0.6381 | 0.6332 | +0.1133 | +0.1007 |
| LINAUSDT | 2025-02 | 8,757,826 | 535,152 | 0.5931 | 0.6316 | +0.0974 | +0.1129 |
| LRCUSDT | 2026-02 | 713,080 | 804,731 | 0.6165 | 0.6153 | +0.1068 | +0.1121 |
| MATICUSDT | 2024-08 | 5,163,143 | 3,320,249 | 0.5803 | 0.6500 | +0.0715 | +0.1115 |
| MKRUSDT | 2025-08 | 1,730,991 | 2,295,934 | 0.6151 | 0.7227 | +0.1008 | +0.2390 |
| NKNUSDT | 2026-01 | 2,132,019 | 392,437 | 0.6249 | 0.6084 | +0.1164 | +0.0974 |
| OCEANUSDT | 2024-05 | 2,221,038 | 2,067,636 | 0.5836 | 0.6541 | +0.0726 | +0.1593 |
| OMGUSDT | 2025-01 | 2,169,007 | 639,378 | 0.5804 | 0.6854 | +0.0705 | +0.2605 |
| PERPUSDT | 2025-10 | 577,837 | 686,569 | 0.6658 | 0.5908 | +0.1494 | +0.0855 |
| PHBUSDT | 2026-04 | 1,414,233 | 1,216,736 | 0.6416 | 0.5974 | +0.1359 | +0.1451 |
| RADUSDT | 2024-04 | 1,177,447 | 1,393,848 | 0.6577 | 0.6716 | +0.1700 | +0.1767 |
| RDNTUSDT | 2026-02 | 1,436,761 | 435,347 | 0.6067 | 0.6729 | +0.0993 | +0.2686 |
| REEFUSDT | 2024-12 | 575,870 | 1,272,089 | 0.6326 | 0.6150 | +0.1034 | +0.1397 |
| RENUSDT | 2024-11 | 2,313,468 | 2,315,963 | 0.6179 | 0.5985 | +0.1216 | +0.0883 |
| RNDRUSDT | 2024-06 | 5,054,960 | 4,836,169 | 0.6322 | 0.6852 | +0.1306 | +0.1776 |
| STMXUSDT | 2025-01 | 658,360 | 792,544 | 0.6777 | 0.6195 | +0.1459 | +0.1392 |
| SXPUSDT | 2025-11 | 2,001,787 | 578,313 | 0.5828 | 0.6549 | +0.0787 | +0.2091 |
| TOMOUSDT | 2023-10 | 9,258,867 | 2,934,859 | 0.5964 | 0.6428 | +0.0933 | +0.1425 |
| TRUUSDT | 2026-03 | 2,059,642 | 829,741 | 0.6248 | 0.6374 | +0.1068 | +0.1534 |
| UNFIUSDT | 2024-09 | 910,925 | 672,069 | 0.6191 | 0.5385 | +0.1011 | +0.0399 |
| WAVESUSDT | 2024-05 | 6,269,680 | 1,904,163 | 0.5739 | 0.6782 | +0.0644 | +0.1693 |
| XEMUSDT | 2024-11 | 708,385 | 524,957 | 0.6434 | 0.6311 | +0.1125 | +0.1294 |

### Where Q9's 10 symbols sit (2023-06)

Percentile ranks within the 136 fitted survivors and the 181 fitted coins of the full universe.

| symbol | events | gbm_all | events pct (survivors) | events pct (full) | gbm_all pct (survivors) | gbm_all pct (full) |
|---|---|---|---|---|---|---|
| BTCUSDT | 21,816,890 | 0.6878 | 100 | 100 | 99 | 99 |
| ETHUSDT | 14,239,099 | 0.6783 | 99 | 99 | 98 | 99 |
| 1000PEPEUSDT | 12,675,042 | 0.5908 | 98 | 99 | 19 | 19 |
| XRPUSDT | 7,617,768 | 0.5930 | 96 | 96 | 23 | 21 |
| SOLUSDT | 6,820,337 | 0.6062 | 95 | 95 | 39 | 36 |
| BNBUSDT | 6,122,425 | 0.5940 | 94 | 94 | 26 | 24 |
| LTCUSDT | 5,400,099 | 0.5928 | 93 | 93 | 22 | 21 |
| DOGEUSDT | 3,605,236 | 0.6123 | 85 | 85 | 50 | 47 |
| LINKUSDT | 2,627,039 | 0.5864 | 79 | 80 | 14 | 14 |
| AVAXUSDT | 2,458,978 | 0.6243 | 78 | 80 | 65 | 62 |

| metric | median, Q9's 10 | median, full universe [95% CI] | median, survivors | Q9 median's percentile in full | share of full below Q9 median |
|---|---|---|---|---|---|
| gbm_all accuracy | 0.6001 | +0.6146 [+0.6096, +0.6214] | 0.6123 | 28 | 0.28 |
| linear accuracy | 0.5700 | +0.5968 [+0.5914, +0.6021] | 0.5939 | 25 | 0.25 |
| lift of gbm_all over majority | 0.1062 | +0.1049 [+0.1007, +0.1098] | 0.1037 | 52 | 0.52 |
| log10_events | 6.81 | +6.12 [+6.05, +6.21] | 6.11 | 95 | 0.95 |

### Predictability and activity

OLS of each metric on log10 events across the full 2023-06 universe (HC1 se).

| metric | slope per decade | se | R^2 | n |
|---|---|---|---|---|
| gbm_all accuracy | -0.0406 | 0.0092 | 0.228 | 181 |
| lift of gbm_all over majority | -0.0265 | 0.0094 | 0.083 | 181 |
| gbm_all minus linear | +0.0147 | 0.0016 | 0.318 | 181 |
| linear accuracy | -0.0553 | 0.0097 | 0.300 | 181 |
| gbm_all accuracy, 2026-07 survivors_2023 | +0.0076 | 0.0084 | 0.005 | 138 |
| gbm_all accuracy, 2026-07 new_listings | -0.0027 | 0.0080 | 0.000 | 113 |
| gbm_all accuracy, 2026-07 new_listings_equity | -0.0072 | 0.0146 | 0.008 | 27 |

### Last complete month: how it was chosen

| contract | last archive month | candidates checked (zip MB: outcome) | chosen |
|---|---|---|---|
| AGIXUSDT | 2024-06 | 2024-06 (39.3: partial, 25 of 30 days); 2024-05 (49.6: ok, 31 of 31 days) | 2024-05 |
| ALPHAUSDT | 2025-09 | 2025-09 (40.0: partial, 23 of 30 days); 2025-08 (11.8: ok, 31 of 31 days) | 2025-08 |
| AMBUSDT | 2025-02 | 2025-02 (26.4: partial, 21 of 28 days); 2025-01 (19.1: ok, 31 of 31 days) | 2025-01 |
| ANTUSDT | 2024-04 | 2024-04 (0.2: partial, 1 of 30 days); 2024-03 (16.3: ok, 31 of 31 days) | 2024-03 |
| ATAUSDT | 2026-05 | 2026-05 (7.8: partial, 19 of 31 days); 2026-04 (8.4: ok, 30 of 30 days) | 2026-04 |
| AUDIOUSDT | 2024-05 | 2024-05 (4.1: partial, 16 of 31 days); 2024-04 (14.1: ok, 30 of 30 days) | 2024-04 |
| BAKEUSDT | 2025-10 | 2025-10 (1.5: partial, 3 of 31 days); 2025-09 (84.5: ok, 30 of 30 days) | 2025-09 |
| BALUSDT | 2025-04 | 2025-04 (4.4: partial, 14 of 30 days); 2025-03 (7.1: ok, 31 of 31 days) | 2025-03 |
| BLZUSDT | 2024-12 | 2024-12 (53.3: partial, 23 of 31 days); 2024-11 (33.7: ok, 30 of 30 days) | 2024-11 |
| BNXUSDT | 2025-03 | 2025-03 (97.6: partial, 17 of 31 days); 2025-02 (266.0: ok, 28 of 28 days) | 2025-02 |
| COMBOUSDT | 2025-03 | 2025-03 (13.0: partial, 27 of 31 days); 2025-02 (13.1: ok, 28 of 28 days) | 2025-02 |
| DARUSDT | 2024-12 | 2024-12 (17.4: partial, 26 of 31 days); 2024-11 (13.5: ok, 30 of 30 days) | 2024-11 |
| DENTUSDT | 2026-04 | 2026-04 (9.6: partial, 21 of 30 days); 2026-03 (23.0: ok, 31 of 31 days) | 2026-03 |
| DGBUSDT | 2024-04 | 2024-04 (0.8: partial, 1 of 30 days); 2024-03 (15.4: ok, 31 of 31 days) | 2024-03 |
| EOSUSDT | 2025-05 | 2025-05 (23.3: partial, 21 of 31 days); 2025-04 (48.5: ok, 30 of 30 days) | 2025-04 |
| FLMUSDT | 2025-11 | 2025-11 (6.3: partial, 21 of 30 days); 2025-10 (13.5: ok, 31 of 31 days) | 2025-10 |
| FTMUSDT | 2025-01 | 2025-01 (12.5: partial, 6 of 31 days); 2024-12 (155.9: ok, 31 of 31 days) | 2024-12 |
| FXSUSDT | 2026-01 | 2026-01 (1.1: partial, 6 of 31 days); 2025-12 (9.8: ok, 31 of 31 days) | 2025-12 |
| GALUSDT | 2024-07 | 2024-07 (17.5: partial, 11 of 31 days); 2024-06 (23.1: ok, 30 of 30 days) | 2024-06 |
| HIGHUSDT | 2026-06 | 2026-06 (8.2: partial, 11 of 30 days); 2026-05 (23.3: ok, 31 of 31 days) | 2026-05 |
| HOOKUSDT | 2026-03 | 2026-03 (13.4: partial, 24 of 31 days); 2026-02 (7.5: ok, 28 of 28 days) | 2026-02 |
| IDEXUSDT | 2024-05 | 2024-05 (12.7: partial, 15 of 31 days); 2024-04 (27.2: ok, 30 of 30 days) | 2024-04 |
| KEYUSDT | 2024-12 | 2024-12 (4.3: partial, 3 of 31 days); 2024-11 (74.9: ok, 30 of 30 days) | 2024-11 |
| KLAYUSDT | 2024-10 | 2024-10 (4.0: partial, 22 of 31 days); 2024-09 (5.5: ok, 30 of 30 days) | 2024-09 |
| LEVERUSDT | 2025-09 | 2025-09 (7.9: partial, 3 of 30 days); 2025-08 (28.0: ok, 31 of 31 days) | 2025-08 |
| LINAUSDT | 2025-03 | 2025-03 (14.4: partial, 27 of 31 days); 2025-02 (8.1: ok, 28 of 28 days) | 2025-02 |
| LRCUSDT | 2026-03 | 2026-03 (12.5: partial, 24 of 31 days); 2026-02 (14.1: ok, 28 of 28 days) | 2026-02 |
| MATICUSDT | 2024-09 | 2024-09 (3.9: partial, 4 of 30 days); 2024-08 (51.2: ok, 31 of 31 days) | 2024-08 |
| MKRUSDT | 2025-09 | 2025-09 (13.2: partial, 8 of 30 days); 2025-08 (44.3: ok, 31 of 31 days) | 2025-08 |
| NKNUSDT | 2026-02 | 2026-02 (2.2: partial, 6 of 28 days); 2026-01 (6.2: ok, 31 of 31 days) | 2026-01 |
| OCEANUSDT | 2024-06 | 2024-06 (29.2: partial, 25 of 30 days); 2024-05 (37.2: ok, 31 of 31 days) | 2024-05 |
| OMGUSDT | 2025-01 | 2025-01 (11.5: ok, 31 of 31 days) | 2025-01 |
| PERPUSDT | 2025-11 | 2025-11 (7.7: partial, 21 of 30 days); 2025-10 (12.2: ok, 31 of 31 days) | 2025-10 |
| PHBUSDT | 2026-05 | 2026-05 (11.3: partial, 19 of 31 days); 2026-04 (21.1: ok, 30 of 30 days) | 2026-04 |
| RADUSDT | 2024-05 | 2024-05 (10.1: partial, 14 of 31 days); 2024-04 (30.7: ok, 30 of 30 days) | 2024-04 |
| RDNTUSDT | 2026-03 | 2026-03 (36.0: partial, 24 of 31 days); 2026-02 (7.6: ok, 28 of 28 days) | 2026-02 |
| REEFUSDT | 2025-01 | 2025-01 (11.9: partial, 22 of 31 days); 2024-12 (22.0: ok, 31 of 31 days) | 2024-12 |
| RENUSDT | 2024-12 | 2024-12 (7.4: partial, 3 of 31 days); 2024-11 (47.7: ok, 30 of 30 days) | 2024-11 |
| RNDRUSDT | 2024-07 | 2024-07 (66.8: partial, 16 of 31 days); 2024-06 (130.9: ok, 30 of 30 days) | 2024-06 |
| STMXUSDT | 2025-02 | 2025-02 (5.3: partial, 21 of 28 days); 2025-01 (12.5: ok, 31 of 31 days) | 2025-01 |
| SXPUSDT | 2025-12 | 2025-12 (5.5: partial, 5 of 31 days); 2025-11 (8.9: ok, 30 of 30 days) | 2025-11 |
| TOMOUSDT | 2023-11 | 2023-11 (35.5: partial, 14 of 30 days); 2023-10 (64.0: ok, 31 of 31 days) | 2023-10 |
| TRUUSDT | 2026-04 | 2026-04 (107.4: partial, 21 of 30 days); 2026-03 (16.4: ok, 31 of 31 days) | 2026-03 |
| UNFIUSDT | 2024-10 | 2024-10 (54.2: partial, 30 of 31 days); 2024-09 (11.4: ok, 30 of 30 days) | 2024-09 |
| WAVESUSDT | 2024-06 | 2024-06 (34.3: partial, 11 of 30 days); 2024-05 (44.7: ok, 31 of 31 days) | 2024-05 |
| XEMUSDT | 2024-12 | 2024-12 (3.0: partial, 9 of 31 days); 2024-11 (7.9: ok, 30 of 30 days) | 2024-11 |

### Units not fitted

Every planned unit that did not produce a fit, with its event count and reason.

| set | contract | status | month | events | outcome | reason |
|---|---|---|---|---|---|---|
| cross_2023 | COMBOUSDT | delisted | 2023-06 | 1,495,384 | partial | incomplete month: traded on 29 of 30 days, days 2 to 30 |
| cross_2023 | MAVUSDT | survivor | 2023-06 | 274,271 | partial | incomplete month: traded on 2 of 30 days, days 29 to 30 |
| cross_2023 | MDTUSDT | relisted | 2023-06 | 34,606 | partial | incomplete month: traded on 1 of 30 days, days 30 to 30 |
| cross_2023 | NMRUSDT | survivor | 2023-06 | 170,600 | partial | incomplete month: traded on 9 of 30 days, days 22 to 30 |
| cross_2026 | EWZUSDT | new_listing_equity | 2026-07 | 45,753 | skipped | too few scoreable events: 20,675 train rows < 50,000, 1,969 validation rows < 5,000 |
| cross_2026 | COSTUSDT | new_listing_equity | 2026-07 | 41,207 | skipped | too few scoreable events: 21,448 train rows < 50,000, 2,401 validation rows < 5,000 |
| cross_2026 | UBERUSDT | new_listing_equity | 2026-07 | 47,015 | skipped | too few scoreable events: 20,292 train rows < 50,000, 2,990 validation rows < 5,000 |
| cross_2026 | SONYUSDT | new_listing_equity | 2026-07 | 51,925 | skipped | too few scoreable events: 23,822 train rows < 50,000, 1,711 validation rows < 5,000 |
| cross_2026 | IWMUSDT | new_listing_equity | 2026-07 | 65,686 | skipped | too few scoreable events: 40,509 train rows < 50,000, 2,638 validation rows < 5,000 |
| cross_2026 | URNMUSDT | new_listing_equity | 2026-07 | 68,892 | skipped | too few scoreable events: 38,084 train rows < 50,000, 4,296 validation rows < 5,000 |
| cross_2026 | VUSDT | new_listing_equity | 2026-07 | 68,672 | skipped | too few scoreable events: 27,686 train rows < 50,000, 2,310 validation rows < 5,000 |
| cross_2026 | CIENUSDT | new_listing_equity | 2026-07 | 74,605 | skipped | too few scoreable events: 31,974 train rows < 50,000, 4,174 validation rows < 5,000 |
| cross_2026 | BRKBUSDT | new_listing_equity | 2026-07 | 89,507 | skipped | too few scoreable events: 36,980 train rows < 50,000 |
| cross_2026 | JPMUSDT | new_listing_equity | 2026-07 | 99,347 | skipped | too few scoreable events: 43,411 train rows < 50,000 |

## Verdict

Across the 2023-06 universe, gbm_all accuracy changes by -0.0406 per decade of events (HC1 se 0.0092, R^2 0.228, n 181) and the lift over majority -0.0265 (se 0.0094, R^2 0.083): busier contracts are less predictable, so activity is a confound that any group comparison has to hold fixed. In 2023-06, all ended contracts (45) have a median gbm_all accuracy of 0.6191 against 0.6123 for survivors (136): a raw median difference of +0.0068 [-0.0047, +0.0232], not distinguishable from zero. Controlling for activity (OLS on log10 events plus a group dummy, HC1), the group difference is +0.0061 [-0.0015, +0.0137], not distinguishable from zero; matched to the survivor contract with the nearest log events (with replacement), it is +0.0082 [+0.0010, +0.0171], distinguishable from zero (positive). Neither raw nor at equal activity is there a difference the data can distinguish; the controlled point estimate is above zero by 0.61 pp. In 2023-06, delisted contracts (33) have a median gbm_all accuracy of 0.6248 against 0.6123 for survivors (136): a raw median difference of +0.0125 [-0.0044, +0.0272], not distinguishable from zero. Controlling for activity (OLS on log10 events plus a group dummy, HC1), the group difference is +0.0084 [+0.0006, +0.0162], distinguishable from zero (positive); matched to the survivor contract with the nearest log events (with replacement), it is +0.0105 [+0.0021, +0.0214], distinguishable from zero (positive). At equal activity, delisted contracts were more predictable than survivors by this measure. In 2023-06, renamed or merged contracts (12) have a median gbm_all accuracy of 0.6151 against 0.6123 for survivors (136): a raw median difference of +0.0028 [-0.0309, +0.0228], not distinguishable from zero. Controlling for activity (OLS on log10 events plus a group dummy, HC1), the group difference is -0.0003 [-0.0154, +0.0147], not distinguishable from zero; matched to the survivor contract with the nearest log events (with replacement), it is +0.0019 [-0.0111, +0.0144], not distinguishable from zero. Neither raw nor at equal activity is there a difference the data can distinguish; the controlled point estimate is below zero by 0.03 pp. Within the 45 ended contracts with both fits, gbm_all accuracy in the last complete month minus 2023-06 has a median of +0.0058 [-0.0049, +0.0318], not distinguishable from zero (23 up, 22 down; median change in log10 events -0.03). At no change in activity (intercept of the change on the change in log10 events, HC1) it is +0.0073 [-0.0076, +0.0221], not distinguishable from zero, with a slope of -0.0333 per decade of events. 37 of the 288 screened 2026-07 contracts are flagged as stock, ETF or commodity perpetuals (identified by ticker name, or by a timing screen: median weekend day below 0.25 of the median weekday, or a median weekday share of at least 0.60 in the US cash session) and are kept out of the crypto comparison: EWZUSDT, COSTUSDT, UBERUSDT, SONYUSDT, IWMUSDT, URNMUSDT, VUSDT, CIENUSDT, BRKBUSDT, HPEUSDT, JPMUSDT, FLNCUSDT, ALABUSDT, ASMLUSDT, CRDOUSDT, SQQQUSDT, ASTSUSDT, XPTUSDT, CRWVUSDT, AVGOUSDT, AMATUSDT, QCOMUSDT, MVLLUSDT, GOOGLUSDT, PAXGUSDT, METAUSDT, QQQUSDT, BEUSDT, TSLAUSDT, CRCLUSDT, ARMUSDT, DRAMUSDT, AMDUSDT, EWYUSDT, XAUUSDT, SKHYNIXUSDT, SNDKUSDT. 27 of them were fitted. In 2026-07, new listings contracts (113) have a median gbm_all accuracy of 0.6309 against 0.6406 for 2023 survivors (138): a raw median difference of -0.0097 [-0.0201, +0.0045], not distinguishable from zero. Controlling for activity (OLS on log10 events plus a group dummy, HC1), the group difference is -0.0105 [-0.0230, +0.0020], not distinguishable from zero; matched to the survivor contract with the nearest log events (with replacement), it is +0.0005 [-0.0247, +0.0105], not distinguishable from zero. Neither raw nor at equal activity is there a difference the data can distinguish; the controlled point estimate is below zero by 1.05 pp. Q9's 10 symbols have a median gbm_all accuracy of 0.6001; the median over all 181 fitted 2023-06 coins is +0.6146 [+0.6096, +0.6214] (survivors only: 0.6123). The Q9 median sits at the 28th percentile of the full universe, and the Q9 symbols' activity at a median 95th percentile (median log10 events 6.81 against 6.12). Q9's 10-symbol headline understates the typical contract: it is -1.45 pp from the universe median, outside that median's interval. The activity slope alone predicts a gap of -2.81 pp for that difference in activity. None of this is a trading result: these are accuracies of next-sign calls on aggressor events, with no prices, costs or profit and loss.

## Caveats

- **Survival is defined by the archive.** A contract counts as ended when data.binance.vision has no monthly file for it at or after 2026-07. The archive's last month is taken as the month the futures contract stopped; a contract delisted and relisted later (MDTUSDT) is kept out of both comparison groups.
- **Classification is hand-made.** Renamed, merged and index contracts are named in a constant in `q14_survivorship.py`; renamed successors were checked to start within two months in the inventory, but the reason a contract was delisted (low volume, project failure, exchange policy) is not known here.
- **Activity is one number.** The controlled comparisons hold log10 aggressor events in the month fixed, linearly (OLS) or by nearest neighbour. Tick size, price level, spread and the share of retail flow also differ across contracts and are not controlled; Q4b found tick size borderline for flip probability.
- **The thinnest contracts are not scored.** A unit needs at least 50,000 scoreable train rows, 5,000 validation rows and 10,000 test rows, and a complete month. Units below that are listed with their counts; if delisted contracts are thinner than survivors, the ones left are the busier ones, which biases the ended group toward survivor-like activity.
- **New listings are a sample.** 150 of the 499 contracts first listed between 2023-07 and 2026-06 that are alive in 2026-07, 15 from each decile of 2026-07 zip size (seed 0); 42 first listed in 2026-07 have no complete July and are outside the frame. Sampled contracts flagged as equity perpetuals are dropped from the crypto group after the draw, so it is smaller than the draw. Zip size is an activity proxy, so the draw is stratified on the confound but is not the full population.
- **One month per unit, seven test days.** Each unit is one month with Q9's split, so a unit's accuracy rests on its 7 or so test days; across-symbol intervals treat each unit's number as exact and include only the between-contract spread.
- **Same ladder, many fits.** No setting was tuned for Q14: every unit uses Q9's default configuration (in the JSON under `rules.q9_config`); only the boosting round count is early-stopped per unit. Q9's own 2023-06 caches are reused for its 10 symbols when their configuration and ladder fingerprint match.
- **Calendar differences.** The last complete month of an ended contract falls between 2023 and 2026, so the paired change mixes approaching the end with market-wide change over time (Q8 and Q10 show the market changed between these years).

## Appendix: every fitted unit

| set | contract | status | month | events | majority | persistence | linear | gbm_all | lift |
|---|---|---|---|---|---|---|---|---|---|
| cross_2023 | 1000FLOKIUSDT | survivor | 2023-06 | 1,071,346 | 0.4949 | 0.5533 | 0.5685 | 0.5959 | +0.1011 |
| cross_2023 | 1000LUNCUSDT | survivor | 2023-06 | 4,196,777 | 0.4933 | 0.4146 | 0.5517 | 0.5960 | +0.1027 |
| cross_2023 | 1000PEPEUSDT | survivor | 2023-06 | 12,675,042 | 0.4963 | 0.4694 | 0.5464 | 0.5908 | +0.0945 |
| cross_2023 | 1000SHIBUSDT | survivor | 2023-06 | 3,031,796 | 0.4993 | 0.5507 | 0.5632 | 0.5894 | +0.0901 |
| cross_2023 | 1000XECUSDT | survivor | 2023-06 | 1,358,479 | 0.5125 | 0.4398 | 0.4955 | 0.5369 | +0.0244 |
| cross_2023 | 1INCHUSDT | survivor | 2023-06 | 993,914 | 0.5046 | 0.5904 | 0.5966 | 0.6146 | +0.1101 |
| cross_2023 | AAVEUSDT | survivor | 2023-06 | 2,282,773 | 0.5088 | 0.4983 | 0.5413 | 0.5698 | +0.0610 |
| cross_2023 | ACHUSDT | survivor | 2023-06 | 1,205,804 | 0.5110 | 0.5752 | 0.6008 | 0.6234 | +0.1124 |
| cross_2023 | ADAUSDT | survivor | 2023-06 | 4,406,216 | 0.4935 | 0.5059 | 0.5541 | 0.5784 | +0.0849 |
| cross_2023 | AGIXUSDT | merged | 2023-06 | 1,526,175 | 0.4935 | 0.5400 | 0.5513 | 0.5748 | +0.0813 |
| cross_2023 | ALGOUSDT | survivor | 2023-06 | 887,166 | 0.5136 | 0.5789 | 0.6055 | 0.6215 | +0.1079 |
| cross_2023 | ALICEUSDT | survivor | 2023-06 | 550,540 | 0.5245 | 0.5895 | 0.6178 | 0.6343 | +0.1098 |
| cross_2023 | ALPHAUSDT | delisted | 2023-06 | 4,736,244 | 0.5001 | 0.6065 | 0.5968 | 0.6103 | +0.1102 |
| cross_2023 | AMBUSDT | delisted | 2023-06 | 2,302,744 | 0.5163 | 0.4067 | 0.5942 | 0.6357 | +0.1194 |
| cross_2023 | ANKRUSDT | survivor | 2023-06 | 1,076,265 | 0.5013 | 0.5062 | 0.5504 | 0.5871 | +0.0858 |
| cross_2023 | ANTUSDT | delisted | 2023-06 | 1,698,405 | 0.5342 | 0.5787 | 0.5800 | 0.6063 | +0.0721 |
| cross_2023 | APEUSDT | survivor | 2023-06 | 3,687,286 | 0.5024 | 0.5268 | 0.6042 | 0.6255 | +0.1232 |
| cross_2023 | API3USDT | survivor | 2023-06 | 472,303 | 0.5149 | 0.6020 | 0.6320 | 0.6497 | +0.1348 |
| cross_2023 | APTUSDT | survivor | 2023-06 | 3,361,904 | 0.5015 | 0.5564 | 0.5561 | 0.5845 | +0.0830 |
| cross_2023 | ARBUSDT | survivor | 2023-06 | 4,308,450 | 0.4960 | 0.5546 | 0.5589 | 0.5924 | +0.0964 |
| cross_2023 | ARPAUSDT | survivor | 2023-06 | 3,793,737 | 0.5005 | 0.5399 | 0.5377 | 0.5763 | +0.0758 |
| cross_2023 | ARUSDT | survivor | 2023-06 | 863,727 | 0.5070 | 0.6058 | 0.6101 | 0.6236 | +0.1166 |
| cross_2023 | ASTRUSDT | survivor | 2023-06 | 754,996 | 0.5054 | 0.6275 | 0.6318 | 0.6484 | +0.1430 |
| cross_2023 | ATAUSDT | delisted | 2023-06 | 451,152 | 0.5179 | 0.5966 | 0.6295 | 0.6452 | +0.1273 |
| cross_2023 | ATOMUSDT | survivor | 2023-06 | 2,456,324 | 0.4953 | 0.5739 | 0.5840 | 0.6087 | +0.1133 |
| cross_2023 | AUDIOUSDT | delisted | 2023-06 | 809,732 | 0.5189 | 0.5500 | 0.5932 | 0.6096 | +0.0907 |
| cross_2023 | AVAXUSDT | survivor | 2023-06 | 2,458,978 | 0.5037 | 0.6058 | 0.6021 | 0.6243 | +0.1205 |
| cross_2023 | AXSUSDT | survivor | 2023-06 | 1,996,023 | 0.5008 | 0.5415 | 0.5565 | 0.5830 | +0.0822 |
| cross_2023 | BAKEUSDT | delisted | 2023-06 | 670,939 | 0.4956 | 0.6165 | 0.6455 | 0.6546 | +0.1591 |
| cross_2023 | BALUSDT | delisted | 2023-06 | 736,383 | 0.5276 | 0.6193 | 0.6259 | 0.6407 | +0.1131 |
| cross_2023 | BANDUSDT | survivor | 2023-06 | 1,886,161 | 0.5074 | 0.6302 | 0.6265 | 0.6358 | +0.1284 |
| cross_2023 | BATUSDT | survivor | 2023-06 | 538,723 | 0.5506 | 0.6069 | 0.6401 | 0.6543 | +0.1036 |
| cross_2023 | BCHUSDT | survivor | 2023-06 | 10,755,244 | 0.5082 | 0.4812 | 0.5279 | 0.5671 | +0.0589 |
| cross_2023 | BELUSDT | survivor | 2023-06 | 1,615,858 | 0.4966 | 0.5909 | 0.5919 | 0.6108 | +0.1142 |
| cross_2023 | BLURUSDT | survivor | 2023-06 | 2,244,288 | 0.4937 | 0.4752 | 0.5222 | 0.5703 | +0.0767 |
| cross_2023 | BLZUSDT | delisted | 2023-06 | 875,652 | 0.4955 | 0.6152 | 0.6235 | 0.6389 | +0.1434 |
| cross_2023 | BNBUSDT | survivor | 2023-06 | 6,122,425 | 0.4934 | 0.5436 | 0.5615 | 0.5940 | +0.1007 |
| cross_2023 | BNXUSDT | renamed | 2023-06 | 1,156,585 | 0.5134 | 0.5807 | 0.5786 | 0.6151 | +0.1017 |
| cross_2023 | BTCDOMUSDT | survivor | 2023-06 | 381,793 | 0.5293 | 0.5953 | 0.5990 | 0.6099 | +0.0806 |
| cross_2023 | BTCUSDT | survivor | 2023-06 | 21,816,890 | 0.5046 | 0.5603 | 0.6541 | 0.6878 | +0.1832 |
| cross_2023 | C98USDT | survivor | 2023-06 | 727,467 | 0.5059 | 0.5668 | 0.5939 | 0.6096 | +0.1037 |
| cross_2023 | CELOUSDT | survivor | 2023-06 | 712,572 | 0.5408 | 0.5967 | 0.6174 | 0.6214 | +0.0806 |
| cross_2023 | CELRUSDT | survivor | 2023-06 | 759,714 | 0.5130 | 0.5879 | 0.6068 | 0.6246 | +0.1116 |
| cross_2023 | CFXUSDT | survivor | 2023-06 | 3,540,863 | 0.5200 | 0.5093 | 0.5639 | 0.5785 | +0.0585 |
| cross_2023 | CHRUSDT | survivor | 2023-06 | 639,559 | 0.4780 | 0.6116 | 0.6482 | 0.6650 | +0.1871 |
| cross_2023 | CHZUSDT | survivor | 2023-06 | 2,224,240 | 0.5035 | 0.5856 | 0.5854 | 0.6084 | +0.1049 |
| cross_2023 | CKBUSDT | survivor | 2023-06 | 614,292 | 0.5010 | 0.6198 | 0.6390 | 0.6557 | +0.1547 |
| cross_2023 | COMPUSDT | survivor | 2023-06 | 3,070,323 | 0.5140 | 0.4272 | 0.4947 | 0.5474 | +0.0334 |
| cross_2023 | COTIUSDT | survivor | 2023-06 | 1,033,785 | 0.5170 | 0.6204 | 0.6248 | 0.6399 | +0.1229 |
| cross_2023 | CRVUSDT | survivor | 2023-06 | 1,471,623 | 0.5013 | 0.5490 | 0.6210 | 0.6420 | +0.1407 |
| cross_2023 | CTKUSDT | survivor_gap | 2023-06 | 544,938 | 0.5128 | 0.6409 | 0.6449 | 0.6572 | +0.1444 |
| cross_2023 | CTSIUSDT | survivor | 2023-06 | 1,022,623 | 0.5089 | 0.5784 | 0.5901 | 0.6061 | +0.0972 |
| cross_2023 | CVXUSDT | survivor_gap | 2023-06 | 521,257 | 0.4917 | 0.6502 | 0.6585 | 0.6741 | +0.1824 |
| cross_2023 | DARUSDT | renamed | 2023-06 | 537,583 | 0.5202 | 0.6175 | 0.6555 | 0.6695 | +0.1493 |
| cross_2023 | DASHUSDT | survivor | 2023-06 | 1,046,537 | 0.5134 | 0.5576 | 0.5759 | 0.5961 | +0.0827 |
| cross_2023 | DENTUSDT | delisted | 2023-06 | 574,735 | 0.5135 | 0.6202 | 0.6620 | 0.6747 | +0.1611 |
| cross_2023 | DGBUSDT | delisted | 2023-06 | 475,555 | 0.5034 | 0.5911 | 0.6318 | 0.6552 | +0.1518 |
| cross_2023 | DOGEUSDT | survivor | 2023-06 | 3,605,236 | 0.5050 | 0.5329 | 0.5922 | 0.6123 | +0.1072 |
| cross_2023 | DOTUSDT | survivor | 2023-06 | 2,209,346 | 0.4996 | 0.5405 | 0.5742 | 0.5899 | +0.0903 |
| cross_2023 | DUSKUSDT | survivor | 2023-06 | 1,454,794 | 0.5012 | 0.5999 | 0.5981 | 0.6144 | +0.1132 |
| cross_2023 | DYDXUSDT | survivor | 2023-06 | 1,808,950 | 0.4959 | 0.4762 | 0.5726 | 0.5889 | +0.0930 |
| cross_2023 | EDUUSDT | survivor | 2023-06 | 2,940,081 | 0.4941 | 0.5687 | 0.5766 | 0.6010 | +0.1069 |
| cross_2023 | EGLDUSDT | survivor | 2023-06 | 819,561 | 0.5066 | 0.5830 | 0.6008 | 0.6188 | +0.1121 |
| cross_2023 | ENJUSDT | survivor | 2023-06 | 887,048 | 0.5286 | 0.5771 | 0.6057 | 0.6239 | +0.0953 |
| cross_2023 | ENSUSDT | survivor | 2023-06 | 938,356 | 0.5087 | 0.6137 | 0.6203 | 0.6331 | +0.1244 |
| cross_2023 | EOSUSDT | renamed | 2023-06 | 1,740,775 | 0.4891 | 0.5208 | 0.5817 | 0.6001 | +0.1110 |
| cross_2023 | ETCUSDT | survivor | 2023-06 | 3,656,191 | 0.4949 | 0.5608 | 0.5821 | 0.6073 | +0.1124 |
| cross_2023 | ETHUSDT | survivor | 2023-06 | 14,239,099 | 0.5023 | 0.5160 | 0.6418 | 0.6783 | +0.1759 |
| cross_2023 | FETUSDT | survivor | 2023-06 | 1,480,413 | 0.5223 | 0.5262 | 0.5592 | 0.5867 | +0.0644 |
| cross_2023 | FILUSDT | survivor | 2023-06 | 2,075,828 | 0.5085 | 0.5432 | 0.5646 | 0.5874 | +0.0789 |
| cross_2023 | FLMUSDT | delisted | 2023-06 | 1,792,306 | 0.5075 | 0.5323 | 0.5916 | 0.6058 | +0.0982 |
| cross_2023 | FLOWUSDT | survivor | 2023-06 | 868,949 | 0.5223 | 0.5797 | 0.5967 | 0.6101 | +0.0878 |
| cross_2023 | FTMUSDT | renamed | 2023-06 | 2,063,610 | 0.4948 | 0.4740 | 0.5585 | 0.5756 | +0.0807 |
| cross_2023 | FXSUSDT | renamed | 2023-06 | 1,163,246 | 0.5077 | 0.6099 | 0.6175 | 0.6336 | +0.1260 |
| cross_2023 | GALAUSDT | survivor | 2023-06 | 2,017,116 | 0.5102 | 0.4988 | 0.5598 | 0.5762 | +0.0661 |
| cross_2023 | GALUSDT | renamed | 2023-06 | 1,571,861 | 0.4980 | 0.6270 | 0.6229 | 0.6317 | +0.1337 |
| cross_2023 | GMTUSDT | survivor | 2023-06 | 1,268,002 | 0.5033 | 0.4783 | 0.5583 | 0.5742 | +0.0709 |
| cross_2023 | GMXUSDT | survivor | 2023-06 | 777,831 | 0.4832 | 0.6343 | 0.6340 | 0.6524 | +0.1692 |
| cross_2023 | GRTUSDT | survivor | 2023-06 | 2,257,050 | 0.5099 | 0.6043 | 0.6033 | 0.6174 | +0.1075 |
| cross_2023 | GTCUSDT | survivor | 2023-06 | 552,519 | 0.5140 | 0.5818 | 0.6043 | 0.6243 | +0.1103 |
| cross_2023 | HBARUSDT | survivor | 2023-06 | 1,120,699 | 0.5264 | 0.5913 | 0.6008 | 0.6179 | +0.0915 |
| cross_2023 | HFTUSDT | survivor | 2023-06 | 663,186 | 0.5184 | 0.6383 | 0.6473 | 0.6611 | +0.1426 |
| cross_2023 | HIGHUSDT | delisted | 2023-06 | 1,511,544 | 0.5074 | 0.5478 | 0.5888 | 0.6092 | +0.1019 |
| cross_2023 | HOOKUSDT | delisted | 2023-06 | 869,362 | 0.5115 | 0.5574 | 0.5831 | 0.6116 | +0.1001 |
| cross_2023 | HOTUSDT | survivor | 2023-06 | 593,653 | 0.5253 | 0.5873 | 0.6263 | 0.6416 | +0.1163 |
| cross_2023 | ICPUSDT | survivor | 2023-06 | 1,216,647 | 0.5121 | 0.5669 | 0.5825 | 0.6067 | +0.0946 |
| cross_2023 | ICXUSDT | survivor | 2023-06 | 822,511 | 0.5147 | 0.5419 | 0.5812 | 0.6025 | +0.0878 |
| cross_2023 | IDEXUSDT | delisted | 2023-06 | 911,298 | 0.4918 | 0.6058 | 0.6142 | 0.6309 | +0.1392 |
| cross_2023 | IDUSDT | survivor | 2023-06 | 2,144,610 | 0.4924 | 0.5239 | 0.5427 | 0.5775 | +0.0852 |
| cross_2023 | IMXUSDT | survivor | 2023-06 | 1,782,554 | 0.5112 | 0.6040 | 0.6098 | 0.6252 | +0.1141 |
| cross_2023 | INJUSDT | survivor | 2023-06 | 4,557,308 | 0.4994 | 0.5288 | 0.5408 | 0.5812 | +0.0818 |
| cross_2023 | IOSTUSDT | survivor | 2023-06 | 785,884 | 0.5340 | 0.6118 | 0.6260 | 0.6401 | +0.1061 |
| cross_2023 | IOTAUSDT | survivor | 2023-06 | 746,848 | 0.5296 | 0.5719 | 0.6055 | 0.6237 | +0.0941 |
| cross_2023 | IOTXUSDT | survivor | 2023-06 | 578,728 | 0.5306 | 0.6072 | 0.6229 | 0.6385 | +0.1079 |
| cross_2023 | JASMYUSDT | survivor | 2023-06 | 1,510,318 | 0.5099 | 0.5693 | 0.5764 | 0.6026 | +0.0927 |
| cross_2023 | JOEUSDT | survivor | 2023-06 | 1,637,416 | 0.5186 | 0.6011 | 0.6125 | 0.6306 | +0.1120 |
| cross_2023 | KAVAUSDT | survivor | 2023-06 | 3,391,557 | 0.5018 | 0.5577 | 0.5676 | 0.5937 | +0.0918 |
| cross_2023 | KEYUSDT | delisted | 2023-06 | 2,889,130 | 0.5064 | 0.5997 | 0.5900 | 0.6095 | +0.1031 |
| cross_2023 | KLAYUSDT | renamed | 2023-06 | 548,117 | 0.5190 | 0.6112 | 0.6352 | 0.6504 | +0.1314 |
| cross_2023 | KNCUSDT | survivor | 2023-06 | 1,122,255 | 0.5059 | 0.5719 | 0.5868 | 0.6035 | +0.0976 |
| cross_2023 | KSMUSDT | survivor | 2023-06 | 728,895 | 0.5105 | 0.5792 | 0.5939 | 0.6131 | +0.1026 |
| cross_2023 | LDOUSDT | survivor | 2023-06 | 3,762,036 | 0.4980 | 0.6257 | 0.6224 | 0.6373 | +0.1392 |
| cross_2023 | LEVERUSDT | delisted | 2023-06 | 903,468 | 0.5248 | 0.5968 | 0.6173 | 0.6381 | +0.1133 |
| cross_2023 | LINAUSDT | delisted | 2023-06 | 8,757,826 | 0.4957 | 0.5563 | 0.5717 | 0.5931 | +0.0974 |
| cross_2023 | LINKUSDT | survivor | 2023-06 | 2,627,039 | 0.4959 | 0.5265 | 0.5643 | 0.5864 | +0.0905 |
| cross_2023 | LITUSDT | survivor_gap | 2023-06 | 655,339 | 0.5113 | 0.6080 | 0.6032 | 0.6048 | +0.0935 |
| cross_2023 | LPTUSDT | survivor | 2023-06 | 1,009,205 | 0.5125 | 0.6137 | 0.6196 | 0.6371 | +0.1246 |
| cross_2023 | LQTYUSDT | survivor | 2023-06 | 1,366,845 | 0.5017 | 0.6268 | 0.6294 | 0.6396 | +0.1379 |
| cross_2023 | LRCUSDT | delisted | 2023-06 | 713,080 | 0.5097 | 0.5719 | 0.5995 | 0.6165 | +0.1068 |
| cross_2023 | LTCUSDT | survivor | 2023-06 | 5,400,099 | 0.4978 | 0.5416 | 0.5676 | 0.5928 | +0.0949 |
| cross_2023 | LUNA2USDT | survivor | 2023-06 | 1,780,217 | 0.5297 | 0.5874 | 0.5997 | 0.6167 | +0.0871 |
| cross_2023 | MAGICUSDT | survivor | 2023-06 | 2,203,613 | 0.5051 | 0.5869 | 0.5884 | 0.6081 | +0.1030 |
| cross_2023 | MANAUSDT | survivor | 2023-06 | 1,661,320 | 0.5041 | 0.5359 | 0.5635 | 0.5827 | +0.0786 |
| cross_2023 | MASKUSDT | survivor | 2023-06 | 2,250,524 | 0.5066 | 0.5243 | 0.5624 | 0.5848 | +0.0781 |
| cross_2023 | MATICUSDT | renamed | 2023-06 | 5,163,143 | 0.5088 | 0.4921 | 0.5522 | 0.5803 | +0.0715 |
| cross_2023 | MINAUSDT | survivor | 2023-06 | 1,145,911 | 0.4993 | 0.6036 | 0.6109 | 0.6297 | +0.1304 |
| cross_2023 | MKRUSDT | renamed | 2023-06 | 1,730,991 | 0.5143 | 0.5779 | 0.6000 | 0.6151 | +0.1008 |
| cross_2023 | MTLUSDT | survivor | 2023-06 | 8,611,397 | 0.4986 | 0.4105 | 0.5513 | 0.5895 | +0.0909 |
| cross_2023 | NEARUSDT | survivor | 2023-06 | 1,947,040 | 0.5125 | 0.4674 | 0.5936 | 0.6123 | +0.0998 |
| cross_2023 | NEOUSDT | survivor | 2023-06 | 1,675,306 | 0.5028 | 0.6098 | 0.6075 | 0.6243 | +0.1215 |
| cross_2023 | NKNUSDT | delisted | 2023-06 | 2,132,019 | 0.5085 | 0.6045 | 0.6118 | 0.6249 | +0.1164 |
| cross_2023 | OCEANUSDT | merged | 2023-06 | 2,221,038 | 0.5110 | 0.5477 | 0.5538 | 0.5836 | +0.0726 |
| cross_2023 | OGNUSDT | survivor | 2023-06 | 474,091 | 0.5060 | 0.6036 | 0.6414 | 0.6612 | +0.1551 |
| cross_2023 | OMGUSDT | delisted | 2023-06 | 2,169,007 | 0.5099 | 0.5479 | 0.5584 | 0.5804 | +0.0705 |
| cross_2023 | ONEUSDT | survivor | 2023-06 | 691,452 | 0.5145 | 0.5781 | 0.6094 | 0.6249 | +0.1104 |
| cross_2023 | ONTUSDT | survivor | 2023-06 | 888,126 | 0.5202 | 0.5334 | 0.5870 | 0.6083 | +0.0880 |
| cross_2023 | OPUSDT | survivor | 2023-06 | 5,208,936 | 0.5023 | 0.5776 | 0.5784 | 0.6028 | +0.1005 |
| cross_2023 | PEOPLEUSDT | survivor | 2023-06 | 997,549 | 0.5036 | 0.4954 | 0.5662 | 0.6028 | +0.0992 |
| cross_2023 | PERPUSDT | delisted | 2023-06 | 577,837 | 0.5164 | 0.6408 | 0.6531 | 0.6658 | +0.1494 |
| cross_2023 | PHBUSDT | delisted | 2023-06 | 1,414,233 | 0.5057 | 0.6172 | 0.6258 | 0.6416 | +0.1359 |
| cross_2023 | QNTUSDT | survivor | 2023-06 | 1,311,302 | 0.4881 | 0.6211 | 0.6322 | 0.6424 | +0.1542 |
| cross_2023 | QTUMUSDT | survivor | 2023-06 | 705,712 | 0.5248 | 0.5595 | 0.5914 | 0.6191 | +0.0944 |
| cross_2023 | RADUSDT | delisted | 2023-06 | 1,177,447 | 0.4877 | 0.6138 | 0.6334 | 0.6577 | +0.1700 |
| cross_2023 | RDNTUSDT | delisted | 2023-06 | 1,436,761 | 0.5074 | 0.5387 | 0.5711 | 0.6067 | +0.0993 |
| cross_2023 | REEFUSDT | delisted | 2023-06 | 575,870 | 0.5292 | 0.5945 | 0.6157 | 0.6326 | +0.1034 |
| cross_2023 | RENUSDT | delisted | 2023-06 | 2,313,468 | 0.4962 | 0.6059 | 0.6003 | 0.6179 | +0.1216 |
| cross_2023 | RLCUSDT | survivor | 2023-06 | 1,398,766 | 0.4997 | 0.6128 | 0.6123 | 0.6256 | +0.1259 |
| cross_2023 | RNDRUSDT | renamed | 2023-06 | 5,054,960 | 0.5016 | 0.6197 | 0.6195 | 0.6322 | +0.1306 |
| cross_2023 | ROSEUSDT | survivor | 2023-06 | 1,165,063 | 0.5053 | 0.5973 | 0.5972 | 0.6124 | +0.1071 |
| cross_2023 | RSRUSDT | survivor | 2023-06 | 887,261 | 0.5221 | 0.5702 | 0.5922 | 0.6119 | +0.0897 |
| cross_2023 | RUNEUSDT | survivor | 2023-06 | 631,519 | 0.5081 | 0.5948 | 0.6227 | 0.6342 | +0.1260 |
| cross_2023 | RVNUSDT | survivor | 2023-06 | 763,338 | 0.5160 | 0.5815 | 0.6026 | 0.6236 | +0.1076 |
| cross_2023 | SANDUSDT | survivor | 2023-06 | 2,732,112 | 0.4979 | 0.5447 | 0.5712 | 0.5939 | +0.0959 |
| cross_2023 | SFPUSDT | survivor | 2023-06 | 2,154,544 | 0.5125 | 0.4328 | 0.5614 | 0.6014 | +0.0888 |
| cross_2023 | SKLUSDT | survivor | 2023-06 | 778,602 | 0.5185 | 0.6074 | 0.6156 | 0.6343 | +0.1158 |
| cross_2023 | SNXUSDT | survivor | 2023-06 | 1,204,975 | 0.5154 | 0.5054 | 0.5620 | 0.5926 | +0.0773 |
| cross_2023 | SOLUSDT | survivor | 2023-06 | 6,820,337 | 0.5011 | 0.5379 | 0.5621 | 0.6062 | +0.1052 |
| cross_2023 | SPELLUSDT | survivor | 2023-06 | 780,629 | 0.4980 | 0.6181 | 0.6280 | 0.6401 | +0.1421 |
| cross_2023 | SSVUSDT | survivor | 2023-06 | 967,784 | 0.5095 | 0.5925 | 0.6047 | 0.6295 | +0.1200 |
| cross_2023 | STGUSDT | survivor | 2023-06 | 1,024,583 | 0.5069 | 0.5967 | 0.6096 | 0.6274 | +0.1205 |
| cross_2023 | STMXUSDT | delisted | 2023-06 | 658,360 | 0.5318 | 0.6388 | 0.6649 | 0.6777 | +0.1459 |
| cross_2023 | STORJUSDT | survivor | 2023-06 | 1,952,059 | 0.5158 | 0.4991 | 0.5699 | 0.6032 | +0.0874 |
| cross_2023 | STXUSDT | survivor | 2023-06 | 4,075,254 | 0.5044 | 0.5734 | 0.5613 | 0.5938 | +0.0894 |
| cross_2023 | SUIUSDT | survivor | 2023-06 | 6,074,349 | 0.5072 | 0.5304 | 0.5485 | 0.5837 | +0.0766 |
| cross_2023 | SUSHIUSDT | survivor | 2023-06 | 1,625,378 | 0.5053 | 0.6029 | 0.5937 | 0.6186 | +0.1133 |
| cross_2023 | SXPUSDT | delisted | 2023-06 | 2,001,787 | 0.5041 | 0.5411 | 0.5549 | 0.5828 | +0.0787 |
| cross_2023 | THETAUSDT | survivor | 2023-06 | 1,287,639 | 0.5114 | 0.5932 | 0.5985 | 0.6160 | +0.1046 |
| cross_2023 | TLMUSDT | survivor | 2023-06 | 437,865 | 0.5148 | 0.5993 | 0.6393 | 0.6565 | +0.1417 |
| cross_2023 | TOMOUSDT | delisted | 2023-06 | 9,258,867 | 0.5032 | 0.5483 | 0.5562 | 0.5964 | +0.0933 |
| cross_2023 | TRBUSDT | survivor | 2023-06 | 528,943 | 0.5162 | 0.5759 | 0.5990 | 0.6223 | +0.1061 |
| cross_2023 | TRUUSDT | delisted | 2023-06 | 2,059,642 | 0.5180 | 0.5945 | 0.6026 | 0.6248 | +0.1068 |
| cross_2023 | TRXUSDT | survivor | 2023-06 | 2,313,889 | 0.4900 | 0.4314 | 0.5868 | 0.6069 | +0.1169 |
| cross_2023 | TUSDT | survivor | 2023-06 | 1,188,607 | 0.5169 | 0.5290 | 0.5704 | 0.5963 | +0.0794 |
| cross_2023 | UMAUSDT | survivor | 2023-06 | 524,242 | 0.5175 | 0.6293 | 0.6576 | 0.6745 | +0.1570 |
| cross_2023 | UNFIUSDT | delisted | 2023-06 | 910,925 | 0.5180 | 0.5877 | 0.6047 | 0.6191 | +0.1011 |
| cross_2023 | UNIUSDT | survivor | 2023-06 | 1,765,940 | 0.5096 | 0.5314 | 0.5815 | 0.6058 | +0.0962 |
| cross_2023 | USDCUSDT | survivor | 2023-06 | 619,244 | 0.4424 | 0.7349 | 0.7636 | 0.7658 | +0.3234 |
| cross_2023 | VETUSDT | survivor | 2023-06 | 1,133,146 | 0.5177 | 0.5408 | 0.5896 | 0.6039 | +0.0862 |
| cross_2023 | WAVESUSDT | delisted | 2023-06 | 6,269,680 | 0.5095 | 0.5239 | 0.5377 | 0.5739 | +0.0644 |
| cross_2023 | WOOUSDT | survivor | 2023-06 | 2,182,934 | 0.5042 | 0.6197 | 0.6223 | 0.6342 | +0.1300 |
| cross_2023 | XEMUSDT | delisted | 2023-06 | 708,385 | 0.5309 | 0.6167 | 0.6357 | 0.6434 | +0.1125 |
| cross_2023 | XLMUSDT | survivor | 2023-06 | 1,906,268 | 0.5075 | 0.5335 | 0.5536 | 0.5859 | +0.0783 |
| cross_2023 | XMRUSDT | survivor | 2023-06 | 1,838,222 | 0.4923 | 0.6115 | 0.6136 | 0.6322 | +0.1399 |
| cross_2023 | XRPUSDT | survivor | 2023-06 | 7,617,768 | 0.4815 | 0.5157 | 0.5725 | 0.5930 | +0.1114 |
| cross_2023 | XTZUSDT | survivor | 2023-06 | 748,247 | 0.5213 | 0.5630 | 0.6193 | 0.6384 | +0.1172 |
| cross_2023 | XVSUSDT | survivor | 2023-06 | 525,608 | 0.5002 | 0.6294 | 0.6435 | 0.6606 | +0.1604 |
| cross_2023 | YFIUSDT | survivor | 2023-06 | 1,071,320 | 0.5089 | 0.6107 | 0.6190 | 0.6365 | +0.1276 |
| cross_2023 | ZECUSDT | survivor | 2023-06 | 950,492 | 0.5249 | 0.5596 | 0.5850 | 0.6118 | +0.0869 |
| cross_2023 | ZENUSDT | survivor | 2023-06 | 1,107,250 | 0.5084 | 0.5635 | 0.5767 | 0.5910 | +0.0826 |
| cross_2023 | ZILUSDT | survivor | 2023-06 | 938,528 | 0.5104 | 0.5457 | 0.5833 | 0.5952 | +0.0848 |
| cross_2023 | ZRXUSDT | survivor | 2023-06 | 656,595 | 0.5499 | 0.5789 | 0.6187 | 0.6342 | +0.0842 |
| last_month | AGIXUSDT | merged | 2024-05 | 2,822,017 | 0.5050 | 0.6370 | 0.6373 | 0.6439 | +0.1389 |
| last_month | ALPHAUSDT | delisted | 2025-08 | 703,719 | 0.5152 | 0.5953 | 0.6200 | 0.6252 | +0.1100 |
| last_month | AMBUSDT | delisted | 2025-01 | 1,047,441 | 0.5177 | 0.6364 | 0.6386 | 0.6415 | +0.1239 |
| last_month | ANTUSDT | delisted | 2024-03 | 884,156 | 0.5086 | 0.6260 | 0.6283 | 0.6356 | +0.1270 |
| last_month | ATAUSDT | delisted | 2026-04 | 531,987 | 0.5299 | 0.5730 | 0.6026 | 0.6128 | +0.0828 |
| last_month | AUDIOUSDT | delisted | 2024-04 | 888,860 | 0.5122 | 0.5780 | 0.5882 | 0.5991 | +0.0869 |
| last_month | BAKEUSDT | delisted | 2025-09 | 5,167,475 | 0.4883 | 0.5051 | 0.5769 | 0.5930 | +0.1047 |
| last_month | BALUSDT | delisted | 2025-03 | 463,243 | 0.4701 | 0.5949 | 0.6146 | 0.6197 | +0.1496 |
| last_month | BLZUSDT | delisted | 2024-11 | 1,656,931 | 0.5092 | 0.6899 | 0.6903 | 0.6951 | +0.1859 |
| last_month | BNXUSDT | renamed | 2025-02 | 12,406,229 | 0.4876 | 0.3565 | 0.5774 | 0.6111 | +0.1235 |
| last_month | COMBOUSDT | delisted | 2025-02 | 750,015 | 0.4860 | 0.6100 | 0.6078 | 0.6154 | +0.1294 |
| last_month | DARUSDT | renamed | 2024-11 | 798,187 | 0.5106 | 0.5775 | 0.5809 | 0.5916 | +0.0810 |
| last_month | DENTUSDT | delisted | 2026-03 | 1,446,680 | 0.4879 | 0.5891 | 0.6668 | 0.6716 | +0.1837 |
| last_month | DGBUSDT | delisted | 2024-03 | 944,512 | 0.4996 | 0.5633 | 0.5758 | 0.5792 | +0.0797 |
| last_month | EOSUSDT | renamed | 2025-04 | 3,357,680 | 0.5109 | 0.5906 | 0.6145 | 0.6321 | +0.1211 |
| last_month | FLMUSDT | delisted | 2025-10 | 903,965 | 0.5064 | 0.4345 | 0.5685 | 0.5673 | +0.0609 |
| last_month | FTMUSDT | renamed | 2024-12 | 8,939,384 | 0.4942 | 0.6052 | 0.6186 | 0.6322 | +0.1380 |
| last_month | FXSUSDT | renamed | 2025-12 | 528,538 | 0.4907 | 0.6523 | 0.6574 | 0.6655 | +0.1748 |
| last_month | GALUSDT | renamed | 2024-06 | 1,019,534 | 0.5081 | 0.6820 | 0.6820 | 0.6837 | +0.1756 |
| last_month | HIGHUSDT | delisted | 2026-05 | 1,408,233 | 0.4884 | 0.5508 | 0.5944 | 0.6061 | +0.1177 |
| last_month | HOOKUSDT | delisted | 2026-02 | 425,826 | 0.5072 | 0.5962 | 0.5972 | 0.6105 | +0.1033 |
| last_month | IDEXUSDT | delisted | 2024-04 | 1,423,149 | 0.5066 | 0.6339 | 0.6340 | 0.6398 | +0.1332 |
| last_month | KEYUSDT | delisted | 2024-11 | 2,369,599 | 0.5037 | 0.6349 | 0.6349 | 0.6413 | +0.1376 |
| last_month | KLAYUSDT | renamed | 2024-09 | 343,523 | 0.5017 | 0.5571 | 0.5829 | 0.5931 | +0.0914 |
| last_month | LEVERUSDT | delisted | 2025-08 | 1,355,790 | 0.5325 | 0.5686 | 0.6156 | 0.6332 | +0.1007 |
| last_month | LINAUSDT | delisted | 2025-02 | 535,152 | 0.5187 | 0.5782 | 0.6219 | 0.6316 | +0.1129 |
| last_month | LRCUSDT | delisted | 2026-02 | 804,731 | 0.5032 | 0.6096 | 0.6098 | 0.6153 | +0.1121 |
| last_month | MATICUSDT | renamed | 2024-08 | 3,320,249 | 0.5384 | 0.5782 | 0.6438 | 0.6500 | +0.1115 |
| last_month | MKRUSDT | renamed | 2025-08 | 2,295,934 | 0.4837 | 0.7195 | 0.7196 | 0.7227 | +0.2390 |
| last_month | NKNUSDT | delisted | 2026-01 | 392,437 | 0.5110 | 0.5692 | 0.6025 | 0.6084 | +0.0974 |
| last_month | OCEANUSDT | merged | 2024-05 | 2,067,636 | 0.4948 | 0.6485 | 0.6488 | 0.6541 | +0.1593 |
| last_month | OMGUSDT | delisted | 2025-01 | 639,378 | 0.4249 | 0.6776 | 0.6781 | 0.6854 | +0.2605 |
| last_month | PERPUSDT | delisted | 2025-10 | 686,569 | 0.5053 | 0.5712 | 0.5774 | 0.5908 | +0.0855 |
| last_month | PHBUSDT | delisted | 2026-04 | 1,216,736 | 0.4523 | 0.5587 | 0.5875 | 0.5974 | +0.1451 |
| last_month | RADUSDT | delisted | 2024-04 | 1,393,848 | 0.4948 | 0.6701 | 0.6701 | 0.6716 | +0.1767 |
| last_month | RDNTUSDT | delisted | 2026-02 | 435,347 | 0.4042 | 0.6568 | 0.6602 | 0.6729 | +0.2686 |
| last_month | REEFUSDT | delisted | 2024-12 | 1,272,089 | 0.4753 | 0.5875 | 0.6105 | 0.6150 | +0.1397 |
| last_month | RENUSDT | delisted | 2024-11 | 2,315,963 | 0.5102 | 0.5781 | 0.5841 | 0.5985 | +0.0883 |
| last_month | RNDRUSDT | renamed | 2024-06 | 4,836,169 | 0.5076 | 0.6814 | 0.6805 | 0.6852 | +0.1776 |
| last_month | STMXUSDT | delisted | 2025-01 | 792,544 | 0.4803 | 0.5414 | 0.5787 | 0.6195 | +0.1392 |
| last_month | SXPUSDT | delisted | 2025-11 | 578,313 | 0.4459 | 0.6106 | 0.6536 | 0.6549 | +0.2091 |
| last_month | TOMOUSDT | delisted | 2023-10 | 2,934,859 | 0.5004 | 0.6347 | 0.6295 | 0.6428 | +0.1425 |
| last_month | TRUUSDT | delisted | 2026-03 | 829,741 | 0.4840 | 0.6206 | 0.6295 | 0.6374 | +0.1534 |
| last_month | UNFIUSDT | delisted | 2024-09 | 672,069 | 0.4986 | 0.5181 | 0.5293 | 0.5385 | +0.0399 |
| last_month | WAVESUSDT | delisted | 2024-05 | 1,904,163 | 0.5089 | 0.6759 | 0.6757 | 0.6782 | +0.1693 |
| last_month | XEMUSDT | delisted | 2024-11 | 524,957 | 0.5017 | 0.5496 | 0.6043 | 0.6311 | +0.1294 |
| cross_2026 | 1000FLOKIUSDT | survivor | 2026-07 | 589,155 | 0.5280 | 0.5766 | 0.6284 | 0.6700 | +0.1420 |
| cross_2026 | 1000LUNCUSDT | survivor | 2026-07 | 919,921 | 0.5438 | 0.6868 | 0.7153 | 0.7216 | +0.1777 |
| cross_2026 | 1000PEPEUSDT | survivor | 2026-07 | 5,365,105 | 0.5016 | 0.6645 | 0.6663 | 0.6845 | +0.1829 |
| cross_2026 | 1000SHIBUSDT | survivor | 2026-07 | 2,476,365 | 0.5015 | 0.5199 | 0.5610 | 0.5748 | +0.0733 |
| cross_2026 | 1000XECUSDT | survivor | 2026-07 | 3,180,158 | 0.4896 | 0.6424 | 0.6415 | 0.6589 | +0.1693 |
| cross_2026 | 1INCHUSDT | survivor | 2026-07 | 462,887 | 0.5045 | 0.7174 | 0.7099 | 0.7180 | +0.2135 |
| cross_2026 | AAVEUSDT | survivor | 2026-07 | 3,059,256 | 0.4978 | 0.5935 | 0.6102 | 0.6304 | +0.1327 |
| cross_2026 | ACHUSDT | survivor | 2026-07 | 920,286 | 0.4901 | 0.6418 | 0.6469 | 0.6498 | +0.1597 |
| cross_2026 | ADAUSDT | survivor | 2026-07 | 2,556,427 | 0.5239 | 0.5505 | 0.6256 | 0.6318 | +0.1079 |
| cross_2026 | ALGOUSDT | survivor | 2026-07 | 670,866 | 0.5204 | 0.6504 | 0.6250 | 0.6112 | +0.0907 |
| cross_2026 | ALICEUSDT | survivor | 2026-07 | 696,119 | 0.4962 | 0.5610 | 0.5889 | 0.5958 | +0.0996 |
| cross_2026 | ANKRUSDT | survivor | 2026-07 | 533,868 | 0.5216 | 0.6038 | 0.6146 | 0.6227 | +0.1011 |
| cross_2026 | APEUSDT | survivor | 2026-07 | 667,991 | 0.4843 | 0.5645 | 0.5994 | 0.6114 | +0.1271 |
| cross_2026 | API3USDT | survivor | 2026-07 | 584,072 | 0.4879 | 0.6465 | 0.6804 | 0.6923 | +0.2044 |
| cross_2026 | APTUSDT | survivor | 2026-07 | 1,688,194 | 0.4620 | 0.6039 | 0.6360 | 0.6442 | +0.1822 |
| cross_2026 | ARBUSDT | survivor | 2026-07 | 2,487,974 | 0.4785 | 0.5915 | 0.6157 | 0.6267 | +0.1482 |
| cross_2026 | ARPAUSDT | survivor | 2026-07 | 1,107,056 | 0.4509 | 0.3677 | 0.5363 | 0.5367 | +0.0858 |
| cross_2026 | ARUSDT | survivor | 2026-07 | 354,017 | 0.4579 | 0.5956 | 0.6367 | 0.6411 | +0.1832 |
| cross_2026 | ASTRUSDT | survivor | 2026-07 | 240,509 | 0.5052 | 0.6204 | 0.6182 | 0.6260 | +0.1208 |
| cross_2026 | ATOMUSDT | survivor | 2026-07 | 837,588 | 0.5218 | 0.5808 | 0.6494 | 0.6534 | +0.1316 |
| cross_2026 | AVAXUSDT | survivor | 2026-07 | 2,595,579 | 0.4948 | 0.5786 | 0.6384 | 0.6498 | +0.1550 |
| cross_2026 | AXSUSDT | survivor | 2026-07 | 487,196 | 0.4579 | 0.5584 | 0.6024 | 0.6085 | +0.1506 |
| cross_2026 | BANDUSDT | survivor | 2026-07 | 258,105 | 0.5001 | 0.5745 | 0.5782 | 0.5857 | +0.0856 |
| cross_2026 | BATUSDT | survivor | 2026-07 | 232,569 | 0.5174 | 0.6874 | 0.6226 | 0.6070 | +0.0896 |
| cross_2026 | BCHUSDT | survivor | 2026-07 | 3,266,519 | 0.5134 | 0.6686 | 0.6559 | 0.6860 | +0.1726 |
| cross_2026 | BELUSDT | survivor | 2026-07 | 2,086,811 | 0.4740 | 0.6466 | 0.6462 | 0.6545 | +0.1805 |
| cross_2026 | BLURUSDT | survivor | 2026-07 | 1,467,831 | 0.4851 | 0.4141 | 0.6256 | 0.6328 | +0.1477 |
| cross_2026 | BNBUSDT | survivor | 2026-07 | 4,812,418 | 0.5338 | 0.5826 | 0.6275 | 0.6500 | +0.1162 |
| cross_2026 | BTCDOMUSDT | survivor | 2026-07 | 323,670 | 0.4965 | 0.6295 | 0.6488 | 0.6531 | +0.1566 |
| cross_2026 | BTCUSDT | survivor | 2026-07 | 14,577,970 | 0.5015 | 0.5240 | 0.6449 | 0.6816 | +0.1801 |
| cross_2026 | C98USDT | survivor | 2026-07 | 337,784 | 0.7535 | 0.7603 | 0.8008 | 0.8043 | +0.0508 |
| cross_2026 | CELOUSDT | survivor | 2026-07 | 803,131 | 0.4998 | 0.6266 | 0.6266 | 0.6323 | +0.1325 |
| cross_2026 | CELRUSDT | survivor | 2026-07 | 267,653 | 0.5836 | 0.6405 | 0.6744 | 0.6784 | +0.0947 |
| cross_2026 | CFXUSDT | survivor | 2026-07 | 642,676 | 0.5418 | 0.5829 | 0.5942 | 0.6040 | +0.0622 |
| cross_2026 | CHRUSDT | survivor | 2026-07 | 1,297,094 | 0.8802 | 0.8170 | 0.8947 | 0.8949 | +0.0147 |
| cross_2026 | CHZUSDT | survivor | 2026-07 | 763,155 | 0.5164 | 0.5631 | 0.6101 | 0.6140 | +0.0976 |
| cross_2026 | CKBUSDT | survivor | 2026-07 | 181,212 | 0.4925 | 0.5817 | 0.6012 | 0.6120 | +0.1195 |
| cross_2026 | COMPUSDT | survivor | 2026-07 | 252,556 | 0.5648 | 0.6589 | 0.6831 | 0.6882 | +0.1234 |
| cross_2026 | COTIUSDT | survivor | 2026-07 | 5,823,097 | 0.5136 | 0.6085 | 0.5819 | 0.5763 | +0.0627 |
| cross_2026 | CRVUSDT | survivor | 2026-07 | 718,109 | 0.5152 | 0.5710 | 0.6052 | 0.6128 | +0.0976 |
| cross_2026 | CTKUSDT | survivor_gap | 2026-07 | 275,273 | 0.2344 | 0.7452 | 0.8060 | 0.8080 | +0.5736 |
| cross_2026 | CTSIUSDT | survivor | 2026-07 | 286,784 | 0.5120 | 0.5768 | 0.5840 | 0.5941 | +0.0821 |
| cross_2026 | CVXUSDT | survivor_gap | 2026-07 | 219,682 | 0.5170 | 0.5867 | 0.5939 | 0.6041 | +0.0871 |
| cross_2026 | DASHUSDT | survivor | 2026-07 | 1,214,246 | 0.5046 | 0.5724 | 0.6362 | 0.6402 | +0.1355 |
| cross_2026 | DOGEUSDT | survivor | 2026-07 | 3,576,542 | 0.5268 | 0.5351 | 0.6030 | 0.6153 | +0.0885 |
| cross_2026 | DOTUSDT | survivor | 2026-07 | 1,583,073 | 0.4867 | 0.5912 | 0.6243 | 0.6228 | +0.1361 |
| cross_2026 | DUSKUSDT | survivor | 2026-07 | 457,845 | 0.5018 | 0.6671 | 0.6671 | 0.6699 | +0.1681 |
| cross_2026 | DYDXUSDT | survivor | 2026-07 | 1,574,024 | 0.4960 | 0.6039 | 0.6493 | 0.6544 | +0.1584 |
| cross_2026 | EDUUSDT | survivor | 2026-07 | 438,257 | 0.4828 | 0.6305 | 0.6352 | 0.6427 | +0.1599 |
| cross_2026 | EGLDUSDT | survivor | 2026-07 | 633,139 | 0.5520 | 0.6209 | 0.6436 | 0.6517 | +0.0997 |
| cross_2026 | ENJUSDT | survivor | 2026-07 | 501,690 | 0.5209 | 0.6059 | 0.6212 | 0.6289 | +0.1080 |
| cross_2026 | ENSUSDT | survivor | 2026-07 | 574,194 | 0.4764 | 0.6277 | 0.6263 | 0.6325 | +0.1561 |
| cross_2026 | ETCUSDT | survivor | 2026-07 | 1,009,838 | 0.5043 | 0.6069 | 0.6323 | 0.6440 | +0.1397 |
| cross_2026 | ETHUSDT | survivor | 2026-07 | 15,881,884 | 0.5001 | 0.5482 | 0.6380 | 0.6832 | +0.1831 |
| cross_2026 | FETUSDT | survivor | 2026-07 | 1,268,156 | 0.5354 | 0.5937 | 0.6726 | 0.6752 | +0.1399 |
| cross_2026 | FILUSDT | survivor | 2026-07 | 2,039,489 | 0.4769 | 0.5920 | 0.6332 | 0.6436 | +0.1667 |
| cross_2026 | FLOWUSDT | survivor | 2026-07 | 381,150 | 0.4991 | 0.5937 | 0.5910 | 0.5937 | +0.0946 |
| cross_2026 | GALAUSDT | survivor | 2026-07 | 849,002 | 0.4638 | 0.5604 | 0.6162 | 0.6221 | +0.1583 |
| cross_2026 | GMTUSDT | survivor | 2026-07 | 360,680 | 0.5004 | 0.6922 | 0.6093 | 0.5903 | +0.0899 |
| cross_2026 | GMXUSDT | survivor | 2026-07 | 380,199 | 0.5040 | 0.6958 | 0.6918 | 0.6948 | +0.1909 |
| cross_2026 | GRTUSDT | survivor | 2026-07 | 293,204 | 0.4974 | 0.6158 | 0.6438 | 0.6477 | +0.1503 |
| cross_2026 | GTCUSDT | survivor | 2026-07 | 435,934 | 0.4930 | 0.6387 | 0.6376 | 0.6458 | +0.1527 |
| cross_2026 | HBARUSDT | survivor | 2026-07 | 1,495,534 | 0.5115 | 0.6131 | 0.6358 | 0.6424 | +0.1309 |
| cross_2026 | HFTUSDT | survivor | 2026-07 | 361,980 | 0.4962 | 0.6003 | 0.6210 | 0.6291 | +0.1328 |
| cross_2026 | HOTUSDT | survivor | 2026-07 | 947,496 | 0.4876 | 0.6339 | 0.6499 | 0.6594 | +0.1718 |
| cross_2026 | ICPUSDT | survivor | 2026-07 | 994,228 | 0.5411 | 0.5825 | 0.6347 | 0.6399 | +0.0988 |
| cross_2026 | ICXUSDT | survivor | 2026-07 | 227,240 | 0.5272 | 0.5871 | 0.5909 | 0.5987 | +0.0716 |
| cross_2026 | IDUSDT | survivor | 2026-07 | 1,322,588 | 0.5442 | 0.6060 | 0.6316 | 0.6463 | +0.1022 |
| cross_2026 | IMXUSDT | survivor | 2026-07 | 345,265 | 0.5203 | 0.5949 | 0.6288 | 0.6296 | +0.1092 |
| cross_2026 | INJUSDT | survivor | 2026-07 | 2,072,492 | 0.5124 | 0.5812 | 0.6332 | 0.6434 | +0.1311 |
| cross_2026 | IOSTUSDT | survivor | 2026-07 | 434,230 | 0.5735 | 0.6930 | 0.7086 | 0.7132 | +0.1397 |
| cross_2026 | IOTAUSDT | survivor | 2026-07 | 623,810 | 0.4938 | 0.6290 | 0.6458 | 0.6532 | +0.1594 |
| cross_2026 | IOTXUSDT | survivor | 2026-07 | 347,226 | 0.4858 | 0.6205 | 0.6269 | 0.6378 | +0.1521 |
| cross_2026 | JASMYUSDT | survivor | 2026-07 | 546,964 | 0.6016 | 0.6876 | 0.6949 | 0.7015 | +0.0999 |
| cross_2026 | JOEUSDT | survivor | 2026-07 | 261,908 | 0.4975 | 0.6002 | 0.6110 | 0.6207 | +0.1232 |
| cross_2026 | KAVAUSDT | survivor | 2026-07 | 271,865 | 0.5158 | 0.6156 | 0.6206 | 0.6302 | +0.1145 |
| cross_2026 | KNCUSDT | survivor | 2026-07 | 175,561 | 0.5361 | 0.5701 | 0.6053 | 0.6129 | +0.0768 |
| cross_2026 | KSMUSDT | survivor | 2026-07 | 316,150 | 0.4998 | 0.5904 | 0.5924 | 0.6032 | +0.1035 |
| cross_2026 | LDOUSDT | survivor | 2026-07 | 1,404,621 | 0.4954 | 0.5995 | 0.6249 | 0.6348 | +0.1394 |
| cross_2026 | LINKUSDT | survivor | 2026-07 | 1,730,243 | 0.4967 | 0.5823 | 0.5986 | 0.6136 | +0.1169 |
| cross_2026 | LITUSDT | survivor_gap | 2026-07 | 6,633,120 | 0.5124 | 0.7100 | 0.7102 | 0.7200 | +0.2077 |
| cross_2026 | LPTUSDT | survivor | 2026-07 | 410,648 | 0.4770 | 0.5948 | 0.6483 | 0.6502 | +0.1732 |
| cross_2026 | LQTYUSDT | survivor | 2026-07 | 301,348 | 0.5184 | 0.6161 | 0.6141 | 0.6217 | +0.1033 |
| cross_2026 | LTCUSDT | survivor | 2026-07 | 1,262,846 | 0.5043 | 0.5674 | 0.6055 | 0.6116 | +0.1073 |
| cross_2026 | LUNA2USDT | survivor | 2026-07 | 369,214 | 0.4742 | 0.6673 | 0.6780 | 0.6849 | +0.2107 |
| cross_2026 | MAGICUSDT | survivor | 2026-07 | 406,652 | 0.4881 | 0.6171 | 0.6175 | 0.6240 | +0.1360 |
| cross_2026 | MANAUSDT | survivor | 2026-07 | 719,991 | 0.5166 | 0.6876 | 0.6750 | 0.6886 | +0.1720 |
| cross_2026 | MASKUSDT | survivor | 2026-07 | 360,294 | 0.4940 | 0.6151 | 0.6167 | 0.6236 | +0.1296 |
| cross_2026 | MAVUSDT | survivor | 2026-07 | 345,837 | 0.5153 | 0.5789 | 0.6095 | 0.6147 | +0.0994 |
| cross_2026 | MINAUSDT | survivor | 2026-07 | 489,846 | 0.5126 | 0.6349 | 0.6408 | 0.6473 | +0.1347 |
| cross_2026 | MTLUSDT | survivor | 2026-07 | 178,253 | 0.5016 | 0.5970 | 0.6034 | 0.6174 | +0.1157 |
| cross_2026 | NEARUSDT | survivor | 2026-07 | 2,461,947 | 0.4885 | 0.5466 | 0.6321 | 0.6354 | +0.1468 |
| cross_2026 | NEOUSDT | survivor | 2026-07 | 342,698 | 0.4842 | 0.6173 | 0.6434 | 0.6448 | +0.1607 |
| cross_2026 | NMRUSDT | survivor | 2026-07 | 460,929 | 0.5286 | 0.6496 | 0.6496 | 0.6580 | +0.1294 |
| cross_2026 | OGNUSDT | survivor | 2026-07 | 958,354 | 0.4806 | 0.5732 | 0.6083 | 0.6139 | +0.1332 |
| cross_2026 | ONEUSDT | survivor | 2026-07 | 745,972 | 0.4817 | 0.5868 | 0.6182 | 0.6221 | +0.1404 |
| cross_2026 | ONTUSDT | survivor | 2026-07 | 339,660 | 0.4954 | 0.6647 | 0.6708 | 0.6776 | +0.1822 |
| cross_2026 | OPUSDT | survivor | 2026-07 | 1,124,589 | 0.5288 | 0.5807 | 0.6592 | 0.6617 | +0.1329 |
| cross_2026 | PEOPLEUSDT | survivor | 2026-07 | 983,649 | 0.4941 | 0.6815 | 0.6816 | 0.6850 | +0.1909 |
| cross_2026 | QNTUSDT | survivor | 2026-07 | 400,838 | 0.5123 | 0.6296 | 0.6377 | 0.6509 | +0.1386 |
| cross_2026 | QTUMUSDT | survivor | 2026-07 | 495,422 | 0.6009 | 0.7112 | 0.7225 | 0.7278 | +0.1269 |
| cross_2026 | RLCUSDT | survivor | 2026-07 | 358,385 | 0.4860 | 0.5993 | 0.6027 | 0.6121 | +0.1261 |
| cross_2026 | ROSEUSDT | survivor | 2026-07 | 531,017 | 0.4612 | 0.6862 | 0.6892 | 0.6906 | +0.2294 |
| cross_2026 | RSRUSDT | survivor | 2026-07 | 268,529 | 0.5183 | 0.6083 | 0.6214 | 0.6344 | +0.1161 |
| cross_2026 | RUNEUSDT | survivor | 2026-07 | 382,080 | 0.5129 | 0.6188 | 0.6215 | 0.6285 | +0.1156 |
| cross_2026 | RVNUSDT | survivor | 2026-07 | 418,651 | 0.5327 | 0.6154 | 0.6212 | 0.6326 | +0.0999 |
| cross_2026 | SANDUSDT | survivor | 2026-07 | 727,999 | 0.5124 | 0.6189 | 0.6375 | 0.6437 | +0.1313 |
| cross_2026 | SFPUSDT | survivor | 2026-07 | 231,105 | 0.4994 | 0.5980 | 0.6011 | 0.6144 | +0.1150 |
| cross_2026 | SKLUSDT | survivor | 2026-07 | 2,532,502 | 0.4640 | 0.5977 | 0.6303 | 0.6410 | +0.1770 |
| cross_2026 | SNXUSDT | survivor | 2026-07 | 602,240 | 0.5001 | 0.6246 | 0.6535 | 0.6595 | +0.1594 |
| cross_2026 | SOLUSDT | survivor | 2026-07 | 6,549,774 | 0.4946 | 0.5230 | 0.6186 | 0.6254 | +0.1308 |
| cross_2026 | SPELLUSDT | survivor | 2026-07 | 994,093 | 0.5197 | 0.7044 | 0.7527 | 0.7569 | +0.2372 |
| cross_2026 | SSVUSDT | survivor | 2026-07 | 229,511 | 0.4944 | 0.6274 | 0.6267 | 0.6390 | +0.1446 |
| cross_2026 | STGUSDT | survivor | 2026-07 | 830,723 | 0.4368 | 0.6520 | 0.6935 | 0.6995 | +0.2627 |
| cross_2026 | STORJUSDT | survivor | 2026-07 | 697,656 | 0.4809 | 0.6184 | 0.6268 | 0.6339 | +0.1529 |
| cross_2026 | STXUSDT | survivor | 2026-07 | 756,215 | 0.2708 | 0.6654 | 0.7607 | 0.7632 | +0.4924 |
| cross_2026 | SUIUSDT | survivor | 2026-07 | 2,557,444 | 0.4873 | 0.5533 | 0.6068 | 0.6143 | +0.1270 |
| cross_2026 | SUSHIUSDT | survivor | 2026-07 | 281,617 | 0.4703 | 0.5960 | 0.6299 | 0.6342 | +0.1639 |
| cross_2026 | THETAUSDT | survivor | 2026-07 | 423,345 | 0.5519 | 0.6839 | 0.7210 | 0.7252 | +0.1733 |
| cross_2026 | TLMUSDT | survivor | 2026-07 | 6,477,040 | 0.5056 | 0.4280 | 0.6133 | 0.6263 | +0.1207 |
| cross_2026 | TRBUSDT | survivor | 2026-07 | 1,478,896 | 0.4969 | 0.7175 | 0.7175 | 0.7208 | +0.2239 |
| cross_2026 | TRXUSDT | survivor | 2026-07 | 1,769,424 | 0.5121 | 0.5999 | 0.6587 | 0.6667 | +0.1546 |
| cross_2026 | TUSDT | survivor | 2026-07 | 2,805,879 | 0.4907 | 0.5958 | 0.6171 | 0.6344 | +0.1436 |
| cross_2026 | UMAUSDT | survivor | 2026-07 | 313,914 | 0.4536 | 0.6263 | 0.6421 | 0.6526 | +0.1989 |
| cross_2026 | UNIUSDT | survivor | 2026-07 | 2,419,759 | 0.5145 | 0.5535 | 0.6115 | 0.6239 | +0.1094 |
| cross_2026 | USDCUSDT | survivor | 2026-07 | 664,009 | 0.5085 | 0.4131 | 0.6588 | 0.6666 | +0.1581 |
| cross_2026 | VETUSDT | survivor | 2026-07 | 497,001 | 0.4670 | 0.6406 | 0.6532 | 0.6597 | +0.1927 |
| cross_2026 | WOOUSDT | survivor | 2026-07 | 246,613 | 0.4809 | 0.5821 | 0.5996 | 0.6057 | +0.1249 |
| cross_2026 | XLMUSDT | survivor | 2026-07 | 3,582,124 | 0.4922 | 0.6395 | 0.6463 | 0.6668 | +0.1746 |
| cross_2026 | XMRUSDT | survivor | 2026-07 | 2,132,872 | 0.4978 | 0.6740 | 0.6745 | 0.6861 | +0.1883 |
| cross_2026 | XRPUSDT | survivor | 2026-07 | 4,561,673 | 0.5147 | 0.5314 | 0.6189 | 0.6282 | +0.1135 |
| cross_2026 | XTZUSDT | survivor | 2026-07 | 409,962 | 0.5104 | 0.6101 | 0.6281 | 0.6338 | +0.1234 |
| cross_2026 | XVSUSDT | survivor | 2026-07 | 209,490 | 0.4909 | 0.6197 | 0.6184 | 0.6341 | +0.1432 |
| cross_2026 | YFIUSDT | survivor | 2026-07 | 1,001,164 | 0.4545 | 0.5624 | 0.5914 | 0.5975 | +0.1430 |
| cross_2026 | ZECUSDT | survivor | 2026-07 | 10,743,966 | 0.4870 | 0.6864 | 0.6882 | 0.7097 | +0.2228 |
| cross_2026 | ZENUSDT | survivor | 2026-07 | 587,443 | 0.4958 | 0.6355 | 0.6577 | 0.6627 | +0.1669 |
| cross_2026 | ZILUSDT | survivor | 2026-07 | 890,921 | 0.4846 | 0.5519 | 0.5826 | 0.5931 | +0.1086 |
| cross_2026 | ZRXUSDT | survivor | 2026-07 | 178,269 | 0.6745 | 0.6910 | 0.7256 | 0.7332 | +0.0587 |
| cross_2026 | ALLUSDT | new_listing | 2026-07 | 98,983 | 0.4846 | 0.6234 | 0.6121 | 0.6243 | +0.1397 |
| cross_2026 | HPEUSDT | new_listing_equity | 2026-07 | 106,613 | 0.4528 | 0.6549 | 0.6507 | 0.6614 | +0.2086 |
| cross_2026 | ARKUSDT | new_listing | 2026-07 | 186,663 | 0.4234 | 0.6219 | 0.6505 | 0.6587 | +0.2353 |
| cross_2026 | 1000000MOGUSDT | new_listing | 2026-07 | 186,781 | 0.6165 | 0.6775 | 0.7017 | 0.7036 | +0.0871 |
| cross_2026 | FLNCUSDT | new_listing_equity | 2026-07 | 211,862 | 0.4926 | 0.5902 | 0.5950 | 0.6033 | +0.1106 |
| cross_2026 | STEEMUSDT | new_listing | 2026-07 | 221,243 | 0.5141 | 0.6144 | 0.6191 | 0.6276 | +0.1136 |
| cross_2026 | BSVUSDT | new_listing | 2026-07 | 259,034 | 0.4923 | 0.6175 | 0.6216 | 0.6308 | +0.1385 |
| cross_2026 | REDUSDT | new_listing | 2026-07 | 252,191 | 0.5030 | 0.5918 | 0.6040 | 0.6114 | +0.1083 |
| cross_2026 | METISUSDT | new_listing | 2026-07 | 235,915 | 0.5132 | 0.5774 | 0.5962 | 0.6066 | +0.0934 |
| cross_2026 | PROVEUSDT | new_listing | 2026-07 | 263,950 | 0.4801 | 0.6126 | 0.6323 | 0.6387 | +0.1586 |
| cross_2026 | AEVOUSDT | new_listing | 2026-07 | 243,480 | 0.5164 | 0.5745 | 0.5812 | 0.5928 | +0.0764 |
| cross_2026 | ALABUSDT | new_listing_equity | 2026-07 | 171,458 | 0.5052 | 0.7240 | 0.7201 | 0.7261 | +0.2209 |
| cross_2026 | SPKUSDT | new_listing | 2026-07 | 281,109 | 0.5067 | 0.6023 | 0.6321 | 0.6388 | +0.1321 |
| cross_2026 | BEAMXUSDT | new_listing | 2026-07 | 262,938 | 0.4655 | 0.6019 | 0.6098 | 0.6210 | +0.1555 |
| cross_2026 | HIVEUSDT | new_listing | 2026-07 | 257,133 | 0.4945 | 0.6100 | 0.6089 | 0.6195 | +0.1251 |
| cross_2026 | AIXBTUSDT | new_listing | 2026-07 | 274,992 | 0.4871 | 0.5846 | 0.5995 | 0.6080 | +0.1208 |
| cross_2026 | KAIAUSDT | new_listing | 2026-07 | 272,934 | 0.5006 | 0.5759 | 0.5790 | 0.5901 | +0.0896 |
| cross_2026 | 1000CATUSDT | new_listing | 2026-07 | 286,200 | 0.4981 | 0.5653 | 0.5946 | 0.6052 | +0.1071 |
| cross_2026 | GOATUSDT | new_listing | 2026-07 | 285,229 | 0.5181 | 0.5632 | 0.5745 | 0.5884 | +0.0703 |
| cross_2026 | DEEPUSDT | new_listing | 2026-07 | 281,100 | 0.4532 | 0.5588 | 0.5700 | 0.5824 | +0.1292 |
| cross_2026 | FORMUSDT | new_listing | 2026-07 | 319,545 | 0.5071 | 0.6298 | 0.6351 | 0.6453 | +0.1382 |
| cross_2026 | WCTUSDT | new_listing | 2026-07 | 310,856 | 0.5920 | 0.6782 | 0.6902 | 0.6943 | +0.1024 |
| cross_2026 | MERLUSDT | new_listing | 2026-07 | 314,085 | 0.5127 | 0.5949 | 0.6026 | 0.6129 | +0.1002 |
| cross_2026 | 1000SATSUSDT | new_listing | 2026-07 | 322,061 | 0.3178 | 0.6780 | 0.7431 | 0.7461 | +0.4283 |
| cross_2026 | ASMLUSDT | new_listing_equity | 2026-07 | 249,449 | 0.4903 | 0.7506 | 0.7464 | 0.7497 | +0.2594 |
| cross_2026 | VELODROMEUSDT | new_listing | 2026-07 | 337,650 | 0.5598 | 0.6412 | 0.6548 | 0.6607 | +0.1009 |
| cross_2026 | CRDOUSDT | new_listing_equity | 2026-07 | 250,768 | 0.5026 | 0.7323 | 0.7322 | 0.7330 | +0.2304 |
| cross_2026 | SQQQUSDT | new_listing_equity | 2026-07 | 385,215 | 0.5058 | 0.6306 | 0.6410 | 0.6574 | +0.1516 |
| cross_2026 | CFGUSDT | new_listing | 2026-07 | 381,504 | 0.5072 | 0.5941 | 0.5979 | 0.6075 | +0.1003 |
| cross_2026 | AUCTIONUSDT | new_listing | 2026-07 | 403,454 | 0.5059 | 0.7296 | 0.7473 | 0.7530 | +0.2471 |
| cross_2026 | RONINUSDT | new_listing | 2026-07 | 342,731 | 0.5003 | 0.6268 | 0.6239 | 0.6321 | +0.1318 |
| cross_2026 | TOSHIUSDT | new_listing | 2026-07 | 362,542 | 0.4965 | 0.5865 | 0.6019 | 0.6111 | +0.1146 |
| cross_2026 | DRIFTUSDT | new_listing | 2026-07 | 391,272 | 0.5491 | 0.5956 | 0.6139 | 0.6212 | +0.0721 |
| cross_2026 | IRYSUSDT | new_listing | 2026-07 | 372,401 | 0.5078 | 0.5448 | 0.5547 | 0.5747 | +0.0668 |
| cross_2026 | SOPHUSDT | new_listing | 2026-07 | 363,738 | 0.5249 | 0.6069 | 0.6075 | 0.6183 | +0.0934 |
| cross_2026 | MUBARAKUSDT | new_listing | 2026-07 | 431,652 | 0.5481 | 0.5787 | 0.6006 | 0.6114 | +0.0633 |
| cross_2026 | ASTSUSDT | new_listing_equity | 2026-07 | 365,929 | 0.5180 | 0.6415 | 0.6424 | 0.6485 | +0.1305 |
| cross_2026 | NEWTUSDT | new_listing | 2026-07 | 386,167 | 0.5119 | 0.6417 | 0.6352 | 0.6401 | +0.1282 |
| cross_2026 | LSKUSDT | new_listing | 2026-07 | 567,034 | 0.0638 | 0.8903 | 0.9360 | 0.9351 | +0.8714 |
| cross_2026 | AKTUSDT | new_listing | 2026-07 | 395,039 | 0.4971 | 0.6614 | 0.6620 | 0.6675 | +0.1704 |
| cross_2026 | ACUUSDT | new_listing | 2026-07 | 414,700 | 0.5307 | 0.6409 | 0.6373 | 0.6468 | +0.1161 |
| cross_2026 | ACXUSDT | new_listing | 2026-07 | 508,354 | 0.1143 | 0.8296 | 0.8890 | 0.8890 | +0.7747 |
| cross_2026 | ORDERUSDT | new_listing | 2026-07 | 421,388 | 0.5011 | 0.5835 | 0.5769 | 0.5887 | +0.0876 |
| cross_2026 | XPTUSDT | new_listing_equity | 2026-07 | 390,836 | 0.5030 | 0.6691 | 0.6689 | 0.6694 | +0.1664 |
| cross_2026 | ALPINEUSDT | new_listing | 2026-07 | 460,925 | 0.5043 | 0.6064 | 0.6106 | 0.6246 | +0.1203 |
| cross_2026 | BIGTIMEUSDT | new_listing | 2026-07 | 440,740 | 0.4964 | 0.6688 | 0.6696 | 0.6721 | +0.1758 |
| cross_2026 | BANUSDT | new_listing | 2026-07 | 444,810 | 0.4876 | 0.6290 | 0.6343 | 0.6422 | +0.1546 |
| cross_2026 | GLMUSDT | new_listing | 2026-07 | 437,601 | 0.5156 | 0.6924 | 0.6920 | 0.6938 | +0.1783 |
| cross_2026 | FHEUSDT | new_listing | 2026-07 | 489,831 | 0.5095 | 0.5922 | 0.5999 | 0.6176 | +0.1081 |
| cross_2026 | STRKUSDT | new_listing | 2026-07 | 535,655 | 0.5249 | 0.5763 | 0.5929 | 0.6036 | +0.0787 |
| cross_2026 | VICUSDT | new_listing | 2026-07 | 481,330 | 0.4927 | 0.5993 | 0.5992 | 0.6100 | +0.1173 |
| cross_2026 | CRWVUSDT | new_listing_equity | 2026-07 | 550,443 | 0.4940 | 0.6489 | 0.6489 | 0.6517 | +0.1577 |
| cross_2026 | MONUSDT | new_listing | 2026-07 | 572,746 | 0.4651 | 0.6214 | 0.6370 | 0.6456 | +0.1805 |
| cross_2026 | POPCATUSDT | new_listing | 2026-07 | 532,274 | 0.5151 | 0.6374 | 0.6371 | 0.6408 | +0.1257 |
| cross_2026 | SWARMSUSDT | new_listing | 2026-07 | 433,251 | 0.4837 | 0.5969 | 0.6021 | 0.6089 | +0.1252 |
| cross_2026 | CUSDT | new_listing | 2026-07 | 466,297 | 0.4814 | 0.6508 | 0.6553 | 0.6601 | +0.1787 |
| cross_2026 | REZUSDT | new_listing | 2026-07 | 558,745 | 0.5215 | 0.6463 | 0.6528 | 0.6618 | +0.1403 |
| cross_2026 | 0GUSDT | new_listing | 2026-07 | 667,157 | 0.5166 | 0.5641 | 0.5975 | 0.6049 | +0.0883 |
| cross_2026 | PIXELUSDT | new_listing | 2026-07 | 546,789 | 0.4744 | 0.6456 | 0.6435 | 0.6526 | +0.1782 |
| cross_2026 | SAGAUSDT | new_listing | 2026-07 | 692,311 | 0.5624 | 0.5795 | 0.6241 | 0.6309 | +0.0684 |
| cross_2026 | METUSDT | new_listing | 2026-07 | 681,683 | 0.4704 | 0.5986 | 0.6037 | 0.6199 | +0.1495 |
| cross_2026 | PRLUSDT | new_listing | 2026-07 | 653,582 | 0.5121 | 0.5536 | 0.5630 | 0.5726 | +0.0605 |
| cross_2026 | BANANAUSDT | new_listing | 2026-07 | 640,595 | 0.4884 | 0.6427 | 0.6366 | 0.6475 | +0.1591 |
| cross_2026 | BRUSDT | new_listing | 2026-07 | 527,644 | 0.4689 | 0.6249 | 0.6270 | 0.6327 | +0.1638 |
| cross_2026 | AVGOUSDT | new_listing_equity | 2026-07 | 554,616 | 0.5099 | 0.6662 | 0.6663 | 0.6811 | +0.1713 |
| cross_2026 | HYPERUSDT | new_listing | 2026-07 | 647,460 | 0.4918 | 0.6772 | 0.6783 | 0.6849 | +0.1930 |
| cross_2026 | EDENUSDT | new_listing | 2026-07 | 699,682 | 0.4846 | 0.6387 | 0.6383 | 0.6475 | +0.1629 |
| cross_2026 | COAIUSDT | new_listing | 2026-07 | 727,128 | 0.4925 | 0.5668 | 0.5643 | 0.5787 | +0.0862 |
| cross_2026 | BIOUSDT | new_listing | 2026-07 | 815,799 | 0.5223 | 0.5717 | 0.5935 | 0.6041 | +0.0819 |
| cross_2026 | SAFEUSDT | new_listing | 2026-07 | 607,404 | 0.5093 | 0.6628 | 0.6345 | 0.6174 | +0.1081 |
| cross_2026 | AMATUSDT | new_listing_equity | 2026-07 | 609,932 | 0.4984 | 0.7504 | 0.7502 | 0.7509 | +0.2525 |
| cross_2026 | STABLEUSDT | new_listing | 2026-07 | 800,407 | 0.5457 | 0.5821 | 0.5949 | 0.6052 | +0.0595 |
| cross_2026 | QCOMUSDT | new_listing_equity | 2026-07 | 668,171 | 0.4942 | 0.6675 | 0.6677 | 0.6704 | +0.1761 |
| cross_2026 | CAKEUSDT | new_listing | 2026-07 | 762,005 | 0.5047 | 0.6769 | 0.6770 | 0.6862 | +0.1815 |
| cross_2026 | POLUSDT | new_listing | 2026-07 | 853,554 | 0.5243 | 0.6316 | 0.6366 | 0.6468 | +0.1225 |
| cross_2026 | AIAUSDT | new_listing | 2026-07 | 678,804 | 0.4529 | 0.6378 | 0.6516 | 0.6615 | +0.2086 |
| cross_2026 | NEIROUSDT | new_listing | 2026-07 | 712,896 | 0.5056 | 0.6621 | 0.6636 | 0.6683 | +0.1627 |
| cross_2026 | SEIUSDT | new_listing | 2026-07 | 903,891 | 0.5157 | 0.6019 | 0.6142 | 0.6206 | +0.1049 |
| cross_2026 | SENTUSDT | new_listing | 2026-07 | 979,353 | 0.4609 | 0.5892 | 0.6549 | 0.6587 | +0.1978 |
| cross_2026 | TSTUSDT | new_listing | 2026-07 | 656,249 | 0.5247 | 0.6210 | 0.6266 | 0.6316 | +0.1069 |
| cross_2026 | ACTUSDT | new_listing | 2026-07 | 980,406 | 0.5114 | 0.7282 | 0.5980 | 0.5791 | +0.0676 |
| cross_2026 | TREEUSDT | new_listing | 2026-07 | 885,450 | 0.5192 | 0.6010 | 0.6041 | 0.6181 | +0.0988 |
| cross_2026 | CATIUSDT | new_listing | 2026-07 | 876,818 | 0.4929 | 0.5893 | 0.6067 | 0.6182 | +0.1252 |
| cross_2026 | RPLUSDT | new_listing | 2026-07 | 1,032,909 | 0.4649 | 0.5647 | 0.5830 | 0.5883 | +0.1234 |
| cross_2026 | DIAUSDT | new_listing | 2026-07 | 1,068,053 | 0.4934 | 0.4907 | 0.5298 | 0.5421 | +0.0486 |
| cross_2026 | FFUSDT | new_listing | 2026-07 | 964,976 | 0.4949 | 0.5990 | 0.6000 | 0.6200 | +0.1251 |
| cross_2026 | MVLLUSDT | new_listing_equity | 2026-07 | 1,090,575 | 0.4978 | 0.5431 | 0.5446 | 0.5553 | +0.0576 |
| cross_2026 | NIGHTUSDT | new_listing | 2026-07 | 1,076,971 | 0.4948 | 0.5575 | 0.5824 | 0.5883 | +0.0934 |
| cross_2026 | AIOTUSDT | new_listing | 2026-07 | 777,762 | 0.5084 | 0.6196 | 0.6313 | 0.6440 | +0.1356 |
| cross_2026 | MANTRAUSDT | new_listing | 2026-07 | 954,566 | 0.5432 | 0.6345 | 0.6564 | 0.6663 | +0.1231 |
| cross_2026 | HOLOUSDT | new_listing | 2026-07 | 912,599 | 0.5230 | 0.6577 | 0.6609 | 0.6678 | +0.1448 |
| cross_2026 | NOMUSDT | new_listing | 2026-07 | 1,043,577 | 0.5372 | 0.5709 | 0.5947 | 0.6058 | +0.0686 |
| cross_2026 | RIVERUSDT | new_listing | 2026-07 | 1,230,671 | 0.5482 | 0.6566 | 0.6940 | 0.7019 | +0.1537 |
| cross_2026 | TRADOORUSDT | new_listing | 2026-07 | 949,059 | 0.4851 | 0.6235 | 0.6252 | 0.6270 | +0.1419 |
| cross_2026 | SCRTUSDT | new_listing | 2026-07 | 978,723 | 0.4696 | 0.5894 | 0.5947 | 0.6067 | +0.1371 |
| cross_2026 | GIGGLEUSDT | new_listing | 2026-07 | 1,326,688 | 0.5027 | 0.5367 | 0.5459 | 0.5672 | +0.0644 |
| cross_2026 | TRUTHUSDT | new_listing | 2026-07 | 1,095,090 | 0.4977 | 0.6379 | 0.5917 | 0.6413 | +0.1436 |
| cross_2026 | B2USDT | new_listing | 2026-07 | 1,102,462 | 0.5197 | 0.6022 | 0.6055 | 0.6138 | +0.0941 |
| cross_2026 | GOOGLUSDT | new_listing_equity | 2026-07 | 1,272,487 | 0.5209 | 0.6608 | 0.6589 | 0.6681 | +0.1472 |
| cross_2026 | PAXGUSDT | new_listing_equity | 2026-07 | 1,468,981 | 0.5186 | 0.6570 | 0.6733 | 0.6827 | +0.1641 |
| cross_2026 | AIOUSDT | new_listing | 2026-07 | 1,001,329 | 0.5903 | 0.6263 | 0.6460 | 0.6596 | +0.0693 |
| cross_2026 | ETHFIUSDT | new_listing | 2026-07 | 1,498,421 | 0.4820 | 0.6130 | 0.6284 | 0.6399 | +0.1579 |
| cross_2026 | PIEVERSEUSDT | new_listing | 2026-07 | 1,323,150 | 0.5045 | 0.6127 | 0.6147 | 0.6267 | +0.1222 |
| cross_2026 | AEROUSDT | new_listing | 2026-07 | 1,568,237 | 0.5150 | 0.5967 | 0.6137 | 0.6251 | +0.1101 |
| cross_2026 | XANUSDT | new_listing | 2026-07 | 1,095,147 | 0.5057 | 0.6250 | 0.6284 | 0.6385 | +0.1328 |
| cross_2026 | METAUSDT | new_listing_equity | 2026-07 | 1,066,084 | 0.5150 | 0.6188 | 0.6198 | 0.6456 | +0.1306 |
| cross_2026 | HUMAUSDT | new_listing | 2026-07 | 1,094,569 | 0.5022 | 0.7356 | 0.7356 | 0.7372 | +0.2350 |
| cross_2026 | ZROUSDT | new_listing | 2026-07 | 1,657,772 | 0.4849 | 0.6710 | 0.6711 | 0.6757 | +0.1908 |
| cross_2026 | PENGUUSDT | new_listing | 2026-07 | 1,954,016 | 0.5072 | 0.6109 | 0.6302 | 0.6412 | +0.1339 |
| cross_2026 | QQQUSDT | new_listing_equity | 2026-07 | 2,118,167 | 0.5139 | 0.7094 | 0.7304 | 0.7595 | +0.2455 |
| cross_2026 | OPNUSDT | new_listing | 2026-07 | 1,835,293 | 0.4924 | 0.6325 | 0.6372 | 0.6479 | +0.1555 |
| cross_2026 | PUMPUSDT | new_listing | 2026-07 | 2,291,102 | 0.4877 | 0.5421 | 0.6142 | 0.6249 | +0.1372 |
| cross_2026 | BEUSDT | new_listing_equity | 2026-07 | 1,529,185 | 0.5100 | 0.6602 | 0.6601 | 0.6653 | +0.1553 |
| cross_2026 | GWEIUSDT | new_listing | 2026-07 | 2,490,723 | 0.5326 | 0.5414 | 0.5765 | 0.5907 | +0.0580 |
| cross_2026 | TSLAUSDT | new_listing_equity | 2026-07 | 2,111,602 | 0.4910 | 0.6523 | 0.6485 | 0.6715 | +0.1804 |
| cross_2026 | JTOUSDT | new_listing | 2026-07 | 2,556,601 | 0.5267 | 0.6221 | 0.6410 | 0.6553 | +0.1286 |
| cross_2026 | BLUAIUSDT | new_listing | 2026-07 | 1,571,092 | 0.5127 | 0.6540 | 0.6505 | 0.6606 | +0.1479 |
| cross_2026 | CRCLUSDT | new_listing_equity | 2026-07 | 2,689,106 | 0.4999 | 0.5374 | 0.5987 | 0.6251 | +0.1252 |
| cross_2026 | ARMUSDT | new_listing_equity | 2026-07 | 2,050,455 | 0.5052 | 0.6720 | 0.6714 | 0.6739 | +0.1687 |
| cross_2026 | CAPUSDT | new_listing | 2026-07 | 2,776,688 | 0.5050 | 0.5582 | 0.5596 | 0.5769 | +0.0719 |
| cross_2026 | ENAUSDT | new_listing | 2026-07 | 3,052,837 | 0.4845 | 0.6076 | 0.6254 | 0.6391 | +0.1546 |
| cross_2026 | BUSDT | new_listing | 2026-07 | 3,176,591 | 0.4850 | 0.4354 | 0.5681 | 0.5978 | +0.1128 |
| cross_2026 | HUSDT | new_listing | 2026-07 | 2,719,477 | 0.4881 | 0.7040 | 0.7069 | 0.7125 | +0.2244 |
| cross_2026 | DRAMUSDT | new_listing_equity | 2026-07 | 3,528,236 | 0.5090 | 0.4997 | 0.5329 | 0.5521 | +0.0431 |
| cross_2026 | MORPHOUSDT | new_listing | 2026-07 | 2,191,695 | 0.4715 | 0.6944 | 0.6949 | 0.7069 | +0.2353 |
| cross_2026 | AMDUSDT | new_listing_equity | 2026-07 | 3,243,807 | 0.4971 | 0.6868 | 0.6868 | 0.6934 | +0.1963 |
| cross_2026 | OUSDT | new_listing | 2026-07 | 4,335,305 | 0.5087 | 0.6210 | 0.5814 | 0.6187 | +0.1099 |
| cross_2026 | EWYUSDT | new_listing_equity | 2026-07 | 4,919,855 | 0.5092 | 0.6475 | 0.6506 | 0.6708 | +0.1616 |
| cross_2026 | BASEDUSDT | new_listing | 2026-07 | 4,096,618 | 0.5063 | 0.6692 | 0.6693 | 0.6721 | +0.1658 |
| cross_2026 | REUSDT | new_listing | 2026-07 | 5,593,372 | 0.5089 | 0.5692 | 0.5728 | 0.5972 | +0.0883 |
| cross_2026 | EPICUSDT | new_listing | 2026-07 | 4,825,620 | 0.5071 | 0.6715 | 0.6605 | 0.6728 | +0.1658 |
| cross_2026 | XAUUSDT | new_listing_equity | 2026-07 | 5,829,116 | 0.5019 | 0.5931 | 0.6284 | 0.6617 | +0.1598 |
| cross_2026 | VELVETUSDT | new_listing | 2026-07 | 6,926,210 | 0.5045 | 0.6254 | 0.6232 | 0.6384 | +0.1338 |
| cross_2026 | EULUSDT | new_listing | 2026-07 | 5,596,287 | 0.4873 | 0.6392 | 0.6389 | 0.6445 | +0.1572 |
| cross_2026 | ESPORTSUSDT | new_listing | 2026-07 | 8,641,958 | 0.4885 | 0.5608 | 0.5426 | 0.5781 | +0.0896 |
| cross_2026 | TACUSDT | new_listing | 2026-07 | 5,461,024 | 0.4794 | 0.6534 | 0.6485 | 0.6613 | +0.1818 |
| cross_2026 | SKHYNIXUSDT | new_listing_equity | 2026-07 | 24,951,484 | 0.5084 | 0.6801 | 0.6826 | 0.7099 | +0.2015 |
| cross_2026 | SNDKUSDT | new_listing_equity | 2026-07 | 27,279,429 | 0.5177 | 0.6507 | 0.6541 | 0.6724 | +0.1547 |
| cross_2026 | AKEUSDT | new_listing | 2026-07 | 21,209,407 | 0.5063 | 0.6498 | 0.6342 | 0.6489 | +0.1425 |
| cross_2026 | BANKUSDT | new_listing | 2026-07 | 32,898,387 | 0.5170 | 0.6049 | 0.5986 | 0.6241 | +0.1071 |
