"""Weather record response and filter schemas conforming to PRD Section 7.3."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginatedResponse


class WeatherMeasurements(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    temperature_c: float | None = None
    apparent_temperature_c: float | None = None
    relative_humidity_pct: float | None = None
    precipitation_mm: float | None = None
    rain_mm: float | None = None
    precipitation_probability_pct: int | None = None
    wind_speed_kmh: float | None = None
    wind_gust_kmh: float | None = None
    wind_direction_deg: float | None = None


class WeatherRecordLocation(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    slug: str
    name: str


class WeatherRecordSource(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    name: str
    display_name: str
    trust_level: str
    attribution_text: str | None = None


class WeatherRecordPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    kind: str
    valid_at: datetime
    issued_at: datetime | None = None
    fetched_at: datetime
    measurement_basis: str
    resolution_seconds: int
    location: WeatherRecordLocation
    source: WeatherRecordSource
    measurements: WeatherMeasurements


class WeatherRecordListResponse(PaginatedResponse[WeatherRecordPublic]):
    pass


class WeatherLatestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: datetime
    items: list[WeatherRecordPublic] = Field(default_factory=list)
    missing_location_ids: list[int] = Field(default_factory=list)
