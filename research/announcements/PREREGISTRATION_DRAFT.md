# D1 pre-registration (DRAFT, not frozen): price and volume before Binance listing and delisting announcements

Drafted 2026-11-19 for review by the main session and the user. **Not frozen.** Written
before any announcement time was matched to a price and before any 1m kline near an event
was downloaded. When frozen, its sha256 goes into the analysis output and the analysis
script refuses to run if the file has changed (as in `research/politics/PREREGISTRATION.md`).
Anything reported that is not specified here is labelled **exploratory**. Items marked
**[open]** need a decision before freezing.

## 0. Question

Before Binance publishes a notice that it will launch, or delist, a USDT-M perpetual, do
the coin's price and trading volume move in the direction the notice would cause (up and
more volume for a listing, down and more volume for a delisting), beyond what the market
and the coin's own recent history predict?

A positive answer means information reached the market before the notice. It does **not**
by itself show insider trading (section 8).

## 1. Inputs

- Announcements: `research/announcements/data/announcements.csv`, from Binance's list
  endpoint (release time in UTC to the second) or `MANUAL_TEMPLATE.csv` (minute). Only
  titles, codes and times. Its sha256 is recorded at freeze time.
- Contract lives: `research/market_evolution/data/contract_lifecycle.csv` (sha256 at freeze).
- Prices and volume: 1-minute klines from data.binance.vision, each SHA-256 checked, using
  close, quote volume and taker-buy quote volume. Listings: Binance **spot** klines of the
  coin (the perpetual does not trade yet). Delistings: **futures** klines of the perpetual.
  Market: BTCUSDT from the same market (spot for listings, futures for delistings).
- Context only: month-end open interest from `data/panels/monthly_panel.parquet`.
- Reused code: `fetch_day` / `Ledger` style SHA-checked downloads and the permutation
  helpers in `research/market_evolution/e3_event_study.py`.

## 2. Event sets

Event time tau = the announcement's release time (UTC). For minute or day precision see
section 6.

**L (futures listings with a prior price).** A notice "Binance Futures Will Launch
USD-M ... Perpetual" whose contract matches a life in the lifecycle (first trade day 3
days before to 60 days after tau), with all of:
- life kind `new` (not a relisting of an old ticker, not a rename successor);
- the Binance spot pair (`X` or, for `1000X` style contracts, `X`) traded on the day before
  tau and 35 days before tau (`spot_status = spot_before_with_baseline`, re-checked
  against tau rather than the futures first day);
- no Binance spot listing notice for the same coin in [tau - 33 days, tau].
Expected size from the inventory: about 109 contracts (2023: 59, 2024: 37, 2025: 13). Notices
that launch several contracts are one cluster.

**D (futures delistings).** The first Binance notice (Delisting catalog, spot or futures)
naming the coin's removal, where the perpetual's last trade day falls 0 to 60 days after
tau. If a spot delisting notice comes first and the futures notice later, tau is the spot
notice (the futures notice is then not news). Lives with status `delisted` or the first
life of a reused ticker; renamed, merged and index contracts excluded; regulatory or product
removals (BUSD and similar) excluded. Expected size: up to 141 contracts in fewer notices.

**[open]** Whether to add L2: futures listings whose coin traded only on other venues
(about 600 lives, mostly 2025 to 2026). Needs Bybit, OKX or Gate history; those hosts are
refused by the proxy now.

## 3. Outcomes

Hourly bars are built from the 1m klines; hour h covers [tau + h, tau + h + 1) with h in
hours relative to tau. Log return r_h = ln(close at the end of the hour / close at the end
of the previous hour); volume v_h = quote volume in the hour.

Windows (both end 1 hour before tau, so a release time off by up to an hour cannot put the
reaction inside the window):
- **W72 = hours -72 to -2 (bars covering [tau - 72h, tau - 1h))**, primary;
- **W24 = [tau - 24h, tau - 1h)**, secondary.

For each event i and window W:

1. **CAR_mkt** (relative to BTC): sum over W of r_ih - beta_i r_BTC,h, with beta_i from an
   OLS of hourly r_i on r_BTC over the estimation period E = [tau - 33 days, tau - 3 days)
   (720 hours). Also reported: beta fixed at 1.
