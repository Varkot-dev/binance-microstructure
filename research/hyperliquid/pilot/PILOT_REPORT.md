# 200-wallet data-quality pilot

Step 3 of the Hyperliquid plan (`research/hyperliquid/README.md`, section 6). This pilot asks one
question: is the free per-wallet data good enough for the flagship skill-vs-luck test? It
reports coverage, spacing, retention, consistency and cost only. **No return, skill or ranking
statistic was computed**, and none of the numbers below say anything about which wallets did
well.

- Code: `research/hyperliquid/pilot.py` (commands `sample`, `fetch`, `summarize`; works on the
  full cohort with `--n all`). Tests: `tests/hyperliquid/test_pilot.py`.
- Raw responses: `data/hyperliquid/pilot/raw/<address>/*.json.gz` (105 MB, git-ignored). Reruns
  replay the cache with no network calls.
- Outputs: `data/hyperliquid/pilot/summary.json` (all aggregates quoted here),
  `wallet_metrics.jsonl` (per-wallet quality metrics), `wallet_log.jsonl` (wall time and
  pacing per wallet), `run.json` (fixed `as_of_ms` = 1795134531265, 2026-11-20 00:28:51 UTC,
  used as `endTime` for every paged call).
- Fetch window: 2026-11-20 00:28 to 03:51 UTC (one restart at wallet 30; cached calls were
  replayed, not refetched).

## 1. Cohort and sample

- Formation file `data/hyperliquid/formation/leaderboard_20261119T235851Z.json.gz`, sha256
  `ac669f966b7ddbd4a4e5aa8ac50781c9a8d9f51a071ac3c062812046217c1a37` (checked by the script
  before every command; it refuses to run on a mismatch).
- The file holds **48,035** rows in `leaderboardRows`, all with distinct addresses. The task
  brief said 48,003; the hash matches, so 48,035 is the correct count for this file and the
  plan should quote it.
- Sampling rule, fixed before any wallet was fetched: lowercase and sort the unique addresses,
  then `numpy.random.default_rng(20261119).choice(48035, size=200, replace=False)`. The seed is
  the formation date. The list is in `data/hyperliquid/pilot/sample_200.txt`.

Sample vs cohort (leaderboard fields, allTime window):

| Quantile | Cohort allTime vlm | Sample allTime vlm | Cohort accountValue | Sample accountValue |
|---|---|---|---|---|
| 10% | $0.51M | $1.67M | $0 | $0 |
| 25% | $11.5M | $12.3M | $0.36 | $0.04 |
| 50% | $21.1M | $25.4M | $349 | $36 |
| 75% | $55.0M | $63.4M | $111.8k | $123.4k |
| 90% | $171.2M | $180.9M | $404.2k | $458.4k |
| 99% | $1.86B | $1.02B | $7.17M | $5.58M |
| Share exactly zero | 5.9% | 6.0% | 8.6% | 14.5% |
| KS distance (5% critical value 0.096) | | 0.075 | | 0.086 |

Neither distribution differs from the cohort at the 5% level on the KS test. The sample does
have more zero-balance wallets than expected (29 of 200 against about 17 at the cohort rate;
binomial p = 0.004 one-sided). The draw rule was fixed in advance, so the sample is kept, but
shares of empty accounts below are a little high.

## 2. What each endpoint returned

| Data type | Returned (HTTP 200) | Non-empty |
|---|---|---|
| `portfolio` | 200 / 200 | 200 / 200 (allTime history present for all) |
| `userNonFundingLedgerUpdates` | 200 / 200 | 200 / 200 |
| `userFillsByTime` | 200 / 200 | 188 / 200 (the other 12 have zero allTime volume) |
| `subAccounts` | 200 / 200 | 20 / 200 list sub-accounts (40 sub-accounts in total); the rest `null` |
| `userRole` | 200 / 200 | 200 / 200 |

No call failed after retries. Over 2,055 requests there was one HTTP 429 and two retries in
total.

The ledger never needed a second page: the largest ledger had 1,593 rows (median 42). Every
wallet had an identifiable first inbound event (deposit, genesis spot balance, vault creation
or incoming transfer).

## 3. Portfolio histories: span and spacing

`allTime` histories (accountValue and pnl, same timestamps):

