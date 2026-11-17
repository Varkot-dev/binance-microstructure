# Rare-event, time-to-event prediction on a panel, without fooling yourself

A methods guide for Part B of the market evolution project: "at each month-end, will this
USDT perpetual stop trading within the next 3 months?" It assumes you have read
`../README.md` (weeks 7 to 11).

**Tags used on claims.**
[V] = verified this session (code below was run on synthetic data with lifelines 0.30.3,
scikit-survival 0.28.0, scikit-learn 1.9.1, lightgbm 4.7.0, xgboost 3.4.1, shap 0.54.1,
or the claim was read in a source fetched this session).
[S] = from a secondary source (documentation summary, textbook, paper) not re-read in full here.
[I] = my inference or advice; reasonable but not checked.

Note: the lifelines and scikit-survival documentation sites could not be fetched from this
session (network block), so their APIs were verified by installing the packages and
inspecting signatures and running the code, not by reading the docs pages.

---

## 0. The problem in one paragraph

You have about 900 contracts, observed monthly for about 6 years. Each month a few of them
die (delisted). Many contracts are still alive when the data ends; for those you only know
"survived at least until now" (right-censored). Features change every month (volume, price,
trades, maybe trade-level predictability). You want a score each month that ranks contracts
by risk of dying in the next 3 months, and you want an honest estimate of how good that
score would have been in real time.

The three things that go wrong most often:

1. The label or a feature secretly uses information from after the prediction date.
2. The evaluation mixes past and future (random K-fold), so the score looks better than
   it would have been live.
3. The metric hides the fact that events are rare (accuracy, ROC-AUC alone).

---

## 1. Framing options and how they relate

### 1.1 Monthly binary classification on a person-period panel

One row per (contract, month-end) while the contract is alive. Label
`y = 1` if the contract's last trading month is in months t+1, t+2 or t+3, else 0.
Fit any classifier (logistic regression, LightGBM). [I]

- Pros: matches the question exactly ("within 3 months"); any classifier works; metrics
  are familiar (PR-AUC, calibration).
- Cons: labels of consecutive rows overlap (the label at t and at t+1 share two months),
  so rows are not independent; the last 3 months of data have no known negative labels and
  must be dropped. [I]

### 1.2 Discrete-time hazard model (the bridge)

Same person-period panel, but the label is "dies in the next month" (h = 1). The monthly
hazard is h(t) = P(die in month t+1 | alive at end of month t, features at t).
A logistic regression on person-period data, with a label that is 1 only in the death
period, is exactly the maximum-likelihood fit of a discrete-time hazard model
(Singer and Willett 1993). [S] Censoring is handled for free: a censored contract simply
contributes rows with y = 0 until it leaves the data. [S]

From monthly hazards you get the 3-month risk:
P(die within 3) = 1 - (1 - h1)(1 - h2)(1 - h3). If you only have features at t, the
simple approximation is 1 - (1 - h(t))^3. [I]

A complementary log-log link instead of logit makes coefficients interpretable like
Cox hazard ratios (grouped-time proportional hazards). [S]

**Practical point:** the "event within 3 months" classifier of 1.1 and a 1-month hazard
model are close relatives. Fit both; if they rank contracts very differently, investigate.
[I]

### 1.3 Continuous-time survival models

- **Kaplan-Meier (KM):** non-parametric survival curve, no features. Use it to *describe*
  (how long does a contract typically live? did survival change by listing cohort?).
  Not a predictor of individual risk. `lifelines.KaplanMeierFitter`. [V]
