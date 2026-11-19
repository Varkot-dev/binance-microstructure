# C3 follow-up: Trump's tariff posts under time-local controls, Trump's posts only

Written 2026-11-19, **after** the C2 local-controls run (`data/c2_ranking_local.md`,
analysis run 2026-11-18T05:34:33Z) had been seen and **before anything in this document
was computed**. This is a **declared follow-up decided after seeing that result**, not a
pre-registered test. `PREREGISTRATION.md` (v1), `PREREGISTRATION_RANKING.md`,
`DEVIATION_LOCAL_CONTROLS.md` and their scripts and outputs stay frozen and unchanged.
The sha256 of this file is fixed in `c3_trump_tariff_local.py` and printed in the output;
the script refuses to run if this file has changed.

## 1. Why

v1 (`data/c1_trump_posts.md`) found that Trump's tariff and trade posts raise BTCUSDT
realized volatility over minutes +1 to +5 by +3.6 bps [1.1, 6.5] (199 clean events; 198
with the RT reclassification), with no rise in minutes -5 to -1. Its controls could lie
up to 26 weeks from the event. Under the C2 local-controls check (same minute of the week
within plus or minus 4 weeks, controls barred near **any** tracked politician's post, and
events dropped when another politician posted within 5 minutes) only 30 Trump tariff
events survived, with +2.48 bps [-0.60, 6.00], placebo p 0.25. Most of the loss came from
the cross-person rules, which remove busy weekday US hours, not from the narrower band.
This follow-up asks one question: **do Trump's tariff/trade posts move BTC volatility when
each post is compared only with nearby weeks, without other politicians' posts excluding
his events or his controls?**

## 2. Data

- Trump's Truth Social posts: `posts/truth_realDonaldTrump.csv`, the frozen v1 conversion,
  sha256 `d3ce5a47062fd0d92dff8dae92f3e616f2386f4b1d378a49eb5d4e40e374cf3c`. The script
  refuses to run if the hash differs. The known v1 mapping error (1,116 "RT: <url><own
  text>" quote posts labelled repost) is kept as-is.
- Trump's 2020 tweets: `posts/x_realDonaldTrump.csv` (9,793 rows, 2020-01-01 to
  2021-01-08), sha256 `42c3abaad0aa7e626cd31bc4a6e860a1272d654f1293bf759c8ed8a59c4819a7`,
  checked the same way.
- The two files are pooled into **one person**. No other account's posts are used for
  anything.
- Prices: the C2 grid, Binance USDT-M 1-minute klines for BTCUSDT, ETHUSDT and SOLUSDT,
  2020-01 to 2026-10 (the cached C2 files), v1 return and window definitions.
- Sample period: events from 2020-01-01 to the last minute whose +60 window lies before
  2026-11-01 00:00 UTC (as C2).

## 3. Events (v1 rules, unchanged)

- Topics: the v1 keyword rules frozen as in v1 (`c1_trump_posts.topic_of`), first match in
  the order crypto, tariffs, fed, else other; an event takes the first topic in that
  order among its merged posts.
- Candidate posts: original and quote only; reposts and replies are never events.
- Merge: candidate posts at most 5 minutes after the previous candidate post join its
  event (chaining); the event minute is the first post's minute
  (`c1_trump_posts.build_events`).
- Clean events: no earlier Trump event whose last post is within 60 minutes before.
- **No cross-person overlap rule**: other politicians' posts never exclude an event.

## 4. Controls

For an event (or placebo minute) at minute m, the candidates are m + 7j days for
j = -4, -3, -2, -1, +1, +2, +3, +4. A candidate is eligible if all closes from -6 to +60
around it exist and **no Trump post of any kind** (original, quote, reply or repost, either
file) has its post minute within 60 minutes of it. Other people's posts are ignored.
All eligible candidates are used; an event or placebo minute with **fewer than 6** is
dropped, and dropped events are counted per topic and reported. Abnormal value = event
value minus the mean over its eligible controls (`c2_ranking.pick_local_controls`,
`c2_ranking.abnormal_local`).

## 5. Outcomes and tests

- **Primary outcome**: abnormal BTCUSDT realized volatility (v1 `rv`, bps) over minutes
  +1 to +5, clean events, tariff/trade topic.
- **Primary test**: tariff minus other, the difference of mean abnormal rv, with a 95%
  percentile bootstrap interval (10,000 resamples within each group, seed 20261118) and a
  two-sided permutation p-value (10,000 label reshuffles), as in v1. Also reported, as in
  v1: the tariff mean with its bootstrap interval and placebo p (placebo pool of 20,000
  random minutes, seed 20261118, from minutes with a complete window and no Trump post
  within 60 minutes, each with the same local controls; pool minutes with fewer than 6
  controls are dropped).
- **Secondary** (descriptive, raw p only):
  - post minus pre: per tariff event, abnormal rv over +1..+5 minus abnormal rv over
    -5..-1 against the same controls; mean with paired bootstrap interval and placebo p;
    also the pre-window (-5..-1) mean by itself;
  - ETHUSDT and SOLUSDT abnormal rv +1..+5;
  - BTCUSDT abnormal absolute return, log volume and taker imbalance over +1..+5;
  - the same per-topic statistics for crypto, fed and other, for context.
- **Robustness**: the primary statistics and post minus pre (a) without 2025-10-10
  (events from 2025-10-10 00:00 to 2025-10-12 00:00 UTC dropped and control and placebo
  minutes in that span barred, as v1), (b) without 2025-04-09 (the same for 2025-04-09
  00:00 to 2025-04-10 00:00 UTC), and (c) without both.

## 6. Decision rule, stated in advance

The result **"supports an effect"** if the 95% interval of the primary test (tariff minus
other) excludes zero **and** the 95% interval of tariff post minus pre excludes zero.
Otherwise it **"does not support an effect"**. The verdict is computed in code and
printed with the direction of both estimates. Robustness runs and secondary outcomes do
not change the verdict; they are reported next to it.

## 7. Known limits

- Decided after seeing the cross-person local result, so it is a follow-up check on v1's
  tariff finding, not an independent confirmation; the tariff topic was chosen because
  v1 singled it out.
- Trump posts at the same hours week after week, so many events will lack 6 eligible
  nearby weeks even with only his own posts excluded; the kept events tilt toward hours
  where he posts less regularly.
- Other politicians' posts can sit inside event or control windows; with controls they can
  only raise control volatility, biasing toward zero.
- The 2020 tweets add events with a different platform and audience; they are pooled as
  one person as in C2.
