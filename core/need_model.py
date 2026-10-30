"""
Need probability models for SharedSpace.
Computes P(need now | days elapsed, history, prior).

Step 8 introduces baseline heuristics:
1. Declared schedule baseline
2. Rolling moving average baseline
"""
from datetime import datetime
from typing import List, Optional
import numpy as np
from core.db import PurchaseEvent


def get_elapsed_days(current_time: datetime, last_purchase_time: datetime) -> float:
    """
    Calculate the elapsed time in fractional days between two timestamps.
    """
    if current_time < last_purchase_time:
        raise ValueError("current_time cannot be earlier than last_purchase_time.")
    
    delta_seconds = (current_time - last_purchase_time).total_seconds()
    return float(delta_seconds / 86400.0)


def compute_historical_intervals(purchases: List[PurchaseEvent]) -> List[float]:
    """
    Extract elapsed intervals (in days) between consecutive purchases.
    Input purchases must be chronologically ordered.
    """
    if len(purchases) < 2:
        return []

    intervals: List[float] = []
    for i in range(1, len(purchases)):
        delta = (purchases[i].purchased_at - purchases[i - 1].purchased_at).total_seconds() / 86400.0
        if delta > 0:
            intervals.append(float(delta))

    return intervals


def p_need_declared_schedule(elapsed_days: float, declared_interval_days: float) -> float:
    """
    Baseline 1: Declared Schedule.
    Assumes need grows linearly with elapsed time according to the user's initial prior.
    
    Formula:
        P(need) = min(1.0, elapsed_days / declared_interval_days)
    """
    if declared_interval_days <= 0:
        raise ValueError("Declared interval must be strictly positive.")
    
    if elapsed_days <= 0:
        return 0.0

    ratio = elapsed_days / declared_interval_days
    return float(np.clip(ratio, 0.0, 1.0))


def p_need_rolling_average(
    elapsed_days: float,
    declared_interval_days: float,
    historical_intervals: List[float],
    window: int = 5
) -> float:
    """
    Baseline 2: Rolling Moving Average.
    Calculates the mean of the most recent `window` completed intervals.
    Falls back to declared_interval_days if no history is available.
    
    Formula:
        mean_interval = mean(last `window` intervals) or declared_interval_days
        P(need) = min(1.0, elapsed_days / mean_interval)
    """
    if declared_interval_days <= 0:
        raise ValueError("Declared interval must be strictly positive.")

    if not historical_intervals:
        effective_interval = declared_interval_days
    else:
        recent_window = historical_intervals[-window:]
        effective_interval = float(np.mean(recent_window))
        if effective_interval <= 0:
            effective_interval = declared_interval_days

    if elapsed_days <= 0:
        return 0.0

    ratio = elapsed_days / effective_interval
    return float(np.clip(ratio, 0.0, 1.0))

