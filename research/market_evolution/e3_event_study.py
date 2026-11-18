"""E3: does a tick-size change cause a change in trade-sign predictability?

Natural experiment for Part A (README weeks 5 to 6). Treated contracts had a verified
10x tick change at one minute (`data/tick_events.csv`); controls are the
activity-matched contracts with no tick change within +/- 30 days
(`data/tick_event_controls.csv`). For every contract and every day from 21 days
before to 21 days after the event (the event day itself is skipped), one daily
aggTrades file is downloaded (SHA-256 checked), turned into aggressor events, and
reduced to one row of numbers per contract-day:

- Predictability. A logistic regression on the last 10 signs and 4 sign EWMAs
  (half-lives 4, 16, 64, 256 events), fitted per contract on relative days -21 to -11
  only and then frozen, scores every later day (-10 to -1 and +1 to +21). Events tied
  in time with the previous event are never scored (as in Q9), nor are the first
  1,024 events of each day (EWMA warm-up; features restart every day). Also the
  persistence accuracy (next sign = last sign) on the same events, the lag-1 sign
  autocorrelation and the sign repeat rate (descriptive, near-circular).
- Mechanisms (proxy library): median trade size in USD, share of same-sign runs of
  10 or more with sweeps merged, unchanged-price share (raw records), events per day,
  relative tick.

Expected signs, fixed before looking (a CUT lowers the relative tick; across
contracts and over time a smaller relative tick goes with HIGHER predictability):
accuracy, excess accuracy, lag-1 autocorrelation, repeat rate and long runs up;
median trade size down; unchanged-price share down (partly mechanical: a finer grid);
relative tick down (the treatment itself). Events per day: no prediction.

Analysis: two-way fixed effects (contract and day) difference in differences with
standard errors clustered by contract, a wild cluster bootstrap (restricted, Webb
weights, on the FWL-transformed data) and a permutation test that reassigns treatment
among all treated and control contracts; CIs for the last two by test inversion. An
event study (day -1 as reference) and a joint F-test of the pre-event coefficients
check pre-trends. numpy only (pyfixest is not installed in this environment).

Resumable: per contract-day summaries are cached as JSON under
data/event_study/<event>/<symbol>/<date>.json and the fitted models under
data/event_study/<event>/models/; zips and parquet files are deleted after use.

    PYTHONPATH=src .venv/bin/python research/market_evolution/e3_event_study.py run --event 2026-03-05
    PYTHONPATH=src .venv/bin/python research/market_evolution/e3_event_study.py analyze
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import csv
import datetime as dt
import json
import math
import shutil
import sys
import threading
import uuid
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "research" / "market_evolution" / "data"
CACHE = ROOT / "data" / "event_study"
INVENTORY = ROOT / "data" / "universe" / "aggtrades_monthly_inventory.json"

WINDOW = 21
TRAIN_REL = tuple(range(-21, -10))  # days -21..-11: the only days the model sees
SCORE_REL = tuple(r for r in range(-10, WINDOW + 1) if r != 0)
REF_DAY = -1
N_LAGS = 10
HALF_LIVES = (4, 16, 64, 256)
WARMUP = 1024
TRAIN_ROWS_PER_DAY = 40_000
REFIT_ROWS = 100_000
MS_PER_DAY = 86_400_000
SUMMARY_VERSION = 2
MIN_TRAIN_DAYS = 3
HARD_CAP = 3.0e9  # bytes downloaded, all events and runs
WORKERS = 4
PREFETCH = 6  # downloads ahead of the (single) compute thread
B_WILD = 9999
B_PERM = 4999
SEED = 20260305

EVENTS = {
    "2026-03-05": {"label": "2026-03-05 cut (12 contracts)", "direction": "cut",
                   "max_rank": 6, "role": "primary"},
    "2024-09-20": {"label": "2024-09-20 cut (10 of 12 contracts)", "direction": "cut",
                   "max_rank": 1, "role": "replication",
                   # the two largest treated contracts (and their rank-1 controls, TON and
                   # 1000BONK) are left out to fit the 3 GB download budget
                   "exclude": ("APTUSDT", "TURBOUSDT")},
    "2024-10-14": {"label": "SOLUSDT 2024-10-14 increase", "direction": "increase",
                   "max_rank": 6, "role": "single contract"},
}

# days between the notice and the change (2026-03-05 notice published on 2026-03-02)
ANNOUNCE_REL = {"2026-03-05": (-3, -2, -1)}

# outcome key -> (summary field transform, label, unit, expected sign after a CUT)
OUTCOMES = {
    "acc_logit": ("accuracy, frozen logistic model", "pp", +1),
    "excess_acc": ("accuracy minus persistence accuracy", "pp", +1),
    "acc_refit": ("accuracy, same-day refit (hours 12-24)", "pp", +1),
    "refit_excess": ("same-day refit minus persistence (hours 12-24)", "pp", +1),
    "sign_acf_lag1": ("lag-1 sign autocorrelation (descriptive)", "x100", +1),
    "repeat_rate": ("sign repeat rate (descriptive)", "pp", +1),
    "log_size": ("median trade size in USD", "log points", -1),
    "long_runs": ("share of same-sign runs >= 10, sweeps merged", "pp", +1),
    "unchanged": ("unchanged-price share (raw records)", "pp", -1),
    "log_events": ("aggressor events per day", "log points", 0),
    "log_rel_tick": ("relative tick", "log points", -1),
}
PREDICTABILITY = ("acc_logit", "excess_acc", "acc_refit", "refit_excess", "sign_acf_lag1",
                  "repeat_rate")


# ---------------------------------------------------------------------------- design

def rel_dates(event: str) -> dict[int, str]:
    e = dt.date.fromisoformat(event)
    return {r: (e + dt.timedelta(days=r)).isoformat()
            for r in range(-WINDOW, WINDOW + 1) if r != 0}


def role_of(rel: int) -> str:
    if rel in TRAIN_REL:
        return "train"
    if rel in SCORE_REL:
        return "score"
    raise ValueError(f"relative day {rel} is outside the design")


def contracts(event: str, max_rank: int | None = None) -> tuple[list[str], list[str]]:
    """Treated and control symbols for an event (controls up to max_rank, unique)."""
    max_rank = EVENTS[event]["max_rank"] if max_rank is None else max_rank
    with (OUT / "tick_events.csv").open() as fh:
        treated = sorted({r["symbol"] for r in csv.DictReader(fh)
                          if r["event"] == event and r["status"] == "verified"}
                         - set(EVENTS[event].get("exclude", ())))
    ctrl: list[str] = []
    with (OUT / "tick_event_controls.csv").open() as fh:
        rows = [r for r in csv.DictReader(fh)
                if r["event_date"] == event and r["treated_symbol"] in treated]
    for r in sorted(rows, key=lambda r: (int(r["rank"]), r["treated_symbol"])):
        s = r["control_symbol"]
        if int(r["rank"]) <= max_rank and s not in ctrl and s not in treated:
            ctrl.append(s)
    return treated, sorted(ctrl)


def planned_bytes(event: str, symbols: list[str]) -> float:
    """Rough download size from the monthly archive inventory (pro rata by day)."""
    inv = json.loads(INVENTORY.read_text())
    tot = 0.0
    for d in rel_dates(event).values():
        y, m = int(d[:4]), int(d[5:7])
        ndays = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.date(y, m, 1)).days
        for s in symbols:
            tot += inv.get(s, {}).get(d[:7], 0) / ndays
    return tot


# ---------------------------------------------------------------------------- features

def ewma_state(x: np.ndarray, half_life: float) -> np.ndarray:
    from microstructure.ml.features import ewma

    return ewma(x, half_life)


def sign_features(signs: np.ndarray) -> np.ndarray:
    """Row i: signs i-1..i-10 and the sign EWMAs after event i-1 (NaN without history)."""
    s = signs.astype(np.float64)
    n = s.size
    cols = []
    for k in range(1, N_LAGS + 1):
        c = np.full(n, np.nan)
        c[k:] = s[:-k]
        cols.append(c)
    for h in HALF_LIVES:
        st = ewma_state(s, h)
        c = np.full(n, np.nan)
        c[1:] = st[:-1]
        cols.append(c)
    return np.column_stack(cols)


def scoreable_mask(ts_ms: np.ndarray) -> np.ndarray:
    """Past the warm-up and not tied with the previous event's millisecond (Q9 rule)."""
    ok = np.ones(ts_ms.size, dtype=bool)
    ok[1:] = ts_ms[1:] != ts_ms[:-1]
    ok[:WARMUP] = False
    return ok


