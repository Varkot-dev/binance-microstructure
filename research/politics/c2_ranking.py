"""C2: which politicians move crypto the most? A ranking with shrinkage and rank intervals.

Part C, version 2. The design is fixed in `research/politics/PREREGISTRATION_RANKING.md`,
written and hashed before any X post file existed; this script refuses to run if that
file has changed. It reuses the v1 event, outcome and placebo machinery of
`c1_trump_posts.py` by import. Three steps, run from the repository root:

    PYTHONPATH=src .venv/bin/python research/politics/c2_ranking.py index
    PYTHONPATH=src .venv/bin/python research/politics/c2_ranking.py analyze
    PYTHONPATH=src .venv/bin/python research/politics/c2_ranking.py report

`index` writes posts_index/<platform>_<handle>.csv (no text) for every post file in
posts/ that passes validate_posts.py. `analyze` uses every validated file listed in
accounts.csv, downloads any missing BTC/ETH/SOL 1-minute kline months into
data/politics/klines/, and writes research/politics/data/c2_ranking.json. `report`
turns that JSON into data/c2_ranking.md and data/c2_ranking.png. When a new post file
arrives in posts/, run all three steps again.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (ROOT / "src", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import c1_trump_posts as c1
import validate_posts as vp

PREREG = HERE / "PREREGISTRATION_RANKING.md"
PREREG_SHA = "41ef1cf1fd1af1479572d06061894a5d58d91f949ec39cf516aeb01c905a22e7"
POSTS = HERE / "posts"
INDEX = HERE / "posts_index"
ACCOUNTS = HERE / "accounts.csv"
KLINES = c1.KLINES
OUT = HERE / "data"
RESULTS = OUT / "c2_ranking.json"
INDEX_COLUMNS = ["platform", "handle", "post_id", "url", "created_at_utc", "kind",
                 "has_media", "topic"]

SYMBOLS = c1.SYMBOLS
MONTHS = ("2020-01", "2026-10")
T0 = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
T_END = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)
N_MIN = int((T_END - T0).total_seconds() // 60)
MIN_EVENTS = 10
OVERLAP_S = 300
MUSK_GROUP = "musk_separate"
NEG_CONTROL = "Barack Obama"
TRUMP_TRUTH = "truth_realDonaldTrump"
TOPICS = c1.TOPICS
TOPIC_NAMES = {"crypto": "Crypto", "tariffs": "Tariffs/trade", "fed": "Fed/rates",
               "other": "Other"}
B = c1.B
SEED = c1.SEED
N_POOL = c1.N_POOL


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_prereg(path: Path = PREREG, expected: str | None = None) -> str:
    """Refuse to run if the pre-registration differs from the hashed version."""
    expected = PREREG_SHA if expected is None else expected
    got = sha256(path)
    if got != expected:
        raise SystemExit(f"{path.name} changed since it was hashed ({got[:12]} != "
                         f"{expected[:12]}); refusing to run")
    return got


# ---------------------------------------------------------------------------- index

def index_rows(rows: list[dict]) -> list[dict]:
    """Text-free index rows with the frozen v1 topic label of each post."""
    out = []
    for r in rows:
        d = {k: r[k] for k in INDEX_COLUMNS[:-1]}
        d["topic"] = c1.topic_of(r["text"])
        out.append(d)
    return out


def write_index(path: Path, out_dir: Path = INDEX) -> Path:
    """Validate one posts CSV and write its index (no text) to out_dir."""
    problems = vp.check_file(path)
    if problems:
        raise ValueError(f"{path.name} fails validation: {problems[0]}")
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / path.name
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=INDEX_COLUMNS)
        w.writeheader()
        w.writerows(index_rows(rows))
    return out


def index_all(posts_dir: Path = POSTS, out_dir: Path = INDEX) -> tuple[list, list]:
    done, failed = [], []
    for path in sorted(posts_dir.glob("*.csv")):
        try:
            done.append(write_index(path, out_dir))
        except ValueError as e:
            failed.append(str(e))
    return done, failed


# ---------------------------------------------------------------------------- posts

def load_accounts(path: Path = ACCOUNTS) -> dict[tuple[str, str], dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return {(r["platform"], r["handle"]): r for r in csv.DictReader(f)}


def discover(posts_dir: Path = POSTS, accounts: dict | None = None) -> tuple[list, list]:
    """(used files, skipped files with reasons). The Trump Truth file must be the v1 one."""
    accounts = load_accounts() if accounts is None else accounts
    used, skipped = [], []
    for path in sorted(posts_dir.glob("*.csv")):
        platform, _, handle = path.stem.partition("_")
        if (platform, handle) not in accounts:
            skipped.append({"file": path.name, "reason": "not in accounts.csv"})
            continue
        problems = vp.check_file(path)
        if problems:
            skipped.append({"file": path.name, "reason": f"fails validation: {problems[0]}"})
            continue
        h = sha256(path)
        if path.stem == TRUMP_TRUTH and h != c1.POSTS_SHA:
            raise SystemExit(f"{path.name} differs from the frozen v1 file; refusing to run")
        acc = accounts[(platform, handle)]
        used.append({"file": path.name, "path": path, "sha256": h, "platform": platform,
                     "handle": handle, "person": acc["person"], "group": acc["group"]})
    return used, skipped


def minute_of(ts: dt.datetime) -> int:
    return int((ts - T0).total_seconds() // 60)


def load_people(files: list[dict]) -> dict[str, dict]:
    """{person: {"group", "files", "posts"}}, posts of a person's accounts pooled, sorted."""
    people: dict[str, dict] = {}
    for f in files:
        with f["path"].open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        p = people.setdefault(f["person"], {"group": f["group"], "files": [], "posts": []})
        p["files"].append(f["file"])
        for r in rows:
            r["ts"] = dt.datetime.strptime(r["created_at_utc"],
                                           "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
            r["minute"] = minute_of(r["ts"])
            p["posts"].append(r)
    for p in people.values():
        p["posts"].sort(key=lambda r: (r["ts"], r["post_id"]))
    return people


def build_person_events(people: dict[str, dict]) -> dict[str, list[dict]]:
    """v1 events per person, plus the cross-person overlap flag and the C2 clean flag."""
    cand = {name: np.sort(np.array([r["ts"].timestamp() for r in p["posts"]
                                    if r["kind"] in ("original", "quote")], dtype=float))
            for name, p in people.items()}
    out = {}
    for name, p in people.items():
        others = [v for k, v in cand.items() if k != name]
        other = np.sort(np.concatenate(others)) if others else np.empty(0)
        events = c1.build_events(p["posts"])
        for e in events:
            lo, hi = e["ts"].timestamp() - OVERLAP_S, e["last_ts"].timestamp() + OVERLAP_S
            n_in = np.searchsorted(other, hi, "right") - np.searchsorted(other, lo, "left")
            e["overlap"] = bool(n_in > 0)
            e["clean2"] = bool(e["clean"] and not e["overlap"])
            e["in_period"] = bool(c1.PRE_SPAN <= e["minute"] < N_MIN - c1.POST_SPAN)
        out[name] = events
    return out


# ---------------------------------------------------------------------------- prices

def ensure_klines(symbols=SYMBOLS, months=MONTHS) -> list[str]:
    """Download kline months not yet cached; returns months Binance does not publish."""
    import httpx

    from microstructure.data.binance import download as dl
    from microstructure.data.binance import month_files

    KLINES.mkdir(parents=True, exist_ok=True)
    missing = []
    with httpx.Client(timeout=120) as client:
        for sym in symbols:
            for mf in month_files(sym, "klines", *months):
                f = c1.kline_file(sym, mf.period)
                if (KLINES / f.filename).exists():
                    continue
                try:
                    dl(f, KLINES, client)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code != 404:
                        raise
                    missing.append(f"{sym} {mf.period}")
    return missing


def _read_month(path: Path) -> tuple[np.ndarray, ...]:
    import io
    import zipfile

    import polars as pl

    with zipfile.ZipFile(path) as zf:
        raw = zf.read(zf.namelist()[0])
    df = pl.read_csv(io.BytesIO(raw), has_header=raw[:9] == b"open_time",
                     infer_schema_length=0)
    cols = df.columns
    ot = df[cols[0]].cast(pl.Int64).to_numpy()
    if ot.max() > 1e14:
        ot = ot // 1000
    return (ot, df[cols[4]].cast(pl.Float64).to_numpy(),
            df[cols[5]].cast(pl.Float64).to_numpy(), df[cols[9]].cast(pl.Float64).to_numpy())


def load_prices(sym: str) -> dict:
    """Close, volume and taker-buy volume on the C2 minute grid (NaN where missing)."""
    from microstructure.data.binance import month_files

    files = [KLINES / c1.kline_file(sym, mf.period).filename
             for mf in month_files(sym, "klines", *MONTHS)]
    present = [f.name for f in files if f.exists()]
    cache = KLINES / f"{sym}_1m_c2_{MONTHS[0]}_{MONTHS[1]}.npz"
    if cache.exists():
        z = np.load(cache)
        if list(z["months"]) == present:
            return {k: z[k] for k in ("close", "vol", "tb")}
    close, vol, tb = (np.full(N_MIN, np.nan) for _ in range(3))
    t0_ms = int(T0.timestamp() * 1000)
    for name in present:
        ot, c, v, t = _read_month(KLINES / name)
        idx = (ot - t0_ms) // 60_000
        ok = (idx >= 0) & (idx < N_MIN)
        close[idx[ok]], vol[idx[ok]], tb[idx[ok]] = c[ok], v[ok], t[ok]
    np.savez_compressed(cache, close=close, vol=vol, tb=tb, months=np.array(present))
    return {"close": close, "vol": vol, "tb": tb}


def excl_mask(n: int = N_MIN) -> np.ndarray:
    a, b = minute_of(c1.EXCL[0]), minute_of(c1.EXCL[1])
    out = np.zeros(n, bool)
    out[max(a, 0):min(b, n)] = True
    return out


def person_run(arr: dict, valid: np.ndarray, ev_min: np.ndarray, post_min: np.ndarray,
               pool_min: np.ndarray | None, drop_1010: bool) -> dict:
    """v1 abnormal outcomes for one person's events (and placebo pool) on one symbol."""
    n = valid.size
    elig = valid & ~c1.busy_mask(post_min, n)
    ex = excl_mask(n)
    if drop_1010:
        elig &= ~ex
    ok = (ev_min >= c1.PRE_SPAN) & (ev_min < n - c1.POST_SPAN)
    ok[ok] &= valid[ev_min[ok]]
    if drop_1010:
        ok[ok] &= ~ex[ev_min[ok]]
    ctrl = np.full((ev_min.size, c1.N_CTRL), -1, dtype=np.int64)
    if ok.any():
        ctrl[ok] = c1.pick_controls(ev_min[ok], elig)
    ab = c1.abnormal(arr, np.where(ok, ev_min, c1.PRE_SPAN), ctrl)
    good = ok & (ctrl >= 0).all(axis=1)
    for w in ab:
        for k in ab[w]:
            ab[w][k][~good] = np.nan
    out = {"ab": ab, "ok": good}
    if pool_min is not None:
        pm = pool_min[elig[pool_min]]
        pctrl = c1.pick_controls(pm, elig)
        keep = (pctrl >= 0).all(axis=1)
        pab = c1.abnormal(arr, pm, pctrl)
        out["pool"] = {w: {k: v[keep] for k, v in d.items()} for w, d in pab.items()}
    return out


# ---------------------------------------------------------------------------- ranking

def bh(p) -> np.ndarray:
    """Benjamini-Hochberg q-values (NaN p treated as 1)."""
    p = np.nan_to_num(np.asarray(p, dtype=float), nan=1.0)
    m = p.size
    if m == 0:
        return p
    order = np.argsort(p)
    ranked = p[order] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(q, 1.0)
    return out


def eb_fit(b, s) -> dict:
    """Normal-normal empirical Bayes with a method-of-moments prior, over the last axis."""
    b = np.asarray(b, dtype=float)
    s2 = np.maximum(np.asarray(s, dtype=float) ** 2, 1e-12)
    J = b.shape[-1]
    if J < 3:
        return {"applied": False, "shrunk": b.copy(), "factor": np.ones_like(b),
                "post_sd": np.sqrt(s2), "m": np.full(b.shape[:-1], np.nan),
                "tau2": np.full(b.shape[:-1], np.nan)}
    tau2 = np.maximum(0.0, b.var(axis=-1, ddof=1) - s2.mean(axis=-1))
    w = 1.0 / (tau2[..., None] + s2)
    m = (w * b).sum(axis=-1) / w.sum(axis=-1)
    f = tau2[..., None] / (tau2[..., None] + s2)
    shrunk = m[..., None] + f * (b - m[..., None])
    return {"applied": True, "shrunk": shrunk, "factor": f, "post_sd": np.sqrt(f * s2),
            "m": m, "tau2": tau2}


def rank_of(x) -> np.ndarray:
    """Rank 1 = largest; rank = 1 + number strictly larger (over the last axis)."""
    x = np.asarray(x, dtype=float)
    return 1 + (x[..., None, :] > x[..., :, None]).sum(axis=-1)


def boot_ranks(xs: list[np.ndarray], B: int = B, seed: int = SEED,
               chunk: int = 250) -> np.ndarray:
    """(B, J) ranks of the re-fitted shrunken effects, events resampled within person."""
    rng = np.random.default_rng(seed)
    J = len(xs)
    out = np.empty((B, J), dtype=np.int64)
    for start in range(0, B, chunk):
        nb = min(chunk, B - start)
        bb, ss = np.empty((nb, J)), np.empty((nb, J))
        for j, x in enumerate(xs):
            v = x[rng.integers(0, x.size, (nb, x.size))]
            bb[:, j] = v.mean(axis=1)
            ss[:, j] = v.std(axis=1, ddof=1) / math.sqrt(x.size)
        out[start:start + nb] = rank_of(eb_fit(bb, ss)["shrunk"])
    return out


def rank_people(samples: dict[str, np.ndarray], pools: dict[str, np.ndarray],
                B: int = B, seed: int = SEED) -> dict:
    """Pre-registered ranking (section 5) of the people in `samples` (all assumed eligible):
    raw mean, bootstrap CI, placebo p, BH q, EB shrinkage, rank and rank interval."""
    names = list(samples)
    xs = [np.asarray(samples[k], dtype=float) for k in names]
    xs = [x[np.isfinite(x)] for x in xs]
    rows = {}
    for name, x in zip(names, xs, strict=True):
        lo, hi = c1.boot_mean(x, B=B, seed=seed)
        p = c1.placebo_p(float(x.mean()), pools[name], x.size, B=B, seed=seed)["p"]
        rows[name] = {"n": int(x.size), "raw": float(x.mean()),
                      "se": float(x.std(ddof=1) / math.sqrt(x.size)),
                      "raw_lo": float(lo), "raw_hi": float(hi), "p": p}
    if not names:
        return {"people": rows, "prior": {"applied": False, "m": None, "tau2": None, "J": 0}}
    q = bh([rows[k]["p"] for k in names])
    b = np.array([rows[k]["raw"] for k in names])
    s = np.array([rows[k]["se"] for k in names])
    fit = eb_fit(b, s)
    rk = rank_of(fit["shrunk"])
    br = boot_ranks(xs, B=B, seed=seed)
    rlo = np.quantile(br, 0.025, axis=0, method="inverted_cdf")
    rhi = np.quantile(br, 0.975, axis=0, method="inverted_cdf")
    for j, k in enumerate(names):
        sh, sd = float(fit["shrunk"][j]), float(fit["post_sd"][j])
        rows[k].update({"q": float(q[j]), "shrunk": sh, "shrunk_lo": sh - 1.96 * sd,
                        "shrunk_hi": sh + 1.96 * sd, "factor": float(fit["factor"][j]),
                        "rank": int(rk[j]), "rank_lo": int(rlo[j]), "rank_hi": int(rhi[j])})
    prior = {"applied": bool(fit["applied"]), "J": len(names),
             "m": float(fit["m"]) if fit["applied"] else None,
             "tau2": float(fit["tau2"]) if fit["applied"] else None}
    return {"people": rows, "prior": prior}


def answer(ranking: dict, pre: dict) -> str:
    """The pre-registered one-sentence answer (section 6)."""
    rows = ranking["people"]
    J = len(rows)
    if J == 0:
        return (f"No politician has enough clean post events ({MIN_EVENTS}) to be ranked "
                "yet, so there is no answer.")
    sig = [k for k, r in rows.items() if r["q"] < 0.05 and r["raw"] > 0]
    if not sig:
        return (f"No politician's posts are distinguishable from random times: none of the "
                f"{J} ranked politician{'s' if J > 1 else ''} has an FDR q below 0.05 with "
                "a positive effect on BTC realized volatility in the 5 minutes after a post.")
    x = max(sig, key=lambda k: rows[k]["shrunk"])
    r = rows[x]
    detail = (f"about {r['shrunk']:+.2f} bps of extra BTC realized volatility in the 5 "
              f"minutes after a post ({'shrunken; ' if ranking['prior']['applied'] else ''}"
              f"raw {r['raw']:+.2f} bps, 95% CI {r['raw_lo']:.2f} to {r['raw_hi']:.2f}, "
              f"FDR q {_p(r['q'])}, {r['n']:,} events)")
    if J == 1:
        s = (f"{x} moves crypto the most, but only because {x} is the only politician with "
             f"enough data so far, so this is not yet a comparison: {detail}")
    else:
        s = (f"{x} moves crypto the most of the {J} ranked politicians: {detail}, rank "
             f"interval {r['rank_lo']} to {r['rank_hi']}")
        if r["rank_hi"] > 1:
            s += ", although the lead is not distinguishable from the next people"
    if pre.get(x, {}).get("elevated"):
        s += ("; the minutes before the posts are elevated too, so the posts may partly "
              "react to moves already under way")
    return s + "."


# ---------------------------------------------------------------------------- analyze

def _num(x):
    if isinstance(x, dict):
        return {str(k): _num(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_num(v) for v in x]
    if isinstance(x, np.integer | np.bool_):
        return x.item()
    if isinstance(x, float | np.floating):
        return None if not np.isfinite(x) else float(x)
    return x


def _ci(x: np.ndarray) -> dict:
    x = x[np.isfinite(x)]
    if x.size < 2:
        return {"n": int(x.size), "mean": float(x.mean()) if x.size else None,
                "lo": None, "hi": None}
    lo, hi = c1.boot_mean(x)
    return {"n": int(x.size), "mean": float(x.mean()), "lo": float(lo), "hi": float(hi)}


def analyze() -> dict:
    prereg_sha = check_prereg()
    files, skipped = discover()
    if not files:
        raise SystemExit("no validated post files listed in accounts.csv")
    missing = ensure_klines()
    people = load_people(files)
    events = build_person_events(people)
    names = sorted(people)
    post_min = {k: np.array([r["minute"] for r in people[k]["posts"]]) for k in names}
    ev_min = {k: np.array([e["minute"] for e in events[k]], dtype=np.int64) for k in names}
    sel = {k: np.array([e["clean2"] and e["in_period"] for e in events[k]], dtype=bool)
           for k in names}
    topics = {k: np.array([e["topic"] for e in events[k]]) for k in names}
    runs: dict = {}
    pools_min = {}
    for sym in SYMBOLS:
        px = load_prices(sym)
        arr = c1.minute_arrays(px["close"], px["vol"], px["tb"])
        valid = c1.valid_mask(px["close"])
        if sym == "BTCUSDT":
            for k in names:
                rng = np.random.default_rng(SEED)
                cand = np.flatnonzero(valid & ~c1.busy_mask(post_min[k], N_MIN))
                pools_min[k] = np.sort(rng.choice(cand, min(N_POOL, cand.size),
                                                  replace=False))
        for k in names:
            pm = pools_min[k] if sym == "BTCUSDT" else None
            runs[(sym, k, False)] = person_run(arr, valid, ev_min[k], post_min[k], pm, False)
            if sym == "BTCUSDT":
                runs[(sym, k, True)] = person_run(arr, valid, ev_min[k], post_min[k], pm,
                                                  True)
        del arr, px, valid

    def x_of(k, w="post5", m="rv", sym="BTCUSDT", drop=False, topic=None):
        run = runs[(sym, k, drop)]
        s = sel[k] & run["ok"]
        if topic is not None:
            s &= topics[k] == topic
        return run["ab"][w][m][s]

    def pool_of(k, w="post5", m="rv", drop=False):
        return runs[("BTCUSDT", k, drop)]["pool"][w][m]

    politicians = [k for k in names if people[k]["group"] != MUSK_GROUP]
    separate = [k for k in names if people[k]["group"] == MUSK_GROUP]

    def ranking(drop=False, topic=None):
        el = [k for k in politicians if x_of(k, drop=drop, topic=topic).size >= MIN_EVENTS]
        res = rank_people({k: x_of(k, drop=drop, topic=topic) for k in el},
                          {k: pool_of(k, drop=drop) for k in el})
        res["listed"] = {k: _ci(x_of(k, drop=drop, topic=topic)) for k in politicians
                         if k not in el}
        return res

    res: dict = {"prereg_sha256": prereg_sha, "generated_utc":
                 dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "period": [T0.isoformat(), T_END.isoformat()], "kline_months": MONTHS,
                 "klines_unpublished": missing,
                 "files": [{k: v for k, v in f.items() if k != "path"} for f in files],
                 "skipped": skipped}
    res["main"] = ranking()
    res["without_1010"] = ranking(drop=True)
    res["topics"] = {t: ranking(topic=t) for t in TOPICS}
    pre = {}
    for k in names:
        a, b = x_of(k), x_of(k, w="pre5")
        st = c1.stats_block(b, pool_of(k, w="pre5"))
        both = sel[k] & runs[("BTCUSDT", k, False)]["ok"]
        pa = runs[("BTCUSDT", k, False)]["ab"]["post5"]["rv"][both]
        pb = runs[("BTCUSDT", k, False)]["ab"]["pre5"]["rv"][both]
        lo, hi = c1.boot_paired(pa, pb) if a.size >= 2 else (np.nan, np.nan)
        st.update({"post_minus_pre": float(np.nanmean(pa - pb)) if a.size else np.nan,
                   "pmp_lo": lo, "pmp_hi": hi,
                   "elevated": bool(st["n"] > 0 and st["mean"] > 0 and st["p"] < 0.05)})
        pre[k] = st
    res["pre"] = pre
    res["separate"] = {}
    for k in separate:
        x = x_of(k)
        st = c1.stats_block(x, pool_of(k)) if x.size else {"n": 0}
        res["separate"][k] = st
    res["secondary"] = {k: {"BTCUSDT absret": _ci(x_of(k, m="absret")),
                            "ETHUSDT rv": _ci(x_of(k, sym="ETHUSDT")),
                            "SOLUSDT rv": _ci(x_of(k, sym="SOLUSDT"))} for k in names}
    cov = {}
    for k in names:
        ev = events[k]
        kinds: dict[str, int] = {}
        for r in people[k]["posts"]:
            kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        cov[k] = {"group": people[k]["group"], "files": people[k]["files"],
                  "posts": len(people[k]["posts"]), "kinds": kinds,
                  "first": people[k]["posts"][0]["created_at_utc"],
                  "last": people[k]["posts"][-1]["created_at_utc"],
                  "events": len(ev), "in_period": sum(e["in_period"] for e in ev),
                  "clean_v1": sum(e["clean"] and e["in_period"] for e in ev),
                  "overlap": sum(e["overlap"] and e["in_period"] for e in ev),
                  "clean": int(sel[k].sum()), "analysable": int(x_of(k).size),
                  "pool": int(pool_of(k).size)}
    res["coverage"] = cov
    res["answer"] = answer(res["main"], pre)
    neg = res["main"]["people"].get(NEG_CONTROL)
    res["negative_control"] = (
        "not in the data yet" if NEG_CONTROL not in names else
        "too few events to rank" if neg is None else
        ("passes (q above 0.05)" if neg["q"] > 0.05 else "FAILS (q at or below 0.05)"))
    return _num(res)


# ---------------------------------------------------------------------------- report

def _f(x, d=2) -> str:
    return "n/a" if x is None else f"{x:.{d}f}"


def _p(x) -> str:
    if x is None:
        return "n/a"
    return f"{x:.4f}" if x < 0.001 else f"{x:.3f}"


def _ci_s(lo, hi) -> str:
    return f"[{_f(lo)}, {_f(hi)}]"


def ranking_table(rk: dict, cov: dict | None = None) -> list[str]:
    L = [("| rank | person | events | shrunken effect [95%] | raw effect [95% CI] | "
         "rank interval | placebo p | FDR q |"), "|---|---|---|---|---|---|---|---|"]
    for k, r in sorted(rk["people"].items(), key=lambda kv: (kv[1]["rank"], kv[0])):
        L.append(f"| {r['rank']} | {k} | {r['n']:,} | {_f(r['shrunk'])} "
                 f"{_ci_s(r['shrunk_lo'], r['shrunk_hi'])} | {_f(r['raw'])} "
                 f"{_ci_s(r['raw_lo'], r['raw_hi'])} | {r['rank_lo']} to {r['rank_hi']} | "
                 f"{_p(r['p'])} | {_p(r['q'])} |")
    if not rk["people"]:
        L.append("| | (nobody has enough events) | | | | | | |")
    pr = rk["prior"]
    note = (f"Prior (method of moments over {pr['J']} people): mean {_f(pr['m'])} bps, "
            f"tau^2 {_f(pr['tau2'], 3)}." if pr["applied"] else
            f"No shrinkage: {pr['J']} ranked {'person' if pr['J'] == 1 else 'people'}, "
            "fewer than the 3 needed to estimate the prior, so shrunken = raw.")
    L += ["", note]
    if rk.get("listed"):
        L += ["", f"Listed, not ranked (fewer than {MIN_EVENTS} analysable clean events): "
              + "; ".join(f"{k} ({v['n']} events, raw {_f(v['mean'])})"
                          for k, v in sorted(rk["listed"].items())) + "."]
    return L


def plot(res: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    main = res["main"]["people"]
    rows = sorted(main.items(), key=lambda kv: kv[1]["rank"])
    sep = [(k, v) for k, v in res["separate"].items() if v.get("n")]
    labels = [k for k, _ in rows] + [f"{k} (separate)" for k, _ in sep]
    n = max(len(labels), 1)
    fig, axes = plt.subplots(1, 2, figsize=(11, 2.2 + 0.45 * n), sharey=True)
    ax = axes[0]
    for i, (_, r) in enumerate(rows):
        ax.plot([r["raw_lo"], r["raw_hi"]], [i - 0.12] * 2, color="#9a9890", lw=2)
        ax.plot(r["raw"], i - 0.12, "o", color="#9a9890", ms=6,
                label="raw, 95% bootstrap CI" if i == 0 else None)
        ax.plot([r["shrunk_lo"], r["shrunk_hi"]], [i + 0.12] * 2, color="#2a78d6", lw=2)
        ax.plot(r["shrunk"], i + 0.12, "o", color="#2a78d6", ms=6,
                label="shrunken, 95% posterior" if i == 0 else None)
    for j, (_, v) in enumerate(sep):
        i = len(rows) + j
        ax.plot([v["lo"], v["hi"]], [i] * 2, color="#eb6834", lw=2)
        ax.plot(v["mean"], i, "o", color="#eb6834", ms=6, label="Musk, raw (not ranked)")
    ax.axvline(0, color="#52514e", lw=0.8)
    ax.set_yticks(range(len(labels)), labels)
    ax.invert_yaxis()
    ax.set_xlabel("abnormal BTC realized volatility, minutes +1 to +5 (bps)")
    ax.set_title("Influence per post event", loc="left", fontsize=11, pad=24)
    ax.legend(frameon=False, fontsize=8, loc="lower left", bbox_to_anchor=(0, 1.0),
                 ncol=4)
    ax2 = axes[1]
    colors = {"crypto": "#2a78d6", "tariffs": "#eb6834", "fed": "#1baf7a", "other": "#9a9890"}
    names = labels
    for ti, t in enumerate(TOPICS):
        tk = res["topics"][t]
        for i, k in enumerate(names):
            r = tk["people"].get(k)
            if r is None:
                continue
            y = i + (ti - 1.5) * 0.15
            ax2.plot([r["raw_lo"], r["raw_hi"]], [y] * 2, color=colors[t], lw=1.5)
            ax2.plot(r["raw"], y, "o", color=colors[t], ms=5,
                     label=TOPIC_NAMES[t] if i == 0 else None)
    ax2.axvline(0, color="#52514e", lw=0.8)
    ax2.set_xlabel("raw effect by topic (bps), people with 10+ events in the topic")
    ax2.set_title("By topic", loc="left", fontsize=11, pad=24)
    ax2.legend(frameon=False, fontsize=8, loc="lower left", bbox_to_anchor=(0, 1.0),
                  ncol=4)
    for a in axes:
        a.spines[["top", "right"]].set_visible(False)
        a.grid(axis="x", color="#e6e5e0", lw=0.6)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def report(res: dict) -> str:
    cov = res["coverage"]
    main = res["main"]
    n_ranked = len(main["people"])
    L = ["# C2: which politicians move crypto the most?", "",
         ("Generated by `research/politics/c2_ranking.py report` from `c2_ranking.json` "
         f"(analysis run {res['generated_utc']}). Design fixed in "
         "`research/politics/PREREGISTRATION_RANKING.md` before any X post file existed:"), "",
         f"- pre-registration sha256 `{res['prereg_sha256']}`"]
    L += [f"- `posts/{f['file']}` ({f['person']}, {f['group']}) sha256 `{f['sha256']}`"
          for f in res["files"]]
    if res["skipped"]:
        L += [f"- skipped `{s['file']}`: {s['reason']}" for s in res["skipped"]]
    L += ["", "## Answer", "", f"**{res['answer']}**", ""]
    if n_ranked < 3:
        L += [(f"This run uses {len(res['files'])} post file(s) and ranks {n_ranked} "
              "politician(s), fewer than the 3 needed for shrinkage. It is a smoke test that "
              "proves the pipeline runs end to end "
              "(validation, events, overlap rule, controls, placebo, shrinkage, rank "
              "intervals, FDR, report); it is not yet a ranking. Re-run `index`, "
              "`analyze` and `report` when X post files arrive in `posts/`."), ""]
    L += [f"Negative control ({NEG_CONTROL}): {res['negative_control']}.", "",
          "## Ranking (pre-registered primary)", "",
          ("Influence = mean abnormal BTCUSDT realized volatility over minutes +1 to +5 per "
          "clean, non-overlapping post event, in bps (event minus the mean of 16 "
          "same-minute-of-week controls with no post by that person within 60 minutes). "
          "Shrunken: empirical-Bayes posterior mean toward the mean of ranked politicians. "
          "Rank interval: 2.5th to 97.5th percentile of ranks over 10,000 bootstraps of "
          "events within person. q: Benjamini-Hochberg over ranked people on placebo "
          "p-values (random post times)."), ""]
    L += ranking_table(main)
    L += ["", "### Without 2025-10-10/11", ""]
    L += ranking_table(res["without_1010"])
    L += ["", "## Musk (reported separately, not ranked)", ""]
    if res["separate"]:
        L += ["| person | events | raw effect [95% CI] | placebo p |", "|---|---|---|---|"]
        for k, v in res["separate"].items():
            L.append(f"| {k} | {v.get('n', 0)} | {_f(v.get('mean'))} "
                     f"{_ci_s(v.get('lo'), v.get('hi'))} | {_p(v.get('p'))} |")
    else:
        L.append("No Musk post file yet.")
    L += ["", "## Per topic (pre-registered, secondary)", "",
          ("Same statistics within each topic; shrinkage, ranks and q among people with at "
          f"least {MIN_EVENTS} analysable clean events in that topic."), "",
          ("| topic | person | events | raw [95% CI] | shrunken | rank interval | placebo p "
          "| q (within topic) |"), "|---|---|---|---|---|---|---|---|"]
    for t in TOPICS:
        tk = res["topics"][t]
        for k, r in sorted(tk["people"].items(), key=lambda kv: kv[1]["rank"]):
            L.append(f"| {TOPIC_NAMES[t]} | {k} | {r['n']:,} | {_f(r['raw'])} "
                     f"{_ci_s(r['raw_lo'], r['raw_hi'])} | {_f(r['shrunk'])} | "
                     f"{r['rank_lo']} to {r['rank_hi']} | {_p(r['p'])} | {_p(r['q'])} |")
        for k, v in sorted(tk["listed"].items()):
            if not v["n"]:
                continue
            L.append(f"| {TOPIC_NAMES[t]} | {k} | {v['n']} | {_f(v['mean'])} (not ranked) "
                     "| | | | |")
    L += ["", "## Pre-window check (pre-registered)", "",
          ("Abnormal BTC realized volatility over minutes -5 to -1, and the paired "
          "difference post minus pre. Elevated = pre-window mean above 0 with placebo "
          "p < 0.05: the posts may react to moves already under way."), "",
          ("| person | events | pre5 mean [95% CI] | placebo p | post minus pre [95% CI] | "
          "elevated |"), "|---|---|---|---|---|---|"]
    for k, v in sorted(res["pre"].items()):
        L.append(f"| {k} | {v['n']} | {_f(v['mean'])} {_ci_s(v['lo'], v['hi'])} | "
                 f"{_p(v['p'])} | {_f(v['post_minus_pre'])} "
                 f"{_ci_s(v['pmp_lo'], v['pmp_hi'])} | {'yes' if v['elevated'] else 'no'} |")
    L += ["", "## Secondary outcomes (descriptive)", "",
          "| person | BTC absret +1..+5 | ETH rv +1..+5 | SOL rv +1..+5 |", "|---|---|---|---|"]
    for k, v in sorted(res["secondary"].items()):
        cells = [f"{_f(c['mean'])} {_ci_s(c['lo'], c['hi'])} (n {c['n']})" for c in
                 (v["BTCUSDT absret"], v["ETHUSDT rv"], v["SOLUSDT rv"])]
        L.append(f"| {k} | " + " | ".join(cells) + " |")
    L += ["", "## Coverage", "",
          ("| person | group | posts | first | last | events in period | clean (v1 rule) | "
          "overlapping | clean, not overlapping | analysable on BTC | placebo pool |"),
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in sorted(cov.items()):
        L.append(f"| {k} | {v['group']} | {v['posts']:,} | {v['first'][:10]} | "
                 f"{v['last'][:10]} | {v['in_period']:,} | {v['clean_v1']:,} | "
                 f"{v['overlap']:,} | {v['clean']:,} | {v['analysable']:,} | {v['pool']:,} |")
    L += ["", f"Prices: Binance USDT-M 1-minute klines {res['kline_months'][0]} to "
          f"{res['kline_months'][1]}; months Binance does not publish: "
          + (", ".join(res["klines_unpublished"]) or "none") + ".", "",
          "## Caveats (fixed in the pre-registration)", "",
          ("- Topic keywords are the frozen v1 list: 'bitcoiner(s)' and 'ETH' are missed, "
          "images, videos and links are invisible, 'powell' and 'reciprocal' can be "
          "off-topic, non-English posts are not matched."),
          ("- Trump's Truth Social file is the frozen v1 file: 1,116 'RT: url + own text' "
          "posts are really quotes but stay reposts, so they are not events."),
          ("- Controls exclude only the same person's posts; other people's posts inside "
          "control windows bias effects toward zero. Events within 5 minutes of another "
          "person's post are dropped for both people, which removes the busiest news moments."),
          ("- Shrinkage pulls toward the mean of ranked politicians (accounts.csv groups are "
          "too small for a prior each); with fewer than 3 ranked people no shrinkage is "
          "applied."),
          "- Times are platform timestamps; markets learn of posts seconds to minutes later.",
          "", "![C2 figure](c2_ranking.png)", ""]
    return "\n".join(L)


def main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=["index", "analyze", "report"])
    a = ap.parse_args(argv)
    check_prereg()
    if a.step == "index":
        done, failed = index_all()
        for p in done:
            print("indexed", p.relative_to(ROOT))
        for msg in failed:
            print("NOT indexed:", msg)
        return 1 if failed else 0
    if a.step == "analyze":
        res = analyze()
        OUT.mkdir(parents=True, exist_ok=True)
        RESULTS.write_text(json.dumps(res, indent=1), encoding="utf-8")
        print("wrote", RESULTS.relative_to(ROOT))
        print(res["answer"])
        return 0
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    if res["prereg_sha256"] != PREREG_SHA:
        raise SystemExit("c2_ranking.json was made under a different pre-registration")
    plot(res, OUT / "c2_ranking.png")
    (OUT / "c2_ranking.md").write_text(report(res), encoding="utf-8")
    print("wrote", (OUT / "c2_ranking.md").relative_to(ROOT))
    print(res["answer"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
