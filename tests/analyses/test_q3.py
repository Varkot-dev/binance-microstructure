import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from microstructure.analyses.q3_ofi import run_q3
from microstructure.data.catalog import parquet_path


def _synthetic_book_ticker(
    n: int, beta: float, base_mid: float, seed: int
) -> pl.DataFrame:
    """Build an L1 update path where delta_mid == beta * ofi_events(...), exactly.

    At every update i>=1, both bid and ask tick UP by the same amount dp_i
    (spread held fixed), so under `ofi_events` only the new-bid term
    (+bid_q[i]) and old-ask term (+ask_q[i-1]) survive:
    ofi_i = bid_q[i] + ask_q[i-1], non-negative by construction, so dp_i >= 0
    and "always ticks up" is self-consistent. bid_q[i] is a random positive
    magnitude and dp_i is defined as beta * ofi_i, so the mid moves by exactly
    beta * ofi_i per update, and by beta * (the bar's summed ofi) over any bar,
    with no residual noise. ask_q[i] (needed for the next update's ofi) is
    drawn independently.
    """
    rng = np.random.default_rng(seed)
    spread = 0.02
    half_spread = spread / 2

    bid_q = np.abs(rng.normal(30.0, 10.0, n)) + 1.0
    ask_q = np.abs(rng.normal(30.0, 10.0, n)) + 1.0

    mid = np.empty(n)
    mid[0] = base_mid
    for i in range(1, n):
        ofi_i = bid_q[i] + ask_q[i - 1]
        mid[i] = mid[i - 1] + beta * ofi_i

    bid_p = mid - half_spread
    ask_p = mid + half_spread

    t0 = datetime(2023, 6, 1, tzinfo=UTC)
    ts = [t0 + timedelta(milliseconds=200 * i) for i in range(n)]
    return pl.DataFrame(
        {
            "update_id": np.arange(n),
            "bid_price": bid_p,
            "bid_qty": bid_q,
            "ask_price": ask_p,
            "ask_qty": ask_q,
            "ts": ts,
        },
        schema_overrides={"ts": pl.Datetime("ms", "UTC")},
    )


def _synthetic_book_ticker_down(
    n: int, beta: float, base_mid: float, seed: int
) -> pl.DataFrame:
    """Mirror of `_synthetic_book_ticker` where bid/ask tick DOWN every update.

    At every update i>=1, both bid and ask tick DOWN by the same amount dp_i
    (spread held fixed), so under `ofi_events` only the old-bid term
    (`-bid_q[i-1]`, from `b_now <= b_prev`) and the new-ask term (`-ask_q[i]`,
    from `a_now <= a_prev`) survive: ofi_i = -(bid_q[i-1] + ask_q[i]), strictly
    negative. bid_q[i] (needed for the next update's ofi) is drawn
    independently. dp_i is defined as beta * ofi_i (< 0), so with beta > 0 the
    mid moves down on every update, the mirror image of the up-ticking fixture
    above.
    """
    rng = np.random.default_rng(seed)
    spread = 0.02
    half_spread = spread / 2

    bid_q = np.abs(rng.normal(30.0, 10.0, n)) + 1.0
    ask_q = np.abs(rng.normal(30.0, 10.0, n)) + 1.0

    mid = np.empty(n)
    mid[0] = base_mid
    for i in range(1, n):
        ofi_i = -(bid_q[i - 1] + ask_q[i])
        mid[i] = mid[i - 1] + beta * ofi_i

    bid_p = mid - half_spread
    ask_p = mid + half_spread

    t0 = datetime(2023, 6, 1, tzinfo=UTC)
    ts = [t0 + timedelta(milliseconds=200 * i) for i in range(n)]
    return pl.DataFrame(
        {
            "update_id": np.arange(n),
            "bid_price": bid_p,
            "bid_qty": bid_q,
            "ask_price": ask_p,
            "ask_qty": ask_q,
            "ts": ts,
        },
        schema_overrides={"ts": pl.Datetime("ms", "UTC")},
    )


