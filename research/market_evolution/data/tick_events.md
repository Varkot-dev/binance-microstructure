# Tick-size change events, 2023-01 to 2026-10: built from the data

Files: `tick_events.csv` (one row per treated contract-event), `tick_event_controls.csv`
(matched untreated contracts per event date), built by `../build_tick_events.py`
(tests: `tests/research/test_tick_events.py`). Run on 2026-11-17/18.

## Method

- **Candidates.** All 66 USDT-M tick notices dated 2023-01 to 2026-10 in the appendix
  of `notes/binance_events.md` (the two November 2026 notices are out of range). Most
  were read by title only, so the treated contracts come from the data: every USDT
  perpetual alive in a month within 12 days of a notice date (15,814 symbol-months)
  was scanned with monthly 2h klines.
- **Tick per day.** The largest power of ten on whose grid at least 70% of the prices
  lie (OHLC prices from klines, trade prices from aggTrades). A cut moves the share on
  the old grid from 1.0 to 0.1 to 0.3. An increase moves the share on the new grid from
  about 0.1 to 0.9 (resting orders keep printing on the old grid). A change counts only
  if it lasts 2 days or more: runs of one day are noise. Changes on a notice's date or
  the day after were attributed to that notice. For a contract a notice names, any
  change within 10 days counts.
- **Trades.** Daily aggTrades (SHA-256 checked by `binance.download`, ingested with
  `ingest_agg_trades`, summarized, then deleted). For each day and each 30-minute bin
  the script keeps a histogram of price levels. The change time is the first bin of the
  new regime, from a two-rate binomial change point on the share on the coarser grid,
  accepted only if both sides look like the old and new tick. `estimate_tick` (smallest
  recurring increment) was kept as a cross-check: it is a power of ten on 1,423 of
  1,430 trade days, and the 7 exceptions are thin days.
- **Budget.** The 32 contract-events of the five events named in the task (2023-02-10,
  2023-08-29, 2024-09-20, 2024-10-14, 2026-03-05) got their +/- 10 days of trades,
  water-filled to 41.7 MB each: 23 have all 21 days. The others have fewer: APT 2023 4,
  OCEAN 8, SOL 9, TRB 10, TURBO 12, BIGTIME 14, APT 2024 15, and API3 and ZRO 17. Every other contract-event got its change day only,
  when that file was 5 MB or less. Otherwise the 2h klines give the time to within 2h.
  No day file was over 300 MB (largest 275 MB), so none was skipped for size. Total
  downloaded: 1.82 GB. Kept: 137 MB of JSON summaries under `data/tick_events/`.
- **events_per_day_pre** is the mean number of aggTrade records over the 10 days before
  the change. It is measured from trades where pre-event days were downloaded (39 rows).
  Otherwise it is the archive size of each pre-event day file divided by the contract's
  own bytes per record (401 rows), or by the median bytes per record (17 rows).
  `events_per_day_pre_method` says which.
- **Controls.** For each detected event date:
  - The candidates are USDT perpetuals in the archive for every month of +/- 30 days,
    excluding any contract with a detected change within +/- 30 days.
  - Each treated contract is matched on two activity measures over days -10 to -1,
    both within a factor of 2: aggTrades bytes per day (archive inventory) and trades
    per day (kline counts).
  - The 6 closest matches are checked for tick stability on every day of +/- 30 days
    from 2h klines. They must show no persistent change, with at least 90% of days on
    one tick.
  - The top-ranked stable control of each treated contract was also checked on the
    event day's trades (48 bins, no old to 10x finer or coarser split). 408 passed and
    39 were skipped (budget or over 25 MB). None failed.
  - For 2026-10-15/22/28 the window ends 2026-10-31 (the last monthly file), so it is
    shorter than +30 days.

## Counts

- **458 treated contract-events** (366 contracts) on 74 distinct change dates: 394
  cuts and 64 increases, all 10x except two 100x changes. 451 are `verified` (the change is on the
  notice date) and 7 are `date-differs`. No contract named in the notes is `no-change`.
  The median relative tick for cuts is 12.3 bps before and 1.3 bps after.
- **Controls:** 2,602 treated-control pairs, 2,225 distinct control-event pairs, and
  about 5 to 6 controls per treated contract. Per event:
  - 2026-03-05: 12 treated, 62 controls.
  - 2024-09-20: 12 treated, 58 controls.
  - 2023-08-29: 5 treated, 27 controls.
  - 2023-02-10: 2 treated, 10 controls.
  - 2024-10-14 (SOL): 1 treated, 6 controls.
  - 2024-11-29: no controls. 1000WHY and 1000CHEEMS were listed in November 2024, with
    fewer than 8 pre-event days.
