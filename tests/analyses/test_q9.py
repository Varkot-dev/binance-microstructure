"""Q9 on synthetic trades with known answers.

Three planted worlds: Markov signs (only the last sign matters, so no rung may
beat persistence), IID signs (nothing is predictable) and a size-dependent
rule that only a nonlinear model with size features can see. The ladder must
report each for what it is before its real-data numbers are trusted.
"""
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from microstructure.analyses import q9_report
from microstructure.analyses.q9_sign_prediction import (
    cache_root,
    fit_cache_path,
    fit_symbol,
    holdout_cache_path,
    holdout_symbol,
    increment_day_sums,
    ladder_path,
    pool_days,
    predict_chunked,
    run_report,
    run_stage,
    sums_block_ci,
)
from microstructure.data.catalog import parquet_path
from microstructure.ml.dataset import load_sign_dataset
from microstructure.ml.evaluate import MS_PER_DAY, day_block_ci, log_loss_bits
from microstructure.ml.ladder import (
    FINGERPRINT_KEY,
    RUNGS,
    Ladder,
    daily_sums,
    ladder_fingerprint,
    predict_ladder,
)
from microstructure.ml.models import LGB_PARAMS
from microstructure.synthetic import iid_signs, markov_signs

PERIOD, HOLDOUT = "2023-06", "2023-07"
PER_DAY = 4000
FIT_KW = {"linear_order": 50, "train_cap": 50_000, "gbm_rounds": 60}
MARKOV = ("MKVAUSDT", "MKVBUSDT")
PLANTED = ("PLNAUSDT", "PLNBUSDT")
IID = ("IIDAUSDT",)


