"""Interval-censored scoring of arrival-time models, and a small neural point process.

Question served (Q12): on identical held-out events, how many nats per event
does a flexible neural model gain over a homogeneous Poisson process and over
the repo's sum-of-exponentials Hawkes fits? Everything here scores ONE object,
the recorded integer-millisecond gap to the next event, so the numbers are
comparable across model families.

Why not a continuous density. Timestamps are integer milliseconds and gaps of
0 and 1 ms are common. A continuous density evaluated on lattice values can
be driven arbitrarily high (a narrow mixture component on the lattice point,
or a Hawkes kernel with beta -> infinity, whose intensity right after an
event is alpha*beta), and a log-normal density at a gap of exactly 0 is 0.
Both are artifacts of the recording resolution.

Convention used for every model. An event recorded `d` ms after its
predecessor is scored as the probability that the model's continuous gap
falls in the cell [d, d+1) ms:

    score = log( F(d+1 ms) - F(d ms) )            (F = conditional gap CDF)

The cells tile [0, infinity), so each model defines a normalized probability
mass function over the recorded integer gap, and the log score of a
normalized pmf is a proper scoring rule: it is at most 0, finite at d = 0,
and cannot be improved by spiking. The symmetric alternative
[max(d-1, 0), d+1) covers the true gap under floor stamping of both events,
but those cells overlap and their masses sum to about 2, so it is not a pmf
and I do not use it. The cell is a device to turn a continuous model into a
pmf for the recorded value; it does not assume the true gap lies in it.

Business time. Models live in business time (seconds of
`rescale_to_business_time`). The 1 ms clock cell maps to a business-time
cell whose width is the local intraday rate times 1 ms; `censor_intervals`
computes both edges by pushing the integer clock times `ts` and `ts + 1`
through the same time change, so cells that straddle a profile bin are exact.

Tie truncation. `to_aggressor_events` merges same-millisecond same-side
prints, so one millisecond holds at most two events (a sell, then a buy).
After such a pair the next event cannot share the millisecond: its gap is at
least 1 ms by construction of the data, not by market behaviour. A flexible
model would learn that and a Hawkes model cannot, which would count a data
artifact as neural skill. So every model is conditioned on the same known
support: after a tied event the score is log((F(hi) - F(lo)) / S(1 ms)).

History and state. The Hawkes state and the model inputs use the recorded
times as if exact. Hawkes: after event j the state of component k is
A_k = sum_{i <= j} exp(-beta_k (t_j - t_i)), and the compensator over a gap x
is Lambda(x) = mu x + sum_k alpha_k A_k (1 - exp(-beta_k x)), so the gap
survival exp(-Lambda(x)) and the cell probability are closed form.

Neural model: a GRU over the event history with a log-normal mixture for the
next gap (the intensity-free model of Shchur, Bilos and Gunnemann 2020),
which has a closed-form CDF and so a closed-form cell probability. Inputs per
event are the log gap and exponentially weighted event rates at a few
log-spaced horizons. Those rates are exactly Hawkes states, so the network
sees slow timescales its truncated recurrent memory cannot hold.

The Poisson and Hawkes scoring is numpy only; the neural part needs PyTorch
and raises a clear error without it.
"""
from __future__ import annotations

import copy
import time
from dataclasses import asdict, dataclass

import numpy as np

from microstructure.estimators.hawkes import _excitation_recursion
from microstructure.signals.eventtime import rescale_to_business_time

try:  # PyTorch is optional: the Poisson/Hawkes scoring must work without it.
    import torch
    from torch import nn
except ImportError:  # pragma: no cover - exercised only where torch is absent
    torch = None
    nn = None

# Standardized log-gap edges are clamped to this magnitude so that a lower
# edge of 0 (log = -inf) contributes CDF 0 with a zero, not NaN, gradient.
_Y_CLAMP = 1.0e3
_SIGMA_MIN, _SIGMA_MAX = 1.0e-3, 20.0
_TINY = 1.0e-300


