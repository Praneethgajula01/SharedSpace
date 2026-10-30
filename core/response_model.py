"""
Response probability model for SharedSpace.
Models P(Yes | features) - the probability that a roommate accepts a replenishment alert:
1. Beta-Binomial conjugate model per (user, item) pair
2. Logistic regression across contextual features (p_need, hour of day, user prior acceptance)
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np
from sklearn.linear_model import LogisticRegression


@dataclass
class BetaBinomialPrior:
    """
    Hyperparameters for the Beta prior on acceptance probability theta ~ Beta(alpha, beta).
    Expected probability E[theta] = alpha / (alpha + beta).
    """
    alpha: float = 2.0  # Pseudo-successes (Yes votes)
    beta: float = 2.0   # Pseudo-failures (No/Expired votes)


def update_beta_binomial(
    prior: BetaBinomialPrior,
    yes_count: int,
    no_count: int
) -> Tuple[float, float, float]:
    """
    Conjugate Bayesian update for binomial trials:
        alpha_post = alpha + yes_count
        beta_post  = beta + no_count
        
    Returns:
        (alpha_post, beta_post, expected_p_yes)
    """
    if yes_count < 0 or no_count < 0:
        raise ValueError("Counts must be non-negative integers.")

    alpha_post = prior.alpha + float(yes_count)
    beta_post = prior.beta + float(no_count)
    expected_p = alpha_post / (alpha_post + beta_post)
    return alpha_post, beta_post, float(expected_p)


class LogisticResponseModel:
    """
    Logistic regression model predicting P(Yes | features).
    Features:
        x = [p_need, user_historical_acceptance_rate, hour_of_day_normalized]
    """
    def __init__(self):
        self.clf: Optional[LogisticRegression] = None
        self.is_fitted: bool = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LogisticResponseModel":
        """
        Train logistic regression on user feedback records.
        X shape: (N, 3), y shape: (N,) with binary labels (1=YES, 0=NO/EXPIRED).
        """
        if len(y) < 4 or len(np.unique(y)) < 2:
            # Need at least both positive and negative examples
            self.is_fitted = False
            return self

        # L2 regularized logistic regression with balanced class weights
        self.clf = LogisticRegression(C=1.0, solver="lbfgs")
        self.clf.fit(X, y)
        self.is_fitted = True
        return self

    def predict_p_yes(
        self,
        p_need: float,
        user_acceptance_rate: float,
        hour_of_day: int
    ) -> float:
        """
        Predict probability of acceptance for a specific alert scenario.
        Falls back to combining p_need and user_acceptance_rate if not yet fitted.
        """
        if not self.is_fitted or self.clf is None:
            # Unfitted heuristic blending: 70% need probability, 30% user friendliness
            blended = 0.70 * p_need + 0.30 * user_acceptance_rate
            return float(np.clip(blended, 0.05, 0.95))

        hour_norm = (hour_of_day % 24) / 24.0
        feature_vector = np.array([[p_need, user_acceptance_rate, hour_norm]])
        
        # Output probability for class 1 (YES)
        p_yes = self.clf.predict_proba(feature_vector)[0][1]
        return float(p_yes)

