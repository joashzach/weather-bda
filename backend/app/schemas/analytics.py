"""Analytics response and query schemas conforming to PRD Section 9."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PeriodSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    from_time: datetime = Field(..., alias="from")
    to_time: datetime = Field(..., alias="to")


# --- Summary Schemas ---


class TemperatureSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float | None = None
    mean_of_location_means: float | None = None
    max: float | None = None


class WindSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mean_speed_kmh: float | None = None
    max_gust_kmh: float | None = None


class WeatherRecordCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: int = 0
    forecast: int = 0


class WeatherSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_counts: WeatherRecordCounts
    records_by_kind: WeatherRecordCounts | None = None
    locations_with_data: int
    temperature_c: TemperatureSummary
    wind: WindSummary


class ReportsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    by_status: dict[str, int]


class SourceSummaryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str
    source_type: str
    trust_level: str
    freshness: str
    last_success_at: datetime | None = None


class IngestionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs_by_status: dict[str, int]
    success_rate: float
    last_failure_at: datetime | None = None


class AnalyticsSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: PeriodSchema
    weather: WeatherSummary
    reports: ReportsSummary
    sources: list[SourceSummaryItem]
    ingestion: IngestionSummary | None = None


# --- Timeseries Schemas ---


class TimeseriesLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    slug: str
    name: str
    region: str | None = None


class TimeseriesBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: datetime
    value: float | None = None
    sample_count: int


class TimeseriesTrend(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = "ols"
    slope_per_day: float
    r_squared: float
    n: int


class TimeseriesSourceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str
    trust_level: str
    attribution_text: str


class TimeseriesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    unit: str
    location: TimeseriesLocation
    kind: str
    interval: str
    agg: str
    buckets: list[TimeseriesBucket]
    sources: list[TimeseriesSourceItem]
    trend: TimeseriesTrend | None = None


# --- Locations Analytics Schemas ---


class LocationAnalyticsItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: TimeseriesLocation
    latest_observation_at: datetime | None = None
    temperature_c: dict[str, float | None]
    total_precipitation_mm: float | None = None
    wind: dict[str, float | None]
    record_count: int
    coverage_pct: float
    report_counts: dict[str, int]


class LocationsAnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LocationAnalyticsItem]
    total: int


# --- Events Analytics Schemas ---


class EventAnalyticsItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    count: int


class EventAnalyticsTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verified: int
    pending: int | None = None
    rejected: int | None = None


class EventAnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_by: str
    items: list[EventAnalyticsItem]
    totals: EventAnalyticsTotals


# --- Anomalies Schemas ---


class AnomalyBaseline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    median: float
    mad: float
    n: int
    window_days: int


class AnomalyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid_at: datetime
    metric: str
    value: float
    baseline: AnomalyBaseline
    score: float
    direction: str  # "high" | "low"
    method: str = "modified_z_score"
    threshold: float
    explanation: str
    is_official_warning: bool = False
    verification: str = "unverified"
    disclaimer: str = "Statistical flag only. Not an official warning."


class AnomaliesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: TimeseriesLocation
    metric: str
    baseline: AnomalyBaseline | None = None
    items: list[AnomalyItem]
    status: str = "ok"
    note: str | None = None
