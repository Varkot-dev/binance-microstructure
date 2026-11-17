"""Order-flow proxies for one contract-month (market-evolution project, Part A).

Every public function takes ONE contract-month of aggressor events (the output of
`microstructure.data.events.to_aggressor_events`: columns ts, sign, qty, price,
n_prints, sorted by ts) and, where it needs them, the raw aggTrades records of the
same month, and returns a flat dict of floats. Nothing is fitted and nothing is
carried between months, so a month's proxies depend on that month only.

Each driver is documented in `PROXY_DOCS` with its definition, units, the
mechanism it proxies and the reference number in
`research/market_evolution/notes/predictability_mechanisms.md` ("note ref N";
"note s5.N" is item N of section 5, "drivers table" is section 6).

Two drivers are listed in `NEAR_CIRCULAR`: the sign repeat rate and the lag-1 sign
autocorrelation. They are nearly the outcome being explained (next-sign accuracy),
so they are descriptive only and must not be used as explanations.

Conventions
- ts is milliseconds since the epoch (a polars Datetime column, or integer ms).
- "Sweep": consecutive events of the same sign at most 1 ms apart. Events already
  merge same-ms same-side prints; a sweep also joins same-side events 1 ms apart.
- Shares are fractions in [0, 1]; ratios to uniform are 1 when activity is flat.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from microstructure.ml.l1_features import estimate_tick

MS_PER_DAY = 86_400_000
SWEEP_GAP_MS = 1
LONG_RUN = 10
SMALL_TRADE_USD = 1_000.0

NEAR_CIRCULAR = ("sign_repeat_rate", "sign_acf_lag1")

_REF_SPLIT = ("order splitting (metaorders): note ref 1 (Lillo, Mike, Farmer 2005), "
              "ref 2 (Toth et al. 2015), ref 3 (Sato, Kanazawa 2023); note s5.3, drivers table")
_REF_CLOCK = "clock-periodic bots: note ref 31 (arXiv 2607.09426); note s5.6, drivers table"
_REF_TICK = ("larger relative tick: note section 4, ref 19 (Dayri, Rosenbaum 2015), "
             "ref 22 (Briola et al. 2025), Q4b; note s5.8, drivers table")
_REF_SIZE = ("smaller trade sizes: note ref 15 (Kyle, Obizhaeva, Tuzun), "
             "ref 16 (O'Hara, Yao, Ye 2014); drivers table")
_REF_SWEEP = "sweeps in aggregation: note ref 37 (Binance aggTrade definition); note s5.1"

PROXY_DOCS: dict[str, dict[str, str]] = {
    "run_mean": {
        "definition": "mean length of maximal runs of same-sign events (sweeps not merged)",
        "units": "events per run", "mechanism": _REF_SPLIT},
    "run_share_ge10": {
        "definition": f"share of same-sign runs (sweeps not merged) with length >= {LONG_RUN}",
        "units": "fraction of runs", "mechanism": _REF_SPLIT},
    "run_mean_sweeps_merged": {
        "definition": "run_mean after merging each sweep (same sign, gap <= 1 ms) into one unit",
        "units": "units per run", "mechanism": _REF_SPLIT},
    "run_share_ge10_sweeps_merged": {
        "definition": f"share of runs with >= {LONG_RUN} units, sweeps merged",
        "units": "fraction of runs", "mechanism": _REF_SPLIT},
    "sweep_share": {
        "definition": "share of events with the same sign as the previous event and <= 1 ms "
                      "after it (absorbed when sweeps are merged)",
        "units": "fraction of events", "mechanism": _REF_SWEEP},
    "equal_size_repeat_share": {
        "definition": "among consecutive event pairs of the same sign, share with identical qty "
                      "(compared in whole lots)",
        "units": "fraction of same-sign pairs",
        "mechanism": "fixed child sizes of slicing algorithms: note s5.4; " + _REF_SPLIT},
    "lot": {
        "definition": "lot size detected from the qty grid (estimate_tick on event qty)",
        "units": "contract units (coin)", "mechanism": "normaliser for round sizes"},
    "round_size_share": {
        "definition": "share of events whose size in lots n has n >= 10 and one significant "
                      "digit (10, 20, ..., 90, 100, 200, ... lots)",
        "units": "fraction of events",
        "mechanism": "human or bot round sizing: note s5.5, ref 31, ref 17; flow composition "
                     "row of drivers table"},
    "round10_share": {
        "definition": "share of events whose size is a multiple of 10 lots",
        "units": "fraction of events", "mechanism": "as round_size_share, coarser"},
    "share_gap_le_1ms": {
        "definition": "share of events at most 1 ms after the previous event (any sign)",
        "units": "fraction of events", "mechanism": "bot bursts and sweeps: note s5.1, s5.6"},
    "fano_1s": {
        "definition": "variance / mean of event counts in 1 s bins from the first to the last "
                      "event of the month (empty bins included); 1 for a Poisson stream",
        "units": "dimensionless", "mechanism": "burstiness (self-excitation, Hawkes): note "
                                                "section 1.2; " + _REF_CLOCK},
    "minute_open_ratio": {
        "definition": "share of events in second 0 of each minute, times 60",
        "units": "ratio to uniform (1 = flat)", "mechanism": _REF_CLOCK},
    "quarter_open_ratio": {
        "definition": "share of events in second 0 of each quarter-hour (:00, :15, :30, :45), "
                      "times 900",
        "units": "ratio to uniform (1 = flat)", "mechanism": _REF_CLOCK},
    "median_notional_usd": {
        "definition": "median of price * qty per event", "units": "USD",
        "mechanism": _REF_SIZE},
    "share_under_1k_usd": {
        "definition": "share of events with price * qty < 1000 USD",
        "units": "fraction of events", "mechanism": _REF_SIZE},
    "tick": {
        "definition": "price tick in force: estimate_tick on the month's on-grid prices (raw "
                      "aggTrade prices, or single-print event prices); the last day's tick if "
                      "it changes within the month",
        "units": "quote currency (USDT)", "mechanism": _REF_TICK},
    "tick_changes": {
        "definition": "1 if the per-day tick estimate is not the same on every day, else 0",
        "units": "flag", "mechanism": _REF_TICK},
    "rel_tick_bps": {
        "definition": "tick / median event price * 1e4; if the tick changes within the month, "
                      "the event-weighted mean over days of tick_day / median price_day * 1e4",
        "units": "bps", "mechanism": _REF_TICK},
    "unchanged_price_share": {
        "definition": "share of consecutive trades at the same price (raw aggTrade records "
                      "in id order when raw is given, else events)",
        "units": "fraction of consecutive pairs",
        "mechanism": "tick-bound book / queue depletion: note section 4 (a); " + _REF_TICK},
    "prints_per_event": {
        "definition": "raw aggTrade records per aggressor event (raw only)",
        "units": "records per event",
        "mechanism": "aggregation shape (possible measurement artifact, README week 0): "
                     + _REF_SWEEP},
    "fills_per_record": {
        "definition": "mean of last_trade_id - first_trade_id + 1 per aggTrade (raw only)",
        "units": "fills per record",
        "mechanism": "queue fragmentation / maker count: note s5.2; maker competition row of "
                     "drivers table (ref 18, Eisler, Bouchaud, Kockelkoren 2012)"},
    "sign_repeat_rate": {
        "definition": "share of events with the same sign as the previous event",
        "units": "fraction of pairs",
        "mechanism": "descriptive, near-circular: nearly the next-sign accuracy itself"},
    "sign_acf_lag1": {
        "definition": "Pearson correlation of sign[t] and sign[t-1]",
        "units": "dimensionless",
        "mechanism": "descriptive, near-circular: nearly the next-sign accuracy itself"},
}
for _k in NEAR_CIRCULAR:
    PROXY_DOCS[_k]["status"] = "descriptive, near-circular"


# ---------------------------------------------------------------- array helpers

def _ts_ms(df: pl.DataFrame) -> np.ndarray:
    col = df["ts"]
    if col.dtype.is_temporal():
        col = col.dt.epoch("ms")
    return col.to_numpy().astype(np.int64)


def _need(df: pl.DataFrame, cols: tuple[str, ...], what: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{what} is missing columns {missing}")


def run_lengths(sign: np.ndarray) -> np.ndarray:
    """Lengths of maximal runs of equal consecutive values."""
    sign = np.asarray(sign)
    if sign.size == 0:
        return np.zeros(0, dtype=np.int64)
    starts = np.flatnonzero(np.r_[True, sign[1:] != sign[:-1]])
    return np.diff(np.r_[starts, sign.size])


def sweep_continues(ts_ms: np.ndarray, sign: np.ndarray, gap_ms: int = SWEEP_GAP_MS) -> np.ndarray:
    """Boolean per event: True if it continues a sweep (same sign, <= gap_ms after previous)."""
    out = np.zeros(sign.size, dtype=bool)
    if sign.size > 1:
        out[1:] = (sign[1:] == sign[:-1]) & (np.diff(ts_ms) <= gap_ms)
    return out


def detect_lot(qty: np.ndarray) -> float:
    """Lot size: the smallest recurring increment of the qty grid (estimate_tick on qty)."""
    return estimate_tick(np.asarray(qty, dtype=np.float64))


def lots(qty: np.ndarray, lot: float) -> np.ndarray:
    """Sizes in whole lots (rounded to the nearest integer to absorb float noise)."""
    return np.rint(np.asarray(qty, dtype=np.float64) / lot).astype(np.int64)


_POW10 = 10 ** np.arange(19, dtype=np.int64)


def is_round(n_lots: np.ndarray) -> np.ndarray:
    """n >= 10 and one significant digit (10..90, 100..900, ...)."""
    n = np.asarray(n_lots, dtype=np.int64)
    k = np.clip(np.searchsorted(_POW10, n, side="right") - 1, 0, None)
    return (n >= 10) & (n % _POW10[k] == 0)


def _days(ts_ms: np.ndarray) -> np.ndarray:
    return ts_ms // MS_PER_DAY


def _per_day(ts_ms: np.ndarray, values: np.ndarray) -> list[tuple[int, np.ndarray]]:
    """Split values by UTC day of ts (does not assume ts sorted)."""
    d = _days(ts_ms)
    order = np.argsort(d, kind="stable")
    d, v = d[order], values[order]
    uniq, idx = np.unique(d, return_index=True)
    return list(zip(uniq.tolist(), np.split(v, idx[1:]), strict=True))


def _safe_tick(prices: np.ndarray) -> float:
    try:
        return estimate_tick(prices)
    except ValueError:
        return float("nan")


def _same_tick(a: float, b: float) -> bool:
    return bool(np.isclose(a, b, rtol=1e-6, atol=0.0))


# ---------------------------------------------------------------- proxy families

def sign_runs(events: pl.DataFrame) -> dict:
    """Same-sign run lengths, unmerged and with sweeps merged (note s5.3, s5.1)."""
    _need(events, ("ts", "sign"), "events")
    ts, sign = _ts_ms(events), events["sign"].to_numpy()
    cont = sweep_continues(ts, sign)
    r0 = run_lengths(sign)
    r1 = run_lengths(sign[~cont])
    return {
        "run_mean": float(r0.mean()),
        "run_share_ge10": float((r0 >= LONG_RUN).mean()),
        "run_mean_sweeps_merged": float(r1.mean()),
        "run_share_ge10_sweeps_merged": float((r1 >= LONG_RUN).mean()),
        "sweep_share": float(cont[1:].mean()) if sign.size > 1 else float("nan"),
    }


def size_clustering(events: pl.DataFrame, lot: float | None = None) -> dict:
    """Identical consecutive same-sign sizes and round sizes in lots (note s5.4, s5.5)."""
    _need(events, ("sign", "qty"), "events")
    sign, qty = events["sign"].to_numpy(), events["qty"].to_numpy()
    lot = detect_lot(qty) if lot is None else float(lot)
    n = lots(qty, lot)
    same = sign[1:] == sign[:-1]
    eq = (n[1:] == n[:-1])[same]
    return {
        "lot": lot,
        "equal_size_repeat_share": float(eq.mean()) if eq.size else float("nan"),
        "round_size_share": float(is_round(n).mean()),
        "round10_share": float(((n % 10 == 0) & (n > 0)).mean()),
    }


def burstiness(events: pl.DataFrame) -> dict:
    """Same-ms bursts, 1 s Fano factor and clock-phase concentration (note s5.6)."""
    _need(events, ("ts",), "events")
    ts = np.sort(_ts_ms(events))
    sec = ts // 1000
    counts = np.bincount(sec - sec.min())
    return {
        "share_gap_le_1ms": float((np.diff(ts) <= 1).mean()) if ts.size > 1 else float("nan"),
        "fano_1s": float(counts.var() / counts.mean()),
        "minute_open_ratio": float((sec % 60 == 0).mean() * 60),
        "quarter_open_ratio": float((sec % 900 == 0).mean() * 900),
    }


def trade_size(events: pl.DataFrame) -> dict:
    """USD notional per event (drivers table: smaller trade sizes)."""
    _need(events, ("price", "qty"), "events")
    notional = events["price"].to_numpy() * events["qty"].to_numpy()
    return {
        "median_notional_usd": float(np.median(notional)),
        "share_under_1k_usd": float((notional < SMALL_TRADE_USD).mean()),
    }


def relative_tick(events: pl.DataFrame, raw: pl.DataFrame | None = None) -> dict:
    """Tick in force over median price in bps, per day if it changes; unchanged-price share.

    Event prices of merged prints are VWAPs and lie off the grid, so the tick is
    estimated on raw aggTrade prices when given, else on single-print events only.
    """
    _need(events, ("ts", "price", "n_prints"), "events")
    ev_ts, ev_price = _ts_ms(events), events["price"].to_numpy()
    if raw is not None:
        _need(raw, ("ts", "price"), "raw")
        if "agg_trade_id" in raw.columns:
            raw = raw.sort("agg_trade_id")
        g_ts, g_price = _ts_ms(raw), raw["price"].to_numpy()
        seq_price = g_price
    else:
        single = events["n_prints"].to_numpy() == 1
        g_ts, g_price = ev_ts[single], ev_price[single]
        seq_price = ev_price
    day_tick = {d: _safe_tick(p) for d, p in _per_day(g_ts, g_price)}
    valid = [t for t in day_tick.values() if np.isfinite(t)]
    if not valid:
        raise ValueError("cannot estimate the tick: no day with two distinct on-grid prices")
    changes = any(not _same_tick(t, valid[0]) for t in valid)
    if not changes:
        tick = estimate_tick(g_price)
        rel = tick / np.median(ev_price) * 1e4
    else:
        num = den = 0.0
        for d, p in _per_day(ev_ts, ev_price):
            t = day_tick.get(d, float("nan"))
            if np.isfinite(t):
                num += p.size * t / np.median(p) * 1e4
                den += p.size
        rel = num / den
        tick = [t for _, t in sorted(day_tick.items()) if np.isfinite(t)][-1]
    unchanged = seq_price[1:] == seq_price[:-1]
    return {
        "tick": float(tick),
        "tick_changes": int(changes),
        "rel_tick_bps": float(rel),
        "unchanged_price_share": float(unchanged.mean()) if unchanged.size else float("nan"),
    }


def aggregation_shape(events: pl.DataFrame, raw: pl.DataFrame) -> dict:
    """Raw records per event and fills per record (note s5.1, s5.2). Needs raw."""
    out = {"prints_per_event": raw.height / events.height}
    if {"first_trade_id", "last_trade_id"} <= set(raw.columns):
        fills = (raw["last_trade_id"] - raw["first_trade_id"] + 1).to_numpy()
        out["fills_per_record"] = float(fills.mean())
    return out


def near_circular(events: pl.DataFrame) -> dict:
    """Descriptive, near-circular: sign repeat rate and lag-1 sign autocorrelation.

    Both are almost the outcome (next-sign accuracy); never use them as explanations.
    """
    _need(events, ("sign",), "events")
    s = events["sign"].to_numpy().astype(np.float64)
    if s.size < 2:
        return {"sign_repeat_rate": float("nan"), "sign_acf_lag1": float("nan")}
    a, b = s[1:], s[:-1]
    sd = a.std() * b.std()
    acf = float(((a - a.mean()) * (b - b.mean())).mean() / sd) if sd > 0 else float("nan")
    return {"sign_repeat_rate": float((a == b).mean()), "sign_acf_lag1": acf}


def _check_one_month(df: pl.DataFrame, what: str) -> str:
    ts = df["ts"]
    if not ts.dtype.is_temporal():
        ts = pl.from_epoch(ts, time_unit="ms")
    months = ts.dt.strftime("%Y-%m").unique()
    if months.len() != 1:
        raise ValueError(f"{what} must cover exactly one calendar month, got {months.to_list()}")
    return months[0]


def contract_month_proxies(events: pl.DataFrame, raw: pl.DataFrame | None = None) -> dict:
    """All drivers of one contract-month as one flat dict (see PROXY_DOCS).

    Raises ValueError if events (or raw) span more than one UTC calendar month,
    so that no driver can mix in another month's data.
    """
    if events.height < 2:
        raise ValueError("need at least two events")
    month = _check_one_month(events, "events")
    if raw is not None and _check_one_month(raw, "raw") != month:
        raise ValueError("raw and events are from different months")
    ts = _ts_ms(events)
    out: dict = {"month": month, "n_events": events.height,
                 "days": int(np.unique(_days(ts)).size)}
    out["events_per_day"] = out["n_events"] / out["days"]
    out |= sign_runs(events)
    out |= size_clustering(events)
    out |= burstiness(events)
    out |= trade_size(events)
    out |= relative_tick(events, raw)
    if raw is not None:
        out |= aggregation_shape(events, raw)
    out |= near_circular(events)
    return out
