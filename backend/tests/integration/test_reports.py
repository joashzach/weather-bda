"""Integration tests for Citizen Reports submission, visibility scoping, tracking token access,

moderation state transitions, concurrency locks, and privacy guarantees.
"""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.db.models.citizen_reports import CitizenReport
from app.db.models.locations import Location
from app.db.models.users import User
from app.repositories.users import UserRepository

PASSWORD_ADMIN = "AdminSecurePassword123!"
PASSWORD_REVIEWER = "ReviewerSecurePassword123!"


def _setup_test_context(db: Session) -> dict[str, str | Location | User]:
    user_repo = UserRepository(db)

    # 1. Ensure active location (Delhi)
    delhi = db.query(Location).filter(Location.slug == "delhi-reports-test").first()
    if not delhi:
        delhi = Location(
            slug="delhi-reports-test",
            name="Delhi Test Station",
            region="Delhi",
            country_code="IN",
            latitude=28.6139,
            longitude=77.2090,
            is_active=True,
        )
        db.add(delhi)

    # Far location (Mumbai)
    mumbai = db.query(Location).filter(Location.slug == "mumbai-reports-test").first()
    if not mumbai:
        mumbai = Location(
            slug="mumbai-reports-test",
            name="Mumbai Test Station",
            region="Maharashtra",
            country_code="IN",
            latitude=19.0760,
            longitude=72.8777,
            is_active=True,
        )
        db.add(mumbai)

    # 2. Staff users
    admin = user_repo.get_by_email("admin-rep@weatherbda.org")
    if not admin:
        admin = User(
            email="admin-rep@weatherbda.org",
            display_name="Admin Reports",
            password_hash=hash_password(PASSWORD_ADMIN),
            role="admin",
            is_active=True,
            token_version=0,
        )
        db.add(admin)

    reviewer = user_repo.get_by_email("reviewer-rep@weatherbda.org")
    if not reviewer:
        reviewer = User(
            email="reviewer-rep@weatherbda.org",
            display_name="Reviewer Reports",
            password_hash=hash_password(PASSWORD_REVIEWER),
            role="reviewer",
            is_active=True,
            token_version=0,
        )
        db.add(reviewer)

    db.commit()
    db.refresh(delhi)
    db.refresh(mumbai)
    db.refresh(admin)
    db.refresh(reviewer)

    admin_token = create_access_token(
        user_id=admin.id,
        role=admin.role,
        token_version=admin.token_version,
    )
    reviewer_token = create_access_token(
        user_id=reviewer.id,
        role=reviewer.role,
        token_version=reviewer.token_version,
    )

    return {
        "delhi": delhi,
        "mumbai": mumbai,
        "admin": admin,
        "reviewer": reviewer,
        "admin_token": admin_token,
        "reviewer_token": reviewer_token,
    }


