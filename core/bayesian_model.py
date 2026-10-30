"""
Bayesian interval model for SharedSpace.
Uses a Normal-Inverse-Gamma conjugate prior on log-transformed purchase intervals:
    Y = ln(T) ~ Normal(mu, sigma^2)
    (mu, sigma^2) ~ Normal-Inverse-Gamma(mu_0, kappa_0, alpha_0, beta_0)

Computes posterior predictive distribution and P(need now | elapsed_days).
"""
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
from scipy import stats


@dataclass
class NIGPrior:
    """
    Hyperparameters for the Normal-Inverse-Gamma (NIG) prior:
    - mu_0: Prior mean of log-intervals
    - kappa_0: Pseudo-observations count measuring confidence in mu_0
    - alpha_0: Shape parameter of the Inverse-Gamma variance prior
    - beta_0: Scale parameter of the Inverse-Gamma variance prior
    """
    mu_0: float
    kappa_0: float
    alpha_0: float
    beta_0: float


@dataclass
class NIGPosterior:
    """
    Updated posterior hyperparameters after observing n empirical log-intervals.
    """
    mu_n: float
    kappa_n: float
    alpha_n: float
    beta_n: float
    n: int


def build_prior_from_declared_interval(
    declared_interval_days: float,
    prior_confidence: float = 2.0,
    assumed_relative_std: float = 0.35
) -> NIGPrior:
    """
    Construct a weakly informative NIG prior centered on the declared schedule:
    - Expected log-interval: mu_0 = ln(declared_interval)
    - kappa_0: Weight of the prior (e.g. 2 pseudo-purchases)
    - Variance of log-normal approx: sigma_0^2 ≈ ln(1 + (std/mean)^2)
    """
    if declared_interval_days <= 0:
        raise ValueError("Declared interval must be strictly positive.")

    mu_0 = float(np.log(declared_interval_days))
    kappa_0 = float(max(0.5, prior_confidence))

    # Log-normal variance approximation: sigma_log^2 = ln(1 + (CV)^2)
    var_log = float(np.log(1.0 + (assumed_relative_std ** 2)))
    
    # We set alpha_0 = 2.0 (so prior variance exists, mean = beta_0 / (alpha_0 - 1))
    alpha_0 = 2.0
    beta_0 = var_log * (alpha_0 - 1.0)

    return NIGPrior(mu_0=mu_0, kappa_0=kappa_0, alpha_0=alpha_0, beta_0=beta_0)


def update_nig_posterior(prior: NIGPrior, intervals: List[float]) -> NIGPosterior:
    """
    Perform exact analytical Bayesian conjugate updating using observed intervals.
    Transforms data to Y = ln(T).
    """
    valid_intervals = [x for x in intervals if x > 0]
    n = len(valid_intervals)

    if n == 0:
        return NIGPosterior(
            mu_n=prior.mu_0,
            kappa_n=prior.kappa_0,
            alpha_n=prior.alpha_0,
            beta_n=prior.beta_0,
            n=0
        )

    y = np.log(valid_intervals)
    y_bar = float(np.mean(y))
    ss_y = float(np.sum((y - y_bar) ** 2)) if n > 1 else 0.0

    # Exact conjugate update formulas
    kappa_n = prior.kappa_0 + n
    mu_n = (prior.kappa_0 * prior.mu_0 + n * y_bar) / kappa_n
    alpha_n = prior.alpha_0 + n / 2.0
    
    extra_var_term = (prior.kappa_0 * n * (y_bar - prior.mu_0) ** 2) / (2.0 * kappa_n)
    beta_n = prior.beta_0 + 0.5 * ss_y + extra_var_term

    return NIGPosterior(
        mu_n=float(mu_n),
        kappa_n=float(kappa_n),
        alpha_n=float(alpha_n),
        beta_n=float(beta_n),
        n=n
    )


def posterior_predictive_student_t(posterior: NIGPosterior) -> Tuple[float, float, float]:
    """
    Return the parameters of the Student's t posterior predictive distribution for Y = ln(T):
        Y_new ~ Student_t(df=2*alpha_n, loc=mu_n, scale=sqrt(beta_n*(kappa_n+1)/(alpha_n*kappa_n)))
    Returns:
        (df, loc, scale)
    """
    df = 2.0 * posterior.alpha_n
    scale_sq = (posterior.beta_n * (posterior.kappa_n + 1.0)) / (posterior.alpha_n * posterior.kappa_n)
    scale = float(np.sqrt(scale_sq))
    loc = posterior.mu_n
    return df, loc, scale


def p_need_bayesian(
    elapsed_days: float,
    declared_interval_days: float,
    historical_intervals: List[float],
    prior_confidence: float = 2.0
) -> float:
    """
    Calculate P(need now) = P(T <= elapsed_days) under the Bayesian predictive model:
    
        P(T <= elapsed) = P(ln(T) <= ln(elapsed)) = F_t(ln(elapsed))
        
    Where F_t is the CDF of the Student's t posterior predictive distribution.
    """
    if declared_interval_days <= 0:
        raise ValueError("Declared interval must be strictly positive.")

    if elapsed_days <= 0:
        return 0.0

    # 1. Build prior from declared schedule
    prior = build_prior_from_declared_interval(
        declared_interval_days=declared_interval_days,
        prior_confidence=prior_confidence
    )

    # 2. Update with observed history
    posterior = update_nig_posterior(prior, historical_intervals)

    # 3. Posterior predictive Student's t distribution
    df, loc, scale = posterior_predictive_student_t(posterior)

    # 4. Compute CDF: P(Y <= ln(elapsed_days))
    log_elapsed = float(np.log(elapsed_days))
    prob = float(stats.t.cdf(log_elapsed, df=df, loc=loc, scale=scale))

    return float(np.clip(prob, 0.0, 1.0))

