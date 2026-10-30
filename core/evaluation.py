"""
Model calibration and evaluation suite for SharedSpace.
Computes:
1. Brier score: mean squared error of probabilistic predictions vs ground truth
2. Reliability curve binning: predicted confidence vs observed empirical frequency
3. Out-of-time sequential backtesting comparing all 4 models:
   - Declared baseline
   - Rolling moving average
   - Bayesian NIG log-interval
   - Weibull survival
"""
from dataclasses import dataclass
from typing import List, Dict, Tuple
import numpy as np


@dataclass
class EvaluationMetric:
    """Evaluation summary for a probabilistic model."""
    model_name: str
    brier_score: float
    log_loss: float
    sample_count: int


def compute_brier_score(y_true: List[int], y_prob: List[float]) -> float:
    """
    Calculate the Brier Score:
        BS = (1/N) * sum((p_i - y_i)^2)
        
    Strictly proper scoring rule bounded in [0, 1].
    Lower is better (0.0 = perfect calibration and discrimination).
    A naive 50/50 coin flip gets 0.25.
    """
    if len(y_true) != len(y_prob):
        raise ValueError("y_true and y_prob must have identical lengths.")
    if len(y_true) == 0:
        return 0.0

    y_t = np.asarray(y_true, dtype=float)
    y_p = np.clip(np.asarray(y_prob, dtype=float), 0.0, 1.0)
    return float(np.mean((y_p - y_t) ** 2))


def compute_log_loss(y_true: List[int], y_prob: List[float], eps: float = 1e-15) -> float:
    """
    Calculate binary cross-entropy (log-loss):
        Loss = -(1/N) * sum(y*ln(p) + (1-y)*ln(1-p))
    """
    if len(y_true) == 0:
        return 0.0

    y_t = np.asarray(y_true, dtype=float)
    y_p = np.clip(np.asarray(y_prob, dtype=float), eps, 1.0 - eps)
    loss = -(y_t * np.log(y_p) + (1.0 - y_t) * np.log(1.0 - y_p))
    return float(np.mean(loss))


def compute_reliability_curve(
    y_true: List[int],
    y_prob: List[float],
    n_bins: int = 5
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Bin probabilities and calculate empirical frequency in each bin:
    Returns (bin_centers, empirical_frequencies, bin_counts).
    
    A perfectly calibrated model has bin_centers == empirical_frequencies.
    """
    if len(y_true) == 0:
        return np.array([]), np.array([]), np.array([])

    y_t = np.asarray(y_true, dtype=float)
    y_p = np.clip(np.asarray(y_prob, dtype=float), 0.0, 1.0)

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_centers: List[float] = []
    emp_freqs: List[float] = []
    counts: List[int] = []

    for i in range(n_bins):
        low, high = bins[i], bins[i + 1]
        mask = (y_p >= low) & (y_p <= high) if i == n_bins - 1 else (y_p >= low) & (y_p < high)
        bin_count = int(np.sum(mask))
        counts.append(bin_count)

        if bin_count > 0:
            bin_centers.append(float(np.mean(y_p[mask])))
            emp_freqs.append(float(np.mean(y_t[mask])))
        else:
            bin_centers.append(float((low + high) / 2.0))
            emp_freqs.append(0.0)

    return np.array(bin_centers), np.array(emp_freqs), np.array(counts)


def evaluate_models_backtest(
    ground_truth_intervals: List[float],
    declared_prior: float,
    eval_step_fraction: float = 0.5
) -> Dict[str, EvaluationMetric]:
    """
    Sequential backtest over an observed timeline of purchase intervals:
    At each step k, uses intervals 0..k-1 as training history,
    and probes probabilities at elapsed points t = [0.5*T_k, 1.0*T_k, 1.5*T_k].
    
    Ground truth label: y = 1 if t >= T_k (depleted), 0 otherwise.
    """
    from core.need_model import p_need_declared_schedule, p_need_rolling_average
    from core.bayesian_model import p_need_bayesian
    from core.survival_model import p_need_survival

    predictions: Dict[str, List[float]] = {
        "Declared Baseline": [],
        "Rolling Average": [],
        "Bayesian NIG": [],
        "Weibull Survival": [],
    }
    ground_truth: List[int] = []

    # Sequential walk-forward evaluation
    for k in range(len(ground_truth_intervals)):
        past_intervals = ground_truth_intervals[:k]
        actual_interval = ground_truth_intervals[k]

        # Probe points: 50% elapsed, 100% elapsed (due), 150% elapsed (overdue)
        probes = [0.5 * actual_interval, 1.0 * actual_interval, 1.5 * actual_interval]

        for elapsed in probes:
            # y = 1 if depleted (elapsed >= actual_interval)
            y_label = 1 if elapsed >= actual_interval else 0
            ground_truth.append(y_label)

            predictions["Declared Baseline"].append(
                p_need_declared_schedule(elapsed, declared_prior)
            )
            predictions["Rolling Average"].append(
                p_need_rolling_average(elapsed, declared_prior, past_intervals)
            )
            predictions["Bayesian NIG"].append(
                p_need_bayesian(elapsed, declared_prior, past_intervals)
            )
            predictions["Weibull Survival"].append(
                p_need_survival(elapsed, declared_prior, past_intervals)
            )

    results: Dict[str, EvaluationMetric] = {}
    for model_name, probs in predictions.items():
        brier = compute_brier_score(ground_truth, probs)
        loss = compute_log_loss(ground_truth, probs)
        results[model_name] = EvaluationMetric(
            model_name=model_name,
            brier_score=round(brier, 4),
            log_loss=round(loss, 4),
            sample_count=len(ground_truth)
        )

    return results