def test_submit_report_success_and_proximity_assignment(client: TestClient, db_session: Session):
    ctx = _setup_test_context(db_session)
    delhi = ctx["delhi"]

    now = datetime.now(UTC)
    payload = {
        "event_type": "heavy_rain",
        "severity": "high",
        "description": "Flash flooding near Connaught Place metro station",
        "location_name": "Connaught Place",
        # ~2 km from Delhi test station
        "latitude": 28.6315,
        "longitude": 77.2167,
        "event_time": now.isoformat(),
        "evidence": [
            {
                "type": "photo",
                "url": "https://example.com/uploads/flood1.jpg",
                "description": "Submerged road",
            }
        ],
        "contact_email": "citizen@example.com",
    }

    resp = client.post("/api/v1/reports", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert "id" in data
    assert data["status"] == "pending"
    assert "submitted_at" in data
    assert "tracking_token" in data
    # Token must be a 32-byte URL-safe string (43 or 44 characters)
    assert len(data["tracking_token"]) >= 40

    # Verify DB state directly
    report_id = uuid.UUID(data["id"])
    db_report = db_session.query(CitizenReport).filter(CitizenReport.id == report_id).first()
    assert db_report is not None
    assert db_report.location_id == delhi.id  # Automatically assigned to Delhi
    assert db_report.ip_hash is not None
    assert db_report.tracking_token_hash is not None
    # Raw token must NOT be in DB
    assert data["tracking_token"] not in db_report.tracking_token_hash


def test_submit_report_extra_fields_forbidden(client: TestClient, db_session: Session):
    _setup_test_context(db_session)
    now = datetime.now(UTC)
    payload = {
        "event_type": "flood",
        "description": "Attempting to supply client-controlled status",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "event_time": now.isoformat(),
        "status": "verified",  # Extra field!
    }

    resp = client.post("/api/v1/reports", json=payload)
    assert resp.status_code == 422
    assert "extra" in resp.text.lower()


def test_submit_report_duplicate_within_1_hour_rejected(client: TestClient, db_session: Session):
    _setup_test_context(db_session)
    now = datetime.now(UTC)
    payload = {
        "event_type": "fog",
        "description": "Dense fog reducing visibility on outer ring road to near zero",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "event_time": now.isoformat(),
    }

    # 1. First submission succeeds
    resp1 = client.post("/api/v1/reports", json=payload)
    assert resp1.status_code == 201

    # 2. Duplicate submission within 1 hour rejected with 409
    resp2 = client.post("/api/v1/reports", json=payload)
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "conflict"
    assert "duplicate" in resp2.json()["error"]["message"].lower()


def test_get_report_visibility_lifecycle_and_tracking_token(
    client: TestClient, db_session: Session
):
    ctx = _setup_test_context(db_session)
    reviewer_token = ctx["reviewer_token"]
    admin_token = ctx["admin_token"]

    now = datetime.now(UTC)
    submit_resp = client.post(
        "/api/v1/reports",
        json={
            "event_type": "storm",
            "description": "Severe hailstorm damaging parked vehicles and trees",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "event_time": now.isoformat(),
            "contact_email": "submitter@example.org",
            "evidence": [
                {
                    "type": "photo",
                    "url": "https://storage.internal/evidence1.jpg",
                    "description": "Damaged windshield",
                }
            ],
        },
    )
    assert submit_resp.status_code == 201
    rep_data = submit_resp.json()
    report_id = rep_data["id"]
    tracking_token = rep_data["tracking_token"]

    # 1. While status is 'pending':
    # Anonymous caller without token -> 404 (not 403 to prevent enumeration)
    r_anon = client.get(f"/api/v1/reports/{report_id}")
    assert r_anon.status_code == 404

    # Anonymous caller with invalid token -> 404
    r_bad_tok = client.get(
        f"/api/v1/reports/{report_id}",
        headers={"X-Tracking-Token": "invalid_token_value_here_that_does_not_match"},
    )
    assert r_bad_tok.status_code == 404

    # Anonymous caller with correct token -> 200
    r_token = client.get(
        f"/api/v1/reports/{report_id}",
        headers={"X-Tracking-Token": tracking_token},
    )
    assert r_token.status_code == 200
    tok_data = r_token.json()
    assert tok_data["id"] == report_id
    assert tok_data["status"] == "pending"
    # Privacy check on tracking token response: sensitive fields absent
    assert "contact_email" not in tok_data
    assert "row_version" not in tok_data
    assert "reviewed_by" not in tok_data
    assert "url" not in tok_data["evidence"][0]
    assert tok_data["evidence"][0]["has_link"] is True

    # Staff caller (reviewer) -> 200 with staff fields
    r_staff = client.get(
        f"/api/v1/reports/{report_id}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert r_staff.status_code == 200
    staff_data = r_staff.json()
    assert staff_data["contact_email"] == "submitter@example.org"
    assert staff_data["row_version"] == 1
    assert staff_data["evidence"][0]["url"] == "https://storage.internal/evidence1.jpg"

    # 2. Reviewer verifies report
    r_verify = client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={
            "decision": "verify",
            "expected_row_version": 1,
        },
    )
    assert r_verify.status_code == 200
    assert r_verify.json()["status"] == "verified"
    assert r_verify.json()["row_version"] == 2

    # 3. Verified report is now visible to EVERYONE without token
    r_pub = client.get(f"/api/v1/reports/{report_id}")
    assert r_pub.status_code == 200
    pub_data = r_pub.json()
    assert pub_data["status"] == "verified"
    assert "contact_email" not in pub_data

    # 4. Admin retracts verified report (verified -> rejected)
    r_retract = client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "decision": "reject",
            "notes": "Determined to be unrelated localized incident",
            "reason_code": "not_weather_event",
            "expected_row_version": 2,
        },
    )
    assert r_retract.status_code == 200
    assert r_retract.json()["status"] == "rejected"
    assert r_retract.json()["row_version"] == 3

    # 5. Rejected report: anonymous without token -> 404
    assert client.get(f"/api/v1/reports/{report_id}").status_code == 404

    # Submitter with token -> 200 with status='rejected'
    r_rej_tok = client.get(
        f"/api/v1/reports/{report_id}",
        headers={"X-Tracking-Token": tracking_token},
    )
    assert r_rej_tok.status_code == 200
    assert r_rej_tok.json()["status"] == "rejected"


