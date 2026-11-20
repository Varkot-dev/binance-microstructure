# DRAFT: cascade event definition and matched control periods

**Status: DRAFT, not locked.** Nothing here may be treated as pre-registered until the open choices in
section 8 are fixed, the word DRAFT is removed, the file is committed, and its hash is recorded. The
thresholds were proposed after exploratory looks at 2025-10-10 and at COIN-M liquidation data
(DATA.md section 6); the locked version must disclose that and should be validated on symbols and
periods nobody has looked at.

Design principles, each with its source:

- Define events on information measured at or after onset, and warnings strictly before it, so the
  event rule cannot mechanically produce the warning (Andersen and Bondarenko 2014, JFM 17, 1-46).
- Evaluate signals prospectively over all time, not only before events (Kaminsky, Lizondo and
  Reinhart 1998, IMF Staff Papers 45(1)).
- Count independent market-wide episodes, not contract-events.
- Control multiple testing in jump detection (Bajgrowicz, Scaillet and Treccani 2016, Management
  Science 62(8), 2198-2217).

## 1. Inputs

Per USDT-M perpetual `i`, all from data.binance.vision (DATA.md):

- 1m `klines` (last price, quote volume, taker buy volume) and 1m `markPriceKlines`.
- `aggTrades` (exact signs; ID gaps).
- 5-minute `metrics` (OI), after the metrics screen (spike-and-reverse rows removed, label convention
  fixed; see section 6).
- bookDepth is **not** used in the event rule, because it is corrupted on the main event (2025-10-10)
  and because depth is a candidate warning variable.

Universe: USDT perpetuals with at least 30 days of history and at least USD 5M median daily quote
volume over the trailing 30 days (threshold to fix), excluding TradFi, equity, commodity and
pre-market contracts (mask rule X6).

## 2. Price leg: dated onset

Let `r_t` be the 1-minute log return of the **last price**. (Mark price is a smoothed composite of
index and basis and damps jumps; it is used for drawdowns in section 4, not for detection.)

Lee and Mykland (2008) statistic with a jump-robust local scale and periodicity correction:

```
L_t = r_t / (f_tow(t) * sigma_hat_t)
sigma_hat_t^2 = MedRV over the K-1 minutes before t            (Andersen, Dobrev and Schaumburg 2012)
f_tow       = robust time-of-week volatility factor              (Boudt, Croux and Laurent 2011)
jump at t   if (|L_t| - C_n) / S_n > beta*,  beta* = -log(-log(1 - alpha))
```

Proposed: K = 120, alpha set per contract-day and then tightened to a universal threshold across the
panel (about 4.7e8 contract-minute tests). Exploratory check on BTCUSDT 2025-10-10 (mark price, K =
120, alpha 1% per day, |L| > 5.78, no periodicity correction): 10 flagged minutes, 9 of them between
20:52 and 21:21 UTC, largest -463 bp at 21:19 (L = -16.6), with +163 bp at 21:18 and +248 bp at 21:21.
Sign reversals inside the cluster mean a single-jump rule is wrong.

**Onset** `t0` for a down cascade: the first jump in a cluster of at least 2 significant negative jumps
within 30 minutes, **and** cumulative mark-price return over `[t0, t0 + 60m]` at most `-k sigma60_i`,
where `sigma60_i` is the trailing 30-day standard deviation of 60-minute returns ending at `t0 - 6h`.
Proposed `k = 4`. Up cascades mirror the rule (short squeezes) and are analysed separately.

Robustness detector: the drift-burst t-statistic of Christensen, Oomen and Reno (2022, J. Econometrics
227(2)), because a forced-selling spiral is a locally explosive drift as much as a jump. Report the
agreement between detectors.

## 3. Forced-flow leg: was the move forced?

There is no USDT-M liquidation history, so forced flow is inferred. Exploratory COIN-M validation
(DATA.md section 6) shows the 5-minute OI drop is a poor timer (AUC 0.60 to 0.65 for top-1% liquidation
bins, and OI rose in 34 to 47% of the top 0.1% bins), while quote volume tracks liquidations closely
(AUC 0.95 to 0.98). OI becomes informative when summed over 1 to 4 hours. On 2025-10-10 the Binance OI
decline across 10 contracts reached half its total at 21:40 and three quarters at 22:05 UTC, after
Hyperliquid liquidations (half by 21:15 to 21:20). The novelty reviewer saw the largest BTCUSDT 5-minute
OI drop at the 21:15 label with the mark low at 21:20; the lag is therefore treated as unknown, and the
OI window is made long enough not to depend on it.

The forced-flow leg holds if **both**:

1. **Activity burst.** Quote volume over `[t0, t0 + 30m]` is above the 99.9th percentile of the same
   contract's 30-minute volume in the trailing 30 days, at the same hour of week (computed with data
   ending at `t0 - 6h`).
2. **Deleveraging.** `Delta log OI` over `[t0 - 5m, t0 + 120m]` is at most the contract's trailing
   30-day 1st percentile of 125-minute changes and at most -3%.

Supplementary marker (reported, not required): aggTrades ID gaps over `[t0, t0 + 30m]` above the
contract's trailing 99.9th percentile of gap counts. On COIN-M, gaps were perfectly specific (every
hour with a gap had a snapshot liquidation; no gap on 314 no-liquidation days) but only 12.5% sensitive,
so requiring them would drop half of large episodes. On USDT-M a background of single-ID gaps from
about 2024-11 (step on 2025-08-06 about 15:00 UTC, LINKUSDT) must be modelled first.

