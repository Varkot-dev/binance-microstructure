"""Build the contract lifecycle table: one row per life of every USDT-M perpetual.

Source: the S3 listing of data.binance.vision, `data/futures/um/daily/aggTrades/`.
aggTrades daily files stop on the last trading day (klines, metrics and funding keep
publishing empty "ghost" files after death), so the first and last day with an aggTrades
file are the trading dates. Daily 1d klines are used only for one close price on a
boundary day, to test rename candidates.

Run from the repository root:

    .venv/bin/python research/market_evolution/build_lifecycle.py

Resumable: every symbol's day listing is cached under
`data/universe/lifecycle_cache/` and reused on the next run (pass --refresh to list the
symbols again whose cached listing reaches the archive end, i.e. the live ones).

Outputs `research/market_evolution/data/contract_lifecycle.csv`.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import io
import json
import random
import re
import sys
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "universe" / "lifecycle_cache"
OUT_CSV = ROOT / "research" / "market_evolution" / "data" / "contract_lifecycle.csv"

S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DL = "https://data.binance.vision"
AGG_PFX = "data/futures/um/daily/aggTrades/"

# --------------------------------------------------------------------------
# Rules (pure; tested offline in tests/research/test_lifecycle.py)
# --------------------------------------------------------------------------
# Known classification of the 2023 cohort, from Q14
# (src/microstructure/analyses/q14_survivorship.py).
RENAMED = {
    "RNDRUSDT": "RENDERUSDT", "MATICUSDT": "POLUSDT", "GALUSDT": "GUSDT",
    "FTMUSDT": "SUSDT", "MKRUSDT": "SKYUSDT", "EOSUSDT": "AUSDT", "DARUSDT": "DUSDT",
    "BNXUSDT": "FORMUSDT", "FXSUSDT": "FRAXUSDT", "KLAYUSDT": "KAIAUSDT",
}
MERGED = {"AGIXUSDT": "FETUSDT", "OCEANUSDT": "FETUSDT"}
INDEX_CONTRACTS = ("BLUEBIRDUSDT", "FOOTBALLUSDT", "DEFIUSDT")

ALIVE_WINDOW_DAYS = 3  # alive if the last trading day is within 3 days of the archive end
REUSE_GAP_DAYS = 30  # a gap of more than 30 days between trading days starts a new life
CANDIDATE_WINDOW_DAYS = 14  # successor must start within 14 days of the old contract's end
DENOMINATIONS = (1.0, 1e3, 1e6)  # allowed price ratios (either direction)
PRICE_TOLERANCE = 0.10  # |ratio / denomination - 1| at most 10 %


def is_usdt_perp(sym: str) -> bool:
    """A USDT-M perpetual: ends in USDT and has no underscore (quarterlies have one)."""
    return sym.endswith("USDT") and "_" not in sym and len(sym) > 4


def split_lives(days: list[date], gap_days: int = REUSE_GAP_DAYS) -> list[list[date]]:
    """Split sorted trading days into lives separated by more than `gap_days` days."""
    days = sorted(days)
    lives: list[list[date]] = []
    for d in days:
        if lives and (d - lives[-1][-1]).days <= gap_days:
            lives[-1].append(d)
        else:
            lives.append([d])
    return lives


def is_alive(last_day: date, archive_end: date, window: int = ALIVE_WINDOW_DAYS) -> bool:
    return (archive_end - last_day).days <= window


def price_match(old_close: float | None, new_close: float | None,
                tol: float = PRICE_TOLERANCE) -> float | None:
    """Denomination (1, 1000, 1e6 or their inverses) that makes the two closes agree
    within `tol`, as old/new; None if none does."""
    if not old_close or not new_close or old_close <= 0 or new_close <= 0:
        return None
    r = old_close / new_close
    for k in DENOMINATIONS:
        for kk in (k, 1.0 / k):
            if abs(r / kk - 1.0) <= tol:
                return kk
    return None


def ticker_multiplier(sym: str) -> float:
    """Units per contract implied by the ticker prefix: 1000PEPE is 1e3, 1000000BOB and
    1MBABYDOGE are 1e6, anything else 1."""
    if sym.startswith("1000000") or re.match(r"1M[A-Z]", sym):
        return 1e6
    if sym.startswith("1000"):
        return 1e3
    return 1.0


def denomination_consistent(old: str, new: str, k: float) -> bool:
    """A price ratio old/new of k is only a plausible rename if the tickers say so:
    k must equal multiplier(old) / multiplier(new) (1 for two plain tickers)."""
    want = ticker_multiplier(old) / ticker_multiplier(new)
    return abs(k / want - 1.0) < 1e-9


def drop_artifact_days(days: dict[str, int], positive_rows: dict[str, int],
                       max_bytes: int = 1000) -> tuple[list[str], list[str]]:
    """Split a symbol's {day: zip size} into (trading days, artifact days). A day is an
    artifact if its file is under `max_bytes` and was checked to hold no print with a
    positive price (`positive_rows[day] == 0`); unchecked tiny days are kept."""
    keep, drop = [], []
    for d in sorted(days):
        if days[d] < max_bytes and positive_rows.get(d) == 0:
            drop.append(d)
        else:
            keep.append(d)
    return keep, drop


def window_candidates(end: date, starts: dict[str, date], own: str,
                      window: int = CANDIDATE_WINDOW_DAYS) -> list[str]:
    """Contracts (life keys) other than `own` whose first day is within `window` days
    of `end`, either side."""
    return sorted(k for k, s in starts.items()
                  if k != own and abs((s - end).days) <= window)


def classify(sym: str, life_idx: int, n_lives: int, alive: bool) -> tuple[str, str, str]:
    """(status, successor symbol, evidence) from the known lists and the life structure.

    Earlier lives of a reused symbol are `reused-symbol`; the known Q14 lists apply to a
    symbol's last life; a dead contract outside them is `delisted` (rename candidates
    from the price rule are reported separately, not asserted)."""
    last_life = life_idx == n_lives - 1
    if not last_life:
        return ("reused-symbol", sym,
                f"symbol trades again after a gap of more than {REUSE_GAP_DAYS} days")
    if sym in INDEX_CONTRACTS:
        return "index", "", "Binance index perpetual (Q14 list)"
    if sym in RENAMED:
        return "renamed", RENAMED[sym], "token rename or migration (Q14 list)"
    if sym in MERGED:
        return "merged", MERGED[sym], "merged into FET, ASI alliance 2024 (Q14 list)"
    if alive:
        return "alive", "", f"trades within {ALIVE_WINDOW_DAYS} days of archive end"
    return "delisted", "", "stopped trading; not in the Q14 rename/merge/index lists"


# --------------------------------------------------------------------------
# Network (S3 listing and tiny downloads), all cached
# --------------------------------------------------------------------------
def _client():
    return httpx.Client(timeout=60, follow_redirects=True)


_CLIENT = None


def client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = _client()
    return _CLIENT


def list_s3(prefix: str, delimiter: str | None = None):
    """Paginated S3 listing. Returns common prefixes (with a delimiter) or (key, size).
    Each <Contents> block is parsed on its own (newer entries carry checksum tags)."""
    out: list = []
    marker = ""
    while True:
        params = {"prefix": prefix, "marker": marker}
        if delimiter:
            params["delimiter"] = delimiter
        for attempt in range(5):
            try:
                r = client().get(S3, params=params)
                r.raise_for_status()
                break
            except httpx.HTTPError:
                if attempt == 4:
                    raise
        t = r.text
        if delimiter:
            items = re.findall(r"<CommonPrefixes><Prefix>([^<]+)</Prefix>", t)
            last = items[-1] if items else None
        else:
            items = []
            for b in re.findall(r"<Contents>(.*?)</Contents>", t, re.DOTALL):
                k = re.search(r"<Key>([^<]+)</Key>", b).group(1)
                s = int(re.search(r"<Size>(\d+)</Size>", b).group(1))
                items.append((k, s))
            last = items[-1][0] if items else None
        out += items
        if "<IsTruncated>true</IsTruncated>" not in t or last is None:
            return out
        m = re.search(r"<NextMarker>([^<]+)</NextMarker>", t)
        marker = m.group(1) if m else last


def symbol_days(sym: str, refresh_after: date | None) -> dict[str, int]:
    """{YYYY-MM-DD: zip size} of the symbol's daily aggTrades files, cached."""
    f = CACHE / "daily_aggtrades" / f"{sym}.json"
    if f.exists():
        cached = json.loads(f.read_text())
        if refresh_after is None or not cached or max(cached) < refresh_after.isoformat():
            return cached
    out = {}
    for k, s in list_s3(f"{AGG_PFX}{sym}/"):
        m = re.search(r"-aggTrades-(\d{4}-\d{2}-\d{2})\.zip$", k)
        if m:
            out[m.group(1)] = s
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, sort_keys=True))
    return out


