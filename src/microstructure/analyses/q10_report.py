"""Q10 report stage: assemble cached artifacts into json, Markdown and a figure.

Reads only the per-symbol caches written by `q10_drift` (never raw data), so
it can be re-run in seconds. It owns the cache layout, the day-block
bootstrap of the transfer matrix, the verdict logic and the writers.

Bootstrap design. Every cell M[i, j] of a symbol's transfer matrix is a mean
over the test days of period j. Each bootstrap replicate draws one set of
whole days per period (shared by all symbols, so market-wide days stay
common) and recomputes every cell from the cached per-day sums. Any quantity
built from cells then inherits the right dependence automatically:

* the staleness gap G_j = M[j, j] - M[src, j] uses two cells of the same
  column, so both terms see the same resampled days (a paired comparison on
  identical test rows);
* the predictability change D_j = M[j, j] - M[src, src] and the raw drop
  M[src, src] - M[src, j] use cells of two different columns, whose days are
  drawn independently (a difference of independent blocks).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from microstructure.data.jsonio import dumps_strict
from microstructure.ml.drift import (
    MIN_ESS_SHARE,
    WEIGHT_CLIP_QUANTILE,
    aligned_day_sums,
    day_picks,
    percentile_ci,
    resampled_means,
    shift_decomposition,
)
from microstructure.ml.features import FEATURE_NAMES

PERIODS = ("2023-06", "2023-07", "2024-07", "2025-07", "2026-07")
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT", "LINKUSDT",
           "LTCUSDT", "AVAXUSDT", "1000PEPEUSDT")
TRANSFER_RUNGS = ("persistence", "linear", "logit_all", "gbm_all")
ATTRIBUTION_RUNGS = ("logit_all", "gbm_all")
PRIMARY_RUNG = "gbm_all"
METRICS = {"accuracy": ("correct", True), "log_loss_bits": ("loss", False)}
N_BOOT = 2000
TOP_COEFFICIENTS = 8
TOP_SHIFTED_FEATURES = 6
STEM = "q10_drift"


# ---------------------------------------------------------------------------
# Cache layout
# ---------------------------------------------------------------------------


def ladder_path(cache: Path, symbol: str, period: str) -> Path:
    """Shared with Q9: one fitted ladder per symbol-month."""
    return cache / "ladders" / symbol / f"{period}.pkl"


def q10_dir(cache: Path, symbol: str) -> Path:
    return cache / "q10" / symbol


def fit_path(cache: Path, symbol: str, period: str) -> Path:
    return q10_dir(cache, symbol) / f"fit_{period}.json"


def sample_path(cache: Path, symbol: str, period: str) -> Path:
    return q10_dir(cache, symbol) / f"sample_{period}.npz"


def transfer_path(cache: Path, symbol: str, test_period: str) -> Path:
    return q10_dir(cache, symbol) / f"transfer_{test_period}.json"


def shift_path(cache: Path, symbol: str, src: str, tgt: str) -> Path:
    return q10_dir(cache, symbol) / f"shift_{src}__{tgt}.json"


def _read(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


# ---------------------------------------------------------------------------
# Loading and the bootstrap of the transfer matrix
# ---------------------------------------------------------------------------


def _load_panel(cache: Path, symbols: list[str], periods: list[str]) -> tuple[dict, list[dict]]:
    """Symbols with a complete transfer matrix over `periods`; the rest with a reason."""
    panel: dict[str, dict] = {}
    skipped: list[dict] = []
    for sym in symbols:
        fits = {p: _read(fit_path(cache, sym, p)) for p in periods}
        transfers = {p: _read(transfer_path(cache, sym, p)) for p in periods}
        missing = [p for p in periods if fits[p] is None or transfers[p] is None]
        if not missing:
            missing = [f"{i}->{j}" for j in periods for i in periods
                       if i not in transfers[j]["cells"]]
        if missing:
            skipped.append({"symbol": sym, "reason": "no cached result for " + ", ".join(missing)})
            continue
        panel[sym] = {"fit": fits, "transfer": transfers}
    return panel, skipped


def _stat(point: np.ndarray, reps: np.ndarray, symbols: list[str]) -> dict:
    """Cross-symbol median with its day-bootstrap CI, plus each symbol's own estimate.

    `point` is [n_symbols], `reps` is [n_boot, n_symbols].
    """
    lo, hi = percentile_ci(np.nanmedian(reps, axis=1))
    per = {}
    for k, sym in enumerate(symbols):
        slo, shi = percentile_ci(reps[:, k])
        per[sym] = {"estimate": float(point[k]), "ci95": [slo, shi]}
    return {"median": float(np.median(point)), "ci95": [lo, hi], "per_symbol": per}


def _excludes_zero(stat: dict) -> int:
    lo, hi = stat["ci95"]
    return 1 if lo > 0 else (-1 if hi < 0 else 0)


def _bootstrap_matrices(panel: dict, periods: list[str], n_boot: int, seed: int) -> tuple:
    """Point and resampled transfer matrices, [S, P, P] and [B, S, P, P] per metric and rung."""
    symbols = list(panel)
    rng = np.random.default_rng(seed)
    n_s, n_p = len(symbols), len(periods)
    point = {m: {r: np.empty((n_s, n_p, n_p)) for r in TRANSFER_RUNGS} for m in METRICS}
    reps = {m: {r: np.empty((n_boot, n_s, n_p, n_p)) for r in TRANSFER_RUNGS} for m in METRICS}
    repeat_point = np.empty((n_s, n_p))
    repeat_reps = np.empty((n_boot, n_s, n_p))
    picks_by_period: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for j, pj in enumerate(periods):
        union = np.unique(np.concatenate(
            [np.asarray(panel[s]["transfer"][pj]["repeat_last"]["day"]) for s in symbols]))
        picks = day_picks(union.size, n_boot, rng)
        picks_by_period[pj] = (union, picks)
        for k, sym in enumerate(symbols):
            tr = panel[sym]["transfer"][pj]
            rl = tr["repeat_last"]
            s, c = aligned_day_sums(rl["day"], rl["correct"], rl["n"], union)
            repeat_point[k, j] = s.sum() / c.sum()
            repeat_reps[:, k, j] = resampled_means(s, c, picks)
            for i, pi in enumerate(periods):
                cell = tr["cells"][pi]
                for metric, (key, _) in METRICS.items():
                    for rung in TRANSFER_RUNGS:
                        s, c = aligned_day_sums(cell["day"], cell[rung][key], cell["n"], union)
                        point[metric][rung][k, i, j] = s.sum() / c.sum()
                        reps[metric][rung][:, k, i, j] = resampled_means(s, c, picks)
    return point, reps, repeat_point, repeat_reps, picks_by_period


def _skill(metric: str, m: np.ndarray, baseline: np.ndarray) -> np.ndarray:
    """Skill over the period's own one-lag baseline: accuracy points, or share of loss removed."""
    return m - baseline if metric == "accuracy" else 1.0 - m / baseline


