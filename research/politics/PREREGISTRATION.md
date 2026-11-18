# C1 pre-registration: Trump's Truth Social posts and crypto futures

Written 2026-11-18, after the post file was built and validated and **before any price
data was downloaded or opened**. The sha256 of this file is printed in
`data/c1_trump_posts.md`; the analysis script refuses to run if the file has changed.
Anything reported that is not specified here is labelled **exploratory**.

## 0. Inputs

- Posts: `research/politics/posts/truth_realDonaldTrump.csv`, 38,074 rows, 2022-02-14 to
  2026-11-17, sha256 `d3ce5a47062fd0d92dff8dae92f3e616f2386f4b1d378a49eb5d4e40e374cf3c`
  (kinds: original 30,186, repost 7,580, quote 308, reply 0; mapping in the docstring of
  `c1_trump_posts.py`).
- Prices: Binance USDT-M perpetual 1-minute klines for BTCUSDT, ETHUSDT and SOLUSDT,
  monthly files 2022-02 to 2026-10 from data.binance.vision, each SHA-256 checked. Only
  the close, volume and taker-buy volume columns are used. Minute t is the bar that
  opens at t. The minute log return is r_t = ln(close_t / close_{t-1}).

## 1. Topic rules (text only)

Each post's `text` field is matched case-insensitively against the patterns below, each
pattern bounded by non-word characters on both sides (no letter, digit or underscore
directly before or after). Nothing but the text is used: not the time, the kind, the
media flag, the reposted handle, or any market data.

- **crypto**: `bitcoins?`, `btc`, `crypto\w*`, `blockchains?`, `stablecoins?`,
  `digital assets?`, `digital currenc(y|ies)`, `cbdcs?`,
  `central bank digital currenc(y|ies)`, `ethereum`, `solana`, `xrp`, `memecoins?`,
  `meme coins?`, `$trump`, `$melania`, `world liberty`, `worldlibertyfi`, `wlfi`,
  `coinbase`, `binance`, `genius act`, `clarity act`, `defi`, `nfts?`, `satoshi`.
- **tariffs** (tariffs and trade): `tariff\w*`,
  `trade (deals?|wars?|deficits?|agreements?|negotiations?|surplus(es)?|imbalances?|partners?|talks|barriers?|policy|policies)`,
  `reciprocal`, `liberation day`, `export controls?`, `anti-dumping`, `section 232`,
  `section 301`, `usmca`, `wto`, `customs duties`, `import (taxes|tax|duties)`.
- **fed** (Fed and rates): `federal reserve`, `the fed`, `fed chair\w*`, `fed's`,
  `powell`, `interest rates?`, `rate (cuts?|hikes?)`,
  `(cut|lower|raise|reduce) (interest )?rates`, `rates (down|should|must)`,
  `basis points`, `fomc`, `monetary policy`, `warsh`, `"too late"` (in straight,
  curly or single quotes), `mr.? too late`.
- **other**: everything else, including media-only posts with empty text.

A post matching several lists takes the first in the order crypto, tariffs, fed. An
event (section 2) takes the first topic in that order among its merged posts. Known
noise, accepted rather than tuned: `powell` also hits unrelated people named Powell,
`reciprocal` can be non-trade, and crypto content in images or linked pages is missed.

## 2. Event rules

1. Candidate posts: kind `original` or `quote` only. Reposts and replies are never events
   (but they do count as "posts" for control eligibility, rule 5).
2. Post minute m = the post's `created_at_utc` floored to the minute.
3. Merge: sort candidate posts by time; a post less than or equal to 5 minutes after the
   previous candidate post joins that post's event (chaining). The event time is the
   time of its first post.
4. Clean sample (primary): drop an event whose time is less than 60 minutes after the
   last post of the previous event. The full merged sample is secondary.
5. Control windows: for an event at minute m, candidate control minutes are m + 7j days
   (j = -1, +1, -2, +2, ..., -26, +26, in that order). A candidate is eligible if no post
   of any kind (original, quote or repost) has its post minute within 60 minutes of it
   (|post minute - candidate| <= 60), and all closes from minute -6 to +60 around it
   exist. The first 16 eligible candidates are the controls. An event with fewer than 16
   eligible controls is dropped. The event's own window must also have all closes from
   -6 to +60, or the event is dropped (per symbol).
