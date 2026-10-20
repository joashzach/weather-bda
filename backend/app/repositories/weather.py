"""Weather records repository handling persistence, content-hash deduplication, and querying."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload

from app.db.models.data_sources import DataSource
from app.db.models.locations import Location
from app.db.models.weather_records import WeatherRecord


class WeatherRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, record_id: int) -> WeatherRecord | None:
        stmt = (
            select(WeatherRecord)
            .options(joinedload(WeatherRecord.location), joinedload(WeatherRecord.source))
            .where(WeatherRecord.id == record_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_records(
        self,
        location_id: int | None = None,
        kind: str = "observation",
        source_name: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        sort_desc: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[WeatherRecord], int]:
        """Query weather records with filtering, total count, and deterministic sorting."""
        conditions = []

        if location_id is not None:
            conditions.append(WeatherRecord.location_id == location_id)

        if kind and kind != "all":
            conditions.append(WeatherRecord.record_kind == kind)

        if source_name:
            conditions.append(
                WeatherRecord.source_id.in_(
                    select(DataSource.id).where(DataSource.name == source_name.strip())
                )
            )

        if from_time is not None:
            conditions.append(WeatherRecord.valid_at >= from_time)

        if to_time is not None:
            # PRD Section 7.1: from <= t < to (exclusive upper bound)
            conditions.append(WeatherRecord.valid_at < to_time)

        # Count total matches
        count_stmt = select(func.count(WeatherRecord.id)).where(*conditions)
        total = self.db.execute(count_stmt).scalar_one()

        # Build order by with deterministic tie-break on id
        if sort_desc:
            order_clause = [WeatherRecord.valid_at.desc(), WeatherRecord.id.desc()]
        else:
            order_clause = [WeatherRecord.valid_at.asc(), WeatherRecord.id.asc()]

        stmt = (
            select(WeatherRecord)
            .options(joinedload(WeatherRecord.location), joinedload(WeatherRecord.source))
            .where(*conditions)
            .order_by(*order_clause)
            .limit(limit)
            .offset(offset)
        )
        records = self.db.execute(stmt).scalars().all()
        return records, total

    def get_latest(
        self,
        location_id: int | None = None,
        kind: str = "observation",
        as_of: datetime | None = None,
    ) -> tuple[list[WeatherRecord], list[int]]:
        """Retrieve latest observation (valid_at <= as_of) or earliest forecast (valid_at >= as_of)."""
        now = as_of or datetime.now(UTC)

        # 1. Identify active locations
        active_loc_query = select(Location.id).where(Location.is_active.is_(True))
        if location_id is not None:
            active_loc_query = active_loc_query.where(Location.id == location_id)
        active_location_ids = set(self.db.execute(active_loc_query).scalars().all())

        if not active_location_ids:
            return [], []

        # 2. Window ranking per location
        if kind == "forecast":
            # Earliest forecast from now into the future
            rank_order = WeatherRecord.valid_at.asc()
            time_filter = WeatherRecord.valid_at >= now
        else:
            # Newest observation up to current time
            rank_order = WeatherRecord.valid_at.desc()
            time_filter = WeatherRecord.valid_at <= now

        rn = (
            func.row_number()
            .over(
                partition_by=WeatherRecord.location_id,
                order_by=[rank_order, WeatherRecord.id.desc()],
            )
            .label("rn")
        )

        subquery = (
            select(WeatherRecord.id, rn)
            .where(
                WeatherRecord.location_id.in_(active_location_ids),
                WeatherRecord.record_kind == kind,
                time_filter,
            )
            .subquery()
        )

        latest_stmt = (
            select(WeatherRecord)
            .join(subquery, WeatherRecord.id == subquery.c.id)
            .options(joinedload(WeatherRecord.location), joinedload(WeatherRecord.source))
            .where(subquery.c.rn == 1)
            .order_by(WeatherRecord.location_id.asc())
        )

        records = list(self.db.execute(latest_stmt).scalars().all())

        # Determine missing location IDs
        found_location_ids = {r.location_id for r in records}
        missing_location_ids = sorted(active_location_ids - found_location_ids)

        return records, missing_location_ids

    def bulk_upsert(self, records_data: list[dict[str, Any]]) -> dict[str, int]:
        """Bulk upsert with ON CONFLICT content_hash comparison. Return counters."""
        if not records_data:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        stmt = (
            insert(WeatherRecord)
            .values(records_data)
            .on_conflict_do_update(
                index_elements=[
                    WeatherRecord.location_id,
                    WeatherRecord.source_id,
                    WeatherRecord.record_kind,
                    WeatherRecord.valid_at,
                ],
                set_={
                    "measurement_basis": insert(WeatherRecord).excluded.measurement_basis,
                    "issued_at": insert(WeatherRecord).excluded.issued_at,
                    "resolution_seconds": insert(WeatherRecord).excluded.resolution_seconds,
                    "temperature_c": insert(WeatherRecord).excluded.temperature_c,
                    "apparent_temperature_c": insert(WeatherRecord).excluded.apparent_temperature_c,
                    "relative_humidity_pct": insert(WeatherRecord).excluded.relative_humidity_pct,
                    "precipitation_mm": insert(WeatherRecord).excluded.precipitation_mm,
                    "rain_mm": insert(WeatherRecord).excluded.rain_mm,
                    "precipitation_probability_pct": insert(
                        WeatherRecord
                    ).excluded.precipitation_probability_pct,
                    "wind_speed_kmh": insert(WeatherRecord).excluded.wind_speed_kmh,
                    "wind_gust_kmh": insert(WeatherRecord).excluded.wind_gust_kmh,
                    "wind_direction_deg": insert(WeatherRecord).excluded.wind_direction_deg,
                    "content_hash": insert(WeatherRecord).excluded.content_hash,
                    "fetched_at": insert(WeatherRecord).excluded.fetched_at,
                    "ingestion_run_id": insert(WeatherRecord).excluded.ingestion_run_id,
                },
                where=(
                    WeatherRecord.content_hash.is_distinct_from(
                        insert(WeatherRecord).excluded.content_hash
                    )
                ),
            )
            .returning(literal_column("(xmax = 0)").label("is_insert"))
        )

        results = self.db.execute(stmt).fetchall()
        inserted = sum(1 for r in results if r.is_insert)
        updated = sum(1 for r in results if not r.is_insert)
        skipped = len(records_data) - (inserted + updated)

        self.db.flush()
        return {"inserted": inserted, "updated": updated, "skipped": skipped}
