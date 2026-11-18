"""Tests for Q16: the delisting-prediction report (assembly and formatting only).

Contract under test:

1. The report (Markdown, figure, verdict) builds from a synthetic result dict.
2. The verdict wording flips between "beats the baseline", "is ahead but not
   decisively" and "does not beat the baseline" with the fair lock-box
   difference, and the main-run sentence follows its own difference.
3. b2's saved lock-box tables parse back into numbers.
4. No em or en dashes in the Markdown.
"""
from __future__ import annotations

import copy
import json

import pytest

from microstructure.analyses import q16_delisting as q16
from microstructure.analyses import q16_report as rep

VARIANTS = ("main", "drop final full month")
KEYS = ("base_a", "base_b", "logit_c", "logit_full", "gbm_full", "logit_vol", "gbm_vol")


def _c(est: float, lo: float, hi: float) -> dict:
    return {"estimate": est, "ci95": [lo, hi]}


def _cand(p: float) -> dict:
    return {"prec": _c(p, p * 0.5, p * 1.5), "rec": _c(2 * p, p, 3 * p),
            "ap": _c(0.8 * p, 0.4 * p, 1.2 * p), "hits": round(500 * p), "alerts": 500}


def _variant_cv(base: float) -> dict:
    precs = dict(zip(KEYS, (0.02, 0.08, 0.05, 0.10, 0.07, 0.06, 0.05)))
    groups = ("age", "price and drawdown", "volatility", "open interest", "funding",
              "other activity")
    return {
        "n_rows": 11000, "n_pos": 260, "n_months": 36, "event_lives": 96,
        "months_with_events": 32, "base": _c(base, base / 2, base * 1.4),
        "candidates": {k: _cand(p) for k, p in precs.items()},
        "diffs_vs_b": {k: {"prec": _c(0.01, -0.01, 0.03), "ap": _c(0.01, -0.02, 0.04)}
                       for k in ("logit_full", "gbm_full", "logit_vol", "gbm_vol", "logit_c")},
        "b_minus_a": _c(0.05, 0.01, 0.1), "bss_logit_full": _c(0.02, -0.01, 0.04),
        "folds": [{"test": "2023-01 to 2023-06", "n_trees": 20},
                  {"test": "2025-07 to 2025-12", "n_trees": 36}],
        "ablation": [{"key": f"{m}_vol+{g}", "model": m, "group": g,
                      "prec": _c(0.06, 0.03, 0.09),
                      "prec_change_vs_volume": 0.03 if g == "open interest" else 0.001,
                      "ap_change_vs_volume": 0.0, "prec_minus_b": _c(-0.01, -0.03, 0.01)}
                     for m in ("logit", "gbm") for g in groups],
        "shap": {"test": "2025-07 to 2025-12",
                 "features": [{"feature": "oi_rank_pct", "mean_abs": 0.2, "share": "25%",
                               "corr": -0.9},
                              {"feature": "zero_volume_days", "mean_abs": 0.0, "share": "0%",
                               "corr": None}],
                 "groups": [{"group": "open interest", "mean_abs": 0.3, "share": "40%"},
                            {"group": "volume level", "mean_abs": 0.1, "share": "13%"}]},
        "hazard": [{"feature": "qv_rank_pct", "or": 0.3, "lo": 0.2, "hi": 0.4, "sd": 0.29},
                   {"feature": "dlog_qv_3m", "or": 0.95, "lo": 0.7, "hi": 1.2, "sd": 1.0}],
        "hazard_gap": 1, "hazard_events": 100,
    }


