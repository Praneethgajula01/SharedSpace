# Applying Probability and Statistics to Evaluate a Machine Learning Model

**Project Title**: SharedSpace — Statistical Evaluation of Bayesian Replenishment Classification vs. Static Schedule Baseline  
**Repository Link**: https://github.com/Praneethgajula01/SharedSpace  
**Reproducible Code File**: [`evaluate_hypothesis_test.py`](./evaluate_hypothesis_test.py)

---

## 1. Problem Statement and Dataset

### 1.1 Real-World Problem Statement
In shared student housing and hostels (**SharedSpace**), roommate groups ("Gangs") regularly share recurring grocery staples (milk, bread, eggs, instant coffee, and 20L water cans). Predicting **when an item is depleted and requires an order** is a binary classification problem under uncertainty:
- If the system triggers an order request too early ($Y = 0$, item still in stock), roommates experience notification fatigue and reject the prompt.
- If the system triggers too late ($Y = 1$, item depleted), the Gang suffers a stockout.

Roommates initially provide a rough estimate of how long an item lasts (the **declared interval prior** $D_0$, e.g., *"Milk lasts 2 days"*). However, human priors are systematically biased and actual consumption exhibits stochastic variance.

### 1.2 Classification Task Formulation
Given a replenishment check event $i$ at elapsed time $\Delta t_i$ since the last purchase, the task is to predict the binary target label:
$$Y_i \in \{0, 1\}, \quad \text{where } Y_i = \begin{cases} 1 & \text{if the item is depleted / Gang approves order (Positive Class)} \\ 0 & \text{if the item is still in stock / order not needed (Negative Class)} \end{cases}$$

### 1.3 Dataset Description
The dataset (`generate_replenishment_dataset` in `evaluate_hypothesis_test.py`, fixed random seed `42`) consists of **$N = 1,000$ replenishment check events** across 5 recurring hostel grocery archetypes (`Milk`, `Bread`, `Eggs (12 pack)`, `Instant Coffee`, `Water Can (20L)`):
- **Training Set ($N_{\text{train}} = 700$)**: Used to fit the classification decision boundaries ($52.9\%$ positive class).
- **Held-Out Test Set ($N_{\text{test}} = 300$)**: Strictly held out to evaluate both models on identical unseen instances ($56.7\%$ positive class).

**Features per instance**:
1. `declared_prior_days` ($D_0$): Roommates' initial belief of the replenishment cycle (days).
2. `elapsed_days` ($\Delta t$): Time elapsed since the item's last recorded purchase.
3. `history_intervals` ($T_1, \dots, T_n$): Historical inter-purchase intervals observed for the Gang.
4. `user_acceptance_rate`: Historical Beta-smoothed responsiveness of the Gang.
5. `hour_norm`: Normalized time of day when the check is performed.
6. `p_need_declared`: Depletion probability estimated by the naive declared schedule:
   $$P_{\text{declared}}(\text{need}) = \min\left(1.0, \frac{\Delta t}{D_0}\right)$$
7. `p_need_bayesian`: Depletion probability estimated by our **Bayesian Normal-Inverse-Gamma (NIG)** conjugate update on log-intervals $y_k = \ln(T_k)$, evaluated via the posterior predictive Student-$t$ Cumulative Distribution Function (CDF).

### 1.4 Models Compared
1. **Baseline Model ($M_0$ — Static Declared-Schedule Classifier)**:
   A logistic regression classifier trained using only the static declared schedule feature (`p_need_declared`) and time of day (`hour_norm`). It relies entirely on the roommates' initial guess $D_0$ without learning from historical purchase intervals.
2. **Improved Model ($M_1$ — Bayesian NIG Posterior Predictive Classifier)**:
   A logistic regression classifier powered by the **Bayesian Normal-Inverse-Gamma (`p_need_bayesian`)** posterior predictive probability and historical Gang acceptance rate (`user_acceptance_rate`, `hour_norm`).

---

## 2. Sampling and Experimental Methodology

