"""Build and verify the tick-size-change event table for Part A's natural experiments.

Candidate events are the 67 USDT-M tick-size notices listed in the appendix of
`notes/binance_events.md` (2023-01 to 2026-10 here). Many notices were read by title
only, so the treated contracts are found in the data, not taken from the notes:

1. Scan. For every USDT perpetual alive in a month around a notice, download the
   monthly 2h klines (tiny) and compute, for each day, the trade-price tick from the
   OHLC prices: the largest power of ten on whose grid at least TICK_SHARE of the
   prices lie. A change of that daily tick that persists is a candidate tick change.
2. Treated. Each change near a notice date (or a contract named in a notice) is
   checked in the daily aggTrades: per day and, on the change day, per 30-minute bin,
   the share of trade prices on each grid. This gives the detected change time, the
   old and new tick, and activity (aggTrade records per day) before the event.
3. Controls. For each event date, USDT perpetuals whose tick did not change within
   +/- 30 days (checked on every day from 2h klines, and on the event day from
   trades for the closest matches) and whose pre-period activity is within a factor
   of 2 of a treated contract (trades per day from klines and aggTrades bytes per day
   from the archive inventory, both within 2x).

Downloads go through `microstructure.data.binance.download` (SHA-256 verified) into a
fresh temporary folder, are summarized, and deleted; only small JSON summaries are kept
under data/tick_events/. Run from the repository root:

    PYTHONPATH=src .venv/bin/python research/market_evolution/build_tick_events.py all
"""
from __future__ import annotations

import argparse
import calendar
import concurrent.futures as cf
import datetime as dt
import json
import math
import shutil
import sys
import threading
import uuid
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "research" / "market_evolution" / "data"
CACHE = ROOT / "data" / "tick_events"
INVENTORY = ROOT / "data" / "universe" / "aggtrades_monthly_inventory.json"

TICK_SHARE = 0.7  # share of prices on a grid needed to call that grid the tick
MIN_DAY_PRICES = 24  # kline prices (4 per 2h row) needed for a daily tick
MIN_DAY_EVENTS = 200  # aggTrade records needed for a daily tick from trades
MIN_BIN_EVENTS = 20  # aggTrade records needed for a 30-minute bin tick
MIN_GAIN = 2  # a change must explain at least this many more days than no change
WINDOW = 10  # days before and after an event for the treated check
CONTROL_WINDOW = 30  # days before and after an event with no tick change for controls
ACTIVITY_FACTOR = 2.0
MAX_DAY_FILE = 300e6  # skip an aggTrades day file larger than this
HARD_CAP = 1.95e9  # total bytes downloaded, all stages and runs
TREATED_AGG_BUDGET = 1.2e9
NAMED_AGG_BUDGET = 0.7e9  # events named in the task: +/- 10 days, water-filled
OTHER_DAY0_MAX = 5e6  # other contract-events: the change day only, if this small
CONTROL_AGG_BUDGET = 0.30e9
CONTROL_SAMPLE_MAX_FILE = 25e6
CONTROLS_CHECKED_PER_TREATED = 6  # stability-checked candidates per treated contract
CONTROLS_TRADE_SAMPLED_PER_TREATED = 1
LAST_MONTH = "2026-10"  # last month with a monthly archive file
LAST_DAY = dt.date(2026, 11, 15)  # last daily file used
WORKERS = 4


# ----------------------------------------------------------------------------------------
# Candidate events: every USDT-M tick notice in the appendix of notes/binance_events.md,
# 2023-01 to 2026-10. `dates` are the effective dates (title dates; 2023-02-03 is the
# publication date and took effect 2023-02-10). `listed` holds the USDT contracts named
# in the notes (None when the body was not read), `time` the stated minute if known.
# ----------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Notice:
    label: str
    dates: tuple[str, ...]
    code: str
    listed: tuple[str, ...] | None = None
    time: str | None = None
    listed_tag: str = ""
    named_in_task: bool = False


def _n(label, dates, code, listed=None, time=None, tag="", named=False):
    syms = None if listed is None else tuple(s + "USDT" for s in listed.split())
    return Notice(label, tuple(dates.split()), code, syms, time, tag, named)


NOTICES: list[Notice] = [
    _n("2023-02-10", "2023-02-10", "98315efa", "APT OCEAN", "06:30", "V", True),
    _n("2023-04-26", "2023-04-26", "33ddfb48", "BNX", None, "V title"),
    _n("2023-06-05", "2023-06-05", "bdb9b2ed"),
    _n("2023-08-29", "2023-08-29", "8764f0d8", "AMB HOOK API3 TRB DODOX", "06:30", "V", True),
    _n("2024-02-05", "2024-02-05", "cb9bf771"),
    _n("2024-03-19", "2024-03-19", "98e60866"),
    _n("2024-04-11", "2024-04-11", "c58b0b29"),
    _n("2024-05-08", "2024-05-08", "aa2bfe79"),
    _n("2024-06-20", "2024-06-20", "50df6c9a"),
    _n("2024-07-25", "2024-07-25", "08f043a4"),
    _n("2024-09-20", "2024-09-20", "fa192e78",
       "APT ASTR JOE KEY XVG BIGTIME ILV GLM ETHFI TURBO ZRO RPL", "06:30", "V", True),
    _n("2024-10-14", "2024-10-14", "8bfe2e9b", "SOL", "06:30", "V", True),
    _n("2024-11-04", "2024-11-04", "f9baa987"),
    _n("2024-11-28", "2024-11-28", "8a4a0a76"),
    _n("2024-11-29", "2024-11-29", "0d330d9e", "1000WHY 1000CHEEMS", None, "V title"),
    _n("2025-03-25", "2025-03-25", "aa26fca9", "LINA", None, "V title"),
    _n("2025-04-17", "2025-04-17", "cb6f7e88"),
    _n("2025-06-12", "2025-06-12", "fed6c0cb"),
    _n("2025-08-01", "2025-08-01", "cf3f3712"),
    _n("2025-08-04", "2025-08-04", "9ae52569"),
    _n("2025-08-11", "2025-08-11", "59caa670"),
    _n("2025-08-25", "2025-08-25", "697d0249"),
    _n("2025-09-02", "2025-09-02", "4661056f", "SOMI", None, "V title"),
    _n("2025-09-03", "2025-09-03", "0f7995f9"),
    _n("2025-09-10", "2025-09-10", "c4e5c658"),
    _n("2025-09-19", "2025-09-19", "01535c3f", "AVNT", "07:00", "S"),
    _n("2025-10-08", "2025-10-08", "d901cffc"),
    _n("2025-10-10", "2025-10-10", "a1e0bd9e"),
    _n("2025-10-17", "2025-10-17", "fd11627d", "BAS CLO", "07:00", "V"),
    _n("2025-10-27", "2025-10-27", "f9dd6ab7", "EVAA XPIN TAC", None, "S"),
    _n("2025-10-31", "2025-10-31", "47ee5d50"),
    _n("2025-11-07", "2025-11-07", "21a1b8c2"),
    _n("2025-11-20", "2025-11-20", "6ca4596f"),
    _n("2025-11-27", "2025-11-27", "aa023c23"),
    _n("2025-12-08", "2025-12-08", "d9d73edb"),
    _n("2025-12-15", "2025-12-15", "baee5eb8",
       "KERNEL LINEA BERA SONIC WCT ZETA MANTA", "07:00", "V"),
    _n("2025-12-22", "2025-12-22", "1cd08ee9",
       "USELESS NOM EVAA SLP WAXP POWR SCR AT VTHO VANRY STABLE", "07:00", "V"),
    _n("2026-01-28", "2026-01-28", "2fe0af37"),
    _n("2026-02-09", "2026-02-09", "093b6071"),
    _n("2026-02-12", "2026-02-12", "5bb4a627"),
    _n("2026-02-27", "2026-02-27", "5f7fa3af"),
    _n("2026-03-05", "2026-03-05", "f0e08cca",
       "MYX GRIFFAIN 4 A MIRA SCRT HEI DRIFT ZKC A2Z LAYER LISTA", "07:00", "S", True),
    _n("2026-03-18", "2026-03-18 2026-03-19", "fb7a1674"),
    _n("2026-04-02", "2026-04-02 2026-04-07", "74de1917"),
    _n("2026-04-06", "2026-04-06", "6dbc37d4"),
    # No date in the title (published 2026-04-10): any day in the next two weeks.
    _n("2026-04-10 (undated)", " ".join(
        (dt.date(2026, 4, 11) + dt.timedelta(i)).isoformat() for i in range(14)), "3208154c"),
    _n("2026-04-21", "2026-04-21 2026-04-22", "b0cea42f"),
    _n("2026-04-27", "2026-04-27 2026-04-29", "bb0c704f"),
    _n("2026-06-04", "2026-06-04 2026-06-08", "fcf3698a"),
    _n("2026-06-06", "2026-06-06", "d38329a5"),
    _n("2026-06-10", "2026-06-10 2026-06-12", "3d7ade5e"),
    _n("2026-06-13", "2026-06-13", "6baee79f"),
    _n("2026-06-17", "2026-06-17", "60b48c91"),
    _n("2026-07-07", "2026-07-07 2026-07-08", "313d5923"),
    _n("2026-07-09", "2026-07-09", "83351356"),
    _n("2026-07-21", "2026-07-21 2026-07-22", "f74b3070"),
    _n("2026-07-30", "2026-07-30", "731403f0"),
    _n("2026-08-06", "2026-08-06", "be5c80d7",
       "MOVE COOKIE AVNT ZK MAV CKB VANA AXS", "06:30", "V"),
    _n("2026-08-15", "2026-08-15", "82a93632"),
    _n("2026-08-18", "2026-08-18", "1fa92e04"),
    _n("2026-08-24", "2026-08-24", "6138b61b"),
    _n("2026-09-17", "2026-09-17", "2b19fead"),
    _n("2026-10-15", "2026-10-15", "7157d432",
       "APR XPIN ROBO BEAT RUM FLNC CSOPSAMSUNG2L", "06:30", "V"),
    _n("2026-10-22", "2026-10-22", "84b9812b", "BILL IDOL ESPORTS BR AGT", "06:30", "V"),
    _n("2026-10-28", "2026-10-28", "4688df6f"),
]


