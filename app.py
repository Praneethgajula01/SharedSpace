"""
SharedSpace - Main Streamlit Application
Interactive Shared-Living Management & Automated Grocery System
"""
import streamlit as st
from datetime import datetime
from sqlalchemy.orm import Session

from core.db import init_db, get_db_session, Gang, Item, User, PurchaseRequest, RequestStatus
from core.gangs import (
    create_user,
    create_gang,
    add_member_to_gang,
    add_item_to_gang,
    record_purchase,
    get_gang_members,
    get_gang_items,
    get_item_purchases
)
from core.simulator import ItemSimulationConfig, seed_simulated_gang
from core.need_model import compute_historical_intervals, get_elapsed_days
from core.bayesian_model import p_need_bayesian
from core.decision import UtilityConfig, should_trigger_request
from core.requests import (
    create_purchase_request,
    respond_to_request,
    get_active_requests_for_gang
)
from core.booking import mock_place_order
from core.expenses import compute_gang_net_balances, simplify_debts

st.set_page_config(
    page_title="SharedSpace | Intelligent Grocery Automation",
    page_icon="🛒",
    layout="wide"
)

# Initialize database schema
init_db()


def ensure_demo_data(session: Session) -> Gang:
    """Populate database with sample gang and items if empty."""
    gang = session.query(Gang).first()
    if gang:
        return gang

    configs = [
        ItemSimulationConfig(
            name="Milk",
            true_mean_interval=2.5,
            true_std_interval=0.3,
            declared_prior_interval=2.0,
            price=60.0,
            unit="liter"
        ),
        ItemSimulationConfig(
            name="Drinking Water Can",
            true_mean_interval=4.0,
            true_std_interval=0.5,
            declared_prior_interval=5.0,
            price=90.0,
            unit="can"
        ),
        ItemSimulationConfig(
            name="Eggs (12-pack)",
            true_mean_interval=3.5,
            true_std_interval=0.4,
            declared_prior_interval=3.0,
            price=85.0,
            unit="pack"
        )
    ]
    gang = seed_simulated_gang(
        session=session,
        gang_name="Room 304 Flatmates",
        member_names=["Arjun", "Kabir", "Rohan"],
        items_config=configs,
        horizon_days=30.0,
        seed=42
    )
    return gang


# -------------------------------------------------------------
# App Layout & State
# -------------------------------------------------------------

with get_db_session() as session:
    current_gang = ensure_demo_data(session)
    members = get_gang_members(session, current_gang.id)
    items = get_gang_items(session, current_gang.id)

st.title("🛒 SharedSpace")
st.caption(f"**Gang: {current_gang.name}** | Active Members: {', '.join([m.name for m in members])}")

# Sidebar user switcher (simulate which roommate is viewing the app)
st.sidebar.header("👤 Roommate Profile")
active_user = st.sidebar.selectbox(
    "Acting as:",
    options=members,
    format_func=lambda u: u.name
)

# -------------------------------------------------------------
# Section 1: Replenishment Alert Inbox
# -------------------------------------------------------------

st.header("🔔 Active Replenishment Inbox")

with get_db_session() as session:
    active_requests = get_active_requests_for_gang(session, current_gang.id)

    if not active_requests:
        st.success("✅ No pending purchase requests. All shared groceries are well stocked!")
    else:
        for req in active_requests:
            item = req.item
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.subheader(f"📦 {item.name}")
                st.write(
                    f"**Predicted Need Probability:** `{req.p_need_at_creation * 100:.1f}%` "
                    f"| Alerted: `{req.created_at.strftime('%Y-%m-%d %H:%M')}`"
                )

            with col2:
                if st.button("✅ Book It! (YES)", key=f"yes_{req.id}", use_container_width=True):
                    respond_to_request(session, req.id, active_user.id, "YES")
                    booking = mock_place_order(item.id, item.name, base_price=60.0)
                    record_purchase(session, item.id, price=booking.total_amount, buyer_id=active_user.id)
                    st.toast(f"🎉 Order {booking.order_id} placed! Rs {booking.total_amount} split among flatmates.")
                    st.rerun()

            with col3:
                if st.button("❌ Not Yet (NO)", key=f"no_{req.id}", use_container_width=True):
                    respond_to_request(session, req.id, active_user.id, "NO")
                    st.info("Response recorded. Models updated.")
                    st.rerun()

st.divider()

# -------------------------------------------------------------
# Section 2: Items & Bayesian Need Monitor
# -------------------------------------------------------------

st.header("📊 Item Health & Probability Monitor")

now = datetime.utcnow()
cols = st.columns(len(items))

for idx, item in enumerate(items):
    with cols[idx]:
        with get_db_session() as session:
            purchases = get_item_purchases(session, item.id)
            intervals = compute_historical_intervals(purchases)
            last_purchase = purchases[-1] if purchases else None

            if last_purchase:
                elapsed = get_elapsed_days(now, last_purchase.purchased_at)
            else:
                elapsed = 1.0

            # Compute real-time Bayesian P(need)
            p_need = p_need_bayesian(
                elapsed_days=elapsed,
                declared_interval_days=item.declared_interval_days,
                historical_intervals=intervals
            )

            # Evaluate decision engine
            utility = UtilityConfig(benefit=3.0, annoyance=1.0)
            should_ask, reason, tau = should_trigger_request(
                p_need=p_need,
                current_time=now,
                last_prompted_at=None,
                utility=utility
            )

        st.markdown(f"### {item.name}")
        st.metric(
            label="P(need now)",
            value=f"{p_need * 100:.1f}%",
            delta=f"Threshold τ*: {tau * 100:.0f}%"
        )
        st.write(f"- **Declared Prior:** `{item.declared_interval_days:.1f} days`")
        st.write(f"- **Days Elapsed:** `{elapsed:.1f} days`")
        st.write(f"- **Purchase History:** `{len(purchases)} times`")

        if should_ask:
            if st.button(f"Trigger Alert for {item.name}", key=f"trig_{item.id}"):
                with get_db_session() as session:
                    create_purchase_request(session, item.id, p_need=p_need)
                st.rerun()

st.divider()

# -------------------------------------------------------------
# Section 3: Expense Split & Debt Ledger
# -------------------------------------------------------------

st.header("💰 Expense Split Ledger")

with get_db_session() as session:
    balances = compute_gang_net_balances(session, current_gang.id)
    settlements = simplify_debts(balances)

col_bal, col_settle = st.columns([1, 1])

with col_bal:
    st.subheader("Member Net Balances")
    for b in balances:
        color = "green" if b.net_amount >= 0 else "red"
        st.markdown(f"- **{b.user_name}**: :{color}[Rs {b.net_amount:+.2f}]")

with col_settle:
    st.subheader("Simplified Settlements")
    if not settlements:
        st.info("All debts are fully settled!")
    else:
        for debtor, creditor, amt in settlements:
            st.warning(f"💸 **{debtor}** pays **{creditor}**: **Rs {amt:.2f}**")