### 2.1 Paired Experimental Design on the Held-Out Test Set
To investigate whether the observed improvement of $M_1$ over $M_0$ is genuine or merely an artifact of random test-set variation, both models are evaluated on the **exact same held-out test sample** $\mathcal{D}_{\text{test}} = \{(x_i, y_i)\}_{i=1}^{300}$.

Because both models predict on the same test units $i \in \{1, \dots, 300\}$, this forms a **paired sample design**. Pairing removes between-instance variance and substantially increases statistical power compared to independent two-sample tests.

For each test instance $i$, we record:
- Binary correctness indicator:
  $$c_i^{(m)} = \mathbb{I}\left(\hat{y}_i^{(m)} = y_i\right) \in \{0, 1\}, \quad d_i^{\text{acc}} = c_i^{(1)} - c_i^{(0)} \in \{-1, 0, +1\}$$
- Probabilistic Brier squared error:
  $$\ell_i^{(m)} = \left(y_i - \hat{p}_i^{(m)}\right)^2, \quad d_i^{\text{loss}} = \ell_i^{(0)} - \ell_i^{(1)}$$

### 2.2 Non-Parametric Paired Bootstrap Resampling ($B = 10,000$)
To estimate the sampling distribution of the performance difference without relying solely on Gaussian assumptions:
1. For $b = 1, 2, \dots, 10,000$, we draw a bootstrap sample $\mathcal{D}_{\text{test}}^{*(b)}$ of size $N_{\text{test}} = 300$ **with replacement** from the held-out test indices $\{1, \dots, 300\}$.
2. On each bootstrap replicate $b$, we compute the paired differences:
   $$\Delta \text{Acc}^{*(b)} = \text{Acc}(M_1)^{*(b)} - \text{Acc}(M_0)^{*(b)}$$
   $$\Delta \text{Brier}^{*(b)} = \text{BS}(M_0)^{*(b)} - \text{BS}(M_1)^{*(b)}$$
3. From the empirical distribution of $10,000$ bootstrap differences, we construct the **95% Percentile Bootstrap Confidence Interval** using the $2.5\text{th}$ and $97.5\text{th}$ percentiles:
   $$\text{CI}_{95\%}^{\text{boot}} = \left[\Delta_{(0.025)}^{*}, \, \Delta_{(0.975)}^{*}\right]$$

### 2.3 Analytical Student-$t$ Confidence Interval
By the Central Limit Theorem, for $N_{\text{test}} = 300$, the sample mean of paired differences $\bar{d} = \frac{1}{n}\sum_{i=1}^n d_i$ follows an approximate Student-$t$ distribution with $n - 1 = 299$ degrees of freedom:
$$\text{CI}_{95\%}^{\text{analytical}} = \bar{d} \pm t_{0.975, \, n-1} \cdot \frac{s_d}{\sqrt{n}}, \quad \text{where } s_d = \sqrt{\frac{1}{n-1}\sum_{i=1}^n (d_i - \bar{d})^2}$$

### 2.4 Formal Hypothesis Testing Framework ($\alpha = 0.05$)
We define our hypotheses at significance level $\alpha = 0.05$:
- **Null Hypothesis ($H_0$)**: $\mu_{\Delta} \le 0$ — The Improved Bayesian NIG model ($M_1$) performs no better than the Baseline Declared-Schedule model ($M_0$); any observed gain on the test set is due to random sampling variation.
- **Alternative Hypothesis ($H_1$)**: $\mu_{\Delta} > 0$ — The Improved Bayesian NIG model ($M_1$) achieves genuinely higher classification accuracy and lower probabilistic Brier error than the Baseline ($M_0$).

We cross-verify this hypothesis using **four statistical tests**:
1. **Paired Student's $t$-Test on Classification Accuracy**: Tests whether mean correctness difference $\bar{d}^{\text{acc}} > 0$.
2. **Paired Student's $t$-Test on Brier Error Reduction**: Tests whether mean squared error reduction $\bar{d}^{\text{loss}} > 0$.
3. **McNemar's $\chi^2$ Test (with Continuity Correction)**: Specifically designed for paired binary classifiers using discordant counts $b$ ($M_0$ correct, $M_1$ wrong) and $c$ ($M_0$ wrong, $M_1$ correct):
   $$\chi^2 = \frac{(|b - c| - 1)^2}{b + c} \sim \chi^2_1$$
