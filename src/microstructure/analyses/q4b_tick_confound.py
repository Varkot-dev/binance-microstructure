"""Q4b: tick-size confound test — does relative tick size explain Q4's p_flip law?

Q4 (results/q4_cross_section.json) found p_flip ~ log10(n_events) with slope
+0.1114, R^2 = 0.2632, n = 121: more actively traded symbols flip sign more
often. A possible alternative explanation is relative tick size
(tickSize / price), a mechanical driver of bid-ask bounce that plausibly
correlates with activity (liquid symbols tend to have small ticks relative to
price). If it is the true driver, "activity" in the Q4 regression is a proxy
and the competitive-response story rests on a bid-ask-bounce artifact.

Method:
1. Fetch current PRICE_FILTER.tickSize per symbol from Binance futures
   exchangeInfo (public, unauthenticated). This is today's tick size, not
   June 2023's (see the caveat in the md output). The raw
   response is cached to `exchangeinfo_snapshot.json` for provenance.
2. For each of Q4's 121 successful symbols, compute mean trade price over
   2023-06 via a lazy Polars scan of the same aggTrades parquet Q4 used, and
   derive rel_tick = tickSize / mean_price.
3. Fit three OLS regressions via `numpy.linalg.lstsq` on the symbols with
   both p_flip (from q4_cross_section.json) and rel_tick (computed here):
   (a) p_flip ~ log10(n_events)          [reproduces Q4's law as baseline]
   (b) p_flip ~ log10(rel_tick)          [does tick size alone predict it?]
   (c) p_flip ~ log10(n_events) + log10(rel_tick)  [which survives jointly?]
   Also reports corr(log10(n_events), log10(rel_tick)), the collinearity
   that motivates the whole test.

Coefficient significance is reported as a "t-ish ratio" (coef / stderr) with
the caveat Q4 uses for its own regressions: the cross-section's OLS
assumptions (i.i.d., homoskedastic residuals) are unverified and almost
certainly violated (heterogeneous symbols, no correction for cross-sectional
dependence), so the ratios are descriptive, not a formal test.

Outputs: q4b_tick_confound.{md,json} plus one PNG (p_flip vs log10(rel_tick),
points colored by log10(n_events)).
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import httpx
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from microstructure.data.catalog import parquet_path

EXCHANGE_INFO_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"


# --------------------------------------------------------------------------
# Regression machinery (numpy lstsq, t-ish ratios and R^2)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RegressionResult:
    """OLS fit via np.linalg.lstsq: coefficient names -> value/stderr/t_ratio."""

    names: tuple[str, ...]
    coefs: tuple[float, ...]
    stderrs: tuple[float, ...]
    t_ratios: tuple[float, ...]
    r2: float
    n: int

    def to_dict(self) -> dict:
        return {
            "coefficients": {
                name: {"value": c, "stderr": se, "t_ratio": t}
                for name, c, se, t in zip(
                    self.names, self.coefs, self.stderrs, self.t_ratios, strict=True
                )
            },
            "r2": self.r2,
            "n": self.n,
        }


def _ols_lstsq(design: np.ndarray, y: np.ndarray, names: tuple[str, ...]) -> RegressionResult:
    """OLS via np.linalg.lstsq with an intercept column already in `design`.

    `design` is the full design matrix (including the intercept column of
    ones), `names` labels its columns in order. Returns coefficients,
    classical OLS stderr (assuming i.i.d. homoskedastic residuals — see
    module docstring caveat), t-ish ratios, and R^2.
    """
    n, k = design.shape
    if n <= k:
        raise ValueError(f"n={n} observations <= k={k} parameters; regression not identified")
    coef, _residuals_sum, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    if rank < k:
        raise ValueError(f"design matrix rank-deficient (rank={rank}, k={k})")

    yhat = design @ coef
    resid = y - yhat
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    dof = n - k
    sigma2 = ss_res / dof if dof > 0 else float("nan")
    xtx_inv = np.linalg.inv(design.T @ design)
    cov = sigma2 * xtx_inv
    stderrs = np.sqrt(np.diag(cov))
    t_ratios = coef / stderrs

    return RegressionResult(
        names=names,
        coefs=tuple(float(c) for c in coef),
        stderrs=tuple(float(s) for s in stderrs),
        t_ratios=tuple(float(t) for t in t_ratios),
        r2=r2,
        n=n,
    )


def fit_univariate(x: np.ndarray, y: np.ndarray, x_name: str) -> RegressionResult:
    """y ~ intercept + x."""
    design = np.column_stack([np.ones_like(x), x])
    return _ols_lstsq(design, y, ("intercept", x_name))


def fit_bivariate(x1: np.ndarray, x2: np.ndarray, y: np.ndarray, x1_name: str, x2_name: str) -> RegressionResult:
    """y ~ intercept + x1 + x2."""
    design = np.column_stack([np.ones_like(x1), x1, x2])
    return _ols_lstsq(design, y, ("intercept", x1_name, x2_name))


# --------------------------------------------------------------------------
# exchangeInfo fetch + caching
# --------------------------------------------------------------------------


def fetch_exchange_info(client: httpx.Client | None = None, url: str = EXCHANGE_INFO_URL) -> dict:
    """Fetch the raw Binance futures exchangeInfo response.

    Public endpoint, no key required. Tick sizes are as of the time of the
    run, not June 2023 (see module docstring and the md caveats). Tick-size
    changes are rare but do happen, so this is a small source of error.

    `url` defaults to the mainnet endpoint. Pass a different URL (e.g. a
    mirror, if mainnet is geo-blocked) together with
    `run_q4b(source_url=..., source_note=...)` so the substitution is
    recorded in the output.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()
    finally:
        if owns_client:
            client.close()