# ---------------------------------------------------------------------------
# Censoring cells in business time.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Censored:
    """Business-time coordinates and censoring cells of one contiguous block.

    `tau[i]` is the business time of event i in seconds from the block's
    first event. Event i >= 1 is scored on the cell [lo[i], hi[i]) of the gap
    after event i-1, conditional on the gap exceeding `floor[i]` (0 unless
    event i-1 was itself tied with its predecessor). Index 0 has no
    predecessor and carries the uninformative cell [0, inf).
    """

    tau: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    floor: np.ndarray
    gap_ms: np.ndarray  # recorded clock gap; -1 at index 0

    @property
    def n(self) -> int:
        return int(self.tau.size)

    def slice(self, start: int, stop: int) -> Censored:
        """Events start..stop-1 as their own block: state and clock restart at `start`."""
        lo, hi, floor = (v[start:stop].copy() for v in (self.lo, self.hi, self.floor))
        gap = self.gap_ms[start:stop].copy()
        lo[0], hi[0], floor[0], gap[0] = 0.0, np.inf, 0.0, -1
        tau = self.tau[start:stop] - self.tau[start]
        return Censored(tau=tau, lo=lo, hi=hi, floor=floor, gap_ms=gap)


def censor_intervals(
    ts_ms: np.ndarray, profile: np.ndarray, tie_truncation: bool = True
) -> Censored:
    """Map integer-ms event times to business-time censoring cells.

    `profile` is the intraday rate profile (training days only, in the
    analysis). With `tie_truncation` the data must obey the aggressor-event
    contract of at most two events per millisecond; a third raises, because
    the truncated support would give it probability 0.
    """
    ts_ms = np.asarray(ts_ms, dtype=np.int64)
    if ts_ms.size < 2:
        raise ValueError("need at least 2 events")
    gap_ms = np.diff(ts_ms)
    if np.any(gap_ms < 0):
        raise ValueError("ts_ms must be sorted in non-decreasing order")
    tau = rescale_to_business_time(ts_ms, profile)
    # tau(ts + 1 ms) on the same anchor: prepend ts[0] so the anchor is unchanged.
    tau_next = rescale_to_business_time(np.concatenate((ts_ms[:1], ts_ms + 1)), profile)[1:]

    n = ts_ms.size
    lo = np.zeros(n)
    hi = np.full(n, np.inf)
    lo[1:] = tau[1:] - tau[:-1]
    hi[1:] = tau_next[1:] - tau[:-1]
    floor = np.zeros(n)
    if tie_truncation:
        tied = np.zeros(n, dtype=bool)
        tied[1:] = gap_ms == 0
        if np.any(tied[1:] & tied[:-1]):
            raise ValueError(
                "three events share a millisecond; tie_truncation assumes aggressor-level "
                "events (at most a sell and a buy per millisecond)"
            )
        # Event i-1 tied => the first clock millisecond after it is excluded.
        width = tau_next - tau
        floor[1:] = np.where(tied[:-1], width[:-1], 0.0)
    gaps = np.concatenate(([-1], gap_ms)).astype(np.int64)
    return Censored(tau=tau, lo=lo, hi=hi, floor=floor, gap_ms=gaps)


# ---------------------------------------------------------------------------
# Scores, residuals.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scored:
    """Per-event censored log-likelihood of one model on one block.

    `loglik[i]` = log P(cell_i | history, gap > floor_i). `log_surv_lo[i]` =
    log P(gap >= lo_i | history, gap > floor_i), kept so that the
    time-rescaling residuals can be formed without re-running the model.
    Entries before the first scored event are 0.
    """

    loglik: np.ndarray
    log_surv_lo: np.ndarray


def poisson_censored(rate: float, cen: Censored) -> Scored:
    """Homogeneous Poisson in business time: S(x) = exp(-rate x)."""
    if rate <= 0.0:
        raise ValueError("rate must be positive")
    return hawkes_censored(rate, np.zeros(0), np.zeros(0), cen)


def hawkes_states(tau: np.ndarray, betas: np.ndarray) -> np.ndarray:
    """A[k, j] = sum_{i <= j} exp(-beta_k (tau_j - tau_i)), reset at the block start."""
    dt = np.diff(tau)
    out = np.empty((len(betas), tau.size))
    for k, beta in enumerate(betas):
        out[k] = _excitation_recursion(np.exp(-beta * dt)) + 1.0
    return out