4. **Exact Monte Carlo Paired Permutation Test ($10,000$ random sign flips)**: A distribution-free test that randomly flips the sign of $d_i^{\text{acc}}$ under $H_0$ to compute the exact empirical $p$-value.

---

## 3. Observations, Decision, and Limitations

### 3.1 Held-Out Test Set Point Estimates ($N_{\text{test}} = 300$)

| Evaluation Metric | Baseline Model ($M_0$: Declared) | Improved Model ($M_1$: Bayesian NIG) | Observed Improvement ($\Delta$) |
|---|---|---|---|
| **Classification Accuracy** | `72.00%` (`0.7200`) | **`78.33%` (`0.7833`)** | **`+6.33%` (`+0.0633`)** |
| **Precision** | `71.94%` (`0.7194`) | **`81.44%` (`0.8144`)** | **`+9.50%` (`+0.0950`)** |
| **Recall** | `82.94%` (`0.8294`) | `80.00%` (`0.8000`) | `-2.94%` (`-0.0294`) |
| **F1-Score** | `0.7705` | **`0.8071`** | **`+0.0366`** |
| **ROC-AUC** | `0.7562` | **`0.8720`** | **`+0.1158`** |
| **Brier Score** *(Lower is Better)* | `0.1931` | **`0.1457`** | **`-0.0474` (24.5% error reduction)** |

### 3.2 Confidence Interval Estimates ($95\%$ Level)

| Performance Difference Metric | Mean Estimate | Analytical Student-$t$ 95% CI | Bootstrap Percentile 95% CI ($B=10,000$) | Contains Zero? |
|---|---|---|---|---|
| **$\Delta$ Accuracy ($M_1 - M_0$)** | **`+0.0633`** (`+6.33%`) | `[+0.0160, +0.1106]` | `[+0.0167, +0.1100]` | **No** (Strictly $> 0$) |
| **Brier Error Reduction ($\text{BS}_0 - \text{BS}_1$)** | **`+0.0474`** | `[+0.0306, +0.0642]` | `[+0.0307, +0.0645]` | **No** (Strictly $> 0$) |
| **$\Delta$ F1-Score ($M_1 - M_0$)** | **`+0.0366`** | — | `[-0.0020, +0.0758]` | Marginal at 95% |

**Interpretation of CIs**: Both the analytical Student-$t$ 95% CI (`[+1.60%, +11.06%]`) and the 10,000-sample Bootstrap 95% CI (`[+1.67%, +11.00%]`) for $\Delta \text{Accuracy}$ lie **entirely above zero**. Even at the conservative lower bound of the 95% confidence interval, the Bayesian model improves accuracy by at least $+1.60\%$ and reduces Brier squared error by $+0.0306$.

### 3.3 Hypothesis Testing Results

| Statistical Test | Test Statistic | $p$-Value | Decision at $\alpha = 0.05$ |
|---|---|---|---|
| **1. Paired $t$-Test (Accuracy Gain)** | $t = 2.6356$ ($\text{df}=299$) | $p = 0.00442$ (`4.42e-03`) | **Reject $H_0$** ($p < 0.01$) |
| **2. Paired $t$-Test (Brier Loss Reduction)** | $t = 5.5466$ ($\text{df}=299$) | $p = 3.21 \times 10^{-8}$ (`3.21e-08`) | **Reject $H_0$** ($p < 0.0001$) |
| **3. McNemar's $\chi^2$ Test (Discordant Pairs)** | $\chi^2 = 6.1132$ ($c=36, b=17$) | $p = 0.01342$ (`1.34e-02`) | **Reject $H_0$** ($p < 0.05$) |
| **4. Exact Permutation Test ($10,000$ flips)** | $\bar{d}_{\text{obs}} = +0.0633$ | $p = 0.00540$ (`5.40e-03`) | **Reject $H_0$** ($p < 0.01$) |

