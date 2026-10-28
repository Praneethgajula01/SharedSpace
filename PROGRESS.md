# SharedSpace — Step-by-Step Roadmap & Progress

## Milestones & Checklist

### Foundation & Data Layer
- [x] **Step 1: Environment & Project Scaffolding** (Repo setup, dependencies, structure)
- [ ] **Step 2: Database Engine & Session Management** (`core/db.py`)
- [ ] **Step 3: Core Relational Schema** (Gangs, Users, Memberships, Items in `core/db.py` & `core/gangs.py`)
- [ ] **Step 4: Request State Machine** (`core/requests.py`)
- [ ] **Step 5: Foundation Integration Tests** (`tests/test_foundation.py`)

### Simulation & Synthetic Data
- [ ] **Step 6: Synthetic Gang & Purchase Simulator** (`core/simulator.py`)
- [ ] **Step 7: Simulating Noise, Wrong Priors, Drift & Responses**

### Need Model (Probability & Survival)
- [ ] **Step 8: Baseline Heuristics** (Declared schedule & rolling averages)
- [ ] **Step 9: Bayesian Interval Model** (Normal-Inverse-Gamma on log-intervals)
- [ ] **Step 10: Survival Analysis Model** (Weibull hazard & open interval censoring)
- [ ] **Step 11: Calibration & Evaluation** (Brier score, reliability curves)

### Decision & Economics
- [ ] **Step 12: Response Probability Model** (Beta-Binomial & logistic regression)
- [ ] **Step 13: Cost-Benefit Decision Rule** (Threshold $\tau = \frac{\text{annoyance}}{\text{annoyance} + \text{benefit}}$)
- [ ] **Step 14: Dynamic Tuning & Bandit Exploration** (Thompson sampling)
- [ ] **Step 15: Habit Drift Detection** (CUSUM filter)

### Application & Workflow
- [ ] **Step 16: Mock Booking API & Expense Splitting** (`core/booking.py`, `core/expenses.py`)
- [ ] **Step 17: Interactive Streamlit UI** (Inbox, gang dashboard, item triggers)
- [ ] **Step 18: Visualizations & Analytics** (Survival curves, drift monitor, split ledger)
- [ ] **Step 19: Comprehensive Testing & Final Polish**
