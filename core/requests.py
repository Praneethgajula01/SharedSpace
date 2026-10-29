"""
Request state machine and feedback handling for SharedSpace.
Governs the lifecycle: PENDING -> ACCEPTED | REJECTED | SNOOZED | EXPIRED.
First decisive user response transitions the request state.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from core.db import (
    Item,
    Membership,
    PurchaseRequest,
    RequestResponse,
    RequestStatus,
    UserAction,
)


def create_purchase_request(
    session: Session,
    item_id: int,
    p_need: float = 0.0
) -> PurchaseRequest:
    """
    Generate a new replenishment request for a gang.
    If a pending request already exists for this item, return it to prevent duplicate alerts.
    """
    item = session.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise ValueError(f"Item with id {item_id} does not exist.")

    # Check for an existing open request for this item
    existing = (
        session.query(PurchaseRequest)
        .filter(
            PurchaseRequest.item_id == item_id,
            PurchaseRequest.status == RequestStatus.PENDING.value
        )
        .first()
    )
    if existing:
        return existing

    request = PurchaseRequest(
        item_id=item.id,
        gang_id=item.gang_id,
        status=RequestStatus.PENDING.value,
        p_need_at_creation=float(p_need),
        created_at=datetime.utcnow()
    )
    session.add(request)
    session.flush()
    return request


def respond_to_request(
    session: Session,
    request_id: int,
    user_id: int,
    action: str,
    responded_at: Optional[datetime] = None
) -> PurchaseRequest:
    """
    Record user feedback (YES, NO, SNOOZE) and transition the request state.
    Raises ValueError if:
    - Request does not exist.
    - User is not a member of the gang.
    - Request is already resolved (first decisive action wins).
    """
    request = session.query(PurchaseRequest).filter(PurchaseRequest.id == request_id).first()
    if not request:
        raise ValueError(f"PurchaseRequest with id {request_id} not found.")

    # Verify membership
    is_member = (
        session.query(Membership)
        .filter(
            Membership.gang_id == request.gang_id,
            Membership.user_id == user_id
        )
        .first()
    ) is not None

    if not is_member:
        raise ValueError(f"User {user_id} is not a member of gang {request.gang_id}.")

    # Validate action
    action_upper = action.strip().upper()
    valid_actions = {a.value for a in UserAction}
    if action_upper not in valid_actions:
        raise ValueError(f"Invalid action '{action}'. Must be one of {valid_actions}.")

    # State Machine check: Only PENDING requests can accept responses
    if request.status != RequestStatus.PENDING.value:
        raise ValueError(
            f"Cannot respond: Request {request_id} is already '{request.status}'."
        )

    if responded_at is None:
        responded_at = datetime.utcnow()

    # 1. Store feedback for model training
    feedback = RequestResponse(
        request_id=request.id,
        user_id=user_id,
        action=action_upper,
        responded_at=responded_at
    )
    session.add(feedback)

    # 2. Transition request state
    if action_upper == UserAction.YES.value:
        request.status = RequestStatus.ACCEPTED.value
    elif action_upper == UserAction.NO.value:
        request.status = RequestStatus.REJECTED.value
    elif action_upper == UserAction.SNOOZE.value:
        request.status = RequestStatus.SNOOZED.value

    request.resolved_at = responded_at
    session.flush()
    return request


def expire_stale_requests(
    session: Session,
    max_age_hours: float = 24.0,
    current_time: Optional[datetime] = None
) -> int:
    """
    Mark PENDING requests older than max_age_hours as EXPIRED.
    Returns the count of expired requests.
    """
    if current_time is None:
        current_time = datetime.utcnow()

    cutoff = current_time - timedelta(hours=max_age_hours)

    stale_requests = (
        session.query(PurchaseRequest)
        .filter(
            PurchaseRequest.status == RequestStatus.PENDING.value,
            PurchaseRequest.created_at <= cutoff
        )
        .all()
    )

    for req in stale_requests:
        req.status = RequestStatus.EXPIRED.value
        req.resolved_at = current_time

    session.flush()
    return len(stale_requests)


def get_active_requests_for_gang(session: Session, gang_id: int) -> List[PurchaseRequest]:
    """
    Fetch all currently PENDING purchase requests for a gang.
    """
    return (
        session.query(PurchaseRequest)
        .filter(
            PurchaseRequest.gang_id == gang_id,
            PurchaseRequest.status == RequestStatus.PENDING.value
        )
        .order_by(PurchaseRequest.created_at.desc())
        .all()
    )


def get_request_history_for_item(session: Session, item_id: int) -> List[PurchaseRequest]:
    """
    Fetch all historical requests (active and resolved) for an item.
    """
    return (
        session.query(PurchaseRequest)
        .filter(PurchaseRequest.item_id == item_id)
        .order_by(PurchaseRequest.created_at.desc())
        .all()
    )