**McNemar Contingency Breakdown ($N_{\text{test}} = 300$)**:
- Both models correct: `199` instances
- **Improved Model ($M_1$) correct, Baseline ($M_0$) wrong ($c$)**: **`36` instances**
- **Baseline ($M_0$) correct, Improved ($M_1$) wrong ($b$)**: **`17` instances**
- Both models wrong: `48` instances
- The Improved Bayesian model corrects more than **twice as many errors** ($36$ vs. $17$) as the baseline.

### 3.4 Final Statistical Decision
We **reject the null hypothesis $H_0$** at significance level $\alpha = 0.05$ across all four statistical tests ($p = 0.0044$ for paired $t$-test on accuracy, $p = 0.0134$ for McNemar's test, and $p = 3.21 \times 10^{-8}$ for Brier loss reduction).

**Conclusion**: The observed improvement of $+6.33\%$ in classification accuracy ($+11.58\%$ in ROC-AUC and $-24.5\%$ reduction in Brier error) achieved by the **Bayesian Normal-Inverse-Gamma model** is **statistically significant and reliable**, and is **not** due to random variation in the test sample.

### 3.5 Limitations
1. **Cold-Start Sample Size ($n < 2$ purchases)**: When a Gang first adds a new item and has fewer than 2 historical purchases, the Bayesian NIG posterior relies heavily on the prior $\mu_0 = \ln(D_0)$, so its performance converges toward the baseline until empirical history accumulates.
2. **Non-Stationarity & Concept Drift**: If a Gang's consumption regime changes abruptly (e.g., mid-semester vacations or exam week), the i.i.d. log-normal assumption on intervals is temporarily violated until our **CUSUM drift filter** (`core/drift.py`) resets the prior.
3. **Synthetic Ground-Truth Generative Assumptions**: While our dataset models realistic Gamma inter-purchase intervals and systematic human prior bias, real-world deployment may encounter external stockouts or bulk multi-pack purchases not captured in a fixed unit size.

---

## 4. Where Probability and Statistics Are Used in This Project

| Component / File | Probabilistic & Statistical Concepts Applied |
|---|---|
| **1. Data & Interval Modeling (`core/simulator.py`)** | **Method of Moments & Gamma Distribution**: Inter-purchase intervals $T > 0$ are modeled via $\text{Gamma}(k, \theta)$ where $k = (\mu/\sigma)^2$ and $\theta = \sigma^2/\mu$. |
| **2. Improved ML Feature Engine (`core/bayesian_model.py`)** | **Conjugate Bayesian Inference (Normal-Inverse-Gamma → Student-$t$)**: Models log-intervals $Y = \ln(T) \sim \mathcal{N}(\mu, \sigma^2)$ with an NIG prior $(\mu_0, \kappa_0, \alpha_0, \beta_0)$ and derives the exact posterior predictive Student-$t$ distribution $t_{2\alpha_n}$ to account for both parameter uncertainty and observation noise. |
| **3. Survival Hazard Modeling (`core/survival_model.py`)** | **Weibull Survival Analysis & Right-Censoring**: Treats currently open intervals as right-censored observations ($E=0$) and computes conditional depletion hazard $1 - S(t + \Delta t)/S(t)$. |
| **4. User Acceptance Modeling (`core/response_model.py`)** | **Beta-Binomial Conjugate Smoothing**: Models roommate response rates with a $\text{Beta}(\alpha_0=2, \beta_0=2)$ prior updated with empirical `YES`/`NO` counts. |
| **5. Economic Decision Rule (`core/decision.py`, `core/bandit.py`)** | **Expected Utility Maximization & Thompson Sampling**: Derives optimal alert threshold $\tau^* = \frac{C}{C + B}$ and explores discrete thresholds via Beta-posterior Thompson Sampling. |
| **6. Regime Shift Monitoring (`core/drift.py`)** | **Page's Two-Sided CUSUM Control Chart**: Tracks standardized residuals $z_t = (x_t - \mu_0)/\sigma_0$ to detect consumption acceleration or slowdown. |
| **7. Model Evaluation (`evaluate_hypothesis_test.py`)** | **Brier Proper Scoring Rule, Paired Bootstrap Resampling ($B=10,000$), Student-$t$ Confidence Intervals, Paired $t$-Test, McNemar's $\chi^2$ Test, and Monte Carlo Permutation Testing**. |
