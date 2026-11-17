"""Q11: with top-of-book quotes, can the direction of the next mid-price change be
predicted, and does any of that predictability survive trading costs?

This is the price-side counterpart of Q9 (which predicts trade signs from
trades alone). It is limited to 2023 because Binance publishes `bookTicker`
dumps for 2023 only.

Method
1. Clock. One sample per aggressor trade event. Sample i sees the best bid and
   ask strictly before trade i and the trades before i, nothing later.
2. Label. For h in {10, 50, 200} events, the sign of mid(i+h) - mid(i), where
   mid(i) is the mid strictly before event i: up, down or unchanged. The label
   is a raw point-to-point difference. Smoothed labels (an average of future
   mids against an average of past mids) are partly computable from the inputs
   and are not used.
3. Overlap. Consecutive samples share (h-1)/h of their label window. Models
   are fitted on every `stride`-th event (stride = gcd of the horizons) with
   the tree leaf size scaled by h/stride, and every reported statistic uses
   every h-th event, so test labels do not overlap. A sample is used in a
   block (fit, validation, test) only if its label window ends inside the same
   block, which removes the last h events before every boundary, and a whole
   UTC day is discarded between blocks.
4. Models. Majority class; logistic regression on queue imbalance alone (Gould
   and Bonart 2016); logistic regression on all features; LightGBM on all
   features. Each is a pair of binary models, P(mid moves) and P(up | moves),
   so the same ladder gives the binary up-versus-down scores on the samples
   that moved and a three-way prediction on all samples.
5. Economics. The signed score P(up) - P(down) is turned into a direction and
   a confidence. For the most confident 100%, 50%, 20% and 5% of samples
   (cut-offs fixed on the validation days) I report the mean realized mid move
   in the predicted direction, in basis points, against the cost of acting on
   it as a taker: half the spread at entry, half at exit, and two taker fees.

Stages. `extract_day` reduces one day of quotes and trades to per-event
arrays (cached); `fit_symbol` builds features, fits the models and caches the
test-window predictions; `score_symbol` turns cached predictions into every
reported number, so the fee is a report-time parameter. Formatting lives in
`q11_report`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from microstructure.data.catalog import parquet_path
from microstructure.ml.evaluate import MS_PER_DAY, day_block_ci, log_loss_bits, score
from microstructure.ml.features import FEATURE_NAMES, WARMUP, build_feature_matrix
from microstructure.ml.l1_features import (
    L1_FEATURES,
    cumulative_quote_ofi,
    estimate_tick,
    fill_l1_columns,
)
from microstructure.ml.models import (
    LGB_MAX_ROUNDS,
    LGB_PARAMS,
    LGB_PATIENCE,
    fit_gbm,
    fit_logistic,
    subsample,
)
from microstructure.signals.load import events_with_prior_mid, load_events

HORIZONS = (10, 50, 200)
MODELS = ("majority", "qi_logit", "logit_all", "gbm_all")
LEARNED = MODELS[1:]
TOP_FRACTIONS = (1.0, 0.5, 0.2, 0.05)
FEATURES = FEATURE_NAMES + L1_FEATURES
QI_COL = FEATURES.index("queue_imb")
DEFAULT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")
TAKER_FEE_BPS = 5.0
VALID_DAYS = 2
EMBARGO_DAYS = 1
TRAIN_CAP = 2_000_000
VALID_CAP = 500_000
BASE_LEAF = 500
SPREAD_HIST_MAX = 64
AUC_BINS = 512
N_BOOT = 2000
CACHE_VERSION = 1
# Layout and content of days/<day>.npz. Bump when `extract_day` changes what it
# returns; a day file with another version (or none) is extracted again.
DAY_CACHE_VERSION = 1
_QUOTE_COLS = ("bid_price", "bid_qty", "ask_price", "ask_qty", "ofi_cum")
_BOOK_FIELDS = ("ts", "sign", "qty", "price", "n_prints",
                "bid_p", "bid_q", "ask_p", "ask_q", "ofi_cum")


# --------------------------------------------------------------------------
# Stage 1: one day of quotes and trades -> per-event arrays
# --------------------------------------------------------------------------


def day_range(start: str, end: str) -> list[str]:
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    if d1 < d0:
        raise ValueError(f"window end {end} is before its start {start}")
    return [(d0 + timedelta(days=k)).isoformat() for k in range((d1 - d0).days + 1)]


def missing_days(root: Path, symbol: str, days: list[str]) -> list[str]:
    return [
        d for d in days
        if not (parquet_path(root, symbol, "bookTicker", d).exists()
                and parquet_path(root, symbol, "aggTrades", d).exists())
    ]


def extract_day(root: Path, symbol: str, day: str) -> dict[str, np.ndarray]:
    """Aggressor events of one day with the quote strictly before each.

    Also returns day-level quote statistics: the smallest price increment, a
    time-weighted histogram of the spread in units of that increment, and the
    share of events printing at or through the prior quote on their own side
    (a check that the trade-to-quote join is not misaligned).
    """
    bt = (
        pl.scan_parquet(parquet_path(root, symbol, "bookTicker", day))
        .select("update_id", "ts", "bid_price", "bid_qty", "ask_price", "ask_qty")
        .collect()
    )
    n_raw = bt.height
    bt = bt.filter(
        (pl.col("bid_qty") > 0) & (pl.col("ask_qty") > 0)
        & (pl.col("ask_price") > pl.col("bid_price"))
    )
    if not (bt["ts"].is_sorted() and bt["update_id"].is_sorted()):
        bt = bt.sort("ts", "update_id")
    bp, bq = bt["bid_price"].to_numpy(), bt["bid_qty"].to_numpy()
    ap, aq = bt["ask_price"].to_numpy(), bt["ask_qty"].to_numpy()
    inc = estimate_tick(np.concatenate([np.unique(bp), np.unique(ap)]))
    qts = bt["ts"].dt.epoch("ms").to_numpy()
    width = np.clip(np.round((ap - bp) / inc), 0, SPREAD_HIST_MAX).astype(np.int64)
    hist = np.bincount(width[:-1], weights=np.diff(qts).astype(np.float64),
                       minlength=SPREAD_HIST_MAX + 1)
    bt = bt.drop("update_id").with_columns(
        pl.Series("ofi_cum", cumulative_quote_ofi(bp, bq, ap, aq)),
        ((pl.col("bid_price") + pl.col("ask_price")) / 2).alias("mid"),
    )
    del bp, bq, ap, aq, qts, width

    events = load_events(root, symbol, [day])
    ev, n_dropped = events_with_prior_mid(events, bt, extra_cols=_QUOTE_COLS)
    sign = ev["sign"].to_numpy()
    price = ev["price"].to_numpy()
    bid_p, ask_p = ev["bid_price"].to_numpy(), ev["ask_price"].to_numpy()
    at_quote = np.where(sign > 0, price >= ask_p - inc / 4, price <= bid_p + inc / 4)
    return {
        "ts": ev["ts"].dt.epoch("ms").to_numpy(),
        "sign": sign.astype(np.int8),
        "qty": ev["qty"].to_numpy(),
        "price": price,
        "n_prints": ev["n_prints"].to_numpy().astype(np.int32),
        "bid_p": bid_p,
        "bid_q": ev["bid_qty"].to_numpy(),
        "ask_p": ask_p,
        "ask_q": ev["ask_qty"].to_numpy(),
        "ofi_cum": ev["ofi_cum"].to_numpy(),
        "increment": np.float64(inc),
        "spread_hist_ms": hist,
        "n_quotes": np.int64(bt.height),
        "n_quotes_invalid": np.int64(n_raw - bt.height),
        "n_events_no_quote": np.int64(n_dropped),
        "at_quote_share": np.float64(at_quote.mean()),
    }


def day_cache_path(cache: Path, symbol: str, day: str) -> Path:
    return cache / symbol / "days" / f"{day}.npz"


def day_cache_current(path: Path) -> bool:
    """True if a day extract exists and was written by the current `extract_day`."""
    if not path.exists():
        return False
    with np.load(path) as z:
        return "version" in z.files and int(z["version"]) == DAY_CACHE_VERSION


def cached_day(root: Path, cache: Path, symbol: str, day: str) -> dict[str, np.ndarray]:
    path = day_cache_path(cache, symbol, day)
    if day_cache_current(path):
        with np.load(path) as z:
            return {k: z[k] for k in z.files if k != "version"}
    out = extract_day(root, symbol, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, version=np.int64(DAY_CACHE_VERSION), **out)
    tmp.rename(path)
    return out


@dataclass(frozen=True)
class EventBook:
    """Aggressor events over a contiguous run of days, with their prior quotes."""

    ts: np.ndarray        # int64 epoch ms
    sign: np.ndarray
    qty: np.ndarray
    price: np.ndarray
    n_prints: np.ndarray
    bid_p: np.ndarray
    bid_q: np.ndarray
    ask_p: np.ndarray
    ask_q: np.ndarray
    ofi_cum: np.ndarray

    @property
    def mid(self) -> np.ndarray:
        return 0.5 * (self.bid_p + self.ask_p)


def load_window(root: Path, cache: Path, symbol: str, days: list[str]) -> tuple[EventBook, list]:
    """Concatenate cached days; returns the book and the per-day quote statistics."""
    parts: dict[str, list[np.ndarray]] = {k: [] for k in _BOOK_FIELDS}
    stats = []
    ofi_offset = 0.0
    for day in days:
        d = cached_day(root, cache, symbol, day)
        for k in _BOOK_FIELDS:
            # The per-day running OFI restarts at 0; chain the days so that a
            # difference across midnight is still a sum of quote flow.
            parts[k].append(d[k] + ofi_offset if k == "ofi_cum" else d[k])
        if d["ofi_cum"].size:
            ofi_offset += float(d["ofi_cum"][-1])
        stats.append({
            "day": day,
            "n_events": int(d["ts"].size),
            "n_quotes": int(d["n_quotes"]),
            "n_quotes_invalid": int(d["n_quotes_invalid"]),
            "n_events_no_quote": int(d["n_events_no_quote"]),
            "at_quote_share": float(d["at_quote_share"]),
            "increment": float(d["increment"]),
            "spread_hist_ms": d["spread_hist_ms"].tolist(),
        })
    return EventBook(**{k: np.concatenate(v) for k, v in parts.items()}), stats


def spread_profile(day_stats: list[dict], tick: float) -> dict:
    """Time-weighted spread statistics in ticks, pooled over days."""
    total = np.zeros(SPREAD_HIST_MAX + 1)
    for s in day_stats:
        # A day whose smallest observed increment is a multiple of the tick
        # has its histogram in coarser units; map it onto the tick grid.
        factor = max(1, round(s["increment"] / tick))
        idx = np.minimum(np.arange(SPREAD_HIST_MAX + 1) * factor, SPREAD_HIST_MAX)
        np.add.at(total, idx, np.asarray(s["spread_hist_ms"]))
    w = total / total.sum()
    return {
        "one_tick_time_share": float(w[:2].sum()),
        "mean_spread_ticks": float((w * np.arange(w.size)).sum()),
    }


# --------------------------------------------------------------------------
# Labels and sampling
# --------------------------------------------------------------------------


def direction_labels(
    mid: np.ndarray, rows: np.ndarray, h: int, tol: float
) -> tuple[np.ndarray, np.ndarray]:
    """(label, has_label) for the given event rows at horizon h.

    label = sign(mid[i+h] - mid[i]) in {-1, 0, +1}, with |difference| <= tol
    counted as unchanged (tol absorbs float noise; a real move is at least
    half a tick). Rows with i + h past the end of the data have no label.
    """
    has = rows + h < mid.size
    label = np.zeros(rows.size, dtype=np.int8)
    diff = mid[rows[has] + h] - mid[rows[has]]
    label[has] = np.where(diff > tol, 1, np.where(diff < -tol, -1, 0))
    return label, has


def inside_block(t0: np.ndarray, t1: np.ndarray, start_ms: int, end_ms: int) -> np.ndarray:
    """True where the whole label window [t0, t1] lies in [start_ms, end_ms).

    This is the purge: a sample whose label closes after its block ends is
    dropped, which in event time is exactly the last h events of the block.
    """
    return (t0 >= start_ms) & (t1 < end_ms)


@dataclass(frozen=True)
class Samples:
    """Feature rows on the sampling grid, with labels and outcomes per horizon."""

    rows: np.ndarray                 # event index of each sample
    ts: np.ndarray                   # decision time t0 (ms)
    X: np.ndarray                    # float32 [n, len(FEATURES)]
    tied: np.ndarray                 # shares a millisecond with the previous event
    label: dict[int, np.ndarray]     # h -> {-1, 0, +1}
    has_label: dict[int, np.ndarray]
    end_ts: dict[int, np.ndarray]    # h -> t1, the time of event i+h
    move_bps: dict[int, np.ndarray]  # h -> (mid[i+h] - mid[i]) / mid[i] * 1e4
    spread_bps: dict[int, np.ndarray]  # h -> half spread at i + half spread at i+h, bps


def build_samples(
    book: EventBook, tick: float, horizons: tuple[int, ...], stride: int
) -> Samples:
    n = book.ts.size
    rows = np.arange(WARMUP, n, stride)
    if rows.size == 0:
        raise ValueError(f"window has {n} events, fewer than the {WARMUP}-event warm-up")
    X = np.empty((rows.size, len(FEATURES)), dtype=np.float32)
    trade = build_feature_matrix(book.ts, book.sign, book.qty, book.price, book.n_prints)
    X[:, : len(FEATURE_NAMES)] = trade[rows]
    del trade
    fill_l1_columns(X, rows, len(FEATURE_NAMES), book.bid_p, book.bid_q, book.ask_p,
                    book.ask_q, book.ofi_cum, tick)
    if not np.isfinite(X).all():
        raise RuntimeError("non-finite feature values after warm-up")

    mid = book.mid
    half_spread = 0.5 * (book.ask_p - book.bid_p)
    label, has_label, end_ts, move_bps, spread_bps = {}, {}, {}, {}, {}
    for h in horizons:
        label[h], has = direction_labels(mid, rows, h, tol=tick / 4)
        end = np.minimum(rows + h, n - 1)
        has_label[h] = has
        end_ts[h] = book.ts[end]
        move_bps[h] = np.where(has, (mid[end] - mid[rows]) / mid[rows] * 1e4, 0.0)
        spread_bps[h] = (half_spread[rows] + half_spread[end]) / mid[rows] * 1e4
    return Samples(
        rows=rows, ts=book.ts[rows], X=X,
        # Same-millisecond events are ordered by sign, not by arrival, so a
        # row whose predecessor shares its timestamp is never fitted or scored.
        tied=book.ts[rows] == book.ts[rows - 1],
        label=label, has_label=has_label, end_ts=end_ts, move_bps=move_bps,
        spread_bps=spread_bps,
    )


def usable(s: Samples, h: int, start_ms: int, end_ms: int, every: int = 1) -> np.ndarray:
    """Indices of samples usable in the block [start_ms, end_ms) at horizon h.

    `every` keeps one grid point in `every`; with every * stride = h the kept
    samples have non-overlapping label windows.
    """
    keep = s.has_label[h] & ~s.tied & inside_block(s.ts, s.end_ts[h], start_ms, end_ms)
    keep &= (np.arange(s.rows.size) % every) == 0
    return np.flatnonzero(keep)


# --------------------------------------------------------------------------
# Stage 2: fit the ladder, cache test predictions
# --------------------------------------------------------------------------


def _fit_stage(
    X: np.ndarray, y: np.ndarray, Xv: np.ndarray, yv: np.ndarray, leaf: int,
    max_rounds: int | None, threads: int | None = None,
) -> tuple[dict, dict]:
    """The four models for one binary target; returns predictors and fit notes.

    If either the fit or the validation rows hold a single class there is
    nothing to learn (and nothing to stop early on), so every model falls back
    to the training frequency.
    """
    base = float(y.mean()) if y.size else 0.5
    const = {name: (lambda Z, b=base: np.full(Z.shape[0], b)) for name in MODELS}
    if y.size == 0 or yv.size == 0 or not (0 < base < 1) or not (0 < yv.mean() < 1):
        return const, {"degenerate": True, "base_rate": base}
    qi = fit_logistic(X[:, [QI_COL]], y)
    logit = fit_logistic(X, y)
    kw = {} if max_rounds is None else {"max_rounds": max_rounds}
    params = {"min_data_in_leaf": leaf}
    if threads is not None:
        # LightGBM threads spin while waiting; on a machine shared with other
        # jobs, fewer threads than cores is far faster than the default.
        params["num_threads"] = threads
    gbm = fit_gbm(X, y, Xv, yv, params=params, **kw)
    gain = gbm.gain_importance()
    top = np.argsort(gain)[::-1][:8]
    return (
        {
            "majority": const["majority"],
            "qi_logit": lambda Z: qi.predict(Z[:, [QI_COL]]),
            "logit_all": logit.predict,
            "gbm_all": gbm.predict,
        },
        {
            "degenerate": False, "base_rate": base,
            "qi_coef_per_sd": float(qi.coef[0]),
            "gbm_rounds": gbm.best_iteration, "gbm_min_data_in_leaf": leaf,
            "gbm_top_gain": {FEATURES[i]: float(gain[i]) for i in top},
        },
    )


def signed_score(p_move: np.ndarray, p_up: np.ndarray) -> np.ndarray:
    """P(up) - P(down) for a sample whose mid may also stay put."""
    return p_move * (2.0 * p_up - 1.0)


def fit_horizon(
    fit: Samples, fit_block: tuple[int, int], valid_block: tuple[int, int],
    test: Samples, test_block: tuple[int, int], h: int, stride: int,
    max_rounds: int | None = None, train_cap: int = TRAIN_CAP, threads: int | None = None,
) -> tuple[dict[str, np.ndarray], dict]:
    """Fit both stages at horizon h; return test predictions and fit metadata."""
    if h % stride:
        raise ValueError(f"horizon {h} is not a multiple of the sampling stride {stride}")
    overlap = h // stride
    tr = subsample(usable(fit, h, *fit_block), train_cap, seed=0)
    va = subsample(usable(fit, h, *valid_block), VALID_CAP, seed=1)
    te = usable(test, h, *test_block, every=overlap)
    if min(tr.size, va.size, te.size) == 0:
        raise ValueError(
            f"h={h}: empty block (fit {tr.size}, validation {va.size}, test {te.size} samples); "
            f"each window must hold more than the {WARMUP}-event warm-up"
        )
    # A leaf must hold BASE_LEAF labels' worth of independent information;
    # fitted rows overlap by a factor h/stride, so the floor scales with it.
    leaf = int(max(20, min(BASE_LEAF * overlap, tr.size // 50)))

    moved_tr, moved_va = fit.label[h][tr] != 0, fit.label[h][va] != 0
    move_models, move_info = _fit_stage(
        fit.X[tr], moved_tr.astype(np.float32), fit.X[va], moved_va.astype(np.float32),
        leaf, max_rounds, threads,
    )
    dtr, dva = tr[moved_tr], va[moved_va]
    up_models, up_info = _fit_stage(
        fit.X[dtr], (fit.label[h][dtr] > 0).astype(np.float32),
        fit.X[dva], (fit.label[h][dva] > 0).astype(np.float32), leaf, max_rounds, threads,
    )

    pred = {
        "ts": test.ts[te], "label": test.label[h][te],
        "move_bps": test.move_bps[h][te].astype(np.float32),
        "spread_bps": test.spread_bps[h][te].astype(np.float32),
    }
    thresholds = {}
    for m in MODELS:
        pred[f"{m}_move"] = move_models[m](test.X[te]).astype(np.float32)
        pred[f"{m}_up"] = up_models[m](test.X[te]).astype(np.float32)
        if m in LEARNED:
            # Confidence cut-offs come from the validation days, so the test
            # window plays no part in deciding which samples count as confident.
            conf = np.abs(signed_score(move_models[m](fit.X[va]), up_models[m](fit.X[va])))
            thresholds[m] = {
                f"{q:g}": float(np.quantile(conf, 1.0 - q)) if conf.size and q < 1 else 0.0
                for q in TOP_FRACTIONS
            }
    meta = {
        "n_fit": int(tr.size), "n_valid": int(va.size), "n_test": int(te.size),
        "n_fit_moved": int(dtr.size), "move_stage": move_info, "direction_stage": up_info,
        "thresholds": thresholds,
    }
    return pred, meta


def _block(days: list[str]) -> tuple[int, int]:
    d0 = date.fromisoformat(days[0]).toordinal() - date(1970, 1, 1).toordinal()
    return d0 * MS_PER_DAY, (d0 + len(days)) * MS_PER_DAY


def split_train_days(
    days: list[str], valid_days: int, embargo_days: int
) -> tuple[list[str], list[str]]:
    n_fit = len(days) - valid_days - embargo_days
    if n_fit < 1 or valid_days < 1:
        raise ValueError(
            f"train window of {len(days)} days cannot hold {valid_days} validation "
            f"and {embargo_days} embargo days"
        )
    return days[:n_fit], days[n_fit + embargo_days:]


def fit_settings() -> dict:
    """The code-level settings that shape cached predictions, besides the run config.

    The LightGBM thread count is left out on purpose: it is a property of the
    machine, a later report must find the predictions whatever `--threads` it
    is given, and the count actually used is recorded in the meta instead.
    """
    return {
        "train_cap": TRAIN_CAP, "valid_cap": VALID_CAP, "base_leaf": BASE_LEAF,
        "warmup_events": WARMUP,
        "lgb_params": {k: v for k, v in LGB_PARAMS.items() if k != "num_threads"},
        "lgb_max_rounds": LGB_MAX_ROUNDS, "lgb_patience": LGB_PATIENCE,
        "features": list(FEATURES), "models": list(MODELS),
        "top_fractions": list(TOP_FRACTIONS), "day_cache_version": DAY_CACHE_VERSION,
    }


def config_key(cfg: dict) -> str:
    """Key of the cached predictions: the run config and every fit setting.

    The fee is not part of either, so it stays a report-time parameter.
    """
    blob = json.dumps({**cfg, "version": CACHE_VERSION, "fit_settings": fit_settings()},
                      sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def fit_symbol(root: Path, cache: Path, symbol: str, cfg: dict,
               threads: int | None = None) -> dict:
    """Run stages 1 and 2 for one symbol; writes pred_<key>.npz and meta_<key>.json."""
    horizons = tuple(cfg["horizons"])
    stride = math.gcd(*horizons)
    train_days = day_range(cfg["train_start"], cfg["train_end"])
    test_days = day_range(cfg["test_start"], cfg["test_end"])
    fit_days, valid_days = split_train_days(train_days, cfg["valid_days"], cfg["embargo_days"])

    book, train_stats = load_window(root, cache, symbol, train_days)
    # The tick is a fitted constant: it comes from the training window only.
    tick = min(s["increment"] for s in train_stats)
    train = build_samples(book, tick, horizons, stride)
    n_train_events = int(book.ts.size)
    del book
    book, test_stats = load_window(root, cache, symbol, test_days)
    test = build_samples(book, tick, horizons, stride)
    n_test_events = int(book.ts.size)
    del book

    arrays: dict[str, np.ndarray] = {}
    per_h = {}
    for h in horizons:
        pred, per_h[str(h)] = fit_horizon(
            train, _block(fit_days), _block(valid_days), test, _block(test_days),
            h, stride, max_rounds=cfg.get("max_rounds"), threads=threads,
        )
        arrays.update({f"h{h}_{k}": v for k, v in pred.items()})
    one_tick_col = FEATURES.index("one_tick")
    meta = {
        "symbol": symbol, "config": cfg, "fit_settings": fit_settings(),
        "lgb_threads": LGB_PARAMS["num_threads"] if threads is None else threads,
        "tick": tick, "stride": stride,
        "fit_days": fit_days, "valid_days": valid_days, "test_days": test_days,
        "n_train_events": n_train_events, "n_test_events": n_test_events,
        "spread": {
            **spread_profile(train_stats + test_stats, tick),
            "one_tick_event_share": float(test.X[:, one_tick_col].mean()),
        },
        "at_quote_share": float(np.mean([s["at_quote_share"] for s in train_stats + test_stats])),
        "n_events_no_quote": int(sum(s["n_events_no_quote"] for s in train_stats + test_stats)),
        "horizons": per_h,
    }
    key = config_key(cfg)
    out = cache / symbol
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / f"pred_{key}.npz", **arrays)
    (out / f"meta_{key}.json").write_text(json.dumps(meta, indent=2))
    return meta


def load_cached(cache: Path, symbol: str, cfg: dict) -> tuple[dict, dict] | None:
    key = config_key(cfg)
    meta_path = cache / symbol / f"meta_{key}.json"
    pred_path = cache / symbol / f"pred_{key}.npz"
    if not (meta_path.exists() and pred_path.exists()):
        return None
    with np.load(pred_path) as z:
        arrays = {k: z[k] for k in z.files}
    return json.loads(meta_path.read_text()), arrays


# --------------------------------------------------------------------------
# Stage 3: predictions -> reported numbers
# --------------------------------------------------------------------------


def auc_from_hist(pos: np.ndarray, neg: np.ndarray) -> np.ndarray:
    """AUC from score histograms over shared bins (last axis); ties within a bin count 1/2."""
    below = np.cumsum(neg, axis=-1) - neg
    num = (pos * (below + 0.5 * neg)).sum(axis=-1)
    den = pos.sum(axis=-1) * neg.sum(axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / den, np.nan)


def mcc_from_confusion(c: np.ndarray) -> np.ndarray:
    """Matthews correlation for K classes (Gorodkin's R_K) from [..., K, K] counts.

    Rows are true classes, columns predicted. For K = 2 this is the usual MCC.
    A classifier that always predicts one class scores 0.
    """
    s = c.sum(axis=(-2, -1))
    correct = np.trace(c, axis1=-2, axis2=-1)
    t, p = c.sum(axis=-1), c.sum(axis=-2)
    num = correct * s - (t * p).sum(axis=-1)
    den = np.sqrt((s * s - (p * p).sum(axis=-1)) * (s * s - (t * t).sum(axis=-1)))
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / den, 0.0)


def day_bootstrap_sums(day_stats: np.ndarray, n_boot: int, seed: int) -> np.ndarray:
    """Sums of per-day statistics [k, m] over n_boot resamples of whole days -> [n_boot, m]."""
    k = day_stats.shape[0]
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, k, size=(n_boot, k))
    weights = np.zeros((n_boot, k))
    np.add.at(weights, (np.arange(n_boot)[:, None], pick), 1.0)
    return weights @ day_stats


def _ci(estimate: float, boot: np.ndarray, n_days: int) -> dict:
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])
    return {"estimate": float(estimate), "ci95": [float(lo), float(hi)], "n_days": n_days}


def _per_day(inv: np.ndarray, k: int, code: np.ndarray, n_codes: int) -> np.ndarray:
    """Counts of each code per day -> [k, n_codes]."""
    return np.bincount(inv * n_codes + code, minlength=k * n_codes).reshape(k, n_codes)


def _score_bins(p: np.ndarray) -> np.ndarray:
    edges = np.unique(np.quantile(p, np.linspace(0, 1, AUC_BINS + 1)[1:-1]))
    return np.searchsorted(edges, p, side="right")


def three_class_prediction(p_move: np.ndarray, p_up: np.ndarray) -> np.ndarray:
    """argmax over (down, unchanged, up), coded 0, 1, 2."""
    probs = np.stack([p_move * (1 - p_up), 1 - p_move, p_move * p_up], axis=1)
    return np.argmax(probs, axis=1)


def _paired_diffs(
    p: dict[str, np.ndarray], a: str, b: str, n_boot: int, seed: int
) -> dict:
    """Day-block CIs for model a minus model b on every headline metric."""
    label, ts = p["label"], p["ts"]
    moved = label != 0
    y = (label[moved] > 0).astype(np.float64)
    tsm = ts[moved]
    pa, pb = p[f"{a}_up"][moved].astype(np.float64), p[f"{b}_up"][moved].astype(np.float64)
    out = {
        "accuracy": day_block_ci(
            ((pa >= 0.5) == (y > 0.5)).astype(float), ((pb >= 0.5) == (y > 0.5)).astype(float),
            tsm, n_boot=n_boot, seed=seed).as_dict(),
        "log_loss_bits": day_block_ci(
            log_loss_bits(y, pa), log_loss_bits(y, pb), tsm, n_boot=n_boot, seed=seed).as_dict(),
    }
    _, inv = np.unique(tsm // MS_PER_DAY, return_inverse=True)
    k = int(inv.max()) + 1
    yi = y.astype(np.int64)

    def binary_stats(q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        bins = _score_bins(q)
        hist = _per_day(inv, k, yi * AUC_BINS + bins, 2 * AUC_BINS)
        conf = _per_day(inv, k, yi * 2 + (q >= 0.5), 4)
        return hist, conf

    (ha, ca), (hb, cb) = binary_stats(pa), binary_stats(pb)
    stats = np.concatenate([ha, hb, ca, cb], axis=1).astype(np.float64)

    def auc_and_mcc(sums: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # Layout: for each model a histogram [negatives | positives], then
        # the two 2x2 confusion tables.
        nb = AUC_BINS
        auc_a = auc_from_hist(sums[..., nb:2 * nb], sums[..., :nb])
        auc_b = auc_from_hist(sums[..., 3 * nb:4 * nb], sums[..., 2 * nb:3 * nb])
        ca_ = sums[..., 4 * nb:4 * nb + 4].reshape(*sums.shape[:-1], 2, 2)
        cb_ = sums[..., 4 * nb + 4:].reshape(*sums.shape[:-1], 2, 2)
        return auc_a - auc_b, mcc_from_confusion(ca_) - mcc_from_confusion(cb_)

    est_auc, est_mcc = auc_and_mcc(stats.sum(axis=0))
    boot_auc, boot_mcc = auc_and_mcc(day_bootstrap_sums(stats, n_boot, seed))
    out["auc"] = _ci(float(est_auc), boot_auc, k)
    out["mcc"] = _ci(float(est_mcc), boot_mcc, k)

    _, inv3 = np.unique(ts // MS_PER_DAY, return_inverse=True)
    k3 = int(inv3.max()) + 1
    true3 = (label + 1).astype(np.int64)
    c3 = np.concatenate([
        _per_day(inv3, k3, true3 * 3 + three_class_prediction(p[f"{m}_move"], p[f"{m}_up"]), 9)
        for m in (a, b)
    ], axis=1).astype(np.float64)

    def mcc3_diff(sums: np.ndarray) -> np.ndarray:
        lead = sums.shape[:-1]
        return (mcc_from_confusion(sums[..., :9].reshape(*lead, 3, 3))
                - mcc_from_confusion(sums[..., 9:].reshape(*lead, 3, 3)))

    out["mcc_three_class"] = _ci(
        float(mcc3_diff(c3.sum(axis=0))), mcc3_diff(day_bootstrap_sums(c3, n_boot, seed)), k3)
    return out


def _economics(
    p: dict[str, np.ndarray], model: str, thresholds: dict[str, float], fee_bps: float,
    n_boot: int, seed: int,
) -> list[dict]:
    """Gross edge against round-trip taker cost at each confidence cut-off.

    Every sample counts, including those whose mid did not move: a trader
    cannot know in advance that the mid will move.
    """
    s = signed_score(p[f"{model}_move"].astype(np.float64), p[f"{model}_up"].astype(np.float64))
    move = p["move_bps"].astype(np.float64)
    spread = p["spread_bps"].astype(np.float64)
    rows = []
    for q in TOP_FRACTIONS:
        fired = (np.abs(s) >= thresholds[f"{q:g}"]) & (s != 0)
        row: dict = {"top_fraction": q, "n": int(fired.sum()),
                     "share_of_test": float(fired.mean()) if fired.size else 0.0}
        if fired.any():
            gross = np.sign(s[fired]) * move[fired]
            ts = p["ts"][fired]
            g = day_block_ci(gross, None, ts, n_boot=n_boot, seed=seed)
            after_spread = day_block_ci(gross, spread[fired], ts, n_boot=n_boot, seed=seed)
            cost = float(spread[fired].mean()) + 2.0 * fee_bps
            row.update({
                "gross_bps": g.estimate, "gross_ci95": [g.lo, g.hi],
                "spread_cost_bps": float(spread[fired].mean()),
                "fee_cost_bps": 2.0 * fee_bps, "cost_bps": cost,
                "gross_over_cost": g.estimate / cost,
                "net_bps": after_spread.estimate - 2.0 * fee_bps,
                "net_ci95": [after_spread.lo - 2.0 * fee_bps, after_spread.hi - 2.0 * fee_bps],
                "hit_rate": float((gross > 0).mean()),
                "unchanged_share": float((move[fired] == 0).mean()),
                "exceeds_cost": bool(g.estimate > cost),
            })
        rows.append(row)
    return rows


def score_horizon(
    p: dict[str, np.ndarray], thresholds: dict[str, dict[str, float]], fee_bps: float,
    n_boot: int = N_BOOT, seed: int = 0,
) -> dict:
    """Every reported number for one symbol and horizon, from cached predictions."""
    label = p["label"]
    moved = label != 0
    y = (label[moved] > 0).astype(np.float64)
    true3 = (label + 1).astype(np.int64)
    abs_move = np.abs(p["move_bps"].astype(np.float64))
    spread = p["spread_bps"].astype(np.float64)
    out: dict = {
        "n_test": int(label.size),
        "n_test_days": int(np.unique(p["ts"] // MS_PER_DAY).size),
        "share_up": float((label > 0).mean()),
        "share_down": float((label < 0).mean()),
        "share_unchanged": float((label == 0).mean()),
        # What a taker with perfect foresight of the direction would gross,
        # and how often the move is even large enough to cover the cost.
        "mean_abs_move_bps": float(abs_move.mean()),
        "mean_spread_cost_bps": float(spread.mean()),
        "share_move_exceeds_cost": float((abs_move > spread + 2.0 * fee_bps).mean()),
        "binary": {}, "three_class": {}, "economics": {},
    }
    for m in MODELS:
        out["binary"][m] = score(y, p[f"{m}_up"][moved].astype(np.float64)).as_dict()
        pred3 = three_class_prediction(p[f"{m}_move"], p[f"{m}_up"])
        conf = np.bincount(true3 * 3 + pred3, minlength=9).reshape(3, 3).astype(np.float64)
        out["three_class"][m] = {
            "accuracy": float((pred3 == true3).mean()),
            "mcc": float(mcc_from_confusion(conf)),
            "predicted_unchanged_share": float((pred3 == 1).mean()),
        }
    out["gbm_minus_qi"] = _paired_diffs(p, "gbm_all", "qi_logit", n_boot, seed)
    for m in LEARNED:
        out["economics"][m] = _economics(p, m, thresholds[m], fee_bps, n_boot, seed)
    return out


def score_symbol(meta: dict, arrays: dict[str, np.ndarray], fee_bps: float,
                 n_boot: int = N_BOOT) -> dict:
    horizons = {}
    for h, info in meta["horizons"].items():
        prefix = f"h{h}_"
        p = {k[len(prefix):]: v for k, v in arrays.items() if k.startswith(prefix)}
        horizons[h] = {**score_horizon(p, info["thresholds"], fee_bps, n_boot), "fit": info}
    return {
        "symbol": meta["symbol"], "tick": meta["tick"], "spread": meta["spread"],
        "at_quote_share": meta["at_quote_share"],
        "n_events_no_quote": meta["n_events_no_quote"],
        "n_train_events": meta["n_train_events"], "n_test_events": meta["n_test_events"],
        "fit_days": meta["fit_days"], "valid_days": meta["valid_days"],
        "test_days": meta["test_days"], "horizons": horizons,
        "fit_settings": meta["fit_settings"], "lgb_threads": meta["lgb_threads"],
    }


def edge_verdict(symbols: list[dict]) -> dict:
    """Does the gross edge exceed the taker cost in any cell, and how close does it get?

    A cell is (symbol, horizon, model, confidence cut-off). `exceeds` lists the
    cells whose point estimate of gross edge is above cost; `significant`
    keeps those whose net-of-cost day-block interval also excludes zero.
    """
    cells = []
    for s in symbols:
        for h, res in s["horizons"].items():
            for m, rows in res["economics"].items():
                for r in rows:
                    if r["n"] > 0:
                        cells.append({"symbol": s["symbol"], "horizon": int(h), "model": m, **r})
    exceeds = [c for c in cells if c["exceeds_cost"]]
    best = max(cells, key=lambda c: c["gross_over_cost"]) if cells else None
    return {
        "n_cells": len(cells),
        "any_exceeds_cost": bool(exceeds),
        "exceeds": exceeds,
        "significant": [c for c in exceeds if c["net_ci95"][0] > 0],
        "best": best,
    }


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def check_windows(cfg: dict) -> None:
    gap = (date.fromisoformat(cfg["test_start"]) - date.fromisoformat(cfg["train_end"])).days - 1
    if gap < cfg["embargo_days"]:
        raise ValueError(
            f"test window starts {gap} whole day(s) after the train window ends; "
            f"need at least {cfg['embargo_days']}"
        )
    for h in cfg["horizons"]:
        if h < 1:
            raise ValueError("horizons must be positive")


def run_q11(root: Path, out: Path, symbols: list[str], cfg: dict, fee_bps: float,
            cache: Path | None = None, report_only: bool = False,
            n_boot: int = N_BOOT, threads: int | None = None) -> dict:
    from microstructure.analyses.q11_report import write_outputs

    check_windows(cfg)
    cache = cache or root / "ml_cache" / "q11"
    days = day_range(cfg["train_start"], cfg["train_end"]) + day_range(
        cfg["test_start"], cfg["test_end"])
    results, skipped = [], []
    for symbol in symbols:
        cached = load_cached(cache, symbol, cfg)
        if cached is None:
            gone = missing_days(root, symbol, days)
            have_days = all(day_cache_current(day_cache_path(cache, symbol, d)) for d in days)
            if report_only:
                skipped.append({"symbol": symbol, "reason": "no cached predictions (report-only)"})
                continue
            if gone and not have_days:
                skipped.append({
                    "symbol": symbol,
                    "reason": f"{len(gone)} of {len(days)} days missing on disk "
                              f"(first: {gone[0]}, last: {gone[-1]})",
                })
                continue
            print(f"[q11] fitting {symbol}", flush=True)
            try:
                fit_symbol(root, cache, symbol, cfg, threads=threads)
            except ValueError as e:
                skipped.append({"symbol": symbol, "reason": f"could not be fitted: {e}"})
                continue
            cached = load_cached(cache, symbol, cfg)
        results.append(score_symbol(*cached, fee_bps=fee_bps, n_boot=n_boot))
    # The feature list the cached predictions were fitted with (it is part of the
    # cache key, so every symbol loaded here shares it), not merely today's code.
    features = results[0]["fit_settings"]["features"] if results else list(FEATURES)
    summary = {
        "config": {**cfg, "taker_fee_bps": fee_bps, "features": features,
                   "models": list(MODELS), "top_fractions": list(TOP_FRACTIONS),
                   "n_boot": n_boot},
        "symbols": results,
        "skipped": skipped,
        "verdict": edge_verdict(results),
    }
    write_outputs(summary, out)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--cache", type=Path, default=None,
                    help="cache directory (default: <root>/ml_cache/q11)")
    ap.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    ap.add_argument("--train-start", default="2023-06-05")
    ap.add_argument("--train-end", default="2023-06-18")
    ap.add_argument("--test-start", default="2023-07-03")
    ap.add_argument("--test-end", default="2023-07-16")
    ap.add_argument("--valid-days", type=int, default=VALID_DAYS,
                    help="last days of the train window, used for early stopping and cut-offs")
    ap.add_argument("--embargo-days", type=int, default=EMBARGO_DAYS)
    ap.add_argument("--horizons", type=int, nargs="+", default=list(HORIZONS))
    ap.add_argument("--fee-bps", type=float, default=TAKER_FEE_BPS,
                    help="taker fee per side in basis points")
    ap.add_argument("--max-rounds", type=int, default=None,
                    help="cap on boosting rounds (default: the ml.models default)")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--threads", type=int, default=None,
                    help="LightGBM threads (default: the ml.models default of 4)")
    ap.add_argument("--report-only", action="store_true",
                    help="rebuild the outputs from cached predictions without fitting")
    a = ap.parse_args()
    cfg = {
        "train_start": a.train_start, "train_end": a.train_end,
        "test_start": a.test_start, "test_end": a.test_end,
        "valid_days": a.valid_days, "embargo_days": a.embargo_days,
        "horizons": sorted(a.horizons),
    }
    if a.max_rounds is not None:
        cfg["max_rounds"] = a.max_rounds
    summary = run_q11(a.root, a.out, a.symbols, cfg, a.fee_bps, cache=a.cache,
                      report_only=a.report_only, n_boot=a.n_boot, threads=a.threads)
    v = summary["verdict"]
    print(f"[q11] {len(summary['symbols'])} symbol(s) scored, {len(summary['skipped'])} skipped; "
          f"gross edge exceeds cost in {len(v['exceeds'])} of {v['n_cells']} cells")


if __name__ == "__main__":
    main()
