"""E5: a stacked event study of tick-size changes (cuts AND increases) on sign predictability.

Scales up the e3 natural experiment (`e3_event_study.py`, two cut batches) to every usable
batch in `data/tick_events.csv`, following `notes/panel_and_causal_methods.md` section 2:
each batch gets its own sub-panel (its treated contracts and their own matched controls,
relative days -21..+21 without the event day), the sub-panels are stacked, and the model
has batch-by-contract and batch-by-day fixed effects, so no already-treated contract ever
serves as a control for another batch (the staggered-adoption problem of plain TWFE).
Standard errors are clustered by contract (a symbol in several batches is one cluster).

Fixed before any new result was looked at (2026-11-18):

- Lock-box. The batches of 2026-08-06 and 2026-10-15 are reserved for a final
  replication (RESERVED). Their files are never downloaded or loaded, and their treated
  contracts are not used in any other sub-panel whose window comes within 21 days of the
  reserved date.
- Primary outcome: the sign repeat rate (and lag-1 sign autocorrelation, same family).
  Secondary: the same-day refit accuracy of e3 (secondary because e3 added it after its
  first result). Mechanisms: unchanged-price share, long same-sign runs (sweeps merged),
  median trade size, events per day. First stage: log relative tick.
- Expected signs (from e3 and the cross-section): a cut raises the repeat rate, an
  increase lowers it; in the pooled model, signed by the log change in tick (a cut is
  -ln 10), the coefficient is NEGATIVE (more relative tick, less persistence).
- Eligibility: status verified, at least 3 matched controls per treated contract (after
  dropping controls that are treated in the same batch), no other tick change of the
  same contract within 21 days, and a batch needs at least 3 such treated contracts or
  an increase. SOLUSDT 2024-10-14 (one increase) is always included, with its 6 controls
  and permutation inference over them.
- Budget rule (the full design costs about 40 GB at 14 days per contract, against a 4 GB
  budget). Days: every third relative day, -19,-16,...,-1 and +1,+4,...,+19 (GRID). Controls:
  the first 3 valid ranks. Cut arms: per batch, the 3 contracts with the smallest
  PRE-event archive size (never post-event size, which moves with the outcome); arms are
  taken cheapest first, round-robin over years, until BUDGET_CUT. Increases are taken one
  contract at a time, cheapest first, until BUDGET_INC. The two e3 batches (2026-03-05,
  2024-09-20) reuse the e3 cache: all their cached treated contracts are kept, and only
  missing control-days are downloaded.

Inference: CR1 clustered by contract; a restricted wild cluster bootstrap (e3's, on the
FWL-transformed stacked data); a permutation test that permutes the treatment (or dose)
across contracts WITHIN each batch, with a CI by test inversion; the stacked pre-trend
permutation test (dispersion of daily treated-minus-control residual means on pre days,
treatment permuted within batches) and a linear pre-trend slope. Per-batch estimates use
e3's single-event DiD and permutation test (forest plot).

    PYTHONPATH=src .venv/bin/python research/market_evolution/e5_stacked_events.py plan
    PYTHONPATH=src .venv/bin/python research/market_evolution/e5_stacked_events.py run
    PYTHONPATH=src .venv/bin/python research/market_evolution/e5_stacked_events.py analyze

Resumable: per contract-day summaries are cached under data/event_study/e5/<batch>/
<symbol>/<date>.json (the e3 cache under data/event_study/<batch>/ is read first).
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import csv
import datetime as dt
import importlib.util
import json
import math
import shutil
import sys
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _load_e3():
    if "e3_event_study" in sys.modules:
        return sys.modules["e3_event_study"]
    spec = importlib.util.spec_from_file_location("e3_event_study", HERE / "e3_event_study.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["e3_event_study"] = mod
    spec.loader.exec_module(mod)
    return mod


e3 = _load_e3()

OUT = HERE / "data"
CACHE = ROOT / "data" / "event_study"
E5_CACHE = CACHE / "e5"
INVENTORY = ROOT / "data" / "universe" / "aggtrades_monthly_inventory.json"
LAST_INVENTORY_MONTH = "2026-10"

RESERVED = ("2026-08-06", "2026-10-15")
E3_CACHED = ("2026-03-05", "2024-09-20")
SOL = ("2024-10-14", "SOLUSDT")
SOL_CONTROLS = 6
WINDOW = 21
GRID = tuple(list(range(-19, 0, 3)) + list(range(1, 20, 3)))
REF_DAY = -1
N_CONTROLS = 3
MIN_TREATED = 3
CUTS_PER_ARM = 3
BUDGET_CUT = 1.75e9
BUDGET_INC = 1.40e9
HARD_CAP = 3.9e9  # bytes downloaded by e5 (its own ledger)
MAX_FILE = 300e6
WORKERS = 4
PREFETCH = 6
B_PERM = 2999
B_WILD = 4999
SEED = 20261118

PRIMARY = ("repeat_rate", "sign_acf_lag1")
SECONDARY = ("acc_refit", "refit_excess")
MECHANISMS = ("unchanged", "long_runs", "log_size", "log_events")
FIRST_STAGE = ("log_rel_tick",)
OUTCOMES = PRIMARY + SECONDARY + MECHANISMS + FIRST_STAGE
ROLE = {**{k: "primary" for k in PRIMARY}, **{k: "secondary" for k in SECONDARY},
        **{k: "mechanism" for k in MECHANISMS}, **{k: "first stage" for k in FIRST_STAGE}}


class ReservedBatchError(RuntimeError):
    pass


def guard(batch: str) -> None:
    if batch in RESERVED:
        raise ReservedBatchError(f"{batch} is in the lock-box and must not be analysed")


# ---------------------------------------------------------------------------- design

def _read_csv(name: str) -> list[dict]:
    with (OUT / name).open() as fh:
        return list(csv.DictReader(fh))


def _date(s: str) -> dt.date:
    return dt.date.fromisoformat(s[:10])


def grid_dates(batch: str) -> dict[int, str]:
    e = _date(batch)
    return {r: (e + dt.timedelta(days=r)).isoformat() for r in GRID}


_INV: dict | None = None


def day_bytes(symbol: str, day: str) -> float:
    """Archive size of one day, pro rata from the monthly inventory."""
    global _INV
    if _INV is None:
        _INV = json.loads(INVENTORY.read_text()) if INVENTORY.exists() else {}
    d = _date(day)
    nd = (dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1) - d.replace(day=1)).days
    return _INV.get(symbol, {}).get(min(day[:7], LAST_INVENTORY_MONTH), 0) / nd


def pre_cost(symbol: str, batch: str) -> float:
    """Estimated bytes for the GRID days, from PRE-event days only (x2)."""
    return 2 * sum(day_bytes(symbol, d) for r, d in grid_dates(batch).items() if r < 0)


def design(events: list[dict] | None = None, controls: list[dict] | None = None,
           budget_cut: float = BUDGET_CUT, budget_inc: float = BUDGET_INC,
           cached: dict[str, set[str]] | None = None) -> dict:
    """Arms (batch x direction) to analyse, chosen by the rules in the module docstring.

    `cached` maps an e3 batch to the treated symbols present in the e3 cache; their
    cost is zero and they are all kept. Returns {"arms": [...], "reserved": [...],
    "eligible": {...}, "dropped": [...]}.
    """
    events = _read_csv("tick_events.csv") if events is None else events
    controls = _read_csv("tick_event_controls.csv") if controls is None else controls
    cached = _e3_cached_treated() if cached is None else cached
    changes = collections.defaultdict(list)
    for r in events:
        changes[r["symbol"]].append(_date(r["detected_time"]))
    by_batch = collections.defaultdict(list)
    for r in events:
        if r["status"] == "verified":
            by_batch[r["detected_time"][:10]].append(r)
    reserved_treated = {b: {r["symbol"] for r in by_batch.get(b, [])} for b in RESERVED}
    ctrl_rows = collections.defaultdict(list)
    for c in controls:
        ctrl_rows[(c["event_date"], c["treated_symbol"])].append(c)

    def touches_reserved(sym: str, batch: str) -> bool:
        days = [_date(d) for d in grid_dates(batch).values()]
        return any(sym in reserved_treated[rb] and any(abs((d - _date(rb)).days) <= WINDOW
                                                       for d in days)
                   for rb in RESERVED)

    eligible, dropped = {}, []
    for b in sorted(by_batch):
        if b in RESERVED:
            continue
        e = _date(b)
        batch_treated = {r["symbol"] for r in by_batch[b]}
        ok = []
        for r in by_batch[b]:
            s = r["symbol"]
            other = [d for d in changes[s] if d != e and abs((d - e).days) <= WINDOW]
            ranked = sorted(ctrl_rows[(b, s)], key=lambda c: int(c["rank"]))
            valid = [c["control_symbol"] for c in ranked
                     if c["control_symbol"] not in batch_treated
                     and not touches_reserved(c["control_symbol"], b)]
            need = SOL_CONTROLS if (b, s) == SOL else N_CONTROLS
            why = ("another tick change within 21 days" if other else
                   f"fewer than {N_CONTROLS} valid controls" if len(valid) < N_CONTROLS else
                   "treated in a reserved window" if touches_reserved(s, b) else None)
            if why:
                dropped.append({"batch": b, "symbol": s, "direction": r["direction"],
                                "reason": why})
                continue
            dose = math.log(float(r["new_tick"]) / float(r["old_tick"]))
            ok.append({"symbol": s, "direction": r["direction"], "dose": dose,
                       "controls": valid[:need]})
        n_inc = sum(t["direction"] == "increase" for t in ok)
        if len(ok) >= MIN_TREATED or n_inc >= 1 or b == SOL[0]:
            eligible[b] = ok
        elif ok:
            dropped += [{"batch": b, "symbol": t["symbol"], "direction": t["direction"],
                         "reason": f"batch has fewer than {MIN_TREATED} eligible treated "
                         "and no increase"} for t in ok]

    def cost(t: dict, b: str, have: set[str]) -> float:
        syms = [s for s in [t["symbol"], *t["controls"]] if s not in have]
        return sum(_cost_of(s, b, cached) for s in syms)

    arms: list[dict] = []
    # cut arms
    cand = []
    for b, ts in eligible.items():
        cuts = [t for t in ts if t["direction"] == "cut"]
        if not cuts:
            continue
        if b in cached:
            keep = [t for t in cuts if t["symbol"] in cached[b]]
        else:
            keep = sorted(cuts, key=lambda t: (cost(t, b, set()), t["symbol"]))[:CUTS_PER_ARM]
        have: set[str] = set()
        c = 0.0
        for t in keep:
            c += cost(t, b, have)
            have |= {t["symbol"], *t["controls"]}
        cand.append({"batch": b, "direction": "cut", "treated": keep, "cost": c,
                     "n_eligible": len(cuts)})
    by_year = collections.defaultdict(list)
    for a in sorted(cand, key=lambda a: (a["cost"], a["batch"])):
        by_year[a["batch"][:4]].append(a)
    spent = 0.0
    while any(by_year.values()):
        for y in sorted(by_year):
            if not by_year[y]:
                continue
            a = by_year[y].pop(0)
            if spent + a["cost"] <= budget_cut:
                spent += a["cost"]
                arms.append(a)
    # increase arms, one contract at a time
    incs = [(b, t) for b, ts in eligible.items() for t in ts if t["direction"] == "increase"]
    spent_inc = 0.0
    chosen = collections.defaultdict(list)
    sol = [(b, t) for b, t in incs if (b, t["symbol"]) == SOL]
    rest = sorted((x for x in incs if x not in sol),
                  key=lambda x: (cost(x[1], x[0], set()), x[0], x[1]["symbol"]))
    for b, t in sol:
        chosen[b].append(t)
        spent_inc += cost(t, b, set())
    for b, t in rest:
        have = {s for a in arms if a["batch"] == b for x in a["treated"]
                for s in (x["symbol"], *x["controls"])}
        have |= {s for x in chosen.get(b, []) for s in (x["symbol"], *x["controls"])}
        c = cost(t, b, have)
        if spent_inc + c <= budget_inc:
            spent_inc += c
            chosen[b].append(t)
    for b, ts in chosen.items():
        arms.append({"batch": b, "direction": "increase", "treated": ts,
                     "cost": float("nan"),
                     "n_eligible": sum(t["direction"] == "increase" for t in eligible[b])})
    arms.sort(key=lambda a: (a["batch"], a["direction"]))
    return {"arms": arms, "reserved": list(RESERVED), "eligible": eligible,
            "dropped": dropped, "planned_cut_bytes": spent, "planned_inc_bytes": spent_inc}


def _cost_of(symbol: str, batch: str, cached: dict[str, set[str]]) -> float:
    if batch in cached:
        missing = sum(not (CACHE / batch / symbol / f"{d}.json").exists()
                      for d in grid_dates(batch).values())
        return pre_cost(symbol, batch) * missing / len(GRID)
    return pre_cost(symbol, batch)


def _e3_cached_treated() -> dict[str, set[str]]:
    out = {}
    for b in E3_CACHED:
        if (CACHE / b).exists():
            out[b] = {p.name for p in (CACHE / b).iterdir()
                      if p.is_dir() and p.name != "models"}
    if not out:
        return {}
    ev = _read_csv("tick_events.csv")
    return {b: {r["symbol"] for r in ev if r["detected_time"][:10] == b} & s
            for b, s in out.items()}


def arm_symbols(arm: dict) -> tuple[list[str], list[str]]:
    tr = [t["symbol"] for t in arm["treated"]]
    ctrl = sorted({c for t in arm["treated"] for c in t["controls"]} - set(tr))
    return tr, ctrl


def downloads(plan: dict) -> list[tuple[str, str, str]]:
    """(batch, symbol, date) to fetch: every GRID day of every arm's contracts not cached."""
    jobs = []
    seen = set()
    for a in plan["arms"]:
        guard(a["batch"])
        tr, ctrl = arm_symbols(a)
        for s in tr + ctrl:
            for d in grid_dates(a["batch"]).values():
                k = (a["batch"], s, d)
                if k not in seen and _cached_summary(*k) is None:
                    seen.add(k)
                    jobs.append(k)
    return jobs


