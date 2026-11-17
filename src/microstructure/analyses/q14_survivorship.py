"""Q14: survivorship. Is next-trade-sign predictability different for contracts
that were later delisted, or listed after 2023, once activity is controlled for?

Q9 and Q10 fitted their ladder on 10 liquid contracts that exist in all five
study months (2023-06, 2023-07, 2024-07, 2025-07, 2026-07). That conditions on
survival and on liquidity. Q14 refits Q9's within-month ladder, unchanged
(same day split, caps and LightGBM settings: `q9_sign_prediction.fit_symbol`
with its defaults), on three sets of symbol-months:

  cross_2023  every coin with a 2023-06 archive file (survivors, renamed,
              merged and delisted contracts; index contracts are listed only)
  last_month  the last complete month of every contract that later stopped
              trading (delisted, renamed or merged)
  cross_2026  every 2023 contract alive in 2026-07, plus a size-stratified
              random sample of contracts first listed after 2023-06

The universe comes from `data/universe/aggtrades_monthly_inventory.json`, a
listing of the data.binance.vision USDT-M monthly aggTrades archive. The
archive's last month for a symbol is taken as the month its futures contract
stopped trading.

Stages:
  universe  classify every perpetual and draw the new-listing sample
            (cache: <cache>/universe.json)
  fit       per unit: download the monthly zip (SHA-256 verified), ingest to
            the normal parquet layout, check the month is complete and active
            enough, run Q9's `fit_symbol`, then delete the zip, the ladder
            pickle and the parquet (only a parquet this stage created: a
            parquet that existed before Q14 first ran is never deleted). One
            status JSON per unit under <cache>/units/, so the stage resumes.
  report    build results/q14_survivorship.{json,md,png} from the caches only

Symbols, not days, are the resampling unit for every interval here.
This is a study of order-flow predictability, not a trading result.
"""
from __future__ import annotations

import argparse
import calendar
import concurrent.futures as cf
import gc
import json
import math
import shutil
import time
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path

import numpy as np
import polars as pl

from microstructure.analyses import q14_report
from microstructure.analyses.q9_sign_prediction import DEFAULT_SYMBOLS as Q9_SYMBOLS
from microstructure.analyses.q9_sign_prediction import (
    fit_cache_path,
    fit_symbol,
    ladder_path,
    run_config,
)
from microstructure.data.binance import DumpFile, download
from microstructure.data.catalog import parquet_path
from microstructure.data.ingest import ingest_agg_trades
from microstructure.data.jsonio import dumps_strict
from microstructure.ml.dataset import split_masks
from microstructure.ml.evaluate import MS_PER_DAY
from microstructure.ml.features import WARMUP
from microstructure.ml.ladder import LINEAR_ORDER, TRAIN_CAP, same_ladder
from microstructure.signals.load import load_events

CROSS_2023 = "2023-06"
CROSS_2026 = "2026-07"
STUDY_MONTHS = ("2023-06", "2023-07", "2024-07", "2025-07", "2026-07")
INVENTORY = Path("universe") / "aggtrades_monthly_inventory.json"
SETS = ("cross_2023", "last_month", "cross_2026")

# --------------------------------------------------------------------------
# Classification of the 2023 contracts that stopped trading
# --------------------------------------------------------------------------
# Evidence. The inventory has no file at or after 2026-07 for 49 perpetuals
# that have a 2023-06 file. For the renamed contracts the successor ticker's
# first archive month is within two months of the old ticker's last month
# (checked in `classify_2023`, reported as successor_lag_months); these are
# token migrations or rebrands announced by the projects (RNDR to RENDER,
# MATIC to POL, GAL to G, FTM to S (Sonic), MKR to SKY, EOS to A (Vaulta),
# DAR to D, BNX to FORM, FXS to FRAX, KLAY to KAIA). AGIX and OCEAN were
# merged into FET (the ASI alliance merger of 2024), whose contract predates
# them. BLUEBIRD, FOOTBALL and DEFI are Binance index perpetuals, not single
# coins. Everything else is a delisting; that includes TOMOUSDT, whose
# successor VICUSDT only appears 15 months later, so the contract itself ended.
RENAMED = {
    "RNDRUSDT": "RENDERUSDT", "MATICUSDT": "POLUSDT", "GALUSDT": "GUSDT",
    "FTMUSDT": "SUSDT", "MKRUSDT": "SKYUSDT", "EOSUSDT": "AUSDT", "DARUSDT": "DUSDT",
    "BNXUSDT": "FORMUSDT", "FXSUSDT": "FRAXUSDT", "KLAYUSDT": "KAIAUSDT",
}
MERGED = {"AGIXUSDT": "FETUSDT", "OCEANUSDT": "FETUSDT"}
INDEX_CONTRACTS = ("BLUEBIRDUSDT", "FOOTBALLUSDT", "DEFIUSDT")
DELISTED = (
    "ALPHAUSDT", "AMBUSDT", "ANTUSDT", "ATAUSDT", "AUDIOUSDT", "BAKEUSDT", "BALUSDT",
    "BLZUSDT", "COMBOUSDT", "DENTUSDT", "DGBUSDT", "FLMUSDT", "HIGHUSDT", "HOOKUSDT",
    "IDEXUSDT", "KEYUSDT", "LEVERUSDT", "LINAUSDT", "LRCUSDT", "NKNUSDT", "OMGUSDT",
    "PERPUSDT", "PHBUSDT", "RADUSDT", "RDNTUSDT", "REEFUSDT", "RENUSDT", "STMXUSDT",
    "SXPUSDT", "TOMOUSDT", "TRUUSDT", "UNFIUSDT", "WAVESUSDT", "XEMUSDT",
)
SUCCESSOR_MAX_LAG = 2  # months between the old ticker's last file and the successor's first

# Status of a 2023-06 contract, and the comparison groups built from them.
ENDED_STATUSES = ("delisted", "renamed", "merged")
GROUPS_2023 = {
    "survivors": ("survivor", "survivor_gap"),
    "delisted": ("delisted",),
    "renamed_merged": ("renamed", "merged"),
    "ended": ENDED_STATUSES,
}
GROUPS_2026 = {"survivors_2023": ("survivor", "survivor_gap"), "new_listings": ("new_listing",),
               # Listed, summarised and plotted, but not pooled with the crypto contracts.
               "new_listings_equity": ("new_listing_equity",)}

