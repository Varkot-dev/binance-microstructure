# C2 pre-registration: which politicians move crypto the most?

Written 2026-11-18, **before any X post file exists**. The only post file available is
the frozen v1 Trump Truth Social file, which has already been analysed in v1
(`data/c1_trump_posts.md`); every other account's posts are unseen. The sha256 of this
file is fixed in `c2_ranking.py` and printed in `data/c2_ranking.md`; the script refuses
to run if this file has changed. Anything reported that is not specified here is
labelled **exploratory**.

This design reuses the v1 pre-registration (`PREREGISTRATION.md`) unchanged wherever it
applies: its topic rules (section 1), event rules (section 2), outcomes (section 3) and
the placebo test (section 4). Only the parts below are new.

## 0. Inputs

- **Accounts**: `accounts.csv`. Each row maps a (platform, handle) to a person and a
  group. Posts of all accounts of the same person (for example Donald Trump on Truth
  Social and on X) are pooled into one post stream for that person.
- **Post files**: every `posts/<platform>_<handle>.csv` that passes `validate_posts.py`
  and whose (platform, handle) is listed in `accounts.csv`. Files that fail validation or
  are not listed are reported and not used. The sha256 of every file used is printed in
  the output.
- **Trump Truth Social file frozen**: `posts/truth_realDonaldTrump.csv` must have the v1
  sha256 `d3ce5a47062fd0d92dff8dae92f3e616f2386f4b1d378a49eb5d4e40e374cf3c` (made by the
  v1 converter, `c1_trump_posts.py convert`, as-is); otherwise the run is refused. Known
  and accepted: in that file 1,116 posts of the form "RT: <status url><own text>" are
  really quote posts with Trump's own comment but are labelled repost, so they are not
  events (they still count as posts for control eligibility). This is **not** fixed for
  C2; fixing it is a later version.
- **Prices**: Binance USDT-M perpetual 1-minute klines for BTCUSDT, ETHUSDT and SOLUSDT
  from data.binance.vision, monthly files 2020-01 to 2026-10, SHA-256 checked at
  download. Months already cached in `data/politics/klines/` are reused; missing months
  are downloaded. Months that Binance does not publish (SOLUSDT before 2020-09) are
  missing, and minutes without a close are handled by the v1 window rule (an event
  without a complete window is dropped for that symbol). Same columns and return
  definition as v1.
- **Sample period**: events from 2020-01-01 00:00 UTC to the last minute whose +60
  window lies before 2026-11-01 00:00 UTC. This is wider than v1 (which started
  2022-02-01) so that earlier X posts are covered. For Trump the only consequence is
  that control weeks for events in early 2022 can now fall in 2021; his estimate can
  therefore differ slightly from v1.

## 1. Topic rules

Exactly the v1 rules (`PREREGISTRATION.md` section 1), applied to each post's `text`,
implemented by `c1_trump_posts.topic_of`, and **frozen as-is**. An event takes the first
topic in the order crypto, tariffs, fed among its merged posts, as in v1. Known misses,
accepted as fixed caveats and not corrected now:

