"""Part B, weeks 8 to 9: models that try to beat the delisting baselines of b0.

Run from the repository root:

    PYTHONPATH=src .venv/bin/python research/market_evolution/b1_models.py

Reads `data/delisting_panel.parquet` (built by `b0_baselines.py build`) and reuses the b0
evaluation code: the same six expanding-window folds (test blocks of 6 months from 2023-01
to 2025-12), the same purge (a training row needs t + 3 < first test month), the same
top-5% alert rule, PR-AUC and the same moving-block bootstrap of test months. Origins from
2026-01 on are the lock-box: they are dropped before anything is fitted and NEVER scored.

Models (each with and without the sensitivity drop of the final full month before the last
trading month, `final_full_month`, from training and test rows alike, as in b0):

1. Logistic regression, full feature set. Train-only median imputation with missing
   indicators, train-only winsorizing and standardizing, L2 penalty, C chosen by the
   PR-AUC on an inner time-based validation split inside the training rows.
2. LightGBM classifier (num_threads=2, fixed modest hyperparameters, no class weights),
   early stopping on the same inner split, refit on all training rows with the chosen
   number of trees. TreeSHAP importance on the last fold (LightGBM's own `pred_contrib`,
   the same algorithm as `shap.TreeExplainer`; the shap package is not installed).
3. Discrete-time hazard view: a logistic hazard (label: dies in the next month) with
   odds ratios per 1 SD and intervals from resampling contract lives. The Cox
   time-varying model needs lifelines, which is not installed, so it is skipped.
4. Calibration: Platt and isotonic maps fitted on the inner validation split (training
   rows only), applied to the test scores; Brier score against the training base rate and
   reliability tables.

Ablations ask whether anything beyond volume level and trend helps: each model on the
volume features only, and on volume plus one other group (age, price and drawdown,
volatility, open interest, funding, other activity).

Writes `data/b1_models.md` and `data/b1_models.png`.
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE / "data"
PANEL = DATA / "delisting_panel.parquet"
OUT_MD = DATA / "b1_models.md"
OUT_PNG = DATA / "b1_models.png"
OUT_JSON = DATA / "b1_models.json"


def _load_b0():
    name = "b0_baselines"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HERE / "b0_baselines.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


b0 = _load_b0()
H = b0.H
LOCKBOX_T = b0.midx(b0.LOCKBOX_START)
FIRST_TEST_T = b0.midx(b0.FIRST_TEST)
N_THREADS = 2
INNER_VAL_LEN = 12          # months of the inner validation block (end of training rows)
C_GRID = (0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0)
LGB_PARAMS = {"objective": "binary", "learning_rate": 0.03, "num_leaves": 15,
              "max_depth": -1, "min_child_samples": 50, "subsample": 0.8,
              "subsample_freq": 1, "colsample_bytree": 0.8, "reg_lambda": 1.0,
              "n_estimators": 1000, "num_threads": N_THREADS, "verbose": -1,
              "random_state": 0}
LGB_PATIENCE = 50
# Early stopping metric: average precision, the ranking target. A first run used binary
# log loss; both stop after 1 to 36 trees in every fold (validation loss rises from the
# first trees on), so the 20-tree floor binds in most folds either way. Results of the two
# runs agree within 0.004 in precision at 5% (see the report).
LGB_STOP_METRIC = "average_precision"
LGB_FALLBACK_TREES = 200    # when the inner validation block has no positive row
N_BOOT_LIVES = 200          # life bootstrap for the hazard odds ratios

# --------------------------------------------------------------------------------------
# Features (month t and earlier only; label-side columns never enter)
# --------------------------------------------------------------------------------------

GROUPS: dict[str, list[str]] = {
    "volume level": ["log_qv", "qv_rank_pct", "log_trades", "trades_rank_pct",
                     "log_qv_median", "log_avg_trade"],
    "volume trend": ["dlog_qv_3m", "dlog_qv_6m", "dlog_trades_3m", "dlog_trades_6m",
                     "log_qv_rel_peak", "log_trades_rel_peak", "dlog_qv_3m_rank"],
    "age": ["log_age"],
    "price and drawdown": ["ret_month", "ret_3m", "ret_6m", "ret_3m_rank",
                           "dd_life_month_end", "max_dd_life", "log_price"],
    "volatility": ["realized_vol", "mean_range"],
    "open interest": ["log_oi", "oi_rank_pct", "log_oi_to_qv", "dlog_oi_3m",
                      "ls_account_month_end", "ls_toptrader_account_month_end"],
    "funding": ["funding_mean", "funding_abs_mean", "funding_interval_min_h",
                "funding_interval_shortened"],
    "other activity": ["taker_buy_share", "zero_volume_days"],
}
VOLUME = GROUPS["volume level"] + GROUPS["volume trend"]
FULL = [f for g in GROUPS.values() for f in g]
EXTRA_GROUPS = [g for g in GROUPS if g not in ("volume level", "volume trend")]
LABEL_SIDE = {"y3", "event", "status", "outcome", "last_trade_day", "last_trade_month",
              "months_to_last", "last_trade_dom", "final_full_month", "successor"}
# Compact set for the hazard odds ratios (one feature per idea, so the ratios can be read)
HAZARD_FEATURES = ["qv_rank_pct", "dlog_qv_3m", "log_qv_rel_peak", "log_age",
                   "dd_life_month_end", "ret_3m", "realized_vol", "log_oi_to_qv",
                   "funding_abs_mean"]


def prepare(df: pl.DataFrame) -> pl.DataFrame:
    """Derived feature columns. Ranks are within month t (same-month information only)."""
    def pct(col: str) -> pl.Expr:
        return pl.col(col).rank("average").over("t") / pl.col(col).count().over("t")

    return df.with_columns(
        log_qv_median=pl.col("quote_volume_median").log1p(),
        log_avg_trade=pl.col("avg_trade_usd").log1p(),
        log_price=pl.when(pl.col("close_last") > 0).then(pl.col("close_last").log()),
        funding_interval_shortened=pl.col("funding_interval_shortened").cast(pl.Float64),
        zero_volume_days=pl.col("zero_volume_days").cast(pl.Float64),
    ).with_columns(dlog_qv_3m_rank=pct("dlog_qv_3m"), ret_3m_rank=pct("ret_3m"))


def matrix(d: pl.DataFrame, feats: list[str]) -> np.ndarray:
    assert not set(feats) & LABEL_SIDE
    return d.select([pl.col(f).cast(pl.Float64) for f in feats]).to_numpy().astype(float)


# --------------------------------------------------------------------------------------
# Inner validation split (training rows only)
# --------------------------------------------------------------------------------------

def inner_split(t_train: np.ndarray, val_len: int = INNER_VAL_LEN, horizon: int = H
                ) -> tuple[np.ndarray, np.ndarray]:
    """Positions (into the training rows) of the inner-train and inner-validation rows.

    The validation block is the last `val_len` months of the training rows; inner-train
    rows have t + horizon < first validation month (the same purge as the outer folds).
    Only training rows are ever passed in, so neither part can hold a test-block or
    lock-box row.
    """
    last = int(t_train.max())
    v0 = last - val_len + 1
    return np.flatnonzero(t_train + horizon < v0), np.flatnonzero(t_train >= v0)


# --------------------------------------------------------------------------------------
# Logistic regression with train-only preprocessing
# --------------------------------------------------------------------------------------

class Prep:
    """Median imputation + missing indicators + winsorizing + standardizing, fitted on the
    rows passed to `fit` only."""

    def fit(self, X: np.ndarray) -> Prep:
        import warnings
        nan = np.isnan(X)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN column -> 0 below
            self.med = np.nan_to_num(np.nanmedian(X, axis=0))
        self.miss_cols = np.flatnonzero(nan.any(axis=0) & ~nan.all(axis=0))
        Xf = np.where(nan, self.med, X)
        self.lo = np.quantile(Xf, 0.01, axis=0)
        self.hi = np.quantile(Xf, 0.99, axis=0)
        Z = self._raw(X)
        self.mu, sd = Z.mean(axis=0), Z.std(axis=0)
        self.sd = np.where(sd > 0, sd, 1.0)
        return self

    def _raw(self, X: np.ndarray) -> np.ndarray:
        nan = np.isnan(X)
        Xf = np.clip(np.where(nan, self.med, X), self.lo, self.hi)
        return np.hstack([Xf, nan[:, self.miss_cols].astype(float)])

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (self._raw(X) - self.mu) / self.sd


class LogitModel:
    def __init__(self, C: float):
        self.C = C

    def fit(self, X: np.ndarray, y: np.ndarray) -> LogitModel:
        from sklearn.linear_model import LogisticRegression
        self.prep = Prep().fit(X)
        self.clf = LogisticRegression(C=self.C, max_iter=3000).fit(self.prep.transform(X), y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.clf.predict_proba(self.prep.transform(X))[:, 1]


def fit_logit_tuned(X: np.ndarray, y: np.ndarray, t: np.ndarray) -> dict:
    """C chosen by inner-validation PR-AUC (ties: the smaller C); refit on all rows."""
    itr, iva = inner_split(t)
    best_c, best_ap, aps = 1.0, -1.0, {}
    if y[iva].sum() > 0 and y[itr].sum() > 0:
        for c in C_GRID:
            m = LogitModel(c).fit(X[itr], y[itr])
            ap = b0.average_precision(y[iva], m.predict(X[iva]))
            aps[c] = ap
            if ap > best_ap + 1e-12:
                best_c, best_ap = c, ap
    inner = LogitModel(best_c).fit(X[itr], y[itr]) if y[itr].sum() > 0 else None
    model = LogitModel(best_c).fit(X, y)
    return {"model": model, "C": best_c, "inner_model": inner, "inner_idx": (itr, iva),
            "inner_ap": aps}


# --------------------------------------------------------------------------------------
# LightGBM
# --------------------------------------------------------------------------------------

class GBMModel:
    def __init__(self, n_trees: int):
        self.n_trees = n_trees

    def fit(self, X: np.ndarray, y: np.ndarray) -> GBMModel:
        import lightgbm as lgb
        params = {**LGB_PARAMS, "n_estimators": self.n_trees}
        self.clf = lgb.LGBMClassifier(**params).fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.clf.predict_proba(X)[:, 1]

    def contrib(self, X: np.ndarray) -> np.ndarray:
        """TreeSHAP values (log-odds), last column is the expected value."""
        return self.clf.predict_proba(X, pred_contrib=True)


def fit_gbm_tuned(X: np.ndarray, y: np.ndarray, t: np.ndarray) -> dict:
    """Early stopping (LGB_STOP_METRIC) on the inner validation block; refit on all rows."""
    import lightgbm as lgb
    itr, iva = inner_split(t)
    n_trees, inner = LGB_FALLBACK_TREES, None
    if y[iva].sum() > 0 and y[itr].sum() > 0:
        clf = lgb.LGBMClassifier(**{**LGB_PARAMS, "metric": LGB_STOP_METRIC}).fit(
            X[itr], y[itr], eval_X=(X[iva],), eval_y=(y[iva],),
            callbacks=[lgb.early_stopping(LGB_PATIENCE, verbose=False)])
        n_trees = max(20, int(clf.best_iteration_ or LGB_FALLBACK_TREES))
        inner = GBMModel(n_trees)
        inner.clf = clf
    model = GBMModel(n_trees).fit(X, y)
    return {"model": model, "n_trees": n_trees, "inner_model": inner,
            "inner_idx": (itr, iva)}


# --------------------------------------------------------------------------------------
# Calibration (fitted on the inner validation block of the training rows)
# --------------------------------------------------------------------------------------

def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def fit_calibrators(score: np.ndarray, y: np.ndarray) -> dict:
    """Platt (logistic on the log-odds of the score) and isotonic maps from (score, y)."""
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression
    platt = LogisticRegression(C=1e6, max_iter=1000).fit(_logit(score)[:, None], y)
    iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(score, y)
    return {"platt": lambda s: platt.predict_proba(_logit(s)[:, None])[:, 1],
            "isotonic": lambda s: iso.predict(s)}


# --------------------------------------------------------------------------------------
# Folds
# --------------------------------------------------------------------------------------

def model_specs() -> dict[str, tuple[str, list[str]]]:
    """key -> (kind, features). Order is the order of the tables."""
    specs = {"logit_full": ("logit", FULL), "gbm_full": ("gbm", FULL),
             "logit_vol": ("logit", VOLUME), "gbm_vol": ("gbm", VOLUME)}
    for g in EXTRA_GROUPS:
        specs[f"logit_vol+{g}"] = ("logit", VOLUME + GROUPS[g])
        specs[f"gbm_vol+{g}"] = ("gbm", VOLUME + GROUPS[g])
    return specs


CALIBRATED = ("logit_full", "gbm_full")


def run_folds(d: pl.DataFrame, folds: list[dict], specs: dict, shap_last: bool = True
              ) -> dict:
    """Out-of-fold scores for every spec plus calibrated scores for CALIBRATED.

    Every fit sees `train` rows of the fold only (and the inner split of those).
    """
    n = d.height
    y = d["y3"].to_numpy().astype(int)
    t = d["t"].to_numpy()
    scores = {k: np.full(n, np.nan) for k in specs}
    scores["base_b"] = -d["qv_rank_pct"].fill_null(np.nan).to_numpy().astype(float)
    cal = {f"{k}_{m}": np.full(n, np.nan) for k in CALIBRATED for m in ("platt", "isotonic")}
    ref = np.full(n, np.nan)
    info: list[dict] = []
    shap = None
    mats = {k: matrix(d, feats) for k, (_, feats) in specs.items()}
    for fi, f in enumerate(folds):
        tr, te = f["train"], f["test"]
        ref[te] = y[tr].mean()
        row = {"test": f"{b0.mstr(f['test_start'])} to {b0.mstr(f['test_stop'] - 1)}",
               "n_train": len(tr), "train_pos": int(y[tr].sum()), "n_test": len(te),
               "test_pos": int(y[te].sum())}
        for k, (kind, feats) in specs.items():
            X = mats[k]
            fit = (fit_logit_tuned if kind == "logit" else fit_gbm_tuned)(X[tr], y[tr], t[tr])
            scores[k][te] = fit["model"].predict(X[te])
            _, iva = fit["inner_idx"]
            if k == "logit_full":
                row.update(C=fit["C"], inner_val=f"{b0.mstr(int(t[tr][iva].min()))} to "
                           f"{b0.mstr(int(t[tr][iva].max()))}",
                           inner_val_pos=int(y[tr][iva].sum()))
            if k == "gbm_full":
                row["n_trees"] = fit["n_trees"]
            if k in CALIBRATED and fit["inner_model"] is not None:
                s_val = fit["inner_model"].predict(X[tr][iva])
                cals = fit_calibrators(s_val, y[tr][iva])
                for m, fn in cals.items():
                    # calibrated model = inner model + its map (the refit model has a
                    # different score range, so the map would not transfer to it)
                    cal[f"{k}_{m}"][te] = fn(fit["inner_model"].predict(X[te]))
            if shap_last and k == "gbm_full" and fi == len(folds) - 1:
                shap = {"values": fit["model"].contrib(X[te]), "X": X[te], "feats": feats,
                        "test": row["test"]}
        info.append(row)
    return {"scores": scores, "cal": cal, "ref": ref, "folds": info, "shap": shap}


# --------------------------------------------------------------------------------------
# Metrics with the month block bootstrap
# --------------------------------------------------------------------------------------

def ap_prepare(y: np.ndarray, s: np.ndarray) -> dict:
    """Sort once; `weighted_ap` then needs only row weights per replicate."""
    s = np.where(np.isfinite(s), s, -np.inf)
    order = np.argsort(-s, kind="stable")
    ss = s[order]
    last = np.append(ss[1:] != ss[:-1], True)  # last row of each tied score group
    return {"order": order, "last": last, "y": y[order].astype(float)}


def weighted_ap(prep: dict, w: np.ndarray) -> float:
    """Average precision (sklearn's step definition) with integer row weights."""
    ww = w[prep["order"]]
    tp = np.cumsum(ww * prep["y"])[prep["last"]]
    n = np.cumsum(ww)[prep["last"]]
    tot = tp[-1]
    if tot <= 0:
        return float("nan")
    prec = np.divide(tp, n, out=np.zeros_like(tp), where=n > 0)
    rec = tp / tot
    return float(np.sum(np.diff(np.concatenate([[0.0], rec])) * prec))


def evaluate_scores(t: np.ndarray, y: np.ndarray, scores: dict[str, np.ndarray],
                    baseline: str = "base_b", n_boot: int = b0.N_BOOT,
                    probs: dict[str, np.ndarray] | None = None) -> dict:
    """Precision and recall at the top 5% per month, PR-AUC, paired differences against
    `baseline`, and Brier scores for `probs`; 95% intervals from b0's month block bootstrap.
    Rows passed in are the test rows only."""
    probs = probs or {}
    months = np.unique(t)
    mpos = {int(m): i for i, m in enumerate(months)}
    row_m = np.array([mpos[int(m)] for m in t])
    alerts = {k: b0.alert_counts(t, y, s) for k, s in scores.items()}
    A = {k: np.array([a[int(m)] for m in months]) for k, a in alerts.items()}
    apz = {k: ap_prepare(y, s) for k, s in scores.items()}
    sq = {k: (p - y) ** 2 for k, p in probs.items()}

    def stats(wm: np.ndarray) -> dict:
        w = wm[row_m]
        out = {"base": float(np.sum(w * y) / np.sum(w))}
        for k in scores:
            a = A[k]
            out[f"prec_{k}"] = float(wm @ a[:, 2] / (wm @ a[:, 1]))
            ev = wm @ a[:, 3]
            out[f"rec_{k}"] = float(wm @ a[:, 2] / ev) if ev else float("nan")
            out[f"ap_{k}"] = weighted_ap(apz[k], w)
        for k in scores:
            if k != baseline:
                for m in ("prec", "rec", "ap"):
                    out[f"{m}_{k}_minus_b"] = out[f"{m}_{k}"] - out[f"{m}_{baseline}"]
        for k, e in sq.items():
            out[f"brier_{k}"] = float(np.sum(w * e) / np.sum(w))
        if "ref" in sq:
            for k in sq:
                if k != "ref":
                    out[f"bss_{k}"] = 1 - out[f"brier_{k}"] / out["brier_ref"]
        return out

    point = stats(np.ones(len(months)))
    reps = b0.block_bootstrap_months(months, n_boot=n_boot)
    boots = []
    for r in reps:
        wm = np.zeros(len(months))
        np.add.at(wm, np.searchsorted(months, r), 1.0)
        boots.append(stats(wm))
    ci = {k: (float(np.nanpercentile([b[k] for b in boots], 2.5)),
              float(np.nanpercentile([b[k] for b in boots], 97.5))) for k in point}
    tot = {k: (int(a[:, 1].sum()), int(a[:, 2].sum()), int(a[:, 3].sum())) for k, a in A.items()}
    return {"point": point, "ci": ci, "alerts_total": tot, "n_months": len(months)}


def reliability(p: np.ndarray, y: np.ndarray, bins: int = 10) -> list[tuple]:
    order = np.argsort(p, kind="stable")
    return [(float(p[b].min()), float(p[b].max()), len(b), int(y[b].sum()),
             float(p[b].mean()), float(y[b].mean())) for b in np.array_split(order, bins)]


# --------------------------------------------------------------------------------------
# Hazard odds ratios (discrete-time logistic hazard, life bootstrap)
# --------------------------------------------------------------------------------------

def hazard_odds_ratios(d: pl.DataFrame, label: np.ndarray, feats: list[str],
                       n_boot: int = N_BOOT_LIVES, seed: int = 0) -> list[dict]:
    """Odds ratio per 1 training SD of each feature (missing -> median + indicator, not
    reported), 95% intervals from resampling contract lives."""
    from sklearn.linear_model import LogisticRegression
    X = matrix(d, feats)
    prep = Prep().fit(X)
    Z = prep.transform(X)
    k = len(feats)

    def coef(idx: np.ndarray) -> np.ndarray:
        return LogisticRegression(C=1e4, max_iter=3000).fit(Z[idx], label[idx]).coef_[0][:k]

    beta = coef(np.arange(len(label)))
    lives = d["life_id"].to_numpy()
    uniq, inv = np.unique(lives, return_inverse=True)
    rows_of = [np.flatnonzero(inv == i) for i in range(len(uniq))]
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(uniq), len(uniq))
        bs.append(coef(np.concatenate([rows_of[i] for i in pick])))
    bs = np.array(bs)
    lo, hi = np.percentile(bs, 2.5, axis=0), np.percentile(bs, 97.5, axis=0)
    return [{"feature": f, "or": float(np.exp(beta[i])), "lo": float(np.exp(lo[i])),
             "hi": float(np.exp(hi[i])), "sd": float(prep.sd[i])}
            for i, f in enumerate(feats)]


