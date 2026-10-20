"""Unit tests for password hashing, JWT claims, token verification, and IP HMAC."""

import uuid
from datetime import timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    check_needs_rehash,
    create_access_token,
    decode_access_token,
    generate_tracking_token,
    hash_ip,
    hash_password,
    hash_tracking_token,
    verify_dummy_password,
    verify_password,
)


def test_password_hash_and_verify() -> None:
    password = "SuperSecurePassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert check_needs_rehash(hashed) is False


def test_dummy_password_verification() -> None:
    # Verifies that dummy verification executes cleanly without exceptions
    verify_dummy_password("any_password_attempt")


def test_jwt_access_token_creation_and_decoding() -> None:
    user_id = uuid.uuid4()
    role = "admin"
    token_version = 1

    token = create_access_token(user_id=user_id, role=role, token_version=token_version)
    claims = decode_access_token(token)

    assert claims["sub"] == str(user_id)
    assert claims["role"] == role
    assert claims["tv"] == token_version
    assert "jti" in claims
    assert "exp" in claims
    assert "iat" in claims


def test_jwt_expired_token_rejected() -> None:
    user_id = uuid.uuid4()
    # Expired token in the past
    token = create_access_token(
        user_id=user_id,
        role="reviewer",
        token_version=0,
        expires_delta=timedelta(seconds=-10),
    )

    with pytest.raises(ValueError) as exc:
        decode_access_token(token)
    assert "Invalid access token" in str(exc.value)


def test_jwt_wrong_algorithm_or_none_rejected() -> None:
    settings = get_settings()
    user_id = uuid.uuid4()
    payload = {
        "sub": str(user_id),
        "role": "admin",
        "tv": 1,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": 1000,
        "exp": 9999999999,
        "jti": "dummy",
    }
    # Forged 'none' algorithm token
    none_token = jwt.encode(payload, "", algorithm="none")

    with pytest.raises(ValueError):
        decode_access_token(none_token)


def test_ip_hashing_and_tracking_tokens() -> None:
    ip = "192.168.1.100"
    hashed_ip_1 = hash_ip(ip)
    hashed_ip_2 = hash_ip(ip)

    assert hashed_ip_1 == hashed_ip_2
    assert len(hashed_ip_1) == 64
    assert hash_ip(None) is None

    token = generate_tracking_token()
    assert len(token) >= 32
    hashed_token = hash_tracking_token(token)
    assert len(hashed_token) == 64


def test_check_needs_rehash_invalid() -> None:
    from app.core.security import check_needs_rehash

    assert check_needs_rehash("not-a-valid-argon2-hash") is False