def test_public_endpoints_never_leak_forbidden_keys(client: TestClient, db_session: Session):
    """PRD Section 10 Forbidden Keys Test:

    Guarantees contact_email, ip_hash, tracking_token_hash, row_version,
    reviewed_by, and evidence URLs never appear in public endpoint responses.
    """
    ctx = _setup_test_context(db_session)
    reviewer_token = ctx["reviewer_token"]

    # Submit and verify a report
    submit_resp = client.post(
        "/api/v1/reports",
        json={
            "event_type": "heavy_rain",
            "description": "Torrential rain causing massive puddles on roadway",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "event_time": datetime.now(UTC).isoformat(),
            "contact_email": "citizen_leak_test@example.com",
            "evidence": [
                {
                    "type": "photo",
                    "url": "https://secret-bucket.s3.internal/private/leak_test.png",
                    "description": "Roadway puddles",
                }
            ],
        },
    )
    report_id = submit_resp.json()["id"]
    tracking_token = submit_resp.json()["tracking_token"]

    # Verify report so it appears on public list
    client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"decision": "verify", "expected_row_version": 1},
    )

    forbidden_keys = {
        "contact_email",
        "ip_hash",
        "tracking_token_hash",
        "row_version",
        "reviewed_by",
    }

    # 1. Inspect GET /api/v1/reports (list)
    r_list = client.get("/api/v1/reports")
    assert r_list.status_code == 200
    list_items = r_list.json()["items"]
    target_items = [i for i in list_items if i["id"] == report_id]
    assert len(target_items) == 1
    item = target_items[0]

    for key in forbidden_keys:
        assert key not in item, f"Forbidden key '{key}' leaked in public list response"
    assert "url" not in item["evidence"][0], "Evidence url leaked in public list response"
    assert item["evidence"][0]["has_link"] is True

    # 2. Inspect GET /api/v1/reports/{report_id} (public single)
    r_single = client.get(f"/api/v1/reports/{report_id}")
    assert r_single.status_code == 200
    single_data = r_single.json()
    for key in forbidden_keys:
        assert key not in single_data, f"Forbidden key '{key}' leaked in public single response"
    assert "url" not in single_data["evidence"][0], "Evidence url leaked in public single response"

    # 3. Inspect GET /api/v1/reports/{report_id} with X-Tracking-Token
    r_track = client.get(
        f"/api/v1/reports/{report_id}",
        headers={"X-Tracking-Token": tracking_token},
    )
    assert r_track.status_code == 200
    track_data = r_track.json()
    for key in forbidden_keys:
        assert key not in track_data, f"Forbidden key '{key}' leaked in tracking response"
    assert "url" not in track_data["evidence"][0], "Evidence url leaked in tracking response"