def fit_contract_model(samples: dict[int, tuple[np.ndarray, np.ndarray]]) -> dict | None:
    """Fit the frozen logistic model on training days only.

    `samples` maps relative day -> (X, y). Days outside TRAIN_REL are ignored, so a
    post-event day can never enter the fit even if a caller passes one.
    """
    from sklearn.linear_model import LogisticRegression

    use = {r: v for r, v in samples.items() if r in TRAIN_REL and len(v[1])}
    if len(use) < MIN_TRAIN_DAYS:
        return None
    X = np.vstack([use[r][0] for r in sorted(use)]).astype(np.float64)
    y = np.concatenate([use[r][1] for r in sorted(use)]).astype(np.int64)
    if np.unique(y).size < 2:
        return None
    m = LogisticRegression(C=1.0, max_iter=500).fit(X, y)
    return {"coef": m.coef_[0].tolist(), "intercept": float(m.intercept_[0]),
            "train_days": sorted(use), "n_train": int(y.size)}


def model_accuracy(model: dict, X: np.ndarray, y: np.ndarray) -> float:
    z = X @ np.asarray(model["coef"]) + model["intercept"]
    return float(((z > 0).astype(np.int64) == y).mean())


def same_day_refit(ts_ms, X, y, prev, model, rng) -> dict:
    """Same-day refit: fit on scored events of UTC hours 0-12, score hours 12-24.

    A separate outcome from the frozen model: it adapts to the regime in force that day
    (so after the event it does use post-event data, but only earlier hours of the same
    day, never later days). The frozen model and persistence are scored on the same
    second half for comparison.
    """
    from sklearn.linear_model import LogisticRegression

    h2 = (ts_ms % MS_PER_DAY) >= MS_PER_DAY // 2
    tr, te = np.flatnonzero(~h2), np.flatnonzero(h2)
    if tr.size < 500 or te.size < 500 or np.unique(y[tr]).size < 2:
        return {}
    if tr.size > REFIT_ROWS:
        tr = np.sort(rng.choice(tr, size=REFIT_ROWS, replace=False))
    m = LogisticRegression(C=1.0, max_iter=500).fit(X[tr], y[tr])
    out = {"acc_refit": float((m.predict(X[te]) == y[te]).mean()),
           "acc_persist_h2": float((prev[te] == np.where(y[te] == 1, 1, -1)).mean()),
           "n_h2": int(te.size)}
    if model is not None:
        out["acc_logit_h2"] = model_accuracy(model, X[te], y[te])
    return out


