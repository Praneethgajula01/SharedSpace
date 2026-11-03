# SharedSpace 🛒🥛

**Intelligent Shared-Living Management & Automated Grocery Replenishment for Hostels & Roommate Gangs**

SharedSpace replaces rigid subscription timers with an autonomous, probability-driven grocery replenishment and bill-splitting system built specifically for hostellers and roommate groups (**Gangs**).

---

## 1. The Core Problem & Solution

Hostellers and roommates share the same recurring staples (milk, bread, eggs, coffee, drinking water cans), which leads to four constant problems:
1. **Unpredictable Stockouts**: Fixed timers (*"buy milk every 2 days"*) fail because human consumption fluctuates wildly between exam weeks and weekends.
2. **Double-Buying & Group Friction**: Either two roommates buy the same item on the way back, or nobody buys it assuming someone else did.
3. **Alert Fatigue**: Apps that spam notifications get muted.
4. **Messy Bill Splits**: Tracking who owes whom after dozens of shared grocery runs creates circular debt confusion.

### How SharedSpace Solves It:
- **Gangs & Declared Priors**: Roommates form a **Gang**, add their members, and register shared groceries with an initial estimate (e.g., *"Milk usually lasts 3 days"*). This estimate acts strictly as a **Bayesian Prior**, not a static rule.
- **Silent Background Learning**: An autonomous background scanner continuously tracks elapsed time and updates depletion probability $P(\text{need now})$ using actual purchase intervals while keeping all complex math completely invisible to the user.
- **Shared Order Requests (`Order Milk?`)**: When an item is about to run out, a single clean request pops up in the Gang's **Order Requests** tab.
- **First-Member Approval & Zero Redundant Orders**: As soon as **any one roommate** clicks **"Yes, Order Now"**, the system atomically locks the request (`PENDING` → `ACCEPTED`), places the order on behalf of the Gang (`#SS-ORD-xxxxx`), blocks duplicate orders from other roommates, and automatically splits the bill equally across the Gang.

---

## 2. System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                  REACT FRONTEND (Vite · Port 5173)                      │
│  Student Dark-Glass UI (Login → My Gangs → Gang Workspace)              │
│   ├── Order Requests Tab   (Approve / Remind Later / We Still Have It)  │
│   ├── Groceries & Roommates (Stock status badges, Offline buy logger)   │
│   └── Split Bills Tab       (Net balances & minimum debt settlements)   │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ REST / JSON (Axios)
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                 FASTAPI BACKEND (Uvicorn · Port 8000)                   │
│  • Autonomous Background Scanner (runs every 30s across all Gangs)      │
│  • /gangs      → Gang creation, roommate enrollment, item registration  │
│  • /requests   → Order request state machine, 0-duplicate lock, receipt │
│  • /items      → Real-time depletion estimation & offline buy logging   │
│  • /expenses   → Equal cost splitting & greedy bilateral settlements    │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                STATISTICAL & MACHINE LEARNING ENGINE                    │
│  1. Bayesian Normal-Inverse-Gamma (NIG) Model (Student-t predictive)    │
│  2. Weibull Survival Analysis (Right-censored open interval hazard)     │
│  3. Economic Cost-Benefit Gate (τ* = Annoyance / (Annoyance + Benefit)) │
│  4. Thompson Sampling Multi-Armed Bandit (Adaptive threshold tuning)    │
│  5. Two-Sided Page's CUSUM Filter (Habit drift & regime shift detection)│
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Statistical & ML Pipeline (Under the Hood)

| Module | File | Purpose |
|---|---|---|
| **Baseline Heuristics** | `core/need_model.py` | Declared schedule baseline $\min(1, \Delta t / D)$ and rolling-window average. |
| **Bayesian NIG Model** | `core/bayesian_model.py` | Conjugate Normal-Inverse-Gamma update on log-intervals $Y = \ln(T)$ with posterior predictive Student-$t$ CDF (**Best Walk-Forward Brier Score: `0.0535`** vs `0.2692` baseline). |
| **Weibull Survival** | `core/survival_model.py` | Parametric survival curve $S(t)$ treating open elapsed intervals as right-censored observations ($E=0$). |
| **Response Model** | `core/response_model.py` | Beta-Binomial conjugate smoothing + L2 regularized logistic regression for roommate acceptance probability. |
| **Economic Decision Gate** | `core/decision.py` | Utility threshold $\tau^* = \frac{C}{C + B}$ paired with a cooldown timer to prevent notification spam. |
| **Thompson Bandit** | `core/bandit.py` | Multi-armed bandit over candidate thresholds $\tau \in \{0.20, 0.35, 0.50, 0.65, 0.80\}$ using Beta posteriors. |
| **CUSUM Drift Detector** | `core/drift.py` | Two-sided Page's CUSUM control chart detecting consumption acceleration (exam weeks) or slowdown (vacations). |
| **Booking & Debt Ledger** | `core/booking.py`, `core/expenses.py` | Mock quick-commerce order execution (`#SS-ORD-xxxxx`), equal split calculation, and minimum-transfer debt simplification. |

