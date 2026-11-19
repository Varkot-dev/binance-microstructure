from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "c4_prepost_trading", ROOT / "research" / "politics" / "c4_prepost_trading.py")
c4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c4)


def _bars(n: int, rng: np.random.Generator) -> dict:
    """Noise market: random-walk price, independent buy and sell notional per minute."""
    px = 100 * np.exp(np.cumsum(rng.normal(0, 1e-3, n)))
    buy = rng.gamma(5.0, 1.0, n)
    sell = rng.gamma(5.0, 1.0, n)
    return {"buy": buy, "sell": sell, "px": px, "n_ev": np.full(n, 100.0),
            "n_large": rng.binomial(100, 0.001, n).astype(float),
            "lbuy": np.zeros(n), "lsell": np.zeros(n)}


# ---------------------------------------------------------------- alignment sign

def test_alignment_sign_follows_later_move():
    n = 400
    px = np.full(n, 100.0)
    a = np.array([100, 250])
    px[101:] = 101.0  # up after anchor 100 (from minute +1 on)
    px[251:] = 99.0  # down after anchor 250
    sg = c4.signs(px, a)
    assert sg["s"].tolist() == [1.0, -1.0]
    # s5 uses P(15)/P(4): flat from +4 to +15 here, so no sign
    assert sg["s5"].tolist() == [0.0, 0.0]
    buy, sell = np.zeros(n), np.zeros(n)
    buy[90:100] = 3.0  # pre-window buying before both anchors
    sell[90:100] = 1.0
    buy[240:250] = 3.0
    sell[240:250] = 1.0
    bars = {"buy": buy, "sell": sell, "px": px}
    al = c4.aligned(c4.pre_outcomes(bars, a), sg["s"])
    assert np.allclose(al["al_imb_pre10"], [0.5, -0.5])  # same way as move: +, opposite: -
    # zero sign gives no aligned value
    al0 = c4.aligned(c4.pre_outcomes(bars, a), sg["s5"])
    assert np.isnan(al0["al_imb_pre10"]).all()


def test_pre_window_excludes_minute_zero_and_shift_moves_one_minute():
    n = 200
    buy, sell = np.ones(n), np.ones(n)
    buy[100] = 1000.0  # minute 0 of anchor 100
    bars = {"buy": buy, "sell": sell, "px": np.full(n, 100.0)}
    a = np.array([100])
    assert c4.pre_outcomes(bars, a)["imb_pre10"][0] == 0.0
    buy[99] = 1000.0  # minute -1: inside the window, outside after a 60 s shift
    assert c4.pre_outcomes(bars, a)["imb_pre10"][0] > 0.9
    assert c4.pre_outcomes(bars, a, shift=-1)["imb_pre10"][0] < 0.01


def test_s5_skips_first_minutes():
    px = np.full(100, 100.0)
    px[41:44] = 105.0  # spike in minutes +1..+3 only, then below the start
    px[44:] = 99.0
    sg = c4.signs(px, np.array([40]))
    assert sg["s"][0] == -1.0 and sg["s5"][0] == 0.0
    px[50:] = 98.0
    assert c4.signs(px, np.array([40]))["s5"][0] == -1.0


# ---------------------------------------------------------------- controls

def test_matched_controls_never_overlap_events():
    rng = np.random.default_rng(1)
    t_min = np.sort(rng.choice(np.arange(5_000, 400_000), 60, replace=False))
    o_min = np.sort(rng.choice(np.arange(0, 420_000), 3_000, replace=False))
    oi = c4.match_others(t_min, o_min, np.ones(o_min.size, bool), t_min, k=2)
    others = o_min[oi]
    assert len(set(oi.tolist())) == oi.size  # without replacement
    assert others.size > 60
    for m in others:
        assert np.abs(t_min - m).min() > c4.GAP
    d = np.diff(np.sort(others))
    assert (d > c4.GAP).all()
    # windows [-70, +16] never share a minute
    assert c4.GAP >= c4.WIN[1] - c4.WIN[0]


