"""
api/routers/items.py — Per-item analytics and stats endpoints.

Endpoints:
  GET  /gangs/{gang_id}/items/{item_id}/stats        → P(need), elapsed days, model comparison
  GET  /gangs/{gang_id}/items/{item_id}/survival     → S(t) curve data for Plotly chart
  POST /gangs/{gang_id}/items/{item_id}/purchase     → manually record a purchase event
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from core.db import get_db_session, Item, User
from core.gangs import get_gang_items, get_item_purchases
from core.need_model import get_elapsed_days, compute_historical_intervals, p_need_declared_schedule, p_need_rolling_average
from core.bayesian_model import p_need_bayesian
from core.survival_model import p_need_survival, fit_weibull_model, prepare_survival_data
from core.drift import CUSUMDriftDetector

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ItemStatsOut(BaseModel):
    item_id: int
    item_name: str
    declared_interval_days: float
    elapsed_days: float
    purchase_count: int
    p_need_declared: float
    p_need_rolling: float
    p_need_bayesian: float
    p_need_survival: float
    best_estimate: float   # Bayesian (lowest Brier score in backtest)
    drift_detected: bool = False
    drift_type: Optional[str] = None
    cusum_pos: float = 0.0
    cusum_neg: float = 0.0


class SurvivalPoint(BaseModel):
    t: float        # days since last purchase
    survival: float # S(t) probability


class SurvivalDataOut(BaseModel):
    item_id: int
    item_name: str
    declared_interval_days: float
    elapsed_days: float
    curve: List[SurvivalPoint]


class RecordPurchaseRequest(BaseModel):
    buyer_id: Optional[int] = Field(None, description="User ID of the buyer (optional)")
    price: float = Field(default=0.0, ge=0)
    purchased_at: Optional[str] = Field(None, description="ISO datetime string; defaults to now")


class PurchaseOut(BaseModel):
    id: int
    item_id: int
    price: float
    purchased_at: str


# ---------------------------------------------------------------------------
# GET /gangs/{gang_id}/items/{item_id}/stats
# ---------------------------------------------------------------------------

@router.get(
    "/{gang_id}/items/{item_id}/stats",
    response_model=ItemStatsOut,
    tags=["Items"],
)
def get_item_stats(gang_id: int, item_id: int):
    """
    Run all four need models for a single item and return their probabilities.
    The frontend uses this to draw the probability gauge cards.
    """
    with get_db_session() as session:
        item = session.query(Item).filter(Item.id == item_id, Item.gang_id == gang_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found in gang {gang_id}")

        purchases = get_item_purchases(session, item_id)
        now = datetime.utcnow()

        if purchases:
            elapsed = get_elapsed_days(now, purchases[-1].purchased_at)
        else:
            elapsed = get_elapsed_days(now, item.created_at)

        intervals = compute_historical_intervals(purchases)

        p_dec = p_need_declared_schedule(elapsed, item.declared_interval_days)
        p_roll = p_need_rolling_average(elapsed, item.declared_interval_days, intervals)
        p_bayes = p_need_bayesian(elapsed, item.declared_interval_days, intervals)
        p_surv = p_need_survival(elapsed, item.declared_interval_days, intervals)

        # Run Two-Sided Page's CUSUM Drift Detector on historical intervals
        detector = CUSUMDriftDetector(
            baseline_mean=item.declared_interval_days,
            baseline_std=max(0.5, item.declared_interval_days * 0.35),
        )
        drift_state = None
        for iv in intervals:
            if iv > 0:
                drift_state = detector.step(iv)

        return ItemStatsOut(
            item_id=item.id,
            item_name=item.name,
            declared_interval_days=item.declared_interval_days,
            elapsed_days=round(elapsed, 2),
            purchase_count=len(purchases),
            p_need_declared=round(p_dec, 4),
            p_need_rolling=round(p_roll, 4),
            p_need_bayesian=round(p_bayes, 4),
            p_need_survival=round(p_surv, 4),
            best_estimate=round(p_bayes, 4),
            drift_detected=drift_state.drift_detected if drift_state else False,
            drift_type=drift_state.drift_type if drift_state else None,
            cusum_pos=round(drift_state.s_pos, 2) if drift_state else 0.0,
            cusum_neg=round(drift_state.s_neg, 2) if drift_state else 0.0,
        )


# ---------------------------------------------------------------------------
# GET /gangs/{gang_id}/items/{item_id}/survival
# ---------------------------------------------------------------------------

@router.get(
    "/{gang_id}/items/{item_id}/survival",
    response_model=SurvivalDataOut,
    tags=["Items"],
)
def get_survival_curve(gang_id: int, item_id: int):
    """
    Return S(t) values from t=0 to 2x the declared interval.
    Used by the frontend Plotly chart to draw the survival curve.
    """
    with get_db_session() as session:
        item = session.query(Item).filter(Item.id == item_id, Item.gang_id == gang_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found in gang {gang_id}")

        purchases = get_item_purchases(session, item_id)
        now = datetime.utcnow()
        elapsed = get_elapsed_days(now, purchases[-1].purchased_at) if purchases else 0.0
        intervals = compute_historical_intervals(purchases)

        # Fit Weibull model for S(t) curve
        fallback_mean = item.declared_interval_days
        dataset = prepare_survival_data(intervals, elapsed)
        wf = fit_weibull_model(dataset, fallback_mean)

        # Sample S(t) at 60 evenly spaced points
        max_t = item.declared_interval_days * 2.5
        step = max_t / 60
        curve = []
        for i in range(61):
            t = round(i * step, 2)
            s = float(wf.survival_function_at_times([t]).iloc[0])
            curve.append(SurvivalPoint(t=t, survival=round(s, 4)))

        return SurvivalDataOut(
            item_id=item.id,
            item_name=item.name,
            declared_interval_days=item.declared_interval_days,
            elapsed_days=round(elapsed, 2),
            curve=curve,
        )


# ---------------------------------------------------------------------------
# POST /gangs/{gang_id}/items/{item_id}/purchase — record a real purchase
# ---------------------------------------------------------------------------

@router.post(
    "/{gang_id}/items/{item_id}/purchase",
    response_model=PurchaseOut,
    status_code=201,
    tags=["Items"],
)
def record_purchase(gang_id: int, item_id: int, body: RecordPurchaseRequest):
    """
    Record a manual purchase event (e.g., user physically bought the item).
    This feeds the Bayesian model with real interval data.
    """
    with get_db_session() as session:
        item = session.query(Item).filter(Item.id == item_id, Item.gang_id == gang_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found in gang {gang_id}")

        purchased_at = datetime.utcnow()
        if body.purchased_at:
            try:
                purchased_at = datetime.fromisoformat(body.purchased_at)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO format.")

        from core.gangs import record_purchase as _record
        from core.db import PurchaseRequest, RequestResponse
        purchase = _record(
            session,
            item_id=item_id,
            purchased_at=purchased_at,
            price=body.price,
            buyer_id=body.buyer_id,
        )

        # Auto-resolve any open PENDING order requests for this item so no one orders it again
        if not body.purchased_at:
            open_reqs = (
                session.query(PurchaseRequest)
                .filter(
                    PurchaseRequest.item_id == item_id,
                    PurchaseRequest.status == "PENDING",
                )
                .all()
            )
            for req in open_reqs:
                req.status = "ACCEPTED"
                req.resolved_at = purchased_at
                if body.buyer_id:
                    session.add(
                        RequestResponse(
                            request_id=req.id,
                            user_id=body.buyer_id,
                            action="YES",
                            responded_at=purchased_at,
                        )
                    )

        session.commit()

        return PurchaseOut(
            id=purchase.id,
            item_id=purchase.item_id,
            price=purchase.price,
            purchased_at=purchase.purchased_at.isoformat(),
        )

