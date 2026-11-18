"""Part B, weeks 10 to 11: the lock-box test of the frozen delisting candidates.

Run from the repository root:

    PYTHONPATH=src .venv/bin/python research/market_evolution/b2_lockbox.py dev
    PYTHONPATH=src .venv/bin/python research/market_evolution/b2_lockbox.py lockbox

`dev` runs the exact pipeline on a pseudo lock-box made of pre-2026 rows (origins 2025-07
to 2025-12, already scored in b1's last fold) and checks that it reproduces b1's last-fold
scores; it never reads a 2026 label and writes nothing. `lockbox` is the single real run:
it trains every candidate on the rows whose label window ends before 2026-01 and scores
once on origins 2026-01 to 2026-07 (the last month whose 3-month label is knowable; the
panel already drops censored rows). It refuses to run when `data/b2_lockbox.md` already
holds a lock-box result, unless `--rerun-reason` says why (a bug found after the run), and
then keeps the earlier run's tables in the report.

Nothing is chosen here. The candidates and their inner procedures are b0's and b1's code,
imported unchanged:

- (a) falling volume (b0): score = -dlog_qv_3m.
- (b) lowest volume rank (b0): score = -qv_rank_pct. The bar.
- logistic, full features (b1): `b1.fit_logit_tuned` on `b1.FULL`.
- LightGBM, full features (b1): `b1.fit_gbm_tuned` on `b1.FULL`.

Metrics are b1's `evaluate_scores` (top 5% of live contracts per month, PR-AUC, paired
differences against (b), Brier score), with b0's moving-block bootstrap of months.
Writes `data/b2_lockbox.md`.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE / "data"
PANEL = DATA / "delisting_panel.parquet"
OUT_MD = DATA / "b2_lockbox.md"
RESULT_MARK = "<!-- b2 lock-box result -->"
FROZEN_FILES = ["research/market_evolution/b0_baselines.py",
                "research/market_evolution/b1_models.py",
                "research/market_evolution/data/delisting_panel.parquet"]


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


b1 = _load("b1_models", HERE / "b1_models.py")
b0 = b1.b0
H = b0.H
LOCKBOX_T = b0.midx(b0.LOCKBOX_START)
LOCKBOX_LAST = "2026-07"        # last origin with a knowable 3-month label (OBS_END - H)
DEV_START, DEV_STOP = b0.midx("2025-07"), LOCKBOX_T   # pseudo lock-box = b1's last fold
CANDIDATES = ("base_a", "base_b", "logit_full", "gbm_full")
NAMES = {"base_a": "(a) falling volume", "base_b": "(b) lowest volume rank",
         "logit_full": "logistic, full features", "gbm_full": "LightGBM, full features"}

# Cross-validation estimates (36 test months 2023-01 to 2025-12), copied from
# data/b0_baselines.md ((a)) and data/b1_models.md (the rest): point, low, high.
CV = {
    "main": {
        "base": 0.0238,
        "prec_base_a": (0.027, 0.008, 0.052), "ap_base_a": (0.028, 0.014, 0.043),
        "prec_base_b": (0.083, 0.031, 0.133), "ap_base_b": (0.056, 0.023, 0.086),
        "prec_logit_full": (0.101, 0.038, 0.153), "ap_logit_full": (0.076, 0.027, 0.120),
        "prec_gbm_full": (0.078, 0.031, 0.114), "ap_gbm_full": (0.053, 0.017, 0.087),
        "prec_logit_full_minus_b": (0.018, -0.008, 0.042),
        "ap_logit_full_minus_b": (0.020, -0.019, 0.055),
        "prec_gbm_full_minus_b": (-0.005, -0.041, 0.017),
        "ap_gbm_full_minus_b": (-0.004, -0.036, 0.030),
        "bss_logit_full": (0.021, -0.006, 0.038),
    },
    "drop final full month": {
        "base": 0.0166,
        "prec_base_a": (0.016, 0.003, 0.032), "ap_base_a": (0.019, 0.009, 0.031),
        "prec_base_b": (0.055, 0.021, 0.082), "ap_base_b": (0.040, 0.014, 0.060),
        "prec_logit_full": (0.062, 0.017, 0.094), "ap_logit_full": (0.060, 0.020, 0.092),
        "prec_gbm_full": (0.045, 0.015, 0.070), "ap_gbm_full": (0.033, 0.012, 0.055),
        "prec_logit_full_minus_b": (0.007, -0.019, 0.022),
        "ap_logit_full_minus_b": (0.020, -0.004, 0.045),
        "prec_gbm_full_minus_b": (-0.009, -0.023, 0.004),
        "ap_gbm_full_minus_b": (-0.008, -0.023, 0.012),
        "bss_logit_full": (0.017, -0.006, 0.029),
    },
}


# --------------------------------------------------------------------------------------
# Split, fit, score (pure, tested in tests/research/test_b2_lockbox.py)
# --------------------------------------------------------------------------------------

def train_mask(t: np.ndarray, lock_start: int = LOCKBOX_T, horizon: int = H) -> np.ndarray:
    """Training rows: label window t+1..t+horizon ends before the first lock-box month."""
    return t + horizon < lock_start


def lock_mask(t: np.ndarray, lock_start: int = LOCKBOX_T, lock_stop: int | None = None
              ) -> np.ndarray:
    m = t >= lock_start
    return m if lock_stop is None else m & (t < lock_stop)


def split(df: pl.DataFrame, drop_final_full: bool, lock_start: int = LOCKBOX_T,
          lock_stop: int | None = None) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(train, lock) frames, both sorted by t and life id. Rows with t in
    lock_start-H..lock_start-1 are purged (in neither). With `lock_stop` (dev mode) rows at
    or after it are removed before anything else, so they cannot reach either side."""
    d = df if lock_stop is None else df.filter(pl.col("t") < lock_stop)
    if drop_final_full:
        d = d.filter(~pl.col("final_full_month"))
    d = d.sort("t", "life_id")
    t = d["t"].to_numpy()
    train = d.filter(pl.Series(train_mask(t, lock_start)))
    lock = d.filter(pl.Series(lock_mask(t, lock_start, lock_stop)))
    assert train["t"].max() + H < lock_start
    assert lock["t"].min() >= lock_start
    return train, lock