2. **CAR_own** (relative to the contract's own prior 30 days): sum over W of r_ih - mean of
   r_i over E.
3. **AV** (abnormal volume): ln(sum of v over W) minus the mean of ln(sum of v over W - 24k
   hours) for k = 4 to 33, i.e. the same clock hours on the 30 days of E. Also the market
   version: the same quantity for the contract minus the same quantity for BTCUSDT.
4. Each outcome is also **standardized** per event by the standard deviation of the same
   statistic over the 30 shifted windows W - 24k hours, k = 4 to 33 (for CAR, computed with
   the same beta). These 30 shifted windows are the event's own null distribution (section 5).
5. Context only (D): month-end OI in the two months before tau, and the ratio of OI to its
   level six months earlier. Not tested.

Expected signs, fixed now: L: CAR > 0, AV > 0. D: CAR < 0, AV > 0.

## 4. Controls

- **Same-clock placebo times (within event).** The 30 windows W - 24k hours, k = 4 to 33,
  give the event's own distribution at the same time of day. The event's rank among its 31
  windows is the per-event statistic for the rank test.
- **Placebo announcement times (across events).** For each event, the same window ending at
  tau - 7 days and tau - 14 days ("fake taus"): the full pipeline is run on them and must
  show no effect.
- **Matched non-announced contracts.** For each event, up to 5 contracts with no Binance
  listing or delisting notice within 60 days of tau, matched on the month before tau:
  - D: quote volume (log), drawdown from peak (`dd_month_end`), age in months, last-month
    return, and OI (log); from the same risk set the delisting baseline model uses, so the
    controls are also weak, low-volume contracts. The matched-control difference is the
    answer to "the coin was already drifting down" selection.
  - L: Binance spot coins without a futures contract at tau, matched on spot log quote
    volume, 30-day return and age. **[open]** whether enough such coins exist after 2024.
  The outcome for the difference is CAR_i - mean of the controls' CAR on the same window.

## 5. Statistics

- **Unit of inference: the notice.** Contracts named in the same notice are averaged first
  (a delisting notice often names 3 to 10 contracts on the same day).
- **Mean effect and CI:** cross-notice mean of each outcome; 95 % CI by bootstrap over
  notices (B = 9,999, percentile; seed fixed at freeze).
- **Rank permutation test (primary p-value):** under the null the event window's rank among
  its 31 same-clock windows is uniform; the test statistic is the mean standardized outcome
  over notices; its null distribution draws, for each notice independently, one of its 31
  windows (B = 9,999). One-sided in the expected direction for the primary tests, two-sided
  reported alongside.
- **Matched-control test:** permutation of the treated label within each matched set
  (B = 9,999).
- **Primary tests (4):** L-CAR_mkt-W72, L-AV-W72, D-CAR_mkt-W72, D-AV-W72. Holm correction
  at 5 % across the four. Everything on W24, CAR_own, beta = 1 and the control difference is
  secondary (reported with unadjusted p-values, labelled secondary).
- **Power, before looking:** the minimum detectable effect is computed from the placebo
  windows only (fake taus at -7 and -14 days), before the event windows are opened.
  **[open]** whether this counts as looking at price data; if so it is done after freezing
  and reported as such.

## 6. Data rules and exclusions

- tau precision: second (API) or minute (manual) are used as is. Day-only events go to a
  secondary set with tau = 00:00 UTC of that day and W ending at tau - 1h (conservative:
  the window then ends before the notice).
- An event is dropped (per contract) if more than 5 % of the 1m bars in W or E are missing,
  or the price was flat (no trade) in more than 20 % of hours in W.
- Overlap: drop a contract-event if any other Binance notice naming the same coin (tick,
  funding, leverage or margin tier, Monitoring Tag, Vote to Delist, spot listing or
  delisting) was published in [tau - 33 days, tau). These are listed, not silently removed.
  Monitoring Tag and Vote to Delist status are reported as subgroups for D (section 8).
- Market-wide days: none excluded; BTC adjustment and controls handle them.
- Sample: tau from 2023-01-01 to 2026-10-31 (delistings: last trade day by 2026-11-16).

## 7. Decision rules

- **"Pre-announcement move" for a set** if, on W72: the Holm-adjusted rank-test p < 0.05
  in the expected direction, the bootstrap CI excludes 0, and the matched-control
  difference has the same sign. Report effect sizes in percent (CAR) and percent volume.
- **"No detectable move"** if the 95 % CI excludes effects larger than the MDE from section
  5; otherwise "inconclusive".
- A significant effect of the wrong sign is reported as such, not as support.
- The fake-tau runs (-7 and -14 days) must show no effect at the same threshold; if they
  do, the main result is reported as not credible (drift unrelated to the notice).

## 8. Guard: leaks through public channels are not insider trading

A pre-announcement move is compatible with public information. Before reading any positive
result as leaked private information:
- **Spot first, other venues first:** for L, the coin may already be rumored or listed on
  futures at other exchanges; Binance often lists futures after a coin's spot volume rises.
- **Public warnings for D:** Monitoring Tag (monthly reviews), Vote to Delist, delisting
  criteria based on low volume and crashes. A drift down before delisting can be the
  selection rule itself (Binance delists coins that are falling). The matched controls and
  the Monitoring Tag subgroup address this, but only partly.
- **Project and social channels:** project teams, Binance Square, X, Telegram and news can
  publish before the notice's release time; the release timestamp may be later than the
  first public visibility (app push, email, pre-scheduled posts).
- **Scheduled patterns:** delistings cluster on certain weekdays and listing notices at
  certain hours; anticipation of a pattern is not a leak.
So the strongest claim the design supports is "information arrived before the official
notice", with a timing profile (W72 versus W24, hour-by-hour CAR) as description.

## 9. Data each piece needs

| piece | data | status |
|---|---|---|
| tau | announcement list with release time | **missing**; host refused, manual route in README |
| event-contract match | lifecycle + announcement symbols | lifecycle ready; matcher ready (`d1_inventory.py match`) |
| L prices and volume | Binance spot 1m klines of the coin, tau - 35 days to tau | in archive for about 140 lives (S3 check), not downloaded |
| D prices and volume | futures 1m klines, tau - 35 days to tau | in archive for all 141 lives, not downloaded |
| market | BTCUSDT spot and futures 1m klines | in archive |
| launch or settlement minute | first or last 1m kline with volume | in archive |
| controls | monthly panel (D); spot 1d klines for coins without futures (L) | D ready; L to be built |
| overlap exclusions | catalogId 49 titles (tick, funding, tag notices) | missing, same route as tau |
| OI context | monthly panel | ready |

## 10. Expectations, stated before looking

D: a negative CAR and higher volume in W72 are likely, mostly from public warnings and
selection; the matched-control difference is expected to be much smaller. L: small positive
CAR, uncertain, since most L events are long-listed spot coins whose futures launch is less
news than a new token listing.
