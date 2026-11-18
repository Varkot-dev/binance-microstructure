"""Part B, weeks 8 to 9: the delisting panel (person-period) and baseline benchmarks.

Two stages, both run from the repository root:

    PYTHONPATH=src .venv/bin/python research/market_evolution/b0_baselines.py build
    PYTHONPATH=src .venv/bin/python research/market_evolution/b0_baselines.py eval

(no argument runs both). Only local files are read: no network.

build
    One row per contract LIFE per month (person-period), from
    `data/contract_lifecycle.csv` (lives, dates, status) and `data/monthly_panel.parquet`
    (month features), plus the per-contract daily klines under `data/raw_panel/` for the
    per-life drawdown and the weekend screen. Writes `data/delisting_panel.parquet` and
    `data/delisting_panel.md`.

eval
    Expanding-window evaluation with monthly origins, 6-month test blocks and a purge, on
    origins before the lock-box (2026-01 on, reserved and NOT scored). Baselines: (a)
    falling volume, (b) lowest volume rank, (c) logistic regression on three features.
    Writes `data/b0_baselines.md`.

Label (horizon H = 3): y3 = 1 if the life's last trading month L is in t+1..t+3. A life is
an event if it ends in a delisting (lifecycle status `delisted`, or `reused-symbol` for a
first life that stopped and whose ticker only came back after more than 30 days). Renamed
and merged lives are censored at L; alive lives are censored at the last complete month.
Index and non-crypto (stock, ETF, commodity, FX, pre-IPO) contracts are excluded.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "research" / "market_evolution"
DATA = HERE / "data"
LIFECYCLE_CSV = DATA / "contract_lifecycle.csv"
MONTHLY_PANEL = DATA / "monthly_panel.parquet"
RAW_CONTRACTS = ROOT / "data" / "raw_panel" / "contracts"
Q14_JSON = ROOT / "results" / "q14_survivorship.json"
PANEL_OUT = DATA / "delisting_panel.parquet"
PANEL_MD = DATA / "delisting_panel.md"
BASELINE_MD = DATA / "b0_baselines.md"
BASELINE_JSON = DATA / "b0_baselines.json"

H = 3                      # label horizon in months
OBS_END = "2026-10"        # last complete month (archive ends 2026-11-16)
LOCKBOX_START = "2026-01"  # origins from here on are the lock-box: reserved, not scored
FIRST_TEST = "2023-01"     # first test block of the expanding window
TEST_LEN = 6               # months per test block
ALERT_RATE = 0.05          # flag the top 5% of live contracts each month
N_BOOT = 2000
BOOT_BLOCK = 3             # months per bootstrap block (labels of neighbouring months overlap)
SEED = 0
LOGIT_FEATURES = ("dlog_qv_3m", "qv_rank_pct", "log_age")
THRESHOLD_QUANTILES = np.round(np.arange(0.005, 0.5001, 0.005), 3)

# Non-crypto screen. Lives first trading on or after this day are flagged when the median
# weekend-day quote volume is below WEEKEND_RATIO_MAX of the median weekday (a crypto
# contract sits near 0.6 to 1.1), or when they have fewer than WEEKEND_MIN_DAYS trading
# days. Every flagged life was reviewed by name; these five are crypto and kept.
NONCRYPTO_SCREEN_FROM = "2025-12-01"
WEEKEND_RATIO_MAX = 0.60
WEEKEND_MIN_DAYS = 14
CRYPTO_KEEP = {("CFGUSDT", 1), ("MOONSHOTUSDT", 1), ("GRVTUSDT", 1), ("PREDICTUSDT", 1),
               ("LITUSDT", 2)}

EVENT_STATUSES = {"delisted", "reused-symbol"}
CENSORED_STATUSES = {"alive", "renamed", "merged"}
EXCLUDED_STATUSES = {"index"}


# --------------------------------------------------------------------------------------
# Month arithmetic: a month is an integer index year * 12 + (month - 1)
# --------------------------------------------------------------------------------------

def midx(month: str) -> int:
    return int(month[:4]) * 12 + int(month[5:7]) - 1


def mstr(i: int) -> str:
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def date_midx(col: str) -> pl.Expr:
    c = pl.col(col)
    return (c.dt.year().cast(pl.Int32) * 12 + c.dt.month().cast(pl.Int32) - 1)


# --------------------------------------------------------------------------------------
# Lives and labels (pure functions, tested in tests/research/test_delisting_panel.py)
# --------------------------------------------------------------------------------------

def life_outcome(status: str) -> str:
    """'event', 'censored' or 'excluded' for a lifecycle status."""
    if status in EVENT_STATUSES:
        return "event"
    if status in CENSORED_STATUSES:
        return "censored"
    if status in EXCLUDED_STATUSES:
        return "excluded"
    raise ValueError(f"unknown status {status!r}")


def assign_labels(rows: pl.DataFrame, horizon: int = H, obs_end: int | None = None
                  ) -> pl.DataFrame:
    """Add `y3` (null when unknown) and `drop_reason` (null when the row is kept).

    `rows` needs `t` (month index), `last_t` (the life's last trading month L) and
    `outcome` ('event' or 'censored'). Rules:
    - t >= L: the final, partial trading month (or later): never a feature row.
    - t > obs_end: after the last complete month.
    - t + horizon > obs_end: the label window runs past the data end. A zero cannot be
      known there, so the row is dropped for EVERY life, events included; keeping the
      event rows would leave the last months with dying contracts only.
    - event life: y3 = 1 if L - t in 1..horizon, else 0; known.
    - censored life: censored at C = min(L, obs_end). y3 = 0 is known only when the whole
      window t+1..t+horizon is at or before C; otherwise the row is dropped, never set to 0.
    """
    if obs_end is None:
        obs_end = midx(OBS_END)
    gap = pl.col("last_t") - pl.col("t")
    is_event = pl.col("outcome") == "event"
    cens = pl.min_horizontal(pl.col("last_t"), pl.lit(obs_end))
    known_zero = (~is_event) & (pl.col("t") + horizon <= cens)
    reason = (pl.when(pl.col("t") >= pl.col("last_t")).then(pl.lit("final_trading_month"))
              .when(pl.col("t") > obs_end).then(pl.lit("after_data_end"))
              .when(pl.col("t") + horizon > obs_end).then(pl.lit("label_window_past_data_end"))
              .when(is_event | known_zero).then(pl.lit(None, dtype=pl.String))
              .otherwise(pl.lit("censored_label_unknown")))
    y = (pl.when(reason.is_not_null()).then(pl.lit(None, dtype=pl.Int8))
         .when(is_event & gap.is_between(1, horizon)).then(pl.lit(1, dtype=pl.Int8))
         .otherwise(pl.lit(0, dtype=pl.Int8)))
    return rows.with_columns(y3=y, drop_reason=reason)


def add_trailing_features(df: pl.DataFrame) -> pl.DataFrame:
    """Trailing features per life from month-t columns; looks only backward.

    Needs `life_id`, `t`, `log_qv`, `log_trades`, `close_last`, `log_oi`,
    `funding_interval_min_h`. Lags are by calendar month (join on t - k), so a missing
    month gives a null, never the wrong month.
    """
    lag_cols = ["log_qv", "log_trades", "close_last", "log_oi", "funding_interval_min_h"]
    base = df.select("life_id", "t", *lag_cols)
    out = df
    for k in (1, 3, 6):
        lag = base.select("life_id", (pl.col("t") + k).alias("t"),
                          *[pl.col(c).alias(f"{c}__lag{k}") for c in lag_cols])
        out = out.join(lag, on=["life_id", "t"], how="left")
    out = out.sort("life_id", "t").with_columns(
        dlog_qv_3m=pl.col("log_qv") - pl.col("log_qv__lag3"),
        dlog_qv_6m=pl.col("log_qv") - pl.col("log_qv__lag6"),
        dlog_trades_3m=pl.col("log_trades") - pl.col("log_trades__lag3"),
        dlog_trades_6m=pl.col("log_trades") - pl.col("log_trades__lag6"),
        ret_3m=pl.col("close_last") / pl.col("close_last__lag3") - 1,
        ret_6m=pl.col("close_last") / pl.col("close_last__lag6") - 1,
        dlog_oi_3m=pl.col("log_oi") - pl.col("log_oi__lag3"),
        log_qv_rel_peak=pl.col("log_qv") - pl.col("log_qv").cum_max().over("life_id"),
        log_trades_rel_peak=(pl.col("log_trades")
                             - pl.col("log_trades").cum_max().over("life_id")),
        funding_interval_shortened=(pl.col("funding_interval_min_h")
                                    < pl.col("funding_interval_min_h__lag1")),
    )
    return out.drop([c for c in out.columns if "__lag" in c])


def add_cross_section_ranks(df: pl.DataFrame) -> pl.DataFrame:
    """Percentile ranks within month among the live universe (`in_universe` rows)."""
    u = df.filter(pl.col("in_universe"))

    def pct(col: str) -> pl.Expr:
        r = pl.col(col).rank("average").over("t")
        return r / pl.col(col).count().over("t")

    ranks = u.select(
        "life_id", "t",
        qv_rank_pct=pct("log_qv"),
        trades_rank_pct=pct("log_trades"),
        oi_rank_pct=pct("log_oi"),
        n_live_month=pl.len().over("t").cast(pl.Int32),
    )
    return df.join(ranks, on=["life_id", "t"], how="left")


# --------------------------------------------------------------------------------------
# Validation pieces (pure, tested)
# --------------------------------------------------------------------------------------

def purged_expanding_folds(t: np.ndarray, first_test: int, test_len: int = TEST_LEN,
                           horizon: int = H, end: int | None = None) -> list[dict]:
    """Expanding-window folds on month indices `t` (one per row).

    Test block = months [T, T + test_len) clipped to `end` (exclusive). Training rows are
    every row with t + horizon < T: their label window t+1..t+horizon ends before the test
    block starts. The purge removes rows T-horizon..T-1, exactly those whose window
    overlaps the block.
    """
    if end is None:
        end = int(t.max()) + 1
    folds = []
    start = first_test
    while start < end:
        stop = min(start + test_len, end)
        folds.append({
            "test_start": start, "test_stop": stop,
            "train": np.flatnonzero(t + horizon < start),
            "test": np.flatnonzero((t >= start) & (t < stop)),
            "purged": np.flatnonzero((t < start) & (t + horizon >= start)),
        })
        start = stop
    return folds


def choose_threshold(x: np.ndarray, y: np.ndarray,
                     quantiles: np.ndarray = THRESHOLD_QUANTILES) -> float:
    """Rule (a): flag x < thr. thr is the training quantile with the best training F1."""
    ok = np.isfinite(x)
    x, y = x[ok], y[ok]
    best_f1, best = -1.0, float("nan")
    for thr in np.unique(np.quantile(x, quantiles)):
        flag = x < thr
        tp = float(np.sum(flag & (y == 1)))
        denom = float(flag.sum() + y.sum())
        f1 = 2 * tp / denom if denom else 0.0
        if f1 > best_f1:
            best_f1, best = f1, float(thr)
    return best


def alert_counts(month: np.ndarray, y: np.ndarray, score: np.ndarray,
                 rate: float = ALERT_RATE) -> dict[int, tuple[int, int, int, int]]:
    """Per month: (n_live, n_alerts, hits, events) when the top `rate` by score is flagged.

    n_alerts = max(1, round(rate * n_live)). NaN scores rank last; ties are broken by row
    order, which is fixed (sorted by month and life id).
    """
    s = np.where(np.isfinite(score), score, -np.inf)
    out = {}
    for m in np.unique(month):
        idx = np.flatnonzero(month == m)
        n = len(idx)
        k = max(1, round(rate * n))
        top = idx[np.argsort(-s[idx], kind="stable")[:k]]
        out[int(m)] = (n, k, int(y[top].sum()), int(y[idx].sum()))
    return out


def average_precision(y: np.ndarray, score: np.ndarray) -> float:
    from sklearn.metrics import average_precision_score
    if y.sum() == 0:
        return float("nan")
    s = np.where(np.isfinite(score), score, -1e300)
    return float(average_precision_score(y, s))


def block_bootstrap_months(months: np.ndarray, n_boot: int = N_BOOT, block: int = BOOT_BLOCK,
                           seed: int = SEED) -> list[np.ndarray]:
    """Moving-block bootstrap of a sorted array of months: each replicate concatenates
    random runs of `block` consecutive months until it has as many months as the sample."""
    rng = np.random.default_rng(seed)
    n = len(months)
    n_blocks = math.ceil(n / block)
    reps = []
    for _ in range(n_boot):
        starts = rng.integers(0, n - block + 1, n_blocks)
        pos = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n]
        reps.append(months[pos])
    return reps


# --------------------------------------------------------------------------------------
# Build stage
# --------------------------------------------------------------------------------------

def q14_noncrypto() -> dict[str, str]:
    """Symbols Q14 keeps out of the crypto comparison (name review or timing screen)."""
    d = json.loads(Q14_JSON.read_text())
    out = {}
    for f in d["equity_screen"]["flagged"]:
        out[f["symbol"]] = (f"Q14 name review: {f['by_name']}" if f["by_name"]
                            else "Q14 timing screen")
    return out


def daily_life_stats(lives: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Per life: weekend ratio, and per month the life-only drawdowns from daily closes."""
    wk_rows, dd_parts = [], []
    for sym, g in lives.group_by("symbol", maintain_order=True):
        sym = sym[0]
        path = RAW_CONTRACTS / sym / "klines.parquet"
        k_all = pl.read_parquet(path) if path.exists() else None
        for r in g.iter_rows(named=True):
            ratio, nd = None, 0
            if k_all is not None:
                k = (k_all.filter((pl.col("count") > 0)
                                  & pl.col("date").is_between(r["first_trade_day"],
                                                              r["last_trade_day"]))
                     .sort("date"))
                nd = k.height
                if nd:
                    wd = k["date"].dt.weekday()
                    we = k.filter(wd >= 6)["quote_volume"].median()
                    wkd = k.filter(wd <= 5)["quote_volume"].median()
                    if we is not None and wkd:
                        ratio = float(we) / float(wkd)
                    k = k.with_columns(
                        dd=pl.col("close") / pl.col("close").cum_max() - 1,
                        month=pl.col("date").dt.strftime("%Y-%m"))
                    dd_parts.append(k.group_by("month").agg(
                        dd_life_month_end=pl.col("dd").last(),
                        max_dd_life=pl.col("dd").min(),
                    ).with_columns(life_id=pl.lit(r["life_id"])))
            wk_rows.append({"life_id": r["life_id"], "weekend_ratio": ratio,
                            "kline_trading_days": nd})
    return pl.DataFrame(wk_rows), pl.concat(dd_parts)


def classify_lives(lives: pl.DataFrame, weekend: pl.DataFrame) -> pl.DataFrame:
    """Add `outcome` and `exclude_reason` to the lifecycle rows."""
    q14 = q14_noncrypto()
    lives = lives.join(weekend, on="life_id", how="left")
    reasons = []
    for r in lives.iter_rows(named=True):
        reason = None
        if r["status"] in EXCLUDED_STATUSES:
            reason = "index contract"
        elif r["symbol"] in q14 and r["life"] == r["n_lives"]:
            reason = q14[r["symbol"]]
        elif (str(r["first_trade_day"]) >= NONCRYPTO_SCREEN_FROM
              and (r["symbol"], r["life"]) not in CRYPTO_KEEP):
            wr, nd = r["weekend_ratio"], r["kline_trading_days"]
            if nd < WEEKEND_MIN_DAYS or wr is None:
                reason = f"non-crypto by name; under {WEEKEND_MIN_DAYS} trading days to screen"
            elif wr < WEEKEND_RATIO_MAX:
                reason = f"weekend screen (ratio {wr:.2f}), non-crypto by name"
        reasons.append(reason)
    return lives.with_columns(
        exclude_reason=pl.Series(reasons, dtype=pl.String),
        outcome=pl.col("status").map_elements(life_outcome, return_dtype=pl.String),
    ).with_columns(outcome=pl.when(pl.col("exclude_reason").is_not_null())
                   .then(pl.lit("excluded")).otherwise(pl.col("outcome")))


PANEL_KEEP = [
    "has_klines", "has_funding", "has_metrics", "ghost_month", "resumed_after_ghost",
    "days_in_month", "n_kline_days", "missing_kline_days", "trading_days", "quote_volume",
    "quote_volume_median", "n_trades", "avg_trade_usd", "taker_buy_share", "close_last",
    "ret_month", "realized_vol", "mean_range", "oi_usd_month_end", "ls_account_month_end",
    "ls_toptrader_account_month_end", "metrics_is_last_day", "n_funding", "funding_mean",
    "funding_abs_mean", "funding_interval_min_h",
]


def build() -> pl.DataFrame:
    t0 = time.time()
    obs_end = midx(OBS_END)
    lc = pl.read_csv(LIFECYCLE_CSV, try_parse_dates=True)
    lives = lc.with_columns(
        life_id=pl.col("symbol") + "#" + pl.col("life").cast(pl.String),
        first_t=date_midx("first_trade_day"), last_t=date_midx("last_trade_day"),
    )
    weekend, dd = daily_life_stats(lives)
    lives = classify_lives(lives, weekend)

    # Person-period grid: every month of every life, from its first trading month to the
    # last trading month (or the last complete month). The final month stays in the grid
    # only so that nothing is shifted wrongly; it is dropped as a feature row below.
    grid = (lives.select("life_id", "symbol", "life", "first_t", "last_t")
            .with_columns(t=pl.int_ranges("first_t",
                                          pl.min_horizontal("last_t", pl.lit(obs_end)) + 1))
            .explode("t", empty_as_null=True).drop_nulls("t")
            .with_columns(month=pl.col("t").map_elements(mstr, return_dtype=pl.String)))
    panel = pl.read_parquet(MONTHLY_PANEL).select("symbol", "month", *PANEL_KEEP)
    df = (grid.join(panel, on=["symbol", "month"], how="left")
          .join(dd, on=["life_id", "month"], how="left")
          .with_columns(
              age_months=(pl.col("t") - pl.col("first_t")).cast(pl.Int32),
              zero_volume_days=(pl.col("n_kline_days").cast(pl.Int32)
                                - pl.col("trading_days")),
              in_panel=pl.col("has_klines").is_not_null(),
              log_qv=pl.col("quote_volume").log1p(),
              log_trades=pl.col("n_trades").cast(pl.Float64).log1p(),
              log_oi=pl.when(pl.col("oi_usd_month_end") > 0)
              .then(pl.col("oi_usd_month_end").log1p()),
          )
          .with_columns(
              log_age=pl.col("age_months").cast(pl.Float64).log1p(),
              has_oi=pl.col("log_oi").is_not_null(),
              log_oi_to_qv=pl.col("log_oi") - pl.col("log_qv"),
          ))
    df = add_trailing_features(df)
    meta = lives.select("life_id", "status", "outcome", "exclude_reason", "n_lives",
                        "first_trade_day", "last_trade_day", "successor")
    df = df.join(meta, on="life_id", how="left")
    # Live universe at month-end t: included lives still trading after month t.
    df = df.with_columns(in_universe=(pl.col("outcome") != "excluded")
                         & (pl.col("t") < pl.col("last_t")) & pl.col("in_panel"))
    df = add_cross_section_ranks(df)
    labelled = assign_labels(df.filter(pl.col("outcome") != "excluded"))
    labelled = labelled.with_columns(
        event=pl.col("outcome") == "event",
        months_to_last=(pl.col("last_t") - pl.col("t")).cast(pl.Int32),
        last_trade_month=pl.col("last_t").map_elements(mstr, return_dtype=pl.String),
        last_trade_dom=pl.col("last_trade_day").dt.day().cast(pl.Int8),
    ).with_columns(
        final_full_month=pl.col("event") & (pl.col("months_to_last") == 1),
        lockbox=pl.col("t") >= midx(LOCKBOX_START),
    )
    stats = {"build_seconds": round(time.time() - t0, 1)}
    kept = labelled.filter(pl.col("drop_reason").is_null() & pl.col("in_panel"))
    # Rows inside a life without any panel row (no kline, funding or metrics file).
    stats["no_panel_rows"] = labelled.filter(pl.col("drop_reason").is_null()
                                             & ~pl.col("in_panel")).height
    stats["drop_reasons"] = (labelled.filter(pl.col("drop_reason").is_not_null())
                             .group_by("drop_reason").len().sort("drop_reason").rows())
    out = kept.select(COLUMN_ORDER).sort("t", "life_id")
    out.write_parquet(PANEL_OUT)
    write_panel_md(out, lives, labelled, stats)
    print(f"wrote {PANEL_OUT.relative_to(ROOT)}: {out.height} rows, "
          f"{out['life_id'].n_unique()} lives, {int(out['y3'].sum())} positive rows")
    return out


COLUMNS = {
    # identifiers and label
    "life_id": "SYMBOL#life (life 2 = the ticker trading again after a gap over 30 days)",
    "symbol": "contract ticker",
    "life": "life number from the lifecycle table",
    "month": "month t (YYYY-MM): the row is a prediction made at the end of month t",
    "t": "month index year * 12 + month - 1 (for arithmetic)",
    "y3": "1 if the life's last trading month L is in t+1..t+3 and the life is an event",
    "event": "the life ends in a delisting (status delisted, or reused-symbol first life)",
    "status": "lifecycle status of the life (delisted, reused-symbol, renamed, merged, alive)",
    "outcome": "event or censored",
    "last_trade_day": "last day with a daily aggTrades file (lifecycle table). LABEL SIDE",
    "last_trade_month": "L, month of last_trade_day. LABEL SIDE, never a feature",
    "months_to_last": "L - t (>= 1). LABEL SIDE, never a feature",
    "last_trade_dom": "day of month of last_trade_day. LABEL SIDE, never a feature",
    "final_full_month": "event life and t = L - 1 (the month most exposed to the "
                        "announcement); the sensitivity run drops these rows. LABEL SIDE",
    "lockbox": "t >= 2026-01: reserved lock-box origin, not scored in b0",
    "first_trade_day": "first day of the life (aggTrades)",
    "successor": "new ticker for renamed and merged lives (information only)",
    # month-t panel features (definitions in monthly_panel.md)
    "age_months": "months since the life's first trading month (0 = listing month)",
    "log_age": "ln(1 + age_months)",
    "has_klines": "a 1d kline file exists for month t",
    "has_funding": "a fundingRate file exists for month t",
    "has_metrics": "a metrics file exists for month t (most contracts from 2021-12)",
    "ghost_month": "files but no day with volume > 0 in month t (only possible inside a life "
                   "if trading paused a whole month; 0 rows in the kept panel)",
    "resumed_after_ghost": "monthly panel flag, kept for audit; the life split already "
                           "resets age and peaks",
    "days_in_month": "calendar days",
    "n_kline_days": "daily kline rows in month t",
    "missing_kline_days": "days_in_month - n_kline_days (listing month, gaps)",
    "trading_days": "daily kline rows with volume > 0",
    "zero_volume_days": "n_kline_days - trading_days (ghost-like days inside month t)",
    "quote_volume": "USDT quote volume summed over month t",
    "quote_volume_median": "median daily quote volume in month t (zero days included)",
    "n_trades": "trades in month t (sum of daily count)",
    "avg_trade_usd": "quote_volume / n_trades",
    "taker_buy_share": "taker buy quote volume / quote volume",
    "close_last": "close of the last kline day of month t",
    "ret_month": "close_last / first open of month t - 1",
    "realized_vol": "std of daily log returns in month t (trading days)",
    "mean_range": "mean (high - low) / close on trading days of month t",
    "dd_life_month_end": "close at the last trading day of month t / running max daily "
                         "close since the life's first day - 1 (per life, so a second "
                         "life does not inherit the first life's peak)",
    "max_dd_life": "worst daily close / running max since the life's first day - 1, "
                   "within month t",
    "oi_usd_month_end": "open interest value (USDT) at the last 5-minute row of the last "
                        "metrics day of month t; null without metrics",
    "has_oi": "oi_usd_month_end is present and > 0",
    "log_oi": "ln(1 + oi_usd_month_end) when > 0, else null",
    "log_oi_to_qv": "log_oi - log_qv (OI relative to monthly volume)",
    "ls_account_month_end": "all-account long/short ratio, same metrics row",
    "ls_toptrader_account_month_end": "top-trader account long/short ratio, same row",
    "metrics_is_last_day": "the metrics day is the calendar month-end",
    "n_funding": "funding events in month t",
    "funding_mean": "mean funding rate per interval in month t",
    "funding_abs_mean": "mean absolute funding rate",
    "funding_interval_min_h": "shortest funding interval (hours) seen in month t",
    # engineered trailing features
    "log_qv": "ln(1 + quote_volume)",
    "log_trades": "ln(1 + n_trades)",
    "dlog_qv_3m": "log_qv(t) - log_qv(t-3), same life; null if t-3 is before the life",
    "dlog_qv_6m": "log_qv(t) - log_qv(t-6), same life",
    "dlog_trades_3m": "log_trades(t) - log_trades(t-3), same life",
    "dlog_trades_6m": "log_trades(t) - log_trades(t-6), same life",
    "log_qv_rel_peak": "log_qv(t) - max over the life's months up to t of log_qv (<= 0; "
                       "-4.6 is the Feder 1%-of-peak rule)",
    "log_trades_rel_peak": "same for log_trades",
    "ret_3m": "close_last(t) / close_last(t-3) - 1, same life",
    "ret_6m": "close_last(t) / close_last(t-6) - 1, same life",
    "dlog_oi_3m": "log_oi(t) - log_oi(t-3), same life",
    "funding_interval_shortened": "funding_interval_min_h(t) < its value at t-1",
    "qv_rank_pct": "percentile rank of log_qv within month t among live contracts "
                   "(1 = largest); live = included lives still trading after month t",
    "trades_rank_pct": "same for log_trades",
    "oi_rank_pct": "same for log_oi (among live contracts with OI)",
    "n_live_month": "number of live contracts in month t (rank denominator)",
}
COLUMN_ORDER = list(COLUMNS)


def _md_table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def write_panel_md(out: pl.DataFrame, lives: pl.DataFrame, labelled: pl.DataFrame,
                   stats: dict) -> None:
    inc = lives.filter(pl.col("outcome") != "excluded")
    ev_lives = inc.filter(pl.col("outcome") == "event")
    pos_ids = set(out.filter(pl.col("y3") == 1)["life_id"].to_list())
    ev_in = len(pos_ids)
    no_pos = sorted(set(ev_lives["life_id"].to_list()) - pos_ids)
    by_year = (out.with_columns(year=pl.col("month").str.slice(0, 4))
               .group_by("year").agg(rows=pl.len(), lives=pl.col("life_id").n_unique(),
                                     pos=pl.col("y3").sum(),
                                     ev=pl.col("life_id").filter(pl.col("y3") == 1)
                                     .n_unique())
               .sort("year"))
    year_rows = [[r["year"], r["rows"], r["lives"], r["pos"], r["ev"],
                  f"{r['pos'] / r['rows']:.4f}"] for r in by_year.iter_rows(named=True)]
    deaths = (ev_lives.with_columns(year=pl.col("last_trade_day").dt.year())
              .group_by("year", "status").len().sort("year", "status"))
    excl = lives.filter(pl.col("outcome") == "excluded").sort("symbol", "life")
    excl_lines = [f"{r['symbol']} (life {r['life']}, from {r['first_trade_day']}): "
                  f"{r['exclude_reason']}" for r in excl.iter_rows(named=True)]
    status_counts = inc.group_by("status").len().sort("status").rows()
    lb = out.filter(pl.col("lockbox"))
    sens = out.filter(~pl.col("final_full_month"))
    col_rows = [[f"`{c}`", out.schema[c], COLUMNS[c]] for c in COLUMN_ORDER]
    txt = f"""# Delisting panel (`delisting_panel.parquet`)

Built by `research/market_evolution/b0_baselines.py build` from `contract_lifecycle.csv`,
`monthly_panel.parquet` and the per-contract daily klines under `data/raw_panel/`.
Person-period layout: one row per contract life per month t, a prediction made at the end
of month t. Horizon H = {H}. Last complete month: {OBS_END} (archive ends 2026-11-16).
Build time {stats['build_seconds']} s.

## Size

- Rows: {out.height:,}; lives: {out['life_id'].n_unique():,}; months: {out['month'].min()} to
  {out['month'].max()}.
- Positive rows (y3 = 1): {int(out['y3'].sum()):,}; base rate {out['y3'].mean():.4f}.
- Event lives (included): {ev_lives.height} ({', '.join(f'{s} {n}' for s, n in
  ev_lives.group_by('status').len().sort('status').rows())}); {ev_in} of them have at
  least one positive row (without one: {', '.join(no_pos) or 'none'}).
- Included lives by status: {', '.join(f'{s} {n}' for s, n in status_counts)}.
- Lock-box rows (t >= {LOCKBOX_START}): {lb.height:,} rows, months {lb['month'].min()} to
  {lb['month'].max()}. Reserved: not scored in b0.
- Sensitivity panel (drop t = L - 1 of event lives): {sens.height:,} rows,
  {int(sens['y3'].sum()):,} positive rows.
- Rows dropped before writing: {', '.join(f'{r} {n:,}' for r, n in stats['drop_reasons'])};
  life months with no panel row at all: {stats['no_panel_rows']}.

## By year of t

{_md_table(['year', 'rows', 'lives', 'positive rows', 'event lives with a positive row',
            'base rate'], year_rows)}

Event lives by year of the last trading day: {'; '.join(f'{y} {s} {n}' for y, s, n in
deaths.rows())}.

## Rules

- **Lives.** From `contract_lifecycle.csv`: a gap of more than 30 days between trading days
  starts a new life, so the 11 reused tickers (ICP, TLM, SLP, CVC, CTK, CVX, MAVIA, AIA,
  MDT, NU, LIT) give two lives each. Age, running peaks, drawdowns and lags restart in each
  life. The monthly panel's `resumed_after_ghost` rows are the second-life starts, plus
  pre-listing funding or metrics files (BNT, BZ, CL, NATGAS, FOOTBALL), which fall outside
  the life and are dropped.
- **Dates from aggTrades.** The last trading month L is the month of the lifecycle
  `last_trade_day` (daily aggTrades), never the last kline, funding or metrics file (ghost
  files continue after death).
- **Event.** Status `delisted`, or `reused-symbol` (a first life that stopped trading for
  more than 30 days before the ticker came back: a delisting followed by a relisting, as for
  ICP in 2022). `renamed` (10) and `merged` (2) lives are censored at L: not events, not
  negatives near the end. `alive` lives are censored at {OBS_END}.
- **Label.** y3 = 1 if L is in t+1..t+3. Event lives: every row t < L has a known label.
  Censored lives (C = min(L, {OBS_END})): y3 = 0 only when t + 3 <= C; rows with
  t + 3 > C are dropped (censored), never set to 0.
- **Common label end.** Rows with t + 3 > {OBS_END} are dropped for every life, events
  included, so the last labelled month is {mstr(midx(OBS_END) - H)}. Keeping the event rows
  there (their labels are known) would leave months {mstr(midx(OBS_END) - H + 1)} to
  {mstr(midx(OBS_END) - 1)} with dying contracts only.
- **No final month.** The row t = L (partial month, often post-announcement trading) is never
  a feature row. Rows after {OBS_END} do not exist.
- **Features** use months up to and including t only: month-t panel values, lags by
  calendar month inside the life (join on t - k, never a row shift), running maxima up to
  t, and within-month ranks among contracts live at the end of t (included lives with
  t < L). Columns marked LABEL SIDE must never enter a model.
- **Exclusions** (listed below): index contracts (3), and non-crypto underlyings: Q14's
  name list and timing screen, plus every life first trading on or after
  {NONCRYPTO_SCREEN_FROM} whose median weekend-day quote volume is under
  {WEEKEND_RATIO_MAX:.2f} of the median weekday (crypto contracts sit near 0.6 to 1.1) or
  which has under {WEEKEND_MIN_DAYS} trading days. Every flagged life was checked by name; five
  crypto lives under the cut are kept: {', '.join(f'{s} life {n}' for s, n in
  sorted(CRYPTO_KEEP))}. No excluded life is an event (all are alive, or index contracts).

## Announcement leakage (limitation)

Binance announces a futures delisting about 5 to 10 days before settlement (verified
notices: XEM/ORBS/LOOM, REEF, DEFI/MEMEFI, the 2025-12-05 batch), and the announcement moves
prices and volume (XEMUSDT quote volume went from about $5M a day to $47M to $90M on the
announcement days). The panel has **no announcement date per contract**. The final trading
month L is already excluded. When settlement falls early in month L, the announcement and
its spike fall in month L - 1, which is a positive row. `final_full_month` marks those rows,
and `b0_baselines.py` reports every result with and without them. Of the event lives with
a positive row, {int(out.filter(pl.col('final_full_month') & (pl.col('last_trade_dom') <= 10))
['life_id'].n_unique())} settled on day 10 or earlier of month L, so for them month L - 1
very likely contains the announcement. Collecting the true announcement times (bapi list
endpoint, notes section 9) would replace this crude drop with a cut at the announcement.

## Data problems found

- AERGOUSDT: daily klines stop on 2026-06-30, but daily aggTrades has a file on 2026-07-23
  (lifecycle last day). L is taken from the lifecycle (2026-07), so the 2026-07 row is the
  final month and is dropped; features are unaffected.
- KEEPUSDT and NUUSDT (life 1) both stopped on 2022-02-15, when the tokens merged into
  Threshold; TUSDT only listed on 2023-02-01. The lifecycle counts them as a delisting and
  a reused-symbol life, so they are events here; the notes call them a merger [I]. Two of
  the 2022 events may therefore be token migrations.
- The listing month is partial, so a 3-month volume change measured from age 3 compares
  against a short month and reads too positive. Rule (a) treats young lives (age < 3,
  `dlog_qv_3m` null) as never flagged.
- Metrics (OI, long/short) start 2021-12 for most contracts: `has_oi` is false before.
  The weekend screen and Q14's list cover non-crypto lives; contracts first trading before
  {NONCRYPTO_SCREEN_FROM} were only checked through Q14 (PAXG is the one excluded).

## Excluded lives ({excl.height})

{chr(10).join('- ' + s for s in excl_lines)}

## Columns

{_md_table(['column', 'type', 'definition'], col_rows)}
"""
    PANEL_MD.write_text(txt)


# --------------------------------------------------------------------------------------
# Evaluation stage
# --------------------------------------------------------------------------------------

def fit_logit(X: np.ndarray, y: np.ndarray):
    """Logistic regression with train-only standardization, no class weights."""
    from sklearn.linear_model import LogisticRegression
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    clf = LogisticRegression(C=1.0, max_iter=2000).fit((X - mu) / sd, y)
    return clf, mu, sd


def logit_matrix(d: pl.DataFrame) -> np.ndarray:
    return d.select(
        pl.col("dlog_qv_3m").fill_null(0.0),
        pl.col("qv_rank_pct").fill_null(0.5),
        pl.col("log_age"),
    ).to_numpy().astype(float)


def score_folds(d: pl.DataFrame, folds: list[dict]) -> dict:
    """Out-of-fold scores of the three baselines, plus the per-fold choices."""
    n = d.height
    y = d["y3"].to_numpy().astype(int)
    dlog = d["dlog_qv_3m"].fill_null(np.nan).to_numpy().astype(float)
    rank = d["qv_rank_pct"].fill_null(np.nan).to_numpy().astype(float)
    X = logit_matrix(d)
    s_a, s_b, s_c = (np.full(n, np.nan) for _ in range(3))
    flag_a = np.zeros(n, dtype=bool)
    brier_ref = np.full(n, np.nan)
    per_fold = []
    for f in folds:
        tr, te = f["train"], f["test"]
        thr = choose_threshold(dlog[tr], y[tr])
        s_a[te] = -dlog[te]
        flag_a[te] = np.isfinite(dlog[te]) & (dlog[te] < thr)
        s_b[te] = -rank[te]
        clf, mu, sd = fit_logit(X[tr], y[tr])
        s_c[te] = clf.predict_proba((X[te] - mu) / sd)[:, 1]
        brier_ref[te] = y[tr].mean()
        per_fold.append({
            "test": f"{mstr(f['test_start'])} to {mstr(f['test_stop'] - 1)}",
            "train_last": mstr(int(d['t'].to_numpy()[tr].max())), "n_train": len(tr),
            "train_events": int(y[tr].sum()), "n_test": len(te),
            "test_pos": int(y[te].sum()), "threshold_a": thr,
            "coef_c": (clf.coef_[0] / sd).round(3).tolist(),
        })
    return {"a": s_a, "b": s_b, "c": s_c, "flag_a": flag_a, "brier_ref": brier_ref,
            "per_fold": per_fold}


def evaluate_variant(df: pl.DataFrame, drop_final_full: bool) -> dict:
    d = df.filter(pl.col("t") < midx(LOCKBOX_START))
    if drop_final_full:
        d = d.filter(~pl.col("final_full_month"))
    d = d.sort("t", "life_id")
    t = d["t"].to_numpy()
    folds = purged_expanding_folds(t, midx(FIRST_TEST), end=midx(LOCKBOX_START))
    sc = score_folds(d, folds)
    test = np.concatenate([f["test"] for f in folds])
    y = d["y3"].to_numpy().astype(int)[test]
    month = t[test]
    months = np.unique(month)
    row_by_month = {int(m): np.flatnonzero(month == m) for m in months}
    scores = {k: sc[k][test] for k in ("a", "b", "c")}
    flag_a = sc["flag_a"][test]
    ref = sc["brier_ref"][test]
    alerts = {k: alert_counts(month, y, s) for k, s in scores.items()}

    def stats(ms: np.ndarray) -> dict:
        idx = np.concatenate([row_by_month[int(m)] for m in ms])
        yy = y[idx]
        out = {}
        for k in scores:
            a = np.array([alerts[k][int(m)] for m in ms])
            out[f"prec_{k}"] = a[:, 2].sum() / a[:, 1].sum()
            out[f"rec_{k}"] = a[:, 2].sum() / a[:, 3].sum() if a[:, 3].sum() else np.nan
            out[f"ap_{k}"] = average_precision(yy, scores[k][idx])
        fa = flag_a[idx]
        out["rule_prec_a"] = (yy[fa].sum() / fa.sum()) if fa.sum() else np.nan
        out["rule_rec_a"] = (yy[fa].sum() / yy.sum()) if yy.sum() else np.nan
        out["rule_rate_a"] = fa.mean()
        out["base"] = yy.mean()
        p = scores["c"][idx]
        out["brier_c"] = float(np.mean((p - yy) ** 2))
        out["brier_ref"] = float(np.mean((ref[idx] - yy) ** 2))
        out["bss_c"] = 1 - out["brier_c"] / out["brier_ref"]
        out["prec_c_minus_a"] = out["prec_c"] - out["prec_a"]
        out["prec_b_minus_a"] = out["prec_b"] - out["prec_a"]
        out["ap_c_minus_a"] = out["ap_c"] - out["ap_a"]
        out["prec_c_minus_b"] = out["prec_c"] - out["prec_b"]
        out["ap_c_minus_b"] = out["ap_c"] - out["ap_b"]
        return out

    point = stats(months)
    boots = [stats(ms) for ms in block_bootstrap_months(months)]
    ci = {k: (float(np.nanpercentile([b[k] for b in boots], 2.5)),
              float(np.nanpercentile([b[k] for b in boots], 97.5))) for k in point}
    # Reliability table for (c): deciles of the predicted probability.
    p, order = scores["c"], np.argsort(scores["c"], kind="stable")
    rel = []
    for b in np.array_split(order, 10):
        rel.append((float(p[b].min()), float(p[b].max()), len(b), int(y[b].sum()),
                    float(p[b].mean()), float(y[b].mean())))
    a_tot = {k: np.array(list(v.values())) for k, v in alerts.items()}
    return {
        "point": point, "ci": ci, "per_fold": sc["per_fold"], "reliability": rel,
        "n_rows": len(test), "n_pos": int(y.sum()), "n_months": len(months),
        "test_events": int(np.unique(d["life_id"].to_numpy()[test][y == 1]).size),
        "alerts_total": {k: (int(v[:, 1].sum()), int(v[:, 2].sum()), int(v[:, 3].sum()))
                         for k, v in a_tot.items()},
        "months_with_events": int(sum(1 for v in alerts["a"].values() if v[3] > 0)),
        "purged_rows": [len(f["purged"]) for f in folds],
    }


def _ci(res: dict, k: str, fmt: str = "{:.3f}") -> str:
    lo, hi = res["ci"][k]
    return f"{fmt.format(res['point'][k])} ({fmt.format(lo)} to {fmt.format(hi)})"


def write_baseline_md(df: pl.DataFrame, res: dict[str, dict], seconds: float) -> None:
    lb = df.filter(pl.col("lockbox"))
    by_year = (df.filter(~pl.col("lockbox")).with_columns(year=pl.col("month").str.slice(0, 4))
               .group_by("year").agg(rows=pl.len(), pos=pl.col("y3").sum(),
                                     ev=pl.col("life_id").filter(pl.col("y3") == 1)
                                     .n_unique()).sort("year"))
    year_rows = [[r["year"], f"{r['rows']:,}", r["pos"], r["ev"], f"{r['pos'] / r['rows']:.4f}"]
                 for r in by_year.iter_rows(named=True)]
    names = {"a": "(a) falling volume: score = -dlog_qv_3m",
             "b": "(b) lowest volume rank: score = -qv_rank_pct",
             "c": "(c) logistic: dlog_qv_3m, qv_rank_pct, log_age"}
    sections = []
    for label, r in res.items():
        rows = []
        for k in ("a", "b", "c"):
            al, hits, _ev = r["alerts_total"][k]
            rows.append([names[k], _ci(r, f"prec_{k}"), _ci(r, f"rec_{k}"), f"{hits}/{al}",
                         _ci(r, f"ap_{k}")])
        fold_rows = [[f["test"], f["train_last"], f"{f['n_train']:,}", f["train_events"],
                      f"{f['n_test']:,}", f["test_pos"], f"{f['threshold_a']:.2f}",
                      ", ".join(f"{c:+.2f}" for c in f["coef_c"])]
                     for f in r["per_fold"]]
        rel_rows = [[f"{lo:.4f} to {hi:.4f}", n, e, f"{mp:.4f}", f"{op:.4f}"]
                    for lo, hi, n, e, mp, op in r["reliability"]]
        p = r["point"]
        sections.append(f"""## {label}

Test rows {r['n_rows']:,} over {r['n_months']} origin months ({FIRST_TEST} to 2025-12),
{r['n_pos']} positive rows from {r['test_events']} event lives; {r['months_with_events']}
of the {r['n_months']} months have at least one positive row. Base rate
{_ci(r, 'base', '{:.4f}')}.
Intervals: 95% percentile intervals from a moving-block bootstrap of test months (blocks
of {BOOT_BLOCK} consecutive months, {N_BOOT} replicates).

Top {ALERT_RATE:.0%} alert rate per month (n alerts = max(1, round(0.05 x live contracts))):

{_md_table(['baseline', 'precision', 'recall', 'hits/alerts', 'PR-AUC'], rows)}

Paired differences (same bootstrap months): precision (c) - (a)
{_ci(r, 'prec_c_minus_a')}; (b) - (a) {_ci(r, 'prec_b_minus_a')}; (c) - (b)
{_ci(r, 'prec_c_minus_b')}. PR-AUC (c) - (a) {_ci(r, 'ap_c_minus_a')}; (c) - (b)
{_ci(r, 'ap_c_minus_b')}.

Rule (a) as a fixed threshold (flag dlog_qv_3m < thr, thr = training quantile with the
best training F1, chosen per fold on training rows only): precision
{_ci(r, 'rule_prec_a')}, recall {_ci(r, 'rule_rec_a')}, alert rate
{_ci(r, 'rule_rate_a')}.

Calibration of (c): Brier {p['brier_c']:.5f} against {p['brier_ref']:.5f} for predicting
the training base rate; Brier skill {_ci(r, 'bss_c')}.

Reliability of (c), deciles of the predicted probability (pooled test rows):

{_md_table(['predicted range', 'rows', 'positives', 'mean predicted', 'observed rate'],
           rel_rows)}

Folds (training rows have t + 3 < test start; rows purged per fold:
{', '.join(str(x) for x in r['purged_rows'])}):

{_md_table(['test block', 'last train month', 'train rows', 'train positives', 'test rows',
            'test positives', 'thr (a)', 'coef (c) per raw unit'], fold_rows)}
""")
    m, s = res["main"]["point"], res["drop final full month"]["point"]
    best_p = max("abc", key=lambda k: m[f"prec_{k}"])
    best_ap = max("abc", key=lambda k: m[f"ap_{k}"])
    n_pos_coef = sum(1 for f in res["main"]["per_fold"] if f["coef_c"][0] > 0)
    pos_2023 = sum(f["test_pos"] for f in res["main"]["per_fold"] if f["test"][:4] == "2023")
    rel = res["main"]["reliability"]
    mean_pred_c = sum(r[2] * r[4] for r in rel) / sum(r[2] for r in rel)
    txt = f"""# B0: baselines for delisting prediction

Built by `research/market_evolution/b0_baselines.py eval` from `delisting_panel.parquet`
(see `delisting_panel.md` for the label, censoring and exclusion rules). Run time
{seconds:.0f} s.

## Dataset

- {df.height:,} rows (life x month), {df['life_id'].n_unique():,} lives,
  {int(df['y3'].sum()):,} positive rows from
  {df.filter(pl.col('y3') == 1)['life_id'].n_unique()} event lives; base rate
  {df['y3'].mean():.4f}.
- Pre-lock-box rows (t <= 2025-12): {df.filter(~pl.col('lockbox')).height:,}, positive rows
  {int(df.filter(~pl.col('lockbox'))['y3'].sum())}.
- **Lock-box: origins {LOCKBOX_START} to {lb['month'].max()} ({lb.height:,} rows) are
  reserved and NOT scored.** Note: origins 2025-10 to 2025-12 have label windows that reach
  2026-01 to 2026-03, so deaths in early 2026 already appear as positives in the last
  pre-lock-box test block.

Base rate by year of t (pre-lock-box):

{_md_table(['year', 'rows', 'positive rows', 'event lives', 'base rate'], year_rows)}

## Validation

Expanding window, monthly origins, 6-month test blocks starting {FIRST_TEST} (6 folds, the
last ending 2025-12). Purge: a training row must have t + 3 < T, the first test month, so
no training label window (t+1..t+3) reaches into the test block. This is one month
stricter than the note's `train_end = T - horizon`, whose last training row has a window
ending in month T. Thresholds, scalers and coefficients come from training rows only.
Censored rows were dropped when the panel was built, so the test set leaves out the last
2 months of lives that are later renamed or merged.

{chr(10).join(sections)}
## What a model must beat (plain language)

- The base rate is {m['base']:.1%} per contract-month on the scored origins: a random 5%
  alert list would be right about {m['base']:.1%} of the time, and a random score has a
  PR-AUC near {m['base']:.3f}.
- Best baseline at the top-5% alert rate: {names[best_p]} with precision
  {m[f'prec_{best_p}']:.1%} and recall {m[f'rec_{best_p}']:.0%} (main run). Best PR-AUC:
  {names[best_ap]}, {m[f'ap_{best_ap}']:.3f}. Those two numbers, with the paired
  month-bootstrap interval of the difference, are the bar for logistic variants, LightGBM
  and any trade-level feature.
- The falling-volume rule (a) is no better than chance here: precision {m['prec_a']:.1%}
  against a base rate of {m['base']:.1%}. Its threshold version flags about
  {m['rule_rate_a']:.0%} of contracts each month and is right {m['rule_prec_a']:.1%} of the
  time. In the logistic fits the coefficient on the 3-month volume change is positive in
  {n_pos_coef} of {len(res['main']['per_fold'])} folds (main run): in recent years volume
  tends to rise, not fall, before a delisting. Market-wide swings in volume and
  announcement or pump spikes are the likely reasons; a within-month rank of the volume
  change would remove the first.
- Small coins die: the level of volume (its rank in the month) carries almost all the
  signal. Adding the volume change and age in (c) does not beat the rank alone; the
  coefficients on those two are small and change sign between folds.
- (c) uses no class weights. On the test rows it predicts {mean_pred_c:.1%} on average
  against an observed {m['base']:.1%}: the delisting rate rose after the training years, so
  it under-predicts in most deciles. Its Brier score barely beats predicting the training
  base rate (skill {m['bss_c']:.3f}).
- Without the final full month before the last trading month (the month most likely to
  contain the announcement), the base rate falls to {s['base']:.1%} and precision to
  {s['prec_a']:.1%} (a), {s['prec_b']:.1%} (b), {s['prec_c']:.1%} (c). The ranking of the
  baselines is unchanged, but part of every score comes from that month, which a live
  model would reach too late to act on. Report both until announcement dates are
  collected.
- Intervals are wide because events come in batches: one delisting wave decides a 6-month
  block (the 2023 blocks have {pos_2023} positive rows in all). Judge differences between methods
  with the paired intervals, not by comparing two separate intervals.
"""
    BASELINE_MD.write_text(txt)


def evaluate() -> dict:
    t0 = time.time()
    df = pl.read_parquet(PANEL_OUT)
    lb = df.filter(pl.col("lockbox"))
    print(f"lock-box RESERVED, not scored: origins {LOCKBOX_START} to {lb['month'].max()}, "
          f"{lb.height} rows")
    res = {"main": evaluate_variant(df, drop_final_full=False),
           "drop final full month": evaluate_variant(df, drop_final_full=True)}
    for label, r in res.items():
        print(f"[{label}] test rows {r['n_rows']}, positives {r['n_pos']}, "
              f"base {r['point']['base']:.4f}")
        for k in ("a", "b", "c"):
            print(f"  ({k}) prec@5% {_ci(r, f'prec_{k}')}  recall {_ci(r, f'rec_{k}')}  "
                  f"PR-AUC {_ci(r, f'ap_{k}')}")
        print(f"  (c) Brier {r['point']['brier_c']:.5f} vs base {r['point']['brier_ref']:.5f}")
    write_baseline_md(df, res, time.time() - t0)
    print(f"wrote {BASELINE_MD.relative_to(ROOT)}")
    return res


# --------------------------------------------------------------------------------------
# Machine-readable output (for the Q16 report). Writes the numbers `evaluate_variant`
# already computes; no modelling choice lives here. `json` stage: pre-lock-box folds only,
# leaves b0_baselines.md untouched.
# --------------------------------------------------------------------------------------

def write_json(res: dict[str, dict], path: Path = BASELINE_JSON) -> None:
    from microstructure.data.jsonio import dumps_strict
    out = {"source": "research/market_evolution/b0_baselines.py",
           "lockbox_start": LOCKBOX_START, "first_test": FIRST_TEST, "test_len": TEST_LEN,
           "alert_rate": ALERT_RATE, "n_boot": N_BOOT, "boot_block": BOOT_BLOCK, "seed": SEED,
           "variants": {}}
    for label, r in res.items():
        out["variants"][label] = {
            "point": r["point"], "ci": {k: list(v) for k, v in r["ci"].items()},
            "alerts_total": r["alerts_total"], "n_rows": r["n_rows"], "n_pos": r["n_pos"],
            "n_months": r["n_months"], "test_events": r["test_events"],
            "months_with_events": r["months_with_events"], "purged_rows": r["purged_rows"],
            "per_fold": r["per_fold"],
        }
    path.write_text(dumps_strict(out) + "\n")


def evaluate_json() -> None:
    df = pl.read_parquet(PANEL_OUT)
    res = {"main": evaluate_variant(df, drop_final_full=False),
           "drop final full month": evaluate_variant(df, drop_final_full=True)}
    write_json(res)
    print(f"wrote {BASELINE_JSON.relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", nargs="?", choices=["build", "eval", "json", "all"],
                    default="all")
    args = ap.parse_args(argv)
    if args.stage in ("build", "all"):
        build()
    if args.stage in ("eval", "all"):
        evaluate()
    if args.stage == "json":
        evaluate_json()


if __name__ == "__main__":
    sys.exit(main())
