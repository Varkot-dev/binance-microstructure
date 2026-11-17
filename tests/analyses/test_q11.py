"""Tests for Q11: mid-price direction from top-of-book quotes.

Contract under test, all on synthetic order books with a known answer:

1. Labels: a known mid path gives known up/down/unchanged labels, and the
   purge drops exactly the samples whose label window crosses a block boundary.
2. Queue-imbalance world, P(up | move) = 0.5 + 0.3 * imbalance: the
   queue-imbalance logistic recovers the Bayes accuracy (0.65) and LightGBM on
   all features does not beat it by more than noise.
3. Interaction world, direction = sign(imbalance) x last trade sign: only the
   tree model finds it.
4. Random-walk world: every model scores about 0.5 and the verdict reports
   that the gross edge never exceeds the cost.
5. The metric helpers agree with scikit-learn, and the end-to-end run from
   parquet files writes its three artifacts and records skipped symbols.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from sklearn.metrics import matthews_corrcoef, roc_auc_score

from microstructure.analyses import q11_mid_direction as q11
from microstructure.analyses.q11_report import economic_lines
from microstructure.ml.evaluate import MS_PER_DAY
from microstructure.ml.features import WARMUP

TICK = 0.01
DAY0 = 19_500 * MS_PER_DAY  # an arbitrary UTC midnight in 2023


def _synthetic_book(n: int, n_days: int, seed: int, rule: str) -> q11.EventBook:
    """Events evenly spread over n_days; the mid steps by one tick after half of them.

    The step after event i is decided by the state a predictor sees at i:
      "imbalance":   P(up) = 0.5 + 0.3 * queue_imbalance[i]
      "interaction": P(up) = 0.5 + 0.3 * sign(queue_imbalance[i]) * sign[i-1]
      "random":      P(up) = 0.5
    """
    rng = np.random.default_rng(seed)
    ts = DAY0 + (np.arange(n) * (n_days * MS_PER_DAY / n)).astype(np.int64)
    sign = rng.choice(np.array([-1, 1], dtype=np.int8), size=n)
    u = rng.uniform(0.02, 0.98, size=n)
    bid_q, ask_q = 100.0 * u, 100.0 * (1.0 - u)
    imb = 2.0 * u - 1.0
    if rule == "imbalance":
        p_up = 0.5 + 0.3 * imb
    elif rule == "interaction":
        last = np.concatenate([[1], sign[:-1]])
        p_up = 0.5 + 0.3 * np.sign(imb) * last
    else:
        p_up = np.full(n, 0.5)
    step = np.where(rng.random(n) < 0.5, np.where(rng.random(n) < p_up, 1, -1), 0)
    mid_ticks = 10_000 + np.concatenate([[0], np.cumsum(step[:-1])])
    bid_p = (mid_ticks - 0.5) * TICK
    ask_p = (mid_ticks + 0.5) * TICK
    return q11.EventBook(
        ts=ts, sign=sign, qty=np.exp(rng.normal(size=n)),
        price=np.where(sign > 0, ask_p, bid_p), n_prints=rng.integers(1, 4, size=n),
        bid_p=bid_p, bid_q=bid_q, ask_p=ask_p, ask_q=ask_q,
        ofi_cum=np.cumsum(rng.normal(scale=20.0, size=n)),
    )


def _run(rule: str, seed: int, horizons=(1,), fee_bps: float = 5.0) -> dict:
    """Fit on a 6-day synthetic window (3 fit, 1 embargo, 2 validation), score on 3 more."""
    stride = int(np.gcd.reduce(horizons))
    train = q11.build_samples(_synthetic_book(70_000, 6, seed, rule), TICK, horizons, stride)
    test_book = _synthetic_book(40_000, 3, seed + 1, rule)
    test = q11.build_samples(test_book, TICK, horizons, stride)
    fit_block = (DAY0, DAY0 + 3 * MS_PER_DAY)
    valid_block = (DAY0 + 4 * MS_PER_DAY, DAY0 + 6 * MS_PER_DAY)
    test_block = (DAY0, DAY0 + 3 * MS_PER_DAY)
    out = {}
    for h in horizons:
        pred, meta = q11.fit_horizon(train, fit_block, valid_block, test, test_block, h,
                                     stride, max_rounds=60, threads=1)
        out[str(h)] = {
            **q11.score_horizon(pred, meta["thresholds"], fee_bps, n_boot=200), "fit": meta,
        }
    return {"symbol": "SYN", "horizons": out}


# ---------------------------------------------------------------- labels


def test_direction_labels_on_a_known_path():
    mid = np.array([10.0, 10.0, 10.5, 10.5, 10.0, 9.5, 9.5, 10.0])
    rows = np.arange(8)
    label, has = q11.direction_labels(mid, rows, h=2, tol=0.1)
    assert has.tolist() == [True] * 6 + [False] * 2
    assert label[:6].tolist() == [1, 1, -1, -1, -1, 1]
    label1, has1 = q11.direction_labels(mid, rows, h=1, tol=0.1)
    assert label1[:7].tolist() == [0, 1, 0, -1, -1, 0, 1]
    assert has1.sum() == 7


def test_label_tolerance_absorbs_float_noise():
    mid = np.array([17.3845, 17.3845 + 1e-12, 17.3850])
    label, _ = q11.direction_labels(mid, np.array([0, 1]), h=1, tol=0.001 / 4)
    assert label.tolist() == [0, 1]


def test_purge_removes_exactly_the_rows_whose_label_crosses_the_boundary():
    h, stride = 6, 2
    book = _synthetic_book(3 * WARMUP, 2, seed=0, rule="random")
    s = q11.build_samples(book, TICK, (h,), stride)
    boundary = DAY0 + MS_PER_DAY
    first_next_day = int(np.searchsorted(book.ts, boundary))
    kept = s.rows[q11.usable(s, h, DAY0, boundary)]
    in_day = s.rows[s.ts < boundary]
    # Kept: every grid row whose closing event i+h is still before the
    # boundary. Dropped: the grid rows among the last h events of the day.
    assert np.array_equal(kept, in_day[in_day + h < first_next_day])
    dropped = np.setdiff1d(in_day, kept)
    assert dropped.size == h // stride
    assert dropped.min() >= first_next_day - h
    # Second block: starts cleanly at the boundary, ends where labels run out.
    kept2 = s.rows[q11.usable(s, h, boundary, boundary + MS_PER_DAY)]
    assert kept2.min() >= first_next_day and kept2.max() + h < book.ts.size


def test_every_hth_sample_has_non_overlapping_label_windows():
    h, stride = 6, 2
    s = q11.build_samples(_synthetic_book(WARMUP + 3000, 1, 0, "random"), TICK, (h,), stride)
    rows = s.rows[q11.usable(s, h, DAY0, DAY0 + MS_PER_DAY, every=h // stride)]
    assert np.all(np.diff(rows) >= h)


def test_tied_millisecond_rows_are_never_used():
    book = _synthetic_book(WARMUP + 2000, 1, 0, "random")
    ts = book.ts.copy()
    ts[WARMUP + 10] = ts[WARMUP + 9]
    tied_book = q11.EventBook(**{**book.__dict__, "ts": ts})
    s = q11.build_samples(tied_book, TICK, (1,), 1)
    assert WARMUP + 10 not in s.rows[q11.usable(s, 1, DAY0, DAY0 + MS_PER_DAY)]
    assert WARMUP + 9 in s.rows[q11.usable(s, 1, DAY0, DAY0 + MS_PER_DAY)]


def test_sample_features_do_not_see_the_future():
    """Corrupting events from `cut` on must leave every earlier sample row unchanged."""
    book = _synthetic_book(WARMUP + 3000, 1, 5, "imbalance")
    cut = WARMUP + 2000
    d = {k: v.copy() for k, v in book.__dict__.items()}
    d["sign"][cut:] *= -1
    d["qty"][cut:] *= 50.0
    d["price"][cut:] += 3.0
    d["bid_p"][cut:] += 3.0
    d["ask_p"][cut:] += 3.07
    d["bid_q"][cut:] *= 0.01
    d["ofi_cum"][cut:] -= 1e5
    base = q11.build_samples(book, TICK, (1,), 1)
    changed = q11.build_samples(q11.EventBook(**d), TICK, (1,), 1)
    before = base.rows < cut
    assert np.array_equal(base.X[before], changed.X[before])
    assert not np.array_equal(base.X[~before], changed.X[~before])


# ---------------------------------------------------------------- metric helpers


def test_mcc_from_confusion_matches_sklearn():
    rng = np.random.default_rng(0)
    for k in (2, 3):
        y = rng.integers(0, k, size=500)
        p = np.where(rng.random(500) < 0.6, y, rng.integers(0, k, size=500))
        c = np.bincount(y * k + p, minlength=k * k).reshape(k, k).astype(float)
        assert q11.mcc_from_confusion(c) == pytest.approx(matthews_corrcoef(y, p))
    always_one_class = np.array([[0.0, 5.0, 0.0], [0.0, 9.0, 0.0], [0.0, 4.0, 0.0]])
    assert q11.mcc_from_confusion(always_one_class) == 0.0


def test_auc_from_hist_matches_sklearn_on_binned_scores():
    rng = np.random.default_rng(1)
    y = rng.integers(0, 2, size=2000)
    score_bin = np.clip((rng.normal(size=2000) + y) * 3 + 10, 0, 19).astype(int)
    pos = np.bincount(score_bin[y == 1], minlength=20).astype(float)
    neg = np.bincount(score_bin[y == 0], minlength=20).astype(float)
    assert q11.auc_from_hist(pos, neg) == pytest.approx(roc_auc_score(y, score_bin))


def test_day_bootstrap_sums_resamples_whole_days():
    stats = np.array([[1.0, 10.0], [2.0, 20.0], [4.0, 40.0]])
    boot = q11.day_bootstrap_sums(stats, n_boot=500, seed=0)
    assert boot.shape == (500, 2)
    assert np.allclose(boot[:, 1], 10.0 * boot[:, 0])       # days stay intact
    assert boot[:, 0].min() >= 3.0 and boot[:, 0].max() <= 12.0
    assert abs(boot[:, 0].mean() - 7.0) < 0.3


def test_three_class_prediction_picks_the_largest_probability():
    p_move = np.array([0.2, 0.9, 0.9])
    p_up = np.array([0.9, 0.9, 0.1])
    assert q11.three_class_prediction(p_move, p_up).tolist() == [1, 2, 0]


# ---------------------------------------------------------------- synthetic worlds


def test_queue_imbalance_world_logistic_recovers_bayes_accuracy():
    res = _run("imbalance", seed=10)["horizons"]["1"]
    b = res["binary"]
    assert abs(res["share_unchanged"] - 0.5) < 0.02
    # Bayes accuracy is E[0.5 + 0.3 |imb|] with imb uniform on (-0.96, 0.96): 0.644.
    assert b["qi_logit"]["accuracy"] == pytest.approx(0.644, abs=0.015)
    assert abs(b["majority"]["accuracy"] - 0.5) < 0.02
    assert b["gbm_all"]["accuracy"] < b["qi_logit"]["accuracy"] + 0.01
    assert b["gbm_all"]["auc"] < b["qi_logit"]["auc"] + 0.01
    assert res["gbm_minus_qi"]["auc"]["ci95"][0] < 0.005
    # Nothing predicts whether the mid moves, so the three-way skill is modest
    # but real: direction is called correctly on the half that moves.
    assert res["three_class"]["majority"]["mcc"] == 0.0
    # A one-tick move (1 bp at this price) cannot pay a 10 bp fee.
    assert not q11.edge_verdict([{"symbol": "SYN", "horizons": {"1": res}}])["any_exceeds_cost"]
    top = res["economics"]["qi_logit"]
    assert top[-1]["gross_bps"] > top[0]["gross_bps"] > 0   # confidence sorts the edge


def test_interaction_world_only_the_tree_model_finds_it():
    b = _run("interaction", seed=20)["horizons"]["1"]["binary"]
    assert abs(b["qi_logit"]["accuracy"] - 0.5) < 0.03
    assert abs(b["logit_all"]["accuracy"] - 0.5) < 0.03
    assert b["gbm_all"]["accuracy"] > 0.75      # Bayes accuracy is 0.80


def test_random_walk_world_scores_one_half_and_reports_no_edge():
    sym = _run("random", seed=30, horizons=(2, 4))
    for h in ("2", "4"):
        res = sym["horizons"][h]
        for m in q11.MODELS:
            assert abs(res["binary"][m]["accuracy"] - 0.5) < 0.03
            assert abs(res["three_class"][m]["mcc"]) < 0.03
        for m in q11.LEARNED:
            assert abs(res["binary"][m]["auc"] - 0.5) < 0.03
            for row in res["economics"][m]:
                assert not row.get("exceeds_cost", False)
    verdict = q11.edge_verdict([sym])
    assert verdict["any_exceeds_cost"] is False and verdict["significant"] == []
    summary = {"verdict": verdict, "config": {"taker_fee_bps": 5.0}}
    text = " ".join(economic_lines(summary))
    assert text.startswith("**No.**") and "not tradeable" in text


def test_verdict_wording_follows_the_computed_cells():
    def cell(gross: float, net_lo: float) -> dict:
        return {"top_fraction": 0.05, "n": 100, "gross_bps": gross, "cost_bps": 10.0,
                "gross_over_cost": gross / 10.0, "net_bps": gross - 10.0,
                "net_ci95": [net_lo, gross - 10.0 + 1.0], "exceeds_cost": gross > 10.0}

    def summary(c: dict) -> dict:
        sym = {"symbol": "SYN", "horizons": {"10": {"economics": {"gbm_all": [c]}}}}
        return {"verdict": q11.edge_verdict([sym]), "config": {"taker_fee_bps": 5.0}}

    weak = " ".join(economic_lines(summary(cell(11.0, -2.0))))
    assert weak.startswith("**Not established.**") and "do not call this tradeable" in weak
    strong = " ".join(economic_lines(summary(cell(14.0, 1.0))))
    assert "not evidence of a profitable strategy" in strong
    assert "tradeable" not in " ".join(economic_lines(summary(cell(14.0, 1.0)))).split("(")[0]
    none = " ".join(economic_lines(summary(cell(2.0, -9.0))))
    assert none.startswith("**No.**")


# ---------------------------------------------------------------- end to end


def _write_day(root: Path, symbol: str, day: str, seed: int, n: int = 7000) -> None:
    rng = np.random.default_rng(seed)
    d0 = int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000)
    tts = d0 + 1000 + np.sort(rng.choice(np.arange(10, 86_000_000, 10), size=n, replace=False))
    mid_ticks = 20_000 + np.cumsum(rng.integers(-1, 2, size=n))
    bid = (mid_ticks - 0.5) * TICK
    ask = (mid_ticks + 0.5) * TICK
    quotes = pl.DataFrame({
        "update_id": np.arange(n, dtype=np.int64) + seed * 1_000_000,
        "bid_price": bid, "bid_qty": rng.uniform(1, 50, size=n),
        "ask_price": ask, "ask_qty": rng.uniform(1, 50, size=n),
        "ts": tts - 5,
    }).with_columns(pl.col("ts").cast(pl.Datetime("ms", "UTC")))
    buyer_maker = rng.random(n) < 0.5
    trades = pl.DataFrame({
        "agg_trade_id": np.arange(n, dtype=np.int64),
        "price": np.where(buyer_maker, bid, ask), "qty": rng.uniform(0.1, 5, size=n),
        "first_trade_id": np.arange(n, dtype=np.int64),
        "last_trade_id": np.arange(n, dtype=np.int64),
        "ts": tts, "is_buyer_maker": buyer_maker,
    }).with_columns(pl.col("ts").cast(pl.Datetime("ms", "UTC")))
    for kind, frame in (("bookTicker", quotes), ("aggTrades", trades)):
        path = root / "parquet" / kind / symbol / f"{day}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(path)


def test_extract_day_joins_the_quote_strictly_before_each_trade(tmp_path: Path):
    _write_day(tmp_path, "AAAUSDT", "2023-06-05", seed=1)
    d = q11.extract_day(tmp_path, "AAAUSDT", "2023-06-05")
    assert d["ts"].size == 7000 and int(d["n_events_no_quote"]) == 0
    assert float(d["increment"]) == pytest.approx(TICK)
    assert float(d["at_quote_share"]) == 1.0
    # Every quote is one tick wide, so all the time is spent in the 1-tick bin.
    assert d["spread_hist_ms"][1] == d["spread_hist_ms"].sum()
    assert q11.spread_profile(
        [{"increment": TICK, "spread_hist_ms": d["spread_hist_ms"].tolist()}], TICK
    )["one_tick_time_share"] == 1.0


def test_run_q11_end_to_end_writes_artifacts_and_records_skips(tmp_path: Path):
    root, out = tmp_path / "data", tmp_path / "results"
    days = q11.day_range("2023-06-05", "2023-06-08") + q11.day_range("2023-06-10", "2023-06-11")
    for k, day in enumerate(days):
        _write_day(root, "AAAUSDT", day, seed=k + 1)
    _write_day(root, "BBBUSDT", "2023-06-05", seed=99)
    cfg = {"train_start": "2023-06-05", "train_end": "2023-06-08", "test_start": "2023-06-10",
           "test_end": "2023-06-11", "valid_days": 2, "embargo_days": 1, "horizons": [2, 4],
           "max_rounds": 20}
    summary = q11.run_q11(root, out, ["AAAUSDT", "BBBUSDT"], cfg, fee_bps=5.0, n_boot=100, threads=1)
    assert [s["symbol"] for s in summary["symbols"]] == ["AAAUSDT"]
    assert summary["skipped"][0]["symbol"] == "BBBUSDT"
    assert "5 of 6 days missing" in summary["skipped"][0]["reason"]
    for ext in ("json", "md", "png"):
        assert (out / f"q11_mid_direction.{ext}").stat().st_size > 0
    stored = json.loads((out / "q11_mid_direction.json").read_text())
    assert stored["verdict"]["any_exceeds_cost"] is False
    assert stored["symbols"][0]["fit_days"] == ["2023-06-05"]
    md = (out / "q11_mid_direction.md").read_text()
    assert "## Verdict" in md and "BBBUSDT" in md
    assert chr(0x2014) not in md and chr(0x2013) not in md
    # A second call must reuse the cached predictions rather than refit.
    (root / "parquet").rename(root / "parquet_gone")
    again = q11.run_q11(root, out, ["AAAUSDT"], cfg, fee_bps=1.0, n_boot=100)
    assert again["symbols"][0]["horizons"]["2"]["economics"]["gbm_all"][0]["fee_cost_bps"] == 2.0
    # The thread override and the fitted feature list come from the cached meta.
    assert summary["symbols"][0]["lgb_threads"] == again["symbols"][0]["lgb_threads"] == 1
    assert stored["config"]["features"] == stored["symbols"][0]["fit_settings"]["features"]
    assert stored["symbols"][0]["fit_settings"]["train_cap"] == q11.TRAIN_CAP


def test_prediction_key_covers_every_fit_setting_but_not_fee_or_threads(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = {"train_start": "2023-06-05", "train_end": "2023-06-08", "test_start": "2023-06-10",
           "test_end": "2023-06-11", "valid_days": 2, "embargo_days": 1, "horizons": [2, 4]}
    base = q11.config_key(cfg)
    assert q11.config_key({**cfg, "max_rounds": 20}) != base
    changes = [
        (q11, "TRAIN_CAP", 1000), (q11, "VALID_CAP", 1000), (q11, "BASE_LEAF", 7),
        (q11, "WARMUP", 10), (q11, "FEATURES", [*q11.FEATURES, "extra"]),
        (q11, "LGB_PARAMS", {**q11.LGB_PARAMS, "num_leaves": 7}),
        (q11, "DAY_CACHE_VERSION", q11.DAY_CACHE_VERSION + 1),
    ]
    keys = set()
    for obj, name, value in changes:
        with monkeypatch.context() as mp:
            mp.setattr(obj, name, value)
            keys.add(q11.config_key(cfg))
    assert base not in keys and len(keys) == len(changes)
    with monkeypatch.context() as mp:
        mp.setattr(q11, "LGB_PARAMS", {**q11.LGB_PARAMS, "num_threads": 1})
        assert q11.config_key(cfg) == base
    # Predictions cached under other settings are not found: a miss, never a silent reuse.
    (tmp_path / "AAAUSDT").mkdir()
    np.savez_compressed(tmp_path / "AAAUSDT" / f"pred_{base}.npz", x=np.zeros(1))
    (tmp_path / "AAAUSDT" / f"meta_{base}.json").write_text("{}")
    assert q11.load_cached(tmp_path, "AAAUSDT", cfg) is not None
    monkeypatch.setattr(q11, "BASE_LEAF", 7)
    assert q11.load_cached(tmp_path, "AAAUSDT", cfg) is None


def test_day_cache_without_the_current_version_is_extracted_again(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, cache, day = tmp_path / "data", tmp_path / "cache", "2023-06-05"
    _write_day(root, "AAAUSDT", day, seed=1)
    first = q11.cached_day(root, cache, "AAAUSDT", day)
    path = q11.day_cache_path(cache, "AAAUSDT", day)
    assert q11.day_cache_current(path) and "version" not in first
    stamp = path.stat().st_mtime_ns
    again = q11.cached_day(root, cache, "AAAUSDT", day)
    assert path.stat().st_mtime_ns == stamp and set(again) == set(first)
    # A file from before the version field (here with wrong content) is not trusted.
    np.savez_compressed(path, **{**first, "ts": first["ts"][:10]})
    assert not q11.day_cache_current(path)
    fresh = q11.cached_day(root, cache, "AAAUSDT", day)
    np.testing.assert_array_equal(fresh["ts"], first["ts"])
    assert q11.day_cache_current(path)
    monkeypatch.setattr(q11, "DAY_CACHE_VERSION", q11.DAY_CACHE_VERSION + 1)
    assert not q11.day_cache_current(path)


def test_windows_must_leave_an_embargo_day():
    cfg = {"train_start": "2023-06-05", "train_end": "2023-06-08", "test_start": "2023-06-09",
           "test_end": "2023-06-10", "valid_days": 1, "embargo_days": 1, "horizons": [10]}
    with pytest.raises(ValueError, match="whole day"):
        q11.check_windows(cfg)
    with pytest.raises(ValueError):
        q11.split_train_days(["2023-06-05", "2023-06-06"], valid_days=2, embargo_days=1)
