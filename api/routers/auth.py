"""
api/routers/auth.py — Real authentication (Sign Up, Log In, Password Hashing & Token Verification).

Endpoints:
  POST /auth/signup  → Register a new user account with salted PBKDF2-SHA256 password hash
                       (or claim an invited roommate profile created by email)
  POST /auth/login   → Authenticate with email + password and return user profile + signed token
"""

import hashlib
import hmac
import secrets
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.db import get_db_session, User
from core import gangs as gang_ops

router = APIRouter()

_SECRET_KEY = "sharedspace-hmac-auth-secret-key"


def hash_password(password: str, salt: str = None) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random 16-byte hex salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored 'salt$hash' string."""
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, _ = stored_hash.split("$", 1)
    expected = hash_password(password, salt)
    return hmac.compare_digest(expected, stored_hash)


def create_auth_token(user_id: int, email: str) -> str:
    """Create an HMAC-SHA256 signed session token for the authenticated user."""
    payload = f"{user_id}:{email.lower()}"
    sig = hmac.new(_SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class SignUpRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Full name")
    email: str = Field(..., min_length=3, description="Email address")
    password: str = Field(..., min_length=4, description="Account password (min 4 chars)")


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class AuthUserOut(BaseModel):
    id: int
    name: str
    email: str
    token: str


# ---------------------------------------------------------------------------
# POST /auth/signup
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=AuthUserOut, status_code=201, tags=["Auth"])
def signup(body: SignUpRequest):
    """
    Create a new account with email and password.
    If a roommate already invited this email to a Gang (so a User row exists without a password),
    this claims that profile, sets the password, and preserves all their Gang memberships!
    """
    email_clean = body.email.strip().lower()
    name_clean = body.name.strip()

    with get_db_session() as session:
        existing = session.query(User).filter(User.email == email_clean).first()

        if existing:
            if existing.password_hash:
                raise HTTPException(
                    status_code=409,
                    detail="An account with this email already exists. Please log in instead.",
                )
            # Claim invited roommate account
            existing.name = name_clean
            existing.password_hash = hash_password(body.password)
            session.commit()
            token = create_auth_token(existing.id, existing.email)
            return AuthUserOut(
                id=existing.id,
                name=existing.name,
                email=existing.email,
                token=token,
            )

        user = gang_ops.create_user(session, name_clean, email_clean)
        user.password_hash = hash_password(body.password)
        session.commit()

        token = create_auth_token(user.id, user.email)
        return AuthUserOut(
            id=user.id,
            name=user.name,
            email=user.email,
            token=token,
        )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=AuthUserOut, tags=["Auth"])
def login(body: LoginRequest):
    """
    Authenticate an existing user with email and password.
    """
    email_clean = body.email.strip().lower()

    with get_db_session() as session:
        user = session.query(User).filter(User.email == email_clean).first()
        if not user:
            raise HTTPException(
                status_code=401,
                detail="No account found with this email. Please sign up first.",
            )

        if not user.password_hash:
            raise HTTPException(
                status_code=401,
                detail="This email was invited by a roommate but hasn't set a password yet. Click 'Sign Up' with this email to claim your account!",
            )

        if not verify_password(body.password, user.password_hash):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password.",
            )

        token = create_auth_token(user.id, user.email)
        return AuthUserOut(
            id=user.id,
            name=user.name,
            email=user.email,
            token=token,
        )
