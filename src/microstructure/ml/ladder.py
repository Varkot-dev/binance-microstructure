"""The model ladder for next-sign prediction, fitted on one symbol-month.

Rungs, in increasing order of what they are allowed to use:

  majority     the training buy share
  persistence  the last sign only
  linear       the last LINEAR_ORDER signs through the Yule-Walker filter
               implied by the measured sign autocorrelation (the theory rung)
  logit_signs  logistic regression on sign-history features
  gbm_signs    boosted trees on the same sign-history features
  logit_all    logistic regression on signs + sizes, timing and price moves
  gbm_all      boosted trees on all features

`gbm_signs - linear` is what nonlinearity adds on the same information;
`gbm_all - gbm_signs` is what trade sizes, timing and price moves add.
"""
from __future__ import annotations

import hashlib
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from microstructure.ml.baselines import (
    fit_linear_predictor,
    linear_predictor_proba,
    persistence_proba,
    repeat_probability,
)
from microstructure.ml.dataset import SignDataset
from microstructure.ml.evaluate import MS_PER_DAY, log_loss_bits
from microstructure.ml.features import FEATURE_NAMES, SIGN_FEATURES
from microstructure.ml.models import GBMModel, LogisticModel, fit_gbm, fit_logistic, subsample

LINEAR_ORDER = 1000
TRAIN_CAP = 2_000_000
VALID_CAP = 500_000
RUNGS = ("majority", "persistence", "linear", "logit_signs", "gbm_signs", "logit_all", "gbm_all")
SIGN_IDX = [FEATURE_NAMES.index(f) for f in SIGN_FEATURES]
# Key under which every cache entry computed from a saved ladder records which one.
FINGERPRINT_KEY = "ladder_sha256"


def ladder_fingerprint(path: Path) -> str | None:
    """sha256 of the saved ladder file, or None if there is none.

    Ladders are cached by symbol and period only, so a refit replaces the file
    in place. Everything computed from a ladder stores this next to its numbers
    and is recomputed when it no longer matches the file on disk.
    """
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def same_ladder(record: dict | None, path: Path) -> bool:
    """True if a cache record was computed with the ladder now saved at `path`.

    A record without a fingerprint (written before fingerprints existed) and a
    missing ladder both count as a mismatch.
    """
    fp = ladder_fingerprint(path)
    return fp is not None and record is not None and record.get(FINGERPRINT_KEY) == fp


@dataclass(frozen=True)
class Ladder:
    symbol: str
    period: str
    n_train_rows: int
    buy_share: float
    p_repeat: float
    lin_weights: np.ndarray
    lin_mean: float
    logit_signs: LogisticModel
    logit_all: LogisticModel
    gbm_signs: GBMModel
    gbm_all: GBMModel

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: Path) -> Ladder:
        with path.open("rb") as f:
            return pickle.load(f)


def fit_ladder(ds: SignDataset, linear_order: int = LINEAR_ORDER,
               train_cap: int = TRAIN_CAP, gbm_rounds: int | None = None) -> Ladder:
    tr = subsample(ds.rows(ds.train), train_cap, seed=0)
    va = subsample(ds.rows(ds.valid), VALID_CAP, seed=1)
    train_signs = ds.signs[ds.train]
    w, m = fit_linear_predictor(train_signs, linear_order)
    Xtr, ytr, Xva, yva = ds.X[tr], ds.y[tr], ds.X[va], ds.y[va]
    kw = {} if gbm_rounds is None else {"max_rounds": gbm_rounds}
    return Ladder(
        symbol=ds.symbol, period=ds.period, n_train_rows=int(tr.size),
        buy_share=float(ds.y[ds.rows(ds.train)].mean()),
        p_repeat=repeat_probability(train_signs),
        lin_weights=w, lin_mean=m,
        logit_signs=fit_logistic(Xtr[:, SIGN_IDX], ytr),
        logit_all=fit_logistic(Xtr, ytr),
        gbm_signs=fit_gbm(Xtr[:, SIGN_IDX], ytr, Xva[:, SIGN_IDX], yva, **kw),
        gbm_all=fit_gbm(Xtr, ytr, Xva, yva, **kw),
    )


def predict_ladder(ladder: Ladder, ds: SignDataset, rows: np.ndarray) -> dict[str, np.ndarray]:
    """P(next sign = +1) from every rung, on the given rows of any dataset."""
    X = ds.X[rows]
    return {
        "majority": np.full(rows.size, ladder.buy_share),
        "persistence": persistence_proba(ds.signs, ladder.p_repeat)[rows],
        "linear": linear_predictor_proba(ds.signs, ladder.lin_weights, ladder.lin_mean)[rows],
        "logit_signs": ladder.logit_signs.predict(X[:, SIGN_IDX]),
        "gbm_signs": ladder.gbm_signs.predict(X[:, SIGN_IDX]),
        "logit_all": ladder.logit_all.predict(X),
        "gbm_all": ladder.gbm_all.predict(X),
    }


def daily_sums(y: np.ndarray, ts_ms: np.ndarray, probs: dict[str, np.ndarray]) -> dict:
    """Per-UTC-day event counts and, per rung, sums of correct calls and log loss.

    Everything the day-block bootstrap needs, small enough to keep as JSON, so
    intervals can be recomputed or pooled across symbols without the raw data.
    """
    day = ts_ms // MS_PER_DAY
    days, inv = np.unique(day, return_inverse=True)
    out: dict = {"day": days.tolist(), "n": np.bincount(inv).tolist()}
    for name, p in probs.items():
        correct = ((p >= 0.5) == (y > 0.5)).astype(np.float64)
        out[name] = {
            "correct": np.bincount(inv, weights=correct).tolist(),
            "loss": np.bincount(inv, weights=log_loss_bits(y, p)).tolist(),
        }
    return out