# ---------------------------------------------------------------------------- I/O

def _summary_path(batch: str, symbol: str, day: str) -> Path:
    return E5_CACHE / batch / symbol / f"{day}.json"


def _cached_summary(batch: str, symbol: str, day: str) -> dict | None:
    guard(batch)
    for p in (CACHE / batch / symbol / f"{day}.json", _summary_path(batch, symbol, day)):
        if p.exists():
            return json.loads(p.read_text())
    return None


def run(plan: dict) -> None:
    import polars as pl

    from microstructure.data.ingest import ingest_agg_trades

    e3.HARD_CAP = HARD_CAP  # e3.fetch_day checks the ledger it is given against this
    ledger = e3.Ledger(CACHE / "e5_ledger.json")
    jobs = downloads(plan)
    est = sum(day_bytes(s, d) for _, s, d in jobs)
    print(f"{len(jobs)} contract-days to fetch, about {est / 1e9:.2f} GB; e5 downloaded so "
          f"far {ledger.total / 1e9:.2f} GB", flush=True)
    q: collections.deque = collections.deque()
    it = iter(jobs)
    done = 0
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        def refill():
            while len(q) < PREFETCH:
                try:
                    b, s, d = next(it)
                except StopIteration:
                    return
                if day_bytes(s, d) > MAX_FILE:
                    q.append((b, s, d, None))
                else:
                    q.append((b, s, d, ex.submit(e3.fetch_day, s, d, ledger)))

        refill()
        while q:
            b, s, d, fut = q.popleft()
            refill()
            rec: dict = {"symbol": s, "date": d, "rel": (_date(d) - _date(b)).days,
                         "v": e3.SUMMARY_VERSION, "batch": b}
            if fut is None:
                rec |= {"present": False, "skipped": "estimated over 300 MB"}
                zp = tmp = None
            else:
                zp, tmp = fut.result()
            try:
                if fut is not None and zp is None:
                    rec["present"] = False
                elif zp is not None and zp.stat().st_size > MAX_FILE:
                    rec |= {"present": False, "skipped": f"{zp.stat().st_size / 1e6:.0f} MB"}
                elif zp is not None:
                    pq = ingest_agg_trades(zp, tmp)
                    zp.unlink()
                    raw = pl.read_parquet(pq)
                    pq.unlink()
                    rng = np.random.default_rng([e3.SEED, zlib.crc32(f"{s}|{d}".encode())])
                    stats, _ = e3.day_stats(raw, rng, None, False)
                    del raw
                    rec |= {"present": True, **stats}
            finally:
                if tmp is not None:
                    shutil.rmtree(tmp, ignore_errors=True)
            p = _summary_path(b, s, d)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(rec))
            done += 1
            if done % 50 == 0:
                print(f"{done}/{len(jobs)} done, {ledger.total / 1e9:.2f} GB downloaded",
                      flush=True)
    print(f"finished; e5 downloaded {ledger.total / 1e9:.2f} GB", flush=True)


