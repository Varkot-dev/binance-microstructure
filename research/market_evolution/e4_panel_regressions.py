"""E4: what explains the rise in trade-sign predictability? (Part A, weeks 3 to 4)

Two analyses on the contract-month data already built in weeks 0 to 1:

1. Composition split. The change in the cross-sectional mean (and median) of fresh-model
   accuracy (Q14 `gbm_all`) from the 2023-06 to the 2026-07 cross-section is split into
   exits (contracts present in 2023-06 only), within-contract change (contracts present
   in both) and entries (new listings, 2026-07 only), with the chain
   all_2023 -> survivors_2023 -> survivors_2026 -> all_2026. For the mean this is the
   decomposition in notes/panel_and_causal_methods.md section 6, term for term; for the
   median it is the same chain of counterfactual medians. Intervals: 2000 bootstrap
   resamples of contracts, stratified by group (survivor pairs, exits, entries). Noise
   floor: the same 10 coins from 2023-06 to 2023-07.
2. Regressions of accuracy on six drivers (log median trade size, log relative tick,
   share of trades under $1k, sweep share, minute-open ratio, log events per day):
   pooled OLS, contract fixed effects, two-way fixed effects, the 10-coin 5-month panel
   with a wild cluster bootstrap, and a 2026 dummy with contract fixed effects whose
   fall when the drivers are added is split per driver by the Gelbach (2016)
   decomposition. Long same-sign runs (near-mechanical) enter only a separately
   labelled model.

Software: numpy and scipy only. pyfixest, linearmodels, statsmodels and pandas are not
installed in this environment (checked with import), and nothing was installed, so the
estimators are written out here: within (demeaning) transformation for contract fixed
effects, CRV1 standard errors clustered by contract with the small-sample factor
G/(G-1) x (N-1)/(N-K) (K counts slope coefficients; contract effects are nested in the
clusters, as in fixest's default), t(G-1) intervals, a restricted wild cluster
bootstrap with Rademacher weights (all 2^G sign vectors enumerated when G <= 12) and
CIs by test inversion, and the Gelbach decomposition with intervals from resampling
contracts. The two pyfixest dtype bugs in the methods note do not arise. The
estimators are checked against dummy-variable regressions in
tests/research/test_e4_panel.py.

    PYTHONPATH=src .venv/bin/python research/market_evolution/e4_panel_regressions.py
"""
from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import polars as pl
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CROSS = HERE / "data" / "proxies_cross_section.parquet"
TEN = HERE / "e1_proxies.json"
Q14 = ROOT / "results" / "q14_survivorship.json"
OUT_MD = HERE / "data" / "e4_panel_regressions.md"
OUT_PNG = HERE / "data" / "e4_panel_regressions.png"

T0, T1 = "2023-06", "2026-07"
TEN_MONTHS = ["2023-06", "2023-07", "2024-07", "2025-07", "2026-07"]
N_BOOT = 2000
SEED = 0

# (column, label, unit of one coefficient step)
DRIVERS = [
    ("log_size", "log median trade size", "per +1 log point"),
    ("log_rel_tick", "log relative tick", "per +1 log point"),
    ("u1k_10pp", "share of trades under $1k", "per +10 pp"),
    ("sweep_pp", "sweep share", "per +1 pp"),
    ("minute_open", "minute-open ratio", "per +1"),
    ("log_epd", "log events per day", "per +1 log point"),
]
MECH = ("long_runs_pp", "long same-sign runs (MECHANICAL)", "per +1 pp")
GROUPS = {
    "trade size (log size + under $1k)": ["log_size", "u1k_10pp"],
    "relative tick": ["log_rel_tick"],
    "sweeps": ["sweep_pp"],
    "minute-open bunching": ["minute_open"],
    "activity": ["log_epd"],
}


# ----------------------------------------------------------------------------- data


def add_drivers(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        (pl.col("median_notional_usd").log()).alias("log_size"),
        (pl.col("rel_tick_bps").log()).alias("log_rel_tick"),
        (pl.col("share_under_1k_usd") * 10).alias("u1k_10pp"),
        (pl.col("sweep_share") * 100).alias("sweep_pp"),
        pl.col("minute_open_ratio").alias("minute_open"),
        (pl.col("events_per_day").log()).alias("log_epd"),
        (pl.col("run_share_ge10_sweeps_merged") * 100).alias("long_runs_pp"),
    )


def load_cross() -> pl.DataFrame:
    d = pl.read_parquet(CROSS).filter(pl.col("status") == "ok")
    d = d.rename({"period": "month"}).with_columns(
        (pl.col("q14_gbm_all") * 100).alias("acc"),
        (pl.col("q14_lift") * 100).alias("lift"),
    )
    return add_drivers(d)


def load_ten() -> pl.DataFrame:
    rows = json.loads(TEN.read_text())["rows"]
    d = pl.DataFrame(rows).with_columns((pl.col("acc_gbm_all") * 100).alias("acc"))
    return add_drivers(d)


# ----------------------------------------------------------------- composition split


def composition_split(ids0, y0, ids1, y1, stat=np.mean) -> dict:
    """Chain all_0 -> survivors_0 -> survivors_1 -> all_1; the three steps sum to the total.

    exit = stat(S at 0) - stat(all at 0); within = stat(S at 1) - stat(S at 0);
    entry = stat(all at 1) - stat(S at 1). For the mean, exit equals
    -share_exit_0 * (mean_exit_0 - mean_S_0) and entry equals
    share_entry_1 * (mean_entry_1 - mean_S_1), the methods-note formula.
    """
    ids0, ids1 = np.asarray(ids0), np.asarray(ids1)
    y0, y1 = np.asarray(y0, float), np.asarray(y1, float)
    s0 = np.isin(ids0, ids1)
    s1 = np.isin(ids1, ids0)
    a0, b0, b1, a1 = stat(y0), stat(y0[s0]), stat(y1[s1]), stat(y1)
    return {
        "level_0": a0, "level_1": a1, "total": a1 - a0,
        "exit": b0 - a0, "within": b1 - b0, "entry": a1 - b1,
        "n_survivors": int(s0.sum()), "n_exit": int((~s0).sum()), "n_entry": int((~s1).sum()),
    }


