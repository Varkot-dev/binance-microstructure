"""End-to-end test for Q10 on synthetic trades with a planted regime change.

Two fake symbols, three periods. The sign process is a Markov chain with
P(repeat) = 0.7 in the first two periods and 0.45 in the third. A model
fitted in period 1 predicts "repeat": it stays right in period 2 and becomes
wrong more often than not in period 3, where a refitted model predicts
"flip". Known answers:

* staleness gap for period 2 near zero (the yardstick);
* staleness gap for period 3 near 0.55 - 0.45 = 0.10 of accuracy;
* predictability change for period 3 near 0.55 - 0.70 = -0.15;
* the old model's loss change lands in the concept residual, because given
  the last sign the model's loss does not depend on the rest of the history.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from microstructure.analyses.q10_drift import _parse_args, run_q10
from microstructure.analyses.q10_report import ladder_path, transfer_path
from microstructure.data.catalog import parquet_path
from microstructure.ml import drift, models
from microstructure.synthetic import markov_signs

SYMBOLS = ["AAAUSDT", "BBBUSDT"]
P_REPEAT = {"2023-06": 0.7, "2023-07": 0.7, "2026-07": 0.45}
PERIODS = list(P_REPEAT)
N_EVENTS = 60_000
FAST = {"linear_order": 20, "train_cap": 30_000, "gbm_rounds": 15, "sample_cap": 8_000,
        "domain_rounds": 30, "n_boot": 300}


def _write_month(root: Path, symbol: str, period: str, p_repeat: float, seed: int) -> None:
    rng = np.random.default_rng(seed)
    year, month = (int(v) for v in period.split("-"))
    t0 = int(datetime(year, month, 1, tzinfo=UTC).timestamp() * 1000)
    # 30 days of evenly spread events with jitter, strictly increasing (no tied ms).
    step = 30 * 86_400_000 // N_EVENTS
    ts = t0 + np.arange(N_EVENTS) * step + rng.integers(0, step // 2, size=N_EVENTS)
    signs = markov_signs(N_EVENTS, p_repeat, seed)
    df = pl.DataFrame({
        "agg_trade_id": np.arange(N_EVENTS),
        "price": 100.0 * np.exp(np.cumsum(rng.normal(scale=1e-4, size=N_EVENTS))),
        "qty": np.exp(rng.normal(size=N_EVENTS)),
        "first_trade_id": np.arange(N_EVENTS),
        "last_trade_id": np.arange(N_EVENTS),
        "ts": pl.Series(ts).cast(pl.Datetime("ms", "UTC")),
        "is_buyer_maker": signs < 0,
    })
    path = parquet_path(root, symbol, "aggTrades", period)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    root = tmp_path_factory.mktemp("q10")
    # One thread: on data this small LightGBM's thread pool costs more than it
    # saves, and it stalls badly when other jobs share the machine.
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(models.LGB_PARAMS, "num_threads", 1)
        mp.setitem(drift.DOMAIN_PARAMS, "num_threads", 1)
        yield _run(root)


def _run(root: Path):
    seed = 0
    for sym in SYMBOLS:
        for period, p in P_REPEAT.items():
            seed += 1
            _write_month(root, sym, period, p, seed)
    out = root / "results"
    result = run_q10(root, out, symbols=[*SYMBOLS, "MISSINGUSDT"], periods=PERIODS, **FAST)
    return root, out, result


def test_staleness_gap_is_zero_for_the_yardstick_and_positive_after_the_change(run):
    _, _, r = run
    assert r["symbols"] == SYMBOLS
    assert [s["symbol"] for s in r["skipped"]] == ["MISSINGUSDT"]
    dec = r["decomposition"]["accuracy"]["gbm_all"]
    yard, late = dec["2023-07"], dec["2026-07"]
    assert abs(yard["staleness_gap"]["median"]) < 0.02
    assert late["staleness_gap"]["median"] == pytest.approx(0.10, abs=0.03)
    assert late["staleness_gap"]["ci95"][0] > 0.05
    assert late["predictability_change"]["median"] == pytest.approx(-0.15, abs=0.03)
    assert late["n_symbols_gap_above_yardstick"] == 2
    for e in (yard, late):
        assert e["raw_drop"]["median"] == pytest.approx(
            e["staleness_gap"]["median"] - e["predictability_change"]["median"], abs=0.02)
    # The identity is exact per symbol.
    for sym in SYMBOLS:
        parts = {k: late[k]["per_symbol"][sym]["estimate"]
                 for k in ("raw_drop", "staleness_gap", "predictability_change")}
        assert parts["raw_drop"] == pytest.approx(
            parts["staleness_gap"] - parts["predictability_change"])
    # Log loss tells the same story, with positive G meaning retraining helps.
    loss = r["decomposition"]["log_loss_bits"]["gbm_all"]
    assert abs(loss["2023-07"]["staleness_gap"]["median"]) < 0.02
    assert loss["2026-07"]["staleness_gap"]["median"] > 0.1


def test_transfer_matrix_and_baseline_match_the_planted_process(run):
    _, _, r = run
    m = np.array(r["transfer"]["accuracy"]["gbm_all"]["median"])
    assert m[0, 0] == pytest.approx(0.70, abs=0.03)
    assert m[0, 1] == pytest.approx(0.70, abs=0.03)
    assert m[0, 2] == pytest.approx(0.45, abs=0.03)
    assert m[2, 2] == pytest.approx(0.55, abs=0.03)
    assert m[2, 0] == pytest.approx(0.30, abs=0.03)     # backward transfer is bad too
    assert r["repeat_last_accuracy"]["2026-07"]["median"] == pytest.approx(0.45, abs=0.02)
    # A Markov chain has nothing beyond one lag: no skill over the one-lag baseline.
    late = r["decomposition"]["accuracy"]["gbm_all"]["2026-07"]
    assert abs(late["skill_fresh"]["median"]) < 0.02
    assert late["skill_stale"]["median"] == pytest.approx(-0.10, abs=0.03)
    assert all(t["median"] == 0.0 for t in r["tie_share"].values())


def test_attribution_and_verdict_say_concept_shift_beyond_the_yardstick(run):
    _, _, r = run
    v = r["verdict"]
    assert v["class"] == "stale_beyond_yardstick"
    assert v["yardstick_gap_sign"] == 0
    assert v["attribution_dominant"] == "concept"
    assert "larger than the one-month yardstick" in v["text"]
    assert "is not distinguishable from zero" in v["text"]
    assert "above the yardstick on 2 of 2 symbols" in v["text"]
    assert "concept residual (the input-to-output relationship changed)" in v["text"]
    att = r["attribution"]["gbm_all"]
    assert att["2026-07"]["concept"]["median"] > 0.1
    assert abs(att["2026-07"]["covariate"]["median"]) < 0.3 * att["2026-07"]["concept"]["median"]
    assert abs(att["2023-07"]["concept"]["median"]) < 0.03
    auc = r["covariate_shift"]["auc"]
    # The slow EWMA features wander within a 60k-event month, so "no shift" is
    # only near 0.5 here, but it is far below the pair with changed dynamics:
    # a change in sign dynamics also moves the history features.
    assert abs(auc["2023-06__2023-07"]["median"] - 0.5) < 0.1
    assert auc["2023-06__2026-07"]["median"] > auc["2023-06__2023-07"]["median"] + 0.15


def test_coefficient_table_flags_the_sign_change(run):
    _, _, r = run
    feats = {row["feature"]: row for row in r["coefficients"]["features"]}
    changed = [f for f, row in feats.items() if row["changes"]["2026-07"]["sign_changed"]]
    assert changed, "the planted reversal of persistence must flip a sign-history coefficient"
    assert not any(row["changes"]["2023-07"]["sign_changed"] for row in feats.values()
                   if abs(row["median_by_period"]["2023-06"]) > 0.1)


def test_artifacts_written_and_stages_resume_from_cache(run):
    root, out, r = run
    for ext in ("json", "md", "png"):
        assert (out / f"q10_drift.{ext}").stat().st_size > 0
    stored = json.loads((out / "q10_drift.json").read_text())
    assert stored["verdict"]["text"] == r["verdict"]["text"]
    md = (out / "q10_drift.md").read_text()
    assert r["verdict"]["text"] in md
    for heading in ("## Question", "## Method", "## Results", "## Verdict", "## Caveats"):
        assert heading in md
    assert chr(0x2014) not in md and chr(0x2013) not in md

    cache = root / "ml_cache"
    watched = [ladder_path(cache, "AAAUSDT", "2023-06"), transfer_path(cache, "AAAUSDT", "2026-07")]
    before = [p.stat().st_mtime_ns for p in watched]
    again = run_q10(root, out, symbols=SYMBOLS, periods=PERIODS, **FAST)
    assert [p.stat().st_mtime_ns for p in watched] == before
    assert again["verdict"]["text"] == r["verdict"]["text"]
    # The report alone runs from caches: deleting the raw data must not matter.
    only = run_q10(root / "nowhere", out, symbols=SYMBOLS, periods=PERIODS, cache=cache,
                   stages=("report",), n_boot=FAST["n_boot"])
    assert only["verdict"]["class"] == r["verdict"]["class"]


def test_two_period_run_reports_the_yardstick_only(run):
    root, _, _ = run
    r = run_q10(root, root / "two", symbols=SYMBOLS, periods=PERIODS[:2],
                stages=("report",), n_boot=100)
    assert r["verdict"]["class"] == "yardstick_only"
    assert "multi-year question is not answered" in r["verdict"]["text"]


def test_cli_refuses_reduced_fits_into_the_shared_cache():
    with pytest.raises(SystemExit):
        _parse_args(["--gbm-rounds", "10"])
    assert _parse_args(["--gbm-rounds", "10", "--cache", "x"]).gbm_rounds == 10