# ---------------------------------------------------------------------------- panel

def load_panel(plan: dict, summary=None) -> list[dict]:
    """One row per (batch, symbol, grid day) present; treated and dose per arm.

    A symbol that is in two arms of one batch (a control shared by a cut and an
    increase) is one row; `cut_arm` / `inc_arm` say which sub-panels it belongs to.
    """
    summary = _cached_summary if summary is None else summary
    members: dict[tuple[str, str], dict] = {}
    for a in plan["arms"]:
        guard(a["batch"])
        tr, ctrl = arm_symbols(a)
        doses = {t["symbol"]: t["dose"] for t in a["treated"]}
        arm_key = "cut_arm" if a["direction"] == "cut" else "inc_arm"
        for s in tr + ctrl:
            m = members.setdefault((a["batch"], s), {"treated": 0, "dose": 0.0,
                                                     "cut_arm": 0, "inc_arm": 0})
            m[arm_key] = 1
            if s in doses:
                m["treated"], m["dose"] = 1, doses[s]
    rows = []
    for (b, s), m in sorted(members.items()):
        for r, d in grid_dates(b).items():
            rec = summary(b, s, d)
            if not rec or not rec.get("present"):
                continue
            row = {"batch": b, "symbol": s, "rel": r, "year": int(b[:4]), **m}
            row |= e3.outcome_values(rec)
            rows.append(row)
    return rows