# ---------------------------------------------------------------------------- one day

def day_stats(raw, rng: np.random.Generator, model: dict | None, want_train: bool):
    """Summary of one contract-day of raw aggTrades; optionally a training sample."""
    from microstructure.data.events import to_aggressor_events
    from microstructure.evolution import proxies as px

    ev = to_aggressor_events(raw)
    ts = ev["ts"].dt.epoch("ms").to_numpy().astype(np.int64)
    sign = ev["sign"].to_numpy().astype(np.int64)
    out: dict = {"n_records": int(raw.height), "n_events": int(ev.height)}
    tied = np.zeros(ts.size, dtype=bool)
    tied[1:] = ts[1:] == ts[:-1]
    out["tie_share"] = float(tied.mean())
    out |= px.trade_size(ev)
    out |= px.sign_runs(ev)
    out |= px.near_circular(ev)
    try:
        out |= px.relative_tick(ev, raw)
    except ValueError:
        out |= {"tick": None, "rel_tick_bps": None, "unchanged_price_share": None}
    sc = scoreable_mask(ts)
    out["n_scored"] = int(sc.sum())
    sample = None
    if sc.sum() >= 200:
        X = sign_features(sign)[sc]
        y = (sign[sc] > 0).astype(np.int64)
        prev = sign[np.flatnonzero(sc) - 1]
        out["acc_persist"] = float((prev == sign[sc]).mean())
        out["share_buy"] = float(y.mean())
        if model is not None:
            out["acc_logit"] = model_accuracy(model, X, y)
        out |= same_day_refit(ts[sc], X, y, prev, model, rng)
        if want_train:
            k = min(TRAIN_ROWS_PER_DAY, y.size)
            pick = np.sort(rng.choice(y.size, size=k, replace=False))
            sample = (X[pick].astype(np.float32), y[pick].astype(np.uint8))
    return out, sample


# ---------------------------------------------------------------------------- I/O

class Ledger:
    def __init__(self, path: Path):
        self.path, self.lock = path, threading.Lock()
        self.files: dict[str, int] = json.loads(path.read_text()) if path.exists() else {}

    @property
    def total(self) -> int:
        return sum(self.files.values())

    def add(self, name: str, size: int) -> None:
        """Cumulative: a file downloaded twice counts twice."""
        with self.lock:
            self.files[name] = self.files.get(name, 0) + size
            self.path.write_text(json.dumps(self.files))


_CLIENT = None


def _client():
    global _CLIENT
    if _CLIENT is None:
        import httpx

        _CLIENT = httpx.Client(timeout=180, limits=httpx.Limits(max_connections=WORKERS + 2))
    return _CLIENT


def fetch_day(symbol: str, day: str, ledger: Ledger) -> tuple[Path | None, Path | None]:
    """Download one daily aggTrades zip into a fresh folder; (None, None) if absent."""
    import httpx

    from microstructure.data.binance import DAILY_BASE, DumpFile, download

    if ledger.total > HARD_CAP:
        raise RuntimeError(f"download cap reached: {ledger.total / 1e9:.2f} GB")
    tmp = CACHE / "_tmp" / uuid.uuid4().hex
    tmp.mkdir(parents=True)
    f = DumpFile(symbol, "aggTrades", day, base=DAILY_BASE)
    for attempt in range(3):
        try:
            path = download(f, tmp, _client())
            ledger.add(f.filename, path.stat().st_size)
            return path, tmp
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404):
                shutil.rmtree(tmp, ignore_errors=True)
                return None, None
            err = e
        except (httpx.TransportError, OSError) as e:  # retry transient failures
            err = e
        if attempt == 2:
            shutil.rmtree(tmp, ignore_errors=True)
            raise err
    return None, None


def _summary_path(event: str, symbol: str, day: str) -> Path:
    return CACHE / event / symbol / f"{day}.json"


def _model_path(event: str, symbol: str) -> Path:
    return CACHE / event / "models" / f"{symbol}.json"


def _train_path(event: str, symbol: str, day: str) -> Path:
    return CACHE / "_train" / event / symbol / f"{day}.npz"


