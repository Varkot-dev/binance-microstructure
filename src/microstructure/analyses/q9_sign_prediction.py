"""Q9: how much of the next trade's sign can be predicted, and by what?

Q1 measured a slowly decaying sign autocorrelation. That alone implies a
forecast: the best linear predictor of the next sign from the last 1000 signs
(the Yule-Walker filter). A learned model is only interesting for what it adds
over that, so this analysis climbs a ladder of predictors of increasing
freedom (`microstructure.ml.ladder.RUNGS`) and reports three paired increments:

  (a) linear minus persistence   what the long memory adds over the last sign
  (b) gbm_signs minus linear     what nonlinearity adds on the same sign history
  (c) gbm_all minus gbm_signs    what trade sizes, timing and price moves add

Method. One symbol-month is split on whole UTC days (20 train, 2 validation,
1 embargo, the rest test). The ladder is fitted once on the train days, the
boosting round count is picked on the validation days, and every rung is
scored on the test days. The same saved ladder is then applied, with no
refitting of any kind, to the whole following month (the lock-box).
Events that share a millisecond with the previous event are never scored
(their order is a sort artifact, see `microstructure.ml.dataset`).

Inference. Trades are strongly dependent, so every interval resamples whole
UTC days. The fit stage caches per-day sums of correct calls and log loss for
each rung, which is all the bootstrap needs: `sums_block_ci` reproduces
`microstructure.ml.evaluate.day_block_ci` from those sums, and the pooled
interval sums each day's sums across symbols so that a calendar day is one
block (symbols share market-wide days, so they are not independent blocks).

Stages (each resumable, one JSON per symbol under data/ml_cache/q9/):
  fit     fit and save the ladder, score the within-month test block
  next    score the frozen ladder on the whole holdout month
  report  build results/q9_sign_prediction.{json,md,png} from the caches only

This is a study of order-flow predictability. It measures no prices and no
costs and is not a trading result.
"""
from __future__ import annotations

import argparse
import dataclasses
import gc
import json
from pathlib import Path

import numpy as np

from microstructure.analyses import q9_report
from microstructure.analyses.q4_cross_section import FIT_LO
from microstructure.data.jsonio import dumps_strict
from microstructure.estimators.acf import fit_power_law, sign_acf
from microstructure.ml.dataset import (
    EMBARGO_DAYS,
    TRAIN_DAYS,
    VALID_DAYS,
    SignDataset,
    load_sign_dataset,
)
from microstructure.ml.evaluate import MS_PER_DAY, PairedCI, score, skill
from microstructure.ml.features import FEATURE_NAMES, SIGN_FEATURES, WARMUP
from microstructure.ml.ladder import (
    LINEAR_ORDER,
    RUNGS,
    TRAIN_CAP,
    VALID_CAP,
    Ladder,
    daily_sums,
    fit_ladder,
    predict_ladder,
)
from microstructure.ml.models import LGB_MAX_ROUNDS, LGB_PARAMS, LGB_PATIENCE

DEFAULT_SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "BNBUSDT", "LINKUSDT", "LTCUSDT", "AVAXUSDT", "1000PEPEUSDT",
)
# (key, lower rung, upper rung, what the difference isolates)
INCREMENTS = (
    ("memory", "persistence", "linear", "what the long memory adds"),
    ("nonlinearity", "linear", "gbm_signs", "what nonlinearity adds on the same sign information"),
    ("context", "gbm_signs", "gbm_all", "what size, timing and price-move features add"),
)
METRICS = ("accuracy", "log_loss")
# Same window as Q4's gamma: sign ACF to lag 1000, fitted over [FIT_LO, max_lag // 2].
ACF_MAX_LAG = 1000
N_BOOT = 2000
# Rows predicted per call. Bounds the float32 feature copies made by
# predict_ladder; a busy month has tens of millions of scoreable rows.
CHUNK_ROWS = 2_000_000
# Fixed inside microstructure.ml.models.fit_logistic; repeated here only so the
# trial log is complete.
LOGISTIC_SETTINGS = {"penalty": "l2", "C": 1.0, "max_iter": 300, "standardized": True}


# --------------------------------------------------------------------------
# Day-block bootstrap from cached daily sums
# --------------------------------------------------------------------------


