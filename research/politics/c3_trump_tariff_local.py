"""C3: do Trump's tariff posts move BTC volatility under time-local controls (own posts only)?

Part C, declared follow-up. The design is fixed in
`research/politics/FOLLOWUP_TRUMP_TARIFF_LOCAL.md`, written and hashed after the C2
local-controls run had been seen and before anything here was computed; this script
refuses to run if that file, or either Trump post file, has changed. It reuses the v1
machinery of `c1_trump_posts.py` and the local-control functions of `c2_ranking.py` by
import, and changes neither. Run from the repository root:

    PYTHONPATH=src .venv/bin/python research/politics/c3_trump_tariff_local.py

It writes research/politics/data/c3_trump_tariff_local.{json,md,png}.

Differences from the C2 local run: only Trump's two files (Truth Social, frozen v1
conversion, and 2020 X) are read; events use the v1 clean rule with no cross-person
overlap rule; controls (same minute of the week within plus or minus 4 weeks, at least 6)
are barred only near Trump's own posts.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (ROOT / "src", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import c1_trump_posts as c1
import c2_ranking as c2

FOLLOWUP = HERE / "FOLLOWUP_TRUMP_TARIFF_LOCAL.md"
FOLLOWUP_SHA = "5ddb736327a041b4d1e358330dd510b9313c4996509becac9e89805c1f2a3c38"
POST_FILES = {
    "truth_realDonaldTrump.csv": c1.POSTS_SHA,
    "x_realDonaldTrump.csv": "42c3abaad0aa7e626cd31bc4a6e860a1272d654f1293bf759c8ed8a59c4819a7",
}
OUT = HERE / "data"
STEM = "c3_trump_tariff_local"
TOPICS = c1.TOPICS
LABEL = c1.LABEL
SYMBOLS = c1.SYMBOLS
SPANS = {
    "2025-10-10": (dt.datetime(2025, 10, 10, tzinfo=dt.UTC),
                   dt.datetime(2025, 10, 12, tzinfo=dt.UTC)),
    "2025-04-09": (dt.datetime(2025, 4, 9, tzinfo=dt.UTC),
                   dt.datetime(2025, 4, 10, tzinfo=dt.UTC)),
}
ROBUST = {"without 2025-10-10": ("2025-10-10",), "without 2025-04-09": ("2025-04-09",),
          "without both": ("2025-10-10", "2025-04-09")}
# reference results, copied from the frozen reports
V1_REF = {"source": "data/c1_trump_posts.md", "n": 199, "mean": 3.64, "lo": 1.09, "hi": 6.53,
          "p": 0.0002, "diff": 3.34, "diff_lo": 0.83, "diff_hi": 6.28, "pmp": 2.81,
          "pmp_lo": 0.56, "pmp_hi": 5.38}
C2_LOCAL = OUT / "c2_ranking_local.json"


# ---------------------------------------------------------------------------- inputs

def check_inputs(followup: Path = FOLLOWUP, expected: str = FOLLOWUP_SHA,
                 posts_dir: Path = c2.POSTS, files: dict | None = None) -> dict:
    """Refuse to run if the follow-up document or a Trump post file changed."""
    shas = {followup.name: c2.check_prereg(followup, expected)}
    for name, sha in (POST_FILES if files is None else files).items():
        shas[name] = c2.check_prereg(posts_dir / name, sha)
    return shas


def load_trump(posts_dir: Path = c2.POSTS) -> list[dict]:
    """Both Trump files pooled as one person (C2 minute grid), sorted by time."""
    files = [{"file": n, "path": posts_dir / n, "person": "Donald Trump", "group": "trump"}
             for n in POST_FILES]
    return c2.load_people(files)["Donald Trump"]["posts"]


def trump_events(posts: list[dict], n_min: int = c2.N_MIN) -> list[dict]:
    """v1 events (merge, topic, clean) with no cross-person rule; in_period on the C2 grid."""
    events = c1.build_events(posts)
    for e in events:
        e["minute"] = c2.minute_of(e["ts"])
        e["in_period"] = bool(c1.PRE_SPAN <= e["minute"] < n_min - c1.POST_SPAN)
    return events


# ---------------------------------------------------------------------------- controls

def span_mask(names, n: int = c2.N_MIN) -> np.ndarray:
    """True at minutes inside any of the named robustness spans."""
    out = np.zeros(n, bool)
    for k in names:
        a, b = (c2.minute_of(t) for t in SPANS[k])
        out[max(a, 0):min(b, n)] = True
    return out


def control_eligible(valid: np.ndarray, own_post_min: np.ndarray,
                     barred: np.ndarray | None = None) -> np.ndarray:
    """Eligible control minutes: complete window, no Trump post within 60 minutes, not
    barred. Nobody else's posts enter."""
    elig = valid & ~c1.busy_mask(own_post_min, valid.size)
    if barred is not None:
        elig &= ~barred
    return elig