def test_matched_controls_prefer_same_hour():
    t_min = np.array([10 * 1440 + 14 * 60 + 5])  # 14:05 on day 10
    o_min = np.array([20 * 1440 + 13 * 60, 30 * 1440 + 14 * 60 + 30, 40 * 1440 + 15 * 60])
    oi = c4.match_others(t_min, o_min, np.ones(3, bool), t_min, k=1)
    assert oi.tolist() == [1]
    oi2 = c4.match_others(t_min, o_min, np.array([True, False, True]), t_min, k=1)
    assert oi2.tolist() == [0]  # nearest hour, earlier first


def test_placebos_spaced_and_away_from_block():
    rng = np.random.default_rng(2)
    block = np.array([1_000, 5_000])
    got = c4.draw_spaced(np.arange(0, 10_000), block, 20, rng)
    assert got.size == 20
    assert all(np.abs(block - g).min() > c4.GAP for g in got)
    assert (np.diff(got) > c4.GAP).all()
    elig = np.ones(50_000, bool)
    pool = c4.placebo_pool(elig, block, 100)
    assert (np.diff(pool) > c4.GAP).all()
    assert all(np.abs(block - g).min() > c4.GAP for g in pool)


def test_post_free_mask():
    posts = np.array([500])
    m = c4.post_free_mask(posts, n=1000, span=(-70, 20))
    assert not m[500 - 20] and not m[500 + 70] and not m[500]
    assert m[500 - 21] and m[500 + 71]


# ---------------------------------------------------------------- planted flow

def _simulate(plant: float, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    n = 200_000
    bars = _bars(n, rng)
    anchors = np.arange(1_000, n - 1_000, 400)
    rng.shuffle(anchors)
    t, o = np.sort(anchors[:120]), np.sort(anchors[120:360])
    if plant:
        # informed-looking flow: in minutes -10..-1 before each tariff anchor, extra
        # taker volume in the direction of the later move
        for a in t:
            up = bars["px"][a + 15] > bars["px"][a]
            side = "buy" if up else "sell"
            bars[side][a - 10:a] += plant
    out = {}
    for g, a in (("t", t), ("o", o)):
        sg = c4.signs(bars["px"], a)
        out[g] = c4.aligned(c4.pre_outcomes(bars, a), sg["s"])["al_imb_pre10"]
    return c4.compare(out["t"], out["o"], B=2_000, seed=seed)


def test_planted_pre_post_flow_is_detected():
    r = _simulate(plant=1.5, seed=3)
    assert r["D"] > 0.05
    assert r["p1"] < 0.01


def test_pure_noise_is_not_detected():
    ps = [_simulate(plant=0.0, seed=s)["p1"] for s in range(20, 40)]
    assert sum(p < 0.05 for p in ps) <= 3  # about 1 in 20 expected by chance
    assert np.median(ps) > 0.2


def test_decision_rule_needs_both_primary_and_guard():
    yes = {"D": 0.1, "p1": 0.01}
    no = {"D": 0.1, "p1": 0.2}
    assert c4.decision(yes, yes) == "evidence of unusual pre-post trading"
    assert c4.decision(yes, no) == "no evidence"
    assert c4.decision(no, yes) == "no evidence"
    assert c4.decision({"D": -0.1, "p1": 0.01}, yes) == "no evidence"


def test_reduce_day_bars_and_large_threshold():
    import datetime as dt

    import polars as pl

    day0 = int(dt.datetime(2025, 1, 2, tzinfo=dt.UTC).timestamp() * 1000)
    n = 5_000
    rng = np.random.default_rng(4)
    ts = np.sort(rng.integers(day0, day0 + 86_400_000, n))
    qty = np.ones(n)
    qty[:3] = 1_000.0  # three huge trades
    df = pl.DataFrame({"ts": pl.Series(ts).cast(pl.Datetime("ms")),
                       "sign": np.where(np.arange(n) % 2 == 0, 1, -1).astype(np.int8),
                       "qty": qty, "price": np.full(n, 10.0)})
    b = c4.reduce_day(df)
    assert b["n_ev"].sum() == n
    assert b["n_large"].sum() == 3
    assert np.isclose(b["buy"].sum() + b["sell"].sum(), 10.0 * qty.sum())
    last_min = int((ts[-1] - day0) // 60_000)
    assert np.isfinite(b["px"][last_min])