- **Cox proportional hazards with time-varying covariates:** hazard =
  baseline(t) x exp(beta . x(t)). With monthly features, use the start/stop ("long")
  format: one row per contract-month with `start`, `stop`, `event`.
  `lifelines.CoxTimeVaryingFitter`. It gives coefficients (hazard ratios) and
  `predict_partial_hazard` / `predict_log_partial_hazard` (relative risk), but no survival
  function prediction method. [V] Good for interpretation ("a 1 SD fall in volume
  multiplies hazard by X"), weaker for calibrated 3-month probabilities. [I]
- **Random survival forest (RSF):** `sksurv.ensemble.RandomSurvivalForest`. Non-linear,
  gives survival curves per row, but takes one feature vector per subject: no
  time-varying covariates. [V for API; I for the "no time-varying" consequence] Use it with
  **landmarking**: at each month-end, take the row's current features and the *remaining*
  time from that month (event or censoring). [S]
- **Gradient-boosted survival:**
  `sksurv.ensemble.GradientBoostingSurvivalAnalysis(loss="coxph")` [V];
  xgboost objectives `survival:cox` and `survival:aft` [V]. LightGBM has **no** built-in Cox
  objective (`objective="cox"` raises "Unknown objective type name") [V]; with LightGBM
  use the person-period classification framing instead.
- **DeepSurv / DeepHit:** neural Cox model and neural discrete-time model, available in
  `pycox` (PyTorch). [S] With about 900 subjects and maybe 150 to 300 events, a neural net
  has nothing to offer over logistic regression or a small boosted model, and is much
  easier to overfit. Mention in the write-up as "not tried, sample too small". [I]

### 1.4 Which one when

| Question you are answering | Recommended framing |
|---|---|
| "Rank this month's contracts by 3-month death risk" | Person-period classifier (logistic, LightGBM) |
| "What is the monthly hazard, and how does it depend on features?" | Discrete-time logistic hazard, or Cox time-varying |
| "How long do contracts live? Has that changed?" | Kaplan-Meier by cohort |
| "Non-linear model that respects censoring, survival curve per row" | RSF or xgboost survival on landmark rows |

[I]

---

## 2. Building the panel and the label (the part where cheating happens)

Definitions (pin these down in code, write them in the report):

- `last_month[c]`: the last calendar month in which contract c has a monthly kline.
- `data_end`: last month of the archive.
- A contract is an **event** if `last_month < data_end` **and** Q14 classifies it as a
  delisting (not a rename, merger, or migration). Renames and migrations are
  **censored** at their last month, or treated as a separate competing risk. [I]
- A contract with `last_month == data_end` is censored (alive).
- A partial last month: if a contract stops on the 5th, its last kline month contains 5
  days of trading. Features computed for that month are contaminated; you never predict
  *from* the last month. [I]

```python
import numpy as np
import pandas as pd

H = 3  # horizon in months

# panel: one row per (symbol, month) with monthly kline aggregates.
# month is a pandas Period with freq "M".
panel = panel.sort_values(["symbol", "month"]).reset_index(drop=True)
data_end = panel["month"].max()

last_month = panel.groupby("symbol")["month"].max()
# is_delisting: boolean Series by symbol from Q14's classification (renames = False)
event_month = last_month.where((last_month < data_end) & is_delisting)  # NaT if no event
cens_month = last_month                                                # where observation ends

panel["event_month"] = panel["symbol"].map(event_month)
m = panel["month"].apply(lambda p: p.ordinal)
e = panel["event_month"].apply(lambda p: p.ordinal if pd.notna(p) else np.nan)
c = panel["symbol"].map(cens_month).apply(lambda p: p.ordinal)

panel["months_to_event"] = e - m          # 0 means this is the last trading month
panel["y"] = panel["months_to_event"].between(1, H).astype(int)

# A row's label is known only if we watched the contract for H more months,
# or the event happened inside the window.
panel["label_known"] = (c - m >= H) | (panel["y"] == 1)

# Never predict from the final trading month (partial month, post-announcement trading).
panel = panel[panel["months_to_event"].fillna(99) >= 1]

# Features: only past and current month. shift() looks backward within each symbol.
panel["log_vol"] = np.log(panel["quote_volume"])
panel["vol_chg_3m"] = panel["log_vol"] - panel.groupby("symbol")["log_vol"].shift(3)
panel["age_m"] = panel.groupby("symbol").cumcount()
# Cross-sectional rank within month: handles the growing universe and market-wide swings.
panel["vol_rank"] = panel.groupby("month")["log_vol"].rank(pct=True)

train_ready = panel[panel["label_known"]].dropna(subset=["vol_chg_3m"])
```

[V: this logic ran on a synthetic panel.]

Things to notice:

- Rows of a renamed contract near its rename get `y = 0` and are kept until its last month,
  then the contract is censored. If you instead counted renames as deaths you would teach
  the model that "a big, liquid coin that got renamed to 1000X" looks like a dying coin. [I]
- Rows with unknown labels at the end of the data are **dropped**, never set to 0. Setting
  them to 0 makes the most recent months look artificially safe. [I]
- Every feature uses `shift()` (backward) or values of month t only. A `rolling` window must
  end at t. Grep your code for `shift(-` before every run. [I]

---

## 3. Validation without leakage

### 3.1 Why random K-fold leaks here

1. **Time:** a random split trains on 2025 and tests on 2022. The model learns from future
   market regimes (e.g. a delisting wave) and from future delisting policies. [I]
2. **Overlapping labels:** the label at month t looks at t+1..t+3. Its neighbour at t+1 has
   nearly the same label and nearly the same features. Random splits put one in train and
   one in test, so the model is graded on near copies of training rows. [S] (López de Prado,
   Advances in Financial Machine Learning, ch. 7)
3. **Same contract on both sides:** a contract's level of volume is a fingerprint. With
   rows of the same contract in train and test, the model can memorise "contract X dies".
   [I]

### 3.2 Expanding-window CV with a purge gap

At test month T, in real life you know labels only for rows with month <= T - H (their
3-month window has closed). So training rows are those with month <= T - H. That gap is
the **purge**. [I, applying López de Prado's idea to this label]

An **embargo** (dropping rows just *after* the test block from training) matters only when
training data can come after the test block (K-fold style). With an expanding window,
training is always before the test block, so the purge is enough. [S, Wikipedia
"Purged cross-validation"; I for the application]

```python
def expanding_splits(months, first_test, horizon=3, test_len=6, step=6):
    """Yield (train_idx, test_idx). months: Series of pandas Period('M').
    Train on rows whose label window closed before the test block starts."""
    ms = np.sort(months.unique())
    t0 = list(ms).index(first_test)
    while t0 < len(ms):
        test_block = ms[t0:t0 + test_len]
        train_end = test_block[0] - horizon        # purge
        tr = np.where(months <= train_end)[0]
        te = np.where(months.isin(test_block))[0]
        yield tr, te
        t0 += step
```

[V: ran.] `sklearn.model_selection.TimeSeriesSplit(n_splits, max_train_size, test_size, gap)`
exists and has a `gap` argument [V], but it splits by row position, not by month, so with
a panel (many rows per month) it cuts through the middle of months. Prefer the explicit
month-based splitter above. [I]

**Grouping by contract.** Within a time split the same contract appears in train (earlier
months) and test (later months). That mirrors deployment, so it is allowed. What is not
allowed is tuning on a test fold. If you want to check "does it work on coins it has never
seen", add a variant that also drops test-block contracts from training
(`GroupKFold`-style). [I]

**Tuning.** Choose hyperparameters with the CV folds on years before the lock box; the
lock box (2026 delistings) is touched once. [README ground rule]

### 3.3 Intervals

Events cluster (Binance often delists several contracts in one announcement), so rows are
not independent. Bootstrap **months** (or blocks of months) for intervals on precision at
an alert rate; bootstrap **contracts** for coefficient intervals. [I]

---

## 4. Class imbalance

Base rate in a typical month is a few percent. [I; check your data]

- **Do not oversample blindly (SMOTE, random duplication).** Synthetic rows interpolate
  between contracts and months, which creates rows that mix future and past, and duplicated
  rows end up on both sides of any later split if you oversample before splitting. It also
  wrecks probability calibration. [I]
- **Class weights** (`class_weight="balanced"` in scikit-learn, `scale_pos_weight` or
  `class_weight` in LightGBM) change the loss, not the data. They can help a tree model
  find splits for the rare class, but **they inflate predicted probabilities**. In the
  synthetic test run, a logistic model with `class_weight="balanced"` predicted about 0.3 to
  0.4 for groups whose true rate was about 0.02, and its Brier score (0.24) was far worse
  than predicting the base rate. [V] If you weight, either recalibrate on a later fold
  (`sklearn.calibration.CalibratedClassifierCV`, or isotonic on out-of-fold scores) or only
  use the scores for ranking. [I]
- Often the best choice is **no resampling and no weights**, and judge by ranking metrics.
  Logistic regression with rare events is fine if you have enough events per feature
  (rule of thumb about 10 or more events per parameter). [S]

---

## 5. Metrics

### 5.1 Classification metrics (the main ones for this project)

- **PR-AUC (average precision):** `sklearn.metrics.average_precision_score`. Compare to
  the base rate (the PR-AUC of a random score is about the positive rate). ROC-AUC can look
  high on rare events while precision is useless; PR curves show that (Saito and Rehmsmeier
  2015). [S]
- **Precision at a fixed alert rate:** each month, flag the top k% (or top N) contracts by
  score; precision = share of flagged that die within 3 months. This handles the
  changing universe size and is what a user would act on. Also report recall at that rate.
  [I] (This is the lock-box metric named in the README.)
- **Calibration:** reliability curve (`sklearn.calibration.calibration_curve` or
  `CalibrationDisplay`), and Brier score (`sklearn.metrics.brier_score_loss`). With rare
  events use quantile bins so each bin has events. [V for APIs]

```python
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_curve
from sklearn.calibration import calibration_curve

d = train_ready.reset_index(drop=True)
feats = ["vol_chg_3m", "vol_rank"]
X, y = d[feats].to_numpy(), d["y"].to_numpy()

oof = np.full(len(d), np.nan)
for tr, te in expanding_splits(d["month"], first_test=pd.Period("2023-01", "M")):
    clf = LogisticRegression(max_iter=1000).fit(X[tr], y[tr])
    oof[te] = clf.predict_proba(X[te])[:, 1]

ok = ~np.isnan(oof)
print("PR-AUC", average_precision_score(y[ok], oof[ok]), "base rate", y[ok].mean())
print("Brier", brier_score_loss(y[ok], oof[ok]),
      "Brier of base rate", brier_score_loss(y[ok], np.full(ok.sum(), y[ok].mean())))
prec, rec, thr = precision_recall_curve(y[ok], oof[ok])
frac_pos, mean_pred = calibration_curve(y[ok], oof[ok], n_bins=10, strategy="quantile")

def precision_at_alert_rate(df, score_col, rate=0.05):
    rows = []
    for month, g in df.groupby("month"):
        n = max(1, int(round(rate * len(g))))
        top = g.nlargest(n, score_col)
        rows.append((month, len(g), n, top["y"].sum(), g["y"].sum()))
    out = pd.DataFrame(rows, columns=["month", "n_live", "n_alerts", "hits", "events"])
    return out  # pooled precision = hits.sum() / n_alerts.sum()

per_month = precision_at_alert_rate(d[ok].assign(score=oof[ok]), "score")
```

[V: ran.] Report pooled precision (`hits.sum() / n_alerts.sum()`) and its interval from
bootstrapping months of `per_month`. [I]

### 5.2 Survival metrics (for Cox, RSF, xgboost survival)

All in `sksurv.metrics` [V for signatures]:

- `concordance_index_censored(event_indicator, event_time, estimate)`: Harrell's C, the
  share of comparable pairs ranked correctly. Easy to inflate with long horizons; it says
  nothing about 3-month calibration. [S]
- `concordance_index_ipcw(survival_train, survival_test, estimate, tau=None)`: Uno's C,
  less biased under heavy censoring; set `tau` to limit to a horizon. [S]
- `cumulative_dynamic_auc(survival_train, survival_test, estimate, times)`: time-dependent
  AUC at given horizons (e.g. 1, 2, 3 months); returns per-time AUCs and their mean. [V]
- `brier_score(...)` and `integrated_brier_score(survival_train, survival_test, estimate,
  times)`: `estimate` is a matrix of survival probabilities, one column per time. [V]

`survival_train` is needed to estimate the censoring distribution (IPCW weights). [S]
`lifelines.utils.concordance_index` also exists. [V]

---

## 6. Baselines that must be beaten

Each, scored with the same splits and the same metric (precision at the same alert rate,
PR-AUC): [I, following the README ground rule]

1. **Falling-volume rule:** score = -(log volume now minus log volume 3 months ago). Flag
   the top k%. No fitting, except perhaps the choice of window, chosen on training data.
2. **Low-volume rule:** score = -(volume rank within month). Small coins die more.
3. **Logistic on 2 features:** `vol_chg_3m` and `vol_rank` (maybe plus `age_m`).
4. **Base rate** as a sanity floor for Brier score and PR-AUC.

The Part B checkpoint ("does a trade-level feature add anything?") is answered by comparing
baseline 3 against the same model plus the trade-level feature, on the same rows, with
the difference's interval from bootstrapping months. Note trade-level features exist only
for coins Q14 processed: compare on that common subset, otherwise the comparison mixes
populations. [I]

---

## 7. Model snippets

### 7.1 Kaplan-Meier and Cox with time-varying covariates (lifelines)

```python
from lifelines import KaplanMeierFitter, CoxTimeVaryingFitter

# Kaplan-Meier on one row per contract (time = months observed, event = delisted)
life = panel.groupby("symbol").agg(T=("age_m", "max"),
                                   E=("event_month", lambda s: s.notna().iloc[0]))
life["T"] += 1
kmf = KaplanMeierFitter().fit(life["T"], event_observed=life["E"], label="all contracts")
kmf.plot_survival_function()

# Cox, long format: one row per contract-month interval (start, stop]
cp = panel.dropna(subset=["vol_chg_3m"]).copy()
cp["start"] = cp["age_m"]
cp["stop"] = cp["age_m"] + 1
cp["event"] = (cp["months_to_event"] == 1).astype(int)   # dies in the next month

ctv = CoxTimeVaryingFitter(penalizer=0.1)
ctv.fit(cp[["symbol", "start", "stop", "event", "vol_chg_3m", "vol_rank"]],
        id_col="symbol", event_col="event", start_col="start", stop_col="stop")
ctv.print_summary()
risk = ctv.predict_partial_hazard(cp[["vol_chg_3m", "vol_rank"]])
```

[V: ran. Constructor is `CoxTimeVaryingFitter(alpha=0.05, penalizer=0.0, l1_ratio=0.0,
strata=None)`; fit is `fit(df, event_col, start_col="start", stop_col="stop",
weights_col=None, id_col=None, show_progress=False, robust=False, strata=None, ...)`.]

Notes:

- Here the time axis is **contract age** (months since listing). An alternative is
  **calendar time**, which absorbs delisting waves into the baseline hazard. Calendar time
  is closer to how predictions are used; try both and say which. [I]
- Contracts listed before the archive starts need **delayed entry**: `start` = age at first
  observed month, not 0. The start/stop format supports that directly. [S]
- Fit Cox inside each CV training fold and score the test fold with
  `predict_partial_hazard`; that gives a ranking you can feed to precision at alert rate. [I]
- Check proportional hazards (`CoxPHFitter.check_assumptions` exists for the
  non-time-varying model). [S, not run here]

### 7.2 Random survival forest on landmark rows (scikit-survival)

```python
from sksurv.ensemble import RandomSurvivalForest
from sksurv.util import Surv
from sksurv.metrics import (concordance_index_censored, cumulative_dynamic_auc,
                            integrated_brier_score)

lm = panel.dropna(subset=["vol_chg_3m"]).copy()
ends = lm["symbol"].map(cens_month).apply(lambda p: p.ordinal)
lm["E"] = lm["event_month"].notna()
lm["T"] = np.where(lm["E"], lm["months_to_event"], ends - m.loc[lm.index])  # remaining months
lm = lm[lm["T"] >= 1]

# Train on landmarks whose remaining-time could be observed before the test block.
# Simplest honest version: train landmarks up to train_end, censor their follow-up at
# train_end (so no event after train_end is used), test on later landmarks.
train_end, test_start, test_end = (pd.Period("2022-12", "M"), pd.Period("2023-01", "M"),
                                   pd.Period("2023-06", "M"))
tr = lm[lm["month"] <= train_end].copy()
cap = train_end.ordinal - tr["month"].apply(lambda p: p.ordinal)
tr["E"] = tr["E"] & (tr["T"] <= cap)
tr["T"] = np.minimum(tr["T"], cap)
tr = tr[tr["T"] >= 1]
te = lm[(lm["month"] >= test_start) & (lm["month"] <= test_end)].copy()
# We only care about the next few months: censor test follow-up at 6 months. This also
# keeps test times inside the training follow-up range, which the IPCW metrics require.
te["E"] = te["E"] & (te["T"] <= 6)
te["T"] = np.minimum(te["T"], 6)

feats = ["vol_chg_3m", "vol_rank", "age_m"]
y_tr = Surv.from_arrays(event=tr["E"].to_numpy(), time=tr["T"].to_numpy())
y_te = Surv.from_arrays(event=te["E"].to_numpy(), time=te["T"].to_numpy())

rsf = RandomSurvivalForest(n_estimators=300, min_samples_leaf=20, max_features="sqrt",
                           n_jobs=-1, random_state=0).fit(tr[feats], y_tr)

risk = rsf.predict(te[feats])                       # higher = riskier
print("Harrell C", concordance_index_censored(te["E"].to_numpy(), te["T"].to_numpy(), risk)[0])

times = np.array([1, 2, 3])
auc_t, mean_auc = cumulative_dynamic_auc(y_tr, y_te, risk, times)

fns = rsf.predict_survival_function(te[feats])      # list of step functions
S = np.vstack([[f(t) for t in times] for f in fns])
print("IBS", integrated_brier_score(y_tr, y_te, S, times))
p_die_3m = 1 - S[:, times.tolist().index(3)]        # comparable to the classifier's score
```

[V: the API calls ran; `RandomSurvivalForest(n_estimators=100, *, max_depth=None,
min_samples_split=6, min_samples_leaf=3, max_features="sqrt", ..., low_memory=False)`;
`predict_survival_function(X, return_array=False)`.]

Cautions [I]:

- Landmark rows of the same contract are strongly dependent: the forest sees each dying
  contract dozens of times. Use a large `min_samples_leaf`, and bootstrap by contract or
  month for intervals.
- The censoring cap at `train_end` is what makes this honest. Without it, a 2022 landmark
  "knows" its contract died in 2024.
- The IPCW metrics (`cumulative_dynamic_auc`, `brier_score`, `integrated_brier_score`,
  `concordance_index_ipcw`) estimate the censoring distribution from `survival_train`. If
  test follow-up runs past the longest training follow-up they fail with
  "censoring survival function is zero at one or more time points". [V: hit this error
  before adding the 6-month test cap above] Capping test follow-up at a short horizon fixes
  it and matches the question.

### 7.3 Boosted models

```python
import lightgbm as lgb
import xgboost as xgb

# (a) LightGBM classifier on the person-period panel (recommended boosted model)
gbm = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=15,
                         min_child_samples=50, subsample=0.8, subsample_freq=1,
                         colsample_bytree=0.8, verbose=-1)
gbm.fit(X[tr_idx], y[tr_idx])
score = gbm.predict_proba(X[te_idx])[:, 1]

# (b) xgboost Cox: label = time for events, -time for censored rows
dtr = xgb.DMatrix(tr[feats], label=np.where(tr["E"], tr["T"], -tr["T"]).astype(float))
bst = xgb.train({"objective": "survival:cox", "eta": 0.05, "max_depth": 3}, dtr, 200)
risk = bst.predict(xgb.DMatrix(te[feats]))          # hazard ratio scale

# (c) xgboost AFT: interval labels, upper bound = inf for censored
daft = xgb.DMatrix(tr[feats])
daft.set_float_info("label_lower_bound", tr["T"].to_numpy(float))
daft.set_float_info("label_upper_bound", np.where(tr["E"], tr["T"], np.inf).astype(float))
params = {"objective": "survival:aft", "eval_metric": "aft-nloglik",
          "aft_loss_distribution": "normal", "aft_loss_distribution_scale": 1.0,
          "eta": 0.05, "max_depth": 3}
bst_aft = xgb.train(params, daft, 200)
pred_time = bst_aft.predict(xgb.DMatrix(te[feats]))  # predicted survival time; lower = riskier
```

[V: ran. The xgboost tutorial says AFT needs `xgb.train` with a DMatrix, not the
scikit-learn wrapper. S]

---

## 8. Interpretability

- **SHAP for tree models:** `shap.TreeExplainer(model)`, then `explainer(X)` returns a
  `shap.Explanation` with `.values` of shape (rows, features). [V] Plots:
  `shap.plots.beeswarm(sv)`, `shap.plots.scatter(sv[:, "vol_chg_3m"])`. [S]
- **Partial dependence:** `sklearn.inspection.partial_dependence` and
  `PartialDependenceDisplay.from_estimator(model, X, features)`. [V for
  `partial_dependence`; S for the display]
- **Cox coefficients** are already interpretable as hazard ratios; standardise features
  first so the ratios are per 1 SD. [I]

Cautions [I]:

- SHAP and PDP explain the *model*, not the market. Correlated features (volume, trades,
  volume rank) share credit arbitrarily; PDP evaluates impossible combinations
  (high volume, few trades).
- For LightGBM classifiers SHAP values are on the log-odds scale by default. [S]
- An important feature on a leaky model is the leak. If one feature dominates, ask how it
  could know the future (section 9).

---

## 9. Pitfall checklist for this exact data

1. **Look-ahead in features.** No forward `shift`, no rolling windows centred on t, no
   normalisation using full-sample means or the full-sample price range. Scalers and
   thresholds are fitted on the training fold only. [I]
2. **Look-ahead in the label.** Label window starts at t+1. Rows with unknown labels at the
   end are dropped. [I]
3. **The delisting announcement.** Binance announces delistings some days before the
   contract stops. If the announcement falls in month t and the stop in t+1, month t's
   volume already includes the announcement crash. That row is "easy" and useless in
   practice. Report results with and without these rows, or predict with a 1-month gap
   (label = event in t+2..t+4). [I; check announcement dates]
4. **Last partial month.** Never use the final trading month as a prediction row. [I]
5. **Survivorship in the training set.** Build the universe from the archive inventory
   (every contract ever listed), not from today's exchange info, or dead contracts vanish.
   Q14 already hit a listing bug of this kind. [README]
6. **Renames and migrations as false events.** A contract that becomes `1000XUSDT`, or moves
   because of a token swap, "stops trading" but did not die. Use Q14's classification;
   censor them, or model them as a competing risk (`lifelines.AalenJohansenFitter` exists
   for cumulative incidence with competing events). [V that the class exists; I for use]
7. **Changing universe size.** 2020 had far fewer contracts than 2025. Use within-month
   ranks or z-scores, alert *rates* (top k%), and report per-month base rates. [I]
8. **Delisting waves.** Several contracts delisted in one announcement make events
   correlated; one bad month can dominate. Bootstrap months; show per-month hits. [I]
9. **Policy drift.** Binance's delisting criteria may change over time, so the past is a
   weaker guide. Expanding-window CV shows whether performance decays; compare to a rolling
   (fixed-length) window. [I]
10. **Short-lived contracts.** A contract listed 2 months ago has no 3-month volume change.
    Missingness itself is informative; include `age_m` and do not drop young contracts
    silently. [I]
11. **Price-based features from the future.** "Price fell 90% from its peak" must use the
    peak up to t, not the all-time peak in the dataset. [I]
12. **Tuning on the lock box**, even once, by looking at it and going back. Freeze first.
    [README]
13. **A surprisingly good number is a bug** until shown otherwise (README ground rule). PR-AUC
    many times the base rate in week 8 means check items 1 to 4 first. [I]

---

## 10. Recommended setup (summary)

[I, all of this section]

- **Main framing:** person-period panel, one row per live contract-month, label "last
  trading month in t+1..t+3", renames censored, unknown-label rows dropped, final month
  excluded.
- **Models in order:** falling-volume rule, low-volume rule, logistic on 2 to 3 features
  (no class weights), LightGBM classifier, then a Cox time-varying model (lifelines) as an
  interpretable hazard check. RSF/xgboost survival on landmark rows only if time permits.
- **Validation:** month-based expanding window, 6-month test blocks, purge of 3 months
  (train rows with month <= test start minus 3), tuning inside the pre-lock-box period,
  lock box 2026 scored once.
- **Metrics:** precision and recall at a fixed monthly alert rate (e.g. top 5%) as the
  headline, PR-AUC versus base rate, Brier score and a reliability curve, plus time-dependent
  AUC at 3 months for survival models. Intervals by bootstrapping months.
- **Checkpoint test:** model with vs without the trade-level feature, same rows, difference
  with month-bootstrap interval.

---

## References

- Singer, J. D. and Willett, J. B. (1993). It's About Time: Using Discrete-Time Survival
  Analysis to Study Duration and the Timing of Events. Journal of Educational Statistics
  18(2). https://econpapers.repec.org/RePEc:sae:jedbes:v:18:y:1993:i:2:p:155-195
- Discrete-time survival in Python, worked notebook:
  https://nbviewer.jupyter.org/github/natematias/research_in_python/blob/master/survival_analysis/Discrete%20Time%20Survival%20Analysis%20in%20Python.ipynb
- Saito, T. and Rehmsmeier, M. (2015). The precision-recall plot is more informative than
  the ROC plot when evaluating binary classifiers on imbalanced datasets. PLoS ONE.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC4349800
- López de Prado, M. (2018). Advances in Financial Machine Learning, ch. 7 (purged K-fold,
  embargo). Summary: https://en.wikipedia.org/wiki/Purged_cross-validation
- lifelines, time-varying survival regression:
  https://lifelines.readthedocs.io/en/latest/Time%20varying%20survival%20regression.html
- lifelines `CoxTimeVaryingFitter`:
  https://lifelines.readthedocs.io/en/latest/fitters/regression/CoxTimeVaryingFitter.html
- scikit-survival documentation (RSF, metrics, evaluation guide):
  https://scikit-survival.readthedocs.io/en/stable/
- XGBoost survival analysis with AFT: https://xgboost.readthedocs.io/en/latest/tutorials/aft_survival_analysis.html
- XGBoost parameters (`survival:cox`, `survival:aft`): https://xgboost.readthedocs.io/en/stable/parameter.html
- scikit-learn probability calibration: https://scikit-learn.org/stable/modules/calibration.html
- scikit-learn precision-recall: https://scikit-learn.org/stable/auto_examples/model_selection/plot_precision_recall.html
- SHAP documentation: https://shap.readthedocs.io/en/latest/
- pycox (DeepSurv, DeepHit, Logistic-Hazard): https://github.com/havakv/pycox and https://pypi.org/project/pycox/
