"""
Survival analysis need model for SharedSpace.
Uses Weibull distribution via lifelines to handle both:
1. Completed inter-purchase intervals (uncensored events: E=1)
2. Current open interval (right-censored: E=0, item has survived until now)

Computes conditional hazard and probability:
    P(depleted by t + delta_t | survived up to t) = 1 - S(t + delta_t) / S(t)
"""
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd
import numpy as np
from lifelines import WeibullFitter


@dataclass
class SurvivalDataset:
    """
    Survival durations and event indicators.
    - durations: List of time intervals (in days).
    - event_observed: 1 for completed purchases, 0 for right-censored open interval.
    """
    durations: List[float]
    event_observed: List[int]


def prepare_survival_data(
    historical_intervals: List[float],
    current_elapsed_days: float
) -> SurvivalDataset:
    """
    Construct dataset for survival fitting:
    - Every historical interval between two actual purchases is an uncensored event (E=1).
    - The current elapsed time since the last purchase is right-censored (E=0):
      we know the item survived AT LEAST current_elapsed_days without depletion.
    """
    durations: List[float] = []
    events: List[int] = []

    # Historical completed intervals
    for interval in historical_intervals:
        if interval > 0:
            durations.append(float(interval))
            events.append(1)

    # Current open right-censored interval
    if current_elapsed_days > 0:
        durations.append(float(current_elapsed_days))
        events.append(0)  # Censored: we haven't bought yet!

    return SurvivalDataset(durations=durations, event_observed=events)


def fit_weibull_model(
    dataset: SurvivalDataset,
    fallback_mean: float = 3.0
) -> WeibullFitter:
    """
    Fit a parametric Weibull survival model:
        Survival function: S(t) = exp(-(t / lambda)^rho)
        Hazard function:   h(t) = (rho / lambda) * (t / lambda)^(rho - 1)
        
    If insufficient completed events exist (< 2), initializes a synthetic
    prior Weibull model centered on fallback_mean.
    """
    wf = WeibullFitter()
    completed_events_count = sum(dataset.event_observed)

    # If we have at least 2 completed events, fit directly via Maximum Likelihood
    if completed_events_count >= 2:
        try:
            wf.fit(
                durations=dataset.durations,
                event_observed=dataset.event_observed
            )
            return wf
        except Exception:
            pass  # Fall back to prior on optimization convergence issues

    # Prior synthetic dataset for weak initialization
    prior_durations = [fallback_mean * 0.85, fallback_mean, fallback_mean * 1.15]
    prior_events = [1, 1, 1]
    
    # Merge with any available censored elapsed time
    if dataset.durations and dataset.event_observed[-1] == 0:
        prior_durations.append(dataset.durations[-1])
        prior_events.append(0)

    wf.fit(durations=prior_durations, event_observed=prior_events)
    return wf


def p_need_survival(
    elapsed_days: float,
    declared_interval_days: float,
    historical_intervals: List[float],
    prediction_window_hours: float = 12.0
) -> float:
    """
    Calculate P(need within next prediction window | survived up to elapsed_days):
    
        P(T <= t + dt | T > t) = 1 - S(t + dt) / S(t)
        
    Where S(t) is the Weibull survival function.
    """
    if declared_interval_days <= 0:
        raise ValueError("Declared interval must be strictly positive.")

    if elapsed_days <= 0:
        return 0.0

    # 1. Prepare survival data including current right-censored elapsed time
    data = prepare_survival_data(
        historical_intervals=historical_intervals,
        current_elapsed_days=elapsed_days
    )

    # 2. Fit Weibull model with right-censoring
    wf = fit_weibull_model(data, fallback_mean=declared_interval_days)

    # 3. Compute conditional probability over lookahead window dt
    dt_days = prediction_window_hours / 24.0
    t_now = elapsed_days
    t_future = elapsed_days + dt_days

    # Survival function S(t) values
    s_now = float(wf.survival_function_at_times(t_now).values[0])
    s_future = float(wf.survival_function_at_times(t_future).values[0])

    if s_now <= 1e-6:
        return 1.0  # Item is essentially guaranteed to be empty

    # Conditional probability: 1 - S(t + dt) / S(t)
    conditional_prob = 1.0 - (s_future / s_now)
    return float(np.clip(conditional_prob, 0.0, 1.0))

