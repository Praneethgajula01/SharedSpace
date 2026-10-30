"""
Expense splitting and debt ledger management for SharedSpace.
Tracks:
1. Expense records associated with purchases and gang members
2. Equal splits across active gang members
3. Pairwise net balances (who owes whom)
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session

from core.db import User, Membership, PurchaseEvent
from core.gangs import get_gang_members


@dataclass
class ExpenseSplit:
    """Individual debtor share for an expense."""
    user_id: int
    user_name: str
    share_amount: float


@dataclass
class NetBalance:
    """Net debt position: positive means user is owed money; negative means user owes money."""
    user_id: int
    user_name: str
    net_amount: float


def split_expense_equally(
    total_amount: float,
    payer: User,
    members: List[User]
) -> List[ExpenseSplit]:
    """
    Split an order cost equally among all active gang members.
    If total_amount = 90.0 and 3 members: each owes 30.0.
    """
    if len(members) == 0:
        raise ValueError("Cannot split expense with zero members.")
    if total_amount <= 0:
        raise ValueError("Total amount must be positive.")

    per_person_share = round(total_amount / len(members), 2)
    splits = []

    for member in members:
        splits.append(
            ExpenseSplit(
                user_id=member.id,
                user_name=member.name,
                share_amount=per_person_share
            )
        )

    return splits


def compute_gang_net_balances(
    session: Session,
    gang_id: int
) -> List[NetBalance]:
    """
    Calculate the net balance for each member in a gang:
        Net = (Total money paid by user) - (User's equal share of all gang purchases)
    """
    members = get_gang_members(session, gang_id)
    if not members:
        return []

    member_map = {m.id: m.name for m in members}
    total_paid: Dict[int, float] = {m.id: 0.0 for m in members}
    total_consumed: Dict[int, float] = {m.id: 0.0 for m in members}

    # Query all purchase events for items belonging to this gang
    from core.db import Item
    purchases = (
        session.query(PurchaseEvent)
        .join(Item, Item.id == PurchaseEvent.item_id)
        .filter(Item.gang_id == gang_id)
        .all()
    )

    n_members = len(members)
    for p in purchases:
        if p.buyer_id in total_paid:
            total_paid[p.buyer_id] += p.price

        # Split cost evenly across all current gang members
        split_share = p.price / n_members
        for m_id in member_map.keys():
            total_consumed[m_id] += split_share

    balances = []
    for m_id, name in member_map.items():
        net = round(total_paid[m_id] - total_consumed[m_id], 2)
        balances.append(
            NetBalance(
                user_id=m_id,
                user_name=name,
                net_amount=net
            )
        )

    # Sort so biggest creditors appear first
    balances.sort(key=lambda b: b.net_amount, reverse=True)
    return balances


def simplify_debts(balances: List[NetBalance]) -> List[Tuple[str, str, float]]:
    """
    Compute minimal bilateral settlements (debt simplification algorithm):
    Returns list of tuples: (debtor_name, creditor_name, settle_amount).
    """
    debtors = []   # net < 0
    creditors = [] # net > 0

    for b in balances:
        if b.net_amount < -0.01:
            debtors.append([b.user_name, -b.net_amount])  # store as positive debt
        elif b.net_amount > 0.01:
            creditors.append([b.user_name, b.net_amount])

    settlements: List[Tuple[str, str, float]] = []
    i, j = 0, 0

    while i < len(debtors) and j < len(creditors):
        debtor_name, debt_amt = debtors[i]
        creditor_name, credit_amt = creditors[j]

        settle_amt = min(debt_amt, credit_amt)
        settle_amt = round(settle_amt, 2)

        if settle_amt > 0.01:
            settlements.append((debtor_name, creditor_name, settle_amt))

        debtors[i][1] -= settle_amt
        creditors[j][1] -= settle_amt

        if debtors[i][1] <= 0.01:
            i += 1
        if creditors[j][1] <= 0.01:
            j += 1

    return settlements