def run_symbol(arr: dict, valid: np.ndarray, ev_min: np.ndarray, own_post_min: np.ndarray,
               pool_min: np.ndarray | None, barred: np.ndarray | None = None) -> dict:
    """Abnormal outcomes with local controls for events and (optionally) placebo minutes."""
    n = valid.size
    elig = control_eligible(valid, own_post_min, barred)
    ok = (ev_min >= c1.PRE_SPAN) & (ev_min < n - c1.POST_SPAN)
    ok[ok] &= valid[ev_min[ok]]
    if barred is not None:
        ok[ok] &= ~barred[ev_min[ok]]
    anchors = np.where(ok, ev_min, c1.PRE_SPAN)
    ctrl, enough = c2.pick_local_controls(anchors, elig)
    good = ok & enough
    out = {"ab": c2.abnormal_local(arr, anchors, ctrl, good), "ok": good, "win_ok": ok,
           "ctrl": ctrl}
    if pool_min is not None:
        pm = pool_min[elig[pool_min]]  # elig = valid, no Trump post within 60, not barred
        pctrl, penough = c2.pick_local_controls(pm, elig)
        pab = c2.abnormal_local(arr, pm, pctrl, penough)
        out["pool"] = {w: {k: v[penough] for k, v in d.items()} for w, d in pab.items()}
    return out


# ---------------------------------------------------------------------------- verdict

def excludes_zero(lo, hi) -> bool:
    return lo is not None and hi is not None and np.isfinite(lo) and np.isfinite(hi) \
        and (lo > 0 or hi < 0)


def verdict(diff: dict, pmp: dict) -> dict:
    """The pre-stated decision rule: 'supports an effect' when the tariff-minus-other
    interval and the tariff post-minus-pre interval both exclude zero."""
    a, b = excludes_zero(diff["lo"], diff["hi"]), excludes_zero(pmp["lo"], pmp["hi"])
    label = "supports an effect" if a and b else "does not support an effect"

    def part(name, d, ex):
        where = ("lies above zero" if d["lo"] > 0 else "lies below zero") if ex \
            else "includes zero"
        if d["lo"] is None or d["hi"] is None:
            return f"{name}: too few events for an interval"
        return (f"{name} {d['mean']:+.2f} bps [{d['lo']:.2f}, {d['hi']:.2f}], "
                f"interval {where}")
    sentence = (f"The follow-up **{label}**: "
                + part("tariff minus other", diff, a) + "; "
                + part("tariff post minus pre", pmp, b) + ".")
    return {"label": label, "primary_excludes_zero": a, "pmp_excludes_zero": b,
            "sentence": sentence}


# ---------------------------------------------------------------------------- analysis

def _block(x: np.ndarray, pool: np.ndarray) -> dict:
    return c1.stats_block(x, pool)


def _diff(x: np.ndarray, y: np.ndarray) -> dict:
    x, y = x[np.isfinite(x)], y[np.isfinite(y)]
    if x.size < 2 or y.size < 2:
        return {"mean": np.nan, "lo": None, "hi": None, "p": np.nan}
    lo, hi = c1.boot_diff(x, y)
    return {"mean": float(x.mean() - y.mean()), "lo": float(lo), "hi": float(hi),
            "p": c1.label_perm_p(x, y)}