def fit_frozen(train: pl.DataFrame, feats: list[str] | None = None) -> dict:
    """Fit the two model candidates with b1's inner procedures on `train` only."""
    feats = list(b1.FULL if feats is None else feats)
    X = b1.matrix(train, feats)
    y = train["y3"].to_numpy().astype(int)
    t = train["t"].to_numpy()
    logit = b1.fit_logit_tuned(X, y, t)
    gbm = b1.fit_gbm_tuned(X, y, t)
    itr, iva = logit["inner_idx"]
    return {"feats": feats, "logit": logit, "gbm": gbm, "train_base": float(y.mean()),
            "train_t_max": int(t.max()), "n_train": len(y), "train_pos": int(y.sum()),
            "inner_val": (b0.mstr(int(t[iva].min())), b0.mstr(int(t[iva].max()))),
            "inner_val_pos": int(y[iva].sum()), "inner_train_rows": len(itr)}


def score(fitted: dict, lock: pl.DataFrame, lock_start: int = LOCKBOX_T) -> dict:
    """Scores of every candidate on the lock-box rows. Labels are not read here."""
    assert lock["t"].min() >= lock_start
    X = b1.matrix(lock, fitted["feats"])
    return {
        "base_a": -lock["dlog_qv_3m"].fill_null(np.nan).to_numpy().astype(float),
        "base_b": -lock["qv_rank_pct"].fill_null(np.nan).to_numpy().astype(float),
        "logit_full": fitted["logit"]["model"].predict(X),
        "gbm_full": fitted["gbm"]["model"].predict(X),
    }


def per_month(lock: pl.DataFrame, sc: dict) -> list[dict]:
    t = lock["t"].to_numpy()
    y = lock["y3"].to_numpy().astype(int)
    lives = lock["life_id"].to_numpy()
    al = {k: b0.alert_counts(t, y, s) for k, s in sc.items()}
    out = []
    for m in np.unique(t):
        n, k, _, ev = al["base_b"][int(m)]
        row = {"month": b0.mstr(int(m)), "rows": n, "alerts": k, "pos": ev,
               "lives": int(np.unique(lives[(t == m) & (y == 1)]).size)}
        row.update({c: al[c][int(m)][2] for c in sc})
        out.append(row)
    return out


def fit_run(df: pl.DataFrame, drop_final_full: bool, lock_start: int = LOCKBOX_T,
            lock_stop: int | None = None, feats: list[str] | None = None) -> dict:
    """Split and fit; nothing is scored and no lock-box label is read."""
    train, lock = split(df, drop_final_full, lock_start, lock_stop)
    return {"lock": lock, "fitted": fit_frozen(train, feats), "lock_start": lock_start}


