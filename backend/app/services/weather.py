"""Weather service implementing business validations, default date window logic, and schema mappings."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.weather_records import WeatherRecord
from app.repositories.locations import LocationRepository
from app.repositories.weather import WeatherRepository
from app.schemas.weather import (
    WeatherLatestResponse,
    WeatherMeasurements,
    WeatherRecordListResponse,
    WeatherRecordLocation,
    WeatherRecordPublic,
    WeatherRecordSource,
)


def _map_record_to_public(r: WeatherRecord) -> WeatherRecordPublic:
    return WeatherRecordPublic(
        id=r.id,
        kind=r.record_kind,
        valid_at=r.valid_at,
        issued_at=r.issued_at,
        fetched_at=r.fetched_at,
        measurement_basis=r.measurement_basis,
        resolution_seconds=r.resolution_seconds,
        location=WeatherRecordLocation(
            id=r.location.id,
            slug=r.location.slug,
            name=r.location.name,
        ),
        source=WeatherRecordSource(
            name=r.source.name,
            display_name=r.source.display_name,
            trust_level=r.source.trust_level,
            attribution_text=r.source.attribution_text,
        ),
        measurements=WeatherMeasurements(
            temperature_c=float(r.temperature_c) if r.temperature_c is not None else None,
            apparent_temperature_c=float(r.apparent_temperature_c)
            if r.apparent_temperature_c is not None
            else None,
            relative_humidity_pct=float(r.relative_humidity_pct)
            if r.relative_humidity_pct is not None
            else None,
            precipitation_mm=float(r.precipitation_mm) if r.precipitation_mm is not None else None,
            rain_mm=float(r.rain_mm) if r.rain_mm is not None else None,
            precipitation_probability_pct=r.precipitation_probability_pct,
            wind_speed_kmh=float(r.wind_speed_kmh) if r.wind_speed_kmh is not None else None,
            wind_gust_kmh=float(r.wind_gust_kmh) if r.wind_gust_kmh is not None else None,
            wind_direction_deg=float(r.wind_direction_deg)
            if r.wind_direction_deg is not None
            else None,
        ),
    )


class WeatherService:
    @staticmethod
    def get_record(db: Session, record_id: int) -> WeatherRecordPublic:
        repo = WeatherRepository(db)
        record = repo.get_by_id(record_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "not_found",
                    "message": f"Weather record with id {record_id} not found",
                },
            )
        return _map_record_to_public(record)

    @staticmethod
    def list_records(
        db: Session,
        location_id: int | None = None,
        kind: str = "observation",
        source: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        sort: str = "-valid_at",
        limit: int = 50,
        offset: int = 0,
    ) -> WeatherRecordListResponse:
        now = datetime.now(UTC)

        # 1. Validate location if specified
        if location_id is not None:
            loc = LocationRepository(db).get_by_id(location_id)
            if not loc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "not_found",
                        "message": f"Location with id {location_id} not found",
                    },
                )

        # 2. Validate timezone awareness
        if from_time is not None and from_time.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": "Query parameter 'from' must be a timezone-aware ISO 8601 instant",
                },
            )
        if to_time is not None and to_time.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": "Query parameter 'to' must be a timezone-aware ISO 8601 instant",
                },
            )

        # 3. Apply default time window when from/to omitted (PRD Section 7.3)
        effective_from = from_time
        effective_to = to_time

        if effective_from is None and effective_to is None:
            if kind == "forecast":
                effective_from = now
                effective_to = now + timedelta(hours=72)
            elif kind == "all":
                effective_from = now - timedelta(hours=24)
                effective_to = now + timedelta(hours=72)
            else:  # observation default
                effective_from = now - timedelta(hours=24)
                effective_to = now

        # 4. Validate span and ordering
        if effective_from is not None and effective_to is not None:
            if effective_from >= effective_to:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "validation_error",
                        "message": "'from' timestamp must be strictly earlier than 'to' timestamp",
                    },
                )
            if (effective_to - effective_from).total_seconds() > 31 * 86400:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "validation_error",
                        "message": "Requested time span exceeds maximum allowed span of 31 days",
                    },
                )

        # 5. Sorting allow-list
        sort_desc = sort.startswith("-")
        clean_sort = sort.lstrip("-")
        if clean_sort != "valid_at":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": f"Invalid sort field '{sort}'. Allowed: 'valid_at', '-valid_at'",
                },
            )

        repo = WeatherRepository(db)
        records, total = repo.list_records(
            location_id=location_id,
            kind=kind,
            source_name=source,
            from_time=effective_from,
            to_time=effective_to,
            sort_desc=sort_desc,
            limit=limit,
            offset=offset,
        )

        items = [_map_record_to_public(r) for r in records]
        return WeatherRecordListResponse(items=items, total=total, limit=limit, offset=offset)

    @staticmethod
    def get_latest(
        db: Session,
        location_id: int | None = None,
        kind: str = "observation",
    ) -> WeatherLatestResponse:
        now = datetime.now(UTC)

        if location_id is not None:
            loc = LocationRepository(db).get_by_id(location_id)
            if not loc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "not_found",
                        "message": f"Location with id {location_id} not found",
                    },
                )

        if kind not in ("observation", "forecast"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": "kind must be 'observation' or 'forecast'",
                },
            )

        repo = WeatherRepository(db)
        records, missing_location_ids = repo.get_latest(
            location_id=location_id,
            kind=kind,
            as_of=now,
        )

        items = [_map_record_to_public(r) for r in records]
        return WeatherLatestResponse(
            as_of=now, items=items, missing_location_ids=missing_location_ids
        )