def analyze() -> dict:
    shas = check_inputs()
    posts = load_trump()
    events = trump_events(posts)
    post_min = np.array([r["minute"] for r in posts], dtype=np.int64)
    ev_min = np.array([e["minute"] for e in events], dtype=np.int64)
    topic = np.array([e["topic"] for e in events])
    clean = np.array([e["clean"] and e["in_period"] for e in events])
    runs: dict = {}
    pool_min = None
    for sym in SYMBOLS:
        px = c2.load_prices(sym)
        arr = c1.minute_arrays(px["close"], px["vol"], px["tb"])
        valid = c1.valid_mask(px["close"])
        if sym == "BTCUSDT":
            rng = np.random.default_rng(c1.SEED)
            cand = np.flatnonzero(control_eligible(valid, post_min))
            pool_min = np.sort(rng.choice(cand, min(c1.N_POOL, cand.size), replace=False))
            runs[(sym, "main")] = run_symbol(arr, valid, ev_min, post_min, pool_min)
            for name, spans in ROBUST.items():
                runs[(sym, name)] = run_symbol(arr, valid, ev_min, post_min, pool_min,
                                               span_mask(spans))
        else:
            runs[(sym, "main")] = run_symbol(arr, valid, ev_min, post_min, pool_min)
        del arr, px, valid

    def x_of(t, w="post5", m="rv", sym="BTCUSDT", run="main"):
        r = runs[(sym, run)]
        return r["ab"][w][m][clean & r["ok"] & (topic == t)]

    def pool_of(w="post5", m="rv", sym="BTCUSDT", run="main"):
        return runs[(sym, run)]["pool"][w][m]

    counts = {}
    main = runs[("BTCUSDT", "main")]
    for t in TOPICS:
        s = topic == t
        counts[t] = {"events": int(s.sum()),
                     "in_period": int((s & np.array([e["in_period"] for e in events])).sum()),
                     "clean": int((s & clean).sum()),
                     "window_ok": int((s & clean & main["win_ok"]).sum()),
                     "kept": int((s & clean & main["ok"]).sum()),
                     "dropped": int((s & clean & main["win_ok"] & ~main["ok"]).sum()),
                     "mean_ctrl": float((main["ctrl"][s & clean & main["ok"]] >= 0)
                                        .sum(axis=1).mean())
                     if (s & clean & main["ok"]).any() else None}

    def core(run="main"):
        tar, oth = x_of("tariffs", run=run), x_of("other", run=run)
        return {"tariffs": _block(tar, pool_of(run=run)),
                "other": _block(oth, pool_of(run=run)),
                "diff": _diff(tar, oth),
                "pmp": _block(x_of("tariffs", w="pmp", run=run), pool_of(w="pmp", run=run)),
                "pre": _block(x_of("tariffs", w="pre5", run=run), pool_of(w="pre5", run=run))}

    res: dict = {"followup_sha256": shas[FOLLOWUP.name], "post_sha256": shas,
                 "generated_utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "period": [c2.T0.isoformat(), c2.T_END.isoformat()],
                 "posts": len(posts), "events": len(events), "counts": counts,
                 "pool": int(pool_of().size)}
    res["primary"] = core()
    pr = res["primary"]
    res["verdict"] = verdict(pr["diff"], {"mean": pr["pmp"]["mean"], "lo": pr["pmp"]["lo"],
                                          "hi": pr["pmp"]["hi"]})
    res["robust"] = {}
    for name in ROBUST:
        c = core(name)
        c["verdict"] = verdict(c["diff"], {"mean": c["pmp"]["mean"], "lo": c["pmp"]["lo"],
                                           "hi": c["pmp"]["hi"]})["label"]
        res["robust"][name] = c
    sec: dict = {}
    for label, kw in (("BTCUSDT rv +1..+5", {}), ("BTCUSDT rv -5..-1", {"w": "pre5"}),
                      ("BTCUSDT rv post minus pre", {"w": "pmp"}),
                      ("BTCUSDT absret +1..+5", {"m": "absret"}),
                      ("BTCUSDT logvol +1..+5", {"m": "logvol"}),
                      ("BTCUSDT imb +1..+5", {"m": "imb"}),
                      ("ETHUSDT rv +1..+5", {"sym": "ETHUSDT"}),
                      ("SOLUSDT rv +1..+5", {"sym": "SOLUSDT"}),
                      ("ETHUSDT rv post minus pre", {"sym": "ETHUSDT", "w": "pmp"}),
                      ("SOLUSDT rv post minus pre", {"sym": "SOLUSDT", "w": "pmp"})):
        sec[label] = {t: _block(x_of(t, **kw), pool_of(**kw)) for t in TOPICS}
    res["secondary"] = sec
    if C2_LOCAL.exists():
        c2l = json.loads(C2_LOCAL.read_text(encoding="utf-8"))
        a = c2l["topics"]["tariffs"]["people"].get("Donald Trump", {})
        b = c2l["pmp_topics"]["tariffs"]["people"].get("Donald Trump", {})
        res["c2_local_ref"] = {"source": "data/c2_ranking_local.json", "n": a.get("n"),
                               "mean": a.get("raw"), "lo": a.get("raw_lo"),
                               "hi": a.get("raw_hi"), "p": a.get("p"), "pmp": b.get("raw"),
                               "pmp_lo": b.get("raw_lo"), "pmp_hi": b.get("raw_hi")}
    res["v1_ref"] = V1_REF
    return c2._num(res)