def _decompose(point: dict, reps: dict, symbols: list[str], periods: list[str], source: str,
               yardstick: str) -> dict:
    s = periods.index(source)
    out: dict = {}
    for metric, (_, hib) in METRICS.items():
        out[metric] = {}
        base_p, base_r = point[metric]["persistence"], reps[metric]["persistence"]
        for rung in TRANSFER_RUNGS:
            mp, mr = point[metric][rung], reps[metric][rung]
            per_target: dict = {}
            gaps: dict[str, tuple[np.ndarray, np.ndarray]] = {}
            for j, pj in enumerate(periods):
                if j == s:
                    continue
                dp = shift_decomposition(mp[:, s, s], mp[:, s, j], mp[:, j, j], hib)
                dr = shift_decomposition(mr[:, :, s, s], mr[:, :, s, j], mr[:, :, j, j], hib)
                entry = {k: _stat(dp[k], dr[k], symbols) for k in dp}
                sk = {
                    "skill_source": (s, s, s), "skill_stale": (s, j, j), "skill_fresh": (j, j, j),
                }
                sp, sr = {}, {}
                for name, (i_, j_, b_) in sk.items():
                    sp[name] = _skill(metric, mp[:, i_, j_], base_p[:, b_, b_])
                    sr[name] = _skill(metric, mr[:, :, i_, j_], base_r[:, :, b_, b_])
                    entry[name] = _stat(sp[name], sr[name], symbols)
                entry["skill_change"] = _stat(sp["skill_fresh"] - sp["skill_source"],
                                              sr["skill_fresh"] - sr["skill_source"], symbols)
                gaps[pj] = (dp["staleness_gap"], dr["staleness_gap"])
                per_target[pj] = entry
            if yardstick in gaps:
                yp, yr = gaps[yardstick]
                for pj, (gp, gr) in gaps.items():
                    if pj == yardstick:
                        continue
                    per_target[pj]["gap_minus_yardstick"] = _stat(gp - yp, gr - yr, symbols)
                    per_target[pj]["n_symbols_gap_above_yardstick"] = int((gp > yp).sum())
            out[metric][rung] = per_target
    return out


# ---------------------------------------------------------------------------
# Covariate shift, attribution, coefficients
# ---------------------------------------------------------------------------


def _covariate_shift(cache: Path, symbols: list[str], periods: list[str]) -> dict:
    auc: dict = {}
    features: dict = {}
    for a, pa in enumerate(periods):
        for pb in periods[a + 1:]:
            files = {s: _read(shift_path(cache, s, pa, pb)) for s in symbols}
            files = {s: f for s, f in files.items() if f is not None}
            if not files:
                continue
            key = f"{pa}__{pb}"
            vals = np.array([f["auc"] for f in files.values()])
            auc[key] = {"median": float(np.median(vals)), "min": float(vals.min()),
                        "max": float(vals.max()), "n_symbols": len(files),
                        "per_symbol": {s: f["auc"] for s, f in files.items()}}
            features[key] = {
                name: {
                    "smd_median": float(np.median([f["features"][name]["smd"]
                                                   for f in files.values()])),
                    "ks_median": float(np.median([f["features"][name]["ks"]
                                                  for f in files.values()])),
                    "domain_gain_median": float(np.median([f["domain_gain"][name]
                                                           for f in files.values()])),
                }
                for name in FEATURE_NAMES
            }
    return {"auc": auc, "features": features}