def columns(rows: list[dict]) -> dict[str, np.ndarray]:
    return {k: np.array([r[k] for r in rows]) for k in rows[0]}


# ---------------------------------------------------------------------------- estimators

def _codes(x) -> np.ndarray:
    return e3._codes(x)


def stacked_fit(y, X, fe_unit, fe_time, cluster) -> dict:
    """OLS of y on X with two absorbed FE sets; CR1 clustered by `cluster` (G-1 df)."""
    from scipy import stats

    y = np.asarray(y, dtype=np.float64)
    X = np.asarray(X, dtype=np.float64)
    X = X[:, None] if X.ndim == 1 else X
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    y, X = y[ok], X[ok]
    fu, ft = _codes(np.asarray(fe_unit)[ok]), _codes(np.asarray(fe_time)[ok])
    cl = _codes(np.asarray(cluster)[ok])
    yt, Xt = e3.demean2(y, fu, ft), e3.demean2(X, fu, ft)
    keep = np.abs(Xt).sum(axis=0) > 1e-9
    b = np.full(X.shape[1], np.nan)
    bk, *_ = np.linalg.lstsq(Xt[:, keep], yt, rcond=None)
    b[keep] = bk
    u = yt - Xt[:, keep] @ bk
    V = np.full((X.shape[1],) * 2, np.nan)
    V[np.ix_(keep, keep)] = e3._cr1(Xt[:, keep], u, cl, ft.max())
    se = np.sqrt(np.diag(V))
    G = int(cl.max() + 1)
    tq = stats.t.ppf(0.975, G - 1)
    return {"b": b, "se": se, "lo": b - tq * se, "hi": b + tq * se,
            "p": 2 * stats.t.sf(np.abs(b / se), G - 1), "G": G, "n": int(y.size),
            "yt": yt, "Xt": Xt, "units": cl, "times": ft, "ok": ok}


def stacked_did(y, D, fe_unit, fe_time, cluster) -> dict:
    f = stacked_fit(y, D, fe_unit, fe_time, cluster)
    return {k: (v[0] if k in ("b", "se", "lo", "hi", "p") else v) for k, v in f.items()}


def _within_assignments(unit_stratum: np.ndarray, unit_dose: np.ndarray, B: int,
                        seed: int) -> np.ndarray:
    """units x B matrix: the dose vector permuted across units within each stratum."""
    rng = np.random.default_rng(seed)
    A = np.empty((unit_dose.size, B))
    for s in np.unique(unit_stratum):
        idx = np.flatnonzero(unit_stratum == s)
        vals = unit_dose[idx]
        for j in range(B):
            A[idx, j] = rng.permutation(vals)
    return A


def _unit_table(fe_unit, stratum, dose):
    u = _codes(fe_unit)
    n = u.max() + 1
    us, ud = np.empty(n, dtype=object), np.zeros(n)
    us[u] = np.asarray(stratum)
    ud[u] = np.asarray(dose, dtype=np.float64)
    return u, _codes(us.astype(str)), ud


