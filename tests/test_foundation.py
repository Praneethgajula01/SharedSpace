"""
Foundation integration tests for SharedSpace.
Validates database schema, user/gang/item relationships, and request state machine.
Uses an isolated in-memory SQLite database for zero-disk-side-effect test execution.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from core.db import Base, RequestStatus
from core.gangs import (
    create_user,
    create_gang,
    add_member_to_gang,
    add_item_to_gang,
    record_purchase,
    get_gang_members,
    get_gang_items,
    get_item_purchases,
)
from core.requests import (
    create_purchase_request,
    respond_to_request,
    expire_stale_requests,
    get_active_requests_for_gang,
)


@pytest.fixture
def session():
    """
    Creates an isolated in-memory SQLite database and session for each test function.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )

    # Enable SQLite foreign key enforcement
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine
    )
    db_session = TestingSession()

    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_user_and_gang_creation(session):
    """Verify user creation, gang creation, and automatic creator membership."""
    alice = create_user(session, "Alice", "alice@test.com")
    assert alice.id is not None
    assert alice.email == "alice@test.com"

    gang = create_gang(session, "Flat 4B", creator=alice)
    assert gang.id is not None

    members = get_gang_members(session, gang.id)
    assert len(members) == 1
    assert members[0].id == alice.id
    assert members[0].name == "Alice"


def test_duplicate_membership_prevention(session):
    """Verify that adding the same user to a gang twice violates the unique constraint."""
    alice = create_user(session, "Alice", "alice@test.com")
    gang = create_gang(session, "Flat 4B", creator=alice)

    # Alice is already enrolled by create_gang; adding her again must fail
    with pytest.raises(IntegrityError):
        add_member_to_gang(session, gang.id, alice.id)


def test_item_creation_validation(session):
    """Verify item registration and interval validation."""
    alice = create_user(session, "Alice", "alice@test.com")
    gang = create_gang(session, "Flat 4B", creator=alice)

    milk = add_item_to_gang(session, gang.id, "Milk", declared_interval_days=2.5, unit="liter")
    assert milk.id is not None
    assert milk.declared_interval_days == 2.5
    assert milk.unit == "liter"

    # Non-positive interval should be rejected
    with pytest.raises(ValueError, match="greater than 0"):
        add_item_to_gang(session, gang.id, "Invalid Item", declared_interval_days=0)


def test_purchase_event_and_interval(session):
    """Verify recording purchases and calculating empirical inter-purchase intervals."""
    alice = create_user(session, "Alice", "alice@test.com")
    gang = create_gang(session, "Flat 4B", creator=alice)
    bread = add_item_to_gang(session, gang.id, "Bread", declared_interval_days=2.0)

    t0 = datetime(2026, 10, 1, 10, 0)
    t1 = datetime(2026, 10, 3, 16, 0)  # 2 days + 6 hours = 2.25 days later

    record_purchase(session, bread.id, purchased_at=t0, price=40.0, buyer_id=alice.id)
    record_purchase(session, bread.id, purchased_at=t1, price=45.0, buyer_id=alice.id)

    purchases = get_item_purchases(session, bread.id)
    assert len(purchases) == 2

    # Compute empirical interval Delta t
    interval_seconds = (purchases[1].purchased_at - purchases[0].purchased_at).total_seconds()
    interval_days = interval_seconds / 86400.0
    assert pytest.approx(interval_days, 0.01) == 2.25


def test_request_state_machine_flow(session):
    """Verify request creation, outsider block, response acceptance, and state locking."""
    alice = create_user(session, "Alice", "alice@test.com")
    bob = create_user(session, "Bob", "bob@test.com")
    charlie = create_user(session, "Charlie", "charlie@test.com")  # Outsider

    gang = create_gang(session, "Flat 4B", creator=alice)
    add_member_to_gang(session, gang.id, bob.id)
    coffee = add_item_to_gang(session, gang.id, "Coffee", declared_interval_days=7.0)

    # 1. System generates a request when P(need) = 0.88
    req = create_purchase_request(session, coffee.id, p_need=0.88)
    assert req.status == RequestStatus.PENDING.value
    assert req.resolved_at is None
    assert len(get_active_requests_for_gang(session, gang.id)) == 1

    # 2. Outsider attempts to vote -> should be rejected
    with pytest.raises(ValueError, match="not a member"):
        respond_to_request(session, req.id, user_id=charlie.id, action="YES")

    # 3. Gang member Bob approves -> transitions to ACCEPTED
    now = datetime(2026, 10, 10, 12, 0)
    resolved_req = respond_to_request(session, req.id, user_id=bob.id, action="YES", responded_at=now)
    assert resolved_req.status == RequestStatus.ACCEPTED.value
    assert resolved_req.resolved_at == now
    assert len(resolved_req.responses) == 1
    assert resolved_req.responses[0].user_id == bob.id
    assert resolved_req.responses[0].action == "YES"

    # 4. State is locked: Alice cannot override or re-respond
    with pytest.raises(ValueError, match="already 'ACCEPTED'"):
        respond_to_request(session, req.id, user_id=alice.id, action="NO")


def test_stale_request_expiration(session):
    """Verify that unhandled requests automatically expire after the configured timeout."""
    alice = create_user(session, "Alice", "alice@test.com")
    gang = create_gang(session, "Flat 4B", creator=alice)
    milk = add_item_to_gang(session, gang.id, "Milk", declared_interval_days=2.0)

    req = create_purchase_request(session, milk.id, p_need=0.75)
    t_created = datetime(2026, 10, 1, 10, 0)
    req.created_at = t_created
    session.flush()

    # Fast forward 12 hours: should not expire yet (max_age_hours=24)
    t_12h = t_created + timedelta(hours=12)
    expired_count = expire_stale_requests(session, max_age_hours=24.0, current_time=t_12h)
    assert expired_count == 0
    assert req.status == RequestStatus.PENDING.value

    # Fast forward 25 hours: should expire
    t_25h = t_created + timedelta(hours=25)
    expired_count = expire_stale_requests(session, max_age_hours=24.0, current_time=t_25h)
    assert expired_count == 1
    assert req.status == RequestStatus.EXPIRED.value
    assert req.resolved_at == t_25h

