"""Record paired order-book snapshots for the RPI contracts: with and without RPI orders.

Binance hides RPI orders from ``/fapi/v1/depth`` and includes them in ``/fapi/v1/rpiDepth``.
Calling the two back to back shows whether RPI liquidity sits in front of the ordinary book,
which is when every app or website order must be flagged. The pre-registration
(``research/rpi/PREREGISTRATION.md``) uses this to measure labelling opportunity and to find
trades that cannot be retail.

Each sweep visits every contract once: ordinary book first, then the RPI book, a few
milliseconds apart. Only the top ``LEVELS`` price levels are kept. Books are stored as served and
nothing is computed from them. A sweep is skipped when the shared request-weight budget is busy,
so the trade recorder running beside this always has priority.

    python -m microstructure.rpi.books run --out DIR --until-iso 2026-11-23T03:38:00Z
    python -m microstructure.rpi.books run --out DIR --minutes 10
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from microstructure.rpi.recorder import SYMBOLS, Api

LEVELS = 20
DEPTH_LIMIT = 20  # smallest-weight call that returns LEVELS levels of the ordinary book
RPI_DEPTH_LIMIT = 1000  # the only limit /fapi/v1/rpiDepth accepted on 2026-11-22
SWEEP_S = 30.0
WEIGHT_YIELD = 1200  # skip a sweep above this used weight (the trade recorder slows at 1,500)


def trim(book: dict, levels: int = LEVELS) -> dict:
    """Keep the update id, both exchange timestamps and the top ``levels`` levels per side."""
    return {"u": book.get("lastUpdateId"), "E": book.get("E"), "T": book.get("T"),
            "bids": book.get("bids", [])[:levels], "asks": book.get("asks", [])[:levels]}


def snapshot(api: Api, symbol: str, clock: Callable[[], float]) -> dict:
    """One paired snapshot: ordinary book, then the book that includes RPI orders."""
    t0 = int(clock() * 1000)
    depth = api.get("depth", {"symbol": symbol, "limit": DEPTH_LIMIT})
    t1 = int(clock() * 1000)
    rpi = api.get("rpiDepth", {"symbol": symbol, "limit": RPI_DEPTH_LIMIT})
    t2 = int(clock() * 1000)
    return {"symbol": symbol, "local_ms": [t0, t1, t2], "depth": trim(depth), "rpi": trim(rpi)}


def record(api: Api, symbols: Iterable[str], out: Path, end_ms: int,
           clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep,
           log: Callable[[str], None] = print, run_id: str | None = None,
           sweep_s: float = SWEEP_S) -> dict:
    """Sweep until ``end_ms``; write ``rpi_books_<run>.jsonl.gz`` and ``rpi_books_run_<run>.json``."""
    symbols = list(symbols)
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.fromtimestamp(clock(), UTC)
    run_id = run_id or started.strftime("%Y%m%dT%H%M%SZ")
    data_path = out / f"rpi_books_{run_id}.jsonl.gz"
    counts = {s: 0 for s in symbols}
    errors = {s: 0 for s in symbols}
    sweeps = skipped = 0
    with gzip.open(data_path, "wt") as fh:
        while clock() * 1000 < end_ms:
            sweep_start = clock()
            if api.used_weight > WEIGHT_YIELD:
                skipped += 1
                api.used_weight = 0  # the header is only refreshed by our own calls
            else:
                sweeps += 1
                for sym in symbols:
                    if clock() * 1000 >= end_ms:
                        break
                    try:
                        fh.write(json.dumps(snapshot(api, sym, clock), separators=(",", ":")))
                        fh.write("\n")
                        counts[sym] += 1
                    except RuntimeError as e:
                        errors[sym] += 1
                        log(f"{sym}: {e}")
            wait = sweep_s - (clock() - sweep_start)
            if wait > 0:
                sleep(min(wait, max(0.0, end_ms / 1000 - clock())))
    summary = {
        "run_id": run_id, "started": started.isoformat(timespec="seconds"),
        "ended": datetime.fromtimestamp(clock(), UTC).isoformat(timespec="seconds"),
        "planned_end": datetime.fromtimestamp(end_ms / 1000, UTC).isoformat(timespec="seconds"),
        "sweep_s": sweep_s, "levels": LEVELS, "sweeps": sweeps, "sweeps_skipped": skipped,
        "http_429_or_418": api.n_429, "data_file": data_path.name,
        "symbols": {s: {"snapshots": counts[s], "errors": errors[s]} for s in symbols},
    }
    (out / f"rpi_books_run_{run_id}.json").write_text(json.dumps(summary, indent=1) + "\n")
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
    r.add_argument("--sweep-seconds", type=float, default=SWEEP_S)
    a = p.parse_args(argv)
    now = datetime.now(UTC)
    end = (now + timedelta(minutes=a.minutes) if a.minutes is not None
           else datetime.fromisoformat(a.until_iso))
    end = min(end, now + timedelta(hours=5, minutes=45))  # GitHub Actions jobs stop at 6 h
    s = record(Api(), a.symbols.split(","), a.out, int(end.timestamp() * 1000),
               sweep_s=a.sweep_seconds)
    n = sum(v["snapshots"] for v in s["symbols"].values())
    err = sum(v["errors"] for v in s["symbols"].values())
    print(f"books run {s['run_id']}: {n} snapshots, {err} errors, "
          f"{s['sweeps_skipped']} sweeps skipped, {s['http_429_or_418']} rate limits")


if __name__ == "__main__":
    main()
