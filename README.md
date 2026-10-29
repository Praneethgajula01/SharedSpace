# SharedSpace 🛒🥛

**Intelligent Shared-Living Management & Automated Grocery Replenishment**

SharedSpace replaces rigid calendar timers with an adaptive, probability-driven replenishment engine for hostels and shared apartments.

---

## 1. The Core Idea

Hostellers and roommates consume the same daily staples repeatedly (milk, bread, eggs, drinking water cans). 

- **The Problem**: Fixed schedules (e.g. *"buy milk every 2 days"*) fail because consumption is inherently stochastic. Exam weeks double coffee intake, weekend trips drop demand to zero, and flatmates forget who bought what.
- **The SharedSpace Solution**: 
  - Roommates join a **Gang** (room group, floor wing, mess club).
  - Members add recurring **Items** with an initial rough estimate (e.g. *"milk every 2 days"*). This declared frequency is treated strictly as an initial **Bayesian prior**, not an inflexible rule.
  - The system observes actual purchase timestamps and continuously calculates $P(\text{need now})$.
  - When $P(\text{need})$ crosses an annoyance-vs-utility threshold, it broadcasts a lightweight alert: *"Milk is likely empty. Book it?"*
  - **First-Decisive Action**: If *any one* flatmate taps **Yes**, the order is booked (mocked) and the expense is evenly split.
  - Every action—**Yes**, **No**, **Snooze**, or **Ignore**—acts as direct feedback that teaches the system when to ask, what to ask, and how often.

---

## 2. Statistical & Machine Learning Architecture

SharedSpace focuses on practical applied statistics and survival analysis rather than naive rule engines:

```
[Declared Prior Schedule] + [Observed Purchase History]
                        │
                        ▼
           1. Inter-Purchase Need Model
           P(need now | days elapsed, history, prior)
           - Continuous Gamma intervals (non-negative, right-skewed)
           - Bayesian Normal-Inverse-Gamma updating on log-intervals
           - Weibull Survival Analysis with right-censoring
                        │
                        ▼
           2. Response Model P(Yes | features)
           - Beta-Binomial per user-item
           - Logistic regression on prompt timing & elapsed time
                        │
                        ▼
           3. Economic Decision Rule
           Ask only if: P(need) * Benefit - (1 - P(need)) * Annoyance > 0
           Threshold: τ* = Annoyance / (Annoyance + Benefit)
           - Cooldown timers & Thompson sampling exploration
           - CUSUM filter for detecting lifestyle drift (e.g. exams)
                        │
                        ▼
           4. Booking & Feedback Loop
           Mock API booking -> Expense split -> Feedback updates priors
```

### Key Statistical Techniques
1. **Gamma Interval Modeling**:
   Inter-purchase intervals $T$ must be strictly positive ($T > 0$) and are right-skewed. We model them using continuous Gamma distributions $\text{Gamma}(k, \theta)$ parameterized from empirical moments ($\mu, \sigma$).
2. **Bayesian Conjugate Priors**:
   We model $\log(T)$ with a Normal-Inverse-Gamma prior. When purchase history is sparse (e.g. first week), the system leans on the human's declared prior. As purchases accumulate, empirical evidence gracefully overwhelms the prior.
3. **Survival Analysis & Censoring**:
   The current open interval (days elapsed since last purchase without an event yet) is a **right-censored** observation. We use Weibull hazard models via `lifelines` to compute the conditional probability $P(T \le t + \Delta t \mid T > t)$.
4. **Logistic Depletion & User Feedback**:
   Roommate acceptance is modeled via logistic response curves centered at the true depletion point, transitioning from rejections when prompted prematurely to high acceptance when stock is genuinely depleted.
5. **Habit Drift (CUSUM)**:
   A Cumulative Sum control chart monitors residual purchase gaps to flag regime shifts (e.g., permanent consumption increases during winter or exams).

---

## 3. Tech Stack

- **Statistical Modeling & ML**: `numpy`, `scipy`, `pandas`, `statsmodels`, `lifelines`, `scikit-learn`
- **Database & Persistence**: `SQLAlchemy 2.0` with `python-dotenv`
  - Zero-setup local development: **SQLite** (with foreign key PRAGMA enforcement)
  - Production / Cloud: **PostgreSQL** (Supabase / Neon compatible via `DATABASE_URL`)
- **Testing**: `pytest` using hermetic in-memory SQLite fixtures (`sqlite:///:memory:`)
- **Web Interface & Visualizations**: `Streamlit` and `Plotly`

---

## 4. Repository Structure

```text
sharedspace/
├── core/
│   ├── db.py                   # SQLAlchemy schema, foreign keys, session context
│   ├── gangs.py                # Users, gangs, memberships, and purchase history CRUD
│   ├── requests.py             # Request state machine (PENDING -> ACCEPTED/REJECTED/EXPIRED)
│   ├── simulator.py            # Synthetic purchase generator via Gamma distributions
│   ├── simulation_dynamics.py  # Habit drift, weekend demand, and logistic roommate responses
│   ├── need_model.py           # (Upcoming) Bayesian intervals & Weibull survival
│   ├── response_model.py       # (Upcoming) Beta-Binomial & logistic response model
│   ├── decision.py             # (Upcoming) Cost-benefit thresholds, cooldowns, CUSUM drift
│   ├── booking.py              # (Upcoming) Mock grocery booking API
│   └── expenses.py             # (Upcoming) Split ledger & debt resolution
├── tests/
│   └── test_foundation.py      # Integration tests with in-memory SQLite
├── notebooks/                  # Model evaluation, calibration & ablations
├── pages/                      # Multi-page Streamlit application
├── LEARNING_NOTES.md           # Progressive concept explanations
├── PROGRESS.md                 # Step-by-step roadmap checklist
├── PROJECT_BRIEF.md            # Original project requirements
├── .env.example                # Database URL template
└── requirements.txt            # Pinned dependencies
```

---

## 5. Quickstart

### Setup Environment
```bash
# Clone the repository
git clone https://github.com/Praneethgajula01/SharedSpace.git
cd SharedSpace

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run Tests
```bash
pytest -v tests/test_foundation.py
```