6. Sample period: events from 2022-02-01 to the last minute where the +60 window still
   lies inside the price data (2026-10-31).

## 3. Outcomes

Windows are in minutes relative to the post minute m (minute 0 is excluded from every
window because the post can arrive late in it):

- post5 = minutes +1 to +5 (primary), post15 = +1 to +15, post60 = +1 to +60,
  pre5 = -5 to -1 (pre-window test).

For a window W:

- absret = |sum of r_t over W| in basis points (the absolute log return across W).
- rv = sqrt(sum of r_t^2 over W) in basis points (realized volatility).
- ret = sum of r_t over W in basis points (signed).
- logvol = ln(sum of volume over W).
- imb = (2 x sum taker-buy volume - sum volume) / sum volume over W.

Abnormal outcome of an event = its value minus the mean of its 16 controls' values
(for logvol: its log volume minus the mean of the controls' log volumes).

- **Primary outcomes**: BTCUSDT abnormal absret and abnormal rv over post5, clean sample.
- **Secondary**: the same over post15 and post60; abnormal logvol and imb; ETHUSDT and
  SOLUSDT versions of all of these; abnormal signed ret for crypto events (no tone
  coding; the mean is reported, not tested against a direction); the full merged sample.

## 4. Statistics

- Per topic: mean abnormal outcome over events, with a 95% percentile bootstrap interval
  (10,000 resamples of events within the topic, seed 20261118). The median is reported
  alongside as a description.
- **Placebo inference (random post times).** A pool of 20,000 placebo minutes is drawn
  uniformly (seed 20261118) from all minutes in the sample period that have no post of
  any kind within 60 minutes and a complete -6 to +60 window; each placebo minute gets
  16 controls and abnormal outcomes by exactly the rules of section 2 and 3 (placebos
  with fewer than 16 controls are dropped from the pool). For a topic with n events,
  10,000 placebo means are formed from n pool minutes drawn without replacement. The
  two-sided p-value is 2 x min(share of placebo means >= observed, share <= observed),
  capped at 1, with the usual +1 correction. Subgroup analyses (section 5) draw
  placebos only from pool minutes that meet the same subgroup condition.
- **Primary comparison**: crypto vs tariffs vs fed vs other. For each of crypto, tariffs
  and fed: the difference of its mean abnormal outcome from the mean for other, a 95%
  bootstrap interval (resampling within each group), and a permutation p-value
  (10,000 reshuffles of topic labels between the two groups).
- **Multiple testing**: the primary family is 2 outcomes x 4 topics (placebo p-values)
  plus 2 outcomes x 3 comparisons; Holm adjustment within each of these two sets is
  reported next to the raw p-values. Secondary results get raw p-values only and are
  read as descriptive.
- **Pre-window test**: the same per-topic statistics on pre5 (abnormal absret and rv),
  plus the per-topic difference post5 minus pre5 with a bootstrap interval (events
  resampled, both windows taken from the same resampled events). If pre5 is as elevated
  as post5, the posts are read as reactions to moves already under way, not causes.
- **Stacked check (secondary)**: per-minute |r_t| (bps) for minutes -5..-1 and +1..+5 for
  each event and its 16 controls; regress on D = real window x post minute with window
  fixed effects and event-by-minute fixed effects, errors clustered by event
  (`e5_stacked_events.stacked_did`), per topic.

## 5. Robustness and subgroups (secondary)

- With and without 2025-10-10: the "without" run drops events from 2025-10-10 00:00 to
  2025-10-12 00:00 UTC and also bars control and placebo minutes in that span.
- Weekdays vs weekends (Saturday or Sunday in UTC).
- US equity market hours (Monday to Friday, 09:30 to 16:00 America/New_York, no holiday
  calendar) vs outside them.

## 6. Illustrations, not tests

A table of the key named events in `notes/post_data_sources.md` that have a Truth
Social time (the post minute is looked up in the post file), with their abnormal BTC
outcomes and the percentile of abnormal rv among the placebo pool. They are chosen
because they are famous, which selects on the outcome, so they are illustrations only.

## 7. Expectations, stated before looking

From the literature notes: most posts move nothing, so "other" should be close to zero;
tariff posts are the most likely movers (2025 J.P. Morgan FX result, Abdi et al.);
crypto posts may move crypto but are few (about 44 posts before merging) so their
interval will be wide; Fed posts weaker. The pre-window may well be elevated, since
posts often react to markets.
