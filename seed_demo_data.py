"""
seed_demo_data.py — Populate SharedSpace with 6 student accounts, 2 Gangs,
and 30 days of realistic purchase & order history for live demonstration.

Run anytime with:
    python seed_demo_data.py
"""

from datetime import datetime, timedelta
import numpy as np

from core.db import (
    init_db,
    get_db_session,
    User,
    Gang,
    Membership,
    Item,
    PurchaseEvent,
    PurchaseRequest,
    RequestResponse,
)
from core import gangs as gang_ops
from core.requests import create_purchase_request, respond_to_request
from api.routers.auth import hash_password
from api.routers.requests import scan_gang_items


def seed_rich_30_day_data():
    init_db()
    rng = np.random.default_rng(42)
    now = datetime.utcnow()
    default_pw = hash_password("password123")

    with get_db_session() as session:
        # Clear old data so we have a clean, well-structured 30-day dataset
        session.query(RequestResponse).delete()
        session.query(PurchaseRequest).delete()
        session.query(PurchaseEvent).delete()
        session.query(Item).delete()
        session.query(Membership).delete()
        session.query(Gang).delete()
        session.query(User).delete()
        session.commit()

        # -------------------------------------------------------------------
        # 1. Create 6 Student Accounts (all password: password123)
        # -------------------------------------------------------------------
        students_spec = [
            ("Arjun Sharma", "arjun@hostel.com"),
            ("Priya Patel", "priya@hostel.com"),
            ("Rohan Verma", "rohan@hostel.com"),
            ("Sneha Reddy", "sneha@hostel.com"),
            ("Karthik Nair", "karthik@hostel.com"),
            ("Ananya Gupta", "ananya@hostel.com"),
        ]
        users = {}
        for name, email in students_spec:
            u = gang_ops.create_user(session, name, email)
            u.password_hash = default_pw
            users[email] = u
        session.commit()

        # -------------------------------------------------------------------
        # 2. Create 2 Gangs with Distinct Roommate Memberships
        # -------------------------------------------------------------------
        # Gang 1: Room 302 - Tech Wing (Arjun, Priya, Rohan, Sneha)
        gang1 = gang_ops.create_gang(session, "Room 302 - Tech Wing", users["arjun@hostel.com"])
        gang_ops.add_member_to_gang(session, gang1.id, users["priya@hostel.com"].id)
        gang_ops.add_member_to_gang(session, gang1.id, users["rohan@hostel.com"].id)
        gang_ops.add_member_to_gang(session, gang1.id, users["sneha@hostel.com"].id)

        # Gang 2: Block C - Night Owls (Karthik, Ananya, Rohan)
        gang2 = gang_ops.create_gang(session, "Block C - Night Owls", users["karthik@hostel.com"])
        gang_ops.add_member_to_gang(session, gang2.id, users["ananya@hostel.com"].id)
        gang_ops.add_member_to_gang(session, gang2.id, users["rohan@hostel.com"].id)
        session.commit()

        gang1_members = [
            users["arjun@hostel.com"],
            users["priya@hostel.com"],
            users["rohan@hostel.com"],
            users["sneha@hostel.com"],
        ]
        gang2_members = [
            users["karthik@hostel.com"],
            users["ananya@hostel.com"],
            users["rohan@hostel.com"],
        ]

        # -------------------------------------------------------------------
        # 3. Helper to simulate 30 days of purchases for an item
        # -------------------------------------------------------------------
        def populate_item_history(
            gang_id: int,
            members: list,
            name: str,
            declared_days: float,
            true_mean_days: float,
            unit: str,
            price: float,
            days_since_last_buy: float,
        ):
            item = gang_ops.add_item_to_gang(
                session,
                gang_id=gang_id,
                name=name,
                declared_interval_days=declared_days,
                unit=unit,
                price=price,
            )
            item.created_at = now - timedelta(days=32)

            # Walk backward from (now - days_since_last_buy) over 30 days
            t_cursor = now - timedelta(days=days_since_last_buy)
            timestamps = [t_cursor]
            while True:
                gap = float(rng.gamma(shape=6.0, scale=true_mean_days / 6.0))
                t_cursor = t_cursor - timedelta(days=gap)
                if t_cursor < now - timedelta(days=30):
                    break
                timestamps.append(t_cursor)

            timestamps.reverse()

            for idx, ts in enumerate(timestamps):
                buyer = members[idx % len(members)]
                actual_price = round(price * float(rng.uniform(0.95, 1.05)), 2)
                gang_ops.record_purchase(
                    session,
                    item_id=item.id,
                    purchased_at=ts,
                    price=actual_price,
                    buyer_id=buyer.id,
                )

            return item, len(timestamps)

        # -------------------------------------------------------------------
        # 4. Seed 30 Days of Items & Purchases for Gang 1 ("Room 302 - Tech Wing")
        # -------------------------------------------------------------------
        g1_items = [
            # (name, declared, true_mean, unit, price, days_since_last_buy)
            ("Amul Taaza Milk", 2.0, 2.2, "litre", 56.0, 2.8),         # Almost Empty -> Triggers Request!
            ("Brown Bread", 3.0, 3.1, "loaf", 50.0, 3.9),             # Almost Empty -> Triggers Request!
            ("Eggs (12 Pack)", 5.0, 4.5, "tray", 96.0, 5.2),          # Almost Empty -> Triggers Request!
            ("Bisleri 20L Water Can", 4.0, 3.5, "can", 90.0, 1.8),    # Running Low (mid-cycle)
            ("Nescafe Classic Coffee", 10.0, 8.5, "jar", 240.0, 1.2), # Stocked (bought yesterday)
        ]
        total_purchases = 0
        created_g1_items = []
        for name, dec, tm, unit, pr, elapsed in g1_items:
            it, cnt = populate_item_history(gang1.id, gang1_members, name, dec, tm, unit, pr, elapsed)
            total_purchases += cnt
            created_g1_items.append(it)

        # -------------------------------------------------------------------
        # 5. Seed 30 Days of Items & Purchases for Gang 2 ("Block C - Night Owls")
        # -------------------------------------------------------------------
        g2_items = [
            ("Maggi 6-Pack", 4.0, 3.2, "pack", 84.0, 4.1),            # Almost Empty -> Triggers Request!
            ("Cold Brew Milk", 2.5, 2.4, "litre", 68.0, 3.1),         # Almost Empty -> Triggers Request!
            ("Peanut Butter (1kg)", 12.0, 10.0, "jar", 320.0, 2.5),   # Stocked
            ("Green Tea (25 Bags)", 8.0, 7.5, "box", 160.0, 1.0),     # Stocked
        ]
        created_g2_items = []
        for name, dec, tm, unit, pr, elapsed in g2_items:
            it, cnt = populate_item_history(gang2.id, gang2_members, name, dec, tm, unit, pr, elapsed)
            total_purchases += cnt
            created_g2_items.append(it)

        session.commit()

        # -------------------------------------------------------------------
        # 6. Create Past Resolved Requests (History) + Active Pending Requests
        # -------------------------------------------------------------------
        # Add 2 historical resolved requests for Gang 1 (3 days ago & 5 days ago)
        hist_req1 = PurchaseRequest(
            item_id=created_g1_items[4].id,  # Coffee
            gang_id=gang1.id,
            status="ACCEPTED",
            p_need_at_creation=0.84,
            created_at=now - timedelta(days=1, hours=6),
            resolved_at=now - timedelta(days=1, hours=5),
        )
        session.add(hist_req1)
        session.flush()
        session.add(
            RequestResponse(
                request_id=hist_req1.id,
                user_id=users["priya@hostel.com"].id,
                action="YES",
                responded_at=now - timedelta(days=1, hours=5),
            )
        )

        hist_req2 = PurchaseRequest(
            item_id=created_g1_items[3].id,  # Water Can
            gang_id=gang1.id,
            status="ACCEPTED",
            p_need_at_creation=0.79,
            created_at=now - timedelta(days=2, hours=3),
            resolved_at=now - timedelta(days=2, hours=2),
        )
        session.add(hist_req2)
        session.flush()
        session.add(
            RequestResponse(
                request_id=hist_req2.id,
                user_id=users["rohan@hostel.com"].id,
                action="YES",
                responded_at=now - timedelta(days=2, hours=2),
            )
        )
        session.commit()

        # Run the Bayesian scanner to trigger active PENDING requests for depleted items
        g1_triggers = scan_gang_items(session, gang1.id)
        g2_triggers = scan_gang_items(session, gang2.id)

        print("=" * 72)
        print("30-DAY DEMO DATASET SEEDED SUCCESSFULLY!")
        print("=" * 72)
        print(f"Total Student Accounts : {len(users)} (Password for all: password123)")
        print(f"Total Gangs Created    : 2")
        print(f"Total 30-Day Purchases : {total_purchases} events across 9 grocery items")
        print("-" * 72)
        print("GANG 1: 'Room 302 - Tech Wing'")
        print("  Members : arjun@hostel.com, priya@hostel.com, rohan@hostel.com, sneha@hostel.com")
        print(f"  Active Order Requests Triggered: {sum(1 for r in g1_triggers if r.triggered)}")
        print("\nGANG 2: 'Block C - Night Owls'")
        print("  Members : karthik@hostel.com, ananya@hostel.com, rohan@hostel.com")
        print(f"  Active Order Requests Triggered: {sum(1 for r in g2_triggers if r.triggered)}")
        print("=" * 72)


if __name__ == "__main__":
    seed_rich_30_day_data()
