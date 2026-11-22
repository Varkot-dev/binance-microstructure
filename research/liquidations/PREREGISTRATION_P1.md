# P1 pre-registration: bookDepth quality mask, metrics screen and onset test

**Status: LOCKED 2026-11-22** after review by the project owner, who settled questions Q1 to Q4
(section 9). The sha256 of this file, of `metrics_screen_v1.txt` and of both mask versions are
written into `p1_scan.py`, which refuses to scan, report or test if any of them changes.
Anything reported that is not specified here is labelled **exploratory**.

## 0. What has already been seen

Honest disclosure of every look at the data before this plan:

- Earlier sessions (README.md, DATA.md) scanned 119,374 bookDepth contract-days and hourly
  windows on stress dates, drafted mask v1 from those artifacts, and computed the onset numbers
  quoted in DATA.md for October 2025 (68 bid-side onsets, median prior 1-hour return -2.57%; 55
  ask-side, +0.84%) and September 2026 (25 of 25 ask onsets positive). The hypotheses of test T1
  below come from those numbers, so T1 on those two months is not a fresh test. Section 5.4
  reports T1 without them.
- This session (2026-11-22) parsed about 30 bookDepth, 30 klines and 30 metrics daily files of
  BTCUSDT, ETHUSDT and DOGEUSDT, for format checks, code tests and the acceptance checks in
  section 6, mostly on dates examined before. It also downloaded 40 days of XRPUSDT files
  (2024-05-01 to 06-09) only to time the transfer; they were never parsed. The acceptance-check
  runs pass through the whole pipeline, so onset returns for those six short windows were
  computed internally; they were not printed or inspected, and no test statistic of T1 was
  computed.
- Two metrics rules were tuned on BTCUSDT 2025-10-10 (see the disclosure at the end of
  `metrics_screen_v1.txt`), and the label-convention rule M5 was designed after
  correlating taker ratios with klines on 10 files.

## 1. Questions

1. **Ledger.** Which bookDepth snapshots and which metrics rows of Binance USDT-M perpetuals are
   corrupted, 2023-01-01 to 2026-11-18, under fixed rules?
2. **T1 (the only hypothesis test).** Do corruption onsets follow price moves in a direction
   that matches the corrupted side? A stale bid level stays in the snapshot after the price falls
   through it, so bid-side onsets should follow falls and ask-side onsets rises. If so, the
   masked data are missing not at random (Rubin 1976), and every later project must treat
   "depth unavailable" as informative instead of ignorable.

## 2. Data and scope

- **Files.** Daily `bookDepth`, `metrics` and 1-minute `klines` (last price) from the public
  bucket of data.binance.vision, read through its S3 address
  `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision`. Every file is checked against
  its published `.CHECKSUM` (a mismatch after two tries stops the run) and recorded in a
  manifest with our sha256, size, S3 Last-Modified, ETag, the timestamp stored inside the zip,
  and the fetch time. Files are held in memory only.
- **Dates.** Every file dated 2023-01-01 to 2026-11-18 inclusive that is listed at fetch time.
- **Symbols.** Folders under `futures/um/daily/bookDepth/` whose name ends in `USDT`, has no
  underscore and has only capital letters and digits (900 on 2026-11-22), minus rule X6 (55),
  giving 845. X6 uses the 2026-08-13 exchangeInfo snapshot in `results/exchangeinfo_snapshot.json`.
  The 241 symbols not in that snapshot are kept and listed as "unclassified"; rules S2 and S3
  still remove static weekend books on any of them.
- **Contract-day.** One symbol and one UTC date with at least one of the three files.

## 3. Rules

### 3.1 bookDepth: mask v2 (primary) and v1 (reported alongside)

- **Primary:** `bookdepth_mask_v2.txt`, sha256
  `c800985ddac189c14044b8c5364c9bce02d5b62401f956cc5b43237d21731a09`.
- **Alongside:** `bookdepth_mask_v1_DRAFT.txt`, sha256
  `61d003375266604e95b2d9ff66149b9f39d0eb03862c8a779f566c6abc4513f7`, committed unchanged on
  2026-11-20 (commit 69ebe50).
