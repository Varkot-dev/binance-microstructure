# Reading guide: what to read, in what order, and why

This guide walks the project plan in `README.md` week by week. For each block it says
which research note to read (all in `notes/`), which outside papers matter most, what to
do with your hands, and how to tell you understood it. The notes tag each claim:
**[V]** checked at the source, **[S]** from a secondary source, **[I]** an inference.
Treat [S] and [I] as leads to check, not facts.

Time estimates assume a few hours a day. Reading is front-loaded; from week 3 on, most
time goes to code.

## Before week 1: orientation (2 to 3 days)

Read your own results first. Everything else builds on them.

| Read | Why |
|---|---|
| `results/q1_results.md`, `results/q4_cross_section.md` | What long memory in trade signs is, and how it varies across 121 coins |
| `results/q9_sign_prediction.md` | The prediction ladder; the 60% headline you are now explaining |
| `results/q10_drift.md` | The rise in predictability from 2023 to 2025, the question of Part A |
| `results/q8_regimes.md`, `results/q4b_tick_confound.md` | Earlier evidence that relative tick size matters |
| `research/market_evolution/README.md` | The plan, and the week 0 findings |

**Check yourself:** explain in two sentences why a predictable trade sign does not mean a
predictable price (Q2 and Q5 answer this).

## Weeks 1 to 2: why order flow is predictable at all

**Read**
- `notes/predictability_mechanisms.md`, sections 1 and 2: order splitting (large orders
  cut into many same-direction trades), herding, and what weakens memory.
- `notes/predictability_mechanisms.md`, section 5: proxies you can compute from trades
  alone (run lengths, identical consecutive sizes, same-millisecond bursts, round sizes).
- `notes/binance_public_data.md`, the summary and "Which type gives what" table, so you
  know what data exists before you design anything.

**Key outside reading** (start with the abstracts; full papers only where you need them)
- Lillo, Mike and Farmer (2005): the theory linking order-size distribution to memory.
- Toth et al. (2015), "Why is order flow so persistent?": splitting versus herding.
- Bouchaud, Bonart, Donier and Gould, *Trades, Quotes and Prices* (2018), chapters on
  order-flow persistence. The best single book for this project.

**Do:** extend `e0_what_changed.py` to the 2023 and 2026 cross-sections from Q14 and add
the section 5 proxies. **Watch out:** the sign repeat rate is nearly the outcome itself,
so do not use it as an explanation (the methods note calls this a near-circular driver).

**Check yourself:** what would you expect to happen to run lengths if more traders split
their orders, and why?

## Weeks 3 to 4: testing explanations with panel regression

**Read**
- `notes/panel_and_causal_methods.md`, section 0 (summary) and section 1 in full. Section
  1.4 is the most important idea of Part A: month fixed effects soak up a market-wide
  rise, so they cannot be used to explain it.
- Same note, section 3: the fixed-effects code, including the two pyfixest bugs and
  their fixes.
- `notes/predictability_mechanisms.md`, section 4: relative tick size as a driver.

**Key outside reading**
- Angrist and Pischke, *Mastering 'Metrics* (2014), chapters on regression and
  differences-in-differences. Plain-language and short.
- The pyfixest documentation, quickstart and "fixed effects" pages.

**Do:** contract fixed-effects regressions of fresh-model accuracy on the drivers,
clustered by contract, plus the composition split (survivors, exits, entries) from
section 0 of the methods note, using 2023-06 versus 2023-07 as the noise floor.

**Check yourself:** with 10 coins, why is a clustered standard error not enough, and
what does the wild cluster bootstrap fix?

## Weeks 5 to 6: natural experiments

**Read**
- `notes/binance_events.md`, the verification pass at the top, then "Best natural
  experiments". The strongest designs are batches of tick-size changes with exact dates
  (12 contracts on 2026-03-05, 7 on 2024-09-20) and SOLUSDT's tick increase on
  2024-10-14 at 06:30 UTC, which the data confirm to the minute.
- `notes/panel_and_causal_methods.md`, section 2 (parallel trends, why two-way fixed
  effects break with staggered dates, what to use instead) and section 4 (code).

**Key outside reading**
- Goodman-Bacon (2021) and Callaway and Sant'Anna (2021): read the introductions; the
  note explains the rest.
- Cunningham, *Causal Inference: The Mixtape*, the difference-in-differences chapter
  (free online).

**Do:** a stacked event study of daily predictability around the tick-change batches,
each treated contract matched to untreated contracts of similar activity.

**Check yourself:** what would a violation of parallel trends look like in your
pre-event plot, and what would you do about it?

## Week 7: setting up Part B without cheating

**Read**
- `notes/delisting_prediction.md`, sections 1 to 4 (why Binance delists, Monitoring
  Tags, futures versus spot timing) and section 8 (label pitfalls) in full.
- `notes/survival_and_rare_event_ml.md`, sections 0 to 2: framing choices and the code
  that builds the panel and labels.

**The traps, in one list**
- Binance keeps publishing empty data files after a contract dies. Take the death date
  from the last day with trades.
- Prices fall and volume spikes after a delisting announcement, days before trading
  stops. Cut features at the announcement, or the model learns from the announcement.
- Renames, mergers and index contracts are not deaths.
- Contracts alive at the end are censored, not "never delisted".
- Futures usually stop a week before spot, so spot delistings are rarely early warnings.

**Do:** build the monthly panel from daily klines and metrics (about 300 MB for every
contract, per `notes/binance_public_data.md`), with labels and censoring.

**Check yourself:** why would random K-fold cross-validation give you a great but
meaningless score here?

## Weeks 8 to 9: models

**Read**
- `notes/survival_and_rare_event_ml.md`, sections 3 to 7: expanding-window validation
  with a purge gap, class imbalance (and why `class_weight="balanced"` wrecks
  probabilities), precision at a fixed alert rate, calibration, baselines, and the
  lifelines and scikit-survival code.
- `notes/delisting_prediction.md`, section 7: the candidate features table.

**Key outside reading**
- The scikit-learn user guide pages on precision-recall and on probability calibration.
- The lifelines documentation, "Survival analysis intro" and "Time varying regression".

**Do:** in this order, and each must beat the one before: a falling-volume rule, logistic
regression on two or three features, LightGBM, then a Cox model as an interpretable
check.

**Check yourself:** if your model flags the top 5% of contracts each month, what fraction
of next quarter's delistings does it catch, and how does that compare with the
falling-volume rule?

## Weeks 10 to 12: lock-box and write-up

**Read:** your own Q9 to Q14 reports again, for the house style: computed verdicts,
intervals from resampling days or coins, a caveats list.

**Do:** freeze every choice, score each part once on its held-out data, and write Q15
(Part A) and Q16 (Part B) reports plus a results-page section.

## If you only read five things

1. `research/market_evolution/README.md` (the plan and week 0 findings)
2. `notes/predictability_mechanisms.md`, sections 1 and 5
3. `notes/panel_and_causal_methods.md`, sections 0 and 1.4
4. `notes/delisting_prediction.md`, section 8
5. `notes/survival_and_rare_event_ml.md`, sections 2 and 3
