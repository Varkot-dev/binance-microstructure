"""Weekly crawl of every wallet in the frozen Project 1 cohort (research/hyperliquid).

Project 1 (``research/hyperliquid/PREREGISTRATION_P1.md``, section 2.2) needs, for each of the
48,035 addresses in the 2026-11-19 leaderboard snapshot and every sub-account they list:
``portfolio``, ``userNonFundingLedgerUpdates`` (paged forward from 0) and ``subAccounts``,
fetched once for the formation window and then every 7 days until the holding window ends.
It also needs benchmark data: daily candles and hourly funding for every perp, hourly candles
for BTC, ETH and HYPE, and HLP's ``vaultDetails`` at every poll.

One pass takes about 62 hours of API weight from one IP, so a pass is split into shards that
run as parallel GitHub Actions jobs (``.github/workflows/hl-p1-crawl.yml``). A pass is named
after the Monday (00:00 UTC) of its ISO week. Each shard is resumable: it reads its own
earlier output for the pass, skips units already fetched and stops before a time budget, so a
shard that is cut short finishes on the next daily run.

This module only fetches and stores responses as served. It computes no return, PnL change
or ranking: those belong to ``research/hyperliquid/p1_skill.py``, which checks the locked plan.

    python -m microstructure.hyperliquid.crawl shard --cohort FILE --shard 3 --n-shards 24 \
        --out DIR [--budget-s 19800] [--pass-id 20261116]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import sys
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

INFO_URL = "https://api.hyperliquid.xyz/info"
COHORT_SHA256 = "ac669f966b7ddbd4a4e5aa8ac50781c9a8d9f51a071ac3c062812046217c1a37"
HLP = "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"
HOURLY_COINS = ("BTC", "ETH", "HYPE")
LEDGER_PAGE = 2000  # full page size of userNonFundingLedgerUpdates
FUNDING_PAGE = 500  # full page size of fundingHistory
BUDGET_PER_MIN = 780.0  # 65% of the documented 1,200 weight per minute per IP
WEIGHT = {"userRole": 60, "candleSnapshot": 20, "meta": 20}  # everything else here is 20
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_TRIES = 3  # attempts per unit across runs before it is recorded as failed for the pass


# ---------------------------------------------------------------------------------------------
# Pure helpers


def pass_id(now: datetime) -> str:
    """Monday 00:00 UTC of ``now``'s ISO week, as YYYYMMDD."""
    d = now.astimezone(UTC).date()
    return (d - timedelta(days=d.weekday())).strftime("%Y%m%d")


def load_cohort(path: Path, expected_sha256: str = COHORT_SHA256) -> list[str]:
    """Sorted, lower-cased, distinct addresses of the frozen leaderboard snapshot."""
    raw = path.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != expected_sha256:
        raise SystemExit(f"cohort file sha256 {got} does not match the frozen {expected_sha256}")
    rows = json.loads(gzip.decompress(raw))["leaderboardRows"]
    return sorted({r["ethAddress"].lower() for r in rows})


def shard_of(items: list, shard: int, n_shards: int) -> list:
    """Every ``n_shards``-th item starting at ``shard``: a fixed, balanced partition."""
    if not 0 <= shard < n_shards:
        raise ValueError(f"shard {shard} outside 0..{n_shards - 1}")
    return items[shard::n_shards]


def ledger_key(r: dict) -> tuple:
    return (r.get("time"), r.get("hash"), json.dumps(r.get("delta"), sort_keys=True))


def funding_key(r: dict) -> tuple:
    return (r.get("coin"), r.get("time"))


@dataclass
class Paged:
    rows: list[dict]
    pages: int = 0
    stuck_steps: int = 0


def paginate(fetch: Callable[[int], list[dict]], key: Callable[[dict], tuple], page_size: int,
             start_ms: int = 0, time_key: str = "time") -> Paged:
    """Page an oldest-first endpoint forward, restarting each page at the last row's time.

    Rows sharing that millisecond are fetched again and removed with ``key``. A full page that
    adds nothing moves the start 1 ms on and counts a ``stuck_step``.
    """
    out = Paged(rows=[])
    seen: set[tuple] = set()
    start = start_ms
    while True:
        page = fetch(start) or []
        out.pages += 1
        new = 0
        for r in page:
            k = key(r)
            if k not in seen:
                seen.add(k)
                out.rows.append(r)
                new += 1
        if len(page) < page_size:
            break
        last = max(int(r[time_key]) for r in page)
        if last > start and new > 0:
            start = last
        else:
            out.stuck_steps += 1
            start = max(start, last) + 1
    out.rows.sort(key=lambda r: int(r[time_key]))
    return out


