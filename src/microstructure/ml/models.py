"""The two learned models: L2 logistic regression and gradient-boosted trees.

Both are fitted on a random subsample of scoreable training rows (labels are
one step ahead, so rows do not overlap and need not be contiguous). Fitted
models are small picklable objects so a model trained in one month can be
scored in another.
"""
from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
from sklearn.linear_model import LogisticRegression

LGB_PARAMS = {
    "objective": "binary",
    "learning_rate": 0.1,
    "num_leaves": 63,
    "min_data_in_leaf": 500,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "max_bin": 63,
    "verbose": -1,
    "num_threads": 4,
    "seed": 0,
}
LGB_MAX_ROUNDS = 400
LGB_PATIENCE = 30


def subsample(rows: np.ndarray, cap: int, seed: int) -> np.ndarray:
    if rows.size <= cap:
        return rows
    return np.sort(np.random.default_rng(seed).choice(rows, size=cap, replace=False))


@dataclass(frozen=True)
class LogisticModel:
    """Standardization constants come from the training rows only."""

    mean: np.ndarray
    scale: np.ndarray
    coef: np.ndarray       # per standardized feature
    intercept: float

    def predict(self, X: np.ndarray) -> np.ndarray:
        z = ((X - self.mean) / self.scale) @ self.coef + self.intercept
        return 1.0 / (1.0 + np.exp(-z))


def fit_logistic(X: np.ndarray, y: np.ndarray) -> LogisticModel:
    mean = X.mean(axis=0, dtype=np.float64)
    scale = X.std(axis=0, dtype=np.float64)
    scale = np.where(scale > 0, scale, 1.0)
    clf = LogisticRegression(C=1.0, max_iter=300).fit((X - mean) / scale, y)
    return LogisticModel(mean=mean, scale=scale, coef=clf.coef_[0].astype(np.float64),
                         intercept=float(clf.intercept_[0]))


@dataclass(frozen=True)
class GBMModel:
    model_str: str
    best_iteration: int

    def booster(self) -> lgb.Booster:
        return lgb.Booster(model_str=self.model_str)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.booster().predict(X, num_iteration=self.best_iteration)

    def gain_importance(self) -> np.ndarray:
        g = self.booster().feature_importance("gain", iteration=self.best_iteration)
        return g / g.sum() if g.sum() > 0 else g


def fit_gbm(
    X: np.ndarray, y: np.ndarray, X_valid: np.ndarray, y_valid: np.ndarray,
    params: dict | None = None, max_rounds: int = LGB_MAX_ROUNDS,
) -> GBMModel:
    """LightGBM; the round count is chosen by early stopping on the validation days."""
    p = {**LGB_PARAMS, **(params or {})}
    dtrain = lgb.Dataset(X, label=y)
    dvalid = lgb.Dataset(X_valid, label=y_valid, reference=dtrain)
    booster = lgb.train(
        p, dtrain, num_boost_round=max_rounds, valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(LGB_PATIENCE, verbose=False)],
    )
    return GBMModel(model_str=booster.model_to_string(),
                    best_iteration=int(booster.best_iteration or max_rounds))
