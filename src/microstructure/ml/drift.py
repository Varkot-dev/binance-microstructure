"""Measuring and attributing distribution shift between two periods.

A model fitted in a source period loses performance in a target period for two
different reasons, and this module separates them.

Covariate shift: the inputs moved (P(x) changed) while the map from inputs to
the label stayed put. Concept shift: the map itself, P(y | x), changed.

Tools, in the order an analysis uses them:

* `feature_shift`: per-feature effect sizes (standardized mean difference and
  the two-sample Kolmogorov-Smirnov distance). With millions of rows every
  test rejects, so only effect sizes are reported.
* `fit_domain_classifier` / `domain_auc`: a small boosted-tree model that tries
  to tell source rows from target rows. Its held-out AUC is one multivariate
  summary of how far the inputs moved (0.5 = indistinguishable).
* `density_ratio`: the classifier's probability pi(x) = P(target | x) turned
  into importance weights w(x) = (n_src / n_tgt) * pi / (1 - pi), an estimate
  of q(x) / p(x).
* `reweighting_attribution`: with those weights, the source model's loss on
  source rows reweighted to look like the target's inputs. The move from the
  plain to the reweighted source loss is the covariate part; what is left
  between the reweighted source loss and the actual target loss is the concept
  residual. The two sum to the total loss change exactly.
* `shift_decomposition`: the transfer-matrix identity that separates "the old
  model is stale" from "the period is harder for every model".
* `aligned_day_sums` / `resampled_means`: whole-day bootstrap on cached
  per-day sums, so intervals need no raw data.

Limits. The reweighting only speaks for the region of input space the source
period covers. When the two periods barely overlap the weights concentrate on
a few rows, the effective sample size collapses, and the split is flagged as
unreliable instead of being reported as if it were sound. "Concept" is also
always relative to the feature set: a change in an omitted variable shows up
in the residual.
"""
from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
from scipy.stats import ks_2samp
from sklearn.metrics import roc_auc_score

# Deliberately small: the classifier only has to rank rows by how target-like
# they are, and a small model gives smoother probabilities, hence tamer weights.
DOMAIN_PARAMS = {
    "objective": "binary",
    "learning_rate": 0.1,
    "num_leaves": 15,
    "min_data_in_leaf": 200,
    "feature_fraction": 0.8,
    "lambda_l2": 1.0,
    "max_bin": 63,
    "verbose": -1,
    "num_threads": 4,
    "seed": 0,
}
DOMAIN_ROUNDS = 100
PI_EPS = 1e-4
# Weights above this quantile are set to it. Trades a small bias (the far tail
# of the target is under-represented) for a large cut in variance.
WEIGHT_CLIP_QUANTILE = 0.99
# The variance of a weighted mean scales with 1 / ESS. Below a tenth of the
# rows the reweighted loss rests on less than one day's worth of a seven-day
# test block and its standard error is more than sqrt(10), about 3.2 times,
# that of the plain mean, so the split is flagged instead of trusted.
MIN_ESS_SHARE = 0.10


@dataclass(frozen=True)
class DomainClassifier:
    """P(row comes from the target period | x), as a picklable LightGBM string."""

    model_str: str
    n_src: int
    n_tgt: int

    def booster(self) -> lgb.Booster:
        return lgb.Booster(model_str=self.model_str)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.booster().predict(X)

    def gain_importance(self) -> np.ndarray:
        g = self.booster().feature_importance("gain")
        return g / g.sum() if g.sum() > 0 else g


