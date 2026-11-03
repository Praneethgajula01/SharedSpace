"""
api/routers/expenses.py — Expense tracking and debt settlement endpoints.

Endpoints:
  GET /gangs/{gang_id}/balances      → net balance per member (who is owed, who owes)
  GET /gangs/{gang_id}/settlements   → minimal set of transfers to settle all debts
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

from core.db import get_db_session
from core.expenses import compute_gang_net_balances, simplify_debts

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class BalanceOut(BaseModel):
    user_id: int
    user_name: str
    net_amount: float   # positive = owed money; negative = owes money


class SettlementOut(BaseModel):
    debtor: str         # person who owes
    creditor: str       # person who is owed
    amount: float       # how much to transfer


# ---------------------------------------------------------------------------
# GET /gangs/{gang_id}/balances
# ---------------------------------------------------------------------------

@router.get("/{gang_id}/balances", response_model=List[BalanceOut], tags=["Expenses"])
def get_balances(gang_id: int):
    """
    Return each member's net balance across all gang purchases.
    net_amount > 0 means the member has paid more than their share (is owed money).
    net_amount < 0 means the member has paid less than their share (owes money).
    """
    with get_db_session() as session:
        balances = compute_gang_net_balances(session, gang_id)
        return [
            BalanceOut(
                user_id=b.user_id,
                user_name=b.user_name,
                net_amount=b.net_amount,
            )
            for b in balances
        ]


# ---------------------------------------------------------------------------
# GET /gangs/{gang_id}/settlements
# ---------------------------------------------------------------------------

@router.get("/{gang_id}/settlements", response_model=List[SettlementOut], tags=["Expenses"])
def get_settlements(gang_id: int):
    """
    Return the minimum set of person-to-person transfers that would settle all debts.
    Uses a greedy bilateral algorithm to minimise the number of transactions.
    Example: if A owes 30 and B owes 20, and C is owed 50 → A pays C 30, B pays C 20.
    """
    with get_db_session() as session:
        balances = compute_gang_net_balances(session, gang_id)
        settlements = simplify_debts(balances)
        return [
            SettlementOut(debtor=d, creditor=c, amount=amt)
            for d, c, amt in settlements
        ]