def tick_sizes_from_exchange_info(raw: dict) -> dict[str, float]:
    """symbol -> PRICE_FILTER.tickSize, for every symbol that has one."""
    out: dict[str, float] = {}
    for sym_info in raw.get("symbols", []):
        symbol = sym_info.get("symbol")
        if not symbol:
            continue
        for f in sym_info.get("filters", []):
            if f.get("filterType") == "PRICE_FILTER" and "tickSize" in f:
                out[symbol] = float(f["tickSize"])
                break
    return out


def cache_exchange_info(raw: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "exchangeinfo_snapshot.json"
    p.write_text(json.dumps(raw, indent=2))
    return p


# --------------------------------------------------------------------------
# mean price per symbol (lazy scan of the same 2023-06 aggTrades Q4 used)
# --------------------------------------------------------------------------


def mean_trade_price(root: Path, symbol: str, period: str = "2023-06") -> float | None:
    """Mean aggTrades price over `period`, via a lazy Polars scan.

    Returns None if the parquet is missing (caller decides how to record
    that as a skip/failure rather than crashing the whole run).
    """
    p = parquet_path(root, symbol, "aggTrades", period)
    if not p.exists():
        return None
    val = pl.scan_parquet(p).select(pl.col("price").mean()).collect().item()
    return float(val) if val is not None else None


# --------------------------------------------------------------------------
# per-symbol assembly
# --------------------------------------------------------------------------


def _load_q4_symbols(q4_json_path: Path) -> list[dict]:
    data = json.loads(q4_json_path.read_text())
    return data["symbols"]


def _assemble_records(
    root: Path,
    q4_symbols: list[dict],
    tick_sizes: dict[str, float],
    period: str,
) -> tuple[list[dict], list[dict]]:
    """Join Q4's per-symbol stats with tick size and mean price.

    Returns (records, skipped) where `records` have rel_tick computable and
    `skipped` lists symbols excluded with a reason (no tickSize in the
    exchangeInfo snapshot, or missing/empty parquet for mean price).
    """
    records: list[dict] = []
    skipped: list[dict] = []
    for s in q4_symbols:
        symbol = s["symbol"]
        tick = tick_sizes.get(symbol)
        if tick is None:
            skipped.append({"symbol": symbol, "reason": "no tickSize in exchangeInfo snapshot"})
            continue
        mean_price = mean_trade_price(root, symbol, period)
        if mean_price is None or mean_price <= 0:
            skipped.append({"symbol": symbol, "reason": "missing parquet or non-positive mean price"})
            continue
        rel_tick = tick / mean_price
        records.append(
            {
                "symbol": symbol,
                "n_events": s["n_events"],
                "p_flip": s["p_flip"],
                "tick_size": tick,
                "mean_price": mean_price,
                "rel_tick": rel_tick,
            }
        )
    return records, skipped


# --------------------------------------------------------------------------
# main entry point
# --------------------------------------------------------------------------


def run_q4b(
    root: Path,
    out_dir: Path,
    q4_json_path: Path,
    period: str = "2023-06",
    client: httpx.Client | None = None,
    source_url: str = EXCHANGE_INFO_URL,
    source_note: str | None = None,
) -> dict:
    """Run the tick-confound analysis.

    `source_url`/`source_note` record what was actually fetched in this run,
    independent of `client` (which may be a mock in tests or a real client
    pointed at a non-default URL; see `fetch_exchange_info`). They default to
    the mainnet endpoint and no note. A caller that fetches elsewhere should
    pass the URL used and a note explaining the substitution.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    q4_symbols = _load_q4_symbols(q4_json_path)

    raw_exchange_info = fetch_exchange_info(client=client, url=source_url)
    cache_exchange_info(raw_exchange_info, out_dir)
    tick_sizes = tick_sizes_from_exchange_info(raw_exchange_info)

    records, skipped = _assemble_records(root, q4_symbols, tick_sizes, period)

    result: dict = {
        "period": period,
        "n_q4_symbols": len(q4_symbols),
        "n_usable": len(records),
        "n_skipped": len(skipped),
        "symbols": records,
        "skipped": skipped,
        "exchange_info_url": source_url,
        "exchange_info_source_note": source_note,
    }

    if len(records) < 4:
        result["regressions"] = {
            "note": f"fewer than 4 usable symbols ({len(records)}); regressions not fit",
            "reg_activity": None,
            "reg_tick": None,
            "reg_joint": None,
            "corr_log_n_log_rel_tick": None,
        }
        _write_results_md(out_dir, result)
        (out_dir / "q4b_tick_confound.json").write_text(json.dumps(result, indent=2))
        return result

    log_n = np.array([np.log10(r["n_events"]) for r in records])
    log_rel_tick = np.array([np.log10(r["rel_tick"]) for r in records])
    p_flip = np.array([r["p_flip"] for r in records])

    reg_activity = fit_univariate(log_n, p_flip, "log10_n_events")
    reg_tick = fit_univariate(log_rel_tick, p_flip, "log10_rel_tick")
    reg_joint = fit_bivariate(log_n, log_rel_tick, p_flip, "log10_n_events", "log10_rel_tick")
    corr = float(np.corrcoef(log_n, log_rel_tick)[0, 1])

    result["regressions"] = {
        "note": None,
        "reg_activity": reg_activity.to_dict(),
        "reg_tick": reg_tick.to_dict(),
        "reg_joint": reg_joint.to_dict(),
        "corr_log_n_log_rel_tick": corr,
    }

    _plot_flip_vs_rel_tick(out_dir, records)
    _write_results_md(out_dir, result)
    (out_dir / "q4b_tick_confound.json").write_text(json.dumps(result, indent=2))
    return result


# --------------------------------------------------------------------------
# plotting
# --------------------------------------------------------------------------


def _plot_flip_vs_rel_tick(out_dir: Path, records: list[dict]) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    log_rel_tick = np.array([np.log10(r["rel_tick"]) for r in records])
    p_flip = np.array([r["p_flip"] for r in records])
    log_n = np.array([np.log10(r["n_events"]) for r in records])

    sc = ax.scatter(log_rel_tick, p_flip, c=log_n, cmap="viridis", s=28, alpha=0.85)
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("log10(n_events)")

    if len(records) >= 4:
        slope, intercept = np.polyfit(log_rel_tick, p_flip, 1)
        x_line = np.array([log_rel_tick.min(), log_rel_tick.max()])
        ax.plot(x_line, slope * x_line + intercept, color="red",
                 label=f"OLS fit (slope={slope:.4f})")
        ax.legend()

    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1.0)
    ax.set_xlabel("log10(relative tick size) = log10(tickSize / mean_price)")
    ax.set_ylabel(r"$p_{flip} = P(sign_{t+1} \neq sign_t)$")
    ax.set_title("Q4b: sign-flip probability vs. relative tick size\n(color = log activity)")
    fig.savefig(out_dir / "q4b_flip_vs_rel_tick.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------
# markdown report
# --------------------------------------------------------------------------


def _fmt_coef(name: str, c: dict) -> str:
    return f"{name} = **{c['value']:.4f}** (stderr {c['stderr']:.4f}, t≈{c['t_ratio']:.2f})"


def _fmt_regression(reg: dict | None) -> str:
    if reg is None:
        return "not estimable"
    parts = [_fmt_coef(name, c) for name, c in reg["coefficients"].items()]
    return ", ".join(parts) + f", R² = {reg['r2']:.4f}, n = {reg['n']}"


def _write_results_md(out_dir: Path, result: dict) -> None:
    regs = result["regressions"]
    lines: list[str] = []
    lines.append("# Q4b: tick-size confound")
    lines.append("")
    lines.append("## Question")
    lines.append("")
    lines.append(
        "Q4 found `p_flip ~ log10(n_events)` with slope +0.1114 (R² = 0.2632, n = 121): "
        "more actively traded symbols flip sign more often. One alternative is relative "
        "tick size (`tickSize / price`), a mechanical driver of bid-ask bounce that "
        "plausibly correlates with activity. If it is the real driver, \"activity\" in "
        "Q4's regression is a proxy and the competitive-response reading is an artifact of "
        "bid-ask bounce. This analysis runs the regression that separates the two."
    )
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        "1. **Tick size**: from the Binance futures `exchangeInfo` endpoint "
        f"(`{result['exchange_info_url']}`, public, unauthenticated), taking each symbol's "
        "`PRICE_FILTER.tickSize`. The raw response is cached in "
        "`exchangeinfo_snapshot.json`."
    )
    source_note = result.get("exchange_info_source_note")
    if source_note:
        lines.append("")
        lines.append("   The endpoint used differs from the default; see Caveats.")
    lines.append(
        "2. **Mean price**: for each of Q4's 121 successful symbols, the mean aggTrades "
        f"price over {result['period']}, from a lazy Polars scan of the parquet Q4 used. "
        "`rel_tick = tickSize / mean_price`."
    )
    lines.append(
        "3. **Regressions**: three OLS fits (`numpy.linalg.lstsq`) on the usable symbols "
        "(in Q4's successful set, in the exchangeInfo snapshot, with a readable mean "
        "price): (a) `p_flip ~ log10(n_events)`, Q4's law on this possibly smaller sample; "
        "(b) `p_flip ~ log10(rel_tick)`; (c) `p_flip ~ log10(n_events) + log10(rel_tick)`, "
        "which shows whose coefficient survives once the other is controlled. I also report "
        "`corr(log10(n_events), log10(rel_tick))`."
    )
    lines.append("")
    lines.append(
        "**t-ratios** are the coefficient over its classical-OLS stderr, which assumes "
        "i.i.d. homoskedastic residuals. That is unverified and likely violated in a "
        "heterogeneous cross-section of 121 assets with no correction for cross-sectional "
        "dependence or heteroskedasticity (the same caveat as Q4). Read them as coefficient "
        "size relative to noise, not as a test with a valid p-value."
    )
    lines.append("")
    lines.append("## Run summary")
    lines.append("")
    lines.append(
        f"Q4 successful symbols: {result['n_q4_symbols']}. Usable for this analysis (tick size "
        f"found + mean price computed): {result['n_usable']}. Skipped: {result['n_skipped']}."
    )
    lines.append("")

    lines.append("## Regressions")
    lines.append("")
    lines.append(f"**(a) p_flip ~ log10(n_events)** [Q4's law, reproduced on this sample]: "
                  f"{_fmt_regression(regs.get('reg_activity'))}")
    lines.append("")
    lines.append(f"**(b) p_flip ~ log10(rel_tick)**: {_fmt_regression(regs.get('reg_tick'))}")
    lines.append("")
    lines.append(f"**(c) p_flip ~ log10(n_events) + log10(rel_tick)** [joint]: "
                  f"{_fmt_regression(regs.get('reg_joint'))}")
    lines.append("")
    corr = regs.get("corr_log_n_log_rel_tick")
    corr_str = f"{corr:.4f}" if corr is not None else "not estimable"
    lines.append(
        f"corr(log10(n_events), log10(rel_tick)) = {corr_str}, the collinearity between "
        "activity and relative tick size."
    )
    lines.append("")

    lines.append("## Verdict")
    lines.append("")
    lines.append(_verdict_paragraph(regs))
    lines.append("")

    if result["skipped"]:
        lines.append("## Skipped symbols")
        lines.append("")
        lines.append("| symbol | reason |")
        lines.append("|---|---|")
        for s in result["skipped"]:
            lines.append(f"| {s['symbol']} | {s['reason']} |")
        lines.append("")

    lines.append("## Caveats")
    lines.append("")
    if source_note:
        lines.append(f"- **exchangeInfo source substitution**: {source_note}")
    lines.append(
        "- **Tick size is current, not June-2023.** `exchangeInfo` returns the tick size as "
        "of the day the analysis is run, not for the June 2023 period behind the trade data "
        "and Q4's p_flip. Binance occasionally changes `PRICE_FILTER.tickSize`, usually "
        "after large price moves. For a symbol whose price regime shifted materially since "
        "June 2023, `rel_tick` may not match the tick size in force during the data "
        "window. This error is probably small for most symbols and is not corrected."
    )
    lines.append(
        "- 121-symbol sample, reduced to the usable subset above. Symbols missing from the "
        "snapshot (e.g. delisted or renamed since June 2023) are dropped, not imputed."
    )
    lines.append(
        "- Single month (2023-06), as in Q4: one market regime, not tested on other periods."
    )
    lines.append(
        "- The OLS assumptions are unverified (see Method), so the reported stderr, "
        "t-ratios and R² are descriptive. Same reasons as Q4: heteroskedastic, non-i.i.d. "
        "residuals across heterogeneous assets."
    )
    lines.append(
        "- Even a clean result in (c) shows which variable better explains this "
        "cross-section statistically. It does not identify the mechanism generating p_flip."
    )
    lines.append("")
    (out_dir / "q4b_tick_confound.md").write_text("\n".join(lines))


def _verdict_paragraph(regs: dict) -> str:
    if regs.get("note"):
        return f"Not estimable: {regs['note']}."

    reg_joint = regs["reg_joint"]
    coefs = reg_joint["coefficients"]
    n_coef = coefs["log10_n_events"]
    tick_coef = coefs["log10_rel_tick"]
    corr = regs["corr_log_n_log_rel_tick"]

    n_survives = abs(n_coef["t_ratio"]) >= 2.0
    tick_survives = abs(tick_coef["t_ratio"]) >= 2.0

    reg_activity_r2 = regs["reg_activity"]["r2"]
    reg_tick_r2 = regs["reg_tick"]["r2"]
    joint_r2 = reg_joint["r2"]

    if n_survives and not tick_survives:
        verdict = (
            f"**Activity survives, relative tick size does not.** In the joint regression (c), "
            f"log10(n_events) has coefficient {n_coef['value']:.4f} (t≈{n_coef['t_ratio']:.2f}) "
            f"and log10(rel_tick) has {tick_coef['value']:.4f} "
            f"(t≈{tick_coef['t_ratio']:.2f}), indistinguishable from zero by this rough "
            f"measure. Despite the collinearity (corr = {corr:.4f}), activity keeps its "
            "explanatory power once tick size is controlled for. This is evidence against "
            "the tick-size confound: the p_flip law appears to be about activity, not a "
            "bid-ask-bounce artifact."
        )
    elif tick_survives and not n_survives:
        verdict = (
            f"**Relative tick size survives, activity does not.** In the joint regression (c), "
            f"log10(rel_tick) has coefficient {tick_coef['value']:.4f} "
            f"(t≈{tick_coef['t_ratio']:.2f}) and log10(n_events) has "
            f"{n_coef['value']:.4f} (t≈{n_coef['t_ratio']:.2f}), indistinguishable from zero. "
            f"Given the collinearity (corr = {corr:.4f}), this is the tick-size confound: "
            "what looked like an activity effect in Q4 is better explained by relative tick "
            "size, a mechanical driver of bid-ask bounce. Q4's competitive-response "
            "interpretation of the p_flip law is unsupported until re-tested against this "
            "control."
        )
    elif n_survives and tick_survives:
        verdict = (
            "**Both variables survive jointly.** In regression (c), log10(n_events) "
            f"(coef {n_coef['value']:.4f}, t≈{n_coef['t_ratio']:.2f}) and log10(rel_tick) "
            f"(coef {tick_coef['value']:.4f}, t≈{tick_coef['t_ratio']:.2f}) both remain "
            f"distinguishable from zero despite their collinearity (corr = {corr:.4f}). "
            "Each carries at least partly independent information about p_flip in this "
            "cross-section, so the tick-size confound is present but does not fully explain "
            "away the activity effect."
        )
    else:
        verdict = (
            "**Neither variable clearly survives jointly.** In regression (c), neither "
            f"log10(n_events) (coef {n_coef['value']:.4f}, t≈{n_coef['t_ratio']:.2f}) nor "
            f"log10(rel_tick) (coef {tick_coef['value']:.4f}, t≈{tick_coef['t_ratio']:.2f}) is "
            f"clearly distinguishable from zero once the other is controlled for. This fits "
            f"their strong collinearity (corr = {corr:.4f}) making the two effects hard to "
            "separate at this sample size. The result is inconclusive."
        )

    r2_note = (
        f" Univariate R² is {reg_activity_r2:.4f} for activity alone and "
        f"{reg_tick_r2:.4f} for relative tick size alone, versus {joint_r2:.4f} jointly."
    )
    return verdict + r2_note


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Q4b: tick-size confound test")
    parser.add_argument("--root", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--q4-json", type=Path, default=Path("results/q4_cross_section.json"))
    parser.add_argument("--period", type=str, default="2023-06")
    parser.add_argument(
        "--exchange-info-url", type=str, default=EXCHANGE_INFO_URL,
        help=(
            "Binance exchangeInfo endpoint to fetch tick sizes from. Defaults to the "
            "documented mainnet futures endpoint; override only if that endpoint is "
            "unreachable (e.g. geo-blocked) and you must use a mirror — pass "
            "--source-note to document the substitution in the output."
        ),
    )
    parser.add_argument(
        "--source-note", type=str, default=None,
        help="Provenance note recorded in the md/json if --exchange-info-url deviates "
             "from the mainnet default (e.g. explaining a network-access substitution).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    run_q4b(
        args.root, args.out, q4_json_path=args.q4_json, period=args.period,
        source_url=args.exchange_info_url, source_note=args.source_note,
    )