def fetch_zip_csv(url: str) -> list[list[str]] | None:
    r = client().get(url)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        text = z.read(z.namelist()[0]).decode()
    return list(csv.reader(io.StringIO(text)))


def _data_rows(rows: list[list[str]]) -> list[list[str]]:
    return [r for r in rows if r and r[0][:1].isdigit()]


def daily_close(sym: str, day: str) -> float | None:
    """1d kline close for one day, from the daily file, else the monthly 1d file."""
    rows = fetch_zip_csv(f"{DL}/data/futures/um/daily/klines/{sym}/1d/{sym}-1d-{day}.zip")
    if rows is None:
        mo = day[:7]
        rows = fetch_zip_csv(f"{DL}/data/futures/um/monthly/klines/{sym}/1d/{sym}-1d-{mo}.zip")
        if rows is None:
            return None
        d0 = date.fromisoformat(day)
        rows = [r for r in _data_rows(rows) if 0 <= int(r[0]) - _ms(d0) < 86_400_000]
    rows = _data_rows(rows)
    return float(rows[0][4]) if rows else None


def _ms(d: date) -> int:
    return (d - date(1970, 1, 1)).days * 86_400_000


def cached_closes(keys: list[tuple[str, str]]) -> dict[str, float | None]:
    f = CACHE / "kline_closes.json"
    cache = json.loads(f.read_text()) if f.exists() else {}
    todo = [(s, d) for s, d in keys if f"{s}|{d}" not in cache]

    def one(sd):
        try:
            return sd, daily_close(*sd)
        except (httpx.HTTPError, zipfile.BadZipFile, ValueError, IndexError) as e:
            print("close failed", sd, e, file=sys.stderr)
            return sd, None
    with cf.ThreadPoolExecutor(8) as ex:
        for (s, d), c in ex.map(one, todo):
            cache[f"{s}|{d}"] = c
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cache, sort_keys=True))
    return cache