- `bitcoins?` does not match "bitcoiner(s)" (for example Trump's "CONGRATULATIONS
  BITCOINERS!!! $100,000!!!" is "other"); a later list should use `bitcoin\w*`.
- "ETH" alone and other ticker-style words (sats, hodl) are not in the list; only
  `ethereum`, `btc`, `xrp`, `solana` are.
- Content in images, videos, linked pages and quoted posts is invisible.
- `powell` matches unrelated people named Powell; `reciprocal` can be non-trade; `the
  fed` can be "the fed up".
- Non-English posts are not matched.

## 2. Events and the clean sample

1. Per person, the v1 event rules apply unchanged (`PREREGISTRATION.md` section 2,
   rules 1 to 4): only `original` and `quote` posts are candidate posts; **reposts and
   replies are never events**; candidate posts at most 5 minutes apart are merged
   (chaining), the event time is its first post's minute; an event is clean only if it
   starts at least 60 minutes after the last post of the same person's previous event.
2. **Cross-person overlap (new)**: an event of person A overlaps if any candidate post
   (original or quote) of a different person with a used post file, Musk included, has
   a timestamp from 5 minutes (300 seconds, inclusive) before A's first post to 5 minutes
   after A's last post in the event. Overlapping events are excluded from the clean
   sample. The rule is symmetric, so both people's events are excluded.
3. **Controls**: v1 rule 5 applied per person. For an event of person A, the candidate
   control minutes are m + 7j days (j = -1, +1, ..., -26, +26); a candidate is eligible
   if no post of any kind by person A has its post minute within 60 minutes of it and
   all closes from -6 to +60 exist; the first 16 eligible are used; events with fewer
   are dropped. Rationale: this keeps each person's design identical to v1 and does not
   change as other files arrive. Posts of other people inside control windows can only
   raise control volatility, which biases effects toward zero.
4. **Analysable clean events** = clean, not overlapping, inside the sample period, with a
   complete BTCUSDT window and 16 controls.

## 3. The influence measure

For person j, the influence measure is

> b_j = mean over j's analysable clean events of the abnormal BTCUSDT realized
> volatility over minutes +1 to +5 (v1 `rv`, post5, in basis points: the event's rv
> minus the mean rv of its 16 controls),

with standard error s_j = (sample standard deviation, ddof 1) / sqrt(n_j). The same is
computed per person by topic (crypto, tariffs, fed, other). Secondary, descriptive per
person: abnormal BTCUSDT absret over post5, and abnormal rv over post5 for ETHUSDT and
SOLUSDT (mean and bootstrap interval only).

## 4. Who is ranked

- **Ranked**: every person in a group other than `musk_separate` with at least **10**
  analysable clean events. People with fewer are **listed, not ranked**, with their
  event counts and raw mean.
- **Musk** (`musk_separate`) is reported separately with the same statistics and is
  never part of the shrinkage prior, the ranking or the FDR family.
- **Obama** (Barack Obama) is included in the ranking as a **negative control**: he left
  office before the data start and is expected to show no effect (FDR q above 0.05 and
  an interval covering 0). The report states in code whether this check passes. A
  failure is read as a sign that the pipeline produces false positives, not as Obama
  moving crypto.

## 5. Statistics

All seeds are 20261118; all bootstraps use 10,000 resamples.

1. **Raw effect** b_j with a 95% percentile bootstrap interval (events resampled within
   person; `c1_trump_posts.boot_mean`).
2. **Placebo p-value** per person: the v1 placebo test (`PREREGISTRATION.md` section 4)
   with a pool of 20,000 random minutes drawn from minutes with no post of any kind by
   that person within 60 minutes and a complete BTCUSDT window, each with its 16
   controls by the same rule; two-sided, +1 corrected.
3. **FDR**: Benjamini-Hochberg q-values across the ranked people (Musk excluded, Obama
   included) on the placebo p-values. A person "moves crypto" when q < 0.05 and b_j > 0.
4. **Empirical-Bayes shrinkage** (normal-normal, method-of-moments prior). Over the J
   ranked people: tau^2 = max(0, sample variance of the b_j (ddof 1) - mean of s_j^2);
   prior mean m = sum w_j b_j / sum w_j with w_j = 1 / (tau^2 + s_j^2). Shrinkage
   factor B_j = tau^2 / (tau^2 + s_j^2); shrunken effect = m + B_j (b_j - m); 95%
   posterior interval = shrunken effect +/- 1.96 x s_j x sqrt(B_j). "The group mean" is
   the prior mean m across all ranked politicians: the `accounts.csv` groups hold one to
   six people each, too few to estimate a prior per group, so group averages are
   reported only descriptively. With fewer than 3 ranked people tau^2 cannot be
   estimated: no shrinkage is applied (shrunken = raw, interval = raw +/- 1.96 s_j) and
   the report says so.
5. **Ranking**: rank 1 = largest shrunken effect (rank = 1 + number of ranked people with
   a strictly larger shrunken effect).
6. **Rank intervals**: in each of the 10,000 bootstrap draws, every ranked person's events
   are resampled with replacement within person; b_j and s_j are recomputed, the
   shrinkage is re-fitted (tau^2 and m re-estimated), and people are re-ranked. The rank
   interval is the 2.5th to 97.5th percentile of each person's bootstrap ranks.
7. **Per person by topic**: for each topic the same statistics (raw, bootstrap interval,
   placebo p with that person's pool, shrinkage and ranks among the people with at least
   10 analysable clean events in that topic, BH within the topic). Topic results are
   secondary and descriptive.
8. **Pre-window test** per person: the same raw mean, bootstrap interval and placebo p
   for abnormal rv over minutes -5 to -1 (pre5), and the paired difference post5 minus
   pre5 with a bootstrap interval (both windows from the same resampled events). A
   person's pre-window is flagged as elevated when its placebo p < 0.05 and its mean is
   positive; an effect with an elevated pre-window is read as possibly reacting to moves
   already under way.
9. **With and without 2025-10-10**: the whole ranking (raw, shrunken, ranks, rank
   intervals, q) is repeated dropping events from 2025-10-10 00:00 to 2025-10-12 00:00
   UTC and barring control and placebo minutes in that span, as in v1.

## 6. The one-sentence answer (computed in code)

Let S be the ranked people with q < 0.05 and b_j > 0. If S is empty: "No politician's
posts are distinguishable from random times ...". Otherwise, with X the member of S with
the largest shrunken effect: "X moves crypto the most ...", giving the shrunken effect,
the rank interval, and the number of ranked people; if X's rank interval does not end at
1 the sentence says the lead is not distinguishable from the next people; if only one
person is ranked it says this is not yet a comparison. If X's pre-window is elevated the
sentence says so.

## 7. Expectations, stated before looking

From v1 and the literature notes: Trump's average effect per event is small (v1: about
+0.4 bps rv over all clean topics, driven by tariff posts) because most of his posts are
about other things; officials and regulators with fewer, more market-relevant posts
(SEC, David Sacks, the White House on tariffs) may have larger per-post effects but wide
intervals; Democrats and Obama close to zero; Musk possibly elevated on crypto posts.
Most people will have few crypto posts, so per-topic results will mostly be too noisy
to rank.