def run_event(event: str, max_rank: int | None = None) -> None:
    import polars as pl

    from microstructure.data.ingest import ingest_agg_trades

    treated, ctrl = contracts(event, max_rank)
    syms = treated + ctrl
    ledger = Ledger(CACHE / "ledger.json")
    print(f"[{event}] {len(treated)} treated, {len(ctrl)} controls; planned about "
          f"{planned_bytes(event, syms) / 1e9:.2f} GB; downloaded so far "
          f"{ledger.total / 1e9:.2f} GB", flush=True)
    dates = rel_dates(event)
    order = sorted(dates, key=lambda r: (role_of(r) != "train", r))
    jobs = [(s, r) for s in syms for r in order]

    def needed(s: str, r: int) -> bool:
        p = _summary_path(event, s, dates[r])
        if not p.exists():
            return True
        rec = json.loads(p.read_text())
        if rec.get("present") and rec.get("v", 1) < SUMMARY_VERSION:
            return True
        # a scored day computed before its model existed is redone once the model exists
        return (role_of(r) == "score" and rec.get("present") and "acc_logit" not in rec
                and _model_path(event, s).exists() and not rec.get("no_model"))

    models: dict[str, dict | None] = {}

    def model_for(s: str) -> dict | None:
        if s in models:
            return models[s]
        mp = _model_path(event, s)
        if mp.exists():
            models[s] = json.loads(mp.read_text()) or None
            return models[s]
        samples = {}
        for r in TRAIN_REL:
            tp = _train_path(event, s, dates[r])
            if tp.exists():
                z = np.load(tp)
                samples[r] = (z["X"], z["y"])
        m = fit_contract_model(samples)
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(json.dumps(m or {}))
        shutil.rmtree(CACHE / "_train" / event / s, ignore_errors=True)
        models[s] = m
        print(f"  model {s}: {'none' if m is None else str(len(m['train_days'])) + ' days'}",
              flush=True)
        return m

    todo = [(s, r) for s, r in jobs if needed(s, r)]
    print(f"[{event}] {len(todo)} of {len(jobs)} contract-days to compute", flush=True)
    q: collections.deque = collections.deque()
    it = iter(todo)
    done = 0
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        def refill():
            while len(q) < PREFETCH:
                try:
                    s, r = next(it)
                except StopIteration:
                    return
                q.append((s, r, ex.submit(fetch_day, s, dates[r], ledger)))

        refill()
        while q:
            s, r, fut = q.popleft()
            refill()
            day = dates[r]
            zp, tmp = fut.result()
            rec: dict = {"symbol": s, "date": day, "rel": r, "role": role_of(r),
                         "v": SUMMARY_VERSION}
            try:
                if zp is None:
                    rec["present"] = False
                else:
                    model = model_for(s) if role_of(r) == "score" else None
                    pq = ingest_agg_trades(zp, tmp)
                    zp.unlink()
                    raw = pl.read_parquet(pq)
                    pq.unlink()
                    rng = np.random.default_rng([SEED, zlib.crc32(f"{s}|{day}".encode())])
                    stats, sample = day_stats(raw, rng, model, role_of(r) == "train")
                    del raw
                    rec |= {"present": True, **stats}
                    if role_of(r) == "score" and model is None:
                        rec["no_model"] = True
                    if sample is not None and not _model_path(event, s).exists():
                        tp = _train_path(event, s, day)
                        tp.parent.mkdir(parents=True, exist_ok=True)
                        np.savez_compressed(tp, X=sample[0], y=sample[1])
            finally:
                if tmp is not None:
                    shutil.rmtree(tmp, ignore_errors=True)
            p = _summary_path(event, s, day)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(rec))
            done += 1
            if done % 50 == 0:
                print(f"[{event}] {done}/{len(todo)} done, {ledger.total / 1e9:.2f} GB "
                      "downloaded in total", flush=True)
    for s in syms:  # contracts whose train days were all cached but no model yet
        model_for(s)
    print(f"[{event}] finished; {ledger.total / 1e9:.2f} GB downloaded in total", flush=True)


# ---------------------------------------------------------------------------- panel

def load_panel(event: str, max_rank: int | None = None) -> list[dict]:
    treated, ctrl = contracts(event, max_rank)
    rows = []
    for s in treated + ctrl:
        for r, day in rel_dates(event).items():
            p = _summary_path(event, s, day)
            if not p.exists():
                continue
            rec = json.loads(p.read_text())
            if not rec.get("present"):
                continue
            row = {"event": event, "symbol": s, "treated": int(s in treated), "rel": r,
                   "date": day}
            row |= outcome_values(rec)
            rows.append(row)
    return rows


def _f(x) -> float:
    return float("nan") if x is None else float(x)


