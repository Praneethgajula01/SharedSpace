"""
Database configuration, session management, and relational ORM schema for SharedSpace.
Supports both SQLite (local dev) and PostgreSQL (production) seamlessly via SQLAlchemy.
"""
import os
from datetime import datetime
from contextlib import contextmanager
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    event,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

# Load environment variables from .env if present
load_dotenv()

# Fallback to local SQLite if DATABASE_URL is not set
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///sharedspace.db")

# SQLite needs check_same_thread=False so multiple threads (e.g. Streamlit) can share connections
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)

# By default, SQLite has foreign key constraints disabled. We turn them ON for data integrity.
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Session factory for generating independent database sessions.
# expire_on_commit=False keeps object attributes accessible after the session commits and closes.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine
)

# Declarative base class for all ORM models
Base = declarative_base()


# ---------------------------------------------------------
# Core Relational Models
# ---------------------------------------------------------

class User(Base):
    """A member who can join one or more gangs."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, name='{self.name}', email='{self.email}')>"


class Gang(Base):
    """A group of hostellers/roommates sharing recurring grocery items."""
    __tablename__ = "gangs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    memberships = relationship("Membership", back_populates="gang", cascade="all, delete-orphan")
    items = relationship("Item", back_populates="gang", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Gang(id={self.id}, name='{self.name}')>"


class Membership(Base):
    """Associates a User with a Gang (many-to-many join table)."""
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True, index=True)
    gang_id = Column(Integer, ForeignKey("gangs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    gang = relationship("Gang", back_populates="memberships")
    user = relationship("User", back_populates="memberships")

    # A user can only join a specific gang once
    __table_args__ = (
        UniqueConstraint("gang_id", "user_id", name="uq_gang_user"),
    )

    def __repr__(self) -> str:
        return f"<Membership(gang_id={self.gang_id}, user_id={self.user_id})>"


class Item(Base):
    """
    A recurring shared grocery item managed by a gang.
    declared_interval_days acts as our initial Bayesian prior schedule.
    """
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    gang_id = Column(Integer, ForeignKey("gangs.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    declared_interval_days = Column(Float, nullable=False)  # Prior frequency, e.g. 2.0 days
    unit = Column(String(50), default="unit", nullable=False)  # e.g. 'pack', 'liter', 'kg'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    gang = relationship("Gang", back_populates="items")
    purchases = relationship("PurchaseEvent", back_populates="item", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Item(id={self.id}, name='{self.name}', prior_interval={self.declared_interval_days}d)>"


class PurchaseEvent(Base):
    """
    Records an actual purchase of an item.
    The time intervals between consecutive purchases provide empirical data for P(need).
    """
    __tablename__ = "purchase_events"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    purchased_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    price = Column(Float, default=0.0, nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    item = relationship("Item", back_populates="purchases")
    buyer = relationship("User")

    def __repr__(self) -> str:
        return f"<PurchaseEvent(item_id={self.item_id}, purchased_at='{self.purchased_at}', price={self.price})>"


# ---------------------------------------------------------
# Session Helper & DB Initializer
# ---------------------------------------------------------

@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Automatically commits on success, rolls back on error, and closes cleanly.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables registered with Base metadata."""
    Base.metadata.create_all(bind=engine)
