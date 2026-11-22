# Recorder data quality: pilot check on 2026-11-22

Scope: gaps and data quality only. Nothing here relates the retail flag to any attribute. The
only statement about the flag is that the column contains both values.

## Why this is a pilot and not "the first days of output"

No recorded data existed on 2026-11-22. The recorder's workflow was only on the branch behind
pull request 19, and GitHub runs scheduled workflows from `main` only, so it had never run and no
`rpi-trades-2026-11` release existed. Pull request 19 was merged at about 23:36 UTC and a first
run was started by hand. That run was still queued at 23:46 UTC, behind the Hyperliquid crawl's
jobs.

To have something to check, the recorder was run from a development machine with the same code
(commit `7a175b8`): a 1-minute smoke test, a 30-minute run (23:15 to 23:45 UTC) and a 4-minute
run started inside it (23:16 to 23:20 UTC) to test overlapping runs. Pilot data are excluded from
all analysis.

Reproduce with `python -m microstructure.rpi.quality DIR [DIR ...]`.

## Results (30-minute run plus the overlapping 4-minute run)

| Check | Result |
|---|---|
| Unique trades | 115,639 across 15 contracts |
| Rate-limit responses (HTTP 429 or 418) | 0 |
| Request errors | 0 |
| Gaps logged by the recorder (a poll that did not reach back to the last stored trade) | 0 |
| Trades recorded by both runs | 31,256, all identical in every field |
| Duplicate rows within a run | 0 |
| Timestamps going backwards in id order | 0 |
| Unparsable numbers, non-positive prices or quantities, flags other than 0 or 1 | 0 |
| Summary row counts agree with the data files | yes, both runs |
| All 15 contracts RPI-enabled in `exchangeInfo` | yes |
| `isRPITrade` contains both values over the whole sample | yes |

| Contract | Trades | Ids absent from the sequence |
|---|---|---|
| BTCUSDC | 32,860 | 8 |
| ETHUSDC | 27,337 | 4 |
| 1000PEPEUSDT | 18,286 | 3 |
| DOGEUSDT | 12,478 | 6 |
| SOLUSDC | 9,374 | 0 |
| the other 10 contracts | 1,064 to 2,369 each | 0 |

## Findings

1. **Single trade ids are absent from Binance's feed itself.** 21 ids are absent (0.018%). Each
   hole is exactly one id wide, the trades on either side are 5 to 2,658 ms apart, and the
   recorder logged no polling gap, which means the neighbouring ids arrived in the same response
   or in overlapping responses. These ids were therefore never served. Binance's documentation
   reportedly says only "market trades" are returned (insurance-fund and ADL trades are left
   out), and the public archive for BTCUSDT on 2026-11-19 has 464 absent ids in about 5 million
   rows. Both points come from the background research and were not re-checked here.
   **Not yet confirmed:** that the same ids are absent from the daily archive. The archive file
   for 2026-11-22 is published the next day; the comparison is a pending check.
2. **Consequence for the plan.** A hole in the id sequence is not by itself a recording loss. The
   pre-registration now defines a recorder gap as ids that are present in the daily archive but
   missing from the recording.
3. **`quoteQty` is truncated.** On BTCUSDC and ETHUSDC it differs from price times quantity in
   over 94% of rows, by up to 0.57%. Notional must be computed as price times quantity.
4. **Overlapping runs agree exactly**, so de-duplicating by (contract, id) is safe.
5. **Polling headroom was adequate in a quiet half hour.** No response was a full page after the
   first call, and no rate limit was hit. This says nothing about a volatile period; the id
   check against the archive is what will show losses then.

## Gaps in the recorder's own checks

- The recorder only detects a gap between polls. It does not report holes inside a response, so
  its "0 gaps" would not reveal finding 1. `quality.py` does.
- `full_pages` in the run summary counts the first call for every contract, so it reads 1 where
  0 would be more natural. Cosmetic.

## Still to do once GitHub runs exist

- Run `quality.py` on the first days of release assets, including a period with heavy trading.
- Compare one full day against the daily archive on data.binance.vision: same ids, prices,
  quantities, times and sides.
- Watch whether recorder runs wait in the queue behind the Hyperliquid crawl. A run that starts
  more than 75 minutes late leaves a hole that only `historicalTrades` could repair.
