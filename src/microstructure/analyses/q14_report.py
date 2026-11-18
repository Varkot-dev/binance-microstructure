"""Q14 report writing: verdict, Markdown and the figure.

Everything here is a pure function of the result dict built by
`q14_survivorship.build_result` from the per-unit caches. Every verdict
sentence is computed from numbers in that dict, so the text cannot drift from
the tables.

Metric names: `gbm_all`, `linear`, `majority` and `persistence` are test-block
accuracies of those Q9 rungs; `lift` is gbm_all minus majority;
`gbm_minus_linear` is what the learned model adds over the autocorrelation's
linear filter; `linear_share` is the share of the lift already in the linear
rung.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_INK, _MUTED, _GRID = "#0b0b0b", "#8a8984", "#e4e3df"
_BLUE, _ORANGE, _AQUA = "#2a78d6", "#eb6834", "#1baf7a"

METRIC_LABEL = {
    "gbm_all": "gbm_all accuracy",
    "linear": "linear accuracy",
    "lift": "lift of gbm_all over majority",
    "gbm_minus_linear": "gbm_all minus linear",
}
COMPARISON_LABEL = {  # (group adjective, control adjective, month)
    "delisted_vs_survivors_2023": ("delisted", "survivor", "2023-06"),
    "renamed_merged_vs_survivors_2023": ("renamed or merged", "survivor", "2023-06"),
    "ended_vs_survivors_2023": ("ended", "survivor", "2023-06"),
    "new_vs_survivors_2026": ("crypto new-listing", "2023 survivor", "2026-07"),
}
STATE_WORD = {"positive": "above zero", "negative": "below zero", "zero": "includes zero"}
STATUS_LABEL = {
    "survivor": "survivor (all five study months)",
    "survivor_gap": "survivor with a gap (alive in 2026-07, misses a middle study month)",
    "relisted": "relisted (no 2026-07 file, a later one)",
    "delisted": "delisted",
    "renamed": "renamed or migrated",
    "merged": "merged into another token",
    "index": "index contract (not a coin, not fitted)",
    "new_listing": "new listing (first file after 2023-06)",
    "new_listing_equity": "new listing that trades like an equity perpetual (excluded)",
}


def _f(x, nd: int = 4, signed: bool = False) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{x:+.{nd}f}" if signed else f"{x:.{nd}f}"


def _ci(d: dict | None, nd: int = 4) -> str:
    if not d:
        return "n/a"
    return f"{d['estimate']:+.{nd}f} [{d['ci95'][0]:+.{nd}f}, {d['ci95'][1]:+.{nd}f}]"


def _ord(x: float) -> str:
    n = round(x)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _pp(x: float | None) -> str:
    """Accuracy difference in percentage points."""
    return "n/a" if x is None else f"{100 * x:+.2f} pp"


def _distinguishable(d: dict | None) -> str:
    if not d:
        return "not estimable"
    return ("not distinguishable from zero" if d["state"] == "zero"
            else f"distinguishable from zero, {'positive' if d['state'] == 'positive' else 'negative'}")


# --------------------------------------------------------------------------
# Verdict
# --------------------------------------------------------------------------


def comparison_sentence(result: dict, key: str, metric: str = "gbm_all") -> str:
    """Raw, activity-controlled and matched difference for one comparison."""
    c = result["comparisons"][key][metric]
    treat, ctrl, month = COMPARISON_LABEL[key]
    if c["raw"] is None:
        return (f"In {month}, {treat} ({c['n_treat']}) against {ctrl} contracts ({c['n_ctrl']}): too "
                f"few fitted contracts to compare {METRIC_LABEL[metric]}.")
    s = (f"In {month}, {treat} contracts ({c['n_treat']}) have a median "
         f"{METRIC_LABEL[metric]} of {_f(c['median_treat'])} against {_f(c['median_ctrl'])} "
         f"for {ctrl} contracts ({c['n_ctrl']}): a raw median difference of {_ci(c['raw'])}, "
         f"{_distinguishable(c['raw'])}. Controlling for activity (OLS on log10 events plus "
         f"a group dummy, HC1), the group difference is {_ci(c['ols'])}, "
         f"{_distinguishable(c['ols'])}; matched to the {ctrl} contract with the "
         f"nearest log events (with replacement), it is {_ci(c['matched'])}, "
         f"{_distinguishable(c['matched'])}.")
    raw_s, ols_s = c["raw"]["state"], c["ols"]["state"]
    if raw_s != "zero" and ols_s == "zero":
        s += (f" The raw gap goes away once activity is held fixed: {treat} contracts were "
              f"{'busier' if c['median_log10_events_treat'] > c['median_log10_events_ctrl'] else 'quieter'} "
              f"(median log10 events {_f(c['median_log10_events_treat'], 2)} against "
              f"{_f(c['median_log10_events_ctrl'], 2)}), and that accounts for it.")
    elif ols_s != "zero":
        word = "more" if ols_s == "positive" else "less"
        s += (f" At equal activity, {treat} contracts were {word} predictable than {ctrl} contracts by "
              f"this measure.")
    elif c["matched"]["state"] != "zero":
        word = "above" if c["matched"]["state"] == "positive" else "below"
        s += (f" Only the matched comparison excludes zero ({word}); the raw and regression "
              f"intervals include it, so a difference at equal activity is weak evidence that "
              f"depends on the method.")
    else:
        sign = "above" if c["ols"]["estimate"] > 0 else "below"
        s += (f" Neither raw nor at equal activity is there a difference the data can "
              f"distinguish; the controlled point estimate is {sign} zero by "
              f"{100 * abs(c['ols']['estimate']):.2f} pp.")
    return s


def paired_sentence(result: dict, metric: str = "gbm_all") -> str:
    p = result["paired_last_vs_2023"]["by_metric"][metric]
    if p["median"] is None:
        return (f"Only {p['n']} ended contracts have both a 2023-06 fit and a last-month fit, "
                "too few for a paired comparison.")
    return (f"Within the {p['n']} ended contracts with both fits, {METRIC_LABEL[metric]} in "
            f"the last complete month minus 2023-06 has a median of {_ci(p['median'])}, "
            f"{_distinguishable(p['median'])} ({p['n_up']} up, {p['n_down']} down; median "
            f"change in log10 events {_f(p['median_dlog10_events'], 2, True)}). At no change in "
            f"activity (intercept of the change on the change in log10 events, HC1) it is "
            f"{_ci(p['controlled'])}, {_distinguishable(p['controlled'])}, with a slope of "
            f"{_f(p['controlled']['slope_dlog10_events'], signed=True)} per decade of events.")


def paired_components_sentence(result: dict) -> str:
    """How the parts of the ladder moved between 2023-06 and the last month."""
    bm = result["paired_last_vs_2023"]["by_metric"]
    if bm["lift"]["median"] is None:
        return ""
    lift, lin, gap = bm["lift"], bm["linear"], bm["gbm_minus_linear"]
    months = sorted(r["period"] for r in result["paired_last_vs_2023"]["rows"])
    return (f"By rung, the median change in the lift over majority is {_ci(lift['median'])} "
            f"({_distinguishable(lift['median'])}), in linear accuracy {_ci(lin['median'])} "
            f"({_distinguishable(lin['median'])}) and in gbm_all minus linear "
            f"{_ci(gap['median'])} ({_distinguishable(gap['median'])}; {gap['n_down']} of "
            f"{gap['n']} contracts down), so by the last month a larger share of what is "
            f"predictable is already in the linear rung. Because the last months fall between "
            f"{months[0]} and {months[-1]}, this mixes the approach to the end with market-wide change "
            f"over those years.")


def representativeness(result: dict) -> tuple[str, float | None]:
    """'overstates', 'understates' or 'representative', and the gap."""
    m = result["q9_position"]["metrics"].get("gbm_all")
    if not m:
        return "unknown", None
    lo, hi = m["median_full"]["ci95"]
    gap = m["median_q9"] - m["median_full"]["estimate"]
    if m["median_q9"] > hi:
        return "overstates", gap
    if m["median_q9"] < lo:
        return "understates", gap
    return "representative", gap


def q9_sentence(result: dict) -> str:
    qp = result["q9_position"]
    m = qp["metrics"].get("gbm_all")
    if not m:
        return "The 2023-06 universe has too few fits to place Q9's symbols."
    word, gap = representativeness(result)
    ev = qp["metrics"]["log10_events"]
    pct_ev = float(np.median([r["pct_events_full"] for r in qp["rows"]]))
    s = (f"Q9's {len(qp['rows'])} symbols have a median gbm_all accuracy of "
         f"{_f(m['median_q9'])}; the median over all {qp['n_full']} fitted 2023-06 coins is "
         f"{_ci(m['median_full'])} (survivors only: {_f(m['median_survivors'])}). The Q9 median "
         f"sits at the {_ord(m['q9_median_pct_full'])} percentile of the full universe, and "
         f"the Q9 symbols' activity at a median {_ord(pct_ev)} percentile (median log10 events "
         f"{_f(ev['median_q9'], 2)} against {_f(ev['median_full']['estimate'], 2)}).")
    if word == "overstates":
        s += (f" Q9's 10-symbol headline overstates the typical contract: it is "
              f"{_pp(gap)} above the universe median, outside that median's interval.")
    elif word == "understates":
        s += (f" Q9's 10-symbol headline understates the typical contract: it is "
              f"{_pp(gap)} from the universe median, outside that median's interval.")
    else:
        s += (f" Q9's 10-symbol headline is representative of the typical contract: the gap "
              f"of {_pp(gap)} lies inside the universe median's interval.")
    lift = qp["metrics"].get("lift")
    if lift:
        s += (f" What the models add over the majority rule is typical, though: Q9's median "
              f"lift, {_f(lift['median_q9'])}, sits at the "
              f"{_ord(lift['q9_median_pct_full'])} percentile of the universe "
              f"(median {_ci(lift['median_full'])}).")
    if "activity_predicted_gap_gbm_all" in qp and gap:
        s += (f" The activity slope alone predicts a gap of "
              f"{_pp(qp['activity_predicted_gap_gbm_all'])} for that difference in activity.")
    return s


def activity_sentence(result: dict) -> str:
    a = result["activity_relation_2023"]
    if not a:
        return ""
    g, lf = a["gbm_all"], a["lift"]
    return (f"Across the 2023-06 universe, gbm_all accuracy changes by "
            f"{_f(g['slope'], signed=True)} per decade of events (HC1 se {_f(g['slope_se'])}, "
            f"R^2 {_f(g['r2'], 3)}, n {g['n']}) and the lift over majority "
            f"{_f(lf['slope'], signed=True)} (se {_f(lf['slope_se'])}, R^2 {_f(lf['r2'], 3)}): "
            f"busier contracts are {'less' if g['slope'] < 0 else 'more'} predictable, so "
            "activity is a confound that any group comparison has to hold fixed.")


def equity_sentence(result: dict) -> str:
    eq = result.get("equity_screen")
    if not eq:
        return ""
    flagged = eq["flagged"]
    if not flagged:
        return (f"None of the {eq['n_screened']} screened 2026-07 contracts trades like an "
                "equity perpetual.")
    names = ", ".join(f["symbol"] for f in flagged)
    return (f"{len(flagged)} of the {eq['n_screened']} screened 2026-07 contracts are flagged as "
            f"stock, ETF or commodity perpetuals (identified by ticker name, or by a timing "
            f"screen: median weekend day below {eq['rule']['weekend_ratio_below']:.2f} of the "
            f"median weekday, or a median weekday share of at least "
            f"{eq['rule']['us_session_median_at_least']:.2f} in the US cash session) and are "
            f"kept out of the crypto comparison: {names}. "
            f"{sum(1 for f in flagged if f['outcome'] == 'ok')} of them were fitted.")


def verdict_paragraph(result: dict) -> str:
    parts = [
        activity_sentence(result),
        comparison_sentence(result, "ended_vs_survivors_2023"),
        comparison_sentence(result, "delisted_vs_survivors_2023"),
        comparison_sentence(result, "renamed_merged_vs_survivors_2023"),
        paired_sentence(result),
        paired_components_sentence(result),
        equity_sentence(result),
        comparison_sentence(result, "new_vs_survivors_2026"),
        q9_sentence(result),
        ("None of this is a trading result: these are accuracies of next-sign calls on "
         "aggressor events, with no prices, costs or profit and loss."),
    ]
    return " ".join(p for p in parts if p)


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------

GROUP_COLS = ("n", "median_events", "median_majority", "median_persistence", "median_linear",
              "median_gbm_all", "median_lift", "median_linear_share", "median_gbm_minus_linear")


def _group_table(rows: list[tuple[str, dict]]) -> list[str]:
    L = [("| group | n | median events | majority | persistence | linear | gbm_all | "
          "lift over majority | share of lift in linear | gbm_all minus linear |"),
         "|---|---|---|---|---|---|---|---|---|---|"]
    for name, g in rows:
        if not g["n"]:
            L.append(f"| {name} | 0 | | | | | | | | |")
            continue
        L.append(
            f"| {name} | {g['n']} | {g['median_events']:,.0f} | {_f(g['median_majority'])} | "
            f"{_f(g['median_persistence'])} | {_f(g['median_linear'])} | "
            f"{_f(g['median_gbm_all'])} | {_f(g['median_lift'], signed=True)} | "
            f"{_f(g['median_linear_share'], 2)} | {_f(g['median_gbm_minus_linear'], signed=True)} |")
    return L


def _comparison_table(result: dict) -> list[str]:
    L = [("| comparison | metric | n (group, control) | median group | median control | "
          "raw median difference [95% CI] | activity-controlled OLS [95% CI] | "
          "matched on log events [95% CI] |"),
         "|---|---|---|---|---|---|---|---|"]
    for key, by_metric in result["comparisons"].items():
        treat, ctrl, month = COMPARISON_LABEL[key]
        for metric, c in by_metric.items():
            L.append(f"| {treat} vs {ctrl} contracts, {month} | {METRIC_LABEL[metric]} | "
                     f"{c['n_treat']}, {c['n_ctrl']} | {_f(c['median_treat'])} | "
                     f"{_f(c['median_ctrl'])} | {_ci(c['raw'])} | {_ci(c['ols'])} | "
                     f"{_ci(c['matched'])} |")
    return L


def _caveats(result: dict) -> list[str]:
    r = result["rules"]
    nl = result["universe"]["new_listings"]
    return [
        ("- **Survival is defined by the archive.** A contract counts as ended when "
         "data.binance.vision has no monthly file for it at or after 2026-07. The archive's "
         "last month is taken as the month the futures contract stopped; a contract delisted "
         "and relisted later (MDTUSDT) is kept out of both comparison groups."),
        ("- **Classification is hand-made.** Renamed, merged and index contracts are named in "
         "a constant in `q14_survivorship.py`; renamed successors were checked to start within "
         "two months in the inventory, but the reason a contract was delisted (low volume, "
         "project failure, exchange policy) is not known here."),
        ("- **Activity is one number.** The controlled comparisons hold log10 aggressor events "
         "in the month fixed, linearly (OLS) or by nearest neighbour. Tick size, price level, "
         "spread and the share of retail flow also differ across contracts and are not "
         "controlled; Q4b found tick size borderline for flip probability."),
        (f"- **The thinnest contracts are not scored.** A unit needs at least "
         f"{r['min_train_scoreable']:,} scoreable train rows, {r['min_valid_scoreable']:,} "
         f"validation rows and {r['min_test_rows']:,} test rows, and a complete month. Units "
         "below that are listed with their counts; if delisted contracts are thinner than "
         "survivors, the ones left are the busier ones, which biases the ended group toward "
         "survivor-like activity."),
        (f"- **New listings are a sample.** {len(nl['sample'])} of the {nl['n_frame']} "
         f"contracts first listed between 2023-07 and 2026-06 that are alive in 2026-07, "
         f"{nl['per_decile']} from each decile of 2026-07 zip size (seed {nl['seed']}); "
         f"{nl['n_listed_in_2026_07']} first listed in 2026-07 have no complete July and are "
         "outside the frame. Sampled contracts flagged as equity perpetuals are dropped from "
         "the crypto group after the draw, so it is smaller than the draw. Zip size is an activity proxy, so the draw is stratified on the "
         "confound but is not the full population."),
        ("- **Non-crypto contracts in 2026-07 are labelled by hand.** Stock, ETF and commodity "
         "perpetuals are identified by a review of the ticker names plus a trade-time screen; "
         "a crypto token on a ticker that happens to look like a stock, or an unrecognised "
         "stock contract that trades round the clock, could be misplaced. The flagged "
         "contracts are more predictable than either crypto group (see the 2026-07 table), so "
         "pooling them would have moved the new-listing comparison."),
        ("- **One month per unit, seven test days.** Each unit is one month with Q9's split, "
         "so a unit's accuracy rests on its 7 or so test days; across-symbol intervals treat "
         "each unit's number as exact and include only the between-contract spread."),
        ("- **Same ladder, many fits.** No setting was tuned for Q14: every unit uses Q9's "
         "default configuration (in the JSON under `rules.q9_config`); only the boosting round "
         "count is early-stopped per unit. Q9's own 2023-06 caches are reused for its 10 "
         "symbols when their configuration and ladder fingerprint match."),
        ("- **Calendar differences.** The last complete month of an ended contract falls "
         "between 2023 and 2026, so the paired change mixes approaching the end with market-wide "
         "change over time (Q8 and Q10 show the market changed between these years)."),
    ]


def write_markdown(path: Path, result: dict) -> None:
    uni = result["universe"]
    c23 = uni["contracts_2023_06"]
    nl = uni["new_listings"]
    r = result["rules"]
    by_status: dict[str, list[str]] = {}
    for s, e in c23.items():
        by_status.setdefault(e["status"], []).append(s)
    L = ["# Q14: survivorship in next-trade-sign prediction", "", "## Question", "",
         result["question"], "", "## Universe", "",
         (f"From the archive inventory (USDT-M monthly aggTrades, months up to "
          f"{uni['archive_last_month']}), {uni['n_perpetuals']} perpetuals (tickers ending in "
          f"USDT without an underscore). {len(c23)} have a 2023-06 file; {nl['n_total']} first "
          "appear after 2023-06 and are alive in 2026-07."), "",
         "| status in 2023-06 universe | contracts |", "|---|---|"]
    for st in ("survivor", "survivor_gap", "relisted", "renamed", "merged", "delisted", "index"):
        L.append(f"| {STATUS_LABEL[st]} | {len(by_status.get(st, []))} |")
    L += ["", "Survivors with a gap: " + "; ".join(
        f"{s} (missing {', '.join(c23[s]['missing_study_months'])})"
        for s in by_status.get("survivor_gap", [])) + ".",
        "", "Relisted: " + "; ".join(
            f"{s} (last file {', '.join(g['after'] for g in c23[s]['gaps'])}, back in "
            f"{', '.join(g['resumes'] for g in c23[s]['gaps'])})"
            for s in by_status.get("relisted", [])) + ". The brief listed MDTUSDT as alive in "
        "2026-07 with a gap; the inventory has no 2026-07 file for it, so it is treated as a "
        "contract that stopped and came back and is left out of both comparison groups. The "
        "2026-10 MDTUSDT trades near 93, as a stock-token perpetual on the reused ticker, so "
        "it is not the same contract in any case.",
        "", "Renamed or migrated (successor verified in the inventory):", "",
        "| contract | last file | successor | successor first file | lag (months) |",
        "|---|---|---|---|---|"]
    for s in by_status.get("renamed", []):
        e = c23[s]
        L.append(f"| {s} | {e['last_month']} | {e['successor']} | {e['successor_first_month']} | "
                 f"{e['successor_lag_months']} |")
    L += ["", "Merged: " + "; ".join(f"{s} into {c23[s]['successor']} (last file "
                                     f"{c23[s]['last_month']})"
                                     for s in by_status.get("merged", [])) + ".",
          "", "Index contracts (listed, not fitted): " + ", ".join(
              f"{s} (last file {c23[s]['last_month']})" for s in by_status.get("index", [])) + ".",
          "", "Delisted (last archive file): " + ", ".join(
              f"{s} ({c23[s]['last_month']})" for s in by_status.get("delisted", [])) + ".",
          "", (f"New-listing sample: the frame is the {nl['n_frame']} new listings first listed "
               f"before 2026-07 ({nl['frame_zip_gb']:.1f} GB of 2026-07 zips); {nl['n_listed_in_2026_07']}"
               f" first listed in 2026-07 are outside it. {nl['per_decile']} were drawn from "
               f"each decile of 2026-07 zip size with seed {nl['seed']} "
               f"({len(nl['sample'])} in all; the list is in the JSON under "
               "`universe.new_listings.sample`). Decile edges in MB: "
               + ", ".join(f"{x / 1e6:.1f}" for x in nl["decile_edges_zip_bytes"]) + "."),
          "", "## Method", "",
          ("1. **Units.** A unit is one symbol-month. Q9's within-month ladder (fit stage "
           "only) is fitted on each with Q9's defaults: 20 train days, 2 validation, 1 "
           "embargo, the rest test; train cap 2,000,000 rows; linear order 1000; LightGBM "
           "settings as in Q9. Three sets: every 2023-06 coin; the last complete month of "
           "every contract that stopped trading; and 2026-07 for the 2023 contracts alive then "
           "plus the new-listing sample."),
          (f"2. **Complete month.** A month is complete when the contract traded on its first "
           f"and last UTC day and on all days in between but at most {r['max_missing_days']}. "
           "A 2023-06 or 2026-07 unit that is not complete is skipped and listed."),
          (f"3. **Last complete month.** Starting from the contract's last archive month, walk "
           f"back until a complete month is found, trying at most {r['last_month_max_back']} "
           "months. A delisting usually happens mid-month, so the last archive file is "
           "typically partial; the zip size of each candidate is reported next to its "
           "coverage, but the decision uses the trading days in the data, not the size."),
          (f"4. **Minimum activity.** A complete unit is fitted only with at least "
           f"{r['min_train_scoreable']:,} scoreable train rows (LightGBM with 63 leaves of at "
           f"least 500 rows needs about 31,500 to grow a full tree), {r['min_valid_scoreable']:,}"
           f" validation rows and {r['min_test_rows']:,} test rows (a binomial standard error "
           "of at most 0.005 on one unit's accuracy). Units below that are skipped and listed."),
          (f"5. **Comparisons.** Symbols are the resampling unit. Raw differences are "
           f"differences of group medians with a {r['n_boot']}-resample bootstrap of symbols "
           "within each group. The activity-controlled difference is the dummy coefficient in "
           "an OLS of the metric on log10 events and a group dummy, with an HC1 interval. The "
           "matched difference pairs each group contract with the control contract with the "
           "nearest log10 events, with replacement, and averages the differences; its "
           "interval resamples both groups and rematches each time. The paired last-month "
           "change uses the same contracts' 2023-06 fits, with the intercept of the change on "
           "the change in log10 events as the change at equal activity."), "",
          "## Run summary", "",
          "| set | status | outcomes |", "|---|---|---|"]
    for key, c in result["outcome_counts"].items():
        s, st = key.split(":")
        L.append(f"| {s} | {st} | " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())) + " |")
    reused = sum(1 for u in result["units"] if u.get("reused_q9_cache"))
    L += ["", f"Q9's own fit caches reused: {reused}.", "", "## Results", "",
          "### 2023-06 cross-section", ""]
    g = result["groups"]
    L += _group_table([(k, v) for k, v in g["cross_2023"].items()]
                      + [("full universe (all fitted coins)", g["cross_2023_full"]),
                         ("Q9's 10 symbols", g["cross_2023_q9"])])
    L += ["", "### Last complete month of ended contracts", ""]
    L += _group_table(list(g["last_month"].items()))
    L += ["", "### 2026-07 cross-section", ""]
    L += _group_table(list(g["cross_2026"].items()))
    eq = result.get("equity_screen")
    if eq:
        r_ = eq["rule"]
        lo, hi = r_["us_session_utc_minutes"]
        L += ["", "### Equity-perpetual screen (2026-07)", "",
              ("Binance listed perpetuals on stock tokens in 2026, some on reused crypto "
               "tickers. A unit is flagged as equity-like when its median UTC weekend day has "
               f"fewer than {r_['weekend_ratio_below']:.2f} times the events of its median "
               f"weekday, or when on the median weekday at least "
               f"{r_['us_session_median_at_least']:.2f} of the day's events fall in the US cash "
               f"session ({lo // 60:02d}:{lo % 60:02d} to {hi // 60:02d}:{hi % 60:02d} UTC; a "
               "flat round-the-clock day puts 0.27 there). Medians over days keep a few burst "
               "days from deciding it: COTIUSDT, a crypto coin, had 5 pump weekdays in 2026-07 "
               "that pushed its plain monthly weekend share to 0.01. Screened: "
               f"{eq['n_screened']} of {eq['n_cross_2026']} 2026-07 units. Timing alone does not "
               "separate the groups (BTCUSDT has a weekend ratio of 0.53; thin ETF contracts "
               "such as EWZUSDT reach 0.85), so the primary label is a review of the ticker "
               "names for stocks, ETFs and commodities, and the strict timing cuts above, which "
               "flag no known crypto contract, are a cross-check for names the review did not "
               "recognise. A unit is excluded if either label flags it. "
               f"Flagged: {len(eq['flagged'])}. Flagged units are summarised as their own row "
               "and left out of every comparison."), ""]
        sess = [u for u in result["units"] if u["set"] == "cross_2026" and u.get("session")]
        for grp, keep in (
                ("2023 survivors, not flagged", lambda u: not u["status_2023"].startswith("new")
                 and not u.get("equity_like")),
                ("crypto new listings", lambda u: u["status_2023"] == "new_listing"),
                ("flagged contracts", lambda u: u.get("equity_like"))):
            w = [u["session"]["weekend_ratio"] for u in sess if keep(u)
                 and u["session"].get("weekend_ratio") is not None]
            us = [u["session"]["us_session_median"] for u in sess if keep(u)
                  and u["session"].get("us_session_median") is not None]
            if w:
                L.append(f"- {grp}: weekend ratio {min(w):.3f} to {max(w):.3f} (median "
                         f"{np.median(w):.3f}); median-weekday US-session share "
                         f"{min(us):.3f} to {max(us):.3f} (median {np.median(us):.3f}).")
        if eq["flagged"]:
            L += ["", ("| contract | outcome | weekend ratio | US-session share (median "
                       "weekday) | flagged by timing screen | identified by name |"),
                  "|---|---|---|---|---|---|"]
            for f in eq["flagged"]:
                L.append(f"| {f['symbol']} | {f['outcome']} | {_f(f.get('weekend_ratio'), 3)} | "
                         f"{_f(f.get('us_session_median'), 3)} | "
                         f"{'yes' if f['by_screen'] else 'no'} | {f['by_name'] or 'no'} |")
    L += ["", "### Group comparisons", "",
          ("Positive means the first group is more predictable (accuracy) or has the larger "
           "lift. Accuracy differences are in accuracy units (0.01 is one percentage point)."),
          ""]
    L += _comparison_table(result)
    p = result["paired_last_vs_2023"]
    L += ["", "### Last complete month against 2023-06, same contracts", "",
          ("| metric | n | median change [95% CI] | mean change [95% CI] | change at equal "
           "activity [95% CI] | slope per decade of events | up, down |"),
          "|---|---|---|---|---|---|---|"]
    for metric, c in p["by_metric"].items():
        if c["median"] is None:
            L.append(f"| {METRIC_LABEL[metric]} | {c['n']} | n/a | n/a | n/a | n/a | |")
            continue
        L.append(f"| {METRIC_LABEL[metric]} | {c['n']} | {_ci(c['median'])} | {_ci(c['mean'])} | "
                 f"{_ci(c['controlled'])} | {_f(c['controlled']['slope_dlog10_events'], signed=True)}"
                 f" | {c['n_up']}, {c['n_down']} |")
    for grp, c in p["by_group"].items():
        if c["median"] is not None:
            L.append(f"| gbm_all accuracy, {grp} only | {c['n']} | {_ci(c['median'])} | "
                     f"{_ci(c['mean'])} | {_ci(c['controlled'])} | "
                     f"{_f(c['controlled']['slope_dlog10_events'], signed=True)} | "
                     f"{c['n_up']}, {c['n_down']} |")
    L += ["", ("| contract | last complete month | events 2023-06 | events last month | "
               "gbm_all 2023-06 | gbm_all last | lift 2023-06 | lift last |"),
          "|---|---|---|---|---|---|---|---|"]
    for row in sorted(p["rows"], key=lambda x: x["symbol"]):
        L.append(f"| {row['symbol']} | {row['period']} | {row['events_2023']:,} | "
                 f"{row['events_last']:,} | {_f(row['gbm_all_2023'])} | {_f(row['gbm_all_last'])} | "
                 f"{_f(row['lift_2023'], signed=True)} | {_f(row['lift_last'], signed=True)} |")
    qp = result["q9_position"]
    L += ["", "### Where Q9's 10 symbols sit (2023-06)", "",
          (f"Percentile ranks within the {qp['n_survivors']} fitted survivors and the "
           f"{qp['n_full']} fitted coins of the full universe."), "",
          ("| symbol | events | gbm_all | events pct (survivors) | events pct (full) | "
           "gbm_all pct (survivors) | gbm_all pct (full) |"), "|---|---|---|---|---|---|---|"]
    for row in sorted(qp["rows"], key=lambda x: -x["n_events"]):
        L.append(f"| {row['symbol']} | {row['n_events']:,} | {_f(row['gbm_all'])} | "
                 f"{row['pct_events_survivors']:.0f} | {row['pct_events_full']:.0f} | "
                 f"{row['pct_gbm_all_survivors']:.0f} | {row['pct_gbm_all_full']:.0f} |")
    L += ["", ("| metric | median, Q9's 10 | median, full universe [95% CI] | "
               "median, survivors | Q9 median's percentile in full | "
               "share of full below Q9 median |"),
          "|---|---|---|---|---|---|"]
    for metric, m in qp["metrics"].items():
        nd = 2 if metric == "log10_events" else 4
        L.append(f"| {METRIC_LABEL.get(metric, metric)} | {_f(m['median_q9'], nd)} | "
                 f"{_ci(m['median_full'], nd)} | {_f(m['median_survivors'], nd)} | "
                 f"{m['q9_median_pct_full']:.0f} | {m['share_full_below_q9_median']:.2f} |")
    L += ["", "### Predictability and activity", "",
          "OLS of each metric on log10 events across the full 2023-06 universe (HC1 se).", "",
          "| metric | slope per decade | se | R^2 | n |", "|---|---|---|---|---|"]
    for metric, a in result["activity_relation_2023"].items():
        L.append(f"| {METRIC_LABEL[metric]} | {_f(a['slope'], signed=True)} | {_f(a['slope_se'])} | "
                 f"{_f(a['r2'], 3)} | {a['n']} |")
    for grp, a in result["activity_relation_2026"].items():
        L.append(f"| gbm_all accuracy, 2026-07 {grp} | {_f(a['slope'], signed=True)} | "
                 f"{_f(a['slope_se'])} | {_f(a['r2'], 3)} | {a['n']} |")
    L += ["", "### Last complete month: how it was chosen", "",
          "| contract | last archive month | candidates checked (zip MB: outcome) | chosen |",
          "|---|---|---|---|"]
    for sym, lm in sorted(result["last_month_resolution"].items()):
        att = "; ".join(
            f"{a['period']} ({(a['zip_bytes'] or 0) / 1e6:.1f}: {a['status']}"
            + (f", {a['coverage']['n_days']} of {a['coverage']['days_in_month']} days"
               if a.get("coverage") else "") + ")"
            for a in lm["attempts"])
        L.append(f"| {sym} | {lm['archive_last_month']} | {att or 'none'} | "
                 f"{lm['chosen'] or 'none'} |")
    L += ["", "### Units not fitted", "",
          "Every planned unit that did not produce a fit, with its event count and reason.", "",
          "| set | contract | status | month | events | outcome | reason |",
          "|---|---|---|---|---|---|---|"]
    n_not = 0
    for u in result["units"]:
        if u["outcome"] == "ok":
            continue
        n_not += 1
        ev = f"{u['counts']['n_events']:,}" if u.get("counts") else "n/a"
        L.append(f"| {u['set']} | {u['symbol']} | {u['status_2023']} | {u['period'] or 'n/a'} | "
                 f"{ev} | {u['outcome']} | {u['reason'] or ''} |")
    if n_not == 0:
        L.append("| | none | | | | | |")
    L += ["", "## Verdict", "", result["verdict"], "", "## Caveats", ""]
    L += _caveats(result)
    L += ["", "## Appendix: every fitted unit", "",
          ("| set | contract | status | month | events | majority | persistence | linear | "
           "gbm_all | lift |"), "|---|---|---|---|---|---|---|---|---|---|"]
    for u in result["units"]:
        if "metrics" not in u:
            continue
        m = u["metrics"]
        L.append(f"| {u['set']} | {u['symbol']} | {u['status_2023']} | {u['period']} | "
                 f"{m['n_events']:,} | {_f(m['majority'])} | {_f(m['persistence'])} | "
                 f"{_f(m['linear'])} | {_f(m['gbm_all'])} | {_f(m['lift'], signed=True)} |")
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
    ax.grid(color=_GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _fitted(result: dict, set_name: str, statuses: tuple[str, ...]) -> list[dict]:
    return [u for u in result["units"] if u["set"] == set_name
            and u["status_2023"] in statuses and "metrics" in u]


def _scatter(ax, units, color, marker, label, size=26, ring=False):
    if not units:
        return
    x = [u["metrics"]["log10_events"] for u in units]
    y = [u["metrics"]["gbm_all"] for u in units]
    if ring:
        ax.scatter(x, y, s=size, facecolors="none", edgecolors=color, linewidths=1.6,
                   label=label, zorder=4)
    else:
        ax.scatter(x, y, s=size, color=color, marker=marker, edgecolors="white",
                   linewidths=0.8, label=label, zorder=3, alpha=0.9)


def _fit_line(ax, units, color, style="-"):
    if len(units) < 3:
        return
    x = np.array([u["metrics"]["log10_events"] for u in units])
    y = np.array([u["metrics"]["gbm_all"] for u in units])
    b, a = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 10)
    ax.plot(xs, a + b * xs, color=color, linewidth=2, linestyle=style, zorder=2)


def plot(path: Path, result: dict) -> None:
    """(a) 2023-06 accuracy against activity by survival group, Q9's symbols
    ringed; (b) 2026-07 new listings against 2023 survivors; (c) last complete
    month against 2023-06 for the same ended contracts."""
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    ax = axes[0]
    surv = _fitted(result, "cross_2023", ("survivor", "survivor_gap"))
    deli = _fitted(result, "cross_2023", ("delisted",))
    ren = _fitted(result, "cross_2023", ("renamed", "merged"))
    _scatter(ax, surv, _MUTED, "o", f"survivors ({len(surv)})")
    _scatter(ax, deli, _ORANGE, "s", f"delisted ({len(deli)})")
    _scatter(ax, ren, _AQUA, "^", f"renamed or merged ({len(ren)})", size=36)
    q9 = [u for u in surv if u.get("q9_symbol")]
    _scatter(ax, q9, _BLUE, "o", f"Q9's symbols ({len(q9)})", size=70, ring=True)
    _fit_line(ax, surv, _MUTED)
    _fit_line(ax, deli + ren, _ORANGE, "--")
    ax.set_xlabel("log10 aggressor events in the month", fontsize=9, color=_INK)
    ax.set_ylabel("gbm_all accuracy on test days", fontsize=9, color=_INK)
    ax.set_title("(a) 2023-06: survivors vs contracts that later ended", fontsize=10,
                 color=_INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    _style(ax)

    ax = axes[1]
    old = _fitted(result, "cross_2026", ("survivor", "survivor_gap"))
    new = _fitted(result, "cross_2026", ("new_listing",))
    _scatter(ax, old, _MUTED, "o", f"2023 survivors ({len(old)})")
    _scatter(ax, new, _ORANGE, "s", f"crypto new listings, sample ({len(new)})")
    eqs = _fitted(result, "cross_2026", ("new_listing_equity", "survivor_equity",
                                          "survivor_gap_equity"))
    _scatter(ax, eqs, _AQUA, "^", f"stock, ETF or commodity, excluded ({len(eqs)})", size=36)
    _fit_line(ax, old, _MUTED)
    _fit_line(ax, new, _ORANGE, "--")
    ax.set_xlabel("log10 aggressor events in the month", fontsize=9, color=_INK)
    ax.set_title("(b) 2026-07: crypto listed after 2023 vs 2023 survivors", fontsize=10,
                 color=_INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    _style(ax)

    ax = axes[2]
    rows = result["paired_last_vs_2023"]["rows"]
    ren_syms = {u["symbol"] for u in ren}
    for grp, color, marker in (("delisted", _ORANGE, "s"), ("renamed or merged", _AQUA, "^")):
        sel = [r for r in rows if (r["symbol"] in ren_syms) == (grp != "delisted")]
        if sel:
            ax.scatter([r["gbm_all_2023"] for r in sel], [r["gbm_all_last"] for r in sel],
                       color=color, marker=marker, s=34, edgecolors="white", linewidths=0.8,
                       label=f"{grp} ({len(sel)})", zorder=3)
    if rows:
        v = [r["gbm_all_2023"] for r in rows] + [r["gbm_all_last"] for r in rows]
        lo, hi = min(v) - 0.01, max(v) + 0.01
        ax.plot([lo, hi], [lo, hi], color=_MUTED, linewidth=1, linestyle="--", zorder=1)
        ax.text(hi - 0.002, hi - 0.006, "no change", fontsize=8, color=_MUTED, ha="right",
                va="top", rotation=45, rotation_mode="anchor")
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
    ax.set_xlabel("gbm_all accuracy, 2023-06", fontsize=9, color=_INK)
    ax.set_ylabel("gbm_all accuracy, last complete month", fontsize=9, color=_INK)
    ax.set_title("(c) Ended contracts: last complete month vs 2023-06", fontsize=10,
                 color=_INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