def bootstrap_composition(ids0, y0, ids1, y1, stat, n_boot=N_BOOT, seed=SEED) -> dict:
    """Resample contracts within each group (survivors as pairs, exits, entries)."""
    rng = np.random.default_rng(seed)
    ids0, ids1 = np.asarray(ids0), np.asarray(ids1)
    y0, y1 = np.asarray(y0, float), np.asarray(y1, float)
    m1 = dict(zip(ids1.tolist(), y1.tolist(), strict=True))
    surv = [i for i in ids0.tolist() if i in m1]
    m0 = dict(zip(ids0.tolist(), y0.tolist(), strict=True))
    ys0 = np.array([m0[i] for i in surv])
    ys1 = np.array([m1[i] for i in surv])
    yx = y0[~np.isin(ids0, ids1)]
    ye = y1[~np.isin(ids1, ids0)]
    keys = ["total", "exit", "within", "entry"]
    out = {k: [] for k in keys}
    for _ in range(n_boot):
        si = rng.integers(0, len(surv), len(surv))
        xi = rng.integers(0, len(yx), len(yx))
        ei = rng.integers(0, len(ye), len(ye))
        # fresh ids so a contract drawn twice counts twice
        n_s, n_x, n_e = len(si), len(xi), len(ei)
        i0 = np.r_[np.arange(n_s), n_s + np.arange(n_x)]
        i1 = np.r_[np.arange(n_s), n_s + n_x + np.arange(n_e)]
        r = composition_split(i0, np.r_[ys0[si], yx[xi]], i1, np.r_[ys1[si], ye[ei]], stat)
        for k in keys:
            out[k].append(r[k])
    return {k: np.percentile(v, [2.5, 97.5]) for k, v in out.items()}


# ------------------------------------------------------------------------ estimation


def demean(groups, a):
    """Subtract group means (contract fixed effects by the within transformation)."""
    groups = np.asarray(groups)
    a = np.asarray(a, float)
    _, inv, cnt = np.unique(groups, return_inverse=True, return_counts=True)
    if a.ndim == 1:
        return a - np.bincount(inv, a)[inv] / cnt[inv]
    sums = np.zeros((cnt.size, a.shape[1]))
    np.add.at(sums, inv, a)
    return a - sums[inv] / cnt[inv][:, None]


def prepare(y, X, cluster, fe=None, add_const=False):
    """Drop singleton FE groups, apply the within transformation, check rank."""
    y = np.asarray(y, float)
    X = np.asarray(X, float).reshape(len(y), -1)
    cluster = np.asarray(cluster)
    if fe is not None:
        fe = np.asarray(fe)
        _, inv, cnt = np.unique(fe, return_inverse=True, return_counts=True)
        keep = cnt[inv] > 1
        y, X, cluster, fe = y[keep], X[keep], cluster[keep], fe[keep]
        y, X = demean(fe, y), demean(fe, X)
    if add_const:
        X = np.column_stack([np.ones(len(y)), X])
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise ValueError("regressors are collinear (for example a driver that only moves "
                         "with the month effects)")
    return y, X, cluster


def _crv1(X, u, cluster, xtx_inv):
    n, k = X.shape
    g_ids, inv = np.unique(cluster, return_inverse=True)
    G = g_ids.size
    scores = np.zeros((G, k))
    np.add.at(scores, inv, X * u[:, None])
    meat = scores.T @ scores
    adj = G / (G - 1) * (n - 1) / (n - k)
    return adj * xtx_inv @ meat @ xtx_inv, G


def ols(y, X, cluster):
    """OLS on already-transformed data with CRV1 errors and t(G-1) intervals."""
    xtx_inv = np.linalg.inv(X.T @ X)
    b = xtx_inv @ X.T @ y
    u = y - X @ b
    V, G = _crv1(X, u, cluster, xtx_inv)
    se = np.sqrt(np.diag(V))
    tc = stats.t.ppf(0.975, G - 1)
    t = b / se
    return {
        "b": b, "se": se, "lo": b - tc * se, "hi": b + tc * se,
        "p": 2 * stats.t.sf(np.abs(t), G - 1), "n": len(y), "G": G,
        "r2_within": 1 - (u @ u) / ((y - y.mean()) @ (y - y.mean())),
    }


def fit(y, X, cluster, fe=None, add_const=False):
    yt, Xt, cl = prepare(y, X, cluster, fe, add_const)
    r = ols(yt, Xt, cl)
    r["data"] = (yt, Xt, cl)
    return r


def _sign_draws(G, reps, rng):
    if G <= 12:
        return np.array(list(itertools.product([-1.0, 1.0], repeat=G)))
    return rng.choice([-1.0, 1.0], size=(reps, G))


def wild_p(yt, Xt, cl, j, null=0.0, reps=9999, seed=SEED, W=None):
    """Restricted wild cluster bootstrap (Rademacher) p-value for H0: b_j = null."""
    rng = np.random.default_rng(seed)
    g_ids, inv = np.unique(cl, return_inverse=True)
    G = g_ids.size
    if W is None:
        W = _sign_draws(G, reps, rng)
    n, k = Xt.shape
    xtx_inv = np.linalg.inv(Xt.T @ Xt)
    full = ols(yt, Xt, cl)
    t_obs = (full["b"][j] - null) / full["se"][j]
    yr = yt - null * Xt[:, j]
    Xr = np.delete(Xt, j, axis=1)
    br = np.linalg.lstsq(Xr, yr, rcond=None)[0] if Xr.shape[1] else np.zeros(0)
    fitted = Xr @ br + null * Xt[:, j]
    ur = yt - fitted
    Ystar = fitted[:, None] + ur[:, None] * W[:, inv].T          # n x B
    P = xtx_inv @ Xt.T                                          # k x n
    Bstar = P @ Ystar                                           # k x B
    U = Ystar - Xt @ Bstar
    c = P[j]                                                    # influence of row i on b_j
    S = np.zeros((G, U.shape[1]))
    np.add.at(S, inv, c[:, None] * U)
    adj = G / (G - 1) * (n - 1) / (n - k)
    se_star = np.sqrt(adj * (S ** 2).sum(axis=0))
    t_star = (Bstar[j] - null) / se_star
    return float(np.mean(np.abs(t_star) >= abs(t_obs) - 1e-12))


def wild_ci(yt, Xt, cl, j, reps=9999, seed=SEED, n_grid=161):
    """95% CI by inverting the restricted wild bootstrap test over a grid."""
    full = ols(yt, Xt, cl)
    b, se = full["b"][j], full["se"][j]
    rng = np.random.default_rng(seed)
    W = _sign_draws(np.unique(cl).size, reps, rng)
    grid = np.linspace(b - 6 * se, b + 6 * se, n_grid)
    ps = np.array([wild_p(yt, Xt, cl, j, null=g, W=W) for g in grid])
    ok = grid[ps > 0.05]
    return (float(ok.min()), float(ok.max())) if ok.size else (math.nan, math.nan)