| Statistic | Min | 10% | 25% | Median | 75% | 90% | Max |
|---|---|---|---|---|---|---|---|
| Points | 34 | 41 | 52 | 69 | 86 | 95 | 107 |
| Span (days) | 16 | 148 | 300 | 530 | 708 | 982 | 1,093 |
| Median gap (h) | 6 | 49 | 168 | 168 | 334 | 336 | 336 |
| Max gap (h) | 26 | 169 | 170 | 170 | 337 | 338 | 349 |

- The first allTime point is 2023 for 6 wallets, 2024 for 59, 2025 for 81 and 2026 for 54.
- Spacing is a **step function of account age**, not irregular noise. Accounts younger than
  about 6 months get finer points (6 h to 85 h). From about 200 to about 700 days of history the
  spacing is exactly 168 h (weekly), with the point count growing to about 100. Past about 700
  days the series is resampled to 336 h (two-weekly) and the count drops back to 58 to 90. 51 of
  200 wallets (26%) are on the two-weekly grid. The first gap is 1 h for almost every wallet (the
  series starts with an hourly point at account creation).
- Shorter windows are regular: `month` has 35 to 66 points over 30 days with a median gap of
  9 to 24 h; `week` has 59 to 74 points every 2.3 to 3.0 h; `day` has 12 to 74 points every
  20 min to 2.3 h. The `perp*` windows mirror these.
- The last allTime point is 0.5 to 3.9 h after the formation snapshot (it tracks the fetch
  time), so the series is current.

## 4. Fills: do they reach back to the first deposit?

The endpoint returns up to 2,000 fills **oldest first** from `startTime`; a backward walk with
`endTime` does not reverse the order, so the earliest retained fill is reached by paging
forward from `startTime = 0` (inclusive start, dedup on `(tid, oid)`). Same result as paging
backwards, fewer edge cases. No wallet hit the 150-page safety cap and no page was stuck inside
one millisecond. The largest wallet returned 146,535 fills in 74 pages.

Two independent completeness checks per wallet:

1. **Volume coverage**: retrieved fill notional divided by portfolio allTime `vlm`. For
   complete histories this is 1.0000 to six decimals (median 1.0000004 in the top group), so
   it is a sharp test.
2. **Open-position flag**: a perp coin whose first retrieved fill has a nonzero
   `startPosition` proves that earlier fills of that coin are missing.

| Volume coverage | No open flag | Open flag | Total |
|---|---|---|---|
| >= 0.99 | 145 | 5 | 150 |
| 0.95 to 0.99 | 4 | 4 | 8 |
| < 0.95 | 4 | 26 | 30 |
| Total (wallets with fills) | 153 | 35 | 188 |

- **Complete back to the first deposit: 145 of 188 trading wallets (77%), 150 (80%) if the
  coverage test alone is used.** In the >= 0.99 group the median gap between the first inbound
  ledger event and the first fill is 0.0 days, 129 of 150 start trading within one day, and the
  90th percentile is 2.8 days.
- **Clearly cut off: 30 of 188 (16%).** Their earliest retained fill is a median 53 days (90th
  percentile 392 days) after the first deposit, and the retained window ranges from under one
  day (an active bot) to 1,000 days.
- Cut-offs are concentrated in heavy traders: 0 of 5 wallets under $1M allTime volume, 3 of 16
  at $1M to $10M, 14 of 137 at $10M to $100M, 11 of 27 at $100M to $1B, and 2 of 3 above $1B.

### Testing the retention cap

| Unit at the cut (coverage < 0.95, n = 30) | Min | 25% | Median | 75% | 90% | Max |
|---|---|---|---|---|---|---|
| Raw fills | 40 | 11,622 | 17,067 | 28,011 | 45,343 | 94,192 |
| Distinct orders (`oid`) | 5 | 1,291 | 3,609 | 9,586 | 10,861 | 11,177 |
| Aggregated fills (distinct `oid`, `time`) | 5 | 3,236 | 10,231 | 10,716 | 11,596 | 13,069 |
| Distinct fill timestamps | 5 | 3,147 | 10,173 | 10,464 | 10,809 | 10,952 |

For comparison, complete wallets (coverage >= 0.99, n = 150) reach 146,535 raw fills, 12,975
orders, 15,690 aggregated fills and 10,895 distinct timestamps.

- "10,000 most recent fills" is **rejected**: cut-off wallets keep 11.6k to 94k raw fills and
  complete wallets keep up to 146,535.
- "10,000 most recent orders" is **rejected as a rule**: one complete wallet has 12,975 orders,
  and half of the cut-off wallets keep fewer than 3,700 orders.
