"""Univariate exponential-kernel Hawkes process: simulator, MLE, count-variance.

Parameterization: intensity λ(t) = mu + Σ_{t_i < t} alpha*beta*exp(-beta*(t-t_i)).
The kernel is φ(t) = alpha*beta*exp(-beta*t); its integral over [0, ∞) is
    ∫ alpha*beta*exp(-beta*t) dt = alpha*beta * (1/beta) = alpha,
so alpha is the branching ratio n (Hawkes & Oakes 1974; Bacry, Mastromatteo
& Muzy 2015, "Hawkes processes in finance"). alpha in [0, 1) for a stationary
process; alpha -> 1 is criticality; alpha >= 1 is explosive/non-stationary.

Three estimators cross-check each other, and n̂ should be reported with its
sensitivity to window and kernel family:
  - simulate_hawkes_exp: ground truth via Ogata (1978) thinning.
  - fit_hawkes_exp: parametric MLE using the O(N) exponential-kernel
    recursion, optimized with a hand-rolled multi-start Nelder-Mead
    (numpy only, no scipy).
  - branching_count_variance: Hardiman & Bouchaud (2014) model-free
    estimator from count mean/variance alone, with no kernel shape assumed.

On a non-stationary-rate (but not self-exciting) process, both a Hawkes MLE
and the count-variance estimator report spurious positive endogeneity
(Filimonov & Sornette 2015; tests/estimators/test_hawkes.py reproduces it).
mu(t) therefore has to be deseasonalized before an n̂ on real data is trusted.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

# ---------------------------------------------------------------------------
# Simulation: Ogata (1978) thinning.
# ---------------------------------------------------------------------------


def simulate_hawkes_exp(mu: float, alpha: float, beta: float, t_end: float, seed: int) -> np.ndarray:
    """Simulate event times of an exponential-kernel Hawkes process via thinning.

    λ(t) = mu + Σ_{t_i < t} alpha*beta*exp(-beta*(t - t_i)); branching ratio
    (kernel integral) is exactly alpha:

        >>> import numpy as np
        >>> alpha, beta = 0.4, 2.0
        >>> t = np.linspace(0, 50, 200_000)
        >>> kernel_integral = np.trapezoid(alpha * beta * np.exp(-beta * t), t)
        >>> bool(abs(kernel_integral - alpha) < 1e-3)
        True

    Algorithm (Ogata thinning): the exponential kernel is Markov, so keep the
    running excitation
        E(t) = Σ_{t_i < t} alpha*beta*exp(-beta*(t - t_i)),
    which decays between events and jumps by +alpha*beta at each accepted
    event. After an event at t_i the intensity mu + E(t_i^+) is its local
    maximum until the next accepted event. The code uses the bound
        lambda_bar = mu + E(t_i^+) + alpha*beta,
    which is looser than that maximum by alpha*beta. It is still a valid upper
    bound on λ(t) on [t_i, next accepted event], and the slack costs only
    extra rejected candidates (the initial bound mu + alpha*beta has the same
    slack). Draw candidates from a homogeneous Poisson process at rate
    lambda_bar and accept a candidate at t_c with probability λ(t_c)/lambda_bar.
    After a rejection the bound is still valid (intensity only decays between
    events), so thinning continues
    from t_c with the same lambda_bar.
    """
    if beta <= 0.0:
        raise ValueError("beta must be positive")
    if mu <= 0.0:
        raise ValueError("mu must be positive")
    if alpha < 0.0 or alpha >= 1.0:
        raise ValueError(
            f"alpha must be in [0, 1); got {alpha}. alpha >= 1 is explosive/"
            "non-stationary (branching ratio >= 1, expected event count "
            "diverges) and thinning would never terminate."
        )
    if t_end <= 0.0:
        raise ValueError("t_end must be positive")

    rng = np.random.default_rng(seed)
    events: list[float] = []

    t = 0.0
    excitation = 0.0  # E(t) just after the most recent processed point
    lambda_bar = mu + excitation + alpha * beta  # upper bound valid until next accept

    while t < t_end:
        # Candidate inter-arrival time from homogeneous Poisson(lambda_bar).
        t += rng.exponential(1.0 / lambda_bar)
        if t >= t_end:
            break

        # Decay the excitation from the last accepted event to the candidate time.
        if events:
            dt_last = t - events[-1]
            excitation_at_t = excitation * np.exp(-beta * dt_last)
        else:
            excitation_at_t = 0.0

        lam_t = mu + excitation_at_t
        u = rng.random()
        if u <= lam_t / lambda_bar:
            events.append(t)
            excitation = excitation_at_t + alpha * beta
            lambda_bar = mu + excitation + alpha * beta
        # else rejected: lambda_bar remains valid; continue thinning from t.

    return np.asarray(events, dtype=np.float64)


def simulate_hawkes_multiexp(
    mu: float, alphas: np.ndarray, betas: np.ndarray, t_end: float, seed: int
) -> np.ndarray:
    """Simulate a sum-of-exponentials-kernel Hawkes process via Ogata thinning.

    λ(t) = mu + Σ_{t_i < t} φ(t - t_i), φ(t) = Σ_k alpha_k*beta_k*exp(-beta_k*t).

    Branching ratio (total kernel integral) is n = Σ_k alpha_k, as each
    component integrates to alpha_k. A sum of exponentials spanning decades of
    timescales is the standard fix for kernel misspecification: a single
    exponential decays too fast to capture a long-memory kernel's mass at long
    lags, so a K=1 fit underestimates n on such data (Bacry, Mastromatteo &
    Muzy 2015).

    Same thinning scheme as `simulate_hawkes_exp`: each component E_k(t)
    decays between events and jumps by +alpha_k*beta_k at each accepted
    event, so mu + Σ_k E_k(t_i^+) is the local maximum until the next accepted
    event and a valid thinning bound.
    """
    if t_end <= 0.0:
        raise ValueError("t_end must be positive")
    if mu <= 0.0:
        raise ValueError("mu must be positive")

    alphas = np.asarray(alphas, dtype=np.float64)
    betas = np.asarray(betas, dtype=np.float64)
    if alphas.ndim != 1 or betas.ndim != 1 or alphas.size == 0:
        raise ValueError("alphas and betas must be non-empty 1-D arrays")
    if alphas.size != betas.size:
        raise ValueError(
            f"alphas and betas must have the same length; got {alphas.size} and {betas.size}"
        )
    if np.any(betas <= 0.0):
        raise ValueError("all betas must be positive")
    if np.any(alphas < 0.0):
        raise ValueError("all alphas must be non-negative")

    n = float(np.sum(alphas))
    if n >= 1.0:
        raise ValueError(
            f"branching ratio n=sum(alphas)={n} must be < 1; n >= 1 is explosive/"
            "non-stationary and thinning would never terminate."
        )

    rng = np.random.default_rng(seed)
    events: list[float] = []

    k = alphas.size
    t = 0.0
    excitation = np.zeros(k, dtype=np.float64)  # E_k(t) just after last processed point
    peak_jump = alphas * betas  # each accepted event adds alpha_k*beta_k to E_k
    lambda_bar = mu + excitation.sum() + peak_jump.sum()

    while t < t_end:
        t += rng.exponential(1.0 / lambda_bar)
        if t >= t_end:
            break

        if events:
            dt_last = t - events[-1]
            excitation_at_t = excitation * np.exp(-betas * dt_last)
        else:
            excitation_at_t = np.zeros(k, dtype=np.float64)

        lam_t = mu + excitation_at_t.sum()
        u = rng.random()
        if u <= lam_t / lambda_bar:
            events.append(t)
            excitation = excitation_at_t + peak_jump
            lambda_bar = mu + excitation.sum() + peak_jump.sum()
        # else rejected: lambda_bar remains valid; continue thinning from t.

    return np.asarray(events, dtype=np.float64)


def simulate_seasonal_hawkes_exp(
    mu_bar: float, alpha: float, beta: float, t_end: float, shape: np.ndarray, seed: int
) -> np.ndarray:
    """Simulate a Hawkes process with a periodic (24h), piecewise-constant baseline.

    λ(t) = mu_bar*shape(tod(t)) + Σ_{t_i < t} alpha*beta*exp(-beta*(t - t_i))

    where `shape` is an `n_bins`-length array (mean 1, as returned by
    `microstructure.signals.eventtime.intraday_rate_profile`) giving the
    baseline-rate multiplier for each equal-width time-of-day bin. The period
    is 86400 seconds (this module works in float seconds, not epoch-ms),
    `tod(t)` is `t mod 86400`, and `t=0` is the start of a day.

    The baseline is seasonal from the start, so unlike thinning an
    already-simulated homogeneous Hawkes process by a time-of-day mask
    (tests/signals/test_eventtime.py's `_thin_by_daily_profile`), it does not
    discard self-excited child events. It is the right generator for testing
    that business-time rescaling recovers the true branching ratio from a
    seasonality-confounded fit.

    Algorithm: the thinning of `simulate_hawkes_exp` with `mu` replaced by
    `mu_bar*shape[bin_idx(t)]`, and the bound
    `lambda_bar = mu_bar*max(shape) + excitation + alpha*beta` using the
    seasonal peak, since the baseline is no longer constant between accepted
    events. Bin boundaries need no special-casing in continuous-time thinning.

    With `shape` identically 1 this has the same distribution as
    `simulate_hawkes_exp(mu_bar, alpha, beta, t_end, seed)`, though not the
    same realized event times (the acceptance draws differ once `lambda_bar`
    differs). tests/estimators/test_hawkes.py checks this through matched
    event counts and fitted parameters.
    """
    if beta <= 0.0:
        raise ValueError("beta must be positive")
    if mu_bar <= 0.0:
        raise ValueError("mu_bar must be positive")
    if alpha < 0.0 or alpha >= 1.0:
        raise ValueError(
            f"alpha must be in [0, 1); got {alpha}. alpha >= 1 is explosive/"
            "non-stationary (branching ratio >= 1, expected event count "
            "diverges) and thinning would never terminate."
        )
    if t_end <= 0.0:
        raise ValueError("t_end must be positive")

    shape = np.asarray(shape, dtype=np.float64)
    if shape.ndim != 1 or shape.size == 0:
        raise ValueError("shape must be a non-empty 1-D array")
    if not np.all(np.isfinite(shape)) or np.any(shape <= 0.0):
        raise ValueError("shape must be finite and strictly positive everywhere")

    day_s = 86_400.0
    n_bins = shape.size
    bin_width_s = day_s / n_bins
    shape_max = float(shape.max())

    rng = np.random.default_rng(seed)
    events: list[float] = []

    t = 0.0
    excitation = 0.0  # E(t) just after the most recent processed point
    # Baseline bound is the seasonal peak mu_bar*shape_max.
    lambda_bar = mu_bar * shape_max + excitation + alpha * beta

    while t < t_end:
        t += rng.exponential(1.0 / lambda_bar)
        if t >= t_end:
            break

        if events:
            dt_last = t - events[-1]
            excitation_at_t = excitation * np.exp(-beta * dt_last)
        else:
            excitation_at_t = 0.0

        bin_idx = min(int((t % day_s) / bin_width_s), n_bins - 1)
        baseline_at_t = mu_bar * shape[bin_idx]
        lam_t = baseline_at_t + excitation_at_t

        u = rng.random()
        if u <= lam_t / lambda_bar:
            events.append(t)
            excitation = excitation_at_t + alpha * beta
            lambda_bar = mu_bar * shape_max + excitation + alpha * beta
        # else rejected: lambda_bar remains a valid upper bound; continue thinning from t.

    return np.asarray(events, dtype=np.float64)


# ---------------------------------------------------------------------------
# MLE: O(N) recursion + hand-rolled multi-start Nelder-Mead.
# ---------------------------------------------------------------------------


# Objective value returned for infeasible/non-finite likelihoods. A Nelder-Mead
# run whose best value is this sentinel has found nothing, however flat its simplex.
_PENALTY = 1e18


def _validate_event_times(times: np.ndarray, t_end: float) -> None:
    """Raise ValueError unless `times` is a 1-D, finite, non-decreasing array in
    [0, t_end] and `t_end` is finite and positive. Empty input is allowed."""
    if not np.isfinite(t_end) or t_end <= 0.0:
        raise ValueError(f"t_end must be finite and > 0; got {t_end}")
    if times.ndim != 1:
        raise ValueError(f"times must be 1-D; got shape {times.shape}")
    if times.size == 0:
        return
    if not np.all(np.isfinite(times)):
        raise ValueError("times must be finite (found NaN or inf)")
    if times[0] < 0.0:
        raise ValueError(f"times[0] must be >= 0; got {times[0]}")
    if np.any(np.diff(times) < 0.0):
        raise ValueError("times must be sorted non-decreasing")
    if times[-1] > t_end:
        raise ValueError(f"t_end {t_end} must be >= the last event time {times[-1]}")


@dataclass(frozen=True)
class HawkesFit:
    mu: float
    alpha: float
    beta: float
    loglik: float
    converged: bool


def _excitation_recursion(decay: np.ndarray) -> np.ndarray:
    """Vectorized R_i recursion: R_0=0, R_i = decay[i-1]*(R_{i-1}+1).

    This is an affine recurrence x_i = a_i*x_{i-1} + b_i with a_i = b_i =
    decay[i-1]. A Python loop over N events dominates MLE runtime (the
    likelihood is called ~1000x by the multi-start Nelder-Mead on up to ~10^5
    events), so it is computed with a Hillis-Steele parallel prefix scan:
    O(N log N) vectorized numpy operations, about 5x faster on a whole fit
    (~16.4s -> ~3.2s on 83k events). Each scan step composes affine maps
    (a1,b1) then (a2,b2) as a = a2*a1, b = a2*b1 + b2.
    """
    n = decay.size
    if n == 0:
        return np.array([0.0])

    a = decay.copy()
    b = decay.copy()
    shift = 1
    while shift < n:
        a_shifted = np.ones_like(a)
        b_shifted = np.zeros_like(b)
        a_shifted[shift:] = a[:-shift]
        b_shifted[shift:] = b[:-shift]
        b = b + a * b_shifted
        a = a * a_shifted
        shift *= 2

    r = np.empty(n + 1, dtype=np.float64)
    r[0] = 0.0
    r[1:] = b  # x_0 = 0, so x_i = a_i*0 + b_i = b_i
    return r


def hawkes_loglik(times: np.ndarray, t_end: float, mu: float, alpha: float, beta: float) -> float:
    """Validated entry point; see `_hawkes_loglik_raw` for the formula.

    Raises ValueError for non-finite, unsorted or out-of-window times."""
    _validate_event_times(times, t_end)
    return _hawkes_loglik_raw(times, t_end, mu, alpha, beta)


def _hawkes_loglik_raw(
    times: np.ndarray, t_end: float, mu: float, alpha: float, beta: float
) -> float:
    """Exact log-likelihood via the O(N) exponential-kernel recursion.

    loglik = Σ_i log(mu + alpha*beta*R_i) - mu*T - alpha*Σ_i (1 - exp(-beta*(T-t_i)))

    with R_1 = 0, R_{i+1} = exp(-beta*(t_{i+1}-t_i)) * (R_i + 1). R_i is
    Σ_{j<i} exp(-beta*(t_i - t_j)), so mu + alpha*beta*R_i is exactly
    λ(t_i^-). The remaining terms are the compensator ∫_0^T λ(t) dt: the
    baseline mu*T plus, per event, its kernel truncated at T:
    ∫_{t_i}^{T} alpha*beta*exp(-beta*(t-t_i)) dt = alpha*(1-exp(-beta*(T-t_i))).
    """
    n = times.size
    if n == 0:
        return -mu * t_end

    if mu <= 0.0 or alpha < 0.0 or alpha >= 1.0 or beta <= 0.0:
        return -np.inf

    dt = np.diff(times)
    decay = np.exp(-beta * dt)
    r = _excitation_recursion(decay)

    intensities = mu + alpha * beta * r
    if np.any(intensities <= 0.0):
        return -np.inf

    log_sum = np.sum(np.log(intensities))
    compensator_baseline = mu * t_end
    compensator_excitation = alpha * np.sum(1.0 - np.exp(-beta * (t_end - times)))

    return float(log_sum - compensator_baseline - compensator_excitation)


def _neg_loglik_transformed(params: np.ndarray, times: np.ndarray, t_end: float) -> float:
    """Negative log-likelihood as a function of unconstrained (log mu, logit alpha, log beta)."""
    log_mu, logit_alpha, log_beta = params
    mu = float(np.exp(log_mu))
    alpha = float(1.0 / (1.0 + np.exp(-logit_alpha)))  # logistic -> (0, 1)
    beta = float(np.exp(log_beta))
    ll = _hawkes_loglik_raw(times, t_end, mu, alpha, beta)
    if not np.isfinite(ll):
        return _PENALTY
    return -ll


def _nelder_mead(
    f: Callable[[np.ndarray], float],
    x0: np.ndarray,
    max_iter: int = 500,
    step: float = 0.5,
    tol: float = 1e-6,
) -> tuple[np.ndarray, float, bool]:
    """Minimal Nelder-Mead simplex minimizer (numpy only, no scipy).

    Standard reflection/expansion/contraction/shrink algorithm (Nelder &
    Mead 1965). Converged when the spread of function values across the
    simplex (max - min) falls below `tol`.
    """
    dim = x0.size
    alpha_r, gamma_e, rho_c, sigma_s = 1.0, 2.0, 0.5, 0.5  # standard coefficients

    simplex = np.empty((dim + 1, dim), dtype=np.float64)
    simplex[0] = x0
    for i in range(dim):
        perturbed = x0.copy()
        perturbed[i] += step if x0[i] == 0.0 else step * x0[i]
        simplex[i + 1] = perturbed

    values = np.array([f(p) for p in simplex])
    converged = False

    for _ in range(max_iter):
        order = np.argsort(values)
        simplex = simplex[order]
        values = values[order]

        if (values[-1] - values[0]) < tol:
            converged = True
            break

        centroid = simplex[:-1].mean(axis=0)
        worst = simplex[-1]
        worst_val = values[-1]

        # Reflection
        reflected = centroid + alpha_r * (centroid - worst)
        reflected_val = f(reflected)

        if values[0] <= reflected_val < values[-2]:
            simplex[-1] = reflected
            values[-1] = reflected_val
            continue

        if reflected_val < values[0]:
            # Expansion
            expanded = centroid + gamma_e * (reflected - centroid)
            expanded_val = f(expanded)
            if expanded_val < reflected_val:
                simplex[-1] = expanded
                values[-1] = expanded_val
            else:
                simplex[-1] = reflected
                values[-1] = reflected_val
            continue

        # Contraction (reflected_val >= values[-2]): outside (toward the
        # reflected point) if it beat the worst point, inside (toward the
        # worst point) otherwise.
        if reflected_val < worst_val:
            contracted = centroid + rho_c * (reflected - centroid)
        else:
            contracted = centroid + rho_c * (worst - centroid)
        contracted_val = f(contracted)
        if contracted_val < min(reflected_val, worst_val):
            simplex[-1] = contracted
            values[-1] = contracted_val
            continue

        # Shrink
        best = simplex[0]
        for i in range(1, dim + 1):
            simplex[i] = best + sigma_s * (simplex[i] - best)
            values[i] = f(simplex[i])

    order = np.argsort(values)
    simplex = simplex[order]
    values = values[order]
    if not converged:
        converged = (values[-1] - values[0]) < tol
    # A simplex stuck on the penalty sentinel has zero spread but found nothing.
    if values[0] >= _PENALTY:
        converged = False
    return simplex[0], float(values[0]), converged


def fit_hawkes_exp(times: np.ndarray, t_end: float) -> HawkesFit:
    """MLE of (mu, alpha, beta) for an exponential-kernel Hawkes process.

    Optimizes over unconstrained params (log mu, logit alpha, log beta), so
    alpha stays in (0, 1) without boundary handling. Runs 5 multi-starts from
    spread initial points (mitigating the weak identification near n≈1) and
    returns the best-loglik result. `converged` is True iff the winning
    start's simplex satisfies the Nelder-Mead spread criterion (tol=1e-6).

    Caveat: `converged` says only that the simplex stopped improving locally,
    not that the parameters are well identified. Near n≈1 the likelihood has a
    long shallow ridge along which mu and alpha trade off (small-mu/high-n
    looks locally like big-mu/low-n), so a fit can report `converged=True`
    anywhere along it. Multi-start helps but does not remove this; near the
    boundary of alpha prefer multi-seed spread checks (as in
    test_mle_alpha_stable_across_seeds) over the single-fit flag.
    """
    _validate_event_times(times, t_end)
    if times.size < 2:
        raise ValueError("need at least 2 events to fit")

    n = times.size
    mean_rate = n / t_end

    starts = [
        (mean_rate * 0.7, 0.1, 1.0),
        (mean_rate * 0.5, 0.3, 2.0),
        (mean_rate * 0.9, 0.5, 0.5),
        (mean_rate * 0.3, 0.6, 3.0),
        (mean_rate * 0.5, 0.2, 5.0),
    ]

    best_params: np.ndarray | None = None
    best_ll = -np.inf
    best_converged = False

    for mu0, alpha0, beta0 in starts:
        x0 = np.array(
            [np.log(mu0), np.log(alpha0 / (1.0 - alpha0)), np.log(beta0)],
            dtype=np.float64,
        )
        best_x, best_f, converged = _nelder_mead(
            lambda p: _neg_loglik_transformed(p, times, t_end), x0, max_iter=500
        )
        ll = -best_f
        if ll > best_ll:
            best_ll = ll
            best_params = best_x
            best_converged = converged

    assert best_params is not None
    if best_ll <= -_PENALTY:
        best_ll, best_converged = -np.inf, False
    log_mu, logit_alpha, log_beta = best_params
    mu = float(np.exp(log_mu))
    alpha = float(1.0 / (1.0 + np.exp(-logit_alpha)))
    beta = float(np.exp(log_beta))

    return HawkesFit(mu=mu, alpha=alpha, beta=beta, loglik=best_ll, converged=best_converged)


# ---------------------------------------------------------------------------
# Sum-of-exponentials MLE: K parallel recursions + the same Nelder-Mead,
# extended to dimension 1+2K. Fitting sums of exponentials spanning decades
# of timescales makes it possible to check n̂ stability across kernel families.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiExpFit:
    """Result of `fit_hawkes_multiexp`.

    `converged` carries the caveat of `HawkesFit.converged`: it says only that
    the winning start's simplex met the tol=1e-6 spread criterion, not that
    `alphas`/`betas` are well identified. The guarantee is weaker at K>=2: a
    K=3 fit can (and on the planted-kernel test data does) report
    `converged=True` with two components on a flat ridge at near-duplicate
    betas (e.g. betas=(0.194, 4.890, 4.890), splitting one true component's
    mass across a degenerate pair). `n = sum(alphas)` is generally far better
    identified than the individual components at high K.
    """

    mu: float
    alphas: np.ndarray
    betas: np.ndarray
    n: float
    loglik: float
    converged: bool
    K: int


def hawkes_multiexp_loglik(
    times: np.ndarray, t_end: float, mu: float, alphas: np.ndarray, betas: np.ndarray
) -> float:
    """Validated entry point; see `_hawkes_multiexp_loglik_raw` for the formula.

    Raises ValueError for non-finite, unsorted or out-of-window times."""
    _validate_event_times(times, t_end)
    return _hawkes_multiexp_loglik_raw(times, t_end, mu, alphas, betas)


def _hawkes_multiexp_loglik_raw(
    times: np.ndarray, t_end: float, mu: float, alphas: np.ndarray, betas: np.ndarray
) -> float:
    """Exact log-likelihood for the sum-of-exponentials kernel.

    loglik = Σ_i log(mu + Σ_k alpha_k*beta_k*R_{k,i}) - mu*T
             - Σ_k alpha_k*Σ_i (1 - exp(-beta_k*(T-t_i)))

    Each R_k is the SAME single-exponential recursion as `hawkes_loglik`
    (R_{k,1}=0, R_{k,i+1} = exp(-beta_k*(t_{i+1}-t_i))*(R_{k,i}+1)), run K
    times in parallel — one call to `_excitation_recursion` per component,
    since the components do not interact except by summing into the total
    intensity. This reuses the existing O(N log N) vectorized recursion
    exactly, just K times instead of once; K is small (1-3 in practice) so
    this stays cheap relative to the O(N log N) cost of each recursion.
    """
    n_events = times.size
    if n_events == 0:
        return -mu * t_end

    if mu <= 0.0 or betas.size == 0 or np.any(betas <= 0.0) or np.any(alphas < 0.0):
        return -np.inf
    total_n = float(np.sum(alphas))
    if total_n >= 1.0:
        return -np.inf

    dt = np.diff(times)
    intensities = np.full(n_events, mu, dtype=np.float64)
    compensator_excitation = 0.0
    for alpha_k, beta_k in zip(alphas, betas, strict=True):
        decay_k = np.exp(-beta_k * dt)
        r_k = _excitation_recursion(decay_k)
        intensities = intensities + alpha_k * beta_k * r_k
        compensator_excitation += alpha_k * np.sum(1.0 - np.exp(-beta_k * (t_end - times)))

    if np.any(intensities <= 0.0):
        return -np.inf

    log_sum = np.sum(np.log(intensities))
    compensator_baseline = mu * t_end

    return float(log_sum - compensator_baseline - compensator_excitation)


def _alphas_from_logits(alpha_logits: np.ndarray) -> np.ndarray:
    """Map K unconstrained logits to K alphas with guaranteed Σalpha_k < 1.

    Softmax with a slack slot: append an implicit 0-logit "non-branching" slot
    to the K free logits, softmax over K+1 slots, and drop the slack slot. The
    K outputs are non-negative and sum to strictly less than 1 for any finite
    logits, so the optimizer cannot reach the explosive n>=1 region and no
    boundary penalty is needed. For K=1 it reduces to the logistic map used by
    `fit_hawkes_exp`.
    """
    padded = np.concatenate([alpha_logits, [0.0]])
    shifted = padded - np.max(padded)  # numerical stability
    weights = np.exp(shifted)
    probs = weights / np.sum(weights)
    return probs[:-1]


def _neg_multiexp_loglik_transformed(
    params: np.ndarray, times: np.ndarray, t_end: float, k: int
) -> float:
    """Negative log-likelihood as a function of unconstrained (log mu, K alpha-logits, K log-betas)."""
    log_mu = params[0]
    alpha_logits = params[1 : 1 + k]
    log_betas = params[1 + k : 1 + 2 * k]

    mu = float(np.exp(log_mu))
    alphas = _alphas_from_logits(alpha_logits)
    betas = np.exp(log_betas)

    ll = _hawkes_multiexp_loglik_raw(times, t_end, mu, alphas, betas)
    if not np.isfinite(ll):
        return _PENALTY
    return -ll


def fit_hawkes_multiexp(
    times: np.ndarray, t_end: float, K: int, betas_init: np.ndarray | None = None
) -> MultiExpFit:
    """MLE of (mu, alphas, betas) for a K-component sum-of-exponentials Hawkes kernel.

    Optimizes over 1+2K unconstrained parameters (log mu, K alpha-logits mapped
    through `_alphas_from_logits` so Σalpha_k < 1, K log-betas) with the same
    Nelder-Mead as `fit_hawkes_exp`. Multi-started from `betas_init` (default:
    log-spaced across decades, 0.1, 1, 10, ... per unit time, so the mixture
    spans timescales instead of collapsing to K copies of one rate) with a few
    perturbed alpha/mu starting points.

    For K=1 this reproduces `fit_hawkes_exp` on the same data: the softmax
    reduces to the same logistic map and the log-likelihoods are the same
    expression, so both optimizers search the same surface. Two independent
    runs agree to ~1e-7 in log-likelihood and mu/alpha and ~1e-5 in beta (the
    flattest direction), the floor set by each optimizer's tol=1e-6 stopping
    criterion (see `test_multiexp_k1_matches_fit_hawkes_exp`, tolerances
    1e-5 for loglik/mu/alpha and 1e-4 for beta).

    Why it exists: a single exponential is too short-memoried for a
    long-memory kernel, so a K=1 fit underestimates n = Σalpha_k. Raising K
    lets the mixture spread mass across well-separated timescales and
    recover more long-lag weight. Re-fitting at K=1,2,3 and reporting how n̂
    moves across K (see `branching_ratio_sensitivity`) is the intended
    diagnostic on real data.

    Identifiability: once K exceeds the number of timescales the sample can
    resolve, components become interchangeable (two can trade alpha and beta
    while barely changing the likelihood, like the near-critical mu/alpha ridge
    on `fit_hawkes_exp`). At K>=3 treat individual `alphas`/`betas` as much
    less identified than their sum n, and report n̂(K) rather than the
    per-component parameters.

    `converged` has the caveat of `fit_hawkes_exp`: it says only that the
    winning simplex stopped improving. A K=3 fit can report `converged=True`
    on a degenerate ridge, e.g. `test_multiexp_k3_on_two_exp_data_does_not_blow_up`
    converges to alphas=(0.348, 0.007, 0.245) with betas=(0.194, 4.890, 4.890),
    a duplicate-beta pair splitting what a K=2 fit represents as one
    component. The sum n is still trustworthy there (it matches K=2 to three
    decimals); the per-component values are not.

    Confound: baseline non-stationarity mimics long memory. A K=1 -> K=2 rise
    in n̂ with a slow (small beta) second component has two possible causes,
    and n̂(K) alone cannot separate them:
      1. A real long-memory kernel: the slow component recovers
         slowly-decaying self-excitation mass that K=1 truncated.
      2. Residual baseline non-stationarity (Filimonov & Sornette 2015):
         imperfect deseasonalization, a regime change or a slow intraday drift
         with a constant-mu model lets the MLE fit the drift with a spurious
         slow self-exciting component. This also fools the multi-exponential
         MLE (see `test_regime_switching_poisson_produces_spurious_endogeneity_trap`).
         `test_seasonal_baseline_confound_mimics_long_memory` shows it on a
         true single-exponential process (n=0.4, beta=2.0) with a
         piecewise-constant ±30% baseline wobble: n̂1=0.46 -> n̂2=0.83 with a
         spurious beta≈0.02 slow component.

    To diagnose a symbol, report the slow component's timescale 1/beta_slow
    next to the deseasonalization bin width and the fit-window length. A
    timescale comparable to the bin width or a large fraction of the window
    points to absorbed drift; a real long-memory timescale sits well inside
    the window and is unrelated to the binning. The control is to re-fit K=1
    with a block-wise piecewise-constant mu(t)
    (`fit_hawkes_exp_piecewise_mu`) and repeat the K=1 vs K=2 comparison. If
    the slow component vanishes, the jump was baseline drift; if it persists,
    that is evidence for real long memory. Run this control before trusting
    any single-symbol K=1->K=2 jump.
    """
    _validate_event_times(times, t_end)
    if times.size < 2:
        raise ValueError("need at least 2 events to fit")
    if K < 1:
        raise ValueError(f"K must be >= 1; got {K}")

    if betas_init is None:
        # Log-spaced across decades: 0.1, 1, 10, 100, ... /unit time.
        betas_init = np.array([10.0 ** (exp - 1) for exp in range(K)], dtype=np.float64)
    else:
        betas_init = np.asarray(betas_init, dtype=np.float64)
        if betas_init.size != K:
            raise ValueError(f"betas_init must have length K={K}; got {betas_init.size}")
        if np.any(betas_init <= 0.0):
            raise ValueError("betas_init must be strictly positive")

    n_events = times.size
    mean_rate = n_events / t_end

    # Multi-start: vary the total branching-ratio budget, the mu scale and a
    # multiplicative shift on betas_init (0.5x, 2x) so the starts do not share
    # beta seeds. Two starts (fit_hawkes_exp uses five) keep runtime bounded
    # as K grows, since betas_init already spans timescales. max_iter=600
    # (vs 500) lets the larger simplex reach tol=1e-6 at K=3.
    total_n_starts = [0.5, 0.25]
    mu_fracs = [0.5, 0.7]
    beta_shifts = [0.5, 2.0]
    max_iter = 600

    best_params: np.ndarray | None = None
    best_ll = -np.inf
    best_converged = False

    for total_n0, mu_frac, beta_shift in zip(total_n_starts, mu_fracs, beta_shifts, strict=True):
        mu0 = mean_rate * mu_frac
        # Start with total_n0 split equally across K components: solve for a
        # common logit z with K*exp(z) / (K*exp(z) + 1) = total_n0,
        # i.e. z = log(total_n0 / (K*(1-total_n0))).
        equal_share = total_n0 / K
        common_logit = np.log(equal_share / (1.0 - total_n0))
        alpha_logits0 = np.full(K, common_logit, dtype=np.float64)
        betas0 = betas_init * beta_shift

        x0 = np.concatenate([[np.log(mu0)], alpha_logits0, np.log(betas0)])
        best_x, best_f, converged = _nelder_mead(
            lambda p: _neg_multiexp_loglik_transformed(p, times, t_end, K),
            x0,
            max_iter=max_iter,
        )
        ll = -best_f
        if ll > best_ll:
            best_ll = ll
            best_params = best_x
            best_converged = converged

    assert best_params is not None
    if best_ll <= -_PENALTY:
        best_ll, best_converged = -np.inf, False
    log_mu = best_params[0]
    alpha_logits = best_params[1 : 1 + K]
    log_betas = best_params[1 + K : 1 + 2 * K]

    mu = float(np.exp(log_mu))
    alphas = _alphas_from_logits(alpha_logits)
    betas = np.exp(log_betas)
    n = float(np.sum(alphas))

    return MultiExpFit(
        mu=mu,
        alphas=alphas,
        betas=betas,
        n=n,
        loglik=best_ll,
        converged=best_converged,
        K=K,
    )


def branching_ratio_sensitivity(
    times: np.ndarray, t_end: float, Ks: tuple[int, ...] = (1, 2, 3)
) -> dict[int, MultiExpFit]:
    """Fit the sum-of-exponentials kernel at each K in `Ks` and return all fits.

    Inspect `{K: fit.n for K, fit in result.items()}` and report the spread
    across K rather than a single n̂. A large K=1 -> K=2 jump that stabilizes
    at K=3 indicates the single-exponential n̂ was biased low by kernel
    misspecification. An n̂(K) that keeps climbing, or becomes unstable at
    higher K, should be reported as such (see `fit_hawkes_multiexp` on
    identifiability).

    A rising n̂(K) with a slow (small beta) component is not by itself evidence
    of long memory: residual baseline non-stationarity produces the same
    signature (`test_seasonal_baseline_confound_mimics_long_memory`, a true
    single-exponential process). Before reading a K=1 -> K=2 jump as long-memory
    self-excitation, compare 1/beta_slow with the deseasonalization bin width
    and the fit window (comparable to either is a red flag), and re-fit K=1
    with a block-wise piecewise-constant mu(t); if the slow component vanishes,
    the jump was baseline drift. See `fit_hawkes_multiexp` for detail.
    """
    return {K: fit_hawkes_multiexp(times, t_end, K) for K in Ks}


def spurious_delta21_null(
    n_events_per_window: int, mu: float, alpha: float, beta: float, n_sims: int, seed: int
) -> np.ndarray:
    """Null distribution of Delta21 = n_hat_2 - n_hat_1 under a true single-exp kernel.

    A K=2 fit has two more free parameters than K=1 and on finite data will
    generally do strictly better in-sample, using the extra component to
    absorb sampling noise in the event-time gaps. For example, on
    `tests/analyses/test_q6b.py`'s ONEEXPUSDT fixture (mu=1.0, alpha=0.4,
    beta=2.0, seed=7, business-time windows of ~16.6k events) a K=2 fit
    converged to betas=(0.021, 0.479) with a ~11 nat log-likelihood gain over
    K=1 for 2 extra parameters, although the generative process has a single
    timescale. So n_hat_2 carries an upward finite-sample bias relative to
    n_hat_1 even when K=1 is exactly right, and Delta21 must be judged against
    the size of that bias at the relevant sample size, not a fixed tolerance.

    Simulates `n_sims` single-exponential Hawkes processes at (mu, alpha, beta),
    each sized via `t_end` to land near `n_events_per_window` events, fits K=1
    and K=2 with `fit_hawkes_multiexp`, and returns the per-simulation
    Delta21. A real Delta21 that does not exceed (e.g.) this null's 90th
    percentile is within the finite-sample null: no more than a well-specified
    K=1 process of the same size would produce.

    The bias shrinks with sample size, so calibrate at the panel's actual
    per-window event count: median null Delta21 is ~0.003-0.02 at ~10k events
    per window and a few times smaller at ~40k (noisy with few simulations, so
    use a large `n_sims` in production). Q6b caps a window's fit at
    `MAX_FIT_EVENTS=250_000`, so simulate at the panel's median per-window
    count after the cap. A smaller size overstates the null; a larger one
    understates it and makes real long memory harder to detect.

    `t_end` per simulation is `n_events_per_window * (1 - alpha) / mu`, from
    the stationary mean rate `mu / (1 - alpha)`, so the realized count lands
    near, not exactly at, the requested size.
    """
    if n_events_per_window <= 0:
        raise ValueError("n_events_per_window must be positive")
    if n_sims <= 0:
        raise ValueError("n_sims must be positive")

    mean_rate = mu / (1.0 - alpha)
    t_end = n_events_per_window / mean_rate

    rng = np.random.default_rng(seed)
    # Independent per-simulation seeds derived from `seed`.
    sim_seeds = rng.integers(0, 2**32 - 1, size=n_sims)

    deltas = np.empty(n_sims, dtype=np.float64)
    for i, sim_seed in enumerate(sim_seeds):
        times = simulate_hawkes_exp(mu, alpha, beta, t_end, seed=int(sim_seed))
        fit1 = fit_hawkes_multiexp(times, float(times[-1]), K=1)
        fit2 = fit_hawkes_multiexp(times, float(times[-1]), K=2)
        deltas[i] = fit2.n - fit1.n

    return deltas


# ---------------------------------------------------------------------------
# Model-free branching-ratio estimator (Hardiman & Bouchaud 2014).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PiecewiseMuFit:
    """Result of `fit_hawkes_exp_piecewise_mu`.

    `mus` holds one baseline rate per equal-width time block (length
    `n_blocks`); `alpha`/`beta` are the single-exponential kernel's branching
    ratio and decay rate, shared across blocks. `n` is an alias for `alpha`.

    `converged` has the caveat of `HawkesFit.converged`. It is more exposed to
    the near-critical mu/alpha ridge than the single-mu case, since a block
    with few events can trade its mu_b against alpha; treat individual `mus`
    as noisier than the shared `alpha`.
    """

    mus: np.ndarray
    alpha: float
    beta: float
    n: float
    loglik: float
    converged: bool
    n_blocks: int


def _block_index(times: np.ndarray, t_end: float, n_blocks: int) -> np.ndarray:
    """Map each event time to its equal-width block index in [0, n_blocks)."""
    block_width = t_end / n_blocks
    idx = np.floor(times / block_width).astype(np.int64)
    return np.clip(idx, 0, n_blocks - 1)


def _block_widths(t_end: float, n_blocks: int) -> np.ndarray:
    """Widths |block_b| for each of n_blocks equal-width blocks covering [0, t_end]."""
    block_width = t_end / n_blocks
    return np.full(n_blocks, block_width, dtype=np.float64)


def hawkes_piecewise_mu_loglik(
    times: np.ndarray, t_end: float, mus: np.ndarray, alpha: float, beta: float, n_blocks: int
) -> float:
    """Validated entry point; see `_hawkes_piecewise_mu_loglik_raw` for the formula.

    Raises ValueError for non-finite, unsorted or out-of-window times."""
    _validate_event_times(times, t_end)
    return _hawkes_piecewise_mu_loglik_raw(times, t_end, mus, alpha, beta, n_blocks)


def _hawkes_piecewise_mu_loglik_raw(
    times: np.ndarray, t_end: float, mus: np.ndarray, alpha: float, beta: float, n_blocks: int
) -> float:
    """Exact log-likelihood for a single-exponential kernel with a block-wise
    constant baseline mu_b(t) = mus[b(t)], b(t) the index of t's equal-width
    time block.

    loglik = Σ_i log(mu_{b(t_i)} + alpha*beta*R_i)
             - Σ_b mu_b*|block_b|
             - alpha*Σ_i (1 - exp(-beta*(T-t_i)))

    The excitation recursion R_i and excitation compensator are those of
    `hawkes_loglik`; only the baseline is block-wise. Σ_b mu_b*|block_b| is
    ∫_0^T mu(t) dt for the piecewise-constant mu(t).
    """
    n_events = times.size
    if mus.size != n_blocks:
        raise ValueError(f"mus must have length n_blocks={n_blocks}; got {mus.size}")

    if n_events == 0:
        widths = _block_widths(t_end, n_blocks)
        return float(-np.sum(mus * widths))

    if np.any(mus <= 0.0) or alpha < 0.0 or alpha >= 1.0 or beta <= 0.0:
        return -np.inf

    block_idx = _block_index(times, t_end, n_blocks)
    mu_at_event = mus[block_idx]

    dt = np.diff(times)
    decay = np.exp(-beta * dt)
    r = _excitation_recursion(decay)

    intensities = mu_at_event + alpha * beta * r
    if np.any(intensities <= 0.0):
        return -np.inf

    log_sum = np.sum(np.log(intensities))
    widths = _block_widths(t_end, n_blocks)
    compensator_baseline = float(np.sum(mus * widths))
    compensator_excitation = alpha * np.sum(1.0 - np.exp(-beta * (t_end - times)))

    return float(log_sum - compensator_baseline - compensator_excitation)


def _neg_piecewise_loglik_transformed(
    params: np.ndarray, times: np.ndarray, t_end: float, n_blocks: int
) -> float:
    """Negative log-likelihood as a function of unconstrained
    (log mu_1..log mu_B, logit alpha, log beta)."""
    log_mus = params[:n_blocks]
    logit_alpha = params[n_blocks]
    log_beta = params[n_blocks + 1]

    mus = np.exp(log_mus)
    alpha = float(1.0 / (1.0 + np.exp(-logit_alpha)))
    beta = float(np.exp(log_beta))

    ll = _hawkes_piecewise_mu_loglik_raw(times, t_end, mus, alpha, beta, n_blocks)
    if not np.isfinite(ll):
        return _PENALTY
    return -ll


MAX_PIECEWISE_BLOCKS = 12

PIECEWISE_MAX_ITER = 1500

# chi-square 0.95 quantiles for df = 1..11 (standard table values, e.g.
# NIST/SEMATECH e-Handbook of Statistical Methods, upper-tail critical values
# of the chi-square distribution at alpha=0.05). Hard-coded to avoid a scipy
# dependency; df = n_blocks - 1 and n_blocks <= MAX_PIECEWISE_BLOCKS = 12.
_CHI2_95 = {
    1: 3.841,
    2: 5.991,
    3: 7.815,
    4: 9.488,
    5: 11.070,
    6: 12.592,
    7: 14.067,
    8: 15.507,
    9: 16.919,
    10: 18.307,
    11: 19.675,
}

# Minimum K=1 -> K=2 log-likelihood gain for the extra kernel component to be
# taken as evidence at all: K=2 adds 2 free parameters (one alpha, one beta),
# so the 95% likelihood-ratio cutoff is chi2_0.95(2) / 2.
K2_GAIN_MIN_DLL = _CHI2_95[2] / 2.0

# Minimum K=1 -> K=2 branching-ratio rise before the verdict looks at the
# piecewise evidence at all.
DRIFT_K2_RISE_MIN = 0.1


def fit_hawkes_exp_piecewise_mu(
    times: np.ndarray, t_end: float, n_blocks: int, fit_k1: HawkesFit | None = None
) -> PiecewiseMuFit:
    """MLE of (mu_1..mu_B, alpha, beta) for a single-exponential-kernel Hawkes
    process with a block-wise constant baseline.

    This is the control described in `fit_hawkes_multiexp`: it re-fits K=1 but
    lets the baseline take one free value per equal-width time block of
    [0, t_end] instead of a single mu. See `baseline_drift_control` for how
    it is paired with the K=1 and K=2 fits.

    Event times lie in [0, t_end]; block b covers [b*t_end/B, (b+1)*t_end/B)
    (the last block is closed at t_end).

    Optimizes B+2 unconstrained parameters (log mu_1..log mu_B, logit alpha,
    log beta) with the module's Nelder-Mead from two starts:
      1. the constant-mu K=1 solution (every mu_b = mu-hat). The constant-mu
         model is nested in this one and Nelder-Mead never returns a point
         worse than its start, so `loglik >= fit_k1.loglik` up to
         floating-point noise; the likelihood-ratio verdict in
         `baseline_drift_control` relies on this.
      2. the empirical per-block event rates scaled by (1 - alpha-hat), with
         the K=1 alpha-hat and beta-hat.
    The better of the two is returned. Pass `fit_k1` to reuse an existing K=1
    fit.

    `n_blocks` is capped at `MAX_PIECEWISE_BLOCKS` (12): each block adds a
    simplex dimension and, at these sample sizes, too many blocks leave too
    few events per block to identify mu_b.

    `converged` has the caveat of `HawkesFit.converged`. A block with few
    events has a nearly flat likelihood in its own mu_b, and with up to 14
    dimensions the optimizer may also stop at max_iter; treat per-block mus
    as noisier than the shared alpha.
    """
    _validate_event_times(times, t_end)
    if n_blocks < 1:
        raise ValueError(f"n_blocks must be >= 1; got {n_blocks}")
    if n_blocks > MAX_PIECEWISE_BLOCKS:
        raise ValueError(f"n_blocks must be <= {MAX_PIECEWISE_BLOCKS}; got {n_blocks}")
    if times.size < 2:
        raise ValueError("need at least 2 events to fit")

    if fit_k1 is None:
        fit_k1 = fit_hawkes_exp(times, t_end)

    block_idx = _block_index(times, t_end, n_blocks)
    block_widths = _block_widths(t_end, n_blocks)
    block_counts = np.bincount(block_idx, minlength=n_blocks).astype(np.float64)
    # Empty blocks start at 0.1x the global rate to avoid log(0).
    global_rate = times.size / t_end
    empirical_block_rates = np.where(
        block_counts > 0.0, block_counts / block_widths, 0.1 * global_rate
    )

    alpha_seed = float(np.clip(fit_k1.alpha, 1e-6, 1.0 - 1e-6))
    tail = [np.log(alpha_seed / (1.0 - alpha_seed)), np.log(fit_k1.beta)]
    starts = [
        np.concatenate([np.full(n_blocks, np.log(fit_k1.mu)), tail]),
        np.concatenate([np.log(empirical_block_rates * (1.0 - alpha_seed)), tail]),
    ]

    best_params: np.ndarray | None = None
    best_ll = -np.inf
    best_converged = False

    for x0 in starts:
        best_x, best_f, converged = _nelder_mead(
            lambda p: _neg_piecewise_loglik_transformed(p, times, t_end, n_blocks),
            x0,
            max_iter=PIECEWISE_MAX_ITER,
        )
        ll = -best_f
        if ll > best_ll:
            best_ll = ll
            best_params = best_x
            best_converged = converged

    assert best_params is not None
    if best_ll <= -_PENALTY:
        best_ll, best_converged = -np.inf, False
    mus = np.exp(best_params[:n_blocks])
    alpha = float(1.0 / (1.0 + np.exp(-best_params[n_blocks])))
    beta = float(np.exp(best_params[n_blocks + 1]))

    return PiecewiseMuFit(
        mus=mus,
        alpha=alpha,
        beta=beta,
        n=alpha,
        loglik=best_ll,
        converged=best_converged,
        n_blocks=n_blocks,
    )


def _drift_verdict(k2_rise: float, dll_pw: float, dll_k2: float, n_blocks: int) -> str:
    """Label a K=1 -> K=2 rise as 'drift', 'long_memory_candidate' or
    'inconclusive' from log-likelihood gains over the constant-mu K=1 fit.

    `dll_pw` is the gain from the block-wise baseline, `dll_k2` the gain from
    the second kernel component, `n_blocks` the number of baseline blocks.
    With threshold = chi2_0.95(n_blocks - 1) / 2 (the classical LR-test
    cutoff for B-1 extra free parameters, halved because the statistic is
    2*dll):
      - k2_rise <= DRIFT_K2_RISE_MIN: 'inconclusive' (nothing to explain).
      - dll_k2 < K2_GAIN_MIN_DLL (= chi2_0.95(2)/2): 'inconclusive' (the
        second kernel component is not itself significant, so there is no
        K=2 effect for a baseline or a memory explanation to account for).
      - dll_pw >= max(threshold, 0.5 * dll_k2): 'drift' (the block baseline
        is significant and buys at least half of what the extra kernel
        component buys).
      - dll_pw < threshold: 'long_memory_candidate' (a flexible baseline does
        not help significantly).
      - otherwise 'inconclusive' (significant but under half of dll_k2).
    """
    if n_blocks < 2 or n_blocks > MAX_PIECEWISE_BLOCKS:
        raise ValueError(f"n_blocks must be in [2, {MAX_PIECEWISE_BLOCKS}]; got {n_blocks}")
    if k2_rise <= DRIFT_K2_RISE_MIN:
        return "inconclusive"
    if dll_k2 < K2_GAIN_MIN_DLL:
        return "inconclusive"
    threshold = _CHI2_95[n_blocks - 1] / 2.0
    if dll_pw >= max(threshold, 0.5 * dll_k2):
        return "drift"
    if dll_pw < threshold:
        return "long_memory_candidate"
    return "inconclusive"


def baseline_drift_control(
    times: np.ndarray,
    t_end: float,
    n_blocks: int = 8,
    fit_k1: HawkesFit | None = None,
    fit_k2: MultiExpFit | None = None,
) -> dict:
    """Compare constant-mu K=1, K=2, and block-wise-baseline K=1 fits to flag
    whether a K=1 -> K=2 branching-ratio rise looks like baseline drift or a
    candidate for long memory.

    Event times lie in [0, t_end]. `fit_k1` / `fit_k2` may be passed to reuse
    precomputed fits of the same `times` and `t_end`.

    Returned keys: n_k1, n_k2, n_k1_piecewise, slow_beta_k2 (smaller beta of
    the K=2 fit), dll_pw = piecewise.loglik - fit_k1.loglik, dll_k2 =
    fit_k2.loglik - fit_k1.loglik, dll_threshold = chi2_0.95(n_blocks-1)/2,
    and verdict (rule in `_drift_verdict`).

    The verdict is a heuristic likelihood-ratio screen, not a formal test: the
    fits come from Nelder-Mead and may miss the global optimum, the chi-square
    calibration assumes asymptotics that Hawkes likelihoods only approximately
    satisfy, and the "at least half of dll_k2" cut-off is a convention. When
    K=1 is misspecified (real long memory), block counts are more dispersed
    than K=1 predicts, which inflates dll_pw. That can push a long-memory
    process to "inconclusive" instead of "long_memory_candidate", or across the
    threshold into "drift". A "drift" label means only that the block baseline
    recovers at least half of the K=2 gain; it does not exclude long memory.

    Resolution limit: a block-wise constant baseline absorbs only drift slower
    than the block width t_end / n_blocks. Faster oscillations average out
    within a block and stay indistinguishable from long memory, so they are
    labelled 'long_memory_candidate'. Choose n_blocks (<= MAX_PIECEWISE_BLOCKS)
    so the block width is below the suspected drift timescale; otherwise that
    verdict carries no meaning.
    """
    if t_end <= 0.0:
        raise ValueError("t_end must be positive")
    if n_blocks < 1 or n_blocks > MAX_PIECEWISE_BLOCKS:
        raise ValueError(f"n_blocks must be in [1, {MAX_PIECEWISE_BLOCKS}]; got {n_blocks}")
    if n_blocks < 2:
        raise ValueError("n_blocks must be >= 2 for the likelihood-ratio verdict")

    if fit_k1 is None:
        fit_k1 = fit_hawkes_exp(times, t_end)
    if fit_k2 is None:
        fit_k2 = fit_hawkes_multiexp(times, t_end, K=2)
    fit_piecewise = fit_hawkes_exp_piecewise_mu(times, t_end, n_blocks, fit_k1=fit_k1)

    n_k1 = fit_k1.alpha
    n_k2 = fit_k2.n
    dll_pw = fit_piecewise.loglik - fit_k1.loglik
    dll_k2 = fit_k2.loglik - fit_k1.loglik
    k2_rise = n_k2 - n_k1

    return {
        "n_k1": n_k1,
        "n_k2": n_k2,
        "n_k1_piecewise": fit_piecewise.alpha,
        "slow_beta_k2": float(np.min(fit_k2.betas)),
        "dll_pw": dll_pw,
        "dll_k2": dll_k2,
        "dll_threshold": _CHI2_95[n_blocks - 1] / 2.0,
        "verdict": _drift_verdict(k2_rise, dll_pw, dll_k2, n_blocks),
    }


def branching_count_variance(times: np.ndarray, window: float, t_end: float) -> float:
    """Model-free branching-ratio estimate from count mean/variance alone.

    For a stationary Hawkes process, as the window W grows much larger than
    the kernel timescale, var(N_W)/mean(N_W) -> 1/(1-n)^2, giving
        n_hat = 1 - sqrt(mean(N_W) / var(N_W)).

    W must be much larger than the kernel timescale (1/beta for the
    exponential kernel); short windows truncate long-memory kernels and bias
    n_hat toward 0 (Bacry, Mastromatteo & Muzy 2015). No kernel shape is
    assumed, which is the estimator's advantage and, per the regime-switching
    trap test in tests/estimators/test_hawkes.py, its weakness: it cannot
    separate self-excitation from a non-stationary baseline rate.

    Raises ValueError if fewer than 20 non-overlapping windows fit in
    [0, t_end], if the window is so small it needs more than 10^9 bins (see
    max_windows below), or if the count variance is zero (regular spacing).
    """
    if window <= 0.0:
        raise ValueError("window must be positive")

    n_windows = int(t_end // window)
    if n_windows < 20:
        raise ValueError(
            f"need at least 20 non-overlapping windows, got {n_windows} "
            f"(t_end={t_end}, window={window})"
        )
    # The edge array below holds one 8-byte value per window, so the cap allows
    # up to 8GB in one call. It guards against a window orders of magnitude too
    # small for t_end (window=1e-9 with t_end=1e4 would need ~80TB) while
    # allowing 1ms windows over ~11.5 days.
    max_windows = 1_000_000_000
    if n_windows > max_windows:
        raise ValueError(
            f"window={window} implies {n_windows} windows over t_end={t_end}, "
            f"exceeding the {max_windows} sanity cap (likely a units error)"
        )

    edges = np.arange(n_windows + 1) * window
    counts, _ = np.histogram(times, bins=edges)
    counts = counts.astype(np.float64)

    mean_count = counts.mean()
    var_count = counts.var(ddof=1)

    if var_count == 0.0:
        raise ValueError("count variance is zero; cannot estimate branching ratio")

    ratio = mean_count / var_count
    return float(1.0 - np.sqrt(ratio))
