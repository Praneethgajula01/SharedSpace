# PROJECT: SharedSpace
Intelligent Shared-Living Management and Automated Grocery System.

## Core Idea
Hostellers buy the same daily items repeatedly (milk, eggs, bread, water cans). SharedSpace automates this.

- A user creates a GANG (roommates, floor group, mess group, friends). A user can belong to multiple gangs.
- Members add ITEMS to the gang with a declared frequency (e.g., "milk every 2 days"). This declared frequency serves only as an initial prior.
- The app watches actual purchase history and computes P(need now) for each item.
- When P(need) crosses an annoyance-vs-utility threshold, it sends a "Book it?" REQUEST to the gang.
- If ANY ONE member taps Yes, the order is booked (mocked), and the cost is split among the gang.
- Every Yes / No / Snooze / ignore provides feedback that refines when, what, and how often the system asks.

## Probability Pipeline
1. Need model: P(need now | days since last purchase, history, prior)
   - Gap between purchases = random variable T
   - Baselines: declared schedule, moving average of intervals
   - Bayesian interval model (Normal-Inverse-Gamma on log-intervals, declared frequency as prior)
   - Survival model (Weibull via lifelines, censored open interval)
2. Response model: P(Yes | ask features)
   - Beta-Binomial per user-item, followed by logistic regression
3. Decision rule: ask only if:
   P(need) * benefit - (1 - P(need)) * annoyance > 0
   Threshold: tau = annoyance / (annoyance + benefit)
   - Cooldowns, Thompson sampling to tune tau, CUSUM for habit drift
4. Booking (mock API) -> split cost -> feedback updates all models

## Tech Stack
Python, pandas, numpy, scipy, statsmodels, lifelines, scikit-learn, SQLAlchemy, Streamlit + Plotly, pytest.

