# C2 deviation: local control windows (post-hoc robustness check)

Written 2026-11-18, **after** the pre-registered C2 run (`data/c2_ranking.md`, analysis
run 2026-11-18T05:26:20Z) had been seen, and **before** anything in this document was
computed. This is a **post-hoc deviation** from `PREREGISTRATION_RANKING.md` and
`PREREGISTRATION_ADDENDUM_CONGRESS.md`. Both stay frozen and unedited; the primary
analysis, its code path and its outputs (`data/c2_ranking.{md,png,json}`) are not
changed. Every result made under this document is a robustness check and is labelled as
such; it does not replace the primary ranking. The sha256 of this file is fixed in
`c2_ranking.py` and printed in the output; the local run refuses to start if this file
has changed.

## 1. Why

The pre-registered controls (v1 rule 5, `PREREGISTRATION_RANKING.md` section 2.3) are
the first 16 eligible minutes among m - 1 week, m + 1 week, m - 2 weeks, ..., up to 26
weeks either side, eligible meaning no post of the same person within 60 minutes and a
complete price window. So controls can lie up to half a year from the event, and where
nearby weeks are ineligible (a person who posts often at the same time of the week, or
events near the start of the 2020-01 sample, where only later weeks exist) they are
drawn from further away and one-sidedly. BTC's volatility level moves a lot over months
and years. A person who posted only in calm stretches is then compared with controls
from more volatile stretches and looks as if they reduce volatility; a person active in
volatile stretches looks as if they raise it. After the run, the two most negative people
were Kamala Harris (raw -4.65 bps, 526 events, posts only to 2021-01) and Mike Conaway
(raw -6.74 bps, 18 events, 2020), and their pre-window means were strongly negative too
(Harris -5.51 bps before posts). The pre-window check also showed elevated volatility
before posts for most people. Both point to the ranking mixing each person's effect with
when they happened to post. A minus-5-to-minus-1 window cannot be moved by a post, so a
nonzero pre-window mean measures exactly this kind of level mismatch (or anticipation).

## 2. The change

**Local controls.** For an event (or placebo minute) at minute m, the candidate control
minutes are m + 7j days for j = -4, -3, -2, -1, +1, +2, +3, +4 (the same minute of the
week within plus or minus 4 weeks). A candidate is eligible if

- all closes from -6 to +60 around it exist (the v1 window rule), and
- **no post of any kind (original, quote, reply or repost) by any tracked person** (every
  person with a used post file, the event's own person included) has its post minute
  within 60 minutes of it.

**All** eligible candidates are used (6, 7 or 8). An event or placebo minute with
**fewer than 6** eligible candidates is dropped; dropped events are counted per person
and reported. The abnormal value is the event's value minus the mean over its eligible
local controls.

**Additional outcome: post minus pre.** Per event, the abnormal BTCUSDT rv over minutes
+1 to +5 minus the abnormal BTCUSDT rv over minutes -5 to -1, both against the same local
controls. A slow-moving volatility level that is the same before and after the post
cancels in this difference. It is ranked with exactly the same machinery as the main
outcome (raw mean and bootstrap interval, placebo p with the person's pool where each pool
minute gets the same difference against its own local controls, BH FDR across ranked
people, empirical-Bayes shrinkage, rank intervals). A person "moves crypto" under this
outcome when q < 0.05 and the mean difference is positive.

**Pre-specified sensitivity (secondary).** To separate the effect of the narrower band
from the effect of the wider exclusion, the main outcome and post minus pre are also
ranked with the same plus or minus 4-week band but with the pre-registered exclusion
(only the same person's posts within 60 minutes). This is reported below the main local
result and does not change it.

## 3. Unchanged

Everything else is as pre-registered: post files, accounts and pooling; topic rules;
events (original and quote only, 5-minute chaining, 60-minute clean rule); the
cross-person overlap rule (5 minutes, both people excluded); the sample period; the
outcome definitions (v1 `rv`, bps); at least 10 analysable clean events to be ranked;
Musk separate; Obama negative control; placebo pool (20,000 minutes with no post by that
person within 60 minutes and a complete window, seed 20261118, the same minutes as the
primary run; pool minutes with fewer than 6 local controls are dropped); placebo p;
BH FDR across ranked people; empirical-Bayes shrinkage toward the mean of ranked people;
ranks and rank intervals from 10,000 bootstraps; per-topic results; the pre-window check;
the 2025-10-10/11 sensitivity (control and placebo minutes in that span barred); the
one-sentence answer, computed in code by the same function from the local ranking.

## 4. Outputs

`research/politics/c2_ranking.py analyze --controls local` and `report --controls local`
write `research/politics/data/c2_ranking_local.{json,md,png}`. The report shows the local
ranking next to the primary ranking (read from `data/c2_ranking.json`), the post-minus-pre
ranking, the dropped-event counts and the sensitivity. The primary files are never
written by the local run.

## 5. Known limits, stated in advance

- Excluding every tracked person's posts removes many weekday US daytime minutes in
  2020 to 2023-07, when about 25 members of Congress were posting; events then may lack
  6 local controls and be dropped, and the remaining controls are tilted toward quieter
  news hours. The drop counts and the own-posts-only sensitivity show how much this
  matters.
- Plus or minus 4 weeks still leaves volatility changes within two months; post minus pre
  addresses the rest but is noisier (two windows) and is also moved by anything that
  differs between the five minutes before and after a post, including reactions to moves
  already under way that continue.
- This check was designed after seeing the primary results; it can show whether those
  results are robust, not confirm a new finding.
