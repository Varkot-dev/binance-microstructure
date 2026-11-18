"""Q16: can a coin's own trading tell that it is about to be delisted?

Assembly only. Every number comes from Part B's saved outputs; nothing is fitted
or scored here, and the 2026 lock-box is never rescored.

Sources (all under `research/market_evolution/data/`):

- `b0_baselines.json` and `b1_models.json`: the cross-validation results of the
  baselines and models (36 test months 2023-01 to 2025-12), written by the
  `json` stage of `b0_baselines.py` and by `b1_models.py --json-only`.
- `b2_lockbox.md`: the single lock-box run. Its tables are parsed; b2 is never
  imported or rerun.
- `delisting_panel.parquet`, `contract_lifecycle.csv`, `monthly_panel.parquet`
  and `delisting_panel.md`: counts that describe the universe, the labels and
  the lock-box batches (rows, lives, stop days). These are counts of labels,
  not scores.

Run from the repository root:

    PYTHONPATH=src .venv/bin/python -m microstructure.analyses.q16_delisting

Writes `results/q16_delisting.{json,md,png}`.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import polars as pl

from microstructure.data.jsonio import dumps_strict

STEM = "q16_delisting"
ME = Path("research/market_evolution")
DATA = ME / "data"

# Candidate keys used throughout: the b2 names, plus the CV-only variants of b0 and b1.
B2_NAMES = {"(a) falling volume": "base_a", "(b) lowest volume rank": "base_b",
            "logistic, full features": "logit_full", "LightGBM, full features": "gbm_full"}
LOCKBOX_CANDIDATES = ("base_a", "base_b", "logit_full", "gbm_full")
VARIANTS = ("main", "drop final full month")
TOL = 0.0015  # rounding tolerance when b2's copied CV numbers are checked against the JSON


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------

def ci(est: float, lo: float, hi: float) -> dict:
    return {"estimate": float(est), "ci95": [float(lo), float(hi)]}


_NUM = r"[-+]?\d+(?:\.\d+)?"
_CI_RE = re.compile(rf"({_NUM}) \(({_NUM}) to ({_NUM})\)")


def parse_ci(s: str) -> dict:
    m = _CI_RE.search(s.replace(",", ""))
    if not m:
        raise ValueError(f"no 'x (lo to hi)' in {s!r}")
    return ci(*(float(g) for g in m.groups()))


def md_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    """Every Markdown table in `text` as (header, rows)."""
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        if (lines[i].startswith("|") and i + 1 < len(lines)
                and re.match(r"^\|(\s*-+\s*\|)+\s*$", lines[i + 1])):
            header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            rows, j = [], i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            out.append((header, rows))
            i = j
        else:
            i += 1
    return out


def table_starting(text: str, first_col: str) -> list[list[str]]:
    for header, rows in md_tables(text):
        if header[0] == first_col:
            return rows
    raise ValueError(f"no table with first column {first_col!r}")


def _section(text: str, start: str, stops: tuple[str, ...]) -> str:
    i = text.index(start)
    j = min((text.find(s, i + len(start)) for s in stops if text.find(s, i + len(start)) > 0),
            default=len(text))
    return text[i:j]


def _flat(s: str) -> str:
    return re.sub(r"\s+", " ", s)


# --------------------------------------------------------------------------------------
# Lock-box: parse b2's saved report (never rerun)
# --------------------------------------------------------------------------------------

def parse_b2_variant(sec: str) -> dict:
    flat = _flat(sec)
    m = re.search(r"Lock-box rows ([\d,]+) \((\d+) lives\) over (\d+) origin months "
                  r"\((\d{4}-\d{2}) to (\d{4}-\d{2})\); (\d+) positive rows from (\d+) "
                  r"event lives; base rate (.+?\))", flat)
    if not m:
        raise ValueError("lock-box size line not found")
    out = {"n_rows": int(m[1].replace(",", "")), "n_lives": int(m[2]),
           "n_months": int(m[3]), "months": [m[4], m[5]], "n_pos": int(m[6]),
           "event_lives": int(m[7]), "base": parse_ci(m[8])}
    cands = {}
    for name, prec, rec, hits, ap in table_starting(sec, "candidate"):
        h, a = (int(x) for x in hits.split("/"))
        cands[B2_NAMES[name]] = {"prec": parse_ci(prec), "rec": parse_ci(rec),
                                 "hits": h, "alerts": a, "ap": parse_ci(ap)}
    out["candidates"] = cands
    diffs = {}
    for name, prec, rec, ap in table_starting(sec, "difference"):
        key = B2_NAMES[name.removesuffix(" - (b)")]
        diffs[key] = {"prec": parse_ci(prec), "rec": parse_ci(rec), "ap": parse_ci(ap)}
    out["diffs_vs_b"] = diffs
    lomo = {}
    lm = re.search(r"left out: (.+?)\. Brier", flat)
    if lm:
        for part in lm[1].split("; "):
            nm, rng = part.rsplit(" ", 3)[0], part.rsplit(" ", 3)[1:]
            lomo[B2_NAMES[nm]] = [float(rng[0]), float(rng[2])]
    out["leave_one_month_out_prec_diff"] = lomo
    bm = re.search(rf"Brier score: logistic ({_NUM}), LightGBM ({_NUM}), predicting the "
                   rf"training base rate ({_NUM})\. Brier skill: logistic (.+?\)), LightGBM "
                   rf"(.+?\))\. Mean predicted probability: logistic ({_NUM}), LightGBM "
                   rf"({_NUM}), against an observed ({_NUM})", flat)
    if bm:
        out["brier"] = {"logit_full": float(bm[1]), "gbm_full": float(bm[2]),
                        "ref": float(bm[3]), "bss_logit_full": parse_ci(bm[4]),
                        "bss_gbm_full": parse_ci(bm[5]), "mean_pred_logit": float(bm[6]),
                        "mean_pred_gbm": float(bm[7]), "observed": float(bm[8])}
    by_month = []
    for row in table_starting(sec, "origin month"):
        month, rows, alerts, pos, lives, a, b, lg, gb = row
        by_month.append({"month": month, "rows": int(rows), "alerts": int(alerts),
                         "pos": int(pos), "lives": int(lives), "base_a": int(a),
                         "base_b": int(b), "logit_full": int(lg), "gbm_full": int(gb)})
    out["by_month"] = by_month
    return out


def parse_b2(text: str) -> dict:
    """The lock-box result as saved in `b2_lockbox.md`."""
    run_line = next((x for x in text.splitlines() if x.startswith("Lock-box runs: ")), "")
    commit = re.search(r"commit `([0-9a-f]{7,40})`", text)
    frozen = {}
    for row in table_starting(text, "run"):
        frozen[row[0]] = {"train_rows": int(row[1].replace(",", "")),
                          "train_pos": int(row[2]), "last_train_month": row[3],
                          "inner_validation": row[4], "inner_val_pos": int(row[5]),
                          "C_logit": float(row[6]), "trees_gbm": int(row[7]),
                          "train_base_rate": float(row[8])}
    results = _section(text, "## 3. Results", ("## 4.",))
    variants = {}
    for v in VARIANTS:
        sec = _section(results, f"### {v}\n", ("### ", "## 4."))
        variants[v] = parse_b2_variant(sec)
    cv_copy = {}
    comp = _section(text, "## 4.", ("## 5.",))
    for row in table_starting(comp, "metric"):
        label, key = row[0].split(": ", 1)
        if key != "base rate":
            cv_copy.setdefault(label, {})[key] = {"cv": parse_ci(row[1]),
                                                  "lockbox": parse_ci(row[2]),
                                                  "b2_verdict": row[3]}
    return {"runs": run_line.removeprefix("Lock-box runs: ").rstrip("."),
            "commit": commit[1] if commit else None, "frozen": frozen,
            "variants": variants, "cv_copied_in_b2": cv_copy,
            "n_runs": len([p for p in run_line.split(";") if p.strip()])}


# --------------------------------------------------------------------------------------
# Cross-validation: b0 and b1 JSON
# --------------------------------------------------------------------------------------

def _pc(v: dict, k: str) -> dict:
    return ci(v["point"][k], *v["ci"][k])


def cv_from_json(b0: dict, b1: dict) -> dict:
    out = {}
    for label in VARIANTS:
        v0, v1 = b0["variants"][label], b1["variants"][label]
        cands = {}
        for key, src, k, tot in (("base_a", v0, "a", v0["alerts_total"]["a"]),
                                 ("base_b", v0, "b", v0["alerts_total"]["b"]),
                                 ("logit_c", v0, "c", v0["alerts_total"]["c"])):
            cands[key] = {"prec": _pc(src, f"prec_{k}"), "rec": _pc(src, f"rec_{k}"),
                          "ap": _pc(src, f"ap_{k}"), "alerts": tot[0], "hits": tot[1]}
        for key in ("logit_full", "gbm_full", "logit_vol", "gbm_vol"):
            tot = v1["alerts_total"][key]
            cands[key] = {"prec": _pc(v1, f"prec_{key}"), "rec": _pc(v1, f"rec_{key}"),
                          "ap": _pc(v1, f"ap_{key}"), "alerts": tot[0], "hits": tot[1]}
        diffs = {k: {"prec": _pc(v1, f"prec_{k}_minus_b"), "ap": _pc(v1, f"ap_{k}_minus_b")}
                 for k in ("logit_full", "gbm_full", "logit_vol", "gbm_vol")}
        diffs["logit_c"] = {"prec": _pc(v0, "prec_c_minus_b"), "ap": _pc(v0, "ap_c_minus_b")}
        ablation = []
        for kind in ("logit", "gbm"):
            vol = v1["point"][f"prec_{kind}_vol"]
            vol_ap = v1["point"][f"ap_{kind}_vol"]
            for key in v1["point"]:
                m = re.fullmatch(rf"prec_{kind}_vol\+(.+)", key)
                if m and not key.endswith("_minus_b"):
                    k = f"{kind}_vol+{m[1]}"
                    ablation.append({
                        "key": k, "model": kind, "group": m[1],
                        "prec": _pc(v1, f"prec_{k}"),
                        "prec_change_vs_volume": v1["point"][f"prec_{k}"] - vol,
                        "ap_change_vs_volume": v1["point"][f"ap_{k}"] - vol_ap,
                        "prec_minus_b": _pc(v1, f"prec_{k}_minus_b")})
        out[label] = {
            "n_rows": v0["n_rows"], "n_pos": v0["n_pos"], "n_months": v0["n_months"],
            "event_lives": v0["test_events"], "months_with_events": v0["months_with_events"],
            "base": _pc(v0, "base"), "candidates": cands, "diffs_vs_b": diffs,
            "b_minus_a": _pc(v0, "prec_b_minus_a"),
            "bss_logit_full": _pc(v1, "bss_logit_full"),
            "folds": v1["folds"], "ablation": ablation, "shap": v1["shap"],
            "hazard": v1["hazard"], "hazard_gap": v1["hazard_gap"],
            "hazard_events": v1["hazard_events"],
        }
    return out


def check_cv_copy(cv: dict, copied: dict) -> list[dict]:
    """b2 hard-codes the CV numbers it compares against; check them against the JSON."""
    rows = []
    for label, items in copied.items():
        for key, d in items.items():
            m = re.fullmatch(r"(prec|ap|bss)_(.+)", key)
            metric, cand = m[1], m[2]
            if metric == "bss":
                ref = cv[label]["bss_logit_full"]
            elif cand.endswith("_minus_b"):
                ref = cv[label]["diffs_vs_b"][cand.removesuffix("_minus_b")][metric]
            else:
                ref = cv[label]["candidates"][cand][metric]
            a = [d["cv"]["estimate"], *d["cv"]["ci95"]]
            b = [ref["estimate"], *ref["ci95"]]
            diff = max(abs(x - y) for x, y in zip(a, b))
            rows.append({"variant": label, "metric": key, "b2": a, "json": b,
                         "max_abs_diff": diff, "ok": diff <= TOL})
    return rows


# --------------------------------------------------------------------------------------
# Universe and labels: counts from the panel files
# --------------------------------------------------------------------------------------

def excluded_lives(panel_md: str) -> dict:
    m = re.search(r"## Excluded lives \((\d+)\)\n\n(.+?)\n\n", panel_md, re.S)
    if not m:
        raise ValueError("excluded lives list not found")
    cats: dict[str, int] = {}
    for line in m[2].splitlines():
        reason = line.split(": ", 1)[1] if ": " in line else line
        if "index contract" in reason:
            c = "index contract"
        elif "stock" in reason:
            c = "stock (Q14 name review)"
        elif "ETF" in reason:
            c = "ETF (Q14 name review)"
        elif "commodity" in reason or "gold-backed" in reason:
            c = "commodity (Q14 name review)"
        elif "weekend screen" in reason:
            c = "weekend screen, non-crypto by name"
        elif "under 14 trading days" in reason:
            c = "non-crypto by name, under 14 trading days"
        elif "timing screen" in reason:
            c = "Q14 timing screen"
        else:
            c = "other"
        cats[c] = cats.get(c, 0) + 1
    kept = re.search(r"five crypto lives under the cut are kept: (.+?)\.", _flat(panel_md))
    dropped = re.search(r"Rows dropped before writing: (.+?);", _flat(panel_md))
    return {"n": int(m[1]), "by_reason": cats,
            "crypto_kept": kept[1] if kept else None,
            "rows_dropped": dropped[1] if dropped else None}


def panel_facts(panel: pl.DataFrame, lifecycle: pl.DataFrame, monthly: pl.DataFrame,
                panel_md: str, lockbox_start: str = "2026-01",
                last_cv_block: tuple[str, str] = ("2025-10", "2025-12")) -> dict:
    lives = panel.group_by("life_id").agg(pl.col("status").first(), pl.col("event").first(),
                                          pl.col("last_trade_day").first(),
                                          pl.col("last_trade_month").first())
    pos = panel.filter(pl.col("y3") == 1)
    year = pl.col("month").str.slice(0, 4)
    by_year = (panel.with_columns(year=year).group_by("year")
               .agg(rows=pl.len(), lives=pl.col("life_id").n_unique(), pos=pl.col("y3").sum(),
                    event_lives=pl.col("life_id").filter(pl.col("y3") == 1).n_unique())
               .sort("year"))
    lb = panel.filter(pl.col("month") >= lockbox_start)
    lb_pos = lb.filter(pl.col("y3") == 1)
    lb_lives = set(lb_pos["life_id"].to_list())
    lb_stop = lives.filter(pl.col("life_id").is_in(pl.Series(sorted(lb_lives), dtype=pl.String).implode()))
    cv_last = set(pos.filter(pl.col("month").is_between(pl.lit(last_cv_block[0]), pl.lit(last_cv_block[1])))["life_id"].to_list())
    ffm = pos.filter(pl.col("final_full_month"))
    pre = panel.filter(pl.col("month") < lockbox_start)
    pre_pos = pre.filter(pl.col("y3") == 1)
    return {
        "lifecycle": {"symbols": lifecycle["symbol"].n_unique(), "lives": lifecycle.height,
                      "by_status": dict(lifecycle.group_by("status").len()
                                        .sort("len", descending=True).iter_rows())},
        "monthly_panel": {"rows": monthly.height,
                          "ghost_months": int(monthly["ghost_month"].sum()),
                          "ghost_share": float(monthly["ghost_month"].mean())},
        "panel": {
            "rows": panel.height, "lives": panel["life_id"].n_unique(),
            "months": [panel["month"].min(), panel["month"].max()],
            "pos": pos.height, "base_rate": pos.height / panel.height,
            "lives_by_status": dict(lives.group_by("status").len()
                                    .sort("len", descending=True).iter_rows()),
            "event_lives": int(lives["event"].sum()),
            "event_lives_with_pos": pos["life_id"].n_unique(),
            "ghost_rows": int(panel["ghost_month"].sum()),
            "by_year": [{"year": r["year"], "rows": r["rows"], "lives": r["lives"],
                         "pos": r["pos"], "event_lives": r["event_lives"],
                         "base_rate": r["pos"] / r["rows"]} for r in by_year.to_dicts()],
        },
        "excluded": excluded_lives(panel_md),
        "leakage": {
            "final_full_month_pos": ffm.height,
            "final_full_month_settled_by_day10": ffm.filter(
                pl.col("last_trade_dom") <= 10).height,
            "pre_lockbox_pos": pre_pos.height,
            "pre_lockbox_final_full_month_pos": int(pre_pos["final_full_month"].sum()),
            "lockbox_pos": lb_pos.height,
            "lockbox_final_full_month_pos": int(lb_pos["final_full_month"].sum()),
        },
        "lockbox_batches": {
            "event_lives": len(lb_lives),
            "stop_days": lb_stop["last_trade_day"].n_unique(),
            "stop_months": lb_stop["last_trade_month"].n_unique(),
            "seen_in_last_cv_block": len(lb_lives & cv_last),
            "last_cv_block": list(last_cv_block),
            "pos_in_first_quarter": lb_pos.filter(
                pl.col("month") <= "2026-03").height,
        },
    }


# --------------------------------------------------------------------------------------
# Verdict inputs (pure functions of the numbers)
# --------------------------------------------------------------------------------------

def standing(d: dict) -> str:
    """'beats' if the paired interval is above 0, 'ahead' if only the point is, else 'not'."""
    lo = d["ci95"][0]
    if lo > 0:
        return "beats"
    return "ahead" if d["estimate"] > 0 else "not"


def summarise(result: dict) -> dict:
    lb, cv = result["lockbox"]["variants"], result["cv"]
    s = {}
    for label in VARIANTS:
        for model in ("logit_full", "gbm_full"):
            s[f"cv|{label}|{model}"] = standing(cv[label]["diffs_vs_b"][model]["prec"])
            s[f"lockbox|{label}|{model}"] = standing(lb[label]["diffs_vs_b"][model]["prec"])
        s[f"lockbox_ap|{label}|logit_full"] = standing(lb[label]["diffs_vs_b"]["logit_full"]["ap"])
    main = lb["main"]["diffs_vs_b"]["logit_full"]["prec"]["estimate"]
    fair = lb["drop final full month"]["diffs_vs_b"]["logit_full"]["prec"]["estimate"]
    s["lockbox_gain_share_from_final_month"] = (1 - fair / main) if main > 0 else None
    return s


def build_result(root: Path = Path(".")) -> dict:
    d = root / DATA
    b0 = json.loads((d / "b0_baselines.json").read_text())
    b1 = json.loads((d / "b1_models.json").read_text())
    b2 = parse_b2((d / "b2_lockbox.md").read_text())
    cv = cv_from_json(b0, b1)
    facts = panel_facts(pl.read_parquet(d / "delisting_panel.parquet"),
                        pl.read_csv(d / "contract_lifecycle.csv", infer_schema_length=0),
                        pl.read_parquet(d / "monthly_panel.parquet", columns=["ghost_month"]),
                        (d / "delisting_panel.md").read_text())
    result = {
        "question": ("Does a contract's own monthly trading (volume, open interest, price, "
                     "funding) rank it as likely to stop trading within 3 months, better than "
                     "the rule that flags the lowest-volume contracts?"),
        "sources": {"b0": str(DATA / "b0_baselines.json"), "b1": str(DATA / "b1_models.json"),
                    "b2": str(DATA / "b2_lockbox.md"),
                    "panel": str(DATA / "delisting_panel.parquet")},
        "config": {"horizon_months": 3, "alert_rate": b0["alert_rate"],
                   "first_test": b0["first_test"], "test_len": b0["test_len"],
                   "lockbox_start": b0["lockbox_start"], "n_boot": b0["n_boot"],
                   "boot_block": b0["boot_block"], "seed": b0["seed"],
                   "b1_names": b1["names"]},
        "facts": facts,
        "cv": cv,
        "lockbox": b2,
        "checks": {"cv_copied_in_b2": check_cv_copy(cv, b2["cv_copied_in_b2"]),
                   "lockbox_counts": {
                       "event_lives_b2": b2["variants"]["main"]["event_lives"],
                       "event_lives_panel": facts["lockbox_batches"]["event_lives"],
                       "pos_b2": b2["variants"]["main"]["n_pos"],
                       "pos_panel": facts["leakage"]["lockbox_pos"],
                       "rows_b2": b2["variants"]["main"]["n_rows"]}},
    }
    result["summary"] = summarise(result)
    return result


def main(argv: list[str] | None = None) -> None:
    from microstructure.analyses import q16_report
    ap = argparse.ArgumentParser(description="Q16: delisting prediction (assembly)")
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path, default=Path("results"))
    a = ap.parse_args(argv)
    result = build_result(a.root)
    result["verdict"] = q16_report.verdict_paragraph(result)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"{STEM}.json").write_text(dumps_strict(result) + "\n")
    q16_report.write_markdown(a.out / f"{STEM}.md", result)
    q16_report.plot(a.out / f"{STEM}.png", result)
    bad = [c for c in result["checks"]["cv_copied_in_b2"] if not c["ok"]]
    print(f"[q16] CV numbers copied in b2: {len(bad)} mismatches")
    print(result["verdict"])


if __name__ == "__main__":
    main()