# ---------------------------------------------------------------------------- report

def _f(x, d=2) -> str:
    return "n/a" if x is None else f"{x:.{d}f}"


def _p(x) -> str:
    return c1._p(x) if x is not None else "n/a"


def _row(b: dict, d=2) -> str:
    return f"{_f(b['mean'], d)} [{_f(b['lo'], d)}, {_f(b['hi'], d)}]"


def report(res: dict) -> str:
    pr, cnt = res["primary"], res["counts"]
    L = ["# C3: Trump's tariff posts under time-local controls (own posts only)", "",
         ("**Declared follow-up, decided after seeing the C2 local-controls result; not "
         "pre-registered.** Design: `research/politics/FOLLOWUP_TRUMP_TARIFF_LOCAL.md`. "
         "Generated by `research/politics/c3_trump_tariff_local.py` (run "
         f"{res['generated_utc']})."), "",
         f"- follow-up sha256 `{res['followup_sha256']}`"]
    for k, v in res["post_sha256"].items():
        if k != FOLLOWUP.name:
            L.append(f"- `posts/{k}` sha256 `{v}`")
    L += ["", "## Verdict (decision rule stated in advance)", "", res["verdict"]["sentence"],
          "", "## Events", "",
          (f"Trump's two files pooled: {res['posts']:,} posts, {res['events']:,} events "
          "(original and quote posts merged within 5 minutes). Clean = no earlier Trump "
          "event within 60 minutes; no cross-person rule. Kept = complete BTCUSDT window and "
          "at least 6 of the 8 same-minute-of-week controls within plus or minus 4 weeks "
          "free of any Trump post within 60 minutes. Dropped = clean with a complete window "
          f"but fewer than 6 controls. Placebo pool: {res['pool']:,} random minutes."), "",
          ("| topic | events | clean, in period | complete window | dropped (< 6 controls) "
          "| kept | mean controls |"), "|---|---|---|---|---|---|---|"]
    for t in TOPICS:
        c = cnt[t]
        L.append(f"| {LABEL[t]} | {c['events']:,} | {c['clean']:,} | {c['window_ok']:,} | "
                 f"{c['dropped']:,} | {c['kept']:,} | {_f(c['mean_ctrl'], 1)} |")
    d, pm = pr["diff"], pr["pmp"]
    L += ["", "## Primary: BTCUSDT abnormal realized volatility, minutes +1 to +5", "",
          ("Mean abnormal rv in bps, 95% bootstrap interval, placebo p (random minutes with "
          "the same local controls). Tariff minus other: bootstrap within groups, "
          "permutation p."), "",
          "| quantity | events | estimate [95% CI] | p |", "|---|---|---|---|",
          (f"| Tariffs/trade | {pr['tariffs']['n']} | {_row(pr['tariffs'])} | "
          f"{_p(pr['tariffs']['p'])} (placebo) |"),
          (f"| Other | {pr['other']['n']} | {_row(pr['other'])} | "
          f"{_p(pr['other']['p'])} (placebo) |"),
          (f"| **Tariffs minus other (primary test)** | | **{_row(d)}** | "
          f"**{_p(d['p'])}** (permutation) |"),
          (f"| Tariffs, minutes -5 to -1 | {pr['pre']['n']} | {_row(pr['pre'])} | "
          f"{_p(pr['pre']['p'])} (placebo) |"),
          (f"| **Tariffs, post minus pre** | {pm['n']} | **{_row(pm)}** | "
          f"{_p(pm['p'])} (placebo) |"),
          "", "## Robustness", "",
          ("| sample | tariff events | tariffs | tariffs minus other (perm. p) | "
          "post minus pre (placebo p) | verdict |"), "|---|---|---|---|---|---|",
          (f"| all (primary) | {pr['tariffs']['n']} | {_row(pr['tariffs'])} | {_row(d)} "
          f"({_p(d['p'])}) | {_row(pm)} ({_p(pm['p'])}) | {res['verdict']['label']} |")]
    for name, c in res["robust"].items():
        L.append(f"| {name} | {c['tariffs']['n']} | {_row(c['tariffs'])} | {_row(c['diff'])} "
                 f"({_p(c['diff']['p'])}) | {_row(c['pmp'])} ({_p(c['pmp']['p'])}) | "
                 f"{c['verdict']} |")
    L += ["", ("Spans drop events and bar control and placebo minutes from 2025-10-10 00:00 to "
          "2025-10-12 00:00 UTC and from 2025-04-09 00:00 to 2025-04-10 00:00 UTC."), "",
          "## Comparison with v1 and the C2 cross-person local run", "",
          "BTCUSDT abnormal rv +1..+5 for Trump's tariff/trade posts, bps.", "",
          "| run | controls | events | tariffs [95% CI] | p | post minus pre [95% CI] |",
          "|---|---|---|---|---|---|"]
    v = res["v1_ref"]
    L.append(f"| v1 (`c1_trump_posts.md`) | 16 within 26 weeks, own posts | {v['n']} | "
             f"{v['mean']:.2f} [{v['lo']:.2f}, {v['hi']:.2f}] | {_p(v['p'])} | "
             f"{v['pmp']:.2f} [{v['pmp_lo']:.2f}, {v['pmp_hi']:.2f}] |")
    if res.get("c2_local_ref"):
        r = res["c2_local_ref"]
        L.append(f"| C2 local (`c2_ranking_local.md`) | 6+ within 4 weeks, any tracked "
                 f"person; overlap rule | {r['n']} | {_f(r['mean'])} [{_f(r['lo'])}, "
                 f"{_f(r['hi'])}] | {_p(r['p'])} | {_f(r['pmp'])} [{_f(r['pmp_lo'])}, "
                 f"{_f(r['pmp_hi'])}] |")
    L.append(f"| **C3 (this run)** | 6+ within 4 weeks, Trump's posts only | "
             f"{pr['tariffs']['n']} | {_row(pr['tariffs'])} | {_p(pr['tariffs']['p'])} | "
             f"{_row(pm)} |")
    L += ["", (f"v1 tariff minus other: {v['diff']:.2f} [{v['diff_lo']:.2f}, "
          f"{v['diff_hi']:.2f}]. v1 covers 2022-02 to 2026-10 (Truth Social only); C2 and C3 "
          "add the 2020 tweets."), "",
          "## Secondary outcomes (descriptive, raw p)", "",
          ("Mean abnormal [95% CI] (placebo p, n). Units: bps for rv and absret; log points "
          "for logvol; imbalance in [-1, 1]."), "",
          "| outcome | " + " | ".join(LABEL[t] for t in TOPICS) + " |",
          "|---|" + "---|" * len(TOPICS)]
    for label, blk in res["secondary"].items():
        dd = 3 if ("logvol" in label or "imb" in label) else 2
        L.append(f"| {label} | " + " | ".join(
            f"{_row(blk[t], dd)} ({_p(blk[t]['p'])}, {blk[t]['n']})" if blk[t]["n"] else "n/a"
            for t in TOPICS) + " |")
    L += ["", "## Caveats", "",
          ("- Decided after seeing the C2 local result and aimed at the topic v1 singled out; "
          "it checks v1's tariff finding, it cannot confirm it independently."),
          ("- Trump posts at the same hours week after week, so most clean events lack 6 "
          "post-free nearby weeks and are dropped; the kept events tilt toward hours where "
          "he posts irregularly."),
          ("- Other politicians' posts can fall inside event or control windows (they are "
          "ignored by design)."),
          ("- All caveats of v1 (`c1_trump_posts.md`) apply: crude keywords, inferred kinds, "
          "1,116 quote posts read as reposts, futures only, no macro-release exclusion."),
          "", f"![C3 figure]({STEM}.png)", ""]
    return "\n".join(L)


