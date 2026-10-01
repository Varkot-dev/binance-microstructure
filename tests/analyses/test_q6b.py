"""Tests for Q6b: kernel-K sensitivity panel.

Contract under test (see the q6b_kernel_sensitivity.py module docstring):
1. A planted two-timescale-kernel symbol (alpha=(0.25,0.35), beta=(5,0.2),
   true n=0.6) must show a large K=1->K=2 rise (Delta21 > 0.15) and n_hat_2
   within +-0.1 of 0.6: K=1 underestimates a long-memory kernel.
2. A planted single-exponential-kernel symbol (n=0.4, well-specified at
   K=1) must show a Delta21 within the finite-sample null floor, the negative control:
   no spurious rise when the true kernel is K=1.
3. A missing symbol must land in `failures` without aborting the run.
4. Output files (.json/.md/.parquet/.png) must exist, and the parquet row
   count must equal the number of successful symbols.
5. The drift-suspect flagging logic (1/beta_slow at K=2 vs. the
   deseasonalization bin width) is unit-tested directly against
   `_is_drift_suspect`, independent of a full pipeline run.

Runtime: windows=2 and ks=(1,2) are used instead of the production defaults
windows=6, ks=(1,2,3). The K=2 fit dominates cost (~1.5-2s per ~30k-event
window), so this cuts runtime ~6x-9x at the price of only 2 window-level
samples per symbol median, which is fine since the tests assert Delta21
direction and magnitude with generous tolerances. Each planted fixture is
sized to ~35-45k events, keeping a symbol's fit cost (2 windows x 2 Ks) in
the single-digit seconds.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from microstructure.analyses import q6b_kernel_sensitivity as q6b
from microstructure.analyses.q6b_kernel_sensitivity import (
    _DRIFT_KEYS,
    BOUNDARY_N_HAT,
    DEFAULT_DRIFT_BLOCKS,
    DEFAULT_NULL_SIMS,
    DESEASON_BIN_WIDTH_S,
    DRIFT_SUSPECT_MULTIPLIER,
    DRIFT_VERDICTS,
    INCONCLUSIVE_REASONS,
    MAX_FIT_EVENTS,
    _drift_headline,
    _fit_capped_multiexp,
    _inconclusive_reason,
    _is_drift_suspect,
    _json_float,
    _null_floor_p90,
    _parse_args,
    _symbol_record,
    _write_results_md,
    run_q6b,
)
from microstructure.data.catalog import parquet_path
from microstructure.estimators.hawkes import (
    simulate_hawkes_exp,
    simulate_hawkes_multiexp,
    simulate_seasonal_hawkes_exp,
    spurious_delta21_null,
)

WINDOWS = 2
KS = (1, 2)

# Two-timescale planted kernel: true n = 0.25 + 0.35 = 0.6, timescales 25x
# apart (beta=5 -> fast, beta=0.2 -> slow). t_end=24_000s lands ~30-40k
# events at this (mu, alphas, betas) (measured at seed=42: ~30.5k events):
# enough for 2 sub-windows to each carry a meaningful sample for K=1 and K=2
# fits, and small enough to keep the K=2 fit in the low-single-digit seconds
# per window.
TWOEXP_MU = 0.5
TWOEXP_ALPHAS = np.array([0.25, 0.35])
TWOEXP_BETAS = np.array([5.0, 0.2])
TWOEXP_N_TRUE = float(TWOEXP_ALPHAS.sum())  # 0.6
TWOEXP_T_END = 24_000.0

# Single-exponential planted kernel: true n = 0.4, well-specified at K=1, the
# negative control. t_end is tuned to ~60k events (mu=1.0, beta=2.0, the scale
# of the single-exponential fixtures in test_hawkes.py and test_q6.py), larger
# than the ~35-45k of the other planted fixtures.
#
# Why 60k rather than a looser tolerance (mechanism in `spurious_delta21_null`,
# src/microstructure/estimators/hawkes.py): the K=2 fit has two more free
# parameters than K=1 and can always fit finite-sample noise at least as well,
# so n_hat_2 carries an upward finite-sample bias over n_hat_1 even when the
# true kernel is K=1. It is not a local-optimum artifact of the multi-start
# search (widening `betas_init` did not remove it on the window that showed
# it), and it shrinks with sample size. At t_end=20_000 (~33k events,
# ~16.6k/window at windows=2), Delta21 measured 0.107 at seed=7, above a 0.08
# tolerance: ~16.6k events/window is small enough for the K=2 fit to overfit
# sampling noise (one window's K=2 fit converged to betas=(0.021, 0.479) with
# a real ~11-nat log-likelihood improvement over K=1, though the generative
# process has no second timescale). At t_end=36_000 (~59.5k events,
# ~29.8k/window at seed=7), Delta21 measured 0.0079, since the estimator is
# less biased at this size (see the null below) and the fixture has more
# margin over the null floor.
ONEEXP_MU, ONEEXP_BETA = 1.0, 2.0
ONEEXP_ALPHA = 0.4
ONEEXP_T_END = 36_000.0

DELTA21_TOL_TWOEXP = 0.15  # Delta21 must exceed this on the two-timescale symbol
N2_TOL_TWOEXP = 0.1  # n_hat_2 must land within this of the true n=0.6

# Slack added on top of the null median when judging the single-exp negative
# control's observed Delta21 (see test_run_q6b_single_exp_symbol_shows_small_delta21).
# n_sims=2 (vs. 3 in spurious_delta21_null's own unit test) keeps this inline
# null computation, redone on every test run, cheap while still giving a noisy
# estimate of the null median at the fixture's per-window event count.
DELTA21_NULL_SIMS = 2
DELTA21_NULL_SLACK = 0.05


# Drift-control fixtures. SEASONAL: the 4-level/day baseline used by the
# estimator's own drift test (test_hawkes.py), pushed through the real Q6b
# pipeline, which first rescales to business time with a 48-bin intraday
# profile. RAMP: a stationary n=0.4 Hawkes thinned by a slow multi-day ramp
# (keep-probability 0.2 -> 1.0 over 3 days), i.e. aperiodic drift the
# time-of-day profile cannot remove. Thinning a simulated Hawkes discards some
# child events, so the ramp symbol's true n is below 0.4; only the verdict is
# asserted, not n.
SEASONAL_MU_BAR = 0.5
SEASONAL_T_END = 60_000.0
RAMP_MU, RAMP_DAYS, RAMP_KEEP_LO = 0.25, 3.0, 0.2


def _ramp_times() -> np.ndarray:
    t_end = RAMP_DAYS * 86_400.0
    base = simulate_hawkes_exp(RAMP_MU, 0.4, 2.0, t_end, seed=11)
    keep_prob = RAMP_KEEP_LO + (1.0 - RAMP_KEEP_LO) * base / t_end
    keep = np.random.default_rng(3).random(base.size) < keep_prob
    return base[keep]


def _write_event_times_fixture(
    root: Path, symbol: str, times_s: np.ndarray, month: str = "2023-06",
) -> int:
    """Write a raw array of event times (float seconds from an arbitrary
    origin) as an aggTrades-schema parquet: int64 epoch-ms `ts`, alternating
    +-1 aggressor sign via `is_buyer_maker`, positive `qty`. Uses the
    dedup/nudge convention of test_q6.py's fixture writers (ms collisions are
    nudged forward by 1ms so `to_aggressor_events` does not merge events away).
    Returns the final event count actually written.
    """
    t0 = datetime(2023, 6, 1, 0, 0, 0, tzinfo=UTC)
    ts_ms = (times_s * 1000.0).astype(np.int64)
    ts_ms = np.maximum.accumulate(ts_ms)
    for i in range(1, ts_ms.size):
        if ts_ms[i] <= ts_ms[i - 1]:
            ts_ms[i] = ts_ms[i - 1] + 1
    n = ts_ms.size
    event_ts = [t0 + timedelta(milliseconds=int(ms)) for ms in ts_ms]
    signs = np.where(np.arange(n) % 2 == 0, 1, -1)
    qty = np.full(n, 1.0) + 0.01 * (np.arange(n) % 5)

    agg = pl.DataFrame(
        {
            "agg_trade_id": np.arange(n),
            "price": np.full(n, 100.0),
            "qty": qty,
            "first_trade_id": np.arange(n),
            "last_trade_id": np.arange(n),
            "ts": event_ts,
            "is_buyer_maker": signs < 0,
        },
        schema_overrides={"ts": pl.Datetime("ms", "UTC")},
    )
    agg_path = parquet_path(root, symbol, "aggTrades", month)
    agg_path.parent.mkdir(parents=True, exist_ok=True)
    agg.write_parquet(agg_path)
    return n


@pytest.fixture(scope="module")
def planted_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("q6b_planted")

    twoexp_times = simulate_hawkes_multiexp(
        TWOEXP_MU, TWOEXP_ALPHAS, TWOEXP_BETAS, TWOEXP_T_END, seed=42
    )
    assert twoexp_times.size > 2 * WINDOWS * 10, "need enough events for a stable 2-window panel"
    _write_event_times_fixture(root, "TWOEXPUSDT", twoexp_times)

    oneexp_times = simulate_hawkes_exp(ONEEXP_MU, ONEEXP_ALPHA, ONEEXP_BETA, ONEEXP_T_END, seed=7)
    assert oneexp_times.size > 2 * WINDOWS * 10, "need enough events for a stable 2-window panel"
    _write_event_times_fixture(root, "ONEEXPUSDT", oneexp_times)

    # Drift-control fixtures (see the "drift-vs-memory control" section below).
    seasonal_times = simulate_seasonal_hawkes_exp(
        SEASONAL_MU_BAR, 0.4, 2.0, SEASONAL_T_END, np.tile([0.7, 1.3], 2), seed=5
    )
    _write_event_times_fixture(root, "SEASONALUSDT", seasonal_times)
    _write_event_times_fixture(root, "RAMPUSDT", _ramp_times())
    _write_event_times_fixture(
        root, "SMALLUSDT", simulate_hawkes_exp(1.0, 0.4, 2.0, 1_500.0, seed=1)
    )

    # MISSINGUSDT has no parquet on disk -> must land in failures.
    return root


def test_run_q6b_two_timescale_symbol_shows_large_delta21(planted_root: Path):
    out_dir = planted_root / "results_two"
    result = run_q6b(
        planted_root, out_dir, symbols=["TWOEXPUSDT"], month="2023-06",
        windows=WINDOWS, ks=KS, null_sims=0, drift_blocks=0,
    )
    assert result["n_symbols_successful"] == 1, result["failures"]
    rec = result["records"][0]

    assert rec["delta21"] > DELTA21_TOL_TWOEXP, (
        f"expected Delta21 > {DELTA21_TOL_TWOEXP} on the two-timescale symbol, "
        f"got {rec['delta21']} (n_hat_1={rec['n_median_by_k'].get(1)}, "
        f"n_hat_2={rec['n_median_by_k'].get(2)})"
    )
    n2 = rec["n_median_by_k"][2]
    assert abs(n2 - TWOEXP_N_TRUE) < N2_TOL_TWOEXP, (
        f"expected n_hat_2 within {N2_TOL_TWOEXP} of true n={TWOEXP_N_TRUE}, got {n2}"
    )


def test_run_q6b_single_exp_symbol_shows_small_delta21(planted_root: Path):
    """The negative control: a well-specified K=1 symbol's observed Delta21
    must not exceed the finite-sample null (see `spurious_delta21_null`),
    computed at this run's median per-window event count, plus a fixed slack.
    A fixed tolerance would be wrong because the K=2 fit has an upward
    finite-sample bias over K=1 even when K=1 is exactly correct (extra free
    parameters only help in-sample likelihood), so a fixed number conflates
    estimator bias at this sample size with a real second timescale. The null
    is recomputed inline (n_sims=2, ~10-15s) since it depends on the fixture's
    (mu, alpha, beta) and event count.

    The same `run_q6b` call (`null_sims=DELTA21_NULL_SIMS`) also exercises its
    `null_floor_p90`/`within_finite_sample_null` wiring (the panel-level null
    floor in the JSON/md), so this is the only test paying for that
    calibration.
    """
    out_dir = planted_root / "results_one"
    result = run_q6b(
        planted_root, out_dir, symbols=["ONEEXPUSDT"], month="2023-06",
        windows=WINDOWS, ks=KS, null_sims=DELTA21_NULL_SIMS, drift_blocks=0,
    )
    assert result["n_symbols_successful"] == 1, result["failures"]
    rec = result["records"][0]

    n_events_per_window = rec["n_events"] // WINDOWS
    null = spurious_delta21_null(
        n_events_per_window, mu=ONEEXP_MU, alpha=ONEEXP_ALPHA, beta=ONEEXP_BETA,
        n_sims=DELTA21_NULL_SIMS, seed=999,
    )
    null_floor = float(np.median(null)) + DELTA21_NULL_SLACK

    assert abs(rec["delta21"]) <= null_floor, (
        f"expected |Delta21| <= null_floor={null_floor:.4f} "
        f"(null median={np.median(null):.4f} + slack={DELTA21_NULL_SLACK}, "
        f"null={null.tolist()}, n_events_per_window={n_events_per_window}) "
        f"on the well-specified K=1 symbol, got {rec['delta21']} "
        f"(n_hat_1={rec['n_median_by_k'].get(1)}, n_hat_2={rec['n_median_by_k'].get(2)})"
    )

    # run_q6b's panel-level null floor: computed once at the panel's median
    # per-window event count via _null_floor_p90, exposed in cross_section and
    # used to label each record within_finite_sample_null. Only the wiring is
    # asserted, not a True/False value: with null_sims=2 the p90 is noisy from
    # run to run, so a specific label would be brittle. The primary assertion
    # above checks that Delta21 is small; this block checks the field is
    # populated and well-typed.
    null_floor_p90 = result["cross_section"]["null_floor_p90"]
    assert null_floor_p90 is not None
    assert null_floor_p90["n_sims"] == DELTA21_NULL_SIMS
    assert null_floor_p90["p90"] >= null_floor_p90["median"]
    assert "within_finite_sample_null" in rec
    assert isinstance(rec["within_finite_sample_null"], bool)


def test_run_q6b_missing_symbol_lands_in_failures(planted_root: Path):
    out_dir = planted_root / "results_missing"
    result = run_q6b(
        planted_root, out_dir,
        symbols=["TWOEXPUSDT", "MISSINGUSDT"], month="2023-06",
        windows=WINDOWS, ks=KS, null_sims=0, drift_blocks=0,
    )
    by_symbol = {r["symbol"]: r for r in result["records"]}
    assert "TWOEXPUSDT" in by_symbol
    assert "MISSINGUSDT" not in by_symbol

    failures = {f["symbol"]: f for f in result["failures"]}
    assert "MISSINGUSDT" in failures
    assert failures["MISSINGUSDT"]["reason"]
    assert result["n_symbols_successful"] == 1
    assert result["n_symbols_failed"] == 1


def test_run_q6b_never_aborts_on_all_failures(tmp_path: Path):
    out_dir = tmp_path / "results"
    result = run_q6b(
        tmp_path, out_dir, symbols=["GHOSTUSDT"], month="2023-06",
        windows=WINDOWS, ks=KS, null_sims=0, drift_blocks=0,
    )
    assert result["records"] == []
    assert len(result["failures"]) == 1
    assert result["failures"][0]["symbol"] == "GHOSTUSDT"
    assert (out_dir / "q6b_kernel_sensitivity.md").exists()
    assert (out_dir / "q6b_kernel_sensitivity.json").exists()
    assert (out_dir / "q6b_kernel_sensitivity.parquet").exists()
    assert (out_dir / "q6b_kernel_sensitivity.png").exists()


def test_run_q6b_outputs_exist_and_parquet_row_count_matches_successes(planted_root: Path):
    out_dir = planted_root / "results_outputs"
    result = run_q6b(
        planted_root, out_dir,
        symbols=["TWOEXPUSDT", "ONEEXPUSDT", "MISSINGUSDT"], month="2023-06",
        windows=WINDOWS, ks=KS, null_sims=0, drift_blocks=0,
    )
    assert (out_dir / "q6b_kernel_sensitivity.json").exists()
    assert (out_dir / "q6b_kernel_sensitivity.md").exists()
    assert (out_dir / "q6b_kernel_sensitivity.parquet").exists()
    assert (out_dir / "q6b_kernel_sensitivity.png").exists()

    df = pl.read_parquet(out_dir / "q6b_kernel_sensitivity.parquet")
    assert df.height == result["n_symbols_successful"] == 2
    assert set(df.columns) >= {
        "symbol", "n_events", "n_hat_k1", "n_hat_k2", "n_hat_k3", "delta21",
        "median_inv_beta_slow_k2_s", "ratio_inv_beta_slow_to_bin_width",
        "ratio_inv_beta_slow_to_window_length", "drift_suspect",
    }

    # Per-symbol JSON records carry every field the module docstring promises.
    for rec in result["records"]:
        assert "n_median_by_k" in rec
        assert "n_converged_by_k" in rec
        assert "delta21" in rec
        assert "median_inv_beta_slow_k2_s" in rec
        assert "ratio_inv_beta_slow_to_bin_width" in rec
        assert "ratio_inv_beta_slow_to_window_length" in rec
        assert "drift_suspect" in rec
        assert isinstance(rec["drift_suspect"], bool)


def test_run_q6b_cross_section_reports_delta21_distribution_and_frac_near_critical(
    planted_root: Path,
):
    out_dir = planted_root / "results_cross"
    result = run_q6b(
        planted_root, out_dir,
        symbols=["TWOEXPUSDT", "ONEEXPUSDT"], month="2023-06",
        windows=WINDOWS, ks=KS, null_sims=0, drift_blocks=0,
    )
    cross = result["cross_section"]
    assert cross["delta21_distribution"] is not None
    assert cross["delta21_distribution"]["n"] == 2
    assert cross["frac_n2_at_least_0_9"] is not None
    # Neither planted symbol has n_hat_2 >= 0.9 (0.6 and ~0.4 respectively).
    assert cross["frac_n2_at_least_0_9"] == 0.0


def test_run_q6b_compares_k2_with_q6_count_variance(planted_root: Path, tmp_path: Path):
    """Optional --q6-json input: compare the K=2 estimate with Q6's count-variance n-hat.

    Delta21 is not correlated with (alpha_cv - alpha_median): both subtract the
    same K=1 estimate, so that correlation is high by construction. Instead the
    cross-section reports corr(n_hat_2, alpha_cv), the median gap to
    count-variance at K=1 and K=2, and the median share of the gap K=2 closes.
    """
    q6_json_path = tmp_path / "fake_q6.json"
    q6_json_path.write_text(
        '{"records": ['
        '{"symbol": "TWOEXPUSDT", "alpha_median": 0.5, "alpha_cv": 0.7},'
        '{"symbol": "ONEEXPUSDT", "alpha_median": 0.3, "alpha_cv": 0.32}'
        "]}"
    )

    out_dir = planted_root / "results_q6json"
    result = run_q6b(
        planted_root, out_dir,
        symbols=["TWOEXPUSDT", "ONEEXPUSDT"], month="2023-06",
        windows=WINDOWS, ks=KS, q6_json=q6_json_path, null_sims=0, drift_blocks=0,
    )
    cmp = result["cross_section"]["cv_comparison"]
    assert cmp is not None
    assert cmp["n"] == 2
    assert "cv_gap_correlation" not in result["cross_section"]
    cv = {"TWOEXPUSDT": 0.7, "ONEEXPUSDT": 0.32}
    recs = {r["symbol"]: r for r in result["records"]}
    gaps_k1 = [cv[s] - recs[s]["n_median_by_k"][1] for s in cv]
    gaps_k2 = [cv[s] - recs[s]["n_median_by_k"][2] for s in cv]
    assert cmp["median_gap_k1"] == pytest.approx(float(np.median(gaps_k1)))
    assert cmp["median_gap_k2"] == pytest.approx(float(np.median(gaps_k2)))
    assert -1.0 <= cmp["corr_n2_cv"] <= 1.0
    report = (out_dir / "q6b_kernel_sensitivity.md").read_text()
    assert "share of the gap" in report

    # Without --q6-json, the field must be present but inert.
    out_dir_no_q6 = planted_root / "results_no_q6json"
    result_no_q6 = run_q6b(
        planted_root, out_dir_no_q6,
        symbols=["TWOEXPUSDT", "ONEEXPUSDT"], month="2023-06",
        windows=WINDOWS, ks=KS, null_sims=0, drift_blocks=0,
    )
    assert result_no_q6["cross_section"]["cv_comparison"] is None
    assert result_no_q6["q6_json_used"] is None


# --- drift-suspect flag logic (unit-level, no pipeline run needed) ---------


def test_drift_suspect_flags_slow_timescale_far_above_bin_width():
    slow_timescale = DRIFT_SUSPECT_MULTIPLIER * DESEASON_BIN_WIDTH_S * 2.0
    assert _is_drift_suspect(slow_timescale) is True


def test_drift_suspect_does_not_flag_timescale_well_below_threshold():
    fast_timescale = DESEASON_BIN_WIDTH_S * 0.5
    assert _is_drift_suspect(fast_timescale) is False


def test_drift_suspect_boundary_is_strictly_greater_than():
    boundary = DRIFT_SUSPECT_MULTIPLIER * DESEASON_BIN_WIDTH_S
    assert _is_drift_suspect(boundary) is False
    assert _is_drift_suspect(boundary + 1e-6) is True


def test_drift_suspect_flags_non_finite_timescale():
    assert _is_drift_suspect(float("inf")) is True
    assert _is_drift_suspect(float("nan")) is True


# --- JSON serializability of the per-symbol record -------------------------

# Every scalar in a `_symbol_record` return value (directly or nested inside
# `n_median_by_k`/`n_converged_by_k`/`per_window`) must be one of these
# Python-native types. numpy scalars (np.bool_, np.float64, np.int64, ...) are
# excluded on purpose: json.dumps raises `TypeError: Object of type
# bool/float64/... is not JSON serializable` on them. The type() check below
# is exact, not isinstance-based, so a numpy subclass cannot slip through.
_JSON_NATIVE_SCALAR_TYPES = (str, int, float, bool, type(None))


def _assert_only_native_scalars(value: object, path: str = "$") -> None:
    """Recursively assert every leaf in a JSON-able structure is a Python-
    native scalar (str/int/float/bool/None), not a numpy scalar subclass.

    `type(value) in _JSON_NATIVE_SCALAR_TYPES` is used instead of `isinstance`
    because `numpy.bool_`/`numpy.float64` register as subclasses of
    `bool`/`float` on some numpy versions, which would let an isinstance check
    pass on exactly the regression being tested.
    """
    if isinstance(value, dict):
        for k, v in value.items():
            _assert_only_native_scalars(v, f"{path}.{k}")
        return
    if isinstance(value, list):
        for i, v in enumerate(value):
            _assert_only_native_scalars(v, f"{path}[{i}]")
        return
    assert type(value) in _JSON_NATIVE_SCALAR_TYPES, (
        f"{path}: expected a Python-native scalar, got {type(value).__name__} ({value!r}) "
        "-- numpy scalars (e.g. numpy.bool_, numpy.float64) are not JSON serializable "
        "by json.dumps and must be coerced with bool()/float()/int() at the record-"
        "building site before being placed in the record dict"
    )


def test_symbol_record_round_trips_through_json_dumps(planted_root: Path):
    """The per-symbol record dict `_symbol_record` returns must contain only
    Python-native scalar types and must round-trip through `json.dumps`
    (strict, allow_nan=False -- Delta21/ratios are None when a K value
    is absent or a slow component's beta rounds to zero) without raising.

    This guards against `fit.converged` (from `fit_hawkes_multiexp`) and the
    `_is_drift_suspect` result arriving as numpy scalars rather than Python
    `bool`, which `json.dumps` cannot encode (`TypeError: Object of type bool
    is not JSON serializable`; the numpy bool's __class__.__name__ prints as
    "bool", which makes the failure confusing).
    """
    rec = _symbol_record(planted_root, "ONEEXPUSDT", "2023-06", WINDOWS, KS, drift_blocks=0)

    encoded = json.dumps(rec, allow_nan=False)  # strict JSON: NaN/inf must already be None
    decoded = json.loads(encoded)
    assert decoded["symbol"] == "ONEEXPUSDT"

    _assert_only_native_scalars(rec)


def test_symbol_record_with_drift_control_round_trips_through_json(planted_root: Path):
    """Same native-scalar contract with the control ON: the new keys are
    populated Python-native str/float values (cheap SMALLUSDT fixture)."""
    rec = _symbol_record(planted_root, "SMALLUSDT", "2023-06", WINDOWS, KS, drift_blocks=6)

    decoded = json.loads(json.dumps(rec))
    _assert_only_native_scalars(rec)
    assert all(key in decoded for key in _DRIFT_KEYS)
    assert rec["drift_error"] is None, rec["drift_error"]
    assert rec["drift_verdict"] in DRIFT_VERDICTS
    assert type(rec["drift_verdict"]) is str
    assert rec["drift_inconclusive_reason"] in (*INCONCLUSIVE_REASONS, None)
    assert (rec["drift_verdict"] == "inconclusive") == (rec["drift_inconclusive_reason"] is not None)
    float_keys = [
        k for k in _DRIFT_KEYS
        if k not in ("drift_verdict", "drift_inconclusive_reason", "drift_error")
    ]
    assert all(type(rec[key]) is float for key in float_keys)


# --- drift-vs-memory control wiring -----------------------------------------


@pytest.fixture(scope="module")
def drift_panel(planted_root: Path) -> dict:
    """ONE run_q6b call (control on, default blocks) shared by the tests below
    so the ~30 s of K=1/K=2/piecewise fits is paid once."""
    return run_q6b(
        planted_root, planted_root / "results_drift",
        symbols=["TWOEXPUSDT", "SEASONALUSDT", "RAMPUSDT"], month="2023-06",
        windows=WINDOWS, ks=KS, null_sims=0,
    )


def _drift_by_symbol(panel: dict) -> dict[str, dict]:
    assert panel["n_symbols_successful"] == 3, panel["failures"]
    return {r["symbol"]: r for r in panel["records"]}


def test_drift_control_planted_two_exp_symbol_is_not_drift(drift_panel: dict):
    rec = _drift_by_symbol(drift_panel)["TWOEXPUSDT"]
    assert rec["drift_verdict"] in DRIFT_VERDICTS
    assert rec["drift_verdict"] != "drift", rec
    assert rec["dll_pw"] < 0.5 * rec["dll_k2"], rec


def test_drift_control_business_time_rescaling_absorbs_profile_periodic_drift(
    drift_panel: dict,
):
    """On this fixture the 4-level/day baseline is intraday seasonality, which
    Q6b's 48-bin business-time rescaling already removes (K=1 n_hat ~= 0.40,
    the true value; the estimator-level test on raw time reads 0.46). The
    control therefore does not call it 'drift'; it targets aperiodic drift (see
    the ramp test), not profile-periodic drift."""
    rec = _drift_by_symbol(drift_panel)["SEASONALUSDT"]
    assert abs(rec["n_median_by_k"][1] - 0.4) < 0.08, rec["n_median_by_k"]
    assert rec["drift_verdict"] != "drift", rec


def test_drift_control_flags_aperiodic_multi_day_ramp_as_drift(drift_panel: dict):
    rec = _drift_by_symbol(drift_panel)["RAMPUSDT"]
    assert rec["delta21"] > 0.1, rec
    assert rec["drift_verdict"] == "drift", rec
    assert rec["dll_pw"] >= rec["dll_threshold"]
    assert rec["dll_pw"] >= 0.5 * rec["dll_k2"]


def test_drift_control_record_fields_and_cross_section_counts(drift_panel: dict):
    records = _drift_by_symbol(drift_panel)
    for rec in records.values():
        assert all(key in rec for key in _DRIFT_KEYS)
        assert rec["dll_threshold"] > 0.0
        assert 0.0 < rec["drift_block_width_s"] < rec["window_length_s"]
        assert rec["n_k1_piecewise"] > 0.0
    counts = drift_panel["cross_section"]["drift_verdict_counts"]
    assert sum(counts.values()) == 3
    assert counts["not_run"] == 0
    for verdict in DRIFT_VERDICTS:
        assert counts[verdict] == sum(r["drift_verdict"] == verdict for r in records.values())
    assert drift_panel["drift_blocks"] == DEFAULT_DRIFT_BLOCKS
    reasons = drift_panel["cross_section"]["drift_inconclusive_reason_counts"]
    assert sum(reasons.values()) == counts["inconclusive"]
    for rec in records.values():
        assert (rec["drift_verdict"] == "inconclusive") == (
            rec["drift_inconclusive_reason"] is not None
        )
        assert rec["drift_n_k2"] > 0.0 and rec["drift_n_k1"] > 0.0


def test_drift_control_outputs_json_parquet_and_markdown(drift_panel: dict, planted_root: Path):
    out_dir = planted_root / "results_drift"
    # Whole result is JSON-native and round-trips (numpy scalars would raise).
    _assert_only_native_scalars(drift_panel["records"])
    _assert_only_native_scalars(drift_panel["cross_section"]["drift_verdict_counts"])
    loaded = json.loads((out_dir / "q6b_kernel_sensitivity.json").read_text())
    assert loaded["cross_section"]["drift_verdict_counts"] == (
        drift_panel["cross_section"]["drift_verdict_counts"]
    )

    df = pl.read_parquet(out_dir / "q6b_kernel_sensitivity.parquet")
    assert set(df.columns) >= set(_DRIFT_KEYS)
    assert sorted(df["drift_verdict"].to_list()) == sorted(
        r["drift_verdict"] for r in drift_panel["records"]
    )

    md = (out_dir / "q6b_kernel_sensitivity.md").read_text()
    assert "## Is the K=2 rise drift or memory?" in md
    counts = drift_panel["cross_section"]["drift_verdict_counts"]
    assert f"drift = {counts['drift']}, long_memory_candidate = " in md
    assert "heuristic likelihood-ratio screen" in md
    assert "Resolution limit" in md and "business-time hours" in md
    assert "Median block width" in md
    assert f"capped at {MAX_FIT_EVENTS:,} events" in md
    assert "(3 of 3 requested symbols assessed; failed, errored and not-run excluded)" in md
    assert "no_rise = " in md and "k2_insignificant = " in md and "errored = 0" in md
    assert "OR across the drift threshold into `drift`" in md
    assert "does not exclude long memory" in md
    assert "| n̂_1 (const) | n̂_2 | n̂_1 (piecewise) |" in md
    assert "| drift verdict |" in md
    assert "conservative" not in md and "guarantee" not in md


def test_drift_blocks_zero_skips_control_cleanly(
    planted_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("baseline_drift_control must not run when --drift-blocks 0")

    monkeypatch.setattr(q6b, "baseline_drift_control", _boom)

    result = run_q6b(
        planted_root, tmp_path / "out", symbols=["SMALLUSDT"], month="2023-06",
        windows=WINDOWS, ks=KS, null_sims=0, drift_blocks=0,
    )
    assert result["n_symbols_successful"] == 1, result["failures"]
    rec = result["records"][0]
    assert all(rec[key] is None for key in _DRIFT_KEYS)
    assert result["cross_section"]["drift_verdict_counts"]["not_run"] == 1
    md = (tmp_path / "out" / "q6b_kernel_sensitivity.md").read_text()
    assert "--drift-blocks 0" in md
    df = pl.read_parquet(tmp_path / "out" / "q6b_kernel_sensitivity.parquet")
    assert df["drift_verdict"].to_list() == [None]
    json.dumps(result)  # must not raise


@pytest.mark.parametrize("bad", [-1, 1, 13])
def test_run_q6b_rejects_invalid_drift_blocks(tmp_path: Path, bad: int):
    with pytest.raises(ValueError, match="drift_blocks"):
        run_q6b(tmp_path, tmp_path / "out", symbols=[], drift_blocks=bad)


def test_cli_drift_blocks_flag_default_and_disable(tmp_path: Path):
    symbols = tmp_path / "s.txt"
    symbols.write_text("AAAUSDT\n")
    assert _parse_args(["--symbols-file", str(symbols)]).drift_blocks == 12
    assert _parse_args(["--symbols-file", str(symbols), "--drift-blocks", "0"]).drift_blocks == 0


def _headline_counts(d: int, m: int, i: int, errored: int = 0) -> dict[str, int]:
    return {
        "drift": d, "long_memory_candidate": m, "inconclusive": i, "not_run": 0,
        "errored": errored,
    }


def _reasons(no_rise: int = 0, k2_insig: int = 0, mixed: int = 0) -> dict[str, int]:
    return {"no_rise": no_rise, "k2_insignificant": k2_insig, "mixed": mixed}


def test_drift_headline_drift_majority_is_hedged_and_states_denominator():
    h = _drift_headline(_headline_counts(3, 1, 1), _reasons(mixed=1), 1.0, 7)
    assert (
        "In this window, a block-wise baseline recovers at least half of the K=2 likelihood "
        "gain for most assessed symbols — consistent with slow baseline drift (heuristic "
        "screen; see caveats)"
    ) in h
    assert "(5 of 7 requested symbols assessed; failed, errored and not-run excluded)" in h
    assert "mostly slow baseline drift" not in h


def test_drift_headline_long_memory_candidate_majority_names_block_width():
    h = _drift_headline(_headline_counts(0, 3, 1), _reasons(k2_insig=1), 2.5, 4)
    assert "not explained by drift slower than 2.5 business-time hours (median block width)" in h


def test_drift_headline_no_rise_majority_says_nothing_to_explain():
    h = _drift_headline(_headline_counts(1, 0, 4), _reasons(no_rise=3, mixed=1), 1.0, 6)
    assert (
        "On the first window, the one the drift control uses, most symbols show no "
        "material K=1→K=2 rise, so the control has no rise to explain there"
    ) in h
    assert "(5 of 6 requested symbols assessed" in h
    assert "Across all" not in h  # no across-window summary supplied


def test_drift_headline_unresolved_names_inconclusive_count_and_largest_reason():
    h = _drift_headline(_headline_counts(6, 6, 18), _reasons(no_rise=12, mixed=6), 1.0, 30)
    assert (
        "No verdict holds a majority; 18 of 30 assessed symbols are inconclusive "
        "(12 show no K=2 rise at all)"
    ) in h
    h2 = _drift_headline(_headline_counts(1, 1, 2), _reasons(k2_insig=2), 1.0, 4)
    assert "2 of 4 assessed symbols are inconclusive (2 have a K=2 gain that is not significant)" in h2
    # Ties are not majorities, and zero-inconclusive ties do not name a reason.
    h3 = _drift_headline(_headline_counts(2, 2, 0), _reasons(), 1.0, 4)
    assert "No verdict holds a majority" in h3 and "inconclusive" not in h3


def test_drift_headline_no_symbol_assessed():
    h = _drift_headline(_headline_counts(0, 0, 0, errored=2), _reasons(), None, 2)
    assert "No symbol was assessed" in h and "(0 of 2 requested symbols assessed" in h


@pytest.mark.parametrize(
    ("n_k1", "n_k2", "dll_k2", "expected"),
    [
        (0.40, 0.45, 50.0, "no_rise"),  # rise 0.05 <= 0.1, even though dll_k2 is big
        (0.40, 0.50, 50.0, "no_rise"),  # boundary: rise == 0.1 is still no_rise
        (0.40, 0.60, 1.0, "k2_insignificant"),
        (0.40, 0.60, 50.0, "mixed"),
    ],
)
def test_inconclusive_reason_split(n_k1: float, n_k2: float, dll_k2: float, expected: str):
    assert _inconclusive_reason(n_k1, n_k2, dll_k2) == expected


def test_drift_control_exception_keeps_k_sweep_record_and_is_reported(
    planted_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def _raise(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic control failure")

    monkeypatch.setattr(q6b, "baseline_drift_control", _raise)
    result = run_q6b(
        planted_root, tmp_path / "out", symbols=["SMALLUSDT"], month="2023-06",
        windows=WINDOWS, ks=KS, null_sims=0,
    )
    assert result["n_symbols_successful"] == 1, result["failures"]
    rec = result["records"][0]
    assert rec["n_median_by_k"][1] > 0.0 and rec["n_median_by_k"][2] > 0.0  # K-sweep survives
    assert rec["drift_verdict"] is None
    assert rec["drift_error"] == "RuntimeError: synthetic control failure"
    counts = result["cross_section"]["drift_verdict_counts"]
    assert counts["errored"] == 1 and counts["not_run"] == 0
    md = (tmp_path / "out" / "q6b_kernel_sensitivity.md").read_text()
    assert "SMALLUSDT: drift control errored (RuntimeError: synthetic control failure)" in md
    assert "errored = 1" in md
    df = pl.read_parquet(tmp_path / "out" / "q6b_kernel_sensitivity.parquet")
    assert df["drift_error"].to_list() == ["RuntimeError: synthetic control failure"]


# --- review fixes: null calibration, strict JSON, first-window labelling ----


def test_null_floor_is_calibrated_at_the_fit_cap(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, int] = {}

    def fake_null(n_events: int, **kwargs: object) -> np.ndarray:
        seen["n_events"] = n_events
        return np.array([0.01, 0.02, 0.03])

    monkeypatch.setattr(q6b, "spurious_delta21_null", fake_null)
    records = [{"n_events_per_window": 699_462, "n_median_by_k": {1: 0.7}}]
    floor = _null_floor_p90(records, null_sims=3)
    assert seen["n_events"] == MAX_FIT_EVENTS
    assert floor["n_events_per_window"] == MAX_FIT_EVENTS
    assert floor["n_events_per_window_uncapped"] == 699_462

    small = [{"n_events_per_window": 40_000, "n_median_by_k": {1: 0.7}}]
    assert _null_floor_p90(small, null_sims=3)["n_events_per_window"] == 40_000
    assert seen["n_events"] == 40_000


def test_null_sims_default_is_50_everywhere(tmp_path: Path):
    import inspect

    assert DEFAULT_NULL_SIMS == 50
    assert inspect.signature(run_q6b).parameters["null_sims"].default == 50
    symbols = tmp_path / "s.txt"
    symbols.write_text("AAAUSDT\n")
    assert _parse_args(["--symbols-file", str(symbols)]).null_sims == 50


def test_json_float_maps_non_finite_to_none():
    assert _json_float(float("nan")) is None
    assert _json_float(float("inf")) is None
    assert _json_float(None) is None
    assert _json_float(0.25) == 0.25


def test_record_is_strict_json_when_beta_is_non_positive(planted_root: Path, monkeypatch: pytest.MonkeyPatch):
    from types import SimpleNamespace

    def fake_fit(times: np.ndarray, t_end: float, K: int) -> SimpleNamespace:
        return SimpleNamespace(n=0.5, alphas=np.array([0.5]), betas=np.array([0.0]), converged=True)

    monkeypatch.setattr(q6b, "fit_hawkes_multiexp", fake_fit)
    # the unbounded timescale is carried internally and flagged drift-suspect ...
    assert _fit_capped_multiexp(np.array([0.0, 1.0, 2.0]), 2.0, 2)["inv_beta_slow"] == float("inf")
    rec = _symbol_record(planted_root, "SMALLUSDT", "2023-06", WINDOWS, KS, drift_blocks=0)
    assert rec["drift_suspect"] is True
    # ... but never reaches the JSON as inf/NaN
    assert rec["median_inv_beta_slow_k2_s"] is None
    assert rec["ratio_inv_beta_slow_to_bin_width"] is None
    assert rec["ratio_inv_beta_slow_to_window_length"] is None
    assert all(w["inv_beta_slow_by_k"][2] is None for w in rec["per_window"])
    json.dumps(rec, allow_nan=False)


def test_record_delta21_is_none_when_k2_is_not_fit(planted_root: Path):
    rec = _symbol_record(planted_root, "SMALLUSDT", "2023-06", WINDOWS, (1,), drift_blocks=0)
    assert rec["delta21"] is None
    assert rec["median_inv_beta_slow_k2_s"] is None
    json.dumps(rec, allow_nan=False)


def _record(symbol: str, delta21: float | None, **over: object) -> dict:
    rec = {
        "symbol": symbol, "n_events": 1_000_000, "n_events_per_window": 166_666, "windows": 6,
        "ks": [1, 2, 3], "n_median_by_k": {"1": 0.7, "2": 0.8, "3": 0.85},
        "n_converged_by_k": {"1": 6, "2": 6, "3": 6}, "delta21": delta21,
        "median_inv_beta_slow_k2_s": 5.0 if delta21 is not None else None,
        "window_length_s": 1000.0, "bin_width_s": 1800.0,
        "ratio_inv_beta_slow_to_bin_width": 0.01 if delta21 is not None else None,
        "ratio_inv_beta_slow_to_window_length": 0.005 if delta21 is not None else None,
        "drift_suspect": False, "within_finite_sample_null": False,
        "drift_verdict": "inconclusive", "drift_inconclusive_reason": "no_rise",
        "dll_pw": 1.0, "dll_k2": 0.5, "dll_threshold": 9.8, "drift_n_k1": 0.7, "drift_n_k2": 0.72,
        "n_k1_piecewise": 0.7, "drift_block_width_s": 3600.0, "drift_error": None,
        "per_window": [
            {"n_by_k": {"1": 0.7, "2": 0.8, "3": 0.85},
             "converged_by_k": {"1": True, "2": True, "3": True},
             "inv_beta_slow_by_k": {"1": 1.0, "2": 5.0, "3": 9.0}}
        ],
    }
    rec.update(over)
    return rec


def _result(records: list[dict], null_floor: dict | None) -> dict:
    n = len(records)
    return {
        "month": "2023-06", "windows": 6, "ks": [1, 2, 3], "drift_blocks": 12,
        "n_symbols_requested": n, "n_symbols_successful": n, "n_symbols_failed": 0,
        "records": records, "failures": [], "q6_json_used": None,
        "cross_section": {
            "delta21_distribution": {"median": 0.14, "mean": 0.14, "std": 0.1, "min": 0.0, "max": 0.3, "n": n},
            "frac_n2_at_least_0_9": 0.0, "cv_comparison": None, "null_floor_p90": null_floor,
            "drift_verdict_counts": {"drift": 0, "long_memory_candidate": 0, "inconclusive": n,
                                      "not_run": 0, "errored": 0},
            "drift_inconclusive_reason_counts": {"no_rise": n, "k2_insignificant": 0, "mixed": 0},
        },
    }


def _null_floor(n_events: int = 250_000) -> dict:
    return {"n_events_per_window": n_events, "n_events_per_window_uncapped": 699_462,
            "alpha_used": 0.7, "beta_used": 2.0, "n_sims": 50, "p90": 0.01, "median": 0.007}


def _md(tmp_path: Path, result: dict) -> str:
    _write_results_md(tmp_path, result)
    return (tmp_path / "q6b_kernel_sensitivity.md").read_text()


def test_headline_labels_first_window_and_reports_across_window_delta21(tmp_path: Path):
    recs = [_record("A", 0.30), _record("B", 0.20), _record("C", 0.05)]
    md = _md(tmp_path, _result(recs, None))
    assert "On the first window, the one the drift control uses" in md
    assert "Across all 6 windows, the median-across-windows Δ21 exceeds 0.1 for 2 of 3 symbols" in md
    assert "Most symbols show no material K=1→K=2 rise in this window" not in md


def test_null_paragraph_is_conditional_on_how_many_symbols_are_within_it(tmp_path: Path):
    none_within = _md(tmp_path, _result([_record("A", 0.3), _record("B", 0.2)], _null_floor()))
    assert "(0/2 symbols)" in none_within
    assert "Their Δ21 is no larger" not in none_within
    assert "No symbol's Δ21 falls at or below it" in none_within

    some = [_record("A", 0.005, within_finite_sample_null=True), _record("B", 0.2)]
    md = _md(tmp_path, _result(some, _null_floor()))
    assert "(1/2 symbols)" in md
    assert "For the symbols within it, Δ21 is no larger than a well-specified" in md


def test_null_paragraph_flags_a_null_calibrated_above_the_fit_cap(tmp_path: Path):
    md = _md(tmp_path, _result([_record("A", 0.3)], _null_floor(699_462)))
    assert "calibrated at a larger size than the fits used" in md
    md = _md(tmp_path, _result([_record("A", 0.3)], _null_floor(250_000)))
    assert "calibrated at a larger size" not in md
    assert "capped at the 250,000-event fit cap" in md


def test_boundary_fits_are_flagged_in_the_drift_table_and_notes(tmp_path: Path):
    boundary = _record("A", 0.3, drift_n_k2=0.9999999999999999)
    boundary["per_window"][0]["n_by_k"]["3"] = 0.9999999999999999
    md = _md(tmp_path, _result([boundary, _record("B", 0.2)], None))
    assert "| 0.7000 | 0.7200 |" in md  # unflagged row unchanged
    assert "1.0000† |" in md
    assert f"† n̂ ≥ {BOUNDARY_N_HAT:g}: the fit sits on the stationarity boundary" in md
    assert "1 of 6 sit on the stationarity boundary" in md


def test_none_delta21_renders_as_na(tmp_path: Path):
    md = _md(tmp_path, _result([_record("A", None), _record("B", 0.2)], None))
    row = next(line for line in md.splitlines() if line.startswith("| A |") and "n/a" in line)
    assert "+nan" not in md and "nan" not in md.lower().replace("finance", "")
    assert row.count("n/a") >= 3
