"""Record Binance USD-M futures trades with the ``isRPITrade`` flag, going forward.

Binance introduced RPI (Retail Price Improvement) orders on futures on 2025-11-20. An RPI
order only fills against orders placed in the Binance app or website, never against API or
algorithmic orders, and the public recent-trades endpoint marks such fills with
``isRPITrade = true``. The daily archive on data.binance.vision does not carry the flag, so a
day that is not recorded is lost. This recorder polls ``/fapi/v1/trades`` (newest 1,000 trades
per call) for a fixed list of RPI-enabled contracts, adapts each contract's polling interval to
its trade rate so consecutive calls overlap, and logs every gap in the trade-id sequence.

It stores trades as served and computes nothing about them. One run writes one gzipped CSV
(all symbols) plus a JSON summary with per-symbol counts, gaps and the RPI-enabled symbol list
from ``exchangeInfo`` at the start of the run.

    python -m microstructure.rpi.recorder run --out DIR --until-iso 2026-11-23T03:38:00Z
    python -m microstructure.rpi.recorder run --out DIR --minutes 10
    python -m microstructure.rpi.recorder end-time   # end of the current 4-hour slot + overlap
"""

from __future__ import annotations

import argparse
import csv
import gzip
import heapq
import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

BASE = "https://www.binance.com/fapi/v1"
# RPI-enabled contracts chosen for the retail-identification project: majors and memecoins
# on USDC margin (where RPI is enabled for the majors), plus the USDT memecoin contracts with
# RPI. Symbols that are not RPI-enabled at the start of a run are still recorded and flagged
# in the summary.
SYMBOLS = (
    "BTCUSDC", "ETHUSDC", "SOLUSDC", "DOGEUSDC", "1000PEPEUSDC", "1000SHIBUSDC", "WIFUSDC",
    "1000BONKUSDC", "TRUMPUSDC", "PNUTUSDC", "PENGUUSDC", "ETHFIUSDC",
    "1000PEPEUSDT", "DOGEUSDT", "FARTCOINUSDT",
)
COLUMNS = ("symbol", "id", "time", "price", "qty", "quoteQty", "isBuyerMaker", "isRPITrade")
LIMIT = 1000
TRADES_WEIGHT = 5
WEIGHT_SOFT_CAP = 1500  # of Binance's 2,400 per minute: slow down above this
MIN_INTERVAL_S, MAX_INTERVAL_S = 1.0, 20.0
FILL_TARGET = 0.07  # aim for each call to cover about 7% of a page, to absorb bursts
SLOT_HOURS, SLOT_MINUTE, OVERLAP_MIN = 4, 23, 75


# ---------------------------------------------------------------------------------------------
# Pure helpers


def slot_end(now: datetime, hours: int = SLOT_HOURS, minute: int = SLOT_MINUTE,
             overlap_min: int = OVERLAP_MIN) -> datetime:
    """End time for a run started in the current slot: the next slot start plus an overlap.

    Slots start every ``hours`` hours at ``minute`` past the hour (the cron schedule). Runs
    overlap by ``overlap_min`` minutes so a late-starting next run leaves no hole.
    """
    now = now.astimezone(UTC)
    anchor = now.replace(minute=minute, second=0, microsecond=0)
    anchor -= timedelta(hours=anchor.hour % hours)
    if anchor > now:
        anchor -= timedelta(hours=hours)
    return anchor + timedelta(hours=hours, minutes=overlap_min)


def next_interval(n_new: int, span_ms: int, full_page: bool, prev_s: float) -> float:
    """Seconds until the next call for a symbol, from the last call's yield.

    A full page means trades may have been missed, so poll at the minimum interval. Otherwise
    aim for ``FILL_TARGET`` of a page per call at the observed rate.
    """
    if full_page:
        return MIN_INTERVAL_S
    if n_new <= 0 or span_ms <= 0:
        return min(MAX_INTERVAL_S, prev_s * 1.5)
    rate = n_new / (span_ms / 1000)  # trades per second over the new trades' span
    return max(MIN_INTERVAL_S, min(MAX_INTERVAL_S, FILL_TARGET * LIMIT / max(rate, 1e-9)))