def sums_block_ci(
    sums: np.ndarray, counts: np.ndarray, n_boot: int = N_BOOT, seed: int = 0,
) -> PairedCI:
    """95% CI for sum(sums) / sum(counts), resampling whole days.

    The sums-based twin of `day_block_ci`: given per-day sums of a per-event
    quantity (or of a paired difference) and per-day event counts, it draws
    the same day indices from the same generator, so on the same data the two
    agree to floating-point rounding.
    """
    sums = np.asarray(sums, dtype=np.float64)
    counts = np.asarray(counts, dtype=np.float64)
    k = sums.size
    if k == 0 or counts.sum() <= 0:
        raise ValueError("need at least one day with events")
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, k, size=(n_boot, k))
    stats = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return PairedCI(float(sums.sum() / counts.sum()), float(lo), float(hi), int(k))


def increment_day_sums(
    daily: dict, lower: str, upper: str, metric: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(days, per-day sum of the gain of `upper` over `lower`, per-day counts).

    Both metrics are signed so that positive means the upper rung is better:
    extra correct calls for accuracy, bits of log loss removed for log_loss.
    """
    days = np.asarray(daily["day"], dtype=np.int64)
    counts = np.asarray(daily["n"], dtype=np.float64)
    if metric == "accuracy":
        d = np.asarray(daily[upper]["correct"]) - np.asarray(daily[lower]["correct"])
    elif metric == "log_loss":
        d = np.asarray(daily[lower]["loss"]) - np.asarray(daily[upper]["loss"])
    else:
        raise ValueError(f"unknown metric {metric!r}")
    return days, d.astype(np.float64), counts


def pool_days(
    parts: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sum per-day sums and counts across symbols on the union of days.

    A symbol with no events on a day contributes nothing to that day. The
    pooled ratio of sums is therefore event-weighted: busy symbols count more.
    """
    days = np.unique(np.concatenate([p[0] for p in parts]))
    sums = np.zeros(days.size)
    counts = np.zeros(days.size)
    for d, s, c in parts:
        idx = np.searchsorted(days, d)
        np.add.at(sums, idx, s)
        np.add.at(counts, idx, c)
    return days, sums, counts


def ci_state(ci: dict) -> str:
    """Where a gain's 95% interval sits: 'positive', 'negative' or 'zero' (straddles 0)."""
    lo, hi = ci["ci95"]
    if lo > 0:
        return "positive"
    if hi < 0:
        return "negative"
    return "zero"


def _ci_dict(sums: np.ndarray, counts: np.ndarray, n_boot: int) -> dict:
    d = sums_block_ci(sums, counts, n_boot=n_boot).as_dict()
    d["state"] = ci_state(d)
    return d


def increments_from_daily(daily: dict, n_boot: int = N_BOOT) -> dict:
    """{increment: {metric: CI dict}} for one symbol's daily sums."""
    out: dict = {}
    for key, lower, upper, _ in INCREMENTS:
        out[key] = {}
        for metric in METRICS:
            _, s, c = increment_day_sums(daily, lower, upper, metric)
            out[key][metric] = _ci_dict(s, c, n_boot)
    return out


def pooled_increments(dailies: list[dict], n_boot: int = N_BOOT) -> dict:
    out: dict = {}
    for key, lower, upper, _ in INCREMENTS:
        out[key] = {}
        for metric in METRICS:
            parts = [increment_day_sums(d, lower, upper, metric) for d in dailies]
            _, s, c = pool_days(parts)
            out[key][metric] = _ci_dict(s, c, n_boot)
    return out


# --------------------------------------------------------------------------
# Fit and scoring stages
# --------------------------------------------------------------------------


def cache_root(root: Path, cache: Path | None = None) -> Path:
    return cache if cache is not None else root / "ml_cache"


def ladder_path(cache: Path, symbol: str, period: str) -> Path:
    return cache / "ladders" / symbol / f"{period}.pkl"


def fit_cache_path(cache: Path, symbol: str, period: str) -> Path:
    return cache / "q9" / f"{symbol}_{period}.json"


def holdout_cache_path(cache: Path, symbol: str, period: str, holdout_period: str) -> Path:
    return cache / "q9" / f"{symbol}_{period}_next_{holdout_period}.json"


def run_config(linear_order: int, train_cap: int, gbm_rounds: int | None) -> dict:
    """Every setting that defines the models of one run (the trial log entry)."""
    return {
        "split_days": {"train": TRAIN_DAYS, "valid": VALID_DAYS, "embargo": EMBARGO_DAYS},
        "warmup_events": WARMUP,
        "linear_order": linear_order,
        "train_cap": train_cap,
        "valid_cap": VALID_CAP,
        "lgb_params": dict(LGB_PARAMS),
        "lgb_max_rounds": LGB_MAX_ROUNDS if gbm_rounds is None else gbm_rounds,
        "lgb_patience": LGB_PATIENCE,
        "logistic": dict(LOGISTIC_SETTINGS),
        "sign_features": list(SIGN_FEATURES),
        "all_features": list(FEATURE_NAMES),
        "rungs": list(RUNGS),
    }


def predict_chunked(
    ladder: Ladder, ds: SignDataset, rows: np.ndarray, chunk_rows: int = CHUNK_ROWS,
) -> dict[str, np.ndarray]:
    """`predict_ladder` on `rows`, a bounded number of rows at a time.

    Each chunk is predicted on a view of the dataset that starts
    len(lin_weights) events before the chunk's first row. The linear rung is a
    finite filter over exactly that many past signs and persistence reads one,
    so the view gives the same probabilities as the full series while the
    filter runs once over the data in total instead of once per chunk.
    """
    if rows.size <= chunk_rows:
        return predict_ladder(ladder, ds, rows)
    order = int(ladder.lin_weights.size)
    parts: dict[str, list[np.ndarray]] = {r: [] for r in RUNGS}
    for a in range(0, rows.size, chunk_rows):
        r = rows[a : a + chunk_rows]
        start = max(0, int(r[0]) - order)
        end = int(r[-1]) + 1
        view = dataclasses.replace(
            ds, ts_ms=ds.ts_ms[start:end], signs=ds.signs[start:end], X=ds.X[start:end],
            y=ds.y[start:end], scoreable=ds.scoreable[start:end], train=ds.train[start:end],
            valid=ds.valid[start:end], test=ds.test[start:end],
        )
        for name, p in predict_ladder(ladder, view, r - start).items():
            parts[name].append(p)
    return {name: np.concatenate(ps) for name, ps in parts.items()}


def score_rows(ladder: Ladder, ds: SignDataset, rows: np.ndarray,
               chunk_rows: int = CHUNK_ROWS) -> dict:
    """Scores per rung and the per-day sums for the bootstrap, on the given rows."""
    probs = predict_chunked(ladder, ds, rows, chunk_rows)
    y = ds.y[rows].astype(np.float64)
    out = {
        "scores": {name: score(y, probs[name]).as_dict() for name in RUNGS},
        "daily": daily_sums(y, ds.ts_ms[rows], probs),
    }
    del probs
    return out


def memory_strength(train_signs: np.ndarray, max_lag: int = ACF_MAX_LAG) -> dict:
    """Sign-ACF power-law exponent on the training days, with Q4's fit window.

    Training days only, so the number that results are related to cannot have
    seen the test block. A series with no positive ACF in the window (short
    memory, as in the synthetic tests) has no power-law fit; gamma is then null.
    """
    max_lag = min(max_lag, train_signs.size - 1)
    acf = sign_acf(train_signs, max_lag)
    out = {"acf1": float(acf[1]), "max_lag": max_lag, "fit_lo": FIT_LO, "fit_hi": max_lag // 2,
           "gamma": None, "gamma_stderr": None}
    try:
        fit = fit_power_law(acf, lo=FIT_LO, hi=max_lag // 2)
        out["gamma"], out["gamma_stderr"] = float(fit.exponent), float(fit.stderr)
    except ValueError:
        pass
    return out


def fit_symbol(
    root: Path, symbol: str, period: str, *, cache: Path | None = None, force: bool = False,
    linear_order: int = LINEAR_ORDER, train_cap: int = TRAIN_CAP,
    gbm_rounds: int | None = None, chunk_rows: int = CHUNK_ROWS,
) -> Path:
    """Fit, save and score the ladder for one symbol-month; returns the cache path."""
    cache = cache_root(root, cache)
    out_path = fit_cache_path(cache, symbol, period)
    if out_path.exists() and not force:
        return out_path
    ds = load_sign_dataset(root, symbol, period)
    test_rows = ds.rows(ds.test)
    n_valid = int(ds.rows(ds.valid).size)
    if test_rows.size == 0 or n_valid == 0:
        raise ValueError(
            f"{symbol} {period}: the day split left {n_valid} validation and "
            f"{test_rows.size} test rows; the month needs more than "
            f"{TRAIN_DAYS + VALID_DAYS + EMBARGO_DAYS} days of events"
        )
    ladder = fit_ladder(ds, linear_order=linear_order, train_cap=train_cap, gbm_rounds=gbm_rounds)
    ladder.save(ladder_path(cache, symbol, period))
    record = {
        "symbol": symbol,
        "period": period,
        "config": run_config(linear_order, train_cap, gbm_rounds),
        "counts": {
            "n_events": int(ds.signs.size),
            "n_train_scoreable": int(ds.rows(ds.train).size),
            "n_train_rows_used": ladder.n_train_rows,
            "n_valid_scoreable": n_valid,
            "n_test_rows": int(test_rows.size),
            "n_test_days": int(np.unique(ds.ts_ms[test_rows] // MS_PER_DAY).size),
            "tie_share": ds.tie_share,
        },
        "baselines": {"buy_share": ladder.buy_share, "p_repeat": ladder.p_repeat},
        "gbm": {
            name: {
                "best_iteration": getattr(ladder, name).best_iteration,
                "gain_share": dict(zip(feats, getattr(ladder, name).gain_importance().tolist(),
                                       strict=True)),
            }
            for name, feats in (("gbm_signs", SIGN_FEATURES), ("gbm_all", FEATURE_NAMES))
        },
        "logit_all_coef": dict(zip(FEATURE_NAMES, ladder.logit_all.coef.tolist(), strict=True)),
        "acf": memory_strength(ds.signs[ds.train]),
        **score_rows(ladder, ds, test_rows, chunk_rows),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dumps_strict(record))
    del ds, ladder, record
    gc.collect()
    return out_path


def holdout_symbol(
    root: Path, symbol: str, period: str, holdout_period: str, *, cache: Path | None = None,
    force: bool = False, chunk_rows: int = CHUNK_ROWS,
) -> Path:
    """Score the saved ladder on the whole holdout month. Nothing is refitted:
    the models, the logistic standardization, the training buy share and the
    repeat probability all come from the pickle written by the fit stage."""
    if holdout_period == period:
        raise ValueError("the holdout month must differ from the training month")
    cache = cache_root(root, cache)
    out_path = holdout_cache_path(cache, symbol, period, holdout_period)
    if out_path.exists() and not force:
        return out_path
    lp = ladder_path(cache, symbol, period)
    if not lp.exists():
        raise FileNotFoundError(f"no saved ladder at {lp}; run the fit stage first")
    ladder = Ladder.load(lp)
    ds = load_sign_dataset(root, symbol, holdout_period)
    rows = np.flatnonzero(ds.scoreable)
    if rows.size == 0:
        raise ValueError(f"{symbol} {holdout_period}: no scoreable rows after warm-up")
    record = {
        "symbol": symbol,
        "period": period,
        "holdout_period": holdout_period,
        "counts": {
            "n_events": int(ds.signs.size),
            "n_rows": int(rows.size),
            "n_days": int(np.unique(ds.ts_ms[rows] // MS_PER_DAY).size),
            "tie_share": ds.tie_share,
        },
        **score_rows(ladder, ds, rows, chunk_rows),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dumps_strict(record))
    del ds, ladder, record
    gc.collect()
    return out_path


def run_stage(stage: str, root: Path, symbols: list[str], period: str,
              holdout_period: str | None, **kw) -> list[dict]:
    """Run 'fit' or 'next' for every symbol; a failing symbol is recorded, not fatal
    (months are still being downloaded, so a missing file must not stop the rest)."""
    failures: list[dict] = []
    for symbol in symbols:
        try:
            if stage == "fit":
                path = fit_symbol(root, symbol, period, **kw)
            else:
                kw_next = {k: v for k, v in kw.items() if k in ("cache", "force", "chunk_rows")}
                path = holdout_symbol(root, symbol, period, holdout_period, **kw_next)
            print(f"[q9 {stage}] {symbol}: {path}")
        except (FileNotFoundError, ValueError) as exc:
            print(f"[q9 {stage}] {symbol}: FAILED ({exc})")
            failures.append({"symbol": symbol, "stage": stage, "reason": str(exc)})
        gc.collect()
    return failures


# --------------------------------------------------------------------------
# Report stage (reads the caches only)
# --------------------------------------------------------------------------


def _median(values: list[float]) -> float | None:
    v = [x for x in values if x is not None and np.isfinite(x)]
    return float(np.median(v)) if v else None


def _corr(x: list[float], y: list[float]) -> dict:
    """Pearson and Spearman correlation across symbols; null below 3 points."""
    xa, ya = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    out = {"n": int(xa.size), "pearson": None, "spearman": None}
    if xa.size >= 3 and np.ptp(xa) > 0 and np.ptp(ya) > 0:
        out["pearson"] = float(np.corrcoef(xa, ya)[0, 1])
        rank = lambda a: np.argsort(np.argsort(a)).astype(np.float64)
        out["spearman"] = float(np.corrcoef(rank(xa), rank(ya))[0, 1])
    return out


def _block_summary(records: dict[str, dict], n_boot: int) -> dict:
    """Per-symbol scores, skills and increments plus the pooled increments for
    one scored block (the within-month test days or the holdout month)."""
    per_symbol: dict = {}
    for sym, rec in records.items():
        ref = rec["scores"]["persistence"]["log_loss_bits"]
        per_symbol[sym] = {
            "counts": rec["counts"],
            "scores": rec["scores"],
            "skill_vs_persistence": {
                r: skill(rec["scores"][r]["log_loss_bits"], ref) for r in RUNGS
            },
            "increments": increments_from_daily(rec["daily"], n_boot),
        }
    syms = list(per_symbol)
    increments_summary: dict = {}
    for key, _, _, _ in INCREMENTS:
        increments_summary[key] = {}
        for metric in METRICS:
            cis = [per_symbol[s]["increments"][key][metric] for s in syms]
            increments_summary[key][metric] = {
                "n_symbols": len(cis),
                "n_positive": sum(c["state"] == "positive" for c in cis),
                "n_negative": sum(c["state"] == "negative" for c in cis),
                "median_gain": _median([c["estimate"] for c in cis]),
            }
    return {
        "per_symbol": per_symbol,
        "median": {
            r: {
                "accuracy": _median([per_symbol[s]["scores"][r]["accuracy"] for s in syms]),
                "log_loss_bits": _median(
                    [per_symbol[s]["scores"][r]["log_loss_bits"] for s in syms]),
                "skill_vs_persistence": _median(
                    [per_symbol[s]["skill_vs_persistence"][r] for s in syms]),
            }
            for r in RUNGS
        },
        "increments_summary": increments_summary,
        "pooled": pooled_increments([r["daily"] for r in records.values()], n_boot),
        "pooled_n_days": int(np.unique(np.concatenate(
            [np.asarray(r["daily"]["day"]) for r in records.values()])).size),
    }


def _trial_log(fits: dict[str, dict]) -> dict:
    """Distinct model configurations across the caches, with the symbols run under each."""
    configs: list[dict] = []
    for sym, rec in fits.items():
        for entry in configs:
            if entry["config"] == rec["config"]:
                entry["symbols"].append(sym)
                break
        else:
            configs.append({"config": rec["config"], "symbols": [sym]})
    # Per configuration set, five models are estimated: the linear filter, two
    # logistic regressions and two boosted-tree models. Majority and persistence
    # are one-number baselines with nothing to tune.
    fitted = ["linear", "logit_signs", "gbm_signs", "logit_all", "gbm_all"]
    return {
        "n_distinct_configurations": len(configs),
        "fitted_models_per_configuration": fitted,
        "n_model_fits": len(fits) * len(fitted),
        "tuned_on_validation": ["LightGBM boosting round count (early stopping)"],
        "configurations": configs,
        "gbm_best_iteration": {
            sym: {m: rec["gbm"][m]["best_iteration"] for m in ("gbm_signs", "gbm_all")}
            for sym, rec in fits.items()
        },
    }


def build_result(
    cache: Path, symbols: list[str], period: str, holdout_period: str | None,
    n_boot: int = N_BOOT,
) -> dict:
    fits: dict[str, dict] = {}
    nexts: dict[str, dict] = {}
    for sym in symbols:
        p = fit_cache_path(cache, sym, period)
        if not p.exists():
            continue
        fits[sym] = json.loads(p.read_text())
        if holdout_period:
            ph = holdout_cache_path(cache, sym, period, holdout_period)
            if ph.exists():
                nexts[sym] = json.loads(ph.read_text())
    if not fits:
        raise FileNotFoundError(f"no Q9 fit caches for {period} under {cache / 'q9'}")

    within = _block_summary(fits, n_boot)
    for sym, rec in fits.items():
        within["per_symbol"][sym]["acf"] = rec["acf"]
        within["per_symbol"][sym]["baselines"] = rec["baselines"]

    gain = {
        f: float(np.mean([rec["gbm"]["gbm_all"]["gain_share"][f] for rec in fits.values()]))
        for f in FEATURE_NAMES
    }
    coef = {
        f: {
            "mean": float(np.mean([rec["logit_all_coef"][f] for rec in fits.values()])),
            "mean_abs": float(np.mean([abs(rec["logit_all_coef"][f]) for rec in fits.values()])),
        }
        for f in FEATURE_NAMES
    }
    with_gamma = [s for s, r in fits.items() if r["acf"]["gamma"] is not None]
    gammas = [fits[s]["acf"]["gamma"] for s in with_gamma]
    gamma_relation = {
        "symbols": with_gamma,
        "gamma": gammas,
        "linear_accuracy": _corr(
            gammas, [fits[s]["scores"]["linear"]["accuracy"] for s in with_gamma]),
        "memory_accuracy_gain": _corr(
            gammas,
            [within["per_symbol"][s]["increments"]["memory"]["accuracy"]["estimate"]
             for s in with_gamma]),
    }

    result = {
        "question": "How much of the next trade's sign can be predicted, and how much does a "
                    "learned model add over what the measured autocorrelation already implies?",
        "period": period,
        "holdout_period": holdout_period,
        "symbols": list(fits),
        "symbols_without_cache": [s for s in symbols if s not in fits],
        "rungs": list(RUNGS),
        "increments": [
            {"key": k, "lower": lo, "upper": up, "meaning": m} for k, lo, up, m in INCREMENTS
        ],
        "n_boot": n_boot,
        "within_month": within,
        "next_month": _block_summary(nexts, n_boot) if nexts else None,
        "next_month_symbols": list(nexts),
        "feature_importance": {
            "gbm_all_mean_gain_share": dict(sorted(gain.items(), key=lambda kv: -kv[1])),
            "logit_all_standardized_coef": coef,
        },
        "gamma_relation": gamma_relation,
        "trial_log": _trial_log(fits),
    }
    result["verdict"] = q9_report.verdict_paragraph(result)
    return result


def run_report(
    out_dir: Path, cache: Path, symbols: list[str], period: str,
    holdout_period: str | None, n_boot: int = N_BOOT,
) -> dict:
    result = build_result(cache, symbols, period, holdout_period, n_boot)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "q9_sign_prediction.json").write_text(dumps_strict(result))
    q9_report.write_markdown(out_dir / "q9_sign_prediction.md", result)
    q9_report.plot(out_dir / "q9_sign_prediction.png", result)
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Q9: next-trade-sign prediction ladder")
    parser.add_argument("--root", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=None,
                        help="cache directory (default: ROOT/ml_cache)")
    parser.add_argument("--stage", choices=("fit", "next", "report", "all"), default="all")
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--period", type=str, default="2023-06")
    parser.add_argument("--holdout-period", type=str, default="2023-07",
                        help="month scored with the frozen ladder; 'none' to skip")
    parser.add_argument("--force", action="store_true", help="recompute existing caches")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    holdout = None if args.holdout_period.lower() == "none" else args.holdout_period
    cache = cache_root(args.root, args.cache)
    if args.stage in ("fit", "all"):
        run_stage("fit", args.root, args.symbols, args.period, holdout,
                  cache=cache, force=args.force)
    if args.stage in ("next", "all") and holdout:
        run_stage("next", args.root, args.symbols, args.period, holdout,
                  cache=cache, force=args.force)
    if args.stage in ("report", "all"):
        result = run_report(args.out, cache, args.symbols, args.period, holdout)
        print(result["verdict"])


if __name__ == "__main__":
    main()