def stratified_permutation(y, dose, post, fe_unit, fe_time, stratum, B: int = B_PERM,
                           seed: int = SEED, n_grid: int = 401, chunk: int = 250) -> dict:
    """Permute treatment (or dose) across contracts within each batch.

    The statistic is the stacked FE coefficient on dose x post. p for b = 0 and a 95% CI
    from inverting the test under a constant effect per unit of dose (as in e3).
    """
    y = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(y)
    y, post = y[ok], np.asarray(post, dtype=np.float64)[ok]
    fe_unit, fe_time = np.asarray(fe_unit)[ok], np.asarray(fe_time)[ok]
    u, us, ud = _unit_table(fe_unit, np.asarray(stratum)[ok], np.asarray(dose)[ok])
    ft = _codes(fe_time)
    yt = e3.demean2(y, u, ft)
    Dot = e3.demean2(ud[u] * post, u, ft)
    b_obs = float(Dot @ yt / (Dot @ Dot))
    A = _within_assignments(us, ud, B, seed)
    bp0, cross = np.empty(B), np.empty(B)
    for j0 in range(0, B, chunk):
        Dp = A[u, j0:j0 + chunk] * post[:, None]
        Dpt = e3.demean2(Dp, u, ft)
        sdd = (Dpt * Dpt).sum(axis=0)
        sdd[sdd < 1e-12] = np.nan
        bp0[j0:j0 + chunk] = (Dpt.T @ yt) / sdd
        cross[j0:j0 + chunk] = (Dpt.T @ Dot) / sdd
    good = np.isfinite(bp0)
    bp0, cross = bp0[good], cross[good]

    def pval(c0: float) -> float:
        return float((1 + (np.abs(bp0 - c0 * cross) >= abs(b_obs - c0) - 1e-12).sum())
                     / (1 + bp0.size))

    span = max(np.abs(bp0).max(), abs(b_obs)) * 3 + 1e-9
    grid = np.linspace(b_obs - span, b_obs + span, n_grid)
    ps = np.array([pval(g) for g in grid])
    inside = grid[ps > 0.05]
    lo, hi = (float(inside.min()), float(inside.max())) if inside.size else (np.nan, np.nan)
    return {"b": b_obs, "p": pval(0.0), "lo": lo, "hi": hi, "B": int(bp0.size)}


def stacked_pre_trend(y, treated, rel, fe_unit, fe_time, stratum, B: int = B_PERM,
                      seed: int = SEED) -> dict:
    """e3's pre-trend dispersion test with treatment permuted within batches.

    Pre-event days only; y residualized on batch-contract and batch-day effects;
    delta_k = treated minus control mean residual on relative day k (pooled over
    batches); statistic sum_k (delta_k - mean delta)^2.
    """
    y = np.asarray(y, dtype=np.float64)
    rel = np.asarray(rel)
    m = (rel < 0) & np.isfinite(y)
    u, us, ut = _unit_table(np.asarray(fe_unit)[m], np.asarray(stratum)[m],
                            np.asarray(treated)[m])
    ft = _codes(np.asarray(fe_time)[m])
    yt = e3.demean2(y[m], u, ft)
    A = np.column_stack([ut, _within_assignments(us, ut, B, seed + 1)])
    T = A[u]
    day = np.eye(_codes(rel[m]).max() + 1)[_codes(rel[m])]
    nt, nc = day.T @ T, day.T @ (1 - T)
    with np.errstate(invalid="ignore", divide="ignore"):
        delta = (day.T @ (yt[:, None] * T)) / nt - (day.T @ (yt[:, None] * (1 - T))) / nc
    stat = np.nansum((delta - np.nanmean(delta, axis=0)) ** 2, axis=0)
    p = float((1 + (stat[1:] >= stat[0] - 1e-12).sum()) / (1 + B))
    # linear pre-trend: treated x rel on pre days, stacked FE, clustered by contract
    return {"p": p, "stat": float(stat[0])}


def stacked_event_study(y, treated, rel, fe_unit, fe_time, cluster, ref: int = REF_DAY):
    y = np.asarray(y, dtype=np.float64)
    rel, treated = np.asarray(rel), np.asarray(treated)
    days = sorted(int(d) for d in np.unique(rel[np.isfinite(y)]) if d != ref)
    X = np.column_stack([(treated == 1) & (rel == d) for d in days]).astype(np.float64)
    f = stacked_fit(y, X, fe_unit, fe_time, cluster)
    m = rel < 0
    sl = stacked_did(y[m], (treated[m] == 1) * rel[m].astype(np.float64),
                     np.asarray(fe_unit)[m], np.asarray(fe_time)[m], np.asarray(cluster)[m])
    return {"days": days, "b": f["b"].tolist(), "lo": f["lo"].tolist(), "hi": f["hi"].tolist(),
            "slope": float(sl["b"]), "slope_lo": float(sl["lo"]), "slope_hi": float(sl["hi"])}


# ---------------------------------------------------------------------------- analysis

def subpanel(col: dict, model: str) -> np.ndarray:
    """Rows of a model's stacked panel: 'cut', 'increase' or 'pooled'."""
    if model == "cut":
        m = col["cut_arm"] == 1
        return m & ~((col["treated"] == 1) & (col["dose"] > 0))
    if model == "increase":
        m = col["inc_arm"] == 1
        return m & ~((col["treated"] == 1) & (col["dose"] < 0))
    return np.ones(col["batch"].size, dtype=bool)