def _hawkes_compensators(
    mu: float, alphas: np.ndarray, betas: np.ndarray, cen: Censored
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Lambda(lo), Lambda(hi) - Lambda(lo) and Lambda(floor) for events 1..n-1."""
    lo, hi, floor = cen.lo[1:], cen.hi[1:], cen.floor[1:]
    lam_lo = mu * lo
    d_lam = mu * (hi - lo)
    lam_floor = mu * floor
    dt = np.diff(cen.tau)
    for alpha, beta in zip(alphas, betas, strict=True):
        # State just after the previous event, one component at a time to
        # keep memory at O(n) for multi-million-event blocks.
        weight = alpha * (_excitation_recursion(np.exp(-beta * dt))[:-1] + 1.0)
        lam_lo += -weight * np.expm1(-beta * lo)
        # The difference is formed analytically: 1 ms cells make
        # Lambda(hi) - Lambda(lo) tiny next to either term.
        d_lam += weight * np.exp(-beta * lo) * -np.expm1(-beta * (hi - lo))
        lam_floor += -weight * np.expm1(-beta * floor)
    return lam_lo, d_lam, lam_floor


def hawkes_censored(mu: float, alphas: np.ndarray, betas: np.ndarray, cen: Censored) -> Scored:
    """Censored per-event score of a sum-of-exponentials Hawkes with given parameters.

    The parameterization is the one of `microstructure.estimators.hawkes`:
    intensity mu + sum_k alpha_k beta_k sum_{t_i < t} exp(-beta_k (t - t_i)).
    The state starts empty at the block's first event.
    """
    alphas = np.asarray(alphas, dtype=np.float64)
    betas = np.asarray(betas, dtype=np.float64)
    if mu <= 0.0 or np.any(alphas < 0.0) or np.any(betas <= 0.0):
        raise ValueError("need mu > 0, alphas >= 0, betas > 0")
    lam_lo, d_lam, lam_floor = _hawkes_compensators(mu, alphas, betas, cen)
    loglik = np.zeros(cen.n)
    log_surv = np.zeros(cen.n)
    with np.errstate(divide="ignore"):
        loglik[1:] = -(lam_lo - lam_floor) + np.log(-np.expm1(-d_lam))
    log_surv[1:] = -(lam_lo - lam_floor)
    return Scored(loglik=loglik, log_surv_lo=log_surv)


def hawkes_density_loglik(
    mu: float, alphas: np.ndarray, betas: np.ndarray, tau: np.ndarray
) -> np.ndarray:
    """Naive continuous per-event log density, log lambda(t_i) - Lambda(gap_i).

    Not used for scoring. It exists to show what the censored score protects
    against (it grows without bound in beta on tied data) and to tie the
    state recursion here to the repo's exact log-likelihood.
    """
    alphas = np.asarray(alphas, dtype=np.float64)
    betas = np.asarray(betas, dtype=np.float64)
    gap = np.diff(tau)
    intensity = np.full(gap.size, mu)
    comp = mu * gap
    for alpha, beta in zip(alphas, betas, strict=True):
        state = _excitation_recursion(np.exp(-beta * gap))
        intensity += alpha * beta * state[1:]
        comp += -alpha * (state[:-1] + 1.0) * np.expm1(-beta * gap)
    out = np.zeros(tau.size)
    out[1:] = np.log(intensity) - comp
    return out


def rescaling_residuals(scored: Scored, first: int, seed: int = 0) -> np.ndarray:
    """Time-rescaling residuals for discretely recorded gaps.

    For a correct model the compensator increment over a gap is Exp(1). The
    gap is only known up to its cell, so I use the randomized
    probability integral transform: draw the survival probability uniformly
    between S(hi) and S(lo) and return z = -log of it. Under a correct model
    this z is exactly Exp(1) and independent across events, with no atom at
    zero from tied timestamps.
    """
    ll = scored.loglik[first:]
    ls = scored.log_surv_lo[first:]
    u = np.random.default_rng(seed).random(ll.size)
    # S(lo) - u*cell = S(lo) * (1 - u * cell / S(lo)); cell / S(lo) <= 1.
    ratio = np.exp(np.minimum(ll - ls, 0.0))
    return -ls - np.log1p(-u * ratio)


def residual_diagnostics(z: np.ndarray) -> dict:
    """Distance of residuals from i.i.d. Exp(1): KS distance and lag-1 autocorrelations.

    Distances, not p-values: at 10^5 to 10^6 events every model is rejected.
    The autocorrelation is reported for z and for the uniform transform
    1 - exp(-z), which is not dominated by the exponential tail.
    """
    z = z[np.isfinite(z)]
    n = z.size
    u = np.sort(-np.expm1(-z))
    grid = np.arange(1, n + 1) / n
    ks = float(max(np.max(grid - u), np.max(u - (grid - 1.0 / n))))

    def lag1(v: np.ndarray) -> float:
        v = v - v.mean()
        den = float(np.dot(v, v))
        return float(np.dot(v[1:], v[:-1]) / den) if den > 0 else 0.0

    return {
        "n": int(n),
        "ks_distance": ks,
        "ks_5pct_critical_iid": float(1.36 / np.sqrt(n)),
        "lag1_autocorr_z": lag1(z),
        "lag1_autocorr_u": lag1(-np.expm1(-z)),
        "mean_z": float(z.mean()),
    }


# ---------------------------------------------------------------------------
# Neural model inputs (numpy, causal by construction).
# ---------------------------------------------------------------------------


def tpp_features(cen: Censored, horizons_s: tuple[float, ...]) -> np.ndarray:
    """Per-event inputs: row j is what is known just after event j.

    Column 0 is the log of the midpoint of event j's own gap cell (finite for
    a recorded gap of 0). Columns 1.. are log exponentially weighted event
    rates, beta * A_beta with beta = 1/horizon, divided by 1 - exp(-beta T)
    for the time T since the block start so a cold start is not read as a
    quiet market. Row j never looks at an event after j.
    """
    n = cen.n
    out = np.empty((n, 1 + len(horizons_s)))
    out[0, 0] = np.nan  # no gap before the first event; the scaler imputes the mean
    out[1:, 0] = np.log(0.5 * (cen.lo[1:] + cen.hi[1:]))
    betas = np.array([1.0 / h for h in horizons_s])
    states = hawkes_states(cen.tau, betas)
    elapsed = cen.tau - cen.tau[0]
    for k, beta in enumerate(betas):
        seen = -np.expm1(-beta * np.maximum(elapsed, 1e-3 / beta))
        out[:, 1 + k] = np.log(beta * states[k] / seen)
    return out


@dataclass(frozen=True)
class TPPScaler:
    """Training-block mean and standard deviation of each input column."""

    mean: np.ndarray
    std: np.ndarray

    def as_dict(self) -> dict:
        return {"mean": self.mean.tolist(), "std": self.std.tolist()}


def fit_scaler(features: np.ndarray, first: int) -> TPPScaler:
    rows = features[first:]
    std = rows.std(axis=0)
    return TPPScaler(mean=rows.mean(axis=0), std=np.where(std > 1e-8, std, 1.0))


# ---------------------------------------------------------------------------
# Log-normal mixture and the recurrent model (PyTorch).
# ---------------------------------------------------------------------------


def _require_torch() -> None:
    if torch is None:
        raise ImportError(
            "the neural point process needs PyTorch (CPU build is enough); "
            "install torch or run only the Poisson/Hawkes scoring"
        )


@dataclass(frozen=True)
class TPPConfig:
    hidden: int = 48
    n_components: int = 8
    horizons_s: tuple[float, ...] = (1.0, 10.0, 100.0, 1000.0)
    window: int = 256          # events per truncated-backpropagation window
    window_burn: int = 64      # leading events of a window that are fed, not scored
    batch_size: int = 64
    max_windows_per_epoch: int = 4096
    epochs: int = 10
    patience: int = 2
    lr: float = 2e-3
    grad_clip: float = 1.0
    eval_batch: int = 512
    seed: int = 0

    def as_dict(self) -> dict:
        return {**asdict(self), "horizons_s": list(self.horizons_s)}


class LogNormalMixture:
    """Mixture of log-normals on the gap x > 0, parameterized in standardized log space.

    y = (log x - shift) / scale, and y | component m ~ Normal(mu_m, sigma_m).
    Density, CDF and sampling are closed form; the density integrates to 1 on
    (0, inf) by construction (Shchur, Bilos and Gunnemann 2020).
    Tensors have shape [..., M]; evaluation points broadcast against [...].
    """

    def __init__(self, logw, mu, sigma, shift: float = 0.0, scale: float = 1.0) -> None:
        self.logw, self.mu, self.sigma = logw.double(), mu.double(), sigma.double()
        self.shift, self.scale = float(shift), float(scale)

    def standardize(self, x):
        """Gap in business seconds -> clamped standardized log gap (x = 0 maps to the clamp)."""
        y = (torch.log(torch.as_tensor(x, dtype=torch.float64)) - self.shift) / self.scale
        return y.clamp(-_Y_CLAMP, _Y_CLAMP)

    def _z(self, y):
        return (y.unsqueeze(-1) - self.mu) / self.sigma

    def survival_y(self, y):
        return (self.logw.exp() * torch.special.ndtr(-self._z(y))).sum(-1)

    def cdf(self, x):
        return (self.logw.exp() * torch.special.ndtr(self._z(self.standardize(x)))).sum(-1)

    def log_prob(self, x):
        """Continuous log density in x. Diagnostic only; never used as a score."""
        x = torch.as_tensor(x, dtype=torch.float64)
        y = (torch.log(x) - self.shift) / self.scale
        z = self._z(y)
        comp = self.logw - 0.5 * z**2 - torch.log(self.sigma) - 0.5 * np.log(2.0 * np.pi)
        return torch.logsumexp(comp, -1) - np.log(self.scale) - torch.log(x)

    def cell_prob_y(self, ylo, yhi):
        """P(ylo <= y < yhi), each component's difference taken in its accurate tail."""
        zlo, zhi = self._z(ylo), self._z(yhi)
        flip = zlo > 0
        a = torch.where(flip, -zhi, zlo)
        b = torch.where(flip, -zlo, zhi)
        diff = torch.special.ndtr(b) - torch.special.ndtr(a)
        return (self.logw.exp() * diff).sum(-1)

    def log_cell_y(self, ylo, yhi, yfloor):
        """(log P(cell | y > yfloor), log P(y >= ylo | y > yfloor))."""
        log_s_floor = torch.log(self.survival_y(yfloor).clamp_min(_TINY))
        ll = torch.log(self.cell_prob_y(ylo, yhi).clamp_min(_TINY)) - log_s_floor
        ls = torch.log(self.survival_y(ylo).clamp_min(_TINY)) - log_s_floor
        return ll, ls

    def sample(self, n: int, generator=None):
        """n draws per leading index; shape [n, ...]."""
        probs = self.logw.exp()
        flat = probs.reshape(-1, probs.shape[-1])
        idx = torch.multinomial(flat, n, replacement=True, generator=generator)
        idx = idx.T.reshape(n, *probs.shape[:-1], 1)
        mu = torch.gather(self.mu.expand(n, *self.mu.shape), -1, idx).squeeze(-1)
        sigma = torch.gather(self.sigma.expand(n, *self.sigma.shape), -1, idx).squeeze(-1)
        eps = torch.randn(mu.shape, dtype=torch.float64, generator=generator)
        return torch.exp(self.shift + self.scale * (mu + sigma * eps))


