"""Theory-derived baselines for next-sign prediction.

A learned model is only interesting for what it adds over what the measured
sign autocorrelation already implies, so these are the bar, not 50%.

* persistence: P(next = last) = the training-sample repeat frequency.
* linear predictor: the best linear forecast of s[i] from s[i-1..i-p] given
  the autocorrelation C(k). Its weights solve the Yule-Walker equations
  sum_k a_k C(|j-k|) = C(j), j = 1..p (a Toeplitz system). For a +-1 series
  E[s | past] = 2 P(s=+1 | past) - 1, so the forecast maps to a probability
  as (1 + forecast) / 2.
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import solve_toeplitz
from scipy.signal import lfilter

from microstructure.estimators.acf import sign_acf

_EPS = 1e-4


def persistence_proba(signs: np.ndarray, p_repeat: float) -> np.ndarray:
    """P(sign[i] = +1) from sign[i-1] alone; row 0 gets 0.5."""
    p = np.full(signs.size, 0.5)
    p[1:] = np.where(signs[:-1] > 0, p_repeat, 1.0 - p_repeat)
    return p


def repeat_probability(signs: np.ndarray) -> float:
    return float((signs[1:] == signs[:-1]).mean())


def yule_walker_weights(acf: np.ndarray, order: int) -> np.ndarray:
    """AR(order) weights a_1..a_order from autocorrelations acf[0..order]."""
    if acf.size < order + 1:
        raise ValueError(f"need acf up to lag {order}; got {acf.size - 1}")
    return solve_toeplitz(acf[:order], acf[1 : order + 1])


def fit_linear_predictor(train_signs: np.ndarray, order: int) -> tuple[np.ndarray, float]:
    """(weights, mean) of the Yule-Walker predictor fitted on training signs."""
    mean = float(train_signs.mean())
    return yule_walker_weights(sign_acf(train_signs, order), order), mean


def linear_predictor_proba(signs: np.ndarray, weights: np.ndarray, mean: float) -> np.ndarray:
    """P(sign[i] = +1) from sign[i-1], ..., sign[i-order]. Causal by construction:
    the filter has a zero coefficient on the current sample."""
    x = signs.astype(np.float64) - mean
    b = np.concatenate([[0.0], weights])
    forecast = lfilter(b, [1.0], x) + mean
    return np.clip((1.0 + forecast) / 2.0, _EPS, 1.0 - _EPS)
