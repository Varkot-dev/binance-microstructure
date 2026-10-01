from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from microstructure.analyses.q3_ofi import run_q3
from microstructure.data.catalog import parquet_path


def _synthetic_book_ticker(
    n: int, beta: float, base_mid: float, seed: int
) -> pl.DataFrame:
    """Build an L1 update path where delta_mid == beta * ofi_events(...), exactly.

    At every update i>=1, both bid and ask tick UP by the same amount
    dp_i (spread held fixed), which under `ofi_events` makes the new-bid
    term (+bid_q[i]) and old-ask term (+ask_q[i-1]) the only surviving
    contributions: ofi_i = bid_q[i] + ask_q[i-1] (both non-negative by
    construction, so dp_i is always >= 0 and the "always ticks up"
    assumption is self-consistent). bid_q[i] is drawn as a random positive
    magnitude; dp_i is then DEFINED as beta * ofi_i, so mid moves by
    exactly beta * ofi_i on every single update -- and therefore by
    beta * (bar's summed ofi) over any bar, with zero residual noise.
    ask_q[i] (needed for the *next* update's ofi_i+1) is drawn independently.
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

    At every update i>=1, both bid and ask tick DOWN by the same amount
    dp_i (spread held fixed), which under `ofi_events` makes the old-bid
    term (`-bid_q[i-1]`, from `b_now <= b_prev`) and the new-ask term
    (`-ask_q[i]`, from `a_now <= a_prev`) the only surviving contributions:
    ofi_i = -(bid_q[i-1] + ask_q[i]), strictly negative for every i since
    both quantities are positive magnitudes. bid_q[i] (needed for the
    *next* update's ofi_i+1) is drawn independently. dp_i is then DEFINED
    as beta * ofi_i (ofi_i < 0), so with beta > 0 the mid moves down on
    every update, matching the "always ticks down" assumption
    self-consistently -- the mirror image of the up-ticking fixture above.
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


def test_run_q3_recovers_known_ofi_slope_when_book_ticks_down(tmp_path: Path):
    """Negative-OFI counterpart of `test_run_q3_recovers_known_ofi_slope`.

    The original fixture only ever produces OFI >= 0 (mid always ticks up),
    which never exercises `ofi_events`' negative-contribution branches
    (`b_now <= b_prev` old-bid subtraction, `a_now <= a_prev` new-ask
    addition) through the real q3 pipeline. This fixture ticks bid/ask DOWN
    every update instead, making every per-update OFI strictly negative (mid
    moves down in lock-step with it, since delta_mid = beta * ofi_sum with
    beta > 0), and asserts the recovered slope still lands within 15% of the
    planted (positive) beta -- the fixture's negativity lives in the OFI
    values and delta_mid, not in the recovered slope itself.
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