if nn is not None:

    class LogNormMixTPP(nn.Module):
        """GRU history encoder with a log-normal mixture head for the next gap.

        The head also reads the current inputs directly, so the slow rate
        features reach it without passing through the recurrent state.
        """

        def __init__(self, n_features: int, hidden: int, n_components: int) -> None:
            super().__init__()
            self.gru = nn.GRU(n_features, hidden, batch_first=True)
            self.head = nn.Sequential(
                nn.Linear(hidden + n_features, hidden), nn.Tanh(),
                nn.Linear(hidden, 3 * n_components),
            )
            with torch.no_grad():
                # Start as a broad mixture over the standardized log gap.
                bias = self.head[-1].bias
                bias.zero_()
                bias[n_components : 2 * n_components] = torch.linspace(-1.5, 1.5, n_components)

        def forward(self, x):
            h, _ = self.gru(x)
            logw, mu, logsig = self.head(torch.cat((h, x), dim=-1)).chunk(3, dim=-1)
            sigma = logsig.exp().clamp(_SIGMA_MIN, _SIGMA_MAX)
            return LogNormalMixture(torch.log_softmax(logw, dim=-1), mu, sigma)


@dataclass
class TPPBlock:
    """One contiguous block ready for the network.

    `x[j]` is the scaled input after event j. `ylo/yhi/yfloor[i]` are the
    standardized log edges of event i's cell. Events with index >= `first`
    are scored; earlier ones only warm the inputs.
    """

    x: object
    ylo: object
    yhi: object
    yfloor: object
    first: int

    @property
    def n(self) -> int:
        return int(self.x.shape[0])


