"""Unit tests verifying sensitive information redaction in structured JSON logs."""

from app.core.logging import redact_sensitive_data


def test_redaction_scrubs_passwords_and_tokens() -> None:
    event = {
        "event": "user_action",
        "password": "super_secret_password_value",
        "token": "secret_session_token_12345",
        "user_email": "user@example.com",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0In0.dummy_sig",
        "nested": {
            "api_key": "sensitive_external_api_key",
            "private_notes": "reviewer notes containing confidential details",
        },
        "safe_field": "public_data",
    }

    redacted = redact_sensitive_data(None, "info", event)

    assert redacted["password"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["user_email"] == "[REDACTED]"
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["nested"]["api_key"] == "[REDACTED]"
    assert redacted["nested"]["private_notes"] == "[REDACTED]"
    assert redacted["safe_field"] == "public_data"


def test_redaction_scrubs_bearer_and_jwt_in_arbitrary_strings() -> None:
    event = {
        "event": "error_log",
        "error_message": "Header was Bearer abc123secretTokenValueHere",
    }

    redacted = redact_sensitive_data(None, "error", event)
    assert "abc123secretTokenValueHere" not in redacted["error_message"]
    assert "Bearer [REDACTED]" in redacted["error_message"]


def test_redaction_scrubs_lists_and_injects_context() -> None:
    from app.core.logging import configure_logging, request_id_ctx, user_id_ctx

    configure_logging("DEBUG")

    token_req = request_id_ctx.set("req-12345")
    token_user = user_id_ctx.set("user-67890")
    try:
        event = {
            "event": "batch",
            "items": [{"password": "secret_in_list"}],
        }
        redacted = redact_sensitive_data(None, "info", event)
        assert redacted["items"][0]["password"] == "[REDACTED]"
        assert redacted["request_id"] == "req-12345"
        assert redacted["user_id"] == "user-67890"
    finally:
        request_id_ctx.reset(token_req)
        user_id_ctx.reset(token_user)
