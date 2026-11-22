"""bookDepth quality mask, versions 1 and 2.

Implements research/liquidations/bookdepth_mask_v1_DRAFT.txt (sha256
61d003375266604e95b2d9ff66149b9f39d0eb03862c8a779f566c6abc4513f7) and
research/liquidations/bookdepth_mask_v2.txt, which differs from v1 only in S6: crossed (S1)
runs shorter than 3 snapshots are invalid themselves but get no buffer. Choose the version
with `s6_min_s1_run` (1 for v1, 3 for v2). Rule names (S0 to S6,
X1 to X6, D1 to D3) follow that text. Where the text leaves a choice open, the choice is
fixed in research/liquidations/PREREGISTRATION_P1.md (section "Interpretation notes") and
marked "I<n>" in comments here.

Work flow for one symbol:

1. `parse_bookdepth_csv` turns one daily file into a `DayBook` (one row per snapshot).
2. `day_features` computes the rules that need only one snapshot (S0, S1, S4, S5) plus
   the equality bits that the run rules need, carrying the previous day's last snapshot.
3. `SymbolMask.from_days` concatenates the days in timestamp order, so runs continue
   across midnight, and applies the run rules (S2, S3) and the buffer (S6).
4. `day_table`, `intervals` and `onsets` summarise the result.

Nothing here downloads, fills, interpolates or carries values forward (rule D4).
"""
from __future__ import annotations

import datetime as dt
import io
from dataclasses import dataclass, field

import numpy as np
import polars as pl

CORE = (-5.0, -4.0, -3.0, -2.0, -1.0, 1.0, 2.0, 3.0, 4.0, 5.0)
N_CORE = len(CORE)
BID_COLS = (4, 3, 2, 1, 0)  # inner to outer: -1, -2, ..., -5
ASK_COLS = (5, 6, 7, 8, 9)  # inner to outer: +1, +2, ..., +5

S2_MIN_RUN = 3
S3_MIN_RUN = 20
S5_TOL = 0.02
S6_BUFFER = 20
S6_MIN_S1_RUN_V1 = 1
S6_MIN_S1_RUN_V2 = 3
D1_MIN_VALID = 2592
D1_MAX_GAP_S = 900
D2_GRID_S = 30
D2_TOL_S = 45
D2_MIN_COVER = 0.90
D2_MAX_GAP_S = 300
D3_MAX_FAIL_SHARE = 0.20

RULES = ("S0", "S1", "S2", "S3", "S4", "S5", "S6")


def _utc(s: str) -> int:
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.UTC).timestamp())


# Calendar exclusions X1 to X4 as half-open [start, end) epoch-second windows. X1's end
# "11:13" is read as 11:13:00 (I5). X2's ETHUSDT-only extension is symbol-specific.
CALENDAR = {
    "X1": [(_utc("2025-04-16T10:31:00"), _utc("2025-05-19T11:13:00"))],
    "X2": [(_utc("2025-10-09T00:00:00"), _utc("2025-10-16T00:00:00")),
           (_utc("2025-10-29T00:00:00"), _utc("2025-10-31T00:00:00"))],
    "X3": [(_utc("2025-08-25T00:00:00"), _utc("2025-08-30T00:00:00"))],
    "X4": [(_utc("2026-09-03T00:00:00"), _utc("2026-09-12T00:00:00"))],
}
CALENDAR_SYMBOL = {
    "X2": {"ETHUSDT": [(_utc("2025-10-31T00:00:00"), _utc("2025-12-02T00:00:00"))]},
}
X6_SUBTYPES = ("TradFi", "Pre-Market")
X6_TYPES = ("EQUITY", "HK_EQUITY", "COMMODITY", "INDEX", "PREMARKET")


# ---------------------------------------------------------------------------- parsing

@dataclass(frozen=True)
class DayBook:
    """One daily bookDepth file, core bands only, one row per snapshot."""

    ts: np.ndarray  # int64 epoch seconds, strictly increasing
    depth: np.ndarray  # (n, 10) float64 in CORE order, NaN where the row is missing
    notional: np.ndarray  # (n, 10) float64
    conflict: np.ndarray  # bool (n,): two rows for one (ts, band) with different values
    n_rows: int  # raw rows in the file, all bands