def _attribution(cache: Path, symbols: list[str], periods: list[str], source: str,
                 picks_by_period: dict) -> dict:
    """Cross-symbol summary of the reweighting split, bootstrapped from cached day sums.

    The covariate part is paired on the source test days (weighted and plain
    loss of the same rows); the concept residual subtracts a source-day
    quantity from a target-day one, so the two blocks resample independently.
    """
    out: dict = {r: {} for r in ATTRIBUTION_RUNGS}
    u_src, picks_src = picks_by_period[source]
    for pj in periods:
        if pj == source:
            continue
        files = {s: _read(shift_path(cache, s, source, pj)) for s in symbols}
        files = {s: f for s, f in files.items() if f is not None and "attribution" in f}
        if not files:
            continue
        syms = list(files)
        u_tgt, picks_tgt = picks_by_period[pj]
        for rung in ATTRIBUTION_RUNGS:
            pts = {k: [] for k in ("total", "covariate", "concept")}
            rps = {k: [] for k in pts}
            ess = {}
            for sym in syms:
                a = files[sym]["attribution"][rung]
                sd, td = a["src_days"], a["tgt_days"]
                l_s, n_s = aligned_day_sums(sd["day"], sd["loss"], sd["n"], u_src)
                wl_s, w_s = aligned_day_sums(sd["day"], sd["w_loss"], sd["w"], u_src)
                l_t, n_t = aligned_day_sums(td["day"], td["loss"], td["n"], u_tgt)
                plain = resampled_means(l_s, n_s, picks_src)
                weighted = resampled_means(wl_s, w_s, picks_src)
                tgt = resampled_means(l_t, n_t, picks_tgt)
                for k, v in (("total", tgt - plain), ("covariate", weighted - plain),
                             ("concept", tgt - weighted)):
                    pts[k].append(a[k])
                    rps[k].append(v)
                ess[sym] = {"ess_share": a["ess_share"], "reliable": a["reliable"]}
            entry = {k: _stat(np.array(pts[k]), np.column_stack(rps[k]), syms) for k in pts}
            cov, con = np.abs(np.array(pts["covariate"])), np.abs(np.array(pts["concept"]))
            entry.update({
                "weights": ess,
                "n_symbols": len(syms),
                "n_reliable": int(sum(e["reliable"] for e in ess.values())),
                "n_symbols_concept_larger": int((con > cov).sum()),
                "ess_share_median": float(np.median([e["ess_share"] for e in ess.values()])),
            })
            out[rung][pj] = entry
    return out


def _coefficients(panel: dict, periods: list[str], source: str) -> dict:
    """Per-period standardized logistic coefficients and which of them moved.

    A coefficient "moved" when the median within-symbol change from the source
    period exceeds the cross-symbol standard deviation of that coefficient
    (the larger of the two periods' spreads): the change is then bigger than
    the disagreement between symbols inside one period.
    """
    symbols = list(panel)
    coef = np.array([[panel[s]["fit"][p]["logit_all_coef"] for p in periods] for s in symbols])
    si = periods.index(source)
    med = np.median(coef, axis=0)                                      # [P, F]
    # With one symbol there is no cross-symbol spread; NaN makes every "moved" test false.
    sd = coef.std(axis=0, ddof=1) if len(symbols) > 1 else np.full_like(med, np.nan)
    order = np.argsort(-np.abs(med[si]))[:TOP_COEFFICIENTS]
    rows = []
    for k in order:
        changes = {}
        for j, pj in enumerate(periods):
            if j == si:
                continue
            delta = float(np.median(coef[:, j, k] - coef[:, si, k]))
            spread = float(max(sd[si, k], sd[j, k]))
            flips = int((np.sign(coef[:, j, k]) != np.sign(coef[:, si, k])).sum())
            changes[pj] = {
                "median_change": delta, "cross_symbol_sd": spread,
                "moved": bool(abs(delta) > spread),
                "sign_changed": bool(med[si, k] * med[j, k] < 0),
                "n_symbols_sign_flipped": flips,
            }
        rows.append({
            "feature": FEATURE_NAMES[k],
            "median_by_period": {p: float(med[j, k]) for j, p in enumerate(periods)},
            "sd_by_period": {p: float(sd[j, k]) for j, p in enumerate(periods)},
            "changes": changes,
        })
    return {"n_symbols": len(symbols), "features": rows}


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


def _pp(x: float) -> str:
    return f"{100 * x:+.2f}"


def _pp_ci(stat: dict) -> str:
    return f"{_pp(stat['median'])} pp [{_pp(stat['ci95'][0])}, {_pp(stat['ci95'][1])}]"


def _bits_ci(stat: dict) -> str:
    return f"{stat['median']:+.4f} bits [{stat['ci95'][0]:+.4f}, {stat['ci95'][1]:+.4f}]"


def _n_positive(stat: dict) -> int:
    return sum(1 for v in stat["per_symbol"].values() if v["ci95"][0] > 0)