def estimate(col: dict, model: str, outcome: str, B: int = B_PERM, wild: bool = True,
             es: bool = True) -> dict:
    m = subpanel(col, model)
    c = {k: v[m] for k, v in col.items()}
    y = c[outcome].astype(np.float64)
    post = (c["rel"] > 0).astype(np.float64)
    # binary for cut / increase, the signed log tick change for the pooled model
    dose = c["dose"] if model == "pooled" else c["treated"].astype(np.float64)
    fe_u = np.char.add(np.char.add(c["batch"].astype(str), "|"), c["symbol"].astype(str))
    fe_t = np.char.add(np.char.add(c["batch"].astype(str), "|"), c["rel"].astype(str))
    if np.isfinite(y).sum() < 20 or (c["treated"] == 1).sum() == 0:
        return {}
    d = stacked_did(y, dose * post, fe_u, fe_t, c["symbol"])
    o = {"b": d["b"], "lo": d["lo"], "hi": d["hi"], "p": d["p"], "n": d["n"], "G": d["G"],
         "batches": int(np.unique(c["batch"]).size),
         "treated": int(np.unique(fe_u[c["treated"] == 1]).size)}
    if wild:
        o["wild"] = e3.wild_bootstrap(d, B=B_WILD)
    o["perm"] = stratified_permutation(y, dose, post, fe_u, fe_t, c["batch"], B=B)
    o["pre_p"] = stacked_pre_trend(y, c["treated"], c["rel"], fe_u, fe_t, c["batch"],
                                   B=B)["p"]
    if es:
        o["es"] = stacked_event_study(y, c["treated"], c["rel"], fe_u, fe_t, c["symbol"])
    return o


def per_arm(col: dict, plan: dict, outcomes=("repeat_rate", "acc_refit"), B: int = 999):
    """e3's single-event DiD and permutation test for each arm (the forest plot)."""
    out = []
    for a in plan["arms"]:
        model = "cut" if a["direction"] == "cut" else "increase"
        m = subpanel(col, model) & (col["batch"] == a["batch"])
        if not m.any() or (col["treated"][m] == 1).sum() == 0:
            continue
        c = {k: v[m] for k, v in col.items()}
        post = c["rel"] > 0
        rec = {"batch": a["batch"], "direction": a["direction"],
               "treated": int(np.unique(c["symbol"][c["treated"] == 1]).size),
               "controls": int(np.unique(c["symbol"][c["treated"] == 0]).size),
               "dose": float(np.mean([t["dose"] for t in a["treated"]]))}
        for k in outcomes:
            y = c[k].astype(np.float64)
            if np.isfinite(y).sum() < 10:
                continue
            d = e3.did(y, c["treated"], post, c["symbol"], c["rel"])
            p = e3.permutation_test(y, c["treated"], post, c["symbol"], c["rel"], B=B)
            pre = e3.pre_trend_permutation(y, c["treated"], c["rel"], c["symbol"], B=B)
            rec[k] = {"b": d["b"], "lo": d["lo"], "hi": d["hi"], "perm_p": p["p"],
                      "perm_lo": p["lo"], "perm_hi": p["hi"], "pre_p": pre["p"]}
        out.append(rec)
    return out


def cross_section_slopes(B: int = 2000, seed: int = SEED) -> dict:
    """Cross-sectional OLS slope of accuracy (and repeat rate) on ln(relative tick).

    From data/proxies_cross_section.parquet; with and without ln(events) as a control;
    95% intervals from resampling contracts.
    """
    import polars as pl

    p = OUT / "proxies_cross_section.parquet"
    if not p.exists():
        return {}
    df = pl.read_parquet(p).filter(pl.col("status") == "ok")
    out = {}
    rng = np.random.default_rng(seed)
    for per in sorted(df["set"].unique().to_list()):
        d = df.filter(pl.col("set") == per)
        x = np.log(d["rel_tick_bps"].to_numpy().astype(float))
        ev = np.asarray(d["q14_log10_events"].to_numpy(), dtype=float) * math.log(10)
        for name, col, scale in (("acc_gbm", "q14_gbm_all", 100.0),
                                 ("repeat_rate", "sign_repeat_rate", 100.0)):
            if col not in d.columns:
                continue
            y = scale * np.asarray(d[col].to_numpy(), dtype=float)
            ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(ev)
            for ctl in (False, True):
                Z = np.column_stack([np.ones(ok.sum()), x[ok]] + ([ev[ok]] if ctl else []))
                yy = y[ok]
                b = np.linalg.lstsq(Z, yy, rcond=None)[0][1]
                bs = []
                for _ in range(B):
                    i = rng.integers(0, yy.size, yy.size)
                    bs.append(np.linalg.lstsq(Z[i], yy[i], rcond=None)[0][1])
                lo, hi = np.percentile(bs, [2.5, 97.5])
                out[f"{per}|{name}|{'activity held fixed' if ctl else 'raw'}"] = {
                    "b": float(b), "lo": float(lo), "hi": float(hi), "n": int(ok.sum())}
    return out