def prepare_block(
    cen: Censored, scaler: TPPScaler, horizons_s: tuple[float, ...], first: int
) -> TPPBlock:
    _require_torch()
    feats = (tpp_features(cen, horizons_s) - scaler.mean) / scaler.std
    feats = np.clip(np.nan_to_num(feats, nan=0.0), -8.0, 8.0)

    def edge(v: np.ndarray):
        with np.errstate(divide="ignore"):
            y = (np.log(v) - scaler.mean[0]) / scaler.std[0]
        return torch.from_numpy(np.clip(y, -_Y_CLAMP, _Y_CLAMP))

    return TPPBlock(
        x=torch.from_numpy(feats.astype(np.float32)),
        ylo=edge(cen.lo), yhi=edge(cen.hi), yfloor=edge(cen.floor), first=int(first),
    )


def _window_loglik(model, block: TPPBlock, starts, length: int, skip: int):
    """Scores of events starts+skip+1 .. starts+length for a batch of windows.

    Position p of a window reads inputs starts .. starts+p and predicts event
    starts+p+1, so nothing after the predicted event's predecessor is read.
    """
    idx = starts.unsqueeze(1) + torch.arange(length).unsqueeze(0)
    mix = model(block.x[idx])
    tgt = idx[:, skip:] + 1
    part = LogNormalMixture(mix.logw[:, skip:], mix.mu[:, skip:], mix.sigma[:, skip:])
    ll, ls = part.log_cell_y(block.ylo[tgt], block.yhi[tgt], block.yfloor[tgt])
    return tgt, ll, ls


