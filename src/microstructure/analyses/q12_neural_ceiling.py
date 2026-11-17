"""Q12: how much held-out timing likelihood does the linear Hawkes family leave unexplained?

Q6 and Q6b fit exponential-kernel Hawkes models to trade arrivals and get
branching ratios that depend on the kernel family (0.71 with one exponential,
0.85 with two, 0.96 from the model-free count-variance estimator). A neural
point process cannot settle that dispute: a recurrent network is a
short-memory model and there is no accepted way to read a branching ratio out
of one. It can answer a different, well-posed question. On identical held-out
events, how many nats per event better is a flexible model than a
homogeneous Poisson process and than the K = 1, 2, 3 exponential Hawkes fits?
If the neural model barely beats the best Hawkes, the parametric family is
close to adequate for one-step-ahead timing. If it wins clearly, there is
structure the linear self-exciting form misses. Either answer is a result.

Method, per symbol-month.

1. Events are aggressor-level (`load_events`). Whole UTC days are split with
   `microstructure.ml.dataset.split_masks`: 20 training days, 2 validation
   days, 1 embargo day, the rest test.
2. Business time as in Q6/Q6b, except that the 48-bin intraday profile is
   estimated on the training days only and applied to all blocks.
3. Every model is scored with the same interval-censored likelihood (the
   probability of the recorded 1 ms cell, mapped to business time, with the
   tie truncation; see `microstructure.ml.tpp`).
4. Poisson: rate from the training block. Hawkes K = 1, 2, 3: the repo's MLE
   (`fit_hawkes_exp`, `fit_hawkes_multiexp`) on contiguous training chunks of
   at most Q6b's event cap. Those fits maximize a continuous likelihood, while
   the neural model is trained on the censored score itself. To keep the
   comparison fair, each K also gets a short Nelder-Mead polish of the
   censored training score started from its MLE. Among a K's candidates the
   one with the best validation score is used, the same role validation
   plays for the network (early stopping). Both variants are reported.
5. Neural: GRU with a log-normal mixture head on log gaps and exponentially
   weighted rates, trained by truncated backpropagation on random contiguous
   windows of the training block.
6. All models start with empty state at the first event of the test block,
   are fed `burn_in` events that are not scored, and are scored on exactly
   the same remaining test events. Reported: nats per event over Poisson,
   day-block confidence intervals for neural minus Hawkes from per-event
   differences, and time-rescaling residual diagnostics.

Each symbol-month is cached as JSON under data/ml_cache/q12/ (the trial log:
configuration, per-epoch training record, fitted parameters, scores). The
report stage (`q12_report`) reads only those caches and needs no PyTorch.

Outputs: q12_neural_ceiling.{json,md,png}.
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from microstructure.analyses import q12_report
from microstructure.analyses.q6b_common import MAX_FIT_EVENTS, N_BINS
from microstructure.data.catalog import parquet_path
from microstructure.data.jsonio import dumps_strict
from microstructure.estimators.hawkes import (
    _alphas_from_logits,
    _nelder_mead,
    fit_hawkes_exp,
    fit_hawkes_multiexp,
)
from microstructure.ml import tpp
from microstructure.ml.dataset import split_masks
from microstructure.ml.evaluate import MS_PER_DAY, day_block_ci
from microstructure.signals.eventtime import intraday_rate_profile
from microstructure.signals.load import load_events

CACHE_VERSION = 1
CACHE_SUBDIR = Path("ml_cache") / "q12"

# Recorded-gap buckets (milliseconds, inclusive lower edge) for locating
# where a likelihood difference comes from.
GAP_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("0 ms", 0, 1), ("1 ms", 1, 2), ("2 to 9 ms", 2, 10), ("10 to 99 ms", 10, 100),
    ("100 to 999 ms", 100, 1000), ("1 s or more", 1000, np.iinfo(np.int64).max),
)


@dataclass(frozen=True)
class Q12Config:
    ks: tuple[int, ...] = (1, 2, 3)
    burn_in: int = 20_000          # events fed but not scored at the start of each block
    hawkes_fit_events: int = MAX_FIT_EVENTS
    hawkes_chunks: int = 3         # contiguous training chunks each K is fit on
    polish_iters: int = 300        # Nelder-Mead iterations on the censored score; 0 disables
    polish_events: int = 100_000
    n_seeds: int = 2
    n_boot: int = 2000
    threads: int = 1               # PyTorch threads; more is slower when cores are shared
    tpp: tpp.TPPConfig = field(default_factory=tpp.TPPConfig)

    def as_dict(self) -> dict:
        return {**asdict(self), "ks": list(self.ks), "tpp": self.tpp.as_dict()}


# ---------------------------------------------------------------------------
# Hawkes candidates.
# ---------------------------------------------------------------------------


def _mean_score(scored: tpp.Scored, first: int) -> float:
    return float(scored.loglik[first:].mean())


def _fit_hawkes(times: np.ndarray, k: int) -> dict:
    t_end = float(times[-1])
    if k == 1:
        fit = fit_hawkes_exp(times, t_end)
        alphas, betas = [fit.alpha], [fit.beta]
    else:
        fit = fit_hawkes_multiexp(times, t_end, K=k)
        alphas, betas = fit.alphas.tolist(), fit.betas.tolist()
    return {"mu": float(fit.mu), "alphas": alphas, "betas": betas, "n": float(sum(alphas)),
            "converged": bool(fit.converged)}


def polish_hawkes(params: dict, cen: tpp.Censored, first: int, iters: int) -> dict:
    """Maximize the censored training score from an MLE start (same family, same K).

    The repo's MLE treats the recorded millisecond times as exact. This puts
    the Hawkes parameters on the objective every model is judged by, as the
    network's training does. Unconstrained coordinates are those of
    `fit_hawkes_multiexp`, so the branching ratio stays below 1.
    """
    k = len(params["alphas"])
    alphas = np.maximum(np.asarray(params["alphas"], dtype=np.float64), 1e-12)
    slack = max(1.0 - float(alphas.sum()), 1e-9)
    x0 = np.concatenate(([np.log(params["mu"])], np.log(alphas / slack), np.log(params["betas"])))

    def neg(p: np.ndarray) -> float:
        try:
            with np.errstate(all="ignore"):
                scored = tpp.hawkes_censored(
                    float(np.exp(p[0])), _alphas_from_logits(p[1 : 1 + k]), np.exp(p[1 + k :]), cen
                )
        except ValueError:
            return 1e18
        value = -_mean_score(scored, first)
        return value if np.isfinite(value) else 1e18

    best, _, converged = _nelder_mead(neg, x0, max_iter=iters, step=0.1, tol=1e-8)
    a = _alphas_from_logits(best[1 : 1 + k])
    return {"mu": float(np.exp(best[0])), "alphas": a.tolist(), "betas": np.exp(best[1 + k :]).tolist(),
            "n": float(a.sum()), "converged": bool(converged)}


def _chunk_starts(n: int, size: int, chunks: int) -> list[int]:
    """Evenly spaced contiguous chunks; a single chunk is the one nearest the test block."""
    if n <= size or chunks <= 1:
        return [max(n - size, 0)]
    return [round(c * (n - size) / (chunks - 1)) for c in range(chunks)]


def hawkes_candidates(
    cen_train: tpp.Censored, cen_valid: tpp.Censored, cfg: Q12Config, burn_valid: int
) -> dict[int, dict]:
    """Per K: the best MLE chunk and the validation-selected candidate (MLE or polished)."""

    def valid_score(p: dict) -> float:
        return _mean_score(tpp.hawkes_censored(p["mu"], p["alphas"], p["betas"], cen_valid),
                           burn_valid)

    size = min(cfg.hawkes_fit_events, cen_train.n)
    out: dict[int, dict] = {}
    for k in cfg.ks:
        fits = []
        for start in _chunk_starts(cen_train.n, size, cfg.hawkes_chunks):
            sub = cen_train.slice(start, start + size)
            t0 = time.perf_counter()
            p = _fit_hawkes(sub.tau, k)
            p.update(chunk_start=start, chunk_events=size, variant="mle",
                     fit_seconds=time.perf_counter() - t0)
            p["valid_nats"] = valid_score(p)
            fits.append(p)
        mle = max(fits, key=lambda p: p["valid_nats"])
        selected = mle
        if cfg.polish_iters > 0:
            n_pol = min(cfg.polish_events, size)
            sub = cen_train.slice(mle["chunk_start"], mle["chunk_start"] + n_pol)
            t0 = time.perf_counter()
            pol = polish_hawkes(mle, sub, min(cfg.burn_in, n_pol // 10), cfg.polish_iters)
            pol.update(chunk_start=mle["chunk_start"], chunk_events=n_pol, variant="polished",
                       fit_seconds=time.perf_counter() - t0)
            pol["valid_nats"] = valid_score(pol)
            if pol["valid_nats"] > mle["valid_nats"]:
                selected = pol
        out[k] = {"mle": mle, "selected": selected, "all_mle_fits": fits}
    return out


# ---------------------------------------------------------------------------
# One symbol-month.
# ---------------------------------------------------------------------------


def _block(ts: np.ndarray, mask: np.ndarray) -> np.ndarray:
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        raise ValueError("an evaluation block is empty; the month has too few days")
    return ts[idx[0] : idx[-1] + 1]


def _bucket_table(diff: np.ndarray, gap_ms: np.ndarray, prev_tied: np.ndarray) -> list[dict]:
    """Where a per-event score difference lives: by recorded gap and after ties.

    `contribution` is share * mean difference, so the gap buckets sum to the
    overall mean difference.
    """
    rows = []
    groups = [(name, (gap_ms >= lo) & (gap_ms < hi)) for name, lo, hi in GAP_BUCKETS]
    groups.append(("previous event tied", prev_tied))
    for name, sel in groups:
        share = float(sel.mean())
        mean = float(diff[sel].mean()) if sel.any() else 0.0
        rows.append({"bucket": name, "share": share, "mean_diff": mean,
                     "contribution": share * mean})
    return rows


def analyze_events(ts_ms: np.ndarray, cfg: Q12Config, symbol: str, month: str) -> dict:
    """Full protocol on one array of event times (int64 ms, sorted). Returns the cache record."""
    tpp._require_torch()
    import torch

    torch.set_num_threads(cfg.threads)
    t_start = time.perf_counter()
    train_m, valid_m, test_m = split_masks(ts_ms)
    ts_train, ts_valid, ts_test = (_block(ts_ms, m) for m in (train_m, valid_m, test_m))
    profile = intraday_rate_profile(ts_train, N_BINS)
    cen_train, cen_valid, cen_test = (
        tpp.censor_intervals(t, profile) for t in (ts_train, ts_valid, ts_test)
    )
    burn = cfg.burn_in
    for name, cen in (("train", cen_train), ("valid", cen_valid), ("test", cen_test)):
        if cen.n < 2 * burn + cfg.tpp.window:
            raise ValueError(f"{name} block has {cen.n} events; too few for burn_in={burn}")

    rate = (cen_train.n - 1) / float(cen_train.tau[-1])
    pois_valid = _mean_score(tpp.poisson_censored(rate, cen_valid), burn)
    pois_test = tpp.poisson_censored(rate, cen_test)

    t0 = time.perf_counter()
    cands = hawkes_candidates(cen_train, cen_valid, cfg, burn)
    hawkes_seconds = time.perf_counter() - t0

    # Neural model: scaler from scored training rows only.
    t0 = time.perf_counter()
    scaler = tpp.fit_scaler(tpp.tpp_features(cen_train, cfg.tpp.horizons_s), burn)
    blocks = [tpp.prepare_block(c, scaler, cfg.tpp.horizons_s, burn)
              for c in (cen_train, cen_valid, cen_test)]
    seeds = []
    best_model, best_valid = None, -np.inf
    for s in range(cfg.n_seeds):
        seed_cfg = tpp.TPPConfig(**{**asdict(cfg.tpp), "seed": cfg.tpp.seed + s})
        model, history = tpp.train_tpp(blocks[0], blocks[1], seed_cfg)
        valid_nats = max(h["valid_nats_per_event"] for h in history)
        test_nats = _mean_score(tpp.score_tpp(model, blocks[2], seed_cfg), burn)
        seeds.append({"seed": seed_cfg.seed, "history": history,
                      "valid_gain": valid_nats - pois_valid,
                      "test_gain": test_nats - _mean_score(pois_test, burn)})
        if valid_nats > best_valid:
            best_model, best_valid, best_seed = model, valid_nats, seed_cfg.seed
    neural_test = tpp.score_tpp(best_model, blocks[2], cfg.tpp)
    neural_seconds = time.perf_counter() - t0
    n_params = int(sum(p.numel() for p in best_model.parameters()))

    # Test scores on identical events.
    ts_scored = ts_test[burn:]
    scored: dict[str, tpp.Scored] = {"poisson": pois_test}
    valid_gain: dict[str, float] = {"neural": best_valid - pois_valid}
    hawkes_out: dict[str, dict] = {}
    for k, c in cands.items():
        name = f"hawkes_k{k}"
        sel = c["selected"]
        scored[name] = tpp.hawkes_censored(sel["mu"], sel["alphas"], sel["betas"], cen_test)
        valid_gain[name] = sel["valid_nats"] - pois_valid
        mle = c["mle"]
        mle_test = tpp.hawkes_censored(mle["mu"], mle["alphas"], mle["betas"], cen_test)
        hawkes_out[str(k)] = {
            "selected": sel, "mle": mle, "all_mle_fits": c["all_mle_fits"],
            "mle_test_gain": _mean_score(mle_test, burn) - _mean_score(pois_test, burn),
        }
    scored["neural"] = neural_test
    hawkes_names = [f"hawkes_k{k}" for k in cfg.ks]
    best_hawkes = max(hawkes_names, key=lambda m: valid_gain[m])  # chosen on validation only

    ll = {m: s.loglik[burn:] for m, s in scored.items()}
    models: dict[str, dict] = {}
    for m in (*hawkes_names, "neural"):
        ci = day_block_ci(ll[m], ll["poisson"], ts_scored, n_boot=cfg.n_boot)
        models[m] = {"test_gain": ci.as_dict(), "valid_gain": valid_gain[m]}
    neural_gain = models["neural"]["test_gain"]["estimate"]
    for m in hawkes_names:
        g = models[m]["test_gain"]["estimate"]
        models[m]["share_of_neural_gain"] = g / neural_gain if neural_gain > 0 else None
        models[m]["neural_minus"] = day_block_ci(
            ll["neural"], ll[m], ts_scored, n_boot=cfg.n_boot).as_dict()
    residuals = {m: tpp.residual_diagnostics(tpp.rescaling_residuals(s, burn))
                 for m, s in scored.items()}

    gap = cen_test.gap_ms[burn:]
    prev_tied = cen_test.gap_ms[burn - 1 : -1] == 0
    day = ts_scored // MS_PER_DAY
    per_day = [{"day": int(d), "n": int((day == d).sum()),
                **{m: float(v[day == d].sum()) for m, v in ll.items()}} for d in np.unique(day)]

    return {
        "cache_version": CACHE_VERSION, "symbol": symbol, "month": month,
        "config": cfg.as_dict(),
        "n_events": int(ts_ms.size), "n_train": cen_train.n, "n_valid": cen_valid.n,
        "n_test_scored": int(ts_scored.size), "n_test_days": int(np.unique(day).size),
        "tie_share_test": float((gap == 0).mean()),
        "share_gap_le_1ms_test": float((gap <= 1).mean()),
        "profile_min_max": [float(profile.min()), float(profile.max())],
        "poisson": {"rate_per_business_s": rate,
                    "test_nats_per_event": _mean_score(pois_test, burn)},
        "hawkes": hawkes_out, "models": models, "residuals": residuals,
        "best_hawkes": best_hawkes,
        "neural_minus_best_hawkes": models[best_hawkes]["neural_minus"],
        "gap_buckets_neural_minus_best_hawkes": _bucket_table(
            ll["neural"] - ll[best_hawkes], gap, prev_tied),
        "per_day_loglik_sums": per_day,
        "neural": {"seeds": seeds, "selected_seed": best_seed, "n_parameters": n_params,
                   "scaler": scaler.as_dict(),
                   "seed_spread_test_gain": float(np.ptp([s["test_gain"] for s in seeds]))},
        "seconds": {"hawkes": hawkes_seconds, "neural": neural_seconds,
                    "total": time.perf_counter() - t_start},
        "torch_version": torch.__version__,
    }


def cache_path(root: Path, symbol: str, month: str) -> Path:
    return root / CACHE_SUBDIR / f"{symbol}_{month}.json"


def symbol_record(root: Path, symbol: str, month: str, cfg: Q12Config, force: bool = False) -> dict:
    """Load the cached record if it was produced with this configuration, else compute it."""
    path = cache_path(root, symbol, month)
    if path.exists() and not force:
        cached = json.loads(path.read_text())
        if cached.get("cache_version") == CACHE_VERSION and cached.get("config") == json.loads(
            dumps_strict(cfg.as_dict())
        ):
            return cached
    ts = load_events(root, symbol, [month])["ts"].dt.epoch("ms").to_numpy()
    record = analyze_events(ts, cfg, symbol, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_strict(record))
    return json.loads(dumps_strict(record))


def run_q12(
    root: Path, out_dir: Path, symbols: list[str], months: list[str],
    cfg: Q12Config | None = None, force: bool = False,
) -> dict:
    cfg = cfg or Q12Config()
    records: list[dict] = []
    failures: list[dict] = []
    for month in months:
        for symbol in symbols:
            if not parquet_path(root, symbol, "aggTrades", month).exists():
                failures.append({"symbol": symbol, "month": month, "reason": "parquet not found"})
                continue
            try:
                records.append(symbol_record(root, symbol, month, cfg, force))
            except Exception as e:  # noqa: BLE001 - a per-symbol failure is logged, not fatal
                failures.append({"symbol": symbol, "month": month,
                                 "reason": f"{type(e).__name__}: {e}"})
    return q12_report.write_report(out_dir, records, failures)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    d, t = Q12Config(), tpp.TPPConfig()
    p = argparse.ArgumentParser(description="Q12: neural point process as a predictability ceiling")
    p.add_argument("--root", type=Path, default=Path("data"))
    p.add_argument("--out", type=Path, default=Path("results"))
    p.add_argument("--symbols", type=str, default="DOGEUSDT", help="comma-separated")
    p.add_argument("--months", type=str, default="2023-06", help="comma-separated YYYY-MM")
    p.add_argument("--force", action="store_true", help="recompute even if a cache matches")
    p.add_argument("--burn-in", type=int, default=d.burn_in)
    p.add_argument("--hawkes-fit-events", type=int, default=d.hawkes_fit_events,
                   help=f"events per Hawkes fit, capped at Q6b's {MAX_FIT_EVENTS}")
    p.add_argument("--hawkes-chunks", type=int, default=d.hawkes_chunks)
    p.add_argument("--polish-iters", type=int, default=d.polish_iters)
    p.add_argument("--polish-events", type=int, default=d.polish_events)
    p.add_argument("--n-seeds", type=int, default=d.n_seeds)
    p.add_argument("--n-boot", type=int, default=d.n_boot)
    p.add_argument("--threads", type=int, default=d.threads)
    p.add_argument("--hidden", type=int, default=t.hidden)
    p.add_argument("--components", type=int, default=t.n_components)
    p.add_argument("--horizons-s", type=str, default=",".join(str(h) for h in t.horizons_s),
                   help="comma-separated horizons of the rate inputs, business-time seconds")
    p.add_argument("--window", type=int, default=t.window)
    p.add_argument("--window-burn", type=int, default=t.window_burn)
    p.add_argument("--batch-size", type=int, default=t.batch_size)
    p.add_argument("--max-windows-per-epoch", type=int, default=t.max_windows_per_epoch)
    p.add_argument("--epochs", type=int, default=t.epochs)
    p.add_argument("--patience", type=int, default=t.patience)
    p.add_argument("--lr", type=float, default=t.lr)
    p.add_argument("--seed", type=int, default=t.seed)
    return p.parse_args(argv)


def config_from_args(a: argparse.Namespace) -> Q12Config:
    net = tpp.TPPConfig(
        hidden=a.hidden, n_components=a.components,
        horizons_s=tuple(float(h) for h in a.horizons_s.split(",")),
        window=a.window, window_burn=a.window_burn, batch_size=a.batch_size,
        max_windows_per_epoch=a.max_windows_per_epoch, epochs=a.epochs, patience=a.patience,
        lr=a.lr, seed=a.seed,
    )
    return Q12Config(
        burn_in=a.burn_in, hawkes_fit_events=min(a.hawkes_fit_events, MAX_FIT_EVENTS),
        hawkes_chunks=a.hawkes_chunks, polish_iters=a.polish_iters,
        polish_events=a.polish_events, n_seeds=a.n_seeds, n_boot=a.n_boot,
        threads=a.threads, tpp=net,
    )


def main(argv: list[str] | None = None) -> None:
    a = _parse_args(argv)
    result = run_q12(a.root, a.out, a.symbols.split(","), a.months.split(","),
                     config_from_args(a), a.force)
    print(result["verdict"]["headline"])


if __name__ == "__main__":
    main()