- The two differ only in S6: v2 does not buffer crossed (S1) runs shorter than 3 snapshots
  (decision Q1, section 9). Both are implemented in `src/microstructure/quality/bookdepth.py`
  and computed in the same pass. S6 does not enter the onsets, so test T1 is the same under
  both. The calendar exclusions X1 to X4 were chosen from artifact data, not from any outcome.

**Interpretation notes.** The mask text leaves these choices open; they are fixed here.

| Note | Choice |
|---|---|
| I1 | "Inner band" is taken among the core bands only; the 0.2 bands are dropped at parsing and play no role in P1. Because S0 requires every core band to be positive, the inner bands of any S0-valid snapshot are -1 and +1. |
| I2 | "Consecutive snapshots" means adjacent in the symbol's concatenated snapshot sequence, whatever the time between them. A missing file does not break a run. |
| I3 | A snapshot whose kline minute is absent fails S5 (counted separately as `n_S5_nokline`). |
| I4 | D1's gap condition uses gaps between consecutive valid snapshots inside the contract-day only; the stretch from 00:00 to the first valid snapshot and from the last one to 24:00 is not a gap. |
| I5 | Calendar windows are half-open, [start, end); X1 ends at 11:13:00. |
| I6 | An S1 run is a maximal run of consecutive crossed snapshots, of any length including 1. Under v1, S6 buffers every such run; under v2, only runs of 3 or more. |
| I7 | X6 matches the strings `TradFi` and `Pre-Market` exactly in `underlyingSubType`, or one of the listed `underlyingType` values. `PreMarket` (3 contracts) and `Pre-IPO` without `TradFi` do not match. |
| I8 | Depth equality in S2 and S3 compares the parsed float64 values of the file's decimal strings. |
| I9 | The 1-minute kline used by S5 is the daily `klines/<SYM>/1m` file of the snapshot's date. |
| I10 | A file that is listed but not served, does not unzip, or does not parse counts as absent and is listed in `errors.csv`. |
| I11 | Snapshots whose timestamp is not later than the previous file's last snapshot are dropped and counted. |
| I12 | D3 uses D1 under S0 to S6 only (`d1_s`); X1 to X4 are applied in addition, as the mask says. The denominator is contracts with a bookDepth file that verified. |

### 3.2 metrics: screen v1

`metrics_screen_v1.txt` (rules M0 to M6; renamed from `metrics_screen_v1_DRAFT.txt` on approval,
content unchanged), implemented in
`src/microstructure/quality/metrics.py`. Its main departure from the README's earlier plan:
the `create_time` label convention is decided per file from the data (M5), not from the
2026-06-25 date in issue #491, because rewritten files dated as early as 2024-08-05 already use
start-of-period labels while an unrewritten 2023-06-01 file uses end-of-period labels.

## 4. Outputs (descriptive, no test)

Written to `research/liquidations/data/p1/` by `p1_scan.py report`:

- `day_table.parquet`: one row per contract-day: snapshots, counts by rule (S0 to S6, S5 without
  kline, calendar), valid counts and largest gap with and without X1 to X4, D1 verdicts, and D1
  under S3 thresholds 10 and 40 (D5), all under v2; the v1 values of every S6-dependent column
  carry the suffix `_v1`.
- `intervals.parquet`: invalid stretches by rule, symbol, side and band. The v2 mask is the union
  of all rows except `S6_v1`, plus X1 to X4; the v1 mask replaces the `S6` rows with the
  `S6_v1` rows.
- `d3_dates.csv`: share of contracts failing D1 per date and the D3 verdict, under v2 and v1.
- `metrics_days.parquet`, `metrics_flags.parquet`: M4 and M5 per contract-day, flagged rows.
- `manifest.parquet`, `errors.csv`, `universe.csv`.
- A report with, for each rule, the share of snapshots and contract-days it removes (D5), the
  episode list (S1, S2, S3 runs longer than 1 hour, merged across symbols by start time), the D3
  date list, and the M5 verdict counts by file date and by zip timestamp year.

## 5. Test T1: do corruption onsets follow same-direction price moves?

### 5.1 Onsets

