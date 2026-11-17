"""One symbol-month of aggressor events as a supervised dataset with day splits.

A month is split on whole UTC days: the first `train_days` train the model,
the next `valid_days` pick the boosting round count, one day is discarded as
an embargo, and the rest are the test block. Whole-day boundaries plus the
embargo keep the long-memory state of the training rows (EWMA features with a
1024-event half-life) from straddling into the test block.

Scoring mask. Events that share a millisecond with the previous event are
excluded from scoring. `to_aggressor_events` orders same-millisecond events
by (ts, sign), so within a tied millisecond a sell always precedes a buy; the
"next sign" there is fixed by the sort, not by the market. Such rows still
feed the features of later rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from microstructure.ml.evaluate import MS_PER_DAY
from microstructure.ml.features import WARMUP, build_feature_matrix
from microstructure.signals.load import load_events

TRAIN_DAYS = 20
VALID_DAYS = 2
EMBARGO_DAYS = 1


@dataclass(frozen=True)
class SignDataset:
    symbol: str
    period: str
    ts_ms: np.ndarray       # int64, all events
    signs: np.ndarray       # int8, all events
    X: np.ndarray           # float32 [n, len(FEATURE_NAMES)]
    y: np.ndarray           # float32, 1.0 where sign == +1
    scoreable: np.ndarray   # bool: past warm-up and not tied with the previous ms
    train: np.ndarray       # bool masks over events (day-based)
    valid: np.ndarray
    test: np.ndarray
    tie_share: float

    def rows(self, mask: np.ndarray) -> np.ndarray:
        return np.flatnonzero(mask & self.scoreable)


def split_masks(ts_ms: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    day = ts_ms // MS_PER_DAY
    d = day - day[0]
    train = d < TRAIN_DAYS
    valid = (d >= TRAIN_DAYS) & (d < TRAIN_DAYS + VALID_DAYS)
    test = d >= TRAIN_DAYS + VALID_DAYS + EMBARGO_DAYS
    return train, valid, test


def from_events(symbol: str, period: str, ts_ms, signs, qty, price, n_prints) -> SignDataset:
    X = build_feature_matrix(ts_ms, signs, qty, price, n_prints)
    tied = np.zeros(signs.size, dtype=bool)
    tied[1:] = ts_ms[1:] == ts_ms[:-1]
    scoreable = ~tied
    scoreable[:WARMUP] = False
    train, valid, test = split_masks(ts_ms)
    return SignDataset(
        symbol=symbol, period=period, ts_ms=ts_ms, signs=signs, X=X,
        y=(signs > 0).astype(np.float32), scoreable=scoreable,
        train=train, valid=valid, test=test, tie_share=float(tied.mean()),
    )


def load_sign_dataset(root: Path, symbol: str, period: str) -> SignDataset:
    ev = load_events(root, symbol, [period])
    return from_events(
        symbol, period,
        ev["ts"].dt.epoch("ms").to_numpy(),
        ev["sign"].to_numpy(),
        ev["qty"].to_numpy(),
        ev["price"].to_numpy(),
        ev["n_prints"].to_numpy(),
    )