def test_run_q3_recovers_known_ofi_slope(tmp_path: Path):
    beta = 0.002
    # 200ms per update -> 50 updates per 10s bar, matching window="10s"
    df = _synthetic_book_ticker(n=60_000, beta=beta, base_mid=1800.0, seed=11)
    p = parquet_path(tmp_path, "TESTUSDT", "bookTicker", "2023-06-01")
    p.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(p)

    out = tmp_path / "results"
    res = run_q3(tmp_path, out, symbol="TESTUSDT", periods=["2023-06-01"], window="10s")

    assert (out / "q3_ofi_scatter.png").exists()
    assert (out / "q3_results.md").exists()
    assert (out / "q3_results.json").exists()

    assert abs(res["slope"] - beta) < 0.15 * abs(beta)
    assert res["r2"] > 0.8
    assert res["n_windows"] > 0
    assert "depth_scaling_check" in res

    def reject_constant(name):
        raise AssertionError(f"non-strict JSON constant {name}")

    json.loads((out / "q3_results.json").read_text(), parse_constant=reject_constant)


def test_run_q3_recovers_known_ofi_slope_when_book_ticks_down(tmp_path: Path):
    """Negative-OFI counterpart of `test_run_q3_recovers_known_ofi_slope`.

    The up-tick fixture only produces OFI >= 0, so it never exercises
    `ofi_events`' negative-contribution branches (`b_now <= b_prev` old-bid
    subtraction, `a_now <= a_prev` new-ask addition) through the q3 pipeline.
    This fixture ticks bid/ask DOWN every update, so every per-update OFI is
    strictly negative and the mid moves down with it (delta_mid = beta * ofi_sum
    with beta > 0). The recovered slope should still land within 15% of the
    planted positive beta, since the negativity is in the OFI values and
    delta_mid, not in the slope.
    """
    beta = 0.002
    df = _synthetic_book_ticker_down(n=60_000, beta=beta, base_mid=1800.0, seed=23)
    p = parquet_path(tmp_path, "TESTDOWNUSDT", "bookTicker", "2023-06-01")
    p.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(p)

    out = tmp_path / "results"
    res = run_q3(tmp_path, out, symbol="TESTDOWNUSDT", periods=["2023-06-01"], window="10s")

    assert (out / "q3_ofi_scatter.png").exists()
    assert (out / "q3_results.md").exists()
    assert (out / "q3_results.json").exists()

    assert abs(res["slope"] - beta) < 0.15 * abs(beta)
    assert res["r2"] > 0.8
    assert res["n_windows"] > 0
    assert "depth_scaling_check" in res


def _unit_step_book(n_bars: int, updates_per_bar: int, seed: int) -> pl.DataFrame:
    """Noiseless L1 book whose every update moves the mid by exactly 0.5 * OFI.

    Quantities are fixed at 1.0. An update either lifts the bid by 1 (OFI +1,
    mid +0.5) or lowers the ask by 1 (OFI -1, mid -0.5), so delta_mid = 0.5 * OFI
    holds update by update and bar by bar. The spread starts wide enough to stay
    positive. Updates sit 2 s apart, starting on a 10 s bar boundary.
    """
    rng = np.random.default_rng(seed)
    n = n_bars * updates_per_bar
    steps = rng.choice([1, -1], size=n)
    bid = 1000.0 + np.cumsum(np.where(steps == 1, 1.0, 0.0))
    ask = 5000.0 - np.cumsum(np.where(steps == -1, 1.0, 0.0))
    t0 = datetime(2023, 6, 1, tzinfo=UTC)
    return pl.DataFrame(
        {
            "bid_price": bid,
            "bid_qty": np.ones(n),
            "ask_price": ask,
            "ask_qty": np.ones(n),
            "mid": (bid + ask) / 2,
            "ts": [t0 + timedelta(seconds=2 * i) for i in range(n)],
        },
        schema_overrides={"ts": pl.Datetime("ms", "UTC")},
    )


def test_bars_anchor_delta_mid_to_the_mid_before_the_bars_first_update():
    """With 5 updates per bar, delta_mid measured from the bar's first post-update
    mid drops one move in five and biases the slope to ~0.4 with R^2 ~ 0.8."""
    from microstructure.analyses.q3_ofi import _bucket_bars
    from microstructure.estimators.ofi import ols_through_origin

    bars = _bucket_bars(_unit_step_book(n_bars=400, updates_per_bar=5, seed=3), "10s")
    # Drop the first bar: it has 4 updates because the first row has no OFI.
    bars = bars.filter(pl.col("n_updates") == 5)
    fit = ols_through_origin(bars["ofi_sum"].to_numpy(), bars["delta_mid"].to_numpy())
    assert fit.slope == pytest.approx(0.5, abs=1e-9)
    assert fit.r2 == pytest.approx(1.0, abs=1e-9)
