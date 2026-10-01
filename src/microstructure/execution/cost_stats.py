"""Summary statistics for the Q7 schedule comparison: pooled and paired.

Shortfalls are in basis points of the arrival mid. Rows are dicts with keys
symbol, day, side, parent_qty_events, schedule and shortfall_bps.
"""
from __future__ import annotations

import numpy as np

SCHEDULE_NAMES = ("twap", "frontloaded", "reactive")


def stats(vals: list[float]) -> dict[str, float | int]:
    if not vals:
        return {"mean_shortfall": float("nan"), "sd_shortfall": float("nan"), "n": 0}
    return {
        "mean_shortfall": float(np.mean(vals)),
        "sd_shortfall": float(np.std(vals)),
        "n": len(vals),
    }


def summarize(rows: list[dict]) -> dict[str, dict]:
    """Per-schedule mean, sd and n of shortfall in bps, pooled over all rows."""
    return {
        name: stats([r["shortfall_bps"] for r in rows if r["schedule"] == name])
        for name in SCHEDULE_NAMES
    }


def summarize_per_symbol(rows: list[dict], symbols: list[str]) -> list[dict]:
    out = []
    for symbol in symbols:
        sym_rows = [r for r in rows if r["symbol"] == symbol]
        entry: dict = {"symbol": symbol}
        for name in SCHEDULE_NAMES:
            entry[name] = stats([r["shortfall_bps"] for r in sym_rows if r["schedule"] == name])
        out.append(entry)
    return out


def paired_difference(rows: list[dict], schedule_a: str, schedule_b: str) -> dict:
    """Mean of (a - b) shortfall over cells where both schedules ran, with the
    paired standard error sd(diff, ddof=1) / sqrt(n) and z = mean / se.

    A cell is one (symbol, day, side, parent size). The cells are not
    independent: the two sides and two sizes of a symbol-day share one replay,
    so the SE is optimistic. mean and z are None when n < 2 or the SE is 0.
    """
    by_cell: dict[tuple, dict[str, float]] = {}
    for r in rows:
        key = (r["symbol"], r["day"], r["side"], r["parent_qty_events"])
        by_cell.setdefault(key, {})[r["schedule"]] = r["shortfall_bps"]
    diffs = np.array(
        [c[schedule_a] - c[schedule_b] for c in by_cell.values() if schedule_a in c and schedule_b in c]
    )
    n = int(diffs.size)
    if n < 2:
        return {"mean": None, "se": None, "z": None, "n": n}
    se = float(np.std(diffs, ddof=1) / np.sqrt(n))
    mean = float(np.mean(diffs))
    return {"mean": mean, "se": se, "z": mean / se if se > 0.0 else None, "n": n}


def sd_ratio(summary: dict) -> float | None:
    """sd of front-loaded shortfall over sd of TWAP shortfall, or None if undefined."""
    sd_front = summary["frontloaded"]["sd_shortfall"]
    sd_twap = summary["twap"]["sd_shortfall"]
    if summary["frontloaded"]["n"] == 0 or summary["twap"]["n"] == 0 or not sd_twap > 0.0:
        return None
    return float(sd_front / sd_twap)