# ----------------------------------------------------------------------------------------
# Pure detection logic (tested offline in tests/research/test_tick_events.py)
# ----------------------------------------------------------------------------------------
def price_levels(prices: np.ndarray, floor_exp: int | None = None) -> np.ndarray:
    """For each price, the largest k such that the price is a multiple of 10**k.

    Prices are checked on decimal grids from the largest power of ten below the
    largest price down to `floor_exp` (default: 9 decades below the median price,
    finer than any real tick); a price on no checked grid gets `floor_exp`.
    """
    p = np.asarray(prices, dtype=np.float64)
    if p.size == 0:
        return np.zeros(0, dtype=np.int64)
    if floor_exp is None:
        floor_exp = math.floor(math.log10(float(np.median(p)))) - 9
    top = math.floor(math.log10(float(p.max())))
    lv = np.full(p.size, floor_exp, dtype=np.int64)
    for k in range(floor_exp + 1, top + 1):
        r = p / (10.0 ** k) if k >= 0 else p * (10.0 ** -k)
        on = np.abs(r - np.rint(r)) < 1e-6
        lv[on] = k
    return lv


def level_histogram(levels: np.ndarray) -> dict[int, int]:
    """Count of prices per level, as {exponent: count}."""
    vals, counts = np.unique(np.asarray(levels, dtype=np.int64), return_counts=True)
    return {int(v): int(c) for v, c in zip(vals, counts)}


def tick_exp(hist: dict[int, int], threshold: float = TICK_SHARE, min_n: int = 1) -> int | None:
    """Largest exponent k with at least `threshold` of the prices on the 10**k grid.

    A price on the 10**k grid has level >= k. Returns None with fewer than min_n prices.
    """
    n = sum(hist.values())
    if n < min_n or n == 0:
        return None
    best = None
    for k in sorted(hist):
        on = sum(c for lv, c in hist.items() if lv >= k)
        if on >= threshold * n:
            best = k
    return best


def grid_share(hist: dict[int, int], k: int) -> float:
    """Share of prices on the 10**k grid."""
    n = sum(hist.values())
    return sum(c for lv, c in hist.items() if lv >= k) / n if n else float("nan")


def _mode(xs):
    c = Counter(xs)
    top = max(c.values())
    for x in xs:  # first-appearing among the most common
        if c[x] == top:
            return x, top
    raise ValueError("empty")


def best_split(labels: list, min_gain: int = MIN_GAIN):
    """One change point in a sequence of labels.

    For each split s (labels[:s] before, labels[s:] after) take the most common label
    on each side; the cost is the number of labels that disagree with their side's mode.
    Returns (s, old, new, cost) for the cheapest split whose two modes differ, if it
    beats the no-change cost by at least min_gain labels; otherwise None.
    """
    n = len(labels)
    if n < 2:
        return None
    base = n - _mode(labels)[1]
    best = None
    for s in range(1, n):
        old, c_old = _mode(labels[:s])
        new, c_new = _mode(labels[s:])
        if old == new:
            continue
        cost = (s - c_old) + (n - s - c_new)
        if best is None or cost < best[3]:
            best = (s, old, new, cost)
    if best is not None and base - best[3] >= min_gain:
        return best
    return None


def segment_changes(labels: list, min_run: int = MIN_GAIN) -> list[tuple[int, object, object]]:
    """All persistent changes in a label sequence: [(index of first new label, old, new)].

    The sequence is cut into runs of equal labels; runs shorter than min_run are noise
    and are absorbed by their neighbours (shortest first; into the longer neighbour, or
    both neighbours merge when they agree). The remaining run boundaries are the changes,
    so a change that is later reverted is found too.
    """
    runs: list[list] = []  # [label, start, length]
    for i, x in enumerate(labels):
        if runs and runs[-1][0] == x:
            runs[-1][2] += 1
        else:
            runs.append([x, i, 1])
    while len(runs) > 1:
        short = [i for i, r in enumerate(runs) if r[2] < min_run]
        if not short:
            break
        i = min(short, key=lambda k: (runs[k][2], k))
        left = runs[i - 1] if i > 0 else None
        right = runs[i + 1] if i + 1 < len(runs) else None
        if left is not None and right is not None and left[0] == right[0]:
            left[2] += runs[i][2] + right[2]
            del runs[i : i + 2]
        elif right is None or (left is not None and left[2] >= right[2]):
            left[2] += runs[i][2]
            del runs[i]
        else:
            right[1], right[2] = runs[i][1], right[2] + runs[i][2]
            del runs[i]
    return [(runs[i][1], runs[i - 1][0], runs[i][0]) for i in range(1, len(runs))]


