"""P1: bookDepth quality mask and metrics screen over all USDT-M perpetuals.

The design is fixed in research/liquidations/PREREGISTRATION_P1.md. This script refuses to
scan, report or test unless that file, bookdepth_mask_v2.txt (primary),
bookdepth_mask_v1_DRAFT.txt (reported alongside) and metrics_screen_v1.txt all match the
sha256 values below. `validate` is the only
command that runs before the lock: it re-runs the mask on the contract-days listed in the
pre-registration's acceptance checks, all of which were examined before the plan was
written, and prints the checks.

    PYTHONPATH=src .venv/bin/python research/liquidations/p1_scan.py universe
    PYTHONPATH=src .venv/bin/python research/liquidations/p1_scan.py validate
    PYTHONPATH=src .venv/bin/python research/liquidations/p1_scan.py scan [--workers 16]
    PYTHONPATH=src .venv/bin/python research/liquidations/p1_scan.py report
    PYTHONPATH=src .venv/bin/python research/liquidations/p1_scan.py onset

Files are read from the S3 address of data.binance.vision (the same bucket; the short
host is not reachable from every environment). Every file is held in memory only, checked
against its published .CHECKSUM, and recorded in a manifest with its own sha256, size,
S3 Last-Modified and ETag, the timestamp stored inside the zip, and the fetch time. Per-
symbol results go to data/liquidations/p1/sym/<SYMBOL>/ (git-ignored) so the scan resumes.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
import polars as pl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from microstructure.quality import bookdepth as bd
from microstructure.quality import metrics as mt

MASK = HERE / "bookdepth_mask_v2.txt"  # primary
MASK_SHA = "c800985ddac189c14044b8c5364c9bce02d5b62401f956cc5b43237d21731a09"
MASK_V1 = HERE / "bookdepth_mask_v1_DRAFT.txt"  # reported alongside
MASK_V1_SHA = "61d003375266604e95b2d9ff66149b9f39d0eb03862c8a779f566c6abc4513f7"
SCREEN = HERE / "metrics_screen_v1.txt"
# SCREEN_SHA and PREREG_SHA recorded when the project owner approved them, 2026-11-22
SCREEN_SHA: str | None = "4e3934d6f2891f92fcd80deedca26b94a567ad364b594e6e3305919b189d09e4"
PREREG = HERE / "PREREGISTRATION_P1.md"
PREREG_SHA: str | None = "f63240d23064848d73613145d0d8e47aaa9086246b67ef1929539f5453f64543"

BUCKET = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
UM = "data/futures/um/daily"
START, END = dt.date(2023, 1, 1), dt.date(2026, 11, 18)
EXCHANGEINFO = ROOT / "results" / "exchangeinfo_snapshot.json"
CACHE = ROOT / "data" / "liquidations" / "p1"
OUT = HERE / "data" / "p1"

HORIZONS = (15, 60, 240)  # minutes; 60 is primary
SHIFT_HOURS = np.array([s * h for h in range(24, 24 * 28 + 1) for s in (-1, 1)], np.int64)
PLACEBO_CLEAR_S = 6 * 3600
SEED = 20261122


# --------------------------------------------------------------------------- locks

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_locks(require_plan: bool = True) -> None:
    for path, want in ((MASK, MASK_SHA), (MASK_V1, MASK_V1_SHA)):
        if sha256_file(path) != want:
            raise SystemExit(f"{path.name} changed since it was hashed; refusing to run")
    if not require_plan:
        return
    for path, want in ((SCREEN, SCREEN_SHA), (PREREG, PREREG_SHA)):
        if want is None:
            raise SystemExit(f"{path.name} is not locked yet (no sha256 recorded in "
                             "p1_scan.py); it must be reviewed and hashed before running")
        if sha256_file(path) != want:
            raise SystemExit(f"{path.name} changed since it was hashed; refusing to run")


# ------------------------------------------------------------------------- archive

@dataclass(frozen=True)
class Key:
    name: str  # file name, e.g. BTCUSDT-bookDepth-2025-10-10.zip
    last_modified: str
    etag: str
    size: int


class Archive:
    """Read-only access to the public bucket: listings and checksum-verified bytes."""

    def __init__(self, base: str = BUCKET, timeout: float = 120, retries: int = 4):
        import httpx

        self.base, self.retries = base, retries
        self.client = httpx.Client(timeout=timeout, limits=httpx.Limits(max_connections=64))

    def _get(self, url: str, params: dict | None = None):
        import httpx

        err: Exception | None = None
        for i in range(self.retries):
            try:
                r = self.client.get(url, params=params)
                if r.status_code in (403, 404):
                    return None
                r.raise_for_status()
                return r
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                err = e
                time.sleep(2 ** i)
        raise RuntimeError(f"GET {url} failed after {self.retries} tries") from err

    def list_dir(self, prefix: str) -> tuple[list[str], list[Key]]:
        """Sub-folders and files directly under prefix (S3 ListObjects with delimiter)."""
        ns = "{http://s3.amazonaws.com/doc/2006-03-01/}"
        dirs: list[str] = []
        keys: list[Key] = []
        marker = ""
        while True:
            r = self._get(self.base, {"prefix": prefix, "delimiter": "/", "marker": marker})
            root = ElementTree.fromstring(r.content)
            for cp in root.iter(f"{ns}CommonPrefixes"):
                dirs.append(cp.find(f"{ns}Prefix").text)
            for c in root.iter(f"{ns}Contents"):
                k = c.find(f"{ns}Key").text
                keys.append(Key(k.rsplit("/", 1)[-1], c.find(f"{ns}LastModified").text,
                                c.find(f"{ns}ETag").text.strip('"'),
                                int(c.find(f"{ns}Size").text)))
            if root.find(f"{ns}IsTruncated").text != "true":
                return dirs, keys
            nxt = root.find(f"{ns}NextMarker")
            marker = nxt.text if nxt is not None else (keys[-1].name if keys else dirs[-1])

    def fetch(self, path: str) -> tuple[bytes, str] | None:
        """(zip bytes, published sha256) after verifying them, or None if absent."""
        ck = self._get(f"{self.base}/{path}.CHECKSUM")
        if ck is None:
            return None
        want = ck.text.split()[0].lower()
        for _ in range(2):
            r = self._get(f"{self.base}/{path}")
            if r is None:
                return None
            if hashlib.sha256(r.content).hexdigest() == want:
                return r.content, want
        raise RuntimeError(f"{path}: sha256 does not match its .CHECKSUM")


def unzip_one(blob: bytes) -> tuple[bytes, str]:
    """Inner CSV bytes and the inner file's stored timestamp (ISO, no zone)."""
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        infos = zf.infolist()
        if len(infos) != 1:
            raise ValueError(f"expected one member, got {len(infos)}")
        # zip stores local time without a zone; kept as written, no zone attached
        stamp = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(*infos[0].date_time)
        return zf.read(infos[0]), stamp