def analyze(plan: dict, B: int = B_PERM) -> dict:
    rows = load_panel(plan)
    col = columns(rows)
    res: dict = {"reserved": list(RESERVED), "grid": list(GRID), "models": {}}
    present = collections.Counter(zip(col["batch"].tolist(), col["symbol"].tolist()))
    res["coverage"] = {
        "rows": len(rows),
        "expected": sum(len(set(arm_symbols(a)[0] + arm_symbols(a)[1])) for a in plan["arms"])
        * len(GRID),
        "batches": int(np.unique(col["batch"]).size),
        "contracts": int(np.unique(col["symbol"]).size),
        "batch_contracts": len(present),
        "short": {f"{b}|{s}": n for (b, s), n in present.items() if n < len(GRID) - 2},
        "scored_median": float(np.median(col["n_scored"])),
    }
    for model in ("cut", "increase", "pooled"):
        res["models"][model] = {}
        for k in OUTCOMES:
            o = estimate(col, model, k, B=B, es=k in PRIMARY + SECONDARY + MECHANISMS
                         + FIRST_STAGE)
            if o:
                res["models"][model][k] = o
        print(f"[{model}] done", flush=True)
    # robustness: pooled model without the two e3 batches (the new evidence only)
    keep = ~np.isin(col["batch"], E3_CACHED)
    res["pooled_without_e3"] = {k: estimate({kk: v[keep] for kk, v in col.items()}, "pooled",
                                            k, B=999, wild=False, es=False)
                                for k in PRIMARY + SECONDARY}
    # by year (pooled per-log-point model and the cut model)
    res["by_year"] = {}
    for y in sorted(np.unique(col["year"]).tolist()):
        m = col["year"] == y
        sub = {kk: v[m] for kk, v in col.items()}
        res["by_year"][str(y)] = {
            mdl: {k: estimate(sub, mdl, k, B=999, wild=False, es=False)
                  for k in ("repeat_rate", "acc_refit")}
            for mdl in ("pooled", "cut", "increase")}
    res["arms"] = per_arm(col, plan)
    sol = [a for a in plan["arms"] if a["batch"] == SOL[0]]
    if sol:
        m = col["batch"] == SOL[0]
        c = {k: v[m] for k, v in col.items()}
        res["sol"] = {}
        for k in PRIMARY + SECONDARY + MECHANISMS + FIRST_STAGE:
            y = c[k].astype(np.float64)
            if np.isfinite(y).sum() < 10:
                continue
            d = e3.did(y, c["treated"], c["rel"] > 0, c["symbol"], c["rel"])
            p = e3.permutation_test(y, c["treated"], c["rel"] > 0, c["symbol"], c["rel"])
            res["sol"][k] = {"b": d["b"], "perm_p": p["p"], "min_p": p["min_p"],
                             "rank_of_treated": _rank_of_treated(y, c)}
    res["cross_section"] = cross_section_slopes()
    return res


def _rank_of_treated(y, c) -> str:
    """Where the treated contract's post-minus-pre change ranks among all contracts."""
    ch = {}
    for s in np.unique(c["symbol"]):
        m = c["symbol"] == s
        a, b = y[m & (c["rel"] > 0)], y[m & (c["rel"] < 0)]
        ch[s] = np.nanmean(a) - np.nanmean(b)
    tr = c["symbol"][c["treated"] == 1][0]
    order = sorted(ch, key=lambda s: ch[s])
    return f"{order.index(tr) + 1} of {len(order)} (1 = largest fall)"


# ---------------------------------------------------------------------------- plot

LABEL = {
    "repeat_rate": ("sign repeat rate (primary)", "pp"),
    "sign_acf_lag1": ("lag-1 sign autocorrelation (primary)", "x100"),
    "acc_refit": ("same-day refit accuracy (secondary)", "pp"),
    "refit_excess": ("refit minus persistence (secondary)", "pp"),
    "unchanged": ("unchanged-price share", "pp"),
    "long_runs": ("same-sign runs >= 10, sweeps merged", "pp"),
    "log_size": ("median trade size (USD)", "log points"),
    "log_events": ("aggressor events per day", "log points"),
    "log_rel_tick": ("relative tick (first stage)", "log points"),
}
CUT_C, INC_C, INK, INK2, GRIDC, SURF = ("#2a78d6", "#eb6834", "#0b0b0b", "#52514e",
                                        "#e6e5e0", "#fcfcfb")


