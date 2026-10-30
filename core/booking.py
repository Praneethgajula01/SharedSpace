"""
Mock grocery order booking API for SharedSpace.
Simulates external delivery service responses (e.g. Blinkit, Zepto, Instamart):
- Generates realistic order delays, mock order IDs, and simulated pricing with delivery fee
- Provides confirmation payloads for gang notifications and expense splitting
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import numpy as np


@dataclass
class BookingResult:
    """Mock API booking response payload."""
    order_id: str
    item_id: int
    item_name: str
    quantity: int
    unit_price: float
    delivery_fee: float
    total_amount: float
    estimated_delivery_time: datetime
    status: str  # 'CONFIRMED', 'DELIVERED', 'FAILED'


def mock_place_order(
    item_id: int,
    item_name: str,
    quantity: int = 1,
    base_price: float = 60.0,
    current_time: Optional[datetime] = None,
    rng: Optional[np.random.Generator] = None
) -> BookingResult:
    """
    Simulate placing an instant grocery delivery order.
    Returns realistic order tracking and pricing details.
    """
    if quantity <= 0:
        raise ValueError("Quantity must be at least 1.")
    if base_price < 0:
        raise ValueError("Price cannot be negative.")

    if current_time is None:
        current_time = datetime.utcnow()
    if rng is None:
        rng = np.random.default_rng()

    # Generate realistic mock order ID (e.g. SS-ORD-84920)
    order_num = rng.integers(10000, 99999)
    order_id = f"SS-ORD-{order_num}"

    # Slight price variation (+/- 5%) and small delivery fee
    variation = rng.uniform(0.95, 1.05)
    effective_unit_price = round(base_price * variation, 2)
    delivery_fee = 15.0 if effective_unit_price * quantity < 100.0 else 0.0
    total_amount = round(effective_unit_price * quantity + delivery_fee, 2)

    # Delivery delay: 15 to 35 minutes
    delay_minutes = int(rng.integers(15, 36))
    estimated_arrival = current_time + timedelta(minutes=delay_minutes)

    return BookingResult(
        order_id=order_id,
        item_id=item_id,
        item_name=item_name,
        quantity=quantity,
        unit_price=effective_unit_price,
        delivery_fee=delivery_fee,
        total_amount=total_amount,
        estimated_delivery_time=estimated_arrival,
        status="CONFIRMED"
    )

