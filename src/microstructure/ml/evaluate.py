"""Metrics and dependent-data inference for probabilistic sign forecasts.

Accuracy alone hides most of what a long-memory predictor adds, because a
forecast of 0.51 and one of 0.90 both count as one correct call. Log loss
scores the probability itself; it is reported in bits and as a skill score
against a reference forecast.

Trades are strongly autocorrelated, so events are not independent draws.
Confidence intervals resample whole UTC days, and model comparisons are
paired: the same resampled days are used for both models.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import roc_auc_score

MS_PER_DAY = 86_400_000


def log_loss_bits(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Per-event log loss in bits; 1.0 is a coin flip, 0.0 is certainty."""
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log2(p) + (1 - y) * np.log2(1 - p))


def mcc(y: np.ndarray, p: np.ndarray) -> float:
    pred = p >= 0.5
    yb = y.astype(bool)
    tp = float((pred & yb).sum())
    tn = float((~pred & ~yb).sum())
    fp = float((pred & ~yb).sum())
    fn = float((~pred & yb).sum())
    den = np.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return float((tp * tn - fp * fn) / den) if den > 0 else 0.0


@dataclass(frozen=True)
class Scores:
    n: int
    accuracy: float
    log_loss_bits: float
    auc: float
    mcc: float

    def as_dict(self) -> dict:
        return {"n": self.n, "accuracy": self.accuracy, "log_loss_bits": self.log_loss_bits,
                "auc": self.auc, "mcc": self.mcc}


def score(y: np.ndarray, p: np.ndarray) -> Scores:
    return Scores(
        n=int(y.size),
        accuracy=float(((p >= 0.5) == (y > 0.5)).mean()),
        log_loss_bits=float(log_loss_bits(y, p).mean()),
        auc=float(roc_auc_score(y, p)) if 0 < y.mean() < 1 else float("nan"),
        mcc=mcc(y, p),
    )


def skill(loss: float, reference_loss: float) -> float:
    """Fraction of the reference forecast's log loss removed (1 = perfect)."""
    return 1.0 - loss / reference_loss


@dataclass(frozen=True)
class PairedCI:
    estimate: float
    lo: float
    hi: float
    n_days: int

    def as_dict(self) -> dict:
        return {"estimate": self.estimate, "ci95": [self.lo, self.hi], "n_days": self.n_days}


def day_block_ci(
    values_a: np.ndarray, values_b: np.ndarray | None, ts_ms: np.ndarray,
    n_boot: int = 2000, seed: int = 0,
) -> PairedCI:
    """95% CI for mean(values_a) - mean(values_b), resampling whole UTC days.

    `values_*` are per-event quantities (a 0/1 correct flag or a log loss).
    With `values_b=None` the interval is for mean(values_a) itself. The
    statistic on each resample is a ratio of sums, so days keep their own
    event counts.
    """
    d = values_a if values_b is None else values_a - values_b
    day = ts_ms // MS_PER_DAY
    _, inv = np.unique(day, return_inverse=True)
    sums = np.bincount(inv, weights=d)
    counts = np.bincount(inv).astype(np.float64)
    k = sums.size
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, k, size=(n_boot, k))
    stats = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return PairedCI(float(sums.sum() / counts.sum()), float(lo), float(hi), int(k))