def cluster_blocks(cl):
    _, inv = np.unique(cl, return_inverse=True)
    return [np.flatnonzero(inv == g) for g in range(inv.max() + 1)]


def pairs_boot(yt, Xt, cl, fn, n_boot=N_BOOT, seed=SEED):
    """Resample whole contracts from already-demeaned data (each draw is a new contract)."""
    rng = np.random.default_rng(seed)
    blocks = cluster_blocks(cl)
    out = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(blocks), len(blocks))
        idx = np.concatenate([blocks[p] for p in pick])
        try:
            out.append(fn(yt[idx], Xt[idx]))
        except np.linalg.LinAlgError:
            continue
    return np.array(out)


def gelbach(y, X1, X2):
    """Gelbach (2016): b1_short - b1_long = sum_k Gamma[:, k] * b2[k] (exact).

    y, X1 (variables of interest) and X2 (added drivers) are already transformed
    (contract-demeaned). Returns the short and long coefficients on X1 and the
    contribution of each X2 column to the fall, one row per X1 column.
    """
    X1 = np.asarray(X1, float).reshape(len(y), -1)
    X2 = np.asarray(X2, float).reshape(len(y), -1)
    b_short = np.linalg.lstsq(X1, y, rcond=None)[0]
    Xl = np.column_stack([X1, X2])
    b_long = np.linalg.lstsq(Xl, y, rcond=None)[0]
    b2 = b_long[X1.shape[1]:]
    gamma = np.linalg.lstsq(X1, X2, rcond=None)[0]                # k1 x k2
    delta = gamma * b2[None, :]
    return {"short": b_short, "long": b_long[: X1.shape[1]], "delta": delta, "b2": b2}


# ---------------------------------------------------------------------- formatting


def f(x, d=2, sign=True):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:+.{d}f}" if sign else f"{x:.{d}f}"


def ci(lo, hi, d=2):
    return f"{f(lo, d)} to {f(hi, d)}"