def plot(res: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(18, 11.5), facecolor=SURF)
    gs = fig.add_gridspec(3, 4, width_ratios=[1, 1, 1, 1.35], hspace=0.45, wspace=0.32)
    panels = ["repeat_rate", "sign_acf_lag1", "acc_refit", "unchanged", "long_runs",
              "log_events", "log_size", "log_rel_tick", "refit_excess"]
    for i, k in enumerate(panels):
        ax = fig.add_subplot(gs[i // 3, i % 3])
        for model, colr, off in (("cut", CUT_C, -0.25), ("increase", INC_C, 0.25)):
            o = res["models"].get(model, {}).get(k)
            if not o or "es" not in o:
                continue
            es = o["es"]
            d = np.array(es["days"] + [REF_DAY], dtype=float)
            b = np.array(es["b"] + [0.0], dtype=float)
            lo = np.array(es["lo"] + [0.0], dtype=float)
            hi = np.array(es["hi"] + [0.0], dtype=float)
            s = np.argsort(d)
            d, b, lo, hi = d[s] + off, b[s], lo[s], hi[s]
            ax.vlines(d, lo, hi, color=colr, lw=1.2, alpha=0.55)
            ax.plot(d, b, color=colr, lw=2, marker="o", ms=4,
                    label=f"{model}s: {o['treated']} contracts, {o['batches']} batches")
        ax.axhline(0, color="#8a8984", lw=0.8)
        ax.axvline(0, color=INK2, lw=0.8, ls="--")
        lbl, unit = LABEL[k]
        ax.set_title(f"{lbl}\n({unit})", fontsize=10, color=INK)
        ax.grid(axis="y", color=GRIDC, lw=0.6)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(labelsize=8, colors=INK2)
        ax.set_facecolor(SURF)
        if i // 3 == 2:
            ax.set_xlabel("days relative to the tick change (day -1 = 0)", fontsize=9,
                          color=INK2)
        if i == 0:
            ax.legend(fontsize=8, frameon=False, loc="upper left")
    # forest: per-arm repeat-rate effect
    ax = fig.add_subplot(gs[:, 3])
    arms = [a for a in res["arms"] if "repeat_rate" in a]
    arms = sorted(arms, key=lambda a: (a["direction"], a["batch"]))
    ys = np.arange(len(arms))[::-1] + 3
    for yv, a in zip(ys, arms, strict=True):
        o = a["repeat_rate"]
        colr = CUT_C if a["direction"] == "cut" else INC_C
        lo, hi = (o["lo"], o["hi"]) if a["treated"] >= 3 else (o["perm_lo"], o["perm_hi"])
        if np.isfinite(lo) and np.isfinite(hi):
            ax.hlines(yv, max(lo, -25), min(hi, 25), color=colr, lw=1.4, alpha=0.7)
        ax.plot(o["b"], yv, "o", color=colr, ms=5)
        ax.text(26.5, yv, f"{a['batch']}  {a['treated']}T/{a['controls']}C", fontsize=7,
                va="center", color=INK2)
    for j, (model, colr) in enumerate((("cut", CUT_C), ("increase", INC_C))):
        o = res["models"].get(model, {}).get("repeat_rate")
        if o:
            yv = 1.6 - j * 1.2
            ax.hlines(yv, o["lo"], o["hi"], color=colr, lw=4)
            ax.plot(o["b"], yv, "D", color=colr, ms=8, mec=SURF, mew=1.5)
            ax.text(26.5, yv, f"stacked {model}s", fontsize=8, va="center", color=INK,
                    weight="bold")
    ax.axvline(0, color="#8a8984", lw=0.8)
    ax.set_xlim(-25, 25)
    ax.set_yticks([])
    ax.set_xlabel("repeat-rate effect, treated minus controls (pp)", fontsize=9, color=INK2)
    ax.set_title("By batch: repeat rate (primary)\n95% CI: clustered, or permutation when "
                 "fewer than 3 treated", fontsize=10, color=INK)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=8, colors=INK2)
    ax.set_facecolor(SURF)
    fig.suptitle("Stacked event study of tick-size changes: treated minus control by day "
                 "(batch-by-contract and batch-by-day effects, 95% CI clustered by contract)."
                 "  Blue: cuts (finer grid). Orange: increases (coarser grid).",
                 fontsize=11, color=INK, y=0.985)
    fig.savefig(path, dpi=120, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------- main

def _jsonable(x):
    return e3._jsonable(x)


def plan_summary(plan: dict) -> dict:
    arms = []
    for a in plan["arms"]:
        tr, ctrl = arm_symbols(a)
        arms.append({"batch": a["batch"], "direction": a["direction"], "treated": tr,
                     "doses": [round(t["dose"], 3) for t in a["treated"]],
                     "controls": ctrl, "n_eligible": a["n_eligible"]})
    return {"reserved": plan["reserved"], "arms": arms, "dropped": plan["dropped"],
            "eligible_batches": sorted(plan["eligible"]),
            "planned_cut_bytes": plan["planned_cut_bytes"],
            "planned_inc_bytes": plan["planned_inc_bytes"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["plan", "run", "analyze"])
    a = ap.parse_args()
    plan = design()
    E5_CACHE.mkdir(parents=True, exist_ok=True)
    ps = plan_summary(plan)
    if a.stage == "plan":
        (E5_CACHE / "e5_plan.json").write_text(json.dumps(ps, indent=1, ensure_ascii=False))
        for x in ps["arms"]:
            print(x["batch"], x["direction"], len(x["treated"]), "of", x["n_eligible"],
                  "treated,", len(x["controls"]), "controls")
        jobs = downloads(plan)
        print(f"{len(ps['arms'])} arms; {len(jobs)} contract-days to fetch, about "
              f"{sum(day_bytes(s, d) for _, s, d in jobs) / 1e9:.2f} GB")
        print("reserved:", ps["reserved"])
    elif a.stage == "run":
        prev = E5_CACHE / "e5_plan.json"
        if prev.exists() and json.loads(prev.read_text())["arms"] != ps["arms"]:
            raise SystemExit("the design changed since `plan`; rerun plan first")
        run(plan)
    else:
        res = analyze(plan)
        res["plan"] = ps
        (E5_CACHE / "e5_results.json").write_text(
            json.dumps(_jsonable(res), indent=1, ensure_ascii=False))
        plot(res, OUT / "e5_stacked_events.png")
        for model, d in res["models"].items():
            for k, o in d.items():
                print(f"{model:9s} {k:14s} b={o['b']:+.3f} [{o['lo']:+.3f},{o['hi']:+.3f}] "
                      f"perm p={o['perm']['p']:.3f} [{o['perm']['lo']:+.3f},"
                      f"{o['perm']['hi']:+.3f}] pre p={o['pre_p']:.3f}")


if __name__ == "__main__":
    main()
