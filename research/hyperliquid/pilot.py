"""Data-quality pilot for the Hyperliquid skill-vs-luck project (step 3 of the plan).

This script measures whether the free per-wallet data is good enough for the flagship luck
test. It deliberately computes **no** skill, return or ranking statistic: every number it
reports is about coverage, spacing, retention, consistency or cost.

Three commands, all idempotent:

``sample``
    Load the frozen formation leaderboard, check its sha256, draw the reproducible random
    sample and print how the sample's allTime volume and accountValue compare with the cohort.

``fetch``
    For each sampled wallet, pull ``portfolio``, ``userNonFundingLedgerUpdates`` (paged),
    ``userFillsByTime`` (paged), ``subAccounts`` and ``userRole`` from the public info
    endpoint. Requests are paced by a sliding-window weight budget, retried with exponential
    backoff, and every raw response is cached under ``data/hyperliquid/pilot/raw/`` so reruns
    make no network calls.

``summarize``
    Read the cache only and write per-wallet data-quality metrics
    (``wallet_metrics.jsonl``) and aggregate tables (``summary.json``, ``summary.md``).

Usage (from the repo root)::

    uv run python research/hyperliquid/pilot.py sample
    uv run python research/hyperliquid/pilot.py fetch --n 200
    uv run python research/hyperliquid/pilot.py summarize --n 200

``--n all`` runs the same code on the whole cohort; ``--out`` moves the cache.

Sampling rule (fixed before any wallet was fetched): sort the cohort's unique lowercase
addresses, then ``numpy.random.default_rng(20261119).choice(n_cohort, size=n,
replace=False)``. The seed is the formation date. Sorting first makes the sample independent
of row order in the file; the file itself is pinned by its sha256.

Pagination: ``userFillsByTime`` and ``userNonFundingLedgerUpdates`` return up to 2,000 rows
**oldest first** from ``startTime``. Passing ``endTime`` does not reverse the order (probed
2026-11-20: ``startTime=0, endTime=T`` returns the oldest rows before ``T``), so the earliest
retained fill is reached by paging forward from ``startTime=0`` with ``startTime = last
time`` (inclusive), and duplicates at page boundaries are dropped by key. All paged calls
share one fixed ``endTime`` (the run's ``as_of_ms``, written to ``run.json`` on the first
fetch) so that the pull is a snapshot as of one moment and reruns hit the cache exactly.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import random
import sys
import time
from collections import Counter, deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
INFO_URL = "https://api.hyperliquid.xyz/info"
FORMATION = ROOT / "data/hyperliquid/formation/leaderboard_20261119T235851Z.json.gz"
FORMATION_SHA256 = "ac669f966b7ddbd4a4e5aa8ac50781c9a8d9f51a071ac3c062812046217c1a37"
FORMATION_MS = 1_795_132_731_000  # 2026-11-19T23:58:51Z, from the snapshot file name
SEED = 20261119
DEFAULT_N = 200
DEFAULT_OUT = ROOT / "data/hyperliquid/pilot"

PAGE_SIZE = 2000  # rows per call for both paged endpoints
DOC_BUDGET_PER_MIN = 1200  # documented weight per minute per IP (DATA.md, section 0)
PACE_FRACTION = 0.65  # stay well under the documented budget
# Documented base weights (DATA.md): userRole 60, the other per-wallet calls 20.
BASE_WEIGHT = {
    "portfolio": 20,
    "userNonFundingLedgerUpdates": 20,
    "userFillsByTime": 20,
    "subAccounts": 20,
    "userRole": 60,
}
# Endpoints that add ceil(items / 20) weight per response (DATA.md).
PER_ITEM_WEIGHT = {"userFillsByTime"}
RETRY_STATUS = {429, 500, 502, 503, 504}
WINDOWS = ("day", "week", "month", "allTime", "perpDay", "perpWeek", "perpMonth", "perpAllTime")


# ---------------------------------------------------------------------------------------------
# Cohort and sampling (pure)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_cohort(path: Path = FORMATION, expected_sha256: str = FORMATION_SHA256) -> list[dict]:
    """Return the frozen leaderboard rows after checking the file hash."""
    got = sha256_file(path)
    if got != expected_sha256:
        raise SystemExit(f"{path.name}: sha256 {got} != frozen {expected_sha256}; refusing")
    with gzip.open(path) as f:
        return json.load(f)["leaderboardRows"]


def cohort_table(rows: Iterable[dict]) -> dict[str, dict[str, float]]:
    """Map lowercase address to the leaderboard fields used by the pilot.

    Keeps accountValue and the allTime window only. If an address appears twice, the first
    row wins (the frozen file has none, but the full cohort run should not silently merge).
    """
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        addr = r["ethAddress"].lower()
        if addr in out:
            continue
        perf = dict(r["windowPerformances"])
        at = perf.get("allTime", {})
        out[addr] = {
            "accountValue": float(r["accountValue"]),
            "pnl": float(at.get("pnl", "nan")),
            "vlm": float(at.get("vlm", "nan")),
        }
    return out


def draw_sample(addresses: Iterable[str], n: int | None, seed: int = SEED) -> list[str]:
    """Reproducible simple random sample without replacement.

    Addresses are lowercased, deduplicated and sorted before drawing, so the result depends
    only on the set of addresses, ``n`` and ``seed``. ``n=None`` or ``n >= len`` returns the
    whole sorted set. The order of the returned list is the draw order.
    """
    pool = sorted({a.lower() for a in addresses})
    if n is None or n >= len(pool):
        return pool
    idx = np.random.default_rng(seed).choice(len(pool), size=n, replace=False)
    return [pool[i] for i in idx]


def quantiles(x: Sequence[float], qs: Sequence[float] = (0.1, 0.25, 0.5, 0.75, 0.9, 0.99)):
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {str(q): None for q in qs}
    return {str(q): float(np.quantile(a, q)) for q in qs}


def ks_statistic(a: Sequence[float], b: Sequence[float]) -> float:
    """Two-sample Kolmogorov-Smirnov distance sup |F_a - F_b| (no scipy dependency)."""
    a = np.sort(np.asarray(a, dtype=float))
    b = np.sort(np.asarray(b, dtype=float))
    grid = np.concatenate([a, b])
    fa = np.searchsorted(a, grid, side="right") / a.size
    fb = np.searchsorted(b, grid, side="right") / b.size
    return float(np.max(np.abs(fa - fb)))


def ks_critical(n1: int, n2: int, alpha: float = 0.05) -> float:
    """Asymptotic two-sample KS critical value, c(alpha) * sqrt((n1 + n2) / (n1 n2))."""
    c = math.sqrt(-0.5 * math.log(alpha / 2))
    return c * math.sqrt((n1 + n2) / (n1 * n2))


def sample_vs_cohort(table: dict[str, dict[str, float]], sample: Sequence[str]) -> dict:
    """Representativeness of the sample on allTime volume and accountValue."""
    out: dict[str, Any] = {"n_cohort": len(table), "n_sample": len(sample)}
    for key in ("vlm", "accountValue"):
        coh = [v[key] for v in table.values()]
        smp = [table[a][key] for a in sample]
        out[key] = {
            "cohort_quantiles": quantiles(coh),
            "sample_quantiles": quantiles(smp),
            "cohort_share_zero": float(np.mean(np.asarray(coh) == 0)),
            "sample_share_zero": float(np.mean(np.asarray(smp) == 0)),
            "ks": ks_statistic(coh, smp),
            "ks_crit_5pct": ks_critical(len(coh), len(smp)),
        }
    return out


# ---------------------------------------------------------------------------------------------
# Request weight, pacing and pagination (pure or clock-injected)


def request_weight(req_type: str, n_items: int = 0) -> int:
    """Documented weight of one info call that returned ``n_items`` rows."""
    w = BASE_WEIGHT.get(req_type, 20)
    if req_type in PER_ITEM_WEIGHT:
        w += math.ceil(n_items / 20)
    return w


class WeightLimiter:
    """Sliding 60 s window over spent weight.

    ``acquire(w)`` blocks until spending ``w`` more keeps the window at or under
    ``budget``; ``charge(w)`` books weight that is only known after the response (the
    per-item part of fill pages). The clock and sleep are injectable for tests.
    """

    def __init__(self, budget: float, window_s: float = 60.0,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.budget, self.window_s = budget, window_s
        self.clock, self.sleep = clock, sleep
        self.events: deque[tuple[float, float]] = deque()
        self.waited_s = 0.0

    def _spent(self, now: float) -> float:
        while self.events and self.events[0][0] <= now - self.window_s:
            self.events.popleft()
        return sum(w for _, w in self.events)

    def acquire(self, w: float) -> None:
        while True:
            now = self.clock()
            if self._spent(now) + w <= self.budget or not self.events:
                self.events.append((now, w))
                return
            wait = self.events[0][0] + self.window_s - now + 0.01
            self.waited_s += wait
            self.sleep(wait)

    def charge(self, w: float) -> None:
        if w > 0:
            self.events.append((self.clock(), w))


@dataclass
class PageResult:
    rows: list[dict]
    pages: int
    truncated: bool = False  # stopped by max_pages before the end
    stuck_steps: int = 0  # full pages whose rows all shared the start ms (start was bumped 1 ms)
    flags: list[str] = field(default_factory=list)


def fill_key(f: dict) -> tuple:
    """A fill is identified by its trade id and the user's order id.

    ``tid`` alone identifies a trade; the ``oid`` guards against the (rare) case where one
    wallet sits on both sides of a trade, which would legitimately give two fills per tid.
    """
    return (f.get("tid"), f.get("oid"))


def ledger_key(r: dict) -> tuple:
    return (r.get("time"), r.get("hash"), json.dumps(r.get("delta"), sort_keys=True))


def dedupe(rows: Iterable[dict], key: Callable[[dict], tuple]) -> list[dict]:
    """Drop repeated rows (first occurrence wins), preserving order."""
    seen: set[tuple] = set()
    out = []
    for r in rows:
        k = key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def paginate(fetch_page: Callable[[int], list[dict]], key: Callable[[dict], tuple],
             start_ms: int = 0, page_size: int = PAGE_SIZE, max_pages: int | None = None,
             time_key: str = "time") -> PageResult:
    """Page an oldest-first endpoint forward from ``start_ms`` and stitch the pages.

    The next request starts at the last row's time (inclusive), because several rows can
    share one millisecond; boundary duplicates are removed with ``key``. Stops on a short
    page or at ``max_pages`` (``truncated=True``). If a full page adds no new row or has
    every row at the start millisecond, the start moves 1 ms past it and the step is counted
    in ``stuck_steps`` (rows beyond one page in that millisecond would be lost).
    """
    rows: list[dict] = []
    seen: set[tuple] = set()
    res = PageResult(rows=rows, pages=0)
    start = start_ms
    while True:
        page = fetch_page(start)
        res.pages += 1
        new = 0
        for r in page:
            k = key(r)
            if k not in seen:
                seen.add(k)
                rows.append(r)
                new += 1
        if len(page) < page_size:
            break
        if max_pages is not None and res.pages >= max_pages:
            res.truncated = True
            break
        last = max(int(r[time_key]) for r in page)
        if last > start and new > 0:
            start = last
        else:  # a full page inside one millisecond: step past it and record the gap risk
            res.stuck_steps += 1
            res.flags.append(f"stuck_at_{start}")
            start = max(start, last) + 1
    rows.sort(key=lambda r: int(r[time_key]))
    return res


# ---------------------------------------------------------------------------------------------
# Cached HTTP client


def cache_name(body: dict) -> str:
    """Readable, deterministic cache file name for one request body."""
    parts = [body["type"]]
    if "startTime" in body:
        parts.append(f"s{body['startTime']}")
    if "endTime" in body:
        parts.append(f"e{body['endTime']}")
    return "_".join(parts) + ".json.gz"


class InfoClient:
    """POST /info with a disk cache, weight pacing and retries.

    Each cached file holds the request body, HTTP status, fetch time, latency, retries, the
    documented weight and the parsed response, so cost statistics survive reruns.
    """

    def __init__(self, raw_dir: Path, limiter: WeightLimiter | None = None,
                 url: str = INFO_URL, max_tries: int = 8, timeout_s: float = 60.0,
                 offline: bool = False):
        self.raw_dir, self.url, self.max_tries = raw_dir, url, max_tries
        self.limiter = limiter or WeightLimiter(DOC_BUDGET_PER_MIN * PACE_FRACTION)
        self.offline = offline
        self.http = None if offline else httpx.Client(timeout=timeout_s, http2=False)
        self.n_network = 0
        self.n_cached = 0
        self.n_429 = 0

    def _path(self, body: dict) -> Path:
        return self.raw_dir / body["user"] / cache_name(body)

    def cached(self, body: dict) -> dict | None:
        p = self._path(body)
        if p.exists():
            with gzip.open(p) as f:
                return json.load(f)
        return None

    def post(self, body: dict) -> dict:
        """Return the cache record for ``body``, fetching it if needed."""
        rec = self.cached(body)
        if rec is not None:
            self.n_cached += 1
            return rec
        if self.offline:
            raise FileNotFoundError(self._path(body))
        rtype = body["type"]
        retries, status, payload, err = 0, None, None, None
        t_fetch = time.time()
        elapsed = 0.0
        for attempt in range(self.max_tries):
            self.limiter.acquire(BASE_WEIGHT.get(rtype, 20))
            t0 = time.monotonic()
            try:
                r = self.http.post(self.url, json=body)
                status = r.status_code
                elapsed = time.monotonic() - t0
                if status == 200:
                    payload = r.json()
                    err = None
                    break
                err = r.text[:300]
            except (httpx.TransportError, json.JSONDecodeError) as e:
                status, err, elapsed = None, repr(e)[:300], time.monotonic() - t0
            if status is not None and status not in RETRY_STATUS:
                break
            if status == 429:
                self.n_429 += 1
            retries += 1
            delay = min(120.0, (5.0 if status == 429 else 1.0) * 2 ** attempt)
            time.sleep(delay * (0.75 + 0.5 * random.random()))
        n_items = len(payload) if isinstance(payload, list) else 0
        weight = request_weight(rtype, n_items)
        self.limiter.charge(weight - BASE_WEIGHT.get(rtype, 20))
        self.n_network += 1
        rec = {
            "request": body, "status": status, "error": err, "retries": retries,
            "fetched_at_ms": int(t_fetch * 1000), "elapsed_s": round(elapsed, 4),
            "weight": weight, "n_items": n_items, "response": payload,
        }
        if status == 200:  # only cache successes; failures are retried on the next run
            p = self._path(body)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            with gzip.open(tmp, "wt") as f:
                json.dump(rec, f, separators=(",", ":"))
            tmp.replace(p)
        return rec


# ---------------------------------------------------------------------------------------------
# Per-wallet fetch


def fetch_wallet(client: InfoClient, user: str, as_of_ms: int,
                 max_fill_pages: int | None = None) -> dict:
    """Fetch (or replay from cache) every pilot endpoint for one wallet.

    Returns the request records, the stitched ledger and fills, and pagination flags.
    """
    log: list[dict] = []

    def call(body: dict) -> Any:
        rec = client.post(body)
        log.append({k: rec[k] for k in ("status", "retries", "elapsed_s", "weight",
                                        "n_items", "fetched_at_ms")} | {"type": body["type"]})
        if rec["status"] != 200:
            raise RuntimeError(f"{body['type']} {user}: status {rec['status']} {rec['error']}")
        return rec["response"]

    out: dict[str, Any] = {"user": user, "errors": {}}
    for rtype in ("portfolio", "subAccounts", "userRole"):
        try:
            out[rtype] = call({"type": rtype, "user": user})
        except RuntimeError as e:
            out["errors"][rtype] = str(e)
    for rtype, key, extra in (
        ("userNonFundingLedgerUpdates", ledger_key, {}),
        ("userFillsByTime", fill_key, {"aggregateByTime": False}),
    ):
        def page(start: int, rtype=rtype, extra=extra) -> list[dict]:
            body = {"type": rtype, "user": user, "startTime": start, "endTime": as_of_ms}
            return call(body | extra) or []
        try:
            res = paginate(page, key, max_pages=max_fill_pages if rtype == "userFillsByTime"
                           else None)
            out[rtype] = res.rows
            out[rtype + "_paging"] = {"pages": res.pages, "truncated": res.truncated,
                                      "stuck_steps": res.stuck_steps, "flags": res.flags}
        except RuntimeError as e:
            out["errors"][rtype] = str(e)
    out["requests"] = log
    return out


# ---------------------------------------------------------------------------------------------
# Per-wallet data-quality metrics (pure)

SPOT_PREFIX = "@"
INFLOW_TYPES = {"deposit", "spotGenesis", "vaultCreate"}


def is_spot(coin: str) -> bool:
    return coin.startswith(SPOT_PREFIX) or "/" in coin


def is_hip3(coin: str) -> bool:
    return ":" in coin


def gaps_hours(ts: Sequence[int]) -> list[float]:
    t = sorted(int(x) for x in ts)
    return [(b - a) / 3.6e6 for a, b in pairwise(t)]


def window_spacing(win: dict) -> dict:
    pts = win.get("accountValueHistory") or []
    ts = [p[0] for p in pts]
    g = gaps_hours(ts)
    return {
        "n_points": len(pts),
        "first_ms": min(ts) if ts else None,
        "last_ms": max(ts) if ts else None,
        "span_days": (max(ts) - min(ts)) / 8.64e7 if len(ts) > 1 else 0.0,
        "median_gap_h": float(np.median(g)) if g else None,
        "max_gap_h": max(g) if g else None,
        "first_gap_h": g[0] if g else None,
        "pnl_points": len(win.get("pnlHistory") or []),
        "vlm": float(win.get("vlm") or 0.0),
    }


def first_inbound_ms(ledger: Sequence[dict], user: str) -> int | None:
    """Time of the first ledger event that brings value into the wallet.

    Deposits, genesis spot balances and vault creation always count; transfers count when
    this wallet is the destination (``destination`` field) or when the wallet is not the
    sender (``user`` field differs) for types that carry one.
    """
    user = user.lower()
    for r in sorted(ledger, key=lambda r: int(r["time"])):
        d = r.get("delta") or {}
        t = d.get("type")
        if t in INFLOW_TYPES:
            return int(r["time"])
        if t in {"send", "internalTransfer", "subAccountTransfer", "spotTransfer"}:
            dest = str(d.get("destination", "")).lower()
            src = str(d.get("user", "")).lower()
            if dest == user or (src and src != user):
                return int(r["time"])
    return None


def fill_notional(fills: Iterable[dict]) -> dict[str, float]:
    out = {"all": 0.0, "perp": 0.0, "spot": 0.0, "hip3": 0.0}
    for f in fills:
        n = abs(float(f["px"]) * float(f["sz"]))
        out["all"] += n
        coin = f.get("coin", "")
        if is_spot(coin):
            out["spot"] += n
        elif is_hip3(coin):
            out["hip3"] += n
        else:
            out["perp"] += n
    return out


def rel_diff(a: float, b: float) -> float | None:
    """|a - b| / |b|, or None when b is zero."""
    return abs(a - b) / abs(b) if b else None


def classify_fills(n_fills: int, coverage: float | None, vlm_all: float,
                   earliest_fill_ms: int | None, first_event_ms: int | None,
                   tol: float = 0.05, lag_ms: int = 7 * 86_400_000) -> str:
    """Label a wallet's fill history.

    ``no_trading``: no fills and zero allTime volume. ``complete``: retrieved fill notional
    covers at least ``1 - tol`` of portfolio allTime volume. ``left_censored``: coverage
    below that and the earliest retrieved fill is more than ``lag_ms`` after the wallet's
    first recorded activity (or there is no fill despite volume). ``partial``: anything else
    (coverage short but no evidence that old history is missing, for example volume that does
    not appear as fills).
    """
    if n_fills == 0 and vlm_all == 0:
        return "no_trading"
    if coverage is not None and coverage >= 1 - tol:
        return "complete"
    if n_fills == 0:
        return "left_censored"
    if earliest_fill_ms is not None and first_event_ms is not None \
            and earliest_fill_ms - first_event_ms > lag_ms:
        return "left_censored"
    return "partial"


def wallet_metrics(w: dict, lb: dict[str, float], as_of_ms: int) -> dict:
    """Data-quality metrics for one fetched wallet (no performance statistics)."""
    user = w["user"]
    m: dict[str, Any] = {"user": user, "errors": sorted(w.get("errors", {}))}
    port = w.get("portfolio")
    wins = dict(port) if isinstance(port, list) else {}
    m["has_portfolio"] = "allTime" in wins
    m["windows"] = {k: window_spacing(wins[k]) for k in WINDOWS if k in wins}
    at = wins.get("allTime", {})
    av_hist = at.get("accountValueHistory") or []
    pnl_hist = at.get("pnlHistory") or []
    m["portfolio_nonempty"] = bool(av_hist)

    ledger = w.get("userNonFundingLedgerUpdates") or []
    m["has_ledger_call"] = "userNonFundingLedgerUpdates" in w
    m["n_ledger"] = len(ledger)
    m["ledger_types"] = dict(Counter((r.get("delta") or {}).get("type") for r in ledger))
    m["ledger_pages"] = (w.get("userNonFundingLedgerUpdates_paging") or {}).get("pages")
    m["first_ledger_ms"] = min((int(r["time"]) for r in ledger), default=None)
    m["first_inbound_ms"] = first_inbound_ms(ledger, user)

    fills = w.get("userFillsByTime") or []
    paging = w.get("userFillsByTime_paging") or {}
    m["has_fills_call"] = "userFillsByTime" in w
    m["n_fills"] = len(fills)
    m["n_oids"] = len({f.get("oid") for f in fills})
    m["fill_pages"] = paging.get("pages")
    m["fill_truncated"] = bool(paging.get("truncated"))
    m["fill_stuck_steps"] = paging.get("stuck_steps", 0)
    m["earliest_fill_ms"] = min((int(f["time"]) for f in fills), default=None)
    m["latest_fill_ms"] = max((int(f["time"]) for f in fills), default=None)
    m["n_liquidation_fills"] = sum(1 for f in fills if f.get("liquidation"))
    notional = fill_notional(fills)
    m["fill_notional"] = notional
    vlm_all = float(at.get("vlm") or 0.0)
    m["portfolio_vlm_allTime"] = vlm_all
    m["portfolio_vlm_perpAllTime"] = float((wins.get("perpAllTime") or {}).get("vlm") or 0.0)
    m["fill_coverage"] = notional["all"] / vlm_all if vlm_all else None
    starts = [x for x in (m["first_ledger_ms"],
                          min((p[0] for p in av_hist), default=None)) if x is not None]
    m["first_activity_ms"] = min(starts) if starts else None
    m["fill_status"] = classify_fills(m["n_fills"], m["fill_coverage"], vlm_all,
                                      m["earliest_fill_ms"], m["first_activity_ms"])
    if m["earliest_fill_ms"] is not None and m["first_inbound_ms"] is not None:
        m["fill_minus_inbound_days"] = (m["earliest_fill_ms"] - m["first_inbound_ms"]) / 8.64e7
    else:
        m["fill_minus_inbound_days"] = None

    role = w.get("userRole")
    m["role"] = role.get("role") if isinstance(role, dict) else None
    m["role_raw"] = role
    subs = w.get("subAccounts")
    m["n_subaccounts"] = len(subs) if isinstance(subs, list) else 0

    m["lb_accountValue"] = lb["accountValue"]
    m["lb_pnl_allTime"] = lb["pnl"]
    m["lb_vlm_allTime"] = lb["vlm"]
    if av_hist:
        last_av = max(av_hist, key=lambda p: p[0])
        m["pf_accountValue"] = float(last_av[1])
        m["pf_last_ms"] = int(last_av[0])
    if pnl_hist:
        m["pf_pnl_allTime"] = float(max(pnl_hist, key=lambda p: p[0])[1])
    for a, b, name in (("pf_accountValue", "lb_accountValue", "accountValue"),
                       ("pf_pnl_allTime", "lb_pnl_allTime", "pnl"),
                       ("portfolio_vlm_allTime", "lb_vlm_allTime", "vlm")):
        if a in m:
            m[f"absdiff_{name}"] = abs(m[a] - m[b])
            m[f"reldiff_{name}"] = rel_diff(m[a], m[b])

    reqs = w.get("requests") or []
    m["n_requests"] = len(reqs)
    m["weight"] = sum(r["weight"] for r in reqs)
    m["weight_by_type"] = {}
    for r in reqs:
        m["weight_by_type"][r["type"]] = m["weight_by_type"].get(r["type"], 0) + r["weight"]
    m["latency_s"] = sum(r["elapsed_s"] for r in reqs)
    m["retries"] = sum(r["retries"] for r in reqs)
    m["as_of_ms"] = as_of_ms
    return m


# ---------------------------------------------------------------------------------------------
# Aggregation


def _q(xs: Iterable[float | None], qs=(0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)) -> dict:
    a = np.asarray([x for x in xs if x is not None], dtype=float)
    if a.size == 0:
        return {"n": 0}
    return {"n": int(a.size)} | {f"q{int(q * 100)}": float(np.quantile(a, q)) for q in qs}


def aggregate(metrics: Sequence[dict], budget_per_min: float, n_cohort: int) -> dict:
    n = len(metrics)
    agg: dict[str, Any] = {"n_wallets": n}
    agg["returned"] = {
        "portfolio_ok": sum(m["has_portfolio"] for m in metrics),
        "portfolio_nonempty_allTime": sum(m["portfolio_nonempty"] for m in metrics),
        "ledger_ok": sum(m["has_ledger_call"] for m in metrics),
        "ledger_nonempty": sum(m["n_ledger"] > 0 for m in metrics),
        "fills_ok": sum(m["has_fills_call"] for m in metrics),
        "fills_nonempty": sum(m["n_fills"] > 0 for m in metrics),
        "subAccounts_nonnull": sum(m["n_subaccounts"] > 0 for m in metrics),
        "userRole_ok": sum(m["role"] is not None for m in metrics),
        "any_error": sum(bool(m["errors"]) for m in metrics),
    }
    agg["roles"] = dict(Counter(m["role"] for m in metrics))
    agg["spacing"] = {}
    for win in WINDOWS:
        ws = [m["windows"][win] for m in metrics if win in m["windows"]]
        agg["spacing"][win] = {
            "n_points": _q(w["n_points"] for w in ws),
            "span_days": _q(w["span_days"] for w in ws),
            "median_gap_h": _q(w["median_gap_h"] for w in ws),
            "max_gap_h": _q(w["max_gap_h"] for w in ws),
            "first_gap_h": _q(w["first_gap_h"] for w in ws),
        }
    at_first = [m["windows"]["allTime"]["first_ms"] for m in metrics
                if "allTime" in m["windows"] and m["windows"]["allTime"]["first_ms"]]
    agg["allTime_first_point_year"] = dict(sorted(Counter(
        datetime.fromtimestamp(t / 1000, UTC).strftime("%Y") for t in at_first).items()))
    agg["fill_status"] = dict(Counter(m["fill_status"] for m in metrics))
    traded = [m for m in metrics if m["fill_status"] != "no_trading"]
    agg["fills"] = {
        "n_fills": _q(m["n_fills"] for m in traded),
        "n_oids": _q(m["n_oids"] for m in traded),
        "coverage": _q(m["fill_coverage"] for m in traded),
        "fill_minus_inbound_days": _q(m["fill_minus_inbound_days"] for m in traded),
        "truncated_by_page_cap": sum(m["fill_truncated"] for m in metrics),
        "stuck_steps": sum(m["fill_stuck_steps"] for m in metrics),
        "wallets_with_liquidation_fills": sum(m["n_liquidation_fills"] > 0 for m in metrics),
    }
    by_status: dict[str, list] = {}
    for m in traded:
        by_status.setdefault(m["fill_status"], []).append(
            {"n_fills": m["n_fills"], "n_oids": m["n_oids"],
             "coverage": m["fill_coverage"], "pages": m["fill_pages"]})
    agg["fills_by_status"] = {k: {"n_fills": _q(x["n_fills"] for x in v),
                                  "n_oids": _q(x["n_oids"] for x in v),
                                  "coverage": _q(x["coverage"] for x in v)}
                              for k, v in by_status.items()}
    agg["censored_detail"] = sorted(
        ({"n_fills": m["n_fills"], "n_oids": m["n_oids"],
          "coverage": m["fill_coverage"], "role": m["role"]}
         for m in metrics if m["fill_status"] in ("left_censored", "partial")),
        key=lambda d: d["n_fills"])
    agg["ledger"] = {"n_rows": _q(m["n_ledger"] for m in metrics),
                     "multi_page": sum((m["ledger_pages"] or 0) > 1 for m in metrics),
                     "types": dict(sum((Counter(m["ledger_types"]) for m in metrics),
                                       Counter()))}
    agg["leaderboard_match"] = {}
    lb_field = {"accountValue": "lb_accountValue", "pnl": "lb_pnl_allTime",
                "vlm": "lb_vlm_allTime"}
    for name, lbk in lb_field.items():
        ms = [m for m in metrics if f"absdiff_{name}" in m]
        absd = [m[f"absdiff_{name}"] for m in ms]
        # Relative differences only where the leaderboard value is at least $100, so that
        # near-zero denominators do not dominate.
        rel = [m[f"reldiff_{name}"] for m in ms
               if m[f"reldiff_{name}"] is not None and abs(m[lbk]) >= 100]
        agg["leaderboard_match"][name] = {
            "n": len(ms),
            "abs": _q(absd, qs=(0.5, 0.9, 0.99, 1.0)),
            "exact_within_1usd": sum(x <= 1 for x in absd),
            "rel_if_lb_abs_ge_100": _q(rel, qs=(0.5, 0.9, 0.99, 1.0)),
            "rel_gt_1pct": sum(x > 0.01 for x in rel),
            "rel_gt_10pct": sum(x > 0.10 for x in rel),
        }
    lags = [(m["pf_last_ms"] - FORMATION_MS) / 3.6e6 for m in metrics if "pf_last_ms" in m]
    agg["portfolio_last_point_minus_formation_h"] = _q(lags)
    weights = [m["weight"] for m in metrics]
    agg["cost"] = {
        "weight_per_wallet": _q(weights, qs=(0.5, 0.9, 0.99, 1.0)) | {
            "mean": float(np.mean(weights)), "total": int(np.sum(weights))},
        "weight_by_type_total": dict(sum((Counter(m["weight_by_type"]) for m in metrics),
                                         Counter())),
        "requests_total": int(sum(m["n_requests"] for m in metrics)),
        "latency_s_per_wallet": _q((m["latency_s"] for m in metrics), qs=(0.5, 0.9, 1.0))
        | {"mean": float(np.mean([m["latency_s"] for m in metrics]))},
        "retries_total": int(sum(m["retries"] for m in metrics)),
        "budget_per_min": budget_per_min,
    }
    mean_w = float(np.mean(weights))
    nonfill = [m["weight"] - m["weight_by_type"].get("userFillsByTime", 0) for m in metrics]
    agg["projection"] = {
        "n_cohort": n_cohort,
        "all_endpoints_hours": n_cohort * mean_w / budget_per_min / 60,
        "without_fills_hours": n_cohort * float(np.mean(nonfill)) / budget_per_min / 60,
        "without_fills_and_userRole_hours": n_cohort * float(np.mean(
            [x - m["weight_by_type"].get("userRole", 0) for x, m in zip(nonfill, metrics,
                                                                         strict=True)]))
        / budget_per_min / 60,
        "latency_floor_hours": n_cohort * float(np.mean([m["latency_s"] for m in metrics]))
        / 3600,
    }
    return agg


# ---------------------------------------------------------------------------------------------
# CLI


def _n_arg(s: str) -> int | None:
    return None if s == "all" else int(s)


def _run_meta(out: Path) -> dict:
    p = out / "run.json"
    if p.exists():
        return json.loads(p.read_text())
    meta = {"as_of_ms": int(time.time() * 1000), "seed": SEED,
            "formation": FORMATION.name, "formation_sha256": FORMATION_SHA256,
            "created_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    out.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def cmd_sample(args) -> dict:
    table = cohort_table(load_cohort())
    sample = draw_sample(table, args.n)
    rep = sample_vs_cohort(table, sample)
    print(json.dumps(rep, indent=2))
    return rep


def cmd_fetch(args) -> None:
    table = cohort_table(load_cohort())
    sample = draw_sample(table, args.n)
    meta = _run_meta(args.out)
    (args.out / f"sample_{len(sample)}.txt").write_text("\n".join(sample) + "\n")
    limiter = WeightLimiter(DOC_BUDGET_PER_MIN * args.pace)
    client = InfoClient(args.out / "raw", limiter)
    log_path = args.out / "wallet_log.jsonl"
    t_start = time.monotonic()
    for i, user in enumerate(sample, 1):
        t0, w0 = time.monotonic(), limiter.waited_s
        n_net0 = client.n_network
        w = fetch_wallet(client, user, meta["as_of_ms"], args.max_fill_pages)
        if client.n_network > n_net0:
            with log_path.open("a") as f:
                f.write(json.dumps({
                    "user": user, "wall_s": round(time.monotonic() - t0, 2),
                    "pacing_wait_s": round(limiter.waited_s - w0, 2),
                    "weight": sum(r["weight"] for r in w["requests"]),
                    "n_fills": len(w.get("userFillsByTime") or []),
                    "errors": w["errors"], "at_utc": datetime.now(UTC).isoformat()}) + "\n")
        if i % 10 == 0 or i == len(sample):
            print(f"{i}/{len(sample)} wallets, {client.n_network} network calls, "
                  f"{client.n_cached} cached, {client.n_429} x 429, "
                  f"{time.monotonic() - t_start:.0f} s", flush=True)


def cmd_summarize(args) -> dict:
    table = cohort_table(load_cohort())
    sample = draw_sample(table, args.n)
    meta = _run_meta(args.out)
    client = InfoClient(args.out / "raw", offline=True)
    metrics = []
    for user in sample:
        w = fetch_wallet(client, user, meta["as_of_ms"], args.max_fill_pages)
        metrics.append(wallet_metrics(w, table[user], meta["as_of_ms"]))
    with (args.out / "wallet_metrics.jsonl").open("w") as f:
        for m in metrics:
            f.write(json.dumps(m) + "\n")
    agg = aggregate(metrics, DOC_BUDGET_PER_MIN * args.pace, len(table))
    agg["sample_vs_cohort"] = sample_vs_cohort(table, sample)
    agg["run"] = meta
    log_path = args.out / "wallet_log.jsonl"
    if log_path.exists():
        logs = [json.loads(x) for x in log_path.read_text().splitlines()]
        last = {x["user"]: x for x in logs}
        wall = [last[u]["wall_s"] for u in sample if u in last]
        agg["cost"]["wall_s_per_wallet_measured"] = _q(wall, qs=(0.5, 0.9, 1.0)) | {
            "mean": float(np.mean(wall)) if wall else None, "n": len(wall)}
        if wall:
            agg["projection"]["measured_wall_hours"] = len(table) * float(np.mean(wall)) / 3600
    (args.out / "summary.json").write_text(json.dumps(agg, indent=2) + "\n")
    print(json.dumps(agg, indent=2))
    return agg


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("sample", "fetch", "summarize"):
        p = sub.add_parser(name)
        p.add_argument("--n", type=_n_arg, default=DEFAULT_N, help="sample size or 'all'")
        p.add_argument("--out", type=Path, default=DEFAULT_OUT)
        p.add_argument("--pace", type=float, default=PACE_FRACTION,
                       help="fraction of the documented 1,200 weight/min budget")
        p.add_argument("--max-fill-pages", type=int, default=150,
                       help="cap on fill pages per wallet (150 pages = 300k fills)")
    args = ap.parse_args(argv)
    {"sample": cmd_sample, "fetch": cmd_fetch, "summarize": cmd_summarize}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
