"""
api/main.py — FastAPI application entry-point for SharedSpace.

Responsibilities:
  - Create the FastAPI app instance
  - Register CORS middleware so the React dev server (localhost:5173) can call us
  - Initialise the SQLite database on startup (creates tables if they don't exist)
  - Provide a /health endpoint for quick sanity checks
  - Include routers (gangs, items, requests, expenses) as we build them step by step
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import our existing DB initialiser so tables are ready on startup
from core.db import init_db, get_db_session, Gang
from api.routers import gangs as gangs_router
from api.routers import requests as requests_router
from api.routers import items as items_router
from api.routers import expenses as expenses_router


async def _autonomous_bayesian_scanner():
    """
    Background loop that automatically scans all gangs every 30 seconds.
    If any item's P(need) crosses the optimal threshold, it creates a PENDING
    request so it pops up automatically in the Gang's Requests inbox.
    """
    while True:
        try:
            with get_db_session() as session:
                all_gangs = session.query(Gang).all()
                for g in all_gangs:
                    requests_router.scan_gang_items(session, g.id)
        except Exception:
            pass
        await asyncio.sleep(30)


# ---------------------------------------------------------------------------
# Lifespan handler — runs once at startup and once at shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 'lifespan' hook (replaces the old @app.on_event pattern).
    Everything before `yield` runs at startup; after `yield` at shutdown.
    """
    # Create all SQLAlchemy tables (no-op if they already exist)
    init_db()
    print("[OK] Database initialised")
    scanner_task = asyncio.create_task(_autonomous_bayesian_scanner())
    yield
    scanner_task.cancel()
    print("[BYE] SharedSpace API shutting down")


# ---------------------------------------------------------------------------
# FastAPI app instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SharedSpace API",
    description="Intelligent shared-living & automated grocery system for Gangs",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS — allow React dev server (Vite default: port 5173) and any localhost
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    # In production you'd lock this to your real domain.
    # During dev, we allow all localhost origins.
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # CRA fallback
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],           # GET, POST, PUT, DELETE, OPTIONS
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health-check endpoint
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Meta"])
def health_check():
    """
    Returns {"status": "ok"} — use this to confirm the server is running.
    React can poll this on startup to show a "connected" badge.
    """
    return {"status": "ok", "service": "SharedSpace API"}


# ---------------------------------------------------------------------------
# Root redirect hint
# ---------------------------------------------------------------------------
@app.get("/", tags=["Meta"])
def root():
    """Friendly message at the root URL."""
    return {
        "message": "SharedSpace API is running.",
        "docs": "/docs",
        "health": "/health",
    }


# ---------------------------------------------------------------------------
# Routers — added one step at a time
# ---------------------------------------------------------------------------
app.include_router(gangs_router.router, prefix="/gangs")
app.include_router(requests_router.router, prefix="/gangs")
app.include_router(items_router.router, prefix="/gangs")
app.include_router(expenses_router.router, prefix="/gangs")

