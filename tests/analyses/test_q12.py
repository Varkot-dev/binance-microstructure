"""Tests for Q12: neural point process as a predictability ceiling.

Contract under test:
1. End to end on a planted one-exponential Hawkes month: the protocol runs,
   every model is scored on the same test events, Hawkes and the network both
   beat Poisson by a margin, and the three artifacts plus the per-symbol
   cache are written. A second run reuses the cache; a missing symbol is
   logged as a failure without aborting.
2. The verdict is computed from the records: synthetic records with a planted
   sign of (neural minus best Hawkes) flip the counts and the reading.
3. The report stage runs from caches alone.

The pipeline test trains a very small network for one seed; it checks
plumbing and direction, not the size of the neural gain (tests/ml/test_tpp.py
covers what the model can and cannot find).
"""
from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from microstructure.analyses import q12_report
from microstructure.data.catalog import parquet_path
from microstructure.estimators.hawkes import simulate_hawkes_exp

MONTH = "2023-06"
SYMBOL = "PLANTUSDT"
# About 0.075 events per second over 28 days: ~180k events, ~6.5k per day.
MU, ALPHA, BETA = 0.03, 0.6, 0.5


def _write_month(root: Path, symbol: str) -> int:
    """A 28-day Hawkes stream as an aggTrades parquet (floor-stamped, sides alternating)."""
    t = simulate_hawkes_exp(MU, ALPHA, BETA, 28 * 86_400.0, seed=12)
    t0 = int(datetime(2023, 6, 1, tzinfo=UTC).timestamp() * 1000)
    ts = t0 + np.floor(t * 1000.0).astype(np.int64)
    n = ts.size
    frame = pl.DataFrame(
        {
            "agg_trade_id": np.arange(n), "price": np.full(n, 100.0), "qty": np.ones(n),
            "first_trade_id": np.arange(n), "last_trade_id": np.arange(n),
            "ts": ts, "is_buyer_maker": np.arange(n) % 2 == 0,
        }
    ).with_columns(pl.col("ts").cast(pl.Datetime("ms", "UTC")))
    path = parquet_path(root, symbol, "aggTrades", MONTH)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path)
    return n


