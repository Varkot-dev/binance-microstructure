"""Report stage of Q12: verdict, Markdown, JSON and figure from per-symbol caches.

Reads only the JSON records written by `q12_neural_ceiling` under
data/ml_cache/q12/, so it runs without PyTorch and without the tick data.
Every sentence of the verdict is assembled here from the numbers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from microstructure.data.jsonio import dumps_strict

CACHE_SUBDIR = Path("ml_cache") / "q12"
STEM = "q12_neural_ceiling"

# Below this many nats per event I do not call a difference material even when
# its interval excludes zero (the threshold proposed in the research notes
# before any data was scored).
MATERIAL_NATS = 0.01

# One hue stepped light to dark for the ordered Hawkes family, a second hue for
# the neural model; marker shapes repeat the identity so it never rests on color.
_STYLE = {
    "hawkes_k1": ("Hawkes K=1", "#86b6ef", "o"),
    "hawkes_k2": ("Hawkes K=2", "#3987e5", "s"),
    "hawkes_k3": ("Hawkes K=3", "#1c5cab", "D"),
    "neural": ("Neural (GRU + log-normal mixture)", "#eb6834", "^"),
}


def _unit(r: dict) -> str:
    return f"{r['symbol']} {r['month']}"


def _hawkes_names(r: dict) -> list[str]:
    return [m for m in r["models"] if m.startswith("hawkes_k")]


def classify(ci: dict) -> str:
    """Sign of a paired difference judged by its day-block interval."""
    lo, hi = ci["ci95"]
    if lo > 0:
        return "neural_better"
    if hi < 0:
        return "hawkes_better"
    return "indistinguishable"


def summarize(records: list[dict]) -> dict:
    """Verdict computed from the records; no sentence here is fixed in advance."""
    n = len(records)
    if n == 0:
        return {"n_units": 0, "headline": "No symbol-month was scored, so there is no verdict."}
    classes = [classify(r["neural_minus_best_hawkes"]) for r in records]
    gaps = np.array([r["neural_minus_best_hawkes"]["estimate"] for r in records])
    neural_gain = np.array([r["models"]["neural"]["test_gain"]["estimate"] for r in records])
    n_better = classes.count("neural_better")
    n_worse = classes.count("hawkes_better")
    n_same = classes.count("indistinguishable")
    n_material = sum(c == "neural_better" and g >= MATERIAL_NATS
                     for c, g in zip(classes, gaps, strict=True))
    names = sorted({m for r in records for m in _hawkes_names(r)})
    shares = {}
    for m in names:
        vals = [r["models"][m]["share_of_neural_gain"] for r in records if m in r["models"]]
        vals = [v for v in vals if v is not None]
        shares[m] = float(np.median(vals)) if vals else None
    n_seed_fragile = sum(
        r["neural"]["seed_spread_test_gain"] >= abs(g) and len(r["neural"]["seeds"]) > 1
        for r, g in zip(records, gaps, strict=True)
    )
    n_neural_below_poisson = int((neural_gain <= 0).sum())

    share_txt = ", ".join(
        f"K={m[-1]} {100 * s:.0f}%" for m, s in shares.items() if s is not None
    ) or "not defined (the neural model did not beat Poisson)"
    headline = (
        f"Across {n} symbol-month(s), the neural model's held-out timing likelihood is "
        f"{np.median(neural_gain):+.4f} nats per event over Poisson (median), and "
        f"{np.median(gaps):+.4f} over the validation-selected Hawkes (median, range "
        f"{gaps.min():+.4f} to {gaps.max():+.4f}). The day-block 95% interval for neural minus "
        f"best Hawkes lies above zero on {n_better} of {n}, below zero on {n_worse}, and "
        f"contains zero on {n_same}. Median share of the Poisson-to-neural gain already "
        f"captured by each Hawkes: {share_txt}."
    )
    if n_material > n / 2:
        reading = (
            f"On {n_material} of {n} the gap is both resolved and at least {MATERIAL_NATS} nats "
            "per event, so on this sample the linear self-exciting form leaves one-step-ahead "
            "timing structure unexplained."
        )
    elif n_worse > n / 2:
        reading = (
            f"On {n_worse} of {n} the Hawkes fit scores higher than the network, so this "
            "network is not a ceiling there: it bounds from below what a flexible model could "
            "do and says nothing against the Hawkes family."
        )
    else:
        reading = (
            f"Only {n_material} of {n} show a gap that is both resolved and at least "
            f"{MATERIAL_NATS} nats per event, so on this sample the exponential-sum Hawkes "
            "family is close to what this network extracts for one-step-ahead timing."
        )
    return {
        "n_units": n, "n_neural_better": n_better, "n_hawkes_better": n_worse,
        "n_indistinguishable": n_same, "n_material": int(n_material),
        "material_threshold_nats": MATERIAL_NATS,
        "median_neural_gain_over_poisson": float(np.median(neural_gain)),
        "median_neural_minus_best_hawkes": float(np.median(gaps)),
        "median_share_of_neural_gain": shares,
        "n_seed_spread_exceeds_gap": int(n_seed_fragile),
        "n_neural_not_above_poisson": n_neural_below_poisson,
        "headline": headline, "reading": reading,
    }


# ---------------------------------------------------------------------------
# Figure.
# ---------------------------------------------------------------------------


def plot(out_dir: Path, records: list[dict]) -> None:
    """Held-out nats per event over Poisson, one row per symbol-month, one mark per model."""
    rows = sorted(records, key=lambda r: (r["month"], -r["n_events"]))
    fig, ax = plt.subplots(figsize=(9.5, 1.6 + 0.62 * max(len(rows), 1)))
    offsets = np.linspace(0.27, -0.27, len(_STYLE))
    for (name, (label, color, marker)), off in zip(_STYLE.items(), offsets, strict=True):
        ys, xs, err = [], [], [[], []]
        for i, r in enumerate(rows):
            if name not in r["models"]:
                continue
            g = r["models"][name]["test_gain"]
            ys.append(i + off)
            xs.append(g["estimate"])
            err[0].append(g["estimate"] - g["ci95"][0])
            err[1].append(g["ci95"][1] - g["estimate"])
        if xs:
            ax.errorbar(xs, ys, xerr=err, fmt=marker, color=color, markersize=7, linewidth=0,
                        elinewidth=1.5, capsize=2.5, markeredgecolor="white",
                        markeredgewidth=0.8, label=label)
    ax.axvline(0.0, color="#8a8a86", linewidth=1.0)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([_unit(r) for r in rows])
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.set_xlabel("held-out nats per event over Poisson (interval-censored; 95% day-block CI)")
    ax.set_title("Q12: one-step-ahead timing likelihood, Hawkes K=1,2,3 vs neural", loc="left")
    ax.grid(axis="x", color="#e4e3df", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.legend(fontsize=8, frameon=False, loc="lower center", ncol=4)
    fig.tight_layout(rect=(0.0, 0.4 / fig.get_figheight(), 1.0, 1.0))
    fig.savefig(out_dir / f"{STEM}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Markdown.
# ---------------------------------------------------------------------------


def _ci(d: dict) -> str:
    return f"{d['estimate']:+.4f} [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}]"


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{100 * v:.0f}%"


def _method_lines(cfg: dict) -> list[str]:
    net = cfg["tpp"]
    return [
        "## Method",
        "",
        ("**Data and split.** Aggressor-level events (`load_events`) of one symbol-month, split "
        "on whole UTC days: 20 training days, 2 validation days, 1 embargo day, the remaining "
        "days are the test block (`microstructure.ml.dataset.split_masks`)."),
        "",
        ("**Business time.** As in Q6 and Q6b (`intraday_rate_profile`, 48 bins, then "
        "`rescale_to_business_time`), except that the profile is estimated on the training days "
        "only and applied unchanged to validation and test, so intraday seasonality is counted "
        "neither as self-excitation nor as neural skill."),
        "",
        ("**Score: interval-censored likelihood, the same for every model.** Timestamps are "
         "integer milliseconds and gaps of 0 and 1 ms are common, so a continuous density is "
         "not a usable score: a log-normal density at a gap of 0 is zero, and a narrow mixture "
         "component or a Hawkes kernel with a very large beta can push the density on lattice "
         "values arbitrarily high. I read the stamps as floors of the true times. If the "
         "previous event truly happened u ms after its stamp, an event recorded d ms later has "
         "a true gap in [d - u, d + 1 - u). Averaging over u uniform on [0, 1), the probability "
         "of the recorded gap is P(d) = integral of F(d + 1 - u) - F(d - u) du, with F the "
         "model's conditional gap CDF and F = 0 below 0, and the score is log P(d). This is the "
         "interval [max(d - 1, 0), d + 1) with the weighting inside it that makes the masses "
         "sum to 1; unweighted, those overlapping intervals would sum to about 2. The integral "
         "uses a 4-node Gauss-Legendre rule, and for each node the cells tile the half-line, so "
         "the rule is an exactly normalized probability mass function over the recorded gap "
         "for any F. The log score is therefore proper, at most zero, finite at d = 0, and "
         "cannot be improved by spiking. The millisecond is mapped to business time exactly by "
         "pushing the times ts and ts + 1 ms through the time change (its business-time width "
         "is the local rate times 1 ms). F is closed form for the log-normal mixture (mixture "
         "of normal CDFs in log time) and for an exponential-sum Hawkes (survival "
         "exp(-Lambda(x)) with Lambda(x) = mu x + sum_k alpha_k A_k (1 - exp(-beta_k x)) and "
         "A_k the recursive state after the previous event). Validation by simulation is in "
         "tests/ml/test_tpp.py."),
        "",
        ("**Tie truncation.** Same-millisecond same-side prints are one event, so a millisecond "
         "holds at most a sell and a buy. After such a pair the next recorded gap is at least "
         "1 ms by construction of the data. Every model is conditioned on that known support "
         "(after a tied event the score is log(P(d) / (1 - P(0)))), so that learning this "
         "artifact is not credited to the network."),
        "",
        ("**Models.** Poisson: constant rate from the training block. Hawkes K = 1, 2, 3: "
        f"`fit_hawkes_exp` and `fit_hawkes_multiexp` on {cfg['hawkes_chunks']} contiguous "
        f"training chunk(s) of at most {cfg['hawkes_fit_events']:,} events (Q6b's cap). Those "
        "fits maximize a continuous likelihood on the recorded times, while the network is "
        "trained on the censored score itself. To keep the comparison fair each K also gets a "
        f"Nelder-Mead polish of the censored training score ({cfg['polish_iters']} iterations "
        f"on {cfg['polish_events']:,} events, started from its MLE). For each K the candidate "
        "with the best validation score is used; validation plays the same role for the "
        "network (early stopping and seed choice). Neural: a GRU with "
        f"{net['hidden']} hidden units and a {net['n_components']}-component log-normal mixture "
        "for the next gap (Shchur, Bilos and Gunnemann 2020). Inputs per event: the log gap and "
        "log exponentially weighted event rates at horizons "
        f"{', '.join(f'{h:g}' for h in net['horizons_s'])} business-time seconds, standardized "
        "with training statistics. No trade sign is used: within a tied millisecond the order "
        "of signs is fixed by the sort and would leak a timing artifact. Training: truncated "
        f"backpropagation on random contiguous windows of {net['window']} events (the first "
        f"{net['window_burn']} warm the state and are not scored), at most "
        f"{net['max_windows_per_epoch']:,} windows per epoch, up to {net['epochs']} epochs, "
        f"batch {net['batch_size']}, Adam at {net['lr']:g}, {cfg['n_seeds']} seed(s)."),
        "",
        ("**Same events, same warm-up.** At the first event of the test block every model starts "
        f"from an empty state. The first {cfg['burn_in']:,} events are fed and not scored. All "
        "models are scored on the same remaining events. The network reads between "
        f"{net['window_burn']} and {net['window'] - 1} past events through its recurrent state "
        "(the same window layout as in training) and the slow rate inputs beyond that."),
        "",
        ("**Reported.** Mean score minus the Poisson score, in nats per event. Intervals are 95% "
        "percentile intervals from resampling whole UTC test days "
        f"({cfg['n_boot']:,} resamples) of per-event differences, paired across models. "
        "Residuals: by the time-rescaling theorem the compensator increments of a correct model "
        "are independent Exp(1). Because a gap is only known up to its cell I use the "
        "randomized probability integral transform (a uniform draw between the model's survival "
        "at the two cell edges), which is exactly Exp(1) under a correct model and has no atom "
        "from ties. I report the KS distance to Exp(1) and lag-1 autocorrelations, not "
        "p-values: at these sample sizes every model is rejected."),
        "",
    ]


def write_md(out_dir: Path, result: dict) -> None:
    records, v = result["records"], result["verdict"]
    L: list[str] = [
        ("# Q12: how much held-out timing likelihood does the linear Hawkes family leave "
        "unexplained?"),
        "",
        "## Question",
        "",
        ("Q6 and Q6b fit exponential-kernel Hawkes models to trade arrivals; the branching ratio "
        "depends on the kernel family. A neural point process cannot settle that, but it can "
        "answer a well-posed question: on identical held-out events, how many nats per event "
        "better is a flexible neural model than Poisson and than the K = 1, 2, 3 exponential "
        "Hawkes fits? If the neural model barely beats the best Hawkes, the parametric family is "
        "close to adequate for one-step-ahead timing. If it wins clearly, there is structure "
        "the linear self-exciting form misses."),
        "",
    ]
    if not records:
        L += ["## Verdict", "", v["headline"], ""]
        (out_dir / f"{STEM}.md").write_text("\n".join(L))
        return
    L += _method_lines(records[0]["config"])
    L += [
        "## Run summary", "",
        f"Symbol-months scored: {len(records)}. Failed: {len(result['failures'])}.", "",
    ]
    for f in result["failures"]:
        L.append(f"- {f['symbol']} {f['month']}: {f['reason']}")
    if result["failures"]:
        L.append("")

    names = sorted({m for r in records for m in _hawkes_names(r)})
    L += ["## Held-out nats per event over Poisson (test block, 95% day-block CI)", "",
          "| symbol-month | scored events | test days | tied (0 ms) | gap <= 1 ms | "
          + " | ".join(_STYLE[m][0] for m in names) + " | neural |",
          "|---|---|---|---|---|" + "---|" * (len(names) + 1)]
    for r in records:
        cells = [_ci(r["models"][m]["test_gain"]) if m in r["models"] else "n/a" for m in names]
        L.append(f"| {_unit(r)} | {r['n_test_scored']:,} | {r['n_test_days']} | "
                 f"{100 * r['tie_share_test']:.1f}% | {100 * r['share_gap_le_1ms_test']:.1f}% | "
                 + " | ".join(cells) + f" | {_ci(r['models']['neural']['test_gain'])} |")
    L += ["", "## Neural minus Hawkes", "",
          ("The best Hawkes is chosen on the validation block, never on the test block. Seed "
          "spread is the range of the neural test gain across seeds."), "",
          "| symbol-month | share of neural gain: "
          + " / ".join(f"K={m[-1]}" for m in names)
          + " | best Hawkes (validation) | neural minus best Hawkes | interval | seed spread |",
          "|---|---|---|---|---|---|"]
    for r in records:
        shares = " / ".join(_pct(r["models"][m]["share_of_neural_gain"]) if m in r["models"]
                            else "n/a" for m in names)
        d = r["neural_minus_best_hawkes"]
        label = {"neural_better": "above zero", "hawkes_better": "below zero",
                 "indistinguishable": "contains zero"}[classify(d)]
        L.append(f"| {_unit(r)} | {shares} | {_STYLE[r['best_hawkes']][0]} | {_ci(d)} | "
                 f"{label} | {r['neural']['seed_spread_test_gain']:.4f} |")

    L += ["", "## Hawkes fits used", "",
          ("`MLE` is the repo's continuous-likelihood fit (best training chunk by validation "
          "score); `used` is the validation-selected candidate, which is the MLE itself or its "
          "censored-score polish. n is the branching ratio, shown for reference only."), "",
          ("| symbol-month | K | used | n (used) | 1/beta (used, business s) | "
          "test gain, MLE | test gain, used |"),
          "|---|---|---|---|---|---|---|"]
    for r in records:
        for k, h in r["hawkes"].items():
            sel = h["selected"]
            scales = ", ".join(f"{1.0 / b:.3g}" for b in sorted(sel["betas"], reverse=True))
            used = r["models"][f"hawkes_k{k}"]["test_gain"]["estimate"]
            L.append(f"| {_unit(r)} | {k} | {sel['variant']} | {sel['n']:.4f} | {scales} | "
                     f"{h['mle_test_gain']:+.4f} | {used:+.4f} |")

    L += ["", "## Time-rescaling residuals (test block)", "",
          ("KS distance of the randomized residuals to Exp(1) (0 is a perfect fit; the 5% "
          "critical value for independent draws at these sizes is about 0.001 to 0.003, so "
          "read the distances as effect sizes) and lag-1 autocorrelation of the residuals z "
          "and of u = 1 - exp(-z)."), "",
          "| symbol-month | model | KS distance | lag-1 autocorr (z) | lag-1 autocorr (u) |",
          "|---|---|---|---|---|"]
    for r in records:
        for m, d in r["residuals"].items():
            label = _STYLE[m][0] if m in _STYLE else "Poisson"
            L.append(f"| {_unit(r)} | {label} | {d['ks_distance']:.4f} | "
                     f"{d['lag1_autocorr_z']:+.4f} | {d['lag1_autocorr_u']:+.4f} |")

    L += ["", "## Where the neural-minus-best-Hawkes difference comes from", "",
          ("Per recorded gap of the scored event: share of events, mean difference in nats, and "
          "contribution (share times mean; the gap rows sum to the overall difference). The "
          "last row is a separate cut: events whose predecessor was tied."), "",
          "| symbol-month | bucket | share | mean difference | contribution |",
          "|---|---|---|---|---|"]
    for r in records:
        for b in r["gap_buckets_neural_minus_best_hawkes"]:
            L.append(f"| {_unit(r)} | {b['bucket']} | {100 * b['share']:.1f}% | "
                     f"{b['mean_diff']:+.4f} | {b['contribution']:+.4f} |")

    L += ["", "## Training log", "",
          ("| symbol-month | parameters | seed | epochs run | best validation gain | test gain | "
          "seconds (Hawkes / neural) |"),
          "|---|---|---|---|---|---|---|"]
    for r in records:
        for s in r["neural"]["seeds"]:
            mark = " (used)" if s["seed"] == r["neural"]["selected_seed"] else ""
            L.append(f"| {_unit(r)} | {r['neural']['n_parameters']:,} | {s['seed']}{mark} | "
                     f"{len(s['history'])} | {s['valid_gain']:+.4f} | {s['test_gain']:+.4f} | "
                     f"{r['seconds']['hawkes']:.0f} / {r['seconds']['neural']:.0f} |")

    L += ["", "## Verdict", "", v["headline"], "", v["reading"], ""]
    if v["n_seed_spread_exceeds_gap"]:
        L += [(f"On {v['n_seed_spread_exceeds_gap']} of {v['n_units']} the spread of the neural "
              "result across seeds is at least as large as the neural-minus-Hawkes gap, so the "
              "sign of the gap there depends on the seed."), ""]
    if v["n_neural_not_above_poisson"]:
        L += [(f"On {v['n_neural_not_above_poisson']} of {v['n_units']} the network did not beat "
              "Poisson on the test block; shares are not defined there."), ""]
    days = sorted({r["n_test_days"] for r in records})
    L += [
        "## Caveats", "",
        ("- **One-step-ahead timing only.** The score is the likelihood of the next recorded "
        "gap given the past. It says nothing about multi-step simulation, about marks (side, "
        "size), or about prices, and it is not a trading result."),
        ("- **Nothing here bears on the branching ratio.** A likelihood gap between a network "
        "and a Hawkes fit does not move the 0.71 / 0.85 / 0.96 dispute of Q6 and Q6b. That "
        "dispute is about long memory versus baseline non-stationarity, which a one-step score "
        "on a few test days barely weighs, and there is no accepted way to read a branching "
        "ratio out of a recurrent network."),
        ("- **The network is a lower bound on flexible models, not an upper bound.** It is a "
        "small, short-memory model (a few hundred events of recurrent state plus "
        "exponentially weighted rates), trained briefly on CPU on a capped number of windows. A "
        "larger or longer-memory model could score higher. A small gap therefore means the "
        "Hawkes family is close to what this network finds, not that nothing better exists; a "
        "gap in favour of Hawkes means the network is not a ceiling at all."),
        ("- **The Hawkes side is also not the best possible linear model.** Constant baseline, "
        f"at most three exponentials, fitted on at most {records[0]['config']['hawkes_fit_events']:,} "
        "events per chunk with Nelder-Mead. A flexible baseline or more components would "
        "likely narrow any gap (the research notes cite evidence that it usually does)."),
        ("- **Cold start.** All models start empty at the test block and are warmed on the "
        "burn-in only, so kernel components slower than the burn-in are under-used by every "
        "model equally."),
        (f"- **Few day blocks.** The test block has {', '.join(str(d) for d in days)} day(s), so "
        "the day-block intervals rest on that many resampling units and are coarse."),
        ("- **Discretization convention.** The score assumes floor stamps with a uniform, "
         "independent sub-millisecond offset, and takes the recorded times as exact when "
         "updating the history state of every model. Stamps that are not floors, or batching "
         "in the matching engine, would shift probability between the 0 and 1 ms gaps for all "
         "models. The bucket table shows how much of any gap between models sits there."),
        ("- **Residual lattice structure.** Even with the tie truncation, a gap of 0 ms can only "
        "occur as a sell followed by a buy, which roughly halves its frequency relative to a "
        "continuous process. A flexible gap distribution can match that and an exponential "
        "kernel cannot, so part of any neural advantage in the 0 ms bucket is recording "
        "structure, not market dynamics."),
        ("- **Business-time profile** is estimated on 20 training days; drift in the intraday "
        "pattern between training and test is left in the data for every model."),
        "",
    ]
    (out_dir / f"{STEM}.md").write_text("\n".join(L))


def write_report(out_dir: Path, records: list[dict], failures: list[dict] | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    records = sorted(records, key=lambda r: (r["month"], -r["n_events"]))
    result = {"records": records, "failures": failures or [], "verdict": summarize(records)}
    (out_dir / f"{STEM}.json").write_text(dumps_strict(result))
    write_md(out_dir, result)
    plot(out_dir, records)
    return result


def load_cached(root: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((root / CACHE_SUBDIR).glob("*.json"))]


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Q12 report from data/ml_cache/q12/*.json")
    p.add_argument("--root", type=Path, default=Path("data"))
    p.add_argument("--out", type=Path, default=Path("results"))
    a = p.parse_args(argv)
    print(write_report(a.out, load_cached(a.root))["verdict"]["headline"])


if __name__ == "__main__":
    main()