@dataclass
class SymbolState:
    symbol: str
    last_id: int | None = None
    last_time: int | None = None
    interval_s: float = 5.0
    trades: int = 0
    rpi: int = 0
    calls: int = 0
    full_pages: int = 0
    errors: int = 0
    gaps: list[dict] = field(default_factory=list)

    def absorb(self, batch: list[dict], now_ms: int) -> list[dict]:
        """Keep trades newer than ``last_id``; record a gap if the batch skips ids."""
        self.calls += 1
        if not batch:
            self.interval_s = next_interval(0, 0, False, self.interval_s)
            return []
        batch = sorted(batch, key=lambda t: t["id"])
        new = batch if self.last_id is None else [t for t in batch if t["id"] > self.last_id]
        full = len(batch) >= LIMIT and (self.last_id is None or batch[0]["id"] > self.last_id)
        if self.last_id is not None and batch[0]["id"] > self.last_id + 1:
            self.gaps.append({"after_id": self.last_id, "before_id": batch[0]["id"],
                              "missing": batch[0]["id"] - self.last_id - 1,
                              "after_time": self.last_time, "before_time": batch[0]["time"],
                              "detected_ms": now_ms})
        if full:
            self.full_pages += 1
        span = (new[-1]["time"] - new[0]["time"]) if len(new) > 1 else 0
        self.interval_s = next_interval(len(new), span, full, self.interval_s)
        if new:
            self.last_id, self.last_time = new[-1]["id"], new[-1]["time"]
            self.trades += len(new)
            self.rpi += sum(bool(t.get("isRPITrade")) for t in new)
        return new


# ---------------------------------------------------------------------------------------------
# HTTP


