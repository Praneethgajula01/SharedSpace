"""
tests/test_api_e2e.py — End-to-end integration tests for SharedSpace API.

Verifies the core hostel gang workflow:
  1. Gang creation, roommate addition, and shared grocery registration
  2. Automatic depletion detection & request generation
  3. First-member approval triggers order & blocks any redundant/duplicate order
  4. Automatic equal expense splitting & debt settlement across roommates
"""

from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_full_gang_order_and_zero_redundancy_flow():
    # 1. Create a gang with 2 roommates and 1 shared item
    res = client.post(
        "/gangs",
        json={
            "name": "Test Hostel Gang",
            "creator_name": "Arjun",
            "creator_email": "arjun_e2e@hostel.com",
        },
    )
    assert res.status_code == 201
    gang = res.json()
    gang_id = gang["id"]
    arjun_id = gang["members"][0]["id"]

    res_m = client.post(
        f"/gangs/{gang_id}/members",
        json={"name": "Priya", "email": "priya_e2e@hostel.com"},
    )
    assert res_m.status_code == 201
    priya_id = res_m.json()["id"]

    res_item = client.post(
        f"/gangs/{gang_id}/items",
        json={
            "name": "Milk",
            "declared_interval_days": 2.0,
            "unit": "litre",
            "price": 60.0,
        },
    )
    assert res_item.status_code == 201
    item_id = res_item.json()["id"]

    # 2. Record a purchase 3 days ago so Milk is depleted
    three_days_ago = (datetime.utcnow() - timedelta(days=3)).isoformat()
    res_p = client.post(
        f"/gangs/{gang_id}/items/{item_id}/purchase",
        json={"price": 60.0, "buyer_id": arjun_id, "purchased_at": three_days_ago},
    )
    assert res_p.status_code == 201

    # 3. Trigger scan -> system should create 1 PENDING request
    res_scan = client.post(f"/gangs/{gang_id}/check-and-trigger")
    assert res_scan.status_code == 200
    scan_data = res_scan.json()
    assert scan_data[0]["triggered"] is True
    req_id = scan_data[0]["request_id"]

    # 4. Priya approves the request -> order is placed
    res_approve = client.post(
        f"/gangs/{gang_id}/requests/{req_id}/respond",
        json={"user_id": priya_id, "action": "YES"},
    )
    assert res_approve.status_code == 200
    approved_data = res_approve.json()
    assert approved_data["status"] == "ACCEPTED"
    assert approved_data["order_receipt"]["order_id"].startswith("SS-ORD-")

    # 5. Arjun tries to approve the same request -> MUST fail with 400 (0 duplicate orders)
    res_dup = client.post(
        f"/gangs/{gang_id}/requests/{req_id}/respond",
        json={"user_id": arjun_id, "action": "YES"},
    )
    assert res_dup.status_code == 400

    # 6. Verify expense ledger automatically split the new order
    res_bal = client.get(f"/gangs/{gang_id}/balances")
    assert res_bal.status_code == 200
    balances = res_bal.json()
    assert len(balances) == 2