def binomial_changepoint(n: np.ndarray, k: np.ndarray) -> int:
    """Split index s (bins[:s] before, bins[s:] after) maximizing the likelihood of a
    two-rate binomial model for k successes out of n per bin. Returns 0 or len(n) if a
    single rate fits as well as any split (no change inside the sequence)."""
    n = np.asarray(n, dtype=np.float64)
    k = np.asarray(k, dtype=np.float64)

    def ll(kk, nn):
        if nn <= 0:
            return 0.0
        p = kk / nn
        out = 0.0
        if kk > 0:
            out += kk * math.log(p)
        if nn - kk > 0:
            out += (nn - kk) * math.log(1 - p)
        return out

    total = ll(k.sum(), n.sum())
    best_s, best = 0, total
    ck, cn = np.cumsum(k), np.cumsum(n)
    for s in range(1, n.size):
        v = ll(ck[s - 1], cn[s - 1]) + ll(ck[-1] - ck[s - 1], cn[-1] - cn[s - 1])
        if v > best + 1e-9:
            best_s, best = s, v
    return best_s


def change_bin(bin_hists: list[dict[int, int]], old: int, new: int) -> int | None:
    """Index of the first bin on the new tick, from per-bin price-level histograms.

    The indicator is "price on the coarser of the two grids": its share drops at a cut
    (all old prices were on it) and rises at an increase. Bins are weighted by their
    counts. Returns None when no bin has prices.
    """
    coarse = max(old, new)
    n = np.array([sum(h.values()) for h in bin_hists], dtype=np.float64)
    if n.sum() == 0:
        return None
    k = np.array([sum(c for lv, c in h.items() if lv >= coarse) for h in bin_hists], dtype=float)
    return binomial_changepoint(n, k)


def regimes_match(bin_hists: list[dict[int, int]], cp: int, old: int, new: int) -> bool:
    """True if the bins before cp look like the old tick and those after like the new
    one: the share on the coarser grid is at least TICK_SHARE exactly on the side whose
    tick is the coarser one."""
    coarse = max(old, new)

    def share(hs):
        n = sum(sum(h.values()) for h in hs)
        k = sum(c for h in hs for lv, c in h.items() if lv >= coarse)
        return k / n if n else float("nan")

    before, after = share(bin_hists[:cp]), share(bin_hists[cp:])
    return (before >= TICK_SHARE) == (old == coarse) and (after >= TICK_SHARE) == (new == coarse)


def direction(old_exp: int, new_exp: int) -> str:
    if new_exp > old_exp:
        return "increase"
    if new_exp < old_exp:
        return "cut"
    return "none"


def rel_tick_bps(exp: int, price: float) -> float:
    return 10.0 ** exp / price * 1e4


def status_for(stated: dt.date, detected: dt.date | None, tolerance_days: int = 0) -> str:
    if detected is None:
        return "no-change"
    if abs((detected - stated).days) <= tolerance_days:
        return "verified"
    return "date-differs"


def within_factor(a: float, b: float, factor: float = ACTIVITY_FACTOR) -> bool:
    if not (a > 0 and b > 0):
        return False
    return 1.0 / factor <= a / b <= factor


def waterfill_cap(totals: list[float], budget: float) -> float:
    """Per-unit cap c such that sum(min(total_i, c)) is at most budget (inf if all fit)."""
    if sum(totals) <= budget:
        return math.inf
    lo, hi = 0.0, max(totals)
    for _ in range(60):
        mid = (lo + hi) / 2
        if sum(min(t, mid) for t in totals) <= budget:
            lo = mid
        else:
            hi = mid
    return lo


def plan_days(sizes: dict[int, float], cap: float, priority: list[int],
              min_days: tuple[int, ...] = (0,)) -> list[int]:
    """Day offsets to download: in priority order while the running size stays within
    cap; the offsets in min_days are always taken if they exist."""
    take, used = [], 0.0
    for d in priority:
        if d not in sizes:
            continue
        if d in min_days or used + sizes[d] <= cap:
            take.append(d)
            used += sizes[d]
    return take


DAY_PRIORITY = [0, -1, 1, -2, 2, -10, 10, -5, 5, -3, 3, -7, 7, -4, 4, -6, 6, -8, 8, -9, 9]


def fmt_tick(exp: int) -> str:
    return format(Decimal(1).scaleb(exp), "f")


