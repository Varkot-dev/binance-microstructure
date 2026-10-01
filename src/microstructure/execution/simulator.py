"""Execution-cost replay simulator: pure functions over pre-loaded frames.

No I/O happens in this module — callers (the analysis layer) load events,
bookTicker, and the symbol's measured kernel, and pass arrays/frames in.

Cost model (per child order of size q, in "units" — the same units as the
input qty column):

    cost(q) = (mid_at_child - arrival_mid) * side       # adverse drift
            + half_spread_at_child                       # crossing the spread
            + temp_impact(q)                              # own-impact

    temp_impact(q) = G[1] * (q / typical_event_qty)

`G[1]` is the symbol's measured lag-1 deconvolved-kernel value (Q5,
`propagator.py`): the price impact, in mid-price units, one event after a
single typical-sized signed event. Scaling it linearly by
`q / typical_event_qty` is a strong assumption. The square-root law
(Almgren et al. 2005; Bouchaud et al. 2018, "Trades, Quotes and Prices")
has temporary impact growing sublinearly (~sqrt(q)) at large child sizes, so
linear scaling overstates the cost of large children and understates it for
very small ones once q/typical_event_qty grows well beyond O(1). Child sizes
here stay within <=3x typical_event_qty (Q7's parent_qty_events in {2, 10}
split across 20 children), where the linear and sqrt curves are close enough
for a local approximation. It is not validated against real large-child data
and should not be extrapolated beyond that regime.

Impact always costs the trader: buys and sells both pay it positively, since
executing in either direction pushes the price against the order. Drift is
signed: a favorable mid move (e.g. price falling while buying) makes
`(mid_at_child - arrival_mid) * side` negative, partly offsetting the
positive spread and impact terms.

shortfall_per_unit = sum(cost_i * q_i) / sum(q_i) over all filled children
— quantity-weighted average implementation shortfall vs. the arrival mid.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl


@dataclass(frozen=True)
class ReplayData:
    """One symbol-day of replay-ready arrays, aligned by event index.

    ts: event timestamps, int64 milliseconds since epoch.
    signs: +1/-1 aggressor sign per event.
    qtys: event size (base-asset units).
    prior_mids: mid price strictly before each event (see
        `signals.load.events_with_prior_mid`).
    half_spreads: (ask - bid) / 2 from bookTicker, asof at each event.
    typical_event_qty: median event qty for the day — the reference size
        the impact kernel's G[1] is scaled against.
    """

    ts: np.ndarray
    signs: np.ndarray
    qtys: np.ndarray
    prior_mids: np.ndarray
    half_spreads: np.ndarray
    typical_event_qty: float


@dataclass(frozen=True)
class ScheduleResult:
    schedule_name: str
    shortfall_per_unit: float
    n_children: int
    filled: bool


def replay_day(events: pl.DataFrame, bt: pl.DataFrame) -> ReplayData:
    """Build a `ReplayData` from one symbol-day's aggressor events + bookTicker.

    Uses `events_with_prior_mid`'s "strictly before" asof convention for both
    the prior mid and the half-spread, so both reflect the book state before
    each event, as in Q1-Q5.
    """
    from microstructure.signals.load import events_with_prior_mid

    joined, _n_dropped = events_with_prior_mid(events, bt)

    from datetime import timedelta

    ev_key = events.with_columns(
        (pl.col("ts") - timedelta(milliseconds=1)).alias("_key")
    ).sort("_key")
    quotes = bt.select("ts", "bid_price", "ask_price").sort("ts").rename({"ts": "_key"})
    spread_joined = ev_key.join_asof(quotes, on="_key", strategy="backward").drop("_key")
    spread_joined = spread_joined.with_columns(
        ((pl.col("ask_price") - pl.col("bid_price")) / 2).alias("half_spread")
    )

    # Align half-spread to `joined`'s row order with a join on ts+sign+qty
    # (events are unique per (ts, sign) after aggressor merging), not row order.
    merged = joined.join(
        spread_joined.select("ts", "sign", "qty", "half_spread"),
        on=["ts", "sign", "qty"],
        how="left",
    ).sort("ts")

    if merged["half_spread"].null_count() > 0:
        merged = merged.drop_nulls("half_spread")

    ts = merged["ts"].cast(pl.Int64).to_numpy()
    signs = merged["sign"].to_numpy().astype(np.int8)
    qtys = merged["qty"].to_numpy().astype(np.float64)
    prior_mids = merged["mid"].to_numpy().astype(np.float64)
    half_spreads = merged["half_spread"].to_numpy().astype(np.float64)
    typical_event_qty = float(np.median(qtys))

    return ReplayData(
        ts=ts,
        signs=signs,
        qtys=qtys,
        prior_mids=prior_mids,
        half_spreads=half_spreads,
        typical_event_qty=typical_event_qty,
    )


def simulate_schedule(
    rd: ReplayData,
    side: int,
    parent_qty_events: float,
    horizon_events: int,
    child_times: np.ndarray,
    child_sizes: np.ndarray,
    kernel_g: np.ndarray,
    schedule_name: str = "",
) -> ScheduleResult:
    """Cost a parent order executed as children at the given event indices.

    `child_times` are event-index offsets from the arrival event (0-based,
    within `[0, horizon_events)`). `child_sizes` are fractions of the parent
    order summing to approximately 1.0, as the schedule generators below
    return. The parent's total size, in the input
    qty units, is `parent_qty_events * rd.typical_event_qty`; each child's
    absolute size is `child_sizes[i] * parent_qty_events * rd.typical_event_qty`.

    `kernel_g` is the symbol's deconvolved cumulative kernel (Q5's `G`); only
    `kernel_g[1]` is used (linear temporary-impact model, see the module
    docstring).

    Arrival mid is `rd.prior_mids[0]`, the mid before the first event of the
    replay window, i.e. when the parent order arrives.
    """
    if horizon_events > rd.prior_mids.size:
        raise ValueError(
            f"horizon_events {horizon_events} exceeds replay length {rd.prior_mids.size}"
        )
    if child_times.size == 0:
        return ScheduleResult(schedule_name, float("nan"), 0, False)

    arrival_mid = float(rd.prior_mids[0])
    g1 = float(kernel_g[1])

    parent_qty_units = parent_qty_events * rd.typical_event_qty
    abs_sizes = child_sizes * parent_qty_units

    child_mids = rd.prior_mids[child_times]
    child_half_spreads = rd.half_spreads[child_times]

    drift = (child_mids - arrival_mid) * side
    temp_impact = g1 * (abs_sizes / rd.typical_event_qty)
    cost_per_unit = drift + child_half_spreads + temp_impact

    total_qty = abs_sizes.sum()
    if total_qty <= 0:
        return ScheduleResult(schedule_name, float("nan"), int(child_times.size), False)

    shortfall_per_unit = float((cost_per_unit * abs_sizes).sum() / total_qty)
    filled = bool(np.all(child_times < horizon_events) and np.all(child_times >= 0))

    return ScheduleResult(
        schedule_name=schedule_name,
        shortfall_per_unit=shortfall_per_unit,
        n_children=int(child_times.size),
        filled=filled,
    )


def twap_schedule(horizon_events: int, n_children: int) -> tuple[np.ndarray, np.ndarray]:
    """Uniform-size children at evenly spaced event indices in [0, horizon).

    Returns (child_times, child_sizes); sizes are equal fractions summing to
    1.0. Times are the floor of evenly spaced offsets, clipped into range and
    guaranteed non-decreasing.
    """
    times = np.floor(np.linspace(0, horizon_events, n_children, endpoint=False)).astype(np.int64)
    times = np.clip(times, 0, horizon_events - 1)
    sizes = np.full(n_children, 1.0 / n_children)
    return times, sizes


def frontloaded_schedule(
    horizon_events: int, n_children: int, decay: float
) -> tuple[np.ndarray, np.ndarray]:
    """Exponentially front-loaded (Almgren-Chriss-flavored) schedule.

    Child i (0-indexed) gets a raw weight `exp(-decay * i / n_children)`,
    normalized to sum to 1.0. Times are `twap_schedule`'s grid (only the size
    profile is front-loaded), which isolates the effect of front-loading from
    child placement. Larger `decay` concentrates more size in the earliest
    children.
    """
    times, _ = twap_schedule(horizon_events, n_children)
    i = np.arange(n_children, dtype=np.float64)
    raw_weights = np.exp(-decay * i / n_children)
    sizes = raw_weights / raw_weights.sum()
    return times, sizes


def kernel_half_life_lag(kernel_g: np.ndarray) -> int:
    """Lag (events) at which G first decays to half its post-peak maximum.

    The panel's measured kernels (Q5) rise from G[0]=0 to a peak within the
    first few-to-dozen lags, then decay. `frontloaded_schedule`'s `decay` is
    set from this timescale, so execution is front-loaded before the impact
    fades (see the q7_execution.py module docstring).

    Falls back to `len(kernel_g) // 4` if G is monotone non-decreasing over
    its recorded range (no post-peak decay observed). That default is not a
    validated timescale.
    """
    peak_idx = int(np.argmax(kernel_g))
    peak_val = float(kernel_g[peak_idx])
    if peak_val <= 0:
        return max(1, len(kernel_g) // 4)
    half = peak_val / 2.0
    tail = kernel_g[peak_idx:]
    below_half = np.where(tail <= half)[0]
    if below_half.size == 0:
        # never decays to half within recorded lags -> fall back
        return max(1, len(kernel_g) // 4)
    return int(peak_idx + below_half[0])


def reactive_schedule(
    rd: ReplayData,
    side: int,
    horizon_events: int,
    n_children: int,
    lookback: int,
    pause_threshold: float,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Flow-reactive TWAP: defer a child slot when trailing flow opposes the parent.

    Starts from `twap_schedule`'s slot grid. At each planned slot t, computes
    the trailing signed-flow imbalance over the `lookback` events before t,
    `mean(signs[t-lookback:t]) * side`. If it is below `-pause_threshold` (flow
    opposing the parent side beyond the threshold), the child is deferred to
    the next event (t+1) and re-checked, up to `horizon_events - 1`. A child
    never executes before the previous child's final slot, so times stay
    non-decreasing. A child still deferred at `horizon_events - 1` is filled
    there, so every child fills by the horizon end. Returns
    (child_times, child_sizes, n_deferrals).
    """
    base_times, sizes = twap_schedule(horizon_events, n_children)
    signs_f = rd.signs.astype(np.float64)

    final_times = np.empty(n_children, dtype=np.int64)
    n_deferrals = 0
    prev_time = -1

    for idx in range(n_children):
        t = int(base_times[idx])
        t = max(t, prev_time)  # never execute before the previous child (no reordering)
        while t < horizon_events - 1:
            lo = max(0, t - lookback)
            window = signs_f[lo:t]
            imbalance = float(window.mean()) * side if window.size > 0 else 0.0
            if imbalance >= -pause_threshold:
                break
            t += 1
            n_deferrals += 1
        final_times[idx] = min(t, horizon_events - 1)
        prev_time = final_times[idx]

    return final_times, sizes, n_deferrals