def outcome_values(rec: dict) -> dict:
    acc, per = _f(rec.get("acc_logit")), _f(rec.get("acc_persist"))
    rt = _f(rec.get("rel_tick_bps"))
    return {
        "acc_logit": 100 * acc,
        "excess_acc": 100 * (acc - per),
        "acc_refit": 100 * _f(rec.get("acc_refit")),
        "refit_excess": 100 * (_f(rec.get("acc_refit")) - _f(rec.get("acc_persist_h2"))),
        "sign_acf_lag1": 100 * _f(rec.get("sign_acf_lag1")),
        "repeat_rate": 100 * _f(rec.get("sign_repeat_rate")),
        "log_size": math.log(rec["median_notional_usd"]),
        "long_runs": 100 * _f(rec.get("run_share_ge10_sweeps_merged")),
        "unchanged": 100 * _f(rec.get("unchanged_price_share")),
        "log_events": math.log(rec["n_events"]),
        "log_rel_tick": math.log(rt) if rt > 0 else float("nan"),
        "n_scored": rec.get("n_scored", 0),
        "tie_share": rec.get("tie_share"),
        "acc_persist": 100 * per,
    }


# ---------------------------------------------------------------------------- estimators

def demean2(M: np.ndarray, g1: np.ndarray, g2: np.ndarray, tol: float = 1e-12,
            maxit: int = 2000) -> np.ndarray:
    """Residuals of each column of M on two sets of fixed effects (alternating projections)."""
    M = np.array(M, dtype=np.float64, copy=True)
    vec = M.ndim == 1
    if vec:
        M = M[:, None]
    from scipy import sparse

    n = M.shape[0]
    n1, n2 = g1.max() + 1, g2.max() + 1
    S1 = sparse.csr_matrix((np.ones(n), (g1, np.arange(n))), shape=(n1, n))
    S2 = sparse.csr_matrix((np.ones(n), (g2, np.arange(n))), shape=(n2, n))
    c1 = np.bincount(g1, minlength=n1)[:, None]
    c2 = np.bincount(g2, minlength=n2)[:, None]
    for _ in range(maxit):
        M -= (np.asarray(S1 @ M) / c1)[g1]
        step = (np.asarray(S2 @ M) / c2)[g2]
        M -= step
        if np.abs(step).max() < tol:
            break
    return M[:, 0] if vec else M


def _codes(x) -> np.ndarray:
    _, inv = np.unique(np.asarray(x), return_inverse=True)
    return inv.astype(np.int64)


def _cr1(Xt: np.ndarray, u: np.ndarray, cl: np.ndarray, n_extra_k: int) -> np.ndarray:
    n, k = Xt.shape
    G = cl.max() + 1
    bread = np.linalg.pinv(Xt.T @ Xt)
    S = np.zeros((G, k))
    np.add.at(S, cl, Xt * u[:, None])
    K = k + n_extra_k
    c = G / (G - 1) * (n - 1) / max(n - K, 1)
    return c * bread @ (S.T @ S) @ bread


def twfe(y, X, unit, time) -> dict:
    """OLS of y on X with unit and time fixed effects; CR1 SEs clustered by unit."""
    from scipy import stats

    y = np.asarray(y, dtype=np.float64)
    X = np.asarray(X, dtype=np.float64)
    X = X[:, None] if X.ndim == 1 else X
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    y, X = y[ok], X[ok]
    u_, t_ = _codes(np.asarray(unit)[ok]), _codes(np.asarray(time)[ok])
    yt, Xt = demean2(y, u_, t_), demean2(X, u_, t_)
    keep = np.abs(Xt).sum(axis=0) > 1e-9
    b = np.full(X.shape[1], np.nan)
    bk, *_ = np.linalg.lstsq(Xt[:, keep], yt, rcond=None)
    b[keep] = bk
    u = yt - Xt[:, keep] @ bk
    V = np.full((X.shape[1],) * 2, np.nan)
    Vk = _cr1(Xt[:, keep], u, u_, t_.max())
    V[np.ix_(keep, keep)] = Vk
    se = np.sqrt(np.diag(V))
    G = u_.max() + 1
    tq = stats.t.ppf(0.975, G - 1)
    return {"b": b, "se": se, "V": V, "lo": b - tq * se, "hi": b + tq * se,
            "p": 2 * stats.t.sf(np.abs(b / se), G - 1), "G": int(G), "n": int(y.size),
            "yt": yt, "Xt": Xt, "units": u_, "times": t_, "ok": ok}


def did(y, treated, post, unit, time) -> dict:
    D = np.asarray(treated, dtype=np.float64) * np.asarray(post, dtype=np.float64)
    r = twfe(y, D, unit, time)
    return {k: (v[0] if k in ("b", "se", "lo", "hi", "p") else v) for k, v in r.items()}


_WEBB = np.array([-math.sqrt(1.5), -1.0, -math.sqrt(0.5), math.sqrt(0.5), 1.0, math.sqrt(1.5)])


