"""
Cost-benefit decision engine and alert gating for SharedSpace.
Implements:
1. Expected utility threshold:
       tau* = Annoyance / (Annoyance + Benefit)
   Alert triggered only if P(need) >= tau*
2. Cooldown suppression logic to avoid spamming roommates after recent prompts.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple


@dataclass
class UtilityConfig:
    """
    Cost-benefit parameters:
    - benefit: Positive utility of timely replenishment (e.g. coffee/milk ready in morning)
    - annoyance: Negative utility of a false-alarm notification (interruption, spam)
    """
    benefit: float = 3.0    # Value gained by having milk stocked on time
    annoyance: float = 1.0  # Cost of bothering the gang when stock was still full


def compute_optimal_threshold(utility: UtilityConfig) -> float:
    """
    Derive the optimal decision threshold tau* from expected utility maximization:
    
        Expected Utility:
            E[U] = P(need) * Benefit - (1 - P(need)) * Annoyance
        Alert if E[U] > 0:
            P(need) * Benefit > (1 - P(need)) * Annoyance
            P(need) * (Benefit + Annoyance) > Annoyance
            P(need) > Annoyance / (Benefit + Annoyance)
            
    Returns:
        tau* = Annoyance / (Annoyance + Benefit)
    """
    if utility.benefit <= 0 or utility.annoyance <= 0:
        raise ValueError("Benefit and annoyance must be strictly positive.")

    tau_star = utility.annoyance / (utility.annoyance + utility.benefit)
    return float(tau_star)


def is_in_cooldown(
    current_time: datetime,
    last_prompted_at: Optional[datetime],
    cooldown_hours: float = 6.0
) -> bool:
    """
    Check if the item was alerted recently and is still within cooldown period.
    Prevents repeated buzzing within a short window.
    """
    if last_prompted_at is None:
        return False

    if current_time < last_prompted_at:
        raise ValueError("current_time cannot be earlier than last_prompted_at.")

    elapsed_hours = (current_time - last_prompted_at).total_seconds() / 3600.0
    return bool(elapsed_hours < cooldown_hours)


def should_trigger_request(
    p_need: float,
    current_time: datetime,
    last_prompted_at: Optional[datetime],
    utility: Optional[UtilityConfig] = None,
    cooldown_hours: float = 6.0
) -> Tuple[bool, str, float]:
    """
    Evaluate whether to fire a purchase request to the gang:
    1. Check cooldown window
    2. Compare P(need) against optimal economic threshold tau*
    
    Returns:
        (should_trigger, reason_code, threshold_tau)
    """
    if utility is None:
        utility = UtilityConfig()

    threshold = compute_optimal_threshold(utility)

    # 1. Cooldown check
    if is_in_cooldown(current_time, last_prompted_at, cooldown_hours):
        return False, "COOLDOWN_ACTIVE", threshold

    # 2. Probability threshold check
    if p_need >= threshold:
        return True, "THRESHOLD_MET", threshold

    return False, "PROBABILITY_TOO_LOW", threshold

