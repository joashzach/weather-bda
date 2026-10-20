"""Analytics service enforcing business rules, metric validations, date window defaults, and limits per PRD Section 9."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.analytics.anomaly import detect_anomalies
from app.analytics.queries import (
    query_analytics_events,
    query_analytics_locations,
    query_analytics_summary,
    query_analytics_timeseries,
)
from app.db.models.users import User
from app.repositories.locations import LocationRepository
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    AnomaliesResponse,
    EventAnalyticsResponse,
    LocationsAnalyticsResponse,
    TimeseriesResponse,
)

ALLOWED_METRICS = {
    "temperature_c",
    "apparent_temperature_c",
    "relative_humidity_pct",
    "precipitation_mm",
    "rain_mm",
    "precipitation_probability_pct",
    "wind_speed_kmh",
    "wind_gust_kmh",
    "wind_direction_deg",
}

ALLOWED_INTERVALS = {"hour", "day", "week", "month"}
ALLOWED_AGGS = {"avg", "min", "max", "sum", "count"}
ALLOWED_EVENT_GROUP_BY = {"event_type", "location", "status", "day"}
ALLOWED_LOCATION_SORTS = {
    "name",
    "-name",
    "record_count",
    "-record_count",
    "coverage_pct",
    "-coverage_pct",
}

MAX_TIMESERIES_BUCKETS = 2000
MAX_TIMESPAN_DAYS = 366


def _validate_time_window(
    from_time: datetime | None,
    to_time: datetime | None,
    default_days: int = 7,
    max_days: int = MAX_TIMESPAN_DAYS,
) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    eff_from = from_time
    eff_to = to_time

    if eff_from is None and eff_to is None:
        eff_from = now - timedelta(days=default_days)
        eff_to = now
    elif eff_from is None:
        eff_from = eff_to - timedelta(days=default_days)  # type: ignore
    elif eff_to is None:
        eff_to = now

    if eff_from.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_error",
                "message": "Query parameter 'from' must be a timezone-aware ISO 8601 instant",
            },
        )
    if eff_to.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_error",
                "message": "Query parameter 'to' must be a timezone-aware ISO 8601 instant",
            },
        )

    if eff_from >= eff_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_error",
                "message": "'from' timestamp must be strictly earlier than 'to' timestamp",
            },
        )

    span_days = (eff_to - eff_from).total_seconds() / 86400.0
    if span_days > max_days:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_error",
                "message": f"Requested time span ({span_days:.1f} days) exceeds maximum allowed span of {max_days} days",
            },
        )

    return eff_from, eff_to


class AnalyticsService:
    @staticmethod
    def get_summary(
        db: Session,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        location_id: int | None = None,
        current_user: User | None = None,
    ) -> AnalyticsSummaryResponse:
        eff_from, eff_to = _validate_time_window(from_time, to_time, default_days=7)

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

        is_staff = current_user is not None and current_user.role in ("reviewer", "admin")
        is_admin = current_user is not None and current_user.role == "admin"

        return query_analytics_summary(
            db=db,
            from_time=eff_from,
            to_time=eff_to,
            location_id=location_id,
            is_staff=is_staff,
            is_admin=is_admin,
        )

    @staticmethod
    def get_timeseries(
        db: Session,
        location_id: int,
        metric: str,
        from_time: datetime,
        to_time: datetime,
        interval: str = "hour",
        agg: str | None = None,
        kind: str = "observation",
        fill_gaps: bool = False,
        include_trend: bool = False,
    ) -> TimeseriesResponse:
        # 1. Location validation
        loc = LocationRepository(db).get_by_id(location_id)
        if not loc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "not_found",
                    "message": f"Location with id {location_id} not found",
                },
            )

        # 2. Metric validation
        if metric not in ALLOWED_METRICS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": f"Invalid metric '{metric}'. Allowed: {sorted(ALLOWED_METRICS)}",
                },
            )

        # 3. Interval validation
        if interval not in ALLOWED_INTERVALS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": f"Invalid interval '{interval}'. Allowed: {sorted(ALLOWED_INTERVALS)}",
                },
            )

        # 4. Aggregation default and rules
        effective_agg = agg
        if not effective_agg:
            effective_agg = "sum" if metric == "precipitation_mm" else "avg"

        if effective_agg not in ALLOWED_AGGS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": f"Invalid aggregation '{effective_agg}'. Allowed: {sorted(ALLOWED_AGGS)}",
                },
            )

        # PRD Section 9 Rule: Rainfall aggregates use SUM, never AVG of rates. sum is allowed only for precipitation.
        if effective_agg == "sum" and metric != "precipitation_mm":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": "Aggregation 'sum' is permitted only for 'precipitation_mm' metric",
                },
            )

        # 5. Kind validation
        if kind not in ("observation", "forecast"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": "kind must be 'observation' or 'forecast'",
                },
            )

        # 6. Time window validation
        eff_from, eff_to = _validate_time_window(from_time, to_time, max_days=366)

        # 7. Max buckets estimation check (PRD Section 9: > 2000 buckets returns 422)
        total_seconds = (eff_to - eff_from).total_seconds()
        interval_seconds_map = {
            "hour": 3600,
            "day": 86400,
            "week": 7 * 86400,
            "month": 30 * 86400,
        }
        estimated_buckets = total_seconds / interval_seconds_map[interval]
        if estimated_buckets > MAX_TIMESERIES_BUCKETS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": f"Requested interval and time range produces approximately {int(estimated_buckets)} buckets, exceeding the maximum limit of {MAX_TIMESERIES_BUCKETS}",
                },
            )

        return query_analytics_timeseries(
            db=db,
            location=loc,
            metric=metric,
            from_time=eff_from,
            to_time=eff_to,
            interval=interval,
            agg=effective_agg,
            kind=kind,
            fill_gaps=fill_gaps,
            include_trend=include_trend,
        )

    @staticmethod
    def get_locations(
        db: Session,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        sort: str = "name",
        current_user: User | None = None,
    ) -> LocationsAnalyticsResponse:
        eff_from, eff_to = _validate_time_window(from_time, to_time, default_days=7)

        if sort not in ALLOWED_LOCATION_SORTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": f"Invalid sort parameter '{sort}'. Allowed: {sorted(ALLOWED_LOCATION_SORTS)}",
                },
            )

        is_staff = current_user is not None and current_user.role in ("reviewer", "admin")

        return query_analytics_locations(
            db=db,
            from_time=eff_from,
            to_time=eff_to,
            sort=sort,
            is_staff=is_staff,
        )

    @staticmethod
    def get_events(
        db: Session,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        event_type: str | None = None,
        location_id: int | None = None,
        group_by: str = "event_type",
        status_filter: str | None = None,
        current_user: User | None = None,
    ) -> EventAnalyticsResponse:
        eff_from, eff_to = _validate_time_window(from_time, to_time, default_days=30)

        if group_by not in ALLOWED_EVENT_GROUP_BY:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": f"Invalid group_by '{group_by}'. Allowed: {sorted(ALLOWED_EVENT_GROUP_BY)}",
                },
            )

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

        is_staff = current_user is not None and current_user.role in ("reviewer", "admin")

        # PRD Section 9 Rule: Anonymous callers see only verified data; status parameter is staff only
        if not is_staff and status_filter and status_filter != "verified":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "forbidden",
                    "message": "Staff credentials required to filter by unverified report status",
                },
            )

        return query_analytics_events(
            db=db,
            from_time=eff_from,
            to_time=eff_to,
            group_by=group_by,
            event_type=event_type,
            location_id=location_id,
            status_filter=status_filter,
            is_staff=is_staff,
        )

    @staticmethod
    def get_anomalies(
        db: Session,
        location_id: int,
        metric: str,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        baseline_days: int = 30,
        threshold: float = 3.5,
    ) -> AnomaliesResponse:
        loc = LocationRepository(db).get_by_id(location_id)
        if not loc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "not_found",
                    "message": f"Location with id {location_id} not found",
                },
            )

        if metric not in ALLOWED_METRICS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": f"Invalid metric '{metric}'. Allowed: {sorted(ALLOWED_METRICS)}",
                },
            )

        if baseline_days < 7 or baseline_days > 366:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": "baseline_days must be between 7 and 366",
                },
            )

        if threshold <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": "threshold must be strictly positive",
                },
            )

        eff_from, eff_to = _validate_time_window(from_time, to_time, default_days=7)

        return detect_anomalies(
            db=db,
            location=loc,
            metric=metric,
            from_time=eff_from,
            to_time=eff_to,
            baseline_days=baseline_days,
            threshold=threshold,
        )
