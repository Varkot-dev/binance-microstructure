"""Q10: does a next-trade-sign model trained in 2023 go stale by 2026, and why?

Q8 found that a cross-sectional sign-flip law present in June 2023 had faded
by July 2026. Q10 asks the same of a predictive model. The model ladder of
`microstructure.ml.ladder` is fitted separately in each of five snapshot
months and every fitted ladder is scored on the held-out last days of every
month, giving a train-period by test-period transfer matrix per symbol.

From the matrix M and the source period s (2023-06):

  raw drop                 M[s, s] - M[s, j]   what the old model lost
  staleness gap G_j        M[j, j] - M[s, j]   what retraining recovers
  predictability change    M[j, j] - M[s, s]   the market got easier or harder

Only G_j measures staleness; a raw drop mixes it with a market that became
less predictable for every model. 2023-06 to 2023-07 is the yardstick for
ordinary one-month drift.

The why: a domain classifier measures how far the inputs moved (covariate
shift), importance reweighting splits the old model's loss change into a
covariate part and a concept residual (`microstructure.ml.drift`), and
per-period logistic refits show which input-to-output coefficients moved.

Stages, each resumable from per-symbol caches under `<cache>/q10/<symbol>/`:

  fit       one dataset at a time: fit the ladder (or reuse the one Q9 cached
            under `<cache>/ladders/`), save a random sample of train-day and
            test-day feature rows for the shift analysis
  transfer  outer loop over the TEST period so only one dataset is in memory:
            apply every cached ladder to its test block, keep per-day sums
  shift     from the saved samples only: domain classifier, per-feature
            shift, reweighting attribution
  report    from caches only: json, Markdown, figure (`q10_report`)

Run: uv run python -m microstructure.analyses.q10_drift --root data --out results
"""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path

import numpy as np

from microstructure.analyses.q10_report import (
    ATTRIBUTION_RUNGS,
    N_BOOT,
    PERIODS,
    SYMBOLS,
    TRANSFER_RUNGS,
    fit_path,
    ladder_path,
    sample_path,
    shift_path,
    transfer_path,
    write_report,
)
from microstructure.data.jsonio import dumps_strict
from microstructure.ml.dataset import load_sign_dataset
from microstructure.ml.drift import (
    DOMAIN_ROUNDS,
    density_ratio,
    domain_auc,
    equal_size,
    feature_shift,
    fit_domain_classifier,
    reweighting_attribution,
)
from microstructure.ml.evaluate import MS_PER_DAY, log_loss_bits
from microstructure.ml.features import FEATURE_NAMES
from microstructure.ml.ladder import (
    LINEAR_ORDER,
    TRAIN_CAP,
    Ladder,
    daily_sums,
    fit_ladder,
    predict_ladder,
)
from microstructure.ml.models import subsample

STAGES = ("fit", "transfer", "shift", "report")
# Rows kept per symbol-period for the shift analysis, from train days and from
# test days. Enough for a 20-feature domain classifier and small on disk.
SAMPLE_CAP = 100_000


