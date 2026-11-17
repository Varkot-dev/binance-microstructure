# Panel econometrics and causal ML for Part A: a practical methods guide

Who this is for: you know basic Python and some ML, and you are about to explain why
trade-sign predictability rose from 2023 to 2025 (Part A of `../README.md`). This note
says which methods to use, why, what goes wrong, and gives tested Python.

Tags: **[V]** verified in this session (library code was installed and run, or the
citation record was checked by search); **[S]** secondary (from memory or a search
summary, not checked against the primary source); **[I]** inference (my reasoning about
this project, not a published result).

How the code was checked: every snippet in sections 3, 4, 6 and 7 was run on a synthetic
panel with the same shape as yours (60 contracts, 5 snapshots, some contracts dying) in
a scratch virtual environment with: pyfixest 0.70.0, linearmodels 7.1, statsmodels
0.15.0, csdid 0.4.5, differences 0.3.0, DoubleML 0.11.4, econml 0.17.0, shap 0.54.1,
wildboottest 0.3.2, scikit-learn 1.9.1, pandas 2.3.3, Python 3.13 [V]. The documentation
sites for pyfixest and linearmodels were not reachable from this session (network
allowlist), so the APIs were verified by introspection and by running code, not by
reading the docs pages.

---

## 0. Summary (read this if nothing else)

1. **Your data are a short, wide, unbalanced panel**: many contracts (10 to 150), few
   time points (5, unevenly spaced), and contracts that drop out. Almost every choice
   below follows from that shape [I].
2. **The main tool is a fixed-effects regression with standard errors clustered by
   contract**, run in `pyfixest` (`pf.feols("y ~ x | contract + month", vcov={"CRV1":
   "contract"})`) [V]. With only 10 contracts, add a wild cluster bootstrap
   (`fit.wildboottest(...)`) [V] or resample whole contracts (the project ground rule).
3. **Two-way fixed effects (contract and month) cannot explain the market-wide rise**,
   because month fixed effects absorb it by construction. To ask "how much of the
   2023 to 2025 rise do the drivers account for", put a 2025 dummy in a contract
   fixed-effects model and measure how much it shrinks when drivers are added (Gelbach
   decomposition, `fit.decompose(param=...)` in pyfixest) [V for the API, I for the
   framing].
4. **Separate composition from within-coin change first** with a simple survivor /
   exit / entry decomposition (code in section 6). This answers the Q14 question
   directly and needs no regression [I].