- **Matching gap.** Controls are matched on activity only. `control_rel_tick_bps` is
  in the file, so a stricter match on relative tick (or price trend, for the cheap 2026
  coins) is a filter away.

## Discrepancies with notes/binance_events.md

1. **2023-02-10 APT and OCEAN switched at 09:00 UTC, not 06:30.** The share on the new
   grid is 0.11 in every half hour up to 08:30, then 0.78 to 0.83 from 09:00 and 0.92+
   after. The date is right.
2. **The notice titled 2024-06-20 took effect on 2024-06-21 at 06:30.** The data show
   six contracts: DYM, EGLD, ENJ, GMT, LRC and REZ. The original "2024-06-21 06:30" row
   was right, and the verification pass's "corrected to 2024-06-20" is wrong.
3. **BNXUSDT (notice titled 2023-04-26) changed on 2023-05-05 at 06:30**, a cut from
   0.001 to 0.0001.
4. **1000WHY and 1000CHEEMS (2024-11-29) went from 0.000001 to 0.0000001** (about 06:00).
   The search snippet was right and the note's "the data show 0.00001 to 0.000001" is not.
5. **2026-10-15 batch: 07:00 or later, not 06:30.** For all 7 contracts the 06:30 to
   07:00 bin is still entirely on the old grid. The new grid appears at 07:00 (APR, BEAT,
   FLNC, ROBO) or 07:30 (CSOPSAMSUNG2L, RUM, XPIN).
6. **2025-12-15 batch: the switch is inside the 07:00 to 07:30 bin.** It is late in the
   bin: the old-grid share there is 0.67 to 0.93, against about 0.3 in other 07:00
   batches.
7. **Lists longer than the notes.**
   - 2025-10-27: 11 contracts, not 3. The data add AI16Z, AKT, G, KDA, MAVIA, MOVE, SYN
     and TNSR (9 cuts, 2 increases).
   - 2025-12-22: 12 contracts. SUSDT is the one not in the list.
   - 2025-09-19 ("AVNT and others"): AVNT is the only USDT perpetual that changed.
8. **2025-08-01 shows no change in any contract**, consistent with its 2025-08-04
   postponement notice. The 2025-08-04 notice has 6 contracts.
9. **The undated notice (published 2026-04-10)** matches changes on 2026-04-13, 04-15
   and 04-16 (10 contracts). The 2026-04-21/22 notice has 7.
10. **Confirmed as in the notes:**
    - 2023-08-29 06:30: all 5, DODOX included.
    - 2024-09-20 06:30: all 12.
    - 2024-10-14 06:30, SOL: the share on the 0.01 grid goes from 0.10 to 0.86 in the
      06:30 bin.
    - 2025-12-22 07:00.
    - 2026-03-05 07:00: all 12.
    - 2026-08-06 06:30: all 8.
    - 2026-10-22 06:30: 3 cuts, plus BR and AGT increases within the 2h kline row.
    - 2025-10-17 07:00 (BAS, CLO, increases) and 2025-09-02 (SOMI) also match.
11. **The notes undercount tick changes.** Their "about 30 contracts" over the verified
    batches is about 458 contract-events across the 66 notices. Treated contracts are
    common enough that controls must be checked for their own changes, which the
    script does.

## Strongest design

The strongest design is **2026-03-05 07:00**:
- The treatment is a single 10x cut on 12 contracts in one minute.
- All 12 have all 21 days of trades, with a sharp switch (the old-grid share drops from
  1.0 to about 0.3 in the 07:00 bin).
- The contracts started from a uniform 11 to 13 bps relative tick (MYX 24) and ended
  near 1.2 bps.
- 62 stable, activity-matched controls are available.

Caveats: these are weak, cheap coins, so match on price trend too; and 2026-02-09,
02-12 and 02-27 each cut ticks on 15 more contracts within a month. Those contracts
are excluded as controls, but they make a stacked design across the 2025 to 2026
batches (all 07:00 or 06:30) the natural extension.

2024-09-20 (12 cuts, 58 controls) is the independent replication in a different regime.
SOL 2024-10-14 is the only large liquid increase.