def plot(res: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    ax = axes[0]
    sec = res["secondary"]
    x = np.arange(len(TOPICS))
    for j, (key, off, lab, col) in enumerate((
            ("BTCUSDT rv -5..-1", -0.18, "pre: -5 to -1", "#a3a29c"),
            ("BTCUSDT rv +1..+5", 0.18, "post: +1 to +5", "#0b0b0b"))):
        m = np.array([sec[key][t]["mean"] if sec[key][t]["n"] else np.nan for t in TOPICS],
                     dtype=float)
        lo = np.array([sec[key][t]["lo"] if sec[key][t]["lo"] is not None else np.nan
                       for t in TOPICS], dtype=float)
        hi = np.array([sec[key][t]["hi"] if sec[key][t]["hi"] is not None else np.nan
                       for t in TOPICS], dtype=float)
        ax.errorbar(x + off, m, yerr=[m - lo, hi - m], fmt="o" if j else "s", ms=8,
                    color=col, capsize=4, lw=2, label=lab)
    ax.axhline(0, color="#52514e", lw=0.8)
    ax.set_xticks(x, [f"{LABEL[t]}\n(n={res['counts'][t]['kept']})" for t in TOPICS])
    ax.set_ylabel("mean abnormal realized vol, bps (95% CI)")
    ax.set_title("A. BTCUSDT, local controls (Trump's posts only)")
    ax.legend(frameon=False, fontsize=9)

    ax = axes[1]
    rows = []
    v = res["v1_ref"]
    rows.append((f"v1, 26-week controls (n={v['n']})", v["mean"], v["lo"], v["hi"], "#8a8984"))
    if res.get("c2_local_ref"):
        r = res["c2_local_ref"]
        rows.append((f"C2 local, cross-person (n={r['n']})", r["mean"], r["lo"], r["hi"],
                     "#8a8984"))
    pr = res["primary"]
    rows.append((f"C3 tariffs (n={pr['tariffs']['n']})", pr["tariffs"]["mean"],
                 pr["tariffs"]["lo"], pr["tariffs"]["hi"], "#eb6834"))
    rows.append(("C3 tariffs minus other", pr["diff"]["mean"], pr["diff"]["lo"],
                 pr["diff"]["hi"], "#eb6834"))
    rows.append(("C3 tariffs post minus pre", pr["pmp"]["mean"], pr["pmp"]["lo"],
                 pr["pmp"]["hi"], "#eb6834"))
    for name, c in res["robust"].items():
        rows.append((f"C3 {name} (n={c['tariffs']['n']})", c["tariffs"]["mean"],
                     c["tariffs"]["lo"], c["tariffs"]["hi"], "#2a78d6"))
    for i, (lab, m, lo, hi, col) in enumerate(rows):
        if m is None or lo is None or hi is None:
            continue
        ax.plot([lo, hi], [i, i], color=col, lw=2)
        ax.plot(m, i, "o", color=col, ms=7)
    ax.axvline(0, color="#52514e", lw=0.8)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel("abnormal realized vol +1 to +5, bps (95% CI)")
    ax.set_title("B. Trump tariff posts across designs")
    for a in axes:
        a.spines[["top", "right"]].set_visible(False)
        a.grid(axis="y", color="#ecebe8", lw=0.6)
    fig.suptitle("C3: Trump tariff posts and BTC volatility, nearby-week controls "
                 f"({res['verdict']['label']})", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main(argv: list[str]) -> int:
    check_inputs()
    res = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{STEM}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    plot(res, OUT / f"{STEM}.png")
    (OUT / f"{STEM}.md").write_text(report(res), encoding="utf-8")
    print("wrote", (OUT / f"{STEM}.md").relative_to(ROOT))
    print(res["verdict"]["sentence"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