# ----------------------------------------------------------------------------------------
# I/O: downloads, summaries, caches
# ----------------------------------------------------------------------------------------
class Ledger:
    """Bytes downloaded, persisted across runs, with a hard cap."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.files: dict[str, int] = json.loads(path.read_text()) if path.exists() else {}

    @property
    def total(self) -> int:
        return sum(self.files.values())

    def check(self, expected: float = 0) -> None:
        if self.total + expected > HARD_CAP:
            raise RuntimeError(f"download budget reached: {self.total / 1e9:.2f} GB")

    def add(self, name: str, size: int) -> None:
        with self.lock:
            self.files[name] = self.files.get(name, 0) + size
            if len(self.files) % 50 == 0:
                self.save()

    def save(self) -> None:
        with self.lock:
            self.path.write_text(json.dumps(self.files))


_LEDGER: Ledger | None = None
_CLIENT = None


def ledger() -> Ledger:
    global _LEDGER
    if _LEDGER is None:
        CACHE.mkdir(parents=True, exist_ok=True)
        _LEDGER = Ledger(CACHE / "ledger.json")
    return _LEDGER


def client():
    global _CLIENT
    if _CLIENT is None:
        import httpx

        _CLIENT = httpx.Client(timeout=180, limits=httpx.Limits(max_connections=8))
    return _CLIENT


def _kline_file(symbol: str, interval: str, period: str):
    from microstructure.data.binance import BASE, DAILY_BASE, DumpFile

    @dataclass(frozen=True)
    class KlineFile(DumpFile):
        interval: str = "2h"

        @property
        def filename(self) -> str:
            return f"{self.symbol}-{self.interval}-{self.period}.zip"

        @property
        def url(self) -> str:
            return f"{self.base}/klines/{self.symbol}/{self.interval}/{self.filename}"

    base = DAILY_BASE if len(period) == 10 else BASE
    return KlineFile(symbol, "klines", period, base, interval)


def _fetch(file, expected: float = 0):
    """Download into a fresh temp folder; returns (path, folder) or (None, None) on 404."""
    import httpx

    from microstructure.data.binance import download

    ledger().check(expected)
    tmp = CACHE / "_tmp" / uuid.uuid4().hex
    tmp.mkdir(parents=True)
    try:
        path = download(file, tmp, client())
    except httpx.HTTPStatusError as e:
        shutil.rmtree(tmp, ignore_errors=True)
        if e.response.status_code in (403, 404):
            return None, None
        raise
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    ledger().add(file.filename, path.stat().st_size)
    return path, tmp


def _head_size(url: str) -> int | None:
    r = client().head(url)
    if r.status_code != 200:
        return None
    return int(r.headers.get("content-length", 0))


KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]


def _summarize_klines(zip_path: Path) -> dict:
    import polars as pl

    from microstructure.data.ingest import _read_zipped_csv

    df = _read_zipped_csv(zip_path, KLINE_COLS)
    df = df.with_columns(
        pl.col("open_time").cast(pl.Int64),
        *(pl.col(c).cast(pl.Float64) for c in ("open", "high", "low", "close", "quote_volume")),
        pl.col("count").cast(pl.Int64),
    ).sort("open_time")
    ot = df["open_time"].to_numpy()
    ot = np.where(ot > 100_000_000_000_000, ot // 1000, ot)
    days = (ot // 86_400_000).astype(np.int64)
    out: dict[str, dict] = {}
    for d in np.unique(days):
        m = days == d
        sub = df.filter(pl.Series(m))
        cnt = sub["count"].to_numpy()
        prices = np.column_stack([sub[c].to_numpy() for c in ("open", "high", "low", "close")])
        traded = cnt > 0
        p = prices[traded].ravel()
        day = (dt.date(1970, 1, 1) + dt.timedelta(int(d))).isoformat()
        if p.size == 0:
            out[day] = {"cnt": 0, "qv": 0.0}
            continue
        lv = price_levels(p)
        rows = ((ot[m][traded] - int(d) * 86_400_000) // 7_200_000).astype(int).tolist()
        out[day] = {
            "cnt": int(cnt.sum()),
            "qv": float(sub["quote_volume"].sum()),
            "med": float(np.median(sub["close"].to_numpy()[traded])),
            "rows": rows,  # 2h row index of each group of 4 levels
            "lv": lv.tolist(),
        }
    return out


def kline_month(symbol: str, month: str) -> dict | None:
    """Per-day summary of one month of 2h klines (cached); None if not in the archive.

    For a month after LAST_MONTH the daily files up to LAST_DAY are used instead.
    """
    path = CACHE / "kl2h" / symbol / f"{month}.json"
    if path.exists():
        data = json.loads(path.read_text())
        return data or None
    if month > LAST_MONTH:
        y, mo = int(month[:4]), int(month[5:])
        data = {}
        for dd in range(1, calendar.monthrange(y, mo)[1] + 1):
            day = dt.date(y, mo, dd)
            if day > LAST_DAY:
                break
            zp, tmp = _fetch(_kline_file(symbol, "2h", day.isoformat()))
            if zp is None:
                continue
            try:
                data.update(_summarize_klines(zp))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    else:
        zp, tmp = _fetch(_kline_file(symbol, "2h", month))
        if zp is None:
            data = {}
        else:
            try:
                data = _summarize_klines(zp)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")))
    return data or None


def agg_day(symbol: str, day: str, size: int | None = None) -> dict | None:
    """Per-day aggTrades summary (cached): records, trades, median price, the
    smallest recurring increment, and per 30-minute bin a histogram of price levels."""
    path = CACHE / "agg" / symbol / f"{day}.json"
    if path.exists():
        data = json.loads(path.read_text())
        return data or None
    import polars as pl

    from microstructure.data.binance import DAILY_BASE, DumpFile
    from microstructure.data.ingest import ingest_agg_trades
    from microstructure.ml.l1_features import estimate_tick

    zp, tmp = _fetch(DumpFile(symbol, "aggTrades", day, base=DAILY_BASE), size or 0)
    if zp is None:
        data = {}
    else:
        try:
            pq = ingest_agg_trades(zp, tmp)
            zp.unlink()
            df = pl.read_parquet(pq, columns=["price", "first_trade_id", "last_trade_id", "ts"])
            p = df["price"].to_numpy()
            ms = df["ts"].dt.epoch("ms").to_numpy()
            d0 = int(dt.datetime.fromisoformat(day).replace(tzinfo=dt.UTC)
                     .timestamp() * 1000)
            b = np.clip((ms - d0) // 1_800_000, 0, 47).astype(int)
            lv = price_levels(p)
            bins = []
            for i in range(48):
                bins.append({str(k): v for k, v in level_histogram(lv[b == i]).items()})
            ntr = (df["last_trade_id"] - df["first_trade_id"] + 1).sum()
            try:
                est = estimate_tick(p)
            except ValueError:
                est = None
            data = {"events": int(df.height), "trades": int(ntr), "med": float(np.median(p)),
                    "est_tick": est, "bins": bins, "zip_bytes": int(size or 0)}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")))
    return data or None


def agg_size(symbol: str, day: str) -> int | None:
    from microstructure.data.binance import DAILY_BASE, DumpFile

    path = CACHE / "sizes.json"
    key = f"{symbol}|{day}"
    with _SIZE_LOCK:
        if not _SIZES and path.exists():
            _SIZES.update(json.loads(path.read_text()))
        if key in _SIZES:
            return _SIZES[key]
    s = _head_size(DumpFile(symbol, "aggTrades", day, base=DAILY_BASE).url)
    with _SIZE_LOCK:
        _SIZES[key] = s
    return s


_SIZES: dict[str, int | None] = {}
_SIZE_LOCK = threading.Lock()


def save_sizes() -> None:
    with _SIZE_LOCK:
        (CACHE / "sizes.json").write_text(json.dumps(_SIZES))


def pmap(fn, items, label: str):
    items = list(items)
    out = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(fn, *it): it for it in items}
        for i, f in enumerate(cf.as_completed(futs), 1):
            try:
                out.append((futs[f], f.result()))
            except Exception as e:  # noqa: BLE001 (keep going; report)
                print(f"[{label}] {futs[f]}: {type(e).__name__}: {e}", file=sys.stderr)
                out.append((futs[f], None))
            if i % 200 == 0:
                print(f"[{label}] {i}/{len(items)} done, {ledger().total / 1e6:.0f} MB "
                      "downloaded so far", file=sys.stderr, flush=True)
    ledger().save()
    return out


# ----------------------------------------------------------------------------------------
# Dates and universe
# ----------------------------------------------------------------------------------------
def d_(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def months_between(a: dt.date, b: dt.date) -> list[str]:
    out, y, m = [], a.year, a.month
    while (y, m) <= (b.year, b.month):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def load_inventory() -> dict[str, dict[str, int]]:
    return json.loads(INVENTORY.read_text())


def usdt_perps(inv: dict, month: str) -> list[str]:
    return sorted(s for s, m in inv.items() if s.endswith("USDT") and "_" not in s and month in m)


def notice_dates() -> list[dt.date]:
    return sorted({d_(x) for n in NOTICES for x in n.dates})


def scan_months() -> set[tuple[str, str]]:
    """(symbol, month) pairs for the universe scan: every USDT perpetual alive in a month
    that overlaps [date - 12 days, date + 12 days] of a notice."""
    inv = load_inventory()
    pairs = set()
    for d in notice_dates():
        for m in months_between(d - dt.timedelta(12), d + dt.timedelta(12)):
            if m > LAST_MONTH:  # daily files only for treated candidates, later
                continue
            for s in usdt_perps(inv, m):
                pairs.add((s, m))
    listed = {(s, n) for n in NOTICES for s in (n.listed or ())}
    for s, n in listed:
        d = d_(n.dates[0])
        for m in months_between(d - dt.timedelta(12), d + dt.timedelta(12)):
            if m <= LAST_MONTH:
                pairs.add((s, m))
    return pairs


def daily_series(symbol: str, months: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in months:
        path = CACHE / "kl2h" / symbol / f"{m}.json"
        if path.exists():
            out.update(json.loads(path.read_text()))
    return dict(sorted(out.items()))


def kline_day_tick(rec: dict) -> int | None:
    if not rec or rec.get("cnt", 0) == 0 or len(rec.get("lv", [])) < MIN_DAY_PRICES:
        return None
    return tick_exp(level_histogram(np.array(rec["lv"])), TICK_SHARE, MIN_DAY_PRICES)


def kline_changes(series: dict[str, dict]) -> list[dict]:
    """Tick changes in a daily kline series: [{day, old, new, time}] with a 2h time."""
    days = [d for d, r in series.items() if kline_day_tick(r) is not None]
    labels = [kline_day_tick(series[d]) for d in days]
    out = []
    for s, old, new in segment_changes(labels):
        day = days[s]
        prev = days[s - 1]
        # 2h resolution: binomial change point over rows of the previous and change day
        coarse = max(old, new)
        n, k, stamps = [], [], []
        for dd in (prev, day):
            r = series[dd]
            lv = np.array(r["lv"]).reshape(-1, 4)
            for row, v in zip(r["rows"], lv):
                n.append(4)
                k.append(int((v >= coarse).sum()))
                stamps.append(f"{dd} {row * 2:02d}:00")
        cp = binomial_changepoint(np.array(n), np.array(k))
        t = stamps[cp] if 0 < cp < len(stamps) else f"{day} 00:00"
        out.append({"day": t[:10], "old": old, "new": new, "time": t, "gap_before":
                    (d_(day) - d_(prev)).days})
    return out


# ----------------------------------------------------------------------------------------
# Stages
# ----------------------------------------------------------------------------------------
def stage_scan() -> None:
    pairs = sorted(scan_months())
    todo = [p for p in pairs if not (CACHE / "kl2h" / p[0] / f"{p[1]}.json").exists()]
    print(f"scan: {len(pairs)} symbol-months, {len(todo)} to fetch", file=sys.stderr)
    pmap(kline_month, todo, "scan")


def attribute(changes: dict[str, list[dict]]) -> list[dict]:
    """Assign each detected change to the notice with the nearest effective date.

    A change at day c belongs to a notice dated D if D <= c <= D + 1 (an increase late in
    the day can label the change day as the next day) or, for a contract the notice names,
    if |c - D| <= WINDOW. Unattributed changes are returned with notice None.
    """
    rows = []
    for sym, chs in changes.items():
        for ch in chs:
            c = d_(ch["time"][:10])
            best = None
            for n in NOTICES:
                for ds in n.dates:
                    D = d_(ds)
                    named = n.listed is not None and sym in n.listed
                    # a change seen across a gap between scanned months has an unknown
                    # day, so only a contract the notice names is attributed then
                    near = 0 <= (c - D).days <= 1 and ch.get("gap_before", 1) <= 3
                    ok = near or (named and abs((c - D).days) <= WINDOW)
                    if not ok:
                        continue
                    undated = n.label.endswith("(undated)")
                    key = (0 if named else 1, 1 if undated else 0, abs((c - D).days))
                    if best is None or key < best[0]:
                        best = (key, n, ds)
            rows.append({"symbol": sym, **ch, "notice": best[1].label if best else None,
                         "notice_date": best[2] if best else None})
    return rows


def all_kline_changes() -> dict[str, list[dict]]:
    by_sym: dict[str, list[str]] = {}
    for p in (CACHE / "kl2h").glob("*/*.json"):
        by_sym.setdefault(p.parent.name, []).append(p.stem)
    out = {}
    for sym, months in by_sym.items():
        ch = kline_changes(daily_series(sym, sorted(months)))
        if ch:
            out[sym] = ch
    return out


def treated_candidates() -> list[dict]:
    """One row per (notice, symbol): detected changes near a notice date, plus every
    contract a notice names (so that a named contract with no change is reported)."""
    changes = all_kline_changes()
    attributed = attribute(changes)
    rows: dict[tuple[str, str], dict] = {}
    for r in attributed:
        if r["notice"] is None:
            continue
        rows[(r["notice"], r["symbol"])] = r
    for n in NOTICES:
        for s in n.listed or ():
            rows.setdefault((n.label, s), {"symbol": s, "notice": n.label,
                                           "notice_date": n.dates[0], "day": None})
    (CACHE / "kline_changes.json").write_text(json.dumps(
        {"attributed": attributed}, indent=0))
    return sorted(rows.values(), key=lambda r: (r["notice"], r["symbol"]))


def _anchor(row: dict) -> dt.date:
    return d_(row["day"]) if row.get("day") else d_(row["notice_date"])


def stage_treated() -> list[dict]:
    cands = treated_candidates()
    print(f"treated: {len(cands)} contract-events", file=sys.stderr)
    # make sure the +/- WINDOW kline days exist for every candidate (named contracts too)
    need = set()
    for r in cands:
        a = _anchor(r)
        for m in months_between(a - dt.timedelta(WINDOW + 1), a + dt.timedelta(WINDOW + 1)):
            if not (CACHE / "kl2h" / r["symbol"] / f"{m}.json").exists():
                need.add((r["symbol"], m))
    pmap(kline_month, sorted(need), "treated-klines")
    # day sizes for the aggTrades plan
    size_jobs = []
    for r in cands:
        a = _anchor(r)
        for off in range(-WINDOW, WINDOW + 1):
            day = a + dt.timedelta(off)
            if day <= LAST_DAY:
                size_jobs.append((r["symbol"], day.isoformat()))
    size_jobs = sorted(set(size_jobs))
    pmap(agg_size, size_jobs, "sizes")
    save_sizes()
    # Budget: the events named in the task get +/- WINDOW days, water-filled to
    # NAMED_AGG_BUDGET; every other contract-event gets its change day only, when that
    # file is at most OTHER_DAY0_MAX (the 30-minute timing), and klines for the rest.
    plans, named_totals = {}, []
    for r in cands:
        a = _anchor(r)
        sizes = {}
        for off in range(-WINDOW, WINDOW + 1):
            s = _SIZES.get(f"{r['symbol']}|{(a + dt.timedelta(off)).isoformat()}")
            if s and s <= MAX_DAY_FILE:
                sizes[off] = s
        plans[(r["notice"], r["symbol"])] = sizes
        if _named_in_task(r):
            named_totals.append(sum(sizes.values()))
    cap = waterfill_cap(named_totals, NAMED_AGG_BUDGET)
    jobs = set()
    for r in cands:
        sizes = plans[(r["notice"], r["symbol"])]
        a = _anchor(r)
        if _named_in_task(r):
            offs = plan_days(sizes, cap, DAY_PRIORITY, min_days=(0,))
        else:
            offs = [0] if sizes.get(0, math.inf) <= OTHER_DAY0_MAX else []
        for off in offs:
            jobs.add((r["symbol"], (a + dt.timedelta(off)).isoformat(), sizes[off]))
    print(f"treated: named cap {cap / 1e6:.1f} MB per contract-event, {len(jobs)} day files, "
          f"{sum(j[2] for j in jobs) / 1e6:.0f} MB planned", file=sys.stderr)
    if sum(j[2] for j in jobs) > TREATED_AGG_BUDGET:
        raise RuntimeError("treated aggTrades plan exceeds its budget")
    pmap(agg_day, sorted(jobs), "treated-agg")
    return cands


def _named_in_task(r: dict) -> bool:
    n = next(x for x in NOTICES if x.label == r["notice"])
    return n.named_in_task


def _bins_hist(rec: dict) -> list[dict[int, int]]:
    return [{int(k): v for k, v in b.items()} for b in rec["bins"]]


def _agg_day_hist(rec: dict) -> dict[int, int]:
    h: Counter = Counter()
    for b in _bins_hist(rec):
        h.update(b)
    return dict(h)


def evaluate(row: dict, extra_download: bool = True) -> dict:
    """Detection for one treated contract-event from its cached summaries."""
    sym = row["symbol"]
    notice = next(x for x in NOTICES if x.label == row["notice"])
    stated = d_(row["notice_date"])
    a = _anchor(row)
    lo, hi = min(a, stated) - dt.timedelta(WINDOW), max(a, stated) + dt.timedelta(WINDOW)
    kl = daily_series(sym, months_between(lo, hi))
    days, labels, src, prices = [], [], [], {}
    agg_days = {}
    d = lo
    while d <= hi:
        ds = d.isoformat()
        rec = None
        p = CACHE / "agg" / sym / f"{ds}.json"
        if p.exists() and p.stat().st_size > 2:
            rec = json.loads(p.read_text())
        t = None
        if rec and rec["events"] >= MIN_DAY_EVENTS:
            t = tick_exp(_agg_day_hist(rec), TICK_SHARE)
            agg_days[ds] = rec
            prices[ds] = rec["med"]
            s = "trades"
        if t is None and ds in kl:
            t = kline_day_tick(kl[ds])
            if t is not None:
                prices[ds] = kl[ds]["med"]
                s = "klines"
        if t is not None:
            days.append(ds)
            labels.append(t)
            src.append(s)
        d += dt.timedelta(1)
    out = {"symbol": sym, "event": notice.label, "listed": notice.listed is not None
           and sym in notice.listed, "notice_code": notice.code}
    out["stated_time"] = f"{stated.isoformat()} {notice.time}" if notice.time else \
        stated.isoformat()
    if notice.label.endswith("(undated)"):
        out["stated_time"] = "2026-04-10 published, no date in title"
    if not labels:
        out.update(status="no-data", detected_time="", note="no klines or trades in window")
        return out
    segs = segment_changes(labels)
    sp = None
    if segs:
        s_, o_, n_ = min(segs, key=lambda c: abs((d_(days[c[0]]) - stated).days))
        sp = (s_, o_, n_, None)
    out["other_changes_in_window"] = len(segs) - 1 if segs else 0
    pre_days = [x for x in agg_days if d_(x) < stated and (stated - d_(x)).days <= WINDOW]
    out["events_per_day_pre"] = (float(np.mean([agg_days[x]["events"] for x in pre_days]))
                                 if pre_days else float("nan"))
    out["pre_trade_days"] = len(pre_days)
    out["trade_days"] = len(agg_days)
    pre_cnt = [kl[x]["cnt"] for x in kl if 1 <= (stated - d_(x)).days <= WINDOW]
    out["trades_per_day_pre_klines"] = float(np.mean(pre_cnt)) if pre_cnt else float("nan")
    if sp is None:
        t0, _ = _mode(labels)
        pr = float(np.median(list(prices.values())))
        out.update(status="no-change", detected_time="", old_tick=fmt_tick(t0),
                   new_tick=fmt_tick(t0), direction="none",
                   rel_tick_before_bps=rel_tick_bps(t0, pr), rel_tick_after_bps=float("nan"),
                   source="trades+klines" if agg_days else "klines")
        return out
    s, old, new, _ = sp
    cday = days[s]
    out["old_exp"], out["new_exp"] = old, new
    # time: 30-minute bins of the change day (and the day before, for a change in the
    # first bin or late labelling), from trades if available, else 2h klines
    tm, tsrc = None, None
    cands_days = [days[s - 1], cday] if s > 0 else [cday]
    if extra_download:
        # the detected change day only, when the planned day was not it
        for x in cands_days[-1:]:
            if x not in agg_days:
                sz = agg_size(sym, x)
                if sz and sz <= OTHER_DAY0_MAX:
                    rec = agg_day(sym, x, sz)
                    if rec and rec["events"] >= 1:
                        agg_days[x] = rec
    bin_list, stamps = [], []
    for x in cands_days:
        if x in agg_days:
            for i, h in enumerate(_bins_hist(agg_days[x])):
                bin_list.append(h)
                stamps.append(f"{x} {i // 2:02d}:{30 * (i % 2):02d}")
    if bin_list:
        keep = [i for i, h in enumerate(bin_list) if sum(h.values()) >= 1]
        kept = [bin_list[i] for i in keep]
        cp = change_bin(kept, old, new)
        if cp is not None and 0 < cp < len(keep) and regimes_match(kept, cp, old, new):
            tm, tsrc = stamps[keep[cp]], "trades (30-minute bins)"
    if tm is None:
        kc = [c for c in kline_changes(kl) if c["old"] == old and c["new"] == new]
        if kc:
            best = min(kc, key=lambda c: abs((d_(c["day"]) - d_(cday)).days))
            tm, tsrc = best["time"], "klines (2h)"
        else:
            tm, tsrc = f"{cday} 00:00", "klines (day)"
    out["detected_time"] = tm
    det = d_(tm[:10])
    multi = [d_(x) for x in notice.dates]
    st = "verified" if any(det == x for x in multi) else "date-differs"
    if notice.label.endswith("(undated)"):
        st = "verified"  # no stated date to differ from; attribution window only
    before = [prices[x] for x in days[:s]][-WINDOW:]
    after = [prices[x] for x in days[s:]][:WINDOW]
    out.update(
        status=st, old_tick=fmt_tick(old), new_tick=fmt_tick(new), direction=direction(old, new),
        rel_tick_before_bps=rel_tick_bps(old, float(np.median(before))),
        rel_tick_after_bps=rel_tick_bps(new, float(np.median(after))),
        source=f"{tsrc}; daily ticks from {'trades+klines' if agg_days else 'klines'}",
    )
    # share of trades on the coarse grid on the trade days just before and after
    coarse = max(old, new)
    pre_sh = [grid_share(_agg_day_hist(agg_days[x]), coarse) for x in agg_days
              if d_(x) < det]
    post_sh = [grid_share(_agg_day_hist(agg_days[x]), coarse) for x in agg_days
               if d_(x) > det]
    out["coarse_share_pre"] = float(np.median(pre_sh)) if pre_sh else float("nan")
    out["coarse_share_post"] = float(np.median(post_sh)) if post_sh else float("nan")
    return out


def time_check(r: dict) -> str:
    """Compare the detected with the stated minute, at the detection's resolution."""
    st, det, src = r.get("stated_time", ""), r.get("detected_time", ""), r.get("source", "")
    if len(st) < 16 or len(det) < 16 or not st[11:13].isdigit():
        return ""
    t0 = dt.datetime.fromisoformat(st[:16])
    t1 = dt.datetime.fromisoformat(det[:16])
    tol = 30 if src.startswith("trades") else 120
    diff = (t1 - t0).total_seconds() / 60
    if src.startswith("trades"):
        if diff == 0:
            return "matches"
        # the bin after the stated one is a match only if the stated bin is already mixed
        at = r.get("coarse_share_bin_at_stated")
        if diff == 30 and at is not None:
            mixed = at < 0.99 if r.get("direction") == "cut" else at > 0.2
            if mixed:
                return "matches (switch inside the stated half hour)"
        return f"differs by {diff / 60:+.1f} h"
    ok = -tol <= diff <= tol
    return "matches (2h klines)" if ok else f"differs by {diff / 60:+.1f} h (2h klines)"


