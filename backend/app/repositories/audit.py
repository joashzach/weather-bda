"""Repository for persisting append-only audit events."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.audit_events import AuditEvent


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_event(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        actor_user_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
        ip_hash: str | None = None,
        created_at: datetime | None = None,
    ) -> AuditEvent:
        """Record an immutable audit event."""
        event = AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            event_metadata=metadata,
            ip_hash=ip_hash,
            created_at=created_at or datetime.now(UTC),
        )
        self.db.add(event)
        self.db.flush()
        return event
