"""Causal, scale-free features for next-trade-sign prediction from trades alone.

Row i describes the market as it stood after event i-1 and before event i, so
it can be used to predict event i. Every column is built in two steps: a
"state after event j" array that reads events 0..j only, then a shift by one
row. Nothing about event i (its sign, size, price or even its arrival time)
enters row i; `tests/ml/test_features.py` checks this by corrupting the
future and asserting earlier rows do not move.

All features are dimensionless (signs, ratios, logs of ratios to a trailing
average), so one model can be applied across symbols and years whose price,
lot size and trade rate differ by orders of magnitude.

Only trade data is used because Binance publishes `bookTicker` dumps for 2023
only; a model that must be scored in 2024-2026 cannot depend on quotes.
"""
from __future__ import annotations

from collections.abc import Iterator

import numpy as np
from scipy.signal import lfilter

SIGN_LAGS = (1, 2, 3, 4, 5)
SIGN_HALF_LIVES = (4, 16, 64, 256, 1024)
RETURN_WINDOWS = (16, 64)
SLOW_HALF_LIFE = 1024
FAST_HALF_LIFE = 16
RUN_CAP = 64
# Rows before this index have EWMA states still dominated by initialization.
WARMUP = 5 * SLOW_HALF_LIFE

SIGN_FEATURES = tuple(f"sign_lag{k}" for k in SIGN_LAGS) + tuple(
    f"sign_ewma{h}" for h in SIGN_HALF_LIVES
) + ("run_length",)
CONTEXT_FEATURES = (
    "rel_log_qty", "signed_rel_log_qty", "log_n_prints",
    "rel_log_dt", "burst", "same_ts",
    "tick_dir", "signed_tick_dir",
) + tuple(f"ret{w}" for w in RETURN_WINDOWS)
FEATURE_NAMES = SIGN_FEATURES + CONTEXT_FEATURES


def ewma(x: np.ndarray, half_life: float) -> np.ndarray:
    """y[t] = a*x[t] + (1-a)*y[t-1], y[-1] = x[0], a = 1 - 2^(-1/half_life)."""
    a = 1.0 - 0.5 ** (1.0 / half_life)
    x = np.asarray(x, dtype=np.float64)
    zi = np.array([(1.0 - a) * x[0]])
    y, _ = lfilter([a], [1.0, -(1.0 - a)], x, zi=zi)
    return y


def _shift(state: np.ndarray, k: int = 1) -> np.ndarray:
    """Row i <- state[i-k]; the first k rows are NaN (no history yet)."""
    out = np.full(state.shape, np.nan)
    out[k:] = state[:-k]
    return out


def _run_length(signs: np.ndarray) -> np.ndarray:
    """Length of the run of identical signs ending at each event (>= 1)."""
    idx = np.arange(signs.size)
    change = np.empty(signs.size, dtype=bool)
    change[0] = True
    change[1:] = signs[1:] != signs[:-1]
    start = np.maximum.accumulate(np.where(change, idx, 0))
    return (idx - start + 1).astype(np.float64)


def _iter_features(
    ts_ms: np.ndarray, signs: np.ndarray, qty: np.ndarray, price: np.ndarray,
    n_prints: np.ndarray,
) -> Iterator[tuple[str, np.ndarray]]:
    """Yield (name, column) one at a time so callers never hold all columns
    in float64 at once (a busy month has tens of millions of events)."""
    n = signs.size
    if not (ts_ms.size == qty.size == price.size == n_prints.size == n):
        raise ValueError("all inputs must have the same length")
    if n < 3:
        raise ValueError("need at least 3 events")
    s = signs.astype(np.float64)

    for k in SIGN_LAGS:
        yield f"sign_lag{k}", _shift(s, k)
    for h in SIGN_HALF_LIVES:
        yield f"sign_ewma{h}", _shift(ewma(s, h))
    yield "run_length", _shift(s * np.log1p(np.minimum(_run_length(signs), RUN_CAP)))

    # Size of the last event relative to the trailing typical size. The slow
    # average is itself lagged one event so the ratio compares event j with
    # the history before j.
    lq = np.log(qty)
    lq_slow = ewma(lq, SLOW_HALF_LIFE)
    rel_q = np.empty(n)
    rel_q[0] = 0.0
    rel_q[1:] = lq[1:] - lq_slow[:-1]
    yield "rel_log_qty", _shift(rel_q)
    yield "signed_rel_log_qty", _shift(s * rel_q)
    yield "log_n_prints", _shift(np.log(n_prints.astype(np.float64)))

    # Gap that ENDED at event j (ts[j] - ts[j-1]); the gap to the event being
    # predicted is unknown before it arrives and is never used.
    dt = np.empty(n)
    dt[0] = 1.0
    dt[1:] = np.diff(ts_ms).astype(np.float64)
    ldt = np.log1p(dt)
    ldt_slow = ewma(ldt, SLOW_HALF_LIFE)
    rel_dt = np.empty(n)
    rel_dt[0] = 0.0
    rel_dt[1:] = ldt[1:] - ldt_slow[:-1]
    yield "rel_log_dt", _shift(rel_dt)
    yield "burst", _shift(ewma(ldt, FAST_HALF_LIFE) - ldt_slow)
    yield "same_ts", _shift((dt == 0.0).astype(np.float64))

    # Trade-price moves, in units of the trailing mean absolute move.
    lp = np.log(price)
    r = np.empty(n)
    r[0] = 0.0
    r[1:] = np.diff(lp)
    tick = np.sign(r)
    yield "tick_dir", _shift(tick)
    yield "signed_tick_dir", _shift(tick * s)
    scale = ewma(np.abs(r), SLOW_HALF_LIFE)
    scale_prev = np.empty(n)
    scale_prev[0] = np.nan
    scale_prev[1:] = scale[:-1]
    csum = np.cumsum(r)
    for w in RETURN_WINDOWS:
        ret = np.full(n, np.nan)
        ret[w:] = csum[w:] - csum[:-w]
        with np.errstate(divide="ignore", invalid="ignore"):
            z = ret / (scale_prev * np.sqrt(w))
        yield f"ret{w}", _shift(np.clip(np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0), -10, 10))


def build_features(
    ts_ms: np.ndarray, signs: np.ndarray, qty: np.ndarray, price: np.ndarray,
    n_prints: np.ndarray,
) -> dict[str, np.ndarray]:
    """Feature columns keyed by FEATURE_NAMES; row i predicts sign[i].

    Inputs are aggressor events sorted by time: int64 epoch-ms, +-1 signs,
    positive sizes and prices, and the print count of each event.
    Rows with index < WARMUP should be dropped by the caller.
    """
    return dict(_iter_features(ts_ms, signs, qty, price, n_prints))


def build_feature_matrix(
    ts_ms: np.ndarray, signs: np.ndarray, qty: np.ndarray, price: np.ndarray,
    n_prints: np.ndarray,
) -> np.ndarray:
    """float32 [n_events, len(FEATURE_NAMES)], columns in FEATURE_NAMES order."""
    X = np.empty((signs.size, len(FEATURE_NAMES)), dtype=np.float32)
    seen = []
    for name, col in _iter_features(ts_ms, signs, qty, price, n_prints):
        X[:, FEATURE_NAMES.index(name)] = col
        seen.append(name)
    if sorted(seen) != sorted(FEATURE_NAMES):
        raise RuntimeError("feature generator and FEATURE_NAMES disagree")
    return X


def feature_matrix(cols: dict[str, np.ndarray], names: tuple[str, ...]) -> np.ndarray:
    return np.column_stack([cols[k] for k in names]).astype(np.float32)