5. **For the natural experiment, do not run a 5-snapshot staggered TWFE regression.**
   Measure predictability on a denser grid (daily or weekly) around each exchange event
   using the raw archive, compare treated contracts with matched untouched contracts,
   and use a heterogeneity-robust estimator (Callaway and Sant'Anna via `csdid`, or
   pyfixest's `event_study(..., estimator="did2s" or "saturated")`) when events are
   staggered [V for APIs, I for the design].
6. **Double/debiased ML is a robustness check here, not the main tool**: with 50 to 750
   rows and a handful of drivers, a well-specified fixed-effects regression is easier to
   defend [I]. SHAP is for describing what a model uses, never for proving cause.

---

## 1. Panel data basics

### 1.1 Vocabulary

- **Unit** (entity, i): a contract, such as `BTCUSDT`.
- **Period** (t): one of the 5 snapshot months.
- **Observation**: one contract-month row, with an outcome (for example fresh-model
  accuracy `acc_gbm_all`, or accuracy minus the persistence baseline) and drivers
  (`events_per_day`, `median_notional_usd`, `share_under_1k_usd`, `share_gap_le_1ms`,
  relative tick size, and so on), as produced by `e0_what_changed.py`.
- **Balanced panel**: every unit observed in every period. Yours is unbalanced because
  of delistings and listings (Q14).

### 1.2 Within versus between variation

Any variable can be split into a contract's own average (between part) and its
deviation from that average in a given month (within part):

    x_it = mean_i(x) + (x_it - mean_i(x))

- **Between variation** compares coins with each other: "coins with smaller trades are
  more predictable". It is contaminated by everything else that differs between coins
  (price level, listing age, who trades them).
- **Within variation** follows one coin over time: "when BTC's trades got smaller, did
  BTC get more predictable?". It removes anything fixed about the coin.

Your README checkpoint for weeks 1 to 2 ("does the rise happen inside each coin?") is
exactly the within versus between question [I]. A quick look: for each variable, compute
the standard deviation of the contract means and the standard deviation of the
deviations. If a driver barely moves within contracts, a fixed-effects model cannot
learn much about it and its coefficient will be noisy [S, standard textbook point, for
example Wooldridge's panel data text].

### 1.3 Three models

Let y_it be predictability and x_it a driver.

1. **Pooled OLS**: `y_it = a + b x_it + e_it`. Uses both within and between variation.
   Biased if anything fixed about a coin (its "type") is correlated with x and y.
2. **Entity (contract) fixed effects**: `y_it = a_i + b x_it + e_it`. One intercept per
   coin, so b is identified only from within-coin changes. Removes all time-invariant
   coin traits, observed or not [S].
3. **Two-way fixed effects (TWFE)**: `y_it = a_i + g_t + b x_it + e_it`. Adds one
   intercept per month. b now comes from coins whose driver moved more or less than the
   market-wide change in that month [S].

A fourth estimator, the **between estimator** (regress the contract means of y on the
contract means of x), isolates the cross-sectional relationship. Comparing between and
within coefficients is a cheap diagnostic: if they differ a lot, coin-level confounding
is present [S].

### 1.4 The key conceptual trap: month fixed effects absorb what you want to explain

The fact to be explained is the **average rise** from 2023 to 2025. In a TWFE model,
the month effects g_t soak up every change common to all contracts, including that
average rise. So TWFE answers "do coins whose driver changed more show bigger rises?",
which is useful, but it cannot by itself tell you how much of the common rise each
driver explains [I]. Two ways to get at the common rise:

- **Contract FE plus a "late" dummy, before and after adding drivers.** Fit
  `y ~ late | contract` and then `y ~ late + drivers | contract`. If the coefficient on
  `late` falls from 0.05 to 0.01, the drivers "account for" most of the rise in an
  accounting sense. The Gelbach (2016) decomposition splits the fall into one piece per
  driver, and is order-invariant, unlike adding controls one at a time [S for the paper,
  V for the pyfixest implementation]. Code in section 7.3.
- **TWFE for the cross-sectional test**, which is more robust to omitted common shocks
  (a fee change hitting everyone, a market-wide volatility regime) [I].

Report both. They answer different questions, and the difference between them is
informative [I].

### 1.5 Clustered standard errors

Observations of the same coin in different months are not independent (a coin that was
unusually predictable in 2023-06 is likely so in 2023-07 too). Ordinary standard errors
pretend you have N x T independent rows and come out too small. **Cluster by
contract**: treat each coin's whole history as one independent draw [S]. In pyfixest:
`vcov={"CRV1": "contract"}` [V]. Abadie, Athey, Imbens and Wooldridge (2023) argue the
reason to cluster is the design (how units were sampled or treated), which here is
"coins are the unit", consistent with the README's "resample whole coins" rule [V for the
citation, I for the application].

You cannot usefully cluster by month: 5 clusters is far too few [S, MacKinnon, Nielsen
and Webb 2023]. Section 8 covers cross-sectional dependence.

### 1.6 Few clusters

Cluster-robust standard errors rely on many clusters. With 10 coins (the Q10 set),
conventional cluster-robust tests over-reject; Cameron, Gelbach and Miller (2008) show
standard tests with 5 to 30 clusters can reject 10% of the time at a nominal 5%, and
that a **wild cluster bootstrap** fixes most of this [V, citation record and abstract].
MacKinnon, Nielsen and Webb (2023) recommend reporting CV3 (a jackknife-type variance)
and/or the wild cluster bootstrap alongside CV1, and randomization inference when very
few clusters are treated [V, from the paper's abstract via search].

Practical rules [I, built on the references above]:

- 10 contracts: report the wild cluster bootstrap p-value (Rademacher weights, null
  imposed, which is the pyfixest default [V]) and a contract-resampling interval. Treat
  them as rough.
- 100 to 150 contracts: CV1 clustered errors are usually fine; still show CV3
  (`vcov={"CRV3": "contract"}` works with fixed effects in pyfixest [V]) as a check.
- In a DiD, what matters is the number of **treated** clusters, not the total. If 3
  contracts had a tick-size change, even the wild bootstrap is unreliable; use
  randomization inference (pyfixest `fit.ritest(resampvar="treated", cluster="cid", reps=999)`; the
  signature was checked [V] but the call was not run) or a permutation over placebo contracts [S, MacKinnon and Webb line of
  work].

### 1.7 What goes wrong with only 5 time points

- **The snapshots are unevenly spaced**: 1 month, then 12, 12, 12 [I]. "One period
  later" means different things, so anything indexed by period number (lags, event
  time) mixes horizons. Use calendar month as the time label and think in months.
- **2023-06 versus 2023-07 is a gift**: the market cannot have changed structurally in
  one month, so the change between these two months estimates the noise floor (sampling
  error plus short-run variation). A driver that "explains" the 2023-06 to 2023-07 change
  as strongly as the 2023 to 2025 change is probably picking up noise [I].
- **Month effects use up degrees of freedom fast and are not separately identified from
  any market-wide driver** (a fee schedule change that hit all coins in 2024 is
  perfectly collinear with the 2024-07 dummy) [I].
- **Dynamics cannot be modelled**: lagged-dependent-variable models with fixed effects
  are biased when T is small (Nickell bias, of order 1/T) [S, Nickell 1981]. Do not put
  last period's accuracy on the right-hand side with contract FE.
- **Pre-trends cannot be checked with 5 points** if the event sits in the middle of the
  sample, which is why section 2 recommends a denser grid for the event study [I].

---

## 2. Difference-in-differences and event studies

### 2.1 The idea in plain terms

Some contracts were changed by an exchange event (a tick-size change on that symbol, a
fee change for a subset, a contract migration) and others were not. Difference-in-
differences (DiD) compares the **change** in predictability for treated contracts with
the **change** for untreated ones over the same window. The untreated change stands in
for "what would have happened to the treated coins anyway" [S].

The 2x2 DiD estimate is:

    (y_treated,after - y_treated,before) - (y_control,after - y_control,before)

In regression form: `y_it = a_i + g_t + b * D_it + e_it`, where D_it = 1 for treated
contracts after the event. With one event date for everyone, this TWFE regression gives
the 2x2 answer and is fine [S].

### 2.2 Parallel trends

The key assumption: **without the event, treated and control contracts would have moved
in parallel** (same expected change, not same level) [S]. It is untestable after the
event. The standard check is an **event study**: estimate separate coefficients for each
period before and after the event, relative to the period just before. Pre-event
coefficients near zero are reassuring but not proof:

- Pre-trend tests have low power, and keeping only specifications that pass a pretest
  distorts the final estimate (Roth 2022) [V, citation record and abstract].
- Rambachan and Roth (2023) offer sensitivity analysis: how large could a violation of
  parallel trends be, relative to the pre-trends you see, before the conclusion flips?
  [V, citation]. A Python port of their HonestDiD method was not verified this session.

Specific threats in this market [I]:

- Exchanges often change tick sizes **because** the price moved a lot (the relative
  tick became too large or too small). Treated coins are then selected on a recent price
  move, which itself changes trading activity. Control coins should have had similar
  price moves without a tick change.
- Relative tick size (tick / price) changes every day with price even with no exchange
  action, so "treatment" is really a jump in a continuous variable that also drifts.
  The README already flags this.
- Market-wide events (a crash, ETF approval) hit all coins but not equally (high-beta
  coins more); a common month effect does not remove that.

### 2.3 Staggered adoption and why TWFE breaks

If different contracts are treated at different dates (tick changes rolled out across
symbols over months), the TWFE coefficient b becomes a weighted average of many 2x2
comparisons, some of which use **already-treated contracts as controls**.
Goodman-Bacon (2021) shows this decomposition explicitly [V, citation]. When treatment
effects change over time or differ across cohorts, those "forbidden comparisons" get
negative weights, and b can even have the opposite sign of every true effect (de
Chaisemartin and D'Haultfoeuille 2020) [V, citation and abstract]. Sun and Abraham (2021)
show the same problem contaminates event-study leads and lags, so pre-trend coefficients
can look non-zero purely from effect heterogeneity [V, citation and abstract].

### 2.4 What to use instead

All of these estimate group-time effects using only clean comparisons (not-yet-treated
or never-treated controls), then average them [S]:

| Estimator | Idea | Python |
|---|---|---|
| Callaway and Sant'Anna (2021) | ATT(g, t) for each cohort g and period t, then aggregate (simple, by cohort, by event time) | `csdid` (`from csdid.att_gt import ATTgt`) [V]; `differences` (`from differences import ATTgt`) [V] |
| Sun and Abraham (2021) | Interaction-weighted event study: cohort x relative-time interactions | pyfixest `event_study(..., estimator="saturated")` is a saturated cohort-specific event study, which is the same idea [V that it runs, I that it matches Sun and Abraham exactly] |
| Borusyak, Jaravel and Spiess (2024); Gardner (2022) | Imputation / two-stage: fit unit and time effects on untreated observations only, impute the untreated outcome, compare | pyfixest `did2s(...)` and `event_study(..., estimator="did2s")` [V] |
| Local projections DiD (Dube, Girardi, Jorda and Taylor) | Long differences with clean controls | pyfixest `lpdid(...)` [V that it runs; citation details not verified, S] |
| de Chaisemartin and D'Haultfoeuille | Handles treatments that switch on and off | PyPI package `py_did_multiplegt_dyn` exists (0.1.9) [V that it exists]; its API was not checked, so read its docs before use |

Recommendation [I]: use `csdid` with `control_group=["notyettreated"]` as the main
estimator because its output (per cohort, per period) is the easiest to inspect, and
pyfixest `did2s` as a cross-check. If all treated contracts share one event date, a
plain TWFE event study is fine and simpler.

Continuous "dose" (size of the relative tick change): the `differences` package's
`ATTgt` takes a `dosage_column` argument [V that the argument exists]. The method
(Callaway, Goodman-Bacon and Sant'Anna, "Difference-in-differences with a continuous
treatment") is [S]; start binary (big change versus none) before trying doses.

### 2.5 Design advice specific to your data [I]

- **Build a denser panel for the event study.** The 5 snapshots were chosen to measure
  drift, not to bracket events. The raw archive has every day, so compute daily (or
  weekly) predictability for treated and control contracts in a window such as 30 days
  before to 30 days after each event. That gives enough pre-periods to look at trends
  and makes event time mean "days since the event". Retrain or freeze the prediction
  model consistently (for example train once on a pre-window and score every day), so
  that a model change is not confused with a market change.
- **Event dates must be verified** (README weeks 5 to 6), and anticipation matters:
  exchanges announce changes days ahead. Use the announcement and effective dates, and
  allow for anticipation (`anticipation=` exists in both `csdid` and `differences`
  `ATTgt` [V]).
- **Define the outcome so it is comparable across coins**: accuracy minus the
  persistence baseline (`acc_gbm_all - acc_persistence`) removes the part explained by
  plain sign repetition and may be a cleaner outcome [I].

### 2.6 Matching treated contracts to controls

Parallel trends is more believable when controls look like the treated coins before the
event [S]. Simple recipe [I]:

1. For each treated contract, compute pre-event features: log activity, log price, price
   change over the prior 30 to 90 days, relative tick size, pre-event predictability,
   listing age.
2. Standardize them and pick the k nearest untreated contracts (k = 3 to 5) by Euclidean
   distance, without replacement if the pool allows. scikit-learn's
   `NearestNeighbors` is enough.
3. Check balance with standardized mean differences (difference in means divided by the
   pooled standard deviation); a common rule of thumb is below 0.1 to 0.25 [S].
4. Run the DiD on the matched sample, or skip manual matching and let Callaway and
   Sant'Anna condition on covariates through `xformla="~ x1 + x2"` with the doubly robust
   method (`est_method="dr"`) [V that the arguments exist].

Do not match on post-event values, and do not match on variables the event itself
changes (trade size after a tick change) [S, standard bad-control advice].

---

## 3. Snippet 1: fixed-effects panel regression (the core analysis)

Tested on a synthetic panel [V]. Replace the column names with the ones from your panel
builder.

```python
import numpy as np
import pandas as pd
import pyfixest as pf

df = pd.read_parquet("panel.parquet")        # one row per contract-month
# pyfixest 0.70 refuses object-dtype fixed-effect columns read from CSV/parquet,
# and its wild bootstrap fails on string cluster ids; make both explicit. [V]
df["month"] = df["month"].astype("string")
df["cid"] = pd.factorize(df["contract"])[0]  # integer contract id
df["log_act"] = np.log(df["events_per_day"])
df["log_size"] = np.log(df["median_notional_usd"])
df["excess_acc"] = df["acc_gbm_all"] - df["acc_persistence"]

drivers = "log_act + log_size + share_gap_le_1ms + rel_tick"

m_pooled = pf.feols(f"excess_acc ~ {drivers}", data=df, vcov={"CRV1": "cid"})
m_fe     = pf.feols(f"excess_acc ~ {drivers} | cid", data=df, vcov={"CRV1": "cid"})
m_twfe   = pf.feols(f"excess_acc ~ {drivers} | cid + month", data=df, vcov={"CRV1": "cid"})
pf.etable([m_pooled, m_fe, m_twfe], type="df")   # side-by-side table

# Few clusters: wild cluster bootstrap p-value for one coefficient
print(m_twfe.wildboottest(param="rel_tick", reps=9999, cluster="cid", seed=1))

# Jackknife-style CV3 as a second opinion
m_cv3 = pf.feols(f"excess_acc ~ {drivers} | cid + month", data=df, vcov={"CRV3": "cid"})
```

The same TWFE model in linearmodels, for comparison [V]:

```python
from linearmodels.panel import PanelOLS, BetweenOLS
p = df.set_index(["contract", "period"])     # MultiIndex: (entity, time), time numeric
res = PanelOLS.from_formula(
    "excess_acc ~ log_act + log_size + EntityEffects + TimeEffects", data=p
).fit(cov_type="clustered", cluster_entity=True)
between = BetweenOLS.from_formula("excess_acc ~ 1 + log_act + log_size", data=p).fit()
```

Standard errors from the two libraries differ slightly because of different
small-sample corrections (on the test panel: 0.00084 versus 0.00094) [V]. State which
you used.

Resampling whole coins (the project ground rule), done by hand [V]:

```python
rng = np.random.default_rng(0)
ids = df["cid"].unique()
boot = []
for _ in range(999):
    pick = rng.choice(ids, size=len(ids), replace=True)
    # give each draw a fresh id so a coin drawn twice gets two fixed effects
    bs = pd.concat([df[df.cid == c].assign(bid=k) for k, c in enumerate(pick)])
    fit = pf.feols(f"excess_acc ~ {drivers} | bid + month", data=bs)
    boot.append(fit.coef()["rel_tick"])
print(np.percentile(boot, [2.5, 97.5]))
```

---

## 4. Snippet 2: staggered DiD and event study

Data layout: one row per contract-period, a numeric period column, and `first_treat` =
the period in which the contract was first treated (0 for never treated), which is the
convention `csdid` and pyfixest `event_study` both accepted in testing [V].

```python
from csdid.att_gt import ATTgt
import pyfixest as pf

# csdid wants a balanced panel unless allow_unbalanced_panel=True
att = ATTgt(yname="excess_acc", tname="period", idname="cid", gname="first_treat",
            data=ev, control_group=["notyettreated"]).fit(est_method="reg")
att.summ_attgt()                       # table of ATT(g, t) with pre-periods
att.aggte(typec="dynamic")             # event-time aggregation, printed with bands
att.aggte(typec="simple")              # one overall ATT

# Cross-checks in pyfixest
twfe  = pf.event_study(ev, yname="excess_acc", idname="cid", tname="period",
                       gname="first_treat", estimator="twfe")
did2s = pf.event_study(ev, yname="excess_acc", idname="cid", tname="period",
                       gname="first_treat", estimator="did2s")
sat   = pf.event_study(ev, yname="excess_acc", idname="cid", tname="period",
                       gname="first_treat", estimator="saturated")
sat.aggregate()                        # event-time effects from the saturated model
pf.panelview(ev, unit="cid", time="period", treat="treated")  # who is treated when (signature checked, not run)
```

Notes [V unless marked]:

- `csdid` `fit()` takes `est_method` in `{"dr", "reg", "ipw"}` style names (`"dr"` is the
  default) and bootstraps by default (`bstrap=True`). [V for default and `"reg"`; the
  full list of names was not checked.]
- `aggte(typec=...)` is spelled `typec`, not `type` [V].
- The `differences` package does the same estimator with a different interface:
  `ATTgt(data=..., cohort_column=...)` on a (entity, time) MultiIndex, then
  `.fit(formula="y", control_group="not_yet_treated")` and `.aggregate("event")` [V for
  signatures, not run end to end].
- On the synthetic test panel with a true effect of 0.02 but staggered cohorts, all
  four estimators were close (0.026 to 0.031); the TWFE bias appears when effects grow
  over time or differ by cohort, so agreement on your data is a useful check, not a
  given [V for the numbers, I for the interpretation].

---

## 5. Causal ML

### 5.1 Double/debiased ML (DML) in plain terms

Goal: the effect of one variable D (say relative tick size) on Y, controlling for many
others X, where you do not want to assume X enters linearly. DML (Chernozhukov et al.
2018) [V, citation]:

1. Predict Y from X with any ML model, out of fold; keep the residual Y - E[Y|X].
2. Predict D from X with any ML model, out of fold; keep the residual D - E[D|X].
3. Regress the Y residual on the D residual. The slope is the effect.

Cross-fitting (fit on some folds, predict on others) and the "orthogonal" residual-on-
residual step make the estimate insensitive to small errors in the ML fits, so you get
valid standard errors [V, paper abstract]. This is the Frisch-Waugh-Lovell theorem with
ML in place of linear regression [S].

### 5.2 Is it worth it here? [I]

- With the 10-coin panel (50 rows): no. ML nuisance models need data; with 50 rows they
  are noise.
- With the 150-coin panel (up to about 750 rows), a few drivers and some controls: a
  fixed-effects linear regression with sensible transforms (logs, a few interactions) is
  more transparent and probably as good. Use DML as a robustness check that the driver
  coefficient does not depend on linearity in the controls.
- DML is worth it when there are many plausible controls (dozens of microstructure
  features), nonlinear confounding (activity matters differently for small and large
  coins), and enough rows.
- DML does **not** fix omitted variables or reverse causality. It only relaxes the
  functional form of observed controls.

### 5.3 Panel structure inside DML [I unless marked]

- **Fixed effects**: DML packages do not have built-in contract fixed effects in the
  partially linear model. A pragmatic approach is to demean Y, D and X within contract
  first, add month dummies to X, then run DML. This is an approximation; there is a
  research literature on DML for panels with fixed effects (for example Clarke and
  Polselli, arXiv 2312.08174 [S, not checked]).
- **Clustering**: DoubleML's `DoubleMLData` takes `cluster_cols` [V], and with it the
  fit runs and reports cluster-aware inference [V that it runs; that sample splitting is
  done by cluster is from DoubleML's documentation as I recall, S]. Without this, folds
  mix months of the same coin and leak information. In econml, pass `groups=` to `fit`
  so folds keep a contract together [V that the argument exists].

### 5.4 Snippet 3: DML with clustering [V]

```python
import doubleml as dml
from sklearn.linear_model import LassoCV
from sklearn.ensemble import RandomForestRegressor

cols = ["excess_acc", "rel_tick"] + controls              # controls: list of names
dm = df.copy()
dm[cols] = df[cols] - df.groupby("cid")[cols].transform("mean")   # within-contract
dm = pd.concat([dm, pd.get_dummies(df["month"], prefix="m", dtype=float)], axis=1)
xcols = controls + [c for c in dm.columns if c.startswith("m_")]

data = dml.DoubleMLData(dm, y_col="excess_acc", d_cols="rel_tick",
                        x_cols=xcols, cluster_cols="cid")
plr = dml.DoubleMLPLR(data,
                      ml_l=RandomForestRegressor(300, min_samples_leaf=5),  # E[Y|X]
                      ml_m=RandomForestRegressor(300, min_samples_leaf=5),  # E[D|X]
                      n_folds=5, n_rep=10)    # repeat the split 10 times
plr.fit()
print(plr.summary)

# Same with Lasso nuisances: if the answers differ a lot, be suspicious
plr_l = dml.DoubleMLPLR(data, ml_l=LassoCV(), ml_m=LassoCV(), n_folds=5, n_rep=10).fit()
```

econml equivalent [V]:

```python
from econml.dml import LinearDML
m = LinearDML(model_y=LassoCV(), model_t=LassoCV(), cv=5, random_state=0)
m.fit(dm["excess_acc"], dm["rel_tick"], X=None, W=dm[xcols], groups=dm["cid"])
print(m.summary())          # with X=None the effect is reported as "cate_intercept"
```

On the test panel the fixed-effects regression, DoubleML (Lasso and forest) and econml
gave 0.0109, 0.0117, 0.0104 and 0.012 for a true value of 0.01 [V].

econml is the better choice if you later want **heterogeneous** effects (does the tick
effect differ by coin size?) via `X=`; DoubleML is closer to the paper and has more
model types (`DoubleMLIRM` for binary treatments, `DoubleMLDID` for DiD) [V that these
classes exist in DoubleML 0.11.4].

### 5.5 SHAP: describing, not proving

SHAP (Lundberg and Lee 2017 [S]) splits each prediction of a fitted model into
per-feature contributions. Use it to answer "what does the gradient boosting model rely
on?" and "is the relationship nonlinear?". Do not use it to say "small trades cause
predictability" [I].

Pitfalls [S unless marked]:

- **Correlated features share credit arbitrarily.** Activity, share of small trades,
  share of sub-millisecond events and trade size all move together. With correlated
  features, SHAP can spread or shift credit between them depending on the model's
  arbitrary choice of splits and on how missing features are simulated. Aas, Jullum and
  Loland (2021) show Kernel SHAP's independence assumption can give very wrong
  explanations under dependence, even for linear models, and propose grouping dependent
  features [V, citation and abstract].
- **Interventional versus path-dependent.** `shap.TreeExplainer(model, data=...,
  feature_perturbation=...)` has options `"auto"`, `"interventional"` and
  `"tree_path_dependent"` [V]. Interventional SHAP breaks correlations (evaluates the
  model on feature combinations that may never occur); path-dependent follows the
  model's internal conditional structure. They can disagree; report which one.
- **SHAP explains the model, not the data-generating process.** Two models with equal
  accuracy can have very different SHAP rankings.
- **Pooled SHAP mixes within and between variation**, just like pooled OLS. A feature
  that separates BTC from small coins will rank high even if it explains none of the
  change over time [I].
- **Group features.** Sum SHAP values for blocks (activity block, size block, timing
  block) and report blocks, not single features [I, following Aas et al.'s grouping
  idea].

Minimal call [V]:

```python
import shap
explainer = shap.TreeExplainer(gbm_model)
sv = explainer(X)            # sv.values has shape (n_rows, n_features)
shap.plots.beeswarm(sv)      # plotting API not run this session [S]
```

---

## 6. Composition versus within-coin change

Part of the rise could be **which coins are in the sample**: if weak, unpredictable coins
were delisted (Q14), the average rises with no coin changing. Decompose the change in the
equal-weighted mean across contracts between two months into three pieces [I, an
unweighted version of the dynamic Olley-Pakes decomposition of Melitz and Polanec (2015),
S]:

    mean_1 - mean_0 =  (mean of survivors at 1 - mean of survivors at 0)       within
                     + share_entrants_1 * (mean_entrants_1 - mean_survivors_1)  entry
                     - share_exiters_0  * (mean_exiters_0  - mean_survivors_0)  exit

The exit term is positive when the coins that died were below the survivors' average,
which is the "survivorship lifts the average" story. Tested code [V, the three parts sum
to the total exactly]:

```python
def decompose(df, t0, t1, y="excess_acc", unit="contract", time="month"):
    a = df[df[time] == t0].set_index(unit)[y]
    b = df[df[time] == t1].set_index(unit)[y]
    S = a.index.intersection(b.index)          # survivors
    X = a.index.difference(b.index)            # exited
    E = b.index.difference(a.index)            # entered
    within = b[S].mean() - a[S].mean()
    exit_ = -(len(X) / len(a)) * (a[X].mean() - a[S].mean()) if len(X) else 0.0
    entry = (len(E) / len(b)) * (b[E].mean() - b[S].mean()) if len(E) else 0.0
    return {"total": b.mean() - a.mean(), "within": within,
            "exit": exit_, "entry": entry}
```

Extensions [I]:

- Put intervals on each term by resampling contracts (bootstrap the function above).
- If you prefer activity-weighted averages (what a typical trade experiences), use
  weights; then a fourth "reallocation" term appears (activity shifting toward more
  predictable coins), which is the classic shift-share split into within, between
  (share change), and cross terms.
- **Oaxaca-Blinder** asks a related question: how much of the 2023 versus 2025 gap is
  due to changed driver levels (explained) versus changed coefficients (unexplained).
  statsmodels has it [V]:

  ```python
  from statsmodels.stats.oaxaca import OaxacaBlinder
  two = df[df.month.isin(["2023-06", "2025-07"])].copy()
  two["late"] = (two.month == "2025-07").astype(int)
  X = two[["log_act", "log_size", "late"]].assign(const=1.0)
  ob = OaxacaBlinder(two["excess_acc"], X, "late", hasconst=True)  # group column is
  ob.two_fold().summary()                                           # a column of X [V]
  ```

  Oaxaca-Blinder treats the two months as two independent samples and ignores that many
  coins appear in both, so prefer the within-contract approaches for inference and use
  Oaxaca for description [I].

---

## 7. How the pieces fit: a suggested order of analysis [I]

1. **Describe** (week 1 to 2): plot each contract's outcome over the 5 months (spaghetti
   plot), and compute the composition decomposition (section 6) for 2023-06 to 2025-07
   and, as a placebo, 2023-06 to 2023-07.
2. **Within versus between**: compute the between and within standard deviations of
   each driver; run pooled, contract FE, TWFE and between regressions side by side
   (section 3).
3. **Account for the common rise**: Gelbach decomposition of the `late` coefficient in a
   contract FE model.

   ```python
   d = df[df.month.isin(["2023-06", "2025-07"])].copy()
   d["late"] = (d.month == "2025-07").astype(float)
   long = pf.feols("excess_acc ~ late + log_act + log_size + share_gap_le_1ms + rel_tick | cid",
                   data=d, vcov={"CRV1": "cid"})
   g = long.decompose(param="late", reps=999, seed=0)   # bootstrap by cluster
   g.tidy()
   ```

   Read the output carefully: on the test panel the rows labelled `direct_effect` and
   `full_effect` held the short-model and long-model `late` coefficients respectively,
   and `explained_effect` their difference, with one row per driver splitting it; the
   contract fixed effects also appear as rows with values of about 0 [V]. Check the
   numbers against `pf.etable([short, long])` before interpreting the labels. Coins
   observed in only one of the two months are dropped as singletons by default
   (`fixef_rm="singleton"` [V]), which is the right sample for a within-coin question
   but should be reported. You can bundle related drivers with
   `combine_covariates={"timing": [...], "size": [...]}` [V that the argument exists].
4. **Robustness**: DML (section 5.4) on the 150-coin panel; SHAP on a gradient boosting
   model of the outcome, grouped features, purely descriptive.
5. **Natural experiment** (weeks 5 to 6): dense daily panel around verified events,
   matched controls, `csdid` plus `did2s`, wild bootstrap or randomization inference if
   few contracts are treated.

---

## 8. Pitfalls checklist for this data

Tick each before believing a number.

**Dependence**

- [ ] Standard errors clustered by contract, never plain OLS errors [S].
- [ ] With 10 contracts, wild cluster bootstrap or contract resampling reported [V/S].
- [ ] In DiD, count the treated contracts; below roughly 5 to 10, use randomization
      inference or placebo permutations [S].
- [ ] **Same-day common shocks**: all contracts in a month share the same market days
      (a crash on one day hits everyone). Month fixed effects remove the average shock
      but not differing exposure (high-beta coins react more). You cannot cluster by
      month with 5 months. Options: control for a coin's beta or size tier interacted
      with month (`| cid + month^tier` style FE), or check that results hold within
      tiers [I].
- [ ] In the daily event-study panel, days within a contract are correlated and all
      contracts share calendar days; cluster by contract and add day fixed effects [I].

**Measurement**

- [ ] **The outcome is estimated with sampling error.** Accuracy measured on a few
      thousand events (small coins) is noisier than on millions (BTC). Noise in the
      outcome does not bias coefficients but inflates variance and makes residuals
      heteroskedastic; consider weighting by the number of test events or by inverse
      sampling variance (pyfixest `weights="w"` [V that the argument exists]) and check
      results with and without [S].
- [ ] **Small coins can produce extreme accuracies by chance.** Look at whether results
      are driven by the smallest decile; trim or weight [I].
- [ ] **Drivers are also estimated** from the same trades. Noise in a regressor biases
      its coefficient toward zero (attenuation) [S], and fixed effects make this worse
      because they remove the stable signal and keep the noise [S]. A driver that looks
      weak within coins may just be noisy.
- [ ] **Near-tautological drivers**: the sign repeat rate is very close to what the
      persistence baseline uses, so "repeat rate explains accuracy" is close to
      circular. Treat it as a mechanism (an intermediate outcome), not a driver, or use
      excess accuracy over persistence as the outcome [I].
- [ ] Same model, same training-window length and same evaluation protocol in every
      contract-month, so that the outcome measures the market and not the pipeline [I].
- [ ] Relative tick size computed from the price in the same month, with the tick size
      in force that month (the Q11 BTC tick bug is the warning) [I].

**Sample and survivorship**

- [ ] Decomposition into within, entry and exit done before any regression (section 6)
      [I].
- [ ] Results reported on the survivor-only balanced panel **and** the full unbalanced
      panel. If they differ, composition matters [I].
- [ ] Renames and migrations handled as the same economic unit or explicitly as
      separate ones, using Q14's classification; a rename must not look like a death
      plus a birth [I].
- [ ] Coins that die may have deteriorated before delisting, so their last snapshots
      are unusual; a contract fixed effect does not fix trends specific to dying coins
      [I].

**Design**

- [ ] No lagged outcome on the right-hand side with contract fixed effects and T = 5
      (Nickell bias) [S].
- [ ] No "bad controls": do not control for variables the event itself changes
      (trade size after a tick change) when estimating the event's total effect [S].
- [ ] Event dates verified against exchange announcements, with anticipation allowed
      [I].
- [ ] Event time measured in calendar units, not snapshot index, because the snapshots
      are unevenly spaced [I].
- [ ] 2023-06 versus 2023-07 used as a placebo or noise floor [I].
- [ ] Every finding compared with a no-ML baseline (the README rule): for the panel,
      the persistence baseline's own trend [I].
- [ ] Multiple drivers tested: say how many you tried; consider `pf.rwolf` or
      `pf.bonferroni` (both exist in pyfixest [V]) for multiple-testing adjustment.

---

## 9. Python libraries: what each is good for

| Library (PyPI name) | Good for | Notes |
|---|---|---|
| `pyfixest` | Main workhorse: OLS/Poisson with many fixed effects (`feols`, `fepois`), clustered SEs (`CRV1`, `CRV3`, two-way via `"a+b"` [S]), wild cluster bootstrap (`.wildboottest`), randomization inference (`.ritest`), Gelbach decomposition (`.decompose`), DiD (`event_study`, `did2s`, `lpdid`, `panelview`), tables (`etable`), multiple testing (`rwolf`, `wyoung`, `bonferroni`) | [V] all names exist in 0.70.0. Gotchas found: object-dtype FE columns raise an error; wild bootstrap fails with string cluster ids [V]. Port of R's fixest, so R fixest docs help [S]. |
| `linearmodels` | `PanelOLS` (entity/time effects), `PooledOLS`, `BetweenOLS`, `RandomEffects`, `FirstDifferenceOLS`; clustered or Driscoll-Kraay (`cov_type="kernel"`) covariances | [V] for `PanelOLS`, `BetweenOLS`, `from_formula` with `EntityEffects + TimeEffects`, `cov_type="clustered", cluster_entity=True`. Needs a (entity, time) MultiIndex. Driscoll-Kraay needs many time periods, so not useful with T = 5 [S]. |
| `statsmodels` | General OLS/GLM, `OaxacaBlinder` (`statsmodels.stats.oaxaca`) | [V] for Oaxaca-Blinder; group indicator must be a column of `exog`. |
| `wildboottest` | Standalone wild cluster bootstrap for statsmodels OLS | [V] signature `wildboottest(model, B, cluster=..., param=...)`; pyfixest calls it internally. |
| `csdid` | Callaway and Sant'Anna, close port of the R `did` package | [V] `ATTgt(yname, tname, idname, gname, data, control_group, xformla, anticipation, ...)`, `.fit(est_method="dr")`, `.aggte(typec="dynamic")`. |
| `differences` | Callaway and Sant'Anna with a pandas-style interface and continuous dose | [V] signatures for `ATTgt(data, cohort_column, dosage_column, base_period, anticipation)`, `.fit(formula, est_method, control_group, cluster_var)`, `.aggregate(...)`; not run end to end. |
| `py_did_multiplegt_dyn` | de Chaisemartin and D'Haultfoeuille estimators | [V] exists on PyPI (0.1.9); API not checked. |
| `diff-diff` | Another DiD collection including a Gardner `TwoStageDiD` class | [V] exists on PyPI (4.0.0); documentation seen only via search; not tested. |
| `DoubleML` (`import doubleml`) | DML: `DoubleMLPLR` (continuous treatment), `DoubleMLIRM` (binary), `DoubleMLDID`, `DoubleMLPanelData`; `cluster_cols` for clustered inference | [V] for `DoubleMLData(..., cluster_cols=...)` and `DoubleMLPLR(data, ml_l, ml_m, n_folds, n_rep)`. |
| `econml` | DML and heterogeneous effects (`LinearDML`, `CausalForestDML`), `groups=` for grouped folds | [V] for `LinearDML` and `fit(Y, T, X=, W=, groups=)`; `CausalForestDML` from memory [S]. |
| `shap` | Model explanations; `TreeExplainer` for gradient boosting | [V] for `TreeExplainer(model, data, feature_perturbation=...)` and calling the explainer. |

Installing: `pip install pyfixest linearmodels statsmodels csdid differences doubleml
econml shap` worked in a fresh Python 3.13 environment this session [V].

---

## 10. References

Methods papers (citation records checked by web search this session unless marked):

- Abadie, A., Athey, S., Imbens, G. W., and Wooldridge, J. M. (2023). When should you
  adjust standard errors for clustering? *Quarterly Journal of Economics*, 138(1).
  doi:10.1093/qje/qjac038. https://arxiv.org/abs/1710.02926 [V; volume/issue S]
- Aas, K., Jullum, M., and Loland, A. (2021). Explaining individual predictions when
  features are dependent: more accurate approximations to Shapley values. *Artificial
  Intelligence*, 298, 103502. https://arxiv.org/abs/1903.10464 [V]
- Borusyak, K., Jaravel, X., and Spiess, J. (2024). Revisiting event-study designs:
  robust and efficient estimation. *Review of Economic Studies*, 91(6), 3253-3285.
  doi:10.1093/restud/rdae007. https://arxiv.org/abs/2108.12419 [V]
- Callaway, B., and Sant'Anna, P. H. C. (2021). Difference-in-differences with multiple
  time periods. *Journal of Econometrics*, 225(2), 200-230.
  doi:10.1016/j.jeconom.2020.12.001. https://arxiv.org/abs/1803.09015 [V]
- Callaway, B., Goodman-Bacon, A., and Sant'Anna, P. H. C. Difference-in-differences
  with a continuous treatment. https://arxiv.org/abs/2107.02637 [S, not checked]
- Cameron, A. C., Gelbach, J. B., and Miller, D. L. (2008). Bootstrap-based improvements
  for inference with clustered errors. *Review of Economics and Statistics*, 90(3),
  414-427. https://www.nber.org/papers/t0344 [V]
- Chernozhukov, V., Chetverikov, D., Demirer, M., Duflo, E., Hansen, C., Newey, W., and
  Robins, J. (2018). Double/debiased machine learning for treatment and structural
  parameters. *Econometrics Journal*, 21(1), C1-C68. doi:10.1111/ectj.12097.
  https://www.nber.org/papers/w23564 [V]
- de Chaisemartin, C., and D'Haultfoeuille, X. (2020). Two-way fixed effects estimators
  with heterogeneous treatment effects. *American Economic Review*, 110(9), 2964-2996.
  doi:10.1257/aer.20181169. https://www.aeaweb.org/doi/10.1257/aer.20181169 [V]
- Dube, A., Girardi, D., Jorda, O., and Taylor, A. M. A local projections approach to
  difference-in-differences. NBER working paper (number not verified).
  [S, not checked]
- Gardner, J. (2022). Two-stage differences in differences.
  https://arxiv.org/abs/2207.05943 [V]
- Gelbach, J. B. (2016). When do covariates matter? And which ones, and how much?
  *Journal of Labor Economics*, 34(2). https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1425737
  [S; the SSRN link is quoted in pyfixest's docstring, V]
- Goodman-Bacon, A. (2021). Difference-in-differences with variation in treatment
  timing. *Journal of Econometrics*, 225(2), 254-277.
  https://www.nber.org/papers/w25018 [V]
- Lundberg, S. M., and Lee, S.-I. (2017). A unified approach to interpreting model
  predictions. *NeurIPS*. https://arxiv.org/abs/1705.07874 [S]
- MacKinnon, J. G., Nielsen, M. O., and Webb, M. D. (2023). Cluster-robust inference: a
  guide to empirical practice. *Journal of Econometrics*, 232(2), 272-299.
  doi:10.1016/j.jeconom.2022.04.001. https://arxiv.org/abs/2205.03285 [V]
- Melitz, M. J., and Polanec, S. (2015). Dynamic Olley-Pakes productivity decomposition
  with entry and exit. *RAND Journal of Economics*, 46(2), 362-375. [S]
- Nickell, S. (1981). Biases in dynamic models with fixed effects. *Econometrica*,
  49(6), 1417-1426. [S]
- Rambachan, A., and Roth, J. (2023). A more credible approach to parallel trends.
  *Review of Economic Studies*, 90(5), 2555-2591.
  https://economics.mit.edu/research/publications/more-credible-approach-parallel-trends [V]
- Roth, J. (2022). Pretest with caution: event-study estimates after testing for
  parallel trends. *American Economic Review: Insights*, 4(3), 305-322.
  doi:10.1257/aeri.20210236. https://www.aeaweb.org/doi/10.1257/aeri.20210236 [V]
- Sun, L., and Abraham, S. (2021). Estimating dynamic treatment effects in event
  studies with heterogeneous treatment effects. *Journal of Econometrics*, 225(2),
  175-199. doi:10.1016/j.jeconom.2020.09.006. https://arxiv.org/abs/1804.05785 [V]

Software documentation (not reachable from this session; APIs verified by running the
installed packages instead):

- pyfixest: https://py-econometrics.github.io/pyfixest/ (quickstart and standard
  errors tutorial seen via search results) [S]
- linearmodels: https://bashtage.github.io/linearmodels/ [S]
- csdid: https://github.com/d2cml-ai/csdid [S]
- differences: https://github.com/bernardodionisi/differences [S]
- DoubleML: https://docs.doubleml.org/ [S]
- econml: https://econml.azurewebsites.net/ [S]
- shap: https://shap.readthedocs.io/ [S]
- statsmodels Oaxaca-Blinder: https://www.statsmodels.org/stable/generated/statsmodels.stats.oaxaca.OaxacaBlinder.html [S]
- diff-diff: https://diff-diff.readthedocs.io/ [S, seen in search results]