def stage_evaluate(cands: list[dict]) -> list[dict]:
    res = pmap(lambda r: evaluate(r), [(r,) for r in cands], "evaluate")
    rows = [r for _, r in res if r]
    allrec = [json.loads(p.read_text()) for p in (CACHE / "agg").glob("*/*.json")
              if p.stat().st_size > 2]
    median_bpr = float(np.median([x["zip_bytes"] / x["events"] for x in allrec
                                  if x.get("zip_bytes") and x.get("events")]))
    for r in rows:
        # share on the coarser grid in the half hour before the stated minute and in
        # the half hour that starts at it (a cut: 1.0 then lower; an increase: the reverse)
        st = r.get("stated_time", "")
        if len(st) >= 16 and st[11:13].isdigit() and r.get("old_exp") is not None:
            path = CACHE / "agg" / r["symbol"] / f"{st[:10]}.json"
            if path.exists() and path.stat().st_size > 2:
                bins = _bins_hist(json.loads(path.read_text()))
                i = int(st[11:13]) * 2 + int(st[14:16]) // 30
                coarse = max(r["old_exp"], r["new_exp"])
                r["coarse_share_bin_before_stated"] = grid_share(bins[i - 1], coarse)
                r["coarse_share_bin_at_stated"] = grid_share(bins[i], coarse)
        r["time_check"] = time_check(r)
        r["events_per_day_pre_method"] = "trades" if r.get("pre_trade_days") else ""
        if r.get("pre_trade_days") or r.get("status") == "no-data":
            continue
        # no pre-event trade day: the archive sizes of the pre-event day files divided
        # by bytes per aggTrade record (this contract's downloaded days, else the median
        # over all downloaded days)
        recs = []
        if (CACHE / "agg" / r["symbol"]).exists():
            recs = [json.loads(p.read_text()) for p in (CACHE / "agg" / r["symbol"]).glob("*.json")
                    if p.stat().st_size > 2]
        recs = [x for x in recs if x.get("zip_bytes") and x.get("events")]
        bpr = (sum(x["zip_bytes"] for x in recs) / sum(x["events"] for x in recs)) if recs \
            else median_bpr
        ref = r.get("detected_time") or r["stated_time"]
        if not ref[:4].isdigit():
            continue
        stated = d_(ref[:10])
        pre = [_SIZES.get(f"{r['symbol']}|{(stated - dt.timedelta(i)).isoformat()}")
               for i in range(1, WINDOW + 1)]
        pre = [x for x in pre if x]
        if len(pre) >= 5:
            r["events_per_day_pre"] = float(np.mean(pre)) / bpr
            r["events_per_day_pre_method"] = ("day-file bytes / bytes per record ("
                                              + ("own days" if recs else "median") + ")")
    save_sizes()
    return sorted(rows, key=lambda r: (r["event"], r["symbol"]))