def _verdict(dec: dict, attribution: dict, n_symbols: int, source: str, yardstick: str,
             target: str) -> dict:
    acc = dec["accuracy"][PRIMARY_RUNG]
    loss = dec["log_loss_bits"][PRIMARY_RUNG]
    g_y = acc[yardstick]["staleness_gap"]
    y_sign = _excludes_zero(g_y)
    y_text = {0: "is not distinguishable from zero", 1: "is positive",
              -1: "is negative (the older model did better)"}[y_sign]
    parts = [
        (f"One month on ({source} model scored on {yardstick}), the staleness gap of "
        f"{PRIMARY_RUNG} is {_pp_ci(g_y)} of accuracy (median of {n_symbols} symbols, 95% "
        f"day-block interval), which {y_text}. This is the ordinary one-month drift yardstick.")
    ]
    v: dict = {"primary_rung": PRIMARY_RUNG, "n_symbols": n_symbols,
               "yardstick_gap": g_y["median"], "yardstick_gap_sign": y_sign}
    if target == yardstick:
        v["class"] = "yardstick_only"
        parts.append("No later period is in this run, so the multi-year question is not answered.")
        v["text"] = " ".join(parts)
        return v

    t = acc[target]
    g_t, d_t, diff = t["staleness_gap"], t["predictability_change"], t["gap_minus_yardstick"]
    n_above = t["n_symbols_gap_above_yardstick"]
    g_sign, diff_sign, d_sign = _excludes_zero(g_t), _excludes_zero(diff), _excludes_zero(d_t)
    if g_sign > 0 and diff_sign > 0:
        cls = "stale_beyond_yardstick"
        head = (f"Yes. By {target} the {source} model is stale, and its staleness gap is larger "
                f"than the one-month yardstick")
    elif g_sign > 0:
        cls = "stale_within_yardstick"
        head = (f"Partly. By {target} the {source} model has a positive staleness gap, but it is "
                f"not distinguishable from the one-month yardstick")
    elif g_sign < 0:
        cls = "not_stale"
        head = (f"No. On {target} the {source} model does at least as well as a model retrained "
                f"in {target} (negative staleness gap), so there is no staleness to report")
    else:
        cls = "not_stale"
        head = (f"No. On {target} the staleness gap of the {source} model is not distinguishable "
                f"from zero")
    ratio = g_t["median"] / g_y["median"] if g_y["median"] > 1e-4 else None
    ratio_text = (f"{ratio:.1f} times the yardstick" if ratio is not None
                  else "the yardstick gap is too close to zero for a ratio to mean anything")
    parts.append(
        f"{head}: G = {_pp_ci(g_t)} against {_pp(g_y['median'])} pp, a difference of "
        f"{_pp_ci(diff)} ({ratio_text}). The gap is above the yardstick on {n_above} of "
        f"{n_symbols} symbols and its own interval excludes zero from above on "
        f"{_n_positive(g_t)} of {n_symbols}."
    )
    d_text = {0: "shows no detectable change in how predictable the next sign is",
              1: "became more predictable for a freshly trained model",
              -1: "became less predictable even for a freshly trained model"}[d_sign]
    parts.append(
        f"Separately from staleness, the market itself {d_text}: D = {_pp_ci(d_t)}. The raw "
        f"drop of the old model, {_pp(t['raw_drop']['median'])} pp, is G minus D, so "
        f"{'retraining would recover' if g_sign > 0 else 'retraining would not visibly recover'} "
        f"{_pp(g_t['median'])} pp of it. Measured against each period's own one-lag baseline, "
        f"fresh-model skill changed by {_pp_ci(t['skill_change'])}. In log loss the staleness "
        f"gap is {_bits_ci(loss[target]['staleness_gap'])}."
    )
    v.update({"class": cls, "target_gap": g_t["median"], "target_gap_sign": g_sign,
              "gap_minus_yardstick": diff["median"], "gap_minus_yardstick_sign": diff_sign,
              "gap_ratio_to_yardstick": ratio, "n_symbols_gap_above_yardstick": n_above,
              "predictability_change": d_t["median"], "predictability_change_sign": d_sign})

    att = attribution.get(PRIMARY_RUNG, {}).get(target)
    if att is None:
        v["attribution_dominant"] = None
        parts.append("The covariate versus concept attribution was not computed for this run.")
    else:
        cov, con = att["covariate"], att["concept"]
        dominant = "concept" if abs(con["median"]) > abs(cov["median"]) else "covariate"
        n_dom = (att["n_symbols_concept_larger"] if dominant == "concept"
                 else att["n_symbols"] - att["n_symbols_concept_larger"])
        label = {"concept": "the concept residual (the input-to-output relationship changed)",
                 "covariate": "the covariate part (the inputs moved)"}[dominant]
        trust = (
            "The weights are healthy on most symbols."
            if att["n_reliable"] * 2 > att["n_symbols"] else
            "The weights are degenerate on most symbols, so this split is unreliable and should "
            "be read as indicative only."
        )
        parts.append(
            f"Attribution of the {source} model's log loss change to {target} "
            f"({att['total']['median']:+.4f} bits): covariate part {_bits_ci(cov)}, concept "
            f"residual {_bits_ci(con)}. The larger side is {label}, on {n_dom} of "
            f"{att['n_symbols']} symbols. Effective sample size is above the "
            f"{MIN_ESS_SHARE:.0%} threshold on {att['n_reliable']} of {att['n_symbols']} symbols "
            f"(median share {att['ess_share_median']:.0%}). {trust}"
        )
        v.update({"attribution_dominant": dominant, "attribution_n_dominant": n_dom,
                  "attribution_n_reliable": att["n_reliable"]})
    v["text"] = " ".join(parts)
    return v


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build_result(cache: Path, symbols: list[str], periods: list[str], n_boot: int = N_BOOT,
                 seed: int = 0) -> dict:
    """Everything the write-up needs, from caches only."""
    if len(periods) < 2:
        raise ValueError("need at least a source and one target period")
    source, yardstick, target = periods[0], periods[1], periods[-1]
    panel, skipped = _load_panel(cache, symbols, periods)
    if not panel:
        raise RuntimeError(f"no symbol has a complete transfer matrix under {cache}: {skipped}")
    syms = list(panel)
    point, reps, rep_p, rep_r, picks = _bootstrap_matrices(panel, periods, n_boot, seed)
    dec = _decompose(point, reps, syms, periods, source, yardstick)
    attribution = _attribution(cache, syms, periods, source, picks)
    transfer = {
        m: {r: {"median": np.median(point[m][r], axis=0),
                "per_symbol": {s: point[m][r][k] for k, s in enumerate(syms)}}
            for r in TRANSFER_RUNGS}
        for m in METRICS
    }
    tie = {}
    for p in periods:
        vals = np.array([panel[s]["fit"][p]["tie_share"] for s in syms])
        tie[p] = {"median": float(np.median(vals)), "min": float(vals.min()),
                  "max": float(vals.max()),
                  "per_symbol": {s: panel[s]["fit"][p]["tie_share"] for s in syms}}
    return {
        "question": "Does a next-trade-sign model trained in 2023 go stale by 2026, and is the "
                    "loss covariate shift or concept shift?",
        "periods": periods, "source": source, "yardstick": yardstick, "target": target,
        "symbols": syms, "skipped": skipped,
        "params": {"n_boot": n_boot, "seed": seed, "rungs": list(TRANSFER_RUNGS),
                   "min_ess_share": MIN_ESS_SHARE, "weight_clip_quantile": WEIGHT_CLIP_QUANTILE,
                   "fit": {s: {p: {k: panel[s]["fit"][p][k] for k in
                                   ("n_events", "n_train_rows", "n_test_rows", "gbm_all_rounds")}
                               for p in periods} for s in syms}},
        "transfer": transfer,
        "repeat_last_accuracy": {
            p: {"median": float(np.median(rep_p[:, j])),
                "ci95": list(percentile_ci(np.nanmedian(rep_r[:, :, j], axis=1))),
                "per_symbol": {s: float(rep_p[k, j]) for k, s in enumerate(syms)}}
            for j, p in enumerate(periods)},
        "decomposition": dec,
        "covariate_shift": _covariate_shift(cache, syms, periods),
        "attribution": attribution,
        "coefficients": _coefficients(panel, periods, source),
        "tie_share": tie,
        "verdict": _verdict(dec, attribution, len(syms), source, yardstick, target),
    }


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def _matrix_table(periods: list[str], m, fmt) -> list[str]:
    lines = ["| trained on \\ tested on | " + " | ".join(periods) + " |",
             "|---|" + "---|" * len(periods)]
    for i, p in enumerate(periods):
        lines.append(f"| {p} | " + " | ".join(fmt(m[i][j]) for j in range(len(periods))) + " |")
    return lines