def wild_bootstrap(fit: dict, B: int = B_WILD, seed: int = SEED, n_grid: int = 161) -> dict:
    """Restricted wild cluster bootstrap-t on the FWL-transformed DiD (Webb weights).

    Returns the p-value for b = 0 and a 95% interval from inverting the test.
    """
    yt, D, cl = fit["yt"], fit["Xt"][:, 0], fit["units"]
    G, n = cl.max() + 1, yt.size
    c = G / (G - 1) * (n - 1) / max(n - 1 - fit["times"].max(), 1)
    sdd = float(D @ D)
    q = np.bincount(cl, weights=D * D, minlength=G)
    W = _WEBB[np.random.default_rng(seed).integers(0, 6, size=(B, G))]
    bhat, sehat = fit["b"], fit["se"]

    def pval(b0: float) -> float:
        ur = yt - b0 * D
        s = np.bincount(cl, weights=D * ur, minlength=G)
        delta = (W @ s) / sdd
        sc = W * s[None, :] - delta[:, None] * q[None, :]
        se = np.sqrt(c * (sc ** 2).sum(axis=1)) / sdd
        tstar = delta / se
        t0 = (bhat - b0) / sehat
        return float((1 + (np.abs(tstar) >= abs(t0)).sum()) / (B + 1))

    p0 = pval(0.0)
    grid = np.linspace(bhat - 6 * sehat, bhat + 6 * sehat, n_grid)
    ps = np.array([pval(g) for g in grid])
    inside = grid[ps > 0.05]
    lo, hi = (float(inside.min()), float(inside.max())) if inside.size else (np.nan, np.nan)
    return {"p": p0, "lo": lo, "hi": hi, "B": B}


def permutation_test(y, treated, post, unit, time, B: int = B_PERM, seed: int = SEED,
                     n_grid: int = 401) -> dict:
    """Reassign the treated set among all contracts; p for b = 0 and an inverted 95% CI.

    With few contracts every assignment is enumerated.
    """
    from itertools import combinations

    y = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(y)
    unit = np.asarray(unit)[ok]
    u_, t_ = _codes(unit), _codes(np.asarray(time)[ok])
    y, post = y[ok], np.asarray(post, dtype=np.float64)[ok]
    tr_units = np.unique(u_[np.asarray(treated)[ok] == 1])
    G, k = u_.max() + 1, tr_units.size
    if math.comb(G, k) <= B:
        assigns = [np.array(a) for a in combinations(range(G), k)]
    else:
        rng = np.random.default_rng(seed)
        assigns = [np.sort(rng.choice(G, size=k, replace=False)) for _ in range(B)]
    obs = np.isin(u_, tr_units).astype(np.float64) * post
    Dp = np.column_stack([np.isin(u_, a).astype(np.float64) * post for a in assigns])
    yt = demean2(y, u_, t_)
    Dot = demean2(obs, u_, t_)
    Dpt = demean2(Dp, u_, t_)
    sdd_p = (Dpt * Dpt).sum(axis=0)
    good = sdd_p > 1e-9
    Dpt, sdd_p = Dpt[:, good], sdd_p[good]
    b_obs = float(Dot @ yt / (Dot @ Dot))
    bp0 = (Dpt.T @ yt) / sdd_p
    cross = (Dpt.T @ Dot) / sdd_p
    is_obs = np.array([set(a.tolist()) == set(tr_units.tolist()) for a in assigns])[good]

    def pval(c0: float) -> float:
        bp = bp0 - c0 * cross
        stat = abs(b_obs - c0)
        others = np.abs(bp[~is_obs]) >= stat - 1e-12
        return float((1 + others.sum()) / (1 + (~is_obs).sum()))

    span = max(np.abs(bp0).max(), abs(b_obs)) * 3 + 1e-9
    grid = np.linspace(b_obs - span, b_obs + span, n_grid)
    ps = np.array([pval(g) for g in grid])
    inside = grid[ps > 0.05]
    lo, hi = (float(inside.min()), float(inside.max())) if inside.size else (np.nan, np.nan)
    return {"b": b_obs, "p": pval(0.0), "lo": lo, "hi": hi, "n_assign": int(good.sum()),
            "min_p": float(1 / (1 + (~is_obs).sum()))}


def pre_trend_permutation(y, treated, rel, unit, B: int = B_PERM, seed: int = SEED) -> dict:
    """Randomization test of parallel pre-trends.

    On pre-event days only, y is residualized on contract and day effects; for an
    assignment of the treated label, delta_k is the treated-minus-control mean residual
    on day k and the statistic is the dispersion sum_k (delta_k - mean delta)^2. The
    p-value compares the real assignment with reassignments among all contracts. (A
    cluster-robust joint F-test of ~20 pre coefficients is not usable here: with 12
    treated clusters its covariance is rank-deficient and it rejected 84% of the time
    at 5% on synthetic panels with parallel trends.)
    """
    from itertools import combinations

    y = np.asarray(y, dtype=np.float64)
    rel = np.asarray(rel)
    m = (rel < 0) & np.isfinite(y)
    u_, t_ = _codes(np.asarray(unit)[m]), _codes(rel[m])
    yt = demean2(y[m], u_, t_)
    tr_units = np.unique(u_[np.asarray(treated)[m] == 1])
    G, k = u_.max() + 1, tr_units.size
    if math.comb(G, k) <= B:
        assigns = [np.array(a) for a in combinations(range(G), k)]
    else:
        rng = np.random.default_rng(seed + 1)
        assigns = [tr_units] + [np.sort(rng.choice(G, size=k, replace=False))
                                for _ in range(B)]
    A = np.zeros((G, len(assigns)))
    for j, a in enumerate(assigns):
        A[a, j] = 1.0
    T = A[u_]  # obs x assignments: 1 if the obs's contract is "treated"
    day = np.eye(t_.max() + 1)[t_]  # obs x days
    nt, nc = day.T @ T, day.T @ (1 - T)
    with np.errstate(invalid="ignore", divide="ignore"):
        delta = (day.T @ (yt[:, None] * T)) / nt - (day.T @ (yt[:, None] * (1 - T))) / nc
    stat = np.nansum((delta - np.nanmean(delta, axis=0)) ** 2, axis=0)
    is_obs = np.array([set(a.tolist()) == set(tr_units.tolist()) for a in assigns])
    s_obs = stat[is_obs][0]
    p = float((1 + (stat[~is_obs] >= s_obs - 1e-12).sum()) / (1 + (~is_obs).sum()))
    return {"p": p, "stat": float(s_obs), "n_assign": len(assigns)}