def score_run(fr: dict, n_boot: int = b0.N_BOOT) -> dict:
    lock, fitted = fr["lock"], fr["fitted"]
    sc = score(fitted, lock, fr["lock_start"])
    t = lock["t"].to_numpy()
    y = lock["y3"].to_numpy().astype(int)
    probs = {"ref": np.full(len(y), fitted["train_base"]), "logit_full": sc["logit_full"],
             "gbm_full": sc["gbm_full"]}
    ev = b1.evaluate_scores(t, y, sc, probs=probs, n_boot=n_boot)
    lives = lock["life_id"].to_numpy()
    pos = lock.filter(pl.col("y3") == 1).select("life_id", "last_trade_day").unique()
    return {"eval": ev, "fitted": fitted, "scores": sc, "months": per_month(lock, sc),
            "n_rows": len(y), "n_pos": int(y.sum()), "n_lives": int(np.unique(lives).size),
            "event_lives": int(np.unique(lives[y == 1]).size),
            "event_days": int(pos["last_trade_day"].n_unique()),
            "event_months": int(pos["last_trade_day"].dt.strftime("%Y-%m").n_unique()),
            "month_range": (b0.mstr(int(t.min())), b0.mstr(int(t.max())))}


def run(df: pl.DataFrame, drop_final_full: bool, lock_start: int = LOCKBOX_T,
        lock_stop: int | None = None, n_boot: int = b0.N_BOOT,
        feats: list[str] | None = None) -> dict:
    return score_run(fit_run(df, drop_final_full, lock_start, lock_stop, feats), n_boot)


# --------------------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------------------

def provenance() -> dict:
    def git(*a: str) -> str:
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    head = git("rev-parse", "HEAD")
    last = {f: git("log", "-1", "--format=%h", "--", f) for f in FROZEN_FILES}
    dirty = git("status", "--porcelain", "--", *FROZEN_FILES)
    sha = hashlib.sha256(PANEL.read_bytes()).hexdigest()
    return {"head": head, "last": last, "dirty": dirty, "panel_sha256": sha}


# --------------------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------------------

def _ci(ev: dict, k: str, fmt: str = "{:.3f}") -> str:
    lo, hi = ev["ci"][k]
    return f"{fmt.format(ev['point'][k])} ({fmt.format(lo)} to {fmt.format(hi)})"


def _cv(label: str, k: str) -> str:
    p, lo, hi = CV[label][k]
    return f"{p:.3f} ({lo:.3f} to {hi:.3f})"


def freeze_md(prov: dict, fitted: dict[str, dict]) -> str:
    last = ", ".join(f"`{Path(f).name}` {h}" for f, h in prov["last"].items())
    lgb = ", ".join(f"{k}={v}" for k, v in b1.LGB_PARAMS.items() if k != "verbose")
    groups = "\n".join(f"  - {g}: {', '.join(fs)}" for g, fs in b1.GROUPS.items())
    rows = []
    for label, f in fitted.items():
        rows.append(f"| {label} | {f['n_train']:,} | {f['train_pos']} | "
                    f"{b0.mstr(f['train_t_max'])} | {f['inner_val'][0]} to {f['inner_val'][1]} "
                    f"| {f['inner_val_pos']} | {f['logit']['C']} | {f['gbm']['n_trees']} | "
                    f"{f['train_base']:.4f} |")
    return f"""## 1. Frozen configuration (written before scoring)

Code and data come from commit `{prov['head']}` (HEAD when the lock-box was run); last
commits touching the frozen files: {last}. Uncommitted changes to them:
{'none' if not prov['dirty'] else prov['dirty']}. `delisting_panel.parquet` sha256
`{prov['panel_sha256'][:16]}...`. b2 imports b0 and b1 and calls their functions; it sets
no modelling option of its own.

- **(a) falling volume** (b0): score = -dlog_qv_3m (null ranks last). No fitted part.
- **(b) lowest volume rank** (b0): score = -qv_rank_pct, the within-month percentile rank of
  log quote volume among live contracts. No fitted part. This is the bar.
- **Logistic, full features** (b1 `fit_logit_tuned`), {len(b1.FULL)} features:
{groups}
  Preprocessing fitted on the training rows only: median imputation plus a missing
  indicator per column with some (not all) missing values, winsorizing at the 1st and 99th
  percentiles, standardizing. L2 penalty, no class weights, lbfgs, max_iter 3000. C chosen
  from {list(b1.C_GRID)} by PR-AUC on the inner split (validation = the last
  {b1.INNER_VAL_LEN} training months; inner-train rows have t + 3 < its first month; ties
  go to the smaller C), then refit on all training rows.
- **LightGBM, full features** (b1 `fit_gbm_tuned`): {lgb}; no class weights, missing
  values native. Trees chosen by early stopping on inner-split average precision (patience
  {b1.LGB_PATIENCE}, at least 20 trees, {b1.LGB_FALLBACK_TREES} if the inner block has no
  positive), then refit on all training rows with that number of trees.
- **Alert rule** (b0): each month flag the top max(1, round(0.05 x live contracts)) by
  score; ties by row order (month, life id). No other threshold enters the headline.
- **Training rows:** every labelled row with t + 3 < 2026-01 (t <= 2025-09), so no label
  window reaches 2026-01; origins 2025-10 to 2025-12 are purged. The sensitivity run also
  drops `final_full_month` rows from training and lock-box rows, as b0 and b1 do.
- **Intervals:** b0's moving-block bootstrap of lock-box months (blocks of
  {b0.BOOT_BLOCK}, {b0.N_BOOT} replicates, seed {b0.SEED}); paired differences use the
  same replicates.

Choices the frozen inner procedures made on the training rows (before scoring):

| run | train rows | train positives | last train month | inner validation | inner val positives | C (logistic) | trees (LightGBM) | training base rate |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}
"""


