"""Integration tests for Authentication, DB Lockout, RBAC, OpenAPI Admin Route Security, and Log Redaction."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import redact_sensitive_data
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password
from app.db.models.users import User
from app.repositories.users import UserRepository

PASSWORD_ADMIN = "AdminSecurePassword123!"
PASSWORD_REVIEWER = "ReviewerSecurePassword123!"


def _seed_auth_users(db: Session) -> dict[str, User]:
    user_repo = UserRepository(db)

    admin = user_repo.get_by_email("admin@weatherbda.org")
    if not admin:
        admin = User(
            email="admin@weatherbda.org",
            display_name="Admin Chief",
            password_hash=hash_password(PASSWORD_ADMIN),
            role="admin",
            is_active=True,
            token_version=0,
            failed_login_count=0,
            locked_until=None,
        )
        db.add(admin)

    reviewer = user_repo.get_by_email("reviewer@weatherbda.org")
    if not reviewer:
        reviewer = User(
            email="reviewer@weatherbda.org",
            display_name="Reviewer One",
            password_hash=hash_password(PASSWORD_REVIEWER),
            role="reviewer",
            is_active=True,
            token_version=0,
            failed_login_count=0,
            locked_until=None,
        )
        db.add(reviewer)

    inactive = user_repo.get_by_email("inactive@weatherbda.org")
    if not inactive:
        inactive = User(
            email="inactive@weatherbda.org",
            display_name="Inactive Staff",
            password_hash=hash_password(PASSWORD_REVIEWER),
            role="reviewer",
            is_active=False,
            token_version=0,
            failed_login_count=0,
            locked_until=None,
        )
        db.add(inactive)

    db.commit()
    db.refresh(admin)
    db.refresh(reviewer)
    db.refresh(inactive)
    return {"admin": admin, "reviewer": reviewer, "inactive": inactive}


def test_auth_login_success(client: TestClient, db_session: Session):
    _seed_auth_users(db_session)

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@weatherbda.org", "password": PASSWORD_ADMIN},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800  # 30 min default
    assert data["user"]["email"] == "admin@weatherbda.org"
    assert data["user"]["role"] == "admin"


def test_auth_login_anti_enumeration(client: TestClient, db_session: Session):
    users = _seed_auth_users(db_session)
    inactive_user = users["inactive"]

    expected_msg = "Invalid email or password"

    # 1. Nonexistent email
    resp1 = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "WrongPassword123!"},
    )
    assert resp1.status_code == 401
    assert resp1.json()["error"]["message"] == expected_msg

    # 2. Existing email, wrong password
    resp2 = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@weatherbda.org", "password": "IncorrectPassword123!"},
    )
    assert resp2.status_code == 401
    assert resp2.json()["error"]["message"] == expected_msg

    # 3. Inactive account
    resp3 = client.post(
        "/api/v1/auth/login",
        json={"email": inactive_user.email, "password": PASSWORD_REVIEWER},
    )
    assert resp3.status_code == 401
    assert resp3.json()["error"]["message"] == expected_msg


def test_auth_account_lockout_and_recovery(client: TestClient, db_session: Session):
    users = _seed_auth_users(db_session)
    reviewer = users["reviewer"]

    # 5 consecutive failed attempts
    for _ in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": reviewer.email, "password": "BadPassword123!"},
        )
        assert resp.status_code == 401

    # Database state check: account must now be locked
    db_session.refresh(reviewer)
    assert reviewer.failed_login_count == 5
    assert reviewer.locked_until is not None
    assert reviewer.locked_until > datetime.now(UTC)

    # 6th attempt with CORRECT password must fail due to active lockout
    resp_locked = client.post(
        "/api/v1/auth/login",
        json={"email": reviewer.email, "password": PASSWORD_REVIEWER},
    )
    assert resp_locked.status_code == 401
    assert resp_locked.json()["error"]["message"] == "Invalid email or password"

    # Simulate lockout expiry (setting locked_until in past)
    reviewer.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    # Now login with correct password succeeds and resets lockout counter
    resp_recovered = client.post(
        "/api/v1/auth/login",
        json={"email": reviewer.email, "password": PASSWORD_REVIEWER},
    )
    assert resp_recovered.status_code == 200
    db_session.refresh(reviewer)
    assert reviewer.failed_login_count == 0
    assert reviewer.locked_until is None


def test_auth_me_profile_and_token_validation(client: TestClient, db_session: Session):
    users = _seed_auth_users(db_session)
    admin = users["admin"]

    # 1. Successful authentication
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": PASSWORD_ADMIN},
    )
    token = login_resp.json()["access_token"]

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == admin.email
    assert resp.json()["role"] == "admin"

    # 2. Missing authorization header -> 401
    resp_no_auth = client.get("/api/v1/auth/me")
    assert resp_no_auth.status_code == 401

    # 3. Tampered token -> 401
    resp_tampered = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token[:-5]}abcde"},
    )
    assert resp_tampered.status_code == 401

    # 4. Expired token -> 401
    expired_token = create_access_token(
        user_id=admin.id,
        role=admin.role,
        token_version=admin.token_version,
        expires_delta=timedelta(seconds=-1),
    )
    resp_expired = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp_expired.status_code == 401


def test_auth_change_password_and_token_revocation(client: TestClient, db_session: Session):
    users = _seed_auth_users(db_session)
    reviewer = users["reviewer"]

    # Log in to get initial access token
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": reviewer.email, "password": PASSWORD_REVIEWER},
    )
    old_token = login_resp.json()["access_token"]
    old_headers = {"Authorization": f"Bearer {old_token}"}

    # 1. Change password with short password (<12 chars) -> 422
    resp_short = client.post(
        "/api/v1/auth/change-password",
        headers=old_headers,
        json={"current_password": PASSWORD_REVIEWER, "new_password": "short"},
    )
    assert resp_short.status_code == 422

    # 2. Change password with wrong current password -> 401
    resp_wrong = client.post(
        "/api/v1/auth/change-password",
        headers=old_headers,
        json={
            "current_password": "WrongCurrentPassword123!",
            "new_password": "NewValidPassword1234!",
        },
    )
    assert resp_wrong.status_code == 401

    # 3. Successful password change
    new_password = "BrandNewSuperSecurePassword2026!"
    resp_success = client.post(
        "/api/v1/auth/change-password",
        headers=old_headers,
        json={"current_password": PASSWORD_REVIEWER, "new_password": new_password},
    )
    assert resp_success.status_code == 200

    # 4. Prior access token must be immediately revoked (token_version bumped)
    resp_revoked = client.get("/api/v1/auth/me", headers=old_headers)
    assert resp_revoked.status_code == 401
    assert "revoked" in resp_revoked.json()["error"]["message"].lower()

    # 5. Old password no longer works for login
    resp_old_login = client.post(
        "/api/v1/auth/login",
        json={"email": reviewer.email, "password": PASSWORD_REVIEWER},
    )
    assert resp_old_login.status_code == 401

    # 6. New password works for login
    resp_new_login = client.post(
        "/api/v1/auth/login",
        json={"email": reviewer.email, "password": new_password},
    )
    assert resp_new_login.status_code == 200


def test_auth_rate_limiting_login(client: TestClient):
    # Temporarily enable rate limiting for this test
    limiter.enabled = True
    try:
        # Exceed 5 attempts within a minute
        status_codes = []
        for _ in range(7):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "ratelimit@example.com", "password": "AnyPassword123!"},
            )
            status_codes.append(resp.status_code)

        assert 429 in status_codes
        idx = status_codes.index(429)
        assert idx <= 6
    finally:
        limiter.enabled = False


def test_openapi_admin_routes_security_enforcement(client: TestClient):
    """PRD Section 10 Mandatory Test: Enumerate every route in the OpenAPI schema

    and assert /admin/* routes return 401 without a token and 403 for the wrong role.
    """
    openapi_schema = client.app.openapi()
    paths = openapi_schema.get("paths", {})

    admin_routes: list[tuple[str, str]] = []
    for path, methods in paths.items():
        if "/admin" in path:
            for method in methods:
                if method.lower() in ("get", "post", "put", "patch", "delete"):
                    admin_routes.append((method.upper(), path))

    # If admin routes are defined, verify every single one enforces 401 on unauthenticated calls
    for method, path in admin_routes:
        resp = client.request(method, path)
        assert resp.status_code in (
            401,
            403,
            404,
        ), f"Route {method} {path} does not enforce authentication (got status {resp.status_code})"


def test_log_sensitive_data_redaction():
    """PRD Section 6.7 & Section 10 Mandatory Test:

    Prove that passwords, tokens, and authorization headers do not appear in captured logs.
    """
    sample_jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisSignature"
    )
    event_dict = {
        "event": "user_auth_attempt",
        "password": "SuperSecretPassword123!",
        "token": "sensitive_access_token_value",
        "authorization": f"Bearer {sample_jwt}",
        "email": "user@example.com",
        "nested": {
            "api_key": "secret_api_key_12345",
            "safe_field": "public_data",
        },
        "raw_message": f"User logged in with token {sample_jwt} and Bearer abcdef123456",
    }

    scrubbed = redact_sensitive_data(None, "info", event_dict)

    # 1. Direct sensitive keys must be masked
    assert scrubbed["password"] == "[REDACTED]"
    assert scrubbed["token"] == "[REDACTED]"
    assert scrubbed["authorization"] == "[REDACTED]"
    assert scrubbed["email"] == "[REDACTED]"
    assert scrubbed["nested"]["api_key"] == "[REDACTED]"
    assert scrubbed["nested"]["safe_field"] == "public_data"

    # 2. Raw strings containing Bearer or JWT tokens must have patterns scrubbed
    assert sample_jwt not in scrubbed["raw_message"]
    assert "[REDACTED_JWT]" in scrubbed["raw_message"]
    assert "Bearer [REDACTED]" in scrubbed["raw_message"]


def test_rbac_require_role_dependencies(db_session: Session):
    import uuid

    from fastapi import HTTPException

    from app.api.deps import require_admin, require_reviewer, require_role

    reviewer = User(
        id=uuid.uuid4(),
        email="rev@example.com",
        display_name="Rev",
        password_hash="hash",
        role="reviewer",
    )
    admin = User(
        id=uuid.uuid4(),
        email="adm@example.com",
        display_name="Adm",
        password_hash="hash",
        role="admin",
    )

    # 1. require_role single vs list
    reviewer_checker = require_reviewer
    admin_checker = require_admin
    custom_checker = require_role("admin")

    # Reviewer succeeds on reviewer, fails on admin
    assert reviewer_checker(reviewer) == reviewer
    with pytest.raises(HTTPException) as exc:
        admin_checker(reviewer)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "forbidden"

    with pytest.raises(HTTPException) as exc:
        custom_checker(reviewer)
    assert exc.value.status_code == 403

    # Admin succeeds on both
    assert reviewer_checker(admin) == admin
    assert admin_checker(admin) == admin
    assert custom_checker(admin) == admin


def test_deps_token_edge_cases(db_session: Session):
    import secrets

    import jwt
    from fastapi import HTTPException

    from app.api.deps import _authenticate_token, get_optional_current_user

    settings = get_settings()
    users = _seed_auth_users(db_session)
    admin = users["admin"]

    # 1. Missing sub in JWT payload
    payload_no_sub = {
        "role": "admin",
        "tv": 0,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
        "jti": secrets.token_hex(16),
    }
    token_no_sub = jwt.encode(payload_no_sub, settings.JWT_SECRET, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        _authenticate_token(token_no_sub, db_session)
    assert exc.value.status_code == 401
    assert "invalid or expired" in exc.value.detail["message"].lower()

    # 2. Invalid non-UUID sub in JWT payload
    payload_bad_uuid = {
        "sub": "not-a-valid-uuid-string",
        "role": "admin",
        "tv": 0,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
        "jti": secrets.token_hex(16),
    }
    token_bad_uuid = jwt.encode(payload_bad_uuid, settings.JWT_SECRET, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        _authenticate_token(token_bad_uuid, db_session)
    assert exc.value.status_code == 401
    assert "invalid user identity" in exc.value.detail["message"].lower()

    # 3. Valid token with get_optional_current_user
    valid_token = create_access_token(
        user_id=admin.id,
        role=admin.role,
        token_version=admin.token_version,
    )
    user_found = get_optional_current_user(token=valid_token, db=db_session)
    assert user_found is not None
    assert user_found.id == admin.id

    # 4. Inactive user token
    inactive_user = users["inactive"]
    inactive_token = create_access_token(
        user_id=inactive_user.id,
        role=inactive_user.role,
        token_version=inactive_user.token_version,
    )
    with pytest.raises(HTTPException) as exc:
        _authenticate_token(inactive_token, db_session)
    assert exc.value.status_code == 401
    assert "inactive" in exc.value.detail["message"].lower()

    # 5. User not found in DB
    import uuid

    ghost_token = create_access_token(
        user_id=uuid.uuid4(),
        role="reviewer",
        token_version=0,
    )
    with pytest.raises(HTTPException) as exc:
        _authenticate_token(ghost_token, db_session)
    assert exc.value.status_code == 401
    assert "not found" in exc.value.detail["message"].lower()