def event_study(y, treated, rel, unit, ref: int = REF_DAY, B: int = B_PERM) -> dict:
    """Treated x relative-day coefficients (ref day omitted) and two pre-trend checks."""
    y = np.asarray(y, dtype=np.float64)
    rel = np.asarray(rel)
    treated = np.asarray(treated)
    have = np.isfinite(y)
    days = sorted(int(d) for d in np.unique(rel[have]) if d != ref)
    X = np.column_stack([(treated == 1) & (rel == d) for d in days]).astype(np.float64)
    fit = twfe(y, X, unit, rel)
    pre = [i for i, d in enumerate(days) if d < ref and np.isfinite(fit["b"][i])]
    perm = pre_trend_permutation(y, treated, rel, unit, B=B)
    # linear pre-trend: slope of treated x rel on pre-event days only
    m = rel < 0
    slope = twfe(y[m], (treated[m] == 1) * rel[m].astype(np.float64), np.asarray(unit)[m],
                 rel[m])
    return {"days": days, "b": fit["b"], "lo": fit["lo"], "hi": fit["hi"], "se": fit["se"],
            "pre_p": perm["p"], "pre_q": len(pre) + 1,
            "slope": float(slope["b"][0]), "slope_lo": float(slope["lo"][0]),
            "slope_hi": float(slope["hi"][0]), "slope_p": float(slope["p"][0])}


# ---------------------------------------------------------------------------- analysis

def analyze_event(event: str, max_rank: int | None = None, wild: bool = True,
                  drop_rel: tuple[int, ...] = ()) -> dict:
    rows = [r for r in load_panel(event, max_rank) if r["rel"] not in drop_rel]
    treated, ctrl = contracts(event, max_rank)
    if not rows:
        return {}
    col = {k: np.array([r[k] for r in rows]) for k in rows[0] if k not in ("event", "date")}
    unit, rel, tr = col["symbol"], col["rel"], col["treated"]
    post = (rel > 0).astype(np.float64)
    res: dict = {"event": event, "label": EVENTS[event]["label"], "treated": treated,
                 "controls": ctrl, "outcomes": {}}
    present = collections.Counter(zip(unit.tolist(), tr.tolist()))
    res["coverage"] = {
        "contract_days": len(rows), "expected": (len(treated) + len(ctrl)) * 2 * WINDOW,
        "treated_present": sum(1 for (s, t) in present if t == 1),
        "controls_present": sum(1 for (s, t) in present if t == 0),
        "short_contracts": {s: n for (s, t), n in present.items() if n < 2 * WINDOW},
        "scored_events_median": float(np.median(col["n_scored"])),
        "models": sum(1 for s in treated + ctrl
                      if (_model_path(event, s).exists()
                          and json.loads(_model_path(event, s).read_text()))),
    }
    if res["coverage"]["controls_present"] < 1 or res["coverage"]["treated_present"] < 1:
        return {}
    for k, (label, unit_lbl, exp) in OUTCOMES.items():
        y = col[k]
        if np.isfinite(y).sum() < 20:
            continue
        d = did(y, tr, post, unit, rel)
        o = {"label": label, "unit": unit_lbl, "expected_after_cut": exp,
             "b": d["b"], "lo": d["lo"], "hi": d["hi"], "p": d["p"], "n": d["n"], "G": d["G"]}
        if len(treated) > 1 and wild:
            o["wild"] = wild_bootstrap(d)
        o["perm"] = permutation_test(y, tr, post, unit, rel)
        es = event_study(y, tr, rel, unit, ref=int(rel[rel < 0].max()))
        o["es"] = {kk: (v.tolist() if isinstance(v, np.ndarray) else v) for kk, v in es.items()}
        # levels: pre and post means for treated and controls
        for g, gv in (("treated", 1), ("control", 0)):
            for ph, pv in (("pre", 0.0), ("post", 1.0)):
                m = (tr == gv) & (post == pv) & np.isfinite(y)
                o[f"{g}_{ph}"] = float(y[m].mean()) if m.any() else float("nan")
        res["outcomes"][k] = o
    return res


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


