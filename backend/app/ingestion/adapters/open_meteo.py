"""Open-Meteo ingestion adapter implementing failure isolation and retry policies per PRD Section 8.2."""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.core.config import Settings
from app.core.http_client import SafeHttpClient
from app.core.logging import get_logger
from app.db.models.data_sources import DataSource
from app.db.models.locations import Location
from app.ingestion.adapters.base import AdapterResult, BaseAdapter, TargetError
from app.ingestion.normalizers import (
    ValidationErrorItem,
    normalize_open_meteo_record,
)

logger = get_logger("app.ingestion.open_meteo")

HOURLY_VARIABLES = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation",
    "rain",
    "precipitation_probability",
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
]


class RetryableHTTPStatusError(Exception):
    pass


def sanitize_error_message(msg: str) -> str:
    """Sanitize error messages: strip query strings, credentials, and truncate to 1000 characters."""
    clean = msg
    try:
        if "?" in clean:
            clean = clean.split("?")[0] + " [QUERY STRIPPED]"
    except Exception:
        pass
    return clean[:1000]


class OpenMeteoAdapter(BaseAdapter):
    key = "open_meteo"

    def is_configured(self, source: DataSource, settings: Settings) -> bool:
        """Open-Meteo free tier requires a valid base URL and allowed source host."""
        base_url = settings.OPEN_METEO_BASE_URL
        if not base_url:
            return False
        parsed = urlparse(base_url)
        return bool(parsed.hostname and parsed.hostname in settings.allowed_source_host_list)

    def _fetch_location_data(
        self,
        location: Location,
        http_client: SafeHttpClient,
        settings: Settings,
        past_days: int,
        forecast_days: int,
    ) -> dict[str, Any]:
        """Fetch weather data for a single location with bounded tenacity retries and jitter."""

        @retry(
            retry=retry_if_exception_type(
                (httpx.TimeoutException, httpx.NetworkError, RetryableHTTPStatusError)
            ),
            stop=stop_after_attempt(settings.HTTP_MAX_RETRIES),
            wait=wait_exponential_jitter(initial=1.0, max=10.0),
            reraise=True,
        )
        def _do_get() -> dict[str, Any]:
            params: dict[str, Any] = {
                "latitude": float(location.latitude),
                "longitude": float(location.longitude),
                "hourly": ",".join(HOURLY_VARIABLES),
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
                "timezone": "UTC",
                "past_days": past_days,
                "forecast_days": forecast_days,
            }

            resp = http_client.get(settings.OPEN_METEO_BASE_URL, params=params)

            # Check status codes
            if resp.status_code == 429 or resp.status_code >= 500:
                raise RetryableHTTPStatusError(
                    f"HTTP {resp.status_code} from Open-Meteo: {resp.text}"
                )

            resp.raise_for_status()
            return resp.json()

        return _do_get()

    def run(
        self,
        source: DataSource,
        targets: list[Any],
        http_client: SafeHttpClient,
        settings: Settings,
    ) -> AdapterResult:
        """Fetch each target location in isolation, validate records, and assemble results."""
        result = AdapterResult()
        fetched_at = datetime.now(UTC)

        # Config overrides or settings defaults
        source_cfg = source.config or {}
        past_days = source_cfg.get("past_days", settings.OPEN_METEO_PAST_DAYS)
        forecast_days = source_cfg.get("forecast_days", settings.OPEN_METEO_FORECAST_DAYS)

        for target in targets:
            if not isinstance(target, Location):
                continue

            try:
                data = self._fetch_location_data(
                    location=target,
                    http_client=http_client,
                    settings=settings,
                    past_days=past_days,
                    forecast_days=forecast_days,
                )
            except Exception as e:
                sanitized = sanitize_error_message(f"Failed to fetch {target.slug}: {e}")
                logger.warning(
                    "open_meteo_location_fetch_failed",
                    location=target.slug,
                    error=sanitized,
                )
                result.errors.append(
                    TargetError(
                        target_key=target.slug,
                        error_code="fetch_error",
                        message=sanitized,
                    )
                )
                result.failed_count += 1
                continue

            hourly = data.get("hourly", {})
            times = hourly.get("time", [])

            if not times:
                result.errors.append(
                    TargetError(
                        target_key=target.slug,
                        error_code="empty_data",
                        message=f"No hourly timestamps returned for location '{target.slug}'",
                    )
                )
                result.failed_count += 1
                continue

            # Verify parallel array lengths
            length_mismatch = False
            for var in HOURLY_VARIABLES:
                arr = hourly.get(var)
                if arr is None or len(arr) != len(times):
                    length_mismatch = True
                    sanitized = f"Array length mismatch for '{var}': expected {len(times)}, got {len(arr) if arr is not None else 'None'}"
                    result.errors.append(
                        TargetError(
                            target_key=target.slug,
                            error_code="length_mismatch",
                            message=sanitized,
                        )
                    )
                    result.failed_count += len(times)
                    break

            if length_mismatch:
                continue

            result.fetched_count += len(times)

            # Zip and normalize hourly records
            for i, raw_time in enumerate(times):
                raw_measurements = {var: hourly[var][i] for var in HOURLY_VARIABLES}
                try:
                    record = normalize_open_meteo_record(
                        location_id=target.id,
                        source_id=source.id,
                        raw_time=raw_time,
                        raw_measurements=raw_measurements,
                        fetched_at=fetched_at,
                    )
                    result.records.append(record)
                except (ValidationErrorItem, Exception) as e:
                    result.failed_count += 1
                    logger.debug(
                        "open_meteo_record_validation_failed",
                        location=target.slug,
                        time=raw_time,
                        error=str(e),
                    )

        return result
