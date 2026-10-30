# SharedSpace — Learning Notes

## Step 1: Environment & Project Scaffolding
- Virtual environments isolate Python packages so our project dependencies don't clash with system-wide packages.
- `.env` files keep secrets and database credentials local and out of Git via `.gitignore`.
- Setting a flexible `DATABASE_URL` abstraction lets our code seamlessly connect to SQLite for local tests and PostgreSQL for production.

## Step 2: Database Engine & Session Management
- SQLAlchemy translates Python objects to SQL commands, allowing our codebase to switch between SQLite and PostgreSQL without code changes.
- In SQLite, foreign keys are turned off by default; we enable them using an engine connect listener with `PRAGMA foreign_keys=ON`.
- Context managers (`with get_db_session() as session:`) guarantee that database transactions commit on success, roll back on errors, and always close cleanly.

## Step 3: Core Relational Schema & Interval Tracking
- Users and Gangs share a many-to-many relationship via a `memberships` join table with a unique `(gang_id, user_id)` constraint.
- Each `Item` holds a `declared_interval_days` float, representing the human's prior belief of how frequently they consume it.
- `PurchaseEvent` records the ground-truth timestamps whenever an item is bought; subtracting consecutive purchase timestamps yields the empirical random variable $T$ (inter-purchase interval).
- Setting `expire_on_commit=False` prevents `DetachedInstanceError` when accessing object attributes outside an active transaction.

## Step 4: Request State Machine & Feedback Loop
- Replenishment alerts follow a state machine: `PENDING` transitions to `ACCEPTED`, `REJECTED`, `SNOOZED`, or `EXPIRED`.
- The state transition operates under a "first decisive response wins" rule: once any roommate accepts, the request resolves and cannot be re-answered.
- Every response (YES, NO, SNOOZE) is permanently recorded in `request_responses` to serve as labeled ground truth for training the user response model $P(\text{Yes} \mid \text{features})$.
- Stale unattended requests automatically expire after a timeout window (e.g. 24h), capturing the implicit "ignored" signal.

## Step 5: Foundation Integration Tests
- In-memory SQLite fixtures (`sqlite:///:memory:`) provide isolated test runs with zero disk writes, fast execution, and zero cross-test pollution.
- Automated tests verify relational constraints (e.g., unique gang memberships), domain validations (positive intervals), and state machine locking.
- Explicit assertion on empirical inter-purchase intervals ensures that $\Delta t$ can be reliably computed from purchase timestamps.

## Step 6: Synthetic Purchase Simulator & Gamma Interval Modeling
- Purchase intervals are strictly positive and right-skewed; modeling them with a Normal distribution risks generating impossible negative intervals.
- The Gamma distribution $\text{Gamma}(k, \theta)$ maps naturally from mean $\mu$ and standard deviation $\sigma$ via shape $k = (\mu/\sigma)^2$ and scale $\theta = \sigma^2 / \mu$.
- The simulator allows us to configure synthetic ground-truth parameters ($\mu_{\text{true}}, \sigma_{\text{true}}$) alongside biased human declarations ($\mu_{\text{prior}}$), providing the benchmark to test Bayesian updating and survival curves.

## Step 7: Simulation Dynamics — Drift, Seasonality & User Feedback
- Real habits drift over time: we model regime shifts (e.g. exam periods) where the true mean interval shrinks by a drift factor (e.g. from 3.0 to 1.8 days).
- Weekend multipliers account for weekly acceleration in hostel grocery consumption.
- Simulated human response behavior follows a logistic sigmoid $P(\text{depleted}) = \sigma(\beta \cdot \frac{\tau - \mu}{\mu})$, transitioning smoothly from rejection when asked too early to enthusiastic acceptance when asked when stock is actually empty.

## Step 8: Baseline Need Heuristics
- Heuristic baselines form the benchmark against which Bayesian and survival models are evaluated.
- **Declared Schedule Baseline**: $P_{\text{declared}}(\text{need}) = \min(1.0, \frac{\Delta t}{D})$. It reflects user expectations but cannot adapt when humans misjudge consumption.
- **Rolling Moving Average Baseline**: $P_{\text{rolling}}(\text{need}) = \min(1.0, \frac{\Delta t}{\bar{T}})$. Uses the empirical mean of the last $k$ completed intervals, falling back to $D$ when history is empty.

## Step 9: Bayesian Interval Model (Normal-Inverse-Gamma on Log-Intervals)
- Taking $Y = \ln(T)$ maps positive intervals into $(-\infty, \infty)$, where the Normal distribution and its conjugate Normal-Inverse-Gamma (NIG) prior apply.
- The human's declared frequency initializes the prior mean $\mu_0 = \ln(D)$, while $\kappa_0$ acts as pseudo-observations (prior confidence).
- As purchases arrive, closed-form conjugate updates smoothly shift the posterior mean from the prior belief toward empirical reality.
- The posterior predictive distribution for a future log-interval follows a Student's $t$-distribution, giving an exact closed-form CDF for $P(\text{need now}) = F_t(\ln(\Delta t))$.

## Step 10: Survival Analysis & Right-Censoring (Weibull Model)
- Unlike completed historical intervals where purchases occurred ($E=1$), the current elapsed time since the last purchase is **right-censored** ($E=0$): we know the item has survived *at least* $\Delta t$ days without running out.
- The Weibull survival function $S(t) = P(T > t) = \exp(-(t/\lambda)^\rho)$ captures changing hazard rates over time ($\rho > 1$ represents "wear-out" or ongoing depletion).
- The conditional probability of replenishment in the upcoming time window $\Delta t_{\text{window}}$ given survival up to time $t$ is:
  $$P(T \le t + \Delta t_{\text{window}} \mid T > t) = 1 - \frac{S(t + \Delta t_{\text{window}})}{S(t)}$$

## Step 11: Calibration & Walk-Forward Evaluation (Brier Score)
- Classification accuracy cannot evaluate probabilities (a model outputting $0.51$ vs $0.99$ shouldn't be scored equally).
- The **Brier Score** $\text{BS} = \frac{1}{N}\sum (p_i - y_i)^2$ is a strictly proper scoring rule where $0.0$ is perfect and an uninformed $50/50$ coin flip scores $0.25$.
- In our sequential walk-forward backtest (where humans declared $2.0\text{ days}$ but true consumption was $3.5\text{ days}$):
  - Declared baseline performed poorly ($\text{BS} = 0.2692$) because it constantly triggered prematurely.
  - Bayesian NIG achieved the highest predictive accuracy ($\text{BS} = 0.0535$) by rapidly correcting the human bias.
