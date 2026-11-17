"""Q11 report writing: JSON, the Markdown write-up and the figure.

Split out of `q11_mid_direction` to keep that module focused on computation.
Nothing is estimated here; every sentence is assembled from the finished
summary, including the verdict.
"""
from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from microstructure.data.jsonio import dumps_strict

STEM = "q11_mid_direction"
MODEL_LABEL = {
    "majority": "majority class",
    "qi_logit": "queue-imbalance logistic",
    "logit_all": "logistic, all features",
    "gbm_all": "LightGBM, all features",
}
# Fixed categorical order (blue, orange, aqua); markers carry the symbol so
# identity never rests on color alone.
SERIES_COLORS = ("#2a78d6", "#eb6834", "#1baf7a")
MARKERS = ("o", "s", "^", "D", "v", "P")
INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def _f(x: float | None, nd: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def _ci(c: dict, nd: int = 4) -> str:
    return f"{c['estimate']:+.{nd}f} [{c['ci95'][0]:+.{nd}f}, {c['ci95'][1]:+.{nd}f}]"


def _excludes_zero(c: dict) -> bool:
    return c["ci95"][0] > 0 or c["ci95"][1] < 0


def _pct(q: float) -> str:
    return "all" if q >= 1 else f"top {q * 100:g}%"


def _horizons(summary: dict) -> list[str]:
    return [str(h) for h in summary["config"]["horizons"]]


# --------------------------------------------------------------------------
# Verdict (assembled from computed fields)
# --------------------------------------------------------------------------


def statistical_lines(summary: dict) -> list[str]:
    syms, hs = summary["symbols"], _horizons(summary)
    if not syms:
        return ["No symbol could be scored, so there is no statistical result."]
    lines = []
    for h in hs:
        qi = [s["horizons"][h]["binary"]["qi_logit"]["auc"] for s in syms]
        gbm = [s["horizons"][h]["binary"]["gbm_all"]["auc"] for s in syms]
        diffs = [s["horizons"][h]["gbm_minus_qi"]["auc"] for s in syms]
        pos = sum(d["ci95"][0] > 0 for d in diffs)
        neg = sum(d["ci95"][1] < 0 for d in diffs)
        lines.append(
            f"- h = {h} events: out-of-sample AUC on the samples whose mid moved is "
            f"{min(qi):.3f} to {max(qi):.3f} for the queue-imbalance logistic and "
            f"{min(gbm):.3f} to {max(gbm):.3f} for LightGBM across {len(syms)} symbol(s). "
            f"The LightGBM minus queue-imbalance AUC difference has a day-block interval "
            f"above zero for {pos}, below zero for {neg} and including zero for "
            f"{len(syms) - pos - neg} of {len(syms)}."
        )
    first, last = hs[0], hs[-1]
    decays = sum(
        s["horizons"][last]["binary"]["gbm_all"]["auc"]
        < s["horizons"][first]["binary"]["gbm_all"]["auc"] for s in syms
    )
    if len(hs) > 1:
        lines.append(
            f"- LightGBM AUC is lower at h = {last} than at h = {first} for {decays} of "
            f"{len(syms)} symbol(s)."
        )
    return lines


def economic_lines(summary: dict) -> list[str]:
    v, fee = summary["verdict"], summary["config"]["taker_fee_bps"]
    if not v["n_cells"]:
        return ["No economics cell could be computed."]
    b = v["best"]
    where = (f"{b['symbol']}, h = {b['horizon']}, {MODEL_LABEL[b['model']]}, "
             f"{_pct(b['top_fraction'])} (n = {b['n']})")
    closest = (
        f"The cell that comes closest is {where}: gross edge {b['gross_bps']:.3f} bps "
        f"against a cost of {b['cost_bps']:.3f} bps, a ratio of {b['gross_over_cost']:.3f}."
    )
    if not v["any_exceeds_cost"]:
        return [
            (f"**No.** In none of the {v['n_cells']} cells (symbol x horizon x model x "
            f"confidence cut-off) does the gross edge exceed the round-trip taker cost at "
            f"a fee of {fee:g} bps per side. {closest} Whatever direction these models "
            "predict is not tradeable by a taker at this fee, and I make no claim of "
            "profitability."),
        ]
    k, n_sig = len(v["exceeds"]), len(v["significant"])
    listing = "; ".join(
        f"{c['symbol']} h = {c['horizon']} {MODEL_LABEL[c['model']]} {_pct(c['top_fraction'])} "
        f"(gross {c['gross_bps']:.3f}, cost {c['cost_bps']:.3f}, net interval "
        f"[{c['net_ci95'][0]:+.3f}, {c['net_ci95'][1]:+.3f}], n = {c['n']})"
        for c in v["exceeds"][:8]
    )
    if n_sig == 0:
        return [
            (f"**Not established.** The point estimate of gross edge exceeds the cost in {k} "
            f"of {v['n_cells']} cells ({listing}), but in every one of them the day-block "
            "interval for the net result includes zero. With that many cells examined, a "
            "few point estimates above cost are expected by chance. I do not call this "
            f"tradeable. {closest}"),
        ]
    return [
        (f"**Gross edge exceeds cost in {k} of {v['n_cells']} cells, {n_sig} with a net "
        f"day-block interval above zero** ({listing}). This is a statement about mid-price "
        "moves under a zero-latency assumption, over many cells without a multiple-testing "
        "correction, on a short test window. It marks those cells as worth a proper "
        f"execution study. It is not evidence of a profitable strategy. {closest}"),
    ]


def tick_regime_lines(summary: dict) -> list[str]:
    syms = sorted(summary["symbols"], key=lambda s: -s["spread"]["one_tick_time_share"])
    if not syms:
        return []
    h = _horizons(summary)[0]
    parts = [
        f"{s['symbol']} spends {s['spread']['one_tick_time_share']:.1%} of the time at a "
        f"one-tick spread (queue-imbalance AUC {s['horizons'][h]['binary']['qi_logit']['auc']:.3f}, "
        f"LightGBM AUC {s['horizons'][h]['binary']['gbm_all']['auc']:.3f} at h = {h})"
        for s in syms
    ]
    lines = ["Ordered from most to least time at a one-tick spread: " + "; ".join(parts) + "."]
    if len(syms) < 2:
        lines.append("With one symbol there is nothing to compare across tick regimes.")
        return lines
    for m in ("qi_logit", "gbm_all"):
        aucs = [s["horizons"][h]["binary"][m]["auc"] for s in syms]
        same = all(a >= b for a, b in pairwise(aucs))
        lines.append(
            f"The ordering by {MODEL_LABEL[m]} AUC "
            + ("matches" if same else "does not match")
            + f" the ordering by one-tick share. With {len(syms)} symbols this is a "
            "description, not a fitted relationship."
        )
    return lines


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out + [""]


def _tables(summary: dict) -> list[str]:
    syms, hs, fee = summary["symbols"], _horizons(summary), summary["config"]["taker_fee_bps"]
    L: list[str] = ["### Data and spread regime", ""]
    L += _table(
        ["symbol", "tick", "train events", "test events", "time at one-tick spread",
         "events at one-tick spread", "mean spread (ticks)", "trades printing at prior quote"],
        [[s["symbol"], f"{s['tick']:g}", f"{s['n_train_events']:,}", f"{s['n_test_events']:,}",
          f"{s['spread']['one_tick_time_share']:.1%}",
          f"{s['spread']['one_tick_event_share']:.1%}",
          f"{s['spread']['mean_spread_ticks']:.2f}", f"{s['at_quote_share']:.1%}"]
         for s in syms],
    )
    L += ["### Label shares in the test window (every h-th event)", ""]
    L += _table(
        ["symbol", "h", "samples", "test days", "up", "down", "unchanged",
         "mean abs move (bps)", f"share with abs move above cost at {fee:g} bps fee"],
        [[s["symbol"], h, f"{r['n_test']:,}", str(r["n_test_days"]), f"{r['share_up']:.1%}",
          f"{r['share_down']:.1%}", f"{r['share_unchanged']:.1%}",
          f"{r['mean_abs_move_bps']:.3f}", f"{r['share_move_exceeds_cost']:.2%}"]
         for s in syms for h in hs for r in [s["horizons"][h]]],
    )
    L += ["### Up versus down, on the samples whose mid moved", "",
          ("Log loss is in bits (1.0 is a coin flip). These scores condition on the mid "
          "having moved, which is not known in advance; the three-class table below does "
          "not condition."), ""]
    L += _table(
        ["symbol", "h", "model", "n", "accuracy", "AUC", "MCC", "log loss"],
        [[s["symbol"], h, MODEL_LABEL[m], f"{b['n']:,}", _f(b["accuracy"]), _f(b["auc"]),
          _f(b["mcc"]), _f(b["log_loss_bits"], 4)]
         for s in syms for h in hs
         for m, b in s["horizons"][h]["binary"].items()],
    )
    L += ["### LightGBM minus queue-imbalance logistic (95% day-block intervals)", ""]
    L += _table(
        ["symbol", "h", "accuracy", "AUC", "MCC", "log loss (bits)", "three-class MCC"],
        [[s["symbol"], h, _ci(d["accuracy"]), _ci(d["auc"]), _ci(d["mcc"]),
          _ci(d["log_loss_bits"]), _ci(d["mcc_three_class"])]
         for s in syms for h in hs for d in [s["horizons"][h]["gbm_minus_qi"]]],
    )
    L += ["### Three-class prediction (up, down, unchanged) on all samples", ""]
    L += _table(
        ["symbol", "h", "model", "accuracy", "MCC", "predicted unchanged"],
        [[s["symbol"], h, MODEL_LABEL[m], _f(t["accuracy"]), _f(t["mcc"]),
          f"{t['predicted_unchanged_share']:.1%}"]
         for s in syms for h in hs
         for m, t in s["horizons"][h]["three_class"].items()],
    )
    L += ["### Gross edge against round-trip taker cost (LightGBM, all samples)", "",
          ("Gross edge is the mean mid move in the predicted direction, in basis points, "
          "over the samples at or above the confidence cut-off, including samples whose "
          f"mid did not move. Cost is half the spread at entry plus half at exit plus "
          f"2 x {fee:g} bps. Intervals are 95% day-block."), ""]
    L += _table(
        ["symbol", "h", "cut-off", "n", "hit rate", "gross (bps)", "spread cost", "fees",
         "cost", "gross / cost", "net (bps)"],
        [[s["symbol"], h, _pct(r["top_fraction"]), f"{r['n']:,}"]
         + ([f"{r['hit_rate']:.1%}",
             f"{r['gross_bps']:.3f} [{r['gross_ci95'][0]:.3f}, {r['gross_ci95'][1]:.3f}]",
             f"{r['spread_cost_bps']:.3f}", f"{r['fee_cost_bps']:.1f}", f"{r['cost_bps']:.3f}",
             f"{r['gross_over_cost']:.3f}",
             f"{r['net_bps']:.3f} [{r['net_ci95'][0]:.3f}, {r['net_ci95'][1]:.3f}]"]
            if r["n"] else ["n/a"] * 7)
         for s in syms for h in hs for r in s["horizons"][h]["economics"]["gbm_all"]],
    )
    L.append("The same table for the two logistic models is in the JSON output.")
    L.append("")
    return L


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------


def markdown(summary: dict) -> str:
    c = summary["config"]
    fee, hs = c["taker_fee_bps"], ", ".join(str(h) for h in c["horizons"])
    L = [
        "# Q11: mid-price direction from top-of-book quotes, and whether it survives costs",
        "",
        "## Question",
        "",
        ("With top-of-book quotes added to the trade tape, can the direction of the next "
        "mid-price change be predicted out of sample, and is any of that predictability "
        "large enough to pay for acting on it as a taker? This is the price-side "
        "counterpart of Q9, which predicts trade signs from trades alone. It is limited "
        "to 2023 because Binance publishes `bookTicker` dumps for 2023 only."),
        "",
        "## Method",
        "",
        (f"- **Windows.** Train {c['train_start']} to {c['train_end']} (the last "
        f"{c['valid_days']} days are validation days, used for early stopping and for the "
        f"confidence cut-offs, after {c['embargo_days']} discarded embargo day). Test "
        f"{c['test_start']} to {c['test_end']}. All splits are on whole UTC days."),
        ("- **Clock.** One sample per aggressor trade event. Sample i reads the best bid and "
        "ask strictly before trade i and the trades before i."),
        (f"- **Label.** For h in {{{hs}}} events: the sign of mid(i+h) - mid(i), raw and "
        "unsmoothed, as up, down or unchanged. Smoothed labels of the FI-2010 or DeepLOB "
        "kind are partly computable from the inputs and are not used."),
        ("- **Overlap.** Models are fitted on every g-th event (g = greatest common divisor "
        "of the horizons) with the tree leaf size scaled by h/g. Every number below is "
        "computed on every h-th event of the test window, so test labels do not overlap. "
        "A sample is used only if its label window closes inside its own block, which "
        "removes the last h events before each boundary. Events sharing a millisecond "
        "with the previous event are not fitted or scored."),
        (f"- **Features ({len(c['features'])}, all causal and scale-free).** Queue imbalance, "
        "spread in ticks, a one-tick-spread indicator, microprice minus mid in ticks, quote "
        "order-flow imbalance over the last 1, 5, 20 and 100 trades in units of trailing "
        "depth, mid return over the last 10, 50 and 200 events in units of trailing "
        "volatility, and the trade-history features of `microstructure.ml.features`. The "
        "tick is the smallest price increment seen in the training window."),
        ("- **Models.** Majority class; logistic regression on queue imbalance alone (Gould "
        "and Bonart 2016); logistic regression on all features; LightGBM on all features. "
        "Each is a pair of binary models, P(mid moves) and P(up given a move), which gives "
        "both the up-versus-down scores and a three-way prediction."),
        (f"- **Economics.** Direction and confidence come from P(up) - P(down). Cost is half "
        f"the spread at entry, half at exit, and 2 x {fee:g} bps of taker fee."),
        f"- **Inference.** 95% intervals resample whole UTC days ({c['n_boot']} resamples).",
        "",
        "## Results",
        "",
    ]
    L += _tables(summary)
    L += ["### Large-tick versus small-tick", ""] + tick_regime_lines(summary) + [""]
    L += [f"![Q11 figure]({STEM}.png)", "", "## Verdict", "",
          "**Is direction predictable?**", ""]
    L += statistical_lines(summary)
    L += ["", "**Does it survive taker costs?**", ""] + economic_lines(summary) + [""]
    if summary["skipped"]:
        L += ["## Skipped symbols", ""]
        L += _table(["symbol", "reason"], [[s["symbol"], s["reason"]] for s in summary["skipped"]])
    n_days = max((r["n_test_days"] for s in summary["symbols"] for r in s["horizons"].values()),
                 default=0)
    L += [
        "## Caveats",
        "",
        (f"- **Fee not verified at source.** The {fee:g} bps taker fee is the Binance USDT-M "
        "regular-tier figure as reported by third-party pages. I could not check it against "
        "Binance's own fee page, and fees changed over time. It is a command-line parameter "
        "(`--fee-bps`); the report can be rebuilt at another fee without refitting."),
        ("- **The cost accounting is optimistic.** Entry is priced at the quote that stood "
        "before trade i, with no latency, no queue of competing takers and no market impact "
        "of the order itself. A real taker acts after seeing the data and gets a later, "
        "usually worse, quote. If the gross edge does not cover the cost here, it will not "
        "cover it in practice."),
        ("- **Taker only.** A passive order would earn the spread and pay a lower fee, but "
        "top-of-book data without queue position cannot say when it would fill. No maker "
        "result is implied."),
        ("- **Conditioning.** The up-versus-down scores use only samples whose mid moved, "
        "which is known only afterwards. The three-class and economics tables use all samples."),
        (f"- **Short sample.** One training window and one test window from 2023, with at most "
        f"{n_days} test day(s). Day-block intervals from so few days are coarse and likely too "
        "narrow. One market regime; nothing here is tested on other years."),
        ("- **Many cells.** The economics table has one cell per symbol, horizon, model and "
        "cut-off, with no multiple-testing correction."),
        ("- **Mechanical component.** At a one-tick spread the thinner queue tends to empty "
        "first, so part of the predictability from queue imbalance is queue mechanics, "
        "bounded by about one tick."),
        ("- **Data.** `bookTicker` shows only the best level and may coalesce updates; trades "
        "are joined to the last quote with a strictly earlier millisecond timestamp. The "
        "table above reports how often a trade prints at or through that quote."),
        ("- **Models were not tuned.** LightGBM uses the project's default settings, and only "
        "the number of rounds is chosen on the validation days."),
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


def figure(summary: dict, path: Path) -> None:
    syms, hs = summary["symbols"], _horizons(summary)
    fee = summary["config"]["taker_fee_bps"]
    fig, (ax_auc, ax_eco) = plt.subplots(1, 2, figsize=(13, 5.2), facecolor=SURFACE)
    learned = ("qi_logit", "logit_all", "gbm_all")
    x = list(range(len(hs)))
    for si, s in enumerate(syms):
        mk = MARKERS[si % len(MARKERS)]
        for mi, m in enumerate(learned):
            ax_auc.plot(x, [s["horizons"][h]["binary"][m]["auc"] for h in hs], marker=mk,
                        markersize=8, linewidth=2, color=SERIES_COLORS[mi],
                        markeredgecolor=SURFACE, markeredgewidth=1.5)
    ax_auc.axhline(0.5, color=INK_MUTED, linestyle="--", linewidth=1)
    ax_auc.annotate("no skill", (x[-1], 0.5), xytext=(0, 4), textcoords="offset points",
                    ha="right", fontsize=9, color=INK_MUTED)
    ax_auc.set_xticks(x, [f"h = {h}" for h in hs])
    ax_auc.set_xlabel("label horizon (trade events)", color=INK_MUTED)
    ax_auc.set_ylabel("AUC, up versus down, samples whose mid moved", color=INK_MUTED)
    ax_auc.set_title("Out-of-sample AUC by horizon and model", color=INK, fontsize=11, loc="left")
    model_handles = [Line2D([], [], color=SERIES_COLORS[i], linewidth=2, label=MODEL_LABEL[m])
                     for i, m in enumerate(learned)]
    symbol_handles = [Line2D([], [], color=INK_MUTED, marker=MARKERS[i % len(MARKERS)],
                             linestyle="", markersize=8, label=s["symbol"])
                      for i, s in enumerate(syms)]
    ax_auc.legend(handles=model_handles + symbol_handles, fontsize=8.5, frameon=False,
                  labelcolor=INK)

    fracs = summary["config"]["top_fractions"]
    xf = list(range(len(fracs)))
    costs = []
    for si, s in enumerate(syms):
        mk = MARKERS[si % len(MARKERS)]
        for hi, h in enumerate(hs):
            rows = s["horizons"][h]["economics"]["gbm_all"]
            ax_eco.plot(xf, [r.get("gross_bps") for r in rows], marker=mk, markersize=8,
                        linewidth=2, color=SERIES_COLORS[hi % len(SERIES_COLORS)],
                        markeredgecolor=SURFACE, markeredgewidth=1.5)
            cost = [r.get("cost_bps") for r in rows]
            costs += [c for c in cost if c is not None]
            ax_eco.plot(xf, cost, marker=mk, markersize=5, linewidth=1, linestyle="--",
                        color=INK_MUTED)
    ax_eco.axhline(0.0, color=GRID, linewidth=1.2)
    if costs:
        ax_eco.annotate(f"round-trip taker cost (spread + 2 x {fee:g} bps)",
                        (xf[0], max(costs)), xytext=(0, 6), textcoords="offset points",
                        fontsize=9, color=INK_MUTED)
        ax_eco.set_ylim(top=max(costs) * 1.15)
    ax_eco.set_xticks(xf, [_pct(q) for q in fracs])
    ax_eco.set_xlabel("confidence cut-off (most confident share of samples)", color=INK_MUTED)
    ax_eco.set_ylabel("basis points per round trip", color=INK_MUTED)
    ax_eco.set_title("LightGBM gross edge against taker cost", color=INK, fontsize=11,
                     loc="left")
    horizon_handles = [Line2D([], [], color=SERIES_COLORS[i % len(SERIES_COLORS)], linewidth=2,
                              label=f"gross edge, h = {h}") for i, h in enumerate(hs)]
    cost_handle = [Line2D([], [], color=INK_MUTED, linewidth=1, linestyle="--", label="cost")]
    ax_eco.legend(handles=horizon_handles + cost_handle + symbol_handles, fontsize=8.5,
                  frameon=False, labelcolor=INK, loc="center left")
    for ax in (ax_auc, ax_eco):
        _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def write_outputs(summary: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{STEM}.json").write_text(dumps_strict(summary))
    (out / f"{STEM}.md").write_text(markdown(summary))
    figure(summary, out / f"{STEM}.png")