# --------------------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------------------

def pre_lockbox(df: pl.DataFrame, drop_final_full: bool) -> pl.DataFrame:
    d = df.filter(pl.col("t") < LOCKBOX_T)
    if drop_final_full:
        d = d.filter(~pl.col("final_full_month"))
    return d.sort("t", "life_id")


def run_variant(df: pl.DataFrame, drop_final_full: bool) -> dict:
    d = pre_lockbox(df, drop_final_full)
    assert d["t"].max() < LOCKBOX_T
    t = d["t"].to_numpy()
    y = d["y3"].to_numpy().astype(int)
    folds = b0.purged_expanding_folds(t, FIRST_TEST_T, end=LOCKBOX_T)
    specs = model_specs()
    res = run_folds(d, folds, specs)
    test = np.concatenate([f["test"] for f in folds])
    tt, yt = t[test], y[test]
    sc = {k: v[test] for k, v in res["scores"].items()}
    probs = {"ref": res["ref"][test], "logit_full": sc["logit_full"],
             "gbm_full": sc["gbm_full"]}
    probs.update({k: v[test] for k, v in res["cal"].items()})
    ev = evaluate_scores(tt, yt, sc, probs=probs)
    rel = {k: reliability(probs[k], yt) for k in probs if k != "ref"}
    # Hazard odds ratios on all pre-lock-box rows (interpretation only, no scoring).
    mtl = d["months_to_last"].to_numpy()
    evt = d["event"].to_numpy()
    gap = 2 if drop_final_full else 1
    haz_label = (evt & (mtl == gap)).astype(int)
    haz = hazard_odds_ratios(d, haz_label, HAZARD_FEATURES)
    return {"eval": ev, "folds": res["folds"], "shap": res["shap"], "reliability": rel,
            "n_rows": len(test), "n_pos": int(yt.sum()),
            "test_lives": int(np.unique(d["life_id"].to_numpy()[test][yt == 1]).size),
            "hazard": haz, "hazard_gap": gap, "hazard_events": int(haz_label.sum()),
            "hazard_rows": len(haz_label), "specs": specs}