From `bookdepth.onsets` for every in-scope symbol: the first snapshot of every S1 run (side from
whichever inner VWAP is farther, in log terms, from the close of the kline minute) and of every
S3 run (side from the band's sign), leaving out candidates whose first snapshot lies inside an S2
whole-book repeat (a whole-book freeze has no side). Per symbol and side, a candidate is kept
only if no candidate of that side started in the preceding 6 hours (declustering, as in
EVENT_DEFINITION_DRAFT.md section 5).

### 5.2 Outcome

`r60 = ln C(m-1) - ln C(m-61)`, where `C` is the 1-minute kline close of the same symbol and `m`
the minute containing the onset: the 60-minute return ending at the last full minute before the
onset. Onsets without both closes are dropped and counted.

### 5.3 Primary test

- **H-bid:** the median `r60` over bid-side onsets is lower than chance. **H-ask:** the median
  over ask-side onsets is higher than chance. One-sided.
- **Null distribution: common time shift.** All onsets of a side are moved together by the same
  shift `d`, for every whole number of hours with 24 <= |d| <= 672 (1,298 shifts, plus and minus
  1 to 28 days), and the same median is recomputed on the shifted times. A shifted time is
  dropped if its returns are missing or if it lies within 6 hours of the start of any S1, S2 or
  S3 run of that symbol. Moving every onset by one common shift keeps the clustering of onsets
  in calendar time and the correlation of returns across contracts at the same moment, which
  random per-onset placebo dates would destroy and which inflates rejection rates in clustered
  event studies (Kolari and Pynnonen 2010). The logic is that of the torus-translation test for
  spatial association (Harms et al. 2001) and of placebo event dates (Brown and Warner 1985).
- **p-value:** `p = (1 + #{shifts with a median at least as extreme}) / (1 + number of shifts)`
  (Phipson and Smyth 2010). Smallest attainable p is 1/1,299.
- **Decision:** Holm (1979) over the two hypotheses at family-wise 5%. Effect sizes reported
  with every p: the observed median, the median of the shift medians, the share of onsets with
  the predicted sign and the same share under the shifts.
- **Assumption, stated so it can be judged:** the return distribution 1 to 28 days away is a
  fair stand-in for the return distribution at the onset in the absence of any link. Shifts
  overlap, so they are not independent draws; the test is a randomization test conditional on
  the observed onset pattern, not a sampling-based test.

### 5.4 Secondary analyses (reported, never used to change the primary verdict)

a. Without onsets in 2025-10 and 2026-09 (the months examined before this plan).
b. Hour-cluster statistic: onsets grouped by UTC clock hour; statistic = median over hours of
   the hour's median; the groups move with the shift.
c. Horizons 15 and 240 minutes instead of 60.
d. S1 onsets and S3 onsets separately.
e. By calendar year of the onset.
f. S3 thresholds 10 and 40 snapshots (D5), recomputing onsets.

### 5.5 What each result means for later projects

- **H-bid or H-ask rejected:** masking is missing not at random in that direction. P3 to P5
  must carry a "depth unavailable" indicator, report results with and without masked windows,
  and must not treat dropping masked contracts as harmless.
- **Neither rejected:** this does not show the mask is ignorable (absence of evidence). P3 to
  P5 still report with and without masked windows.

## 6. Acceptance checks of the code (run before locking)

`p1_scan.py validate` re-ran the mask on six windows that were examined before this plan and
reproduced every documented feature (output in `data/p1/validation.md`):

| Window | Expected (DATA.md) | Got |
|---|---|---|
| BTCUSDT 2025-10-09 to 10-11 | Ghost bid from 15:30:42 on 10-10 | First S1 2025-10-10 15:30:42, bid |
| BTCUSDT 2025-04-15 to 04-17 | Whole-book freeze from 2025-04-16 about 10:31 | First S2 2025-04-16 10:30:49 |
| DOGEUSDT 2024-02-19 to 02-22 | Isolated crossed snapshots | S1 snapshots only. Under v1, S6 removed most of each day (02-22: 490 of 2,873 valid); under v2, 02-19 and 02-20 keep 2,851 and 2,823 and pass D1 |
| ETHUSDT 2025-10-10 | Ghost bid from 15:30:06 | First S1 15:04:33, bid (earlier than DATA.md noted) |
| BTCUSDT 2026-09-02 to 09-04 | Ask crossed 14:25:32, frozen 14:46:03 on 09-03 | Same, to the second |
| BTCUSDT 2024-08-04 to 08-06 | Clean | No flags, D1 passes |

## 7. Deviations

Any change after this file is hashed is a new version (v2) with a new hash; results under both
versions are reported side by side. Bugs found after locking are fixed in code, listed with the
commit that fixes them, and every affected output is recomputed.

## 8. References

Status tags as in LITERATURE.md: **[C]** bibliographic details confirmed by a web search on
2026-11-22; **[K]** standard reference cited from knowledge, not checked this round.

- [C] Barndorff-Nielsen, O. E., Hansen, P. R., Lunde, A. and Shephard, N. (2009). Realized
  kernels in practice: trades and quotes. Econometrics Journal 12(3), C1-C32. Data-cleaning
  rules for high-frequency quotes, including removal of quotes with a negative spread: the
  precedent for S1. (Bibliographic record confirmed; the exact rule wording was not re-read.)
- [C] Brownlees, C. T. and Gallo, G. M. (2006). Financial econometric analysis at ultra-high
  frequency: Data handling concerns. Computational Statistics and Data Analysis 51(4),
  2232-2245. https://doi.org/10.1016/j.csda.2006.09.030. Shows that uncleaned "wrong" ticks
  change estimates; precedent for neighbourhood-based outlier rules such as M2.
- [C] Hoffmann, M., Rosenbaum, M. and Yoshida, N. (2013). Estimation of the lead-lag parameter
  from non-synchronous data. Bernoulli 19(2), 426-461. https://doi.org/10.3150/11-BEJ407.
  Choosing a time shift by maximising cross-correlation: the idea behind M5.
- [C] Kolari, J. W. and Pynnonen, S. (2010). Event study testing with cross-sectional
  correlation of abnormal returns. Review of Financial Studies 23(11), 3996-4025.
  https://doi.org/10.1093/rfs/hhq072. Even small cross-correlation over-rejects when event dates
  cluster; the reason T1 shifts all onsets together.
- [C] Harms, K. E., Condit, R., Hubbell, S. P. and Foster, R. B. (2001). Habitat associations of
  trees and shrubs in a 50-ha neotropical forest plot. Journal of Ecology 89(6), 947-959.
  Torus-translation test that keeps spatial structure under the null. (Bibliographic record
  confirmed; the methods section was not read, so the description is from secondary sources.)
- [C] Phipson, B. and Smyth, G. K. (2010). Permutation p-values should never be zero.
  Statistical Applications in Genetics and Molecular Biology 9(1), article 39.
  https://doi.org/10.2202/1544-6115.1585.
- [K] Brown, S. J. and Warner, J. B. (1985). Using daily stock returns: The case of event
  studies. Journal of Financial Economics 14(1), 3-31. Placebo event dates.
- [K] Holm, S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian
  Journal of Statistics 6(2), 65-70.
- [K] Rubin, D. B. (1976). Inference and missing data. Biometrika 63(3), 581-592. Definition of
  data missing at random and not at random.
- From LITERATURE.md: Baumgartner and Guettler (2022, [L]) as precedent that Binance data fail at
  exactly the events studied; Andersen and Bondarenko (2014, [C]) for why events and warnings
  must be kept apart in time.

## 9. Decisions taken at review (2026-11-22)

- **Q1. S6 around isolated crossings: v2.** Under v1, one crossed snapshot invalidates 41
  snapshots and leaves a 1,260-second hole, so that contract-day fails D1 (DOGEUSDT 2024-02-22:
  490 of 2,873 snapshots valid). v2, written before any outcome was computed, buffers S2 and S3
  runs and only S1 runs of 3 or more snapshots. v2 is primary and v1 is reported alongside.
- **Q2. Scope: full.** All 845 in-scope symbols, about 1.5 million files, resumable by symbol.
- **Q3. Approved as written:** I4 (D1 gaps inside the contract-day only) and I7 (exact string
  matching for X6).
- **Q4. Approved:** metrics screen v1 as written, including M2 (two-sided return within 10%,
  1% floor) and M5 (per-file label convention).