def _write_json(path: Path, obj: dict) -> None:
    """Write then rename, so an interrupted run never leaves a half file that looks done."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(dumps_strict(obj, indent=0))
    os.replace(tmp, path)


def _log(msg: str) -> None:
    print(f"[q10] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Stage 1: fit
# ---------------------------------------------------------------------------


def fit_stage(
    root: Path, cache: Path, symbol: str, periods: list[str], *,
    linear_order: int = LINEAR_ORDER, train_cap: int = TRAIN_CAP,
    gbm_rounds: int | None = None, sample_cap: int = SAMPLE_CAP,
) -> list[dict]:
    """Ladder, feature samples and fit summary for each period; returns skips."""
    skips: list[dict] = []
    for period in periods:
        lp, sp, fp = (f(cache, symbol, period) for f in (ladder_path, sample_path, fit_path))
        if lp.exists() and sp.exists() and fp.exists():
            continue
        try:
            ds = load_sign_dataset(root, symbol, period)
        except FileNotFoundError as e:
            skips.append({"symbol": symbol, "period": period, "reason": str(e)})
            continue
        train_rows, test_rows = ds.rows(ds.train), ds.rows(ds.test)
        if train_rows.size == 0 or test_rows.size == 0 or ds.rows(ds.valid).size == 0:
            skips.append({"symbol": symbol, "period": period,
                          "reason": "month too short for the train/valid/test day split"})
            continue
        if lp.exists():
            ladder = Ladder.load(lp)
        else:
            ladder = fit_ladder(ds, linear_order=linear_order, train_cap=train_cap,
                                gbm_rounds=gbm_rounds)
            ladder.save(lp)
        tr = subsample(train_rows, sample_cap, seed=10)
        te = subsample(test_rows, sample_cap, seed=11)
        sp.parent.mkdir(parents=True, exist_ok=True)
        tmp = sp.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, X_train=ds.X[tr], X_test=ds.X[te], y_test=ds.y[te],
                            ts_test=ds.ts_ms[te])
        os.replace(tmp, sp)
        _write_json(fp, {
            "symbol": symbol, "period": period, "n_events": int(ds.signs.size),
            "tie_share": ds.tie_share, "n_train_rows": ladder.n_train_rows,
            "n_test_rows": int(test_rows.size), "p_repeat_train": ladder.p_repeat,
            "buy_share_train": ladder.buy_share,
            "gbm_all_rounds": ladder.gbm_all.best_iteration,
            "feature_names": list(FEATURE_NAMES),
            # Standardized within this symbol and period, so comparable across periods.
            "logit_all_coef": ladder.logit_all.coef, "logit_all_mean": ladder.logit_all.mean,
            "logit_all_scale": ladder.logit_all.scale,
            "gbm_all_gain": ladder.gbm_all.gain_importance(),
        })
        _log(f"fit {symbol} {period}: {ds.signs.size} events, {ladder.n_train_rows} train rows")
        del ds
        gc.collect()
    return skips


# ---------------------------------------------------------------------------
# Stage 2: transfer
# ---------------------------------------------------------------------------


def transfer_stage(root: Path, cache: Path, symbol: str, periods: list[str]) -> list[dict]:
    """Score every cached ladder on each period's test block; returns skips."""
    skips: list[dict] = []
    trained = [p for p in periods if ladder_path(cache, symbol, p).exists()]
    for test_period in periods:
        path = transfer_path(cache, symbol, test_period)
        existing = json.loads(path.read_text()) if path.exists() else None
        todo = [p for p in trained if existing is None or p not in existing["cells"]]
        if not todo:
            continue
        try:
            ds = load_sign_dataset(root, symbol, test_period)
        except FileNotFoundError as e:
            skips.append({"symbol": symbol, "period": test_period, "reason": str(e)})
            continue
        rows = ds.rows(ds.test)
        if rows.size == 0:
            skips.append({"symbol": symbol, "period": test_period, "reason": "empty test block"})
            continue
        y, ts = ds.y[rows], ds.ts_ms[rows]
        # "Repeat the last sign" as a degenerate forecast, to get its per-day hit counts.
        repeat = daily_sums(y, ts, {"r": (ds.signs[rows - 1] > 0).astype(np.float64)})
        out = existing or {"symbol": symbol, "test_period": test_period, "cells": {}}
        out.update({"n_test_rows": int(rows.size), "tie_share": ds.tie_share,
                    "repeat_last": {"day": repeat["day"], "n": repeat["n"],
                                    "correct": repeat["r"]["correct"]}})
        for train_period in todo:
            probs = predict_ladder(Ladder.load(ladder_path(cache, symbol, train_period)), ds, rows)
            out["cells"][train_period] = daily_sums(y, ts, {r: probs[r] for r in TRANSFER_RUNGS})
            del probs
        _write_json(path, out)
        _log(f"transfer {symbol} test={test_period}: {rows.size} rows, trained on {todo}")
        del ds
        gc.collect()
    return skips


# ---------------------------------------------------------------------------
# Stage 3: shift
# ---------------------------------------------------------------------------


