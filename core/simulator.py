"""
Synthetic data simulator for SharedSpace.
Generates realistic inter-purchase intervals using continuous Gamma distributions.
Enables rapid statistical model prototyping and ground-truth validation.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import numpy as np
from sqlalchemy.orm import Session

from core.db import Gang, Item, User, PurchaseEvent
from core.gangs import create_user, create_gang, add_member_to_gang, add_item_to_gang, record_purchase


@dataclass
class ItemSimulationConfig:
    """
    Configuration for simulating a single recurring item.
    declared_prior_interval can deliberately differ from true_mean_interval
    to simulate human estimation error.
    """
    name: str
    true_mean_interval: float  # Ground truth mean interval in days (mu)
    true_std_interval: float   # Ground truth interval variability in days (sigma)
    declared_prior_interval: float  # The initial belief humans told the app
    price: float = 50.0
    unit: str = "unit"


def gamma_params_from_moments(mean: float, std: float) -> Tuple[float, float]:
    """
    Convert empirical moments (mean mu, standard deviation sigma)
    into Gamma distribution shape (k) and scale (theta).

    Formulas:
        mean   = k * theta       =>  k = (mean / std)^2
        var    = k * theta^2     =>  theta = (std^2) / mean
    """
    if mean <= 0:
        raise ValueError("Mean interval must be strictly positive.")
    if std <= 0:
        raise ValueError("Standard deviation must be strictly positive.")

    shape_k = (mean / std) ** 2
    scale_theta = (std ** 2) / mean
    return float(shape_k), float(scale_theta)


def generate_purchase_timestamps(
    mean_days: float,
    std_days: float,
    horizon_days: float,
    start_time: datetime,
    rng: np.random.Generator
) -> List[Tuple[datetime, float]]:
    """
    Sample a series of purchase timestamps across a time horizon.
    Returns a list of tuples: (timestamp, interval_days_since_previous).
    The first purchase occurs at start_time with interval 0.0.
    """
    shape_k, scale_theta = gamma_params_from_moments(mean_days, std_days)

    events: List[Tuple[datetime, float]] = [(start_time, 0.0)]
    current_time = start_time
    end_time = start_time + timedelta(days=horizon_days)

    while True:
        # Sample positive interval from Gamma distribution
        interval_days = float(rng.gamma(shape=shape_k, scale=scale_theta))
        next_time = current_time + timedelta(days=interval_days)

        if next_time > end_time:
            break

        events.append((next_time, interval_days))
        current_time = next_time

    return events


def seed_simulated_gang(
    session: Session,
    gang_name: str,
    member_names: List[str],
    items_config: List[ItemSimulationConfig],
    horizon_days: float = 60.0,
    start_time: Optional[datetime] = None,
    seed: int = 42
) -> Gang:
    """
    Populate database with a complete synthetic gang:
    - Users and gang membership
    - Items configured with human prior schedule
    - Ground-truth purchase history sampled from Gamma distributions
    """
    rng = np.random.default_rng(seed)

    if start_time is None:
        # Default start date 60 days before current time
        start_time = datetime.utcnow() - timedelta(days=horizon_days)

    if not member_names:
        raise ValueError("At least one member name is required.")

    # 1. Create Users
    users: List[User] = []
    for idx, name in enumerate(member_names):
        email = f"{name.lower().replace(' ', '_')}@simulator.local"
        users.append(create_user(session, name, email))

    # 2. Create Gang with creator
    gang = create_gang(session, gang_name, creator=users[0])

    # 3. Add remaining members
    for user in users[1:]:
        add_member_to_gang(session, gang.id, user.id)

    # 4. Create Items and generate purchase histories
    for item_cfg in items_config:
        item = add_item_to_gang(
            session=session,
            gang_id=gang.id,
            name=item_cfg.name,
            declared_interval_days=item_cfg.declared_prior_interval,
            unit=item_cfg.unit
        )

        history = generate_purchase_timestamps(
            mean_days=item_cfg.true_mean_interval,
            std_days=item_cfg.true_std_interval,
            horizon_days=horizon_days,
            start_time=start_time,
            rng=rng
        )

        # Record purchases in database
        for purchase_time, _ in history:
            buyer = rng.choice(users)
            record_purchase(
                session=session,
                item_id=item.id,
                purchased_at=purchase_time,
                price=item_cfg.price,
                buyer_id=buyer.id
            )

    return gang