NAMES = {"base_b": "(b) lowest volume rank (bar)",
         "logit_full": "logistic, full features", "gbm_full": "LightGBM, full features",
         "logit_vol": "logistic, volume level + trend", "gbm_vol": "LightGBM, volume level + trend"}


def name(k: str) -> str:
    if k in NAMES:
        return NAMES[k]
    kind, grp = k.split("_vol+")
    return f"{'logistic' if kind == 'logit' else 'LightGBM'}, volume + {grp}"


def _ci(ev: dict, k: str, fmt: str = "{:.3f}") -> str:
    lo, hi = ev["ci"][k]
    return f"{fmt.format(ev['point'][k])} ({fmt.format(lo)} to {fmt.format(hi)})"


def _excl0(ev: dict, k: str) -> bool:
    lo, hi = ev["ci"][k]
    return lo > 0 or hi < 0


def shap_summary(sh: dict) -> tuple[list[list], list[list]]:
    v = sh["values"][:, :-1]
    X = sh["X"]
    imp = np.abs(v).mean(axis=0)
    rows = []
    for i in np.argsort(-imp):
        ok = np.isfinite(X[:, i])
        r = (np.corrcoef(X[ok, i], v[ok, i])[0, 1]
             if ok.sum() > 2 and np.std(X[ok, i]) > 0 and np.std(v[ok, i]) > 0 else np.nan)
        rows.append([sh["feats"][i], f"{imp[i]:.3f}", f"{imp[i] / imp.sum():.0%}",
                     "nan" if np.isnan(r) else f"{r:+.2f}"])
    grp_rows = []
    gi = {g: sum(imp[sh["feats"].index(f)] for f in fs) for g, fs in GROUPS.items()}
    for g, val in sorted(gi.items(), key=lambda kv: -kv[1]):
        grp_rows.append([g, f"{val:.3f}", f"{val / imp.sum():.0%}"])
    return rows, grp_rows