def _bytes_per_day(inv: dict, sym: str, days: list[dt.date]) -> float:
    m = inv.get(sym, {})
    vals = []
    for d in days:
        key = f"{d.year:04d}-{d.month:02d}"
        if key in m:
            vals.append(m[key] / calendar.monthrange(d.year, d.month)[1])
    return float(np.mean(vals)) if len(vals) == len(days) else float("nan")


def stage_controls(treated: list[dict]) -> list[dict]:
    inv = load_inventory()
    events: dict[str, list[dict]] = {}
    for r in treated:
        if r["status"] in ("verified", "date-differs"):
            events.setdefault(r["detected_time"][:10], []).append(r)
    # every detected change anywhere (for exclusion)
    changed: dict[str, list[dt.date]] = {}
    for sym, chs in all_kline_changes().items():
        changed.setdefault(sym, []).extend(d_(c["day"]) for c in chs)
    for r in treated:
        if r["status"] in ("verified", "date-differs"):
            changed.setdefault(r["symbol"], []).append(d_(r["detected_time"][:10]))
    pairs = []
    check_jobs = set()
    per_event = {}
    for ev, trs in sorted(events.items()):
        D = d_(ev)
        pre = [D - dt.timedelta(i) for i in range(1, WINDOW + 1)]
        months = months_between(D - dt.timedelta(CONTROL_WINDOW), D + dt.timedelta(CONTROL_WINDOW))
        alive_m = [m for m in months if m <= LAST_MONTH]
        universe = [s for s in usdt_perps(inv, alive_m[0])
                    if all(m in inv[s] for m in alive_m)]
        treated_syms = {r["symbol"] for r in trs}
        cands = []
        for c in universe:
            if c in treated_syms:
                continue
            if any(abs((x - D).days) <= CONTROL_WINDOW for x in changed.get(c, [])):
                continue
            cands.append(c)
        tr_act = {}
        for r in trs:
            ser = daily_series(r["symbol"], months_between(pre[-1], pre[0]))
            cnt = [ser[x.isoformat()]["cnt"] for x in pre if x.isoformat() in ser]
            tr_act[r["symbol"]] = (float(np.mean(cnt)) if len(cnt) >= 8 else float("nan"),
                                   _bytes_per_day(inv, r["symbol"], pre))
        # prefilter on inventory bytes, then klines trade counts (cached scan months)
        matches = {r["symbol"]: [] for r in trs}
        pre_months = months_between(pre[-1], pre[0])
        for c in cands:
            cb = _bytes_per_day(inv, c, pre)
            hits = [t for t, (_, tb) in tr_act.items() if within_factor(cb, tb)]
            if not hits:
                continue
            ser = daily_series(c, pre_months)
            if not all((CACHE / "kl2h" / c / f"{m}.json").exists() for m in pre_months):
                for m in pre_months:
                    kline_month(c, m)
                ser = daily_series(c, pre_months)
            cnt = [ser[x.isoformat()]["cnt"] for x in pre if x.isoformat() in ser]
            if len(cnt) < 8:
                continue
            cc = float(np.mean(cnt))
            for ts_ in hits:
                tc, tb = tr_act[ts_]
                if within_factor(cc, tc):
                    dist = abs(math.log(cc / tc)) + abs(math.log(cb / tb))
                    matches[ts_].append((dist, c, cc, cb))
        per_event[ev] = (trs, tr_act, matches)
        for ts_, ms in matches.items():
            for _, c, _, _ in sorted(ms)[:CONTROLS_CHECKED_PER_TREATED]:
                for m in months:
                    check_jobs.add((c, m))
    todo = [j for j in sorted(check_jobs) if not (CACHE / "kl2h" / j[0] / f"{j[1]}.json").exists()]
    print(f"controls: {len(todo)} kline months to fetch for stability", file=sys.stderr)
    pmap(kline_month, todo, "controls-klines")
    sample_jobs = {}
    for ev, (trs, tr_act, matches) in per_event.items():
        D = d_(ev)
        months = months_between(D - dt.timedelta(CONTROL_WINDOW), D + dt.timedelta(CONTROL_WINDOW))
        for r in trs:
            ts_ = r["symbol"]
            rank = 0
            for dist, c, cc, cb in sorted(matches[ts_])[:CONTROLS_CHECKED_PER_TREATED]:
                ser = {k: v for k, v in daily_series(c, months).items()
                       if abs((d_(k) - D).days) <= CONTROL_WINDOW}
                labels = [kline_day_tick(v) for v in ser.values()]
                labels = [x for x in labels if x is not None]
                if len(labels) < 20:
                    continue
                stable = not segment_changes(labels)
                mode, cnt = _mode(labels)
                stable = stable and cnt >= 0.9 * len(labels)
                if not stable:
                    continue
                rank += 1
                pre_prices = [ser[x.isoformat()]["med"] for x in
                              [D - dt.timedelta(i) for i in range(1, WINDOW + 1)]
                              if x.isoformat() in ser and "med" in ser[x.isoformat()]]
                price = float(np.median(pre_prices)) if pre_prices else float("nan")
                tc, tb = tr_act[ts_]
                pair = {
                    "event_date": ev, "treated_symbol": ts_, "control_symbol": c, "rank": rank,
                    "treated_trades_per_day_pre": round(tc, 1),
                    "control_trades_per_day_pre": round(cc, 1),
                    "trades_ratio": round(cc / tc, 3), "bytes_ratio": round(cb / tb, 3),
                    "treated_events_per_day_pre": r.get("events_per_day_pre"),
                    "control_events_per_day_pre_est": (r.get("events_per_day_pre") or
                                                       float("nan")) * cb / tb,
                    "control_tick": fmt_tick(mode),
                    "control_rel_tick_bps": rel_tick_bps(mode, price) if not math.isnan(price)
                    else float("nan"),
                    "kline_days_checked": len(labels),
                    "window_days": f"{max(-CONTROL_WINDOW, (min(d_(k) for k in ser) - D).days)}"
                                   f" to {(max(d_(k) for k in ser) - D).days}",
                    "trade_check": "not sampled", "_exp": mode,
                }
                pairs.append(pair)
                if rank <= CONTROLS_TRADE_SAMPLED_PER_TREATED:
                    sample_jobs.setdefault((c, ev), []).append(pair)
    # light trade check: the event day of the top-ranked control per treated contract
    budget = CONTROL_AGG_BUDGET
    sizes = {k: agg_size(*k) for k in sorted(sample_jobs)}
    # smallest files first, so the budget covers as many treated contracts as possible
    order = sorted(sample_jobs, key=lambda k: (sizes[k] or 0, k))
    jobs = []
    for c, ev in order:
        sz = sizes[(c, ev)]
        if not sz or sz > CONTROL_SAMPLE_MAX_FILE:
            for p in sample_jobs[(c, ev)]:
                p["trade_check"] = "skipped (file over 25 MB)" if sz else "no file"
            continue
        if sz > budget:
            for p in sample_jobs[(c, ev)]:
                p["trade_check"] = "skipped (budget)"
            continue
        budget -= sz
        jobs.append((c, ev, sz))
    save_sizes()
    res = {(c, ev): r for (c, ev, _), r in pmap(agg_day, jobs, "controls-agg")}
    for (c, ev), rec in res.items():
        for p in sample_jobs[(c, ev)]:
            if not rec:
                p["trade_check"] = "no file"
                continue
            ticks = [tick_exp(h, TICK_SHARE, MIN_BIN_EVENTS) for h in _bins_hist(rec)]
            ticks = [t for t in ticks if t is not None]
            day_t = tick_exp(_agg_day_hist(rec), TICK_SHARE)
            bad = sum(t != p["_exp"] for t in ticks)
            # thin bins can misread the tick, so test for a change instead: no split of
            # the day into an old-tick part and a 10x finer or coarser part fits
            hs = [h for h in _bins_hist(rec) if sum(h.values())]
            moved = False
            for new in (p["_exp"] - 1, p["_exp"] + 1):
                cp = change_bin(hs, p["_exp"], new)
                moved |= bool(cp and 0 < cp < len(hs) and regimes_match(hs, cp, p["_exp"], new))
            ok = day_t == p["_exp"] and not moved
            p["trade_check"] = (f"ok ({len(ticks)} bins)" if ok else
                                f"FAILED (day tick {fmt_tick(day_t) if day_t is not None else '?'}"
                                f", {bad} of {len(ticks)} bins off)")
            p["control_events_on_event_day"] = rec["events"]
    for p in pairs:
        p.pop("_exp", None)
    return pairs