# ------------------------------------------------------------------------ universe

def x6_table(path: Path = EXCHANGEINFO) -> dict[str, bool]:
    info = json.loads(path.read_text())
    return {s["symbol"]: bd.x6_excluded(s) for s in info["symbols"]}


def is_usdt_perp(sym: str) -> bool:
    return sym.endswith("USDT") and "_" not in sym and re.fullmatch(r"[0-9A-Z]+", sym) is not None


def build_universe(archive: Archive) -> pl.DataFrame:
    dirs, _ = archive.list_dir(f"{UM}/bookDepth/")
    syms = sorted(d.rstrip("/").rsplit("/", 1)[-1] for d in dirs)
    x6 = x6_table()
    rows = []
    for s in syms:
        rows.append({"symbol": s, "usdt_perp": is_usdt_perp(s),
                     "x6": x6.get(s), "classified": s in x6})
    df = pl.DataFrame(rows)
    return df.with_columns(
        (pl.col("usdt_perp") & ~pl.col("x6").fill_null(False)).alias("in_scope"))


# --------------------------------------------------------------------- one symbol

def _date_of(name: str) -> dt.date | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})\.zip$", name)
    return dt.date.fromisoformat(m.group(1)) if m else None


def _kind_keys(archive: Archive, sym: str, kind: str, start: dt.date,
               end: dt.date) -> dict[dt.date, Key]:
    sub = f"{UM}/{kind}/{sym}/" + ("1m/" if kind == "klines" else "")
    _, keys = archive.list_dir(sub)
    out = {}
    for k in keys:
        d = _date_of(k.name)
        if d is not None and start <= d <= end:
            out[d] = k
    return out


def _path(kind: str, sym: str, d: dt.date) -> str:
    if kind == "klines":
        return f"{UM}/klines/{sym}/1m/{sym}-1m-{d.isoformat()}.zip"
    return f"{UM}/{kind}/{sym}/{sym}-{kind}-{d.isoformat()}.zip"


KINDS = ("bookDepth", "klines", "metrics")


S3_SENSITIVITY = (10, 40)


