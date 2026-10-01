"""Constants and pure helpers shared by the Q8 computation and its report writer.

Lives in its own module so `q8_regimes` (which calls the report writer) and
`q8_report` (which needs these values) do not import each other.
"""
from __future__ import annotations

import re

import numpy as np

# Recomputed vs. stored slope/intercept/r2 are flagged if they differ by more
# than this absolute amount. Both sides use `np.polyfit(..., deg=1)` on the
# same records, so they should match exactly; the tolerance only has to
# absorb float noise while still catching a different symbol set, a stale
# json or code drift.
REGRESSION_MISMATCH_TOL = 1e-6

# γ-invariance verdict threshold: a regime's γ-vs-activity regression is
# "flat" (no detectable activity dependence) when its R² is below this, the
# same informal bar Q4 uses for a weak/no relationship.
GAMMA_FLAT_R2_THRESHOLD = 0.05

# A flip-law slope counts toward a sign verdict only when it is at least this
# many standard errors from zero. A slope inside that band has no reliable
# sign, so "same sign as the baseline" would carry no information.
FLIP_SLOPE_MIN_SE = 2.0

# Kernel-mode split for Q6's single-exponential Hawkes fits. A fitted decay
# rate above this (1/beta < 0.1 business-time seconds) means the MLE locked
# onto the fast component of a multi-timescale kernel, which captures only
# part of the excitation and so understates alpha. A regime whose fast-mode
# share moves this far from the baseline's has an alpha median that is not
# comparable to the baseline's as a measure of endogeneity.
FAST_MODE_BETA = 10.0
FAST_MODE_SHIFT_FLAG = 0.2

# Drop-one-out: the spread of R² across single-symbol removals, as a fraction of
# the full-sample R², at or above which the break's strength is called
# outlier-sensitive.
LOO_R2_SWING_LARGE = 0.25


def _chrono_key(label: str) -> tuple:
    """Sort key for a regime label: (YYYY, MM) parsed from a leading YYYY-MM
    prefix, else the label itself (pushed after any parsed labels) so an
    unexpected label format degrades to alphabetical rather than crashing.
    """
    m = re.match(r"^(\d{4})-(\d{2})", label)
    if m:
        return (0, int(m.group(1)), int(m.group(2)), label)
    return (1, 0, 0, label)


def _ols_with_intercept(x: np.ndarray, y: np.ndarray) -> dict | None:
    """OLS slope/intercept/stderr/R²/n via np.polyfit, with intercept.

    Same as q4_cross_section._ols_with_intercept and q6_endogeneity's helper,
    reimplemented rather than imported so the cross-check stays independent of
    the upstream implementation.
    Returns None if fewer than 3 points or x has zero variance.
    """
    if x.size < 3 or np.ptp(x) == 0.0:
        return None
    (slope, intercept), cov = np.polyfit(x, y, 1, cov=True)
    yhat = slope * x + intercept
    resid = y - yhat
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "stderr": float(np.sqrt(cov[0, 0])),
        "r2": r2,
        "n": int(x.size),
    }


def _average_ranks(values: np.ndarray) -> np.ndarray:
    """Rank `values` ascending, tied values getting the average of their ranks (1-indexed).

    E.g. [10, 20, 20, 30] -> ranks [1.0, 2.5, 2.5, 4.0] (equivalent to
    scipy.stats.rankdata(method="average"), reimplemented to avoid scipy).
    """
    order = np.argsort(values, kind="mergesort")
    sorted_vals = values[order]
    n = values.size
    ranks = np.empty(n, dtype=np.float64)

    i = 0
    while i < n:
        j = i
        while j + 1 < n and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        # Positions i..j (0-indexed) are tied; average 1-indexed rank.
        avg_rank = (i + 1 + j + 1) / 2.0
        ranks[order[i : j + 1]] = avg_rank
        i = j + 1

    return ranks


def spearman_corr(x: np.ndarray, y: np.ndarray) -> float | None:
    """Spearman rank correlation between `x` and `y` (equal length, no scipy).

    Computed as the Pearson correlation of the average-rank-transformed
    arrays, matching scipy.stats.spearmanr. Returns None when fewer than 2 points, or either array
    has zero rank variance (a constant array has undefined correlation).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size != y.size:
        raise ValueError(f"length mismatch: {x.size} vs {y.size}")
    if x.size < 2:
        return None
    rx = _average_ranks(x)
    ry = _average_ranks(y)
    if np.std(rx) == 0.0 or np.std(ry) == 0.0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])
