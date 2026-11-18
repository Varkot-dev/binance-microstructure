"""Q16 report writing: verdict, Markdown and the figure.

Everything here is a pure function of the result dict built by
`q16_delisting.build_result` from Part B's saved outputs. Every verdict
sentence is computed from numbers in that dict, so the text cannot drift from
the tables. Nothing is estimated here.

Keys: `base_a` falling volume, `base_b` lowest volume rank (the baseline every
model must beat), `logit_c` b0's three-feature logistic, `logit_full` and
`gbm_full` the full-feature models frozen for the lock-box, `logit_vol` and
`gbm_vol` the same models on volume features only.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

_INK, _MUTED, _GRID = "#0b0b0b", "#52514e", "#e4e3df"
_BLUE, _ORANGE = "#2a78d6", "#eb6834"
VARIANTS = ("main", "drop final full month")
VARIANT_LABEL = {"main": "final full month kept",
                 "drop final full month": "final full month dropped"}
VARIANT_COLOR = {"main": _BLUE, "drop final full month": _ORANGE}
NAME = {
    "base_a": "(a) falling volume",
    "base_b": "(b) lowest volume rank",
    "logit_c": "(c) logistic, 3 features",
    "logit_full": "logistic, full features",
    "gbm_full": "LightGBM, full features",
    "logit_vol": "logistic, volume only",
    "gbm_vol": "LightGBM, volume only",
}
PLOT_KEYS = ("base_a", "base_b", "logit_full", "gbm_full")
STANDING_PHRASE = {
    "beats": "beats the baseline",
    "ahead": "is ahead but not decisively",
    "not": "does not beat the baseline",
}


# --------------------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------------------

def _ci(d: dict, nd: int = 3, signed: bool = False) -> str:
    f = f"{{:+.{nd}f}}" if signed else f"{{:.{nd}f}}"
    lo, hi = d["ci95"]
    return f"{f.format(d['estimate'])} [{f.format(lo)}, {f.format(hi)}]"


def _sd(d: dict, nd: int = 3) -> str:
    return _ci(d, nd, signed=True)


def _pct(x: float, nd: int = 1) -> str:
    return f"{100 * x:.{nd}f}%"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out + [""]


def standing(d: dict) -> str:
    """'beats' if the paired interval is above 0, 'ahead' if only the point is, else 'not'."""
    if d["ci95"][0] > 0:
        return "beats"
    return "ahead" if d["estimate"] > 0 else "not"


def phrase(d: dict) -> str:
    return STANDING_PHRASE[standing(d)]


# --------------------------------------------------------------------------------------
# Verdict (assembled from computed fields)
# --------------------------------------------------------------------------------------

def _lb(result: dict, v: str) -> dict:
    return result["lockbox"]["variants"][v]


def gain_share(result: dict) -> float | None:
    main = _lb(result, "main")["diffs_vs_b"]["logit_full"]["prec"]["estimate"]
    fair = _lb(result, "drop final full month")["diffs_vs_b"]["logit_full"]["prec"]["estimate"]
    return (1 - fair / main) if main > 0 else None


def _share_words(share: float | None) -> str:
    if share is None:
        return ("the comparison of the two runs gives no share, since the main-run gain "
                "is not positive")
    if share >= 0.5:
        size = "more than half"
    elif share > 0:
        size = "less than half"
    else:
        size = "none"
    return (f"{_pct(max(share, 0.0), 0)} of the main-run gain, {size}, disappears when "
            "that month is dropped")


def _extra_words(result: dict) -> str:
    """What the extra features add on the fair test, with the CV sign as a check."""
    fair = _lb(result, "drop final full month")["diffs_vs_b"]["logit_full"]["prec"]
    cv = result["cv"]["drop final full month"]["diffs_vs_b"]["logit_full"]["prec"]
    same = (fair["estimate"] > 0) == (cv["estimate"] > 0)
    sign = ("with the same sign in CV and the lock-box" if same
            else "with opposite signs in CV and the lock-box")
    st = standing(fair)
    if st == "beats":
        return f"the extra features add an edge that holds without the announcement month, {sign}"
    if st == "ahead":
        return (f"the extra features add an edge {sign}, but its size is not established "
                "once the announcement month is removed")
    return "the extra features add nothing measurable once the announcement month is removed"


def verdict_paragraph(result: dict) -> str:
    cfg = result["config"]
    m, f = _lb(result, "main"), _lb(result, "drop final full month")
    cvm, cvf = result["cv"]["main"], result["cv"]["drop final full month"]
    dm, df = m["diffs_vs_b"]["logit_full"], f["diffs_vs_b"]["logit_full"]
    cm, cf = m["candidates"], f["candidates"]
    head = (f"**On the fair test (final full month dropped), the frozen full-feature logistic "
            f"model {phrase(df['prec'])}.**")
    s1 = (f"The baseline is the lowest-volume-rank rule (b), and the headline metric is "
          f"precision among the top {cfg['alert_rate'] * 100:g}% of live contracts each month "
          f"on the 2026 lock-box ({m['n_rows']:,} contract-months over {m['n_months']} origin "
          f"months, {m['event_lives']} delisted contracts, base rate "
          f"{_pct(m['base']['estimate'])}).")
    s2 = (f"With the final full month before the last trading day kept, the logistic model "
          f"{phrase(dm['prec'])}: {cm['logit_full']['prec']['estimate']:.3f} against "
          f"{cm['base_b']['prec']['estimate']:.3f}, paired difference {_sd(dm['prec'])}.")
    s3 = (f"With that month dropped, since it often holds the delisting announcement, it "
          f"{phrase(df['prec'])}: {cf['logit_full']['prec']['estimate']:.3f} against "
          f"{cf['base_b']['prec']['estimate']:.3f}, paired difference {_sd(df['prec'])} "
          f"(PR-AUC difference {_sd(df['ap'])}); {_share_words(gain_share(result))}.")
    s4 = (f"In cross-validation ({cvm['n_months']} test months, {cfg['first_test']} to 2025-12) "
          f"the same model {phrase(cvm['diffs_vs_b']['logit_full']['prec'])} with the month "
          f"kept ({_sd(cvm['diffs_vs_b']['logit_full']['prec'])}) and "
          f"{phrase(cvf['diffs_vs_b']['logit_full']['prec'])} without it "
          f"({_sd(cvf['diffs_vs_b']['logit_full']['prec'])}).")
    g = f["diffs_vs_b"]["gbm_full"]["prec"]
    s5 = (f"LightGBM on the same features {phrase(g)} on the fair lock-box test "
          f"({_sd(g)}), and the falling-volume rule (a) stays near chance "
          f"({cf['base_a']['prec']['estimate']:.3f} against a base rate of "
          f"{f['base']['estimate']:.3f}).")
    mult = cf["base_b"]["prec"]["estimate"] / f["base"]["estimate"]
    grp = cvm["shap"]["groups"][0]
    s6 = (f"So a contract's own monthly trading does flag likely delistings, mostly through "
          f"its volume rank (rule (b) alone reaches {mult:.1f} times the base rate on the fair "
          f"lock-box test) and its open-interest rank ({grp['group']} is "
          f"{grp['share']} of the tree model's attributions); {_extra_words(result)}.")
    return f"{head} {s1} {s2} {s3} {s4} {s5} {s6}"


# --------------------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------------------

def _cand_rows(block: dict, keys: tuple[str, ...]) -> list[list[str]]:
    rows = []
    for k in keys:
        c = block["candidates"][k]
        rows.append([NAME[k], _ci(c["prec"]), _ci(c["rec"]), f"{c['hits']}/{c['alerts']}",
                     _ci(c["ap"])])
    return rows


def hazard_sentence(result: dict) -> str:
    cv = result["cv"]
    clear = {v: {h["feature"]: h for h in cv[v]["hazard"] if h["lo"] > 1 or h["hi"] < 1}
             for v in VARIANTS}
    both = [f for f in clear["main"] if f in clear["drop final full month"]]
    never = [h["feature"] for h in cv["main"]["hazard"]
             if all(h["feature"] not in clear[v] for v in VARIANTS)]
    parts = [f"{f} {clear['main'][f]['or']:.2f} and "
             f"{clear['drop final full month'][f]['or']:.2f}" for f in both]
    txt = ("Odds ratios per SD with an interval clear of 1 in both runs (kept, dropped): "
           + ("; ".join(parts) if parts else "none") + ". ")
    if "qv_rank_pct" in both:
        txt += "A higher volume rank cuts the hazard: small coins die. "
    txt += ("Intervals covering 1 in both runs, once the rest is in the model: "
            + (", ".join(never) if never else "none") + ".")
    if "dlog_qv_3m" in never:
        txt += (" The 3-month volume change is among them, which is why the classic "
                "falling-volume rule (a) is near chance.")
    return txt


def _caveats(result: dict) -> list[str]:
    fa = result["facts"]
    lb = fa["lockbox_batches"]
    m = _lb(result, "main")
    f = _lb(result, "drop final full month")
    br = m.get("brier", {})
    lk = fa["leakage"]
    nblocks = m["n_months"] - result["config"]["boot_block"] + 1
    ratios = [_lb(result, v)["candidates"][k]["prec"]["estimate"]
              / result["cv"][v]["candidates"][k]["prec"]["estimate"]
              for v in VARIANTS for k in PLOT_KEYS
              if result["cv"][v]["candidates"][k]["prec"]["estimate"] > 0]
    out = [
        (f"- **No announcement dates.** Binance announces a futures delisting about 5 to 10 "
         f"days before settlement, and the announcement moves price and volume. The panel "
         f"has no announcement date per contract, so the fair run drops the whole final full "
         f"month instead ({lk['final_full_month_pos']} of {fa['panel']['pos']} positive rows; "
         f"{lk['lockbox_final_full_month_pos']} of {lk['lockbox_pos']} in the lock-box). That "
         "removes some genuine pre-announcement signal along with the leak, and keeps any "
         "announcement that falls earlier than the final full month. The true cut needs the "
         "announcement times."),
        (f"- **Batched delistings, few independent months.** The {lb['event_lives']} lock-box "
         f"delistings stopped on {lb['stop_days']} distinct days in {lb['stop_months']} "
         f"calendar months, and {lb['pos_in_first_quarter']} of the {lk['lockbox_pos']} "
         f"positive rows sit in origins 2026-01 to 2026-03. A life is positive at L-3, L-2 and "
         f"L-1, so rows are not independent. The month block bootstrap has only {nblocks} "
         f"distinct 3-month blocks over {m['n_months']} months, so the lock-box intervals are "
         "rough and probably too narrow; the leave-one-month-out ranges are a check, not a "
         "frozen metric."),
        (f"- **The lock-box was not perfectly untouched.** {lb['seen_in_last_cv_block']} of the "
         f"{lb['event_lives']} lock-box delistings were already positives in the last CV block "
         f"(origins {lb['last_cv_block'][0]} to {lb['last_cv_block'][1]}, whose label windows "
         "reach into 2026). No lock-box training row contains them (training stops at "
         f"t = {result['lockbox']['frozen']['main']['last_train_month']}), but the choice of "
         "the logistic model as a candidate was made after seeing CV results that counted "
         "those deaths."),
    ]
    if br:
        fb = f.get("brier", {})
        out.append(
            f"- **Scores rank, they are not probabilities.** No class weights; the delisting "
            f"rate keeps rising, so every fitted probability under-predicts (lock-box mean "
            f"predicted {br['mean_pred_logit']:.4f} against {br['observed']:.4f} observed with "
            f"the final month, {fb.get('mean_pred_logit', float('nan')):.4f} against "
            f"{fb.get('observed', float('nan')):.4f} without). Brier skill of the logistic "
            f"model is small ({_ci(br['bss_logit_full'])} on the lock-box, "
            f"{_ci(result['cv']['main']['bss_logit_full'])} in CV), and Platt and isotonic "
            "maps fitted on the inner split did not improve it in CV. Read the scores as a "
            "ranking at a fixed alert rate.")
    out += [
        (f"- **Many comparisons on {result['cv']['main']['n_months']} CV months.** b1 "
         f"compared {len(result['cv']['main']['ablation'])} ablations and 4 models per run on "
         "the same test months; the largest of several noisy gains (open interest) is biased "
         "upward. Only the two frozen models and two rules were scored on the lock-box, once."),
        (f"- **Size of the lock-box gain.** Lock-box precision is {min(ratios):.1f} to "
         f"{max(ratios):.1f} times its CV value across the {len(ratios)} candidate-run pairs, "
         f"mostly because the 2026 base rate is higher ({m['base']['estimate']:.4f} against "
         f"{result['cv']['main']['base']['estimate']:.4f} in CV) and the early-2026 batches "
         "were large. The sign of the logistic edge carries over from CV; its size does not."),
        ("- **No trade-level features.** Predictability and trade size from aggTrades are "
         "not in the monthly panel, so Q16 says nothing about whether they add to volume and "
         "open interest."),
        ("- **Universe screens.** The non-crypto screen uses each life's whole trading "
         "history; every excluded life is alive or an index contract, so it removes "
         "negatives only, and a live user would know the underlying at listing. Renames and "
         "mergers are censored by Q14's hand-made list; two 2022 events (KEEP and NU into "
         "Threshold) may be token migrations."),
        ("- **Output code added after the lock-box.** `b0_baselines.py` and `b1_models.py` "
         "gained a JSON writer (stage `json`, flag `--json-only`) after the frozen commit "
         f"{result['lockbox']['commit'][:7] if result['lockbox']['commit'] else ''}; it "
         "writes numbers they already compute, changes no modelling, and was run on the "
         "pre-2026 folds only. The lock-box numbers are parsed from `b2_lockbox.md`; b2 was "
         "not rerun."),
    ]
    return out


def write_markdown(path: Path, result: dict) -> None:
    fa, cfg = result["facts"], result["config"]
    lc, pn, ex, lk = fa["lifecycle"], fa["panel"], fa["excluded"], fa["leakage"]
    cv, lbx = result["cv"], result["lockbox"]
    L: list[str] = ["# Q16: can a coin's own trading tell that it is about to be delisted?", ""]
    L += ["## Question", "", result["question"], ""]

    # Universe and labels -----------------------------------------------------------
    L += ["## Universe and labels", ""]
    status = ", ".join(f"{k} {v}" for k, v in lc["by_status"].items())
    L += [(f"- **Lifecycle.** Every USDT-M perpetual with a daily aggTrades file in the "
           f"data.binance.vision archive: {lc['symbols']} symbols, {lc['lives']} lives "
           f"({status}). Dates come from daily aggTrades only. A gap of more than 30 days "
           "starts a new life, so 11 reused tickers give two lives each."),
          (f"- **Ghost months.** Klines, funding and metrics keep publishing files after a "
           f"contract stops trading: {fa['monthly_panel']['ghost_months']:,} of "
           f"{fa['monthly_panel']['rows']:,} monthly panel rows "
           f"({_pct(fa['monthly_panel']['ghost_share'])}) are ghost months with files but no "
           f"traded volume. They are never used as a death date, and the labelled panel keeps "
           f"{pn['ghost_rows']} of them."),
          ("- **Events and censoring.** An event is a delisting (status `delisted`, or the "
           "first life of a reused ticker). Renamed (10) and merged (2) lives are censored at "
           "their last trading month: not events, and not negatives near the end. Alive lives "
           "are censored at 2026-10."),
          ("- **Label.** At the end of month t, y = 1 if the life's last trading month L is "
           "in t+1 to t+3, using data up to month t only. Censored rows with t + 3 past the "
           "censoring month are dropped, never set to 0; the final trading month L itself is "
           "never a feature row; rows with t + 3 past 2026-10 are dropped for every life, so "
           f"the last labelled month is {pn['months'][1]}."),
          (f"- **Exclusions.** {ex['n']} lives: "
           + ", ".join(f"{v} {k}" for k, v in sorted(ex["by_reason"].items(),
                                                       key=lambda kv: -kv[1]))
           + f". Crypto lives under the weekend cut that were kept by name: "
             f"{ex['crypto_kept']}. No excluded life is an event."),
          (f"- **Panel.** {pn['rows']:,} life-months, {pn['lives']} lives with at least one "
           f"labelled row ({', '.join(f'{k} {v}' for k, v in pn['lives_by_status'].items())}), "
           f"{pn['months'][0]} to {pn['months'][1]}; {pn['pos']} positive rows from "
           f"{pn['event_lives_with_pos']} event lives, base rate {pn['base_rate']:.4f}. "
           f"Rows dropped when the panel was built: {ex['rows_dropped']}."),
          ""]
    L += ["### Base rate by year of the prediction month", ""]
    rows = []
    for r in pn["by_year"]:
        role = "lock-box" if r["year"] >= cfg["lockbox_start"][:4] else (
            "CV test" if r["year"] >= cfg["first_test"][:4] else "training only")
        rows.append([r["year"], f"{r['rows']:,}", r["lives"], r["pos"], r["event_lives"],
                     f"{r['base_rate']:.4f}", role])
    L += _table(["year", "rows", "lives", "positive rows", "event lives", "base rate", "role"],
                rows)

    # Method ----------------------------------------------------------------------------
    L += ["## Method", "",
          (f"1. **Validation.** Expanding window with monthly origins and "
           f"{cfg['test_len']}-month test blocks from {cfg['first_test']} to 2025-12 (6 folds, "
           f"36 test months). A training row needs t + 3 before the first test month, so no "
           "training label window reaches the test block. Scalers, thresholds, C and tree "
           "counts are fitted on training rows only (inner split: the last 12 training "
           "months)."),
          (f"2. **Alert rule and metrics.** Each month, flag the top max(1, round("
           f"{cfg['alert_rate']:g} x live contracts)) by score; precision and recall over all "
           "alerts, and PR-AUC. 95% intervals from a moving-block bootstrap of test months "
           f"(blocks of {cfg['boot_block']}, {cfg['n_boot']} replicates, seed {cfg['seed']}); "
           "model comparisons use paired differences on the same replicates."),
          ("3. **Candidates.** Baselines (b0): (a) falling 3-month volume, (b) lowest volume "
           "rank within the month, (c) logistic on those two plus age. Models (b1): L2 "
           "logistic and LightGBM on 35 features in 8 groups (volume level, volume trend, "
           "age, price and drawdown, volatility, open interest, funding, other activity), "
           "plus ablations and a discrete-time hazard for interpretation."),
          (f"4. **Lock-box (b2).** The full logistic model, LightGBM and rules (a) and (b) "
           f"were frozen at commit {(lbx['commit'] or '')[:7]}, trained on every row with "
           f"t + 3 before {cfg['lockbox_start']}, and scored once on origins "
           f"{cfg['lockbox_start']} to 2026-07 ({lbx['runs']})."),
          ("5. **Announcement sensitivity.** Every result is reported twice: as labelled, and "
           "with the final full month before the last trading month (`final_full_month`) "
           "dropped from training and test rows, since that month often holds the delisting "
           "announcement."),
          ("6. **Assembly.** This report parses b2's saved tables and reads the CV numbers "
           "from b0's and b1's JSON output; nothing is refitted or rescored here."),
          ""]

    # Results ---------------------------------------------------------------------------
    L += ["## Results", ""]
    L += ["### Baselines in cross-validation", ""]
    for v in VARIANTS:
        c = cv[v]
        L += [(f"{VARIANT_LABEL[v].capitalize()}: {c['n_rows']:,} test rows, {c['n_pos']} "
              f"positive rows from {c['event_lives']} event lives, base rate "
              f"{_ci(c['base'], 4)}."), ""]
        L += _table(["baseline", "precision at top 5%", "recall", "hits/alerts", "PR-AUC"],
                    _cand_rows(c, ("base_a", "base_b", "logit_c")))
        L += [(f"Paired differences: (b) - (a) {_sd(c['b_minus_a'])}; (c) - (b) "
              f"{_sd(c['diffs_vs_b']['logit_c']['prec'])}. The volume rank (b) is the bar."), ""]

    L += ["### Models in cross-validation", ""]
    for v in VARIANTS:
        c = cv[v]
        L += [f"**{VARIANT_LABEL[v].capitalize()}.**", ""]
        rows = []
        for k in ("base_b", "logit_full", "gbm_full", "logit_vol", "gbm_vol"):
            x = c["candidates"][k]
            d = c["diffs_vs_b"].get(k)
            rows.append([NAME[k], _ci(x["prec"]), f"{x['hits']}/{x['alerts']}", _ci(x["ap"]),
                         _sd(d["prec"]) if d else "", STANDING_PHRASE[standing(d["prec"])]
                         if d else "(bar)"])
        L += _table(["model", "precision at top 5%", "hits/alerts", "PR-AUC",
                     "precision - (b)", "against (b)"], rows)
    trees = sorted({fo["n_trees"] for v in VARIANTS for fo in cv[v]["folds"]})
    vol = [cv[v]["diffs_vs_b"][k]["prec"]["estimate"] for v in VARIANTS
           for k in ("logit_vol", "gbm_vol")]
    L += [(f"LightGBM's early stopping kept {trees[0]} to {trees[-1]} trees in every fold (20 "
           "is the floor), so it is close to a few shallow trees: what it learns from earlier "
           f"years does not carry forward. Models fitted on the volume features alone are "
           f"below the raw volume rank in {sum(x < 0 for x in vol)} of {len(vol)} model-run "
           f"pairs (precision differences {min(vol):+.3f} to {max(vol):+.3f}): fitting weights "
           "to volume level and trend on earlier years adds drift, not signal."), ""]

    L += ["### Lock-box (2026)", ""]
    fr = lbx["frozen"]
    L += _table(["run", "train rows", "train positives", "C (logistic)", "trees (LightGBM)",
                 "training base rate"],
                [[VARIANT_LABEL[v], f"{fr[v]['train_rows']:,}", fr[v]["train_pos"],
                  f"{fr[v]['C_logit']:g}", fr[v]["trees_gbm"], f"{fr[v]['train_base_rate']:.4f}"]
                 for v in VARIANTS if v in fr])
    for v in VARIANTS:
        b = _lb(result, v)
        L += [(f"**{VARIANT_LABEL[v].capitalize()}.** {b['n_rows']:,} rows ({b['n_lives']} "
              f"lives) over {b['n_months']} origin months ({b['months'][0]} to "
              f"{b['months'][1]}); {b['n_pos']} positive rows from {b['event_lives']} event "
              f"lives; base rate {_ci(b['base'], 4)}."), ""]
        L += _table(["candidate", "precision at top 5%", "recall", "hits/alerts", "PR-AUC"],
                    _cand_rows(b, PLOT_KEYS))
        rows = []
        for k in ("logit_full", "gbm_full", "base_a"):
            d = b["diffs_vs_b"][k]
            lomo = b["leave_one_month_out_prec_diff"].get(k)
            rows.append([f"{NAME[k]} - (b)", _sd(d["prec"]), _sd(d["ap"]),
                         f"{lomo[0]:+.3f} to {lomo[1]:+.3f}" if lomo else "n/a",
                         STANDING_PHRASE[standing(d["prec"])]])
        L += _table(["difference", "precision", "PR-AUC", "leave one month out (precision)",
                     "against (b)"], rows)
    L += ["Hits among the alerts by origin month (final month kept / dropped):", ""]
    mm = {r["month"]: r for r in _lb(result, "main")["by_month"]}
    ff = {r["month"]: r for r in _lb(result, "drop final full month")["by_month"]}
    rows = []
    for mo, a in mm.items():
        b = ff.get(mo)
        rows.append([mo, a["alerts"], f"{a['pos']} / {b['pos'] if b else ''}",
                     *(f"{a[k]} / {b[k] if b else ''}" for k in PLOT_KEYS)])
    L += _table(["origin month", "alerts", "positive rows", "(a)", "(b)", "logistic",
                 "LightGBM"], rows)

    L += ["### Cross-validation against the lock-box (the figure)", ""]
    rows = []
    for v in VARIANTS:
        for k in PLOT_KEYS:
            rows.append([VARIANT_LABEL[v], NAME[k], _ci(cv[v]["candidates"][k]["prec"]),
                         _ci(_lb(result, v)["candidates"][k]["prec"])])
    L += _table(["run", "candidate", "CV precision at top 5%", "lock-box precision"], rows)
    L += ["![Precision at the top 5%](q16_delisting.png)", ""]

    # Features ---------------------------------------------------------------------------
    L += ["### Which features matter", ""]
    for v in VARIANTS:
        sh = cv[v]["shap"]
        top = sh["features"][:5]
        L += [(f"**{VARIANT_LABEL[v].capitalize()}**, LightGBM TreeSHAP on the last CV fold "
               f"({sh['test']}): groups "
               + ", ".join(f"{g['group']} {g['share']}" for g in sh["groups"])
               + "; top features "
               + ", ".join(f"{t['feature']} {t['share']} (corr with SHAP "
                           f"{'n/a' if t['corr'] is None else format(t['corr'], '+.2f')})"
                           for t in top) + "."), ""]
    rows = []
    for v in VARIANTS:
        for a in cv[v]["ablation"]:
            rows.append([VARIANT_LABEL[v], "logistic" if a["model"] == "logit" else "LightGBM",
                         a["group"], _ci(a["prec"]), f"{a['prec_change_vs_volume']:+.3f}",
                         f"{a['ap_change_vs_volume']:+.3f}", _sd(a["prec_minus_b"])])
    L += [("Ablations in CV: volume features plus one group (change against the same model on "
          "volume features only; last column is the paired difference against rule (b))."), ""]
    L += _table(["run", "model", "added group", "precision", "change vs volume only",
                 "PR-AUC change", "precision - (b)"], rows)
    oi = {v: {a["model"]: a for a in cv[v]["ablation"] if a["group"] == "open interest"}
          for v in VARIANTS}
    lifts = [oi[v][m]["prec_change_vs_volume"] for v in VARIANTS for m in ("logit", "gbm")]
    best_other = {v: max((a for a in cv[v]["ablation"] if a["group"] != "open interest"),
                         key=lambda a: a["prec_change_vs_volume"]) for v in VARIANTS}
    clear = [a for v in VARIANTS for a in cv[v]["ablation"] if a["prec_minus_b"]["ci95"][0] > 0]
    L += [(f"Open interest raises precision over volume features alone for "
           f"{sum(x > 0 for x in lifts)} of 4 model-run pairs (by {min(lifts):+.3f} to "
           f"{max(lifts):+.3f}); the best other group adds "
           + " and ".join(f"{best_other[v]['prec_change_vs_volume']:+.3f} "
                          f"({best_other[v]['group']}, {VARIANT_LABEL[v]})" for v in VARIANTS)
           + f". {len(clear)} of the {sum(len(cv[v]['ablation']) for v in VARIANTS)} ablations "
             "beat rule (b) with a paired interval clear of zero."), ""]
    rows = []
    for v in VARIANTS:
        for h in cv[v]["hazard"]:
            excl = h["lo"] > 1 or h["hi"] < 1
            rows.append([VARIANT_LABEL[v], h["feature"], f"{h['sd']:.3g}", f"{h['or']:.2f}",
                         f"{h['lo']:.2f} to {h['hi']:.2f}", "yes" if excl else "no"])
    L += [("Discrete-time hazard (interpretation only, not scored): odds ratio per 1 SD of "
           "the monthly death hazard, all features in one model, intervals from resampling "
           "lives. Without the final month the label is shifted to t + 2."), ""]
    L += _table(["run", "feature", "SD", "odds ratio", "95% interval", "excludes 1"], rows)
    L += [hazard_sentence(result), ""]

    # Leakage ------------------------------------------------------------------------------
    m, f = _lb(result, "main"), _lb(result, "drop final full month")
    share = gain_share(result)
    cvm, cvf = cv["main"], cv["drop final full month"]
    L += ["### Announcement leakage", ""]
    L += [(f"Binance announces a delisting about 5 to 10 days before settlement, so when "
           f"settlement falls early in the last month the announcement lands in the final "
           f"full month, which is a positive row. {lk['final_full_month_pos']} of the "
           f"{pn['pos']} positive rows are final full months; "
           f"{lk['final_full_month_settled_by_day10']} of those lives settled on day 10 or "
           f"earlier. In the lock-box, {lk['lockbox_final_full_month_pos']} of "
           f"{lk['lockbox_pos']} positive rows are final full months."),
          "",
          (f"Dropping that month cuts the logistic model's lock-box gain over (b) from "
           f"{_sd(m['diffs_vs_b']['logit_full']['prec'])} to "
           f"{_sd(f['diffs_vs_b']['logit_full']['prec'])}: "
           + _share_words(share) + ". LightGBM's gain goes from "
           f"{_sd(m['diffs_vs_b']['gbm_full']['prec'])} to "
           f"{_sd(f['diffs_vs_b']['gbm_full']['prec'])}. In CV the logistic gain goes from "
           f"{_sd(cvm['diffs_vs_b']['logit_full']['prec'])} to "
           f"{_sd(cvf['diffs_vs_b']['logit_full']['prec'])}. The two runs differ in their "
           "rows (positives and training data), so the share is a description, not a "
           "decomposition. The announcement month is where the models' extra features earn "
           "most: price, volatility and volume move sharply on the announcement, which a live "
           "user would see too late to act on."), ""]

    # Checks -------------------------------------------------------------------------------
    chk = result["checks"]
    bad = [c for c in chk["cv_copied_in_b2"] if not c["ok"]]
    lc_ = chk["lockbox_counts"]
    L += ["### Consistency checks", "",
          (f"- b2 compares against CV numbers it copied by hand; "
           f"{len(chk['cv_copied_in_b2']) - len(bad)} of {len(chk['cv_copied_in_b2'])} agree "
           f"with b0's and b1's JSON within {0.0015:g}"
           + (": mismatches in " + ", ".join(f"{c['variant']} {c['metric']}" for c in bad)
              if bad else ".")),
          (f"- Lock-box positives and event lives recounted from the panel: "
           f"{lc_['pos_panel']} and {lc_['event_lives_panel']} (b2: {lc_['pos_b2']} and "
           f"{lc_['event_lives_b2']})."),
          ""]

    L += ["## Verdict", "", result.get("verdict") or verdict_paragraph(result), ""]
    L += ["## Caveats", "", *_caveats(result), ""]
    text = "\n".join(L)
    path.write_text(text.rstrip("\n") + "\n")


# --------------------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------------------

def _style(ax) -> None:
    ax.grid(axis="x", color=_GRID, lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(_MUTED)
    ax.tick_params(colors=_MUTED, labelsize=9)
    ax.tick_params(axis="y", length=0, labelcolor=_INK)


def plot(path: Path, result: dict) -> None:
    cv, lb = result["cv"], result["lockbox"]["variants"]
    panels = [("Cross-validation", (f"36 test months, {result['config']['first_test']} to "
               "2025-12"), cv),
              ("Lock-box", (f"{lb['main']['n_months']} origin months, "
               f"{lb['main']['months'][0]} to {lb['main']['months'][1]}, scored once"), lb)]
    hi = max(src[v]["candidates"][k]["prec"]["ci95"][1]
             for _, _, src in panels for v in VARIANTS for k in PLOT_KEYS)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), sharey=True, sharex=True)
    for ax, (title, sub, src) in zip(axes, panels):
        for j, v in enumerate(VARIANTS):
            col = VARIANT_COLOR[v]
            off = -0.16 if j == 0 else 0.16
            for i, k in enumerate(PLOT_KEYS):
                p = src[v]["candidates"][k]["prec"]
                y = i + off
                ax.plot(p["ci95"], [y, y], color=col, lw=2, solid_capstyle="round", zorder=2)
                ax.plot(p["estimate"], y, "o", color=col, ms=7.5, mec="white", mew=1.5,
                        zorder=3)
                ax.text(p["ci95"][1] + hi * 0.015, y, f"{p['estimate']:.3f}", va="center",
                        ha="left", fontsize=7.5, color=_MUTED)
            ax.axvline(src[v]["base"]["estimate"], color=col, lw=1.1, ls=":", zorder=1)
        ax.set_title(f"{title}\n", loc="left", fontsize=11, color=_INK, fontweight="bold")
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=8.5, color=_MUTED)
        ax.set_xlim(0, hi * 1.18)
        ax.set_xlabel("precision among the top 5% of live contracts per month", fontsize=9,
                      color=_MUTED)
        _style(ax)
    axes[0].set_yticks(range(len(PLOT_KEYS)), [NAME[k] for k in PLOT_KEYS])
    axes[0].invert_yaxis()
    handles = [Line2D([], [], color=VARIANT_COLOR[v], marker="o", lw=2, ms=7, mec="white",
                      label=VARIANT_LABEL[v]) for v in VARIANTS]
    handles.append(Line2D([], [], color=_MUTED, lw=1.1, ls=":", label="base rate (same colour)"))
    fig.legend(handles=handles, frameon=False, loc="upper right", ncol=3, fontsize=8.5,
               bbox_to_anchor=(0.99, 1.0))
    fig.text(0.01, 0.01, "95% intervals from a moving-block bootstrap of months (blocks of 3). "
             "Separate intervals overlap more than the paired differences in the report "
             "suggest.\nThe lock-box has only 5 distinct 3-month blocks, so its intervals are "
             "rough. (b) is the baseline every model must beat.", fontsize=7.8, color=_MUTED)
    fig.tight_layout(rect=(0, 0.07, 1, 0.93))
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)
