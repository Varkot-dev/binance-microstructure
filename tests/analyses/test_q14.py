"""Q14 on synthetic inputs with planted answers. Offline and fast: no network,
and the ladder fit is replaced by a stub wherever the pipeline is exercised.

Planted worlds:
* a group effect hidden behind an activity gap, which the raw median
  difference gets wrong and the activity-controlled regression recovers;
* treated units that are exact copies of controls plus a constant, which the
  matched comparison must return exactly;
* months with known trading days for the last-full-month rule;
* a pipeline run next to a pre-existing parquet, which must survive.
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from microstructure.analyses import q14_report
from microstructure.analyses import q14_survivorship as q14
from microstructure.analyses.q9_sign_prediction import DEFAULT_SYMBOLS
from microstructure.data.catalog import parquet_path
from microstructure.ml.evaluate import MS_PER_DAY

REPO = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------
# Activity-controlled regression and matching
# --------------------------------------------------------------------------


def _groups(effect: float, seed: int = 0, n_t: int = 60, n_c: int = 150):
    """Treated contracts are a decade of events quieter than controls, and
    accuracy rises 0.03 per decade, so the raw gap is about -0.03 + effect."""
    rng = np.random.default_rng(seed)
    x_t = rng.normal(5.5, 0.5, n_t)
    x_c = rng.normal(6.5, 0.5, n_c)
    y_t = 0.40 + 0.03 * x_t + effect + rng.normal(0, 0.002, n_t)
    y_c = 0.40 + 0.03 * x_c + rng.normal(0, 0.002, n_c)
    return y_t, x_t, y_c, x_c


def test_controlled_regression_recovers_planted_effect():
    y_t, x_t, y_c, x_c = _groups(effect=-0.01)
    c = q14.compare_groups(y_t, x_t, y_c, x_c, n_boot=300)
    assert c["ols"]["estimate"] == pytest.approx(-0.01, abs=0.002)
    assert c["ols"]["state"] == "negative"
    assert c["ols"]["slope_log_events"] == pytest.approx(0.03, abs=0.003)
    # The raw gap mixes in the activity difference: about -0.04.
    assert c["raw"]["estimate"] == pytest.approx(-0.04, abs=0.01)


def test_controlled_regression_finds_no_effect_when_there_is_none():
    y_t, x_t, y_c, x_c = _groups(effect=0.0)
    c = q14.compare_groups(y_t, x_t, y_c, x_c, n_boot=300)
    assert c["raw"]["state"] == "negative"          # activity alone
    assert c["ols"]["state"] == "zero"
    assert abs(c["ols"]["estimate"]) < 0.002


def test_ols_hc1_matches_textbook_formula():
    rng = np.random.default_rng(3)
    x = rng.normal(size=200)
    y = 1.0 + 2.0 * x + rng.normal(size=200) * (1 + np.abs(x))
    X = np.column_stack([np.ones_like(x), x])
    fit = q14.ols_hc1(y, X)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    bread = np.linalg.inv(X.T @ X)
    cov = bread @ (X.T * e ** 2) @ X @ bread * 200 / 198
    assert np.allclose(fit["beta"], beta)
    assert np.allclose(fit["se"], np.sqrt(np.diag(cov)))


def test_matched_comparison_returns_planted_shift_with_replacement():
    x_c = np.array([4.0, 5.0, 6.0, 7.0])
    y_c = np.array([0.50, 0.52, 0.55, 0.60])
    # Two treated units sit on the same control: matching is with replacement.
    x_t = np.array([5.0, 5.02, 6.99])
    y_t = y_c[[1, 1, 3]] + 0.03
    assert q14.match_nearest(x_t, x_c).tolist() == [1, 1, 3]
    est, gap = q14.matched_diff(y_t, x_t, y_c, x_c)
    assert est == pytest.approx(0.03)
    assert gap == pytest.approx((0 + 0.02 + 0.01) / 3)
    y_t2, x_t2, y_c2, x_c2 = _groups(effect=-0.01, seed=5)
    c = q14.compare_groups(y_t2, x_t2, y_c2, x_c2, n_boot=300)
    assert c["matched"]["replace"] is True
    assert c["matched"]["estimate"] == pytest.approx(-0.01, abs=0.01)


def test_paired_change_controls_for_activity_change():
    rng = np.random.default_rng(1)
    n = 40
    x0 = rng.normal(6, 0.5, n)
    dx = rng.normal(-1.0, 0.3, n)                   # contracts get quieter
    y0 = 0.4 + 0.03 * x0
    y1 = 0.4 + 0.03 * (x0 + dx) + 0.005 + rng.normal(0, 0.001, n)
    p = q14.paired_change(y1, y0, x0 + dx, x0, n_boot=300)
    assert p["controlled"]["estimate"] == pytest.approx(0.005, abs=0.002)
    assert p["controlled"]["slope_dlog10_events"] == pytest.approx(0.03, abs=0.005)
    assert p["median"]["state"] == "negative"       # raw change is driven by activity


def test_percentile_rank_counts_ties_as_half():
    assert q14.percentile_rank([1, 2, 3, 4], 3) == pytest.approx(62.5)
    assert q14.percentile_rank([1, 2, 3, 4], 10) == 100.0


# --------------------------------------------------------------------------
# Month completeness and the last-full-month rule
# --------------------------------------------------------------------------


def _ts(period: str, days: list[int], per_day: int = 3) -> np.ndarray:
    t0 = q14.month_start_day(period) * MS_PER_DAY
    return np.array([t0 + (d - 1) * MS_PER_DAY + k * 1000 for d in days for k in range(per_day)])


def test_coverage_and_completeness():
    full = q14.coverage("2024-02", _ts("2024-02", list(range(1, 30))))
    assert full == {"days_in_month": 29, "n_days": 29, "first_day": 1, "last_day": 29}
    assert q14.is_complete(full)
    one_gap = q14.coverage("2024-02", _ts("2024-02", [d for d in range(1, 30) if d != 10]))
    assert q14.is_complete(one_gap)
    two_gap = q14.coverage("2024-02", _ts("2024-02", [d for d in range(1, 30) if d not in (9, 10)]))
    assert not q14.is_complete(two_gap)
    stops = q14.coverage("2025-03", _ts("2025-03", list(range(1, 18))))  # delisted on the 17th
    assert not q14.is_complete(stops)
    late = q14.coverage("2023-06", _ts("2023-06", list(range(5, 31))))   # listed on the 5th
    assert not q14.is_complete(late)
    assert not q14.is_complete(q14.coverage("2023-06", np.array([], dtype=np.int64)))


def test_last_full_month_rule():
    cands = ["2025-03", "2025-02", "2025-01"]
    partial = q14.coverage("2025-03", _ts("2025-03", list(range(1, 18))))
    full_feb = q14.coverage("2025-02", _ts("2025-02", list(range(1, 29))))
    assert q14.choose_last_full_month(cands, {}) == ("check", "2025-03")
    assert q14.choose_last_full_month(cands, {"2025-03": partial}) == ("check", "2025-02")
    assert q14.choose_last_full_month(cands, {"2025-03": partial, "2025-02": full_feb}) == (
        "chosen", "2025-02")
    # A complete last month is used as it is.
    full_mar = q14.coverage("2025-03", _ts("2025-03", list(range(1, 32))))
    assert q14.choose_last_full_month(cands, {"2025-03": full_mar}) == ("chosen", "2025-03")
    # Nothing complete within the candidates: no unit, and the walk stops.
    bad = {m: partial for m in cands}
    assert q14.choose_last_full_month(cands, bad) == ("none", None)
    assert q14.choose_last_full_month(cands + ["2024-12"], bad)[0] == "none"


def test_activity_threshold():
    rng = np.random.default_rng(0)
    ts = np.sort(rng.integers(0, 30 * MS_PER_DAY, 200_000))
    c = q14.activity_counts(ts)
    assert c["n_events"] == 200_000
    assert q14.activity_reason(c) is None
    thin = q14.activity_counts(np.sort(rng.integers(0, 30 * MS_PER_DAY, 20_000)))
    assert "train rows" in q14.activity_reason(thin)


# --------------------------------------------------------------------------
# Universe and sampler
# --------------------------------------------------------------------------


def test_stratified_sampler_reproducible_and_covers_deciles():
    rng = np.random.default_rng(7)
    sizes = {f"S{i:03d}USDT": int(s) for i, s in enumerate(rng.lognormal(16, 1.5, 541))}
    a = q14.stratified_sample(sizes, per_bin=10, seed=0)
    b = q14.stratified_sample(sizes, per_bin=10, seed=0)
    assert a == b
    assert len(a) == 100
    assert sorted({d["decile"] for d in a}) == list(range(10))
    assert all(sum(d["decile"] == k for d in a) == 10 for k in range(10))
    assert len({d["symbol"] for d in a}) == 100
    # Every draw lies inside its own decile's size range.
    ranked = sorted(sizes, key=lambda s: (sizes[s], s))
    for d in a:
        r = ranked.index(d["symbol"])
        assert d["decile"] * 541 // 10 <= r < (d["decile"] + 1) * 541 // 10
    # A larger draw keeps the smaller one; another seed gives another draw.
    big = {d["symbol"] for d in q14.stratified_sample(sizes, per_bin=15, seed=0)}
    assert {d["symbol"] for d in a} <= big
    assert a != q14.stratified_sample(sizes, per_bin=10, seed=1)


def test_universe_constants_match_shipped_inventory():
    inv_path = REPO / "data" / q14.INVENTORY
    if not inv_path.exists():
        pytest.skip("inventory not present")
    uni = q14.build_universe(json.loads(inv_path.read_text()))
    st = [e["status"] for e in uni["contracts_2023_06"].values()]
    assert len(st) == 188
    assert st.count("survivor") == 135
    assert st.count("delisted") == 34 and st.count("renamed") == 10
    assert st.count("merged") == 2 and st.count("index") == 3
    assert uni["contracts_2023_06"]["MDTUSDT"]["status"] == "relisted"
    assert uni["new_listings"]["n_total"] == 541


def test_classification_refuses_unknown_ended_contract():
    perps = {s: {"2023-06": 1, "2026-07": 1, "2023-07": 1, "2024-07": 1, "2025-07": 1}
             for s in DEFAULT_SYMBOLS}
    perps["ZZZUSDT"] = {"2023-06": 5, "2024-01": 5}
    with pytest.raises(ValueError, match="ZZZUSDT"):
        q14.classify_2023(perps)


# --------------------------------------------------------------------------
# Pipeline: parquet safety
# --------------------------------------------------------------------------

PERIOD = "2023-06"


def _trades(period: str, n_days: int = 30, per_day: int = 3000, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    n = n_days * per_day
    y, m = int(period[:4]), int(period[5:7])
    t0 = int(datetime(y, m, 1, tzinfo=UTC).timestamp() * 1000)
    ts = t0 + np.arange(n, dtype=np.int64) * (n_days * MS_PER_DAY // n)
    return pl.DataFrame({
        "agg_trade_id": np.arange(n), "price": 100 + np.cumsum(rng.normal(0, 0.01, n)),
        "qty": np.ones(n), "first_trade_id": np.arange(n), "last_trade_id": np.arange(n),
        "ts": ts, "is_buyer_maker": rng.random(n) < 0.5,
    })


def _zip_fetch(tmp: Path, n_days: int = 30) -> callable:
    calls: list[tuple[str, str]] = []

    def fetch(symbol: str, period: str) -> Path:
        calls.append((symbol, period))
        df = _trades(period, n_days=n_days)
        buf = io.StringIO()
        df.write_csv(buf, include_header=False)
        zp = tmp / "zips" / f"{symbol}-aggTrades-{period}.zip"
        zp.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr(f"{symbol}-aggTrades-{period}.csv", buf.getvalue())
        return zp

    fetch.calls = calls
    return fetch


def _stub_fit(ws: q14.Workspace, symbol: str, period: str) -> Path:
    p = ws.cache / "q9" / f"{symbol}_{period}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"counts": {"n_events": 1, "n_test_rows": 1}, "scores": {}}))
    return p


def _write_parquet(root: Path, symbol: str, period: str) -> Path:
    df = _trades(period).with_columns(pl.col("ts").cast(pl.Datetime("ms", "UTC")))
    p = parquet_path(root, symbol, "aggTrades", period)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(p)
    return p


def test_pipeline_never_deletes_preexisting_parquet(tmp_path: Path):
    root = tmp_path / "data"
    pre = _write_parquet(root, "OLDUSDT", PERIOD)
    ws = q14.Workspace(root)
    fetch = _zip_fetch(tmp_path)
    st = q14.run_unit(ws, "OLDUSDT", PERIOD, fetch, fit=_stub_fit)
    assert st["status"] == "ok" and st["parquet_preexisting"] is True
    assert pre.exists() and not st["parquet_deleted"]
    assert fetch.calls == []

    # A failing fit on a pre-existing parquet still leaves it alone.
    pre2 = _write_parquet(root, "OLD2USDT", PERIOD)
    q14.Workspace(root).snapshot.unlink()           # retake the snapshot with OLD2 in it

    def boom(*_):
        raise RuntimeError("fit exploded")

    st = q14.run_unit(ws, "OLD2USDT", PERIOD, fetch, fit=boom)
    assert st["status"] == "failed" and "fit exploded" in st["reason"]
    assert pre2.exists()

    # A parquet that appears after the snapshot but was not made by Q14 stays too.
    later = _write_parquet(root, "LATEUSDT", PERIOD)
    st = q14.run_unit(ws, "LATEUSDT", PERIOD, fetch, fit=_stub_fit)
    assert later.exists() and st["parquet_preexisting"] is True

    # A unit Q14 downloads itself is ingested, fitted and then cleaned up.
    st = q14.run_unit(ws, "NEWUSDT", PERIOD, fetch, fit=_stub_fit)
    assert st["status"] == "ok" and st["parquet_deleted"] is True
    assert not parquet_path(root, "NEWUSDT", "aggTrades", PERIOD).exists()
    assert fetch.calls == [("NEWUSDT", PERIOD)]
    assert not any((tmp_path / "zips").glob("*.zip"))
    assert st["counts"]["n_events"] == 90_000
    # Resumable: a final status is not redone.
    assert q14.run_unit(ws, "NEWUSDT", PERIOD, fetch, fit=boom)["status"] == "ok"
    assert pre.exists() and pre2.exists() and later.exists()


def test_pipeline_marks_partial_month(tmp_path: Path):
    root = tmp_path / "data"
    ws = q14.Workspace(root)
    st = q14.run_unit(ws, "HALFUSDT", PERIOD, _zip_fetch(tmp_path, n_days=17), fit=_stub_fit)
    assert st["status"] == "partial" and "17 of 30" in st["reason"]
    assert not parquet_path(root, "HALFUSDT", "aggTrades", PERIOD).exists()


# --------------------------------------------------------------------------
# Report: verdict sentences flip with the planted numbers
# --------------------------------------------------------------------------

RUNG = ("majority", "persistence", "linear", "logit_signs", "gbm_signs", "logit_all", "gbm_all")


def _record(ws: q14.Workspace, sym: str, period: str, log_ev: float, acc: float) -> str:
    p = ws.cache / "q9" / f"{sym}_{period}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    scores = {r: {"accuracy": 0.5 + (acc - 0.5) * k / 6} for k, r in enumerate(RUNG)}
    p.write_text(json.dumps({"counts": {"n_events": int(10 ** log_ev), "n_test_rows": 50_000},
                             "scores": scores}))
    return ws.rel(p)


def _status(ws, sym, period, status="ok", record=None, cov_days=30, n_month=30,
            session=None):
    extra = {} if session is None else {"session": session,
                                        "equity_like": q14.is_equity_like(session)}
    ws.write_status({**extra, "symbol": sym, "period": period, "status": status, "reason": None,
                     "record": record, "reused_q9_cache": False,
                     "coverage": {"days_in_month": n_month, "n_days": cov_days, "first_day": 1,
                                  "last_day": cov_days},
                     "counts": {"n_events": 1, "n_train_scoreable": 1, "n_valid_scoreable": 1,
                                "n_test_rows": 1}})


def _world(tmp: Path, ended_effect: float, q9_boost: float, seed: int = 0) -> q14.Workspace:
    """Survivors and ended contracts with accuracy 0.40 + 0.03 log10 events, ended
    contracts a decade quieter, plus `ended_effect`; Q9's symbols get `q9_boost`."""
    rng = np.random.default_rng(seed)
    ws = q14.Workspace(tmp / "data")
    surv = list(DEFAULT_SYMBOLS) + [f"S{i:02d}USDT" for i in range(40)]
    ended = [f"D{i:02d}USDT" for i in range(30)]
    renamed = [f"R{i:02d}USDT" for i in range(6)]
    new = [f"N{i:02d}USDT" for i in range(30)] + ["EQAUSDT", "EQBUSDT"]
    c23: dict = {}
    for s in surv:
        c23[s] = {"symbol": s, "status": "survivor", "missing_study_months": [],
                  "last_month": "2026-10", "q9_symbol": s in DEFAULT_SYMBOLS}
    for s in ended:
        c23[s] = {"symbol": s, "status": "delisted", "missing_study_months": ["2026-07"],
                  "last_month": "2025-03"}
    for s in renamed:
        c23[s] = {"symbol": s, "status": "renamed", "missing_study_months": ["2026-07"],
                  "last_month": "2025-03", "successor": s.replace("R", "Q"),
                  "successor_first_month": "2025-03", "successor_lag_months": 0}
    c23["IDXUSDT"] = {"symbol": "IDXUSDT", "status": "index", "missing_study_months": ["2026-07"],
                      "last_month": "2024-03"}
    universe = {
        "archive_last_month": "2026-10", "n_perpetuals": 200, "contracts_2023_06": c23,
        "new_listings": {"n_total": 40, "n_listed_in_2026_07": 2, "listed_in_2026_07": [],
                         "n_frame": 38, "frame_zip_gb": 1.0, "per_decile": 3, "seed": 0,
                         "decile_edges_zip_bytes": [1e6 * k for k in range(11)],
                         "sample": [{"symbol": s, "decile": i % 10, "zip_bytes": 1}
                                    for i, s in enumerate(new)]},
        "last_month_candidates": {s: ["2025-03", "2025-02", "2025-01"] for s in ended + renamed},
        "zip_bytes": {s: {"2025-03": 1_000_000, "2025-02": 9_000_000} for s in ended + renamed},
    }
    ws.cache.mkdir(parents=True, exist_ok=True)
    ws.universe.write_text(json.dumps(universe))

    def acc(x, extra=0.0):
        return 0.40 + 0.03 * x + extra + rng.normal(0, 0.001)

    for s in surv:
        x = rng.normal(6.8 if s in DEFAULT_SYMBOLS else 6.3, 0.3)
        a = acc(x, q9_boost if s in DEFAULT_SYMBOLS else 0.0)
        _status(ws, s, "2023-06", record=_record(ws, s, "2023-06", x, a))
        _status(ws, s, "2026-07", record=_record(ws, s, "2026-07", x, a))
    for s in ended + renamed:
        x = rng.normal(5.3, 0.3)
        _status(ws, s, "2023-06", record=_record(ws, s, "2023-06", x, acc(x, ended_effect)))
        _status(ws, s, "2025-03", status="partial", cov_days=17, n_month=31)
        x2 = x - 0.5
        _status(ws, s, "2025-02", record=_record(ws, s, "2025-02", x2, acc(x2, ended_effect)),
                cov_days=28, n_month=28)
    crypto = {"version": q14.SESSION_VERSION, "weekend_ratio": 0.85, "us_session_median": 0.31}
    equity = {"version": q14.SESSION_VERSION, "weekend_ratio": 0.02, "us_session_median": 0.81}
    for s in new:
        x = rng.normal(5.8, 0.3)
        # The equity perpetuals are far more predictable; pooled, they would
        # flip the new-listing comparison.
        a = acc(x, 0.2 if s.startswith("EQ") else 0.0)
        _status(ws, s, "2026-07", record=_record(ws, s, "2026-07", x, a),
                session=equity if s.startswith("EQ") else crypto)
    return ws