def results_md(label: str, r: dict) -> str:
    ev = r["eval"]
    rows = []
    for k in CANDIDATES:
        n_al, hits, _ = ev["alerts_total"][k]
        rows.append(f"| {NAMES[k]} | {_ci(ev, f'prec_{k}')} | {_ci(ev, f'rec_{k}')} | "
                    f"{hits}/{n_al} | {_ci(ev, f'ap_{k}')} |")
    diffs = []
    for k in ("logit_full", "gbm_full", "base_a"):
        diffs.append(f"| {NAMES[k]} - (b) | {_ci(ev, f'prec_{k}_minus_b')} | "
                     f"{_ci(ev, f'rec_{k}_minus_b')} | {_ci(ev, f'ap_{k}_minus_b')} |")
    mrows = []
    for m in r["months"]:
        mrows.append(f"| {m['month']} | {m['rows']} | {m['alerts']} | {m['pos']} | "
                     f"{m['lives']} | {m['base_a']} | {m['base_b']} | {m['logit_full']} | "
                     f"{m['gbm_full']} |")
    p = ev["point"]
    lomo = "; ".join(
        "{} {:+.3f} to {:+.3f}".format(NAMES[k], *leave_one_month_out(r["months"], k))
        for k in ("logit_full", "gbm_full", "base_a"))
    return f"""### {label}

Lock-box rows {r['n_rows']:,} ({r['n_lives']} lives) over {ev['n_months']} origin months
({r['month_range'][0]} to {r['month_range'][1]}); {r['n_pos']} positive rows from
{r['event_lives']} event lives; base rate {_ci(ev, 'base', '{:.4f}')}.

| candidate | precision at top 5% | recall | hits/alerts | PR-AUC |
|---|---|---|---|---|
{chr(10).join(rows)}

Paired differences against (b), same bootstrap months:

| difference | precision | recall | PR-AUC |
|---|---|---|---|
{chr(10).join(diffs)}

Robustness (not a frozen metric): range of the precision difference against (b) when one
lock-box month is left out: {lomo}.

Brier score: logistic {p['brier_logit_full']:.5f}, LightGBM {p['brier_gbm_full']:.5f},
predicting the training base rate {p['brier_ref']:.5f}. Brier skill: logistic
{_ci(ev, 'bss_logit_full')}, LightGBM {_ci(ev, 'bss_gbm_full')}. Mean predicted
probability: logistic {float(np.mean(r['scores']['logit_full'])):.4f}, LightGBM
{float(np.mean(r['scores']['gbm_full'])):.4f}, against an observed {p['base']:.4f}.

By month (hits among the alerts):

| origin month | live rows | alerts | positive rows | event lives | (a) | (b) | logistic | LightGBM |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(mrows)}
"""