def write_md(res: dict, seconds: float) -> None:
    tbl = b0._md_table
    sections = []
    for label, r in res.items():
        ev = r["eval"]
        keys = ["base_b", "logit_full", "gbm_full", "logit_vol", "gbm_vol"]
        head_rows = []
        for k in keys:
            al, hits, _ = ev["alerts_total"][k]
            head_rows.append([name(k), _ci(ev, f"prec_{k}"), _ci(ev, f"rec_{k}"),
                              f"{hits}/{al}", _ci(ev, f"ap_{k}")])
        diff_rows = [[name(k), _ci(ev, f"prec_{k}_minus_b"), _ci(ev, f"rec_{k}_minus_b"),
                      _ci(ev, f"ap_{k}_minus_b"),
                      "yes" if _excl0(ev, f"prec_{k}_minus_b") and
                      ev["point"][f"prec_{k}_minus_b"] > 0 else "no"]
                     for k in keys[1:]]
        abl_rows = []
        for kind in ("logit", "gbm"):
            base_ap = ev["point"][f"ap_{kind}_vol"]
            base_p = ev["point"][f"prec_{kind}_vol"]
            for g in EXTRA_GROUPS:
                k = f"{kind}_vol+{g}"
                abl_rows.append([name(k), _ci(ev, f"prec_{k}"),
                                 f"{ev['point'][f'prec_{k}'] - base_p:+.3f}",
                                 _ci(ev, f"ap_{k}"), f"{ev['point'][f'ap_{k}'] - base_ap:+.3f}",
                                 _ci(ev, f"ap_{k}_minus_b")])
        cal_rows = [["training base rate (reference)", f"{ev['point']['brier_ref']:.5f}", ""]]
        for k in ("logit_full", "gbm_full", "logit_full_platt", "logit_full_isotonic",
                  "gbm_full_platt", "gbm_full_isotonic"):
            cal_rows.append([k.replace("_", " "), f"{ev['point'][f'brier_{k}']:.5f}",
                             _ci(ev, f"bss_{k}")])
        fold_rows = [[f["test"], f"{f['n_train']:,}", f["train_pos"], f.get("inner_val", ""),
                      f.get("inner_val_pos", ""), f.get("C", ""), f.get("n_trees", ""),
                      f"{f['n_test']:,}", f["test_pos"]] for f in r["folds"]]
        shap_rows, shap_grp = shap_summary(r["shap"])
        best_cal = min(("logit_full_platt", "logit_full_isotonic", "gbm_full_platt",
                        "gbm_full_isotonic"), key=lambda k: ev["point"][f"brier_{k}"])
        rel_rows = [[f"{lo:.4f} to {hi:.4f}", n, e, f"{mp:.4f}", f"{op:.4f}"]
                    for lo, hi, n, e, mp, op in r["reliability"][best_cal]]
        rel_raw = [[f"{lo:.4f} to {hi:.4f}", n, e, f"{mp:.4f}", f"{op:.4f}"]
                   for lo, hi, n, e, mp, op in r["reliability"]["gbm_full"]]
        haz_rows = [[h["feature"], f"{h['sd']:.3g}", f"{h['or']:.2f}",
                     f"{h['lo']:.2f} to {h['hi']:.2f}",
                     "yes" if h["lo"] > 1 or h["hi"] < 1 else "no"] for h in r["hazard"]]
        sections.append(f"""## {label}

Test rows {r['n_rows']:,} over {ev['n_months']} origin months (2023-01 to 2025-12),
{r['n_pos']} positive rows from {r['test_lives']} event lives; base rate
{_ci(ev, 'base', '{:.4f}')}. 95% intervals: b0's moving-block bootstrap of test months
(blocks of {b0.BOOT_BLOCK}, {b0.N_BOOT} replicates, seed {b0.SEED}: the same replicates
as b0, so the (b) row reproduces b0 exactly).

### Headline: top 5% of live contracts per month

{tbl(['model', 'precision', 'recall', 'hits/alerts', 'PR-AUC'], head_rows)}

Paired differences against (b), same bootstrap months:

{tbl(['model', 'precision - (b)', 'recall - (b)', 'PR-AUC - (b)',
      'beats (b), interval excludes 0'], diff_rows)}

### Does anything beyond volume level and trend help?

Volume features alone ({len(VOLUME)}: {', '.join(VOLUME)}), plus one group at a time. The
change columns are the point change against the same model on volume features only.

{tbl(['model', 'precision', 'change vs volume only', 'PR-AUC', 'change vs volume only',
      'PR-AUC - (b)'], abl_rows)}

### SHAP importance, LightGBM full model, last fold (test block {r['shap']['test']})

Mean absolute TreeSHAP value (mean abs SHAP) on the test rows (log-odds), share of the total, and the
correlation between a feature's value and its SHAP value (sign = direction of the effect).

{tbl(['feature', 'mean abs SHAP', 'share', 'corr(value, SHAP)'], shap_rows)}

By group:

{tbl(['group', 'mean abs SHAP summed', 'share'], shap_grp)}

### Discrete-time hazard: odds ratios per 1 SD

Logistic hazard on all {r['hazard_rows']:,} pre-lock-box rows of this variant, label = the
life's last trading month is t + {r['hazard_gap']} ({r['hazard_events']} events){
' (t + 1 rows are the dropped final full months, so the hazard is shifted by one month)'
if r['hazard_gap'] == 2 else ''}. Odds ratio per 1 training SD (raw SD given), all
features in one model, missing values set to the median with an indicator; 95% intervals
from resampling contract lives ({N_BOOT_LIVES} replicates). For rare events the odds ratio
is close to the hazard ratio. Interpretation only: this fit is not scored.

{tbl(['feature', 'SD', 'odds ratio', '95% interval', 'excludes 1'], haz_rows)}

### Calibration

Calibration maps are fitted per fold on the inner validation block (the last
{INNER_VAL_LEN} training months, scored by the model fitted on the inner-train rows) and
applied to the test scores of that inner model (the refitted model has a different score
range, so a map fitted on the inner model does not transfer to it). Brier skill =
1 - Brier / Brier of predicting the training base rate.

{tbl(['scores', 'Brier', 'Brier skill (95%)'], cal_rows)}

Reliability, best calibrated scores by Brier ({best_cal.replace('_', ' ')}), deciles:

{tbl(['predicted range', 'rows', 'positives', 'mean predicted', 'observed rate'], rel_rows)}

Reliability, LightGBM full model before calibration, deciles:

{tbl(['predicted range', 'rows', 'positives', 'mean predicted', 'observed rate'], rel_raw)}

### Folds

Training rows have t + 3 < test start (b0's folds). Inner split inside the training rows:
validation = the last {INNER_VAL_LEN} training months; inner-train rows have t + 3 < its
first month. C chosen by inner PR-AUC from {list(C_GRID)}; LightGBM trees by early stopping
on inner {LGB_STOP_METRIC.replace('_', ' ')} (patience {LGB_PATIENCE}; {LGB_FALLBACK_TREES} trees when the inner block
has no positive row).

{tbl(['test block', 'train rows', 'train pos', 'inner validation', 'inner val pos',
      'C (logistic full)', 'trees (LightGBM full)', 'test rows', 'test pos'], fold_rows)}
""")
    m = res["main"]["eval"]
    s = res["drop final full month"]["eval"]

    def verdict(ev: dict) -> str:
        wins = [name(k) for k in ("logit_full", "gbm_full", "logit_vol", "gbm_vol")
                if _excl0(ev, f"prec_{k}_minus_b") and ev["point"][f"prec_{k}_minus_b"] > 0]
        winsap = [name(k) for k in ("logit_full", "gbm_full", "logit_vol", "gbm_vol")
                  if _excl0(ev, f"ap_{k}_minus_b") and ev["point"][f"ap_{k}_minus_b"] > 0]
        return ((f"precision at 5%: {', '.join(wins)}" if wins else
                 "no model beats (b) on precision at 5% with an interval excluding zero")
                + "; " + (f"PR-AUC: {', '.join(winsap)}" if winsap else
                          "none on PR-AUC either"))

    def abl_best(ev: dict, kind: str) -> str:
        g = max(EXTRA_GROUPS, key=lambda g: ev["point"][f"ap_{kind}_vol+{g}"])
        return (f"{g} ({ev['point'][f'ap_{kind}_vol+{g}']:.3f} against "
                f"{ev['point'][f'ap_{kind}_vol']:.3f} for volume only)")

    shap_grp = shap_summary(res["main"]["shap"])[1]
    txt = f"""# B1: models against the delisting baselines

Built by `research/market_evolution/b1_models.py` from `delisting_panel.parquet`, reusing
the folds, purge, alert rule, PR-AUC and month block bootstrap of `b0_baselines.py`. Run
time {seconds:.0f} s, LightGBM on {N_THREADS} threads.

**Lock-box: origins {b0.LOCKBOX_START} on are removed before any fit and are NOT scored.**
The bar to beat is b0's baseline (b), score = -qv_rank_pct: precision 8.3% at the top 5%,
PR-AUC 0.056 (main run).

Packages: lightgbm and scikit-learn are installed. **shap is not installed**: SHAP values
come from LightGBM's built-in TreeSHAP (`pred_contrib=True`), the algorithm that
`shap.TreeExplainer` uses. **lifelines is not installed, so the Cox time-varying model is
skipped**; the hazard view is a discrete-time logistic hazard with odds ratios instead
(for a monthly death rate of a few percent the odds ratio is close to the hazard ratio).

## Setup

- Features ({len(FULL)}, month t and earlier only; within-month ranks use month t only):
{chr(10).join(f'  - {g}: {", ".join(fs)}' for g, fs in GROUPS.items())}
- Logistic regression: median imputation and missing indicators, winsorizing at the 1st
  and 99th percentiles and standardizing, all fitted on the training rows of the fold;
  L2 penalty, no class weights; C from the inner split.
- LightGBM: {', '.join(f'{k}={v}' for k, v in LGB_PARAMS.items() if k not in ('verbose',))};
  no class weights, missing values handled natively, early stopping on the inner split.
- Every model is fitted and scored on the same six folds as b0, then the sensitivity run
  drops `final_full_month` rows (the month before the last trading month, the one most
  likely to hold the announcement) from training and test rows, as b0 does.

{chr(10).join(sections)}
## Conclusion (plain language)

- **Nothing beats the volume-rank rule (b) with an interval that excludes zero.** Main
  run, precision at the top 5%: logistic on all features
  {m['point']['prec_logit_full']:.1%}, LightGBM {m['point']['prec_gbm_full']:.1%}, rule (b)
  {m['point']['prec_base_b']:.1%}. Paired differences against (b): logistic
  {_ci(m, 'prec_logit_full_minus_b')}, LightGBM {_ci(m, 'prec_gbm_full_minus_b')}; PR-AUC
  logistic {_ci(m, 'ap_logit_full_minus_b')}, LightGBM {_ci(m, 'ap_gbm_full_minus_b')}.
  Verdict, main run: {verdict(m)}. Without the final full month: {verdict(s)}.
- The full logistic model is the best candidate: its point estimates are above (b) in both
  runs ({m['point']['prec_logit_full_minus_b']:+.3f} and
  {s['point']['prec_logit_full_minus_b']:+.3f} in precision,
  {m['point']['ap_logit_full_minus_b']:+.3f} and {s['point']['ap_logit_full_minus_b']:+.3f}
  in PR-AUC), but 36 test months with clustered delistings cannot tell that from noise. It
  is the natural model to freeze for the lock-box, with (b) scored alongside it.
- LightGBM does not help. On the inner time split its validation score is best after 1 to
  36 trees in every fold, under both log loss and average precision, so the model is close
  to a few shallow trees: what it learns from earlier years does not carry forward. It
  lands at or below (b).
- Fitted models on the volume features alone do worse than the raw volume rank
  (logistic {_ci(m, 'prec_logit_vol_minus_b')}, LightGBM {_ci(m, 'prec_gbm_vol_minus_b')}
  in precision). Fitting weights to volume level and trend on earlier years adds drift, not
  signal; the rank alone is the robust part.
- **What carries the signal beyond volume:** open interest is the only group that lifts
  both models in both runs (precision at 5%
  {m['point']['prec_logit_vol+open interest'] - m['point']['prec_logit_vol']:+.3f} logistic,
  {m['point']['prec_gbm_vol+open interest'] - m['point']['prec_gbm_vol']:+.3f} LightGBM over
  volume only, main run), and in the LightGBM SHAP values of the last fold the groups rank
  {', '.join(f'{g[0]} {g[2]}' for g in shap_grp)}: a low open-interest rank (little
  leverage held relative to other contracts) is the strongest single feature, followed by
  funding (short funding intervals, large absolute funding) and price (low price, falls
  over 6 months). Price and drawdown add a little to the logistic model; age, volatility,
  funding and the other-activity group add nothing measurable to the top-5% precision on
  their own. None of the single-group gains has a paired interval clear of zero against
  (b).
- The hazard view agrees: per 1 SD, a higher volume rank cuts the monthly hazard
  (odds ratio about 0.24 main, 0.35 with the one-month shift), higher realized volatility
  and higher absolute funding raise it (about 2.1 and 1.4 main, 1.4 and 1.25 shifted), and
  volume change, drawdown from the peak, age and 3-month return have intervals covering 1
  once rank is in the model. Volatility's odds ratio falls from about 2.1 to 1.4 when the
  month before the last trading month is removed, so part of it is the announcement month.
- Calibration: no class weights were used, so raw probabilities are already close to the
  base rate. The full logistic model has the best Brier skill
  ({_ci(m, 'bss_logit_full')}); Platt and isotonic maps fitted on the inner block do not
  improve it: they are fitted on a 12-month block whose delisting rate differs from the
  next test block (2023 had almost no delistings, 2025 many), and isotonic maps from about
  30 to 80 events are coarse. The top deciles are under-predicted: use the scores for
  ranking, not as probabilities.

## Caveats

- **No announcement dates.** Binance announces a futures delisting about 5 to 10 days
  before settlement and the announcement moves price and volume. The panel has no
  announcement date per contract, so the sensitivity run drops the whole final full month
  instead. Part of the main-run score can come from announcement crashes that a live user
  would see too late; the sensitivity run is the fairer number.
- **Correlated delisting batches.** Binance delists in batches after review rounds, so
  positives cluster in a few months and one wave decides a 6-month block (the two 2023
  blocks have 9 positive rows in all). Intervals resample blocks of 3 months, and model
  comparisons use paired differences on the same replicates; separate intervals overlap far
  more than the paired ones suggest. With so few independent batches even a real gain of
  2 points of precision would be hard to confirm.
- The base rate drifts upward (2023 0.4%, 2025 3.0%), so every probability fitted on
  earlier years under-predicts; this hurts Brier scores but not the top-5% ranking.
- Many models and ablations were compared on the same 36 test months; the largest of
  several noisy differences is biased upward, so the open-interest gain is a lead to
  confirm on the lock-box, not a finding.
- Choices made after a first run, on these folds: the LightGBM early-stopping metric was
  changed from log loss to average precision (the four headline LightGBM results moved
  by at most 0.004 in precision at 5% and 0.003 in PR-AUC), and the calibration maps were first applied to the
  refitted model instead of the inner model they were fitted on (a bug: Brier skill was far
  below zero). No feature, hyperparameter or threshold was changed after seeing test
  results, and the lock-box is untouched.
- The `final_full_month` rows are also dropped from training in the sensitivity run, so
  the two runs differ in their training data as well as their test rows (as in b0).
- Open interest and long/short ratios start around 2021-12, so early training rows rely
  on missing indicators; the first two folds train mostly on 2021 to 2022 deaths.
- `oi_rank_pct` is ranked among contracts with open-interest data only; contracts without
  it get a missing value (and a missing indicator in the logistic model).
- Trade-level features (predictability, trade size from aggTrades) are not in this panel;
  the README checkpoint on them needs the Q14 subset.
- SHAP values explain one fitted model on one fold (2025-07 to 2025-12); correlated
  features (OI rank, OI level, trade rank, volume rank) share credit arbitrarily.
- The hazard odds ratios come from one model with correlated features (volume rank,
  peak drawdown, volume change); read them as conditional on the others. The Cox model
  was not fitted (lifelines missing).
"""
    OUT_MD.write_text(txt)


