"""Data source repository handling persistence and querying of reference data sources."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models.data_sources import DataSource


class DataSourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, source_id: int) -> DataSource | None:
        return self.db.execute(
            select(DataSource).where(DataSource.id == source_id)
        ).scalar_one_or_none()

    def get_by_name(self, name: str) -> DataSource | None:
        return self.db.execute(
            select(DataSource).where(DataSource.name == name.strip())
        ).scalar_one_or_none()

    def list_all(self) -> Sequence[DataSource]:
        stmt = select(DataSource).order_by(DataSource.name.asc())
        return self.db.execute(stmt).scalars().all()

    def list_enabled(self) -> Sequence[DataSource]:
        stmt = (
            select(DataSource)
            .where(DataSource.is_enabled.is_(True))
            .order_by(DataSource.name.asc())
        )
        return self.db.execute(stmt).scalars().all()

    def upsert(
        self,
        name: str,
        display_name: str,
        source_type: str,
        adapter_key: str,
        trust_level: str,
        interval_seconds: int = 3600,
        is_enabled: bool = False,
        config: dict[str, Any] | None = None,
        attribution_text: str | None = None,
        license_url: str | None = None,
        homepage_url: str | None = None,
    ) -> DataSource:
        """Idempotent upsert by name using PostgreSQL ON CONFLICT."""
        normalized_name = name.strip()
        stmt = (
            insert(DataSource)
            .values(
                name=normalized_name,
                display_name=display_name.strip(),
                source_type=source_type,
                adapter_key=adapter_key,
                trust_level=trust_level,
                interval_seconds=interval_seconds,
                is_enabled=is_enabled,
                config=config or {},
                attribution_text=attribution_text,
                license_url=license_url,
                homepage_url=homepage_url,
            )
            .on_conflict_do_update(
                index_elements=[DataSource.name],
                set_={
                    "display_name": display_name.strip(),
                    "source_type": source_type,
                    "adapter_key": adapter_key,
                    "trust_level": trust_level,
                    "attribution_text": attribution_text,
                    "license_url": license_url,
                    "homepage_url": homepage_url,
                },
            )
            .returning(DataSource)
        )
        source = self.db.execute(stmt).scalar_one()
        return source

    def update_timestamps(
        self,
        source_id: int,
        last_attempt_at: datetime,
        last_success_at: datetime | None = None,
    ) -> None:
        source = self.get_by_id(source_id)
        if source:
            source.last_attempt_at = last_attempt_at
            if last_success_at:
                source.last_success_at = last_success_at
            self.db.flush()