def positive_price_rows(files: list[tuple[str, str]]) -> dict[str, int]:
    """Number of aggTrades rows with a positive price in each (symbol, day) file, cached."""
    f = CACHE / "positive_price_rows.json"
    cache = json.loads(f.read_text()) if f.exists() else {}
    for s, d in files:
        k = f"{s}|{d}"
        if k not in cache:
            rows = fetch_zip_csv(f"{DL}/{AGG_PFX}{s}/{s}-aggTrades-{d}.zip") or []
            cache[k] = sum(float(r[1]) > 0 for r in _data_rows(rows))
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cache, sort_keys=True))
    return cache


def verify_rows(samples: list[tuple[str, str]]) -> dict[str, int]:
    """Row count of a few last-day aggTrades files (header excluded), cached."""
    f = CACHE / "last_day_rows.json"
    cache = json.loads(f.read_text()) if f.exists() else {}
    for s, d in samples:
        k = f"{s}|{d}"
        if k in cache:
            continue
        rows = fetch_zip_csv(f"{DL}/{AGG_PFX}{s}/{s}-aggTrades-{d}.zip")
        cache[k] = len(_data_rows(rows)) if rows is not None else -1
    f.write_text(json.dumps(cache, sort_keys=True))
    return cache


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
COLUMNS = [
    "symbol", "life", "n_lives", "first_trade_day", "last_trade_day", "n_trading_days",
    "calendar_days", "missing_days", "alive_at_end", "status", "successor", "gap_days",
    "rename_candidates", "last_day_zip_bytes", "last_day_rows", "evidence",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="re-list the symbol list and every symbol whose cached days reach the last 7 days")
    ap.add_argument("--n-verify", type=int, default=12)
    args = ap.parse_args()

    syms_f = CACHE / "daily_aggtrades_symbols.json"
    if syms_f.exists() and not args.refresh:
        syms = json.loads(syms_f.read_text())
    else:
        syms = sorted(p[len(AGG_PFX):-1] for p in list_s3(AGG_PFX, "/"))
        CACHE.mkdir(parents=True, exist_ok=True)
        syms_f.write_text(json.dumps(syms))
    perps = [s for s in syms if is_usdt_perp(s)]
    print(len(syms), "symbols,", len(perps), "USDT perps", file=sys.stderr)

    refresh_after = (datetime.now(UTC).date() - timedelta(days=7)) if args.refresh else None
    inv: dict[str, dict[str, int]] = {}
    with cf.ThreadPoolExecutor(8) as ex:
        for s, d in zip(perps, ex.map(lambda s: symbol_days(s, refresh_after), perps)):
            if d:
                inv[s] = d
    archive_end = max(date.fromisoformat(max(d)) for d in inv.values())
    print("archive end", archive_end, file=sys.stderr)

    # tiny files (under 1 KB) are opened: a file holding only zero-price prints (seen
    # after settlement) is not a trading day
    tiny = [(s, d) for s in inv for d, b in inv[s].items() if b < 1000]
    pos = positive_price_rows(tiny)

    # one record per life
    lives = []
    for s in sorted(inv):
        keep, dropped = drop_artifact_days(
            inv[s], {d: pos[f"{s}|{d}"] for (ss, d) in tiny if ss == s})
        if not keep:
            continue
        days = [date.fromisoformat(x) for x in keep]
        parts = split_lives(days)
        for i, ds in enumerate(parts):
            lives.append({"symbol": s, "life": i + 1, "n_lives": len(parts), "days": ds,
                          "first": ds[0], "last": ds[-1],
                          "alive": is_alive(ds[-1], archive_end),
                          "last_bytes": inv[s][ds[-1].isoformat()],
                          "dropped": [d for d in dropped if ds[0].isoformat() <= d]
                          if i == len(parts) - 1 else []})
    key = {(lv["symbol"], lv["life"]): lv for lv in lives}
    starts = {f"{lv['symbol']}#{lv['life']}": lv["first"] for lv in lives}

    reuse_pairs = []
    for lv in lives:
        st, succ, ev = classify(lv["symbol"], lv["life"] - 1, lv["n_lives"], lv["alive"])
        lv.update(status=st, successor=succ, evidence=ev)
        if lv["dropped"]:
            lv["evidence"] += ("; ignored zero-price artifact file(s) on "
                               + ", ".join(lv["dropped"]))
        if st == "reused-symbol":
            nxt = key[(lv["symbol"], lv["life"] + 1)]
            lv["gap_days"] = (nxt["first"] - lv["last"]).days
            lv["evidence"] += f" (life {lv['life'] + 1} starts {nxt['first']})"
            reuse_pairs.append((lv, nxt))
        elif succ:
            ss = [x for x in lives if x["symbol"] == succ]
            if ss:
                # successor life that is nearest to the old contract's end
                n = min(ss, key=lambda x: abs((x["first"] - lv["last"]).days))
                lv["gap_days"] = (n["first"] - lv["last"]).days
                if n["first"] < lv["last"]:
                    lv["evidence"] += f"; successor already trading since {n['first']}"
            else:
                lv["evidence"] += "; successor not in archive"

    # rename candidates by the price rule, for dead contracts outside the known lists
    # (and for the known renames, as a check of the rule)
    pairs = []
    for lv in lives:
        if lv["alive"] or lv["status"] in ("index", "merged"):
            continue
        own = f"{lv['symbol']}#{lv['life']}"
        for c in window_candidates(lv["last"], starts, own):
            cs, cl = c.split("#")
            if cs == lv["symbol"]:
                continue
            pairs.append((lv, key[(cs, int(cl))]))
    allp = pairs + reuse_pairs
    need = sorted({(a["symbol"], a["last"].isoformat()) for a, _ in allp}
                  | {(b["symbol"], b["first"].isoformat()) for _, b in allp})
    print(len(pairs), "candidate pairs,", len(need), "closes", file=sys.stderr)
    closes = cached_closes(need)
    n_raw = 0
    for a, b in pairs:
        ca = closes.get(f"{a['symbol']}|{a['last'].isoformat()}")
        cb = closes.get(f"{b['symbol']}|{b['first'].isoformat()}")
        k = price_match(ca, cb)
        if k is None:
            continue
        n_raw += 1
        if denomination_consistent(a["symbol"], b["symbol"], k):
            dev = abs(ca / cb / k - 1)
            a.setdefault("cands", []).append(
                (dev, (f"{b['symbol']} (starts {b['first']}, close {ca:g} vs {cb:g}, "
                       f"ratio {ca / cb:.3g})")))
    for lv in lives:
        lv["cands"] = [t for _, t in sorted(lv.get("cands", []))]
    print(n_raw, "raw price matches;",
          sum(bool(lv["cands"]) for lv in lives), "contracts with candidates",
          file=sys.stderr)
    for a, b in reuse_pairs:
        ca = closes.get(f"{a['symbol']}|{a['last'].isoformat()}")
        cb = closes.get(f"{b['symbol']}|{b['first'].isoformat()}")
        if ca and cb:
            a["evidence"] += (f"; close {ca:g} at end vs {cb:g} at restart "
                              f"(ratio {ca / cb:.3g})")

    # verify that the last day is a real trading day for a sample of small files
    rng = random.Random(0)
    dead = [lv for lv in lives if not lv["alive"]]
    small = [lv for lv in dead if lv["last_bytes"] < 3_000_000]
    sample = rng.sample(small, min(args.n_verify, len(small)))
    rows = verify_rows([(lv["symbol"], lv["last"].isoformat()) for lv in sample])

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        for lv in lives:
            cal = (lv["last"] - lv["first"]).days + 1
            w.writerow([
                lv["symbol"], lv["life"], lv["n_lives"], lv["first"], lv["last"],
                len(lv["days"]), cal, cal - len(lv["days"]), int(lv["alive"]),
                lv["status"], lv["successor"], lv.get("gap_days", ""),
                "; ".join(lv["cands"]), lv["last_bytes"],
                rows.get(f"{lv['symbol']}|{lv['last'].isoformat()}", ""), lv["evidence"],
            ])
    print("wrote", OUT_CSV, len(lives), "rows", file=sys.stderr)


if __name__ == "__main__":
    main()