def verdict(d: tuple[float, float, float], cv: tuple[float, float, float]) -> str:
    """Lock-box paired difference (point, lo, hi) against the CV point estimate's sign."""
    p, lo, hi = d
    if lo > 0:
        return ("strengthens: positive, interval now excludes 0" if cv[0] > 0
                else "reverses: positive, interval excludes 0")
    if hi < 0:
        return ("reverses: negative, interval excludes 0" if cv[0] > 0
                else "strengthens: negative, interval now excludes 0")
    if (p > 0) == (cv[0] > 0):
        return "confirms the sign, interval includes 0"
    return "weakens: sign flips, interval includes 0"


def leave_one_month_out(months: list[dict], k: str, base: str = "base_b") -> tuple:
    """Range of the precision difference k - base when one lock-box month is left out."""
    vals = []
    for i in range(len(months)):
        rest = months[:i] + months[i + 1:]
        al = sum(m["alerts"] for m in rest)
        vals.append((sum(m[k] for m in rest) - sum(m[base] for m in rest)) / al)
    return min(vals), max(vals)


def compare_md(res: dict) -> str:
    rows = []
    for label, r in res.items():
        ev = r["eval"]
        rows.append(f"| {label}: base rate | {CV[label]['base']:.4f} | "
                    f"{ev['point']['base']:.4f} | |")
        for k in ("prec_base_a", "prec_base_b", "prec_logit_full", "prec_gbm_full",
                  "ap_base_b", "ap_logit_full", "ap_gbm_full",
                  "prec_logit_full_minus_b", "ap_logit_full_minus_b",
                  "prec_gbm_full_minus_b", "ap_gbm_full_minus_b", "bss_logit_full"):
            lb = (ev["point"][k], *ev["ci"][k])
            v = verdict(lb, CV[label][k]) if "minus_b" in k else ""
            rows.append(f"| {label}: {k} | {_cv(label, k)} | {_ci(ev, k)} | {v} |")
    return f"""## 4. Comparison with the cross-validation estimates

CV = 36 test months 2023-01 to 2025-12 (b0 and b1, same metrics and bootstrap). The
verdict column applies only to the paired differences against (b).

| metric | CV (b0/b1) | lock-box | lock-box vs CV |
|---|---|---|---|
{chr(10).join(rows)}
"""


def write_md(res: dict, prov: dict, seconds: float, run_log: list[str],
             earlier: str = "") -> None:
    fitted = {k: r["fitted"] for k, r in res.items()}
    m = res["main"]
    body = "\n".join(results_md(k, r) for k, r in res.items())
    txt = f"""# B2: lock-box test of the frozen delisting candidates

Built by `research/market_evolution/b2_lockbox.py lockbox` from `delisting_panel.parquet`.
Run time {seconds:.0f} s, LightGBM on {b1.N_THREADS} threads.

{RESULT_MARK}
Lock-box runs: {'; '.join(run_log)}.

{freeze_md(prov, fitted)}
## 2. Lock-box size

- Origins {m['month_range'][0]} to {m['month_range'][1]}: {m['eval']['n_months']} months,
  {m['n_rows']:,} contract-months, {m['n_pos']} positive rows from {m['event_lives']}
  event lives (main run). Those lives stopped trading on {m['event_days']} distinct days in
  {m['event_months']} calendar months: Binance delists in batches, so the effective number
  of independent events is closer to the number of batches than to {m['event_lives']}.
- The bootstrap resamples {m['eval']['n_months']} months in blocks of {b0.BOOT_BLOCK}:
  only {m['eval']['n_months'] - b0.BOOT_BLOCK + 1} distinct blocks exist, so the intervals
  are rough and likely too narrow.
- Sensitivity run (final full month dropped): {res['drop final full month']['n_rows']:,}
  rows, {res['drop final full month']['n_pos']} positive rows.

## 3. Results

{body}
{compare_md(res)}
{CONCLUSION_PLACEHOLDER}
{earlier}"""
    OUT_MD.write_text(txt)


CONCLUSION_PLACEHOLDER = "<!-- conclusion and caveats are added below after the run -->"


# --------------------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------------------