def scan_symbol(sym: str, archive: Archive, start: dt.date = START, end: dt.date = END,
                workers: int = 16, log: Callable[[str], None] = print) -> dict:
    """Mask, screen and onset inputs for one symbol; returns frames and arrays in memory.

    The mask is applied with the S3 threshold of v1 (20) and, for the D5 sensitivity
    checks, with 10 and 40; only D1 verdicts and onset inputs are kept for those.
    """
    keys = {k: _kind_keys(archive, sym, k, start, end) for k in KINDS}
    dates = sorted(set(keys["bookDepth"]) | set(keys["metrics"]))
    manifest: list[dict] = []

    def get(d: dt.date) -> dict:
        out = {}
        for kind in KINDS:
            key = keys[kind].get(d)
            if key is None:
                continue
            got = archive.fetch(_path(kind, sym, d))
            rec = {"symbol": sym, "kind": kind, "date": d, "file": key.name,
                   "bytes": key.size, "last_modified": key.last_modified, "etag": key.etag,
                   "fetched_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                   "sha256": None, "zip_member_mtime": None, "error": None}
            if got is None:
                rec["error"] = "listed but not served"
            else:
                blob, sha = got
                rec["sha256"] = sha
                try:
                    out[kind], rec["zip_member_mtime"] = unzip_one(blob)
                except (zipfile.BadZipFile, ValueError) as e:
                    rec["error"] = f"unzip: {e}"
            manifest.append(rec)
        return out

    feats: list[bd.DayFeatures] = []
    prev_depth = None
    last_ts = -1
    closes: dict[int, np.ndarray] = {}
    metric_frames: list[pl.DataFrame] = []
    metric_days: list[dict] = []
    errors: list[dict] = []
    with cf.ThreadPoolExecutor(workers) as ex:
        for i in range(0, len(dates), 4 * workers):
            chunk = dates[i:i + 4 * workers]
            for d, files in zip(chunk, ex.map(get, chunk), strict=True):
                kl = bd.Klines.empty()
                if "klines" in files:
                    try:
                        kl = bd.parse_klines_csv(files["klines"])
                    except Exception as e:  # noqa: BLE001 - recorded, day treated as missing
                        errors.append({"symbol": sym, "date": d, "kind": "klines",
                                       "error": repr(e)[:300]})
                    day0 = int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.UTC).timestamp())
                    c = np.full(1440, np.nan)
                    k = (kl.open_s - day0) // 60
                    ok = (k >= 0) & (k < 1440)
                    c[k[ok]] = kl.close[ok]
                    closes[day0] = c
                if "bookDepth" in files:
                    try:
                        book = bd.parse_bookdepth_csv(files["bookDepth"])
                    except Exception as e:  # noqa: BLE001
                        errors.append({"symbol": sym, "date": d, "kind": "bookDepth",
                                       "error": repr(e)[:300]})
                        book = None
                    if book is not None and book.ts.size:
                        keep = book.ts > last_ts  # I11: overlap with the previous file
                        if not keep.all():
                            errors.append({"symbol": sym, "date": d, "kind": "bookDepth",
                                           "error": f"dropped {int((~keep).sum())} "
                                                    "snapshots not after previous file"})
                            book = bd.DayBook(book.ts[keep], book.depth[keep],
                                              book.notional[keep], book.conflict[keep],
                                              book.n_rows)
                        if book.ts.size:
                            f = bd.day_features(book, kl, prev_depth)
                            feats.append(f)
                            prev_depth, last_ts = f.last_depth, int(book.ts[-1])
                if "metrics" in files:
                    try:
                        mdf = mt.parse_metrics_csv(files["metrics"])
                    except Exception as e:  # noqa: BLE001
                        errors.append({"symbol": sym, "date": d, "kind": "metrics",
                                       "error": repr(e)[:300]})
                        mdf = None
                    if mdf is not None:
                        metric_frames.append(mdf)
                        day0 = int(dt.datetime(d.year, d.month, d.day,
                                               tzinfo=dt.UTC).timestamp())
                        conv = mt.label_convention(mt.screen(mdf).rows, kl)
                        metric_days.append({"symbol": sym, "date": d, "n_rows": mdf.height,
                                            "n_missing": mt.missing_labels(
                                                mdf["ts"].drop_nulls().to_numpy(), day0),
                                            **conv})
            log(f"{sym}: {min(i + 4 * workers, len(dates))}/{len(dates)} dates")

    mask = bd.SymbolMask.from_days(sym, feats, s6_min_s1_run=bd.S6_MIN_S1_RUN_V2)
    days = mask.day_table()
    v1 = bd.SymbolMask.from_days(sym, feats, s6_min_s1_run=bd.S6_MIN_S1_RUN_V1)
    if days.height:
        days = days.join(v1.day_table().select(
            "date", *[pl.col(c).alias(f"{c}_v1") for c in
                      ("n_S6", "n_valid_s", "max_gap_s", "d1_s", "n_valid_sx", "max_gap_sx",
                       "d1_sx")]), on="date", how="left")
    v1_s6 = v1.intervals().filter(pl.col("rule") == "S6").with_columns(
        pl.lit("S6_v1").alias("rule"))
    sens = {}
    for k in S3_SENSITIVITY:
        mk = bd.SymbolMask.from_days(sym, feats, s3_min_run=k)
        if days.height:
            days = days.join(mk.day_table().select("date", pl.col("d1_s").alias(f"d1_s_s3_{k}"),
                                                   pl.col("d1_sx").alias(f"d1_sx_s3_{k}")),
                             on="date", how="left")
        sens[k] = onset_inputs(mk, closes)
    res = {"days": days, "intervals": pl.concat([mask.intervals(), v1_s6]),
           "manifest": pl.DataFrame(manifest, infer_schema_length=None),
           "errors": pl.DataFrame(errors, infer_schema_length=None),
           "metric_days": pl.DataFrame(metric_days, infer_schema_length=None)}
    if metric_frames:
        scr = mt.screen(pl.concat(metric_frames))
        res["metric_flags"] = (scr.rows.filter(pl.col("m0") | pl.col("m2") | pl.col("m2_value")
                                               | pl.col("m3"))
                               .select("ts", "m0", "m2", "m2_value", "m3")
                               .with_columns(pl.lit(sym).alias("symbol")))
        res["metric_dups"] = {"identical": scr.n_dup_identical, "conflict": scr.n_dup_conflict}
    res |= onset_inputs(mask, closes)
    res["sens"] = sens
    return res


