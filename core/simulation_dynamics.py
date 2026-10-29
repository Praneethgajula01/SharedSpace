"""
Advanced simulation dynamics for SharedSpace:
- Habit drift (sudden or gradual shifts in consumption patterns)
- Weekend & day-of-week demand multipliers
- Ground-truth probabilistic user responses (logistic curve based on actual stock state)
"""
from datetime import datetime
from typing import Tuple, Optional, List
import numpy as np

from core.db import User


def get_drifted_mean_interval(
    baseline_mean: float,
    current_day: float,
    drift_start_day: Optional[float] = None,
    drift_factor: float = 1.0
) -> float:
    """
    Simulates a shift in consumption habits (e.g. exams, new flatmate, season change).
    If current_day >= drift_start_day, the mean interval scales by drift_factor.
    
    Example:
        baseline = 3.0 days, drift_factor = 0.5 (drinking coffee twice as fast)
        After day 20, mean becomes 1.5 days.
    """
    if baseline_mean <= 0:
        raise ValueError("Baseline mean must be strictly positive.")

    if drift_start_day is not None and current_day >= drift_start_day:
        return max(0.2, baseline_mean * drift_factor)
    return baseline_mean


def get_day_of_week_multiplier(timestamp: datetime, weekend_acceleration: float = 0.85) -> float:
    """
    Adjusts consumption rate depending on day of week.
    Hostellers often consume snacks/milk faster on weekends (Saturday/Sunday).
    A multiplier < 1.0 indicates faster replenishment (shorter interval).
    """
    # 5 = Saturday, 6 = Sunday in Python datetime.weekday()
    if timestamp.weekday() in (5, 6):
        return weekend_acceleration
    return 1.0


def compute_true_need_probability(
    elapsed_days: float,
    true_interval: float,
    sensitivity: float = 3.5
) -> float:
    """
    Ground-truth probability that the item is physically depleted in the flat.
    Uses a standard logistic (sigmoid) response curve centered at true_interval:
    
        z = (elapsed_days - true_interval) / true_interval
        P(depleted) = 1 / (1 + exp(-sensitivity * z))
        
    At elapsed = true_interval: z = 0  => P = 0.50
    At elapsed > true_interval: z > 0  => P -> 1.0 (empty)
    At elapsed < true_interval: z < 0  => P -> 0.0 (still stocked)
    """
    if true_interval <= 0:
        raise ValueError("True interval must be positive.")

    relative_overdue = (elapsed_days - true_interval) / true_interval
    # Clip exponent to avoid numerical overflow
    clipped_exp = np.clip(-sensitivity * relative_overdue, -25.0, 25.0)
    return float(1.0 / (1.0 + np.exp(clipped_exp)))


def sample_user_response(
    elapsed_days: float,
    true_interval: float,
    rng: np.random.Generator,
    user_responsiveness: float = 0.85
) -> str:
    """
    Simulate an individual roommate's response to an alert.
    
    Outcomes:
    - 'IGNORE': User didn't look at phone or ignored alert.
    - 'YES': Confirms need (probability proportional to true depletion).
    - 'NO': Rejects (still plenty left).
    - 'SNOOZE': User knows it's low but asks to check back later.
    """
    # Chance that the user responds at all
    if rng.random() > user_responsiveness:
        return "IGNORE"

    p_depleted = compute_true_need_probability(elapsed_days, true_interval)

    # If item is genuinely empty, user is very likely to say YES
    roll = rng.random()
    if roll < p_depleted:
        return "YES"

    # If not empty, user either rejects or snoozes
    # 75% chance NO, 25% chance SNOOZE
    if rng.random() < 0.75:
        return "NO"
    return "SNOOZE"


def simulate_gang_response(
    elapsed_days: float,
    true_interval: float,
    members: List[User],
    rng: np.random.Generator
) -> Tuple[str, Optional[User]]:
    """
    Simulate collective gang decision on an alert:
    Roommates check their phones in random order.
    The first decisive response (YES, NO, or SNOOZE) resolves the alert.
    If all ignore, the result is 'IGNORE'.
    
    Returns (action, decisive_member).
    """
    if not members:
        return "IGNORE", None

    # Shuffle members to model random arrival order
    shuffled_members = list(members)
    rng.shuffle(shuffled_members)

    for member in shuffled_members:
        action = sample_user_response(elapsed_days, true_interval, rng)
        if action in ("YES", "NO", "SNOOZE"):
            return action, member

    return "IGNORE", None

