"""Pure normalization and validation functions for weather ingestion conforming to PRD Section 4.4 and 8.1."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NormalizedWeatherRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: int
    source_id: int
    record_kind: str
    measurement_basis: str
    valid_at: datetime
    issued_at: datetime | None = None
    resolution_seconds: int = 3600
    temperature_c: float | None = None
    apparent_temperature_c: float | None = None
    relative_humidity_pct: float | None = None
    precipitation_mm: float | None = None
    rain_mm: float | None = None
    precipitation_probability_pct: int | None = None
    wind_speed_kmh: float | None = None
    wind_gust_kmh: float | None = None
    wind_direction_deg: float | None = None
    content_hash: str = Field(min_length=64, max_length=64)
    fetched_at: datetime


class ValidationErrorItem(Exception):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


def parse_utc_timestamp(val: str | datetime) -> datetime:
    """Parse timestamp ensuring it is timezone-aware and converted to UTC. Reject naive strings."""
    if isinstance(val, datetime):
        if val.tzinfo is None:
            raise ValidationErrorItem(
                "Naive datetime object is strictly rejected; must have timezone info."
            )
        return val.astimezone(UTC)

    if not isinstance(val, str) or not val.strip():
        raise ValidationErrorItem("Timestamp string must be non-empty.")

    raw = val.strip()
    try:
        # If open-meteo returns 'YYYY-MM-DDTHH:MM' without timezone, handle when caller requested UTC
        if "Z" in raw or "+" in raw or "-" in raw[10:]:
            dt = datetime.fromisoformat(raw)
        else:
            # Assume UTC when iso format has no offset (since API requested with timezone=UTC)
            dt = datetime.fromisoformat(raw).replace(tzinfo=UTC)

        if dt.tzinfo is None:
            raise ValidationErrorItem(f"Timestamp '{val}' is naive; UTC timezone required.")
        return dt.astimezone(UTC)
    except Exception as e:
        raise ValidationErrorItem(f"Failed to parse UTC timestamp '{val}': {e}") from e


def validate_range(
    val: Any,
    min_val: float,
    max_val: float,
    field_name: str,
    as_int: bool = False,
) -> float | int | None:
    """Validate numeric ranges. Return None for nulls, reject out-of-range values (never clamp)."""
    if val is None:
        return None

    try:
        num = float(val)
    except (ValueError, TypeError) as e:
        raise ValidationErrorItem(
            f"Non-numeric value '{val}' for field '{field_name}'", field=field_name
        ) from e

    if num < min_val or num > max_val:
        raise ValidationErrorItem(
            f"Value {num} for '{field_name}' is out of bounds [{min_val}, {max_val}]",
            field=field_name,
        )

    if as_int:
        return int(round(num))
    return round(num, 2)


def compute_content_hash(measurements: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 content hash of normalized measurement fields (PRD line 152)."""
    canonical_keys = [
        "temperature_c",
        "apparent_temperature_c",
        "relative_humidity_pct",
        "precipitation_mm",
        "rain_mm",
        "precipitation_probability_pct",
        "wind_speed_kmh",
        "wind_gust_kmh",
        "wind_direction_deg",
    ]
    canonical_dict = {k: measurements.get(k) for k in canonical_keys}
    payload_str = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


def normalize_open_meteo_record(
    location_id: int,
    source_id: int,
    raw_time: str | datetime,
    raw_measurements: dict[str, Any],
    fetched_at: datetime,
) -> NormalizedWeatherRecord:
    """Validate, normalize, classify observation vs forecast, and hash a single hourly record."""
    valid_at = parse_utc_timestamp(raw_time)

    # Observation vs forecast split (PRD Section 8.2)
    # Floor fetched_at to the top of the hour
    hour_floor = fetched_at.replace(minute=0, second=0, microsecond=0)

    if valid_at <= hour_floor:
        record_kind = "observation"
        measurement_basis = "model_analysis"
        issued_at = None
    else:
        record_kind = "forecast"
        measurement_basis = "model_forecast"
        issued_at = fetched_at

    # Range validations conforming to PRD Section 4.4
    temp_c = validate_range(raw_measurements.get("temperature_2m"), -90.0, 60.0, "temperature_c")
    apparent_temp_c = validate_range(
        raw_measurements.get("apparent_temperature"), -90.0, 60.0, "apparent_temperature_c"
    )
    humidity = validate_range(
        raw_measurements.get("relative_humidity_2m"), 0.0, 100.0, "relative_humidity_pct"
    )
    precipitation = validate_range(
        raw_measurements.get("precipitation"), 0.0, 1000.0, "precipitation_mm"
    )
    rain = validate_range(raw_measurements.get("rain"), 0.0, 1000.0, "rain_mm")
    precip_prob = validate_range(
        raw_measurements.get("precipitation_probability"),
        0.0,
        100.0,
        "precipitation_probability_pct",
        as_int=True,
    )
    wind_speed = validate_range(
        raw_measurements.get("wind_speed_10m"), 0.0, 500.0, "wind_speed_kmh"
    )
    wind_gust = validate_range(raw_measurements.get("wind_gusts_10m"), 0.0, 500.0, "wind_gust_kmh")
    wind_dir = validate_range(
        raw_measurements.get("wind_direction_10m"), 0.0, 360.0, "wind_direction_deg"
    )

    measurements_dict = {
        "temperature_c": temp_c,
        "apparent_temperature_c": apparent_temp_c,
        "relative_humidity_pct": humidity,
        "precipitation_mm": precipitation,
        "rain_mm": rain,
        "precipitation_probability_pct": precip_prob,
        "wind_speed_kmh": wind_speed,
        "wind_gust_kmh": wind_gust,
        "wind_direction_deg": wind_dir,
    }
    content_hash = compute_content_hash(measurements_dict)

    return NormalizedWeatherRecord(
        location_id=location_id,
        source_id=source_id,
        record_kind=record_kind,
        measurement_basis=measurement_basis,
        valid_at=valid_at,
        issued_at=issued_at,
        resolution_seconds=3600,
        content_hash=content_hash,
        fetched_at=fetched_at,
        **measurements_dict,
    )