def _decomposition_table(dec: dict, metric: str, rung: str, fmt) -> list[str]:
    lines = [("| target | raw drop | staleness gap G (paired) | predictability change D "
             "(independent blocks) | G minus yardstick G | symbols with G above yardstick |"),
             "|---|---|---|---|---|---|"]
    for pj, e in dec[metric][rung].items():
        extra = (f"{fmt(e['gap_minus_yardstick'])} | {e['n_symbols_gap_above_yardstick']}"
                 if "gap_minus_yardstick" in e else "yardstick | n/a")
        lines.append(f"| {pj} | {fmt(e['raw_drop'])} | {fmt(e['staleness_gap'])} | "
                     f"{fmt(e['predictability_change'])} | {extra} |")
    return lines


def write_md(out_dir: Path, r: dict) -> Path:
    periods, source, yardstick, target = r["periods"], r["source"], r["yardstick"], r["target"]
    n = len(r["symbols"])
    dec = r["decomposition"]
    L: list[str] = ["# Q10: does a 2023 sign model go stale, and why", ""]
    L += ["## Question", "",
          (f"Q8 found that a cross-sectional sign-flip law present in June 2023 had faded by July "
          f"2026. Here I ask the same of a predictive model: if the next-trade-sign ladder is "
          f"fitted on {source} and never updated, how much worse is it on later months than a "
          f"ladder refitted in that month, and is the loss because the inputs moved (covariate "
          f"shift) or because the relationship between inputs and the next sign moved (concept "
          f"shift)?"), ""]
    L += ["## Method", "",
          (f"1. **Transfer matrix.** For each symbol and every ordered pair of periods, the "
          f"ladder fitted on the train days of period i is scored on the held-out test block "
          f"(the last days, after a one-day embargo) of period j. The diagonal is therefore a "
          f"genuine out-of-sample number and every cell in a column uses identical test rows. "
          f"Rungs: {', '.join(TRANSFER_RUNGS)}. Events sharing a millisecond with the previous "
          f"event are never scored."),
          (f"2. **Decomposition.** With M the matrix and s = {source}: raw drop = M[s,s] - "
          f"M[s,j]; staleness gap G_j = M[j,j] - M[s,j] (what retraining recovers); "
          f"predictability change D_j = M[j,j] - M[s,s] (the period itself got easier or "
          f"harder). Raw drop = G_j - D_j. For log loss all three are negated so that positive G "
          f"still means retraining helps."),
          (f"3. **Intervals.** 95% percentile intervals from {r['params']['n_boot']} resamples of "
          f"whole UTC test days, one draw of days per period shared by all symbols. G_j is "
          f"**paired**: both terms are means over the same test rows of period j and see the "
          f"same resampled days. D_j and the raw drop are **differences of independent blocks**: "
          f"the days of period j and of {source} are resampled independently. \"G minus "
          f"yardstick G\" is also a difference of independent blocks. Headline numbers are the "
          f"median across the {n} symbols, with the symbol panel held fixed."),
          ("4. **Skill over the period's own baseline.** The accuracy of repeating the last sign "
          "moves between years, so I also report accuracy minus the accuracy of the period's own "
          "persistence rung (the best one-lag rule, fitted on that period's train days)."),
          (f"5. **Yardstick.** {source} to {yardstick} is ordinary one-month drift. Multi-year "
          f"gaps are judged against it."),
          ("6. **Covariate shift size.** A small LightGBM domain classifier is trained to tell "
          "the feature rows of two periods apart (equal-size random samples from each period's "
          "train days) and evaluated on samples from each period's test days. AUC 0.5 means "
          "indistinguishable. Per feature I report the standardized mean difference and the "
          "two-sample KS distance."),
          (f"7. **Attribution.** The classifier's probability gives a density ratio w(x) = "
          f"(n_src/n_tgt) pi/(1-pi), clipped at its {WEIGHT_CLIP_QUANTILE:.0%} quantile. For the "
          f"{source} model's log loss: covariate part = E_src[w loss] - E_src[loss]; concept "
          f"residual = E_tgt[loss] - E_src[w loss]. The split is flagged unreliable when the "
          f"effective sample size of the weights falls below {MIN_ESS_SHARE:.0%} of the rows "
          f"(the reweighted mean then rests on less than one test day's worth of data)."),
          ("8. **Per-period refits.** The logistic rung is refitted in each period on features "
          "standardized within that symbol and period, and the coefficients are compared. I do "
          "not compare SHAP values of the fixed 2023 model across periods: the model function "
          "is unchanged, so such a comparison can only show that inputs moved."), ""]
    L += ["## Run summary", "",
          (f"Periods: {', '.join(periods)}. Symbols with a complete matrix: {n} "
          f"({', '.join(r['symbols'])}).")]
    if r["skipped"]:
        L += ["", "Skipped:", ""] + [f"- {s['symbol']}: {s['reason']}" for s in r["skipped"]]
    L += ["", "## Results", "",
          f"### Transfer matrix, {PRIMARY_RUNG} accuracy (median across symbols)", ""]
    L += _matrix_table(periods, r["transfer"]["accuracy"][PRIMARY_RUNG]["median"],
                       lambda v: f"{100 * v:.2f}%")
    L += ["", f"### Transfer matrix, {PRIMARY_RUNG} log loss in bits (median across symbols)", ""]
    L += _matrix_table(periods, r["transfer"]["log_loss_bits"][PRIMARY_RUNG]["median"],
                       lambda v: f"{v:.4f}")
    for rung in ("gbm_all", "logit_all", "linear"):
        L += ["", f"### Decomposition, {rung} accuracy (percentage points)", ""]
        L += _decomposition_table(dec, "accuracy", rung, _pp_ci)
    L += ["", f"### Decomposition, {PRIMARY_RUNG} log loss", ""]
    L += _decomposition_table(dec, "log_loss_bits", PRIMARY_RUNG, _bits_ci)

    L += ["", ("### Skill over each period's own one-lag baseline (accuracy points, "
          f"{PRIMARY_RUNG})"), "",
          ("| target | repeat-last accuracy in target | stale model skill | fresh model skill | "
          f"fresh skill in {source} | change in fresh skill |"), "|---|---|---|---|---|---|"]
    for pj, e in dec["accuracy"][PRIMARY_RUNG].items():
        rl = r["repeat_last_accuracy"][pj]["median"]
        L.append(f"| {pj} | {100 * rl:.2f}% | {_pp_ci(e['skill_stale'])} | "
                 f"{_pp_ci(e['skill_fresh'])} | {_pp(e['skill_source']['median'])} pp | "
                 f"{_pp_ci(e['skill_change'])} |")
    L += ["", (f"Repeat-last accuracy in {source}: "
          f"{100 * r['repeat_last_accuracy'][source]['median']:.2f}%.")]

    L += ["", f"### Staleness gap by symbol, {PRIMARY_RUNG} accuracy (percentage points)", "",
          "| symbol | " + " | ".join(dec["accuracy"][PRIMARY_RUNG]) + " |",
          "|---|" + "---|" * len(dec["accuracy"][PRIMARY_RUNG])]
    for s in r["symbols"]:
        cells = []
        for e in dec["accuracy"][PRIMARY_RUNG].values():
            ps = e["staleness_gap"]["per_symbol"][s]
            cells.append(f"{_pp(ps['estimate'])} [{_pp(ps['ci95'][0])}, {_pp(ps['ci95'][1])}]")
        L.append(f"| {s} | " + " | ".join(cells) + " |")

    cs = r["covariate_shift"]
    if cs["auc"]:
        L += ["", "### Covariate shift: domain classifier AUC (0.5 = indistinguishable)", "",
              "| pair | median AUC | min | max | symbols |", "|---|---|---|---|---|"]
        for key, a in cs["auc"].items():
            L.append(f"| {key.replace('__', ' vs ')} | {a['median']:.3f} | {a['min']:.3f} | "
                     f"{a['max']:.3f} | {a['n_symbols']} |")
        key = f"{source}__{target}"
        if key in cs["features"]:
            top = sorted(cs["features"][key].items(), key=lambda kv: -kv[1]["ks_median"])
            L += ["", (f"Features that moved most between {source} and {target} (median across "
                  f"symbols, ranked by KS distance):"), "",
                  ("| feature | KS distance | standardized mean difference | "
                  "KS in the yardstick pair |"), "|---|---|---|---|"]
            yk = cs["features"].get(f"{source}__{yardstick}", {})
            for name, f in top[:TOP_SHIFTED_FEATURES]:
                y = f"{yk[name]['ks_median']:.3f}" if name in yk else "n/a"
                L.append(f"| {name} | {f['ks_median']:.3f} | {f['smd_median']:+.3f} | {y} |")
    for rung in ATTRIBUTION_RUNGS:
        if not r["attribution"].get(rung):
            continue
        L += ["", f"### Attribution of the {source} {rung} log loss change (bits)", "",
              ("| target | total change | covariate part (paired on source days) | concept "
              "residual (independent blocks) | symbols where concept is larger | median ESS "
              "share | symbols with reliable weights |"), "|---|---|---|---|---|---|---|"]
        for pj, a in r["attribution"][rung].items():
            L.append(f"| {pj} | {a['total']['median']:+.4f} | {_bits_ci(a['covariate'])} | "
                     f"{_bits_ci(a['concept'])} | {a['n_symbols_concept_larger']} of "
                     f"{a['n_symbols']} | {a['ess_share_median']:.0%} | {a['n_reliable']} of "
                     f"{a['n_symbols']} |")

    co = r["coefficients"]
    L += ["", ("### Per-period logistic refits: standardized coefficients (median across "
          "symbols)"), "", "| feature | " + " | ".join(periods) + f" | verdict for {target} |",
          "|---|" + "---|" * (len(periods) + 1)]
    moved, flipped = [], []
    for row in co["features"]:
        ch = row["changes"][target]
        tag = []
        if ch["sign_changed"]:
            tag.append(f"sign changed ({ch['n_symbols_sign_flipped']} of {co['n_symbols']} "
                       f"symbols)")
            flipped.append(row["feature"])
        if ch["moved"]:
            tag.append(f"moved {ch['median_change']:+.3f}, more than the cross-symbol SD "
                       f"{ch['cross_symbol_sd']:.3f}")
            moved.append(row["feature"])
        L.append(f"| {row['feature']} | "
                 + " | ".join(f"{row['median_by_period'][p]:+.3f}" for p in periods)
                 + f" | {'; '.join(tag) if tag else 'within the cross-symbol spread'} |")
    y_moved = [row["feature"] for row in co["features"]
               if yardstick != target and row["changes"][yardstick]["moved"]]
    L += ["", f"Of the {len(co['features'])} largest coefficients in {source}, "
          f"{len(flipped)} changed sign by {target}"
          f"{' (' + ', '.join(flipped) + ')' if flipped else ''} and {len(moved)} moved by more "
          f"than the cross-symbol spread{' (' + ', '.join(moved) + ')' if moved else ''}. "
          + (f"Over the one-month yardstick {len(y_moved)} moved by that much."
             if yardstick != target else "")]

    L += ["", "### Share of events tied with the previous millisecond", "",
          "| period | median | min | max |", "|---|---|---|---|"]
    for p, t in r["tie_share"].items():
        L.append(f"| {p} | {t['median']:.1%} | {t['min']:.1%} | {t['max']:.1%} |")

    L += ["", "## Verdict", "", r["verdict"]["text"], "", "## Caveats", "",
          ("- **Snapshots, not a path.** Five snapshot months cannot distinguish gradual from "
          "abrupt change between them, cannot give a retraining cadence finer than a year, and "
          "cannot detect regimes that came and went between snapshots."),
          (f"- **Survivors.** The {n} symbols are ones present in all the months studied. Symbols "
          "delisted or listed in between are absent, so this is drift within a surviving panel, "
          "not drift of the market's composition."),
          ("- **Timestamp resolution.** The raw dumps changed timestamp resolution across years. "
          "The ingest normalizes everything to milliseconds, but the share of events tied with "
          "the previous millisecond (table above) differs by period. Tied events are excluded "
          "from scoring, so a different tie share means a different scored population, and the "
          "`same_ts` feature moves with it."),
          ("- **Few day blocks.** Each test block is about a week, so the day-block intervals "
          "rest on seven or eight resampling units and are approximate. They hold the symbol "
          "panel fixed and say nothing about other symbols."),
          (f"- **One source month.** {source} followed regulatory actions against the exchange "
          "and may itself be an unusual regime; '2023 versus later' is not 'normal versus "
          "changed'."),
          ("- **Attribution limits.** The reweighting only speaks for inputs the source period "
          "covers, clipping the weights biases the covariate part toward zero, and 'concept' is "
          "relative to this feature set: a change in an omitted variable (tick size in basis "
          "points, participant mix) lands in the residual. In a sequence model the features are "
          "past signs, so a change in the sign dynamics also moves the feature distribution; "
          "the two kinds of shift are not independent causes."),
          ("- **Coefficients.** The sign-history features are strongly collinear, so single "
          "coefficients can trade off against each other without the fitted function changing "
          "much. The coefficient table is a description, not a test."),
          ("- **No trading claim.** Accuracy on the next aggressor sign is not profitability; no "
          "fees or execution are modelled."), ""]
    path = out_dir / f"{STEM}.md"
    path.write_text("\n".join(L))
    return path


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------

