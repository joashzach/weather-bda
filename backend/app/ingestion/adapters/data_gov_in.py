"""data.gov.in Open Data portal adapter conforming to PRD Section 8.4."""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from app.core.config import Settings
from app.core.enums import MeasurementBasis, RecordKind
from app.core.http_client import SafeHttpClient
from app.core.logging import get_logger
from app.db.models.data_sources import DataSource
from app.ingestion.adapters.base import (
    AdapterResult,
    BaseAdapter,
    TargetError,
    sanitize_error_text,
)
from app.ingestion.normalizers import (
    NormalizedWeatherRecord,
    compute_content_hash,
    parse_utc_timestamp,
)

logger = get_logger("app.ingestion.adapters.data_gov_in")

DATA_GOV_IN_BASE_URL = "https://api.data.gov.in/resource"


class DataGovInAdapter(BaseAdapter):
    key = "data_gov_in"

    def is_configured(self, source: DataSource, settings: Settings) -> bool:
        """data.gov.in requires a valid API key and a configured resource_id."""
        api_key = (settings.DATA_GOV_IN_API_KEY or "").strip()
        if not api_key:
            return False

        cfg = source.config or {}
        resource_id = cfg.get("resource_id")
        return bool(resource_id and isinstance(resource_id, str) and resource_id.strip())

    def run(
        self,
        source: DataSource,
        targets: list[Any],
        http_client: SafeHttpClient,
        settings: Settings,
    ) -> AdapterResult:
        """Ingest meteorological datasets from data.gov.in API with strict schema mapping and station matching."""
        if not self.is_configured(source, settings):
            return AdapterResult(
                errors=[
                    TargetError(
                        target_key=source.name,
                        error_code="source_not_configured",
                        message="data.gov.in adapter requires DATA_GOV_IN_API_KEY and resource_id in config",
                    )
                ],
                failed_count=1,
            )

        cfg = source.config or {}
        resource_id = cfg["resource_id"].strip()
        field_map = cfg.get("field_map", {})
        unit_conversions = cfg.get("unit_conversions", {})
        location_match = cfg.get("location_match", {})
        limit = min(int(cfg.get("limit", 100)), 500)
        measurement_basis = cfg.get("measurement_basis", MeasurementBasis.UNKNOWN)

        # Build target lookup dictionary
        target_map = {getattr(t, "slug", str(t)): getattr(t, "id", None) for t in targets}

        params = {
            "api-key": settings.DATA_GOV_IN_API_KEY,
            "format": "json",
            "limit": limit,
            "offset": 0,
        }
        url = f"{DATA_GOV_IN_BASE_URL}/{resource_id}?{urlencode(params)}"

        try:
            response = http_client.get(url)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.error("data_gov_in_fetch_failed", resource_id=resource_id, error=str(exc))
            return AdapterResult(
                errors=[
                    TargetError(
                        target_key=resource_id,
                        error_code="http_fetch_error",
                        message=sanitize_error_text(f"Failed to fetch data.gov.in resource: {exc}"),
                    )
                ],
                failed_count=1,
            )

        if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
            return AdapterResult(
                errors=[
                    TargetError(
                        target_key=resource_id,
                        error_code="response_malformed",
                        message="Response JSON is missing expected 'records' array",
                    )
                ],
                failed_count=1,
            )

        raw_records = payload.get("records", [])
        now = datetime.now(UTC)
        weather_records: list[NormalizedWeatherRecord] = []
        errors: list[TargetError] = []
        skipped_unmatched = 0

        station_field = field_map.get("station_name", "station")
        timestamp_field = field_map.get("valid_at", "timestamp")

        def _extract_metric(row_data: dict[str, Any], field_key: str) -> float | None:
            provider_key = field_map.get(field_key)
            if not provider_key or provider_key not in row_data:
                return None
            val_raw = row_data[provider_key]
            if val_raw is None or str(val_raw).strip() in ("", "NA", "null", "None"):
                return None
            try:
                val = float(val_raw)
            except (ValueError, TypeError):
                return None

            conv = unit_conversions.get(field_key)
            if conv == "kelvin_to_celsius":
                val = val - 273.15
            elif conv == "fahrenheit_to_celsius":
                val = (val - 32.0) * 5.0 / 9.0
            return round(val, 2)

        for row in raw_records:
            # 1. Location matching
            raw_station = str(row.get(station_field, "")).strip().lower()
            loc_slug = location_match.get(raw_station) or location_match.get(raw_station.upper())
            if not loc_slug or loc_slug not in target_map:
                skipped_unmatched += 1
                continue

            location_id = target_map[loc_slug]
            if location_id is None:
                skipped_unmatched += 1
                continue

            # 2. Timestamp parsing
            raw_time = row.get(timestamp_field)
            if not raw_time:
                continue

            try:
                valid_at = parse_utc_timestamp(str(raw_time))
            except Exception:
                continue

            # 3. Numeric metric extraction and unit conversion
            temp_c = _extract_metric(row, "temperature_c")
            humidity = _extract_metric(row, "relative_humidity_pct")
            precip_mm = _extract_metric(row, "precipitation_mm")
            wind_speed = _extract_metric(row, "wind_speed_kmh")
            wind_gust = _extract_metric(row, "wind_gust_kmh")
            wind_dir = _extract_metric(row, "wind_direction_deg")

            measurements = {
                "temperature_c": temp_c,
                "apparent_temperature_c": None,
                "relative_humidity_pct": humidity,
                "precipitation_mm": precip_mm,
                "rain_mm": precip_mm,
                "precipitation_probability_pct": None,
                "wind_speed_kmh": wind_speed,
                "wind_gust_kmh": wind_gust,
                "wind_direction_deg": wind_dir,
            }
            content_hash = compute_content_hash(measurements)

            weather_records.append(
                NormalizedWeatherRecord(
                    location_id=location_id,
                    source_id=source.id,
                    record_kind=RecordKind.OBSERVATION,
                    measurement_basis=str(measurement_basis),
                    valid_at=valid_at,
                    issued_at=None,
                    resolution_seconds=3600,
                    temperature_c=temp_c,
                    apparent_temperature_c=None,
                    relative_humidity_pct=humidity,
                    precipitation_mm=precip_mm,
                    rain_mm=precip_mm,
                    precipitation_probability_pct=None,
                    wind_speed_kmh=wind_speed,
                    wind_gust_kmh=wind_gust,
                    wind_direction_deg=wind_dir,
                    content_hash=content_hash,
                    fetched_at=now,
                )
            )

        if skipped_unmatched > 0:
            logger.info(
                "data_gov_in_unmatched_rows", skipped=skipped_unmatched, resource_id=resource_id
            )

        return AdapterResult(
            records=weather_records,
            news_records=[],
            errors=errors,
            fetched_count=len(raw_records),
            failed_count=0,
        )
