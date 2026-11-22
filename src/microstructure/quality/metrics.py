"""metrics screen v1.

Implements research/liquidations/metrics_screen_v1.txt. Rule names (M0 to M5)
follow that text. Input is one symbol's daily `metrics` files (5-minute open interest,
long/short ratios, taker buy/sell ratio) and the same days' 1-minute klines.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
import polars as pl

from microstructure.quality.bookdepth import Klines, paint, repeat_runs

COLS = ("create_time", "symbol", "sum_open_interest", "sum_open_interest_value",
        "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio",
        "count_long_short_ratio", "sum_taker_long_short_vol_ratio")
NUM = COLS[2:]
STEP_S = 300
ROWS_PER_DAY = 288
M2_WINDOW = 24  # trailing rows (2 hours) for the median |dOI|
M2_MIN_OBS = 12
M2_MULT = 3.0
M2_REVERSE = 0.90
M2_MIN_REL = 0.01  # jump at least 1% of the previous level
M3_MIN_RUN = 12  # identical rows (1 hour)
M5_MIN_PAIRS = 100
M5_MIN_CORR = 0.80
M5_MIN_MARGIN = 0.30


def parse_metrics_csv(raw: bytes) -> pl.DataFrame:
    """One daily metrics file as a frame with `ts` (epoch s of create_time) and floats.

    Empty numeric cells become null (M0 flags them). Rows are kept in file order.
    """
    first = raw.split(b"\n", 1)[0]
    has_header = first.lower().startswith(b"create_time")
    df = pl.read_csv(io.BytesIO(raw), has_header=has_header, infer_schema_length=0,
                     new_columns=list(COLS))
    return df.select(
        pl.col("create_time").str.strptime(pl.Datetime("ms"), "%Y-%m-%d %H:%M:%S",
                                           strict=False).dt.epoch("s").alias("ts"),
        *[pl.col(c).cast(pl.Float64, strict=False) for c in NUM],
    )


@dataclass
class ScreenedMetrics:
    rows: pl.DataFrame  # one row per unique ts, with flag columns
    n_dup_identical: int
    n_dup_conflict: int


def screen(df: pl.DataFrame) -> ScreenedMetrics:
    """Apply M0 to M3 to one symbol's metrics rows, concatenated over days.

    M0 empty or off-grid: any numeric field null, or ts not a multiple of 300 s.
    M1 duplicate: several rows with one ts. Identical copies are collapsed; if copies
       differ, every copy is dropped and the ts is flagged.
    M2 spike-and-reverse on open interest (base units): row t is flagged if the rows t-1,
       t, t+1 are 300 s apart, |dOI_t| > 3 x median(|dOI|) over the 24 changes ending at
       t-1 (at least 12 present, median > 0), |dOI_t| >= 1% of OI_{t-1}, and the next row returns to within 10% of
       the jump: |OI_{t+1} - OI_{t-1}| <= 0.1 |dOI_t|. The same rule on OI value is
       reported as m2_value.
    M3 ghost rows: zero open interest, or a run of >= 12 consecutive 300 s-spaced rows in
       which all six numeric fields equal the previous row's.
    """
    df = df.filter(pl.col("ts").is_not_null())
    n0 = df.height
    df = df.unique(maintain_order=True)
    n_ident = n0 - df.height
    dup = df.group_by("ts").len().filter(pl.col("len") > 1).get_column("ts")
    n_conf = int(df.filter(pl.col("ts").is_in(dup.implode())).height)
    df = df.filter(~pl.col("ts").is_in(dup.implode())).sort("ts")
    ts = df.get_column("ts").to_numpy().astype(np.int64)
    n = ts.size

    m0 = df.select(pl.any_horizontal([pl.col(c).is_null() for c in NUM])).to_series().to_numpy()
    m0 = m0 | (ts % STEP_S != 0)

    def spike(x: np.ndarray) -> np.ndarray:
        flag = np.zeros(n, bool)
        if n < 3:
            return flag
        d = np.full(n, np.nan)
        step_ok = np.r_[False, np.diff(ts) == STEP_S]
        d[1:] = x[1:] - x[:-1]
        d[~step_ok] = np.nan
        a = np.abs(d)
        # window for row t: changes t-24 .. t-1
        pad = np.r_[np.full(M2_WINDOW, np.nan), a[:-1]]
        win = np.lib.stride_tricks.sliding_window_view(pad, M2_WINDOW)
        enough = np.isfinite(win).sum(axis=1) >= M2_MIN_OBS
        med = np.full(n, np.nan)
        if enough.any():
            med[enough] = np.nanmedian(win[enough], axis=1)
        nxt = np.r_[d[1:], np.nan]
        back = np.abs(d + nxt)  # |x[t+1] - x[t-1]|
        with np.errstate(invalid="ignore"):
            prev = np.r_[np.nan, x[:-1]]
            flag = ((a > M2_MULT * med) & (med > 0) & (a >= M2_MIN_REL * np.abs(prev))
                    & (back <= (1 - M2_REVERSE) * a))
        return flag & np.isfinite(d) & np.isfinite(nxt)

    oi = df.get_column("sum_open_interest").to_numpy().astype(float)
    m2 = spike(oi)
    m2_value = spike(df.get_column("sum_open_interest_value").to_numpy().astype(float))

    vals = df.select(NUM).to_numpy().astype(float)
    same = np.r_[False, (vals[1:] == vals[:-1]).all(axis=1) & (np.diff(ts) == STEP_S)]
    m3 = paint(n, repeat_runs(same, M3_MIN_RUN)) | (oi == 0)

    rows = df.with_columns(pl.Series("m0", m0), pl.Series("m2", m2),
                           pl.Series("m2_value", m2_value), pl.Series("m3", m3))
    return ScreenedMetrics(rows, n_ident, n_conf)


def missing_labels(ts: np.ndarray, day_start: int) -> int:
    """M4: number of the 288 grid labels of one UTC day with no row."""
    grid = day_start + STEP_S * np.arange(ROWS_PER_DAY)
    return int((~np.isin(grid, ts)).sum())


def label_convention(rows: pl.DataFrame, kl: Klines) -> dict:
    """M5: which 5-minute block does a row's taker ratio describe?

    Correlates log(sum_taker_long_short_vol_ratio) with log(taker buy / taker sell volume)
    summed from the 1-minute klines over [ts, ts+300) ('start') and [ts-300, ts) ('end').
    Verdict 'start' or 'end' if that correlation is >= 0.80 and exceeds the other by
    >= 0.30 on >= 100 pairs; otherwise 'undetermined'.
    """
    out = {"corr_start": np.nan, "corr_end": np.nan, "n_pairs": 0, "convention":
           "undetermined"}
    if kl.open_s.size == 0 or rows.height == 0:
        return out
    blk = (kl.open_s // STEP_S) * STEP_S
    ub, inv = np.unique(blk, return_inverse=True)
    cnt = np.bincount(inv)
    buy = np.bincount(inv, weights=kl.taker_buy)
    sell = np.bincount(inv, weights=kl.volume - kl.taker_buy)
    full = cnt == 5
    with np.errstate(divide="ignore", invalid="ignore"):
        lr = np.where(full & (buy > 0) & (sell > 0), np.log(buy / sell), np.nan)
    ts = rows.get_column("ts").to_numpy().astype(np.int64)
    with np.errstate(divide="ignore", invalid="ignore"):
        mr = np.log(rows.get_column("sum_taker_long_short_vol_ratio").to_numpy())

    def corr(shift: int) -> tuple[float, int]:
        k = np.searchsorted(ub, ts + shift)
        ok = k < ub.size
        ok[ok] = ub[k[ok]] == ts[ok] + shift
        x = np.where(ok, lr[np.minimum(k, ub.size - 1)], np.nan)
        good = np.isfinite(x) & np.isfinite(mr)
        if good.sum() < 3:
            return np.nan, int(good.sum())
        return float(np.corrcoef(x[good], mr[good])[0, 1]), int(good.sum())

    cs, ns = corr(0)
    ce, ne = corr(-STEP_S)
    out |= {"corr_start": cs, "corr_end": ce, "n_pairs": min(ns, ne)}
    if min(ns, ne) >= M5_MIN_PAIRS and np.isfinite(cs) and np.isfinite(ce):
        if cs >= M5_MIN_CORR and cs - ce >= M5_MIN_MARGIN:
            out["convention"] = "start"
        elif ce >= M5_MIN_CORR and ce - cs >= M5_MIN_MARGIN:
            out["convention"] = "end"
    return out