def equal_size(a: np.ndarray, b: np.ndarray, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Random subsamples of the rows of `a` and `b` with the same row count."""
    m = min(a.shape[0], b.shape[0])
    rng = np.random.default_rng(seed)
    ia = np.sort(rng.choice(a.shape[0], size=m, replace=False))
    ib = np.sort(rng.choice(b.shape[0], size=m, replace=False))
    return a[ia], b[ib]


def fit_domain_classifier(
    X_src: np.ndarray, X_tgt: np.ndarray, rounds: int = DOMAIN_ROUNDS,
    params: dict | None = None,
) -> DomainClassifier:
    """Fit source (label 0) against target (label 1).

    The round count is fixed, not early-stopped: the model is only ever applied
    to rows it was not trained on, so a mild overfit costs nothing and no
    validation split is needed.
    """
    X = np.concatenate([X_src, X_tgt])
    d = np.concatenate([np.zeros(X_src.shape[0]), np.ones(X_tgt.shape[0])])
    booster = lgb.train({**DOMAIN_PARAMS, **(params or {})}, lgb.Dataset(X, label=d),
                        num_boost_round=rounds)
    return DomainClassifier(booster.model_to_string(), int(X_src.shape[0]), int(X_tgt.shape[0]))


def domain_auc(clf: DomainClassifier, X_src_holdout: np.ndarray,
               X_tgt_holdout: np.ndarray) -> float:
    """AUC of the classifier on rows from neither training sample."""
    p = clf.predict(np.concatenate([X_src_holdout, X_tgt_holdout]))
    d = np.concatenate([np.zeros(X_src_holdout.shape[0]), np.ones(X_tgt_holdout.shape[0])])
    return float(roc_auc_score(d, p))


def density_ratio(
    pi: np.ndarray, n_src: int, n_tgt: int, clip_quantile: float | None = WEIGHT_CLIP_QUANTILE,
) -> np.ndarray:
    """Importance weights q(x) / p(x) from P(target | x), normalized to mean 1.

    By Bayes' rule pi / (1 - pi) = (n_tgt / n_src) * q(x) / p(x) for a
    classifier trained on n_src source and n_tgt target rows, hence the
    (n_src / n_tgt) factor.
    """
    pi = np.clip(np.asarray(pi, dtype=np.float64), PI_EPS, 1.0 - PI_EPS)
    w = (n_src / n_tgt) * pi / (1.0 - pi)
    if clip_quantile is not None:
        w = np.minimum(w, np.quantile(w, clip_quantile))
    return w / w.mean()


def effective_sample_size(w: np.ndarray) -> float:
    """Kish's (sum w)^2 / sum w^2: n for equal weights, 1 for a single nonzero weight."""
    w = np.asarray(w, dtype=np.float64)
    return float(w.sum() ** 2 / (w**2).sum())


def reweighting_attribution(
    loss_src: np.ndarray, w_src: np.ndarray, loss_tgt: np.ndarray,
    min_ess_share: float = MIN_ESS_SHARE,
) -> dict:
    """Split E_tgt[loss] - E_src[loss] into a covariate part and a concept residual.

    `loss_src` and `loss_tgt` are per-row losses of the SAME fixed model on
    held-out source and target rows; `w_src` are the density-ratio weights of
    the source rows.

      covariate = E_src[w * loss] - E_src[loss]
      concept   = E_tgt[loss]     - E_src[w * loss]

    The weighted mean is self-normalized (divided by sum w).
    """
    src = float(np.mean(loss_src))
    tgt = float(np.mean(loss_tgt))
    weighted = float(np.sum(w_src * loss_src) / np.sum(w_src))
    ess = effective_sample_size(w_src)
    share = ess / loss_src.size
    return {
        "loss_src": src, "loss_src_reweighted": weighted, "loss_tgt": tgt,
        "total": tgt - src, "covariate": weighted - src, "concept": tgt - weighted,
        "ess": ess, "ess_share": share, "reliable": bool(share >= min_ess_share),
    }


def feature_shift(X_a: np.ndarray, X_b: np.ndarray, names: tuple[str, ...]) -> dict[str, dict]:
    """Per feature: standardized mean difference (b minus a, in pooled SDs) and KS distance."""
    out: dict[str, dict] = {}
    for k, name in enumerate(names):
        a = X_a[:, k].astype(np.float64)
        b = X_b[:, k].astype(np.float64)
        pooled = np.sqrt(0.5 * (a.var() + b.var()))
        smd = float((b.mean() - a.mean()) / pooled) if pooled > 0 else 0.0
        out[name] = {"smd": smd, "ks": float(ks_2samp(a, b, method="asymp").statistic)}
    return out


def shift_decomposition(m_ss, m_sj, m_jj, higher_is_better: bool = True) -> dict:
    """Staleness and predictability parts of the source model's raw drop.

    With M[i, j] the metric of the model trained in i on held-out rows of j:

      raw_drop              = M[s, s] - M[s, j]   what the old model lost
      staleness_gap         = M[j, j] - M[s, j]   what retraining recovers
      predictability_change = M[j, j] - M[s, s]   the period got easier (+) or harder (-)

    and raw_drop = staleness_gap - predictability_change. For a loss (lower is
    better) every difference is negated so the signs keep the same meaning.
    Inputs may be scalars or arrays (bootstrap replicates broadcast).
    """
    sgn = 1.0 if higher_is_better else -1.0
    m_ss, m_sj, m_jj = (np.asarray(v, dtype=np.float64) for v in (m_ss, m_sj, m_jj))
    return {
        "raw_drop": sgn * (m_ss - m_sj),
        "staleness_gap": sgn * (m_jj - m_sj),
        "predictability_change": sgn * (m_jj - m_ss),
    }


def aligned_day_sums(days: list[int], sums: list[float], counts: list[float],
                     union_days: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-day sums and counts placed on a common calendar (zero where a day is absent).

    Lets several symbols share one draw of resampled days, which keeps
    market-wide days (a crash, a quiet weekend) common across the panel.
    """
    pos = {int(d): i for i, d in enumerate(union_days.tolist())}
    s = np.zeros(union_days.size)
    c = np.zeros(union_days.size)
    for d, sv, cv in zip(days, sums, counts, strict=True):
        s[pos[int(d)]] = sv
        c[pos[int(d)]] = cv
    return s, c


def day_picks(n_days: int, n_boot: int, rng: np.random.Generator) -> np.ndarray:
    """[n_boot, n_days] indices of days drawn with replacement."""
    return rng.integers(0, n_days, size=(n_boot, n_days))


def resampled_means(sums: np.ndarray, counts: np.ndarray, picks: np.ndarray) -> np.ndarray:
    """Ratio-of-sums mean on each resample of whole days (NaN if a resample is empty)."""
    num = sums[picks].sum(axis=1)
    den = counts[picks].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / den, np.nan)


def percentile_ci(reps: np.ndarray) -> tuple[float, float]:
    """95% percentile interval, ignoring empty resamples."""
    lo, hi = np.nanpercentile(reps, [2.5, 97.5])
    return float(lo), float(hi)
