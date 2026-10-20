"""Anomaly detection using modified z-score against a bounded baseline window per PRD Section 9."""

from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.queries import METRIC_UNITS
from app.db.models.locations import Location
from app.db.models.weather_records import WeatherRecord
from app.schemas.analytics import (
    AnomaliesResponse,
    AnomalyBaseline,
    AnomalyItem,
    TimeseriesLocation,
)

MINIMUM_BASELINE_HOURLY_SAMPLES = 168  # 7 days * 24 hours


def detect_anomalies(
    db: Session,
    location: Location,
    metric: str,
    from_time: datetime,
    to_time: datetime,
    baseline_days: int = 30,
    threshold: float = 3.5,
) -> AnomaliesResponse:
    col = getattr(WeatherRecord, metric)
    loc_schema = TimeseriesLocation(
        id=location.id,
        slug=location.slug,
        name=location.name,
        region=location.region,
    )
    unit = METRIC_UNITS.get(metric, "")

    # 1. Fetch baseline observations strictly before evaluation window [from_time - baseline_days, from_time)
    baseline_start = from_time - timedelta(days=baseline_days)
    base_stmt = (
        select(col)
        .where(
            WeatherRecord.location_id == location.id,
            WeatherRecord.record_kind == "observation",
            WeatherRecord.valid_at >= baseline_start,
            WeatherRecord.valid_at < from_time,
            col.is_not(None),
        )
        .order_by(WeatherRecord.valid_at.asc())
    )
    baseline_rows = db.scalars(base_stmt).all()
    baseline_vals = np.array([float(v) for v in baseline_rows], dtype=np.float64)

    # Require at least 168 baseline samples (PRD Section 9)
    if len(baseline_vals) < MINIMUM_BASELINE_HOURLY_SAMPLES:
        return AnomaliesResponse(
            location=loc_schema,
            metric=metric,
            items=[],
            status="insufficient_data",
            note=(
                f"Baseline sample count ({len(baseline_vals)}) is below the required "
                f"minimum of {MINIMUM_BASELINE_HOURLY_SAMPLES} hourly observations for a robust baseline."
            ),
        )

    median = float(np.median(baseline_vals))
    abs_deviations = np.abs(baseline_vals - median)
    mad = float(np.median(abs_deviations))

    baseline_info = AnomalyBaseline(
        median=round(median, 2),
        mad=round(mad, 4),
        n=len(baseline_vals),
        window_days=baseline_days,
    )

    # If MAD == 0, robust z-score cannot be computed, skip with note (PRD Section 9)
    if mad == 0.0:
        return AnomaliesResponse(
            location=loc_schema,
            metric=metric,
            baseline=baseline_info,
            items=[],
            status="zero_mad",
            note="Median Absolute Deviation (MAD) of the baseline is zero; modified z-scores cannot be calculated.",
        )

    # 2. Fetch target evaluation observations [from_time, to_time]
    target_stmt = (
        select(WeatherRecord.valid_at, col)
        .where(
            WeatherRecord.location_id == location.id,
            WeatherRecord.record_kind == "observation",
            WeatherRecord.valid_at >= from_time,
            WeatherRecord.valid_at <= to_time,
            col.is_not(None),
        )
        .order_by(WeatherRecord.valid_at.asc())
    )
    target_rows = db.execute(target_stmt).all()

    # 3. Compute modified z-scores: 0.6745 * (x - median) / MAD
    anomaly_items: list[AnomalyItem] = []
    for valid_at, raw_val in target_rows:
        val = float(raw_val)
        score = 0.6745 * (val - median) / mad
        abs_score = abs(score)

        if abs_score >= threshold:
            direction = "high" if val > median else "low"
            rel_word = "above" if score > 0 else "below"
            unit_str = f" {unit}" if unit else ""
            explanation = (
                f"Value {val:.1f}{unit_str} is {abs_score:.1f} robust deviations {rel_word} "
                f"the {baseline_days}-day median of {median:.1f}{unit_str} (n={len(baseline_vals)})"
            )

            anomaly_items.append(
                AnomalyItem(
                    valid_at=valid_at,
                    metric=metric,
                    value=round(val, 2),
                    baseline=baseline_info,
                    score=round(float(score), 2),
                    direction=direction,
                    method="modified_z_score",
                    threshold=float(threshold),
                    explanation=explanation,
                    # PRD Rule: Mandatory safety assertions; never labeled as warning or alert
                    is_official_warning=False,
                    verification="unverified",
                    disclaimer="Statistical flag only. Not an official warning.",
                )
            )

    return AnomaliesResponse(
        location=loc_schema,
        metric=metric,
        baseline=baseline_info,
        items=anomaly_items,
        status="ok",
    )