class WeightLimiter:
    """Sliding 60 s window of spent weight; ``acquire`` blocks until ``w`` more fits."""

    def __init__(self, budget: float = BUDGET_PER_MIN, window_s: float = 60.0,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.budget, self.window_s, self.clock, self.sleep = budget, window_s, clock, sleep
        self.events: deque[tuple[float, float]] = deque()

    def acquire(self, w: float) -> None:
        while True:
            now = self.clock()
            while self.events and self.events[0][0] <= now - self.window_s:
                self.events.popleft()
            if not self.events or sum(x for _, x in self.events) + w <= self.budget:
                self.events.append((now, w))
                return
            self.sleep(self.events[0][0] + self.window_s - now + 0.01)


class FetchError(RuntimeError):
    pass


class Client:
    """POST /info with weight pacing and retries with backoff on 429 and 5xx."""

    def __init__(self, limiter: WeightLimiter | None = None, url: str = INFO_URL,
                 tries: int = 6, timeout_s: float = 60.0,
                 post: Callable[[dict], tuple[int, Any]] | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.limiter = limiter or WeightLimiter()
        self.url, self.tries, self.sleep = url, tries, sleep
        self._http = None if post else httpx.Client(timeout=timeout_s)
        self._post = post or self._http_post
        self.n_calls = self.n_429 = self.weight = 0

    def _http_post(self, body: dict) -> tuple[int, Any]:
        r = self._http.post(self.url, json=body)
        return r.status_code, (r.json() if r.status_code == 200 else r.text[:300])

    def info(self, body: dict) -> Any:
        w = WEIGHT.get(body["type"], 20)
        err: Any = None
        for attempt in range(self.tries):
            self.limiter.acquire(w)
            self.n_calls += 1
            self.weight += w
            try:
                status, payload = self._post(body)
            except (httpx.TransportError, json.JSONDecodeError) as e:
                status, payload = None, repr(e)[:300]
            if status == 200:
                return payload
            err = f"status {status}: {payload}"
            if status is not None and status not in RETRY_STATUS:
                break
            if status == 429:
                self.n_429 += 1
            delay = min(120.0, (5.0 if status == 429 else 1.0) * 2 ** attempt)
            self.sleep(delay * (0.75 + 0.5 * random.random()))
        raise FetchError(f"{body.get('type')}: {err}")


# ---------------------------------------------------------------------------------------------
# Units of work


def fetch_wallet(client: Client, address: str) -> dict:
    """``portfolio``, ``subAccounts`` and the full forward-paged ledger of one address."""
    portfolio = client.info({"type": "portfolio", "user": address})
    subs = client.info({"type": "subAccounts", "user": address})
    led = paginate(lambda s: client.info({"type": "userNonFundingLedgerUpdates",
                                          "user": address, "startTime": s}),
                   ledger_key, LEDGER_PAGE)
    return {"portfolio": portfolio, "subAccounts": subs, "ledger": led.rows,
            "ledger_pages": led.pages, "ledger_stuck_steps": led.stuck_steps}


def sub_addresses(subs: Any) -> list[str]:
    if not isinstance(subs, list):
        return []
    return sorted({s["subAccountUser"].lower() for s in subs
                   if isinstance(s, dict) and s.get("subAccountUser")})


def bench_units(perps: list[str], shard: int, n_shards: int) -> list[str]:
    """Benchmark unit keys for this shard: daily candles and funding for its share of the
    perps; shard 0 also takes the hourly candles and HLP's vault details."""
    units = [f"candle1d:{c}" for c in shard_of(perps, shard, n_shards)]
    units += [f"funding:{c}" for c in shard_of(perps, shard, n_shards)]
    if shard == 0:
        units += [f"candle1h:{c}" for c in HOURLY_COINS] + [f"vault:{HLP}"]
    return units


def fetch_bench(client: Client, unit: str, now_ms: int) -> dict:
    kind, key = unit.split(":", 1)
    if kind in ("candle1d", "candle1h"):
        interval = "1d" if kind == "candle1d" else "1h"
        rows = client.info({"type": "candleSnapshot", "req": {
            "coin": key, "interval": interval, "startTime": 0, "endTime": now_ms}})
        return {"candles": rows}
    if kind == "funding":
        res = paginate(lambda s: client.info({"type": "fundingHistory", "coin": key,
                                              "startTime": s}), funding_key, FUNDING_PAGE)
        return {"funding": res.rows, "pages": res.pages, "stuck_steps": res.stuck_steps}
    if kind == "vault":
        return {"vaultDetails": client.info({"type": "vaultDetails", "vaultAddress": key})}
    raise ValueError(unit)


# ---------------------------------------------------------------------------------------------
# Shard runner


@dataclass
class ShardState:
    """Records of one shard for one pass, keyed by unit (``wallet:<addr>`` or a bench key)."""

    records: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> ShardState:
        st = cls()
        if path.exists():
            with gzip.open(path, "rt") as f:
                for line in f:
                    rec = json.loads(line)
                    st.records[rec["unit"]] = rec
        return st

    def done(self, unit: str) -> bool:
        r = self.records.get(unit)
        return r is not None and (r["status"] == "ok" or r.get("tries", 0) >= MAX_TRIES)

    def save(self, path: Path) -> str:
        """Write deterministically (sorted units, gzip mtime 0); return the sha256."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "wb") as fh, gzip.GzipFile(filename="", fileobj=fh, mode="wb",
                                                  mtime=0) as gz:
            for unit in sorted(self.records):
                gz.write((json.dumps(self.records[unit], separators=(",", ":")) + "\n")
                         .encode())
        tmp.replace(path)
        return hashlib.sha256(path.read_bytes()).hexdigest()


def run_shard(client: Client, cohort: list[str], perps: list[str], shard: int, n_shards: int,
              out: Path, pid: str, budget_s: float, now: Callable[[], float] = time.time,
              save_every: int = 200, log: Callable[[str], None] = print) -> dict:
    """Fetch every unit of this shard not yet done for pass ``pid``; return the status."""
    t_start = now()
    data_path = out / f"shard_{shard:02d}.jsonl.gz"
    st = ShardState.load(data_path)
    queue: list[tuple[str, str | None]] = [(f"wallet:{a}", None)
                                           for a in shard_of(cohort, shard, n_shards)]
    queue += [(u, None) for u in bench_units(perps, shard, n_shards)]
    # sub-accounts listed in earlier runs of this pass
    for rec in list(st.records.values()):
        if rec["unit"].startswith("wallet:") and rec["status"] == "ok":
            for s in sub_addresses(rec["data"]["subAccounts"]):
                queue.append((f"wallet:{s}", rec["unit"].split(":", 1)[1]))
    seen: set[str] = set()
    n_new = 0
    stopped_early = False
    i = 0
    while i < len(queue):
        unit, master = queue[i]
        i += 1
        if unit in seen:
            continue
        seen.add(unit)
        if st.done(unit):
            continue
        if now() - t_start > budget_s:
            stopped_early = True
            break
        prev = st.records.get(unit, {})
        rec = {"unit": unit, "pass": pid, "master": master, "fetched_ms": int(now() * 1000),
               "tries": prev.get("tries", 0) + 1}
        try:
            if unit.startswith("wallet:"):
                rec["data"] = fetch_wallet(client, unit.split(":", 1)[1])
                for s in sub_addresses(rec["data"]["subAccounts"]):
                    queue.append((f"wallet:{s}", unit.split(":", 1)[1]))
            else:
                rec["data"] = fetch_bench(client, unit, int(now() * 1000))
            rec["status"] = "ok"
        except FetchError as e:
            rec["status"], rec["error"] = "failed", str(e)
        st.records[unit] = rec
        n_new += 1
        if n_new % save_every == 0:
            st.save(data_path)
            log(f"shard {shard}: {n_new} fetched this run, {client.n_calls} calls, "
                f"{client.n_429} x 429, {now() - t_start:.0f} s")
    sha = st.save(data_path)
    pending = [u for u, _ in queue if not st.done(u)]
    recs = st.records.values()
    status = {
        "pass": pid, "shard": shard, "n_shards": n_shards, "cohort_sha256": COHORT_SHA256,
        "complete": not stopped_early and not pending,
        "units": len(st.records),
        "wallets_ok": sum(r["status"] == "ok" and r["unit"].startswith("wallet:") for r in recs),
        "sub_accounts_ok": sum(r["status"] == "ok" and bool(r.get("master")) for r in recs),
        "bench_ok": sum(r["status"] == "ok" and not r["unit"].startswith("wallet:")
                        for r in recs),
        "failed": sum(r["status"] == "failed" for r in recs),
        "pending": len(pending), "fetched_this_run": n_new,
        "calls_this_run": client.n_calls, "weight_this_run": client.weight,
        "http_429_this_run": client.n_429, "seconds_this_run": round(now() - t_start, 1),
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "data_file": data_path.name, "data_sha256": sha,
    }
    (out / f"shard_{shard:02d}.status.json").write_text(json.dumps(status, indent=1) + "\n")
    return status


def perp_names(client: Client) -> list[str]:
    """Every perp in ``meta`` (delisted ones included), in served order."""
    return [u["name"] for u in client.info({"type": "meta"})["universe"]]


def main(argv: Iterable[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("shard", help="fetch one shard of the current pass")
    s.add_argument("--cohort", type=Path, required=True)
    s.add_argument("--shard", type=int, required=True)
    s.add_argument("--n-shards", type=int, required=True)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--budget-s", type=float, default=5.5 * 3600)
    s.add_argument("--pass-id", default=None)
    sub.add_parser("pass-id", help="print the current pass id")
    a = p.parse_args(list(argv) if argv is not None else None)
    if a.cmd == "pass-id":
        print(pass_id(datetime.now(UTC)))
        return
    pid = a.pass_id or pass_id(datetime.now(UTC))
    client = Client()
    cohort = load_cohort(a.cohort)
    status = run_shard(client, cohort, perp_names(client), a.shard, a.n_shards, a.out, pid,
                       a.budget_s)
    print(json.dumps(status, indent=1))
    sys.exit(0)


if __name__ == "__main__":
    main()
