"""Record Hyperliquid public data that cannot be downloaded for free later.

Two commands:

``snapshot``
    Once a day: the full leaderboard, the vault list and market metadata, saved byte for
    byte as returned, with a sha256 manifest. The leaderboard snapshot is what freezes a
    wallet cohort before outcomes are known.

``stream``
    For a fixed duration: every public trade on every listed market (main perps, spot
    pairs and builder-deployed HIP-3 perps) from the websocket, plus asset contexts (open
    interest, funding, mark and oracle prices) polled every few minutes. New markets are
    picked up every refresh interval, which matters for the memecoin launch census.

Output is gzipped JSON lines, one file per kind per UTC hour, named with a run id so that
overlapping recorders never write the same file. Each closed file is listed in
``manifest.jsonl`` with its sha256, and an optional ``--on-close`` command (for example an
upload) runs on it. Duplicates between overlapping runs are removed later by trade id.

    python -m microstructure.hyperliquid.recorder snapshot --out data/hyperliquid
    python -m microstructure.hyperliquid.recorder stream --out data/hyperliquid --duration 3600
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx

INFO_URL = "https://api.hyperliquid.xyz/info"
WS_URL = "wss://api.hyperliquid.xyz/ws"
STATS_URL = "https://stats-data.hyperliquid.xyz/Mainnet"
MAX_SUBSCRIPTIONS = 1000  # Hyperliquid's documented per-IP websocket limit
PING_EVERY_S = 30  # the server drops connections idle for 60 s


def utc_stamp(ms: int, fmt: str = "%Y%m%dT%H%M%SZ") -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).strftime(fmt)


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def run_hook(template: str | None, path: Path) -> None:
    """Run the --on-close command for one file; a failed hook is reported, not fatal."""
    if not template:
        return
    cmd = template.replace("{path}", shlex.quote(str(path)))
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(f"on-close failed ({res.returncode}) for {path}: {res.stderr.strip()}",
              file=sys.stderr, flush=True)


def append_manifest(out: Path, path: Path, **extra) -> dict:
    entry = {"file": str(path.relative_to(out)), "bytes": path.stat().st_size,
             "sha256": sha256_file(path), **extra}
    with (out / "manifest.jsonl").open("a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def gzip_bytes(path: Path, raw: bytes) -> None:
    """Write deterministic gzip (mtime 0), so equal content gives an equal file hash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(raw)


class HourlyWriter:
    """Gzipped JSON-lines files, one per (kind, UTC hour), closed and hooked on rotation."""

    def __init__(self, out: Path, run_id: str, on_close: Callable[[Path, int], None]):
        self.out, self.run_id, self.on_close = out, run_id, on_close
        self._open: dict[str, tuple[str, Path, gzip.GzipFile, object, int]] = {}

    def path_for(self, kind: str, hour: str) -> Path:
        return self.out / "stream" / hour[:8] / f"{kind}_{hour}_{self.run_id}.jsonl.gz"

    def write(self, kind: str, obj: dict, ts_ms: int) -> Path | None:
        """Write one record; return the path of a file this rotation closed, if any."""
        hour = utc_stamp(ts_ms, "%Y%m%dT%H")
        closed = None
        cur = self._open.get(kind)
        if cur is not None and cur[0] != hour:
            closed = self._close(kind)
        if kind not in self._open:
            path = self.path_for(kind, hour)
            path.parent.mkdir(parents=True, exist_ok=True)
            fh = path.open("wb")
            gz = gzip.GzipFile(fileobj=fh, mode="wb", mtime=0)
            self._open[kind] = (hour, path, gz, fh, 0)
        h, path, gz, fh, n = self._open[kind]
        gz.write((json.dumps(obj, separators=(",", ":")) + "\n").encode())
        self._open[kind] = (h, path, gz, fh, n + 1)
        return closed

    def _close(self, kind: str) -> Path:
        _, path, gz, fh, n = self._open.pop(kind)
        gz.close()
        fh.close()
        self.on_close(path, n)
        return path

    def close_all(self) -> list[Path]:
        return [self._close(k) for k in list(self._open)]


# ---------------------------------------------------------------- market lists

def live_perps(meta: dict) -> list[str]:
    return [a["name"] for a in meta["universe"] if not a.get("isDelisted")]


def spot_pairs(spot_meta: dict) -> list[str]:
    return [p["name"] for p in spot_meta["universe"]]


def builder_dexes(perp_dexs: list) -> list[str]:
    return [d["name"] for d in perp_dexs if d]  # the first entry (main dex) is null


def compact_ctxs(meta_and_ctxs: list) -> dict:
    """metaAndAssetCtxs -> {names, ctxs}; the full meta repeats every poll otherwise."""
    meta, ctxs = meta_and_ctxs
    return {"names": [a["name"] for a in meta["universe"]], "ctxs": ctxs}