# ----------------------------------------------------------------------------------------
# Outputs
# ----------------------------------------------------------------------------------------
TICK_COLS = ["symbol", "stated_time", "detected_time", "old_tick", "new_tick", "direction",
             "rel_tick_before_bps", "rel_tick_after_bps", "events_per_day_pre", "status",
             "source", "time_check", "event", "listed_in_notes", "notice_code", "trade_days",
             "pre_trade_days", "events_per_day_pre_method", "trades_per_day_pre_klines", "coarse_share_pre",
             "coarse_share_post", "coarse_share_bin_before_stated", "coarse_share_bin_at_stated"]


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    import csv

    def fmt(v):
        if isinstance(v, float):
            return "" if math.isnan(v) else f"{v:.6g}"
        if isinstance(v, bool):
            return "yes" if v else "no"
        return "" if v is None else v

    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow([fmt(r.get(c)) for c in cols])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("stage", choices=["scan", "treated", "controls", "all"])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    if args.stage in ("scan", "all"):
        stage_scan()
    if args.stage in ("treated", "all"):
        cands = stage_treated()
        rows = stage_evaluate(cands)
        for r in rows:
            r["listed_in_notes"] = r.pop("listed", False)
        (CACHE / "treated_rows.json").write_text(json.dumps(rows, indent=0, default=str))
        write_csv(OUT / "tick_events.csv", rows, TICK_COLS)
    if args.stage in ("controls", "all"):
        rows = json.loads((CACHE / "treated_rows.json").read_text())
        pairs = stage_controls(rows)
        (CACHE / "control_rows.json").write_text(json.dumps(pairs, indent=0, default=str))
        cols = ["event_date", "treated_symbol", "control_symbol", "rank",
                "treated_trades_per_day_pre", "control_trades_per_day_pre", "trades_ratio",
                "bytes_ratio", "treated_events_per_day_pre", "control_events_per_day_pre_est",
                "control_tick", "control_rel_tick_bps", "kline_days_checked", "window_days",
                "trade_check", "control_events_on_event_day"]
        write_csv(OUT / "tick_event_controls.csv", pairs, cols)
    print(f"downloaded in total: {ledger().total / 1e6:.0f} MB", file=sys.stderr)


if __name__ == "__main__":
    main()