# --------------------------------------------------------------------------
# Unit rules
# --------------------------------------------------------------------------
# Minimum activity. Q9's ladder needs scoreable rows in all three blocks of the
# day split. LightGBM's num_leaves=63 with min_data_in_leaf=500 needs about
# 31,500 rows to grow one full tree, so the train block must hold well above
# that; the test block must be large enough that one unit's accuracy has a
# binomial standard error of at most 0.005 (10,000 rows).
MIN_TRAIN_SCOREABLE = 50_000
MIN_VALID_SCOREABLE = 5_000
MIN_TEST_ROWS = 10_000
# A month is complete when the contract traded on its first and last UTC day
# and on every day in between except at most one. Q9's split counts days from
# the first event, so a month that starts late would shift the test block.
MAX_MISSING_DAYS = 1
LAST_MONTH_MAX_BACK = 3  # candidate months tried for the last complete month
# Equity perpetuals. In 2026 Binance listed perpetuals on stock tokens, some on
# reused crypto tickers (MDTUSDT trades near 93 from 2026-10-21). They follow
# the US equity week, so they are flagged from the unit's own trade times and
# kept out of the crypto new-listing group. Both signals are medians over
# days, so a few burst days (a pump on five weekdays, as COTIUSDT had in
# 2026-07) cannot flip them: the median weekend day against the median weekday
# (about 0.7 to 1 for a crypto contract) and the median weekday share of events
# in the US cash session (13:30 to 20:00 UTC in July; 6.5 / 24 = 0.27 for a
# flat round-the-clock day).
EQUITY_WEEKEND_RATIO_MAX = 0.25
EQUITY_US_SESSION_MIN = 0.60
US_SESSION_UTC_MIN = (13 * 60 + 30, 20 * 60)  # EDT; the 2026-07 cross-section only
SESSION_VERSION = 2
N_BOOT = 2000
SAMPLE_DECILES = 10
SAMPLE_PER_DECILE = 10
SAMPLE_SEED = 0
MIN_FREE_BYTES = 2_500_000_000
LOOKAHEAD = 3
COMPARE_METRICS = ("gbm_all", "lift", "gbm_minus_linear", "linear")
PRIMARY_METRIC = "gbm_all"


def month_add(period: str, k: int) -> str:
    y, m = int(period[:4]), int(period[5:7])
    t = y * 12 + (m - 1) + k
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def months_between(a: str, b: str) -> int:
    """Number of months from a to b (b later is positive)."""
    return (int(b[:4]) * 12 + int(b[5:7])) - (int(a[:4]) * 12 + int(a[5:7]))


# --------------------------------------------------------------------------
# Universe
# --------------------------------------------------------------------------


def perpetuals(inventory: dict) -> dict[str, dict[str, int]]:
    """USDT-margined perpetuals: tickers ending in USDT with no underscore
    (dated quarterly contracts carry an underscore and an expiry)."""
    return {s: m for s, m in inventory.items() if s.endswith("USDT") and "_" not in s}


def classify_2023(perps: dict[str, dict[str, int]]) -> dict[str, dict]:
    """Status of every perpetual with a 2023-06 file.

    survivor      a file in every study month
    survivor_gap  alive in 2026-07 but missing a middle study month
    relisted      no 2026-07 file but a later one (stopped, then came back)
    delisted / renamed / merged / index   no file at or after 2026-07
    Raises if the constants above no longer match the inventory.
    """
    out: dict[str, dict] = {}
    ended_found: set[str] = set()
    for sym in sorted(s for s, m in perps.items() if CROSS_2023 in m):
        months = sorted(perps[sym])
        entry = {
            "symbol": sym, "first_month": months[0], "last_month": months[-1],
            "missing_study_months": [m for m in STUDY_MONTHS if m not in perps[sym]],
            "zip_bytes_2023_06": perps[sym][CROSS_2023],
            "q9_symbol": sym in Q9_SYMBOLS,
        }
        if not entry["missing_study_months"]:
            entry["status"] = "survivor"
        elif CROSS_2026 in perps[sym]:
            entry["status"] = "survivor_gap"
        elif any(m > CROSS_2026 for m in months):
            entry["status"] = "relisted"
            after = [m for m in months if m > CROSS_2023]
            gaps = [(a, b) for a, b in pairwise(after)
                    if months_between(a, b) > 1]
            entry["gaps"] = [{"after": a, "resumes": b} for a, b in gaps]
        else:
            ended_found.add(sym)
            if sym in RENAMED or sym in MERGED:
                succ = RENAMED.get(sym) or MERGED[sym]
                entry["status"] = "renamed" if sym in RENAMED else "merged"
                entry["successor"] = succ
                s_months = sorted(perps.get(succ, {}))
                entry["successor_first_month"] = s_months[0] if s_months else None
                entry["successor_alive_2026_07"] = CROSS_2026 in perps.get(succ, {})
                if sym in RENAMED:
                    lag = months_between(months[-1], s_months[0]) if s_months else None
                    entry["successor_lag_months"] = lag
                    entry["successor_verified"] = lag is not None and 0 <= lag <= SUCCESSOR_MAX_LAG
            elif sym in INDEX_CONTRACTS:
                entry["status"] = "index"
            elif sym in DELISTED:
                entry["status"] = "delisted"
            else:
                raise ValueError(f"{sym} stopped trading but is not classified in Q14's constants")
        out[sym] = entry
    named = set(RENAMED) | set(MERGED) | set(INDEX_CONTRACTS) | set(DELISTED)
    if named != ended_found:
        raise ValueError(
            "Q14's ended-contract constants do not match the inventory: "
            f"listed but not ended {sorted(named - ended_found)}, "
            f"ended but not listed {sorted(ended_found - named)}")
    unverified = [s for s, e in out.items() if e["status"] == "renamed"
                  and not e["successor_verified"]]
    if unverified:
        raise ValueError(f"renamed contracts without a successor within "
                         f"{SUCCESSOR_MAX_LAG} months: {unverified}")
    return out