def test_report_verdict_flips_with_planted_effects(tmp_path: Path):
    ws = _world(tmp_path / "a", ended_effect=-0.02, q9_boost=0.03)
    res = q14.build_result(ws, n_boot=200)
    c = res["comparisons"]["ended_vs_survivors_2023"]["gbm_all"]
    assert c["ols"]["state"] == "negative"
    assert res["last_month_resolution"]["D00USDT"]["chosen"] == "2025-02"
    assert res["groups"]["cross_2023"]["ended"]["n"] == 36
    v = res["verdict"]
    assert "less predictable" in v
    assert "overstates the typical contract" in v
    # Equity perpetuals are flagged, named and kept out of the crypto comparison.
    assert [f["symbol"] for f in res["equity_screen"]["flagged"]] == ["EQAUSDT", "EQBUSDT"]
    assert res["groups"]["cross_2026"]["new_listings"]["n"] == 30
    assert res["groups"]["cross_2026"]["new_listings_equity"]["n"] == 2
    assert res["comparisons"]["new_vs_survivors_2026"]["gbm_all"]["n_treat"] == 30
    assert "EQAUSDT, EQBUSDT" in v
    assert q14_report.representativeness(res)[0] == "overstates"

    ws = _world(tmp_path / "b", ended_effect=0.0, q9_boost=0.0)
    res = q14.build_result(ws, n_boot=200)
    c = res["comparisons"]["ended_vs_survivors_2023"]["gbm_all"]
    assert c["raw"]["state"] == "negative"          # quieter contracts look worse raw
    assert c["ols"]["state"] == "zero"
    v = res["verdict"]
    assert "The raw gap goes away once activity is held fixed" in v
    assert "less predictable" not in q14_report.comparison_sentence(
        res, "ended_vs_survivors_2023")
    # Q9 symbols are busier, so their median accuracy is above the universe's;
    # the verdict must say so plainly either way.
    assert ("overstates" in v) or ("is representative" in v)

    ws = _world(tmp_path / "c", ended_effect=+0.03, q9_boost=-0.03)
    res = q14.build_result(ws, n_boot=200)
    assert "were more predictable" in res["verdict"]
    assert q14_report.representativeness(res)[0] == "understates"


