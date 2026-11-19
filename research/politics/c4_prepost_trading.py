"""C4: did aggregate Binance trading move unusually before Trump's tariff posts?

Part C. The design is fixed in `research/politics/PREREGISTRATION_PREPOST.md`, written
and hashed before any aggTrades file was downloaded or any pre-post window opened;
this script refuses to run if that file has changed.

Binance public data is anonymous. This can only show whether aggregate trading before
posts was unusual, never who traded; no person or entity is named or implied as having
traded on information. It is a statistical test, not an accusation.

    PYTHONPATH=src .venv/bin/python research/politics/c4_prepost_trading.py download
    PYTHONPATH=src .venv/bin/python research/politics/c4_prepost_trading.py analyze

`download` fetches daily USDT-M aggTrades (SHA-256 checked), collapses each day to
aggressor events, reduces it at once to per-minute bars and caches those as
data/politics/prepost/days/<SYMBOL>/<date>.npz (git-ignored); zips and parquet files
are deleted after use. It is resumable and stops starting downloads at 3.7 GB.
`analyze` builds the event, control and placebo sets and writes
research/politics/data/c4_prepost_trading.{md,png,json}.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import threading
import uuid
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

PREREG = HERE / "PREREGISTRATION_PREPOST.md"
PREREG_SHA = "d5b47c00b8198b125d41963155d22c5dd422200be8940044ee455d9327f6ff13"
POSTS_SHA = "d3ce5a47062fd0d92dff8dae92f3e616f2386f4b1d378a49eb5d4e40e374cf3c"
CACHE = ROOT / "data" / "politics" / "prepost"
OUT = HERE / "data"

SEED = 20261119
B = 10_000
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
WIN = (-70, 16)  # every window used lies inside [m-70, m+16]
PLACEBO_FREE = (-70, 20)  # no post of any kind with post minute in [p-70, p+20]
GAP = 120  # anchors more than 2 hours apart
K_OTHER = 2
PLACEBO_PER_DATE = 6
N_POOL = 20_000
BUDGET_STOP = 3.7e9
WORKERS = 4
MIN_CTRL_WEEKS = 3
T_LAST = dt.datetime(2026, 10, 31, 23, 0, tzinfo=dt.UTC)
EXCL = (dt.datetime(2025, 10, 10, tzinfo=dt.UTC), dt.datetime(2025, 10, 12, tzinfo=dt.UTC))
PRE = {"pre10": (-10, -1), "pre60": (-60, -1)}
KEY = [  # (label, UTC post time) from notes/post_data_sources.md
    ("$TRUMP memecoin launch post", "2025-01-18T02:00:51Z"),
    ("Crypto reserve post (XRP, SOL, ADA)", "2025-03-02T15:24:20Z"),
    ("'Great time to buy' post", "2025-04-09T13:37:01Z"),
    ("90-day tariff pause post", "2025-04-09T17:18:40Z"),
    ("China 'very strange things' post", "2025-10-10T14:57:52Z"),
    ("100% tariff on China post", "2025-10-10T20:50:01Z"),
]
FRAMING = ("Binance public data is anonymous. This can only show whether aggregate "
           "trading before posts was unusual, never who traded; no person or entity is "
           "named or implied as having traded on information. It is a statistical test, "
           "not an accusation.")


def _load_c1():
    name = "c1_trump_posts"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HERE / "c1_trump_posts.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


c1 = _load_c1()
T0 = c1.T0
N_MIN = c1.N_MIN


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_prereg() -> None:
    if _sha(PREREG) != PREREG_SHA:
        raise SystemExit("PREREGISTRATION_PREPOST.md changed since it was hashed; refusing to run")


def minute_of(ts: dt.datetime) -> int:
    return int((ts - T0).total_seconds() // 60)


def minute_time(m: int) -> dt.datetime:
    return T0 + dt.timedelta(minutes=int(m))


def dates_for(m: int, win=WIN) -> list[str]:
    """UTC dates touched by minutes m+win[0] .. m+win[1]."""
    a, b = minute_time(m + win[0]).date(), minute_time(m + win[1]).date()
    out = []
    while a <= b:
        out.append(a.isoformat())
        a += dt.timedelta(days=1)
    return out


# ---------------------------------------------------------------------------- events

def load_events() -> dict:
    posts = c1.load_posts()
    ev = c1.build_events(posts)
    inside = [e for e in ev if T0 <= e["ts"] < T_LAST]
    tariff = [e for e in inside if e["clean"] and e["topic"] == "tariffs"]
    other = [e for e in inside if e["clean"] and e["topic"] == "other"]
    key = []
    for label, t in KEY:
        ts = dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
        key.append({"label": label, "ts": ts, "minute": minute_of(ts)})
    return {"tariff": tariff, "other": other, "key": key,
            "post_min": np.array([p["minute"] for p in posts], dtype=np.int64)}


def count_in_range(points: np.ndarray, n: int, lo: int, hi: int) -> np.ndarray:
    """c[t] = number of points p with t+lo <= p <= t+hi, for t in 0..n-1."""
    ind = np.zeros(n, dtype=np.int64)
    p = points[(points >= 0) & (points < n)]
    np.add.at(ind, p, 1)
    cs = np.concatenate([[0], np.cumsum(ind)])
    t = np.arange(n)
    a = np.clip(t + lo, 0, n)
    b = np.clip(t + hi + 1, 0, n)
    return cs[b] - cs[a]


def post_free_mask(post_min: np.ndarray, n: int = N_MIN, span=PLACEBO_FREE) -> np.ndarray:
    return count_in_range(post_min, n, span[0], span[1]) == 0


def far_from(c: int, taken: np.ndarray, gap: int = GAP) -> bool:
    return taken.size == 0 or bool(np.min(np.abs(taken - c)) > gap)


def hour_order(h: int) -> list[int]:
    return [h % 24, (h - 1) % 24, (h + 1) % 24, (h - 2) % 24, (h + 2) % 24,
            (h - 3) % 24, (h + 3) % 24]


def match_others(t_min: np.ndarray, o_min: np.ndarray, o_ok: np.ndarray, block: np.ndarray,
                 k: int = K_OTHER, same_year: bool = False, seed: int = SEED) -> np.ndarray:
    """Up to k other events per tariff event (in random order) with the same UTC hour
    (else the nearest hour, earlier first), without replacement, more than GAP minutes
    from every blocked anchor and every drawn control. Returns indices into o_min."""
    rng = np.random.default_rng(seed)
    hours = np.array([minute_time(m).hour for m in o_min])
    years = np.array([minute_time(m).year for m in o_min])
    used = np.zeros(o_min.size, bool)
    taken = np.array(sorted(block), dtype=np.int64)
    far = np.array([far_from(int(m), taken) for m in o_min]) & o_ok
    drawn: list[int] = []
    for i in rng.permutation(t_min.size):
        th = minute_time(t_min[i])
        for _ in range(k):
            pick = None
            for h in hour_order(th.hour):
                cand = far & ~used & (hours == h)
                if same_year:
                    cand &= years == th.year
                idx = np.flatnonzero(cand)
                if idx.size:
                    pick = int(rng.choice(idx))
                    break
            if pick is None:
                break
            used[pick] = True
            drawn.append(pick)
            far &= np.abs(o_min - o_min[pick]) > GAP
    return np.array(drawn, dtype=np.int64)


def draw_spaced(cands: np.ndarray, block: np.ndarray, n_max: int, rng: np.random.Generator,
                gap: int = GAP) -> np.ndarray:
    """Random candidates more than gap from block and from each other, at most n_max."""
    out: list[int] = []
    blk = np.sort(np.asarray(block, dtype=np.int64))
    for c in rng.permutation(cands):
        if len(out) >= n_max:
            break
        j = np.searchsorted(blk, c)
        if (j < blk.size and blk[j] - c <= gap) or (j > 0 and c - blk[j - 1] <= gap):
            continue
        if out and min(abs(c - x) for x in out) <= gap:
            continue
        out.append(int(c))
    return np.array(sorted(out), dtype=np.int64)


def placebo_pool(eligible: np.ndarray, block: np.ndarray, n: int, seed: int = SEED) -> np.ndarray:
    """Up to n minutes, uniform over eligible minutes, spaced more than GAP apart and
    from block (greedy in random order)."""
    rng = np.random.default_rng(seed)
    blocked = np.zeros(eligible.size, bool)
    for b in block:
        blocked[max(b - GAP, 0):b + GAP + 1] = True
    out = []
    for c in rng.permutation(np.flatnonzero(eligible)):
        if blocked[c]:
            continue
        out.append(c)
        blocked[max(c - GAP, 0):c + GAP + 1] = True
        if len(out) >= n:
            break
    return np.array(sorted(out), dtype=np.int64)


# ---------------------------------------------------------------------------- outcomes

def _wsum(cs: np.ndarray, a: np.ndarray, lo: int, hi: int) -> np.ndarray:
    """Sum over minutes a+lo .. a+hi from a prefix sum cs (len n+1); NaN outside."""
    n = cs.size - 1
    s, e = a + lo, a + hi + 1
    ok = (s >= 0) & (e <= n)
    out = np.full(a.size, np.nan)
    out[ok] = cs[e[ok]] - cs[s[ok]]
    return out


def _cs(x: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(np.nan_to_num(x, nan=0.0))])


def _px(px: np.ndarray, idx: np.ndarray) -> np.ndarray:
    out = np.full(idx.size, np.nan)
    ok = (idx >= 0) & (idx < px.size)
    out[ok] = px[idx[ok]]
    return out


def signs(px: np.ndarray, a: np.ndarray) -> dict:
    """Alignment signs: s from ln(P(15)/P(0)) and s5 from ln(P(15)/P(4)); 0 if flat,
    NaN if a price is missing."""
    p0, p4, p15 = _px(px, a), _px(px, a + 4), _px(px, a + 15)
    return {"s": np.sign(np.log(p15 / p0)), "s5": np.sign(np.log(p15 / p4)),
            "move15": np.log(p15 / p0) * 1e4}


def pre_outcomes(bars: dict, a: np.ndarray, shift: int = 0) -> dict:
    """Unaligned pre-window outcomes for anchors a (window moved |shift| minutes
    earlier when shift < 0). bars: buy, sell, (n_ev, n_large, lbuy, lsell), px."""
    out = {}
    cb, cs_ = _cs(bars["buy"]), _cs(bars["sell"])
    has_large = "n_large" in bars
    if has_large:
        cn, cl = _cs(bars["n_ev"]), _cs(bars["n_large"])
        clb, cls = _cs(bars["lbuy"]), _cs(bars["lsell"])
    b = a + shift
    for w, (lo, hi) in PRE.items():
        buy, sell = _wsum(cb, b, lo, hi), _wsum(cs_, b, lo, hi)
        tot = buy + sell
        with np.errstate(invalid="ignore", divide="ignore"):
            out[f"imb_{w}"] = np.where(tot > 0, (buy - sell) / tot, np.nan)
            if has_large:
                ne, nl = _wsum(cn, b, lo, hi), _wsum(cl, b, lo, hi)
                out[f"large_{w}"] = np.where(ne > 0, nl / ne, np.nan)
                lb, ls = _wsum(clb, b, lo, hi), _wsum(cls, b, lo, hi)
                out[f"limb_{w}"] = np.where(lb + ls > 0, (lb - ls) / (lb + ls), np.nan)
            out[f"premove_{w}"] = np.log(_px(bars["px"], b + hi) / _px(bars["px"], b + lo - 1)) * 1e4
    return out


def aligned(pre: dict, sign: np.ndarray) -> dict:
    """Multiply signed outcomes by the alignment sign (zero sign -> NaN)."""
    s = np.where(sign == 0, np.nan, sign)
    out = {}
    for k, v in pre.items():
        if k.startswith(("imb_", "limb_", "premove_")):
            out["al_" + k] = v * s
        else:
            out[k] = v
    return out


def complete_mask(px: np.ndarray, a: np.ndarray, win=WIN) -> np.ndarray:
    """Every minute from a+win[0] to a+win[1] has a price."""
    cs = np.concatenate([[0], np.cumsum(~np.isfinite(px))])
    s, e = a + win[0], a + win[1] + 1
    ok = (s >= 0) & (e <= px.size)
    out = np.zeros(a.size, bool)
    out[ok] = (cs[e[ok]] - cs[s[ok]]) == 0
    return out


def complete_all(px: np.ndarray, win=WIN) -> np.ndarray:
    return complete_mask(px, np.arange(px.size), win)


def rel_volume(vol: np.ndarray, a: np.ndarray, free: np.ndarray, ok_px: np.ndarray) -> dict:
    """ln(window volume / mean over weeks -4..-1, +1..+4 at the same minute of week);
    control weeks need a post-free [c-70, c+16] and complete data; >= 3 else NaN."""
    cv = _cs(vol)
    offs = np.array([s * j for j in range(1, 5) for s in (-1, 1)]) * c1.WEEK
    out = {}
    for w, (lo, hi) in PRE.items():
        ev = _wsum(cv, a, lo, hi)
        cand = a[:, None] + offs[None, :]
        inside = (cand >= 0) & (cand < vol.size)
        okc = np.zeros(cand.shape, bool)
        okc[inside] = free[cand[inside]] & ok_px[cand[inside]]
        cvals = _wsum(cv, np.where(inside, cand, 0).ravel(), lo, hi).reshape(cand.shape)
        cvals[~okc] = np.nan
        n_ok = okc.sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.nanmean(np.where(okc, cvals, np.nan), axis=1)
            r = np.log(ev / mean)
        r[n_ok < MIN_CTRL_WEEKS] = np.nan
        out[f"relvol_{w}"] = r
    return out


# ---------------------------------------------------------------------------- stats

def boot_diff(x, y, B=B, seed=SEED):
    return c1.boot_diff(np.asarray(x, float), np.asarray(y, float), B=B, seed=seed)


def perm_p(x: np.ndarray, y: np.ndarray, B: int = B, seed: int = SEED) -> dict:
    """Permutation p for mean(x) - mean(y): one-sided (x > y) and two-sided."""
    x, y = x[np.isfinite(x)], y[np.isfinite(y)]
    if x.size < 2 or y.size < 2:
        return {"p1": np.nan, "p2": np.nan}
    z = np.concatenate([x, y])
    obs = x.mean() - y.mean()
    rng = np.random.default_rng(seed)
    d = np.empty(B)
    for j in range(B):
        p = rng.permutation(z.size)
        d[j] = z[p[:x.size]].mean() - z[p[x.size:]].mean()
    return {"p1": float((1 + (d >= obs - 1e-12).sum()) / (B + 1)),
            "p2": float((1 + (np.abs(d) >= abs(obs) - 1e-12).sum()) / (B + 1))}


def placebo_p1(obs: float, pool: np.ndarray, n: int, B: int = B, seed: int = SEED) -> dict:
    """One-sided p: share of means of n placebo values (no replacement) >= obs."""
    pool = pool[np.isfinite(pool)]
    if n < 1 or pool.size < n or not np.isfinite(obs):
        return {"p1": np.nan, "mean": np.nan}
    rng = np.random.default_rng(seed)
    means = np.array([pool[rng.choice(pool.size, n, replace=False)].mean() for _ in range(B)])
    return {"p1": float((1 + (means >= obs - 1e-12).sum()) / (B + 1)),
            "mean": float(means.mean()), "lo": float(np.percentile(means, 2.5)),
            "hi": float(np.percentile(means, 97.5))}


def binom_p1(k: int, n: int, p: float = 0.05) -> float:
    from math import comb

    return float(sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def compare(xt: np.ndarray, xo: np.ndarray, xp: np.ndarray | None = None,
            B: int = B, seed: int = SEED) -> dict:
    """Tariff vs matched other (D, interval, permutation p) and vs placebo."""
    xt = np.asarray(xt, float)
    xo = np.asarray(xo, float)
    ft, fo = xt[np.isfinite(xt)], xo[np.isfinite(xo)]
    res = {"n_t": int(ft.size), "n_o": int(fo.size),
           "mean_t": float(ft.mean()) if ft.size else np.nan,
           "mean_o": float(fo.mean()) if fo.size else np.nan}
    res["D"] = res["mean_t"] - res["mean_o"]
    if ft.size >= 2 and fo.size >= 2:
        lo, hi = boot_diff(ft, fo, B=B, seed=seed)
        res |= {"lo": float(lo), "hi": float(hi)} | perm_p(ft, fo, B=B, seed=seed)
    else:
        res |= {"lo": np.nan, "hi": np.nan, "p1": np.nan, "p2": np.nan}
    if xp is not None:
        fp = np.asarray(xp, float)
        fp = fp[np.isfinite(fp)]
        res["n_p"] = int(fp.size)
        res["mean_p"] = float(fp.mean()) if fp.size else np.nan
        pp = placebo_p1(res["mean_t"], fp, ft.size, B=B, seed=seed)
        res["plac_p1"] = pp["p1"]
        if fp.size >= 20 and ft.size:
            q95 = float(np.percentile(fp, 95))
            k = int((ft > q95).sum())
            res |= {"q95": q95, "top5_k": k, "top5_share": k / ft.size,
                    "top5_binom_p": binom_p1(k, ft.size)}
    return res


def decision(primary: dict, guard5: dict) -> str:
    ok = (np.isfinite(primary.get("p1", np.nan)) and primary["D"] > 0 and primary["p1"] < 0.05
          and np.isfinite(guard5.get("p1", np.nan)) and guard5["D"] > 0 and guard5["p1"] < 0.05)
    return "evidence of unusual pre-post trading" if ok else "no evidence"


# ---------------------------------------------------------------------------- download

class Ledger:
    def __init__(self, path: Path):
        self.path, self.lock = path, threading.Lock()
        self.files: dict[str, int] = json.loads(path.read_text()) if path.exists() else {}

    @property
    def total(self) -> int:
        return sum(self.files.values())

    def add(self, name: str, size: int) -> None:
        with self.lock:
            self.files[name] = self.files.get(name, 0) + size
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.files))


def day_path(sym: str, date: str) -> Path:
    return CACHE / "days" / sym / f"{date}.npz"


def missing_path(sym: str, date: str) -> Path:
    return CACHE / "days" / sym / f"{date}.missing"


def have_day(sym: str, date: str) -> bool:
    return day_path(sym, date).exists() or missing_path(sym, date).exists()


_CLIENT = None


def _client():
    global _CLIENT
    if _CLIENT is None:
        import httpx

        _CLIENT = httpx.Client(timeout=300, limits=httpx.Limits(max_connections=WORKERS + 2))
    return _CLIENT


def fetch_day(sym: str, date: str, ledger: Ledger) -> tuple[Path | None, Path | None]:
    """Download one daily aggTrades zip into a fresh folder; (None, None) if absent."""
    import httpx

    from microstructure.data.binance import DAILY_BASE, DumpFile, download

    tmp = CACHE / "_tmp" / uuid.uuid4().hex
    tmp.mkdir(parents=True)
    f = DumpFile(sym, "aggTrades", date, base=DAILY_BASE)
    err: Exception | None = None
    for _ in range(3):
        try:
            path = download(f, tmp, _client())
            ledger.add(f.filename, path.stat().st_size)
            return path, tmp
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404):
                shutil.rmtree(tmp, ignore_errors=True)
                return None, None
            err = e
        except (httpx.TransportError, OSError) as e:
            err = e
    shutil.rmtree(tmp, ignore_errors=True)
    raise err  # type: ignore[misc]


def reduce_day(agg) -> dict:
    """Per-minute bars of one UTC day from aggressor events (ts, sign, qty, price)."""
    import polars as pl

    notional = (agg["qty"] * agg["price"]).to_numpy()
    thr = float(np.quantile(notional, 0.999)) if notional.size else np.nan
    ts = agg["ts"].cast(pl.Int64).to_numpy()  # epoch ms
    day0 = (ts.min() // 86_400_000) * 86_400_000
    mi = ((ts - day0) // 60_000).astype(np.int64)
    keep = (mi >= 0) & (mi < 1440)
    mi, notional, ts = mi[keep], notional[keep], ts[keep]
    sign = agg["sign"].to_numpy()[keep]
    price = agg["price"].to_numpy()[keep]
    large = notional > thr
    buy = np.bincount(mi, weights=notional * (sign > 0), minlength=1440)
    sell = np.bincount(mi, weights=notional * (sign < 0), minlength=1440)
    n_ev = np.bincount(mi, minlength=1440).astype(float)
    n_large = np.bincount(mi, weights=large.astype(float), minlength=1440)
    lbuy = np.bincount(mi, weights=notional * large * (sign > 0), minlength=1440)
    lsell = np.bincount(mi, weights=notional * large * (sign < 0), minlength=1440)
    px = np.full(1440, np.nan)
    order = np.lexsort((ts, mi))  # last trade per minute
    last = np.r_[mi[order][1:] != mi[order][:-1], True]
    px[mi[order][last]] = price[order][last]
    return {"buy": buy, "sell": sell, "n_ev": n_ev, "n_large": n_large, "lbuy": lbuy,
            "lsell": lsell, "px": px, "thr": np.array([thr]),
            "day0_ms": np.array([day0], dtype=np.int64)}


def process_zip(zp: Path, tmp: Path, sym: str, date: str) -> None:
    import polars as pl

    from microstructure.data.events import to_aggressor_events
    from microstructure.data.ingest import ingest_agg_trades

    pq = ingest_agg_trades(zp, tmp)
    zp.unlink()
    agg = to_aggressor_events(pl.scan_parquet(pq).select("ts", "is_buyer_maker", "price", "qty"))
    pq.unlink()
    bars = reduce_day(agg)
    want0 = int(dt.datetime.fromisoformat(date).replace(tzinfo=dt.UTC).timestamp() * 1000)
    if int(bars["day0_ms"][0]) != want0:
        raise RuntimeError(f"{sym} {date}: first trade not on the file's date")
    p = day_path(sym, date)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(p, **bars)


def download_plan(evs: dict) -> list[tuple[str, list[str]]]:
    """Ordered (symbol, dates) units: key dates for all symbols, then BTC tariff events
    in a random order (seed SEED)."""
    units: list[tuple[str, list[str]]] = []
    kd = sorted({d for e in evs["key"] for d in dates_for(e["minute"])})
    for s in SYMBOLS:
        units.append((s, kd))
    rng = np.random.default_rng(SEED)
    for i in rng.permutation(len(evs["tariff"])):
        units.append(("BTCUSDT", dates_for(evs["tariff"][i]["minute"])))
    return units


def download() -> None:
    check_prereg()
    os.environ.setdefault("POLARS_MAX_THREADS", "2")
    evs = load_events()
    ledger = Ledger(CACHE / "ledger.json")
    jobs: list[tuple[str, str]] = []
    seen = set()
    for s, ds in download_plan(evs):
        for d in ds:
            if (s, d) not in seen:
                seen.add((s, d))
                jobs.append((s, d))
    todo = [j for j in jobs if not have_day(*j)]
    print(f"{len(jobs)} symbol-days planned, {len(todo)} to fetch; downloaded so far "
          f"{ledger.total / 1e9:.2f} GB", flush=True)
    it = iter(todo)
    done = 0
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        q: list = []

        def refill():
            while len(q) < WORKERS and ledger.total < BUDGET_STOP:
                try:
                    s, d = next(it)
                except StopIteration:
                    return
                q.append((s, d, ex.submit(fetch_day, s, d, ledger)))

        refill()
        while q:
            s, d, fut = q.pop(0)
            zp, tmp = fut.result()
            try:
                if zp is None:
                    missing_path(s, d).parent.mkdir(parents=True, exist_ok=True)
                    missing_path(s, d).write_text("absent")
                else:
                    process_zip(zp, tmp, s, d)
            finally:
                if tmp is not None:
                    shutil.rmtree(tmp, ignore_errors=True)
            done += 1
            if done % 10 == 0:
                print(f"{done}/{len(todo)} done, {ledger.total / 1e9:.2f} GB", flush=True)
            refill()
    print(f"finished {done} symbol-days; {ledger.total / 1e9:.2f} GB downloaded in total "
          f"(stop rule {BUDGET_STOP / 1e9:.1f} GB)", flush=True)


# ---------------------------------------------------------------------------- analysis

def load_bars(sym: str) -> tuple[dict, set]:
    """Global minute grid (T0..T_END) from cached daily bars; NaN where not downloaded."""
    keys = ("buy", "sell", "n_ev", "n_large", "lbuy", "lsell", "px")
    out = {k: np.full(N_MIN, np.nan) for k in keys}
    dates = set()
    d = CACHE / "days" / sym
    for p in sorted(d.glob("*.npz")) if d.exists() else []:
        z = np.load(p)
        m0 = minute_of(dt.datetime.fromisoformat(p.stem).replace(tzinfo=dt.UTC))
        if m0 < 0 or m0 + 1440 > N_MIN:
            continue
        for k in keys:
            out[k][m0:m0 + 1440] = z[k]
        dates.add(p.stem)
    return out, dates


def kline_bars(sym: str) -> dict:
    px = c1.load_symbol(sym)
    return {"buy": px["tb"], "sell": px["vol"] - px["tb"], "px": px["close"], "vol": px["vol"]}


def group_outcomes(bars: dict, a: np.ndarray, sgn: dict, idx: np.ndarray | None = None) -> dict:
    """All aligned outcomes (primary sign, +5..+15 sign, 60 s shift) for anchors a."""
    if idx is None:
        idx = np.arange(a.size)
    a = a[idx]
    s, s5 = sgn["s"][idx], sgn["s5"][idx]
    base = pre_outcomes(bars, a)
    sh = pre_outcomes(bars, a, shift=-1)
    out = aligned(base, s)
    out |= {k + "_s5": v for k, v in aligned(base, s5).items() if k.startswith("al_")}
    out |= {k + "_shift": v for k, v in aligned(sh, s).items() if k.startswith("al_")}
    out["move15"] = sgn["move15"][idx]
    return out


ROWS = [  # (key, label) for the result tables
    ("al_imb_pre10", "aligned imbalance, -10..-1 (primary)"),
    ("al_imb_pre10_s5", "aligned imbalance, -10..-1, sign from +5..+15 (guard)"),
    ("al_imb_pre10_shift", "aligned imbalance, -10..-1, post time 60 s earlier (guard)"),
    ("al_imb_pre60", "aligned imbalance, -60..-1"),
    ("al_imb_pre60_s5", "aligned imbalance, -60..-1, sign from +5..+15"),
    ("al_imb_pre60_shift", "aligned imbalance, -60..-1, post time 60 s earlier"),
    ("relvol_pre10", "relative volume, -10..-1 (log points)"),
    ("relvol_pre60", "relative volume, -60..-1 (log points)"),
    ("large_pre10", "large-trade share, -10..-1 (%)"),
    ("large_pre60", "large-trade share, -60..-1 (%)"),
    ("al_limb_pre10", "aligned imbalance of large trades, -10..-1"),
    ("al_limb_pre60", "aligned imbalance of large trades, -60..-1"),
    ("al_premove_pre10", "aligned pre-move, -10..-1 (bps)"),
    ("al_premove_pre10_shift", "aligned pre-move, -10..-1, post time 60 s earlier (bps)"),
    ("al_premove_pre60", "aligned pre-move, -60..-1 (bps)"),
]
KLINE_ROWS = ["al_imb_pre10", "al_imb_pre10_s5", "al_imb_pre10_shift", "al_imb_pre60",
              "relvol_pre10", "al_premove_pre10"]


def analyze() -> dict:
    check_prereg()
    if _sha(c1.POSTS_CSV) != POSTS_SHA:
        raise SystemExit("posts file changed since the pre-registration; refusing to run")
    evs = load_events()
    post_min = evs["post_min"]
    free70 = post_free_mask(post_min, span=PLACEBO_FREE)
    free_vol = post_free_mask(post_min, span=WIN)
    t_min = np.array([e["minute"] for e in evs["tariff"]], dtype=np.int64)
    o_min = np.array([e["minute"] for e in evs["other"]], dtype=np.int64)
    k_min = np.array([e["minute"] for e in evs["key"]], dtype=np.int64)

    def in_excl(m: np.ndarray) -> np.ndarray:
        a, b = minute_of(EXCL[0]), minute_of(EXCL[1])
        return (m >= a) & (m < b)

    res: dict = {"prereg_sha": PREREG_SHA, "posts_sha": POSTS_SHA, "framing": FRAMING}
    kl = {s: kline_bars(s) for s in SYMBOLS}
    btc_kl_ok = complete_all(kl["BTCUSDT"]["px"])

    # ------------------------------------------------ aggTrades, BTCUSDT (primary)
    bars, dates = load_bars("BTCUSDT")
    px = bars["px"]
    ok_all = complete_all(px)
    t_ok = ok_all[t_min]
    res["n_tariff_events"] = int(t_min.size)
    res["n_tariff_downloaded"] = int(sum(all(d in dates for d in dates_for(m)) for m in t_min))
    block = np.concatenate([t_min, k_min])
    o_ok = ok_all[o_min] & btc_kl_ok[o_min]
    oi = match_others(t_min[t_ok], o_min, o_ok, block)
    others = o_min[oi]
    tdates = sorted({minute_time(m).date().isoformat() for m in t_min[t_ok]})
    rng = np.random.default_rng(SEED)
    pblock = np.concatenate([block, others])
    elig = ok_all & free70 & btc_kl_ok
    plac = []
    for d in tdates:
        m0 = minute_of(dt.datetime.fromisoformat(d).replace(tzinfo=dt.UTC))
        cand = np.arange(m0, m0 + 1440)
        cand = cand[(cand >= 0) & (cand < N_MIN)]
        cand = cand[elig[cand]]
        got = draw_spaced(cand, np.concatenate([pblock, np.array(plac, dtype=np.int64)]),
                          PLACEBO_PER_DATE, rng)
        plac.extend(got.tolist())
    plac = np.array(sorted(plac), dtype=np.int64)
    res["sets"] = {"tariff": t_min[t_ok].tolist(), "other": others.tolist(),
                   "placebo": plac.tolist()}

    def outcomes_for(br: dict, anchors: np.ndarray, vol_src: dict | None) -> dict:
        o = group_outcomes(br, anchors, signs(br["px"], anchors))
        if vol_src is not None:
            o |= rel_volume(vol_src["vol"], anchors, free_vol, btc_kl_ok)
        for k in list(o):
            if k.startswith("large_"):
                o[k] = o[k] * 100
        return o

    G = {"tariff": outcomes_for(bars, t_min[t_ok], kl["BTCUSDT"]),
         "other": outcomes_for(bars, others, kl["BTCUSDT"]),
         "placebo": outcomes_for(bars, plac, kl["BTCUSDT"])}
    res["agg"] = {k: compare(G["tariff"][k], G["other"][k], G["placebo"][k])
                  for k, _ in ROWS}
    res["agg_sign_zero"] = {g: int(np.sum(G[g]["move15"] == 0)) for g in G}
    res["agg_n"] = {g: len(res["sets"][g]) for g in G}
    res["decision"] = decision(res["agg"]["al_imb_pre10"], res["agg"]["al_imb_pre10_s5"])
    # without 2025-10-10/11
    keep = {"tariff": ~in_excl(t_min[t_ok]), "other": ~in_excl(others),
            "placebo": ~in_excl(plac)}
    res["agg_no1010"] = {k: compare(G["tariff"][k][keep["tariff"]],
                                    G["other"][k][keep["other"]],
                                    G["placebo"][k][keep["placebo"]])
                         for k in ("al_imb_pre10", "al_imb_pre10_s5")}
    # event-time profile of aligned per-minute imbalance (display)
    prof = {}
    for g, anchors in (("tariff", t_min[t_ok]), ("other", others), ("placebo", plac)):
        s = signs(px, anchors)["s"]
        s = np.where(s == 0, np.nan, s)
        rows = []
        for k in range(-60, 16):
            idx = anchors + k
            b_, s_ = bars["buy"][idx], bars["sell"][idx]
            with np.errstate(invalid="ignore", divide="ignore"):
                rows.append(float(np.nanmean((b_ - s_) / (b_ + s_) * s)))
        prof[g] = rows
    res["profile"] = {"minutes": list(range(-60, 16)), **prof}
    res["placebo_dist"] = G["placebo"]["al_imb_pre10"][np.isfinite(G["placebo"]["al_imb_pre10"])].tolist()
    res["tariff_dist"] = G["tariff"]["al_imb_pre10"][np.isfinite(G["tariff"]["al_imb_pre10"])].tolist()

    # ------------------------------------------------ klines, full sample
    res["kline"] = {}
    kblock = np.concatenate([t_min, k_min])
    for sym in SYMBOLS:
        kb = kl[sym]
        okk = complete_all(kb["px"]) & btc_kl_ok
        tk = t_min[okk[t_min]]
        ok_o = okk[o_min]
        oik = match_others(tk, o_min, ok_o, kblock, same_year=True)
        ok_ = o_min[oik]
        pool = placebo_pool(okk & free70, np.concatenate([kblock, ok_]), N_POOL)
        btc_px = kl["BTCUSDT"]["px"]
        out = {}
        for g, anchors in (("tariff", tk), ("other", ok_), ("placebo", pool)):
            sg = signs(btc_px, anchors)  # flows aligned with the BTC move
            o = group_outcomes(kb, anchors, sg)
            o |= rel_volume(kb["vol"], anchors, free_vol, okk)
            out[g] = o
        res["kline"][sym] = {"n": {"tariff": int(tk.size), "other": int(ok_.size),
                                   "placebo": int(pool.size)},
                             "rows": {k: compare(out["tariff"][k], out["other"][k],
                                                 out["placebo"][k]) for k in KLINE_ROWS}}
        print(f"kline {sym} done", flush=True)

    # ------------------------------------------------ key events (illustrations)
    key_rows = []
    kdates = sorted({minute_time(m).date().isoformat() for m in k_min})
    sym_bars = {"BTCUSDT": bars}
    for s in ("ETHUSDT", "SOLUSDT"):
        sym_bars[s], _ = load_bars(s)
    rng = np.random.default_rng(SEED + 1)
    kplac = []
    for d in kdates:
        m0 = minute_of(dt.datetime.fromisoformat(d).replace(tzinfo=dt.UTC))
        cand = np.arange(m0, m0 + 1440)
        okc = elig[cand]
        for s in ("ETHUSDT", "SOLUSDT"):
            okc &= complete_mask(sym_bars[s]["px"], cand)
        got = draw_spaced(cand[okc], np.concatenate([block, others, plac,
                                                     np.array(kplac, dtype=np.int64)]),
                          PLACEBO_PER_DATE, rng)
        kplac.extend(got.tolist())
    kplac = np.array(sorted(kplac), dtype=np.int64)
    res["key_placebo_n"] = int(kplac.size)
    for e in evs["key"]:
        m = np.array([e["minute"]])
        sg = signs(px, m)
        row = {"label": e["label"], "utc": e["ts"].strftime("%Y-%m-%d %H:%M:%S"),
               "btc_move15": float(sg["move15"][0])}
        for s in SYMBOLS:
            br = sym_bars[s]
            o = aligned(pre_outcomes(br, m), sg["s"])
            ref = (G["placebo"]["al_imb_pre10"] if s == "BTCUSDT" else
                   aligned(pre_outcomes(br, kplac), signs(px, kplac)["s"])["al_imb_pre10"])
            ref = ref[np.isfinite(ref)]
            v = float(o["al_imb_pre10"][0])
            row[s] = {"al_imb_pre10": v, "al_imb_pre60": float(o["al_imb_pre60"][0]),
                      "large_pre10": float(o["large_pre10"][0] * 100),
                      "al_premove_pre10": float(o["al_premove_pre10"][0]),
                      "pctl": float((ref < v).mean() * 100) if ref.size and np.isfinite(v)
                      else float("nan"), "n_ref": int(ref.size)}
        key_rows.append(row)
    res["key"] = key_rows
    return res


# ---------------------------------------------------------------------------- report

COLORS = {"tariff": "#eb6834", "other": "#8a8984", "placebo": "#2a78d6"}
LABEL = {"tariff": "Tariff posts", "other": "Matched other posts", "placebo": "Placebo times"}


def _f(x, d=3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{d}f}"


def _p(x) -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    return f"{x:.4f}" if x < 0.001 else f"{x:.3f}"


def plot(res: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    ax = axes[0]
    keys = [("al_imb_pre10", "-10..-1\nprimary"), ("al_imb_pre10_s5", "-10..-1\nsign +5..+15"),
            ("al_imb_pre10_shift", "-10..-1\n60 s earlier"), ("al_imb_pre60", "-60..-1")]
    x = np.arange(len(keys))
    for j, g in enumerate(("tariff", "other", "placebo")):
        vals = [res["agg"][k]["mean_" + g[0]] for k, _ in keys]
        ax.bar(x + (j - 1) * 0.26, vals, 0.24, color=COLORS[g], label=LABEL[g])
    for i, (k, _) in enumerate(keys):
        r = res["agg"][k]
        ax.plot([i - 0.26] * 2, [r["mean_o"] + r["lo"], r["mean_o"] + r["hi"]], color="#333", lw=1.2)
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_xticks(x, [lab for _, lab in keys], fontsize=8)
    ax.set_ylabel("mean aligned taker imbalance")
    ax.set_title("BTCUSDT aggTrades: pre-post aligned flow\n(bar line: other mean + 95% CI of D)",
                 fontsize=9)
    ax.legend(fontsize=8, frameon=False)
    ax = axes[1]
    pd_, td = np.array(res["placebo_dist"]), np.array(res["tariff_dist"])
    bins = np.linspace(-1, 1, 41)
    ax.hist(pd_, bins=bins, density=True, color=COLORS["placebo"], alpha=0.45, label=LABEL["placebo"])
    ax.hist(td, bins=bins, density=True, histtype="step", lw=2, color=COLORS["tariff"],
            label=LABEL["tariff"])
    if pd_.size:
        ax.axvline(np.percentile(pd_, 95), color="#333", ls="--", lw=1)
        ax.text(np.percentile(pd_, 95), ax.get_ylim()[1] * 0.92, " placebo 95th pctl", fontsize=7)
    ax.set_xlabel("aligned imbalance, -10..-1, per event")
    ax.set_title("Per-event distribution", fontsize=9)
    ax.legend(fontsize=8, frameon=False)
    ax = axes[2]
    mins = res["profile"]["minutes"]
    for g in ("tariff", "other", "placebo"):
        ax.plot(mins, res["profile"][g], color=COLORS[g], lw=2 if g == "tariff" else 1.4,
                label=LABEL[g])
    ax.axvline(0, color="#333", lw=0.8)
    ax.axvspan(-10, -1, color="#ddd", alpha=0.5, lw=0)
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_xlabel("minute relative to post minute")
    ax.set_ylabel("mean aligned imbalance in the minute")
    ax.set_title("Event-time profile (minutes after 0 are aligned by construction)", fontsize=9)
    ax.legend(fontsize=8, frameon=False)
    for a_ in axes:
        a_.spines[["top", "right"]].set_visible(False)
    fig.suptitle("C4: aggregate trading before Trump tariff posts (anonymous data; no "
                 "trader is identified)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _row(label: str, r: dict, d: int = 3) -> str:
    top = (f"{r['top5_share'] * 100:.1f}% (p {_p(r['top5_binom_p'])})"
           if "top5_share" in r else "n/a")
    return (f"| {label} | {r['n_t']} / {r['n_o']} / {r.get('n_p', 0)} | {_f(r['mean_t'], d)} | "
            f"{_f(r['mean_o'], d)} | {_f(r.get('mean_p', np.nan), d)} | {_f(r['D'], d)} "
            f"[{_f(r['lo'], d)}, {_f(r['hi'], d)}] | {_p(r['p1'])} | {_p(r['p2'])} | "
            f"{_p(r.get('plac_p1', np.nan))} | {top} |")


HEAD = ("| outcome | n tariff / other / placebo | tariff mean | other mean | placebo mean | "
        "D = tariff - other [95% CI] | perm p (one-sided) | perm p (two-sided) | "
        "placebo p (one-sided) | tariff events above placebo 95th pctl |\n"
        "|---|---|---|---|---|---|---|---|---|---|")


def report(res: dict) -> str:
    a = res["agg"]
    pr, g5, sh = a["al_imb_pre10"], a["al_imb_pre10_s5"], a["al_imb_pre10_shift"]
    L = ["# C4: did aggregate trading move unusually before Trump's tariff posts?", "",
         f"**{FRAMING}**", "",
         ("Generated by `research/politics/c4_prepost_trading.py analyze`. Design fixed in "
         "`research/politics/PREREGISTRATION_PREPOST.md` before any aggTrades file was "
         "downloaded or any pre-post window opened:"), "",
         f"- pre-registration sha256 `{res['prereg_sha']}`",
         f"- posts file sha256 `{res['posts_sha']}`", "",
         "## Verdict under the pre-registered decision rule", "",
         (f"**{res['decision'].capitalize()}.** Primary: mean aligned taker imbalance over "
         f"minutes -10 to -1 (BTCUSDT aggTrades, sign of the BTC move over +1..+15) for "
         f"tariff events minus matched other events, D = {_f(pr['D'])} "
         f"[95% CI {_f(pr['lo'])}, {_f(pr['hi'])}], one-sided permutation p {_p(pr['p1'])}. "
         f"With the sign from +5..+15: D = {_f(g5['D'])} [{_f(g5['lo'])}, {_f(g5['hi'])}], "
         f"p {_p(g5['p1'])}. The rule needs both above zero with p < 0.05."), "",
         ("This concerns anonymous aggregate order flow only. It identifies no one, and even "
         "a positive result would have innocent readings (posts reacting to news or to "
         "moves under way, other news, order-flow momentum)."), "",
         "## Coverage", "",
         (f"- Clean v1 tariff events 2022-02 to 2026-10: {res['n_tariff_events']}; with all "
         f"needed BTCUSDT aggTrades dates downloaded under the budget rule: "
         f"{res['n_tariff_downloaded']}; with complete minute data (analysed): "
         f"{res['agg_n']['tariff']}. Download order was random (seed), so the analysed set "
         "is a random subset."),
         (f"- Matched other events (same UTC hour, else nearest, up to 2 per tariff event, "
         f"from downloaded dates): {res['agg_n']['other']}. Placebo times (up to 6 per "
         f"tariff date, no post within [-70, +20] minutes): {res['agg_n']['placebo']}. "
         "Every anchor is more than 2 hours from every other anchor, so no control window "
         "overlaps an event window."),
         (f"- Events with a zero BTC move over +1..+15 (no sign, left out of aligned "
         f"outcomes): {res['agg_sign_zero']}."),
         (f"- Downloaded: {res.get('downloaded_gb', float('nan')):.2f} GB of daily aggTrades "
         "(SHA-256 checked), reduced to per-minute bars; zips deleted."), "",
         "## Primary and guard results (BTCUSDT aggTrades)", "",
         ("Aligned imbalance in [-1, 1]: positive means pre-post taker flow went the same way "
         "as the later BTC move. Interval: bootstrap within groups; permutation: 10,000 "
         "label shuffles; placebo p: 10,000 means of n placebo times."), "", HEAD]
    for k, lab in ROWS:
        L.append(_row(lab, a[k], 2 if k.startswith(("relvol", "large", "al_premove")) else 3))
    L += ["", (f"Guard (60 s earlier): D = {_f(sh['D'])} [{_f(sh['lo'])}, {_f(sh['hi'])}], "
          f"p {_p(sh['p1'])}."), "",
          "### Without 2025-10-10 and 2025-10-11 (secondary)", "", HEAD]
    for k in ("al_imb_pre10", "al_imb_pre10_s5"):
        L.append(_row(dict(ROWS)[k], res["agg_no1010"][k]))
    L += ["", "## Full-sample replication from 1-minute klines (secondary)", "",
          ("All clean tariff events with complete klines; imbalance from taker-buy volume "
          "(base quantity); matched others from all clean other events (same hour and "
          "year); placebo pool drawn over the whole sample; ETH and SOL flows aligned with "
          "the BTC move."), ""]
    for sym, blk in res["kline"].items():
        L += [(f"**{sym}** (tariff {blk['n']['tariff']}, other {blk['n']['other']}, "
              f"placebo {blk['n']['placebo']})"), "", HEAD]
        for k in KLINE_ROWS:
            L.append(_row(dict(ROWS)[k], blk["rows"][k],
                          2 if k.startswith(("relvol", "al_premove")) else 3))
        L.append("")
    L += ["## Key named events: illustrations only, not tests", "",
          ("Each row is one event, chosen because it is famous (which selects on the "
          "outcome). **One event cannot establish anything**, and none of these numbers "
          "says anything about who traded. pctl = percentile of the event's aligned "
          "imbalance (-10..-1) among BTC placebo times (BTC) or among "
          f"{res['key_placebo_n']} placebo times on the key dates (ETH, SOL)."), "",
          ("| illustration | UTC | BTC move +1..+15, bps | symbol | aligned imb -10..-1 | pctl | "
          "aligned imb -60..-1 | large-trade share -10..-1, % | aligned pre-move -10..-1, bps |"),
          "|---|---|---|---|---|---|---|---|---|"]
    for r in res["key"]:
        for s in SYMBOLS:
            v = r[s]
            L.append(f"| Illustration: {r['label']} | {r['utc']} | {_f(r['btc_move15'], 1)} | "
                     f"{s} | {_f(v['al_imb_pre10'])} | {v['pctl']:.0f} | "
                     f"{_f(v['al_imb_pre60'])} | {v['large_pre10']:.2f} | "
                     f"{_f(v['al_premove_pre10'], 1)} |")
    L += ["", "## Caveats", "",
          "- Anonymous, aggregate data: nothing here can attribute any trade to anyone.",
          ("- Post times are when Truth Social stored the post, in whole seconds; the 60 s "
          "shift guards against a slightly late timestamp, not against news that reached "
          "markets through other channels before the post."),
          ("- The budget (under 4 GB) did not hold every BTC tariff date, so the aggTrades "
          "analysis uses a random subset; the kline replication covers all events but "
          "has no large-trade measure."),
          ("- Placebo and matched times for the aggTrades analysis come from the same dates "
          "as tariff events (newsy days), which is conservative for day-level news but "
          "means they are not a random sample of all days."),
          "- Clean events exclude posting bursts; topic keywords are crude (see C1).",
          ("- Relative volume is ln(window volume / mean control volume), whose mean is "
           "below zero even with no effect (Jensen's inequality); compare groups, not "
           "levels. It comes from klines and needs at least 3 post-free control weeks."),
          ("- ETH and SOL key-event percentiles rest on the few placebo times that fit on "
           "the key dates, so they are coarse."),
          ("- 'No evidence' bounds the average effect by the interval; it cannot rule out "
          "unusual trading before a single post."), "",
          "![C4 figure](c4_prepost_trading.png)", ""]
    return "\n".join(L)


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_jsonable(v) for v in x.tolist()]
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


def main(argv: list[str]) -> int:
    os.environ.setdefault("POLARS_MAX_THREADS", "2")
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "download":
        download()
    elif cmd == "analyze":
        res = analyze()
        res["downloaded_gb"] = Ledger(CACHE / "ledger.json").total / 1e9
        OUT.mkdir(parents=True, exist_ok=True)
        plot(res, OUT / "c4_prepost_trading.png")
        (OUT / "c4_prepost_trading.md").write_text(report(res))
        (OUT / "c4_prepost_trading.json").write_text(json.dumps(_jsonable(res), indent=1))
        print(f"verdict: {res['decision']}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
