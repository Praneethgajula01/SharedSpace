"""
Habit drift detection for SharedSpace using a Two-Sided CUSUM (Cumulative Sum) filter.
Monitors standardized residuals of consecutive purchase intervals:
- Detects acceleration (e.g. exams: items finished much faster than usual)
- Detects slowdown (e.g. vacations: items lasting much longer than usual)

When a drift is signaled, the system resets priors or adjusts confidence.
"""
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np


@dataclass
class CUSUMState:
    """
    Cumulative Sum tracking state:
    - s_pos: Positive cumulative sum (detects interval shrinkage / acceleration)
    - s_neg: Negative cumulative sum (detects interval expansion / slowdown)
    - drift_detected: True if either cumulative sum crossed threshold h
    - drift_type: 'ACCELERATION', 'SLOWDOWN', or None
    """
    s_pos: float = 0.0
    s_neg: float = 0.0
    drift_detected: bool = False
    drift_type: Optional[str] = None


class CUSUMDriftDetector:
    """
    Two-Sided Page's CUSUM control chart:
    Monitors deviations from an expected baseline mean mu_0 and standard deviation sigma_0.
    
    Standardized residual:
        z_t = (x_t - mu_0) / sigma_0
        
    Updates:
        S_pos[t] = max(0, S_pos[t-1] - (z_t + k))   # Checks if intervals got shorter (x < mu)
        S_neg[t] = max(0, S_neg[t-1] + (z_t - k))   # Checks if intervals got longer (x > mu)
        
    Alarm triggered if S_pos >= h or S_neg >= h.
    """
    def __init__(
        self,
        baseline_mean: float,
        baseline_std: float,
        allowance_k: float = 0.5,
        decision_threshold_h: float = 4.0
    ):
        if baseline_mean <= 0 or baseline_std <= 0:
            raise ValueError("Baseline mean and std must be strictly positive.")

        self.mu_0 = float(baseline_mean)
        self.sigma_0 = float(baseline_std)
        self.k = float(allowance_k)  # Slack / slack allowance (typically 0.5 sigma)
        self.h = float(decision_threshold_h)  # Decision boundary (typically 4.0 to 5.0)

        self.s_pos: float = 0.0
        self.s_neg: float = 0.0

    def step(self, observed_interval: float) -> CUSUMState:
        """
        Process a new completed inter-purchase interval x_t.
        Returns the updated CUSUMState.
        """
        if observed_interval <= 0:
            raise ValueError("Observed interval must be strictly positive.")

        # Standardized residual
        z = (observed_interval - self.mu_0) / self.sigma_0

        # Acceleration detection: observed intervals are smaller than baseline (z < 0)
        # We accumulate -z minus slack k
        self.s_pos = max(0.0, self.s_pos + (-z - self.k))

        # Slowdown detection: observed intervals are larger than baseline (z > 0)
        # We accumulate +z minus slack k
        self.s_neg = max(0.0, self.s_neg + (z - self.k))

        drift_detected = False
        drift_type = None

        if self.s_pos >= self.h:
            drift_detected = True
            drift_type = "ACCELERATION"
        elif self.s_neg >= self.h:
            drift_detected = True
            drift_type = "SLOWDOWN"

        return CUSUMState(
            s_pos=float(self.s_pos),
            s_neg=float(self.s_neg),
            drift_detected=drift_detected,
            drift_type=drift_type
        )

    def reset(self, new_mean: Optional[float] = None, new_std: Optional[float] = None) -> None:
        """Reset CUSUM statistics after an alarm is handled or acknowledged."""
        self.s_pos = 0.0
        self.s_neg = 0.0
        if new_mean is not None and new_mean > 0:
            self.mu_0 = float(new_mean)
        if new_std is not None and new_std > 0:
            self.sigma_0 = float(new_std)

