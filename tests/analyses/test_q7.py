"""Tests for Q7: execution-cost schedule comparison.

Contract under test:
1. Symbol selection: 6 symbols at ranks 1,4,7,10,13,16 of the panel's Q5
   n_events ordering (spanning the panel's activity range), chosen
   programmatically from the kernels json, never hardcoded.
2. `run_q7` runs each symbol x day x side x parent_qty_events combination
   through TWAP / front-loaded / reactive, with reactive's (lookback,
   pause_threshold) calibrated only on days 1-3 and evaluated only on days
   4-7. No-leakage check: planting different data on the evaluation days
   leaves the chosen params and calibration scores unchanged, while planting
   different data on the calibration days changes the scores.
3. Shortfall is in bps of the arrival mid: two symbols with the same relative
   path but prices 1000x apart report the same shortfall.
4. Calibration-stage failures land in `failures`; a negative G[1] is a
   recorded failure, not a crash; an all-failed calibration raises a clear
   ValueError.
5. Output files (.md, .json, .png) exist and the json is strict (no NaN);
   the reactive-vs-twap sentence follows the paired SE.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from microstructure.analyses.q7_execution import (
    REACTIVE_GRID,
    _build_calibration_scorer,
    _pick_panel_symbols,
    _reactive_vs_twap_lines,
    calibrate_reactive_params,
    run_q7,
)
from microstructure.data.catalog import parquet_path

DAYS = [f"2023-06-0{d}" for d in range(1, 8)]
CALIB_DAYS = DAYS[:3]
EVAL_DAYS = DAYS[3:]


# --------------------------------------------------------------------------
# _pick_panel_symbols: pure, rank-based selection
# --------------------------------------------------------------------------


def test_pick_panel_symbols_selects_ranks_1_4_7_10_13_16():
    # 16 fake records with distinct n_events, symbols named by descending rank.
    records = [{"symbol": f"SYM{i:02d}", "n_events": 16 - i} for i in range(16)]
    kernels = {"records": records}
    picked = _pick_panel_symbols(kernels, n_pick=6)
    # sorted by n_events descending: SYM00 (rank1) .. SYM15 (rank16)
    expected_ranks = [1, 4, 7, 10, 13, 16]
    expected = [f"SYM{r - 1:02d}" for r in expected_ranks]
    assert picked == expected


def test_pick_panel_symbols_handles_fewer_than_16_gracefully():
    records = [{"symbol": f"SYM{i:02d}", "n_events": 10 - i} for i in range(8)]
    kernels = {"records": records}
    picked = _pick_panel_symbols(kernels, n_pick=6)
    assert len(picked) == 6
    assert len(set(picked)) == 6


# --------------------------------------------------------------------------
# calibrate_reactive_params: grid search, no leakage
# --------------------------------------------------------------------------


def test_calibrate_reactive_params_picks_grid_argmax():
    """Feed a hand-scored advantage table and confirm the argmax is returned."""

    def fake_scorer(lookback: int, pause_threshold: float) -> float:
        # Planted maximum at (200, 0.4).
        table = {
            (50, 0.2): 0.01,
            (50, 0.4): 0.02,
            (200, 0.2): 0.015,
            (200, 0.4): 0.05,
        }
        return table[(lookback, pause_threshold)]

    lookback, pause_threshold, scores = calibrate_reactive_params(fake_scorer)
    assert (lookback, pause_threshold) == (200, 0.4)
    assert scores[(200, 0.4)] == pytest.approx(0.05)
    assert set(scores.keys()) == set(REACTIVE_GRID)


def test_calibrate_reactive_params_raises_clear_error_when_nothing_scores():
    with pytest.raises(ValueError, match="no finite score"):
        calibrate_reactive_params(lambda lookback, pause_threshold: float("-inf"))


# --------------------------------------------------------------------------
# run_q7: full synthetic pipeline through parquet fixtures
# --------------------------------------------------------------------------


def _write_symbol_week(
    root: Path,
    symbol: str,
    seed: int,
    n_per_day: int = 3000,
    price_scale: float = 1.0,
    eval_seed: int | None = None,
    skip_bt_days: tuple[str, ...] = (),
) -> None:
    """One week (2023-06-01..07) of synthetic aggTrades + bookTicker.

    Flat-ish random-walk mids, i.i.d. random signs -- no planted structure,
    just enough real data flow for the full pipeline (replay -> schedules
    -> shortfall) to execute end-to-end without error.

    `seed` drives days 1-3 (the calibration window) and `eval_seed`, if given,
    drives days 4-7. `price_scale` multiplies prices and the quoted half-spread,
    leaving the relative path unchanged. Days in `skip_bt_days` get no
    bookTicker file.
    """
    rng = np.random.default_rng(seed)
    eval_rng = np.random.default_rng(eval_seed) if eval_seed is not None else rng
    month = "2023-06"

    all_ts: list[datetime] = []
    all_signs: list[int] = []
    all_qty: list[float] = []
    all_price: list[float] = []
    for day_idx, day in enumerate(DAYS):
        day_rng = rng if day in CALIB_DAYS else eval_rng
        day_start = datetime(2023, 6, 1 + day_idx, 0, 0, 0, tzinfo=UTC)
        signs = day_rng.choice(np.array([-1, 1], dtype=np.int8), size=n_per_day)
        qtys = day_rng.uniform(0.5, 2.0, size=n_per_day)
        price_walk = price_scale * (100.0 + np.cumsum(day_rng.normal(0, 0.001, size=n_per_day)))
        for i in range(n_per_day):
            all_ts.append(day_start + timedelta(milliseconds=5 * i))
            all_signs.append(int(signs[i]))
            all_qty.append(float(qtys[i]))
            all_price.append(float(price_walk[i]))

    n = len(all_ts)
    agg = pl.DataFrame(
        {
            "agg_trade_id": np.arange(n),
            "price": all_price,
            "qty": all_qty,
            "first_trade_id": np.arange(n),
            "last_trade_id": np.arange(n),
            "ts": all_ts,
            "is_buyer_maker": [s < 0 for s in all_signs],
        },
        schema_overrides={"ts": pl.Datetime("ms", "UTC")},
    )
    agg_path = parquet_path(root, symbol, "aggTrades", month)
    agg_path.parent.mkdir(parents=True, exist_ok=True)
    agg.write_parquet(agg_path)

    for day_idx, day in enumerate(DAYS):
        if day in skip_bt_days:
            continue
        day_start = datetime(2023, 6, 1 + day_idx, 0, 0, 0, tzinfo=UTC)
        quote_ts = [day_start + timedelta(milliseconds=5 * i - 1) for i in range(n_per_day)]
        day_prices = all_price[day_idx * n_per_day : (day_idx + 1) * n_per_day]
        bt = pl.DataFrame(
            {
                "update_id": np.arange(n_per_day),
                "bid_price": [p - 0.02 * price_scale for p in day_prices],
                "bid_qty": np.ones(n_per_day),
                "ask_price": [p + 0.02 * price_scale for p in day_prices],
                "ask_qty": np.ones(n_per_day),
                "ts": quote_ts,
            },
            schema_overrides={"ts": pl.Datetime("ms", "UTC")},
        )
        bt_path = parquet_path(root, symbol, "bookTicker", day)
        bt_path.parent.mkdir(parents=True, exist_ok=True)
        bt.write_parquet(bt_path)


def _fake_kernels_json(
    tmp_path: Path,
    symbols: list[str],
    scales: dict[str, float] | None = None,
    window: tuple[str, str] = ("2023-06-01", "2023-06-07"),
) -> Path:
    """Minimal Q5-shaped kernels json: G rises then decays (like the real panel).

    `scales` multiplies a symbol's G (to match a symbol whose prices are scaled);
    `window` is the Q5 estimation window recorded in the file.
    """
    scales = scales or {}
    records = []
    for i, sym in enumerate(symbols):
        lags = np.arange(100)
        peak_lag = 5
        g = np.where(
            lags <= peak_lag,
            0.01 * lags,
            0.01 * peak_lag * np.exp(-(lags - peak_lag) / 10.0),
        )
        g[0] = 0.0
        g = g * scales.get(sym, 1.0)
        records.append(
            {
                "symbol": sym,
                "n_events": 1_000_000 - i * 10_000,
                "G": g.tolist(),
            }
        )
    path = tmp_path / "fake_kernels.json"
    path.write_text(
        json.dumps({"start_day": window[0], "end_day": window[1], "records": records})
    )
    return path


def test_run_q7_end_to_end_synthetic(tmp_path: Path):
    symbols = [f"SYM{i:02d}" for i in range(6)]
    for i, sym in enumerate(symbols):
        _write_symbol_week(tmp_path, sym, seed=i, n_per_day=3000)

    kernels_path = _fake_kernels_json(tmp_path, symbols)
    symbols_file = tmp_path / "symbols.txt"
    symbols_file.write_text("\n".join(symbols))

    out_dir = tmp_path / "results"
    result = run_q7(
        root=tmp_path,
        out_dir=out_dir,
        symbols_file=symbols_file,
        kernels_path=kernels_path,
        month="2023-06",
        days=DAYS,
        horizon_events=500,
        n_children=10,
        parent_qty_events_list=[2.0, 10.0],
    )

    # --- calibration / evaluation split present and distinct ---
    assert "calibration" in result
    assert "evaluation" in result
    assert result["calibration"]["days"] == CALIB_DAYS
    assert result["evaluation"]["days"] == EVAL_DAYS
    assert "lookback" in result["calibration"]["chosen_params"]
    assert "pause_threshold" in result["calibration"]["chosen_params"]

    # --- evaluation results carry per-schedule mean/sd shortfall ---
    eval_summary = result["evaluation"]["summary"]
    for schedule_name in ("twap", "frontloaded", "reactive"):
        assert schedule_name in eval_summary
        assert "mean_shortfall" in eval_summary[schedule_name]
        assert "sd_shortfall" in eval_summary[schedule_name]

    # --- per-symbol table present ---
    assert len(result["evaluation"]["per_symbol"]) == 6

    # --- output files exist ---
    assert (out_dir / "q7_execution.json").exists()
    assert (out_dir / "q7_execution.md").exists()
    assert (out_dir / "q7_execution.png").exists()

    md_text = (out_dir / "q7_execution.md").read_text()
    assert "not a trading recommendation" in md_text.lower()
    assert "cost model" in md_text.lower()


def test_run_q7_symbol_failure_does_not_abort_run(tmp_path: Path):
    symbols = [f"SYM{i:02d}" for i in range(6)]
    # Only build data for 5 of the 6 symbols; the 6th has no parquet at all.
    for i, sym in enumerate(symbols[:5]):
        _write_symbol_week(tmp_path, sym, seed=i, n_per_day=1500)

    kernels_path = _fake_kernels_json(tmp_path, symbols)
    symbols_file = tmp_path / "symbols.txt"
    symbols_file.write_text("\n".join(symbols))

    out_dir = tmp_path / "results"
    result = run_q7(
        root=tmp_path,
        out_dir=out_dir,
        symbols_file=symbols_file,
        kernels_path=kernels_path,
        month="2023-06",
        days=DAYS,
        horizon_events=300,
        n_children=10,
        parent_qty_events_list=[2.0, 10.0],
    )
    assert len(result["failures"]) >= 1
    failed_symbols = {f["symbol"] for f in result["failures"]}
    assert "SYM05" in failed_symbols
    assert (out_dir / "q7_execution.json").exists()


# --------------------------------------------------------------------------
# No leakage, units, failures, strict JSON, paired statement
# --------------------------------------------------------------------------


def _small_run(root: Path, symbols: list[str], kernels_path: Path, out: str = "results") -> dict:
    symbols_file = root / "symbols.txt"
    symbols_file.write_text("\n".join(symbols))
    return run_q7(
        root=root, out_dir=root / out, symbols_file=symbols_file, kernels_path=kernels_path,
        month="2023-06", days=DAYS, horizon_events=300, n_children=10,
        parent_qty_events_list=[2.0, 10.0],
    )


def test_calibration_ignores_evaluation_days_but_not_calibration_days(tmp_path: Path):
    symbols = ["SYM00", "SYM01", "SYM02"]
    runs = {}
    for name, (seed_offset, eval_seed) in {
        "base": (0, None),
        "other_eval_days": (0, 777),
        "other_calib_days": (50, 4242),
    }.items():
        root = tmp_path / name
        for i, sym in enumerate(symbols):
            # base uses one stream for all days; the variants split calib / eval streams
            _write_symbol_week(
                root, sym, seed=i + seed_offset, n_per_day=1500,
                eval_seed=None if name == "base" else (eval_seed or 0) + i,
            )
        runs[name] = _small_run(root, symbols, _fake_kernels_json(root, symbols))

    base, other_eval = runs["base"], runs["other_eval_days"]
    # Same days 1-3, different days 4-7 (for "base" the eval days continue the seed's
    # stream, so they differ from the eval_seed stream): calibration is untouched.
    assert base["calibration"]["chosen_params"] == other_eval["calibration"]["chosen_params"]
    assert base["calibration"]["scores"] == other_eval["calibration"]["scores"]
    assert (
        base["evaluation"]["summary"]["twap"]["mean_shortfall"]
        != other_eval["evaluation"]["summary"]["twap"]["mean_shortfall"]
    )
    # Different days 1-3: the scores move, so the comparison above can fail.
    assert base["calibration"]["scores"] != runs["other_calib_days"]["calibration"]["scores"]


def test_shortfall_is_in_bps_so_price_level_does_not_matter(tmp_path: Path):
    symbols = ["LOWPX", "HIGHPX"]
    _write_symbol_week(tmp_path, "LOWPX", seed=3, n_per_day=1500, price_scale=1.0)
    _write_symbol_week(tmp_path, "HIGHPX", seed=3, n_per_day=1500, price_scale=1000.0)
    kernels = _fake_kernels_json(tmp_path, symbols, scales={"HIGHPX": 1000.0})
    result = _small_run(tmp_path, symbols, kernels)

    by_symbol = {p["symbol"]: p for p in result["evaluation"]["per_symbol"]}
    for schedule in ("twap", "frontloaded", "reactive"):
        low, high = by_symbol["LOWPX"][schedule], by_symbol["HIGHPX"][schedule]
        assert high["mean_shortfall"] == pytest.approx(low["mean_shortfall"], rel=1e-6)
        assert high["sd_shortfall"] == pytest.approx(low["sd_shortfall"], rel=1e-6)
    pooled = result["evaluation"]["summary"]["twap"]["mean_shortfall"]
    assert pooled == pytest.approx(by_symbol["LOWPX"]["twap"]["mean_shortfall"], rel=1e-6)


def test_calibration_replay_failures_are_recorded_not_skipped(tmp_path: Path):
    symbols = ["SYM00", "SYM01"]
    _write_symbol_week(tmp_path, "SYM00", seed=0, n_per_day=1500)
    _write_symbol_week(tmp_path, "SYM01", seed=1, n_per_day=1500, skip_bt_days=("2023-06-02",))
    kernels = _fake_kernels_json(tmp_path, symbols)
    result = _small_run(tmp_path, symbols, kernels)

    calibration_failures = [f for f in result["failures"] if f["stage"] == "calibration"]
    assert [(f["symbol"], f["day"]) for f in calibration_failures] == [("SYM01", "2023-06-02")]
    assert "bookTicker" in calibration_failures[0]["reason"]


def test_scorer_returns_its_failures(tmp_path: Path):
    _write_symbol_week(tmp_path, "SYM00", seed=0, n_per_day=1500)
    kernels = _fake_kernels_json(tmp_path, ["SYM00"])
    scorer, failures = _build_calibration_scorer(
        root=tmp_path, symbols=["SYM00", "GHOST"], kernels_path=kernels, month="2023-06",
        calib_days=CALIB_DAYS, horizon_events=300, n_children=10,
        parent_qty_events_list=[2.0],
    )
    assert [(f["symbol"], f["stage"]) for f in failures] == [("GHOST", "calibration")]
    assert np.isfinite(scorer(50, 0.2))


def test_negative_lag_one_kernel_is_a_recorded_failure_not_a_crash(tmp_path: Path):
    symbols = ["SYM00", "SYM01"]
    for i, sym in enumerate(symbols):
        _write_symbol_week(tmp_path, sym, seed=i, n_per_day=1500)
    kernels = _fake_kernels_json(tmp_path, symbols, scales={"SYM01": -1.0})
    result = _small_run(tmp_path, symbols, kernels)

    reasons = [(f["symbol"], f["stage"]) for f in result["failures"] if "G[1]" in f["reason"]]
    assert ("SYM01", "calibration") in reasons and ("SYM01", "evaluation") in reasons
    by_symbol = {p["symbol"]: p for p in result["evaluation"]["per_symbol"]}
    assert by_symbol["SYM01"]["twap"]["n"] == 0
    assert by_symbol["SYM00"]["twap"]["n"] > 0


def test_json_is_strict_and_md_carries_units_and_in_sample_caveat(tmp_path: Path):
    symbols = ["SYM00", "SYM01"]
    for i, sym in enumerate(symbols):
        _write_symbol_week(tmp_path, sym, seed=i, n_per_day=1500)
    kernels = _fake_kernels_json(tmp_path, symbols)
    result = _small_run(tmp_path, symbols, kernels)

    def reject_constant(name):
        raise AssertionError(f"non-strict JSON constant {name}")

    parsed = json.loads(
        (tmp_path / "results" / "q7_execution.json").read_text(), parse_constant=reject_constant
    )
    assert parsed["shortfall_unit"] == "basis points of the arrival mid"
    assert parsed["evaluation"]["summary"]["sd_ratio_frontloaded_vs_twap"] > 0
    assert "mean" in parsed["evaluation"]["summary"]["reactive_minus_twap"]
    assert result["kernel_window"] == {"start_day": "2023-06-01", "end_day": "2023-06-07"}

    md = (tmp_path / "results" / "q7_execution.md").read_text()
    assert "bps" in md
    assert "Kernels are in-sample" in md
    assert "2023-06-04" in md.split("Kernels are in-sample")[1].split("\n")[0]


def test_in_sample_caveat_is_absent_when_kernels_come_from_another_window(tmp_path: Path):
    symbols = ["SYM00", "SYM01"]
    for i, sym in enumerate(symbols):
        _write_symbol_week(tmp_path, sym, seed=i, n_per_day=1500)
    kernels = _fake_kernels_json(tmp_path, symbols, window=("2023-05-01", "2023-05-07"))
    _small_run(tmp_path, symbols, kernels)
    assert "Kernels are in-sample" not in (tmp_path / "results" / "q7_execution.md").read_text()


def test_reactive_vs_twap_sentence_follows_the_paired_standard_error():
    inside = _reactive_vs_twap_lines({"mean": -0.05, "se": 0.1, "z": -0.5, "n": 40})
    assert "does not statistically distinguish" in inside[0]
    assert "-0.05" in inside[0] and "paired SE 0.1" in inside[0]

    outside = _reactive_vs_twap_lines({"mean": -0.5, "se": 0.1, "z": -5.0, "n": 40})
    assert "does not statistically distinguish" not in outside[0]
    assert "reactive is cheaper than twap" in outside[0]

    worse = _reactive_vs_twap_lines({"mean": 0.5, "se": 0.1, "z": 5.0, "n": 40})
    assert "reactive is more expensive than twap" in worse[0]

    too_few = _reactive_vs_twap_lines({"mean": None, "se": None, "z": None, "n": 1})
    assert "Too few paired cells" in too_few[0]
