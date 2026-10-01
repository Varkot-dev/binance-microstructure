"""Univariate exponential-kernel Hawkes process: simulator, MLE, count-variance.

Parameterization: intensity λ(t) = mu + Σ_{t_i < t} alpha*beta*exp(-beta*(t-t_i)).
The kernel is φ(t) = alpha*beta*exp(-beta*t); its integral over [0, ∞) is
    ∫ alpha*beta*exp(-beta*t) dt = alpha*beta * (1/beta) = alpha,
so **alpha IS the branching ratio n** (Hawkes & Oakes 1974 branching
interpretation: docs/research/02-hawkes-processes.md §1 "Branching interpretation
and criticality"). alpha in [0, 1) for a stationary process; alpha -> 1 is
criticality; alpha >= 1 is explosive/non-stationary.

Three independent estimators are provided so they can cross-check each
other, as the literature insists on (docs/research/02 §4 "Non-negotiables:
... report n̂ sensitivity to window and kernel family"):
  - simulate_hawkes_exp: ground truth via Ogata (1978) thinning.
  - fit_hawkes_exp: parametric MLE using the O(N) exponential-kernel
    recursion, optimized with a hand-rolled multi-start Nelder-Mead
    (numpy only, no scipy).
  - branching_count_variance: Hardiman & Bouchaud (2014) model-free
    estimator from count mean/variance alone — no kernel shape assumed.

The Poisson-refutation / regime-switching trap tests in
tests/estimators/test_hawkes.py document a critical failure mode: on a
non-stationary-rate (but NOT self-exciting) process, both a Hawkes MLE and
the count-variance estimator report spurious positive endogeneity
(Filimonov & Sornette 2015, docs/research/02 §"The calibration counterattack").
This motivates deseasonalizing mu(t) before ever trusting an n̂ on real
data.
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

    Algorithm (Ogata thinning, exploiting the exponential kernel's Markov
    property so no per-candidate rebuild of the full excitation sum is
    needed): maintain the running excitation
        E(t) = Σ_{t_i < t} alpha*beta*exp(-beta*(t - t_i)),
    which decays smoothly between events and jumps by +alpha*beta at each
    accepted event. Immediately after an event at time t_i, the intensity
    is at its local maximum for the segment until the next accepted event
    (since the kernel is monotonically decaying), so
        lambda_bar = mu + E(t_i^+) = mu + E(t_i^-) + alpha*beta
    is a valid upper bound for λ(t) on [t_i, next accepted event]. Draw
    candidate arrival times from a homogeneous Poisson process at rate
    lambda_bar; accept a candidate at time t_c with probability
    λ(t_c)/lambda_bar. On rejection, the bound is still valid going
    forward (intensity only decays between events) so we simply continue
    thinning from t_c without recomputing lambda_bar.
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

        # Decay excitation from the last processed point to the candidate time.
        # (excitation tracked at the time of the last event/candidate, "dt" is
        # the gap since then.)
        # We recompute excitation at t directly below via the last event time.
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
        # else rejected: lambda_bar remains valid (intensity only decays
        # between accepted events), continue thinning from t.

    return np.asarray(events, dtype=np.float64)


def simulate_hawkes_multiexp(
    mu: float, alphas: np.ndarray, betas: np.ndarray, t_end: float, seed: int
) -> np.ndarray:
    """Simulate a sum-of-exponentials-kernel Hawkes process via Ogata thinning.

    λ(t) = mu + Σ_{t_i < t} φ(t - t_i), φ(t) = Σ_k alpha_k*beta_k*exp(-beta_k*t).

    Branching ratio (total kernel integral) is n = Σ_k alpha_k, exactly as in
    the single-exponential case (each component integrates to alpha_k). This
    is the standard "sum of exponentials spanning decades of timescales" fix
    for kernel misspecification noted in docs/research/02-hawkes-processes.md
    §4 pitfall 3 ("Exponential fits to power-law data underestimate n; power-
    law fits are sensitive to short-time regularization. Fit sums of
    exponentials spanning decades of timescales; check n̂ stability.") — a
    single exponential decays too fast to capture a long-memory/power-law-like
    kernel's mass at long lags, so a K=1 MLE fit systematically underestimates
    n on such data; a mixture of exponentials at well-separated timescales
    approximates the long-memory shape and recovers more of that mass.

    Reuses the same structure as `simulate_hawkes_exp`: each component's
    excitation E_k(t) = Σ_{t_i<t} alpha_k*beta_k*exp(-beta_k*(t-t_i)) decays
    smoothly between events and jumps by +alpha_k*beta_k at each accepted
    event, so immediately after an event the total intensity
    mu + Σ_k E_k(t_i^+) is the local maximum until the next accepted event
    (sum of monotonically-decaying components is itself monotonically
    decaying), giving a valid Ogata thinning upper bound.
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
        # else rejected: lambda_bar remains valid (each component only
        # decays between accepted events), continue thinning from t.

    return np.asarray(events, dtype=np.float64)


def simulate_seasonal_hawkes_exp(
    mu_bar: float, alpha: float, beta: float, t_end: float, shape: np.ndarray, seed: int
) -> np.ndarray:
    """Simulate a Hawkes process with a periodic (24h), piecewise-constant baseline.

    λ(t) = mu_bar*shape(tod(t)) + Σ_{t_i < t} alpha*beta*exp(-beta*(t - t_i))

    where `shape` is an `n_bins`-length array (mean 1 by construction, as
    returned by `microstructure.signals.eventtime.intraday_rate_profile`)
    giving the baseline-rate multiplier for each equal-width time-of-day bin
    over a 24h period (period = 86400 SECONDS here, since this module works
    in float seconds, not the eventtime module's epoch-ms; the caller is
    responsible for keeping units consistent, e.g. by choosing `shape` to
    represent one bin per 86400/n_bins seconds and treating `t=0` as the
    start of a day). `tod(t)` is `t mod 86400`.

    This is the honest generative model this module was missing: unlike
    thinning an already-simulated homogeneous-mu Hawkes process by a
    time-of-day mask (an approximation used in
    tests/signals/test_eventtime.py's `_thin_by_daily_profile` secondary
    control test — see that test's docstring), this simulator makes the
    baseline rate itself seasonal from the start, so it does not also
    discard already-realized self-excited "child" events the way
    post-hoc thinning does. It is the correct tool for testing that
    business-time rescaling recovers the true branching ratio from a
    seasonality-confounded Hawkes fit.

    Algorithm: same Ogata (1978) thinning / exponential-kernel excitation
    tracking as `simulate_hawkes_exp`, except the constant `mu` is replaced
    by `mu_bar*shape[bin_idx(t)]` and the thinning upper bound
    `lambda_bar = mu_bar*max(shape) + excitation + alpha*beta` uses the
    seasonal peak (`max(shape)`) instead of a constant baseline, since the
    baseline term is no longer constant between accepted events (only the
    excitation term's monotonic decay is exploited for the bound, same as
    the unseasonal simulator; the baseline swap point (bin boundary) is a
    negligible/zero-measure event under continuous-time thinning so no
    special-casing across bin boundaries is required for correctness).

    Sanity property: with `shape` identically 1 everywhere, this reduces
    statistically to `simulate_hawkes_exp(mu_bar, alpha, beta, t_end, seed)`
    (same distribution, not necessarily the same realized event times,
    since the acceptance draws differ once `lambda_bar` differs — verified
    in tests/estimators/test_hawkes.py via matched event-count and fitted-
    parameter statistics, not exact event-time equality).
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
    # Upper bound on the baseline is mu_bar*shape_max (seasonal peak); the
    # excitation term contributes its own post-event peak as in the
    # unseasonal simulator.
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
        # else rejected: lambda_bar remains a valid upper bound (baseline is
        # capped at mu_bar*shape_max, excitation only decays between
        # accepted events), continue thinning from t.

    return np.asarray(events, dtype=np.float64)


# ---------------------------------------------------------------------------
# MLE: O(N) recursion + hand-rolled multi-start Nelder-Mead.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HawkesFit:
    mu: float
    alpha: float
    beta: float
    loglik: float
    converged: bool


def _excitation_recursion(decay: np.ndarray) -> np.ndarray:
    """Vectorized R_i recursion: R_0=0, R_i = decay[i-1]*(R_{i-1}+1).

    This is an affine linear recurrence x_i = a_i*x_{i-1} + b_i with
    a_i = b_i = decay[i-1]. A naive Python for-loop over N events is the
    bottleneck in MLE fitting (called ~1000x by Nelder-Mead multi-start,
    on up to ~10^5 events per call) — the loop's per-element Python
    overhead dominates runtime. This computes the same recursion with a
    Hillis-Steele parallel prefix scan: O(N log N) numpy vector ops
    instead of O(N) Python-level iterations, measured ~5x faster in
    practice (whole-fit wall clock, ~16.4s -> ~3.2s on an 83k-event fit)
    for N ~ 10^4-10^5 despite the extra log-factor work, because every
    step here is a vectorized numpy op rather than a scalar Python one.
    Each scan step combines affine maps (a1,b1) then (a2,b2) via
    a = a2*a1, b = a2*b1 + b2 (composition x -> a2*(a1*x+b1)+b2).
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
    """Exact log-likelihood via the O(N) exponential-kernel recursion.

    loglik = Σ_i log(mu + alpha*beta*R_i) - mu*T - alpha*Σ_i (1 - exp(-beta*(T-t_i)))

    with R_1 = 0, R_{i+1} = exp(-beta*(t_{i+1}-t_i)) * (R_i + 1)  (docs/research/02
    §4.1). R_i represents Σ_{j<i} exp(-beta*(t_i - t_j)), so
    mu + alpha*beta*R_i is exactly λ(t_i^-). The second term is the
    compensator ∫_0^T λ(t) dt, split into the baseline mu*T plus, for each
    event, the integral of its own decaying kernel contribution truncated
    at T: ∫_{t_i}^{T} alpha*beta*exp(-beta*(t-t_i)) dt = alpha*(1-exp(-beta*(T-t_i))).
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
    ll = hawkes_loglik(times, t_end, mu, alpha, beta)
    if not np.isfinite(ll):
        return 1e18
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
    Mead 1965), including the outside-vs-inside contraction distinction:
    when the reflected point beats the worst point but not the
    second-worst, contract toward whichever of {reflected, worst} is
    better (outside contraction toward reflected if it improved on worst,
    inside contraction toward worst otherwise). Convergence criterion:
    the spread of function values across the simplex (max - min) falls
    below `tol`.
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

        # Contraction (reflected_val >= values[-2]): outside vs inside per
        # the standard algorithm. If the reflected point beat the worst
        # point, contract toward the reflected point (outside contraction);
        # otherwise contract toward the original worst point (inside
        # contraction) since reflection didn't even improve on worst.
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
    return simplex[0], float(values[0]), converged


def fit_hawkes_exp(times: np.ndarray, t_end: float) -> HawkesFit:
    """MLE of (mu, alpha, beta) for an exponential-kernel Hawkes process.

    Optimizes over unconstrained params (log mu, logit alpha, log beta) so
    the simplex search never has to respect boundary constraints; alpha is
    mapped through a logistic transform into (0, 1) (per the brief: "alpha
    constrained to (0,1) via logistic transform"). Runs 5 multi-starts from
    spread initial points (mitigates the near-unidentifiability at n≈1
    documented in docs/research/02 §4 pitfall 5) and returns the best-loglik
    result. `converged` is True iff the winning start's simplex satisfies
    the Nelder-Mead spread-in-loglik convergence criterion (tol=1e-6).

    CAVEAT on `converged`: this reflects ONLY that the simplex's
    function values stopped spreading out — i.e. the optimizer found a
    local optimum of the likelihood surface it could no longer improve
    on with small moves. It does NOT mean the parameters themselves are
    well identified. Near n≈1 the likelihood surface can have a long,
    shallow ridge along which mu and alpha trade off (a small-mu/high-n
    combination looks locally like a big-mu/low-n one — docs/research/02 §4
    pitfall 5), so a fit can report `converged=True` while sitting
    anywhere along that ridge; the reported point estimate is then much
    less trustworthy than `converged=True` alone would suggest. Multi-
    start helps but does not eliminate this — treat `converged=True`
    near the boundary of alpha as a weaker signal than the same flag
    away from it, and prefer profile-likelihood or multi-seed spread
    checks (as in test_mle_alpha_stable_across_seeds) over trusting a
    single fit's convergence flag in that regime.
    """
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
    log_mu, logit_alpha, log_beta = best_params
    mu = float(np.exp(log_mu))
    alpha = float(1.0 / (1.0 + np.exp(-logit_alpha)))
    beta = float(np.exp(log_beta))

    return HawkesFit(mu=mu, alpha=alpha, beta=beta, loglik=best_ll, converged=best_converged)


# ---------------------------------------------------------------------------
# Sum-of-exponentials MLE: K parallel recursions + the same Nelder-Mead,
# extended to dimension 1+2K. See docs/research/02-hawkes-processes.md §4
# pitfall 3: "Fit sums of exponentials spanning decades of timescales; check
# n̂ stability" — the point of this section is to make that check possible.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiExpFit:
    """Result of `fit_hawkes_multiexp`.

    `converged` mirrors `HawkesFit.converged`'s caveat: it is True iff the
    winning multi-start's Nelder-Mead simplex satisfied the tol=1e-6
    f-spread stopping criterion, which says only that the optimizer stopped
    improving locally -- NOT that `alphas`/`betas` are well identified. This
    is a weaker guarantee at K>=2 than at K=1: a K=3 fit can (and, on this
    module's own planted-kernel test data, does) report `converged=True`
    while two components sit on a flat ridge with near-duplicate betas
    (e.g. betas=(0.194, 4.890, 4.890) splitting one true component's mass
    across a degenerate pair). `n = sum(alphas)` is generally far better
    identified than the individual components at high K; see
    `fit_hawkes_multiexp`'s docstring for the full discussion.
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

    Softmax-with-a-slack-slot: append an implicit 0-logit "non-branching"
    slot to the K free logits, softmax over all K+1 slots, then drop the
    slack slot's probability. This gives K non-negative numbers that sum to
    strictly less than 1 (the slack slot always retains positive mass since
    exp(0)=1 > 0 in the softmax denominator), for any finite logits — so the
    optimizer can never wander into the explosive/non-stationary n>=1
    region, without a boundary penalty. Equivalent in spirit to the
    single-exponential case's logistic-into-(0,1) transform, generalized to
    K components sharing one probability budget.
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

    ll = hawkes_multiexp_loglik(times, t_end, mu, alphas, betas)
    if not np.isfinite(ll):
        return 1e18
    return -ll


def fit_hawkes_multiexp(
    times: np.ndarray, t_end: float, K: int, betas_init: np.ndarray | None = None
) -> MultiExpFit:
    """MLE of (mu, alphas, betas) for a K-component sum-of-exponentials Hawkes kernel.

    Optimizes over 1+2K unconstrained parameters (log mu, K alpha-logits
    mapped through `_alphas_from_logits` so Σalpha_k < 1 always holds, K
    log-betas) using the same hand-rolled Nelder-Mead as `fit_hawkes_exp`,
    multi-started from `betas_init` (default: log-spaced across decades —
    0.1, 1, 10, ... per unit time, extended/truncated to K values — so the
    mixture is initialized to actually span timescales rather than
    collapsing to K copies of the same decay rate) combined with a few
    perturbed alpha/mu starting points.

    For K=1 this must (and, per `test_multiexp_k1_matches_fit_hawkes_exp`,
    does) reproduce `fit_hawkes_exp` on the same data: with one component the
    alpha-logit softmax-with-slack-slot reduces exactly to a logistic map
    into (0,1), i.e. the same reparameterization `fit_hawkes_exp` uses, and
    the log-likelihoods (`hawkes_multiexp_loglik` vs `hawkes_loglik`) are the
    same expression with one term, so both optimizers search the identical
    surface. In practice two independent Nelder-Mead runs (different simplex
    paths, including different multi-start beta seeds) land within ~1e-7 of
    each other in log-likelihood and mu/alpha, and ~1e-5 in beta (the
    flattest direction near the optimum) — see
    `test_multiexp_k1_matches_fit_hawkes_exp`'s measured diffs and asserted
    tolerances (loglik/mu/alpha at 1e-5, beta at 1e-4). This is the floor
    set by each optimizer's own tol=1e-6 f-spread stopping criterion, not a
    discrepancy between the two code paths.

    THE POINT OF THIS FUNCTION (docs/research/02-hawkes-processes.md §4
    pitfall 3): a single exponential is too short-memoried to represent a
    long-memory/power-law-like true kernel, so a K=1 fit systematically
    underestimates n = Σalpha_k. Increasing K lets the mixture spread mass
    across widely-separated timescales and recover more of the long-lag
    kernel weight, pulling n̂ up toward the true value. Re-fitting the same
    data at K=1,2,3 and reporting how n̂ MOVES across K (see
    `branching_ratio_sensitivity`) is therefore the intended diagnostic on
    real data, not a nuisance to average away.

    KNOWN IDENTIFIABILITY WEAKNESS AT LARGE K: once K exceeds the number of
    timescales actually resolvable from the data's sample size and window,
    components become interchangeable/degenerate (two components can trade
    off alpha and beta against each other while barely changing the
    likelihood, similar in spirit to the near-critical mu/alpha ridge
    documented on `fit_hawkes_exp`). Individual `alphas`/`betas` at K=3 and
    above should be treated as much less identified than their sum n; this
    is why `branching_ratio_sensitivity`'s docs recommend reporting n̂(K),
    not the per-component parameters, as the headline diagnostic.

    `converged` HAS THE SAME CAVEAT AS `fit_hawkes_exp`'s: it reflects ONLY
    that the winning start's Nelder-Mead simplex stopped spreading out in
    log-likelihood (the tol=1e-6 f-spread criterion), NOT that the
    parameters are well identified. This is *more* likely to bite at K>=2
    than in the single-exponential case: a K=3 fit can report
    `converged=True` while sitting on a degenerate ridge where two
    components have nearly duplicate betas and one carries almost all the
    weight -- e.g. `test_multiexp_k3_on_two_exp_data_does_not_blow_up`'s own
    planted-data K=3 fit converges to alphas=(0.348, 0.007, 0.245) with
    betas=(0.194, 4.890, 4.890), a duplicate-beta pair splitting what a
    correctly-specified K=2 fit represents as one component. The SUM n is
    still trustworthy there (it matches K=2 to three decimal places); the
    individual per-component (alpha, beta) values are not, regardless of
    what `converged` says.

    CONFOUND WARNING — BASELINE NON-STATIONARITY CAN MIMIC LONG MEMORY: a
    K=1 -> K=2 rise in n̂ together with a slow (small beta) second
    component is the SAME numerical signature produced by two completely
    different underlying causes, and n̂(K) alone cannot distinguish them:
      1. Genuine long-memory kernel (the motivating case above): the extra
         slow component recovers real, slowly-decaying self-excitation mass
         a K=1 fit truncated.
      2. Residual baseline non-stationarity (Filimonov & Sornette 2015,
         also documented on `simulate_seasonal_hawkes_exp` /
         `branching_count_variance`): if mu(t) is not actually constant
         (imperfect deseasonalization, a regime change, a slow intraday
         drift) but the model assumes constant mu, the misspecified
         exponential-kernel MLE can "explain" the baseline's slow swings by
         inventing a spurious slow self-exciting component instead -- the
         mixture fits the drift, not real branching. This is the exact same
         family of failure as the regime-switching trap already documented
         on `branching_count_variance` and exercised in
         `test_regime_switching_produces_spurious_endogeneity`, now shown to
         also fool the MULTI-exponential MLE, not just the single-exponential
         one or the count-variance estimator.
         `test_seasonal_baseline_confound_mimics_long_memory` demonstrates
         this concretely: a TRUE single-exponential Hawkes process (n=0.4,
         beta=2.0, no long memory at all) with a piecewise-constant ±30%
         baseline wobble produces n̂1=0.46 -> n̂2=0.83 with a spurious
         beta≈0.02 "slow" component, the same qualitative signature as the
         genuine-long-memory headline test.

    PER-SYMBOL OBSERVABLE TO REPORT (so this can be diagnosed on real data,
    not just guessed at): for any slow component that appears when K
    increases, report its timescale 1/beta_slow next to (a) the
    deseasonalization bin width used to build mu(t) and (b) the fit-window
    length. If 1/beta_slow is comparable to or larger than the
    deseasonalization bin width, or is a large fraction of the fit-window
    length, the "slow component" is a prime suspect for absorbed baseline
    drift rather than real long-memory self-excitation -- a genuine
    long-memory timescale should be well inside the fit window and
    unrelated to the deseasonalization binning choice.

    THE CONTROL: re-fit K=1 with a block-wise PIECEWISE-CONSTANT mu(t)
    (one free mu per block, e.g. matching the deseasonalization bins or the
    non-stationarity block length under suspicion) instead of a single
    constant mu, then re-run the K=1 vs K=2 comparison. If the spurious slow
    component VANISHES once the baseline is allowed to vary block-wise, the
    original K=1->K=2 jump was baseline drift, not kernel misspecification.
    If it persists even with a flexible block-wise baseline soaking up the
    non-stationarity, that is evidence for genuine long memory. This module
    does not yet implement a block-wise-mu variant of `fit_hawkes_multiexp`
    (see `simulate_seasonal_hawkes_exp` for the seasonal SIMULATOR
    counterpart) -- running this control is a prerequisite for trusting any
    single-symbol K=1->K=2 jump as evidence of long memory, not an optional
    nicety.
    """
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

    # Multi-start: vary the total branching-ratio budget, mu scale, AND a
    # multiplicative shift on betas_init (0.5x, 2x) so the two starts don't
    # search from identical beta seeds -- different starts don't collapse
    # onto identical local optima. Two starts (rather than fit_hawkes_exp's
    # five) keep runtime bounded as K grows -- each start already costs O(K)
    # recursions per Nelder-Mead evaluation over a 1+2K-dimensional simplex,
    # and betas_init already does most of the work of spanning timescales,
    # so the marginal value of extra starts is lower here than in the
    # single-exponential case. max_iter=600 (vs fit_hawkes_exp's 500) gives
    # the larger simplex (dim+1 = 2+2K vertices) enough iterations to
    # actually reach the tol=1e-6 stopping criterion at K=3 rather than
    # exhausting the iteration budget mid-search.
    total_n_starts = [0.5, 0.25]
    mu_fracs = [0.5, 0.7]
    beta_shifts = [0.5, 2.0]
    max_iter = 600

    best_params: np.ndarray | None = None
    best_ll = -np.inf
    best_converged = False

    for total_n0, mu_frac, beta_shift in zip(total_n_starts, mu_fracs, beta_shifts, strict=True):
        mu0 = mean_rate * mu_frac
        # Split total_n0 equally across K components as the starting point;
        # the alpha-logit softmax-with-slack-slot reaches this via equal
        # logits summing (with the implicit 0 slack logit) to total_n0.
        equal_share = total_n0 / K
        # Solve for a common logit z such that K*exp(z) / (K*exp(z) + 1) = total_n0
        # => exp(z) = total_n0 / (K*(1-total_n0)) => z = log(...).
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

    This is the panel-level diagnostic docs/research/02-hawkes-processes.md
    §4 calls for: "Fit sums of exponentials spanning decades of timescales;
    check n̂ stability." Rather than picking one K and reporting a single n̂,
    the intended use is to inspect `{K: fit.n for K, fit in result.items()}`
    and report the SPREAD across K, not just the K=3 (or whichever) point
    estimate — a large jump from K=1 to K=2 that then stabilizes at K=3 is
    itself the finding (evidence the single-exponential branching ratio was
    biased low by kernel misspecification, per the project's headline
    41/41-symbol disagreement between the exp-kernel MLE and the model-free
    count-variance estimator). A n̂(K) that keeps climbing without
    stabilizing, or that becomes unstable/non-converged at higher K, is
    itself informative (see `fit_hawkes_multiexp`'s identifiability caveat)
    and should be reported rather than papered over by picking the
    best-converged K.

    CONFOUND WARNING (see `fit_hawkes_multiexp`'s docstring for full detail):
    a rising n̂(K) with a slow (small beta) component appearing at higher K
    is NOT on its own evidence of long memory -- residual baseline
    non-stationarity (imperfect deseasonalization, regime changes, slow
    intraday drift) produces the identical signature, because a
    misspecified constant-mu fit can "explain" slow baseline swings with a
    spurious slow self-exciting component instead
    (`test_seasonal_baseline_confound_mimics_long_memory` demonstrates this
    on a TRUE single-exponential process with no long memory at all). Before
    reporting a symbol's K=1->K=2 jump as evidence of long-memory
    self-excitation:
      1. Report the slow component's timescale 1/beta_slow next to the
         deseasonalization bin width and the fit-window length -- a
         timescale comparable to either is a red flag for absorbed drift
         rather than genuine long memory.
      2. Run the control: re-fit K=1 with a block-wise piecewise-constant
         mu(t) instead of a single constant mu. If the spurious slow
         component vanishes under that control, the jump was baseline
         drift, not kernel misspecification.
    """
    return {K: fit_hawkes_multiexp(times, t_end, K) for K in Ks}


def spurious_delta21_null(
    n_events_per_window: int, mu: float, alpha: float, beta: float, n_sims: int, seed: int
) -> np.ndarray:
    """Null distribution of Delta21 = n_hat_2 - n_hat_1 under a TRUE single-exp kernel.

    WHY THIS EXISTS: `fit_hawkes_multiexp` at K=2 has two more free parameters
    than the K=1 fit and can never do worse in-sample log-likelihood -- on
    FINITE data it will generally do strictly better, by using its extra
    component to absorb ordinary sampling noise in the event-time gaps
    rather than any real second timescale. Concretely (see the investigation
    behind this function, reproduced against `tests/analyses/test_q6b.py`'s
    ONEEXPUSDT fixture: mu=1.0, alpha=0.4, beta=2.0, seed=7, business-time
    windows of ~16.6k events each), a K=2 fit on one such window converged to
    betas=(0.021, 0.479) with a genuine log-likelihood improvement of
    ~11 nats over K=1 for 2 extra parameters -- a real gain by naive
    likelihood-ratio standards, yet the generative process has no second
    timescale at all. The "slow" component is not a local-optimum fluke in
    general (a wider `betas_init` search can still land on it); it is the
    K=2 model's extra flexibility fitting sampling noise in a finite sample.
    This means `n_hat_2` carries an intrinsic upward finite-sample bias
    relative to `n_hat_1` even when K=1 is exactly correct, and Delta21 must
    be judged against the SIZE of that bias at the relevant sample size, not
    against a fixed tolerance chosen without reference to it.

    This function simulates `n_sims` independent single-exponential Hawkes
    processes with the given (mu, alpha, beta), each sized (via `t_end`) to
    land close to `n_events_per_window` events, fits both K=1 and K=2 via
    `fit_hawkes_multiexp` on each, and returns the array of per-simulation
    Delta21 = n_hat_2 - n_hat_1. This is the null distribution a real
    symbol's observed Delta21 should be compared against: a real Delta21
    that does not exceed (e.g.) this null's 90th percentile is "within
    finite-sample null" -- i.e. no more than what a well-specified K=1
    process of the same sample size would produce anyway -- rather than
    evidence of genuine long-memory kernel structure.

    THE BIAS SHRINKS WITH SAMPLE SIZE, AND MUST BE CALIBRATED AT THE PANEL'S
    ACTUAL PER-WINDOW EVENT COUNT: more events per window pin down the K=1
    fit's residual gaps more tightly, leaving less unexplained noise for a
    second component to absorb, so the median null Delta21 falls as
    `n_events_per_window` grows (measured: median null Delta21 ~0.003-0.02 at
    ~10k events per window vs. a few times smaller at ~40k, over independent
    seeds -- exact values are noisy with only a handful of simulations, which
    is why `n_sims` should be large enough for a stable percentile in
    production use). Since Q6b caps any single window's fit at
    `MAX_FIT_EVENTS=250_000` events, the null must be simulated at the
    PANEL's actual median per-window event count (post-cap), not at an
    arbitrary or worst-case size -- calibrating at a smaller size than the
    real windows overstates the null (too permissive would be the opposite
    error: calibrating at a larger size understates it and makes genuine
    long-memory harder to detect).

    `t_end` per simulation is derived from `n_events_per_window` via the
    exponential-kernel process's theoretical mean rate
    `mu / (1 - alpha)` events per unit time (exact for a stationary Hawkes
    process: each immigrant plus its full branching-process descendant tree
    contributes `1/(1-alpha)` events in expectation), so the realized event
    count lands close to (not exactly at, since simulation is stochastic)
    the requested size.
    """
    if n_events_per_window <= 0:
        raise ValueError("n_events_per_window must be positive")
    if n_sims <= 0:
        raise ValueError("n_sims must be positive")

    mean_rate = mu / (1.0 - alpha)
    t_end = n_events_per_window / mean_rate

    rng = np.random.default_rng(seed)
    # Draw independent per-simulation seeds from this function's own seed so
    # callers get reproducible, non-correlated draws without exposing an
    # array of seeds in the signature.
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
    `n_blocks`); `alpha`/`beta` are the single-exponential kernel's
    branching ratio and decay rate, shared across all blocks. `n` is an
    alias for `alpha` (the branching ratio, matching `HawkesFit`/
    `MultiExpFit`'s convention of exposing `n` alongside the raw kernel
    parameter it equals for a single component).

    `converged` carries the SAME caveat as `HawkesFit.converged` and
    `MultiExpFit.converged`: it reflects only that the winning multi-start's
    Nelder-Mead simplex stopped spreading out in log-likelihood (tol=1e-6),
    not that (mus, alpha, beta) are individually well identified. This is
    *more* exposed to the near-critical mu/alpha ridge than the single-mu
    case, since a block with few events can trade its own mu_b off against
    alpha along a shallow direction; treat individual `mus` entries as
    noisier than the shared `alpha`.
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
    """Exact log-likelihood for a single-exponential kernel with a block-wise
    constant baseline mu_b(t) = mus[b(t)], b(t) the index of t's equal-width
    time block.

    loglik = Σ_i log(mu_{b(t_i)} + alpha*beta*R_i)
             - Σ_b mu_b*|block_b|
             - alpha*Σ_i (1 - exp(-beta*(T-t_i)))

    The excitation recursion R_i and the excitation compensator term are
    exactly `hawkes_loglik`'s (the kernel does not know about blocks at
    all — only the baseline is block-wise). The baseline compensator
    Σ_b mu_b*|block_b| replaces the single mu*T term: since blocks are
    disjoint and cover [0, T] exactly, this is ∫_0^T mu(t) dt for the
    piecewise-constant mu(t).
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

    ll = hawkes_piecewise_mu_loglik(times, t_end, mus, alpha, beta, n_blocks)
    if not np.isfinite(ll):
        return 1e18
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
    process with a block-wise constant baseline: the CONTROL described in
    `fit_hawkes_multiexp`'s "THE CONTROL" section. It re-fits K=1 but lets the
    baseline take one free value per equal-width time block of [0, t_end]
    instead of a single constant mu. See `baseline_drift_control` for how it
    is paired with the K=1 and K=2 fits.

    Time-axis assumption: event times lie in [0, t_end]; block b covers
    [b*t_end/B, (b+1)*t_end/B) (the last block is closed at t_end).

    Optimizes over B+2 unconstrained parameters (log mu_1..log mu_B, logit
    alpha, log beta) with the module's hand-rolled Nelder-Mead. Two starts:
      1. the constant-mu K=1 solution (`fit_hawkes_exp`; every mu_b = mu-hat,
         alpha-hat, beta-hat). Because the constant-mu model is nested in
         this one and Nelder-Mead never returns a point worse than its
         starting vertex, `loglik >= fit_k1.loglik` (up to floating-point
         noise), which is what the likelihood-ratio verdict in
         `baseline_drift_control` relies on.
      2. the empirical per-block event rates scaled by (1 - alpha-hat), with
         the K=1 alpha-hat, beta-hat, so the baseline starts block-shaped.
    The better of the two is returned. Pass `fit_k1` to reuse an existing
    K=1 fit instead of recomputing it.

    `n_blocks` is capped at `MAX_PIECEWISE_BLOCKS` (12) because every block
    adds a dimension to the simplex search and, at the sample sizes this
    module targets, too many blocks leave too few events per block to
    identify mu_b.

    CAVEAT on `converged`: same as `HawkesFit.converged`; it says only that
    the winning simplex stopped spreading in log-likelihood. It does not
    certify that every mu_b is individually identified (a block with few
    events has a nearly flat likelihood in its own mu_b), and with up to 14
    dimensions the optimizer may also stop at max_iter; treat per-block mus
    as noisier than the shared alpha.
    """
    if t_end <= 0.0:
        raise ValueError("t_end must be positive")
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
    # Empirical per-block rate, floored well above zero so an empty block
    # still gets a sane (small but positive) starting mu instead of log(0).
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
    candidate for genuine long memory.

    Event times are assumed to lie in [0, t_end]. `fit_k1` / `fit_k2` may be
    passed to reuse precomputed fits (they must be fits of the same `times`
    and `t_end`).

    Returned keys: n_k1, n_k2, n_k1_piecewise, slow_beta_k2 (smaller beta of
    the K=2 fit), dll_pw = piecewise.loglik - fit_k1.loglik, dll_k2 =
    fit_k2.loglik - fit_k1.loglik, dll_threshold = chi2_0.95(n_blocks-1)/2,
    and verdict (see `_drift_verdict` for the rule).

    The verdict is a HEURISTIC likelihood-ratio screen, not a formal test:
    the K=2 and block-wise fits are found by Nelder-Mead and may not reach
    the global optimum, the chi-square calibration assumes standard
    likelihood-ratio asymptotics that Hawkes likelihoods only approximately
    satisfy, and the "at least half of dll_k2" cut-off is a convention, not
    derived. When the K=1 model is misspecified (genuine long memory), block
    counts are more dispersed than K=1 predicts, which inflates dll_pw. That
    inflation can push a genuinely long-memory process to "inconclusive"
    rather than "long_memory_candidate", OR across the drift threshold into
    "drift". A "drift" label therefore means only that the block baseline
    recovers at least half of the K=2 gain; it does not exclude long memory.

    RESOLUTION LIMIT: a block-wise constant baseline can absorb only drift
    that is SLOWER than the block width t_end / n_blocks. Faster baseline
    oscillations average out inside each block and look like stationary
    noise, so they remain indistinguishable from long memory and will be
    labelled 'long_memory_candidate'. The caller must choose n_blocks
    (<= MAX_PIECEWISE_BLOCKS) so that the block width is below the suspected
    drift timescale; a 'long_memory_candidate' verdict carries no meaning if
    that condition fails.
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

    For a stationary Hawkes process, as the window W grows much larger
    than the kernel timescale, var(N_W)/mean(N_W) -> 1/(1-n)^2, giving
        n_hat = 1 - sqrt(mean(N_W) / var(N_W)).

    This requires windows W much larger than the kernel timescale
    (1/beta for the exponential kernel) — the large-window asymptotic is
    what makes the estimator "see" the amplification from clustering
    rather than just Poisson counting noise; too-small windows bias
    n_hat toward 0 (docs/research/02 §4: "short windows truncate long-memory
    kernels and bias n̂ down"). No kernel shape is assumed, which is the
    estimator's advantage (and, per the regime-switching trap test in
    tests/estimators/test_hawkes.py, also its weakness: it cannot
    distinguish real self-excitation from non-stationary baseline rate).

    Raises ValueError if fewer than 20 non-overlapping windows fit in
    [0, t_end], if window is so small it would require an unreasonable
    number of bins (>10^9 — see max_windows derivation below), or if the
    count variance is zero (degenerate/regular spacing), since none of
    these leave the estimator statistically meaningful.
    """
    if window <= 0.0:
        raise ValueError("window must be positive")

    n_windows = int(t_end // window)
    if n_windows < 20:
        raise ValueError(
            f"need at least 20 non-overlapping windows, got {n_windows} "
            f"(t_end={t_end}, window={window})"
        )
    # `edges = np.arange(n_windows + 1) * window` below allocates one
    # int64 (8 bytes) per bin edge. At the cap, 1e9 edges * 8 bytes = 8GB
    # — a large but single, bounded, non-swap-inducing allocation on a
    # modern dev/CI machine. This still guards the genuine pathology (a
    # window many orders of magnitude too small for t_end — e.g. window=
    # 1e-9 with t_end=1e4 would ask for ~1e13 edges, ~80TB, the case that
    # motivated this cap in the first place) while comfortably allowing
    # legitimate sub-millisecond windows: 1e9 windows at window=1ms spans
    # ~1e6s (~11.5 days) of t_end, more than enough for a multi-day
    # trading-time analysis. Widen further only with an explicit reason —
    # 8GB is already a lot to ask a laptop for from a single call.
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
