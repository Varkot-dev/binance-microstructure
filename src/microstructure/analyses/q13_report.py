"""Q13 report writing: JSON, the Markdown write-up and the figure.

Split out of `q13_break_even` to keep that module focused on computation.
Nothing is estimated here; every sentence is assembled from the finished
summary, including the verdict.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from microstructure.data.jsonio import dumps_strict

STEM = "q13_break_even"
MODEL_LABEL = {
    "qi_logit": "queue-imbalance logistic",
    "logit_all": "logistic, all features",
    "gbm_all": "LightGBM, all features",
}
# Fixed categorical order (blue, orange, aqua), one hue per horizon in both panels.
SERIES_COLORS = ("#2a78d6", "#eb6834", "#1baf7a")
INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def _pct(q: float) -> str:
    return "all" if q >= 1 else f"top {q * 100:g}%"


def _ci(c: dict, nd: int = 3) -> str:
    return f"{c['estimate']:+.{nd}f} [{c['ci95'][0]:+.{nd}f}, {c['ci95'][1]:+.{nd}f}]"


def _num(x: float | None, nd: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def _mult(x: float | None) -> str:
    return "n/a (gross <= 0)" if x is None else f"{x:.1f}x"


def _be(r: dict) -> str:
    lo, hi = r["break_even_fee_ci95"]
    return f"{r['break_even_fee_bps']:+.3f} [{lo:+.3f}, {hi:+.3f}]"


def _horizons(summary: dict) -> list[str]:
    return [str(h) for h in summary["config"]["horizons"]]


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out + [""]


def _where(c: dict) -> str:
    return (f"h = {c['horizon']}, {MODEL_LABEL[c['model']]}, {_pct(c['top_fraction'])} "
            f"(n = {c['n']:,})")


# --------------------------------------------------------------------------
# Verdict (assembled from computed fields)
# --------------------------------------------------------------------------


def check_lines(summary: dict) -> list[str]:
    ch = summary["q11_check"]
    if ch["status"] == "not_checked":
        return [f"The gross-edge numbers were **not** checked against Q11 ({ch['reason']})."]
    parts = [f"{MODEL_LABEL[m]} {d['n_cells']} cells, largest difference {d['max_abs_diff_bps']:.2g} bps"
             for m, d in ch["by_model"].items()]
    what = ("n, gross edge, spread cost and both day-block intervals"
            if ch["intervals_compared"] else "n, gross edge and spread cost (intervals not "
            "compared: different resample counts)")
    head = ("reproduce" if ch["status"] == "matched" else "do not reproduce")
    return [f"The numbers below {head} Q11's economics table ({what}; tolerance "
            f"{ch['tolerance_bps']:g} bps): " + "; ".join(parts) + "."]


def break_even_lines(summary: dict) -> list[str]:
    v, fee = summary["verdict"], summary["config"]["taker_fee_bps"]
    if not v["n_cells"]:
        return ["No break-even cell could be computed."]
    lines = [
        (f"- Across all {v['n_cells']} cells (symbol x horizon x model x cut-off), "
         f"{v['n_pays_at_fee']} pay at the assumed {fee:g} bps per side and "
         f"{v['n_pays_at_zero_fee']} have a gross edge above the spread cost, that is, "
         "would pay at a zero fee."),
    ]
    for ps in v["per_symbol"]:
        b, sym = ps["best_break_even"], ps["symbol"]
        if b is None:
            lines.append(f"- **{sym}:** no cell could be computed.")
            continue
        be, lo, hi = b["break_even_fee_bps"], *b["break_even_fee_ci95"]
        detail = (f"best cell is {_where(b)}: gross edge {b['gross_bps']:.3f} bps against a "
                  f"spread cost of {b['spread_cost_bps']:.3f} bps, break-even fee "
                  f"{be:+.3f} bps per side [{lo:+.3f}, {hi:+.3f}]")
        if ps["category"] == "pays_at_fee":
            lines.append(f"- **{sym}: pays at the assumed fee.** The {detail}, above the assumed "
                         f"{fee:g} bps." + (" The interval's lower end is below that fee, so "
                                            "this is not established." if lo <= fee else ""))
        elif ps["category"] == "pays_below_fee":
            lines.append(
                f"- **{sym}: pays only below {be:.3f} bps per side.** The {detail}. At the "
                f"assumed {fee:g} bps the round-trip cost is {_mult(b['required_multiple'])} "
                "the gross edge."
                + (f" Even the interval's upper end is {hi / fee:.1%} of the assumed fee."
                   if hi < fee else "")
                + (" The interval includes zero, so a positive break-even fee is itself not "
                   "established." if lo <= 0 else ""))
        else:
            lines.append(
                f"- **{sym}: does not pay even at zero fee.** The {detail}; the spread alone "
                f"is {_mult(b['required_multiple_zero_fee'])} the gross edge.")
    return lines


def _q7_symbol(summary: dict, sym: str) -> dict | None:
    q7 = summary.get("q7")
    if not q7:
        return None
    return next((r for r in q7["per_symbol"] if r["symbol"] == sym), None)


def timing_lines(summary: dict) -> list[str]:
    v, q7 = summary["verdict"], summary.get("q7")
    lines = []
    for ps in v["per_symbol"]:
        t, sym = ps["best_timing"], ps["symbol"]
        if t is None:
            continue
        pf, rnd = t["perfect_foresight"], t["random"]
        rnd_zero = rnd["saving"]["ci95"][0] <= 0 <= rnd["saving"]["ci95"][1]
        line = (
            f"- **{sym}:** the largest mean saving is at h = {t['horizon']}, "
            f"{MODEL_LABEL[t['model']]}, {_pct(t['top_fraction'])}: {t['share_delayed']:.1%} of "
            f"orders delayed, {_ci(t['saving'])} bps per order (standard deviation "
            f"{t['sd_per_order']:.3f} bps per order, {t['share_worse_when_delayed']:.1%} of "
            f"delayed orders end up worse), "
            f"{_num(t['share_of_perfect'], 2)} of the perfect-foresight bound of "
            f"{pf['saving']['estimate']:.3f} bps and {_num(t['saving_over_half_spread'], 2)} "
            "times the mean half spread."
            + (" At the \"all\" cut-off one side of every sample is delayed, hence about half "
               "of all orders." if t["top_fraction"] >= 1 else "")
            + f" The random wait at the same rate saves {_ci(rnd['saving'])} bps, an interval that "
            + ("includes zero." if rnd_zero else "excludes zero.")
        )
        r7 = _q7_symbol(summary, sym)
        if r7 is not None:
            line += (f" Q7 put this symbol's mean shortfall at {r7['twap']['mean_shortfall']:.3f} "
                     f"bps (TWAP), {r7['frontloaded']['mean_shortfall']:.3f} bps (front-loaded) "
                     f"and {r7['reactive']['mean_shortfall']:.3f} bps (flow-reactive).")
        lines.append(line)
    if q7:
        rt = q7["reactive_minus_twap"]
        best = [ps["best_timing"]["saving"]["estimate"] for ps in v["per_symbol"]
                if ps["best_timing"]]
        bigger = sum(abs(rt["mean"]) < s for s in best)
        lines.append(
            f"- Against Q7: its flow-reactive schedule beat TWAP by {-rt['mean']:.3f} bps "
            f"per unit pooled over its symbols (paired SE {rt['se']:.3f}, n = {rt['n']}). "
            f"The best mid-only timing saving above is larger than that in {bigger} of "
            f"{len(best)} symbol(s). The two are not like for like: Q7 is a model-based replay "
            f"of {q7['horizon_events']}-event parent orders on {q7['days'][0]} to "
            f"{q7['days'][-1]}, Q13 is single orders delayed h events on the Q11 test window, "
            "and the Q13 saving leaves out the spread change and the order's own impact.")
    else:
        lines.append("- Q7's results file was not found, so there is no comparison with Q7.")
    return lines


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


def _tables_a(summary: dict) -> list[str]:
    syms, hs, fee = summary["symbols"], _horizons(summary), summary["config"]["taker_fee_bps"]
    L = ["### Part A: best cell per symbol", "",
         ("The best cell is the one with the highest break-even fee per side over every "
          "horizon, model and cut-off."), ""]
    L += _table(
        ["symbol", "best cell", "gross (bps)", "spread cost", "break-even fee per side (bps)",
         f"cost at {fee:g} bps / gross", "pays at zero fee"],
        [[ps["symbol"], _where(b), f"{b['gross_bps']:.3f}", f"{b['spread_cost_bps']:.3f}",
          _be(b), _mult(b["required_multiple"]),
          "yes" if b["pays_at_zero_fee"] else "no"]
         for ps in summary["verdict"]["per_symbol"] for b in [ps["best_break_even"]] if b],
    )
    L += ["### Part A: every LightGBM cell", "",
          ("Gross edge and spread cost are Q11's. Break-even fee per side = (gross - spread "
           "cost) / 2, with its 95% day-block interval. The multiple is the round-trip cost "
           f"at {fee:g} bps per side divided by the gross edge. The logistic models' cells "
           "are in the JSON output."), ""]
    L += _table(
        ["symbol", "h", "cut-off", "n", "gross (bps)", "spread cost", "break-even fee (bps)",
         "pays at zero fee", f"cost at {fee:g} bps / gross"],
        [[s["symbol"], h, _pct(r["top_fraction"]), f"{r['n']:,}"]
         + ([f"{r['gross_bps']:.3f}", f"{r['spread_cost_bps']:.3f}",
             _be(r),
             "yes" if r["pays_at_zero_fee"] else "no", _mult(r["required_multiple"])]
            if r["n"] else ["n/a"] * 5)
         for s in syms for h in hs for r in s["horizons"][h]["break_even"]["gbm_all"]],
    )
    return L


def _tables_b(summary: dict) -> list[str]:
    syms, hs = summary["symbols"], _horizons(summary)
    L = ["### Part B: wait or trade now, every model at the \"all\" cut-off", "",
         ("Mean saving per order against always trading now, in bps of the mid, over buyers "
          "and sellers with equal weight (orders not delayed save 0). Intervals are 95% "
          "day-block. \"Half spreads\" divides by the mean cached half spread (the average of "
          "the entry and exit half spreads). \"Of perfect\" is the share of the "
          "perfect-foresight saving. The random wait delays the same share of orders on a "
          "coin flip."), ""]
    rows = []
    for s in syms:
        for h in hs:
            t = s["horizons"][h]["timing"]
            pf = t["perfect_foresight"]
            for m, mrows in t["models"].items():
                r = mrows[0]
                rows.append([s["symbol"], h, MODEL_LABEL[m], f"{r['share_delayed']:.1%}",
                             _ci(r["saving"]), f"{r['sd_per_order']:.3f}",
                             _num(r["saving_over_half_spread"], 2),
                             _num(r["share_of_perfect"], 2), _ci(r["random"]["saving"])])
            rows.append([s["symbol"], h, "perfect foresight", f"{pf['share_delayed']:.1%}",
                         _ci(pf["saving"]), f"{pf['sd_per_order']:.3f}",
                         _num(pf["saving_over_half_spread"], 2), "1.00", ""])
    L += _table(["symbol", "h", "policy", "orders delayed", "saving per order (bps)",
                 "sd per order", "half spreads", "of perfect", "random wait (bps)"], rows)
    L += ["### Part B: LightGBM across Q11's cut-offs", "",
          ("\"Saving when delayed\" is the mean favourable mid move over the delayed orders "
           "only (it equals Q11's gross edge for the cell). \"Worse\" is the share of delayed "
           "orders whose mid moved against the trader."), ""]
    L += _table(
        ["symbol", "h", "cut-off", "orders delayed", "saving per order (bps)", "sd per order",
         "saving when delayed", "sd when delayed", "worse", "of perfect"],
        [[s["symbol"], h, _pct(r["top_fraction"]), f"{r['share_delayed']:.1%}", _ci(r["saving"]),
          f"{r['sd_per_order']:.3f}", _num(r["saving_when_delayed"]),
          _num(r["sd_when_delayed"]),
          "n/a" if r["share_worse_when_delayed"] is None else f"{r['share_worse_when_delayed']:.1%}",
          _num(r["share_of_perfect"], 2)]
         for s in syms for h in hs for r in s["horizons"][h]["timing"]["models"]["gbm_all"]],
    )
    q7 = summary.get("q7")
    if q7:
        L += [f"### Q7 execution costs, quoted from `{q7['source']}`", "",
              (f"Mean shortfall per unit in {q7['unit']}, evaluation days {q7['days'][0]} to "
               f"{q7['days'][-1]}, parent orders over {q7['horizon_events']} events in "
               f"{q7['n_children']} children. Only the symbols shared with Q13 are listed, "
               "with Q7's pooled panel figures in the last row."), ""]
        rows = [[r["symbol"]] + [f"{r[k]['mean_shortfall']:.3f} (sd {r[k]['sd_shortfall']:.2f})"
                                 for k in ("twap", "frontloaded", "reactive")]
                for r in q7["per_symbol"]]
        rows.append(["pooled (Q7 panel)"]
                    + [f"{q7['summary'][k]['mean_shortfall']:.3f} "
                       f"(sd {q7['summary'][k]['sd_shortfall']:.2f})"
                       for k in ("twap", "frontloaded", "reactive")])
        L += _table(["symbol", "TWAP (bps)", "front-loaded (bps)", "flow-reactive (bps)"], rows)
    return L


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------


def markdown(summary: dict) -> str:
    c = summary["config"]
    fee, qc = c["taker_fee_bps"], c["q11_config"]
    L = [
        ("# Q13: how far the Q11 mid-direction edge is from break-even, and what it is worth "
         "for order timing"),
        "",
        "## Question",
        "",
        ("Q11 found that the direction of the next mid-price change is predictable out of "
         "sample, but that the gross edge never covers a round-trip taker cost. Q13 asks two "
         "follow-up questions of the same test-window predictions. (A) At what taker fee per "
         "side would each cell break even, and does any cell pay even at a zero fee? (B) For a "
         "trader who must buy or sell anyway, how much does waiting h events when the model "
         "expects the mid to move in the trader's favour save against trading at once? "
         "Nothing is refitted and no new data is read."),
        "",
        "## Method",
        "",
        (f"- **Predictions.** Q11's cached test-window predictions under key "
         f"`{c['q11_cache_key']}`, which is what Q11's `config_key` gives today for its default "
         f"run config (train {qc['train_start']} to {qc['train_end']}, test {qc['test_start']} "
         f"to {qc['test_end']}) and its current fit settings. Other keys on disk, including "
         "the one written before the tick-size fix, are not read. Every number uses every h-th "
         "test event, as in Q11."),
        ("- **Cut-offs.** Q11 fixed its confidence cut-offs on the validation days (the most "
         "confident 100%, 50%, 20% and 5% of validation samples ranked by |P(up) - P(down)|) "
         "and stored the thresholds with the predictions. Q13 applies those stored thresholds "
         "unchanged. The \"all\" cut-off is the rule P(up) - P(down) != 0, which needs no "
         "data. No threshold is chosen on the test window."),
        ("- **Part A.** Gross edge (mean mid move in the predicted direction over the samples "
         "at or above the cut-off) and spread cost (half the spread at entry plus half at "
         "exit) are computed by Q11's own code. Break-even taker fee per side = (gross - "
         f"spread cost) / 2. Required multiple = round-trip cost at {fee:g} bps per side / "
         "gross edge."),
        ("- **Part B.** At each test sample one buyer and one seller must trade one unit, with "
         "equal weight. If the model's P(down) - P(up) is at or above the cut-off the buyer "
         "waits h events and buys then; if P(up) - P(down) is, the seller waits; otherwise "
         "both trade now. The saving of a delayed order is the mid move in its favour, in bps "
         "of the mid at i; an order traded now saves 0. Perfect foresight waits exactly when "
         "the mid moves in the trader's favour. The random wait delays the same share of "
         "orders on a coin flip (seeded)."),
        ("- **Spread at the delayed time.** The cache holds only the sum of the half spreads "
         "at i and i+h, so the half spread at the delayed time cannot be separated from the "
         "one at i. The saving is therefore mid-only: it leaves out any change in the half "
         "spread between i and i+h. As a scale, the saving is divided by half the mean cached "
         "spread, the average of the entry and exit half spreads."),
        (f"- **Inference.** 95% intervals resample whole UTC days ({c['n_boot']} resamples, "
         "seed 0 as in Q11)."),
        "",
        "## Check against Q11",
        "",
    ]
    L += check_lines(summary) + [""]
    L += ["## Results", ""]
    L += _tables_a(summary) + _tables_b(summary)
    L += [f"![Q13 figure]({STEM}.png)", "", "## Verdict", "",
          f"**(A) How far from break-even, at an assumed {fee:g} bps per side?**", ""]
    L += break_even_lines(summary)
    L += ["", "**(B) What is the prediction worth for timing an order that must be placed?**",
          ""] + timing_lines(summary) + [""]
    if summary["skipped"]:
        L += ["## Skipped symbols", ""]
        L += _table(["symbol", "reason"], [[s["symbol"], s["reason"]] for s in summary["skipped"]])
    n_q7 = len(summary["q7"]["per_symbol"]) if summary.get("q7") else 0
    n_days = max((r["n_test_days"] for s in summary["symbols"] for r in s["horizons"].values()),
                 default=0)
    L += [
        "## Caveats",
        "",
        (f"- **Fee not verified at source.** The {fee:g} bps taker fee per side is the Binance "
         "USDT-M regular-tier figure as reported by third-party pages, the same assumption as "
         "Q11. I could not check it against Binance's own fee page, and fees changed over "
         "time. No other fee tier is assumed here; the break-even fee lets a reader compare "
         "with whatever fee applies to them. It is a command-line parameter (`--fee-bps`)."),
        ("- **Spread change not included.** The saving in Part B is a mid-price saving. A "
         "delayed order crosses the half spread at i+h, not at i, and the cache cannot "
         "separate the two. When the spread sits at one tick most of the time (see the "
         "one-tick shares in Q11) the change is usually zero, but it is not measured here."),
        ("- **Delaying has costs not modelled.** The order's own market impact, the risk that "
         "the quote moves away and the order is not filled at all, other participants trading "
         "on the same signal, and latency are all absent. The standard deviation and the "
         "share of delayed orders that end up worse show that waiting adds risk, even when "
         "the mean saving is positive."),
        ("- **Optimistic timing.** Sample i reads the quote that stood before trade i, with no "
         "latency, as in Q11. A real trader sees the data later."),
        ("- **Q7 is not like for like.** Q7 is a model-based replay (drift, half spread and "
         "linear own impact) of parent orders on different days in June 2023, and "
         f"{n_q7} of its symbols are in Q13. Its numbers are quoted for scale, not as a benchmark "
         "this analysis beats or misses."),
        (f"- **Short sample.** One test window from 2023 with at most {n_days} test day(s); "
         "day-block intervals from so few days are coarse and likely too narrow."),
        ("- **Many cells.** Part A has one cell per symbol, horizon, model and cut-off, and "
         "the best cell per symbol is a maximum over them, which flatters it. No "
         "multiple-testing correction is applied."),
        "",
    ]
    return "\n".join(L)


# --------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=9)


def _best_per_horizon(s: dict, h: str) -> dict | None:
    cells = [r for rows in s["horizons"][h]["break_even"].values() for r in rows if r["n"]]
    return max(cells, key=lambda r: r["break_even_fee_bps"]) if cells else None


def figure(summary: dict, path: Path) -> None:
    syms, hs = summary["symbols"], _horizons(summary)
    fee = summary["config"]["taker_fee_bps"]
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(13, 5.2), facecolor=SURFACE)
    x = list(range(len(syms)))
    width = 0.22
    offsets = [(i - (len(hs) - 1) / 2) * width for i in range(len(hs))]
    for hi, h in enumerate(hs):
        color = SERIES_COLORS[hi % len(SERIES_COLORS)]
        for si, s in enumerate(syms):
            b = _best_per_horizon(s, h)
            if b is None:
                continue
            est = b["break_even_fee_bps"]
            lo, hi_ = b["break_even_fee_ci95"]
            ax_a.errorbar(x[si] + offsets[hi], est, yerr=[[est - lo], [hi_ - est]], fmt="o",
                          color=color, markersize=8, elinewidth=2, capsize=0,
                          markeredgecolor=SURFACE, markeredgewidth=1.5)
    ax_a.axhline(fee, color=INK_MUTED, linestyle="--", linewidth=1)
    ax_a.annotate(f"assumed taker fee, {fee:g} bps per side", (0.01, fee), xytext=(0, -14),
                  textcoords="offset points", xycoords=ax_a.get_yaxis_transform(), fontsize=9, color=INK_MUTED)
    ax_a.axhline(0.0, color=INK_MUTED, linewidth=1)
    ax_a.annotate("zero fee", (0.01, 0.0), xytext=(0, 5), textcoords="offset points",
                  xycoords=ax_a.get_yaxis_transform(), fontsize=9, color=INK_MUTED)
    ax_a.set_xticks(x, [s["symbol"] for s in syms])
    ax_a.set_ylim(min(-1.0, ax_a.get_ylim()[0]), max(fee * 1.15, ax_a.get_ylim()[1]))
    ax_a.set_ylabel("break-even taker fee per side (bps)", color=INK_MUTED)
    ax_a.set_title("Part A: best cell per symbol and horizon, 95% day-block interval",
                   color=INK, fontsize=11, loc="left")

    for hi, h in enumerate(hs):
        color = SERIES_COLORS[hi % len(SERIES_COLORS)]
        for si, s in enumerate(syms):
            r = s["horizons"][h]["timing"]["models"]["gbm_all"][0]
            pf = s["horizons"][h]["timing"]["perfect_foresight"]["saving"]["estimate"]
            if pf <= 0:
                continue
            est = r["saving"]["estimate"] / pf
            lo, hi_ = (v / pf for v in r["saving"]["ci95"])
            xx = x[si] + offsets[hi]
            ax_b.errorbar(xx, est, yerr=[[est - lo], [hi_ - est]], fmt="o", color=color,
                          markersize=8, elinewidth=2, capsize=0, markeredgecolor=SURFACE,
                          markeredgewidth=1.5)
            rnd = r["random"]["saving"]["estimate"] / pf
            ax_b.plot(xx, rnd, marker="x", color=INK_MUTED, markersize=7, linestyle="")
    ax_b.axhline(0.0, color=INK_MUTED, linewidth=1)
    ax_b.axhline(1.0, color=INK_MUTED, linestyle="--", linewidth=1)
    ax_b.annotate("perfect foresight", (0.01, 1.0), xytext=(0, -14), textcoords="offset points",
                  xycoords=ax_b.get_yaxis_transform(), fontsize=9, color=INK_MUTED)
    ax_b.set_xticks(x, [s["symbol"] for s in syms])
    ax_b.set_ylim(-0.1, 1.1)
    ax_b.set_ylabel("saving per order / perfect-foresight saving", color=INK_MUTED)
    ax_b.set_title("Part B: LightGBM wait-or-trade-now, \"all\" cut-off, mid-only",
                   color=INK, fontsize=11, loc="left")
    handles = [Line2D([], [], color=SERIES_COLORS[i % len(SERIES_COLORS)], marker="o",
                      linestyle="", markersize=8, label=f"h = {h} events")
               for i, h in enumerate(hs)]
    ax_a.legend(handles=handles, fontsize=8.5, frameon=False, labelcolor=INK, loc="center right")
    ax_b.legend(handles=handles + [Line2D([], [], color=INK_MUTED, marker="x", linestyle="",
                                          markersize=7, label="random wait, same delay rate")],
                fontsize=8.5, frameon=False, labelcolor=INK, loc="center right")
    for ax in (ax_a, ax_b):
        _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def write_outputs(summary: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{STEM}.json").write_text(dumps_strict(summary))
    (out / f"{STEM}.md").write_text(markdown(summary))
    figure(summary, out / f"{STEM}.png")