# ---------------------------------------------------------------- onset test inputs

def minute_closes(closes: dict[int, np.ndarray]) -> tuple[int, np.ndarray]:
    """(first minute epoch s, close per minute) over the span of the given days."""
    if not closes:
        return 0, np.empty(0)
    d0, d1 = min(closes), max(closes)
    arr = np.full((d1 - d0) // 60 + 1440, np.nan)
    for day, c in closes.items():
        arr[(day - d0) // 60:(day - d0) // 60 + 1440] = c
    return d0, arr


def prior_returns(t0: int, close: np.ndarray, minute_s: np.ndarray, h: int) -> np.ndarray:
    """ln C(m-1) - ln C(m-1-h) for onset minutes m (epoch s); NaN outside the data."""
    m = (minute_s - t0) // 60
    a, b = m - 1, m - 1 - h
    ok = (b >= 0) & (a < close.size)
    out = np.full(m.shape, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        out[ok] = np.log(close[a[ok]]) - np.log(close[b[ok]])
    return out


def onset_inputs(mask: bd.SymbolMask, closes: dict[int, np.ndarray]) -> dict:
    """Onsets with their prior returns at the onset and at every common time shift.

    returns[h] has shape (n_onsets, 1 + len(SHIFT_HOURS)); column 0 is the onset itself.
    A shifted time within 6 h of any S1, S2 or S3 run start of the symbol is NaN.
    """
    on = bd.onsets(mask)
    t0, close = minute_closes(closes)
    starts = [mask.s1_runs[:, 0], mask.s2_runs[:, 0]] + [r[:, 0] for _, r in mask.s3_runs]
    starts = np.unique(np.concatenate([mask.ts[s] for s in starts if s.size])) if any(
        s.size for s in starts) else np.empty(0, np.int64)
    ts = on["ts"].to_numpy().astype(np.int64)
    minute = (ts // 60) * 60
    shifts = np.r_[0, SHIFT_HOURS * 3600]
    grid = minute[:, None] + shifts[None, :]
    near = np.zeros(grid.shape, bool)
    if starts.size:
        k = np.searchsorted(starts, grid)
        lo = np.abs(grid - starts[np.maximum(k - 1, 0)])
        hi = np.abs(starts[np.minimum(k, starts.size - 1)] - grid)
        near = np.minimum(lo, hi) < PLACEBO_CLEAR_S
        near[:, 0] = False
    out = {"onsets": on}
    for h in HORIZONS:
        r = prior_returns(t0, close, grid.ravel(), h).reshape(grid.shape)
        r[near] = np.nan
        out[f"r{h}"] = r.astype(np.float32)
    return out


# ------------------------------------------------------------------- onset test

def _median_cols(r: np.ndarray) -> np.ndarray:
    """Median of each column over its finite entries; NaN for an empty column."""
    out = np.full(r.shape[1], np.nan)
    fin = np.isfinite(r)
    for j in np.flatnonzero(fin.any(axis=0)):
        out[j] = np.median(r[fin[:, j], j])
    return out


def shift_test(r: np.ndarray, side: str, cluster: np.ndarray | None = None) -> dict:
    """One-sided common-time-shift test of the median prior return (test T1).

    r: (n_onsets, 1 + n_shifts) for one side; column 0 is the onset, the others the same
    onsets moved by each common shift. Predicted sign: negative for bid, positive for ask.
    p = (1 + #{shifts at least as extreme as observed}) / (1 + n_shifts).
    With cluster labels, the statistic is the median over clusters of the cluster
    median (secondary S-b); the clusters move with the shift.
    """
    if r.shape[0] == 0 or not np.isfinite(r[:, 0]).any():
        return {"n": 0, "median": np.nan, "p": np.nan}
    if cluster is None:
        stat = _median_cols(r)
    else:
        labels = np.unique(cluster)
        per = np.vstack([_median_cols(r[cluster == c]) for c in labels])
        stat = _median_cols(per)
    t_obs, null = float(stat[0]), stat[1:]
    null = null[np.isfinite(null)]
    extreme = (null <= t_obs) if side == "bid" else (null >= t_obs)
    obs = r[np.isfinite(r[:, 0]), 0]
    pred = (obs < 0) if side == "bid" else (obs > 0)
    fin = np.isfinite(r[:, 1:])
    hit = (r[:, 1:] < 0) if side == "bid" else (r[:, 1:] > 0)
    return {"n": int(obs.size), "median": t_obs,
            "null_median": float(np.median(null)) if null.size else np.nan,
            "n_shifts": int(null.size),
            "p": float((1 + extreme.sum()) / (1 + null.size)) if null.size else np.nan,
            "share_predicted_sign": float(pred.mean()),
            "null_share": float(hit[fin].mean()) if fin.any() else np.nan}


def holm(ps: dict[str, float], alpha: float = 0.05) -> dict[str, bool]:
    """Holm (1979) step-down rejections at family-wise level alpha."""
    order = sorted(ps, key=lambda k: (not np.isfinite(ps[k]), ps[k]))
    out, stop = {}, False
    for i, k in enumerate(order):
        ok = not stop and bool(np.isfinite(ps[k])) and ps[k] <= alpha / (len(order) - i)
        stop = stop or not ok
        out[k] = ok
    return out


SEEN_MONTHS = ("2025-10", "2026-09")  # onset months examined before the plan


def t1_tables(on: pl.DataFrame, r: dict[int, np.ndarray],
              sens: dict[int, tuple[pl.DataFrame, np.ndarray]] | None = None) -> dict:
    """Primary and secondary results of T1 (PREREGISTRATION_P1.md section 5)."""
    side = on["side"].to_numpy()
    t = on["ts"].to_numpy()
    month = np.array([dt.datetime.fromtimestamp(x, dt.UTC).strftime("%Y-%m") for x in t])
    year = np.array([m[:4] for m in month])
    hour = t // 3600
    rule = on["rule"].to_numpy()
    out: dict = {"primary": {}, "secondary": {}}
    for sd in ("bid", "ask"):
        out["primary"][sd] = shift_test(r[60][side == sd], sd)
    out["holm_reject"] = holm({sd: out["primary"][sd]["p"] for sd in ("bid", "ask")})
    sec = out["secondary"]
    for sd in ("bid", "ask"):
        m = side == sd
        sec[f"{sd}:unseen_months"] = shift_test(r[60][m & ~np.isin(month, SEEN_MONTHS)], sd)
        sec[f"{sd}:hour_clusters"] = shift_test(r[60][m], sd, cluster=hour[m])
        for h in HORIZONS:
            if h != 60:
                sec[f"{sd}:h{h}"] = shift_test(r[h][m], sd)
        for ru in ("S1", "S3"):
            sec[f"{sd}:{ru}"] = shift_test(r[60][m & (rule == ru)], sd)
        for y in sorted(set(year)):
            sec[f"{sd}:{y}"] = shift_test(r[60][m & (year == y)], sd)
        for k, (on_k, r_k) in (sens or {}).items():
            sk = on_k["side"].to_numpy() == sd
            sec[f"{sd}:s3_{k}"] = shift_test(r_k[sk], sd)
    return out


# --------------------------------------------------------------------- commands

def _symdir(sym: str) -> Path:
    return CACHE / "sym" / sym


def save_symbol(sym: str, res: dict, root: Path | None = None) -> None:
    d = (root or CACHE / "sym") / sym
    d.mkdir(parents=True, exist_ok=True)
    for k in ("days", "intervals", "manifest", "errors", "metric_days", "metric_flags",
              "onsets"):
        if k in res and res[k].height:
            res[k].write_parquet(d / f"{k}.parquet")
    arrays = {f"r{h}": res[f"r{h}"] for h in HORIZONS}
    for k, sres in res.get("sens", {}).items():
        if sres["onsets"].height:
            sres["onsets"].write_parquet(d / f"onsets_s3_{k}.parquet")
        arrays[f"r60_s3_{k}"] = sres["r60"]
    np.savez_compressed(d / "returns.npz", **arrays)
    (d / "meta.json").write_text(json.dumps({"metric_dups": res.get("metric_dups", {}),
                                             "mask_sha": MASK_SHA, "screen_sha": SCREEN_SHA,
                                             "prereg_sha": PREREG_SHA}))
    (d / "DONE").touch()


def cmd_universe(_: argparse.Namespace) -> None:
    check_locks(require_plan=False)
    uni = build_universe(Archive())
    OUT.mkdir(parents=True, exist_ok=True)
    uni.write_csv(OUT / "universe.csv")
    n = uni.filter(pl.col("in_scope"))
    print(f"{uni.height} bookDepth folders; {uni['usdt_perp'].sum()} USDT perps; "
          f"{n.height} in scope; {n.filter(~pl.col('classified')).height} in scope but not "
          "in the 2026-08-13 exchangeInfo snapshot (unclassified for X6)")


def shard_symbols(symbols: list[str], shard: str) -> list[str]:
    """Symbols of shard "i/n" (0-based i): every n-th symbol starting at position i."""
    i, n = (int(x) for x in shard.split("/"))
    if not 0 <= i < n:
        raise ValueError(f"bad shard {shard!r}")
    return [s for k, s in enumerate(symbols) if k % n == i]


def cmd_scan(a: argparse.Namespace) -> None:
    """Scan every in-scope symbol not yet DONE. A symbol that fails after all retries gets a
    FAILED file with its traceback and is retried on the next run; the scan goes on."""
    import traceback

    check_locks()
    uni = pl.read_csv(OUT / "universe.csv").filter(pl.col("in_scope"))
    archive = Archive()
    n_fail = 0
    for sym in shard_symbols(uni["symbol"].to_list(), a.shard):
        d = _symdir(sym)
        if (d / "DONE").exists():
            continue
        t = time.time()
        try:
            res = scan_symbol(sym, archive, workers=a.workers, log=lambda s: None)
            save_symbol(sym, res)
        except Exception:  # noqa: BLE001 - recorded in FAILED and retried on the next run
            n_fail += 1
            d.mkdir(parents=True, exist_ok=True)
            (d / "FAILED").write_text(traceback.format_exc())
            print(f"{sym}: FAILED after {time.time() - t:.0f}s (see {d / 'FAILED'})",
                  flush=True)
            continue
        (d / "FAILED").unlink(missing_ok=True)
        print(f"{sym}: {res['days'].height} contract-days, {res['onsets'].height} onsets, "
              f"{time.time() - t:.0f}s", flush=True)
    print(f"shard {a.shard} finished, {n_fail} symbols failed", flush=True)


VALIDATION = (  # (symbol, first date, last date): every one was looked at before the plan
    ("BTCUSDT", "2025-10-09", "2025-10-11"),
    ("BTCUSDT", "2025-04-15", "2025-04-17"),
    ("DOGEUSDT", "2024-02-19", "2024-02-22"),
    ("ETHUSDT", "2025-10-10", "2025-10-10"),
    ("BTCUSDT", "2026-09-02", "2026-09-04"),
    ("BTCUSDT", "2024-08-04", "2024-08-06"),
)


def cmd_validate(_: argparse.Namespace) -> None:
    """Acceptance checks of the implementation on contract-days examined before the plan."""
    check_locks(require_plan=False)
    archive = Archive()
    report = []
    for sym, a, b in VALIDATION:
        res = scan_symbol(sym, archive, dt.date.fromisoformat(a), dt.date.fromisoformat(b),
                          log=lambda s: None)
        iv = res["intervals"]
        first = {}
        for rule in ("S1", "S2", "S3"):
            sub = iv.filter(pl.col("rule") == rule).sort("start_ts")
            if sub.height:
                t = dt.datetime.fromtimestamp(sub["start_ts"][0], dt.UTC)
                first[rule] = f"{t:%Y-%m-%d %H:%M:%S} {sub['side'][0]}"
        days = res["days"].select("date", "n_snap", "n_valid_s", "d1_s", "n_S1", "n_S2",
                                  "n_S3", "n_S5", "n_S6")
        conv = res["metric_days"].select("date", "convention", "corr_start", "corr_end")
        n_bad = res["manifest"].filter(pl.col("error").is_not_null()).height
        report.append(f"## {sym} {a} to {b}\n\nfirst runs: {first}\n\n"
                      f"files: {res['manifest'].height}, errors: {n_bad}\n\n"
                      f"```\n{days}\n{conv}\n```\n")
        print(report[-1], flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "validation.md").write_text(
        "# P1 implementation acceptance checks\n\nRun "
        f"{dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M} UTC on contract-days examined before "
        "the plan. Mask sha256 " + MASK_SHA + ".\n\n" + "\n".join(report))


def _load_all(name: str) -> pl.DataFrame:
    parts = sorted((CACHE / "sym").glob(f"*/{name}.parquet"))
    return pl.concat([pl.read_parquet(p) for p in parts], how="diagonal_relaxed") if parts \
        else pl.DataFrame()


def cmd_report(_: argparse.Namespace) -> None:
    check_locks()
    OUT.mkdir(parents=True, exist_ok=True)
    days = _load_all("days")
    man = _load_all("manifest")
    files = (man.filter((pl.col("kind") == "bookDepth") & pl.col("sha256").is_not_null())
             .select("symbol", "date").unique())
    d1_cols = [c for c in days.columns if c.startswith("d1_")]
    full = files.join(days, on=["symbol", "date"], how="left").with_columns(
        [pl.col(c).fill_null(False) for c in d1_cols])
    d3 = bd.d3_dropped_dates(full)
    d3_v1 = bd.d3_dropped_dates(full, col="d1_s_v1").select(
        "date", pl.col("fail_share").alias("fail_share_v1"),
        pl.col("d3_dropped").alias("d3_dropped_v1"))
    d3 = d3.join(d3_v1, on="date", how="left")
    days.write_parquet(OUT / "day_table.parquet")
    d3.write_csv(OUT / "d3_dates.csv")
    _load_all("intervals").write_parquet(OUT / "intervals.parquet", compression="zstd")
    man.write_parquet(OUT / "manifest.parquet", compression="zstd")
    _load_all("metric_days").write_parquet(OUT / "metrics_days.parquet")
    _load_all("metric_flags").write_parquet(OUT / "metrics_flags.parquet")
    _load_all("errors").write_csv(OUT / "errors.csv")
    t1p = OUT / "t1_onset_test.json"
    t1 = json.loads(t1p.read_text()) if t1p.exists() else None
    (OUT / "p1_report.md").write_text(write_report(
        full, d3, _load_all("intervals"), _load_all("metric_days"), man,
        _load_all("metric_flags"), t1))
    print(f"{full.height} contract-days with a file; D1 pass v2 {full['d1_s'].mean():.3f}, "
          f"v1 {full['d1_s_v1'].mean():.3f}; D3 drops {d3['d3_dropped'].sum()} dates (v2), "
          f"{d3['d3_dropped_v1'].sum()} (v1)")


def episodes(iv: pl.DataFrame, min_s: int = 3600, link_s: int = 3600) -> pl.DataFrame:
    """S1, S2 and S3 runs longer than min_s, merged across symbols: a run joins the current
    episode if it starts within link_s of the previous run's start."""
    runs = (iv.filter(pl.col("rule").is_in(["S1", "S2", "S3"])
                      & ((pl.col("end_ts") - pl.col("start_ts")) >= min_s))
            .sort("start_ts"))
    if runs.height == 0:
        return pl.DataFrame()
    start = runs["start_ts"].to_numpy()
    ep = np.cumsum(np.r_[True, np.diff(start) > link_s])
    return (runs.with_columns(pl.Series("episode", ep))
            .group_by("episode").agg(
                pl.col("start_ts").min().alias("first_start"),
                pl.col("start_ts").max().alias("last_start"),
                pl.col("end_ts").max().alias("last_end"),
                pl.col("symbol").n_unique().alias("n_symbols"),
                pl.col("rule").unique().sort().str.join("+").alias("rules"),
                pl.col("side").unique().sort().str.join("+").alias("sides"))
            .sort("first_start")
            .with_columns([pl.from_epoch(c).alias(c) for c in
                           ("first_start", "last_start", "last_end")]))


def _md_table(df: pl.DataFrame, floatfmt: str = "{:.4f}") -> str:
    cols = df.columns
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.iter_rows():
        out.append("| " + " | ".join(floatfmt.format(v) if isinstance(v, float) else str(v)
                                     for v in row) + " |")
    return "\n".join(out)


def d5_table(full: pl.DataFrame) -> pl.DataFrame:
    """D5: share of snapshots and of contract-days touched by each rule, and D1 failures."""
    n_snap = full["n_snap"].sum()
    rows = []
    for r in bd.RULES + ("S5_nokline", "S6_v1", "calendar"):
        col = f"n_{r}"
        if col in full.columns:
            rows.append({"item": f"rule {r}", "share_of_snapshots": full[col].sum() / n_snap,
                         "share_of_contract_days": float((full[col] > 0).mean())})
    for c in [c for c in full.columns if c.startswith("d1_")]:
        rows.append({"item": f"fails D1 ({c})", "share_of_snapshots": float("nan"),
                     "share_of_contract_days": float((~full[c]).mean())})
    return pl.DataFrame(rows)


def write_report(full: pl.DataFrame, d3: pl.DataFrame, iv: pl.DataFrame,
                 mdays: pl.DataFrame, man: pl.DataFrame, mflags: pl.DataFrame,
                 t1: dict | None) -> str:
    """Markdown report of P1 (PREREGISTRATION_P1.md sections 4 and 5)."""
    L = ["# P1 results: bookDepth mask, metrics screen and onset test", "",
         f"Generated {dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M} UTC by `p1_scan.py report`.",
         (f"Pre-registration sha256 `{PREREG_SHA}`; mask v2 `{MASK_SHA}` (primary), "
          f"v1 `{MASK_V1_SHA}`; metrics screen `{SCREEN_SHA}`."), "",
         (f"- Symbols: {full['symbol'].n_unique()}; contract-days with a verified bookDepth "
          f"file: {full.height}; files in manifest: {man.height}; files with an error: "
          f"{man.filter(pl.col('error').is_not_null()).height}."), "",
         "## 1. Share removed by each rule (D5)", "",
         _md_table(d5_table(full.filter(pl.col("n_snap").is_not_null()))), "",
         "## 2. Dates dropped for all contracts (D3)", ""]
    dropped = d3.filter(pl.col("d3_dropped") | pl.col("d3_dropped_v1"))
    L += [(f"{d3['d3_dropped'].sum()} dates under v2, {d3['d3_dropped_v1'].sum()} under v1, "
           f"of {d3.height}."), "", _md_table(dropped) if dropped.height else "(none)", "",
          "## 3. Corruption episodes (runs over 1 hour, merged across symbols)", ""]
    ep = episodes(iv)
    L += [_md_table(ep) if ep.height else "(none)", "",
          "## 4. Metrics screen", ""]
    if mflags.height:
        L += ["| rule | rows flagged |", "|---|---|"]
        L += [f"| {c} | {int(mflags[c].sum())} |" for c in ("m0", "m2", "m2_value", "m3")]
        L += [""]
    if mdays.height:
        conv = mdays.join(man.filter(pl.col("kind") == "metrics").select(
            "symbol", "date", "zip_member_mtime"), on=["symbol", "date"], how="left")
        by_month = (conv.with_columns(pl.col("date").dt.strftime("%Y-%m").alias("file_month"))
                    .group_by("file_month").agg(
                        (pl.col("convention") == "start").sum().alias("start"),
                        (pl.col("convention") == "end").sum().alias("end"),
                        (pl.col("convention") == "undetermined").sum().alias("undetermined"))
                    .sort("file_month"))
        by_rewrite = (conv.with_columns(pl.col("zip_member_mtime").str.slice(0, 4)
                                        .alias("zip_year"))
                      .group_by("zip_year").agg(
                          (pl.col("convention") == "start").sum().alias("start"),
                          (pl.col("convention") == "end").sum().alias("end"),
                          (pl.col("convention") == "undetermined").sum().alias("undetermined"))
                      .sort("zip_year"))
        L += ["Label convention (M5) by file date:", "", _md_table(by_month), "",
              ("By year of the timestamp stored inside the zip (a later year means the file "
               "was rewritten):"), "", _md_table(by_rewrite), ""]
    L += ["## 5. Test T1: do corruption onsets follow same-direction price moves?", ""]
    if t1 is None:
        L += ["Not run yet (`p1_scan.py onset`)."]
    else:
        prim = pl.DataFrame([{"side": k, **{x: v.get(x) for x in
                              ("n", "median", "null_median", "n_shifts", "p",
                               "share_predicted_sign", "null_share")}}
                             for k, v in t1["primary"].items()])
        L += ["Primary (60-minute prior return, Holm over the two sides at 5%):", "",
              _md_table(prim, "{:.5f}"), "", f"Holm rejections: {t1['holm_reject']}", "",
              "Secondary analyses (reported, never used to change the verdict):", "",
              _md_table(pl.DataFrame([{"analysis": k, **{x: v.get(x) for x in
                                       ("n", "median", "null_median", "p")}}
                                      for k, v in t1["secondary"].items()]), "{:.5f}")]
    return "\n".join(L) + "\n"


def _load_onsets(suffix: str = "", key: str = "r60") -> tuple[pl.DataFrame, list[np.ndarray]]:
    ons, rets = [], []
    for done in sorted((CACHE / "sym").glob("*/DONE")):
        p = done.parent / f"onsets{suffix}.parquet"
        if p.exists():
            ons.append(pl.read_parquet(p))
            rets.append(np.load(done.parent / "returns.npz")[key].astype(float))
    return (pl.concat(ons) if ons else pl.DataFrame()), rets


def cmd_onset(_: argparse.Namespace) -> None:
    check_locks()
    on, _ = _load_onsets()
    r = {h: np.vstack(_load_onsets(key=f"r{h}")[1]) for h in HORIZONS}
    sens = {}
    for k in S3_SENSITIVITY:
        on_k, r_k = _load_onsets(f"_s3_{k}", f"r60_s3_{k}")
        if on_k.height:
            sens[k] = (on_k, np.vstack(r_k))
    res = {"prereg_sha": PREREG_SHA, "mask_sha": MASK_SHA, "screen_sha": SCREEN_SHA,
           "n_onsets": on.height} | t1_tables(on, r, sens)
    OUT.mkdir(parents=True, exist_ok=True)
    on.write_parquet(OUT / "onsets.parquet")
    (OUT / "t1_onset_test.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res["primary"], indent=1), res["holm_reject"])


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("universe").set_defaults(f=cmd_universe)
    sub.add_parser("validate").set_defaults(f=cmd_validate)
    s = sub.add_parser("scan")
    s.add_argument("--workers", type=int, default=16)
    s.add_argument("--shard", default="0/1", help="i/n: scan every n-th symbol from i")
    s.set_defaults(f=cmd_scan)
    sub.add_parser("report").set_defaults(f=cmd_report)
    sub.add_parser("onset").set_defaults(f=cmd_onset)
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