Why these legs are not circular: both are measured at or after `t0`. Warning features (README P5) are
measured in `[t0 - 6h, t0 - g]` with `g = 15 min`, and every warning test includes pre-window volume
and realized volatility in its baseline. OI build-up before `t0` may be a warning feature; the OI leg
here measures the fall after `t0`.

## 4. Severity outcomes (for the cross-section, README P3)

Measured for **every** live contract on each market-wide episode date, not only those that triggered,
to avoid truncation on the outcome:

- `DD_i` = max drawdown of the **mark price** over `[t0_mkt, t0_mkt + 2h]` relative to the close at
  `t0_mkt - 1m`.
- NCSKEW and DUVOL of 1-minute returns over the same window (Chen, Hong and Stein 2001, JFE 61(3)).
- `Delta log OI` over `[t0_mkt - 5m, t0_mkt + 4h]`.
- Recovery: half-life of masked bookDepth within plus or minus 1% (README P4), only where mask rule D2
  passes. Price-based recovery: time to retrace 50% of `DD_i`.

## 5. Declustering and market-wide episodes

- Within a contract, a new event needs at least 6 hours with no flagged jump since the previous event.
- A **market-wide episode** is a 60-minute window in which at least 20% of universe contracts have an
  onset; `t0_mkt` is the median onset time. Contracts triggering inside an episode are not separate
  observations for timing questions.
- **Unit of inference** is the episode. Standard errors clustered by episode, or block bootstrap over
  episodes; power is stated in number of episodes `E`, expected to be on the order of 5 to 15 for
  2023 to 2026.
- Candidate episodes to check against the locked rule, not to hand-pick: 2024-08-05 (about 01:00 to
  06:00 UTC), 2025-02-03, 2025-04-07, 2025-10-10 (about 20:50 to 21:30 UTC). Anchor COIN-M liquidation
  hours for validation: 2024-04-12 18h, 2024-04-02 03h, 2024-03-11 13h, 2024-08-05 01h and 06h,
  2023-08-17 21h, 2024-03-05 05h and 19h, 2024-04-13 20h, 2023-12-11 02h.

## 6. Data-quality conditions

- Metrics: remove rows where `|dOI| > 3 x` rolling 2-hour median `|dOI|` and the next row reverses at
  least 90% of it (BTCUSDT 2025-10-10: +736.4M at 21:45, -717.1M at 21:50). State the `create_time`
  convention (end-of-period before 2026-06-25, start-of-period after, issue #491); results must be
  robust to a one-row shift.
- Klines and aggTrades: drop contract-days with missing files (issue #525, 2026-10-28) or duplicated IDs
  (issue #529, 2025-08-29).
- Contracts with a tick-size change within 48 hours of `t0` are flagged and excluded from the
  cross-section (from `research/market_evolution/data/tick_events.csv`).
- Delisting final hours (insurance fund not used; IOC then ADL) are excluded.

## 7. Matched control periods

For each contract-event `(i, t0)`, draw up to 8 control times `c` with:

- same contract `i`;
- same hour of week as `t0` (within plus or minus 30 minutes), within plus or minus 4 weeks;
- no event (any contract in an episode, or contract `i` alone) within 24 hours of `c`;
- matching variables measured **only** on data ending at `c - 6h - 1h` (before the pre-window plus a
  buffer): trailing 7-day realized volatility, trailing 7-day quote volume, last funding rate, and BTC
  trailing 7-day realized volatility. Nearest-neighbour matching with replacement and the bias
  correction of Abadie and Imbens (2006, Econometrica 74(1));
- the same data-quality conditions as the event window (mask D2 for any depth feature).

Rationale: the repo's Trump-tariff result disappeared once each post was compared with the same time
of week in nearby weeks (`research/politics/data/c3_trump_tariff_local.md`). Pre-cascade hours are
often in the late US session or near funding times, which have their own seasonality. Matching on
variables measured inside the pre-window would match the warning signal away.

For the prospective test (README P5), controls are replaced by evaluating every contract-hour, with
case-control subsampling only if needed and the King and Zeng (2001) prior correction.

## 8. Event classes

Pre-register three classes before computing any signal:

- **News shock:** a dated item from a fixed calendar (FOMC, CPI, tariff announcements, repo politics
  data) within 30 minutes before `t0`, and no second item in `[t0 - 6h, t0 - 30m]`.
- **Endogenous:** no dated item in `[t0 - 6h, t0]`.
- **Mixed:** dated items both inside `[t0 - 30m, t0]` and earlier in the pre-window. 2025-10-10 is
  mixed: Trump posts at 14:57:52Z and 20:50:01Z, with the long/short account ratio rising from 1.048
  (16:00) to 1.274 (19:00) and BTC mark falling from about 121.3k to 116.6k between them. Report it
  separately, never pooled into "exogenous".

## 9. Open choices to fix before locking

| Choice | Proposal | Alternatives for the sensitivity table |
|---|---|---|
| Jump window K | 120 minutes | 60, 240 |
| Price threshold k | 4 sigma60 | 3, 5 |
| Volume percentile | 99.9th | 99.5th |
| OI window and threshold | `[t0-5m, t0+120m]`, 1st percentile and -3% | +60m, +240m; -2%, -5% |
| Declustering | 6 h | 3 h, 12 h |
| Market-wide share | 20% of universe in 60 min | 10%, 33% |
| Universe floor | USD 5M median daily volume | 1M, 20M |
| Up cascades | separate analysis | excluded |

Report the sensitivity table as a small pre-declared grid, not a search, and report the event count
for each cell. Validate the volume and OI legs against COIN-M liquidationSnapshot (deduplicated,
outage days masked) on a held-out set of COIN-M symbols before applying the rule to USDT-M.
