"""Constants and helpers shared by the Q6b computation and its report writer.

Lives in its own module so `q6b_kernel_sensitivity` (which calls the report
writer) and `q6b_report` (which needs these values) do not import each other.
"""
from __future__ import annotations

import numpy as np

N_BINS = 48  # intraday_rate_profile bin count, matches Q6

# Runtime cap on events per sum-of-exponentials Hawkes MLE fit. Fits at K=1,2,3
# cost more per event than Q6's K=1 fit (K recursions per evaluation, dimension
# 1+2K instead of 3), so Q6's 250k-event cap is kept (see MAX_FIT_EVENTS in
# q6_endogeneity.py for the sampling-noise argument).
MAX_FIT_EVENTS = 250_000

# Deseasonalization bin width in business-time seconds: one day (86400s) split
# into the same N_BINS=48 bins as intraday_rate_profile. A slow kernel
# component at or beyond this timescale is what residual bin-scale seasonality
# would produce, since the profile cannot resolve structure finer than a bin.
DESEASON_BIN_WIDTH_S = 86_400.0 / N_BINS

# A symbol whose median 1/beta_slow (at K=2) exceeds this multiple of the
# deseasonalization bin width is flagged "drift-suspect": the slow component
# decays far slower than deseasonalization could resolve, so it is as
# consistent with residual baseline drift as with a long-memory kernel. A
# flag for caution, not a verdict (see the module docstring).
DRIFT_SUSPECT_MULTIPLIER = 10.0

# A fitted n-hat at or above this sits on the stationarity boundary (n = 1), where
# mu and alpha are only weakly identified (`fit_hawkes_exp` docstring). Such values
# are flagged in the tables.
BOUNDARY_N_HAT = 0.9999

DRIFT_VERDICTS: tuple[str, ...] = ("drift", "long_memory_candidate", "inconclusive")

# Why a symbol's verdict is 'inconclusive' (derived here from the control's
# outputs; `_drift_verdict` itself only returns the bare label).
INCONCLUSIVE_REASONS: tuple[str, ...] = ("no_rise", "k2_insignificant", "mixed")


def _is_finite_number(value: float | None) -> bool:
    return value is not None and bool(np.isfinite(value))