def _day_sums(ts_ms: np.ndarray, **cols: np.ndarray) -> dict:
    days, inv = np.unique(ts_ms // MS_PER_DAY, return_inverse=True)
    out = {"day": days.tolist(), "n": np.bincount(inv).tolist()}
    out.update({k: np.bincount(inv, weights=v).tolist() for k, v in cols.items()})
    return out


def shift_stage(cache: Path, symbol: str, periods: list[str],
                domain_rounds: int = DOMAIN_ROUNDS) -> None:
    """Domain classifier, per-feature shift and attribution for every period pair i < j.

    The classifier is trained on train-day samples and only ever applied to
    test-day samples, so the AUC and the weights are out of sample. The
    attribution is for the ladder of the earlier period scored forward.
    """
    samples: dict[str, dict] = {}

    def sample(p: str) -> dict:
        if p not in samples:
            with np.load(sample_path(cache, symbol, p)) as z:
                samples[p] = {k: z[k] for k in z.files}
        return samples[p]

    have = [p for p in periods if sample_path(cache, symbol, p).exists()
            and ladder_path(cache, symbol, p).exists()]
    for a, src in enumerate(have):
        for tgt in have[a + 1:]:
            path = shift_path(cache, symbol, src, tgt)
            if path.exists():
                continue
            s, t = sample(src), sample(tgt)
            Xs_fit, Xt_fit = equal_size(s["X_train"], t["X_train"], seed=0)
            clf = fit_domain_classifier(Xs_fit, Xt_fit, rounds=domain_rounds)
            auc = domain_auc(clf, *equal_size(s["X_test"], t["X_test"], seed=1))
            w = density_ratio(clf.predict(s["X_test"]), clf.n_src, clf.n_tgt)
            ladder = Ladder.load(ladder_path(cache, symbol, src))
            attribution = {}
            for rung in ATTRIBUTION_RUNGS:
                model = getattr(ladder, rung)
                loss_s = log_loss_bits(s["y_test"], model.predict(s["X_test"]))
                loss_t = log_loss_bits(t["y_test"], model.predict(t["X_test"]))
                att = reweighting_attribution(loss_s, w, loss_t)
                att["src_days"] = _day_sums(s["ts_test"], loss=loss_s, w=w, w_loss=w * loss_s)
                att["tgt_days"] = _day_sums(t["ts_test"], loss=loss_t)
                attribution[rung] = att
            _write_json(path, {
                "symbol": symbol, "source": src, "target": tgt, "auc": auc,
                "n_fit_per_period": clf.n_src, "n_src_eval": int(s["X_test"].shape[0]),
                "n_tgt_eval": int(t["X_test"].shape[0]),
                "features": feature_shift(Xs_fit, Xt_fit, FEATURE_NAMES),
                "domain_gain": dict(zip(FEATURE_NAMES, clf.gain_importance().tolist(),
                                        strict=True)),
                "attribution": attribution,
            })
            _log(f"shift {symbol} {src} vs {tgt}: AUC {auc:.3f}, "
                 f"ESS share {attribution['gbm_all']['ess_share']:.2f}")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_q10(
    root: Path, out_dir: Path, *, symbols: list[str] | None = None,
    periods: list[str] | None = None, cache: Path | None = None,
    stages: tuple[str, ...] = STAGES, linear_order: int = LINEAR_ORDER,
    train_cap: int = TRAIN_CAP, gbm_rounds: int | None = None, sample_cap: int = SAMPLE_CAP,
    domain_rounds: int = DOMAIN_ROUNDS, n_boot: int = N_BOOT, seed: int = 0,
) -> dict | None:
    """Run the requested stages; returns the report dict if the report stage ran.

    The first period is the source, the second the one-month yardstick, the
    last the headline target.
    """
    symbols = list(symbols or SYMBOLS)
    periods = list(periods or PERIODS)
    cache = cache or root / "ml_cache"
    skips: list[dict] = []
    for symbol in symbols:
        if "fit" in stages:
            skips += fit_stage(root, cache, symbol, periods, linear_order=linear_order,
                               train_cap=train_cap, gbm_rounds=gbm_rounds, sample_cap=sample_cap)
        if "transfer" in stages:
            skips += transfer_stage(root, cache, symbol, periods)
        if "shift" in stages:
            shift_stage(cache, symbol, periods, domain_rounds=domain_rounds)
    for s in skips:
        _log(f"skipped {s['symbol']} {s['period']}: {s['reason']}")
    if "report" not in stages:
        return None
    result = write_report(cache, out_dir, symbols, periods, n_boot=n_boot, seed=seed)
    _log(result["verdict"]["text"])
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Q10: staleness of a 2023 sign model, and its cause")
    p.add_argument("--root", type=Path, default=Path("data"))
    p.add_argument("--out", type=Path, default=Path("results"))
    p.add_argument("--cache", type=Path, default=None,
                   help="cache directory (default <root>/ml_cache, shared with Q9's ladders)")
    p.add_argument("--symbols", nargs="+", default=list(SYMBOLS))
    p.add_argument("--periods", nargs="+", default=list(PERIODS),
                   help="chronological; first = source, second = yardstick, last = target")
    p.add_argument("--stages", nargs="+", choices=STAGES, default=list(STAGES))
    p.add_argument("--train-cap", type=int, default=TRAIN_CAP)
    p.add_argument("--gbm-rounds", type=int, default=None)
    p.add_argument("--linear-order", type=int, default=LINEAR_ORDER)
    p.add_argument("--sample-cap", type=int, default=SAMPLE_CAP)
    p.add_argument("--n-boot", type=int, default=N_BOOT)
    args = p.parse_args(argv)
    reduced = (args.train_cap != TRAIN_CAP or args.gbm_rounds is not None
               or args.linear_order != LINEAR_ORDER)
    if reduced and args.cache is None:
        # Ladders are cached by symbol and period only; a reduced fit written to the
        # shared cache would silently be reused by Q9 and by later full runs.
        p.error("non-default --train-cap/--gbm-rounds/--linear-order need an explicit --cache "
                "so reduced ladders never land in the shared cache")
    return args


if __name__ == "__main__":
    a = _parse_args()
    run_q10(a.root, a.out, symbols=a.symbols, periods=a.periods, cache=a.cache,
            stages=tuple(a.stages), linear_order=a.linear_order, train_cap=a.train_cap,
            gbm_rounds=a.gbm_rounds, sample_cap=a.sample_cap, n_boot=a.n_boot)
