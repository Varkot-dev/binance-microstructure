from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from microstructure.analyses.q1b_zigzag import (
    SURVIVAL_MAX_REL_CHANGE,
    _survives,
    _write_results_md,
    run_q1b,
    zigzag_amplitude,
)
from microstructure.data.catalog import parquet_path
from microstructure.estimators.acf import sign_acf


def test_zigzag_amplitude_zero_for_flat_acf():
    acf = np.zeros(11)
    acf[0] = 1.0
    assert zigzag_amplitude(acf) == 0.0


def test_zigzag_amplitude_positive_for_alternating_acf():
    # even lags high, odd lags low/negative -> positive amplitude
    acf = np.zeros(11)
    acf[0] = 1.0
    for lag in range(1, 11):
        acf[lag] = 0.3 if lag % 2 == 0 else -0.2
    amp = zigzag_amplitude(acf)
    assert amp > 0
    assert abs(amp - 0.5) < 1e-9  # 0.3 - (-0.2)


def _write_alternating_fixture_with_same_ts_pairs(
    tmp_path: Path, symbol: str, period: str, n_events: int, n_same_ts_pairs: int
) -> None:
    """Strictly alternating +1/-1/+1/-1... sign series (perfect zigzag), with a
    subset of adjacent event pairs forced onto a SHARED millisecond timestamp
    (opposite-signed, since alternation already guarantees adjacent signs
    differ) so the same-ts tie-break machinery (B, C) is actually exercised.
    """
    signs = np.array([1 if i % 2 == 0 else -1 for i in range(n_events)], dtype=np.int8)
    t0 = datetime(2023, 6, 1, tzinfo=UTC)

    # give each event its own ms by default, 2ms apart
    ts = [t0 + timedelta(milliseconds=2 * i) for i in range(n_events)]

    # force the first n_same_ts_pairs adjacent (even, odd) index pairs to share a ts
    for k in range(min(n_same_ts_pairs, n_events // 2)):
        i = 2 * k
        ts[i + 1] = ts[i]

    df = pl.DataFrame(
        {
            "agg_trade_id": np.arange(n_events),
            "price": np.full(n_events, 100.0),
            "qty": np.ones(n_events),
            "first_trade_id": np.arange(n_events),
            "last_trade_id": np.arange(n_events),
            "ts": ts,
            "is_buyer_maker": signs < 0,
        },
        schema_overrides={"ts": pl.Datetime("ms", "UTC")},
    )
    p = parquet_path(tmp_path, symbol, "aggTrades", period)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(p)


def test_run_q1b_recovers_perfect_zigzag_and_survives_perturbations(tmp_path: Path):
    n_events = 5_000
    _write_alternating_fixture_with_same_ts_pairs(tmp_path, "TESTUSDT", "2023-06", n_events, n_same_ts_pairs=200)

    out = tmp_path / "results"
    res = run_q1b(tmp_path, out, symbol="TESTUSDT", period="2023-06")

    assert (out / "q1b_zigzag.png").exists()
    assert (out / "q1b_zigzag.md").exists()
    assert (out / "q1b_zigzag.json").exists()

    # to_aggressor_events merges opposite-signed same-ts rows only if they share
    # (ts, side); here consecutive pairs differ in sign, so no merging happens
    # and n_events survives the load_events round trip.
    assert res["n_events"] == n_events

    # perfect alternation -> baseline ACF(1) should be strongly negative,
    # ACF(2) strongly positive -> large positive zigzag amplitude
    baseline = res["baseline"]
    assert baseline["acf_1_to_10"][0] < -0.8  # lag 1
    assert baseline["acf_1_to_10"][1] > 0.8  # lag 2
    assert baseline["zigzag_amplitude"] > 0.8

    # randomizing the tie-break on the forced same-ts pairs should barely move
    # the amplitude, since only a small fraction of pairs are affected
    randomized = res["randomized_tiebreak"]
    rel_change = abs(randomized["zigzag_amplitude"] - baseline["zigzag_amplitude"]) / baseline["zigzag_amplitude"]
    assert rel_change < 0.1

    # netting collapses the forced same-ts pairs (opposite signs, equal qty ->
    # zero net, dropped), but the vast majority of untouched alternating events
    # preserve the zigzag
    netted = res["netted"]
    assert netted["zero_net_groups_dropped"] == 200
    assert netted["zigzag_amplitude"] > 0.7


def test_zigzag_amplitude_matches_sign_acf_direct_computation(tmp_path: Path):
    """Cross-check: the baseline zigzag amplitude in run_q1b's output matches an
    independent sign_acf call on the raw loaded signs, not just internal consistency."""
    n_events = 3_000
    _write_alternating_fixture_with_same_ts_pairs(tmp_path, "TESTUSDT", "2023-06", n_events, n_same_ts_pairs=0)

    out = tmp_path / "results"
    res = run_q1b(tmp_path, out, symbol="TESTUSDT", period="2023-06")

    signs = np.array([1 if i % 2 == 0 else -1 for i in range(n_events)], dtype=np.int8)
    acf = sign_acf(signs, 30)
    expected = [float(acf[lag]) for lag in range(1, 11)]
    for got, exp in zip(res["baseline"]["acf_1_to_10"], expected, strict=True):
        assert abs(got - exp) < 1e-9


def _result(amp_a: float, amp_b: float, amp_c: float) -> dict:
    acf = [0.1] * 10
    return {
        "symbol": "TESTUSDT", "period": "2023-06", "n_events": 1000,
        "frac_consecutive_pairs_same_ts": 0.01,
        "frac_opposite_sign_among_same_ts_adjacent_pairs": 1.0,
        "n_same_ts_pairs": 10, "max_same_ts_group_size": 2,
        "baseline": {"acf_1_to_10": acf, "zigzag_amplitude": amp_a},
        "randomized_tiebreak": {"pairs_swapped": 5, "acf_1_to_10": acf, "zigzag_amplitude": amp_b},
        "netted": {"n_netted_events": 990, "zero_net_groups_dropped": 1, "acf_1_to_10": acf,
                   "zigzag_amplitude": amp_c},
    }


def test_survives_uses_the_stated_threshold():
    assert _survives(0.10, 0.10 * (1 + SURVIVAL_MAX_REL_CHANGE - 0.01))
    assert not _survives(0.10, 0.10 * (1 + SURVIVAL_MAX_REL_CHANGE + 0.01))
    assert not _survives(0.10, -0.10)  # sign flip never survives
    assert not _survives(0.0, 0.0)


def test_verdict_survival_claim_is_computed(tmp_path: Path):
    _write_results_md(tmp_path, _result(0.10, 0.099, 0.09))
    md = (tmp_path / "q1b_zigzag.md").read_text()
    assert "The zigzag survives both perturbations" in md
    assert "at most 25%" in md

    _write_results_md(tmp_path, _result(0.10, 0.099, 0.04))
    md = (tmp_path / "q1b_zigzag.md").read_text()
    assert "survives both perturbations" not in md
    assert "does not survive every perturbation" in md
    assert "fails that test under netting" in md
    assert "persists through both perturbations" not in md