def score_tpp(model, block: TPPBlock, cfg: TPPConfig) -> Scored:
    """Censored per-event scores on events `block.first` .. n-1.

    Windows are laid on a fixed grid from `block.first`, each with
    `window_burn` warm-up events, exactly as in training; the last window is
    simply shorter. The score of event i therefore depends on events up to i
    only, and does not change if later events are altered or removed.
    """
    _require_torch()
    burn, stride = cfg.window_burn, cfg.window - cfg.window_burn
    if block.first < burn + 1:
        raise ValueError("block.first must leave room for the window warm-up")
    loglik = np.zeros(block.n)
    log_surv = np.zeros(block.n)
    first_start = block.first - burn - 1
    n_full = max((block.n - 1 - first_start - burn) // stride, 0)
    starts = first_start + stride * torch.arange(n_full)
    model.eval()
    with torch.no_grad():
        batches = [(s, cfg.window) for s in torch.split(starts, cfg.eval_batch)]
        tail_start = first_start + stride * n_full
        tail_len = block.n - 1 - tail_start
        if tail_len > burn:
            batches.append((torch.tensor([tail_start]), tail_len))
        for s, length in batches:
            tgt, ll, ls = _window_loglik(model, block, s, length, burn)
            loglik[tgt.numpy().ravel()] = ll.numpy().ravel()
            log_surv[tgt.numpy().ravel()] = ls.numpy().ravel()
    return Scored(loglik=loglik, log_surv_lo=log_surv)


def train_tpp(train: TPPBlock, valid: TPPBlock, cfg: TPPConfig):
    """Fit the network by truncated backpropagation; early-stop on validation.

    Each epoch draws `max_windows_per_epoch` random contiguous windows of the
    training block (events are never subsampled individually: thinning
    changes the process). Returns (model at the best validation epoch, list of
    per-epoch records).
    """
    _require_torch()
    torch.manual_seed(cfg.seed)
    gen = torch.Generator().manual_seed(cfg.seed)
    model = LogNormMixTPP(train.x.shape[1], cfg.hidden, cfg.n_components)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    lo_start = train.first - cfg.window_burn - 1
    hi_start = train.n - 1 - cfg.window
    if lo_start < 0 or hi_start <= lo_start:
        raise ValueError("training block too short for the window and warm-up")

    history: list[dict] = []
    best_state, best_valid, stale = None, -np.inf, 0
    for epoch in range(cfg.epochs):
        t0 = time.perf_counter()
        model.train()
        starts = torch.randint(lo_start, hi_start + 1, (cfg.max_windows_per_epoch,), generator=gen)
        total, count = 0.0, 0
        for s in torch.split(starts, cfg.batch_size):
            _, ll, _ = _window_loglik(model, train, s, cfg.window, cfg.window_burn)
            loss = -ll.mean()
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            opt.step()
            total += float(ll.detach().sum())
            count += ll.numel()
        valid_ll = float(score_tpp(model, valid, cfg).loglik[valid.first:].mean())
        history.append({
            "epoch": epoch, "train_nats_per_event": total / count,
            "valid_nats_per_event": valid_ll, "seconds": time.perf_counter() - t0,
        })
        if valid_ll > best_valid:
            best_valid, stale = valid_ll, 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            stale += 1
            if stale >= cfg.patience:
                break
    model.load_state_dict(best_state)
    return model, history