def test_report_files_have_no_long_dashes(tmp_path: Path):
    ws = _world(tmp_path, ended_effect=-0.02, q9_boost=0.03)
    res = q14.run_report(ws, tmp_path / "out", n_boot=100)
    md = (tmp_path / "out" / "q14_survivorship.md").read_text()
    assert "## Verdict" in md and res["verdict"] in md
    assert (tmp_path / "out" / "q14_survivorship.png").stat().st_size > 10_000
    json.loads((tmp_path / "out" / "q14_survivorship.json").read_text())
    src = [REPO / "src/microstructure/analyses/q14_survivorship.py",
           REPO / "src/microstructure/analyses/q14_report.py", Path(__file__)]
    for text in [md, res["verdict"], *(p.read_text() for p in src)]:
        assert chr(0x2014) not in text and chr(0x2013) not in text


def test_equity_screen_separates_session_profiles():
    rng = np.random.default_rng(0)
    start = q14.month_start_day("2026-07")
    t0 = start * MS_PER_DAY
    crypto = np.sort(t0 + rng.integers(0, 31 * MS_PER_DAY, 100_000))
    prof = q14.session_profile(crypto)
    assert prof["weekend_share"] == pytest.approx(8 / 31, abs=0.01)   # July 2026: 8 weekend days
    assert prof["weekend_ratio"] == pytest.approx(1.0, abs=0.1)
    assert prof["us_session_median"] == pytest.approx(6.5 / 24, abs=0.02)
    assert not q14.is_equity_like(prof)
    # A crypto coin with a pump on its last five weekdays: the monthly weekend
    # share collapses, the day medians do not (COTIUSDT in 2026-07).
    pump = np.concatenate([crypto, t0 + 26 * MS_PER_DAY
                           + rng.integers(0, 5 * MS_PER_DAY, 3_000_000)])
    prof = q14.session_profile(np.sort(pump))
    assert prof["weekend_share"] < 0.05
    assert not q14.is_equity_like(prof)
    # Equity-like: weekdays only, inside 13:30 to 20:00 UTC.
    days = [d for d in range(31) if (start + d + 3) % 7 < 5]
    eq = np.sort(np.concatenate([
        t0 + d * MS_PER_DAY + rng.integers(13 * 3_600_000 + 1_800_000, 20 * 3_600_000, 3000)
        for d in days]))
    prof = q14.session_profile(eq)
    assert prof["weekend_ratio"] == 0.0 and prof["us_session_median"] == 1.0
    assert q14.is_equity_like(prof)
    # Trades every day but concentrated in the US session: flagged on that signal.
    us_heavy = np.sort(np.concatenate([eq, t0 + rng.integers(0, 31 * MS_PER_DAY, 15_000)]))
    assert q14.is_equity_like(q14.session_profile(us_heavy))
    assert not q14.is_equity_like(None)


@pytest.mark.parametrize("header", [False, True])
def test_streaming_ingest_matches_repo_ingest(tmp_path: Path, header: bool):
    from microstructure.data.ingest import ingest_agg_trades
    df = _trades(PERIOD, n_days=2, per_day=500).with_columns(pl.col("ts") * 1000)  # microseconds
    df = df.sample(fraction=1.0, shuffle=True, seed=1)        # out of order: must be sorted
    buf = io.StringIO()
    df.write_csv(buf, include_header=header)
    zp = tmp_path / "XUSDT-aggTrades-2023-06.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("XUSDT-aggTrades-2023-06.csv", buf.getvalue())
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = pl.read_parquet(ingest_agg_trades(zp, tmp_path / "a"))
    b = pl.read_parquet(q14.ingest_agg_trades_streaming(zp, tmp_path / "b"))
    assert a.schema == b.schema
    assert a.equals(b)
    assert not any(p.suffix == ".csv" for p in tmp_path.rglob("*"))
