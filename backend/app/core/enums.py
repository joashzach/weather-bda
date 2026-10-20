"""Domain enums and string constants for database CHECK constraints and Pydantic validation."""

from enum import StrEnum


class EnvironmentType(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class UserRole(StrEnum):
    ADMIN = "admin"
    REVIEWER = "reviewer"


class TrustLevel(StrEnum):
    OFFICIAL = "official"
    PROVIDER_MODEL = "provider_model"
    NEWS = "news"
    CITIZEN = "citizen"


class SourceType(StrEnum):
    WEATHER_API = "weather_api"
    RSS = "rss"
    OPEN_DATASET = "open_dataset"
    CITIZEN = "citizen"


class RecordKind(StrEnum):
    OBSERVATION = "observation"
    FORECAST = "forecast"


class MeasurementBasis(StrEnum):
    STATION = "station"
    MODEL_ANALYSIS = "model_analysis"
    MODEL_FORECAST = "model_forecast"
    UNKNOWN = "unknown"


class ReportEventType(StrEnum):
    HEAVY_RAIN = "heavy_rain"
    FLOOD = "flood"
    HEATWAVE = "heatwave"
    COLD_WAVE = "cold_wave"
    STORM = "storm"
    CYCLONE = "cyclone"
    DROUGHT = "drought"
    LANDSLIDE = "landslide"
    LIGHTNING = "lightning"
    HAIL = "hail"
    FOG = "fog"
    OTHER = "other"


class ReportSeverity(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


class ReportStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class EvidenceType(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
    LINK = "link"
    OTHER = "other"


class NewsCategory(StrEnum):
    NEWS = "news"
    ADVISORY_FEED = "advisory_feed"


class IngestionTrigger(StrEnum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class IngestionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    ABANDONED = "abandoned"