def parse_bookdepth_csv(raw: bytes) -> DayBook:
    """Parse the CSV inside a daily bookDepth zip.

    Handles both band spellings (-5 in 2025 files, -5.00 in 2026 files) and files with or
    without a header row. Rows for non-core bands (the 0.2 bands) are dropped here (I1).
    Exact duplicate rows are collapsed; duplicates with different values mark S0.
    """
    first = raw.split(b"\n", 1)[0]
    has_header = first.lower().startswith(b"timestamp")
    df = pl.read_csv(io.BytesIO(raw), has_header=has_header, infer_schema_length=0,
                     new_columns=["timestamp", "percentage", "depth", "notional"])
    n_rows = df.height
    df = df.select(
        pl.col("timestamp").str.strptime(pl.Datetime("ms"), "%Y-%m-%d %H:%M:%S", strict=True)
        .dt.epoch("s").alias("ts"),
        pl.col("percentage").cast(pl.Float64).alias("pct"),
        pl.col("depth").cast(pl.Float64, strict=False),
        pl.col("notional").cast(pl.Float64, strict=False),
    ).filter(pl.col("pct").is_in(list(CORE)))
    if df.height == 0:
        e = np.empty((0, N_CORE))
        return DayBook(np.empty(0, np.int64), e, e.copy(), np.empty(0, bool), n_rows)
    df = df.unique()
    conflict_ts = (df.group_by("ts", "pct").len().filter(pl.col("len") > 1)
                   .get_column("ts").unique().to_numpy())
    ts_all = df.get_column("ts").to_numpy().astype(np.int64)
    ts = np.unique(ts_all)
    row = np.searchsorted(ts, ts_all)
    col = np.searchsorted(np.array(CORE), df.get_column("pct").to_numpy())
    depth = np.full((ts.size, N_CORE), np.nan)
    notional = np.full((ts.size, N_CORE), np.nan)
    depth[row, col] = df.get_column("depth").to_numpy()
    notional[row, col] = df.get_column("notional").to_numpy()
    conflict = np.isin(ts, conflict_ts)
    return DayBook(ts, depth, notional, conflict, n_rows)


@dataclass(frozen=True)
class Klines:
    """1-minute futures/um klines of one day: open time (epoch s), low, high, close."""

    open_s: np.ndarray
    low: np.ndarray
    high: np.ndarray
    close: np.ndarray
    taker_buy: np.ndarray
    volume: np.ndarray

    @classmethod
    def empty(cls) -> Klines:
        z = np.empty(0)
        return cls(np.empty(0, np.int64), z, z, z, z, z)


