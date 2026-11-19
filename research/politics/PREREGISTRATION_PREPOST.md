# C4 pre-registration: did aggregate trading move unusually before Trump's posts?

Written 2026-11-19, **before any aggTrades file was downloaded and before any pre-post
window was opened** for this question. The sha256 of this file is printed in
`data/c4_prepost_trading.md`; `c4_prepost_trading.py` refuses to run if the file has
changed. Anything reported that is not specified here is labelled **exploratory**.

## What this can and cannot show

Binance public data is anonymous: no account, person or entity is attached to any
trade. This study can only show whether **aggregate** trading in the minutes before
posts was unusual compared with matched times. It can never show **who** traded, and
no person or entity is named or implied as having traded on information. It is a
statistical test, not an accusation. Even a positive result has innocent readings:
posts that react to news or to market moves already under way, other news at the same
time, or momentum in order flow.

Disclosure: C1 (`PREREGISTRATION.md`) already opened Binance 1-minute klines around
the same posts and reported pre-window volatility, absolute return and volume over
minutes -5 to -1 (tariff posts: nothing unusual) and post-window taker imbalance. It
did not compute any outcome defined below (aligned imbalance, large-trade share,
aligned pre-move, the -10 to -1 or -60 to -1 windows).

## 1. Events

Posts file: `posts/truth_realDonaldTrump.csv` (frozen v1 conversion, sha256
`d3ce5a47062fd0d92dff8dae92f3e616f2386f4b1d378a49eb5d4e40e374cf3c`), with the topic,
merge and clean rules of C1 (`PREREGISTRATION.md` sections 1 and 2, implemented in
`c1_trump_posts.py`: `topic_of`, `build_events`). Post minute m = the post time
(whole seconds in the file) floored to the minute. Sample period: event times from
2022-02-01 to 2026-10-31 23:00 UTC.

- **(a) Tariff events (tested).** Every clean v1 event with topic tariffs (223 events
  counted from the post file) that has complete data (section 2).
- **(b) Key named events (illustrations only, never tested):** 2025-01-18 02:00:51
  ($TRUMP launch post), 2025-03-02 15:24:20 (crypto reserve post), 2025-04-09 13:37:01
  ("great time to buy" post), 2025-04-09 17:18:40 (90-day tariff pause post),
  2025-10-10 14:57:52 and 2025-10-10 20:50:01 (China tariff posts). They are famous
  because markets moved, which selects on the outcome; one event cannot establish
  anything.
- **(c) Comparison sets.**
  - *Matched other events*: clean v1 events with topic other. For each tariff event in
    a random order (seed 20261119), draw up to 2 other events without replacement
    whose UTC hour of day equals the tariff event's hour; if none is left, the nearest
    hour (plus or minus 1, then 2, then 3, the earlier hour first). Candidates must
    have complete data on the same data source, and their time must be more than
    2 hours from every tariff event and every already drawn control.
  - *Placebo times*: random minutes with no post of any kind (original, quote or
    repost) whose post minute lies in [p-70, p+20], more than 2 hours from every
    tariff, key and drawn other event, and with complete data from -70 to +16.
  Controls and events never share a window: every window used is [-70, +16] minutes
  around its anchor, and anchors are more than 2 hours apart.

## 2. Data

- **aggTrades (primary).** Binance USDT-M daily aggTrades files from
  data.binance.vision, each verified against Binance's published SHA-256
  (`microstructure.data.binance.download`), parsed with
  `microstructure.data.ingest.ingest_agg_trades` and collapsed to aggressor events
  with `microstructure.data.events.to_aggressor_events` (one event per (ms timestamp,
  side); sign +1 when the buyer is the taker). Each day is reduced at once to
  per-minute bars (taker buy and sell notional, aggressor-event count, count and
  notional of large events, last price), cached under `data/politics/prepost/`
  (git-ignored); raw zips and parquet files are deleted after use.
- A window needs the daily file of every UTC date that [m-70, m+16] touches (the
  context span of -2 hours to +30 minutes is not needed for any outcome and is not
  downloaded separately).
- **Budget rule (fixed now).** All tariff days on BTCUSDT are estimated at about
  3.8 GB, so the budget (under 4 GB) cannot hold all symbols. Order of downloads:
  1. BTCUSDT, ETHUSDT and SOLUSDT for the dates of the key events (b);
  2. BTCUSDT for the tariff events, in a random order (seed 20261119), one event's
     dates at a time.
  No new download starts once 3.7 GB have been downloaded in total. Tariff events
  whose dates were not reached are "not downloaded (budget)"; because the order is
  random, the analysed set is a random subset. Matched other events and placebo
  times for the aggTrades analysis are drawn only from BTCUSDT dates that were
  downloaded (so they come from the same days as the tariff events), placebo times up
  to 6 per downloaded date of a tariff event (seed 20261119).
