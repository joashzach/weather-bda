from app.schemas.common import paginate_collection
"""Analytics REST API endpoints conforming to PRD Section 9."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_optional_current_user
from app.db.models.users import User
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    AnomaliesResponse,
    EventAnalyticsResponse,
    LocationsAnalyticsResponse,
    TimeseriesResponse,
)
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Analytics summary overview",
    description="Returns high-level summary of weather records, reports, data source freshness, and admin ingestion status.",
)
def get_analytics_summary(
    from_time: datetime | None = Query(
        None, alias="from", description="Inclusive start time (ISO 8601 UTC, default: 7 days ago)"
    ),
    to_time: datetime | None = Query(
        None, alias="to", description="Exclusive end time (ISO 8601 UTC, default: now)"
    ),
    location_id: int | None = Query(None, description="Optional location filter ID"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> AnalyticsSummaryResponse:
    return AnalyticsService.get_summary(
        db=db,
        from_time=from_time,
        to_time=to_time,
        location_id=location_id,
        current_user=current_user,
    )


@router.get(
    "/timeseries",
    response_model=TimeseriesResponse,
    summary="Aggregated weather metric timeseries",
    description="Returns time-bucketed aggregations (avg, min, max, sum, count) with optional gap filling and OLS trend analysis.",
)
def get_analytics_timeseries(
    location_id: int = Query(..., description="Target location ID"),
    metric: str = Query(
        ...,
        description="Metric field name (e.g., 'temperature_c', 'relative_humidity_pct', 'precipitation_mm', 'wind_speed_kmh')",
    ),
    from_time: datetime = Query(
        ..., alias="from", description="Inclusive start time (ISO 8601 UTC)"
    ),
    to_time: datetime = Query(
        ..., alias="to", description="Exclusive end time (ISO 8601 UTC, max 366 days span)"
    ),
    interval: Literal["hour", "day", "week", "month"] = Query(
        "hour", description="Bucketing interval (hour, day, week, month)"
    ),
    agg: Literal["avg", "min", "max", "sum", "count"] | None = Query(
        None, description="Aggregation function (default: avg; default: sum for precipitation_mm)"
    ),
    kind: Literal["observation", "forecast"] = Query(
        "observation", description="Record kind ('observation' or 'forecast')"
    ),
    fill_gaps: bool = Query(
        False,
        description="When true, generates contiguous series where missing buckets have null values",
    ),
    include_trend: bool = Query(
        False,
        description="When true, calculates ordinary least squares (OLS) linear regression trend",
    ),
    db: Session = Depends(get_db),
) -> TimeseriesResponse:
    return AnalyticsService.get_timeseries(
        db=db,
        location_id=location_id,
        metric=metric,
        from_time=from_time,
        to_time=to_time,
        interval=interval,
        agg=agg,
        kind=kind,
        fill_gaps=fill_gaps,
        include_trend=include_trend,
    )


@router.get(
    "/locations",
    response_model=LocationsAnalyticsResponse,
    summary="Comparative metrics per active location",
    description="Returns comparative weather statistics, data coverage percentage, and report counts across all active locations.",
)
def get_analytics_locations(
    from_time: datetime | None = Query(
        None, alias="from", description="Inclusive start time (ISO 8601 UTC, default: 7 days ago)"
    ),
    to_time: datetime | None = Query(
        None, alias="to", description="Exclusive end time (ISO 8601 UTC, default: now)"
    ),
    sort: str = Query(
        "name",
        description="Sorting field: 'name', '-name', 'record_count', '-record_count', 'coverage_pct', '-coverage_pct'",
    ),
    limit: int | None = Query(None, ge=1, le=200, description="Optional page size; clients use 50. Omit for the complete legacy response."),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> LocationsAnalyticsResponse:
    result = AnalyticsService.get_locations(
        db=db,
        from_time=from_time,
        to_time=to_time,
        sort=sort,
        current_user=current_user,
    )
    return paginate_collection(result, limit, offset)


@router.get(
    "/events",
    response_model=EventAnalyticsResponse,
    summary="Citizen report event counts",
    description="Aggregates verified disaster/weather citizen reports grouped by event_type, location, status, or day.",
)
def get_analytics_events(
    from_time: datetime | None = Query(
        None, alias="from", description="Inclusive start time (ISO 8601 UTC, default: 30 days ago)"
    ),
    to_time: datetime | None = Query(
        None, alias="to", description="Exclusive end time (ISO 8601 UTC, default: now)"
    ),
    group_by: Literal["event_type", "location", "status", "day"] = Query(
        "event_type", description="Grouping dimension ('event_type', 'location', 'status', 'day')"
    ),
    event_type: str | None = Query(None, description="Optional filter by specific event type"),
    location_id: int | None = Query(None, description="Optional filter by location ID"),
    status: str | None = Query(
        None,
        description="Optional filter by status (staff only; anonymous requests restricted to verified)",
    ),
    limit: int | None = Query(None, ge=1, le=200, description="Optional page size; clients use 50. Omit for the complete legacy response."),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> EventAnalyticsResponse:
    result = AnalyticsService.get_events(
        db=db,
        from_time=from_time,
        to_time=to_time,
        group_by=group_by,
        event_type=event_type,
        location_id=location_id,
        status_filter=status,
        current_user=current_user,
    )
    return paginate_collection(result, limit, offset)


@router.get(
    "/anomalies",
    response_model=AnomaliesResponse,
    summary="Statistical anomaly detection",
    description="Detects anomalous observation readings using modified z-scores against a 30-day baseline. NOT an official warning.",
)
def get_analytics_anomalies(
    location_id: int = Query(..., description="Target location ID"),
    metric: str = Query(..., description="Metric field name to evaluate"),
    from_time: datetime | None = Query(
        None, alias="from", description="Evaluation start time (ISO 8601 UTC, default: 7 days ago)"
    ),
    to_time: datetime | None = Query(
        None, alias="to", description="Evaluation end time (ISO 8601 UTC, default: now)"
    ),
    baseline_days: int = Query(
        30,
        ge=7,
        le=366,
        description="Number of baseline days prior to 'from' window (default: 30, min: 7)",
    ),
    threshold: float = Query(
        3.5, gt=0, description="Modified z-score threshold for anomaly flag (default: 3.5)"
    ),
    limit: int | None = Query(None, ge=1, le=200, description="Optional page size; clients use 50. Omit for the complete legacy response."),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
) -> AnomaliesResponse:
    result = AnalyticsService.get_anomalies(
        db=db,
        location_id=location_id,
        metric=metric,
        from_time=from_time,
        to_time=to_time,
        baseline_days=baseline_days,
        threshold=threshold,
    )
    return paginate_collection(result, limit, offset)
