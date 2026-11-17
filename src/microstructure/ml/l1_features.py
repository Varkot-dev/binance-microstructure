"""Causal, scale-free top-of-book features, one row per aggressor trade event.

Row i describes the best bid and ask as they stood strictly before trade
event i (the `events_with_prior_mid` convention), so it can be used to predict
anything that happens from event i onward. Inputs are per-event arrays of that
prior quote plus `ofi_cum`, the running sum of order-flow imbalance over all
quote updates up to and including that prior quote. Row i therefore reads
quotes with a timestamp strictly below ts[i] and nothing else;
`tests/ml/test_l1_features.py` checks this by corrupting the future.

All columns are dimensionless: ratios of sizes, prices in ticks, order flow in
units of trailing depth, returns in units of trailing volatility.

A note on the microprice. With microprice = (ask * bid_qty + bid * ask_qty) /
(bid_qty + ask_qty), the quantity (microprice - mid) / spread is identically
queue_imbalance / 2, so measured in spreads it would duplicate the queue
imbalance column. I measure it in ticks instead, which makes it the product of
imbalance and spread width: the same imbalance means a larger expected
displacement when the spread is wide.
"""
from __future__ import annotations

from collections.abc import Iterator

import numpy as np

from microstructure.estimators.ofi import ofi_events
from microstructure.ml.features import SLOW_HALF_LIFE, ewma

OFI_WINDOWS = (1, 5, 20, 100)
MIDRET_WINDOWS = (10, 50, 200)
SPREAD_CAP_TICKS = 20.0
RETURN_CLIP = 10.0

L1_FEATURES = (
    ("queue_imb", "spread_ticks", "one_tick", "micro_dev_ticks")
    + tuple(f"ofi{k}" for k in OFI_WINDOWS)
    + tuple(f"midret{k}" for k in MIDRET_WINDOWS)
)


def estimate_tick(prices: np.ndarray) -> float:
    """Smallest positive increment between distinct observed prices.

    Rounded to 6 significant digits so float noise in the subtraction
    (17.385 - 17.384 = 0.000999999...) does not survive into the estimate.
    """
    u = np.unique(np.asarray(prices, dtype=np.float64))
    if u.size < 2:
        raise ValueError("need at least two distinct prices to estimate the tick")
    return float(f"{np.diff(u).min():.6g}")


def cumulative_quote_ofi(
    bid_p: np.ndarray, bid_q: np.ndarray, ask_p: np.ndarray, ask_q: np.ndarray
) -> np.ndarray:
    """c[j] = sum of the Cont-Kukanov-Stoikov OFI of quote updates 1..j; c[0] = 0.

    The OFI of quote flow between two instants is then a difference of two
    entries, which lets a trade-to-quote asof join carry it like any column.
    """
    c = np.zeros(bid_p.size)
    if bid_p.size > 1:
        np.cumsum(ofi_events(bid_p, bid_q, ask_p, ask_q), out=c[1:])
    return c


def _lagged_diff(x: np.ndarray, k: int) -> np.ndarray:
    """x[i] - x[i-k]; the first k rows are 0 (no history yet)."""
    out = np.zeros(x.size)
    out[k:] = x[k:] - x[:-k]
    return out


def _iter_l1_features(
    bid_p: np.ndarray, bid_q: np.ndarray, ask_p: np.ndarray, ask_q: np.ndarray,
    ofi_cum: np.ndarray, tick: float,
) -> Iterator[tuple[str, np.ndarray]]:
    n = bid_p.size
    if not (bid_q.size == ask_p.size == ask_q.size == ofi_cum.size == n):
        raise ValueError("all inputs must have the same length")
    if n < 3:
        raise ValueError("need at least 3 events")
    if tick <= 0:
        raise ValueError("tick must be positive")

    depth = bid_q + ask_q
    imb = (bid_q - ask_q) / depth
    spread = np.round((ask_p - bid_p) / tick)
    yield "queue_imb", imb
    yield "spread_ticks", np.minimum(spread, SPREAD_CAP_TICKS)
    yield "one_tick", (spread <= 1.0).astype(np.float64)
    yield "micro_dev_ticks", 0.5 * imb * np.minimum(spread, SPREAD_CAP_TICKS)

    # Quote flow since the quote that preceded trade i-k, in units of the
    # trailing average size at one side of the book. It includes the book's
    # reaction to trades i-k..i-1, all of which precede trade i. The signed
    # log keeps the heavy tails from dominating the logistic fit.
    mean_side_depth = ewma(0.5 * depth, SLOW_HALF_LIFE)
    for k in OFI_WINDOWS:
        z = _lagged_diff(ofi_cum, k) / mean_side_depth
        yield f"ofi{k}", np.sign(z) * np.log1p(np.abs(z))

    # Mid return over the last k events, scaled by the trailing volatility of
    # one-event mid changes so the column means the same thing across symbols.
    lm = np.log(0.5 * (bid_p + ask_p))
    r1 = _lagged_diff(lm, 1)
    vol = np.sqrt(ewma(r1 * r1, SLOW_HALF_LIFE))
    for k in MIDRET_WINDOWS:
        with np.errstate(divide="ignore", invalid="ignore"):
            z = _lagged_diff(lm, k) / (vol * np.sqrt(k))
        z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
        yield f"midret{k}", np.clip(z, -RETURN_CLIP, RETURN_CLIP)


def build_l1_features(
    bid_p: np.ndarray, bid_q: np.ndarray, ask_p: np.ndarray, ask_q: np.ndarray,
    ofi_cum: np.ndarray, tick: float,
) -> dict[str, np.ndarray]:
    """Feature columns keyed by L1_FEATURES; row i reads the quote before event i.

    `bid_p`, `bid_q`, `ask_p`, `ask_q` are the best quote prevailing strictly
    before each event, `ofi_cum` is `cumulative_quote_ofi` evaluated at that
    same quote, and `tick` is the price increment (estimated on training data
    only). Rows before `microstructure.ml.features.WARMUP` should be dropped.
    """
    return dict(_iter_l1_features(bid_p, bid_q, ask_p, ask_q, ofi_cum, tick))


def fill_l1_columns(
    out: np.ndarray, rows: np.ndarray, col_offset: int,
    bid_p: np.ndarray, bid_q: np.ndarray, ask_p: np.ndarray, ask_q: np.ndarray,
    ofi_cum: np.ndarray, tick: float,
) -> None:
    """Write the L1 columns for `rows` into out[:, col_offset:], one at a time.

    A two-week window of a busy symbol has tens of millions of events; keeping
    only the sampled rows of each column avoids holding the full matrix.
    """
    for name, col in _iter_l1_features(bid_p, bid_q, ask_p, ask_q, ofi_cum, tick):
        out[:, col_offset + L1_FEATURES.index(name)] = col[rows]