- **1-minute klines (free, already on disk from C1, SHA-256 checked).** Used for
  (i) the volume outcome, which needs control weeks, and (ii) a full-sample
  replication for BTCUSDT, ETHUSDT and SOLUSDT over all 223 tariff events, with
  imbalance = (2 x taker-buy volume - volume) / volume (base-asset quantity). For the
  kline analysis the matched others are drawn from all clean other events (same hour
  rule, plus the same calendar year) and placebo times are a pool of 20,000 minutes
  drawn uniformly over the sample period (seed 20261119) under the placebo rule
  above.
- ETHUSDT and SOLUSDT aggTrades are used only for the key-event illustrations.

## 3. Outcomes

Minute k is the minute starting at m + k minutes. Pre-windows: **-10 to -1
(primary)** and -60 to -1 (secondary). Minute 0 is in no window.

- **Post move and alignment sign.** P(k) = last trade price in minute k (aggTrades) or
  the close (klines). The BTC move over +1..+15 is ln(P(15)/P(0)); s = its sign. For
  the guard, s5 = sign of ln(P(15)/P(4)) (minutes +5..+15 only). Events with a zero
  move get no sign and are left out of aligned outcomes. ETH and SOL flows are aligned
  with the BTC sign.
- **Signed taker order-flow imbalance** over window W: (taker buy notional - taker
  sell notional) / (taker buy notional + taker sell notional) over aggressor events in
  W. **Aligned imbalance** = s x imbalance. Positive means pre-post flow went the same
  way as the later BTC move.
- **Relative volume** (klines): ln(volume over W / mean volume over the same W at the
  same minute of the week in weeks -4..-1 and +1..+4), using only control weeks with
  no post of any kind in [c-70, c+16] and complete data, at least 3 of them, else
  missing.
- **Large-trade share**: the share of aggressor events in W whose notional is in the
  top 0.1% of aggressor-event notional over the whole UTC day of that event's file
  (threshold computed from the full day before reduction). Also, secondary, the
  aligned imbalance of large events only (s x signed large notional / large notional,
  missing if there is none).
- **Aligned pre-move**: s x ln(P(-1)/P(-11)) in bps for -10..-1, s x ln(P(-1)/P(-61))
  for -60..-1.

## 4. Tests

- **Primary statistic**: D = mean aligned imbalance (BTCUSDT aggTrades, -10..-1, sign
  from +1..+15) over tariff events minus the mean over matched other events. 95%
  percentile bootstrap interval (10,000 resamples within each group, seed 20261119);
  one-sided permutation p for D > 0 (10,000 shuffles of the tariff/other labels, +1
  correction); the two-sided p is reported beside it.
- **Against placebo times**: one-sided placebo p = share of 10,000 means of n
  placebo times (drawn without replacement, n = number of tariff events) that are at
  least the tariff mean. Also the fraction of tariff events whose aligned imbalance is
  above the 95th percentile of the per-placebo distribution, with a one-sided
  binomial p against 5%.
- **Guards against mechanical alignment**: (1) the same statistics with the sign s5
  (+5..+15); (2) the post time shifted 60 seconds earlier (so m becomes the minute of
  t - 60 s, and all pre-windows move one minute earlier), with the sign kept from the
  recorded time, to check that a slightly late timestamp is not putting the reaction
  into the pre-window.
- **Secondary, descriptive** (same D, interval and permutation p, and placebo p):
  -60..-1; relative volume; large-trade share and large-trade aligned imbalance;
  aligned pre-move; the kline full-sample replication for BTCUSDT, ETHUSDT, SOLUSDT;
  BTCUSDT without 2025-10-10 and 2025-10-11.

## 5. Decision rule (stated in advance)

Report **"evidence of unusual pre-post trading"** only if the primary D (tariff events
minus matched other events, aligned imbalance, -10..-1, sign +1..+15) is above zero
with one-sided permutation p < 0.05 **and** the same holds with the sign from
+5..+15 (D > 0, one-sided permutation p < 0.05). Otherwise report **"no evidence"**.
"No evidence" is not proof that nothing happened: the interval says how large an
effect the data can rule out. Either way, the result concerns anonymous aggregate
flow only and identifies no one.

## 6. Key events: illustrations only

For each key event: BTC, ETH and SOL aligned imbalance over -10..-1 and -60..-1, the
large-trade share, the aligned pre-move, and the percentile of the aligned imbalance
among the BTC placebo times (BTC) or among placebo times on the key dates (ETH, SOL).
Each is labelled as an illustration; one event cannot establish anything.

## 7. Expectations, stated before looking

Aligned imbalance is probably slightly positive even at random times (order flow
predicts short-horizon returns), which is why the test is against matched controls.
From C1 (no unusual pre-window volatility before tariff posts) the expectation is
"no evidence".
