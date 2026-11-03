"""
api/routers/requests.py — Endpoints for purchase request alerts, group approval, and auto-booking.

Endpoints:
  GET  /gangs/{gang_id}/requests                     → list active PENDING alerts
  GET  /gangs/{gang_id}/requests/history             → recent resolved requests (with order receipts & approver name)
  POST /gangs/{gang_id}/requests/{req_id}/respond    → any gang member approves (YES), snoozes, or rejects (NO)
  POST /gangs/{gang_id}/check-and-trigger            → run Bayesian model, fire alert if P(need) high
  GET  /gangs/{gang_id}/bandit                       → inspect Thompson Sampling bandit arms
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import numpy as np

from core.db import get_db_session, Item, PurchaseRequest, RequestResponse, User
from core import requests as req_ops
from core.gangs import get_gang_items, get_item_purchases, record_purchase
from core.need_model import get_elapsed_days, compute_historical_intervals
from core.bayesian_model import p_need_bayesian
from core.decision import should_trigger_request, UtilityConfig
from core.booking import mock_place_order
from core.bandit import ThompsonThresholdBandit

router = APIRouter()

# Per-gang Thompson Sampling Bandit instances & Order Receipt store
_BANDITS: Dict[int, ThompsonThresholdBandit] = {}
_RECEIPTS: Dict[int, dict] = {}


def get_gang_bandit(gang_id: int) -> ThompsonThresholdBandit:
    if gang_id not in _BANDITS:
        _BANDITS[gang_id] = ThompsonThresholdBandit()
    return _BANDITS[gang_id]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RespondRequest(BaseModel):
    user_id: int = Field(..., description="ID of the responding gang member")
    action: str = Field(..., description="One of: YES, NO, SNOOZE")


class OrderReceiptOut(BaseModel):
    order_id: str
    item_name: str
    unit_price: float
    delivery_fee: float
    total_amount: float
    estimated_delivery_time: str
    approved_by: str
    status: str


class RequestOut(BaseModel):
    id: int
    item_id: int
    item_name: str
    item_unit: str
    item_price: float
    gang_id: int
    status: str
    p_need_at_creation: float
    created_at: str
    resolved_at: Optional[str] = None
    decided_by_name: Optional[str] = None
    order_receipt: Optional[OrderReceiptOut] = None


class TriggerCheckResponse(BaseModel):
    item_id: int
    item_name: str
    p_need: float
    elapsed_days: float
    threshold_used: float
    triggered: bool
    reason: str
    request_id: Optional[int] = None


class BanditArmOut(BaseModel):
    tau: float
    expected_reward: float
    pulls: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_request_out(req: PurchaseRequest, session) -> RequestOut:
    """Convert a PurchaseRequest ORM object to a rich response dict including who responded and order receipt."""
    item = session.query(Item).filter(Item.id == req.item_id).first()
    item_name = item.name if item else "Unknown"
    item_unit = item.unit if item else "unit"
    item_price = item.price if item and item.price > 0 else 50.0

    # Find who cast the decisive response (if resolved)
    decided_by_name = None
    resp = (
        session.query(RequestResponse)
        .filter(RequestResponse.request_id == req.id)
        .order_by(RequestResponse.responded_at.asc())
        .first()
    )
    if resp:
        u = session.query(User).filter(User.id == resp.user_id).first()
        if u:
            decided_by_name = u.name

    # Build or retrieve order receipt if ACCEPTED
    receipt = None
    if req.status == "ACCEPTED":
        if req.id not in _RECEIPTS:
            # Generate deterministic receipt seeded by request ID so it stays consistent across refreshes
            rng = np.random.default_rng(seed=req.id + 1000)
            booking = mock_place_order(
                item_id=req.item_id,
                item_name=item_name,
                quantity=1,
                base_price=item_price,
                current_time=req.resolved_at or datetime.utcnow(),
                rng=rng,
            )
            _RECEIPTS[req.id] = {
                "order_id": booking.order_id,
                "item_name": booking.item_name,
                "unit_price": booking.unit_price,
                "delivery_fee": booking.delivery_fee,
                "total_amount": booking.total_amount,
                "estimated_delivery_time": booking.estimated_delivery_time.isoformat(),
                "approved_by": decided_by_name or "Gang Member",
                "status": booking.status,
            }
        receipt = OrderReceiptOut(**_RECEIPTS[req.id])

    return RequestOut(
        id=req.id,
        item_id=req.item_id,
        item_name=item_name,
        item_unit=item_unit,
        item_price=item_price,
        gang_id=req.gang_id,
        status=req.status,
        p_need_at_creation=req.p_need_at_creation,
        created_at=req.created_at.isoformat(),
        resolved_at=req.resolved_at.isoformat() if req.resolved_at else None,
        decided_by_name=decided_by_name,
        order_receipt=receipt,
    )


def scan_gang_items(session, gang_id: int) -> List[TriggerCheckResponse]:
    """
    Scan all items in a gang using the Bayesian NIG model + Cost-Benefit gate.
    Creates PENDING requests for items that need replenishment (0 duplicates allowed).
    """
    utility = UtilityConfig()  # tau* = 0.25 baseline
    results: List[TriggerCheckResponse] = []
    items = get_gang_items(session, gang_id)
    now = datetime.utcnow()

    for item in items:
        purchases = get_item_purchases(session, item.id)

        if purchases:
            elapsed = get_elapsed_days(now, purchases[-1].purchased_at)
        else:
            elapsed = get_elapsed_days(now, item.created_at)

        intervals = compute_historical_intervals(purchases)
        p_need = p_need_bayesian(
            elapsed_days=elapsed,
            declared_interval_days=item.declared_interval_days,
            historical_intervals=intervals,
        )

        # Check if there is already a PENDING request (0-redundancy guard)
        existing_pending = (
            session.query(PurchaseRequest)
            .filter(
                PurchaseRequest.item_id == item.id,
                PurchaseRequest.status == "PENDING",
            )
            .first()
        )
        if existing_pending:
            results.append(
                TriggerCheckResponse(
                    item_id=item.id,
                    item_name=item.name,
                    p_need=round(p_need, 4),
                    elapsed_days=round(elapsed, 2),
                    threshold_used=0.25,
                    triggered=False,
                    reason="ALREADY_PENDING",
                    request_id=existing_pending.id,
                )
            )
            continue

        last_req = (
            session.query(PurchaseRequest)
            .filter(PurchaseRequest.item_id == item.id)
            .order_by(PurchaseRequest.created_at.desc())
            .first()
        )
        last_prompted_at = last_req.created_at if last_req else None

        should_trigger, reason_code, threshold = should_trigger_request(
            p_need=p_need,
            current_time=now,
            last_prompted_at=last_prompted_at,
            utility=utility,
        )

        request_id = None
        if should_trigger:
            new_req = req_ops.create_purchase_request(session, item.id, p_need)
            session.commit()
            request_id = new_req.id

        results.append(
            TriggerCheckResponse(
                item_id=item.id,
                item_name=item.name,
                p_need=round(p_need, 4),
                elapsed_days=round(elapsed, 2),
                threshold_used=round(threshold, 2),
                triggered=should_trigger,
                reason=reason_code,
                request_id=request_id,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{gang_id}/requests", response_model=List[RequestOut], tags=["Requests"])
def get_active_requests(gang_id: int):
    """Return all PENDING purchase requests for a gang — shown in the Requests section."""
    with get_db_session() as session:
        req_ops.expire_stale_requests(session)
        session.commit()
        active = req_ops.get_active_requests_for_gang(session, gang_id)
        return [_build_request_out(r, session) for r in active]


@router.get("/{gang_id}/requests/history", response_model=List[RequestOut], tags=["Requests"])
def get_request_history(gang_id: int):
    """Return resolved requests (approved orders, snoozed, rejected) ordered newest first."""
    with get_db_session() as session:
        from sqlalchemy import desc
        history = (
            session.query(PurchaseRequest)
            .filter(
                PurchaseRequest.gang_id == gang_id,
                PurchaseRequest.status != "PENDING",
            )
            .order_by(desc(PurchaseRequest.resolved_at), desc(PurchaseRequest.created_at))
            .limit(50)
            .all()
        )
        return [_build_request_out(r, session) for r in history]


@router.post(
    "/{gang_id}/requests/{request_id}/respond",
    response_model=RequestOut,
    tags=["Requests"],
)
def respond_to_request(gang_id: int, request_id: int, body: RespondRequest):
    """
    Any member of the gang responds (YES / NO / SNOOZE).
    - First YES locks the request (0 duplicate orders), places the mock order,
      and records the purchase in the Expense Ledger under that member's name.
    - Updates the gang's Thompson Sampling Bandit with the feedback.
    """
    with get_db_session() as session:
        try:
            updated = req_ops.respond_to_request(
                session,
                request_id=request_id,
                user_id=body.user_id,
                action=body.action,
            )
            bandit = get_gang_bandit(gang_id)

            if updated.status == "ACCEPTED":
                item = session.query(Item).filter(Item.id == updated.item_id).first()
                user = session.query(User).filter(User.id == body.user_id).first()
                base_price = item.price if item and item.price > 0 else 50.0

                # Place order via mock booking engine
                rng = np.random.default_rng(seed=updated.id + 1000)
                booking = mock_place_order(
                    item_id=updated.item_id,
                    item_name=item.name if item else "Item",
                    quantity=1,
                    base_price=base_price,
                    current_time=updated.resolved_at or datetime.utcnow(),
                    rng=rng,
                )
                _RECEIPTS[updated.id] = {
                    "order_id": booking.order_id,
                    "item_name": booking.item_name,
                    "unit_price": booking.unit_price,
                    "delivery_fee": booking.delivery_fee,
                    "total_amount": booking.total_amount,
                    "estimated_delivery_time": booking.estimated_delivery_time.isoformat(),
                    "approved_by": user.name if user else "Gang Member",
                    "status": booking.status,
                }

                # Record the purchase in the ledger with the exact booked total amount
                record_purchase(
                    session,
                    item_id=updated.item_id,
                    price=booking.total_amount,
                    buyer_id=body.user_id,
                )
                bandit.update(updated.p_need_at_creation, accepted=True)
            elif updated.status == "REJECTED":
                bandit.update(updated.p_need_at_creation, accepted=False)

            session.commit()
            return _build_request_out(updated, session)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{gang_id}/check-and-trigger",
    response_model=List[TriggerCheckResponse],
    tags=["Requests"],
)
def check_and_trigger(gang_id: int):
    """Run the Bayesian need scanner for all items in the gang and trigger pending requests."""
    with get_db_session() as session:
        return scan_gang_items(session, gang_id)


@router.get(
    "/{gang_id}/bandit",
    response_model=List[BanditArmOut],
    tags=["Requests"],
)
def get_bandit_status(gang_id: int):
    """Return Thompson Sampling Bandit threshold arms and their learned reward probabilities."""
    bandit = get_gang_bandit(gang_id)
    return [
        BanditArmOut(tau=tau, expected_reward=reward, pulls=pulls)
        for tau, reward, pulls in bandit.get_summary()
    ]