class Api:
    def __init__(self, base: str = BASE, timeout_s: float = 20.0,
                 get: Callable[[str, dict], tuple[int, Any, dict]] | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.base, self.sleep = base, sleep
        self._http = None if get else httpx.Client(timeout=timeout_s)
        self._get = get or self._http_get
        self.used_weight = 0
        self.n_429 = 0

    def _http_get(self, path: str, params: dict) -> tuple[int, Any, dict]:
        r = self._http.get(f"{self.base}/{path}", params=params)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") \
            else r.text[:300]
        return r.status_code, body, dict(r.headers)

    def get(self, path: str, params: dict, tries: int = 5) -> Any:
        err = None
        for attempt in range(tries):
            try:
                status, body, headers = self._get(path, params)
            except (httpx.TransportError, json.JSONDecodeError) as e:
                status, body, headers = None, repr(e)[:300], {}
            w = headers.get("x-mbx-used-weight-1m") or headers.get("X-MBX-USED-WEIGHT-1M")
            if w:
                self.used_weight = int(w)
            if status == 200:
                return body
            err = f"status {status}: {body}"
            if status in (418, 429):
                self.n_429 += 1
                retry = float(headers.get("retry-after") or headers.get("Retry-After") or 30)
                self.sleep(min(300.0, retry))
                continue
            if status is not None and status < 500:
                break
            self.sleep(min(30.0, 2 ** attempt))
        raise RuntimeError(f"{path} {params}: {err}")


def rpi_symbols(api: Api) -> list[str]:
    info = api.get("exchangeInfo", {})
    return sorted(s["symbol"] for s in info["symbols"]
                  if s.get("status") == "TRADING"
                  and any("RPI" in str(p) for p in s.get("permissionSets", [])))


# ---------------------------------------------------------------------------------------------
# Recorder loop


def record(api: Api, symbols: Iterable[str], out: Path, end_ms: int,
           clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep,
           log: Callable[[str], None] = print, run_id: str | None = None) -> dict:
    """Poll until ``end_ms``; write ``rpi_trades_<run>.csv.gz`` and ``rpi_run_<run>.json``."""
    symbols = list(symbols)
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.fromtimestamp(clock(), UTC)
    run_id = run_id or started.strftime("%Y%m%dT%H%M%SZ")
    try:
        enabled = rpi_symbols(api)
    except RuntimeError as e:
        enabled = []
        log(f"exchangeInfo failed: {e}")
    states = {s: SymbolState(s) for s in symbols}
    queue = [(clock(), s) for s in symbols]
    heapq.heapify(queue)
    data_path = out / f"rpi_trades_{run_id}.csv.gz"
    last_log = clock()
    with gzip.open(data_path, "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        while queue and clock() * 1000 < end_ms:
            due, sym = heapq.heappop(queue)
            wait = due - clock()
            if wait > 0:
                sleep(min(wait, max(0.0, end_ms / 1000 - clock())))
                if clock() * 1000 >= end_ms:
                    break
            st = states[sym]
            if api.used_weight > WEIGHT_SOFT_CAP:
                sleep(5.0)
            try:
                batch = api.get("trades", {"symbol": sym, "limit": LIMIT})
                new = st.absorb(batch, int(clock() * 1000))
                for t in new:
                    w.writerow((sym, t["id"], t["time"], t["price"], t["qty"], t["quoteQty"],
                                int(bool(t["isBuyerMaker"])), int(bool(t.get("isRPITrade")))))
            except RuntimeError as e:
                st.errors += 1
                st.interval_s = min(MAX_INTERVAL_S, st.interval_s * 2)
                log(f"{sym}: {e}")
            heapq.heappush(queue, (clock() + st.interval_s, sym))
            if clock() - last_log > 600:
                last_log = clock()
                log(" ".join(f"{s}:{v.trades}/{v.rpi}" for s, v in states.items()))
    summary = {
        "run_id": run_id, "started": started.isoformat(timespec="seconds"),
        "ended": datetime.fromtimestamp(clock(), UTC).isoformat(timespec="seconds"),
        "planned_end": datetime.fromtimestamp(end_ms / 1000, UTC).isoformat(timespec="seconds"),
        "rpi_enabled_at_start": enabled, "http_429_or_418": api.n_429,
        "data_file": data_path.name,
        "symbols": {s: {"rpi_enabled": s in enabled, "trades": v.trades, "rpi_trades": v.rpi,
                        "calls": v.calls, "full_pages": v.full_pages, "errors": v.errors,
                        "gap_free": not v.gaps, "gaps": v.gaps,
                        "last_id": v.last_id, "final_interval_s": round(v.interval_s, 2)}
                    for s, v in states.items()},
    }
    (out / f"rpi_run_{run_id}.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", type=Path, required=True)
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--minutes", type=float)
    g.add_argument("--until-iso")
    r.add_argument("--symbols", default=",".join(SYMBOLS))
    r.add_argument("--label", default="", help="suffix for file names, e.g. a replica id")
    sub.add_parser("end-time")
    a = p.parse_args(argv)
    if a.cmd == "end-time":
        print(slot_end(datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return
    now = datetime.now(UTC)
    end = (now + timedelta(minutes=a.minutes) if a.minutes is not None
           else datetime.fromisoformat(a.until_iso))
    end = min(end, now + timedelta(hours=5, minutes=45))  # GitHub Actions jobs stop at 6 h
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + (f"_{a.label}" if a.label else "")
    s = record(Api(), a.symbols.split(","), a.out, int(end.timestamp() * 1000), run_id=run_id)
    tot = sum(v["trades"] for v in s["symbols"].values())
    gaps = sum(len(v["gaps"]) for v in s["symbols"].values())
    print(f"run {s['run_id']}: {tot} trades, {gaps} gaps, {s['http_429_or_418']} rate limits")


if __name__ == "__main__":
    main()