- The best single description is a cap of **about 10,000 to 11,000 aggregated fills (distinct
  order-millisecond pairs, or distinct timestamps)**: 17 of the 30 cut-off wallets hold between
  10,000 and 13,069 aggregated fills (14 of them between 10,000 and 11,600) and between 10,000
  and 10,952 distinct timestamps. It is still not a hard rule: one complete wallet has 10,895
  distinct timestamps, and the other 13 cut-off wallets hold far fewer (5 to 9,330 aggregated
  fills; one has 5 orders and 40 fills with 85% of volume missing). Those small cases point to a second mechanism (possibly cancelled orders
  counting toward the cap, or missing middle segments) that this pilot cannot identify.
- Practical consequence: no count threshold can certify completeness. **The volume-coverage
  test must be run per wallet**, and it is cheap once fills are pulled.

## 5. Vaults and sub-accounts

- `userRole`: 192 `user`, 8 `vault` (4.0%), 0 `subAccount` (0 of 200; 95% upper bound about
  1.5%). Sub-accounts appear not to be listed on the leaderboard under their own address, or
  are rare.
- 20 wallets (10%) are masters with 40 sub-accounts between them. Their own portfolio excludes
  the sub-accounts, so the entity rule in the plan must merge them.
- Vault fills: 5 of 8 vaults are complete; 3 are cut off (coverage 0.38 to 0.97).

## 6. Does the portfolio agree with the leaderboard?

The leaderboard file was saved at 23:58:51 UTC; wallets were fetched 0.5 to 3.9 h later. The
raw comparison (last portfolio point vs leaderboard) mixes data error with real changes after
the snapshot, so the script also reads the value at the last `day`-window point at or before
the snapshot (median 1.0 h earlier, max 2.3 h) and rolls allTime pnl back by the day-window
pnl change. Relative differences are reported only where the leaderboard value is at least
$100 in absolute size.

| Field | n | Median abs diff | Worst abs diff | Within $1 | Median rel | 99% rel | Worst rel | Rel > 1% | Rel > 10% |
|---|---|---|---|---|---|---|---|---|---|
| accountValue, last point | 200 | $0.004 | $129,656 | 124 | 0.48% | 8.5% | 11.1% | 34 / 95 | 1 / 95 |
| accountValue, at formation | 200 | $0.001 | $37,946 | 127 | 0.27% | 3.0% | 3.5% | 11 / 95 | 0 / 95 |
| allTime vlm | 200 | $0 | $38.8M | 184 | 0% | 14.2% | 91.0% | 5 / 188 | 2 / 188 |
| allTime pnl, at formation | 200 | $24 | $2.51M | 89 | 0.02% | 590% | 6,010% | 55 / 196 | 29 / 196 |
| perpAllTime pnl, at formation | 200 | $7 | $5.27M | 90 | 0.03% | 255% | 1,704% | 81 / 196 | 65 / 196 |

- **accountValue agrees** once timing is matched: worst relative gap 3.5% on balances of at
  least $100, and the remaining gaps fit the 1 to 2 h between the snapshot and the nearest
  day-window point.
- **Volume agrees exactly** for 184 of 200 wallets; the remaining differences are trading that
  happened between the snapshot and the fetch.
- **The leaderboard pnl field has no single definition.** Of 196 wallets with |pnl| >= $100,
  the leaderboard matches portfolio allTime pnl within 1% for 141, perpAllTime pnl for 115
  (82 match both because they trade only perps), allTime only for 59, perpAllTime only for 33,
  and **neither for 22 (11%)**, some by millions of dollars. The perp-only matches tend to be
  wallets with spot balances (spot transfers or genesis distributions), which suggests that the
  leaderboard sometimes drops the spot component, but the pilot cannot pin the rule down.
- Consequence: the leaderboard is fine as a frozen universe list and for accountValue and
  volume, but **its pnl must not be used as an outcome**. All outcomes should come from
  `portfolio` histories with the window (total or perp-only) fixed in the pre-registration.

## 7. Cost and projection to the full cohort

Weights follow the documented schedule in DATA.md section 0 (base 20, `userRole` 60, plus
`ceil(items/20)` per fill page). The run paced itself to 65% of the documented 1,200 per
minute, that is 780 weight per minute.