def dev() -> None:
    """Pseudo lock-box on b1's last fold (2025-07 to 2025-12): must reproduce b1."""
    df = b1.prepare(pl.read_parquet(PANEL))
    df = df.filter(pl.col("t") < LOCKBOX_T)   # no 2026 row enters dev mode at all
    for label, drop in (("main", False), ("drop final full month", True)):
        r = run(df, drop, DEV_START, DEV_STOP, n_boot=500)
        # reference: b1's own fold code on the same data
        d = b1.pre_lockbox(df, drop)
        folds = b0.purged_expanding_folds(d["t"].to_numpy(), b1.FIRST_TEST_T, end=LOCKBOX_T)
        ref = b1.run_folds(d, folds[-1:], {"logit_full": ("logit", b1.FULL),
                                           "gbm_full": ("gbm", b1.FULL)}, shap_last=False)
        te = folds[-1]["test"]
        for k in ("logit_full", "gbm_full"):
            np.testing.assert_allclose(r["scores"][k], ref["scores"][k][te], rtol=1e-9)
        f = r["fitted"]
        ev = r["eval"]
        print(f"[dev {label}] train {f['n_train']} pos {f['train_pos']} C {f['logit']['C']} "
              f"trees {f['gbm']['n_trees']}; test {r['n_rows']} pos {r['n_pos']}: "
              "scores match b1's last fold")
        for k in CANDIDATES:
            print(f"   {NAMES[k]:28s} prec {_ci(ev, f'prec_{k}')} AP {_ci(ev, f'ap_{k}')}")
        print(f"   logit - (b) prec {_ci(ev, 'prec_logit_full_minus_b')}")


def lockbox(rerun_reason: str | None) -> None:
    t0 = time.time()
    earlier, run_log = "", []
    if OUT_MD.exists() and RESULT_MARK in OUT_MD.read_text():
        if not rerun_reason:
            sys.exit("b2_lockbox.md already holds a lock-box result; the lock-box is scored "
                     "once. Pass --rerun-reason only to fix a bug, and report both runs.")
        old = OUT_MD.read_text()
        line = next(x for x in old.splitlines() if x.startswith("Lock-box runs: "))
        run_log = [line.removeprefix("Lock-box runs: ").rstrip(".")]
        run_log.append(f"rerun on {time.strftime('%Y-%m-%d')} because: {rerun_reason}")
        start = old.index("## 3. Results")
        stop = old.index("## 4. Comparison")
        earlier = ("\n## Earlier lock-box run (superseded, kept for the record)\n\n"
                   + old[start:stop].replace("## 3. Results", "").strip() + "\n")
    else:
        run_log = [f"first run on {time.strftime('%Y-%m-%d')}"]
    prov = provenance()
    df = b1.prepare(pl.read_parquet(PANEL))
    assert df["t"].max() == b0.midx(LOCKBOX_LAST)
    variants = (("main", False), ("drop final full month", True))
    fits = {label: fit_run(df, drop) for label, drop in variants}
    # Freeze: write the configuration and the fitted choices to disk before any scoring.
    OUT_MD.write_text("# B2: lock-box test (frozen, not yet scored)\n\n"
                      + freeze_md(prov, {k: f["fitted"] for k, f in fits.items()}))
    for label, fr in fits.items():
        f = fr["fitted"]
        print(f"[{label}] FROZEN before scoring: train rows {f['n_train']} "
              f"(t <= {b0.mstr(f['train_t_max'])}), positives {f['train_pos']}, "
              f"C {f['logit']['C']}, trees {f['gbm']['n_trees']}")
    res = {}
    for label, fr in fits.items():
        res[label] = score_run(fr)
        ev = res[label]["eval"]
        print(f"[{label}] lock-box rows {res[label]['n_rows']}, positives "
              f"{res[label]['n_pos']}, base {ev['point']['base']:.4f}")
        for k in CANDIDATES:
            print(f"   {NAMES[k]:28s} prec {_ci(ev, f'prec_{k}')} rec {_ci(ev, f'rec_{k}')} "
                  f"AP {_ci(ev, f'ap_{k}')}")
        print(f"   logit - (b) prec {_ci(ev, 'prec_logit_full_minus_b')} "
              f"AP {_ci(ev, 'ap_logit_full_minus_b')}; Brier skill "
              f"{_ci(ev, 'bss_logit_full')}")
    write_md(res, prov, time.time() - t0, run_log, earlier)
    print(f"wrote {OUT_MD.relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", choices=["dev", "lockbox"])
    ap.add_argument("--rerun-reason", default=None)
    a = ap.parse_args(argv)
    if a.stage == "dev":
        dev()
    else:
        lockbox(a.rerun_reason)


if __name__ == "__main__":
    main()