def test_pipeline_on_planted_hawkes(tmp_data_dir: Path, tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    from microstructure.analyses import q12_neural_ceiling as q12
    from microstructure.ml import tpp

    _write_month(tmp_data_dir, SYMBOL)
    out = tmp_path / "results"
    args = q12._parse_args([
        "--burn-in", "400", "--hawkes-fit-events", "8000", "--hawkes-chunks", "1",
        "--polish-iters", "30", "--polish-events", "4000", "--n-seeds", "1", "--n-boot", "200",
        "--hidden", "12", "--components", "4", "--horizons-s", "10,100", "--window", "64",
        "--window-burn", "16", "--batch-size", "32", "--max-windows-per-epoch", "256",
        "--epochs", "4", "--lr", "0.004",
    ])
    cfg = q12.config_from_args(args)
    assert cfg.tpp.horizons_s == (10.0, 100.0) and cfg.threads == 1
    result = q12.run_q12(tmp_data_dir, out, [SYMBOL, "MISSINGUSDT"], [MONTH], cfg)

    assert [f["symbol"] for f in result["failures"]] == ["MISSINGUSDT"]
    (rec,) = result["records"]
    # 28 days: 20 train, 2 validation, 1 embargo, 5 test.
    assert rec["n_test_days"] == 5
    assert rec["n_train"] + rec["n_valid"] < rec["n_events"]
    assert sum(d["n"] for d in rec["per_day_loglik_sums"]) == rec["n_test_scored"]
    assert set(rec["models"]) == {"hawkes_k1", "hawkes_k2", "hawkes_k3", "neural"}
    # The planted self-excitation is worth a clear margin over Poisson to every Hawkes K
    # and to the network.
    for name, m in rec["models"].items():
        g = m["test_gain"]
        assert g["ci95"][0] <= g["estimate"] <= g["ci95"][1], name
        assert g["estimate"] > 0.1, name
    k1 = rec["hawkes"]["1"]["selected"]
    assert k1["n"] == pytest.approx(ALPHA, abs=0.12)
    # Residuals: the well-specified Hawkes is far closer to Exp(1) than Poisson.
    assert rec["residuals"]["hawkes_k1"]["ks_distance"] < 0.5 * rec["residuals"]["poisson"][
        "ks_distance"]
    assert rec["residuals"]["poisson"]["lag1_autocorr_u"] > 0.05
    # Per-day sums reproduce the headline difference.
    days = rec["per_day_loglik_sums"]
    best = rec["best_hawkes"]
    diff = sum(d["neural"] - d[best] for d in days) / rec["n_test_scored"]
    assert diff == pytest.approx(rec["neural_minus_best_hawkes"]["estimate"], abs=1e-9)
    buckets = rec["gap_buckets_neural_minus_best_hawkes"]
    assert sum(b["contribution"] for b in buckets[:-1]) == pytest.approx(diff, abs=1e-9)
    # The trial log records the budget that was used.
    assert rec["config"]["tpp"]["max_windows_per_epoch"] == 256
    assert rec["neural"]["seeds"][0]["history"][0]["epoch"] == 0
    assert rec["torch_version"] == torch.__version__

    for suffix in ("json", "md", "png"):
        assert (out / f"q12_neural_ceiling.{suffix}").stat().st_size > 0
    md = (out / "q12_neural_ceiling.md").read_text()
    for section in ("## Question", "## Method", "## Verdict", "## Caveats"):
        assert section in md
    assert result["verdict"]["headline"] in md
    assert "\u2014" not in md and "\u2013" not in md  # no em or en dashes in the write-up
    json.loads((out / "q12_neural_ceiling.json").read_text())

    # Cached: a second run must not retrain (training would raise here).
    cache = q12.cache_path(tmp_data_dir, SYMBOL, MONTH)
    assert cache.exists()

    def boom(*a, **k):
        raise AssertionError("retrained despite a matching cache")

    original = tpp.train_tpp
    tpp.train_tpp = boom
    try:
        again = q12.run_q12(tmp_data_dir, out, [SYMBOL], [MONTH], cfg)
    finally:
        tpp.train_tpp = original
    assert again["records"][0]["models"] == rec["models"]
    # The report stage alone rebuilds the artifacts from the cache.
    out2 = tmp_path / "results2"
    q12_report.main(["--root", str(tmp_data_dir), "--out", str(out2)])
    assert json.loads((out2 / "q12_neural_ceiling.json").read_text())["verdict"] == result[
        "verdict"]


def _record(symbol: str, gains: dict[str, float], gap_ci: tuple[float, float, float]) -> dict:
    """Minimal record with planted gains over Poisson and a planted neural-minus-best interval."""
    est, lo, hi = gap_ci
    models = {m: {"test_gain": {"estimate": g, "ci95": [g - 0.01, g + 0.01], "n_days": 7},
                  "valid_gain": g} for m, g in gains.items()}
    for m, entry in models.items():
        if m != "neural":
            entry["share_of_neural_gain"] = (
                gains[m] / gains["neural"] if gains["neural"] > 0 else None)
    return {
        "symbol": symbol, "month": MONTH, "n_events": 1000, "models": models,
        "best_hawkes": "hawkes_k3",
        "neural_minus_best_hawkes": {"estimate": est, "ci95": [lo, hi], "n_days": 7},
        "neural": {"seed_spread_test_gain": 0.001, "seeds": [{"seed": 0}, {"seed": 1}]},
    }


def test_verdict_follows_the_numbers() -> None:
    hawkes = {"hawkes_k1": 0.10, "hawkes_k2": 0.20, "hawkes_k3": 0.30}
    wins = [_record(f"W{i}", {**hawkes, "neural": 0.40}, (0.10, 0.08, 0.12)) for i in range(3)]
    v = q12_report.summarize(wins)
    assert (v["n_neural_better"], v["n_hawkes_better"], v["n_indistinguishable"]) == (3, 0, 0)
    assert v["n_material"] == 3
    assert v["median_share_of_neural_gain"]["hawkes_k3"] == pytest.approx(0.75)
    assert v["median_share_of_neural_gain"]["hawkes_k1"] == pytest.approx(0.25)
    assert "leaves one-step-ahead timing structure unexplained" in v["reading"]
    assert "above zero on 3 of 3" in v["headline"]

    ties = [_record(f"T{i}", {**hawkes, "neural": 0.302}, (0.002, -0.004, 0.008))
            for i in range(3)]
    v = q12_report.summarize(ties)
    assert (v["n_neural_better"], v["n_indistinguishable"], v["n_material"]) == (0, 3, 0)
    assert "close to what this network extracts" in v["reading"]

    # Resolved but below the materiality threshold does not count as material.
    small = [_record("S", {**hawkes, "neural": 0.305}, (0.005, 0.002, 0.008))]
    v = q12_report.summarize(small)
    assert (v["n_neural_better"], v["n_material"]) == (1, 0)

    losses = [_record(f"L{i}", {**hawkes, "neural": 0.25}, (-0.05, -0.07, -0.03))
              for i in range(2)]
    v = q12_report.summarize(losses + wins[:1])
    assert (v["n_neural_better"], v["n_hawkes_better"]) == (1, 2)
    assert "not a ceiling" in v["reading"]

    # Seed spread at least as large as the gap is flagged.
    fragile = copy.deepcopy(ties[0])
    fragile["neural"]["seed_spread_test_gain"] = 0.01
    assert q12_report.summarize([fragile])["n_seed_spread_exceeds_gap"] == 1
    assert q12_report.summarize(ties[:1])["n_seed_spread_exceeds_gap"] == 0

    # No skill over Poisson: shares are undefined, not divided by a non-positive number.
    flat = _record("F", {**hawkes, "neural": -0.01}, (-0.31, -0.33, -0.29))
    v = q12_report.summarize([flat])
    assert v["median_share_of_neural_gain"]["hawkes_k1"] is None
    assert v["n_neural_not_above_poisson"] == 1
    assert q12_report.summarize([])["n_units"] == 0
    assert q12_report.classify({"ci95": [0.0, 0.1]}) == "indistinguishable"


def test_hawkes_fit_problems_flags_degenerate_and_losing_fits():
    from microstructure.analyses.q12_report import hawkes_fit_problems

    def fit(betas):
        return {"selected": {"betas": betas, "converged": True}}

    record = {
        "hawkes": {"1": fit([40.0]), "2": fit([0.7, 90.0]), "3": fit([1e308, 26.0, 1e-17])},
        "models": {"hawkes_k1": {"test_gain": {"estimate": -0.13}},
                   "hawkes_k2": {"test_gain": {"estimate": 0.27}},
                   "hawkes_k3": {"test_gain": {"estimate": -0.84}}},
    }
    assert hawkes_fit_problems(record) == [
        "K=1 scores below Poisson on test", "K=3 fit is degenerate"]
    record["hawkes"] = {"2": fit([0.7, 90.0])}
    assert hawkes_fit_problems(record) == []
