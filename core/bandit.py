"""
Dynamic threshold tuning and multi-armed bandit exploration for SharedSpace.
Uses Thompson Sampling on discrete threshold candidates:
    tau in [0.20, 0.35, 0.50, 0.65, 0.80]

Balances:
- Exploitation: using thresholds that yield high roommate acceptance
- Exploration: testing alternative thresholds to adapt to changing roommate tolerance
"""
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import numpy as np


@dataclass
class BanditArm:
    """
    A candidate decision threshold tau and its Beta prior on positive reward:
    Reward = 1 if alert is ACCEPTED (YES), 0 if REJECTED (NO) or EXPIRED.
    """
    tau: float
    successes: float = 1.0  # alpha prior
    failures: float = 1.0   # beta prior

    def sample_reward(self, rng: np.random.Generator) -> float:
        """Draw a sample from the posterior Beta distribution Beta(alpha, beta)."""
        return float(rng.beta(self.successes, self.failures))

    @property
    def expected_value(self) -> float:
        """Posterior mean reward."""
        return self.successes / (self.successes + self.failures)


class ThompsonThresholdBandit:
    """
    Multi-Armed Bandit for finding the optimal decision threshold tau* per gang/item.
    Default arms cover aggressive to conservative alerting:
        tau in [0.20, 0.35, 0.50, 0.65, 0.80]
    """
    def __init__(self, candidate_thresholds: Optional[List[float]] = None):
        if candidate_thresholds is None:
            candidate_thresholds = [0.20, 0.35, 0.50, 0.65, 0.80]

        self.arms: Dict[float, BanditArm] = {
            float(t): BanditArm(tau=float(t)) for t in candidate_thresholds
        }

    def select_threshold(self, rng: Optional[np.random.Generator] = None) -> float:
        """
        Thompson Sampling action selection:
        1. Sample theta_k ~ Beta(alpha_k, beta_k) for each candidate threshold arm k.
        2. Pick the threshold arm with the highest sampled value.
        """
        if rng is None:
            rng = np.random.default_rng()

        best_tau = list(self.arms.keys())[0]
        best_sample = -1.0

        for tau, arm in self.arms.items():
            sample = arm.sample_reward(rng)
            if sample > best_sample:
                best_sample = sample
                best_tau = tau

        return best_tau

    def update(self, chosen_tau: float, accepted: bool) -> None:
        """
        Bayesian update of the chosen threshold arm:
        - If roommate accepted (YES): alpha += 1.0
        - If rejected or expired (NO/EXPIRED): beta += 1.0
        """
        if chosen_tau not in self.arms:
            # Find closest arm if floating point mismatch
            closest_tau = min(self.arms.keys(), key=lambda t: abs(t - chosen_tau))
            chosen_tau = closest_tau

        arm = self.arms[chosen_tau]
        if accepted:
            arm.successes += 1.0
        else:
            arm.failures += 1.0

    def get_summary(self) -> List[Tuple[float, float, int]]:
        """
        Returns list of (tau, expected_reward, total_pulls) sorted by tau.
        """
        summary = []
        for tau in sorted(self.arms.keys()):
            arm = self.arms[tau]
            pulls = int(arm.successes + arm.failures - 2.0)  # subtract initial priors
            summary.append((tau, round(arm.expected_value, 3), max(0, pulls)))
        return summary
