"""Q9 report writing: the verdict, the Markdown writer and the matplotlib figure.

Everything here is a pure function of the result dict assembled by
`q9_sign_prediction.build_result` from the per-symbol caches, so the write-up
can be regenerated without touching the trade data. Every sentence of the
verdict is built from numbers in that dict.

Sign convention for increments: both metrics are reported as gains of the
upper rung over the lower one, so positive is always better (extra accuracy,
or bits of log loss removed).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INCREMENT_LETTERS = {"memory": "a", "nonlinearity": "b", "context": "c"}
STATE_PHRASE = {
    "positive": "the interval excludes zero on the positive side",
    "negative": "the interval excludes zero on the negative side",
    "zero": "the interval includes zero",
}
BLOCK_LABEL = {"within_month": "within-month test days", "next_month": "next month"}
_INK, _MUTED, _GRID = "#0b0b0b", "#8a8984", "#e4e3df"
_BLUE, _ORANGE = "#2a78d6", "#eb6834"


def _f(x: float | None, nd: int = 4, signed: bool = False) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.{nd}f}" if signed else f"{x:.{nd}f}"


def _range(lo: float, hi: float, fmt: str) -> str:
    a, b = format(lo, fmt), format(hi, fmt)
    return a if a == b else f"{a} to {b}"


def _ci(ci: dict, nd: int = 4) -> str:
    return f"{ci['estimate']:+.{nd}f} [{ci['ci95'][0]:+.{nd}f}, {ci['ci95'][1]:+.{nd}f}]"


def _increment(result: dict, key: str) -> dict:
    return next(i for i in result["increments"] if i["key"] == key)


# --------------------------------------------------------------------------
# Verdict (computed from the numbers)
# --------------------------------------------------------------------------


def increment_sentence(result: dict, key: str, block: str = "within_month") -> str:
    """One sentence on one increment in one scored block, both metrics."""
    inc = _increment(result, key)
    b = result[block]
    acc, ll = b["pooled"][key]["accuracy"], b["pooled"][key]["log_loss"]
    sa = b["increments_summary"][key]["accuracy"]
    sl = b["increments_summary"][key]["log_loss"]
    n = sa["n_symbols"]
    return (
        f"({INCREMENT_LETTERS[key]}) {inc['meaning'].capitalize()} "
        f"({inc['upper']} minus {inc['lower']}): pooled accuracy gain {_ci(acc)}, "
        f"{STATE_PHRASE[acc['state']]}; per symbol the interval lies above zero for "
        f"{sa['n_positive']} of {n} and below zero for {sa['n_negative']}, with a median gain "
        f"of {_f(sa['median_gain'], signed=True)}. Pooled log loss removed {_ci(ll)} bits, "
        f"{STATE_PHRASE[ll['state']]}; above zero for {sl['n_positive']} of {n} symbols, "
        f"below zero for {sl['n_negative']}, median {_f(sl['median_gain'], signed=True)} bits."
    )


def _median_gap(block: dict, upper: str, lower: str) -> float:
    ps = block["per_symbol"]
    return float(np.median(
        [ps[s]["scores"][upper]["accuracy"] - ps[s]["scores"][lower]["accuracy"] for s in ps]))


def _holdout_sentence(result: dict) -> str:
    nxt = result["next_month"]
    if nxt is None:
        return (
            "No next-month scores are cached, so whether the edge survives a month the "
            "models never saw is not tested here."
        )
    syms = result["next_month_symbols"]
    win = result["within_month"]["per_symbol"]
    parts = []
    for rung in ("linear", "gbm_all"):
        w = float(np.median([win[s]["scores"][rung]["accuracy"] for s in syms]))
        x = nxt["median"][rung]["accuracy"]
        parts.append(f"{rung} {_f(w)} within the month and {_f(x)} in the next ({_f(x - w, signed=True)})")
    total = {
        m: sum(nxt["pooled"][k][m]["estimate"] for k in ("nonlinearity", "context"))
        for m in ("accuracy", "log_loss")
    }
    states = [nxt["pooled"][k]["accuracy"]["state"] for k in ("nonlinearity", "context")]
    n_pos = sum(s == "positive" for s in states)
    return (
        f"Out of month ({result['holdout_period']}, the frozen {result['period']} ladder, "
        f"{len(syms)} symbols, {nxt['pooled_n_days']} day blocks), median accuracy is "
        f"{parts[0]}; {parts[1]}. There the pooled gain of gbm_all over the linear rung is "
        f"{_f(total['accuracy'], signed=True)} in accuracy and {_f(total['log_loss'], signed=True)} "
        f"bits of log loss, and {n_pos} of the 2 learned increments (b, c) have a pooled "
        f"accuracy interval above zero."
    )


def _not_trading_sentence(result: dict) -> str:
    blocks = [result["within_month"]] + ([result["next_month"]] if result["next_month"] else [])
    best = max(
        b["per_symbol"][s]["scores"][r]["accuracy"]
        for b in blocks for s in b["per_symbol"] for r in result["rungs"]
    )
    n_calls = sum(
        b["per_symbol"][s]["scores"]["gbm_all"]["n"] for b in blocks for s in b["per_symbol"]
    )
    n_features = len(next(iter(result["trial_log"]["configurations"]))["config"]["all_features"])
    return (
        f"None of this is a trading result. The best accuracy in any cell is {_f(best)}, "
        f"which still leaves {_f(1 - best)} of next signs called wrong, and what was scored is "
        f"{n_calls:,} sign calls, not returns: the {n_features} inputs are built from trade "
        "signs, sizes, times and trade-price moves, and the analysis measures no quotes, no "
        "spreads, no fees and no profit and loss. The repo's Q2 and Q5 show that price impact "
        "adjusts to the memory of order flow so that predictable signs do not make prices "
        "predictable, so a predictable sign is not a predictable return."
    )


def verdict_paragraph(result: dict) -> str:
    win = result["within_month"]
    med = win["median"]
    n = len(result["symbols"])
    lift_lin = _median_gap(win, "linear", "majority")
    lift_all = _median_gap(win, "gbm_all", "majority")
    learned = _median_gap(win, "gbm_all", "linear")
    head = (
        f"Across {n} symbol{'s' if n != 1 else ''} ({result['period']}, within-month test "
        f"days), median accuracy is {_f(med['majority']['accuracy'])} for the majority rule, "
        f"{_f(med['persistence']['accuracy'])} for persistence, {_f(med['linear']['accuracy'])} "
        f"for the linear filter implied by the autocorrelation and "
        f"{_f(med['gbm_all']['accuracy'])} for boosted trees on all features. The median lift "
        f"over the majority rule is {_f(lift_lin, signed=True)} for the linear rung and "
        f"{_f(lift_all, signed=True)} for gbm_all, so the learned model adds a median "
        f"{_f(learned, signed=True)} in accuracy over what the measured autocorrelation already "
        f"implies"
    )
    if lift_all > 0.005:
        head += f" ({100 * lift_lin / lift_all:.0f}% of the gbm_all lift is already in the linear rung)"
    head += (
        f". In log loss, the median skill relative to persistence is "
        f"{_f(med['linear']['skill_vs_persistence'])} for linear and "
        f"{_f(med['gbm_all']['skill_vs_persistence'])} for gbm_all."
    )
    body = [increment_sentence(result, i["key"]) for i in result["increments"]]
    return " ".join([head, *body, _holdout_sentence(result), _not_trading_sentence(result)])


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------


def _rung_table(block: dict, rungs: list[str], field: str, median_field: str) -> list[str]:
    lines = ["| symbol | n scored | " + " | ".join(rungs) + " |",
             "|---|---|" + "---|" * len(rungs)]
    for sym, ps in block["per_symbol"].items():
        if field == "skill_vs_persistence":
            vals = [ps["skill_vs_persistence"][r] for r in rungs]
        else:
            vals = [ps["scores"][r][field] for r in rungs]
        lines.append(f"| {sym} | {ps['scores']['gbm_all']['n']:,} | "
                     + " | ".join(_f(v) for v in vals) + " |")
    lines.append("| **median** | | "
                 + " | ".join(_f(block["median"][r][median_field]) for r in rungs) + " |")
    return lines


def _increment_table(result: dict, block: dict, metric: str) -> list[str]:
    incs = result["increments"]
    head = " | ".join(f"({INCREMENT_LETTERS[i['key']]}) {i['upper']} minus {i['lower']}"
                      for i in incs)
    lines = [f"| symbol | days | {head} |", "|---|---|" + "---|" * len(incs)]
    for sym, ps in block["per_symbol"].items():
        cells = [_ci(ps["increments"][i["key"]][metric]) for i in incs]
        n_days = ps["increments"][incs[0]["key"]][metric]["n_days"]
        lines.append(f"| {sym} | {n_days} | " + " | ".join(cells) + " |")
    pooled = [_ci(block["pooled"][i["key"]][metric]) for i in incs]
    lines.append(f"| **pooled** | {block['pooled_n_days']} | " + " | ".join(pooled) + " |")
    counts = [
        f"{block['increments_summary'][i['key']][metric]['n_positive']} above, "
        f"{block['increments_summary'][i['key']][metric]['n_negative']} below"
        for i in incs
    ]
    lines.append("| symbols with CI off zero | | " + " | ".join(counts) + " |")
    return lines


def _holdout_table(result: dict) -> list[str]:
    nxt, win = result["next_month"], result["within_month"]
    lines = [
        ("| symbol | linear acc (within) | linear acc (next) | gbm_all acc (within) | "
        "gbm_all acc (next) | linear loss (within) | linear loss (next) | "
        "gbm_all loss (within) | gbm_all loss (next) |"),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for sym in result["next_month_symbols"]:
        w, x = win["per_symbol"][sym]["scores"], nxt["per_symbol"][sym]["scores"]
        cells = [
            v[r][f] for f in ("accuracy", "log_loss_bits") for r in ("linear", "gbm_all")
            for v in (w, x)
        ]
        lines.append(f"| {sym} | " + " | ".join(_f(c) for c in cells) + " |")
    return lines


def _caveats(result: dict) -> list[str]:
    cfg = result["trial_log"]["configurations"][0]["config"]
    win = result["within_month"]["per_symbol"]
    ties = [ps["counts"]["tie_share"] for ps in win.values()]
    days = [ps["counts"]["n_test_days"] for ps in win.values()]
    capped = sum(
        ps["counts"]["n_train_scoreable"] > ps["counts"]["n_train_rows_used"]
        for ps in win.values()
    )
    sp = cfg["split_days"]
    return [
        (f"- **One training month per symbol.** Each ladder is fitted on the first "
        f"{sp['train']} days of {result['period']} only. The within-month test block has "
        f"{_range(min(days), max(days), 'd')} days, so each per-symbol interval rests on that many "
        "day blocks and is coarse; a percentile bootstrap over so few blocks tends to be "
        "too narrow. The next-month block has more days and is the stronger test."),
        ("- **Survivor symbols.** The symbols are liquid contracts chosen because they "
        "exist in all five downloaded months. Contracts that were delisted or listed later "
        "are absent, so nothing here speaks for thin or short-lived markets."),
        (f"- **Hyperparameters fixed in advance.** The LightGBM settings, the feature list and "
        f"the linear order ({cfg['linear_order']}) are the fixed values in "
        f"`microstructure.ml` and were not varied in this analysis. Only the boosting round count is tuned, by early stopping on the "
        f"{sp['valid']} validation days (patience {cfg['lgb_patience']}, at most "
        f"{cfg['lgb_max_rounds']} rounds). The trial log lists every configuration run. "
        "A pilot on SOLUSDT 2023-06 was run while the ladder was being built, so that "
        "symbol's within-month test block is not untouched."),
        (f"- **Training subsample cap.** The learned rungs train on a random subsample of at "
        f"most {cfg['train_cap']:,} scoreable training rows (validation at most "
        f"{cfg['valid_cap']:,}); the cap was binding for {capped} of {len(win)} symbols. The "
        "linear rung uses every training-day sign, which favors it slightly."),
        (f"- **Tie exclusion.** An event that shares a millisecond with the previous event is "
        f"never scored, because the order inside a tied millisecond is fixed by the sort "
        f"(sells first), not by the market. Tied events are "
        f"{_range(100 * min(ties), 100 * max(ties), '.1f')}% of events here. They still feed the features of later rows, "
        "and the scores describe untied events only."),
        ("- **Millisecond timestamps.** Timestamps are in milliseconds, so the true order of "
        "events inside one millisecond is unknown, and prints with the same millisecond and "
        "side are merged into one event. \"The next trade\" means the next such event."),
        ("- **Pooled intervals are event-weighted.** The pooled estimate sums each day's sums "
        "across symbols, so the busiest symbols dominate it; the per-symbol median is given "
        "alongside for that reason."),
        ("- **Trades only.** No quote data enters the features (quotes exist for 2023 only), "
        "so a model with the order book could do better or worse than these numbers."),
    ]


def _run_problems(result: dict) -> str:
    """Sentences for symbols that failed in this run or whose holdout cache is stale."""
    out = ""
    failures = result.get("failures") or []
    if failures:
        out += " Failed in this run and left out of the affected block: " + "; ".join(
            f"{f['symbol']} ({f['stage']} stage: {f['reason']})" for f in failures) + "."
    stale = result.get("next_month_stale_symbols") or []
    if stale:
        out += (" Next-month caches left out because they were scored with a ladder that has "
                f"since been refitted: {', '.join(stale)}.")
    return out


def write_markdown(path: Path, result: dict) -> None:
    win, nxt = result["within_month"], result["next_month"]
    rungs = result["rungs"]
    cfg = result["trial_log"]["configurations"][0]["config"]
    sp = cfg["split_days"]
    L: list[str] = ["# Q9: next-trade-sign prediction", "", "## Question", "", result["question"],
                    "", "## Method", ""]
    L += [
        (f"1. **Data and split.** For each symbol, the {result['period']} aggressor events are "
        f"split on whole UTC days: {sp['train']} train, {sp['valid']} validation, "
        f"{sp['embargo']} embargo, the rest test. Features for event i read only events "
        f"before i; the first {cfg['warmup_events']:,} events and every event tied in time "
        "with its predecessor are not scored."),
        ("2. **Ladder.** `majority` (training buy share), `persistence` (last sign), `linear` "
        f"(Yule-Walker filter of order {cfg['linear_order']} from the training sign "
        "autocorrelation), `logit_signs` and `gbm_signs` (logistic regression and LightGBM on "
        "sign-history features), `logit_all` and `gbm_all` (the same on sign history plus "
        "size, timing and trade-price moves)."),
        "3. **Increments.** " + "; ".join(
            f"({INCREMENT_LETTERS[i['key']]}) {i['upper']} minus {i['lower']}: {i['meaning']}"
            for i in result["increments"]) + ". Gains are signed so that positive is better: "
        "accuracy gained, or bits of log loss removed.",
        (f"4. **Intervals.** 95% percentile intervals from {result['n_boot']} resamples of whole "
        "UTC days, paired across rungs. The pooled interval sums each day's sums across "
        "symbols so a calendar day is one block."),
        ("5. **Lock-box.** The saved ladder is applied unchanged to every scoreable event of "
        f"{result['holdout_period'] or 'the next month (not run)'}."),
        "",
        "## Run summary",
        "",
        (f"Symbols with a fit cache: {len(result['symbols'])} ({', '.join(result['symbols'])}). "
        f"Without: {', '.join(result['symbols_without_cache']) or 'none'}. "
        f"Next-month caches: {len(result['next_month_symbols'])}."
        + _run_problems(result)),
        "",
        ("| symbol | events | train rows used | test rows | test days | tie share | "
        "gbm_all rounds | gamma (train days) |"),
        "|---|---|---|---|---|---|---|---|",
    ]
    for sym, ps in win["per_symbol"].items():
        c = ps["counts"]
        L.append(
            f"| {sym} | {c['n_events']:,} | {c['n_train_rows_used']:,} | {c['n_test_rows']:,} | "
            f"{c['n_test_days']} | {c['tie_share']:.4f} | "
            f"{result['trial_log']['gbm_best_iteration'][sym]['gbm_all']} | "
            f"{_f(ps['acf']['gamma'])} |"
        )
    L += ["", "## Results", "", "### Accuracy by rung (within-month test)", ""]
    L += _rung_table(win, rungs, "accuracy", "accuracy")
    L += ["", "### Log loss in bits by rung (within-month test; 1.0 is a coin flip)", ""]
    L += _rung_table(win, rungs, "log_loss_bits", "log_loss_bits")
    L += ["", "### Log-loss skill relative to persistence", "",
          ("Fraction of the persistence rung's log loss removed; negative is worse than "
          "persistence."), ""]
    L += _rung_table(win, rungs, "skill_vs_persistence", "skill_vs_persistence")
    above = [s for s, ps in win["per_symbol"].items()
             if ps["scores"]["persistence"]["log_loss_bits"] > 1.0]
    L += ["", (f"The persistence rung's own log loss is above the 1 bit of a coin flip for "
               f"{len(above)} of {len(win['per_symbol'])} symbols"
               + (f" ({', '.join(above)})" if above else "")
               + ". Where it is, the training repeat rate did not carry over to the test days "
               "and skill relative to persistence flatters every other rung; compare with the "
               "majority column.")]
    L += ["", "### Increments in accuracy (estimate [95% CI], within-month test)", ""]
    L += _increment_table(result, win, "accuracy")
    L += ["", "### Increments in log loss removed, bits (estimate [95% CI], within-month test)",
          ""]
    L += _increment_table(result, win, "log_loss")
    L += ["", f"### Within-month versus next month ({result['holdout_period']})", ""]
    if nxt is None:
        L.append("No next-month caches were found, so this comparison is not available.")
    else:
        L += _holdout_table(result)
        L += ["", "Increments on the next month, accuracy:", ""]
        L += _increment_table(result, nxt, "accuracy")
        L += ["", "Increments on the next month, log loss removed (bits):", ""]
        L += _increment_table(result, nxt, "log_loss")
    L += ["", "### Feature importance", "",
          ("Mean across symbols of each feature's share of total split gain in `gbm_all`, and "
          "the mean standardized coefficient in `logit_all`."), "",
          "| feature | mean gain share | mean logit coef | mean abs logit coef |",
          "|---|---|---|---|"]
    coef = result["feature_importance"]["logit_all_standardized_coef"]
    for feat, g in result["feature_importance"]["gbm_all_mean_gain_share"].items():
        L.append(f"| {feat} | {g:.4f} | {_f(coef[feat]['mean'], signed=True)} | "
                 f"{_f(coef[feat]['mean_abs'])} |")
    gr = result["gamma_relation"]
    L += ["", "### Memory strength and the linear rung", ""]
    la, mg = gr["linear_accuracy"], gr["memory_accuracy_gain"]
    if la["pearson"] is None:
        L.append(f"Only {la['n']} symbol(s) have a fitted gamma, too few for a correlation.")
    else:
        L.append(
            f"Across {la['n']} symbols, the correlation between the training-day sign-ACF "
            f"exponent gamma (lags {next(iter(win['per_symbol'].values()))['acf']['fit_lo']} "
            f"to {next(iter(win['per_symbol'].values()))['acf']['fit_hi']}, Q4's window) and "
            f"the linear rung's test accuracy is {_f(la['pearson'], 2, True)} (Pearson) and "
            f"{_f(la['spearman'], 2, True)} (Spearman); with the gain of linear over "
            f"persistence it is {_f(mg['pearson'], 2, True)} and {_f(mg['spearman'], 2, True)}. "
            f"A smaller gamma means slower decay, so a negative correlation means stronger "
            f"memory goes with a better linear forecast. With {la['n']} points this is "
            "descriptive only."
        )
    tl = result["trial_log"]
    L += ["", "### Trial log", "",
          f"{tl['n_distinct_configurations']} distinct configuration(s) were run, each fitting "
          f"{len(tl['fitted_models_per_configuration'])} models per symbol "
          f"({', '.join(tl['fitted_models_per_configuration'])}), {tl['n_model_fits']} model "
          f"fits in total. No hyperparameter grid was searched; the only quantity tuned on "
          f"validation data is the {tl['tuned_on_validation'][0]}. Fixed LightGBM parameters: "
          + ", ".join(f"`{k}={v}`" for k, v in cfg["lgb_params"].items())
          + f". Logistic regression: L2, C = {cfg['logistic']['C']}, standardized inputs. "
          "The full configuration is in the JSON under `trial_log`.",
          "", "## Verdict", "", result["verdict"], "", "## Caveats", ""]
    L += _caveats(result)
    path.write_text("\n".join(L) + "\n")


# --------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------


def _style(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(_MUTED)
    ax.tick_params(colors=_INK, labelsize=8)
    ax.grid(axis="y", color=_GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot(path: Path, result: dict) -> None:
    """Left: accuracy by rung, one line per symbol plus the median. Right: pooled
    increments with day-block CIs, one panel per metric (their units differ)."""
    win, nxt = result["within_month"], result["next_month"]
    rungs = result["rungs"]
    x = np.arange(len(rungs))
    fig = plt.figure(figsize=(13, 5.2))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.5, 1.0], hspace=0.45, wspace=0.22)
    ax = fig.add_subplot(gs[:, 0])
    for i, (_sym, ps) in enumerate(win["per_symbol"].items()):
        acc = [ps["scores"][r]["accuracy"] for r in rungs]
        ax.plot(x, acc, color=_MUTED, linewidth=1.0, marker="o", markersize=3, alpha=0.7,
                label="one symbol" if i == 0 else None)
    med = [win["median"][r]["accuracy"] for r in rungs]
    ax.plot(x, med, color=_BLUE, linewidth=2.0, marker="o", markersize=7,
            markeredgecolor="white", markeredgewidth=1.5, label="cross-symbol median")
    for xi, m in zip(x, med, strict=True):
        ax.annotate(f"{m:.3f}", (xi, m), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=8, color=_INK)
    ax.axhline(0.5, color=_MUTED, linestyle="--", linewidth=0.8)
    ax.set_xticks(x, rungs, rotation=20)
    ax.set_ylabel("accuracy on test days", fontsize=9, color=_INK)
    ax.set_title(f"Next-sign accuracy by rung, {result['period']} test days "
                 f"({len(result['symbols'])} symbol{'s' if len(result['symbols']) != 1 else ''})", fontsize=10, color=_INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    _style(ax)

    incs = result["increments"]
    xi = np.arange(len(incs))
    labels = [f"({INCREMENT_LETTERS[i['key']]}) {i['upper']}\nminus {i['lower']}" for i in incs]
    panels = (("accuracy", "accuracy gain"), ("log_loss", "log loss removed (bits)"))
    for row, (metric, ylabel) in enumerate(panels):
        a = fig.add_subplot(gs[row, 1])
        series = [(win, f"{result['period']} test days", _BLUE, "o", -0.1)]
        if nxt is not None:
            series.append((nxt, f"{result['holdout_period']} (frozen ladder)", _ORANGE, "s", 0.1))
        for block, label, color, marker, dx in series:
            est = np.array([block["pooled"][i["key"]][metric]["estimate"] for i in incs])
            lo = np.array([block["pooled"][i["key"]][metric]["ci95"][0] for i in incs])
            hi = np.array([block["pooled"][i["key"]][metric]["ci95"][1] for i in incs])
            off = xi + (dx if len(series) > 1 else 0.0)
            a.errorbar(off, est, yerr=[est - lo, hi - est], fmt=marker, color=color,
                       markersize=7, markeredgecolor="white", markeredgewidth=1.2,
                       elinewidth=2, capsize=3, label=label)
        a.axhline(0.0, color=_MUTED, linewidth=0.8)
        a.set_xticks(xi, labels if row == 1 else [""] * len(incs), fontsize=8)
        a.set_xlim(-0.5, len(incs) - 0.5)
        a.set_ylabel(ylabel, fontsize=9, color=_INK)
        if row == 0:
            a.set_title("Pooled increments, 95% day-block CI", fontsize=10, color=_INK,
                        loc="left")
            a.legend(frameon=False, fontsize=8)
        _style(a)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