def test_list_reports_scoping_and_status_filter_rbac(client: TestClient, db_session: Session):
    ctx = _setup_test_context(db_session)
    reviewer_token = ctx["reviewer_token"]

    # 1. Non-staff attempting status filter receives 403 Forbidden
    r_anon_forbidden = client.get("/api/v1/reports?status=pending")
    assert r_anon_forbidden.status_code == 403
    assert r_anon_forbidden.json()["error"]["code"] == "forbidden"

    # 2. Non-staff receives only verified reports
    r_anon_ok = client.get("/api/v1/reports")
    assert r_anon_ok.status_code == 200
    for item in r_anon_ok.json()["items"]:
        assert item["status"] == "verified"

    # 3. Staff member can filter by pending, verified, rejected, all
    r_staff_pending = client.get(
        "/api/v1/reports?status=pending",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert r_staff_pending.status_code == 200
    for item in r_staff_pending.json()["items"]:
        assert item["status"] == "pending"

    r_staff_all = client.get(
        "/api/v1/reports?status=all",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert r_staff_all.status_code == 200


def test_admin_reports_pending_queue_oldest_first(client: TestClient, db_session: Session):
    ctx = _setup_test_context(db_session)
    reviewer_token = ctx["reviewer_token"]

    # Submit 2 pending reports with small delay
    now = datetime.now(UTC)
    r1 = client.post(
        "/api/v1/reports",
        json={
            "event_type": "flood",
            "description": "First flood report for queue ordering test",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "event_time": now.isoformat(),
        },
    )
    r2 = client.post(
        "/api/v1/reports",
        json={
            "event_type": "storm",
            "description": "Second storm report for queue ordering test",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "event_time": now.isoformat(),
        },
    )
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]

    resp = client.get(
        "/api/v1/admin/reports/pending",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    items = data["items"]

    # Verify all items in queue are pending
    for it in items:
        assert it["status"] == "pending"

    # Verify oldest first default ordering
    idx1 = next((i for i, x in enumerate(items) if x["id"] == id1), None)
    idx2 = next((i for i, x in enumerate(items) if x["id"] == id2), None)
    if idx1 is not None and idx2 is not None:
        assert idx1 < idx2, "Moderation queue must be ordered oldest first (submitted_at ASC)"


def test_moderation_transition_rules_and_permissions(client: TestClient, db_session: Session):
    ctx = _setup_test_context(db_session)
    reviewer_token = ctx["reviewer_token"]
    admin_token = ctx["admin_token"]

    # Submit report
    submit_resp = client.post(
        "/api/v1/reports",
        json={
            "event_type": "cyclone",
            "description": "High velocity wind gusts and damage in test scenario",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "event_time": datetime.now(UTC).isoformat(),
        },
    )
    report_id = submit_resp.json()["id"]

    # 1. Pending -> Reject without notes: 422
    r_no_notes = client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"decision": "reject", "expected_row_version": 1},
    )
    assert r_no_notes.status_code == 422

    # 2. Pending -> Verify: succeeds without notes (row_version: 1 -> 2)
    r_verify = client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"decision": "verify", "expected_row_version": 1},
    )
    assert r_verify.status_code == 200
    assert r_verify.json()["status"] == "verified"

    # 3. Verified -> Retract (reject): Reviewer gets 403 (admin only!)
    r_rev_retract = client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"decision": "reject", "notes": "Retracting", "expected_row_version": 2},
    )
    assert r_rev_retract.status_code == 403

    # Admin retracts: succeeds (row_version: 2 -> 3)
    r_adm_retract = client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "decision": "reject",
            "notes": "Admin retracted false report",
            "expected_row_version": 2,
        },
    )
    assert r_adm_retract.status_code == 200
    assert r_adm_retract.json()["status"] == "rejected"

    # 4. Rejected -> Reopen: Reviewer gets 403 (admin only!)
    r_rev_reopen = client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"decision": "reopen", "notes": "Reopening", "expected_row_version": 3},
    )
    assert r_rev_reopen.status_code == 403

    # Admin reopens: succeeds (row_version: 3 -> 4)
    r_adm_reopen = client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "decision": "reopen",
            "notes": "Admin reopened for further investigation",
            "expected_row_version": 3,
        },
    )
    assert r_adm_reopen.status_code == 200
    assert r_adm_reopen.json()["status"] == "pending"

    # 5. Invalid transition: pending -> reopen: returns 409 invalid_transition
    r_inv = client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "reopen", "notes": "Illegal move", "expected_row_version": 4},
    )
    assert r_inv.status_code == 409
    assert r_inv.json()["error"]["code"] == "invalid_transition"


def test_concurrency_stale_row_version(client: TestClient, db_session: Session):
    ctx = _setup_test_context(db_session)
    reviewer_token = ctx["reviewer_token"]

    submit_resp = client.post(
        "/api/v1/reports",
        json={
            "event_type": "fog",
            "description": "Concurrency version conflict test report",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "event_time": datetime.now(UTC).isoformat(),
        },
    )
    report_id = submit_resp.json()["id"]

    # Attempt review with stale expected_row_version (actual is 1, providing 999)
    resp = client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"decision": "verify", "expected_row_version": 999},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "stale_version"
    assert "mismatch" in resp.json()["error"]["message"].lower()


def test_admin_reviews_history_audit_trail(client: TestClient, db_session: Session):
    ctx = _setup_test_context(db_session)
    reviewer = ctx["reviewer"]
    reviewer_token = ctx["reviewer_token"]
    admin = ctx["admin"]
    admin_token = ctx["admin_token"]

    submit_resp = client.post(
        "/api/v1/reports",
        json={
            "event_type": "heavy_rain",
            "description": "Audit history test report for multiple state reviews",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "event_time": datetime.now(UTC).isoformat(),
        },
    )
    report_id = submit_resp.json()["id"]

    # 1. Reviewer verifies
    client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={
            "decision": "verify",
            "notes": "Verified against radar imagery",
            "expected_row_version": 1,
        },
    )

    # 2. Admin retracts
    client.post(
        f"/api/v1/admin/reports/{report_id}/review",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "decision": "reject",
            "notes": "Citizen retracted original submission via contact form",
            "reason_code": "user_retracted",
            "expected_row_version": 2,
        },
    )

    # 3. Query review history
    resp = client.get(
        f"/api/v1/admin/reports/{report_id}/reviews",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    items = data["items"]
    assert len(items) == 2

    # Chronological order
    rev1 = items[0]
    assert rev1["from_status"] == "pending"
    assert rev1["to_status"] == "verified"
    assert rev1["reviewer"]["id"] == str(reviewer.id)
    assert rev1["private_notes"] == "Verified against radar imagery"

    rev2 = items[1]
    assert rev2["from_status"] == "verified"
    assert rev2["to_status"] == "rejected"
    assert rev2["reviewer"]["id"] == str(admin.id)
    assert rev2["reason_code"] == "user_retracted"
    assert rev2["private_notes"] == "Citizen retracted original submission via contact form"
