"""C1: do Trump's Truth Social posts move crypto markets, and which kinds of posts?

Part C, version 1. The design is fixed in `research/politics/PREREGISTRATION.md`, written
and hashed before any price data was downloaded or opened. Three steps:

    PYTHONPATH=src .venv/bin/python research/politics/c1_trump_posts.py convert
    PYTHONPATH=src .venv/bin/python research/politics/c1_trump_posts.py download
    PYTHONPATH=src .venv/bin/python research/politics/c1_trump_posts.py analyze

`convert` turns the Truth Social archive (data/politics/raw/pletcher_truth/posts.jsonl,
git-ignored) into research/politics/posts/truth_realDonaldTrump.csv in the data contract
of posts/README.md. Mapping choices (the archive has no reply, quote or repost flags;
`in_reply_to_id` and `quote_id` are always empty):

- repost: text starts with "RT @<handle>" or "RT: <truthsocial status url>". The handle
  after "RT @" is glued to the reposted text, so it is resolved as the longest handle
  seen elsewhere in the archive (in status URLs, or 3 or more times as an @mention
  outside RT prefixes) that is a prefix of the glued string; otherwise the leading run
  of handle characters minus a trailing "http(s)" or final capitalized word (best
  effort: the reposted handle is descriptive only and is not used in the analysis).
- quote: not a repost, and the text contains a truthsocial.com status URL; the handle
  is the account in the first such URL.
- reply: never assigned. The archive carries no reply information, and the 31 posts
  that start with "@" read as citations ("@EricTrump: ...") or shout-outs, so they are
  kept as original.
- original: everything else, including media-only posts with empty text.
- has_media: media_count > 0. Text: mojibake (UTF-8 read as Latin-1) is repaired
  segment by segment; newlines would be written as a literal backslash-n (none occur).
- Times are truncated to whole seconds (the contract format); collected_at_utc is the
  archive's scraped_at, truncated the same way.
- Two posts with empty text and no media (2024-03-05 17:23:39) fail the contract and are
  dropped.

Known mapping error, found after the file was frozen and pre-registered: 1,116 posts of
the form "RT: <status url><own text>" are quote posts with Trump's own comment, but are
mapped to repost. The frozen file is kept for v1; `analyze` reports an exploratory
re-run with them as quotes. Fix in the converter before a v2.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

RAW = ROOT / "data" / "politics" / "raw" / "pletcher_truth" / "posts.jsonl"
POSTS_CSV = HERE / "posts" / "truth_realDonaldTrump.csv"
PREREG = HERE / "PREREGISTRATION.md"
KLINES = ROOT / "data" / "politics" / "klines"
OUT = HERE / "data"
COLUMNS = ["platform", "handle", "post_id", "url", "created_at_utc", "text", "kind",
           "quoted_or_reposted_handle", "has_media", "collected_at_utc"]

# ---------------------------------------------------------------------------- convert

_STATUS_URL = re.compile(r"truthsocial\.com/(?:users/|@)([A-Za-z0-9_]+)(?:/statuses/|/)\d+")
_ANY_TS_URL = re.compile(r"truthsocial\.com/(?:users/|@)([A-Za-z0-9_]+)")
_MENTION = re.compile(r"@([A-Za-z0-9_]+)(?=[^A-Za-z0-9_]|$)")
_HANDLE_RUN = re.compile(r"[A-Za-z0-9_]+")
_MOJIBAKE = re.compile(r"[\u00c2-\u00f4][\u0080-\u00bf]+")


def fix_mojibake(text: str) -> str:
    """Repair UTF-8 bytes that were decoded as Latin-1, one run at a time."""
    def one(m: re.Match) -> str:
        s = m.group(0)
        try:
            return s.encode("latin-1").decode("utf-8")
        except UnicodeError:
            return s
    return _MOJIBAKE.sub(one, text)


def known_handles(texts: list[str], min_mentions: int = 3) -> set[str]:
    """Handles seen in status URLs, or at least `min_mentions` times as @mentions
    outside an "RT @" prefix (single mentions are often glued typos)."""
    urls: set[str] = set()
    mentions: dict[str, int] = {}
    for t in texts:
        urls.update(_ANY_TS_URL.findall(t))
        body = t
        if t.startswith("RT @"):
            m = _HANDLE_RUN.match(t[4:])
            body = t[4 + (m.end() if m else 0):]
        for h in _MENTION.findall(body):
            mentions[h] = mentions.get(h, 0) + 1
    return urls | {h for h, n in mentions.items() if n >= min_mentions}


_GLUED_TAIL = re.compile(r"(?<=[a-z0-9])(?:https?|[A-Z][a-z]+)$")


def _unglue(run: str) -> str:
    """Best-effort split of an unknown handle from glued text: drop a trailing "http(s)"
    or a final capitalized word ("patriotmomfloridaHoly" -> "patriotmomflorida")."""
    m = _GLUED_TAIL.search(run)
    return run[:m.start()] if m and m.start() >= 3 else run


def classify_kind(text: str, known: set[str]) -> tuple[str, str]:
    """(kind, quoted_or_reposted_handle) from the post text alone."""
    if text.startswith("RT @"):
        glued = text[4:]
        for n in range(min(30, len(glued)), 0, -1):
            if glued[:n] in known:
                return "repost", glued[:n]
        m = _HANDLE_RUN.match(glued)
        return "repost", (_unglue(m.group(0)) if m else "unknown")
    if text.startswith("RT:"):
        m = _ANY_TS_URL.search(text)
        return "repost", (m.group(1) if m else "unknown")
    m = _STATUS_URL.search(text)
    if m:
        return "quote", m.group(1)
    return "original", ""


def _sec(ts: str) -> str:
    return ts[:19] + "Z"


def convert(raw: Path = RAW, out: Path = POSTS_CSV) -> dict:
    rows = [json.loads(line) for line in raw.open(encoding="utf-8")]
    texts = [fix_mojibake(r.get("text") or "") for r in rows]
    known = known_handles(texts)
    recs, dropped = [], []
    for r, t in zip(rows, texts, strict=True):
        kind, h = classify_kind(t, known)
        media = (r.get("media_count") or 0) > 0
        if kind != "repost" and not t.strip() and not media:
            dropped.append(r["id"])
            continue
        recs.append({
            "platform": "truth", "handle": "realDonaldTrump", "post_id": str(r["id"]),
            "url": f"https://truthsocial.com/@realDonaldTrump/{r['id']}",
            "created_at_utc": _sec(r["created_at"]),
            "text": t.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"),
            "kind": kind, "quoted_or_reposted_handle": h,
            "has_media": "true" if media else "false",
            "collected_at_utc": _sec(r["scraped_at"]),
        })
    recs.sort(key=lambda d: (d["created_at_utc"], d["post_id"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(recs)
    kinds: dict[str, int] = {}
    for d in recs:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    return {"rows": len(recs), "dropped": dropped, "kinds": kinds,
            "first": recs[0]["created_at_utc"], "last": recs[-1]["created_at_utc"]}


# ---------------------------------------------------------------------------- constants

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
MONTHS = ("2022-02", "2026-10")
T0 = dt.datetime(2022, 2, 1, tzinfo=dt.UTC)
T_END = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)
N_MIN = int((T_END - T0).total_seconds() // 60)
WEEK = 7 * 1440
MERGE_MIN = 5
CLEAN_MIN = 60
BUSY_MIN = 60
N_CTRL = 16
MAX_WEEKS = 26
PRE_SPAN, POST_SPAN = 6, 60  # closes needed from m-6 to m+60
N_POOL = 20_000
B = 10_000
SEED = 20261118
WINDOWS = {"post5": (1, 5), "post15": (1, 15), "post60": (1, 60), "pre5": (-5, -1)}
MEASURES = ("absret", "rv", "ret", "logvol", "imb")
TOPICS = ("crypto", "tariffs", "fed", "other")
EXCL = (dt.datetime(2025, 10, 10, tzinfo=dt.UTC), dt.datetime(2025, 10, 12, tzinfo=dt.UTC))
PROFILE = (-30, 60)

# ---------------------------------------------------------------------------- topics

_TOPIC_PATTERNS = {
    "crypto": [r"bitcoins?", r"btc", r"crypto\w*", r"blockchains?", r"stablecoins?",
               r"digital assets?", r"digital currenc(?:y|ies)", r"cbdcs?",
               r"central bank digital currenc(?:y|ies)", r"ethereum", r"solana", r"xrp",
               r"memecoins?", r"meme coins?", r"\$trump", r"\$melania", r"world liberty",
               r"worldlibertyfi", r"wlfi", r"coinbase", r"binance", r"genius act",
               r"clarity act", r"defi", r"nfts?", r"satoshi"],
    "tariffs": [r"tariff\w*",
                (r"trade (?:deals?|wars?|deficits?|agreements?|negotiations?|surplus(?:es)?"
                 r"|imbalances?|partners?|talks|barriers?|policy|policies)"),
                r"reciprocal", r"liberation day", r"export controls?", r"anti-dumping",
                r"section 232", r"section 301", r"usmca", r"wto", r"customs duties",
                r"import (?:taxes|tax|duties)"],
    "fed": [r"federal reserve", r"the fed", r"fed chair\w*", r"fed's", r"powell",
            r"interest rates?", r"rate (?:cuts?|hikes?)",
            r"(?:cut|lower|raise|reduce) (?:interest )?rates", r"rates (?:down|should|must)",
            r"basis points", r"fomc", r"monetary policy", r"warsh",
            r"[\"“']too late[\"”']", r"mr\.? too late"],
}
# a pattern starting with "$" cannot use a word-character lookbehind on its own first
# character, so the boundary is: no word character directly before or after the match
TOPIC_RE = {k: re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(v) + r")(?![A-Za-z0-9_])",
                          re.IGNORECASE) for k, v in _TOPIC_PATTERNS.items()}


def topic_of(text: str) -> str:
    """Topic of one post from its text alone (first match in crypto, tariffs, fed)."""
    for k in ("crypto", "tariffs", "fed"):
        if TOPIC_RE[k].search(text):
            return k
    return "other"


# ---------------------------------------------------------------------------- events

def load_posts(path: Path = POSTS_CSV) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        t = dt.datetime.strptime(r["created_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
        r["minute"] = int((t - T0).total_seconds() // 60)
        r["ts"] = t
    rows.sort(key=lambda r: r["ts"])
    return rows


def build_events(posts: list[dict]) -> list[dict]:
    """Merge original/quote posts within MERGE_MIN minutes (chained); flag the clean
    sample (no previous event's last post within CLEAN_MIN minutes before)."""
    cand = [p for p in posts if p["kind"] in ("original", "quote")]
    events: list[dict] = []
    for p in cand:
        if events and (p["ts"] - events[-1]["last_ts"]).total_seconds() <= MERGE_MIN * 60:
            e = events[-1]
            e["last_ts"] = p["ts"]
            e["texts"].append(p["text"])
            e["ids"].append(p["post_id"])
            continue
        events.append({"ts": p["ts"], "last_ts": p["ts"], "minute": p["minute"],
                       "texts": [p["text"]], "ids": [p["post_id"]]})
    prev_last = None
    for e in events:
        topics = {topic_of(t) for t in e["texts"]}
        e["topic"] = next((k for k in TOPICS if k in topics), "other")
        e["n_posts"] = len(e["ids"])
        e["clean"] = prev_last is None or (e["ts"] - prev_last).total_seconds() >= CLEAN_MIN * 60
        prev_last = e["last_ts"]
    return events


def busy_mask(post_minutes: np.ndarray, n: int, span: int = BUSY_MIN) -> np.ndarray:
    """True at minute t when some post minute p has |p - t| <= span."""
    ind = np.zeros(n + 2 * span + 1, dtype=np.int64)
    pm = post_minutes[(post_minutes >= -span) & (post_minutes < n + span)] + span
    np.add.at(ind, pm, 1)
    c = np.concatenate([[0], np.cumsum(ind)])
    # minute t covers ind positions t .. t + 2*span (shifted by span)
    t = np.arange(n)
    return (c[t + 2 * span + 1] - c[t]) > 0


def valid_mask(close: np.ndarray) -> np.ndarray:
    """True at minute t when every close from t-PRE_SPAN to t+POST_SPAN exists."""
    n = close.size
    bad = np.concatenate([[0], np.cumsum(~np.isfinite(close))])
    t = np.arange(n)
    lo, hi = t - PRE_SPAN, t + POST_SPAN
    ok = (lo >= 0) & (hi < n)
    out = np.zeros(n, dtype=bool)
    out[ok] = (bad[hi[ok] + 1] - bad[lo[ok]]) == 0
    return out


def week_offsets(max_weeks: int = MAX_WEEKS) -> np.ndarray:
    return np.array([s * j for j in range(1, max_weeks + 1) for s in (-1, 1)]) * WEEK


def pick_controls(anchors: np.ndarray, eligible: np.ndarray, k: int = N_CTRL,
                  max_weeks: int = MAX_WEEKS) -> np.ndarray:
    """(n, k) control minutes: the first k eligible of m-1w, m+1w, m-2w, ...; -1 if short."""
    cand = anchors[:, None] + week_offsets(max_weeks)[None, :]
    inside = (cand >= 0) & (cand < eligible.size)
    ok = np.zeros_like(inside)
    ok[inside] = eligible[cand[inside]]
    rank = np.cumsum(ok, axis=1)
    out = np.full((anchors.size, k), -1, dtype=np.int64)
    for j in range(k):
        hit = ok & (rank == j + 1)
        has = hit.any(axis=1)
        out[has, j] = cand[has, hit[has].argmax(axis=1)]
    return out


# ---------------------------------------------------------------------------- outcomes

def minute_arrays(close: np.ndarray, vol: np.ndarray, tb: np.ndarray) -> dict:
    r = np.full(close.size, np.nan)
    r[1:] = np.diff(np.log(close)) * 1e4  # basis points
    def cs(x):
        return np.concatenate([[0.0], np.cumsum(np.nan_to_num(x))])
    return {"r": r, "cr": cs(r), "cr2": cs(r * r), "cv": cs(vol), "ctb": cs(tb)}


def window_values(arr: dict, m: np.ndarray, a: int, b: int) -> dict:
    """Outcomes over minutes m+a..m+b (m any int array; caller guarantees validity)."""
    lo, hi = m + a, m + b + 1
    s = arr["cr"][hi] - arr["cr"][lo]
    s2 = arr["cr2"][hi] - arr["cr2"][lo]
    v = arr["cv"][hi] - arr["cv"][lo]
    tb = arr["ctb"][hi] - arr["ctb"][lo]
    with np.errstate(divide="ignore", invalid="ignore"):
        return {"absret": np.abs(s), "rv": np.sqrt(s2), "ret": s,
                "logvol": np.log(v), "imb": (2 * tb - v) / v}


def abnormal(arr: dict, anchors: np.ndarray, ctrl: np.ndarray) -> dict:
    """{window: {measure: abnormal value per anchor}}; NaN where controls are short."""
    good = (ctrl >= 0).all(axis=1)
    out: dict = {}
    for w, (a, b) in WINDOWS.items():
        ev = window_values(arr, anchors, a, b)
        cv = window_values(arr, np.where(ctrl >= 0, ctrl, PRE_SPAN), a, b)
        out[w] = {}
        for k in MEASURES:
            x = ev[k] - cv[k].mean(axis=1)
            x[~good] = np.nan
            out[w][k] = x
    return out


def profile(arr: dict, anchors: np.ndarray, ctrl: np.ndarray, span=PROFILE) -> np.ndarray:
    """(n, len) abnormal |r| per event minute k in span."""
    ks = np.arange(span[0], span[1] + 1)
    r = np.abs(arr["r"])
    n = r.size
    def at(idx):
        idx = np.clip(idx, 0, n - 1)
        return r[idx]
    ev = at(anchors[:, None] + ks[None, :])
    cc = at(np.where(ctrl >= 0, ctrl, 0)[:, :, None] + ks[None, None, :])
    out = ev - np.nanmean(cc, axis=1)
    out[~(ctrl >= 0).all(axis=1)] = np.nan
    return out


# ---------------------------------------------------------------------------- inference

def boot_mean(x: np.ndarray, B: int = B, seed: int = SEED, chunk: int = 500) -> tuple:
    x = x[np.isfinite(x)]
    if x.size < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    means = np.empty(B)
    for j in range(0, B, chunk):
        nb = min(chunk, B - j)
        means[j:j + nb] = x[rng.integers(0, x.size, (nb, x.size))].mean(axis=1)
    return tuple(np.percentile(means, [2.5, 97.5]))


def boot_diff(x: np.ndarray, y: np.ndarray, B: int = B, seed: int = SEED,
              chunk: int = 500) -> tuple:
    """Percentile interval of mean(x) - mean(y), resampling within each group."""
    x, y = x[np.isfinite(x)], y[np.isfinite(y)]
    rng = np.random.default_rng(seed)
    d = np.empty(B)
    for j in range(0, B, chunk):
        nb = min(chunk, B - j)
        d[j:j + nb] = (x[rng.integers(0, x.size, (nb, x.size))].mean(axis=1)
                       - y[rng.integers(0, y.size, (nb, y.size))].mean(axis=1))
    return tuple(np.percentile(d, [2.5, 97.5]))


def boot_paired(x: np.ndarray, y: np.ndarray, B: int = B, seed: int = SEED,
                chunk: int = 500) -> tuple:
    ok = np.isfinite(x) & np.isfinite(y)
    d = (x - y)[ok]
    return boot_mean(d, B, seed, chunk)


def placebo_p(obs: float, pool: np.ndarray, n: int, B: int = B, seed: int = SEED) -> dict:
    """Two-sided p of obs against means of n placebo values drawn without replacement."""
    pool = pool[np.isfinite(pool)]
    if n < 1 or pool.size < n or not np.isfinite(obs):
        return {"p": np.nan, "mean": np.nan}
    rng = np.random.default_rng(seed)
    means = np.empty(B)
    if n * 4 <= pool.size:  # draw with rejection of duplicates via permutation chunks
        for j in range(B):
            means[j] = pool[rng.choice(pool.size, n, replace=False)].mean()
    else:
        for j in range(B):
            means[j] = pool[rng.permutation(pool.size)[:n]].mean()
    hi = (1 + (means >= obs).sum()) / (B + 1)
    lo = (1 + (means <= obs).sum()) / (B + 1)
    return {"p": float(min(1.0, 2 * min(hi, lo))), "mean": float(means.mean()),
            "lo": float(np.percentile(means, 2.5)), "hi": float(np.percentile(means, 97.5))}


def label_perm_p(x: np.ndarray, y: np.ndarray, B: int = B, seed: int = SEED) -> float:
    """Two-sided permutation p for mean(x) - mean(y), reshuffling labels."""
    x, y = x[np.isfinite(x)], y[np.isfinite(y)]
    z = np.concatenate([x, y])
    obs = abs(x.mean() - y.mean())
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(B):
        p = rng.permutation(z.size)
        cnt += abs(z[p[:x.size]].mean() - z[p[x.size:]].mean()) >= obs - 1e-12
    return float((1 + cnt) / (B + 1))


def holm(ps: list[float]) -> list[float]:
    ps = np.asarray(ps, dtype=float)
    order = np.argsort(ps)
    m = ps.size
    adj = np.empty(m)
    run = 0.0
    for i, j in enumerate(order):
        run = max(run, min(1.0, (m - i) * ps[j]))
        adj[j] = run
    return adj.tolist()


# ---------------------------------------------------------------------------- prices

def download(symbols=SYMBOLS, months=MONTHS) -> list[Path]:
    """Monthly 1m klines into data/politics/klines/, SHA-256 checked (cached files kept)."""
    import httpx

    from microstructure.data.binance import download as dl
    from microstructure.data.binance import month_files

    KLINES.mkdir(parents=True, exist_ok=True)
    out = []
    with httpx.Client(timeout=120) as client:
        for sym in symbols:
            for mf in month_files(sym, "klines", *months):
                out.append(dl(kline_file(sym, mf.period), KLINES, client))
    return out


def kline_file(sym: str, period: str):
    """A DumpFile for futures/um/monthly/klines/{SYM}/1m/{SYM}-1m-{YYYY-MM}.zip, so that
    microstructure.data.binance.download (SHA-256 check) can fetch it."""
    from microstructure.data.binance import BASE, DumpFile

    class KlineFile(DumpFile):
        @property
        def filename(self) -> str:
            return f"{self.symbol}-1m-{self.period}.zip"

        @property
        def url(self) -> str:
            return f"{self.base}/klines/{self.symbol}/1m/{self.filename}"

    return KlineFile(sym, "klines", period, base=BASE)


def load_symbol(sym: str) -> dict:
    """Minute grid (T0..T_END) of close, volume, taker-buy volume; NaN where missing.
    Cached as data/politics/klines/<sym>_1m.npz."""
    import io
    import zipfile

    import polars as pl

    from microstructure.data.binance import month_files

    cache = KLINES / f"{sym}_1m.npz"
    if cache.exists():
        z = np.load(cache)
        return {k: z[k] for k in ("close", "vol", "tb")}
    close, vol, tb = (np.full(N_MIN, np.nan) for _ in range(3))
    t0_ms = int(T0.timestamp() * 1000)
    for mf in month_files(sym, "klines", *MONTHS):
        f = kline_file(sym, mf.period)
        with zipfile.ZipFile(KLINES / f.filename) as zf:
            raw = zf.read(zf.namelist()[0])
        has_header = raw[:9] == b"open_time"
        df = pl.read_csv(io.BytesIO(raw), has_header=has_header, new_columns=None,
                         infer_schema_length=0)
        cols = df.columns
        ot = df[cols[0]].cast(pl.Int64).to_numpy()
        if ot.max() > 1e14:  # microseconds (newer spot-style files)
            ot = ot // 1000
        idx = (ot - t0_ms) // 60_000
        ok = (idx >= 0) & (idx < N_MIN)
        close[idx[ok]] = df[cols[4]].cast(pl.Float64).to_numpy()[ok]
        vol[idx[ok]] = df[cols[5]].cast(pl.Float64).to_numpy()[ok]
        tb[idx[ok]] = df[cols[9]].cast(pl.Float64).to_numpy()[ok]
    np.savez_compressed(cache, close=close, vol=vol, tb=tb)
    return {"close": close, "vol": vol, "tb": tb}


# ---------------------------------------------------------------------------- analysis

PREREG_SHA = "8a3e0a074749d54a116c4db97b80a46a3bebf771a7a819d782822a47480cbabd"
POSTS_SHA = "d3ce5a47062fd0d92dff8dae92f3e616f2386f4b1d378a49eb5d4e40e374cf3c"
NAMED = [  # (label, UTC time of the Truth Social post) from notes/post_data_sources.md
    ("Open minded to crypto companies", "2024-05-25T19:13:35Z"),
    ("Thank you, Bitcoin 2024", "2024-07-27T21:20:41Z"),
    ("World Liberty Financial promoted", "2024-09-30T15:11:13Z"),
    ("Atkins nominated to SEC", "2024-12-04T17:47:48Z"),
    ("Congratulations Bitcoiners $100,000", "2024-12-05T12:55:19Z"),
    ("Sacks named crypto czar", "2024-12-06T00:50:46Z"),
    ("$TRUMP memecoin launch", "2025-01-18T02:00:51Z"),
    ("$MELANIA re-truth (repost)", "2025-01-19T21:22:03Z"),
    ("Crypto reserve: XRP, SOL, ADA", "2025-03-02T15:24:20Z"),
    ("Reserve follow-up: BTC and ETH", "2025-03-02T17:11:00Z"),
    ("Great time to buy", "2025-04-09T13:37:01Z"),
    ("90-day tariff pause", "2025-04-09T17:18:40Z"),
    ("Senate passes GENIUS Act", "2025-06-19T00:01:39Z"),
    ("Happy crypto week", "2025-07-15T15:29:02Z"),
    ("GENIUS Act signed", "2025-07-18T23:53:21Z"),
    ("China 'very strange things'", "2025-10-10T14:57:52Z"),
    ("100% tariff on China", "2025-10-10T20:50:01Z"),
    ("Banks and the GENIUS Act", "2026-03-03T22:02:10Z"),
    ("Gensler and the Anti-Crypto Army", "2026-05-27T22:42:10Z"),
    ("Pass the CLARITY Act", "2026-07-13T14:26:03Z"),
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_e5():
    import importlib.util

    name = "e5_stacked_events"
    if name in sys.modules:
        return sys.modules[name]
    path = ROOT / "research" / "market_evolution" / "e5_stacked_events.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def minute_time(m) -> dt.datetime:
    return T0 + dt.timedelta(minutes=int(m))


def calendar_flags(minutes: np.ndarray) -> dict:
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    wk, mh = np.zeros(minutes.size, bool), np.zeros(minutes.size, bool)
    for i, m in enumerate(minutes):
        t = minute_time(m)
        wk[i] = t.weekday() >= 5
        lt = t.astimezone(ny)
        mins = lt.hour * 60 + lt.minute
        mh[i] = lt.weekday() < 5 and 570 <= mins < 960
    return {"weekend": wk, "mkt": mh}


def excl_mask(n: int = N_MIN) -> np.ndarray:
    a = int((EXCL[0] - T0).total_seconds() // 60)
    b = int((EXCL[1] - T0).total_seconds() // 60)
    out = np.zeros(n, bool)
    out[max(a, 0):min(b, n)] = True
    return out


def stats_block(x: np.ndarray, pool: np.ndarray, seed: int = SEED) -> dict:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {"n": 0, "mean": np.nan, "median": np.nan, "lo": np.nan, "hi": np.nan,
                "p": np.nan}
    lo, hi = boot_mean(x, seed=seed)
    pp = placebo_p(float(x.mean()), pool, x.size, seed=seed)
    return {"n": int(x.size), "mean": float(x.mean()), "median": float(np.median(x)),
            "lo": float(lo), "hi": float(hi), "p": pp["p"], "plac_mean": pp["mean"]}


def compute_symbol(sym: str, events: list[dict], post_min: np.ndarray, pool_min: np.ndarray,
                   drop_1010: bool) -> dict:
    """Abnormal outcomes for events and the placebo pool for one symbol and one run."""
    px = load_symbol(sym)
    arr = minute_arrays(px["close"], px["vol"], px["tb"])
    valid = valid_mask(px["close"])
    elig = valid & ~busy_mask(post_min, N_MIN)
    ex = excl_mask()
    if drop_1010:
        elig &= ~ex
    em = np.array([e["minute"] for e in events])
    ok = (em >= PRE_SPAN) & (em < N_MIN - POST_SPAN)
    ok[ok] &= valid[em[ok]]
    if drop_1010:
        ok[ok] &= ~ex[em[ok]]
    ctrl = np.full((em.size, N_CTRL), -1, dtype=np.int64)
    ctrl[ok] = pick_controls(em[ok], elig)
    anchors = np.where(ok, em, PRE_SPAN)
    ab = abnormal(arr, anchors, ctrl)
    for w in ab:
        for k in ab[w]:
            ab[w][k][~ok] = np.nan
    pm = pool_min[elig[pool_min]]
    pctrl = pick_controls(pm, elig)
    pab = abnormal(arr, pm, pctrl)
    keep = (pctrl >= 0).all(axis=1)
    pab = {w: {k: v[keep] for k, v in d.items()} for w, d in pab.items()}
    return {"ab": ab, "ok": ok & (ctrl >= 0).all(axis=1), "ctrl": ctrl, "arr": arr,
            "pool": pab, "pool_min": pm[keep], "elig": elig, "anchors": anchors}


def stacked_check(arr: dict, anchors: np.ndarray, ctrl: np.ndarray) -> dict:
    """Secondary: per-minute |r| stacked DiD, window FE and event-by-minute FE."""
    e5 = _load_e5()
    ks = np.array([-5, -4, -3, -2, -1, 1, 2, 3, 4, 5])
    win = np.column_stack([anchors, ctrl])  # (n, 17), column 0 = real
    n, W = win.shape
    idx = win[:, :, None] + ks[None, None, :]
    y = np.abs(arr["r"][idx]).ravel()
    ev = np.repeat(np.arange(n), W * ks.size)
    w = np.tile(np.repeat(np.arange(W), ks.size), n)
    k = np.tile(ks, n * W)
    D = ((w == 0) & (k > 0)).astype(float)
    f = e5.stacked_did(y, D, ev * W + w, ev * 100 + (k + 50), ev)
    return {"b": float(f["b"]), "lo": float(f["lo"]), "hi": float(f["hi"]),
            "p": float(f["p"]), "G": int(f["G"])}


_RT_URL = re.compile(r"RT: https://truthsocial\.com/\S*?/statuses/\d+")


def reclassify_rt_comments(posts: list[dict]) -> list[dict]:
    """Exploratory: posts "RT: <status url><own text>" become quotes (found after step 1
    was frozen; the pre-registered file keeps them as reposts)."""
    out = []
    for p in posts:
        q = dict(p)
        if p["kind"] == "repost" and p["text"].startswith("RT:"):
            m = _RT_URL.match(p["text"])
            if m and p["text"][m.end():].strip():
                q["kind"] = "quote"
        out.append(q)
    return out


def exploratory_reclass(posts: list[dict], post_min: np.ndarray, pool_min: np.ndarray) -> dict:
    rp = reclassify_rt_comments(posts)
    events = [e for e in build_events(rp) if PRE_SPAN <= e["minute"] < N_MIN - POST_SPAN]
    topics = np.array([e["topic"] for e in events])
    clean = np.array([e["clean"] for e in events])
    run = compute_symbol("BTCUSDT", events, post_min, pool_min, False)
    out = {"n_reclassified": sum(a["kind"] != b["kind"] for a, b in zip(posts, rp, strict=True))}
    for w in ("post5", "pre5"):
        for k in ("absret", "rv"):
            pool = run["pool"][w][k]
            out[(w, k)] = {t: stats_block(run["ab"][w][k][clean & (topics == t) & run["ok"]],
                                          pool) for t in TOPICS}
    return out


def analyze() -> dict:
    if _sha(PREREG) != PREREG_SHA:
        raise SystemExit("PREREGISTRATION.md changed since it was hashed; refusing to run")
    if _sha(POSTS_CSV) != POSTS_SHA:
        raise SystemExit("posts CSV differs from the pre-registered file")
    posts = load_posts()
    post_min = np.array([p["minute"] for p in posts])
    events = [e for e in build_events(posts)
              if PRE_SPAN <= e["minute"] < N_MIN - POST_SPAN]
    topics = np.array([e["topic"] for e in events])
    clean = np.array([e["clean"] for e in events])
    em = np.array([e["minute"] for e in events])
    cal = calendar_flags(em)
    rng = np.random.default_rng(SEED)
    btc_valid = valid_mask(load_symbol("BTCUSDT")["close"])
    cand = np.flatnonzero(btc_valid & ~busy_mask(post_min, N_MIN))
    pool_min = np.sort(rng.choice(cand, N_POOL, replace=False))
    res: dict = {"events": events, "n_posts": len(posts),
                 "kinds": {k: sum(p["kind"] == k for p in posts)
                           for k in ("original", "quote", "repost", "reply")}}
    runs = {}
    for sym in SYMBOLS:
        runs[(sym, False)] = compute_symbol(sym, events, post_min, pool_min, False)
    runs[("BTCUSDT", True)] = compute_symbol("BTCUSDT", events, post_min, pool_min, True)
    btc = runs[("BTCUSDT", False)]
    pcal = calendar_flags(btc["pool_min"])

    def table(run, w, k, sel, pool_sel=None, topic_list=TOPICS):
        out = {}
        pool = run["pool"][w][k] if pool_sel is None else run["pool"][w][k][pool_sel]
        for t in topic_list:
            m = sel & (topics == t) & run["ok"]
            out[t] = stats_block(run["ab"][w][k][m], pool)
        return out

    base = clean
    # primary
    prim = {k: table(btc, "post5", k, base) for k in ("absret", "rv")}
    ps = [prim[k][t]["p"] for k in ("absret", "rv") for t in TOPICS]
    hp = holm(ps)
    for i, (k, t) in enumerate((k, t) for k in ("absret", "rv") for t in TOPICS):
        prim[k][t]["p_holm"] = hp[i]
    comp = {}
    for k in ("absret", "rv"):
        x_all = btc["ab"]["post5"][k]
        oth = x_all[base & (topics == "other") & btc["ok"]]
        comp[k] = {}
        for t in ("crypto", "tariffs", "fed"):
            x = x_all[base & (topics == t) & btc["ok"]]
            x = x[np.isfinite(x)]
            o = oth[np.isfinite(oth)]
            lo, hi = boot_diff(x, o)
            comp[k][t] = {"diff": float(x.mean() - o.mean()), "lo": float(lo),
                          "hi": float(hi), "p": label_perm_p(x, o)}
    cp = [comp[k][t]["p"] for k in ("absret", "rv") for t in ("crypto", "tariffs", "fed")]
    hc = holm(cp)
    for i, (k, t) in enumerate((k, t) for k in ("absret", "rv")
                               for t in ("crypto", "tariffs", "fed")):
        comp[k][t]["p_holm"] = hc[i]
    res["primary"], res["comparison"] = prim, comp
    # pre-window
    pre = {k: table(btc, "pre5", k, base) for k in ("absret", "rv")}
    for k in ("absret", "rv"):
        for t in TOPICS:
            m = base & (topics == t) & btc["ok"]
            a, b = btc["ab"]["post5"][k][m], btc["ab"]["pre5"][k][m]
            lo, hi = boot_paired(a, b)
            pre[k][t]["post_minus_pre"] = float(np.nanmean(a - b))
            pre[k][t]["pmp_lo"], pre[k][t]["pmp_hi"] = float(lo), float(hi)
    res["pre"] = pre
    # secondary
    sec = {}
    for w in ("post15", "post60"):
        for k in ("absret", "rv"):
            sec[("BTCUSDT", w, k)] = table(btc, w, k, base)
    for w in ("post5", "post15", "post60"):
        sec[("BTCUSDT", w, "logvol")] = table(btc, w, "logvol", base)
    sec[("BTCUSDT", "post5", "imb")] = table(btc, "post5", "imb", base)
    sec[("BTCUSDT", "pre5", "logvol")] = table(btc, "pre5", "logvol", base)
    for sym in ("ETHUSDT", "SOLUSDT"):
        for k in ("absret", "rv", "logvol"):
            sec[(sym, "post5", k)] = table(runs[(sym, False)], "post5", k, base)
        sec[(sym, "pre5", "rv")] = table(runs[(sym, False)], "pre5", "rv", base)
    signed = {}
    for sym in SYMBOLS:
        for w in ("post5", "post15", "post60"):
            signed[(sym, w)] = table(runs[(sym, False)], w, "ret", base,
                                     topic_list=("crypto",))["crypto"]
    res["secondary"], res["signed"] = sec, signed
    # robustness and subgroups (BTC primary outcomes)
    rob = {}
    allev = np.ones_like(clean)
    rob["full merged sample"] = {k: table(btc, "post5", k, allev) for k in ("absret", "rv")}
    nb = runs[("BTCUSDT", True)]
    rob["clean, without 2025-10-10/11"] = {k: table(nb, "post5", k, base)
                                           for k in ("absret", "rv")}
    for name, f, pf in (("weekdays", ~cal["weekend"], ~pcal["weekend"]),
                        ("weekends", cal["weekend"], pcal["weekend"]),
                        ("US market hours", cal["mkt"], pcal["mkt"]),
                        ("outside market hours", ~cal["mkt"], ~pcal["mkt"])):
        rob[name] = {k: table(btc, "post5", k, base & f, pool_sel=pf)
                     for k in ("absret", "rv")}
    rob["pre5, without 2025-10-10/11"] = {k: table(nb, "pre5", k, base)
                                          for k in ("absret", "rv")}
    res["robust"] = rob
    # stacked check
    st = {}
    for t in TOPICS:
        m = base & (topics == t) & btc["ok"]
        st[t] = stacked_check(btc["arr"], btc["anchors"][m], btc["ctrl"][m])
    res["stacked"] = st
    # exploratory: share of events in the top 5% of the placebo distribution
    expl = {}
    q95 = np.nanpercentile(btc["pool"]["post5"]["rv"], 95)
    for t in TOPICS:
        m = base & (topics == t) & btc["ok"]
        x = btc["ab"]["post5"]["rv"][m]
        expl[t] = float(np.mean(x > q95))
    res["exploratory_top5"] = expl
    # exploratory: "RT: <status url>" followed by own text is read as a quote, not a repost
    res["reclass"] = exploratory_reclass(posts, post_min, pool_min)
    # profile
    res["profile"] = {}
    for t in TOPICS:
        m = base & (topics == t) & btc["ok"]
        res["profile"][t] = np.nanmean(profile(btc["arr"], btc["anchors"][m], btc["ctrl"][m]),
                                       axis=0)
    # named events (illustrations)
    by_ts = {p["created_at_utc"]: p for p in posts}
    ev_by_min = {e["minute"]: e for e in events}
    named = []
    for label, ts in NAMED:
        p = by_ts.get(ts)
        if p is None:
            named.append({"label": label, "ts": ts, "missing": True})
            continue
        m = np.array([p["minute"]])
        row = {"label": label, "ts": ts, "kind": p["kind"], "topic": topic_of(p["text"])}
        ev = ev_by_min.get(p["minute"])
        row["status"] = ("clean event" if ev and ev["clean"] else "event, not clean" if ev
                         else "merged into earlier event" if p["kind"] in ("original", "quote")
                         else "not an event")
        for sym in SYMBOLS:
            r = runs[(sym, False)]
            c = pick_controls(m, r["elig"])
            row[f"fallback_{sym}"] = bool((c < 0).any())
            if row[f"fallback_{sym}"]:  # illustration-only: widen to +/-52 weeks, k >= 4
                c = pick_controls(m, r["elig"], max_weeks=52)
                c = c[:, c[0] >= 0]
            if c.shape[1] < 4:
                row[sym] = {w: {k: np.nan for k in ("absret", "rv", "ret")} for w in WINDOWS}
                continue
            ab = abnormal(r["arr"], m, c)
            row[sym] = {w: {k: float(ab[w][k][0]) for k in ("absret", "rv", "ret")}
                        for w in ab}
        prv = btc["pool"]["post5"]["rv"]
        v = row["BTCUSDT"]["post5"]["rv"]
        row["pctl"] = float(np.mean(prv[np.isfinite(prv)] <= v)) if np.isfinite(v) else np.nan
        named.append(row)
    res["named"] = named
    # counts and coverage
    res["counts"] = {
        "events_all": {t: int((topics == t).sum()) for t in TOPICS},
        "events_clean": {t: int((clean & (topics == t)).sum()) for t in TOPICS},
        "analysed": {t: int((clean & (topics == t) & btc["ok"]).sum()) for t in TOPICS},
        "pool": int(btc["pool_min"].size),
        "first_event": events[0]["ts"].isoformat(), "last_event": events[-1]["ts"].isoformat(),
    }
    res["coverage"] = {}
    for sym in SYMBOLS:
        c = load_symbol(sym)["close"]
        res["coverage"][sym] = {"minutes": int(np.isfinite(c).sum()), "grid": int(c.size)}
    return res


# ---------------------------------------------------------------------------- report

COLORS = {"crypto": "#2a78d6", "tariffs": "#eb6834", "fed": "#1baf7a", "other": "#8a8984"}
LABEL = {"crypto": "Crypto", "tariffs": "Tariffs/trade", "fed": "Fed/rates", "other": "Other"}


def _f(x, d=2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.{d}f}"


def _p(x) -> str:
    return "n/a" if x is None or not np.isfinite(x) else (f"{x:.4f}" if x < 0.001 else f"{x:.3f}")


def plot(res: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    ax = axes[0, 0]
    ks = np.arange(PROFILE[0], PROFILE[1] + 1)
    for t in TOPICS:
        y = res["profile"][t].copy()
        y[ks == 0] = np.nan
        ax.plot(ks, y, color=COLORS[t], lw=2 if t != "other" else 1.5,
                label=f"{LABEL[t]} (n={res['counts']['analysed'][t]})")
    ax.axhline(0, color="#52514e", lw=0.8)
    ax.axvline(0, color="#52514e", lw=0.8, ls=":")
    ax.axvspan(0.5, 5.5, color="#d9d8d4", alpha=0.5, lw=0)
    ax.axvspan(-5.5, -0.5, color="#ecebe8", alpha=0.6, lw=0)
    ax.set_xlabel("minutes from post (minute 0 not shown)")
    ax.set_ylabel("abnormal |1-min return|, bps")
    ax.set_title("A. BTCUSDT abnormal |return| by minute, clean events")
    ax.set_ylim(-3, 4)
    ax.legend(frameon=False, fontsize=9, ncol=2, loc="upper left")

    for ax, k, title in ((axes[0, 1], "rv", "B. Abnormal realized vol, BTCUSDT"),
                         (axes[1, 0], "absret", "C. Abnormal |return|, BTCUSDT")):
        x = np.arange(len(TOPICS))
        for j, (blk, off, lab) in enumerate(((res["pre"][k], -0.18, "pre: -5 to -1"),
                                             (res["primary"][k], 0.18, "post: +1 to +5"))):
            m = np.array([blk[t]["mean"] for t in TOPICS])
            lo = np.array([blk[t]["lo"] for t in TOPICS])
            hi = np.array([blk[t]["hi"] for t in TOPICS])
            ax.errorbar(x + off, m, yerr=[m - lo, hi - m], fmt="o" if j else "s", ms=8,
                        color="#0b0b0b" if j else "#a3a29c", capsize=4, lw=2, label=lab)
        ax.axhline(0, color="#52514e", lw=0.8)
        ax.set_xticks(x, [LABEL[t] for t in TOPICS])
        ax.set_ylabel("mean abnormal, bps (95% bootstrap CI)")
        ax.set_title(title + ", clean events")
        ax.legend(frameon=False, fontsize=9)

    ax = axes[1, 1]
    names = list(res["robust"].keys())
    names = ["clean (primary)"] + [n for n in names if not n.startswith("pre5")]
    for i, t in enumerate(TOPICS):
        for j, n in enumerate(names):
            blk = res["primary"]["rv"][t] if j == 0 else res["robust"][n]["rv"][t]
            yv = j + (i - 1.5) * 0.18
            if blk["n"] == 0:
                continue
            ax.plot([blk["lo"], blk["hi"]], [yv, yv], color=COLORS[t], lw=2)
            ax.plot(blk["mean"], yv, "o", color=COLORS[t], ms=6,
                    label=LABEL[t] if j == 0 else None)
    ax.axvline(0, color="#52514e", lw=0.8)
    ax.set_yticks(range(len(names)), names)
    ax.invert_yaxis()
    ax.set_xlabel("mean abnormal realized vol +1 to +5, bps (95% CI)")
    ax.set_title("D. Robustness and subgroups, BTCUSDT")
    ax.legend(frameon=False, fontsize=9, ncol=4, loc="upper center",
              bbox_to_anchor=(0.4, -0.12))
    for a in axes.ravel():
        a.spines[["top", "right"]].set_visible(False)
        a.grid(axis="y", color="#ecebe8", lw=0.6)
    fig.suptitle("C1: Trump Truth Social posts and Binance BTC futures, 2022-05 to 2026-10",
                 fontsize=13)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def topic_table(blk: dict, holm_col: bool = False) -> list[str]:
    hdr = "| topic | events | mean | 95% CI | median | placebo p |" + (
        " Holm p |" if holm_col else "")
    out = [hdr, "|---|---|---|---|---|---|" + ("---|" if holm_col else "")]
    for t in TOPICS:
        b = blk[t]
        line = (f"| {LABEL[t]} | {b['n']} | {_f(b['mean'])} | [{_f(b['lo'])}, {_f(b['hi'])}] "
                f"| {_f(b['median'])} | {_p(b['p'])} |")
        if holm_col:
            line += f" {_p(b.get('p_holm', np.nan))} |"
        out.append(line)
    return out


def report(res: dict, conclusion: str) -> str:
    c = res["counts"]
    L = ["# C1: do Trump's Truth Social posts move crypto markets?", ""]
    L += ["Generated by `research/politics/c1_trump_posts.py analyze`. Design fixed in",
          "`research/politics/PREREGISTRATION.md` before any price data was opened:",
          "", f"- pre-registration sha256 `{PREREG_SHA}`",
          f"- posts file sha256 `{POSTS_SHA}`", ""]
    L += ["## Plain-language conclusion", "", conclusion, ""]
    L += ["## Coverage", "",
          f"- Posts: `posts/truth_realDonaldTrump.csv`, {res['n_posts']:,} posts from "
          "2022-02-14 to 2026-11-17 (" + ", ".join(f"{k} {v:,}" for k, v in res["kinds"].items())
          + "). Kinds come from text patterns; the archive has no reply flag, and posts "
          "deleted before 2026-08-20 are probably missing.",
          (f"- Events (originals and quotes, merged within 5 minutes) inside the price data: "
          f"{sum(c['events_all'].values()):,}, from {c['first_event'][:10]} to "
          f"{c['last_event'][:10]}; clean (no earlier event within 60 minutes): "
          f"{sum(c['events_clean'].values()):,}; clean and analysable on BTCUSDT "
          f"(complete window and 16 controls): {sum(c['analysed'].values()):,}."),
          "- Prices: Binance USDT-M 1-minute klines 2022-02 to 2026-10, SHA-256 checked; "
          + "; ".join(f"{s} {v['minutes']:,} of {v['grid']:,} minutes"
                      for s, v in res["coverage"].items()) + ".",
          f"- Placebo pool: {c['pool']:,} random minutes with no post within 60 minutes.", ""]
    L += ["### Events per topic", "", "| topic | all events | clean | clean, analysed |",
          "|---|---|---|---|"]
    for t in TOPICS:
        L.append(f"| {LABEL[t]} | {c['events_all'][t]:,} | {c['events_clean'][t]:,} | "
                 f"{c['analysed'][t]:,} |")
    L += ["", "## Primary result (pre-registered)", "",
          ("BTCUSDT, clean events, minutes +1 to +5 after the post minute. Abnormal = event "
          "value minus the mean of 16 same-minute-of-week controls on other weeks with no "
          "post within 60 minutes, in basis points. Intervals: 95% bootstrap over events. "
          "p: two-sided placebo test against random post times; Holm over the 8 tests."), ""]
    for k, name in (("absret", "Abnormal absolute log return, bps"),
                    ("rv", "Abnormal realized volatility, bps")):
        L += [f"**{name}**", ""] + topic_table(res["primary"][k], True) + [""]
    L += ["### Primary comparison: each topic minus Other", "",
          "| outcome | topic | difference | 95% CI | permutation p | Holm p |",
          "|---|---|---|---|---|---|"]
    for k in ("absret", "rv"):
        for t in ("crypto", "tariffs", "fed"):
            b = res["comparison"][k][t]
            L.append(f"| {k} | {LABEL[t]} | {_f(b['diff'])} | [{_f(b['lo'])}, {_f(b['hi'])}] "
                     f"| {_p(b['p'])} | {_p(b['p_holm'])} |")
    L += ["", "## Pre-window check (pre-registered)", "",
          ("Same statistics over minutes -5 to -1, and the paired difference post minus pre. "
          "If the pre-window is as elevated as the post-window, the posts are reacting to "
          "moves already under way."), ""]
    for k in ("absret", "rv"):
        L += [f"**{k}, minutes -5 to -1**", ""] + topic_table(res["pre"][k]) + [""]
        L += ["| topic | post minus pre | 95% CI |", "|---|---|---|"]
        for t in TOPICS:
            b = res["pre"][k][t]
            L.append(f"| {LABEL[t]} | {_f(b['post_minus_pre'])} | "
                     f"[{_f(b['pmp_lo'])}, {_f(b['pmp_hi'])}] |")
        L.append("")
    L += ["## Robustness and subgroups (pre-registered, secondary)", "",
          ("BTCUSDT abnormal realized volatility and absolute return, +1 to +5, mean [95% CI] "
          "(placebo p). Subgroup placebos are drawn from pool minutes in the same subgroup."),
          "", "| sample | outcome | " + " | ".join(LABEL[t] for t in TOPICS) + " |",
          "|---|---|" + "---|" * len(TOPICS)]
    for name, blk in res["robust"].items():
        for k in ("rv", "absret"):
            cells = [f"{_f(blk[k][t]['mean'])} [{_f(blk[k][t]['lo'])}, {_f(blk[k][t]['hi'])}] "
                     f"(p {_p(blk[k][t]['p'])}, n {blk[k][t]['n']})" for t in TOPICS]
            L.append(f"| {name} | {k} | " + " | ".join(cells) + " |")
    L += ["", "## Secondary outcomes (pre-registered, descriptive)", "",
          ("Clean events, mean abnormal [95% CI] (placebo p). Units: bps for absret, rv and "
          "ret; log points for logvol; imbalance in [-1, 1]."), "",
          "| symbol | window | outcome | " + " | ".join(LABEL[t] for t in TOPICS) + " |",
          "|---|---|---|" + "---|" * len(TOPICS)]
    for (sym, w, k), blk in res["secondary"].items():
        d = 3 if k in ("logvol", "imb") else 2
        cells = [f"{_f(blk[t]['mean'], d)} [{_f(blk[t]['lo'], d)}, {_f(blk[t]['hi'], d)}] "
                 f"(p {_p(blk[t]['p'])})" for t in TOPICS]
        L.append(f"| {sym} | {w} | {k} | " + " | ".join(cells) + " |")
    L += ["", ("**Signed abnormal return after crypto posts** (no tone coding, so positive "
          "and negative posts can cancel):"), "",
          "| symbol | window | events | mean, bps | 95% CI | placebo p |", "|---|---|---|---|---|---|"]
    for (sym, w), b in res["signed"].items():
        L.append(f"| {sym} | {w} | {b['n']} | {_f(b['mean'])} | [{_f(b['lo'])}, {_f(b['hi'])}] "
                 f"| {_p(b['p'])} |")
    L += ["", ("**Stacked check** (per-minute |r|, minutes -5..-1 and +1..+5, event and its 16 "
          "controls; window and event-by-minute fixed effects; errors clustered by event; "
          "`e5_stacked_events.stacked_did`): coefficient on real window x post minute, bps "
          "per minute."), "", "| topic | b | 95% CI | p | clusters |", "|---|---|---|---|---|"]
    for t in TOPICS:
        b = res["stacked"][t]
        L.append(f"| {LABEL[t]} | {_f(b['b'])} | [{_f(b['lo'])}, {_f(b['hi'])}] | {_p(b['p'])} "
                 f"| {b['G']} |")
    L += ["", "## Exploratory (not in the pre-registration)", "",
          "Share of clean events whose abnormal realized volatility (+1 to +5) is above the "
          "95th percentile of the placebo pool (5% expected under no effect): "
          + ", ".join(f"{LABEL[t]} {100 * v:.1f}%" for t, v in res["exploratory_top5"].items())
          + ".", ""]
    rc = res["reclass"]
    L += ["### Exploratory: quote posts misread as reposts", "",
          (f"After the post file was frozen, the analysis showed that {rc['n_reclassified']:,} "
           "posts of the form \"RT: <truthsocial status url><own text>\" are quote posts with "
           "Trump's own comment (for example the 2025-03-02 17:11 'And, obviously, BTC and "
           "ETH...' post), not plain reposts. The pre-registered results above keep them as "
           "reposts (not events). Re-running the primary and pre-window statistics with them "
           "as quotes (BTCUSDT, clean events, mean [95% CI] (placebo p, n)):"), "",
          "| window | outcome | " + " | ".join(LABEL[t] for t in TOPICS) + " |",
          "|---|---|" + "---|" * len(TOPICS)]
    for (w, k), blk in ((key, v) for key, v in rc.items() if isinstance(key, tuple)):
        cells = [f"{_f(blk[t]['mean'])} [{_f(blk[t]['lo'])}, {_f(blk[t]['hi'])}] "
                 f"(p {_p(blk[t]['p'])}, n {blk[t]['n']})" for t in TOPICS]
        L.append(f"| {w} | {k} | " + " | ".join(cells) + " |")
    L += [""]
    L += ["## Key named events: illustrations, not tests", "",
          ("Chosen because they are famous, which selects on the outcome. BTCUSDT abnormal "
          "values in bps; pctl = percentile of the +1 to +5 abnormal realized volatility "
          "within the placebo pool. Status says whether the post is a clean event in the "
          "tested sample. * = fewer than 16 eligible controls within 26 weeks (busy "
          "posting hours), so up to 16 from within 52 weeks are used, illustration only; "
          "n/a = fewer than 4."), "",
          ("| event | UTC | kind / topic | status | BTC pre rv | BTC +1..+5 rv | pctl | "
          "BTC +1..+5 ret | BTC +1..+60 ret | SOL +1..+60 ret |"),
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in res["named"]:
        if r.get("missing"):
            L.append(f"| {r['label']} | {r['ts']} | not found | | | | | | | |")
            continue
        b, s = r["BTCUSDT"], r["SOLUSDT"]
        pct = _f(100 * r["pctl"], 0)
        star = "*" if r["fallback_BTCUSDT"] else ""
        L.append(f"| {r['label']} | {r['ts'][:16].replace('T', ' ')} | {r['kind']} / "
                 f"{r['topic']} | {r['status']} | {_f(b['pre5']['rv'], 1)} | "
                 f"{_f(b['post5']['rv'], 1)}{star} | {pct} | "
                 f"{_f(b['post5']['ret'], 1)} | {_f(b['post60']['ret'], 1)} | "
                 f"{_f(s['post60']['ret'], 1)} |")
    L += ["", "## Caveats", "",
          ("- Topic keywords are crude: content in images, videos and links is invisible, "
          "and 'powell' or 'reciprocal' can be off-topic. Media-only posts are 'other'."),
          ("- The archive probably lacks posts deleted before 2026-08-20, and kinds are "
          "inferred from text; there is no reply flag. 1,116 quote posts were misread as "
          "reposts in the frozen file (see the exploratory section)."),
          ("- The pre-registered keywords miss some crypto posts: 'CONGRATULATIONS "
          "BITCOINERS!!! $100,000!!!' is 'other' because `bitcoins?` does not match "
          "'bitcoiners'. Left as registered; a v2 list should use `bitcoin\\w*`."),
          ("- About 17% of clean events (1,276) lack 16 eligible control weeks (or a complete "
          "window) "
          "within 26 weeks, because Trump posts at the same hours week after week; they are "
          "dropped, so the busiest posting hours are under-represented."),
          ("- Times are when Truth Social stored the post; markets learn of it seconds to "
          "minutes later through alert accounts and wires, which is why minute 0 is "
          "skipped and +15 and +60 are reported."),
          ("- Clean events exclude posting bursts, so the sample under-represents the busiest "
          "moments; the full merged sample is shown as a check."),
          ("- Futures only (no spot cross-check), no equity-market factor, and no exclusion "
          "of scheduled macro releases (FOMC, CPI), which can coincide with Fed posts."),
          ("- Abnormal means of absolute moves are dominated by a few large events; medians "
          "are shown, and 2025-10-10 is dropped as a check."), "",
          "![C1 figure](c1_trump_posts.png)", ""]
    return "\n".join(L)


def main(argv: list[str]) -> int:
    import argparse
    import pickle

    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["convert", "download", "analyze"])
    ap.add_argument("--cached", action="store_true",
                    help="reuse the saved results (data/politics/klines/c1_results.pkl)")
    a = ap.parse_args(argv)
    if a.step == "convert":
        print(convert())
        return 0
    if a.step == "download":
        files = download()
        print(len(files), "files,", round(sum(f.stat().st_size for f in files) / 1e6, 1), "MB")
        return 0
    cache = KLINES / "c1_results.pkl"
    if a.cached and cache.exists():
        res = pickle.loads(cache.read_bytes())
    else:
        res = analyze()
        cache.write_bytes(pickle.dumps(res))
    OUT.mkdir(parents=True, exist_ok=True)
    plot(res, OUT / "c1_trump_posts.png")
    (OUT / "c1_trump_posts.md").write_text(report(res, CONCLUSION), encoding="utf-8")
    print("wrote", OUT / "c1_trump_posts.md")
    return 0


CONCLUSION = """\
**Yes, but only some posts, by a little, and mainly through tariffs.** Over 6,055 clean
post events (2022-05 to 2026-10), BTC futures were more volatile than usual in the five
minutes after a Trump post about tariffs and trade: abnormal realized volatility +3.6 bps
[95% CI 1.1, 6.5] on a normal level of about 12.6 bps (roughly +29%), abnormal absolute
return +5.1 bps [1.3, 9.8] (about +49%), volume about +23%, placebo p 0.0002 (Holm
0.002), and clearly larger than for other posts (difference +3.3 bps rv [0.8, 6.3],
permutation p 0.0001). ETH and SOL show the same pattern. The effect is a small average
with a long tail: 13% of tariff posts land in the top 5% of the placebo distribution,
led by the 2025-04-09 tariff pause and the 2025-10-10 100% China tariff, and it holds
without 2025-10-10.

Fed and rates posts point the same way (+3.4 bps rv [0.6, 6.6]) but do not survive the
multiple-testing correction (placebo p 0.044, Holm 0.18). Crypto posts, the topic one
would expect to matter most, show no average effect (-1.2 bps rv [-4.7, 3.4], n = 17
clean events): too few posts, several famous ones fall inside posting bursts and are
not in the clean sample, and the big ones (the 2025-03-02 reserve post) are rare
exceptions. All other posts, 96% of events, move BTC by about +0.3 bps (2.5%), which
is statistically detectable only because there are thousands of them and is matched by
a similar rise just before the posts, so it is not evidence of influence.

The pre-window check is reassuring for the topics that matter: in minutes -5 to -1
before tariff and Fed posts, BTC was no more volatile than usual (tariffs +0.8 bps rv
[-0.6, 2.3]), and the post-minus-pre difference is positive (tariffs +2.8 [0.6, 5.4]).
So, on average, tariff posts are not just commentary on a move already under way.

In plain terms: a typical Trump post does nothing to crypto; a tariff post adds a few
basis points of extra movement in the next five minutes, and occasionally a great deal;
crypto-specific posts have no detectable average effect at this sample size."""

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
