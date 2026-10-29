"""
Gang, membership, and item management operations for SharedSpace.
Provides clean helper functions for creating entities and recording purchases.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from core.db import User, Gang, Membership, Item, PurchaseEvent


def create_user(session: Session, name: str, email: str) -> User:
    """
    Create and persist a new user.
    """
    user = User(name=name.strip(), email=email.strip().lower())
    session.add(user)
    session.flush()  # Populates user.id without closing the transaction
    return user


def create_gang(session: Session, name: str, creator: User) -> Gang:
    """
    Create a new gang and immediately add the creator as its first member.
    """
    gang = Gang(name=name.strip())
    session.add(gang)
    session.flush()  # Populates gang.id

    # Automatically enroll the creator
    membership = Membership(gang_id=gang.id, user_id=creator.id)
    session.add(membership)
    session.flush()

    return gang


def add_member_to_gang(session: Session, gang_id: int, user_id: int) -> Membership:
    """
    Add an existing user to an existing gang.
    """
    membership = Membership(gang_id=gang_id, user_id=user_id)
    session.add(membership)
    session.flush()
    return membership


def add_item_to_gang(
    session: Session,
    gang_id: int,
    name: str,
    declared_interval_days: float,
    unit: str = "unit"
) -> Item:
    """
    Register a recurring grocery item under a gang.
    declared_interval_days represents the group's initial estimate of how often it is needed.
    """
    if declared_interval_days <= 0:
        raise ValueError("Declared interval must be greater than 0 days.")

    item = Item(
        gang_id=gang_id,
        name=name.strip(),
        declared_interval_days=float(declared_interval_days),
        unit=unit.strip()
    )
    session.add(item)
    session.flush()
    return item


def record_purchase(
    session: Session,
    item_id: int,
    purchased_at: Optional[datetime] = None,
    price: float = 0.0,
    buyer_id: Optional[int] = None
) -> PurchaseEvent:
    """
    Record an actual purchase event for an item.
    These timestamps will feed our interval distributions and survival models.
    """
    if purchased_at is None:
        purchased_at = datetime.utcnow()

    purchase = PurchaseEvent(
        item_id=item_id,
        purchased_at=purchased_at,
        price=float(price),
        buyer_id=buyer_id
    )
    session.add(purchase)
    session.flush()
    return purchase


def get_gang_members(session: Session, gang_id: int) -> List[User]:
    """
    Return all users who are members of a given gang.
    """
    return (
        session.query(User)
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.gang_id == gang_id)
        .all()
    )


def get_gang_items(session: Session, gang_id: int) -> List[Item]:
    """
    Return all recurring items tracked by a gang.
    """
    return session.query(Item).filter(Item.gang_id == gang_id).all()


def get_item_purchases(session: Session, item_id: int) -> List[PurchaseEvent]:
    """
    Return all recorded purchase events for an item, sorted chronologically.
    """
    return (
        session.query(PurchaseEvent)
        .filter(PurchaseEvent.item_id == item_id)
        .order_by(PurchaseEvent.purchased_at.asc())
        .all()
    )