def stratified_sample(sizes: dict[str, int], n_bins: int = SAMPLE_DECILES,
                      per_bin: int = SAMPLE_PER_DECILE, seed: int = SAMPLE_SEED) -> list[dict]:
    """Equal-count random draw from each size quantile bin.

    Symbols are ranked by size (ties by name), bin b holds ranks
    [b n / n_bins, (b + 1) n / n_bins), and each bin is shuffled with one
    generator seeded once, then its first `per_bin` symbols are taken. Each bin
    holds 1 / n_bins of the population and gets the same number of draws, so
    the sample is self-weighting. The draw is nested: a larger `per_bin` with
    the same seed keeps every symbol of a smaller one.
    """
    syms = sorted(sizes, key=lambda s: (sizes[s], s))
    n = len(syms)
    rng = np.random.default_rng(seed)
    out: list[dict] = []
    for b in range(n_bins):
        members = syms[b * n // n_bins:(b + 1) * n // n_bins]
        order = rng.permutation(len(members))
        for i in sorted(order[:per_bin].tolist()):
            out.append({"symbol": members[i], "decile": b, "zip_bytes": int(sizes[members[i]])})
    return out


def build_universe(inventory: dict, per_decile: int = SAMPLE_PER_DECILE,
                   seed: int = SAMPLE_SEED) -> dict:
    perps = perpetuals(inventory)
    c23 = classify_2023(perps)
    new_all = sorted(s for s, m in perps.items() if min(m) > CROSS_2023 and CROSS_2026 in m)
    # A contract first listed in 2026-07 has a partial July; it cannot be scored
    # on a complete month, so it is outside the sampling frame (and counted).
    frame = [s for s in new_all if min(perps[s]) < CROSS_2026]
    sample = stratified_sample({s: perps[s][CROSS_2026] for s in frame},
                               per_bin=per_decile, seed=seed)
    sizes = np.array([perps[s][CROSS_2026] for s in frame], dtype=np.float64)
    edges = [float(np.quantile(sizes, q / SAMPLE_DECILES)) for q in range(SAMPLE_DECILES + 1)]
    ended = [s for s, e in c23.items() if e["status"] in ENDED_STATUSES]
    # Candidates for the last complete month, and the month before each, whose
    # zip sizes are reported next to the coverage check.
    lm = {s: sorted(perps[s], reverse=True)[:LAST_MONTH_MAX_BACK + 1] for s in ended}
    return {
        "archive_last_month": max(m for v in perps.values() for m in v),
        "n_perpetuals": len(perps),
        "contracts_2023_06": c23,
        "new_listings": {
            "n_total": len(new_all),
            "n_listed_in_2026_07": len(new_all) - len(frame),
            "listed_in_2026_07": [s for s in new_all if s not in frame],
            "n_frame": len(frame),
            "frame_zip_gb": float(sizes.sum() / 1e9),
            "decile_edges_zip_bytes": edges,
            "per_decile": per_decile,
            "seed": seed,
            "sample": sample,
        },
        "last_month_candidates": {
            s: sorted(perps[s], reverse=True)[:LAST_MONTH_MAX_BACK] for s in ended
        },
        "zip_bytes": {s: {m: perps[s][m] for m in sorted(perps[s])
                          if m in (CROSS_2023, CROSS_2026) or m in lm.get(s, ())}
                      for s in sorted(set(c23) | {d["symbol"] for d in sample})},
    }


# --------------------------------------------------------------------------
# Month completeness, activity and the last-full-month rule
# --------------------------------------------------------------------------


def month_start_day(period: str) -> int:
    """UTC day index (days since epoch) of the first day of the month."""
    y, m = int(period[:4]), int(period[5:7])
    return int(np.datetime64(f"{y:04d}-{m:02d}-01", "D").astype(np.int64))


def coverage(period: str, ts_ms: np.ndarray) -> dict:
    """Which days of the month the contract traded on (day of month, 1-based)."""
    n_days = calendar.monthrange(int(period[:4]), int(period[5:7]))[1]
    if ts_ms.size == 0:
        return {"days_in_month": n_days, "n_days": 0, "first_day": None, "last_day": None}
    dom = np.unique(np.asarray(ts_ms, dtype=np.int64) // MS_PER_DAY) - month_start_day(period) + 1
    dom = dom[(dom >= 1) & (dom <= n_days)]
    return {"days_in_month": n_days, "n_days": int(dom.size),
            "first_day": int(dom.min()) if dom.size else None,
            "last_day": int(dom.max()) if dom.size else None}


def is_complete(cov: dict | None) -> bool:
    if not cov or cov["n_days"] == 0:
        return False
    return (cov["first_day"] == 1 and cov["last_day"] == cov["days_in_month"]
            and cov["n_days"] >= cov["days_in_month"] - MAX_MISSING_DAYS)


def choose_last_full_month(candidates_desc: list[str], checked: dict[str, dict | None]
                           ) -> tuple[str, str | None]:
    """Next step of the last-full-month rule.

    Walk the contract's archive months from the last one backwards, at most
    LAST_MONTH_MAX_BACK of them. Returns ("chosen", month) for the first month
    whose coverage is complete, ("check", month) when that month's coverage is
    not known yet, and ("none", None) when every candidate was checked and none
    is complete. `checked` maps a month to its coverage (None: no data).
    """
    for m in candidates_desc[:LAST_MONTH_MAX_BACK]:
        if m not in checked:
            return "check", m
        if is_complete(checked[m]):
            return "chosen", m
    return "none", None


def session_profile(ts_ms: np.ndarray) -> dict:
    """Weekly and intraday shape of a unit's trading, from its trade times.

    weekend_ratio      median events on a UTC Saturday or Sunday over the median
                       events on a weekday
    us_session_median  median over weekdays of the share of the day's events in
                       the US cash session
    weekend_share and us_session_share are the plain monthly shares, for reference.
    """
    ts_ms = np.asarray(ts_ms, dtype=np.int64)
    out = {"version": SESSION_VERSION, "weekend_share": None, "us_session_share": None,
           "weekend_ratio": None, "us_session_median": None}
    if ts_ms.size == 0:
        return out
    day = ts_ms // MS_PER_DAY
    weekday = (day + 3) % 7                         # 1970-01-01 was a Thursday; Monday = 0
    minute = (ts_ms % MS_PER_DAY) // 60_000
    lo, hi = US_SESSION_UTC_MIN
    in_us = (minute >= lo) & (minute < hi)
    out["weekend_share"] = float((weekday >= 5).mean())
    out["us_session_share"] = float((in_us & (weekday < 5)).mean())
    days = np.arange(day.min(), day.max() + 1)
    n = np.bincount(day - day.min(), minlength=days.size).astype(np.float64)
    n_us = np.bincount(day - day.min(), weights=in_us, minlength=days.size)
    wd = (days + 3) % 7
    week, wkend = n[wd < 5], n[wd >= 5]
    if week.size and np.median(week) > 0:
        out["weekend_ratio"] = float(np.median(wkend) / np.median(week)) if wkend.size else None
        busy = (wd < 5) & (n > 0)
        out["us_session_median"] = float(np.median(n_us[busy] / n[busy]))
    return out


def is_equity_like(profile: dict | None) -> bool:
    if not profile or profile.get("us_session_median") is None:
        return False
    low_weekend = (profile["weekend_ratio"] is not None
                   and profile["weekend_ratio"] < EQUITY_WEEKEND_RATIO_MAX)
    return low_weekend or profile["us_session_median"] >= EQUITY_US_SESSION_MIN


def activity_counts(ts_ms: np.ndarray) -> dict:
    """Scoreable rows per block of Q9's split, as `SignDataset.rows` counts them."""
    ts_ms = np.asarray(ts_ms, dtype=np.int64)
    scoreable = np.ones(ts_ms.size, dtype=bool)
    scoreable[1:] = ts_ms[1:] != ts_ms[:-1]
    scoreable[:WARMUP] = False
    if ts_ms.size == 0:
        return {"n_events": 0, "n_train_scoreable": 0, "n_valid_scoreable": 0,
                "n_test_rows": 0}
    train, valid, test = split_masks(ts_ms)
    return {"n_events": int(ts_ms.size),
            "n_train_scoreable": int((train & scoreable).sum()),
            "n_valid_scoreable": int((valid & scoreable).sum()),
            "n_test_rows": int((test & scoreable).sum())}


def activity_reason(c: dict) -> str | None:
    """Why a unit is too thin for Q9's split, or None if it is not."""
    short = []
    if c["n_train_scoreable"] < MIN_TRAIN_SCOREABLE:
        short.append(f"{c['n_train_scoreable']:,} train rows < {MIN_TRAIN_SCOREABLE:,}")
    if c["n_valid_scoreable"] < MIN_VALID_SCOREABLE:
        short.append(f"{c['n_valid_scoreable']:,} validation rows < {MIN_VALID_SCOREABLE:,}")
    if c["n_test_rows"] < MIN_TEST_ROWS:
        short.append(f"{c['n_test_rows']:,} test rows < {MIN_TEST_ROWS:,}")
    return "too few scoreable events: " + ", ".join(short) if short else None


# --------------------------------------------------------------------------
# Workspace, parquet safety, unit processing
# --------------------------------------------------------------------------


class Workspace:
    """Paths of one Q14 run. `root` is the repo's data directory."""

    def __init__(self, root: Path, cache: Path | None = None):
        self.root = Path(root)
        self.cache = Path(cache) if cache is not None else self.root / "ml_cache" / "q14"
        self.units = self.cache / "units"
        self.raw = self.root / "raw" / "q14"
        self.universe = self.cache / "universe.json"
        self.snapshot = self.cache / "preexisting_parquet.json"
        self.ledger = self.cache / "created_parquet.txt"

    def rel(self, p: Path) -> str:
        p = Path(p)
        try:
            return str(p.resolve().relative_to(self.root.resolve()))
        except ValueError:
            return str(p.resolve())

    def resolve(self, s: str) -> Path:
        p = Path(s)
        return p if p.is_absolute() else self.root / p

    def status_path(self, symbol: str, period: str) -> Path:
        return self.units / f"{symbol}_{period}.json"

    def read_status(self, symbol: str, period: str) -> dict | None:
        p = self.status_path(symbol, period)
        return json.loads(p.read_text()) if p.exists() else None

    def write_status(self, st: dict) -> None:
        self.units.mkdir(parents=True, exist_ok=True)
        self.status_path(st["symbol"], st["period"]).write_text(dumps_strict(st))

    # Parquet safety. A snapshot of every parquet under root/parquet is taken
    # the first time the fit stage runs; a path in it is never deleted. A path
    # is deletable only if it is also in the ledger, written just before this
    # stage ingests a file there.
    def ensure_snapshot(self) -> set[str]:
        if not self.snapshot.exists():
            self.cache.mkdir(parents=True, exist_ok=True)
            files = sorted(self.rel(p) for p in (self.root / "parquet").rglob("*.parquet"))
            self.snapshot.write_text(dumps_strict({"taken_unix": time.time(), "files": files}))
        return set(json.loads(self.snapshot.read_text())["files"])

    def ledger_entries(self) -> set[str]:
        if not self.ledger.exists():
            return set()
        return {ln.strip() for ln in self.ledger.read_text().splitlines() if ln.strip()}

    def record_created(self, p: Path) -> None:
        self.cache.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a") as fh:
            fh.write(self.rel(p) + "\n")

    def may_delete(self, p: Path) -> bool:
        r = self.rel(p)
        return r in self.ledger_entries() and r not in self.ensure_snapshot()


def delete_if_created(ws: Workspace, p: Path) -> bool:
    """Delete a parquet only if Q14 created it; returns whether it was deleted."""
    if p.exists() and ws.may_delete(p):
        p.unlink()
        return True
    return False


def ingest_zip(ws: Workspace, zip_path: Path, symbol: str, period: str) -> Path:
    """Ingest into the normal parquet layout, verified before the final rename."""
    dest = parquet_path(ws.root, symbol, "aggTrades", period)
    dest.parent.mkdir(parents=True, exist_ok=True)
    ws.record_created(dest)
    produced = ingest_agg_trades(zip_path, dest.parent)
    try:
        pl.scan_parquet(produced).select(pl.len()).collect()
    except Exception:
        produced.unlink(missing_ok=True)
        raise
    produced.rename(dest)
    return dest


def q9_reusable(root: Path, symbol: str, period: str) -> Path | None:
    """Q9's own fit cache for this unit, if it was made with the settings Q14
    uses and from the ladder now on disk; None means refit into Q14's cache."""
    q9_cache = Path(root) / "ml_cache"
    p = fit_cache_path(q9_cache, symbol, period)
    if symbol not in Q9_SYMBOLS or not p.exists():
        return None
    rec = json.loads(p.read_text())
    expected = json.loads(dumps_strict(run_config(LINEAR_ORDER, TRAIN_CAP, None)))
    if rec.get("config") != expected:
        return None
    if not same_ladder(rec, ladder_path(q9_cache, symbol, period)):
        return None
    return p


def default_fit(ws: Workspace, symbol: str, period: str, keep_ladder: bool) -> Path:
    path = fit_symbol(ws.root, symbol, period, cache=ws.cache)
    if not keep_ladder:
        lp = ladder_path(ws.cache, symbol, period)
        lp.unlink(missing_ok=True)
        if lp.parent.exists() and not any(lp.parent.iterdir()):
            lp.parent.rmdir()
    return path


FINAL = ("ok", "skipped", "partial")


def run_unit(ws: Workspace, symbol: str, period: str, fetch: Callable[[str, str], Path], *,
             fit: Callable[[Workspace, str, str], Path] | None = None,
             keep_ladder: bool = False, need_session: bool = False) -> dict:
    """Process one symbol-month and write its status. Final statuses:
    ok (fitted), skipped (too few scoreable events), partial (incomplete
    month); failed is retried on the next run."""
    st = ws.read_status(symbol, period)
    if st and st["status"] in FINAL:
        if need_session and (st.get("session") or {}).get("version") != SESSION_VERSION:
            return backfill_session(ws, st, fetch)
        return st
    ws.ensure_snapshot()
    fit = fit or (lambda w, s, p: default_fit(w, s, p, keep_ladder))
    p = parquet_path(ws.root, symbol, "aggTrades", period)
    st = {"symbol": symbol, "period": period, "status": "failed", "reason": None,
          "reused_q9_cache": False, "record": None, "parquet_preexisting": None}
    zip_path: Path | None = None
    t0 = time.time()
    try:
        st["parquet_preexisting"] = p.exists() and not ws.may_delete(p)
        if not p.exists():
            zip_path = fetch(symbol, period)
            ingest_zip(ws, zip_path, symbol, period)
            zip_path.unlink(missing_ok=True)
        ts = load_events(ws.root, symbol, [period])["ts"].dt.epoch("ms").to_numpy()
        st["coverage"] = coverage(period, ts)
        st["counts"] = activity_counts(ts)
        st["session"] = session_profile(ts)
        st["equity_like"] = is_equity_like(st["session"])
        del ts
        reason = activity_reason(st["counts"])
        if not is_complete(st["coverage"]):
            c = st["coverage"]
            st["status"], st["reason"] = "partial", (
                f"incomplete month: traded on {c['n_days']} of {c['days_in_month']} days, "
                f"days {c['first_day']} to {c['last_day']}")
        elif reason:
            st["status"], st["reason"] = "skipped", reason
        else:
            reuse = q9_reusable(ws.root, symbol, period)
            rec_path = reuse if reuse is not None else fit(ws, symbol, period)
            st["reused_q9_cache"] = reuse is not None
            st["record"] = ws.rel(rec_path)
            st["status"] = "ok"
    except Exception as exc:  # noqa: BLE001 - recorded in the status, retried next run
        st["status"], st["reason"] = "failed", f"{type(exc).__name__}: {exc}"
    finally:
        if zip_path is not None:
            zip_path.unlink(missing_ok=True)
        st["parquet_deleted"] = delete_if_created(ws, p)
        st["seconds"] = round(time.time() - t0, 1)
        gc.collect()
    ws.write_status(st)
    return st


def backfill_session(ws: Workspace, st: dict, fetch: Callable[[str, str], Path]) -> dict:
    """Add the session profile to a unit finished before it was recorded,
    without refitting: fetch, ingest, read the trade times, clean up."""
    symbol, period = st["symbol"], st["period"]
    p = parquet_path(ws.root, symbol, "aggTrades", period)
    zip_path: Path | None = None
    try:
        if not p.exists():
            zip_path = fetch(symbol, period)
            ingest_zip(ws, zip_path, symbol, period)
        ts = load_events(ws.root, symbol, [period])["ts"].dt.epoch("ms").to_numpy()
        st["session"] = session_profile(ts)
        st["equity_like"] = is_equity_like(st["session"])
        ws.write_status(st)
    finally:
        if zip_path is not None:
            zip_path.unlink(missing_ok=True)
        delete_if_created(ws, p)
    return st


class Prefetcher:
    """Download zips a few units ahead on a small thread pool."""

    def __init__(self, raw_dir: Path, workers: int = 3, retries: int = 3):
        self.raw = raw_dir
        self.raw.mkdir(parents=True, exist_ok=True)
        self.ex = cf.ThreadPoolExecutor(max_workers=workers)
        self.futs: dict[tuple[str, str], cf.Future] = {}
        self.retries = retries

    def _download(self, symbol: str, period: str) -> Path:
        err: Exception | None = None
        for attempt in range(self.retries):
            try:
                return download(DumpFile(symbol, "aggTrades", period), self.raw)
            except Exception as exc:  # noqa: BLE001 - network hiccup or checksum: retry
                err = exc
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"download failed after {self.retries} tries: {err}") from err

    def want(self, symbol: str, period: str) -> None:
        if (symbol, period) not in self.futs:
            self.futs[(symbol, period)] = self.ex.submit(self._download, symbol, period)

    def __call__(self, symbol: str, period: str) -> Path:
        self.want(symbol, period)
        return self.futs.pop((symbol, period)).result()

    def close(self) -> None:
        self.ex.shutdown(wait=True, cancel_futures=True)
        for f in self.raw.glob("*.zip"):
            f.unlink(missing_ok=True)
        for f in self.raw.glob("*.part"):
            f.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Fit stage
# --------------------------------------------------------------------------


def plan(universe: dict, sets: tuple[str, ...] = SETS) -> list[dict]:
    """Ordered tasks: the 2023-06 set first, then last months, then 2026-07."""
    c23 = universe["contracts_2023_06"]
    tasks: list[dict] = []
    if "cross_2023" in sets:
        tasks += [{"set": "cross_2023", "symbol": s, "period": CROSS_2023}
                  for s, e in c23.items() if e["status"] != "index"]
    if "last_month" in sets:
        tasks += [{"set": "last_month", "symbol": s,
                   "candidates": universe["last_month_candidates"][s]}
                  for s, e in c23.items() if e["status"] in ENDED_STATUSES]
    if "cross_2026" in sets:
        old = [s for s, e in c23.items() if e["status"] in ("survivor", "survivor_gap")]
        new = [d["symbol"] for d in universe["new_listings"]["sample"]]
        tasks += [{"set": "cross_2026", "symbol": s, "period": CROSS_2026} for s in old + new]
    return tasks


def _checked(ws: Workspace, symbol: str, candidates: list[str]) -> dict[str, dict | None]:
    out: dict[str, dict | None] = {}
    for m in candidates:
        st = ws.read_status(symbol, m)
        if st and st["status"] in FINAL:
            out[m] = st.get("coverage")
    return out


def _next_period(ws: Workspace, task: dict) -> str | None:
    """The unit this task still needs processed, or None if the task is done."""
    if task["set"] != "last_month":
        st = ws.read_status(task["symbol"], task["period"])
        done = st and st["status"] in FINAL and (
            task["set"] != "cross_2026"
            or (st.get("session") or {}).get("version") == SESSION_VERSION)
        return None if done else task["period"]
    step, m = choose_last_full_month(task["candidates"], _checked(ws, task["symbol"],
                                                                   task["candidates"]))
    if step == "check":
        return m
    if step == "chosen":
        st = ws.read_status(task["symbol"], m)
        return None if st and st["status"] in FINAL else m
    return None


def run_fit(ws: Workspace, universe: dict, sets: tuple[str, ...] = SETS,
            max_units: int | None = None, workers: int = 3,
            keep_ladders: bool = False) -> list[dict]:
    tasks = plan(universe, sets)
    pre = Prefetcher(ws.raw, workers=workers)
    done_now: list[dict] = []
    try:
        i = 0
        while i < len(tasks):
            period = _next_period(ws, tasks[i])
            if period is None:
                i += 1
                continue
            if max_units is not None and len(done_now) >= max_units:
                break
            free = shutil.disk_usage(ws.root).free
            if free < MIN_FREE_BYTES:
                raise RuntimeError(f"only {free / 1e9:.1f} GB free; stopping before "
                                   f"{tasks[i]['symbol']} {period}")
            # Prefetch the next few units whose parquet is not on disk yet.
            ahead = 0
            for t in tasks[i + 1:]:
                if ahead >= LOOKAHEAD:
                    break
                q = _next_period(ws, t)
                if q is None:
                    continue
                ahead += 1
                if not parquet_path(ws.root, t["symbol"], "aggTrades", q).exists():
                    pre.want(t["symbol"], q)
            st = run_unit(ws, tasks[i]["symbol"], period, pre, keep_ladder=keep_ladders,
                          need_session=tasks[i]["set"] == "cross_2026")
            done_now.append(st)
            print(f"[q14 fit] {tasks[i]['set']} {st['symbol']} {st['period']}: {st['status']}"
                  f"{' (' + st['reason'] + ')' if st['reason'] else ''} {st['seconds']}s",
                  flush=True)
            if st["status"] == "failed" or tasks[i]["set"] != "last_month":
                i += 1
            # A last-month task loops on itself until _next_period says it is done.
    finally:
        pre.close()
    return done_now


# --------------------------------------------------------------------------
# Statistics (pure functions; symbols are the resampling unit)
# --------------------------------------------------------------------------


def ci_state(lo: float, hi: float) -> str:
    if lo > 0:
        return "positive"
    if hi < 0:
        return "negative"
    return "zero"


def ols_hc1(y: np.ndarray, X: np.ndarray) -> dict:
    """OLS with HC1 heteroskedasticity-robust standard errors. X includes the
    intercept column."""
    y = np.asarray(y, dtype=np.float64)
    X = np.asarray(X, dtype=np.float64)
    n, k = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    e = y - X @ beta
    meat = (X * (e ** 2)[:, None]).T @ X
    cov = xtx_inv @ meat @ xtx_inv * (n / max(n - k, 1))
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float((e ** 2).sum()) / tss if tss > 0 else float("nan")
    return {"beta": beta.tolist(), "se": se.tolist(), "r2": r2, "n": int(n)}


def _interval(est: float, se: float) -> dict:
    lo, hi = est - 1.96 * se, est + 1.96 * se
    return {"estimate": float(est), "se": float(se), "ci95": [float(lo), float(hi)],
            "state": ci_state(lo, hi)}


def _boot_interval(est: float, draws: np.ndarray) -> dict:
    draws = draws[np.isfinite(draws)]
    lo, hi = np.percentile(draws, [2.5, 97.5]) if draws.size else (np.nan, np.nan)
    return {"estimate": float(est), "ci95": [float(lo), float(hi)],
            "state": ci_state(lo, hi) if draws.size else "zero"}


def group_effect(y_t, x_t, y_c, x_c) -> dict:
    """Coefficient on the treated dummy in y = a + b log_events + d treated."""
    y = np.concatenate([y_t, y_c])
    x = np.concatenate([x_t, x_c])
    d = np.concatenate([np.ones(len(y_t)), np.zeros(len(y_c))])
    fit = ols_hc1(y, np.column_stack([np.ones_like(x), x, d]))
    out = _interval(fit["beta"][2], fit["se"][2])
    out["slope_log_events"] = float(fit["beta"][1])
    out["n"] = fit["n"]
    return out


def match_nearest(x_t: np.ndarray, x_c: np.ndarray) -> np.ndarray:
    """Index of the control with the nearest x for every treated unit, with
    replacement (a control can serve several treated units); ties go to the
    lower index."""
    x_t, x_c = np.asarray(x_t, dtype=np.float64), np.asarray(x_c, dtype=np.float64)
    return np.abs(x_t[:, None] - x_c[None, :]).argmin(axis=1)


def matched_diff(y_t, x_t, y_c, x_c) -> tuple[float, float]:
    """(mean treated-minus-matched-control difference, mean |log gap| of the pairs)."""
    y_t, x_t, y_c, x_c = (np.asarray(a, dtype=np.float64) for a in (y_t, x_t, y_c, x_c))
    j = match_nearest(x_t, x_c)
    return float(np.mean(y_t - y_c[j])), float(np.mean(np.abs(x_t - x_c[j])))


def compare_groups(y_t, x_t, y_c, x_c, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """Raw median difference, the activity-controlled OLS dummy and a matched
    comparison of a treated group against a control group of symbols."""
    y_t, x_t, y_c, x_c = (np.asarray(a, dtype=np.float64) for a in (y_t, x_t, y_c, x_c))
    out = {"n_treat": int(y_t.size), "n_ctrl": int(y_c.size),
           "median_treat": float(np.median(y_t)) if y_t.size else None,
           "median_ctrl": float(np.median(y_c)) if y_c.size else None,
           "median_log10_events_treat": float(np.median(x_t)) if x_t.size else None,
           "median_log10_events_ctrl": float(np.median(x_c)) if x_c.size else None}
    if y_t.size < 2 or y_c.size < 2:
        out.update(raw=None, ols=None, matched=None)
        return out
    rng = np.random.default_rng(seed)
    it = rng.integers(0, y_t.size, size=(n_boot, y_t.size))
    ic = rng.integers(0, y_c.size, size=(n_boot, y_c.size))
    raw_draws = np.median(y_t[it], axis=1) - np.median(y_c[ic], axis=1)
    out["raw"] = _boot_interval(out["median_treat"] - out["median_ctrl"], raw_draws)
    out["ols"] = group_effect(y_t, x_t, y_c, x_c)
    est, gap = matched_diff(y_t, x_t, y_c, x_c)
    m_draws = np.array([matched_diff(y_t[a], x_t[a], y_c[b], x_c[b])[0]
                        for a, b in zip(it, ic, strict=True)])
    out["matched"] = _boot_interval(est, m_draws)
    out["matched"].update(replace=True, mean_abs_log10_gap=gap)
    return out


def paired_change(y_last, y_first, x_last, x_first, n_boot: int = N_BOOT,
                  seed: int = 0) -> dict:
    """Within-contract change from 2023-06 to the last month.

    The median and mean change get symbol-bootstrap intervals; the intercept
    of change = a + b * (change in log10 events) is the change at no change in
    activity, with an HC1 interval."""
    d = np.asarray(y_last, dtype=np.float64) - np.asarray(y_first, dtype=np.float64)
    dx = np.asarray(x_last, dtype=np.float64) - np.asarray(x_first, dtype=np.float64)
    out = {"n": int(d.size), "median_dlog10_events": float(np.median(dx)) if d.size else None}
    if d.size < 3:
        out.update(median=None, mean=None, controlled=None)
        return out
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(n_boot, d.size))
    out["median"] = _boot_interval(float(np.median(d)), np.median(d[idx], axis=1))
    out["mean"] = _boot_interval(float(np.mean(d)), np.mean(d[idx], axis=1))
    fit = ols_hc1(d, np.column_stack([np.ones_like(dx), dx]))
    out["controlled"] = _interval(fit["beta"][0], fit["se"][0])
    out["controlled"]["slope_dlog10_events"] = float(fit["beta"][1])
    out["controlled"]["slope_se"] = float(fit["se"][1])
    out["n_up"] = int((d > 0).sum())
    out["n_down"] = int((d < 0).sum())
    return out


def percentile_rank(values, x: float) -> float:
    """Percent of `values` below x, counting ties as half."""
    v = np.asarray(values, dtype=np.float64)
    return float(100.0 * ((v < x).sum() + 0.5 * (v == x).sum()) / v.size)


def activity_slope(y, x) -> dict:
    fit = ols_hc1(np.asarray(y, dtype=np.float64),
                  np.column_stack([np.ones(len(x)), np.asarray(x, dtype=np.float64)]))
    return {"intercept": fit["beta"][0], "slope": fit["beta"][1], "slope_se": fit["se"][1],
            "r2": fit["r2"], "n": fit["n"],
            "state": ci_state(fit["beta"][1] - 1.96 * fit["se"][1],
                              fit["beta"][1] + 1.96 * fit["se"][1])}


# --------------------------------------------------------------------------
# Report stage (caches only)
# --------------------------------------------------------------------------

RUNG_ACC = ("majority", "persistence", "linear", "gbm_all")


def unit_metrics(rec: dict) -> dict:
    acc = {r: float(rec["scores"][r]["accuracy"]) for r in RUNG_ACC}
    lift = acc["gbm_all"] - acc["majority"]
    return {
        **acc,
        "n_events": int(rec["counts"]["n_events"]),
        "log10_events": math.log10(rec["counts"]["n_events"]),
        "n_test_rows": int(rec["counts"]["n_test_rows"]),
        "lift": lift,
        # Q9's rule: the share is only defined when the lift is above 0.005.
        "linear_share": (acc["linear"] - acc["majority"]) / lift if lift > 0.005 else None,
        "gbm_minus_linear": acc["gbm_all"] - acc["linear"],
    }


def _med(v: list) -> float | None:
    v = [x for x in v if x is not None and np.isfinite(x)]
    return float(np.median(v)) if v else None


def group_summary(units: list[dict]) -> dict:
    return {"n": len(units),
            "median_events": _med([u["n_events"] for u in units]),
            **{f"median_{k}": _med([u[k] for u in units]) for k in
               (*RUNG_ACC, "lift", "linear_share", "gbm_minus_linear", "log10_events")}}


def _arrays(units: list[dict], metric: str) -> tuple[np.ndarray, np.ndarray]:
    return (np.array([u[metric] for u in units], dtype=np.float64),
            np.array([u["log10_events"] for u in units], dtype=np.float64))


def _comparison(treat: list[dict], ctrl: list[dict], n_boot: int) -> dict:
    out = {}
    for k, metric in enumerate(COMPARE_METRICS):
        yt, xt = _arrays(treat, metric)
        yc, xc = _arrays(ctrl, metric)
        out[metric] = compare_groups(yt, xt, yc, xc, n_boot=n_boot, seed=k)
    return out


def build_result(ws: Workspace, n_boot: int = N_BOOT) -> dict:
    universe = json.loads(ws.universe.read_text())
    c23 = universe["contracts_2023_06"]
    sample = universe["new_listings"]["sample"]
    tasks = plan(universe)

    units: list[dict] = []        # every planned unit with its outcome
    last_month: dict[str, dict] = {}
    for t in tasks:
        sym = t["symbol"]
        status = c23[sym]["status"] if sym in c23 else "new_listing"
        if t["set"] == "last_month":
            checked = _checked(ws, sym, t["candidates"])
            step, chosen = choose_last_full_month(t["candidates"], checked)
            attempts = []
            for m in t["candidates"]:
                st = ws.read_status(sym, m)
                if st is None:
                    continue
                attempts.append({"period": m, "status": st["status"], "reason": st["reason"],
                                 "coverage": st.get("coverage"),
                                 "zip_bytes": universe["zip_bytes"][sym].get(m)})
            last_month[sym] = {"archive_last_month": t["candidates"][0], "step": step,
                               "chosen": chosen, "attempts": attempts}
            period = chosen
            if period is None:
                units.append({"set": "last_month", "symbol": sym, "status_2023": status,
                              "period": None, "outcome": "failed" if step == "check"
                              else "no_complete_month",
                              "reason": ("not processed yet" if step == "check" else
                                         f"none of the last {LAST_MONTH_MAX_BACK} archive "
                                         "months is complete"), "counts": None})
                continue
        else:
            period = t["period"]
        st = ws.read_status(sym, period)
        u = {"set": t["set"], "symbol": sym, "status_2023": status, "period": period,
             "q9_symbol": sym in Q9_SYMBOLS}
        if st is None:
            u.update(outcome="not_run", reason="not processed yet", counts=None)
        else:
            u.update(outcome=st["status"], reason=st["reason"], counts=st.get("counts"),
                     coverage=st.get("coverage"), reused_q9_cache=st.get("reused_q9_cache"))
            if t["set"] == "cross_2026":
                u["session"] = st.get("session")
                u["equity_like"] = st.get("equity_like")
                if st.get("equity_like"):
                    u["status_2023"] = status = f"{status}_equity"
            if st["status"] == "ok":
                rec = json.loads(ws.resolve(st["record"]).read_text())
                u["metrics"] = unit_metrics(rec)
                u["record"] = st["record"]
        if status.startswith("new_listing"):
            u["decile"] = next(d["decile"] for d in sample if d["symbol"] == sym)
        units.append(u)

    def fitted(set_name: str, statuses: tuple[str, ...]) -> list[dict]:
        return [dict(u["metrics"], symbol=u["symbol"]) for u in units
                if u["set"] == set_name and u["status_2023"] in statuses and "metrics" in u]

    groups_2023 = {g: fitted("cross_2023", st) for g, st in GROUPS_2023.items()}
    full_2023 = [dict(u["metrics"], symbol=u["symbol"], status=u["status_2023"]) for u in units
                 if u["set"] == "cross_2023" and "metrics" in u]
    groups_2026 = {g: fitted("cross_2026", st) for g, st in GROUPS_2026.items()}
    groups_last = {g: fitted("last_month", st) for g, st in GROUPS_2023.items()
                   if g != "survivors"}

    comparisons = {
        "delisted_vs_survivors_2023": _comparison(groups_2023["delisted"],
                                                  groups_2023["survivors"], n_boot),
        "renamed_merged_vs_survivors_2023": _comparison(groups_2023["renamed_merged"],
                                                        groups_2023["survivors"], n_boot),
        "ended_vs_survivors_2023": _comparison(groups_2023["ended"], groups_2023["survivors"],
                                               n_boot),
        "new_vs_survivors_2026": _comparison(groups_2026["new_listings"],
                                             groups_2026["survivors_2023"], n_boot),
    }

    # Paired: last complete month against 2023-06, same contract.
    first = {u["symbol"]: u for u in groups_2023["ended"]}
    pairs = [(first[u["symbol"]], u) for u in groups_last["ended"] if u["symbol"] in first]
    paired: dict = {"symbols": [a["symbol"] for a, _ in pairs], "by_metric": {},
                    "by_group": {}}
    for k, metric in enumerate(COMPARE_METRICS):
        paired["by_metric"][metric] = paired_change(
            [b[metric] for _, b in pairs], [a[metric] for a, _ in pairs],
            [b["log10_events"] for _, b in pairs], [a["log10_events"] for a, _ in pairs],
            n_boot=n_boot, seed=k)
    for g in ("delisted", "renamed_merged"):
        syms = {u["symbol"] for u in groups_2023[g]}
        sub = [(a, b) for a, b in pairs if a["symbol"] in syms]
        paired["by_group"][g] = paired_change(
            [b[PRIMARY_METRIC] for _, b in sub], [a[PRIMARY_METRIC] for a, _ in sub],
            [b["log10_events"] for _, b in sub], [a["log10_events"] for a, _ in sub],
            n_boot=n_boot, seed=11)
    paired["rows"] = [
        {"symbol": a["symbol"], "period": next(u["period"] for u in units
                                               if u["set"] == "last_month"
                                               and u["symbol"] == a["symbol"]),
         "events_2023": a["n_events"], "events_last": b["n_events"],
         **{f"{m}_2023": a[m] for m in COMPARE_METRICS},
         **{f"{m}_last": b[m] for m in COMPARE_METRICS}}
        for a, b in pairs]

    # Where the Q9 symbols sit.
    surv = groups_2023["survivors"]
    q9 = [u for u in full_2023 if u["symbol"] in Q9_SYMBOLS]
    q9_rows = []
    for u in q9:
        q9_rows.append({
            "symbol": u["symbol"], "n_events": u["n_events"], "gbm_all": u["gbm_all"],
            "linear": u["linear"], "lift": u["lift"],
            "pct_events_survivors": percentile_rank([v["log10_events"] for v in surv],
                                                    u["log10_events"]),
            "pct_events_full": percentile_rank([v["log10_events"] for v in full_2023],
                                               u["log10_events"]),
            "pct_gbm_all_survivors": percentile_rank([v["gbm_all"] for v in surv],
                                                     u["gbm_all"]),
            "pct_gbm_all_full": percentile_rank([v["gbm_all"] for v in full_2023],
                                                u["gbm_all"]),
        })
    rng = np.random.default_rng(99)
    q9_pos: dict = {"rows": q9_rows, "n_full": len(full_2023), "n_survivors": len(surv),
                    "metrics": {}}
    for metric in ("gbm_all", "linear", "lift", "log10_events"):
        full_v = np.array([u[metric] for u in full_2023], dtype=np.float64)
        q9_v = np.array([u[metric] for u in q9], dtype=np.float64)
        if full_v.size < 2 or q9_v.size == 0:
            continue
        idx = rng.integers(0, full_v.size, size=(n_boot, full_v.size))
        q9_med = float(np.median(q9_v))
        q9_pos["metrics"][metric] = {
            "median_q9": q9_med,
            "median_full": _boot_interval(float(np.median(full_v)),
                                          np.median(full_v[idx], axis=1)),
            "median_survivors": _med([u[metric] for u in surv]),
            "q9_median_pct_full": percentile_rank(full_v, q9_med),
            "share_full_below_q9_median": float((full_v < q9_med).mean()),
        }
    # How much of the gap the activity gradient alone would predict.
    activity = {m: activity_slope([u[m] for u in full_2023],
                                  [u["log10_events"] for u in full_2023])
                for m in COMPARE_METRICS} if len(full_2023) >= 3 else {}
    if activity and "gbm_all" in q9_pos["metrics"]:
        dlog = (q9_pos["metrics"]["log10_events"]["median_q9"]
                - q9_pos["metrics"]["log10_events"]["median_full"]["estimate"])
        q9_pos["activity_predicted_gap_gbm_all"] = activity["gbm_all"]["slope"] * dlog
        q9_pos["dlog10_events_q9_vs_full"] = dlog
    activity_2026 = {g: activity_slope([u[PRIMARY_METRIC] for u in groups_2026[g]],
                                       [u["log10_events"] for u in groups_2026[g]])
                     for g in GROUPS_2026 if len(groups_2026[g]) >= 3}

    counts: dict = {}
    for set_name in SETS:
        for u in units:
            if u["set"] != set_name:
                continue
            key = f"{set_name}:{u['status_2023']}"
            c = counts.setdefault(key, {})
            c[u["outcome"]] = c.get(u["outcome"], 0) + 1

    result = {
        "question": ("Is next-trade-sign predictability different for contracts that were "
                     "later delisted, and for contracts listed after 2023, once trading "
                     "activity is controlled for? How unrepresentative are Q9's 10 symbols?"),
        "universe": universe,
        "rules": {
            "min_train_scoreable": MIN_TRAIN_SCOREABLE, "min_valid_scoreable": MIN_VALID_SCOREABLE,
            "min_test_rows": MIN_TEST_ROWS, "max_missing_days": MAX_MISSING_DAYS,
            "last_month_max_back": LAST_MONTH_MAX_BACK, "n_boot": n_boot,
            "primary_metric": PRIMARY_METRIC, "compare_metrics": list(COMPARE_METRICS),
            "q9_config": run_config(LINEAR_ORDER, TRAIN_CAP, None),
        },
        "units": units,
        "equity_screen": {
            "rule": {"weekend_ratio_below": EQUITY_WEEKEND_RATIO_MAX,
                     "us_session_median_at_least": EQUITY_US_SESSION_MIN,
                     "us_session_utc_minutes": list(US_SESSION_UTC_MIN)},
            "flagged": [{"symbol": u["symbol"], "status": u["status_2023"],
                         **(u.get("session") or {})}
                        for u in units if u["set"] == "cross_2026" and u.get("equity_like")],
            "n_screened": sum(1 for u in units if u["set"] == "cross_2026"
                              and u.get("session") is not None),
            "n_cross_2026": sum(1 for u in units if u["set"] == "cross_2026"),
        },
        "outcome_counts": counts,
        "last_month_resolution": last_month,
        "groups": {
            "cross_2023": {g: group_summary(v) for g, v in groups_2023.items()},
            "cross_2023_full": group_summary(full_2023),
            "cross_2023_q9": group_summary(q9),
            "last_month": {g: group_summary(v) for g, v in groups_last.items()},
            "cross_2026": {g: group_summary(v) for g, v in groups_2026.items()},
        },
        "comparisons": comparisons,
        "paired_last_vs_2023": paired,
        "q9_position": q9_pos,
        "activity_relation_2023": activity,
        "activity_relation_2026": activity_2026,
    }
    result["verdict"] = q14_report.verdict_paragraph(result)
    return result


def run_report(ws: Workspace, out_dir: Path, n_boot: int = N_BOOT) -> dict:
    result = build_result(ws, n_boot)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "q14_survivorship.json").write_text(dumps_strict(result))
    q14_report.write_markdown(out_dir / "q14_survivorship.md", result)
    q14_report.plot(out_dir / "q14_survivorship.png", result)
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Q14: survivorship in next-trade-sign prediction")
    ap.add_argument("--root", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--cache", type=Path, default=None, help="default: ROOT/ml_cache/q14")
    ap.add_argument("--stages", nargs="+", choices=("universe", "fit", "report"),
                    default=["universe", "fit", "report"])
    ap.add_argument("--sets", nargs="+", choices=SETS, default=list(SETS))
    ap.add_argument("--sample-per-decile", type=int, default=SAMPLE_PER_DECILE)
    ap.add_argument("--seed", type=int, default=SAMPLE_SEED)
    ap.add_argument("--max-units", type=int, default=None,
                    help="stop after this many newly processed units (testing)")
    ap.add_argument("--download-workers", type=int, default=3)
    ap.add_argument("--keep-ladders", action="store_true",
                    help="keep Q14's ladder pickles (default: delete, keep the JSON scores)")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    ws = Workspace(args.root, args.cache)
    if "universe" in args.stages:
        inv = json.loads((args.root / INVENTORY).read_text())
        uni = build_universe(inv, per_decile=args.sample_per_decile, seed=args.seed)
        ws.cache.mkdir(parents=True, exist_ok=True)
        ws.universe.write_text(dumps_strict(uni))
        print(f"[q14 universe] {len(uni['contracts_2023_06'])} contracts in 2023-06, "
              f"{len(uni['new_listings']['sample'])} new listings sampled")
    if "fit" in args.stages:
        uni = json.loads(ws.universe.read_text())
        run_fit(ws, uni, tuple(args.sets), args.max_units, args.download_workers,
                args.keep_ladders)
    if "report" in args.stages:
        result = run_report(ws, args.out, args.n_boot)
        print(result["verdict"])


if __name__ == "__main__":
    main()