| Item | Value |
|---|---|
| Weight per wallet, median / mean / 90% / max | 477 / 819 / 1,792 / 9,041 |
| Weight by endpoint (total 163,795) | fills 139,795 (85%), userRole 12,000 (7%), portfolio, ledger and subAccounts 4,000 each |
| Requests | 2,055 (10.3 per wallet) |
| Server latency per wallet, median / mean | 2.8 s / 4.5 s |
| Wall time per wallet, median / mean / max | 57 s / 60 s / 668 s (almost all of it pacing waits) |
| Total wall time for 200 wallets | about 3.4 h |

Projection to all 48,035 wallets on one IP:

| Scope | At 780/min (65%) | At 1,200/min (100%, not advised) |
|---|---|---|
| All five endpoints, full fill history | about 841 h (35 days) | about 547 h (23 days) |
| portfolio + ledger + subAccounts + userRole | about 123 h (5.1 days) | about 80 h |
| portfolio + ledger + subAccounts (role taken from the vault list instead) | about 62 h (2.6 days) | about 40 h |
| portfolio alone (one refresh) | about 21 h | about 13 h |

The serial latency floor is about 60 h for all endpoints, so the weight budget, not latency,
binds. Storage is about 0.5 MB raw gzip per wallet with fills (105 MB for 200), so about 25 GB
for the full cohort with fills, under 2 GB without.

## 8. Verdict

**Yes, the free data is good enough for the flagship test, provided the test is built on
`portfolio` histories and not on fills or on the leaderboard pnl field.**

- `portfolio` returned a full allTime equity and pnl history for 200 of 200 wallets, back to
  account creation, consistent with the leaderboard's accountValue (worst 3.5% once timed) and
  volume (exact for 92%). It costs 20 weight per wallet, so the whole cohort can be pulled in
  under a day and refreshed weekly.
- Fills are complete back to the first deposit for about 77 to 80% of trading wallets, but the
  missing 16 to 20% are disproportionately the heavy traders, which is exactly the group a
  skill test cares about. A full fill crawl of the cohort would take about 35 days on one IP.
  Fills are therefore a secondary source for mechanism analysis on a subset, not the basis of
  the main test.

Restrictions the pre-registration must impose:

1. **Outcome source.** Dollar pnl and flows come from `portfolio` (`pnlHistory` and
   `accountValueHistory`), with the window fixed in advance (allTime or perpAllTime, and the
   same choice in formation and test). Never use the leaderboard `pnl` or `roi` fields as an
   outcome.
2. **Return grid.** The formation-period grid can be no finer than two weeks for every wallet,
   because 26% of the cohort's allTime series are two-weekly and the rest weekly; either use a
   common 336 h grid or use only total formation-period dollar pnl. Finer test-period data must
   come from forward recording: poll `portfolio` for the whole cohort at least every 3 weeks
   (the `month` window covers 30 days at 9 to 24 h spacing); weekly polling costs about 21 h of
   crawl per week at 65% of the budget.
3. **Minimum history.** Require the first allTime point at least 182 days before formation
   (176 of 200 sampled wallets qualify, 88%), or 365 days for a stricter variant (139 of 200,
   70%). Report results for the stricter cut as a robustness check, not as a second primary
   test.
4. **Dead and empty accounts.** 29 of 200 (14.5%) have accountValue 0 at formation and 12
   have no fills. Fix in advance whether they stay in the cohort (they should, for dollar pnl
   and survivorship) and how a return is defined when equity is zero.
5. **Entities.** Exclude vaults (4%) from the trader cohort or test them separately, and merge
   masters with their sub-accounts (10% of wallets have sub-accounts) before testing.
6. **Fill-based analyses.** Use only wallets whose retrieved fill notional covers at least 99%
   of portfolio allTime volume and that have no open-position-at-first-fill flag, or restrict
   to the retained window per wallet. State that this subset under-represents high-volume
   wallets (2 of 3 above $1B and 11 of 27 at $100M to $1B are cut off). Start the forward
   websocket recorder for any wallet whose history the test will need, because the retention
   cap keeps eating history every day.
7. **Snapshot time.** Treat portfolio data fetched up to a few hours after formation as
   formation data only after rolling it back to the formation time with the `day` window, as
   `pilot.py` does.

## 9. Reproduce

```bash
uv run python research/hyperliquid/pilot.py sample      # sample vs cohort, no network
uv run python research/hyperliquid/pilot.py fetch       # about 3.4 h cold, seconds from cache
uv run python research/hyperliquid/pilot.py summarize   # cache only, writes summary.json
uv run pytest tests/hyperliquid -q
```