def _variant_lb(main_diff: tuple, base: float) -> dict:
    precs = {"base_a": 0.05, "base_b": 0.15, "logit_full": 0.15 + main_diff[0],
             "gbm_full": 0.18}
    month = {"month": "2026-01", "rows": 540, "alerts": 27, "pos": 30, "lives": 30,
             "base_a": 3, "base_b": 9, "logit_full": 12, "gbm_full": 8}
    return {
        "n_rows": 3730, "n_lives": 574, "n_months": 7, "months": ["2026-01", "2026-07"],
        "n_pos": 145, "event_lives": 61, "base": _c(base, base * 0.6, base * 1.4),
        "candidates": {k: _cand(p) for k, p in precs.items()},
        "diffs_vs_b": {"logit_full": {"prec": _c(*main_diff), "rec": _c(0.1, 0.0, 0.2),
                                      "ap": _c(0.04, 0.002, 0.09)},
                       "gbm_full": {"prec": _c(0.0, -0.005, 0.02), "rec": _c(0, 0, 0),
                                    "ap": _c(0.0, -0.02, 0.04)},
                       "base_a": {"prec": _c(-0.09, -0.14, -0.04), "rec": _c(0, 0, 0),
                                  "ap": _c(-0.05, -0.09, -0.02)}},
        "leave_one_month_out_prec_diff": {"logit_full": [0.02, 0.08]},
        "brier": {"logit_full": 0.034, "gbm_full": 0.036, "ref": 0.037,
                  "bss_logit_full": _c(0.08, 0.04, 0.1), "bss_gbm_full": _c(0.03, 0.02, 0.04),
                  "mean_pred_logit": 0.03, "mean_pred_gbm": 0.022, "observed": base},
        "by_month": [month],
    }


def synthetic_result(main=(0.119, 0.097, 0.145), fair=(0.049, -0.016, 0.081)) -> dict:
    by_year = [{"year": y, "rows": 1000, "lives": 100, "pos": 25, "event_lives": 10,
                "base_rate": 0.025} for y in ("2022", "2023", "2026")]
    r = {
        "question": "Synthetic question?",
        "config": {"horizon_months": 3, "alert_rate": 0.05, "first_test": "2023-01",
                   "test_len": 6, "lockbox_start": "2026-01", "n_boot": 2000,
                   "boot_block": 3, "seed": 0},
        "facts": {
            "lifecycle": {"symbols": 924, "lives": 935, "by_status": {"alive": 758}},
            "monthly_panel": {"rows": 23356, "ghost_months": 2126, "ghost_share": 0.091},
            "panel": {"rows": 18329, "lives": 686, "months": ["2020-01", "2026-07"],
                      "pos": 465, "base_rate": 0.025, "lives_by_status": {"alive": 513},
                      "event_lives": 161, "event_lives_with_pos": 161, "ghost_rows": 0,
                      "by_year": by_year},
            "excluded": {"n": 238, "by_reason": {"stocks": 25}, "crypto_kept": "CFGUSDT",
                         "rows_dropped": "final_trading_month 174"},
            "leakage": {"final_full_month_pos": 153, "final_full_month_settled_by_day10": 39,
                        "pre_lockbox_pos": 320, "pre_lockbox_final_full_month_pos": 100,
                        "lockbox_pos": 145, "lockbox_final_full_month_pos": 53},
            "lockbox_batches": {"event_lives": 61, "stop_days": 23, "stop_months": 9,
                                "seen_in_last_cv_block": 16,
                                "last_cv_block": ["2025-10", "2025-12"],
                                "pos_in_first_quarter": 93},
        },
        "cv": {"main": _variant_cv(0.0238), "drop final full month": _variant_cv(0.0166)},
        "lockbox": {
            "runs": "first run on 2026-11-18", "commit": "b3571a691e6c", "n_runs": 1,
            "frozen": {v: {"train_rows": 13002, "train_pos": 244, "last_train_month": "2025-09",
                           "inner_validation": "2024-10 to 2025-09", "inner_val_pos": 119,
                           "C_logit": 0.03, "trees_gbm": 20, "train_base_rate": 0.0188}
                       for v in VARIANTS},
            "variants": {"main": _variant_lb(main, 0.0389),
                         "drop final full month": _variant_lb(fair, 0.025)},
        },
        "checks": {"cv_copied_in_b2": [{"variant": "main", "metric": "prec_base_b",
                                        "ok": True}],
                   "lockbox_counts": {"event_lives_b2": 61, "event_lives_panel": 61,
                                      "pos_b2": 145, "pos_panel": 145, "rows_b2": 3730}},
    }
    return r


def _head(text: str) -> str:
    return text.split("**")[1]