def pfmt(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


# ------------------------------------------------------------------------- analysis


def run():
    cross = load_cross()
    ten = load_ten()
    q14 = json.loads(Q14.read_text())
    md = []

    # sanity: the 10 coins' 2023-06 and 2026-07 rows are the same numbers in both files
    chk = ten.filter(pl.col("month").is_in([T0, T1])).join(
        cross.select("symbol", "month", pl.col("acc").alias("acc_x"),
                     pl.col("log_size").alias("ls_x")),
        on=["symbol", "month"])
    assert chk.height == 20
    assert np.allclose(chk["acc"], chk["acc_x"]) and np.allclose(chk["log_size"], chk["ls_x"])

    c0 = cross.filter(pl.col("month") == T0)
    c1 = cross.filter(pl.col("month") == T1)
    # survivors whose 2023-06 month was incomplete (not fitted in 2023) are neither
    # survivors nor new listings; left out of the split
    odd = c1.filter((pl.col("q14_status") != "new_listing")
                    & ~pl.col("symbol").is_in(c0["symbol"].to_list()))["symbol"].to_list()
    c1s = c1.filter(~pl.col("symbol").is_in(odd))

    # ------------------------------------------------------------ 1. composition
    comp = {}
    for yname in ["acc", "lift"]:
        for sname, stat in [("mean", np.mean), ("median", np.median)]:
            r = composition_split(c0["symbol"], c0[yname], c1s["symbol"], c1s[yname], stat)
            b = bootstrap_composition(c0["symbol"], c0[yname], c1s["symbol"], c1s[yname],
                                      stat, seed=SEED + (yname == "lift"))
            comp[(yname, sname)] = (r, b)
    # renamed contracts linked to a successor in the 2026 sample (same economic unit)
    links = {s: t for s, t in zip(c0["symbol"], c0["lifecycle_successor"], strict=True)
             if t is not None and t in set(c1s["symbol"]) and t not in set(c0["symbol"])}
    ids1_linked = [next((k for k, v in links.items() if v == s), s) for s in c1s["symbol"]]
    r_link = composition_split(c0["symbol"], c0["acc"], ids1_linked, c1s["acc"], np.mean)
    # entries reweighted to their share of the 2026 population (the sample is 15 per
    # zip-size decile of 499 new listings, 113 of 150 fitted, the rest stock/ETF tokens)
    nl = q14["universe"]["new_listings"]
    n_e_sample = comp[("acc", "mean")][0]["n_entry"]
    n_s = comp[("acc", "mean")][0]["n_survivors"]
    n_e_pop = nl["n_frame"] * n_e_sample / len(nl["sample"])
    share_pop = n_e_pop / (n_e_pop + n_s)
    rm = comp[("acc", "mean")][0]
    ye = c1s.filter(~pl.col("symbol").is_in(c0["symbol"].to_list()))["acc"].to_numpy()
    ys1 = c1s.filter(pl.col("symbol").is_in(c0["symbol"].to_list()))["acc"].to_numpy()
    entry_pop = share_pop * (ye.mean() - ys1.mean())

    # noise floor: 10 coins, 2023-06 -> 2023-07, and the same coins to 2026-07
    tw = ten.pivot(on="month", index="symbol", values="acc")
    d_floor = (tw["2023-07"] - tw["2023-06"]).to_numpy()
    d_ten = (tw["2026-07"] - tw["2023-06"]).to_numpy()
    rng = np.random.default_rng(SEED)
    bi = rng.integers(0, 10, (N_BOOT, 10))
    floor_ci = np.percentile(d_floor[bi].mean(1), [2.5, 97.5])
    ten_ci = np.percentile(d_ten[bi].mean(1), [2.5, 97.5])
    sd_floor = d_floor.std(ddof=1)
    surv_d = (c1s.join(c0.select("symbol", pl.col("acc").alias("a0")), on="symbol")
              .with_columns((pl.col("acc") - pl.col("a0")).alias("d")))["d"].to_numpy()

    md += [
        "# E4: panel regressions and the composition split (Part A, weeks 3 to 4)",
        "",
        ("Script: `../e4_panel_regressions.py` (tests: `tests/research/test_e4_panel.py`). "
        "Figure: `e4_panel_regressions.png`. Inputs: `proxies_cross_section.parquet` "
        "(Q14 cross-sections, 181 contracts in 2023-06 and 251 in 2026-07) and "
        "`../e1_proxies.json` (the 10 Q10 coins x 5 months). Outcome: fresh-model "
        "accuracy (`gbm_all`, fitted within each contract-month, Q9 protocol), in "
        "percent; robustness outcome: lift over the majority-class rule (Q14 `lift`, "
        "cross-sections only, because Q10 did not store the majority rule for "
        "2023-07 to 2025-07). The 10 coins' 2023-06 and 2026-07 rows are identical in "
        "both files (checked in the script), so the panels can be stacked."),
        "",
        ("**Software.** pyfixest, linearmodels, statsmodels and pandas are not installed "
        "(checked with `import`; nothing was installed). The estimators are written in "
        "numpy and scipy: contract fixed effects by demeaning, CRV1 errors clustered by "
        "contract (factor G/(G-1) x (N-1)/(N-K), K = slope coefficients), t(G-1) "
        "intervals, a restricted wild cluster bootstrap (Rademacher, all 1,024 sign "
        "vectors for 10 coins, CI by test inversion), percentile intervals from "
        f"{N_BOOT} resamples of whole contracts, and the Gelbach decomposition written "
        "out (pyfixest `decompose` computes the same quantity). The tests check them "
        "against dummy-variable regressions. The pyfixest dtype bugs do not arise."),
        "",
        "## 1. Composition split, 2023-06 to 2026-07",
        "",
        (f"Groups: {rm['n_survivors']} contracts in both months, {rm['n_exit']} exits "
        f"(delisted, renamed or merged before 2026-07), {rm['n_entry']} entries (new "
        f"listings in the 2026-07 sample). {len(odd)} survivors fitted only in 2026-07 "
        f"({', '.join(odd)}: their 2023-06 month was incomplete) are left out. "
        "Chain: all 2023 -> survivors 2023 (exit term) -> survivors 2026 (within term) -> "
        "all 2026 (entry term); the terms sum exactly to the total. For the mean this "
        "is the methods-note formula term for term. Accuracy in percentage points (pp), "
        f"95% intervals from {N_BOOT} resamples of contracts within each group."),
        "",
        "| outcome, statistic | 2023-06 | 2026-07 | total change | exits | within | entries |",
        "|---|---|---|---|---|---|---|",
    ]
    for (yname, sname), (r, b) in comp.items():
        lab = {"acc": "accuracy", "lift": "lift over majority"}[yname]
        cells = [f"{f(r[k])} ({ci(*b[k])})" for k in ["total", "exit", "within", "entry"]]
        md.append(f"| {lab}, {sname} | {r['level_0']:.2f} | {r['level_1']:.2f} | "
                  + " | ".join(cells) + " |")
    rmed = comp[("acc", "median")][0]
    md += [
        "",
        ("Shares of the change in mean accuracy: within "
        f"{100 * rm['within'] / rm['total']:.0f}%, exits {100 * rm['exit'] / rm['total']:.0f}%, "
        f"entries {100 * rm['entry'] / rm['total']:.0f}% (median: within "
        f"{100 * rmed['within'] / rmed['total']:.0f}%, exits "
        f"{100 * rmed['exit'] / rmed['total']:.0f}%, entries "
        f"{100 * rmed['entry'] / rmed['total']:.0f}%)."),
        "",
        "Checks on the split:",
        (f"- **Noise floor.** On the 10 coins, 2023-06 to 2023-07 moves mean accuracy by "
        f"{f(d_floor.mean())} pp ({ci(*floor_ci)}), with a coin-level standard "
        f"deviation of {sd_floor:.2f} pp. The same coins from 2023-06 to 2026-07: "
        f"{f(d_ten.mean())} pp ({ci(*ten_ci)}). If a one-month change of that spread were "
        f"pure noise, the mean of {rm['n_survivors']} survivor changes would carry a "
        f"noise of about {sd_floor / math.sqrt(rm['n_survivors']):.2f} pp, small against "
        f"the within term of {f(rm['within'])} pp. {int((surv_d > 0).sum())} of "
        f"{surv_d.size} survivors rose."),
        (f"- **Renames linked.** Linking the {len(links)} renamed contracts whose successor "
        f"is in the 2026 sample ({', '.join(f'{k} to {v}' for k, v in links.items())}) as "
        f"one unit: within {f(r_link['within'])}, exits {f(r_link['exit'])}, entries "
        f"{f(r_link['entry'])} (mean, pp). Essentially unchanged."),
        (f"- **Entries at their population share.** The 2026 sample holds {n_e_sample} "
        f"entries next to {n_s} survivors ({100 * n_e_sample / (n_e_sample + n_s):.0f}% "
        f"entries), but the 2026-07 population has about {n_e_pop:.0f} crypto new "
        f"listings ({nl['n_frame']} in the frame x {n_e_sample}/{len(nl['sample'])} "
        f"fitted), so about {100 * share_pop:.0f}%. With that weight the entry term "
        f"would be {f(entry_pop)} pp instead of {f(rm['entry'])} pp. The sample is "
        "stratified by zip-size decile, so the entrants' mean is close to "
        "representative; only their weight is off."),
        "",
    ]

    # ----------------------------------------------------------- 2. regressions
    dcols = [c for c, _, _ in DRIVERS]
    # pooled sample: every cross-section row plus the 10 coins' middle months
    extra = ten.filter(pl.col("month").is_in(["2023-07", "2024-07", "2025-07"]))
    keep = ["symbol", "month", "acc", *dcols, MECH[0]]
    pooled = pl.concat([cross.select(keep), extra.select(keep)])
    surv_syms = set(c0["symbol"]) & set(c1s["symbol"])
    panel = pooled.filter(pl.col("symbol").is_in(list(surv_syms)))   # survivors + 10 coins
    two = cross.filter(pl.col("symbol").is_in(list(surv_syms)))      # survivors, 2 months
    ten10 = ten.select(keep)

    def mat(df, cols):
        return df.select(cols).to_numpy().astype(float)

    def month_dummies(df, months):
        return np.column_stack([(df["month"] == m).to_numpy().astype(float) for m in months])

    later = ["2023-07", "2024-07", "2025-07", "2026-07"]
    models = {}
    models["a1"] = fit(pooled["acc"], mat(pooled, dcols), pooled["symbol"], add_const=True)
    Xa2 = np.column_stack([mat(pooled, dcols), month_dummies(pooled, later)])
    models["a2"] = fit(pooled["acc"], Xa2, pooled["symbol"], add_const=True)
    models["b1"] = fit(panel["acc"], mat(panel, dcols), panel["symbol"], fe=panel["symbol"])
    Xb2 = np.column_stack([mat(panel, dcols), month_dummies(panel, later)])
    models["b2"] = fit(panel["acc"], Xb2, panel["symbol"], fe=panel["symbol"])
    models["b3"] = fit(ten10["acc"], mat(ten10, dcols), ten10["symbol"], fe=ten10["symbol"])
    models["m1"] = fit(panel["acc"], mat(panel, [*dcols, MECH[0]]), panel["symbol"],
                       fe=panel["symbol"])
    # wild bootstrap for the 10-coin model
    yt, Xt, cl = models["b3"]["data"]
    wild = {j: (wild_p(yt, Xt, cl, j), wild_ci(yt, Xt, cl, j)) for j in range(len(dcols))}
    # pairs bootstrap (resample contracts) for the FE panel model
    yt, Xt, cl = models["b1"]["data"]
    pb = pairs_boot(yt, Xt, cl, lambda y, X: np.linalg.lstsq(X, y, rcond=None)[0])
    pb_ci = np.percentile(pb, [2.5, 97.5], axis=0)

    # between-within spread of each driver (survivor two-month panel)
    sd_rows = []
    for c, lab, _ in DRIVERS:
        v = two[c].to_numpy()
        g = two["symbol"].to_numpy()
        means = np.array([v[g == s].mean() for s in np.unique(g)])
        sd_rows.append((lab, means.std(ddof=1), demean(g, v).std(ddof=1) * math.sqrt(2)))

    md += [
        "## 2. Regressions",
        "",
        ("Coefficients in pp of accuracy per step of the driver (step in the second "
        "column). Brackets: 95% interval, CRV1 clustered by contract, t(G-1). Models:"),
        (f"- (a1) pooled OLS on all {models['a1']['n']} contract-months (cross-sections "
        "plus the 10 coins' middle months), no time effects; (a2) the same with month "
        "intercepts."),
        (f"- (b1) contract fixed effects on the {len(surv_syms)} contracts present in both "
        f"cross-sections plus the 10-coin middle months ({models['b1']['n']} rows, "
        f"{models['b1']['G']} contracts); identified from within-contract changes, "
        "including the common rise."),
        ("- (b2) the same with month fixed effects (two-way): identified only from "
        "contracts whose driver moved more or less than the market in that month "
        "(section 1.4: the month effects absorb the common rise)."),
        (f"- (b3) contract fixed effects on the 10-coin 5-month panel ({models['b3']['n']} "
        "rows, 10 contracts); brackets are CRV1, the wild cluster bootstrap result is "
        "in the next table."),
        "",
        ("| driver | step | (a1) pooled | (a2) pooled + month | (b1) contract FE | "
        "(b2) two-way FE | (b3) 10 coins, contract FE |"),
        "|---|---|---|---|---|---|---|",
    ]
    for j, (_, lab, step) in enumerate(DRIVERS):
        cells = []
        for k in ["a1", "a2", "b1", "b2", "b3"]:
            m = models[k]
            jj = j + (1 if k.startswith("a") else 0)
            cells.append(f"{f(m['b'][jj])} ({ci(m['lo'][jj], m['hi'][jj])})")
        md.append(f"| {lab} | {step} | " + " | ".join(cells) + " |")
    md.append("| R2 (within for FE) | | " + " | ".join(
        f"{models[k]['r2_within']:.2f}" for k in ["a1", "a2", "b1", "b2", "b3"]) + " |")
    md += [
        "",
        ("Contract FE model (b1), second opinions: contract-resampling percentile "
        f"intervals ({N_BOOT} draws) and Bonferroni p-values for 6 drivers; the 10-coin "
        "model (b3) with the restricted wild cluster bootstrap (Rademacher, all 1,024 "
        "sign vectors, CI by test inversion):"),
        "",
        ("| driver | (b1) CRV1 p | (b1) Bonferroni p | (b1) contract-resampling 95% | "
        "(b3) wild p | (b3) wild 95% |"),
        "|---|---|---|---|---|---|",
    ]
    for j, (_, lab, _) in enumerate(DRIVERS):
        m = models["b1"]
        md.append(f"| {lab} | {pfmt(m['p'][j])} | {pfmt(min(1, 6 * m['p'][j]))} | "
                  f"{ci(pb_ci[0, j], pb_ci[1, j])} | {pfmt(wild[j][0])} | "
                  f"{ci(*wild[j][1])} |")
    m = models["m1"]
    md += [
        "",
        ("**Mechanical model, not an explanation.** Adding long same-sign runs (share of "
        "runs of 10 or more, sweeps merged) to (b1): its coefficient is "
        f"{f(m['b'][-1])} pp per +1 pp ({ci(m['lo'][-1], m['hi'][-1])}), and the within "
        f"R2 goes from {models['b1']['r2_within']:.2f} to {m['r2_within']:.2f}. Long runs "
        "are almost the outcome restated (a run of 10 is 9 correct persistence guesses), "
        "so this measures how the rise shows up, not why."),
        "",
        ("Within versus between spread of each driver (survivors, two months; the within "
        "standard deviation is scaled to the size of a two-month change):"),
        "",
        "| driver | SD of contract means | SD within contract |",
        "|---|---|---|",
        *[f"| {lab} | {a:.2f} | {b:.2f} |" for lab, a, b in sd_rows],
        "",
    ]

    # ------------------------------------------------- 2c. the 2026 dummy, Gelbach
    def gel_block(df, yname, extra_cols=()):
        cols = [*dcols, *extra_cols]
        y = df[yname].to_numpy().astype(float)
        g = df["symbol"].to_numpy()
        d26 = (df["month"] == T1).to_numpy().astype(float)
        X1 = d26[:, None]
        if df["month"].n_unique() > 2:
            X1 = np.column_stack([d26, month_dummies(df, ["2023-07", "2024-07", "2025-07"])])
        X2 = mat(df, cols)
        short = fit(y, X1, g, fe=g)
        long = fit(y, np.column_stack([X1, X2]), g, fe=g)
        yt, Xt, cl = long["data"]
        k1 = X1.shape[1]
        gb = gelbach(yt, Xt[:, :k1], Xt[:, k1:])
        bt = pairs_boot(yt, Xt, cl, lambda yy, XX: np.r_[
            (r := gelbach(yy, XX[:, :k1], XX[:, k1:]))["short"][0],
            r["long"][0], r["delta"][0]], seed=SEED + 7)
        return {"short": short, "long": long, "gb": gb, "boot": bt, "cols": cols,
                "yt": yt, "Xt": Xt, "cl": cl}

    G2 = gel_block(two, "acc")
    G2m = gel_block(two, "acc", (MECH[0],))
    G2l = gel_block(two, "lift")
    G10 = gel_block(ten10, "acc")
    # robustness: drop the smallest decile of contracts by 2023-06 events
    ev0 = c0.filter(pl.col("symbol").is_in(list(surv_syms))).select("symbol", "n_events")
    ev_cut = np.quantile(ev0["n_events"].to_numpy(), 0.1)
    big = set(ev0.filter(pl.col("n_events") > ev_cut)["symbol"])
    G2b = gel_block(two.filter(pl.col("symbol").is_in(list(big))), "acc")
    # 10-coin wild bootstrap on the 2026 dummy, short and long
    w10s = wild_ci(*G10["short"]["data"], 0)
    w10l = wild_ci(*G10["long"]["data"], 0)

    def gel_rows(G):
        gb, bt = G["gb"], G["boot"]
        lo, hi = np.percentile(bt, [2.5, 97.5], axis=0)
        short, long = gb["short"][0], gb["long"][0]
        rows = [("2026 coefficient, no drivers", short, lo[0], hi[0], 100.0),
                ("2026 coefficient, with drivers (unexplained)", long, lo[1], hi[1],
                 100 * long / short)]
        lab = {c: lbl for c, lbl, _ in [*DRIVERS, MECH]}
        for k, c in enumerate(G["cols"]):
            rows.append((f"explained by {lab[c]}", gb["delta"][0, k], lo[2 + k], hi[2 + k],
                         100 * gb["delta"][0, k] / short))
        for name, members in GROUPS.items():
            idx = [G["cols"].index(c) for c in members]
            v = bt[:, [2 + i for i in idx]].sum(1)
            val = gb["delta"][0, idx].sum()
            rows.append((f"group: {name}", val, *np.percentile(v, [2.5, 97.5]),
                         100 * val / short))
        return rows

    def gel_table(G, title):
        out = [f"**{title}** ({G['long']['n']} rows, {G['long']['G']} contracts)", "",
               "| term | pp | 95% (resampling contracts) | share of the 2026 coefficient |",
               "|---|---|---|---|"]
        for name, v, lo, hi, sh in gel_rows(G):
            out.append(f"| {name} | {f(v)} | {ci(lo, hi)} | {sh:.0f}% |")
        return out + [""]

    # driver changes on survivors (mean within-contract change 2023 -> 2026)
    dchg = {}
    for c in [*dcols, MECH[0]]:
        w = two.pivot(on="month", index="symbol", values=c)
        dd = (w[T1] - w[T0]).to_numpy()
        dchg[c] = (dd.mean(), *np.percentile(dd[np.random.default_rng(1).integers(
            0, dd.size, (N_BOOT, dd.size))].mean(1), [2.5, 97.5]))

    md += [
        "### The 2026 effect and what accounts for it (Gelbach decomposition)",
        "",
        ("Model: accuracy ~ 2026 dummy | contract (short), then + the six drivers "
        "(long). The 2026 coefficient in the short model is the mean within-contract "
        "rise (it equals the within term of the composition split). The Gelbach "
        "decomposition splits the fall from the short to the long coefficient into one "
        "exact, order-free piece per driver: (how much the driver moved within "
        "contracts) x (its coefficient in the long model). Intervals: "
        f"{N_BOOT} resamples of contracts. With two months, contract fixed effects are "
        "first differences. A month fixed effect cannot be added here: it would be the "
        "2026 dummy itself (section 1.4)."),
        "",
        *gel_table(G2, "Main: survivors, 2023-06 vs 2026-07, accuracy"),
        ("Mean within-contract change of each driver on these survivors (the first "
        "factor of each Gelbach piece):"),
        "",
        "| driver | mean change | 95% |",
        "|---|---|---|",
        *[f"| {lab} ({step}) | {f(dchg[c][0], 3)} | {ci(dchg[c][1], dchg[c][2], 3)} |"
          for c, lab, step in [*DRIVERS, MECH]],
        "",
        *gel_table(G2l, "Robustness outcome: lift over the majority rule, same survivors"),
        *gel_table(G2b, "Robustness: drop the smallest decile of survivors by 2023-06 events"),
        *gel_table(G10, "10 coins, 5 months (2026-07 dummy; 2023-07, 2024-07, 2025-07 "
                        "dummies in both models)"),
        (f"10 coins, restricted wild cluster bootstrap on the 2026-07 coefficient: no "
        f"drivers {ci(*w10s)}, with drivers {ci(*w10l)}. With 10 contracts the "
        "contract-resampling intervals above are rough."),
        "",
        *gel_table(G2m, "Mechanical, labelled separately: main model plus long runs"),
    ]

    # --------------------------------------------------- 3. link to e3 experiment
    # tick alone (total effect, trade size not held fixed) and the partial effect
    jt = dcols.index("log_rel_tick")
    tick_only = fit(two["acc"], np.column_stack([(two["month"] == T1).to_numpy()
                                                 .astype(float), two["log_rel_tick"]]),
                    two["symbol"], fe=two["symbol"])
    tick_pan = fit(panel["acc"], np.column_stack([month_dummies(panel, later),
                                                  panel["log_rel_tick"]]),
                   panel["symbol"], fe=panel["symbol"])
    ln10 = math.log(10)
    long_b = G2["long"]

    def cut(b, lo, hi):  # effect of a 10x tick cut: log rel tick falls by ln 10
        return -ln10 * b, -ln10 * hi, -ln10 * lo

    e_tick_only = cut(tick_only["b"][1], tick_only["lo"][1], tick_only["hi"][1])
    e_tick_pan = cut(tick_pan["b"][-1], tick_pan["lo"][-1], tick_pan["hi"][-1])
    e_partial = cut(long_b["b"][1 + jt], long_b["lo"][1 + jt], long_b["hi"][1 + jt])
    e_b2 = cut(models["b2"]["b"][jt], models["b2"]["lo"][jt], models["b2"]["hi"][jt])

    md += [
        "## 3. Agreement with the e3 natural experiment",
        "",
        ("e3 cut the tick 10x (log relative tick -2.15 to -2.30) and found same-day "
        "refit accuracy +3.9 pp (+1.0 to +6.9) in 2026 and +7.5 pp (+4.8 to +10.2) in "
        "2024 against matched controls, with a frozen pre-cut model showing no change "
        "(-0.7 pp). The `gbm_all` outcome here is fitted on each contract-month's own "
        "data, so the refit number is the comparable one. A 10x cut implied by the "
        "regressions (coefficient on log relative tick x -ln 10):"),
        "",
        "| model | implied effect of a 10x cut (pp) | 95% |",
        "|---|---|---|",
        (f"| survivors, contract FE + 2026 dummy, relative tick only (total effect) | "
        f"{f(e_tick_only[0])} | {ci(*e_tick_only[1:])} |"),
        (f"| panel (b1 sample), contract FE + month dummies, relative tick only | "
        f"{f(e_tick_pan[0])} | {ci(*e_tick_pan[1:])} |"),
        (f"| survivors, all six drivers (partial: trade size etc. held fixed) | "
        f"{f(e_partial[0])} | {ci(*e_partial[1:])} |"),
        f"| (b2) two-way FE, all drivers | {f(e_b2[0])} | {ci(*e_b2[1:])} |",
        "| e3 2026-03-05 event, same-day refit | +3.9 | +1.0 to +6.9 |",
        "| e3 2024-09-20 event, same-day refit | +7.5 | +4.8 to +10.2 |",
        "",
    ]
    jb3 = cut(models["b3"]["b"][jt], *wild[jt][1])
    md += [
        (f"The 10-coin model (b3) gives {f(jb3[0])} pp ({ci(*jb3[1:])}, wild bootstrap) "
        "for a 10x cut."),
        "",
    ]

    gr = {name: (v, lo, hi, sh) for name, v, lo, hi, sh in gel_rows(G2)}
    gr_l_size = {n: (v, lo, hi) for n, v, lo, hi, _ in gel_rows(G2l)}[
        "group: trade size (log size + under $1k)"]
    ws = two.pivot(on="month", index="symbol", values="log_size")
    size_neg = (ws[T1] - ws[T0]).to_numpy() < 0
    g10 = {name: (v, lo, hi, sh) for name, v, lo, hi, sh in gel_rows(G10)}
    size = gr["group: trade size (log size + under $1k)"]
    tick = gr["group: relative tick"]
    unex = gr["2026 coefficient, with drivers (unexplained)"]
    size10 = g10["group: trade size (log size + under $1k)"]
    unex10 = g10["2026 coefficient, with drivers (unexplained)"]
    rb = comp[("acc", "mean")][1]
    md += [
        "## 4. What explains the rise? (plain language)",
        "",
        (f"- **Not composition.** Mean accuracy across the cross-section rose {f(rm['total'])} "
        f"pp ({ci(*rb['total'])}). Contracts present in both months rose by more, "
        f"{f(rm['within'])} pp ({ci(*rb['within'])}). The coins that died were slightly "
        f"below the survivors, but removing them adds only {f(-rm['exit'])} pp; the new "
        f"listings are slightly less predictable than the survivors and pull the 2026 "
        f"average down by {f(-rm['entry'], sign=False)} pp (more, {f(-entry_pop, sign=False)} pp, "
        "at their population weight). Both composition terms are small and of opposite "
        "sign to the survivorship story; the whole rise, and a bit more, happens inside "
        "contracts. The median and the lift outcome say the same. The noise floor (one "
        f"month on 10 coins, {f(d_floor.mean())} pp) is far below the within change."),
        (f"- **Trade size accounts for all of the within-contract rise, and more.** Survivors' "
        f"median trade size fell in {100 * float(np.mean(size_neg)):.0f}% of "
        f"contracts, by {f(dchg['log_size'][0])} log points on average (about "
        f"{100 * (1 - math.exp(dchg['log_size'][0])):.0f}% smaller). Contracts whose trades "
        "shrank more became more predictable (about "
        f"{f(-long_b['b'][1], sign=False)} pp per log point, holding the other drivers "
        "fixed; similar in pooled, contract FE and two-way FE models). Multiplied out, "
        f"the size group accounts for {f(size[0])} pp ({ci(size[1], size[2])}) of the "
        f"{f(gr['2026 coefficient, no drivers'][0])} pp rise, so the remaining 2026 effect "
        f"turns negative ({f(unex[0])}, {ci(unex[1], unex[2])}). On the 10-coin 5-month "
        f"panel the size group accounts for {f(size10[0])} pp ({ci(size10[1], size10[2])}) "
        f"of {f(g10['2026 coefficient, no drivers'][0])} pp, leaving {f(unex10[0])}. "
        "Read as: the fall in trade size is more than enough, in an accounting sense, "
        "to explain the rise; the overshoot says the cross-contract slope does not carry "
        "over one-for-one to a market-wide shift of this size (or that something else "
        "pushed accuracy down at the same time). With the lift outcome the size group "
        f"is {f(gr_l_size[0])} pp ({ci(gr_l_size[1], gr_l_size[2])}): same direction, "
        "much wider."),
        (f"- **Relative tick explains none of the rise** ({f(tick[0])} pp, "
        f"{ci(tick[1], tick[2])}), not because it does not matter but because it did not "
        f"move on average: survivors' log relative tick changed by "
        f"{f(dchg['log_rel_tick'][0])} ({ci(dchg['log_rel_tick'][1], dchg['log_rel_tick'][2])}); "
        "about half the coins' ticks got relatively larger as prices fell, half smaller."),
        ("- **Other drivers.** Minute-open bunching and activity rose or fell in ways that "
        "point the wrong way (they subtract from the explained part, intervals include "
        "0); sweep share adds a little. The minute-open coefficient flips sign between "
        "the 10 coins (+) and the 136-contract panel (-), the within versus between "
        "warning from weeks 1 to 2. Long same-sign runs (mechanical) absorb part of the "
        "effect once added, as expected of a near-restatement of the outcome."),
        ("- **Agreement with e3.** Same sign: within contracts, a smaller relative tick goes "
        "with higher accuracy, and the implied effect of a 10x cut is "
        f"{f(e_tick_only[0])} to {f(e_partial[0])} pp on the 136-contract panel and "
        f"{f(jb3[0])} pp on the 10 coins, against e3's +3.9 and +7.5 pp. The "
        "estimates on the 136 contracts are smaller and their intervals include 0; they "
        "overlap the 2026 event's interval but not the 2024 one (the 10-coin interval "
        "overlaps both). Smaller is expected: relative tick is measured with "
        "noise and moves gradually with price (attenuation), and e3's treated coins had "
        "large ticks (11 to 13 bps) where a cut bites most. So the experiment and the "
        "regression agree that a finer relative tick raises predictability, and the "
        "regression adds that this channel cannot be what lifted the market from 2023 "
        "to 2026, because relative ticks did not shrink on average."),
        "",
        "## 5. Caveats",
        "",
        ("- **Noisy outcome.** Each accuracy comes from one month (at least 10,000 test "
        "events, binomial SE up to 0.5 pp); with only two snapshots per contract, "
        "contract fixed effects keep that noise and attenuate noisy drivers. Dropping "
        "the smallest decile by activity changes little."),
        ("- **Few snapshots.** The panel has two cross-section months (plus three middle "
        "months for 10 coins), so the 2026 dummy is one market-wide contrast, and "
        "everything else that changed between 2023 and 2026 is in it. The Gelbach split "
        "is an accounting identity given a linear model, not a causal attribution; the "
        "trade-size piece extrapolates a cross-contract slope to a common shift."),
        ("- **Trade size may partly be a change in what an event is.** Median notional per "
        "aggressor event fell about 84% within survivors. Week 0 flagged a change in "
        "aggregation shape for some coins (more fills per record); if the exchange's "
        "matching or reporting changed, part of the size fall, and of the accuracy "
        "rise, could be measurement. Not settled here."),
        ("- **Survivorship and sampling.** Survivors are contracts trading in both months; "
        "the 2026 entries are a decile-stratified sample of new listings (113 of 150 "
        "drawn were crypto and fitted), so the entry term uses the sample weight unless "
        "reweighted (both reported). Renames are separate units in the main split; "
        "linking the 3 that are in the sample changes nothing."),
        ("- **Multiple drivers tested.** Six drivers, four models, two outcomes. In the "
        "contract FE model only trade size survives a Bonferroni correction for six "
        "drivers. Treat the others as leads."),
        ("- **Few clusters for the 10-coin panel.** Reported with the wild cluster "
        "bootstrap; its intervals are wide."),
        ("- **Software.** Estimators written by hand (no pyfixest, linearmodels or "
        "statsmodels installed); checked against dummy-variable regressions in the "
        "tests."),
    ]

    res = {"comp": comp, "models": models, "G2": G2, "G2l": G2l, "G10": G10, "G2m": G2m,
           "G2b": G2b, "dchg": dchg, "floor": (d_floor.mean(), floor_ci), "entry_pop": entry_pop,
           "share_pop": share_pop, "e3": (e_tick_only, e_tick_pan, e_partial, e_b2),
           "wild": wild, "pb_ci": pb_ci, "w10": (w10s, w10l), "links": links, "r_link": r_link}
    return md, res


def figure(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, grid = "#0b0b0b", "#52514e", "#e4e3df"
    blue, orange, gray = "#2a78d6", "#eb6834", "#8a8984"
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": muted, "axes.labelcolor": ink,
                         "xtick.color": muted, "ytick.color": muted})
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2), gridspec_kw={"width_ratios": [1, 1.25]})

    # left: composition split of the mean, waterfall with intervals
    ax = axes[0]
    r, b = res["comp"][("acc", "mean")]
    steps = [("exits", r["exit"], b["exit"]), ("within\ncontract", r["within"], b["within"]),
             ("entries", r["entry"], b["entry"])]
    lvl = r["level_0"]
    tops = [lvl]
    ax.bar(0, lvl, color=gray, width=0.6)
    ax.text(0, lvl + 0.05, f"{lvl:.2f}", ha="center", va="bottom", color=ink)
    for i, (name, v, (lo, hi)) in enumerate(steps, start=1):
        col = blue if name.startswith("within") else orange
        ax.bar(i, v, bottom=lvl, color=col, width=0.6)
        ax.errorbar(i, lvl + v, yerr=[[v - lo], [hi - v]], color=ink, capsize=4, lw=1.2)
        ax.text(i, lvl + max(0.0, hi)
                + 0.08, f"{v:+.2f}", ha="center", va="bottom", color=ink)
        tops.append(lvl + max(0.0, hi))
        lvl += v
    ax.bar(4, r["level_1"], color=gray, width=0.6)
    ax.text(4, r["level_1"] + 0.05, f"{r['level_1']:.2f}", ha="center", va="bottom", color=ink)
    fl, (flo, fhi) = res["floor"]
    ax.set_xticks(range(5), ["2023-06\nmean", *[s[0] for s in steps], "2026-07\nmean"])
    lo_y = min(r["level_0"], r["level_1"]) - 2.5
    ax.set_ylim(lo_y, max(tops) + 0.6)
    ax.set_ylabel("mean fresh-model accuracy (%)")
    ax.set_title("Composition split of the 2023 to 2026 change\n(bars: 95% from resampling "
                 "contracts)", loc="left", color=ink)
    ax.set_xlabel(f"noise floor (same 10 coins, 2023-06 to 2023-07): {fl:+.2f} pp "
                  f"({flo:+.2f} to {fhi:+.2f})", color=muted, fontsize=9)
    ax.grid(axis="y", color=grid)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)

    # right: Gelbach decomposition of the within-contract 2026 effect
    ax = axes[1]
    G = res["G2"]
    gb, bt = G["gb"], G["boot"]
    lo, hi = np.percentile(bt, [2.5, 97.5], axis=0)
    lab = {c: lbl for c, lbl, _ in DRIVERS}
    items = [("2026 effect, no drivers", gb["short"][0], lo[0], hi[0], gray)]
    for k, c in enumerate(G["cols"]):
        items.append((f"explained: {lab[c]}", gb["delta"][0, k], lo[2 + k], hi[2 + k], blue))
    items.append(("unexplained (with drivers)", gb["long"][0], lo[1], hi[1], orange))
    ys = np.arange(len(items))[::-1]
    for y, (name, v, l, h, col) in zip(ys, items, strict=True):
        ax.barh(y, v, color=col, height=0.6)
        ax.errorbar(v, y, xerr=[[v - l], [h - v]], color=ink, capsize=3, lw=1.1)
        ax.text(max(h, 0) + 0.08, y, f"{v:+.2f}", va="center", color=ink, fontsize=9)
    ax.set_yticks(ys, [it[0] for it in items])
    ax.axvline(0, color=muted, lw=0.8)
    ax.set_xlabel("pp of accuracy (survivors, contract fixed effects)")
    ax.set_title("What accounts for the within-contract rise (Gelbach)\n"
                 f"{G['long']['G']} survivors, 2023-06 vs 2026-07", loc="left", color=ink)
    ax.grid(axis="x", color=grid)
    ax.set_axisbelow(True)
    xmax = max(hi.max(), gb["short"][0]) + 0.9
    ax.set_xlim(min(lo.min(), 0) - 0.3, xmax)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)


def main():
    md, res = run()
    figure(res)
    OUT_MD.write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