def plot(res: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    keys = ["base_b", "logit_vol", "gbm_vol", "logit_full", "gbm_full"]
    colors = {"main": "#2a78d6", "drop final full month": "#eb6834"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    for ax, (metric, title) in zip(axes, [("prec", "Precision at top 5% per month"),
                                         ("ap", "PR-AUC")]):
        for j, (label, r) in enumerate(res.items()):
            ev = r["eval"]
            for i, k in enumerate(keys):
                p = ev["point"][f"{metric}_{k}"]
                lo, hi = ev["ci"][f"{metric}_{k}"]
                yy = i + (0.15 if j == 0 else -0.15)
                ax.plot([lo, hi], [yy, yy], color=colors[label], lw=2, solid_capstyle="round")
                ax.plot(p, yy, "o", color=colors[label], ms=7,
                        mec="white", mew=1.5, label=label if i == 0 else None)
            ax.axvline(ev["point"][f"{metric}_base_b"], color=colors[label], lw=1, ls="--",
                       alpha=0.6)
            ax.axvline(ev["point"]["base"], color=colors[label], lw=1, ls=":", alpha=0.6)
        ax.set_title(title, fontsize=11, loc="left")
        ax.grid(axis="x", color="#e6e5e0", lw=0.8)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.set_xlim(left=0)
    axes[0].set_yticks(range(len(keys)), [name(k) for k in keys])
    axes[0].invert_yaxis()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="upper right", ncol=2, fontsize=9)
    fig.text(0.01, 0.01, "Test origins 2023-01 to 2025-12, 95% month block bootstrap. "
             "Dashed: baseline (b); dotted: base rate. Separate intervals; compare\n"
             "models with the paired differences in b1_models.md. Lock-box (2026) not scored.",
             fontsize=8, color="#52514e")
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(OUT_PNG, dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------------------
# Machine-readable output (for the Q16 report). Writes the numbers `run_variant` already
# computes; no modelling choice lives here. `--json-only` writes this file and leaves the
# Markdown and the figure untouched. Pre-lock-box folds only, as always in b1.
# --------------------------------------------------------------------------------------

def write_json(res: dict, path: Path = OUT_JSON) -> None:
    from microstructure.data.jsonio import dumps_strict
    out = {"source": "research/market_evolution/b1_models.py", "names": {}, "variants": {}}
    for label, r in res.items():
        ev = r["eval"]
        feat_rows, grp_rows = shap_summary(r["shap"])
        out["variants"][label] = {
            "point": ev["point"], "ci": {k: list(v) for k, v in ev["ci"].items()},
            "alerts_total": ev["alerts_total"], "n_months": ev["n_months"],
            "n_rows": r["n_rows"], "n_pos": r["n_pos"], "test_lives": r["test_lives"],
            "folds": r["folds"],
            "shap": {"test": r["shap"]["test"],
                     "features": [{"feature": f, "mean_abs": float(m), "share": sh,
                                   "corr": None if c == "nan" else float(c)}
                                  for f, m, sh, c in feat_rows],
                     "groups": [{"group": g, "mean_abs": float(m), "share": sh}
                                for g, m, sh in grp_rows]},
            "hazard": r["hazard"], "hazard_gap": r["hazard_gap"],
            "hazard_events": r["hazard_events"], "hazard_rows": r["hazard_rows"],
        }
        for k in r["specs"]:
            out["names"][k] = name(k)
    out["names"]["base_b"] = name("base_b")
    path.write_text(dumps_strict(out) + "\n")


def main(argv: list[str] | None = None) -> None:
    json_only = "--json-only" in (sys.argv[1:] if argv is None else argv)
    t0 = time.time()
    df = prepare(pl.read_parquet(PANEL))
    lb = df.filter(pl.col("t") >= LOCKBOX_T)
    print(f"lock-box RESERVED, not scored: {lb.height} rows from {b0.LOCKBOX_START}")
    res = {}
    for label, drop in (("main", False), ("drop final full month", True)):
        r = run_variant(df, drop)
        res[label] = r
        ev = r["eval"]
        print(f"[{label}] test rows {r['n_rows']}, positives {r['n_pos']}")
        for k in ("base_b", "logit_full", "gbm_full", "logit_vol", "gbm_vol"):
            print(f"  {name(k):40s} prec {_ci(ev, f'prec_{k}')} rec {_ci(ev, f'rec_{k}')} "
                  f"AP {_ci(ev, f'ap_{k}')}")
        print(f"  ({time.time() - t0:.0f} s)")
    write_json(res)
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    if json_only:
        return
    write_md(res, time.time() - t0)
    plot(res)
    print(f"wrote {OUT_MD.relative_to(ROOT)} and {OUT_PNG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
