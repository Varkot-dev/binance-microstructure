"""Part B: monthly contract panel of every USDT-M perpetual, from cheap archive files.

One row per contract (symbol ending in USDT, no underscore) per calendar month in which
it had any file (1d klines, fundingRate or metrics), from the first archive month to the
latest complete month. Features use only that month's data, except the running peak
close for the drawdown, which uses all months up to and including this one. No labels.

Sources (data.binance.vision, futures/um):
- monthly/klines/{SYM}/1d/: daily OHLCV, quote volume, trades, taker buy volume. If the
  last panel month has no monthly file yet, its daily 1d files are used instead.
- monthly/fundingRate/{SYM}/: every funding event.
- daily/metrics/{SYM}/: ONE file per contract-month only, the last available day of the
  month (usually the last calendar day), to keep downloads bounded. Month-end values are
  the last 5-minute row of that file with a non-null open interest value.

Stages, both resumable:
1. fetch: per contract, list the S3 keys, download each zip with
   `microstructure.data.binance.download` (verifies the published SHA-256), parse it,
   delete the zip, and write data/raw_panel/contracts/{SYM}/{klines,funding,metrics}
   .parquet plus done.json. Contracts with done.json are skipped.
2. build: aggregate to data/panels/monthly_panel.parquet and write the summary
   research/market_evolution/data/monthly_panel.md.

Run from the repository root:
    PYTHONPATH=src .venv/bin/python research/market_evolution/build_monthly_panel.py
Options: --end YYYY-MM (default: last complete month), --workers N (default 6),
--symbols A,B (subset, for trials), --build-only.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import dataclasses
import datetime as dt
import io
import json
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

import httpx
import polars as pl

from microstructure.data.binance import BASE, DAILY_BASE, DumpFile, download

S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
UM = "data/futures/um"
ROOT = Path("data")
RAW = ROOT / "raw_panel"
CONTRACTS = RAW / "contracts"
ZIPS = RAW / "zips"
PANEL_PATH = ROOT / "panels" / "monthly_panel.parquet"
SUMMARY_PATH = Path("research/market_evolution/data/monthly_panel.md")
INVENTORY = ROOT / "universe" / "aggtrades_monthly_inventory.json"
SYMBOL_RE = re.compile(r"^[A-Z0-9]+USDT$")

KLINE_COLS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
    "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore",
]
FUNDING_COLS = ["calc_time", "funding_interval_hours", "last_funding_rate"]
METRIC_COLS = [
    "create_time", "symbol", "sum_open_interest", "sum_open_interest_value",
    "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio",
    "count_long_short_ratio", "sum_taker_long_short_vol_ratio",
]


# --------------------------------------------------------------------------------------
# Archive addressing and listing
# --------------------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class KlineFile(DumpFile):
    """A 1d kline zip: the interval sits in both the folder and the file name."""

    interval: str = "1d"

    @property
    def filename(self) -> str:
        return f"{self.symbol}-{self.interval}-{self.period}.zip"

    @property
    def url(self) -> str:
        return f"{self.base}/klines/{self.symbol}/{self.interval}/{self.filename}"


def list_keys(client: httpx.Client, prefix: str) -> list[tuple[str, int]]:
    """All (key, size) under an S3 prefix, following pagination."""
    out: list[tuple[str, int]] = []
    marker = ""
    while True:
        r = _get(client, S3, params={"prefix": prefix, "marker": marker})
        t = r.text
        blocks = re.findall(r"<Contents>(.*?)</Contents>", t, re.DOTALL)
        for b in blocks:
            k = re.search(r"<Key>([^<]+)</Key>", b).group(1)
            s = int(re.search(r"<Size>(\d+)</Size>", b).group(1))
            out.append((k, s))
        if "<IsTruncated>true</IsTruncated>" not in t or not blocks:
            return out
        marker = out[-1][0]


def list_symbols(client: httpx.Client, prefix: str) -> list[str]:
    out: list[str] = []
    marker = ""
    while True:
        r = _get(client, S3, params={"prefix": prefix, "delimiter": "/", "marker": marker})
        t = r.text
        pfx = [p for p in re.findall(r"<Prefix>([^<]+)</Prefix>", t) if p != prefix]
        out += [p[len(prefix):].rstrip("/") for p in pfx]
        if "<IsTruncated>true</IsTruncated>" not in t or not pfx:
            return sorted(set(out))
        m = re.search(r"<NextMarker>([^<]+)</NextMarker>", t)
        marker = m.group(1) if m else pfx[-1]


def _get(client: httpx.Client, url: str, **kw) -> httpx.Response:
    for attempt in range(4):
        try:
            r = client.get(url, **kw)
            r.raise_for_status()
            return r
        except httpx.HTTPError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def universe(client: httpx.Client) -> list[str]:
    syms: set[str] = set()
    for pfx in (f"{UM}/monthly/klines/", f"{UM}/monthly/fundingRate/", f"{UM}/daily/metrics/"):
        syms |= {s for s in list_symbols(client, pfx) if SYMBOL_RE.match(s)}
    return sorted(syms)


def months_in_keys(keys: list[tuple[str, int]], pattern: str) -> dict[str, int]:
    """period -> zip size, for keys whose file name matches pattern (one capture group).

    Stray keys that do not follow the naming pattern (e.g. part-00000 files) are dropped.
    """
    rx = re.compile(pattern)
    out: dict[str, int] = {}
    for k, s in keys:
        m = rx.search(k)
        if m:
            out[m.group(1)] = s
    return out


# --------------------------------------------------------------------------------------
# Parsing raw files
# --------------------------------------------------------------------------------------

def read_zip_csv(path: Path, columns: list[str]) -> pl.DataFrame:
    """Read the single CSV in a Binance zip, with or without a header row, as strings."""
    with zipfile.ZipFile(path) as zf:
        data = zf.read(zf.namelist()[0])
    if not data.strip():
        return pl.DataFrame(schema={c: pl.Utf8 for c in columns})
    has_header = not data[:1].isdigit()
    df = pl.read_csv(
        io.BytesIO(data), has_header=has_header, new_columns=columns,
        infer_schema=False, truncate_ragged_lines=True,
    )
    return df.select(columns[: df.width])


def _ms_to_datetime(col: pl.Expr) -> pl.Expr:
    # USDT-M files are in ms; guard against microseconds just in case.
    v = col.cast(pl.Int64, strict=False)
    return pl.when(v > 10**14).then(v // 1000).otherwise(v).cast(pl.Datetime("ms"))


def parse_klines(df: pl.DataFrame, symbol: str) -> pl.DataFrame:
    f = pl.Float64
    return (
        df.filter(pl.col("open_time").str.contains(r"^\d+$"))
        .select(
            pl.lit(symbol).alias("symbol"),
            _ms_to_datetime(pl.col("open_time")).dt.date().alias("date"),
            *[pl.col(c).cast(f, strict=False) for c in
              ("open", "high", "low", "close", "volume", "quote_volume",
               "taker_buy_quote_volume")],
            pl.col("count").cast(pl.Int64, strict=False),
        )
        .unique("date", keep="last")
        .sort("date")
    )


def parse_funding(df: pl.DataFrame, symbol: str) -> pl.DataFrame:
    return (
        df.filter(pl.col("calc_time").str.contains(r"^\d+$"))
        .select(
            pl.lit(symbol).alias("symbol"),
            _ms_to_datetime(pl.col("calc_time")).alias("time"),
            pl.col("funding_interval_hours").cast(pl.Float64, strict=False),
            pl.col("last_funding_rate").cast(pl.Float64, strict=False).alias("rate"),
        )
        .unique("time", keep="last")
        .sort("time")
    )


def parse_metrics_last(df: pl.DataFrame, symbol: str, day: str) -> pl.DataFrame:
    """Month-end snapshot from one metrics day: the last row with a non-null OI value."""
    f = pl.Float64
    d = df.select(
        pl.col("create_time").str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False).alias("ts"),
        pl.col("sum_open_interest").cast(f, strict=False).alias("oi"),
        pl.col("sum_open_interest_value").cast(f, strict=False).alias("oi_usd"),
        pl.col("count_long_short_ratio").cast(f, strict=False).alias("ls_account"),
        pl.col("count_toptrader_long_short_ratio").cast(f, strict=False)
        .alias("ls_toptrader_account"),
    ).drop_nulls("ts").sort("ts")
    n = d.height
    d = d.drop_nulls("oi_usd").tail(1)
    if d.height == 0:
        d = pl.DataFrame([[None]] * 5, schema=d.schema, orient="col")
    return d.with_columns(
        pl.lit(symbol).alias("symbol"),
        pl.lit(day).str.to_date().alias("metrics_date"),
        pl.lit(n).alias("metrics_rows"),
    )


# --------------------------------------------------------------------------------------
# Fetch stage
# --------------------------------------------------------------------------------------

def _download_retry(f: DumpFile, dest: Path, client: httpx.Client) -> Path:
    for attempt in range(3):
        try:
            return download(f, dest, client)
        except (httpx.HTTPError, OSError) as e:
            if attempt == 2:
                raise
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                raise
            time.sleep(2 + 3 * attempt)
    raise AssertionError("unreachable")


def fetch_contract(symbol: str, end: str, client: httpx.Client) -> dict:
    out_dir = CONTRACTS / symbol
    if (out_dir / "done.json").exists():
        return json.loads((out_dir / "done.json").read_text())
    t0 = time.time()
    zdir = ZIPS / symbol
    zdir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    kl_keys = list_keys(client, f"{UM}/monthly/klines/{symbol}/1d/")
    fu_keys = list_keys(client, f"{UM}/monthly/fundingRate/{symbol}/")
    me_keys = list_keys(client, f"{UM}/daily/metrics/{symbol}/")
    s = re.escape(symbol)
    kl_m = {m: z for m, z in months_in_keys(kl_keys, rf"/{s}-1d-(\d{{4}}-\d{{2}})\.zip$").items()
            if m <= end}
    fu_m = {m: z for m, z in
            months_in_keys(fu_keys, rf"/{s}-fundingRate-(\d{{4}}-\d{{2}})\.zip$").items()
            if m <= end}
    me_d = {d: z for d, z in
            months_in_keys(me_keys, rf"/{s}-metrics-(\d{{4}}-\d{{2}}-\d{{2}})\.zip$").items()
            if d[:7] <= end}
    me_pick: dict[str, str] = {}
    for d in sorted(me_d):
        me_pick[d[:7]] = d  # last available day of each month wins

    errors: list[str] = []
    nbytes = 0
    nfiles = 0
    kl_parts: list[pl.DataFrame] = []
    fu_parts: list[pl.DataFrame] = []
    me_parts: list[pl.DataFrame] = []

    def grab(f: DumpFile, size: int, cols: list[str]) -> pl.DataFrame | None:
        nonlocal nbytes, nfiles
        try:
            p = _download_retry(f, zdir, client)
        except Exception as e:  # noqa: BLE001, recorded and reported
            errors.append(f"{f.filename}: {type(e).__name__}: {e}"[:300])
            return None
        try:
            df = read_zip_csv(p, cols)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{f.filename}: parse {type(e).__name__}: {e}"[:300])
            df = None
        nbytes += size
        nfiles += 1
        p.unlink(missing_ok=True)
        return df

    for m, size in sorted(kl_m.items()):
        df = grab(KlineFile(symbol, "klines", m), size, KLINE_COLS)
        if df is not None:
            kl_parts.append(parse_klines(df, symbol))

    # Last panel month without a monthly kline file yet: fall back to daily 1d files.
    daily_fallback = []
    if end not in kl_m and (end in fu_m or end in me_pick):
        dk = list_keys(client, f"{UM}/daily/klines/{symbol}/1d/{symbol}-1d-{end}")
        days = months_in_keys(dk, rf"/{s}-1d-(\d{{4}}-\d{{2}}-\d{{2}})\.zip$")
        for d, size in sorted(days.items()):
            f = KlineFile(symbol, "klines", d, base=DAILY_BASE)
            df = grab(f, size, KLINE_COLS)
            if df is not None:
                kl_parts.append(parse_klines(df, symbol))
                daily_fallback.append(d)

    for m, size in sorted(fu_m.items()):
        df = grab(DumpFile(symbol, "fundingRate", m, base=BASE), size, FUNDING_COLS)
        if df is not None:
            fu_parts.append(parse_funding(df, symbol))

    for m, d in sorted(me_pick.items()):
        df = grab(DumpFile(symbol, "metrics", d, base=DAILY_BASE), me_d[d], METRIC_COLS)
        if df is not None:
            me_parts.append(parse_metrics_last(df, symbol, d))

    _write(kl_parts, out_dir / "klines.parquet")
    _write(fu_parts, out_dir / "funding.parquet")
    _write(me_parts, out_dir / "metrics.parquet")
    shutil.rmtree(zdir, ignore_errors=True)
    info = {
        "symbol": symbol, "end": end,
        "kline_months": sorted(kl_m), "funding_months": sorted(fu_m),
        "metrics_days": [me_pick[m] for m in sorted(me_pick)],
        "kline_daily_fallback": daily_fallback,
        "files": nfiles, "bytes": nbytes, "errors": errors,
        "seconds": round(time.time() - t0, 1),
    }
    (out_dir / "done.json").write_text(json.dumps(info))
    return info


def _write(parts: list[pl.DataFrame], path: Path) -> None:
    if parts:
        pl.concat(parts, how="diagonal_relaxed").write_parquet(path)
    elif path.exists():
        path.unlink()


# --------------------------------------------------------------------------------------
# Aggregation (pure functions, tested offline)
# --------------------------------------------------------------------------------------

def _month_str(col: str) -> pl.Expr:
    return pl.col(col).dt.strftime("%Y-%m").alias("month")


def kline_month_features(daily: pl.DataFrame) -> pl.DataFrame:
    """Per symbol-month features from daily klines.

    Input columns: symbol, date, open, high, low, close, volume, quote_volume, count,
    taker_buy_quote_volume. Everything is within the month except the running peak close,
    a cumulative max over the contract's own history up to each day (no future data).
    """
    d = daily.sort("symbol", "date").with_columns(_month_str("date"))
    d = d.with_columns(
        run_peak=pl.col("close").cum_max().over("symbol"),
        prev_close=pl.col("close").shift(1).over("symbol", "month"),
        trading=(pl.col("volume") > 0),
    ).with_columns(
        dd=pl.col("close") / pl.col("run_peak") - 1.0,
        # First day of the month uses its own open as the previous close, so the return
        # never reaches back into last month.
        logret=(pl.col("close") / pl.coalesce("prev_close", "open")).log(),
        range_rel=(pl.col("high") - pl.col("low")) / pl.col("close"),
    )
    g = d.group_by("symbol", "month").agg(
        n_kline_days=pl.len(),
        trading_days=pl.col("trading").sum().cast(pl.Int32),
        first_day=pl.col("date").min(),
        last_day=pl.col("date").max(),
        last_trading_day=pl.col("date").filter(pl.col("trading")).max(),
        quote_volume=pl.col("quote_volume").sum(),
        quote_volume_median=pl.col("quote_volume").median(),
        n_trades=pl.col("count").sum(),
        taker_buy_quote=pl.col("taker_buy_quote_volume").sum(),
        open_first=pl.col("open").first(),
        close_last=pl.col("close").last(),
        realized_vol=pl.col("logret").filter(pl.col("trading")).std(ddof=1),
        mean_range=pl.col("range_rel").filter(pl.col("trading")).mean(),
        dd_month_end=pl.col("dd").last(),
        max_dd=pl.col("dd").min(),
    )
    return g.with_columns(
        taker_buy_share=pl.when(pl.col("quote_volume") > 0)
        .then(pl.col("taker_buy_quote") / pl.col("quote_volume")),
        avg_trade_usd=pl.when(pl.col("n_trades") > 0)
        .then(pl.col("quote_volume") / pl.col("n_trades")),
        ret_month=pl.col("close_last") / pl.col("open_first") - 1.0,
    ).drop("taker_buy_quote").sort("symbol", "month")


def funding_month_features(funding: pl.DataFrame) -> pl.DataFrame:
    """Input: symbol, time, funding_interval_hours, rate."""
    return (
        funding.with_columns(_month_str("time"))
        .group_by("symbol", "month")
        .agg(
            n_funding=pl.len(),
            funding_mean=pl.col("rate").mean(),
            funding_abs_mean=pl.col("rate").abs().mean(),
            funding_interval_min_h=pl.col("funding_interval_hours").min(),
        )
        .sort("symbol", "month")
    )


def metrics_month_features(snap: pl.DataFrame) -> pl.DataFrame:
    """Input: one row per symbol-month, from parse_metrics_last."""
    return (
        snap.with_columns(_month_str("metrics_date"))
        .select(
            "symbol", "month", "metrics_date", "metrics_rows",
            pl.col("ts").alias("metrics_ts"),
            pl.col("oi_usd").alias("oi_usd_month_end"),
            pl.col("ls_account").alias("ls_account_month_end"),
            pl.col("ls_toptrader_account").alias("ls_toptrader_account_month_end"),
        )
        .unique(["symbol", "month"], keep="last")
        .sort("symbol", "month")
    )


def assemble_panel(kl: pl.DataFrame, fu: pl.DataFrame, me: pl.DataFrame) -> pl.DataFrame:
    """Outer-join the three sources on (symbol, month); add coverage and ghost flags."""
    keys = pl.concat([x.select("symbol", "month") for x in (kl, fu, me)]).unique()
    p = (
        keys.join(kl, on=["symbol", "month"], how="left")
        .join(fu, on=["symbol", "month"], how="left")
        .join(me, on=["symbol", "month"], how="left")
    )
    mdate = (pl.col("month") + "-01").str.to_date()
    p = p.with_columns(
        has_klines=pl.col("n_kline_days").is_not_null(),
        has_funding=pl.col("n_funding").is_not_null(),
        has_metrics=pl.col("metrics_date").is_not_null(),
        days_in_month=mdate.dt.month_end().dt.day().cast(pl.Int32),
    ).with_columns(
        trading_days=pl.col("trading_days").fill_null(0),
        missing_kline_days=pl.col("days_in_month") - pl.col("n_kline_days").fill_null(0),
        # Ghost month: some file exists but nothing traded (volume 0 every day, or no
        # kline file at all while funding or metrics files keep appearing).
        ghost_month=pl.col("trading_days").fill_null(0) == 0,
        metrics_is_last_day=pl.col("metrics_date").dt.day() == pl.col("days_in_month"),
    )
    p = p.sort("symbol", "month").with_columns(
        age_months=pl.col("month").cum_count().over("symbol") - 1,
    )
    order = [
        "symbol", "month", "age_months", "has_klines", "has_funding", "has_metrics",
        "ghost_month", "days_in_month", "n_kline_days", "missing_kline_days",
        "trading_days", "first_day", "last_day", "last_trading_day",
        "quote_volume", "quote_volume_median", "n_trades", "avg_trade_usd",
        "taker_buy_share", "open_first", "close_last", "ret_month", "realized_vol",
        "mean_range", "dd_month_end", "max_dd", "oi_usd_month_end",
        "ls_account_month_end", "ls_toptrader_account_month_end", "metrics_date",
        "metrics_ts", "metrics_rows", "metrics_is_last_day", "n_funding", "funding_mean",
        "funding_abs_mean", "funding_interval_min_h",
    ]
    return p.select([c for c in order if c in p.columns])


# --------------------------------------------------------------------------------------
# Build stage and summary
# --------------------------------------------------------------------------------------

def _load(name: str, symbols: list[str]) -> pl.DataFrame:
    paths = [CONTRACTS / s / f"{name}.parquet" for s in symbols]
    paths = [p for p in paths if p.exists()]
    return pl.concat([pl.read_parquet(p) for p in paths], how="diagonal_relaxed")


def build(symbols: list[str], stats: dict) -> pl.DataFrame:
    kl = kline_month_features(_load("klines", symbols))
    fu = funding_month_features(_load("funding", symbols))
    me = metrics_month_features(_load("metrics", symbols))
    panel = assemble_panel(kl, fu, me)
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    panel.write_parquet(PANEL_PATH)
    write_summary(panel, stats)
    return panel


COLUMN_DOCS = [
    ("symbol", "", "contract, ends in USDT, no underscore"),
    ("month", "YYYY-MM", "calendar month (UTC)"),
    ("age_months", "months", "months since the contract's first panel row (0 = first)"),
    ("has_klines / has_funding / has_metrics", "bool", "a file of that type exists"),
    ("ghost_month", "bool", "files exist but no day with volume > 0 (incl. no kline file)"),
    ("days_in_month", "days", "calendar days"),
    ("n_kline_days", "days", "daily kline rows in the month"),
    ("missing_kline_days", "days", "days_in_month minus n_kline_days (listing, gaps, end)"),
    ("trading_days", "days", "daily rows with volume > 0"),
    ("first_day, last_day, last_trading_day", "date", ("first/last kline day; last day "
     "with volume > 0")),
    ("quote_volume", "USDT", "sum of daily quote volume"),
    ("quote_volume_median", "USDT/day", ("median over the month's kline days (zero days "
     "included)")),
    ("n_trades", "trades", "sum of daily `count`"),
    ("avg_trade_usd", "USDT", "quote_volume / n_trades"),
    ("taker_buy_share", "fraction", "taker buy quote volume / quote volume"),
    ("open_first, close_last", "USDT", "open of the first kline day, close of the last"),
    ("ret_month", "fraction", ("close_last / open_first - 1 (the first day's open is the "
     "previous close on a continuous contract)")),
    ("realized_vol", "log return/day", ("std (ddof 1) of daily close-to-close log returns on "
     "days with volume > 0; the month's first day uses its own open, so no prior-month data")),
    ("mean_range", "fraction", "mean (high - low) / close on days with volume > 0"),
    ("dd_month_end", "fraction <= 0", ("month-end close / running peak close - 1; the "
     "running peak is the max daily close from the first kline day up to that day")),
    ("max_dd", "fraction <= 0", "worst daily close / running peak - 1 within the month"),
    ("oi_usd_month_end", "USDT", ("sum_open_interest_value, last 5-min row with OI of the "
     "metrics day used (0 in ghost months)")),
    ("ls_account_month_end", "ratio", "count_long_short_ratio (all accounts), same row"),
    ("ls_toptrader_account_month_end", "ratio", "count_toptrader_long_short_ratio, same row"),
    ("metrics_date, metrics_ts, metrics_rows", "date, datetime, rows", ("metrics day used "
     "(last available day of the month), its row time, rows in that file")),
    ("metrics_is_last_day", "bool", "metrics_date is the calendar month-end"),
    ("n_funding", "events", "funding events in the month"),
    ("funding_mean, funding_abs_mean", "rate per interval", ("mean and mean absolute "
     "`last_funding_rate` (0.0001 = 1 bp; ghost months show the constant default)")),
    ("funding_interval_min_h", "hours", "shortest funding interval seen in the month"),
]


def write_summary(panel: pl.DataFrame, stats: dict) -> None:
    n = panel.height
    nsym = panel["symbol"].n_unique()
    ghost = int(panel["ghost_month"].sum())
    by_month = (
        panel.group_by("month")
        .agg(
            contracts=pl.len(),
            trading=(~pl.col("ghost_month")).sum(),
            ghost=pl.col("ghost_month").sum(),
            with_metrics=pl.col("has_metrics").sum(),
            with_funding=pl.col("has_funding").sum(),
        )
        .sort("month")
    )
    lines = [
        "# Monthly contract panel (Part B)",
        "",
        ("Built by `research/market_evolution/build_monthly_panel.py`; the parquet is "
        "`data/panels/monthly_panel.parquet` (git-ignored). One row per USDT-M perpetual "
        "(symbol ends in USDT, no underscore) per calendar month with any 1d kline, "
        "fundingRate or metrics file. No labels: join the lifecycle table later. "
        "Features use only that month's data, except the running peak close behind the "
        "drawdowns (history up to and including the month)."),
        "",
        ("Metrics are subsampled: ONE daily metrics file per contract-month, the last "
        "available day of that month. Month-end OI and long/short ratios come from its "
        "last 5-minute row with a non-null OI. Metrics start 2021-12 for most contracts "
        "(BTCUSDT 2020-09); earlier months have nulls, not zeros."),
        "",
        ("Ghost rows: klines, funding and metrics keep publishing files after a contract "
        "stops trading (flat prices, volume 0, OI 0, funding 0.0001). They are kept and "
        "flagged with `ghost_month`; do not use the last file as the delisting date."),
        "",
        "## Build",
        "",
        f"- Built {stats.get('built_at', '')}, panel end month {stats.get('end', '')}.",
        (f"- Rows: {n:,}; contracts: {nsym}; months: {panel['month'].min()} to "
        f"{panel['month'].max()} ({panel['month'].n_unique()} months)."),
        (f"- Ghost months: {ghost:,} ({ghost / n:.1%} of rows); rows with klines but no "
        f"trading: {int((panel['has_klines'] & panel['ghost_month']).sum()):,}; rows "
        f"without any kline file: {int((~panel['has_klines']).sum()):,}."),
        (f"- Rows with metrics: {int(panel['has_metrics'].sum()):,}; metrics day is the "
        f"calendar month-end in {int(panel['metrics_is_last_day'].fill_null(False).sum()):,}"
        " of them."),
        (f"- Downloaded: {stats.get('files', 0):,} zips, {stats.get('bytes', 0) / 1e6:.1f} MB "
        f"(klines {stats.get('kline_files', 0):,}, funding {stats.get('funding_files', 0):,},"
        f" metrics {stats.get('metrics_files', 0):,}); each checked against its published "
        "SHA-256, zips deleted after parsing."),
        (f"- Build time: fetch {stats.get('fetch_seconds', 0) / 60:.1f} min (summed over "
        f"runs, {stats.get('workers', '')} workers), aggregation "
        f"{stats.get('build_seconds', 0):.1f} s."),
        f"- Download errors: {stats.get('n_errors', 0)}.",
    ]
    for note in stats.get("notes", []):
        lines.append(f"- {note}")
    lines += ["", "## Columns", "", "| column | unit | definition |", "|---|---|---|"]
    lines += [f"| `{c}` | {u} | {d} |" for c, u, d in COLUMN_DOCS]
    lines += [
        "", "## Coverage by month", "",
        "| month | contracts | trading | ghost | with metrics | with funding |",
        "|---|---|---|---|---|---|",
    ]
    for r in by_month.iter_rows(named=True):
        lines.append(f"| {r['month']} | {r['contracts']} | {r['trading']} | {r['ghost']} | "
                     f"{r['with_metrics']} | {r['with_funding']} |")
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text("\n".join(lines) + "\n")


def last_complete_month(today: dt.date | None = None) -> str:
    today = today or dt.datetime.now(dt.UTC).date()
    first = today.replace(day=1)
    prev = first - dt.timedelta(days=1)
    return f"{prev.year:04d}-{prev.month:02d}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default=last_complete_month())
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--symbols", default="")
    ap.add_argument("--build-only", action="store_true")
    a = ap.parse_args()
    CONTRACTS.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=60, limits=httpx.Limits(max_connections=a.workers + 2))

    uni_path = RAW / f"universe_{a.end}.json"
    if a.symbols:
        symbols = a.symbols.split(",")
    elif uni_path.exists():
        symbols = json.loads(uni_path.read_text())
    else:
        symbols = universe(client)
        uni_path.write_text(json.dumps(symbols))
    print(f"{len(symbols)} symbols, end {a.end}", file=sys.stderr)

    infos: list[dict] = []
    if not a.build_only:
        todo = [s for s in symbols if not (CONTRACTS / s / "done.json").exists()]
        print(f"{len(todo)} to fetch", file=sys.stderr)
        with cf.ThreadPoolExecutor(a.workers) as ex:
            futs = {ex.submit(fetch_contract, s, a.end, client): s for s in todo}
            for i, fut in enumerate(cf.as_completed(futs), 1):
                s = futs[fut]
                try:
                    info = fut.result()
                    print(f"[{i}/{len(todo)}] {s} files={info['files']} "
                          f"err={len(info['errors'])} {info['seconds']}s",
                          file=sys.stderr, flush=True)
                except Exception as e:  # noqa: BLE001
                    print(f"[{i}/{len(todo)}] {s} FAILED {e}", file=sys.stderr, flush=True)
    for s in symbols:
        p = CONTRACTS / s / "done.json"
        if p.exists():
            infos.append(json.loads(p.read_text()))
    missing = sorted(set(symbols) - {i["symbol"] for i in infos})

    t0 = time.time()
    stats = {
        "built_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "end": a.end, "workers": a.workers,
        "files": sum(i["files"] for i in infos),
        "bytes": sum(i["bytes"] for i in infos),
        "kline_files": sum(len(i["kline_months"]) + len(i["kline_daily_fallback"])
                           for i in infos),
        "funding_files": sum(len(i["funding_months"]) for i in infos),
        "metrics_files": sum(len(i["metrics_days"]) for i in infos),
        "fetch_seconds": sum(i["seconds"] for i in infos),
        "n_errors": sum(len(i["errors"]) for i in infos),
        "notes": [],
    }
    if missing:
        stats["notes"].append(f"Contracts not fetched: {', '.join(missing)}.")
    fb = [i["symbol"] for i in infos if i["kline_daily_fallback"]]
    if fb:
        stats["notes"].append(f"Daily 1d klines used for {a.end} (no monthly file yet): "
                              f"{', '.join(fb)}.")
    if INVENTORY.exists():
        inv = json.loads(INVENTORY.read_text())
        no_agg = sorted(i["symbol"] for i in infos if i["kline_months"] and i["symbol"]
                        not in inv)
        stats["notes"].append(
            f"{len(no_agg)} contracts have 1d klines but are absent from the aggTrades "
            f"inventory (`data/universe/aggtrades_monthly_inventory.json`)"
            + (f": {', '.join(no_agg)}." if no_agg and len(no_agg) <= 40 else ".")
        )
    no_kl = sorted(i["symbol"] for i in infos if not i["kline_months"]
                   and not i["kline_daily_fallback"])
    if no_kl:
        stats["notes"].append(f"{len(no_kl)} contracts have funding or metrics files but no "
                              f"1d klines: {', '.join(no_kl[:40])}.")
    errs = [e for i in infos for e in i["errors"]]
    if errs:
        stats["notes"].append("First errors: " + "; ".join(errs[:5]))
    stats["build_seconds"] = 0.0
    panel = build([i["symbol"] for i in infos], stats)
    stats["build_seconds"] = time.time() - t0
    write_summary(panel, stats)
    (RAW / "build_stats.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps({k: v for k, v in stats.items() if k != "notes"}), file=sys.stderr)


if __name__ == "__main__":
    main()