def test_report_builds_from_a_synthetic_dict(tmp_path):
    r = synthetic_result()
    r["verdict"] = rep.verdict_paragraph(r)
    md, png = tmp_path / "q16.md", tmp_path / "q16.png"
    rep.write_markdown(md, r)
    rep.plot(png, r)
    text = md.read_text()
    for section in ("## Question", "## Universe and labels", "## Method", "## Results",
                    "### Base rate by year", "### Baselines in cross-validation",
                    "### Models in cross-validation", "### Lock-box (2026)",
                    "### Which features matter", "### Announcement leakage",
                    "## Verdict", "## Caveats"):
        assert section in text, section
    for caveat in ("No announcement dates", "Batched delistings", "16 of the 61",
                   "not probabilities"):
        assert caveat in text, caveat
    assert "\u2014" not in text and "\u2013" not in text
    assert "\u2014" not in r["verdict"] and "\u2013" not in r["verdict"]
    assert png.stat().st_size > 10_000
    # The result dict is JSON-serialisable as the module writes it.
    json.loads(q16.dumps_strict(r))


@pytest.mark.parametrize(("fair", "word"), [
    ((0.06, 0.01, 0.10), "beats the baseline"),
    ((0.049, -0.016, 0.081), "is ahead but not decisively"),
    ((-0.01, -0.05, 0.02), "does not beat the baseline"),
    ((0.0, -0.005, 0.022), "does not beat the baseline"),
])
def test_verdict_wording_flips_with_the_fair_difference(fair, word):
    v = rep.verdict_paragraph(synthetic_result(fair=fair))
    assert word in _head(v)
    others = set(rep.STANDING_PHRASE.values()) - {word}
    assert not any(o in _head(v) for o in others)


def test_main_run_sentence_follows_its_own_difference():
    for main, word in (((0.119, 0.097, 0.145), "beats the baseline"),
                       ((0.02, -0.01, 0.05), "is ahead but not decisively"),
                       ((-0.02, -0.05, 0.01), "does not beat the baseline")):
        v = rep.verdict_paragraph(synthetic_result(main=main))
        assert f"kept, the logistic model {word}" in v


def test_share_of_gain_from_the_final_month():
    r = synthetic_result(main=(0.10, 0.05, 0.15), fair=(0.04, -0.01, 0.08))
    assert rep.gain_share(r) == pytest.approx(0.6)
    assert "more than half" in rep.verdict_paragraph(r)
    r = synthetic_result(main=(0.10, 0.05, 0.15), fair=(0.08, 0.01, 0.12))
    assert "less than half" in rep.verdict_paragraph(r)
    r = synthetic_result(main=(-0.01, -0.05, 0.02), fair=(0.02, -0.01, 0.05))
    assert rep.gain_share(r) is None


def test_extra_feature_words_follow_the_fair_test():
    r = synthetic_result(fair=(-0.01, -0.05, 0.02))
    assert "add nothing measurable" in rep.verdict_paragraph(r)
    r = synthetic_result(fair=(0.06, 0.01, 0.10))
    assert "holds without the announcement month" in rep.verdict_paragraph(r)


def test_standing_is_the_same_in_both_modules():
    for d in (_c(0.05, 0.01, 0.1), _c(0.05, -0.01, 0.1), _c(0.0, -0.01, 0.01),
              _c(-0.05, -0.1, -0.01)):
        assert rep.standing(d) == q16.standing(d)