def parse_klines_csv(raw: bytes) -> Klines:
    first = raw.split(b"\n", 1)[0]
    has_header = first.lower().startswith(b"open_time")
    df = pl.read_csv(io.BytesIO(raw), has_header=has_header, infer_schema_length=0)
    c = df.columns
    t = df.get_column(c[0]).cast(pl.Int64).to_numpy()
    t = np.where(t > 10**14, t // 1000, t) // 1000  # us or ms to s
    order = np.argsort(t, kind="stable")

    def f(i: int) -> np.ndarray:
        return df.get_column(c[i]).cast(pl.Float64).to_numpy()[order]

    return Klines(t[order].astype(np.int64), f(3), f(2), f(4), f(9), f(5))


# ---------------------------------------------------------------- one-snapshot rules

def inner_cols(depth: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Column of the inner bid and inner ask band (closest to zero with depth > 0); -1 if
    none."""
    def first_pos(cols: tuple[int, ...]) -> np.ndarray:
        sub = depth[:, list(cols)]
        ok = np.isfinite(sub) & (sub > 0)
        k = np.argmax(ok, axis=1)
        out = np.asarray(cols)[k]
        return np.where(ok.any(axis=1), out, -1)

    return first_pos(BID_COLS), first_pos(ASK_COLS)


def band_vwap(depth: np.ndarray, notional: np.ndarray, cols: np.ndarray) -> np.ndarray:
    i = np.arange(depth.shape[0])
    c = np.where(cols < 0, 0, cols)
    with np.errstate(divide="ignore", invalid="ignore"):
        v = notional[i, c] / depth[i, c]
    return np.where(cols < 0, np.nan, v)


@dataclass
class DayFeatures:
    """Per-snapshot results of one day, ready to concatenate."""

    ts: np.ndarray
    s0: np.ndarray
    s1: np.ndarray
    s4: np.ndarray
    s5: np.ndarray
    s5_nokline: np.ndarray
    s1_side: np.ndarray  # int8: -1 bid stale, +1 ask stale, 0 unknown
    eq_band: np.ndarray  # (n, 10) depth equals the previous snapshot's in that band
    pos_band: np.ndarray  # (n, 10) depth finite and > 0
    mid: np.ndarray  # implied mid (VWAP inner bid + VWAP inner ask) / 2
    last_depth: np.ndarray  # depth vector of the last snapshot, for the next day's carry


def day_features(book: DayBook, kl: Klines, prev_depth: np.ndarray | None) -> DayFeatures:
    d, n = book.depth, book.notional
    finite = np.isfinite(d).all(axis=1) & np.isfinite(n).all(axis=1)
    with np.errstate(invalid="ignore"):
        nonpos = ((d <= 0) | (n <= 0)).any(axis=1)
    s0 = book.conflict | ~finite | nonpos

    bc, ac = inner_cols(d)
    vb, va = band_vwap(d, n, bc), band_vwap(d, n, ac)
    with np.errstate(invalid="ignore"):
        s1 = vb >= va  # NaN compares False; such snapshots already fail S0

    with np.errstate(invalid="ignore"):
        bid_viol = (d[:, list(BID_COLS[1:])] < d[:, list(BID_COLS[:-1])]).any(axis=1)
        ask_viol = (d[:, list(ASK_COLS[1:])] < d[:, list(ASK_COLS[:-1])]).any(axis=1)
    s4 = bid_viol | ask_viol

    mid = (vb + va) / 2
    minute = (book.ts // 60) * 60
    k = np.searchsorted(kl.open_s, minute)
    k_ok = (k < kl.open_s.size)
    k_ok[k_ok] = kl.open_s[k[k_ok]] == minute[k_ok]
    kc = np.where(k_ok, k, 0)
    low = np.where(k_ok, kl.low[kc] if kl.low.size else np.nan, np.nan)
    high = np.where(k_ok, kl.high[kc] if kl.high.size else np.nan, np.nan)
    close = np.where(k_ok, kl.close[kc] if kl.close.size else np.nan, np.nan)
    with np.errstate(invalid="ignore"):
        off = (mid < (1 - S5_TOL) * low) | (mid > (1 + S5_TOL) * high)
    s5_nokline = ~k_ok
    s5 = off | s5_nokline | ~np.isfinite(mid)  # I3: no kline for the minute is invalid

    with np.errstate(divide="ignore", invalid="ignore"):
        db = np.abs(np.log(vb / close))
        da = np.abs(np.log(va / close))
    s1_side = np.where(~np.isfinite(db) | ~np.isfinite(da), 0,
                       np.where(db >= da, -1, 1)).astype(np.int8)

    prev = np.vstack([prev_depth[None, :] if prev_depth is not None
                      else np.full((1, N_CORE), np.nan), d[:-1]]) if d.shape[0] else d
    eq_band = d == prev  # NaN never equal
    with np.errstate(invalid="ignore"):
        pos_band = np.isfinite(d) & (d > 0)
    last = d[-1].copy() if d.shape[0] else (prev_depth if prev_depth is not None
                                            else np.full(N_CORE, np.nan))
    return DayFeatures(book.ts, s0, s1, s4, s5, s5_nokline, s1_side, eq_band, pos_band,
                       mid, last)


# ---------------------------------------------------------------------- run rules

def true_runs(x: np.ndarray) -> np.ndarray:
    """(k, 2) inclusive [start, end] index pairs of maximal runs of True."""
    x = np.asarray(x, bool)
    if x.size == 0:
        return np.empty((0, 2), np.int64)
    dx = np.diff(np.r_[0, x.astype(np.int8), 0])
    starts = np.flatnonzero(dx == 1)
    ends = np.flatnonzero(dx == -1) - 1
    return np.column_stack([starts, ends]).astype(np.int64)


def repeat_runs(same_as_prev: np.ndarray, min_len: int) -> np.ndarray:
    """Runs of identical consecutive snapshots of length >= min_len.

    same_as_prev[i] says snapshot i equals snapshot i-1. A True run [a, b] means
    snapshots a-1 .. b are identical, a run of b - a + 2 snapshots. Every snapshot of the
    run is returned, including its first (S2, S3: "every snapshot of the run").
    """
    r = true_runs(same_as_prev)
    if r.size == 0:
        return r
    r = np.column_stack([np.maximum(r[:, 0] - 1, 0), r[:, 1]])
    return r[(r[:, 1] - r[:, 0] + 1) >= min_len]


def paint(n: int, runs: np.ndarray) -> np.ndarray:
    """Boolean mask of length n that is True on every [start, end] run."""
    m = np.zeros(n + 1, np.int32)
    if runs.size:
        np.add.at(m, runs[:, 0], 1)
        np.add.at(m, runs[:, 1] + 1, -1)
    return np.cumsum(m[:-1]) > 0


@dataclass
class SymbolMask:
    """Mask v1 applied to one symbol's full concatenated snapshot series."""

    symbol: str
    ts: np.ndarray
    flags: dict[str, np.ndarray]  # rule -> bool per snapshot
    s5_nokline: np.ndarray
    s1_side: np.ndarray
    s1_runs: np.ndarray
    s2_runs: np.ndarray
    s3_runs: list[tuple[int, np.ndarray]]  # (band column, runs)
    invalid: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        inv = np.zeros(self.ts.size, bool)
        for r in RULES:
            inv |= self.flags[r]
        self.invalid = inv

    @classmethod
    def from_days(cls, symbol: str, days: list[DayFeatures],
                  s3_min_run: int = S3_MIN_RUN,
                  s6_min_s1_run: int = S6_MIN_S1_RUN_V2) -> SymbolMask:
        days = [d for d in days if d.ts.size]
        if not days:
            z = np.empty(0, bool)
            e = np.empty((0, 2), np.int64)
            return cls(symbol, np.empty(0, np.int64), {r: z for r in RULES}, z,
                       np.empty(0, np.int8), e, e, [])
        ts = np.concatenate([d.ts for d in days])
        if np.any(np.diff(ts) <= 0):
            raise ValueError(f"{symbol}: snapshot timestamps not increasing across days")
        cat = {k: np.concatenate([getattr(d, k) for d in days])
               for k in ("s0", "s1", "s4", "s5", "s5_nokline", "s1_side")}
        eq_band = np.concatenate([d.eq_band for d in days])
        pos_band = np.concatenate([d.pos_band for d in days])
        n = ts.size

        s1_runs = true_runs(cat["s1"])
        s2_runs = repeat_runs(eq_band.all(axis=1), S2_MIN_RUN)
        s3_runs = []
        s3 = np.zeros(n, bool)
        for b in range(N_CORE):
            r = repeat_runs(eq_band[:, b] & pos_band[:, b], s3_min_run)
            if r.size:
                s3_runs.append((b, r))
                s3 |= paint(n, r)
        s2 = paint(n, s2_runs)

        s1_long = s1_runs[(s1_runs[:, 1] - s1_runs[:, 0] + 1) >= s6_min_s1_run]
        anchors = [s1_long, s2_runs] + [r for _, r in s3_runs]
        anchors = np.vstack(anchors) if any(a.size for a in anchors) else np.empty((0, 2), int)
        if anchors.size:
            before = np.column_stack([np.maximum(anchors[:, 0] - S6_BUFFER, 0),
                                      anchors[:, 0] - 1])
            after = np.column_stack([anchors[:, 1] + 1,
                                     np.minimum(anchors[:, 1] + S6_BUFFER, n - 1)])
            buf = np.vstack([before, after])
            buf = buf[buf[:, 1] >= buf[:, 0]]
            s6 = paint(n, buf)
        else:
            s6 = np.zeros(n, bool)

        flags = {"S0": cat["s0"], "S1": cat["s1"], "S2": s2, "S3": s3, "S4": cat["s4"],
                 "S5": cat["s5"], "S6": s6}
        return cls(symbol, ts, flags, cat["s5_nokline"], cat["s1_side"], s1_runs, s2_runs,
                   s3_runs)

    # ------------------------------------------------------------------ summaries

    def calendar_mask(self) -> np.ndarray:
        """True where X1 to X4 exclude the snapshot (X5 is D1, X6 is a symbol rule)."""
        out = np.zeros(self.ts.size, bool)
        for name, wins in CALENDAR.items():
            for a, b in wins + CALENDAR_SYMBOL.get(name, {}).get(self.symbol, []):
                out |= (self.ts >= a) & (self.ts < b)
        return out

    def day_table(self) -> pl.DataFrame:
        """One row per contract-day: snapshot counts by rule, valid counts, D1 verdicts."""
        if self.ts.size == 0:
            return pl.DataFrame()
        day = self.ts // 86_400
        xmask = self.calendar_mask()
        valid_s = ~self.invalid
        valid_sx = valid_s & ~xmask
        bounds = np.flatnonzero(np.r_[True, day[1:] != day[:-1], True])
        rows = []
        for i in range(bounds.size - 1):
            a, b = bounds[i], bounds[i + 1]
            t = self.ts[a:b]
            r = {"symbol": self.symbol,
                 "date": dt.date(1970, 1, 1) + dt.timedelta(days=int(day[a])),
                 "n_snap": int(b - a)}
            for k in RULES:
                r[f"n_{k}"] = int(self.flags[k][a:b].sum())
            r["n_S5_nokline"] = int(self.s5_nokline[a:b].sum())
            r["n_calendar"] = int(xmask[a:b].sum())
            for tag, v in (("s", valid_s[a:b]), ("sx", valid_sx[a:b])):
                tv = t[v]
                gap = int(np.diff(tv).max()) if tv.size > 1 else (0 if tv.size else 86_400)
                r[f"n_valid_{tag}"] = int(v.sum())
                r[f"max_gap_{tag}"] = gap
                r[f"d1_{tag}"] = bool(v.sum() >= D1_MIN_VALID and gap <= D1_MAX_GAP_S)
            rows.append(r)
        return pl.DataFrame(rows)

    def intervals(self) -> pl.DataFrame:
        """Invalid stretches by rule: one row per maximal run of flagged snapshots.

        Rows for S1, S2 and S3 are the anchor runs themselves (S3 one row per band); rows for
        S0, S4, S5 and S6 are maximal runs of that flag. A snapshot is valid under v1 iff
        its timestamp lies in no interval (start and end inclusive).
        """
        out: list[dict] = []

        def add(rule: str, runs: np.ndarray, band: float | None, side: str) -> None:
            for s, e in runs:
                out.append({"symbol": self.symbol, "rule": rule, "band": band, "side": side,
                            "start_ts": int(self.ts[s]), "end_ts": int(self.ts[e]),
                            "n_snap": int(e - s + 1)})

        for rule in ("S0", "S4", "S5", "S6"):
            add(rule, true_runs(self.flags[rule]), None, "na")
        for s, e in self.s1_runs:
            side = {-1: "bid", 1: "ask"}.get(int(self.s1_side[s]), "unknown")
            add("S1", np.array([[s, e]]), None, side)
        add("S2", self.s2_runs, None, "both")
        for b, runs in self.s3_runs:
            add("S3", runs, CORE[b], "bid" if CORE[b] < 0 else "ask")
        schema = {"symbol": pl.Utf8, "rule": pl.Utf8, "band": pl.Float64, "side": pl.Utf8,
                  "start_ts": pl.Int64, "end_ts": pl.Int64, "n_snap": pl.Int64}
        return pl.DataFrame(out, schema=schema)


# ---------------------------------------------------------------------- window rules

def d2_usable(valid_ts: np.ndarray, start: int, end: int) -> bool:
    """D2 for one part (pre or post) of an event window [start, end), epoch seconds.

    Usable iff >= 90% of the 30-second grid points in the part have a valid snapshot
    within 45 s and no gap between consecutive valid snapshots inside the part exceeds
    300 s.
    """
    v = np.sort(np.asarray(valid_ts, np.int64))
    grid = np.arange(start, end, D2_GRID_S, dtype=np.int64)
    if grid.size == 0:
        return False
    k = np.searchsorted(v, grid)
    left = np.where(k > 0, np.abs(grid - v[np.maximum(k - 1, 0)]), np.iinfo(np.int64).max)
    right = np.where(k < v.size, np.abs(v[np.minimum(k, v.size - 1)] - grid),
                     np.iinfo(np.int64).max)
    cover = (np.minimum(left, right) <= D2_TOL_S).mean() if v.size else 0.0
    inside = v[(v >= start) & (v < end)]
    gap = np.diff(inside).max() if inside.size > 1 else np.inf
    return bool(cover >= D2_MIN_COVER and gap <= D2_MAX_GAP_S)


def d3_dropped_dates(days: pl.DataFrame, col: str = "d1_s") -> pl.DataFrame:
    """D3: dates on which more than 20% of contracts with a file fail D1."""
    g = (days.group_by("date").agg(pl.len().alias("n_contracts"),
                                   (~pl.col(col)).sum().alias("n_fail_d1"))
         .with_columns((pl.col("n_fail_d1") / pl.col("n_contracts")).alias("fail_share"))
         .sort("date"))
    return g.with_columns((pl.col("fail_share") > D3_MAX_FAIL_SHARE).alias("d3_dropped"))


def x6_excluded(symbol_info: dict) -> bool:
    """X6 from one exchangeInfo symbol record."""
    sub = symbol_info.get("underlyingSubType") or []
    return (any(s in X6_SUBTYPES for s in sub)
            or symbol_info.get("underlyingType") in X6_TYPES)


# ---------------------------------------------------------------------------- onsets

ONSET_DECLUSTER_S = 6 * 3600


def onsets(mask: SymbolMask, decluster_s: int = ONSET_DECLUSTER_S) -> pl.DataFrame:
    """Directional corruption onsets for the onset test (PREREGISTRATION_P1.md, test T1).

    Candidates are the first snapshots of S1 runs (side from which inner VWAP is farther
    from the kline close) and of S3 runs (side from the band's sign). Candidates whose
    first snapshot lies inside an S2 whole-book repeat are left out: a whole-book freeze
    starts every band at once and has no side. Per side, a candidate is kept only if no
    other candidate of that side started in the preceding decluster_s seconds.
    """
    s2 = paint(mask.ts.size, mask.s2_runs)
    rows: list[tuple[int, int, str]] = []
    for s, _ in mask.s1_runs:
        side = int(mask.s1_side[s])
        if side != 0 and not s2[s]:
            rows.append((int(mask.ts[s]), side, "S1"))
    for b, runs in mask.s3_runs:
        side = -1 if CORE[b] < 0 else 1
        for s, _ in runs:
            if not s2[s]:
                rows.append((int(mask.ts[s]), side, "S3"))
    rows.sort()
    out = []
    last: dict[int, int] = {}
    for t, side, rule in rows:
        prev = last.get(side)
        last[side] = t
        if prev is not None and t - prev < decluster_s:
            continue
        out.append({"symbol": mask.symbol, "ts": t, "side": "bid" if side < 0 else "ask",
                    "rule": rule})
    return pl.DataFrame(out, schema={"symbol": pl.Utf8, "ts": pl.Int64, "side": pl.Utf8,
                                     "rule": pl.Utf8})
