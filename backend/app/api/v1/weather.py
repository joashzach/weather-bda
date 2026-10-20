"""Weather API routes conforming to PRD Section 7.2 and 7.3."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.weather import (
    WeatherLatestResponse,
    WeatherRecordListResponse,
    WeatherRecordPublic,
)
from app.services.weather import WeatherService

router = APIRouter(prefix="/weather", tags=["Weather"])


@router.get(
    "",
    response_model=WeatherRecordListResponse,
    summary="List weather records",
    description="List observations and forecasts with date range, source, location, and sorting filters.",
)
def list_weather(
    location_id: int | None = Query(None, description="Location ID filter"),
    kind: Literal["observation", "forecast", "all"] = Query(
        "observation", description="Record kind ('observation', 'forecast', or 'all')"
    ),
    source: str | None = Query(None, description="Data source name filter (e.g. 'open_meteo')"),
    from_time: datetime | None = Query(
        None, alias="from", description="Inclusive start time (ISO 8601 UTC)"
    ),
    to_time: datetime | None = Query(
        None, alias="to", description="Exclusive end time (ISO 8601 UTC)"
    ),
    sort: str = Query(
        "-valid_at", description="Sort parameter ('valid_at' or '-valid_at', default '-valid_at')"
    ),
    limit: int = Query(50, ge=1, le=500, description="Page limit (default 50, max 500)"),
    offset: int = Query(0, ge=0, description="Page offset (default 0)"),
    db: Session = Depends(get_db),
) -> WeatherRecordListResponse:
    return WeatherService.list_records(
        db=db,
        location_id=location_id,
        kind=kind,
        source=source,
        from_time=from_time,
        to_time=to_time,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/latest",
    response_model=WeatherLatestResponse,
    summary="Latest record per active location",
    description="Returns the newest observation (valid_at <= now) or earliest forecast (valid_at >= now) per active location.",
)
def get_latest_weather(
    location_id: int | None = Query(None, description="Optional location ID filter"),
    kind: Literal["observation", "forecast"] = Query(
        "observation", description="Record kind ('observation' or 'forecast')"
    ),
    db: Session = Depends(get_db),
) -> WeatherLatestResponse:
    return WeatherService.get_latest(
        db=db,
        location_id=location_id,
        kind=kind,
    )


@router.get(
    "/{id}",
    response_model=WeatherRecordPublic,
    summary="Get weather record by ID",
    description="Retrieve a single weather record by integer ID.",
)
def get_weather_by_id(
    id: int = Path(..., ge=1, description="Unique weather record ID"),
    db: Session = Depends(get_db),
) -> WeatherRecordPublic:
    return WeatherService.get_record(db=db, record_id=id)