B2_SNIPPET = """# B2

Lock-box runs: first run on 2026-11-18.

Code and data come from commit `b3571a691e6cfb52cea23c8d875c163e0b7e39a8` (HEAD).

| run | train rows | train positives | last train month | inner validation | inner val positives | C (logistic) | trees (LightGBM) | training base rate |
|---|---|---|---|---|---|---|---|---|
| main | 13,002 | 244 | 2025-09 | 2024-10 to 2025-09 | 119 | 0.03 | 20 | 0.0188 |
| drop final full month | 12,930 | 172 | 2025-09 | 2024-10 to 2025-09 | 87 | 0.01 | 36 | 0.0133 |

## 3. Results

### {v}

Lock-box rows 3,730 (574 lives) over 7 origin months
(2026-01 to 2026-07); 145 positive rows from
61 event lives; base rate 0.0389 (0.0241 to 0.0533).

| candidate | precision at top 5% | recall | hits/alerts | PR-AUC |
|---|---|---|---|---|
| (a) falling volume | 0.054 (0.016 to 0.090) | 0.069 (0.033 to 0.087) | 10/185 | 0.052 (0.020 to 0.082) |
| (b) lowest volume rank | 0.151 (0.066 to 0.243) | 0.193 (0.135 to 0.217) | 28/185 | 0.119 (0.046 to 0.196) |
| logistic, full features | 0.270 (0.187 to 0.356) | 0.345 (0.318 to 0.392) | 50/185 | 0.202 (0.119 to 0.312) |
| LightGBM, full features | 0.216 (0.148 to 0.309) | 0.276 (0.251 to 0.327) | 40/185 | 0.171 (0.123 to 0.245) |

Paired differences against (b), same bootstrap months:

| difference | precision | recall | PR-AUC |
|---|---|---|---|
| logistic, full features - (b) | 0.119 (0.097 to 0.145) | 0.152 (0.103 to 0.247) | 0.083 (0.061 to 0.151) |
| LightGBM, full features - (b) | 0.065 (0.038 to 0.124) | 0.083 (0.045 to 0.183) | 0.052 (0.033 to 0.119) |
| (a) falling volume - (b) | -0.097 (-0.148 to -0.044) | -0.124 (-0.149 to -0.083) | -0.067 (-0.113 to -0.025) |

Robustness (not a frozen metric): range of the precision difference against (b) when one
lock-box month is left out: logistic, full features +0.101 to +0.139; LightGBM, full features +0.044 to +0.095; (a) falling volume -0.119 to -0.076.

Brier score: logistic 0.03467, LightGBM 0.03658,
predicting the training base rate 0.03777. Brier skill: logistic
0.082 (0.041 to 0.102), LightGBM 0.031 (0.027 to 0.035). Mean predicted
probability: logistic 0.0300, LightGBM
0.0227, against an observed 0.0389.

By month (hits among the alerts):

| origin month | live rows | alerts | positive rows | event lives | (a) | (b) | logistic | LightGBM |
|---|---|---|---|---|---|---|---|---|
| 2026-01 | 543 | 27 | 34 | 34 | 3 | 9 | 13 | 6 |
"""


def test_b2_tables_parse_back():
    sec = B2_SNIPPET.split("## 3. Results")[1]
    body = sec.replace("{v}", "main") + sec.replace("{v}", "drop final full month")
    text = (B2_SNIPPET.split("## 3. Results")[0] + "## 3. Results" + body
            + "\n## 4. Comparison\n\n| metric | CV (b0/b1) | lock-box | lock-box vs CV |\n"
              "|---|---|---|---|\n| main: base rate | 0.0238 | 0.0389 | |\n"
              "| main: prec_base_b | 0.083 (0.031 to 0.133) | 0.151 (0.066 to 0.243) |  |\n"
              "\n## 5. Conclusion\n")
    b2 = q16.parse_b2(text)
    assert b2["commit"].startswith("b3571a6") and b2["n_runs"] == 1
    assert b2["frozen"]["drop final full month"]["trees_gbm"] == 36
    m = b2["variants"]["main"]
    assert m["n_rows"] == 3730 and m["event_lives"] == 61 and m["n_pos"] == 145
    assert m["candidates"]["logit_full"]["prec"] == _c(0.270, 0.187, 0.356)
    assert m["candidates"]["base_b"]["hits"] == 28
    assert m["diffs_vs_b"]["base_a"]["prec"]["ci95"] == [-0.148, -0.044]
    assert m["leave_one_month_out_prec_diff"]["gbm_full"] == [0.044, 0.095]
    assert m["brier"]["bss_logit_full"] == _c(0.082, 0.041, 0.102)
    assert m["by_month"][0]["logit_full"] == 13
    assert b2["cv_copied_in_b2"]["main"]["prec_base_b"]["cv"] == _c(0.083, 0.031, 0.133)


def test_cv_copy_check_flags_a_mismatch():
    r = synthetic_result()
    cv = copy.deepcopy(r["cv"])
    copied = {"main": {"prec_base_b": {"cv": cv["main"]["candidates"]["base_b"]["prec"]},
                       "prec_logit_full_minus_b": {"cv": _c(0.5, 0.4, 0.6)}}}
    rows = {x["metric"]: x["ok"] for x in q16.check_cv_copy(cv, copied)}
    assert rows == {"prec_base_b": True, "prec_logit_full_minus_b": False}