def plot(results: dict[str, dict], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"2026-03-05": "#2a78d6", "2024-09-20": "#eb6834", "2024-10-14": "#1baf7a"}
    keys = list(OUTCOMES)
    fig, axes = plt.subplots(3, 4, figsize=(17, 10.5), sharex=True)
    axes.ravel()[-1].axis("off")
    for ax, k in zip(axes.ravel(), keys, strict=False):
        label, unit_lbl, _ = OUTCOMES[k]
        for ev, res in results.items():
            o = res.get("outcomes", {}).get(k)
            if not o or ev == "2024-10-14":
                continue
            es = o["es"]
            d = np.array(es["days"] + [REF_DAY])
            b = np.array(es["b"] + [0.0], dtype=float)
            lo = np.array(es["lo"] + [0.0], dtype=float)
            hi = np.array(es["hi"] + [0.0], dtype=float)
            s = np.argsort(d)
            d, b, lo, hi = d[s], b[s], lo[s], hi[s]
            primary = EVENTS[ev]["role"] == "primary"
            if primary:
                ax.fill_between(d, lo, hi, color=colors[ev], alpha=0.18, lw=0)
                ax.plot(d, b, color=colors[ev], lw=2, marker="o", ms=3.5,
                        label=EVENTS[ev]["label"])
            else:
                ax.plot(d, b, color=colors[ev], lw=1.2, marker="o", ms=3, alpha=0.9,
                        label=EVENTS[ev]["label"] + " (no band)")
        ax.axhline(0, color="#8a8984", lw=0.8)
        ax.axvline(0, color="#52514e", lw=0.8, ls="--")
        ax.axvspan(-21.5, -10.5, color="#d9d8d2", alpha=0.35, lw=0)
        ax.set_title(f"{label}\n({unit_lbl})", fontsize=10, color="#0b0b0b")
        ax.grid(axis="y", color="#e6e5e0", lw=0.6)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(labelsize=8, colors="#52514e")
    for ax in axes[-1]:
        ax.set_xlabel("days relative to the tick change (day -1 = 0)", fontsize=9)
    h, lbl = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, lbl, loc="upper center", ncol=3, frameon=False, fontsize=10)
    fig.suptitle("Treated minus control, by day (event-study coefficients, 95% CI clustered "
                 "by contract). Grey: model training days (-21 to -11).",
                 y=0.955, fontsize=11, color="#0b0b0b")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=130, facecolor="#fcfcfb")
    plt.close(fig)


def analyze(events: list[str]) -> dict:
    results = {}
    for ev in events:
        if not (CACHE / ev).exists():
            continue
        r = analyze_event(ev)
        if r:
            results[ev] = r
            if EVENTS[ev]["role"] == "primary":
                # robustness: only the top-ranked control of each treated contract
                rr = analyze_event(ev, max_rank=1, wild=False)
                results[ev]["rank1_only"] = {} if not rr else {
                    k: {"b": o["b"], "lo": o["lo"], "hi": o["hi"],
                        "perm_p": o["perm"]["p"]}
                    for k, o in rr["outcomes"].items()}
                results[ev]["rank1_controls"] = len(rr.get("controls", []))
                # robustness: drop the days after the notice (published 2026-03-02 06:00,
                # day -3), in case traders anticipated the change
                ra = analyze_event(ev, wild=False, drop_rel=ANNOUNCE_REL.get(ev, ()))
                results[ev]["no_announce_days"] = {
                    k: {"b": o["b"], "lo": o["lo"], "hi": o["hi"],
                        "perm_p": o["perm"]["p"]} for k, o in ra["outcomes"].items()}
    (CACHE / "e3_results.json").write_text(json.dumps(_jsonable(results), indent=1))
    plot(results, OUT / "e3_event_study.png")
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["plan", "run", "analyze"])
    ap.add_argument("--event", action="append")
    ap.add_argument("--max-rank", type=int)
    a = ap.parse_args()
    events = a.event or list(EVENTS)
    if a.stage == "plan":
        for ev in events:
            for mr in range(1, 7):
                t, c = contracts(ev, mr)
                print(ev, "max_rank", mr, len(t), len(c),
                      f"{planned_bytes(ev, t + c) / 1e9:.2f} GB")
    elif a.stage == "run":
        for ev in events:
            run_event(ev, a.max_rank)
    else:
        res = analyze(events)
        for ev, r in res.items():
            print(ev, r["coverage"])
            for k, o in r["outcomes"].items():
                w = o.get("wild", {})
                print(f"  {k:14s} b={o['b']:+.3f} [{o['lo']:+.3f},{o['hi']:+.3f}] "
                      f"wild p={w.get('p', float('nan')):.3f} perm p={o['perm']['p']:.3f} "
                      f"pre perm p={o["es"]["pre_p"]:.3f} slope={o["es"]["slope"]:+.4f} "
                      f"[{o["es"]["slope_lo"]:+.4f},{o["es"]["slope_hi"]:+.4f}]")


if __name__ == "__main__":
    main()