_BLUE, _ORANGE, _INK, _MUTED = "#2a78d6", "#eb6834", "#1a1a19", "#6b6a63"
_SEQ = LinearSegmentedColormap.from_list("q10_blue", ["#eef4fd", "#86b6ef", "#256abf", "#0d366b"])


def plot(out_dir: Path, r: dict) -> Path:
    periods = r["periods"]
    m = 100 * np.asarray(r["transfer"]["accuracy"][PRIMARY_RUNG]["median"])
    fig, (ax_m, ax_d) = plt.subplots(1, 2, figsize=(13.5, 5.2), gridspec_kw={"wspace": 0.28})

    im = ax_m.imshow(m, cmap=_SEQ, aspect="auto")
    mid = 0.5 * (m.min() + m.max())
    for i in range(len(periods)):
        for j in range(len(periods)):
            ax_m.text(j, i, f"{m[i, j]:.1f}", ha="center", va="center", fontsize=10,
                      color="white" if m[i, j] > mid else _INK)
    ax_m.set_xticks(range(len(periods)), periods)
    ax_m.set_yticks(range(len(periods)), periods)
    ax_m.set_xlabel("tested on (held-out last days of the month)")
    ax_m.set_ylabel("trained on")
    ax_m.set_title(f"{PRIMARY_RUNG} accuracy, %, median of {len(r['symbols'])} symbols",
                   loc="left", fontsize=11)
    fig.colorbar(im, ax=ax_m, fraction=0.046, pad=0.03).outline.set_visible(False)

    dec = r["decomposition"]["accuracy"][PRIMARY_RUNG]
    targets = list(dec)
    x = np.arange(len(targets))
    for key, label, color, dx, marker in (
        ("staleness_gap", "staleness gap G (retraining recovers this)", _BLUE, -0.1, "o"),
        ("predictability_change", ("predictability change D (fresh model, later vs "
                                  f"{r['source']})"), _ORANGE, 0.1, "s"),
    ):
        y = np.array([100 * dec[t][key]["median"] for t in targets])
        lo = np.array([100 * dec[t][key]["ci95"][0] for t in targets])
        hi = np.array([100 * dec[t][key]["ci95"][1] for t in targets])
        ax_d.errorbar(x + dx, y, yerr=[y - lo, hi - y], fmt=marker, color=color, markersize=7,
                      linewidth=2, capsize=3, label=label)
    ax_d.axhline(0, color=_MUTED, linewidth=1)
    ax_d.set_xticks(x, targets)
    ax_d.set_xlim(-0.5, len(targets) - 0.5)
    ax_d.set_xlabel(f"target period ({r['yardstick']} is the one-month yardstick)")
    ax_d.set_ylabel("accuracy points")
    ax_d.set_title(f"{r['source']} model: stale, or a harder market? (95% intervals)",
                   loc="left", fontsize=11)
    ax_d.grid(axis="y", color="#e4e3dd", linewidth=0.8)
    ax_d.set_axisbelow(True)
    for side in ("top", "right"):
        ax_d.spines[side].set_visible(False)
    # Below the axes: inside, the legend would sit on top of points near zero.
    ax_d.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.16))
    path = out_dir / f"{STEM}.png"
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return path


def write_report(cache: Path, out_dir: Path, symbols: list[str], periods: list[str],
                 n_boot: int = N_BOOT, seed: int = 0) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = build_result(cache, symbols, periods, n_boot=n_boot, seed=seed)
    (out_dir / f"{STEM}.json").write_text(dumps_strict(result))
    write_md(out_dir, result)
    plot(out_dir, result)
    return result
