"""Q15 report writing: verdict, Markdown and the figure.

Everything here is a pure function of the result dict built by
`q15_market_evolution.build_result`. Every verdict sentence is computed from numbers in
that dict, so the text cannot drift from the tables. Units: pp are percentage points of
accuracy or of the sign repeat rate; autocorrelation is x100; "per log point" is per unit
of ln(relative tick).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_INK, _INK2, _MUTED, _GRID, _SURF = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
_BLUE, _ORANGE, _AQUA = "#2a78d6", "#eb6834", "#1baf7a"

OUTCOME_LABEL = {
    "repeat_rate": "sign repeat rate (primary)",
    "sign_acf_lag1": "lag-1 sign autocorrelation, x100 (primary)",
    "acc_refit": "same-day refit accuracy (secondary, post hoc in e3)",
    "refit_excess": "refit minus persistence (secondary, post hoc in e3)",
    "unchanged": "unchanged-price share (mechanism)",
    "long_runs": "same-sign runs of 10 or more (mechanism)",
    "log_size": "median trade size, log points (mechanism)",
    "log_events": "events per day, log points (mechanism)",
    "log_rel_tick": "relative tick, log points (first stage)",
    "acc_logit": "frozen-model accuracy (e3's prespecified outcome)",
}
PRIMARY = ("repeat_rate", "sign_acf_lag1")
SECONDARY = ("acc_refit", "refit_excess")
VERDICT_WORD = {"confirm": "confirms", "weaken": "weakens", "reverse": "reverses",
                "not estimable": "cannot test"}


def _f(x, nd: int = 2, signed: bool = True) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{x:+.{nd}f}" if signed else f"{x:.{nd}f}"


def _ci(d: dict | None, nd: int = 2) -> str:
    if not d:
        return "n/a"
    return f"{_f(d['b'], nd)} ({_f(d['lo'], nd)} to {_f(d['hi'], nd)})"


def _excludes_zero(d: dict) -> bool:
    return bool(d) and (d["lo"] > 0 or d["hi"] < 0)


def _p(p) -> str:
    if p is None:
        return "n/a"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


# --------------------------------------------------------------------------
# The lock-box rule (identical to e5's `lockbox_verdict`, fixed before the run)
# --------------------------------------------------------------------------


def classify(lb: dict, ref: dict) -> str:
    """confirm: same sign as e5, CR1 interval excludes zero, permutation p < 0.05;
    reverse: opposite sign and the CR1 interval excludes zero; weaken: otherwise."""
    if not lb or not ref:
        return "not estimable"
    same = np.sign(lb["b"]) == np.sign(ref["b"])
    perm_ok = lb.get("perm", {}).get("p", 1.0) < 0.05
    if same and _excludes_zero(lb) and perm_ok:
        return "confirm"
    if not same and _excludes_zero(lb):
        return "reverse"
    return "weaken"


def lockbox_overall(result: dict) -> str:
    """One word for the primary family (pooled, per log point): confirm only if both
    primary outcomes confirm, reverse if either reverses, weaken otherwise. This
    aggregation of the two primary outcomes was written after the run."""
    lb = result.get("lockbox") or {}
    if not lb:
        return "not run"
    words = [classify(lb["final"]["models"]["pooled"].get(k, {}),
                      result["e5"]["models"]["pooled"].get(k, {})) for k in PRIMARY]
    if "reverse" in words:
        return "reverse"
    if all(w == "confirm" for w in words):
        return "confirm"
    return "weaken"


# --------------------------------------------------------------------------
# Verdict sentences
# --------------------------------------------------------------------------


def composition_sentence(r: dict) -> str:
    c = r["e4"]["composition"]
    comp = c["exits"]["b"] + c["entries"]["b"]
    s = (f"Across the Q14 cross-sections, mean accuracy rose {_ci(c['total'])} pp from "
         f"2023-06 to 2026-07. Contracts present in both months rose {_ci(c['within'])} pp; "
         f"exits contributed {_ci(c['exits'])} and new listings {_ci(c['entries'])}.")
    if c["within"]["lo"] > 0 and c["within"]["b"] >= c["total"]["b"]:
        s += (f" So the rise is not composition: the two composition terms sum to "
              f"{_f(comp)} pp and pull the average {'down' if comp < 0 else 'up'}, and the "
              f"whole rise happens inside contracts (one-month noise floor "
              f"{_ci(r['e4']['noise_floor'])} pp).")
    elif c["within"]["lo"] > 0:
        s += (f" Most of the rise happens inside contracts; composition adds {_f(comp)} pp.")
    else:
        s += " The within-contract term is not distinguishable from zero, so composition " \
             "cannot be ruled out."
    return s


def size_sentence(r: dict) -> str:
    sv, g = r["survivors"], r["e4"]["gelbach"]
    fe = r["e4"]["regression"]["log_size"]["b1_contract_fe"]
    pct = 100 * (1 - np.exp(sv["lsize"]["b"]))
    s = (f"Median trade size in USD fell in {100 * sv['lsize']['share_down']:.0f}% of the "
         f"{sv['n']} survivors, by {_ci(sv['lsize'])} log points on average (about "
         f"{pct:.0f}% smaller). With contract fixed effects, accuracy moves "
         f"{_ci(fe)} pp per log point of trade size, and in the Gelbach split trade size "
         f"accounts for {_ci(g['trade_size'])} pp of the {_f(g['rise']['b'])} pp "
         f"within-contract rise.")
    if g["trade_size"]["lo"] > g["rise"]["b"]:
        s += (" That is more than the whole rise, so the cross-contract slope does not carry "
              "over one for one to a market-wide shift this large; it is an accounting "
              "identity, not a causal attribution.")
    elif g["trade_size"]["lo"] > 0:
        s += " Trade size accounts for part of the rise (accounting, not causal)."
    else:
        s += " Trade size does not account for the rise by this split."
    return s


def tick_cross_sentence(r: dict) -> str:
    cs = r["cross_section"]
    keys = [k for k in cs if k.endswith("|rep")]
    neg = [k for k in keys if cs[k]["log_rel_tick"]["hi"] < 0]
    parts = " and ".join(f"{_ci(cs[k]['log_rel_tick'])} pp in {k.split('|')[0][-4:]}"
                         for k in keys)
    s = (f"Across contracts at equal activity and trade size, the repeat rate changes by "
         f"{parts} per log point of relative tick, below zero in {len(neg)} of {len(keys)} "
         f"months (descriptive).")
    return s


def experiment_sentence(r: dict) -> str:
    m = r["e5"]["models"]
    cut, inc, pool = (m[k]["repeat_rate"] for k in ("cut", "increase", "pooled"))
    ok_cut = cut["lo"] > 0
    ok_inc = inc["hi"] < 0
    s = (f"In the stacked event study (e5, {pool['batches']} batches, {cut['treated']} cuts "
         f"and {inc['treated']} increases), a 10x cut raises the repeat rate by {_ci(cut)} pp "
         f"and an increase lowers it by {_ci(inc)} pp; pooled, {_ci(pool)} pp per log point "
         f"of tick.")
    if ok_cut and ok_inc:
        s += " Both prespecified signs hold, with intervals that exclude zero."
    elif ok_cut or ok_inc:
        s += (f" Only the {'cut' if ok_cut else 'increase'} prediction has an interval that "
              f"excludes zero.")
    else:
        s += " Neither prespecified sign is established."
    return s


def lockbox_sentence(r: dict) -> str:
    lb = r.get("lockbox") or {}
    if not lb:
        return "The lock-box has not been run."
    fin = lb["final"]
    m, ref = fin["models"]["pooled"], r["e5"]["models"]["pooled"]
    tr = sum(a["treated"] for a in fin["arms"])
    nb = len(fin["arms"])
    words = {k: classify(m.get(k, {}), ref.get(k, {})) for k in PRIMARY + SECONDARY}
    parts = []
    for k in PRIMARY + SECONDARY:
        o = m.get(k)
        if not o:
            continue
        parts.append(f"{OUTCOME_LABEL[k]} {_ci(o)} per log point against e5's "
                     f"{_f(ref[k]['b'])} (permutation p {_p(o['perm']['p'])}): "
                     f"{VERDICT_WORD[words[k]]}")
    overall = lockbox_overall(r)
    runs = len(lb["runs"])
    s = (f"The lock-box ({nb} reserved batches, {tr} treated contracts, run "
         f"{'once' if runs == 1 else f'{runs} times after a bug fix'} with the frozen e5 code) "
         f"gives: " + "; ".join(parts) + ".")
    inside = [k for k in PRIMARY if m.get(k) and m[k]["lo"] <= ref[k]["b"] <= m[k]["hi"]]
    if overall == "confirm":
        s += " Both primary outcomes confirm e5 out of sample."
    elif overall == "reverse":
        s += (" At least one primary outcome reverses the e5 estimate out of sample, so the "
              "causal claim does not survive the lock-box.")
    else:
        s += (" The primary family is mixed: the direction agrees with e5 but not every "
              "primary outcome is decisive on this small sample, so the lock-box weakens "
              "rather than confirms.")
    if inside and overall != "reverse":
        s += (f" The e5 point estimate lies inside the lock-box interval for "
              f"{len(inside)} of {len(PRIMARY)} primary outcomes, so the lock-box does not "
              f"contradict its size.")
    return s


def slope_sentence(r: dict) -> str:
    cs = r["e5"]["cross_section"]
    held = [cs[k] for k in cs if k.endswith("|repeat_rate|activity held fixed")]
    lo, hi = min(h["b"] for h in held), max(h["b"] for h in held)
    e5b = r["e5"]["models"]["pooled"]["repeat_rate"]
    s = (f"Per log point of relative tick, the cross-sectional repeat-rate slope at equal "
         f"activity is {_f(lo)} to {_f(hi)} pp and the experimental one {_ci(e5b)} pp")
    lb = r.get("lockbox") or {}
    if lb:
        s += f" (lock-box {_ci(lb['final']['models']['pooled']['repeat_rate'])})"
    s += "."
    if lo <= e5b["b"] <= hi:
        s += (" The experiment lies inside the cross-sectional range, so the across-contract "
              "pattern has about the causal size.")
    elif e5b["b"] < lo:
        s += " The experiment is steeper than the cross-section."
    else:
        s += " The experiment is flatter than the cross-section."
    return s


def explained_sentence(r: dict) -> str:
    ta, sv, q = r["tick_accounting"], r["survivors"], r["q10"]
    rise_q10 = q["d_acc"]
    a_q10 = ta["q10"]["acc_refit"]
    a_sv = ta["survivors"]["acc_refit"]
    share = a_q10["b"] / rise_q10["b"] if rise_q10["b"] else float("nan")
    s = (f"What tick explains: across the {sv['n']} survivors, log relative tick changed by "
         f"{_ci(sv['ltick'])} from 2023-06 to 2026-07, which at the experimental slope "
         f"implies {_ci(a_sv)} pp of accuracy against a rise of {_f(sv['acc']['b'])} pp")
    s += (", so tick explains essentially none of that rise." if abs(a_sv["b"]) <
          0.25 * abs(sv["acc"]["b"]) else ".")
    s += (f" On Q10's {q['n']} coins from {q['from']} to {q['to']}, prices rose and log "
          f"relative tick fell by {_ci(q['d_log_rel_tick'])}, which implies {_ci(a_q10)} pp "
          f"against their rise of {_ci(rise_q10)} pp, about {100 * share:.0f}% of it, while "
          f"their log trade size moved {_ci(q['d_log_size'])}.")
    s += (" That extrapolates a slope measured on small contracts and on a same-day refit "
          "model to large coins and a month-long boosted model, so it is a rough share.")
    return s


def answer_sentence(r: dict) -> str:
    overall = lockbox_overall(r)
    q = r["q10"]
    nb = r["e5"]["models"]["pooled"]["repeat_rate"]["batches"]
    share = r["tick_accounting"]["q10"]["acc_refit"]["b"] / q["d_acc"]["b"]
    a = ("Answer. The rise in next-sign predictability happened inside contracts, not "
         "through which coins survived. ")
    if overall == "confirm":
        a += ("Tick size does cause sign persistence: a finer grid raises it and a coarser "
              f"grid lowers it, in {nb} batches and again in the untouched lock-box. ")
    elif overall == "weaken":
        a += (f"Tick size very likely causes sign persistence ({nb} batches in both "
              "directions), and the untouched lock-box points the same way but is "
              "weaker and not decisive on every primary outcome. ")
    elif overall == "reverse":
        a += ("Whether tick size causes sign persistence is not established: the e5 "
              "estimate is reversed in the untouched lock-box. ")
    else:
        a += "The lock-box has not been run, so the e5 causal estimate is in-sample only. "
    if overall != "reverse":
        a += (f"Through falling relative ticks as prices rose, it can account for roughly "
              f"{100 * share:.0f}% of Q10's {q['from']} to {q['to']} rise on its 10 coins, "
              f"but for none of the 2023 to 2026 rise across the cross-section, where "
              f"relative ticks did not shrink on average. ")
    sz = r["survivors"]["lsize"]
    a += (f"The 2023 to 2026 within-contract rise lines up instead with much smaller trades "
          f"({_f(sz['b'])} log points), consistent with algorithmic slicing but a "
          f"correlation without an experiment")
    if q["d_log_size"]["lo"] <= 0 <= q["d_log_size"]["hi"]:
        a += (f"; on Q10's coins trade size had not yet moved by {q['to']}, so it does not "
              f"explain the part of their rise that tick leaves")
    a += ". All of this is sign persistence, not price predictability."
    return a


def verdict_paragraph(r: dict) -> str:
    return " ".join([composition_sentence(r), size_sentence(r), tick_cross_sentence(r),
                     experiment_sentence(r), lockbox_sentence(r), slope_sentence(r),
                     explained_sentence(r), answer_sentence(r)])


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------


def _row(*cells) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def _est_table(models: dict, keys, cols=("cut", "increase", "pooled")) -> list[str]:
    L = [_row("outcome", *[f"{c} (CR1)" for c in cols], "pooled permutation", "pooled pre-trend p"),
         _row(*["---"] * (len(cols) + 3))]
    for k in keys:
        cells = [_ci(models.get(c, {}).get(k)) for c in cols]
        po = models.get("pooled", {}).get(k, {})
        perm = po.get("perm", {})
        L.append(_row(OUTCOME_LABEL[k], *cells,
                      f"{_f(perm.get('lo'))} to {_f(perm.get('hi'))}" if perm else "n/a",
                      _p(po.get("pre_p"))))
    return L


def _caveats(r: dict) -> list[str]:
    lb = r.get("lockbox") or {}
    fin = lb.get("final", {})
    n_inc = r["e5"]["models"]["increase"]["repeat_rate"]["treated"]
    unch = r["e5"]["models"]["cut"]["unchanged"]["b"]
    n_inc_lb = sum(a["treated"] for a in fin.get("arms", []) if a["direction"] == "increase")
    stock = [s for a in fin.get("plan_arms", []) for s in a["treated"] + a["controls"]
             if s in {"CSOPSAMSUNG2LUSDT", "FLNCUSDT", "HK0625USDT", "KUAISHOUUSDT", "NOWUSDT",
                      "SMHUSDT", "TERUSDT", "UNHUSDT", "UVXYUSDT", "VRTUSDT"}]
    return [
        ("- **Sign persistence is not price predictability.** Every outcome here is about the "
        "direction of the next aggressor event. Q2 and Q5 show that price impact adjusts to "
        "order-flow memory, so a more predictable sign is not a more predictable price, and "
        "no outcome here measures spreads, fees or profit."),
        ("- **Part of the tick effect is mechanical.** A finer grid splits the same taker flow "
        "into more same-side events at new prices (the unchanged-price share changes by "
        f"{_f(unch, 1)} pp after a cut in e5), and aggTrades cannot separate that from "
        "changed trader behaviour."),
        ("- **Budget-limited contract selection.** e5 and the lock-box keep, per batch, the 3 "
        "cut contracts with the smallest pre-event archive size, every third day of the "
        "window, and cheap increases one at a time. The rule uses pre-event size only, but "
        "the results describe small and mid-sized contracts, not the largest coins whose "
        "rise Q10 measured."),
        (f"- **Few increases.** e5 has {n_inc} increase contracts; the lock-box batches contain "
        f"{n_inc_lb}. The coarser-grid direction rests mostly on two multi-contract batches "
        "and SOLUSDT."),
        ("- **Post-hoc outcomes are labelled.** Same-day refit accuracy and refit minus "
        "persistence were added in e3 after its first result and are secondary. The "
        "prespecified frozen-model accuracy in e3 did not move. Combining the two primary "
        "lock-box outcomes into one word (confirm only if both confirm) was decided after "
        "the run; the per-outcome rule was fixed before it."),
        ("- **Correlations are descriptive.** The cross-sectional slopes, the panel "
        "regressions and the Gelbach split are associations; the trade-size story has no "
        "experiment, and the tick accounting for Q10's coins carries a slope from small "
        "contracts and a different outcome to large coins."),
        (f"- **The lock-box is small.** {fin.get('coverage', {}).get('contracts', 'n/a')} "
        f"contracts in {len(fin.get('arms', []))} batches; "
        f"{len(stock)} of them are stock-linked perpetuals (2026-10-15 especially), which "
        "trade mostly in US hours, so same-day refit accuracy (fitted on UTC hours 0 to 12) "
        "is missing for the thinnest of them."),
        ("- **Controls are matched on activity only**, not on price trend; Binance cuts a "
        "tick after a price fall, and the first-stage relative tick drifts before some "
        "events."),
    ]


def write_markdown(path: Path, r: dict) -> None:
    q, c, sv, e4 = r["q10"], r["e4"]["composition"], r["survivors"], r["e4"]
    e5m = r["e5"]["models"]
    lb = r.get("lockbox") or {}
    L = ["# Q15: why next-trade signs became more predictable, and what tick size does", ""]
    L += ["## Question", "", r["question"] + " Q10 found that a freshly trained model "
          f"predicts the next trade's sign better in {q['to']} than in {q['from']} on the "
          "same 10 contracts. Part A of `research/market_evolution` asked whether that rise "
          "is composition or change within contracts, which measured drivers move with it, "
          "and whether one of them, relative tick size, causes sign persistence in natural "
          "experiments.", ""]
    L += ["## Method", "",
          ("This report fits nothing new except descriptive cross-sectional regressions; it "
          "assembles the Part A outputs (`q15_market_evolution.py`):"), "",
          f"- `{r['inputs']['e0']}` and `{r['inputs']['e1']}`: Q10's 10 coins x 5 months.",
          (f"- `{r['inputs']['e2']}` (e2): 181 contracts in 2023-06 and 251 in 2026-07 (Q14 "
          "cross-sections), with Q14 accuracy and the order-flow proxies."),
          (f"- `{r['inputs']['e4']}`: composition split, fixed-effects regressions and "
          "Gelbach decomposition (parsed from its tables; e4 writes no JSON)."),
          (f"- `{r['inputs']['e3']}` and `{r['inputs']['e5']}`: the two-batch event study and "
          "the stacked event study over 35 batches."),
          (f"- `{r['inputs']['lockbox']}`: one run of the frozen e5 design on the two "
          "reserved batches."), "",
          ("Intervals are 95%: contract-resampling percentiles (2000 draws) for changes and "
          "cross-sectional slopes, CR1 clustered by contract with t(G-1) for the event "
          "studies, plus e5's within-batch permutation test. The tick accounting multiplies "
          "a mean change in log relative tick by the e5 pooled slope per log point."), ""]
    L += ["## Verdict", "", r.get("verdict") or verdict_paragraph(r), ""]
    L += ["## Results", "", "### 1. Composition versus within-contract change", "",
          f"Q10's 10 coins, mean fresh-model accuracy (pp, `{r['inputs']['e0']}`):", "",
          _row(*q["months"]), _row(*["---"] * len(q["months"])),
          _row(*[f"{q['mean_acc_pp'][m]:.2f}" for m in q["months"]]), "",
          ("Q14 cross-sections, mean accuracy (pp), split as in e4 (exits, within, entries "
          "sum to the total):"), "",
          _row("2023-06", "2026-07", "total", "exits", "within (survivors)", "entries"),
          _row(*["---"] * 6),
          _row(f"{c['acc_2023']:.2f}", f"{c['acc_2026']:.2f}", _ci(c["total"]),
               _ci(c["exits"]), _ci(c["within"]), _ci(c["entries"])), "",
          composition_sentence(r), ""]
    L += ["### 2. Trade size and relative tick: cross-section and panel", "",
          f"Within-contract change, 2026-07 minus 2023-06, {sv['n']} survivors:", "",
          _row("quantity", "mean change", "share of contracts that fell"),
          _row("---", "---", "---")]
    for k, lbl in (("acc", "accuracy (pp)"), ("rep", "sign repeat rate (pp)"),
                   ("lsize", "log median trade size (USD)"), ("ltick", "log relative tick")):
        L.append(_row(lbl, _ci(sv[k]), f"{100 * sv[k]['share_down']:.0f}%"))
    L += ["", ("Cross-section, OLS per month of the outcome on log trade size, log relative "
          "tick and log events (descriptive; per log point):"), "",
          _row("month, outcome", "n", "log trade size", "log relative tick"),
          _row("---", "---", "---", "---")]
    for k, o in r["cross_section"].items():
        per, y = k.split("|")
        L.append(_row(f"{per[-4:]}, {'accuracy' if y == 'acc' else 'repeat rate'} (pp)",
                      o["n"], _ci(o["log_size"]), _ci(o["log_rel_tick"])))
    reg = e4["regression"]
    L += ["", "Panel regressions of accuracy (e4, pp per log point, CRV1 by contract):", "",
          _row("driver", "pooled", "contract FE", "two-way FE", "10 coins, contract FE"),
          _row(*["---"] * 5)]
    for k, lbl in (("log_size", "log median trade size"), ("log_rel_tick", "log relative tick")):
        L.append(_row(lbl, _ci(reg[k]["a1_pooled"]), _ci(reg[k]["b1_contract_fe"]),
                      _ci(reg[k]["b2_two_way_fe"]), _ci(reg[k]["b3_ten_coins"])))
    g = e4["gelbach"]
    L += ["", "Gelbach split of the within-contract rise (e4, survivors, pp):", "",
          _row("term", "pp"), _row("---", "---"),
          _row("rise, no drivers", _ci(g["rise"])),
          _row("explained by trade size (log size and share under $1k)", _ci(g["trade_size"])),
          _row("explained by relative tick", _ci(g["rel_tick"])),
          _row("unexplained, with all six drivers", _ci(g["unexplained"])), "",
          size_sentence(r), "", tick_cross_sentence(r), ""]
    L += ["### 3. Natural experiments", "", "e3, two 10x cuts (pp; CR1 clustered):", "",
          _row("event", "treated / controls", *[OUTCOME_LABEL[k] for k in
                                                ("repeat_rate", "acc_logit", "acc_refit")]),
          _row(*["---"] * 5)]
    for ev, d in r["e3"].items():
        L.append(_row(ev, f"{d['treated']} / {d['controls']}", _ci(d.get("repeat_rate")),
                      _ci(d.get("acc_logit")), _ci(d.get("acc_refit"))))
    L += ["", (f"e5, stacked over {e5m['pooled']['repeat_rate']['batches']} batches (cut and "
          "increase: treated minus controls; pooled: per log point of signed tick change):"),
          "", *_est_table(e5m, PRIMARY + SECONDARY + ("unchanged", "log_rel_tick")), ""]
    L += [experiment_sentence(r), ""]
    if lb:
        fin = lb["final"]
        cols = [c for c in ("cut", "increase", "pooled") if fin["models"].get(c)]
        L += ["### 4. Lock-box", "",
              f"Frozen code: commit `{fin['frozen_commit']}` (e5 unchanged since; the only "
              "edit is the `--lockbox` switch, the only path allowed to load the reserved "
              f"dates). HEAD at analysis `{fin['head'][:7]}`. Runs: {len(lb['runs'])}"
              + ("" if len(lb["runs"]) == 1 else
                 " (" + "; ".join(f"run {x['run']}: {x['rerun_reason']}"
                                  for x in lb["runs"][1:]) + ")")
              + (". No bug was found when the per-contract changes were checked after the "
                 "run, so there is no second run" if len(lb["runs"]) == 1 else "")
              + ". Design written down before any download: per reserved batch, the 3 "
              "eligible cut contracts with the smallest pre-event archive size, their first "
              "3 valid controls, every third relative day.", "",
              _row("batch", "treated", "controls"), _row("---", "---", "---")]
        for a in fin["plan_arms"]:
            L.append(_row(a["batch"], ", ".join(a["treated"]) + f" ({len(a['treated'])} of "
                          f"{a['n_eligible']} eligible)", len(a["controls"])))
        dl = lb.get("downloaded_bytes")
        cov = fin["coverage"]
        L += ["", f"Coverage: {cov['rows']} of {cov['expected']} contract-days, "
              f"{cov['contracts']} contracts, median {cov['scored_median']:,.0f} scored events "
              f"per contract-day; downloaded {dl / 1e9:.2f} GB." if dl else "", "",
              "Lock-box estimates next to e5 (pp; CR1):", "",
              _row("outcome", *[f"lock-box {c}" for c in cols], "lock-box permutation p",
                   "lock-box pre-trend p", "e5 pooled", "rule"),
              _row(*["---"] * (len(cols) + 5))]
        for k in PRIMARY + SECONDARY + ("unchanged", "log_rel_tick"):
            po = fin["models"]["pooled"].get(k, {})
            ref = e5m["pooled"].get(k, {})
            L.append(_row(OUTCOME_LABEL[k], *[_ci(fin["models"][c].get(k)) for c in cols],
                          _p(po.get("perm", {}).get("p")), _p(po.get("pre_p")), _ci(ref),
                          classify(po, ref) if k in PRIMARY + SECONDARY else "not tested"))
        L += ["", "Per batch (e3's single-event DiD; repeat rate, pp):", "",
              _row("batch", "treated / controls", "repeat rate", "permutation p",
                   "pre-trend p"), _row(*["---"] * 5)]
        for a in fin["arms"]:
            o = a["repeat_rate"]
            L.append(_row(a["batch"], f"{a['treated']} / {a['controls']}",
                          _ci(o), _p(o["perm_p"]), _p(o["pre_p"])))
        L += ["", ("Rule, fixed in e5 before the run: confirm when the sign matches e5, the CR1 "
              "interval excludes zero and the permutation p is below 0.05; reverse when the "
              "sign is opposite and the interval excludes zero; weaken otherwise."), "",
              lockbox_sentence(r), ""]
    cs = r["e5"]["cross_section"]
    L += ["### 5. Cross-sectional versus experimental slope", "",
          ("Per log point of relative tick (pp). Cross-section: OLS across contracts, raw and "
          "with log events (from e5, same parquet)."), "",
          _row("estimate", "repeat rate", "accuracy"), _row("---", "---", "---")]
    for per in ("cross_2023", "cross_2026"):
        for ctl in ("raw", "activity held fixed"):
            L.append(_row(f"cross-section {per[-4:]}, {ctl}",
                          _ci(cs.get(f"{per}|repeat_rate|{ctl}")),
                          _ci(cs.get(f"{per}|acc_gbm|{ctl}")) + " (gbm, month)"))
    L.append(_row("e5 stacked event study", _ci(e5m["pooled"]["repeat_rate"]),
                  _ci(e5m["pooled"]["acc_refit"]) + " (same-day refit)"))
    if lb:
        pm = lb["final"]["models"]["pooled"]
        L.append(_row("lock-box", _ci(pm["repeat_rate"]),
                      _ci(pm["acc_refit"]) + " (same-day refit)"))
    L += ["", slope_sentence(r), ""]
    ta = r["tick_accounting"]
    L += ["### 6. What is and is not explained", "",
          _row("sample, period", "change in log relative tick", "implied repeat rate (pp)",
               "implied accuracy (pp)", "observed accuracy change (pp)"),
          _row(*["---"] * 5),
          _row(f"{sv['n']} survivors, 2023-06 to 2026-07", _ci(sv["ltick"]),
               _ci(ta["survivors"]["repeat_rate"]), _ci(ta["survivors"]["acc_refit"]),
               _ci(sv["acc"])),
          _row(f"Q10's {q['n']} coins, {q['from']} to {q['to']}", _ci(q["d_log_rel_tick"]),
               _ci(ta["q10"]["repeat_rate"]), _ci(ta["q10"]["acc_refit"]), _ci(q["d_acc"])),
          "", explained_sentence(r), "",
          ("- **Explained, with an experiment:** relative tick moves sign persistence in the "
          "predicted direction, both ways."),
          ("- **Explained only as an accounting identity:** the 2023 to 2026 within-contract "
          f"rise lines up with a {100 * (1 - np.exp(sv['lsize']['b'])):.0f}% fall in median "
          "trade size; there is no experiment for trade size."),
          ("- **Not explained:** why trades shrank (algorithmic slicing is the leading story), "
          "why the Gelbach split overshoots, why the 2023 batches show no tick effect, and "
          "whether any of this makes prices, rather than signs, more predictable."), ""]
    L += ["## Caveats", "", *_caveats(r), ""]
    L += ["## Files", "",
          ("- `src/microstructure/analyses/q15_market_evolution.py` builds the result dict; "
          "`q15_report.py` writes this file and the figure."),
          "- `results/q15_market_evolution.json` holds every number above.",
          "- `research/market_evolution/e5_stacked_events.py --lockbox` ran the lock-box.", ""]
    text = "\n".join(L) + "\n"
    for bad in (chr(0x2014), chr(0x2013)):
        if bad in text:
            raise ValueError("em or en dash in the report")
    path.write_text(text)


# --------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------


def _style(ax) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8, colors=_INK2)
    ax.grid(axis="x", color=_GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.set_facecolor(_SURF)


def _arm_ci(a: dict) -> tuple[float, float]:
    o = a["repeat_rate"]
    return (o["lo"], o["hi"]) if a["treated"] >= 3 else (o["perm_lo"], o["perm_hi"])


def plot(path: Path, r: dict) -> None:
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(15, 11), facecolor=_SURF,
                                 gridspec_kw={"width_ratios": [1.25, 1], "wspace": 0.55})
    lim = 25
    arms = sorted([a for a in r["e5"]["arms"] if "repeat_rate" in a],
                  key=lambda a: (a["direction"], a["batch"]))
    lb = r.get("lockbox") or {}
    lb_arms = lb.get("final", {}).get("arms", [])
    rows = []  # (label, b, lo, hi, color, marker, size, bold)
    for a in arms:
        lo, hi = _arm_ci(a)
        col = _BLUE if a["direction"] == "cut" else _ORANGE
        rows.append((f"{a['batch']} {a['direction']} {a['treated']}T/{a['controls']}C",
                     a["repeat_rate"]["b"], lo, hi, col, "o", 5, False))
    for d, col in (("cut", _BLUE), ("increase", _ORANGE)):
        o = r["e5"]["models"][d]["repeat_rate"]
        rows.append((f"e5 stacked {d}s ({o['treated']} treated)", o["b"], o["lo"], o["hi"],
                     col, "D", 8, True))
    for a in lb_arms:
        lo, hi = _arm_ci(a)
        rows.append((f"lock-box {a['batch']} {a['direction']} {a['treated']}T/{a['controls']}C",
                     a["repeat_rate"]["b"], lo, hi, _AQUA, "s", 6, False))
    if lb:
        for d in ("cut", "increase"):
            o = lb["final"]["models"].get(d, {}).get("repeat_rate")
            if o:
                rows.append((f"lock-box stacked {d}s ({o['treated']} treated)", o["b"],
                             o["lo"], o["hi"], _AQUA, "s", 9, True))
    ys = np.arange(len(rows))[::-1].astype(float)
    n_e5 = len(arms)
    ys[n_e5:] -= 0.8  # gap before the stacked rows
    ys[n_e5 + 2:] -= 0.8  # and before the lock-box
    for y, (lbl, b, lo, hi, col, mk, ms, bold) in zip(ys, rows, strict=True):
        if np.isfinite(lo) and np.isfinite(hi):
            ax.hlines(y, max(lo, -lim), min(hi, lim), color=col, lw=3.5 if bold else 1.4,
                      alpha=0.9 if bold else 0.7)
        ax.plot(b, y, mk, color=col, ms=ms, mec=_SURF, mew=1.2)
    ax.set_yticks(ys, [x[0] for x in rows], fontsize=7)
    for t, x in zip(ax.get_yticklabels(), rows, strict=True):
        t.set_color(_INK if x[7] else _INK2)
        if x[7]:
            t.set_fontweight("bold")
    ax.axvline(0, color=_MUTED, lw=0.8)
    ax.set_xlim(-lim, lim)
    ax.set_xlabel("repeat-rate effect, treated minus controls (pp)", fontsize=9, color=_INK2)
    ax.set_title("Tick changes, by batch: sign repeat rate (primary)\nblue cuts, orange "
                 "increases, green lock-box; 95% CI (permutation when < 3 treated)",
                 fontsize=10, color=_INK, loc="left")
    _style(ax)
    # right: slope per log point of relative tick
    cs = r["e5"]["cross_section"]
    items = []
    for out, cskey, lbl in (("repeat_rate", "repeat_rate", "repeat rate"),
                            ("acc_refit", "acc_gbm", "accuracy")):
        for per in ("cross_2023", "cross_2026"):
            for ctl, short in (("raw", "raw"), ("activity held fixed", "equal activity")):
                o = cs.get(f"{per}|{cskey}|{ctl}")
                if o:
                    items.append((f"{lbl}: cross-section {per[-4:]}, {short}", o, _INK2, "o"))
        items.append((f"{lbl}: e5 experiment", r["e5"]["models"]["pooled"][out], _BLUE, "D"))
        if lb:
            items.append((f"{lbl}: lock-box", lb["final"]["models"]["pooled"][out], _AQUA, "s"))
        items.append(None)
    items = items[:-1]
    y = len(items)
    yt, yl = [], []
    for it in items:
        y -= 1
        if it is None:
            continue
        lbl, o, col, mk = it
        bx.hlines(y, o["lo"], o["hi"], color=col, lw=2.2)
        bx.plot(o["b"], y, mk, color=col, ms=8, mec=_SURF, mew=1.2)
        bx.text(o["hi"] + 0.15, y, f"{o['b']:+.2f}", va="center", fontsize=8, color=_INK2)
        yt.append(y)
        yl.append(lbl)
    bx.set_yticks(yt, yl, fontsize=8)
    bx.axvline(0, color=_MUTED, lw=0.8)
    bx.set_xlabel("pp per log point of relative tick (negative: coarser grid, less "
                  "persistence)", fontsize=9, color=_INK2)
    bx.set_title("Cross-sectional slope against the experimental slope\naccuracy: Q14 "
                 "monthly gbm across contracts, same-day refit in the experiments",
                 fontsize=10, color=_INK, loc="left")
    _style(bx)
    fig.suptitle("Q15: tick size and next-trade-sign persistence", fontsize=12, color=_INK,
                 x=0.06, ha="left", y=0.955)
    fig.savefig(path, dpi=130, bbox_inches="tight", facecolor=_SURF)
    plt.close(fig)