---

## 4. Tech Stack

- **Frontend**: `React 19`, `Vite`, `React Router v7`, `Axios`, Custom Dark-Glass CSS Design System (`Plus Jakarta Sans`)
- **Backend API**: `FastAPI`, `Uvicorn`, `Pydantic v2`, `asyncio` background task runner
- **Statistical & ML Engine**: `numpy`, `scipy`, `pandas`, `statsmodels`, `lifelines`, `scikit-learn`
- **Database & ORM**: `SQLAlchemy 2.0` (`SQLite` with `PRAGMA foreign_keys=ON` for local dev; `PostgreSQL` ready via `DATABASE_URL`)
- **Testing**: `pytest` + `FastAPI TestClient` (unit + end-to-end integration tests)

---

## 5. Repository Structure

```text
SharedSpace/
├── api/
│   ├── main.py                 # FastAPI app, CORS, DB lifespan, 30s autonomous scanner
│   └── routers/
│       ├── gangs.py            # POST /gangs, GET /gangs/{id}, add members & items
│       ├── requests.py         # Order requests, YES/NO/SNOOZE lock, receipts, bandit
│       ├── items.py            # Per-item Bayesian/Weibull stats, survival curve, purchases
│       └── expenses.py         # Net balances & simplified bilateral debt settlements
├── frontend/
│   ├── src/
│   │   ├── api/client.js       # Central Axios API client
│   │   ├── pages/
│   │   │   ├── Login.jsx       # Passwordless student sign-in portal
│   │   │   ├── GangList.jsx    # My Gangs directory & Join/Create workspace
│   │   │   └── GangDashboard.jsx # Main Gang workspace (Requests, Groceries, Split Bills)
│   │   ├── components/
│   │   │   ├── RequestCard.jsx    # Clean "Order {Item}?" prompt & order receipt card
│   │   │   ├── ItemHealthCard.jsx # Grocery status card (Stocked / Running Low / Almost Empty)
│   │   │   ├── ExpenseLedger.jsx  # Net balances & "How to Settle Up" view
│   │   │   └── SurvivalChart.jsx  # Weibull survival curve S(t) SVG visualization
│   │   └── index.css           # Student dark-glass design system
│   └── package.json
├── core/
│   ├── db.py                   # SQLAlchemy ORM models (User, Gang, Membership, Item, PurchaseRequest)
│   ├── gangs.py                # Gang, member, item, and purchase CRUD operations
│   ├── requests.py             # First-decisive-response state machine & expiration
│   ├── simulator.py            # Gamma distribution synthetic gang simulator
│   ├── simulation_dynamics.py  # Drift, weekend multipliers, and user response simulation
│   ├── need_model.py           # Baseline schedule & rolling average heuristics
│   ├── bayesian_model.py       # Conjugate Normal-Inverse-Gamma need model
│   ├── survival_model.py       # Weibull survival analysis with right-censoring
│   ├── evaluation.py           # Walk-forward backtesting, Brier score, log-loss, calibration
│   ├── response_model.py       # Beta-Binomial & logistic acceptance model
│   ├── decision.py             # Cost-benefit threshold & cooldown gating
│   ├── bandit.py               # Thompson Sampling threshold bandit
│   ├── drift.py                # Two-sided CUSUM habit drift detector
│   ├── booking.py              # Mock instant grocery order booking API
│   └── expenses.py             # Equal expense splitting & debt simplification algorithm
├── tests/
│   ├── test_foundation.py      # Database, ORM, and state machine unit tests
│   └── test_api_e2e.py         # Full end-to-end API & 0-duplicate order workflow test
├── LEARNING_NOTES.md           # Step-by-step mathematical & architectural notes
├── PROGRESS.md                 # Project milestone checklist (Steps 1–22 completed)
└── requirements.txt            # Python dependencies
```

---

## 6. Quickstart (Run Full Stack Locally)

### 1. Clone & Install Backend Dependencies
```bash
git clone https://github.com/Praneethgajula01/SharedSpace.git
cd SharedSpace
pip install -r requirements.txt
pip install fastapi uvicorn httpx
```

### 2. Start the FastAPI Backend (Port 8000)
```bash
python -m uvicorn api.main:app --port 8000 --reload
```
- **API Server**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`

### 3. Start the React Frontend (Port 5173)
Open a second terminal:
```bash
cd frontend
npm install
npm run dev
```
- **Web App**: `http://localhost:5173`

### 4. Run Automated Test Suite
```bash
pytest -v tests/
```
