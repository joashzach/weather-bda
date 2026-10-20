"""Security primitives: Argon2id password hashing, JWT encoding/decoding, IP HMAC and tracking tokens."""

import contextlib
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

# Argon2id password hasher with secure defaults
ph = PasswordHasher()

# Pre-computed dummy hash to prevent timing attacks during user enumeration attempts
DUMMY_HASH = ph.hash("nonexistent_user_dummy_password_timing_defense")


def hash_password(password: str) -> str:
    """Hash plaintext password with Argon2id."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash in constant time."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def verify_dummy_password(plain_password: str) -> None:
    """Perform constant-time dummy verification when user is absent to prevent timing enumeration."""
    with contextlib.suppress(Exception):
        ph.verify(DUMMY_HASH, plain_password)


def check_needs_rehash(hashed_password: str) -> bool:
    """Check if hash parameters are outdated and need rehashing."""
    try:
        return ph.check_needs_rehash(hashed_password)
    except Exception:
        return False


def create_access_token(
    user_id: uuid.UUID | str,
    role: str,
    token_version: int,
    expires_delta: timedelta | None = None,
) -> str:
    """Create short-lived HS256 JWT access token with all required claims."""
    settings = get_settings()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "tv": token_version,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(16),
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and strictly validate JWT access token claims with HS256 pinned."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
                "verify_aud": True,
                "require": ["sub", "role", "tv", "iss", "aud", "iat", "exp", "jti"],
            },
        )
        return payload
    except jwt.PyJWTError as e:
        raise ValueError(f"Invalid access token: {e}") from e


def hash_ip(client_ip: str | None) -> str | None:
    """Generate SHA256-HMAC of client IP for privacy-preserving rate limiting and abuse control."""
    if not client_ip:
        return None
    settings = get_settings()
    return hmac.new(
        settings.IP_HASH_SECRET.encode("utf-8"),
        client_ip.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_tracking_token() -> str:
    """Generate 32-byte URL-safe tracking token for anonymous citizen report updates."""
    return secrets.token_urlsafe(32)


def hash_tracking_token(token: str) -> str:
    """Hash tracking token with SHA-256 for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
