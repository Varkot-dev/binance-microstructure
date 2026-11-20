"""HIP-1 spot token launch census: crawl only, no outcome statistics.

Project 2 of research/hyperliquid/README.md. This script downloads, politely and with a
cache, the raw public data needed for the launch census:

1. ``spotMeta``: every spot token and every spot pair.
2. ``tokenDetails`` for every token index listed in spotMeta, with retries. Every attempt's
   HTTP status is recorded, so the set of tokens without launch data is itself data (the
   selection problem in PREREGISTRATION_DRAFT.md section 6).
3. ``spotMetaAndAssetCtxs``: current supply, mark price and 24h volume per pair.
4. Daily ``candleSnapshot`` for every pair, from time 0 (the API returns at most the last
   5,000 bars, which covers the whole spot history at 1d) to the crawl time.

It deliberately computes no survival, collapse or return statistic. Those wait until the
pre-registration is locked. The only summaries written are coverage counts (how many
tokens, pairs, failures, and the calendar span of the downloaded bars).

Raw responses are saved byte for byte (gzipped) under
``data/hyperliquid/memecoin/raw/<crawl_id>/``; ``manifest.jsonl`` there lists each file with
its sha256. Re-running with the same ``--crawl-id`` reuses every cached success and retries
only what failed.

    uv run python research/hyperliquid/memecoin/census.py crawl
    uv run python research/hyperliquid/memecoin/census.py crawl --crawl-id 20261120T000000Z
    uv run python research/hyperliquid/memecoin/census.py coverage --crawl-id <id>
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

INFO_URL = "https://api.hyperliquid.xyz/info"
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = ROOT / "data" / "hyperliquid" / "memecoin" / "raw"

# Pacing. Documented budget is 1,200 weight per minute per IP; tokenDetails and
# candleSnapshot cost 20 (plus ceil(bars/60) for candles). One request every 1.5 s is
# about 40 requests or about 900 weight per minute, under the 70% rule in DATA.md once
# candle surcharges are counted.
MIN_INTERVAL_S = 1.5
MAX_ATTEMPTS = 3
BACKOFF_BASE_S = 3.0
TIMEOUT_S = 60.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


# ---------------------------------------------------------------- pure helpers (tested)

def crawl_id_now(ms: int | None = None) -> str:
    ms = int(time.time() * 1000) if ms is None else ms
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y%m%dT%H%M%SZ")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def backoff_s(attempt: int, status: int | None, base: float = BACKOFF_BASE_S) -> float:
    """Wait before retry number ``attempt`` (1-based) after a failure with ``status``.

    Exponential in the attempt number; a 429 waits twice as long as a server error,
    because 429 is the only status that means we are going too fast."""
    w = base * 2 ** (attempt - 1)
    return w * 2 if status == 429 else w


def classify(status: int | None, body: bytes | None) -> str:
    """Outcome of one HTTP attempt: 'ok', 'null' (200 with JSON null), 'bad_json',
    'http_<code>' or 'network'. Only 'ok' is cached as a success."""
    if status is None:
        return "network"
    if status != 200:
        return f"http_{status}"
    try:
        obj = json.loads(body or b"")
    except ValueError:
        return "bad_json"
    return "null" if obj is None else "ok"


def is_retryable(outcome: str) -> bool:
    if outcome in ("network", "bad_json"):
        return True
    if outcome.startswith("http_"):
        return int(outcome[5:]) in RETRY_STATUSES
    return False


def pair_coin(pair: dict) -> str:
    """Coin string candleSnapshot expects for a spot pair: 'PURR/USDC' keeps its name,
    every other pair is '@<pair index>'."""
    name = pair.get("name", "")
    return name if "/" in name else f"@{pair['index']}"


def safe_name(s: str) -> str:
    """Filesystem-safe file stem ('@107' -> 'at107', 'PURR/USDC' -> 'PURR_USDC')."""
    return s.replace("@", "at").replace("/", "_").replace(":", "_")


def missing_indices(indices: list[int]) -> list[int]:
    """Token indices between 0 and the maximum that spotMeta does not list."""
    if not indices:
        return []
    have = set(indices)
    return [i for i in range(max(have) + 1) if i not in have]


def candle_span(bars: list[dict]) -> dict:
    """Coverage of one candle response: number of bars, number with volume > 0 (earlier
    bars are back-filled with v = 0, DATA.md section 4), and the first and last bar open
    time of each. Coverage only, no prices."""
    traded = [b for b in bars if float(b.get("v", 0) or 0) > 0]
    t = [int(b["t"]) for b in bars]
    tt = [int(b["t"]) for b in traded]
    return {"n_bars": len(bars), "n_traded": len(traded),
            "first_t": min(t) if t else None, "last_t": max(t) if t else None,
            "first_traded_t": min(tt) if tt else None,
            "last_traded_t": max(tt) if tt else None}


def summarize_status(rows: list[dict]) -> dict:
    """Counts of final outcomes and of how many attempts the successes needed."""
    final = Counter(r["final"] for r in rows)
    tries = Counter(len(r["attempts"]) for r in rows if r["final"] == "ok")
    return {"n": len(rows), "final": dict(sorted(final.items())),
            "attempts_for_ok": {str(k): v for k, v in sorted(tries.items())}}


def ms_to_date(ms: int | None) -> str | None:
    return None if ms is None else datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- crawling

@dataclass
class Client:
    out: Path
    min_interval: float = MIN_INTERVAL_S
    http: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=TIMEOUT_S))
    _last: float = 0.0
    n_requests: int = 0

    def _pace(self) -> None:
        wait = self._last + self.min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def post(self, body: dict) -> tuple[int | None, bytes | None, str | None]:
        self._pace()
        self.n_requests += 1
        try:
            r = self.http.post(INFO_URL, json=body)
            return r.status_code, r.content, None
        except httpx.HTTPError as e:
            return None, None, type(e).__name__

    def fetch(self, rel: str, body: dict) -> dict:
        """Fetch ``body`` into ``out/rel`` (gzipped) unless already cached. Returns a status
        row with every attempt; failures are never written as data files."""
        path = self.out / rel
        if path.exists():
            final = "null" if load_gz(path) is None else "ok"
            return {"file": rel, "final": final, "attempts": [], "cached": True}
        attempts = []
        outcome = "network"
        for k in range(1, MAX_ATTEMPTS + 1):
            status, content, err = self.post(body)
            outcome = classify(status, content)
            attempts.append({"status": status, "outcome": outcome, "error": err,
                             "at": crawl_id_now()})
            if outcome in ("ok", "null"):
                break
            if not is_retryable(outcome) or k == MAX_ATTEMPTS:
                break
            time.sleep(backoff_s(k, status))
        row = {"file": rel, "final": outcome, "attempts": attempts, "cached": False}
        if outcome in ("ok", "null"):
            # A JSON null is a real answer from the API; keep it so it is auditable.
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(gzip.compress(content))
            tmp.rename(path)
            with (self.out / "manifest.jsonl").open("a") as f:
                f.write(json.dumps({"file": rel, "bytes": len(content),
                                    "sha256": sha256_bytes(content), "outcome": outcome,
                                    "fetched_at": attempts[-1]["at"]}, sort_keys=True) + "\n")
        return row


def load_gz(path: Path):
    return json.loads(gzip.decompress(path.read_bytes()))


def crawl(out_root: Path, crawl_id: str, end_ms: int | None, only: str | None) -> Path:
    out = out_root / crawl_id
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "run.json"
    if meta_path.exists():
        run = json.loads(meta_path.read_text())
    else:
        run = {"crawl_id": crawl_id, "started": crawl_id_now(),
               "end_ms": end_ms or int(time.time() * 1000)}
        meta_path.write_text(json.dumps(run, indent=1))
    end_ms = run["end_ms"]  # fixed per crawl so a resumed crawl asks the same question
    c = Client(out)

    for kind in ("spotMeta", "spotMetaAndAssetCtxs"):
        row = c.fetch(f"{kind}.json.gz", {"type": kind})
        if row["final"] != "ok":
            raise SystemExit(f"{kind} failed: {row}")
    meta = load_gz(out / "spotMeta.json.gz")
    tokens, pairs = meta["tokens"], meta["universe"]
    print(f"spotMeta: {len(tokens)} tokens, {len(pairs)} pairs", flush=True)

    if only in (None, "tokens"):
        rows = []
        for i, t in enumerate(sorted(tokens, key=lambda t: t["index"])):
            r = c.fetch(f"tokenDetails/{t['index']:05d}_{t['tokenId']}.json.gz",
                        {"type": "tokenDetails", "tokenId": t["tokenId"]})
            r.update(index=t["index"], tokenId=t["tokenId"], name=t["name"])
            rows.append(r)
            if i % 50 == 0:
                print(f"tokenDetails {i}/{len(tokens)} {t['name']}: {r['final']}", flush=True)
        _merge_status(out / "status_tokenDetails.jsonl", rows)

    if only in (None, "candles"):
        rows = []
        for i, p in enumerate(sorted(pairs, key=lambda p: p["index"])):
            coin = pair_coin(p)
            r = c.fetch(f"candles_1d/{p['index']:05d}_{safe_name(coin)}.json.gz",
                        {"type": "candleSnapshot",
                         "req": {"coin": coin, "interval": "1d", "startTime": 0,
                                 "endTime": int(end_ms)}})
            r.update(pair_index=p["index"], coin=coin, tokens=p["tokens"])
            rows.append(r)
            if i % 50 == 0:
                print(f"candles {i}/{len(pairs)} {coin}: {r['final']}", flush=True)
        _merge_status(out / "status_candles.jsonl", rows)

    run["finished"] = crawl_id_now()
    run["requests_this_pass"] = c.n_requests
    meta_path.write_text(json.dumps(run, indent=1))
    return out


def _merge_status(path: Path, rows: list[dict]) -> None:
    """Keep attempt history across resumed passes: a cached row inherits its earlier
    attempts, so failures that later succeeded stay visible."""
    old = {}
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            old[r["file"]] = r
    with path.open("w") as f:
        for r in rows:
            prev = old.get(r["file"])
            if prev is not None:
                r["attempts"] = prev["attempts"] + r["attempts"]
                if r["cached"]:
                    r["cached"] = prev.get("cached", False)
            f.write(json.dumps(r, sort_keys=True) + "\n")


def coverage(out: Path) -> dict:
    """Coverage numbers only: counts, failures by status, calendar span of bars."""
    meta = load_gz(out / "spotMeta.json.gz")
    tokens, pairs = meta["tokens"], meta["universe"]
    st_t = [json.loads(x) for x in (out / "status_tokenDetails.jsonl").read_text().splitlines()]
    st_c = [json.loads(x) for x in (out / "status_candles.jsonl").read_text().splitlines()]
    ever = Counter(a["outcome"] for r in st_t for a in r["attempts"])
    spans = []
    for r in st_c:
        if r["final"] == "ok":
            bars = load_gz(out / r["file"]) or []
            spans.append({"coin": r["coin"], **candle_span(bars)})
    first = [s["first_traded_t"] for s in spans if s["first_traded_t"] is not None]
    last = [s["last_traded_t"] for s in spans if s["last_traded_t"] is not None]
    run = json.loads((out / "run.json").read_text())
    fails = [{"index": r["index"], "name": r["name"], "final": r["final"],
              "statuses": [a["status"] for a in r["attempts"]]}
             for r in st_t if r["final"] != "ok"]
    return {
        "crawl_id": out.name, "end_ms": run["end_ms"], "end_date": ms_to_date(run["end_ms"]),
        "n_tokens": len(tokens), "n_pairs": len(pairs),
        "max_token_index": max(t["index"] for t in tokens),
        "n_missing_token_indices": len(missing_indices([t["index"] for t in tokens])),
        "tokenDetails": summarize_status(st_t),
        "tokenDetails_attempt_outcomes": dict(sorted(ever.items())),
        "tokenDetails_not_ok": fails,
        "candles": summarize_status(st_c),
        "pairs_with_any_traded_bar": sum(s["n_traded"] > 0 for s in spans),
        "pairs_with_no_traded_bar": sum(s["n_traded"] == 0 for s in spans),
        "total_bars": sum(s["n_bars"] for s in spans),
        "total_traded_bars": sum(s["n_traded"] for s in spans),
        "first_traded_date": ms_to_date(min(first)) if first else None,
        "last_traded_date": ms_to_date(max(last)) if last else None,
        "max_bars_one_pair": max((s["n_bars"] for s in spans), default=0),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("crawl")
    a.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a.add_argument("--crawl-id", default=None)
    a.add_argument("--end-ms", type=int, default=None)
    a.add_argument("--only", choices=["tokens", "candles"], default=None)
    b = sub.add_parser("coverage")
    b.add_argument("--out", type=Path, default=DEFAULT_OUT)
    b.add_argument("--crawl-id", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "crawl":
        out = crawl(args.out, args.crawl_id or crawl_id_now(), args.end_ms, args.only)
        print(f"done: {out}", flush=True)
    else:
        out = args.out / args.crawl_id
        cov = coverage(out)
        (out / "coverage.json").write_text(json.dumps(cov, indent=1))
        json.dump({k: v for k, v in cov.items() if k != "tokenDetails_not_ok"}, sys.stdout,
                  indent=1)
        print()


if __name__ == "__main__":
    main()
