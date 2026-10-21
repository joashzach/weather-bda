"""PostgreSQL aggregation queries for analytics conforming to PRD Section 9."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session

from app.db.models.citizen_reports import CitizenReport
from app.db.models.data_sources import DataSource
from app.db.models.ingestion_runs import IngestionRun
from app.db.models.locations import Location
from app.db.models.weather_records import WeatherRecord
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    EventAnalyticsItem,
    EventAnalyticsResponse,
    EventAnalyticsTotals,
    IngestionSummary,
    LocationAnalyticsItem,
    LocationsAnalyticsResponse,
    PeriodSchema,
    ReportsSummary,
    SourceSummaryItem,
    TemperatureSummary,
    TimeseriesBucket,
    TimeseriesLocation,
    TimeseriesResponse,
    TimeseriesSourceItem,
    TimeseriesTrend,
    WeatherRecordCounts,
    WeatherSummary,
    WindSummary,
)

METRIC_UNITS = {
    "temperature_c": "°C",
    "apparent_temperature_c": "°C",
    "relative_humidity_pct": "%",
    "precipitation_mm": "mm",
    "rain_mm": "mm",
    "precipitation_probability_pct": "%",
    "wind_speed_kmh": "km/h",
    "wind_gust_kmh": "km/h",
    "wind_direction_deg": "°",
}


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    return float(val)


def query_analytics_summary(
    db: Session,
    from_time: datetime,
    to_time: datetime,
    location_id: int | None = None,
    is_staff: bool = False,
    is_admin: bool = False,
) -> AnalyticsSummaryResponse:
    now = datetime.now(UTC)

    # 1. Weather record counts by kind
    counts_stmt = (
        select(WeatherRecord.record_kind, func.count().label("cnt"))
        .where(WeatherRecord.valid_at >= from_time, WeatherRecord.valid_at <= to_time)
        .group_by(WeatherRecord.record_kind)
    )
    if location_id is not None:
        counts_stmt = counts_stmt.where(WeatherRecord.location_id == location_id)

    obs_count = 0
    fc_count = 0
    for row in db.execute(counts_stmt):
        if row.record_kind == "observation":
            obs_count = row.cnt
        elif row.record_kind == "forecast":
            fc_count = row.cnt

    # 2. Locations with data (observations only)
    loc_with_data_stmt = select(func.count(func.distinct(WeatherRecord.location_id))).where(
        WeatherRecord.valid_at >= from_time,
        WeatherRecord.valid_at <= to_time,
        WeatherRecord.record_kind == "observation",
    )
    if location_id is not None:
        loc_with_data_stmt = loc_with_data_stmt.where(WeatherRecord.location_id == location_id)
    locations_with_data = db.scalar(loc_with_data_stmt) or 0

    # 3. Temperature aggregates (observations only)
    # min and max
    temp_min_max_stmt = select(
        func.min(WeatherRecord.temperature_c).label("min_t"),
        func.max(WeatherRecord.temperature_c).label("max_t"),
    ).where(
        WeatherRecord.valid_at >= from_time,
        WeatherRecord.valid_at <= to_time,
        WeatherRecord.record_kind == "observation",
    )
    if location_id is not None:
        temp_min_max_stmt = temp_min_max_stmt.where(WeatherRecord.location_id == location_id)
    temp_row = db.execute(temp_min_max_stmt).first()
    t_min = _to_float(temp_row.min_t) if temp_row else None
    t_max = _to_float(temp_row.max_t) if temp_row else None

    # mean_of_location_means
    subq = select(func.avg(WeatherRecord.temperature_c).label("loc_mean")).where(
        WeatherRecord.valid_at >= from_time,
        WeatherRecord.valid_at <= to_time,
        WeatherRecord.record_kind == "observation",
        WeatherRecord.temperature_c.is_not(None),
    )
    if location_id is not None:
        subq = subq.where(WeatherRecord.location_id == location_id)
    subq = subq.group_by(WeatherRecord.location_id).subquery()
    mean_of_means = db.scalar(select(func.avg(subq.c.loc_mean)))
    t_mean_of_means = _to_float(mean_of_means)

    # 4. Wind aggregates (observations only, direction is never arithmetically averaged)
    wind_stmt = select(
        func.avg(WeatherRecord.wind_speed_kmh).label("avg_spd"),
        func.max(WeatherRecord.wind_gust_kmh).label("max_gst"),
    ).where(
        WeatherRecord.valid_at >= from_time,
        WeatherRecord.valid_at <= to_time,
        WeatherRecord.record_kind == "observation",
    )
    if location_id is not None:
        wind_stmt = wind_stmt.where(WeatherRecord.location_id == location_id)
    wind_row = db.execute(wind_stmt).first()
    avg_speed = _to_float(wind_row.avg_spd) if wind_row else None
    max_gust = _to_float(wind_row.max_gst) if wind_row else None

    # 5. Reports Summary (Section 9: Anonymous see only verified; staff see pending/rejected)
    rep_stmt = (
        select(CitizenReport.status, func.count().label("cnt"))
        .where(CitizenReport.event_time >= from_time, CitizenReport.event_time <= to_time)
        .group_by(CitizenReport.status)
    )
    if location_id is not None:
        rep_stmt = rep_stmt.where(CitizenReport.location_id == location_id)

    raw_rep_counts = {row.status: row.cnt for row in db.execute(rep_stmt)}

    if is_staff:
        rep_by_status = {
            "verified": raw_rep_counts.get("verified", 0),
            "pending": raw_rep_counts.get("pending", 0),
            "rejected": raw_rep_counts.get("rejected", 0),
        }
        total_reports = sum(rep_by_status.values())
    else:
        verified_count = raw_rep_counts.get("verified", 0)
        rep_by_status = {"verified": verified_count}
        total_reports = verified_count

    # 6. Sources Summary with freshness computation
    sources = db.query(DataSource).all()
    source_items: list[SourceSummaryItem] = []
    for s in sources:
        if not s.is_enabled:
            freshness = "disabled"
        elif s.last_success_at is None:
            freshness = "never"
        else:
            diff_sec = (now - s.last_success_at).total_seconds()
            freshness = "fresh" if diff_sec <= (2 * s.interval_seconds) else "stale"

        source_items.append(
            SourceSummaryItem(
                name=s.name,
                display_name=s.display_name,
                source_type=s.source_type,
                trust_level=s.trust_level,
                freshness=freshness,
                last_success_at=s.last_success_at,
                attribution_text=s.attribution_text,
                license_url=s.license_url,
                homepage_url=s.homepage_url,
            )
        )

    # 7. Ingestion Summary (admin only)
    ingestion_summary = None
    if is_admin:
        runs_stmt = (
            select(IngestionRun.status, func.count().label("cnt"))
            .where(IngestionRun.started_at >= from_time, IngestionRun.started_at <= to_time)
            .group_by(IngestionRun.status)
        )
        runs_counts = {row.status: row.cnt for row in db.execute(runs_stmt)}
        total_runs = sum(runs_counts.values())
        successful_runs = runs_counts.get("succeeded", 0) + runs_counts.get("partial", 0)
        success_rate = (successful_runs / total_runs) if total_runs > 0 else 0.0

        last_fail_stmt = select(func.max(IngestionRun.finished_at)).where(
            IngestionRun.status == "failed",
            IngestionRun.started_at >= from_time,
            IngestionRun.started_at <= to_time,
        )
        last_failure_at = db.scalar(last_fail_stmt)

        ingestion_summary = IngestionSummary(
            runs_by_status=runs_counts,
            success_rate=round(success_rate, 4),
            last_failure_at=last_failure_at,
        )

    return AnalyticsSummaryResponse(
        period=PeriodSchema.model_validate({"from": from_time, "to": to_time}),
        weather=WeatherSummary(
            record_counts=WeatherRecordCounts(observation=obs_count, forecast=fc_count),
            records_by_kind=WeatherRecordCounts(observation=obs_count, forecast=fc_count),
            locations_with_data=locations_with_data,
            temperature_c=TemperatureSummary(
                min=t_min, mean_of_location_means=t_mean_of_means, max=t_max
            ),
            wind=WindSummary(mean_speed_kmh=avg_speed, max_gust_kmh=max_gust),
        ),
        reports=ReportsSummary(total=total_reports, by_status=rep_by_status),
        sources=source_items,
        ingestion=ingestion_summary,
    )


def query_analytics_timeseries(
    db: Session,
    location: Location,
    metric: str,
    from_time: datetime,
    to_time: datetime,
    interval: str = "hour",
    agg: str = "avg",
    kind: str = "observation",
    fill_gaps: bool = False,
    include_trend: bool = False,
) -> TimeseriesResponse:
    unit = METRIC_UNITS.get(metric, "")

    interval_step_map = {
        "hour": "1 hour",
        "day": "1 day",
        "week": "1 week",
        "month": "1 month",
    }
    step_interval = interval_step_map[interval]

    buckets: list[TimeseriesBucket] = []

    if fill_gaps:
        # SQL with generate_series and LEFT JOIN
        sql = text(f"""
            WITH grid AS (
                SELECT generate_series(
                    date_trunc('{interval}', CAST(:from_time AS timestamptz)),
                    date_trunc('{interval}', CAST(:to_time AS timestamptz)),
                    INTERVAL '{step_interval}'
                ) AS bucket_start
            ),
            data AS (
                SELECT
                    date_trunc('{interval}', valid_at) AS bucket_start,
                    {agg.upper()}({metric}) AS agg_val,
                    count({metric}) AS cnt
                FROM weather_records
                WHERE location_id = :location_id
                  AND record_kind = :kind
                  AND valid_at >= :from_time
                  AND valid_at <= :to_time
                GROUP BY 1
            )
            SELECT
                grid.bucket_start,
                data.agg_val,
                COALESCE(data.cnt, 0) AS sample_count
            FROM grid
            LEFT JOIN data ON grid.bucket_start = data.bucket_start
            ORDER BY grid.bucket_start ASC;
        """)
        rows = db.execute(
            sql,
            {
                "from_time": from_time,
                "to_time": to_time,
                "location_id": location.id,
                "kind": kind,
            },
        ).fetchall()
        for r in rows:
            buckets.append(
                TimeseriesBucket(
                    start=r.bucket_start,
                    value=_to_float(r.agg_val),
                    sample_count=r.sample_count,
                )
            )
    else:
        # Query without grid fill
        sql = text(f"""
            SELECT
                date_trunc('{interval}', valid_at) AS bucket_start,
                {agg.upper()}({metric}) AS agg_val,
                count({metric}) AS cnt
            FROM weather_records
            WHERE location_id = :location_id
              AND record_kind = :kind
              AND valid_at >= :from_time
              AND valid_at <= :to_time
            GROUP BY 1
            ORDER BY 1 ASC;
        """)
        rows = db.execute(
            sql,
            {
                "location_id": location.id,
                "kind": kind,
                "from_time": from_time,
                "to_time": to_time,
            },
        ).fetchall()
        for r in rows:
            buckets.append(
                TimeseriesBucket(
                    start=r.bucket_start,
                    value=_to_float(r.agg_val),
                    sample_count=r.cnt,
                )
            )

    # Distinct data sources contributing to this series
    sources_stmt = (
        select(DataSource)
        .join(WeatherRecord, WeatherRecord.source_id == DataSource.id)
        .where(
            WeatherRecord.location_id == location.id,
            WeatherRecord.record_kind == kind,
            WeatherRecord.valid_at >= from_time,
            WeatherRecord.valid_at <= to_time,
        )
        .distinct()
    )
    sources = db.scalars(sources_stmt).all()
    source_items = [
        TimeseriesSourceItem(
            name=s.name,
            display_name=s.display_name,
            trust_level=s.trust_level,
            attribution_text=s.attribution_text,
        )
        for s in sources
    ]

    # OLS Trend computation using PostgreSQL linear regression aggregates
    trend = None
    if include_trend:
        # regr_slope(Y, X), regr_r2(Y, X), regr_count(Y, X)
        # X is epoch day: EXTRACT(EPOCH FROM valid_at) / 86400.0
        trend_sql = text(f"""
            SELECT
                regr_slope({metric}, EXTRACT(EPOCH FROM valid_at) / 86400.0) AS slope,
                regr_r2({metric}, EXTRACT(EPOCH FROM valid_at) / 86400.0) AS r2,
                regr_count({metric}, EXTRACT(EPOCH FROM valid_at) / 86400.0) AS n
            FROM weather_records
            WHERE location_id = :location_id
              AND record_kind = :kind
              AND valid_at >= :from_time
              AND valid_at <= :to_time
              AND {metric} IS NOT NULL;
        """)
        t_row = db.execute(
            trend_sql,
            {
                "location_id": location.id,
                "kind": kind,
                "from_time": from_time,
                "to_time": to_time,
            },
        ).first()
        if t_row and t_row.n and t_row.n >= 2 and t_row.slope is not None and t_row.r2 is not None:
            trend = TimeseriesTrend(
                method="ols",
                slope_per_day=round(float(t_row.slope), 4),
                r_squared=round(float(t_row.r2), 4),
                n=t_row.n,
            )

    return TimeseriesResponse(
        metric=metric,
        unit=unit,
        location=TimeseriesLocation(
            id=location.id,
            slug=location.slug,
            name=location.name,
            region=location.region,
        ),
        kind=kind,
        interval=interval,
        agg=agg,
        buckets=buckets,
        sources=source_items,
        trend=trend,
    )


def query_analytics_locations(
    db: Session,
    from_time: datetime,
    to_time: datetime,
    sort: str = "name",
    is_staff: bool = False,
) -> LocationsAnalyticsResponse:
    # Expected hours in evaluation span
    span_hours = max(1, int((to_time - from_time).total_seconds() / 3600))

    # All active locations
    active_locations = db.query(Location).filter_by(is_active=True).all()

    # Weather metrics per location
    w_sql = text("""
        SELECT
            location_id,
            max(valid_at) AS latest_obs,
            min(temperature_c) AS min_t,
            avg(temperature_c) AS mean_t,
            max(temperature_c) AS max_t,
            sum(precipitation_mm) AS total_precip,
            avg(wind_speed_kmh) AS mean_wind,
            max(wind_gust_kmh) AS max_gust,
            count(*) AS rec_count,
            count(DISTINCT date_trunc('hour', valid_at)) AS distinct_hours
        FROM weather_records
        WHERE record_kind = 'observation'
          AND valid_at >= :from_time
          AND valid_at <= :to_time
        GROUP BY location_id;
    """)
    w_rows = {
        row.location_id: row
        for row in db.execute(w_sql, {"from_time": from_time, "to_time": to_time})
    }

    # Report metrics per location
    r_sql = text("""
        SELECT
            location_id,
            status,
            count(*) AS cnt
        FROM citizen_reports
        WHERE event_time >= :from_time
          AND event_time <= :to_time
          AND location_id IS NOT NULL
        GROUP BY location_id, status;
    """)
    r_data: dict[int, dict[str, int]] = {}
    for r in db.execute(r_sql, {"from_time": from_time, "to_time": to_time}):
        if r.location_id not in r_data:
            r_data[r.location_id] = {}
        r_data[r.location_id][r.status] = r.cnt

    items: list[LocationAnalyticsItem] = []
    for loc in active_locations:
        w = w_rows.get(loc.id)
        r_counts_raw = r_data.get(loc.id, {})

        if is_staff:
            r_counts = {
                "verified": r_counts_raw.get("verified", 0),
                "pending": r_counts_raw.get("pending", 0),
                "rejected": r_counts_raw.get("rejected", 0),
            }
        else:
            r_counts = {"verified": r_counts_raw.get("verified", 0)}

        if w:
            latest_obs = w.latest_obs
            temp_dict = {
                "min": _to_float(w.min_t),
                "mean": _to_float(w.mean_t),
                "max": _to_float(w.max_t),
            }
            total_precip = _to_float(w.total_precip)
            wind_dict = {
                "mean_speed_kmh": _to_float(w.mean_wind),
                "max_gust_kmh": _to_float(w.max_gust),
            }
            rec_count = w.rec_count
            distinct_h = w.distinct_hours
            coverage_pct = round(min(100.0, (distinct_h / span_hours) * 100.0), 2)
        else:
            latest_obs = None
            temp_dict = {"min": None, "mean": None, "max": None}
            total_precip = None
            wind_dict = {"mean_speed_kmh": None, "max_gust_kmh": None}
            rec_count = 0
            coverage_pct = 0.0

        items.append(
            LocationAnalyticsItem(
                location=TimeseriesLocation(
                    id=loc.id,
                    slug=loc.slug,
                    name=loc.name,
                    region=loc.region,
                ),
                latest_observation_at=latest_obs,
                temperature_c=temp_dict,
                total_precipitation_mm=total_precip,
                wind=wind_dict,
                record_count=rec_count,
                coverage_pct=coverage_pct,
                report_counts=r_counts,
            )
        )

    # Sorting
    reverse = sort.startswith("-")
    sort_key = sort.lstrip("-")
    if sort_key == "name":
        items.sort(key=lambda x: x.location.name.lower(), reverse=reverse)
    elif sort_key == "record_count":
        items.sort(key=lambda x: x.record_count, reverse=reverse)
    elif sort_key == "coverage_pct":
        items.sort(key=lambda x: x.coverage_pct, reverse=reverse)

    return LocationsAnalyticsResponse(items=items, total=len(items))


def query_analytics_events(
    db: Session,
    from_time: datetime,
    to_time: datetime,
    group_by: str,
    event_type: str | None = None,
    location_id: int | None = None,
    status_filter: str | None = None,
    is_staff: bool = False,
) -> EventAnalyticsResponse:
    # 1. Calculate totals
    totals_stmt = select(CitizenReport.status, func.count().label("cnt")).where(
        CitizenReport.event_time >= from_time, CitizenReport.event_time <= to_time
    )
    if event_type:
        totals_stmt = totals_stmt.where(CitizenReport.event_type == event_type)
    if location_id is not None:
        totals_stmt = totals_stmt.where(CitizenReport.location_id == location_id)
    totals_stmt = totals_stmt.group_by(CitizenReport.status)

    totals_dict = {row.status: row.cnt for row in db.execute(totals_stmt)}

    if is_staff:
        totals = EventAnalyticsTotals(
            verified=totals_dict.get("verified", 0),
            pending=totals_dict.get("pending", 0),
            rejected=totals_dict.get("rejected", 0),
        )
    else:
        totals = EventAnalyticsTotals(
            verified=totals_dict.get("verified", 0),
        )

    # 2. Main aggregation grouping
    if group_by == "event_type":
        group_expr = CitizenReport.event_type
    elif group_by == "location":
        group_expr = func.coalesce(CitizenReport.location_name, "Unknown")
    elif group_by == "status":
        group_expr = CitizenReport.status
    elif group_by == "day":
        group_expr = func.to_char(func.date_trunc("day", CitizenReport.event_time), "YYYY-MM-DD")
    else:
        group_expr = CitizenReport.event_type

    stmt = select(group_expr.label("grp_key"), func.count().label("cnt")).where(
        CitizenReport.event_time >= from_time, CitizenReport.event_time <= to_time
    )
    if event_type:
        stmt = stmt.where(CitizenReport.event_type == event_type)
    if location_id is not None:
        stmt = stmt.where(CitizenReport.location_id == location_id)

    # Status scoping
    if not is_staff:
        stmt = stmt.where(CitizenReport.status == "verified")
    elif status_filter:
        stmt = stmt.where(CitizenReport.status == status_filter)

    stmt = stmt.group_by(group_expr).order_by(desc("cnt"))

    items = [EventAnalyticsItem(key=str(row.grp_key), count=row.cnt) for row in db.execute(stmt)]

    return EventAnalyticsResponse(
        group_by=group_by,
        items=items,
        totals=totals,
    )