def _planted(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Signs repeat with probability 0.8 after a large trade and 0.3 after a
    small one. The average repeat rate is 0.55, which is all a sign-only model
    can use; knowing the size of the last trade lifts accuracy to 0.75."""
    rng = np.random.default_rng(seed)
    large = rng.random(n) < 0.5
    qty = np.where(large, 5.0, 0.2)
    p_rep = np.where(large, 0.8, 0.3)
    repeat = rng.random(n) < np.concatenate([[1.0], p_rep[:-1]])
    signs = np.cumprod(np.where(repeat, 1, -1)).astype(np.int8)
    return signs, qty


def _write(root: Path, symbol: str, period: str, n_days: int, signs: np.ndarray,
           qty: np.ndarray | None = None, seed: int = 0) -> None:
    n = signs.size
    assert n == n_days * PER_DAY
    year, month = (int(x) for x in period.split("-"))
    t0 = int(datetime(year, month, 1, tzinfo=UTC).timestamp() * 1000)
    ts = t0 + np.arange(n, dtype=np.int64) * (MS_PER_DAY // PER_DAY)
    rng = np.random.default_rng(seed + 999)
    df = pl.DataFrame({
        "agg_trade_id": np.arange(n),
        "price": 100.0 * np.exp(np.cumsum(1e-4 * rng.standard_normal(n))),
        "qty": np.ones(n) if qty is None else qty,
        "first_trade_id": np.arange(n),
        "last_trade_id": np.arange(n),
        "ts": pl.Series(ts).cast(pl.Datetime("ms", "UTC")),
        "is_buyer_maker": signs < 0,
    })
    p = parquet_path(root, symbol, "aggTrades", period)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(p)


@pytest.fixture(scope="module")
def world(tmp_path_factory) -> Path:
    """Synthetic months for every case, fitted once and shared by the tests."""
    root = tmp_path_factory.mktemp("q9")
    seed = 0
    for period, n_days in ((PERIOD, 28), (HOLDOUT, 10)):
        n = n_days * PER_DAY
        for sym in MARKOV:
            seed += 1
            _write(root, sym, period, n_days, markov_signs(n, 0.7, seed), seed=seed)
        for sym in PLANTED:
            seed += 1
            signs, qty = _planted(n, seed)
            _write(root, sym, period, n_days, signs, qty, seed=seed)
    _write(root, IID[0], PERIOD, 28, iid_signs(28 * PER_DAY, 77), seed=77)
    symbols = [*MARKOV, *PLANTED, *IID]
    # One LightGBM thread: these fits are tiny, and four threads per process
    # stall badly when the machine is already busy.
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(LGB_PARAMS, "num_threads", 1)
        assert run_stage("fit", root, symbols, PERIOD, HOLDOUT, **FIT_KW) == []
    assert run_stage("next", root, [*MARKOV, *PLANTED], PERIOD, HOLDOUT, **FIT_KW) == []
    return root


def _fit(root: Path, symbol: str) -> dict:
    return json.loads(fit_cache_path(cache_root(root), symbol, PERIOD).read_text())


def test_markov_every_rung_matches_persistence(world: Path):
    for sym in MARKOV:
        rec = _fit(world, sym)
        acc = {r: rec["scores"][r]["accuracy"] for r in RUNGS}
        assert abs(acc["majority"] - 0.5) < 0.03
        for rung in RUNGS[1:]:
            assert abs(acc[rung] - 0.70) < 0.015, (sym, rung, acc[rung])
        for rung in ("linear", "gbm_signs", "gbm_all"):
            assert acc[rung] - acc["persistence"] < 0.005
        # Counts and the split are what the dataset module promises.
        c = rec["counts"]
        assert c["n_events"] == 28 * PER_DAY and c["n_test_days"] == 5
        assert c["n_train_rows_used"] == FIT_KW["train_cap"] < c["n_train_scoreable"]
        assert c["tie_share"] == 0.0
        assert abs(rec["acf"]["acf1"] - 0.4) < 0.03
        assert abs(sum(rec["gbm"]["gbm_all"]["gain_share"].values()) - 1.0) < 1e-9


def test_iid_nothing_is_predictable(world: Path):
    rec = _fit(world, IID[0])
    for rung in RUNGS:
        assert abs(rec["scores"][rung]["accuracy"] - 0.5) < 0.02, rung
        assert rec["scores"][rung]["log_loss_bits"] > 0.99


def test_planted_size_rule_is_found_by_gbm_all_only(world: Path):
    for sym in PLANTED:
        acc = {r: _fit(world, sym)["scores"][r]["accuracy"] for r in RUNGS}
        assert abs(acc["linear"] - 0.55) < 0.02
        assert abs(acc["gbm_signs"] - 0.55) < 0.02
        assert abs(acc["gbm_all"] - 0.75) < 0.02
        assert acc["gbm_all"] - acc["linear"] > 0.15
        # The frozen ladder keeps the edge in a month it never saw.
        nxt = json.loads(
            holdout_cache_path(cache_root(world), sym, PERIOD, HOLDOUT).read_text())
        assert abs(nxt["scores"]["gbm_all"]["accuracy"] - 0.75) < 0.02
        assert nxt["counts"]["n_rows"] == 10 * PER_DAY - 5120


def test_report_runs_from_caches_and_verdict_follows_the_data(world: Path, tmp_path: Path):
    cache = cache_root(world)
    res_m = run_report(tmp_path / "markov", cache, list(MARKOV), PERIOD, HOLDOUT, n_boot=500)
    res_p = run_report(tmp_path / "planted", cache, list(PLANTED), PERIOD, HOLDOUT, n_boot=500)
    for d in ("markov", "planted"):
        for ext in ("json", "md", "png"):
            assert (tmp_path / d / f"q9_sign_prediction.{ext}").stat().st_size > 0
        md = (tmp_path / d / "q9_sign_prediction.md").read_text()
        for section in ("## Question", "## Method", "## Results", "## Verdict", "## Caveats"):
            assert section in md
        assert chr(0x2014) not in md and chr(0x2013) not in md
        on_disk = json.loads((tmp_path / d / "q9_sign_prediction.json").read_text())
        assert on_disk["verdict"] in md

    pos = q9_report.STATE_PHRASE["positive"]
    ctx_p = q9_report.increment_sentence(res_p, "context")
    ctx_m = q9_report.increment_sentence(res_m, "context")
    assert "pooled accuracy gain +0.2" in ctx_p or "pooled accuracy gain +0.1" in ctx_p
    assert ctx_p.split(";")[0].endswith(pos)
    assert not ctx_m.split(";")[0].endswith(pos)
    assert ctx_p in res_p["verdict"] and ctx_m in res_m["verdict"]
    assert res_m["verdict"] != res_p["verdict"]

    pooled_p = res_p["within_month"]["pooled"]
    assert pooled_p["context"]["accuracy"]["state"] == "positive"
    assert pooled_p["context"]["log_loss"]["state"] == "positive"
    assert res_p["within_month"]["increments_summary"]["context"]["accuracy"]["n_positive"] == 2
    assert pooled_p["context"]["accuracy"]["n_days"] == 5  # a day is one block across symbols
    for key in ("memory", "nonlinearity", "context"):
        assert res_m["within_month"]["pooled"][key]["accuracy"]["state"] != "positive"
        assert abs(res_m["within_month"]["pooled"][key]["accuracy"]["estimate"]) < 0.01
    assert res_p["next_month"]["pooled"]["context"]["accuracy"]["state"] == "positive"
    assert res_p["next_month"]["pooled_n_days"] == 9  # day 1 is partly warm-up, still a block

    for res in (res_m, res_p):
        assert "None of this is a trading result" in res["verdict"]
        assert "no fees" in res["verdict"]
        tl = res["trial_log"]
        assert tl["n_distinct_configurations"] == 1 and tl["n_model_fits"] == 10
        cfg = tl["configurations"][0]["config"]
        assert cfg["linear_order"] == 50 and cfg["train_cap"] == 50_000
        assert cfg["lgb_max_rounds"] == 60 and cfg["lgb_params"]["num_leaves"] == 63

    # Without next-month caches the report says so instead of inventing a comparison.
    res_i = run_report(tmp_path / "iid", cache, [*IID, "ABSENTUSDT"], PERIOD, HOLDOUT, n_boot=200)
    assert res_i["next_month"] is None and "No next-month scores" in res_i["verdict"]
    assert res_i["symbols_without_cache"] == ["ABSENTUSDT"]
    with pytest.raises(FileNotFoundError):
        run_report(tmp_path / "none", cache, ["ABSENTUSDT"], PERIOD, HOLDOUT)


def test_sums_bootstrap_matches_day_block_ci():
    rng = np.random.default_rng(3)
    parts = []
    for k in range(2):
        n = 6000 + 1000 * k
        # Symbol 1 misses the first day, so pooling must align on calendar days.
        ts = np.sort(rng.integers(k * MS_PER_DAY, 9 * MS_PER_DAY, size=n)) + 19_500 * MS_PER_DAY
        y = (rng.random(n) < 0.5).astype(np.float64)
        pa = np.clip(0.5 + 0.2 * (y - 0.5) + 0.3 * rng.standard_normal(n), 0.01, 0.99)
        pb = np.clip(0.5 + 0.4 * (y - 0.5) + 0.3 * rng.standard_normal(n), 0.01, 0.99)
        parts.append((ts, y, pa, pb))

    def correct(y, p):
        return ((p >= 0.5) == (y > 0.5)).astype(np.float64)

    dailies = [daily_sums(y, ts, {"a": pa, "b": pb}) for ts, y, pa, pb in parts]
    for (ts, y, pa, pb), daily in zip(parts, dailies, strict=True):
        ref = {
            "accuracy": day_block_ci(correct(y, pb), correct(y, pa), ts, n_boot=400, seed=5),
            "log_loss": day_block_ci(log_loss_bits(y, pa), log_loss_bits(y, pb), ts,
                                     n_boot=400, seed=5),
        }
        for metric, want in ref.items():
            _, s, c = increment_day_sums(daily, "a", "b", metric)
            got = sums_block_ci(s, c, n_boot=400, seed=5)
            assert got.n_days == want.n_days
            np.testing.assert_allclose(
                [got.estimate, got.lo, got.hi], [want.estimate, want.lo, want.hi], atol=1e-12)
            assert got.estimate > 0  # b is the better forecast by construction

    # Pooled: summing each day's sums across symbols equals day_block_ci on the
    # concatenated events, where a calendar day is one block.
    ts_all = np.concatenate([p[0] for p in parts])
    d_all = np.concatenate([correct(y, pb) - correct(y, pa) for _, y, pa, pb in parts])
    want = day_block_ci(d_all, None, ts_all, n_boot=400, seed=5)
    days, s, c = pool_days([increment_day_sums(d, "a", "b", "accuracy") for d in dailies])
    got = sums_block_ci(s, c, n_boot=400, seed=5)
    assert days.size == want.n_days == 9
    np.testing.assert_allclose(
        [got.estimate, got.lo, got.hi], [want.estimate, want.lo, want.hi], atol=1e-12)


def test_chunked_prediction_equals_one_pass(world: Path):
    ds = load_sign_dataset(world, PLANTED[0], HOLDOUT)
    ladder = Ladder.load(ladder_path(cache_root(world), PLANTED[0], PERIOD))
    rows = np.flatnonzero(ds.scoreable)
    full = predict_ladder(ladder, ds, rows)
    chunked = predict_chunked(ladder, ds, rows, chunk_rows=7001)
    for rung in RUNGS:
        np.testing.assert_allclose(chunked[rung], full[rung], rtol=0, atol=1e-12)


def test_stages_resume_and_holdout_never_refits(world: Path):
    cache = cache_root(world)
    sym = MARKOV[0]
    fit_path, lad_path = fit_cache_path(cache, sym, PERIOD), ladder_path(cache, sym, PERIOD)
    before = (fit_path.stat().st_mtime_ns, lad_path.stat().st_mtime_ns, lad_path.read_bytes())
    assert fit_symbol(world, sym, PERIOD, **FIT_KW) == fit_path
    holdout_symbol(world, sym, PERIOD, HOLDOUT, force=True)
    assert before == (fit_path.stat().st_mtime_ns, lad_path.stat().st_mtime_ns,
                      lad_path.read_bytes())
    with pytest.raises(ValueError):
        holdout_symbol(world, sym, PERIOD, PERIOD)
    # A symbol with no data is recorded as a failure and does not stop the run.
    failures = run_stage("fit", world, ["ABSENTUSDT"], PERIOD, HOLDOUT, **FIT_KW)
    assert [f["symbol"] for f in failures] == ["ABSENTUSDT"]


def test_refit_invalidates_the_holdout_cache(world: Path, tmp_path: Path):
    root = tmp_path / "copy"
    shutil.copytree(world, root)
    cache, sym = cache_root(root), MARKOV[0]
    lad, nxt = ladder_path(cache, sym, PERIOD), holdout_cache_path(cache, sym, PERIOD, HOLDOUT)
    old_fp = ladder_fingerprint(lad)
    assert json.loads(nxt.read_text())[FINGERPRINT_KEY] == old_fp
    assert _fit(root, sym)[FINGERPRINT_KEY] == old_fp
    stamp = nxt.stat().st_mtime_ns
    holdout_symbol(root, sym, PERIOD, HOLDOUT)
    assert nxt.stat().st_mtime_ns == stamp  # same ladder: the cache is reused

    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(LGB_PARAMS, "num_threads", 1)
        fit_symbol(root, sym, PERIOD, force=True, **{**FIT_KW, "gbm_rounds": 5})
    new_fp = ladder_fingerprint(lad)
    assert new_fp != old_fp and _fit(root, sym)[FINGERPRINT_KEY] == new_fp
    # Until the holdout is rescored the report leaves the stale file out and says so.
    res = run_report(tmp_path / "stale", cache, list(MARKOV), PERIOD, HOLDOUT, n_boot=100)
    assert res["next_month_symbols"] == [MARKOV[1]]
    assert res["next_month_stale_symbols"] == [sym]
    assert sym in (tmp_path / "stale" / "q9_sign_prediction.md").read_text().split(
        "since been refitted:")[1]
    holdout_symbol(root, sym, PERIOD, HOLDOUT)  # no force: the mismatch alone triggers it
    assert json.loads(nxt.read_text())[FINGERPRINT_KEY] == new_fp
    res = run_report(tmp_path / "fresh", cache, list(MARKOV), PERIOD, HOLDOUT, n_boot=100)
    assert res["next_month_symbols"] == list(MARKOV) and not res["next_month_stale_symbols"]

    # A cache written before fingerprints existed is a mismatch, not a crash.
    rec = json.loads(nxt.read_text())
    del rec[FINGERPRINT_KEY]
    nxt.write_text(json.dumps(rec))
    holdout_symbol(root, sym, PERIOD, HOLDOUT)
    assert json.loads(nxt.read_text())[FINGERPRINT_KEY] == new_fp


def test_failed_symbol_is_reported_with_its_reason_not_from_a_stale_cache(
        world: Path, tmp_path: Path):
    root = tmp_path / "copy"
    shutil.copytree(world, root)
    cache, sym = cache_root(root), MARKOV[0]
    # The month disappears, then a forced refit fails; the old fit JSON is still on disk.
    parquet_path(root, sym, "aggTrades", PERIOD).unlink()
    failures = run_stage("fit", root, [sym], PERIOD, HOLDOUT, force=True, **FIT_KW)
    assert [(f["symbol"], f["stage"]) for f in failures] == [(sym, "fit")]
    assert failures[0]["reason"] and fit_cache_path(cache, sym, PERIOD).exists()
    res = run_report(tmp_path / "out", cache, list(MARKOV), PERIOD, HOLDOUT, n_boot=100,
                     failures=failures)
    assert res["symbols"] == [MARKOV[1]] and sym not in res["within_month"]["per_symbol"]
    assert res["next_month_symbols"] == [MARKOV[1]]
    assert res["symbols_without_cache"] == []
    on_disk = json.loads((tmp_path / "out" / "q9_sign_prediction.json").read_text())
    assert on_disk["failures"] == failures
    md = (tmp_path / "out" / "q9_sign_prediction.md").read_text()
    assert f"{sym} (fit stage: {failures[0]['reason']})" in md
    assert chr(0x2014) not in md and chr(0x2013) not in md
    # Without the failure record the same call would have reported the old numbers.
    assert sym in run_report(tmp_path / "old", cache, list(MARKOV), PERIOD, HOLDOUT,
                             n_boot=100)["symbols"]
    # A holdout failure keeps the within-month scores and drops only the next-month block.
    nxt_fail = [{"symbol": MARKOV[1], "stage": "next", "reason": "boom"}]
    res = run_report(tmp_path / "nxt", cache, [MARKOV[1]], PERIOD, HOLDOUT, n_boot=100,
                     failures=nxt_fail)
    assert res["symbols"] == [MARKOV[1]] and res["next_month"] is None
