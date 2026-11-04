"""
api/routers/gangs.py — REST endpoints for Gang management.

Endpoints:
  POST /gangs                        → create gang + enrol creator
  GET  /gangs/{gang_id}              → gang details + members + items
  POST /gangs/{gang_id}/members      → add an existing or new user to a gang
  POST /gangs/{gang_id}/items        → add a grocery item with a declared interval prior
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional

from core.db import get_db_session, Gang, User, Membership
from core import gangs as gang_ops

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response models
# These are the JSON shapes FastAPI validates automatically.
# ---------------------------------------------------------------------------

class CreateGangRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Gang display name")
    creator_name: str = Field(..., min_length=1, description="Full name of the creator")
    creator_email: str = Field(..., description="Email of the creator (used as unique ID)")


class AddMemberRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: str = Field(...)


class JoinGangRequest(BaseModel):
    user_id: int = Field(..., description="ID of the authenticated user joining this gang")


class AddItemRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Grocery item name, e.g. 'Milk'")
    declared_interval_days: float = Field(
        ..., gt=0, description="How often (in days) the group expects to buy this"
    )
    unit: str = Field(default="unit", description="e.g. 'litres', 'kg', 'pack'")
    price: float = Field(default=0.0, ge=0, description="Estimated price per purchase")


# Response shapes — what we send back as JSON
class UserOut(BaseModel):
    id: int
    name: str
    email: str

    model_config = {"from_attributes": True}  # allows building from ORM objects


class ItemOut(BaseModel):
    id: int
    name: str
    declared_interval_days: float
    unit: str
    price: float

    model_config = {"from_attributes": True}


class GangOut(BaseModel):
    id: int
    name: str
    members: List[UserOut] = []
    items: List[ItemOut] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# POST /gangs — Create a new gang
# ---------------------------------------------------------------------------

@router.post("", response_model=GangOut, status_code=201, tags=["Gangs"])
def create_gang(body: CreateGangRequest):
    """
    Create a new gang and automatically enrol the creator as the first member.
    If the creator's email already exists in the DB, we reuse that user record.
    """
    with get_db_session() as session:
        # Find or create the creator user
        existing = session.query(User).filter(User.email == body.creator_email.lower()).first()
        if existing:
            creator = existing
        else:
            creator = gang_ops.create_user(session, body.creator_name, body.creator_email)

        gang = gang_ops.create_gang(session, body.name, creator)
        session.commit()

        # Build response manually so ORM objects are still inside the session
        members = gang_ops.get_gang_members(session, gang.id)
        items = gang_ops.get_gang_items(session, gang.id)

        return GangOut(
            id=gang.id,
            name=gang.name,
            members=[UserOut(id=u.id, name=u.name, email=u.email) for u in members],
            items=[],
        )


# ---------------------------------------------------------------------------
# GET /gangs/user/{user_id} — Fetch ONLY the gangs this user belongs to
# ---------------------------------------------------------------------------

@router.get("/user/{user_id}", response_model=List[GangOut], tags=["Gangs"])
def get_user_gangs(user_id: int):
    """
    Return all gangs that the specified user is a member of.
    Ensures strict account-level isolation: a user only sees their own gangs.
    """
    with get_db_session() as session:
        user_gangs = (
            session.query(Gang)
            .join(Membership, Membership.gang_id == Gang.id)
            .filter(Membership.user_id == user_id)
            .order_by(Gang.id.asc())
            .all()
        )

        result = []
        for g in user_gangs:
            members = gang_ops.get_gang_members(session, g.id)
            items = gang_ops.get_gang_items(session, g.id)
            result.append(
                GangOut(
                    id=g.id,
                    name=g.name,
                    members=[UserOut(id=u.id, name=u.name, email=u.email) for u in members],
                    items=[
                        ItemOut(
                            id=it.id,
                            name=it.name,
                            declared_interval_days=it.declared_interval_days,
                            unit=it.unit,
                            price=it.price,
                        )
                        for it in items
                    ],
                )
            )
        return result


# ---------------------------------------------------------------------------
# POST /gangs/{gang_id}/join — Join an existing gang by ID
# ---------------------------------------------------------------------------

@router.post("/{gang_id}/join", response_model=GangOut, tags=["Gangs"])
def join_gang(gang_id: int, body: JoinGangRequest):
    """
    Enroll the authenticated user into an existing gang by ID.
    """
    with get_db_session() as session:
        gang = session.query(Gang).filter(Gang.id == gang_id).first()
        if not gang:
            raise HTTPException(status_code=404, detail=f"Gang #{gang_id} does not exist.")

        user = session.query(User).filter(User.id == body.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User account not found.")

        existing_membership = (
            session.query(Membership)
            .filter(Membership.gang_id == gang_id, Membership.user_id == user.id)
            .first()
        )
        if not existing_membership:
            gang_ops.add_member_to_gang(session, gang_id, user.id)
            session.commit()

        members = gang_ops.get_gang_members(session, gang_id)
        items = gang_ops.get_gang_items(session, gang_id)
        return GangOut(
            id=gang.id,
            name=gang.name,
            members=[UserOut(id=u.id, name=u.name, email=u.email) for u in members],
            items=[
                ItemOut(
                    id=it.id,
                    name=it.name,
                    declared_interval_days=it.declared_interval_days,
                    unit=it.unit,
                    price=it.price,
                )
                for it in items
            ],
        )


# ---------------------------------------------------------------------------
# GET /gangs/{gang_id} — Fetch gang details with members and items
# ---------------------------------------------------------------------------

@router.get("/{gang_id}", response_model=GangOut, tags=["Gangs"])
def get_gang(gang_id: int, user_id: Optional[int] = Query(None)):
    """
    Return gang details including all current members and tracked grocery items.
    If user_id is provided, verifies that the user is actually a member of this gang.
    """
    with get_db_session() as session:
        gang = session.query(Gang).filter(Gang.id == gang_id).first()
        if not gang:
            raise HTTPException(status_code=404, detail=f"Gang {gang_id} not found")

        members = gang_ops.get_gang_members(session, gang_id)
        if user_id is not None and not any(m.id == user_id for m in members):
            raise HTTPException(
                status_code=403,
                detail="Access denied: You are not a member of this Gang.",
            )

        items = gang_ops.get_gang_items(session, gang_id)

        return GangOut(
            id=gang.id,
            name=gang.name,
            members=[UserOut(id=u.id, name=u.name, email=u.email) for u in members],
            items=[
                ItemOut(
                    id=it.id,
                    name=it.name,
                    declared_interval_days=it.declared_interval_days,
                    unit=it.unit,
                    price=it.price,
                )
                for it in items
            ],
        )


# ---------------------------------------------------------------------------
# POST /gangs/{gang_id}/members — Add a member to an existing gang
# ---------------------------------------------------------------------------

@router.post("/{gang_id}/members", response_model=UserOut, status_code=201, tags=["Gangs"])
def add_member(gang_id: int, body: AddMemberRequest):
    """
    Add a user to an existing gang by email.
    If no account exists for that email, one is created automatically.
    If they're already a member, returns 409 Conflict.
    """
    with get_db_session() as session:
        gang = session.query(Gang).filter(Gang.id == gang_id).first()
        if not gang:
            raise HTTPException(status_code=404, detail=f"Gang {gang_id} not found")

        # Find or create user
        user = session.query(User).filter(User.email == body.email.lower()).first()
        if not user:
            user = gang_ops.create_user(session, body.name, body.email)

        # Check for duplicate membership (unique constraint in DB would also catch this)
        already_member = any(
            m.id == user.id for m in gang_ops.get_gang_members(session, gang_id)
        )
        if already_member:
            raise HTTPException(status_code=409, detail="User is already a member of this gang")

        gang_ops.add_member_to_gang(session, gang_id, user.id)
        session.commit()

        return UserOut(id=user.id, name=user.name, email=user.email)


# ---------------------------------------------------------------------------
# POST /gangs/{gang_id}/items — Add a grocery item with a declared interval
# ---------------------------------------------------------------------------

@router.post("/{gang_id}/items", response_model=ItemOut, status_code=201, tags=["Gangs"])
def add_item(gang_id: int, body: AddItemRequest):
    """
    Register a recurring grocery item for a gang.
    declared_interval_days is the Bayesian prior: how often the gang THINKS they buy it.
    The model will update this belief as purchase history accumulates.
    """
    with get_db_session() as session:
        gang = session.query(Gang).filter(Gang.id == gang_id).first()
        if not gang:
            raise HTTPException(status_code=404, detail=f"Gang {gang_id} not found")

        item = gang_ops.add_item_to_gang(
            session,
            gang_id=gang_id,
            name=body.name,
            declared_interval_days=body.declared_interval_days,
            unit=body.unit,
            price=body.price,
        )
        session.commit()

        return ItemOut(
            id=item.id,
            name=item.name,
            declared_interval_days=item.declared_interval_days,
            unit=item.unit,
            price=item.price,
        )
