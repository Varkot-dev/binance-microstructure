"""D1 data inventory: Binance listing and delisting announcements vs contract lives.

DATA AND PLAN ONLY. This script never opens a price or volume value: it reads file
listings (which daily files exist on data.binance.vision) and dates. No pre-announcement
statistic is computed here.

Subcommands (run from the repository root):

    .venv/bin/python research/announcements/d1_inventory.py probe
        One request to Binance's announcement list endpoint; prints the HTTP outcome.
    .venv/bin/python research/announcements/d1_inventory.py ingest
        Parse saved list pages (data/announcements/raw/*.json, the JSON that
        www.binance.com/bapi/composite/v1/public/cms/article/list/query returns) into
        research/announcements/data/announcements.csv. Titles only, no bodies.
    .venv/bin/python research/announcements/d1_inventory.py events
        Candidate events from contract_lifecycle.csv (futures listings and delistings,
        2023-01 to 2026-10) with archive data availability (S3 listings only; cached in
        data/announcements/raw/s3_cache.json). Writes
        research/announcements/data/event_inventory.csv.
    .venv/bin/python research/announcements/d1_inventory.py match [--file PATH]
        Match an announcement table (announcements.csv, or a filled MANUAL_TEMPLATE.csv)
        to contract lives and write research/announcements/data/matches.csv plus a
        summary of lead times and unmatched cases.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import json
import re
import statistics
import sys
import threading
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE = ROOT / "research" / "market_evolution" / "data" / "contract_lifecycle.csv"
AGG_CACHE = ROOT / "data" / "universe" / "lifecycle_cache" / "daily_aggtrades"
RAW = ROOT / "data" / "announcements" / "raw"
OUT = ROOT / "research" / "announcements" / "data"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
CMS_LIST = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
CATALOGS = {48: "New Cryptocurrency Listing", 161: "Delisting", 49: "Latest Binance News"}

START, END = dt.date(2023, 1, 1), dt.date(2026, 10, 31)
ARCHIVE_END = dt.date(2026, 11, 16)
BASELINE_DAYS = 30  # own-history baseline before the -72h window
PRE_DAYS = 3  # the -72h..-1h window
NEED_BEFORE = BASELINE_DAYS + PRE_DAYS + 2  # days of data needed before announcement day
DELIST_LEAD_ASSUMED = 14  # announcement assumed at most 14 days before the last trade day
MATCH_LISTING = (-3, 60)  # first_trade_day - announcement date, days
MATCH_DELIST = (0, 60)  # last_trade_day - announcement date, days

FIELDS = ["article_code", "release_time_utc", "time_precision", "type", "market", "symbols",
          "title", "catalog", "source"]


# --------------------------------------------------------------------------
# Title rules (pure)
# --------------------------------------------------------------------------
FUT_SYM = re.compile(r"\b((?:1000000|1000|1M)?[A-Z0-9]{2,20}(?:USDT|USDC))\b")
SPOT_TICKER = re.compile(r"\(([A-Z0-9]{2,15})\)")


def classify(title: str) -> tuple[str, str]:
    """(type, market) from a title: type listing/delisting/other, market futures/spot/both."""
    t = title.lower()
    fut = "futures" in t or "perpetual" in t or "usdⓢ-m" in t or "usds-m" in t
    if "delist" in t or "will cease" in t or "removal of" in t:
        if "margin will delist" in t or "removal of spot trading pairs" in t:
            return "other", "spot" if not fut else "futures"
        head = t.split("delist")[0]
        if "futures" in head or "perpetual" in head:
            return "delisting", "futures"  # "Binance Futures Will Delist ..."
        return "delisting", "both" if fut else "spot"  # spot notice that also names perps
    if fut and re.search(r"will launch|launches|will list", t) and "perpetual" in t:
        return "listing", "futures"
    if re.search(r"binance will list|will add .* on binance spot", t) and not fut:
        return "listing", "spot"
    return "other", "futures" if fut else "spot"


def parse_symbols(title: str, market: str) -> list[str]:
    """Contract symbols named in a title (futures), else spot tickers in parentheses + USDT."""
    syms = [s for s in FUT_SYM.findall(title) if not s.startswith(("USDT", "USDC"))]
    if syms:
        return sorted(set(syms))
    if market not in ("spot", "both"):
        return []
    tickers = SPOT_TICKER.findall(title)
    m = re.search(r"[Dd]elist\s+(.+?)\s+on\s+\d{4}-\d{2}-\d{2}", title)
    if not tickers and m:  # "Binance Will Delist ALPHA, BSW & KMD on 2025-07-04"
        tickers = [x for x in re.split(r",\s*|\s*&\s*|\s+and\s+", m.group(1))
                   if re.fullmatch(r"[A-Z0-9]{2,15}", x)]
    return sorted({f"{t}USDT" for t in tickers})


def spot_candidates(fut_symbol: str) -> list[str]:
    """Binance spot pairs that could carry the same coin as a USDT-M contract."""
    out = [fut_symbol]
    m = re.match(r"^(1000000|1000|1M)(.+)$", fut_symbol)
    if m:
        out.append(m.group(2))
    return out


# --------------------------------------------------------------------------
# Announcement lists
# --------------------------------------------------------------------------
def probe() -> int:
    try:
        r = httpx.get(CMS_LIST, params={"type": 1, "catalogId": 161, "pageNo": 1,
                                        "pageSize": 5}, timeout=20)
        print("HTTP", r.status_code, r.text[:300])
        return 0 if r.status_code == 200 else 1
    except httpx.HTTPError as e:
        print("unreachable:", repr(e))
        return 1


def collect(max_pages: int = 60) -> None:
    """Polite collector (1 request per second, stops at the first refusal)."""
    RAW.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30) as c:
        for cat in (48, 161):
            for page in range(1, max_pages + 1):
                path = RAW / f"cms_list_{cat}_{page:03d}.json"
                if path.exists():
                    continue
                r = c.get(CMS_LIST, params={"type": 1, "catalogId": cat, "pageNo": page,
                                            "pageSize": 50})
                time.sleep(1.0)
                if r.status_code != 200:
                    print("stopped: HTTP", r.status_code, "catalog", cat, "page", page)
                    return
                path.write_text(r.text)
                if not list(_articles(r.json())):
                    break


def _articles(obj, catalog: str = ""):
    """Yield (catalog, article dict) for every dict carrying code, title and releaseDate."""
    if isinstance(obj, dict):
        cat = obj.get("catalogName", catalog) or catalog
        if {"code", "title", "releaseDate"} <= obj.keys():
            yield cat, obj
        for v in obj.values():
            yield from _articles(v, cat)
    elif isinstance(obj, list):
        for v in obj:
            yield from _articles(v, catalog)


def ingest() -> None:
    rows: dict[str, dict] = {}
    files = sorted(RAW.glob("*.json"))
    files = [f for f in files if f.name != "s3_cache.json"]
    for f in files:
        for cat, a in _articles(json.loads(f.read_text())):
            ts = dt.datetime.fromtimestamp(int(a["releaseDate"]) / 1000, dt.UTC)
            if not (START <= ts.date() <= END + dt.timedelta(days=16)):
                continue
            typ, market = classify(a["title"])
            rows[a["code"]] = {
                "article_code": a["code"], "release_time_utc": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "time_precision": "second", "type": typ, "market": market,
                "symbols": ";".join(parse_symbols(a["title"], market)),
                "title": a["title"].strip(), "catalog": cat, "source": "bapi_list"}
    if not rows:
        print(f"no announcement pages under {RAW}; nothing written")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    out = sorted(rows.values(), key=lambda r: r["release_time_utc"])
    with open(OUT / "announcements.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS)
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)} announcements from {len(files)} files")


# --------------------------------------------------------------------------
# Archive availability (S3 listings only, cached)
# --------------------------------------------------------------------------
class S3Cache:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, list[str]] = json.loads(path.read_text()) if path.exists() else {}
        self.lock = threading.Lock()
        self.client = httpx.Client(timeout=60)

    def keys(self, prefix: str, max_keys: int = 4) -> list[str]:
        with self.lock:
            if prefix in self.data:
                return self.data[prefix]
        for attempt in range(5):
            try:
                r = self.client.get(S3, params={"prefix": prefix, "max-keys": max_keys})
                r.raise_for_status()
                break
            except httpx.HTTPError:
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        keys = [k for k in re.findall(r"<Key>([^<]+)</Key>", r.text) if k.endswith(".zip")]
        with self.lock:
            self.data[prefix] = keys
        return keys

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, sort_keys=True))


def first_spot_day(s3: S3Cache, pair: str) -> dt.date | None:
    keys = s3.keys(f"data/spot/daily/aggTrades/{pair}/", max_keys=2)
    m = re.search(r"(\d{4}-\d{2}-\d{2})\.zip$", keys[0]) if keys else None
    return dt.date.fromisoformat(m.group(1)) if m else None


def spot_on(s3: S3Cache, pair: str, day: dt.date) -> bool:
    return bool(s3.keys(f"data/spot/daily/aggTrades/{pair}/{pair}-aggTrades-{day}.zip"))


def fut_kline_1m_on(s3: S3Cache, sym: str, day: dt.date) -> bool:
    return bool(s3.keys(f"data/futures/um/daily/klines/{sym}/1m/{sym}-1m-{day}.zip"))


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def load_lifecycle() -> list[dict]:
    with open(LIFECYCLE) as fh:
        return list(csv.DictReader(fh))


def listing_row(s3: S3Cache, r: dict, renamed_to: set[str]) -> dict:
    sym, d0 = r["symbol"], _d(r["first_trade_day"])
    kind = "relisting" if int(r["life"]) > 1 else (
        "rename_successor" if sym in renamed_to else "new")
    out = {"event": "futures_listing", "symbol": sym, "life": r["life"], "kind": kind,
           "futures_day": str(d0), "spot_pair": "", "spot_first_day": "",
           "spot_status": "no_binance_spot", "spot_on_d_minus_1": "",
           f"spot_on_d_minus_{NEED_BEFORE}": ""}
    for pair in spot_candidates(sym):
        f = first_spot_day(s3, pair)
        if f is None:
            continue
        out["spot_pair"], out["spot_first_day"] = pair, str(f)
        lead = (d0 - f).days
        if lead <= 0:
            out["spot_status"] = "spot_same_day_or_after"
        else:
            on1 = spot_on(s3, pair, d0 - dt.timedelta(days=1))
            onn = spot_on(s3, pair, d0 - dt.timedelta(days=NEED_BEFORE))
            out["spot_on_d_minus_1"] = int(on1)
            out[f"spot_on_d_minus_{NEED_BEFORE}"] = int(onn)
            if on1 and onn:
                out["spot_status"] = "spot_before_with_baseline"
            elif on1:
                out["spot_status"] = "spot_before_short_history"
            else:
                out["spot_status"] = "spot_not_trading_at_launch"
        break
    return out


def delisting_row(s3: S3Cache, r: dict) -> dict:
    sym, first, last = r["symbol"], _d(r["first_trade_day"]), _d(r["last_trade_day"])
    path = AGG_CACHE / f"{sym}.json"
    days = set(json.loads(path.read_text())) if path.exists() else set()
    lo = last - dt.timedelta(days=DELIST_LEAD_ASSUMED + NEED_BEFORE)
    window = [lo + dt.timedelta(days=i) for i in range((last - lo).days)]
    have = sum(str(d) in days for d in window)
    probe_day = last - dt.timedelta(days=DELIST_LEAD_ASSUMED)
    pairs = [p for p in spot_candidates(sym) if first_spot_day(s3, p)]
    return {"event": "futures_delisting", "symbol": sym, "life": r["life"], "kind": r["status"],
            "futures_day": str(last), "first_trade_day": str(first),
            "age_days_at_last": (last - first).days,
            "agg_days_in_window": have, "window_days": len(window),
            "kline_1m_on_probe_day": int(fut_kline_1m_on(s3, sym, probe_day)),
            "baseline_ok": int(first <= lo and have >= len(window) - 2),
            "spot_pair": pairs[0] if pairs else "",
            "spot_alive_at_last": int(spot_on(s3, pairs[0], last)) if pairs else ""}


def events(workers: int = 4) -> None:
    lc = load_lifecycle()
    renamed_to = {r["successor"] for r in lc if r["status"] in ("renamed", "merged")}
    s3 = S3Cache(RAW / "s3_cache.json")
    lst = [r for r in lc if START <= _d(r["first_trade_day"]) <= END
           and r["status"] != "index"]
    dl = [r for r in lc if r["status"] in ("delisted", "reused-symbol")
          and START <= _d(r["last_trade_day"]) <= ARCHIVE_END]
    rows: list[dict] = []
    try:
        with cf.ThreadPoolExecutor(workers) as ex:
            rows += list(ex.map(lambda r: listing_row(s3, r, renamed_to), lst))
            rows += list(ex.map(lambda r: delisting_row(s3, r), dl))
    finally:
        s3.save()
    OUT.mkdir(parents=True, exist_ok=True)
    cols: list[str] = []
    for r in rows:
        cols += [k for k in r if k not in cols]
    with open(OUT / "event_inventory.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, cols)
        w.writeheader()
        w.writerows(rows)
    summarize_events(rows)


def summarize_events(rows: list[dict]) -> None:
    from collections import Counter
    L = [r for r in rows if r["event"] == "futures_listing"]
    D = [r for r in rows if r["event"] == "futures_delisting"]
    print(f"futures listings {START}..{END}: {len(L)}")
    print("  by kind:", dict(Counter(r["kind"] for r in L)))
    print("  by year:", dict(sorted(Counter(r["futures_day"][:4] for r in L).items())))
    print("  spot status:", dict(Counter(r["spot_status"] for r in L)))
    ok = [r for r in L if r["spot_status"] == "spot_before_with_baseline" and r["kind"] == "new"]
    print("  new + Binance spot with baseline, by year:",
          dict(sorted(Counter(r["futures_day"][:4] for r in ok).items())))
    print(f"futures delistings {START}..{ARCHIVE_END}: {len(D)}")
    print("  by kind:", dict(Counter(r["kind"] for r in D)))
    print("  by year:", dict(sorted(Counter(r["futures_day"][:4] for r in D).items())))
    print("  baseline_ok:", sum(int(r["baseline_ok"]) for r in D),
          " 1m klines on probe day:", sum(int(r["kline_1m_on_probe_day"]) for r in D))
    print("  spot alive at last day:", dict(Counter(str(r["spot_alive_at_last"]) for r in D)))


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------
def parse_time(s: str) -> dt.datetime:
    s = s.strip().replace("T", " ").rstrip("Z")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt).replace(tzinfo=dt.UTC)
        except ValueError:
            pass
    raise ValueError(f"bad time {s!r}")


def match(path: Path) -> None:
    lc = load_lifecycle()
    by_sym: dict[str, list[dict]] = {}
    for r in lc:
        by_sym.setdefault(r["symbol"], []).append(r)
    with open(path) as fh:
        ann = [a for a in csv.DictReader(fh) if a.get("release_time_utc", "").strip()]
    out, unmatched = [], []
    for a in ann:
        if a["type"] not in ("listing", "delisting") or a["market"] not in ("futures", "both"):
            continue
        t = parse_time(a["release_time_utc"])
        syms = [s for s in a["symbols"].split(";") if s] or parse_symbols(a["title"], a["market"])
        for s in syms:
            best = None
            for life in by_sym.get(s, []):
                day = _d(life["first_trade_day" if a["type"] == "listing" else "last_trade_day"])
                gap = (day - t.date()).days
                lo, hi = MATCH_LISTING if a["type"] == "listing" else MATCH_DELIST
                if lo <= gap <= hi and (best is None or gap < best[0]):
                    best = (gap, life, day)
            if best is None:
                unmatched.append({**a, "symbol": s, "reason": "no life in window"
                                  if s in by_sym else "symbol not in lifecycle"})
                continue
            gap, life, day = best
            lead_h = (dt.datetime.combine(day, dt.time(), dt.UTC) - t).total_seconds() / 3600
            out.append({"article_code": a["article_code"], "type": a["type"], "symbol": s,
                        "life": life["life"], "release_time_utc": a["release_time_utc"],
                        "time_precision": a.get("time_precision", ""),
                        "contract_day": str(day), "lead_days": gap,
                        "lead_hours_to_day_start": round(lead_h, 2),
                        "status": life["status"]})
    OUT.mkdir(parents=True, exist_ok=True)
    if out:
        with open(OUT / "matches.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, list(out[0]))
            w.writeheader()
            w.writerows(out)
    for typ in ("listing", "delisting"):
        lead = [m["lead_days"] for m in out if m["type"] == typ]
        if lead:
            q = statistics.quantiles(lead, n=4) if len(lead) > 1 else [lead[0]] * 3
            print(f"{typ}: {len(lead)} matched; lead days min {min(lead)} q1 {q[0]} "
                  f"median {q[1]} q3 {q[2]} max {max(lead)}")
        else:
            print(f"{typ}: 0 matched")
    print(f"unmatched symbol mentions: {len(unmatched)}")
    for u in unmatched[:30]:
        print("  ", u["release_time_utc"], u["type"], u["symbol"], "|", u["reason"])
    # Contract events without an announcement in the table's time span
    if ann:
        t0 = min(parse_time(a["release_time_utc"]) for a in ann).date()
        t1 = max(parse_time(a["release_time_utc"]) for a in ann).date()
        got = {(m["symbol"], m["life"], m["type"]) for m in out}
        miss_l = [r for r in lc if t0 <= _d(r["first_trade_day"]) <= t1
                  and (r["symbol"], r["life"], "listing") not in got]
        miss_d = [r for r in lc if r["status"] in ("delisted", "reused-symbol")
                  and t0 <= _d(r["last_trade_day"]) <= t1
                  and (r["symbol"], r["life"], "delisting") not in got]
        print(f"contract lives {t0}..{t1} with no matched announcement: listings "
              f"{len(miss_l)}, delistings {len(miss_d)}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe")
    sub.add_parser("collect")
    sub.add_parser("ingest")
    sub.add_parser("events")
    m = sub.add_parser("match")
    m.add_argument("--file", type=Path, default=OUT / "announcements.csv")
    a = p.parse_args()
    if a.cmd == "probe":
        sys.exit(probe())
    if a.cmd == "collect":
        collect()
    elif a.cmd == "ingest":
        ingest()
    elif a.cmd == "events":
        events()
    elif a.cmd == "match":
        match(a.file)


if __name__ == "__main__":
    main()