def compact_spot_ctxs(spot_and_ctxs: list) -> dict:
    meta, ctxs = spot_and_ctxs
    return {"names": [p["name"] for p in meta["universe"]], "ctxs": ctxs}


# ---------------------------------------------------------------- HTTP

def _retry(fn, attempts: int = 5):
    for i in range(attempts):
        try:
            return fn()
        except (httpx.HTTPError, ValueError) as e:
            if i == attempts - 1:
                raise
            wait = 2 ** i
            print(f"retry in {wait}s after {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            time.sleep(wait)
    raise AssertionError("unreachable")


def info(client: httpx.Client, payload: dict) -> httpx.Response:
    def go():
        r = client.post(INFO_URL, json=payload)
        r.raise_for_status()
        return r
    return _retry(go)


def get(client: httpx.Client, url: str) -> httpx.Response:
    def go():
        r = client.get(url)
        r.raise_for_status()
        return r
    return _retry(go)


def market_lists(client: httpx.Client) -> tuple[list[str], list[str]]:
    """(all trade-subscription coins, builder dex names with live markets)."""
    coins = live_perps(info(client, {"type": "meta"}).json())
    coins += spot_pairs(info(client, {"type": "spotMeta"}).json())
    dexes = []
    for dex in builder_dexes(info(client, {"type": "perpDexs"}).json()):
        names = live_perps(info(client, {"type": "meta", "dex": dex}).json())
        if names:
            dexes.append(dex)
            coins += names
    return coins, dexes


# ---------------------------------------------------------------- snapshot

def snapshot(out: Path, hook: str | None) -> list[dict]:
    """Save the leaderboard, vaults and market metadata exactly as served."""
    t = now_ms()
    stamp = utc_stamp(t)
    day_dir = out / "snapshot" / stamp[:8]
    sources: list[tuple[str, Callable[[httpx.Client], httpx.Response]]] = [
        ("leaderboard", lambda c: get(c, f"{STATS_URL}/leaderboard")),
        ("vaults", lambda c: get(c, f"{STATS_URL}/vaults")),
        ("meta", lambda c: info(c, {"type": "meta"})),
        ("spotMeta", lambda c: info(c, {"type": "spotMeta"})),
        ("perpDexs", lambda c: info(c, {"type": "perpDexs"})),
        ("metaAndAssetCtxs", lambda c: info(c, {"type": "metaAndAssetCtxs"})),
        ("spotMetaAndAssetCtxs", lambda c: info(c, {"type": "spotMetaAndAssetCtxs"})),
    ]
    entries = []
    with httpx.Client(timeout=120) as client:
        dexes = builder_dexes(info(client, {"type": "perpDexs"}).json())
        for dex in dexes:
            sources.append((f"meta_{dex}", lambda c, d=dex: info(c, {"type": "meta", "dex": d})))
        for name, fetch in sources:
            fetched = now_ms()
            raw = fetch(client).content
            json.loads(raw)  # refuse to store a body that is not valid JSON
            path = day_dir / f"{name}_{stamp}.json.gz"
            gzip_bytes(path, raw)
            entry = append_manifest(out, path, kind=f"snapshot:{name}", fetched_utc=utc_stamp(fetched),
                                    raw_bytes=len(raw), raw_sha256=hashlib.sha256(raw).hexdigest())
            entries.append(entry)
            print(f"{name}: {len(raw):,} bytes", flush=True)
            run_hook(hook, path)
    run_hook(hook, out / "manifest.jsonl")
    return entries


# ---------------------------------------------------------------- stream

async def _stream(out: Path, duration_s: float, ctx_every_s: float, refresh_s: float,
                  hook: str | None, run_id: str) -> dict:
    import websockets  # optional dependency group "hl"

    stats = {"trade_msgs": 0, "trades": 0, "ctx_polls": 0, "reconnects": 0, "files": 0}

    def on_close(path: Path, n: int) -> None:
        stats["files"] += 1
        append_manifest(out, path, kind="stream:" + path.name.split("_")[0], records=n)
        run_hook(hook, path)

    writer = HourlyWriter(out, run_id, on_close)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + duration_s
    subscribed: set[str] = set()
    state: dict = {"ws": None, "dexes": []}

    def event(what: str, **kw) -> None:
        writer.write("events", {"recv_ms": now_ms(), "event": what, **kw}, now_ms())

    async def subscribe(ws, coins: list[str]) -> None:
        for coin in coins:
            if len(subscribed) >= MAX_SUBSCRIPTIONS:
                event("subscription_limit", skipped=coin)
                continue
            await ws.send(json.dumps({"method": "subscribe",
                                      "subscription": {"type": "trades", "coin": coin}}))
            subscribed.add(coin)
            await asyncio.sleep(0.02)  # stay well under 2000 sent messages per minute

    async def current_markets() -> list[str]:
        with httpx.Client(timeout=60) as c:
            coins, dexes = await asyncio.to_thread(market_lists, c)
        state["dexes"] = dexes
        return coins

    async def ws_loop() -> None:
        backoff = 1
        while loop.time() < deadline:
            try:
                coins = await current_markets()
                async with websockets.connect(WS_URL, max_size=None, ping_interval=None) as ws:
                    state["ws"] = ws
                    subscribed.clear()
                    event("connected", markets=len(coins))
                    await subscribe(ws, coins)
                    backoff = 1
                    while loop.time() < deadline:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=PING_EVERY_S)
                        except TimeoutError:
                            await ws.send(json.dumps({"method": "ping"}))
                            continue
                        t = now_ms()
                        m = json.loads(msg)
                        ch = m.get("channel")
                        if ch == "trades":
                            stats["trade_msgs"] += 1
                            stats["trades"] += len(m["data"])
                            writer.write("trades", {"recv_ms": t, "data": m["data"]}, t)
                        elif ch in ("pong", "subscriptionResponse"):
                            continue
                        else:
                            writer.write("events", {"recv_ms": t, "event": "message", "msg": m}, t)
            except (OSError, websockets.WebSocketException, httpx.HTTPError) as e:
                stats["reconnects"] += 1
                event("disconnected", error=f"{type(e).__name__}: {e}", retry_in_s=backoff)
                print(f"websocket down ({e}); retrying in {backoff}s", file=sys.stderr, flush=True)
                state["ws"] = None
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def refresh_loop() -> None:
        while loop.time() + refresh_s < deadline:
            await asyncio.sleep(refresh_s)
            ws = state["ws"]
            if ws is None:
                continue
            try:
                new = [c for c in await current_markets() if c not in subscribed]
                if new:
                    event("new_markets", coins=new)
                    await subscribe(ws, new)
            except (httpx.HTTPError, websockets.WebSocketException, OSError) as e:
                event("refresh_failed", error=str(e))

    async def ctx_loop() -> None:
        async with httpx.AsyncClient(timeout=60) as c:
            while loop.time() < deadline:
                t = now_ms()
                polls = [("perp", None, {"type": "metaAndAssetCtxs"}, compact_ctxs),
                         ("spot", None, {"type": "spotMetaAndAssetCtxs"}, compact_spot_ctxs)]
                polls += [("perp", d, {"type": "metaAndAssetCtxs", "dex": d}, compact_ctxs)
                          for d in state["dexes"]]
                for market, dex, payload, compact in polls:
                    try:
                        r = await c.post(INFO_URL, json=payload)
                        r.raise_for_status()
                        writer.write("ctx", {"recv_ms": now_ms(), "market": market, "dex": dex,
                                             **compact(r.json())}, t)
                    except (httpx.HTTPError, ValueError, KeyError) as e:
                        event("ctx_failed", market=market, dex=dex, error=str(e))
                stats["ctx_polls"] += 1
                await asyncio.sleep(max(0.0, ctx_every_s - (now_ms() - t) / 1000))

    async def stop_at_deadline() -> None:
        await asyncio.sleep(max(0.0, deadline - loop.time()))

    tasks = [asyncio.create_task(f()) for f in (ws_loop, refresh_loop, ctx_loop)]
    await stop_at_deadline()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    writer.close_all()
    run_hook(hook, out / "manifest.jsonl")
    stats["markets"] = len(subscribed)
    return stats


def stream(out: Path, duration_s: float, ctx_every_s: float = 300, refresh_s: float = 3600,
           hook: str | None = None, run_id: str | None = None) -> dict:
    run_id = run_id or os.environ.get("GITHUB_RUN_ID") or "local"
    return asyncio.run(_stream(out, duration_s, ctx_every_s, refresh_s, hook, run_id))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("snapshot", "stream"):
        s = sub.add_parser(name)
        s.add_argument("--out", type=Path, default=Path("data/hyperliquid"))
        s.add_argument("--on-close", default=None,
                       help="shell command run on each finished file; {path} is replaced")
        if name == "stream":
            s.add_argument("--duration", type=float, required=True, help="seconds")
            s.add_argument("--ctx-every", type=float, default=300, help="seconds")
            s.add_argument("--refresh-every", type=float, default=3600, help="seconds")
            s.add_argument("--run-id", default=None)
    a = p.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "snapshot":
        snapshot(a.out, a.on_close)
    else:
        print(json.dumps(stream(a.out, a.duration, a.ctx_every, a.refresh_every,
                                a.on_close, a.run_id)), flush=True)


if __name__ == "__main__":
    main()
