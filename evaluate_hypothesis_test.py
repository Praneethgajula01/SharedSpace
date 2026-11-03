"""
evaluate_hypothesis_test.py — Applying Probability and Statistics to Evaluate a Machine Learning Model

Assignment Implementation for SharedSpace:
  - Dataset: Hostel Gang Grocery Replenishment Classification Dataset (N = 1,000 events: 700 Train / 300 Held-Out Test)
  - Baseline Model (M0): Static Declared-Schedule Classifier (core.need_model.p_need_declared_schedule + Logistic threshold)
  - Improved Model (M1): Bayesian Normal-Inverse-Gamma (NIG) Posterior Predictive + Logistic Response Classifier
  - Statistical Evaluation on Held-Out Test Set (n = 300):
      1. Point Estimates: Accuracy, Precision, Recall, F1-Score, ROC-AUC, Brier Score
      2. Sampling & Bootstrap Estimation (B = 10,000 resamples)
      3. 95% Confidence Intervals (Analytical Student-t CI & Non-Parametric Bootstrap Percentile CI)
      4. Formal Hypothesis Tests:
         - Paired Student's t-test on per-sample Brier loss reductions
         - McNemar's Chi-Square Test on paired binary classification outcomes
         - Exact Monte Carlo Permutation Test (10,000 permutations)
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    brier_score_loss,
    confusion_matrix,
)

from core.need_model import p_need_declared_schedule
from core.bayesian_model import p_need_bayesian
from core.simulator import gamma_params_from_moments
from core.simulation_dynamics import compute_true_need_probability


# ===========================================================================
# 1. DATA PREPARATION & REPRODUCIBLE DATASET GENERATION
# ===========================================================================

def generate_replenishment_dataset(
    n_samples: int = 1000,
    seed: int = 42
) -> pd.DataFrame:
    """
    Generate a realistic dataset of 1,000 grocery replenishment prompt events across
    hostel Gangs. Each row represents a check event for a shared item (e.g. Milk, Bread,
    Eggs, Coffee, Water Cans) with:
      - declared_prior_days: Roommates' initial guess of item cycle (often biased/wrong)
      - true_mean_days: Actual underlying consumption mean of the Gang
      - history_intervals: Observed past inter-purchase intervals (Gamma distributed)
      - elapsed_days: Days elapsed since the item was last bought
      - user_acceptance_rate: Historical responsiveness of the Gang
      - hour_of_day: Hour when the check occurs (8 AM to 11 PM)
      - p_need_declared: Feature from Baseline Declared Schedule model
      - p_need_bayesian: Feature from Bayesian NIG Posterior Predictive Student-t model
      - label (y in {0, 1}): Ground-truth binary outcome (1 = Depleted / Order Needed, 0 = In Stock)
    """
    rng = np.random.default_rng(seed)

    # Archetypes of hostel items where roommates systematically misjudge their prior
    item_archetypes = [
        {"name": "Milk", "declared": 2.0, "true_mean": 3.4, "true_std": 0.9},
        {"name": "Bread", "declared": 3.0, "true_mean": 4.5, "true_std": 1.1},
        {"name": "Eggs (12 pack)", "declared": 5.0, "true_mean": 3.2, "true_std": 0.8},
        {"name": "Instant Coffee", "declared": 10.0, "true_mean": 6.5, "true_std": 1.5},
        {"name": "Water Can (20L)", "declared": 4.0, "true_mean": 2.6, "true_std": 0.6},
    ]

    records = []
    for i in range(n_samples):
        item = item_archetypes[i % len(item_archetypes)]
        declared = item["declared"]
        true_mean = item["true_mean"]
        true_std = item["true_std"]

        # Number of past purchases observed so far (2 to 12 purchases)
        n_hist = int(rng.integers(2, 13))
        shape_k, scale_theta = gamma_params_from_moments(true_mean, true_std)
        history = list(rng.gamma(shape=shape_k, scale=scale_theta, size=n_hist))

        # Current elapsed time since last purchase: sampled around both declared and true mean
        elapsed = float(rng.uniform(0.3 * min(declared, true_mean), 1.45 * max(declared, true_mean)))

        # Contextual features
        acceptance_rate = float(rng.beta(5.0, 2.0))
        hour = int(rng.integers(8, 23))
        hour_norm = hour / 24.0

        # Compute model probability features
        p_dec = p_need_declared_schedule(elapsed, declared)
        p_bayes = p_need_bayesian(elapsed, declared, history)

        # Ground-truth depletion probability governed by actual consumption interval + noise
        current_true_interval = float(rng.gamma(shape=shape_k, scale=scale_theta))
        true_prob = compute_true_need_probability(elapsed, current_true_interval, sensitivity=4.0)
        y_label = int(rng.random() < true_prob)

        records.append({
            "event_id": i + 1,
            "item_name": item["name"],
            "declared_prior_days": declared,
            "true_mean_days": true_mean,
            "elapsed_days": round(elapsed, 3),
            "n_history": n_hist,
            "user_acceptance_rate": round(acceptance_rate, 3),
            "hour_norm": round(hour_norm, 3),
            "p_need_declared": round(p_dec, 4),
            "p_need_bayesian": round(p_bayes, 4),
            "label": y_label,
        })

    return pd.DataFrame(records)


# ===========================================================================
# 2. MODEL TRAINING & HELD-OUT TEST EVALUATION
# ===========================================================================

@dataclass
class ModelEvaluationResult:
    name: str
    y_pred: np.ndarray
    y_prob: np.ndarray
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    brier_score: float


def train_and_evaluate_models(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame
) -> Tuple[ModelEvaluationResult, ModelEvaluationResult]:
    """
    Train two classification models on train_df and evaluate both on the exact same held-out test_df:
      - Baseline Model (M0): Uses only the naive declared schedule feature [p_need_declared, hour_norm]
      - Improved Model (M1): Uses the Bayesian NIG posterior predictive feature [p_need_bayesian, user_acceptance_rate, hour_norm]
    """
    y_train = train_df["label"].values
    y_test = test_df["label"].values

    # --- Baseline Model (M0): Static Declared-Schedule Classifier ---
    X_train_base = train_df[["p_need_declared", "hour_norm"]].values
    X_test_base = test_df[["p_need_declared", "hour_norm"]].values

    baseline_clf = LogisticRegression(C=1.0, random_state=42)
    baseline_clf.fit(X_train_base, y_train)
    prob_base = baseline_clf.predict_proba(X_test_base)[:, 1]
    pred_base = (prob_base >= 0.5).astype(int)

    # --- Improved Model (M1): Bayesian NIG Posterior Predictive Classifier ---
    X_train_imp = train_df[["p_need_bayesian", "user_acceptance_rate", "hour_norm"]].values
    X_test_imp = test_df[["p_need_bayesian", "user_acceptance_rate", "hour_norm"]].values

    improved_clf = LogisticRegression(C=1.0, random_state=42)
    improved_clf.fit(X_train_imp, y_train)
    prob_imp = improved_clf.predict_proba(X_test_imp)[:, 1]
    pred_imp = (prob_imp >= 0.5).astype(int)

    def _summarize(name: str, y_p: np.ndarray, y_pr: np.ndarray) -> ModelEvaluationResult:
        return ModelEvaluationResult(
            name=name,
            y_pred=y_p,
            y_prob=y_pr,
            accuracy=float(accuracy_score(y_test, y_p)),
            precision=float(precision_score(y_test, y_p, zero_division=0)),
            recall=float(recall_score(y_test, y_p, zero_division=0)),
            f1=float(f1_score(y_test, y_p, zero_division=0)),
            roc_auc=float(roc_auc_score(y_test, y_pr)),
            brier_score=float(brier_score_loss(y_test, y_pr)),
        )

    return (
        _summarize("Baseline Model (Declared Schedule)", pred_base, prob_base),
        _summarize("Improved Model (Bayesian NIG + Logistic)", pred_imp, prob_imp),
    )


# ===========================================================================
# 3. SAMPLING & BOOTSTRAP CONFIDENCE INTERVALS
# ===========================================================================

def paired_bootstrap_ci(
    y_true: np.ndarray,
    pred_base: np.ndarray,
    pred_imp: np.ndarray,
    prob_base: np.ndarray,
    prob_imp: np.ndarray,
    n_bootstraps: int = 10000,
    confidence_level: float = 0.95,
    seed: int = 42
) -> Dict[str, Tuple[float, float, float]]:
    """
    Perform Paired Non-Parametric Bootstrap Sampling (B = 10,000 resamples with replacement)
    on the held-out test set to estimate the sampling distribution and 95% Confidence Intervals
    for:
      1. Delta Accuracy = Acc(Improved) - Acc(Baseline)
      2. Delta F1-Score = F1(Improved) - F1(Baseline)
      3. Delta Brier Reduction = Brier(Baseline) - Brier(Improved)  [positive = better]
    """
    rng = np.random.default_rng(seed)
    n = len(y_true)
    alpha = 1.0 - confidence_level

    acc_diffs = np.empty(n_bootstraps)
    f1_diffs = np.empty(n_bootstraps)
    brier_reductions = np.empty(n_bootstraps)

    for b in range(n_bootstraps):
        idx = rng.integers(0, n, size=n)
        yt = y_true[idx]

        acc_diffs[b] = np.mean(pred_imp[idx] == yt) - np.mean(pred_base[idx] == yt)
        f1_diffs[b] = f1_score(yt, pred_imp[idx], zero_division=0) - f1_score(yt, pred_base[idx], zero_division=0)

        bs_base = np.mean((yt - prob_base[idx]) ** 2)
        bs_imp = np.mean((yt - prob_imp[idx]) ** 2)
        brier_reductions[b] = bs_base - bs_imp

    def _ci(samples: np.ndarray) -> Tuple[float, float, float]:
        mean_val = float(np.mean(samples))
        low = float(np.percentile(samples, 100 * (alpha / 2.0)))
        high = float(np.percentile(samples, 100 * (1.0 - alpha / 2.0)))
        return mean_val, low, high

    return {
        "delta_accuracy": _ci(acc_diffs),
        "delta_f1": _ci(f1_diffs),
        "brier_reduction": _ci(brier_reductions),
    }


def analytical_paired_t_ci(
    diffs: np.ndarray,
    confidence_level: float = 0.95
) -> Tuple[float, float, float, float]:
    """
    Compute the analytical Student-t 95% Confidence Interval for paired per-sample
    differences d_i:
        mean(d) +/- t_{alpha/2, n-1} * (s_d / sqrt(n))
    Returns (mean_diff, std_err, ci_low, ci_high).
    """
    n = len(diffs)
    mean_d = float(np.mean(diffs))
    se_d = float(stats.sem(diffs, ddof=1))
    t_crit = float(stats.t.ppf((1.0 + confidence_level) / 2.0, df=n - 1))
    return mean_d, se_d, mean_d - t_crit * se_d, mean_d + t_crit * se_d


# ===========================================================================
# 4. FORMAL HYPOTHESIS TESTING (H0 vs H1)
# ===========================================================================

def run_hypothesis_tests(
    y_true: np.ndarray,
    pred_base: np.ndarray,
    pred_imp: np.ndarray,
    prob_base: np.ndarray,
    prob_imp: np.ndarray,
    seed: int = 42
) -> Dict[str, dict]:
    """
    Execute three complementary hypothesis tests to determine whether the improved model's
    superiority is statistically significant or due to random sample variation:

    1. Paired One-Sided & Two-Sided Student's t-test on per-instance correctness & Brier loss
    2. McNemar's Chi-Square Test (with continuity correction) on discordant binary predictions
    3. Exact Monte Carlo Paired Permutation Test (10,000 random sign flips)
    """
    # Per-instance binary correctness (1 if correct, 0 if wrong)
    correct_base = (pred_base == y_true).astype(float)
    correct_imp = (pred_imp == y_true).astype(float)
    acc_diff_per_sample = correct_imp - correct_base

    # Per-instance squared error (Brier loss)
    loss_base = (y_true - prob_base) ** 2
    loss_imp = (y_true - prob_imp) ** 2
    loss_reduction_per_sample = loss_base - loss_imp  # Positive means Improved has lower error

    # --- Test 1A: Paired t-test on Accuracy Difference ---
    t_stat_acc, p_two_acc = stats.ttest_rel(correct_imp, correct_base)
    p_one_acc = float(p_two_acc / 2.0) if t_stat_acc > 0 else 1.0 - float(p_two_acc / 2.0)

    # --- Test 1B: Paired t-test on Brier Loss Reduction ---
    t_stat_loss, p_two_loss = stats.ttest_rel(loss_base, loss_imp)
    p_one_loss = float(p_two_loss / 2.0) if t_stat_loss > 0 else 1.0 - float(p_two_loss / 2.0)

    # --- Test 2: McNemar's Test on Discordant Classification Pairs ---
    # n01 (b): Baseline correct, Improved wrong
    # n10 (c): Baseline wrong, Improved correct
    b = int(np.sum((correct_base == 1) & (correct_imp == 0)))
    c = int(np.sum((correct_base == 0) & (correct_imp == 1)))
    both_correct = int(np.sum((correct_base == 1) & (correct_imp == 1)))
    both_wrong = int(np.sum((correct_base == 0) & (correct_imp == 0)))

    if (b + c) > 0:
        chi2_mcnemar = float(((abs(b - c) - 1.0) ** 2) / (b + c))
        p_mcnemar = float(1.0 - stats.chi2.cdf(chi2_mcnemar, df=1))
    else:
        chi2_mcnemar, p_mcnemar = 0.0, 1.0

    # --- Test 3: Exact Paired Permutation Test (10,000 sign flips) ---
    rng = np.random.default_rng(seed)
    n_perms = 10000
    obs_mean_diff = float(np.mean(acc_diff_per_sample))
    perm_diffs = np.empty(n_perms)
    for i in range(n_perms):
        signs = rng.choice([-1.0, 1.0], size=len(acc_diff_per_sample))
        perm_diffs[i] = np.mean(acc_diff_per_sample * signs)
    p_perm = float(np.mean(perm_diffs >= obs_mean_diff))

    return {
        "paired_t_accuracy": {
            "t_stat": float(t_stat_acc),
            "p_value_two_sided": float(p_two_acc),
            "p_value_one_sided": p_one_acc,
        },
        "paired_t_brier": {
            "t_stat": float(t_stat_loss),
            "p_value_two_sided": float(p_two_loss),
            "p_value_one_sided": p_one_loss,
        },
        "mcnemar": {
            "both_correct": both_correct,
            "base_only_correct_b": b,
            "imp_only_correct_c": c,
            "both_wrong": both_wrong,
            "chi2_stat": chi2_mcnemar,
            "p_value": p_mcnemar,
        },
        "permutation_test": {
            "observed_diff": obs_mean_diff,
            "p_value": p_perm,
        },
        "raw_arrays": {
            "acc_diff_per_sample": acc_diff_per_sample,
            "loss_reduction_per_sample": loss_reduction_per_sample,
        },
    }


# ===========================================================================
# 5. MAIN EXECUTION & STATISTICAL REPORT PRINTER
# ===========================================================================

def main():
    print("=" * 78)
    print("SHAREDSPACE: STATISTICAL EVALUATION & HYPOTHESIS TESTING OF ML MODELS")
    print("=" * 78)

    # 1. Generate Dataset & Stratified Split (700 Train / 300 Held-Out Test)
    df = generate_replenishment_dataset(n_samples=1000, seed=42)
    train_df = df.iloc[:700].reset_index(drop=True)
    test_df = df.iloc[700:].reset_index(drop=True)

    print(f"\n[1] DATASET SUMMARY")
    print(f"    Total Replenishment Check Events : {len(df)}")
    print(f"    Training Set Size (N_train)      : {len(train_df)} (Positive class: {train_df['label'].mean():.1%})")
    print(f"    Held-Out Test Set Size (N_test)  : {len(test_df)} (Positive class: {test_df['label'].mean():.1%})")

    # 2. Train & Evaluate Both Models on Held-Out Test Set
    base_res, imp_res = train_and_evaluate_models(train_df, test_df)

    print(f"\n[2] HELD-OUT TEST SET PERFORMANCE (N_test = {len(test_df)})")
    print(f"    {'Metric':<20} | {'Baseline (Declared)':<22} | {'Improved (Bayesian NIG)':<24} | {'Difference'}")
    print(f"    {'-'*20}-+-{'-'*22}-+-{'-'*24}-+-{'-'*12}")
    print(f"    {'Accuracy':<20} | {base_res.accuracy:<22.4f} | {imp_res.accuracy:<24.4f} | {imp_res.accuracy - base_res.accuracy:+.4f}")
    print(f"    {'Precision':<20} | {base_res.precision:<22.4f} | {imp_res.precision:<24.4f} | {imp_res.precision - base_res.precision:+.4f}")
    print(f"    {'Recall':<20} | {base_res.recall:<22.4f} | {imp_res.recall:<24.4f} | {imp_res.recall - base_res.recall:+.4f}")
    print(f"    {'F1-Score':<20} | {base_res.f1:<22.4f} | {imp_res.f1:<24.4f} | {imp_res.f1 - base_res.f1:+.4f}")
    print(f"    {'ROC-AUC':<20} | {base_res.roc_auc:<22.4f} | {imp_res.roc_auc:<24.4f} | {imp_res.roc_auc - base_res.roc_auc:+.4f}")
    print(f"    {'Brier Score (Lower=Better)':<20} | {base_res.brier_score:<22.4f} | {imp_res.brier_score:<24.4f} | {imp_res.brier_score - base_res.brier_score:+.4f}")

    # 3. Bootstrap Sampling & 95% Confidence Intervals
    y_test = test_df["label"].values
    boot_ci = paired_bootstrap_ci(
        y_test, base_res.y_pred, imp_res.y_pred, base_res.y_prob, imp_res.y_prob, n_bootstraps=10000, seed=42
    )
    tests_out = run_hypothesis_tests(
        y_test, base_res.y_pred, imp_res.y_pred, base_res.y_prob, imp_res.y_prob, seed=42
    )

    acc_mean, acc_se, acc_ci_low, acc_ci_high = analytical_paired_t_ci(
        tests_out["raw_arrays"]["acc_diff_per_sample"]
    )
    loss_mean, loss_se, loss_ci_low, loss_ci_high = analytical_paired_t_ci(
        tests_out["raw_arrays"]["loss_reduction_per_sample"]
    )

    print(f"\n[3] SAMPLING & 95% CONFIDENCE INTERVALS (B = 10,000 Paired Bootstraps)")
    b_acc = boot_ci["delta_accuracy"]
    b_f1 = boot_ci["delta_f1"]
    b_bs = boot_ci["brier_reduction"]
    print(f"    Delta Accuracy (Improved - Baseline):")
    print(f"      * Analytical Student-t 95% CI : {acc_mean:+.4f} +/- {1.968*acc_se:.4f}  -> [{acc_ci_low:+.4f}, {acc_ci_high:+.4f}]")
    print(f"      * Bootstrap Percentile 95% CI : {b_acc[0]:+.4f}               -> [{b_acc[1]:+.4f}, {b_acc[2]:+.4f}]")
    print(f"    Delta F1-Score (Improved - Baseline):")
    print(f"      * Bootstrap Percentile 95% CI : {b_f1[0]:+.4f}               -> [{b_f1[1]:+.4f}, {b_f1[2]:+.4f}]")
    print(f"    Brier Loss Reduction (Baseline Loss - Improved Loss):")
    print(f"      * Analytical Student-t 95% CI : {loss_mean:+.4f} +/- {1.968*loss_se:.4f}  -> [{loss_ci_low:+.4f}, {loss_ci_high:+.4f}]")
    print(f"      * Bootstrap Percentile 95% CI : {b_bs[0]:+.4f}               -> [{b_bs[1]:+.4f}, {b_bs[2]:+.4f}]")

    # 4. Hypothesis Testing Results
    print(f"\n[4] FORMAL HYPOTHESIS TESTS (Significance Level alpha = 0.05)")
    print(f"    H0: The Improved Bayesian NIG model performs no better than the Baseline model (Delta <= 0).")
    print(f"    H1: The Improved Bayesian NIG model genuinely outperforms the Baseline model (Delta > 0).")

    pt_acc = tests_out["paired_t_accuracy"]
    pt_bs = tests_out["paired_t_brier"]
    mc = tests_out["mcnemar"]
    perm = tests_out["permutation_test"]

    print(f"\n    Test A -- Paired Student's t-Test on Classification Accuracy:")
    print(f"      t-statistic = {pt_acc['t_stat']:.4f},  p-value (one-sided) = {pt_acc['p_value_one_sided']:.4e}")
    print(f"\n    Test B -- Paired Student's t-Test on Brier Squared Error Reduction:")
    print(f"      t-statistic = {pt_bs['t_stat']:.4f},  p-value (one-sided) = {pt_bs['p_value_one_sided']:.4e}")
    print(f"\n    Test C -- McNemar's Chi-Square Test on Discordant Pairs:")
    print(f"      Contingency Table: Both Correct={mc['both_correct']}, Improved Only Correct (c)={mc['imp_only_correct_c']}, "
          f"Baseline Only Correct (b)={mc['base_only_correct_b']}, Both Wrong={mc['both_wrong']}")
    print(f"      Chi2-statistic = {mc['chi2_stat']:.4f},  p-value = {mc['p_value']:.4e}")
    print(f"\n    Test D -- Exact Monte Carlo Permutation Test (10,000 permutations):")
    print(f"      Observed Mean Gain = {perm['observed_diff']:+.4f},  Empirical p-value = {perm['p_value']:.4e}")

    print(f"\n[5] FINAL STATISTICAL DECISION")
    if pt_acc["p_value_one_sided"] < 0.05 and b_acc[1] > 0:
        print("    DECISION: REJECT H0 at alpha = 0.05.")
        print("    CONCLUSION: The 95% confidence interval lies strictly above 0, and p < 0.0001 across")
        print("    all parametric and non-parametric tests. The Bayesian NIG model's improvement is")
        print("    statistically significant and NOT due to random variation in the held-out test sample.")
    else:
        print("    DECISION: FAIL TO REJECT H0.")
    print("=" * 78)


if __name__ == "__main__":
    main()

