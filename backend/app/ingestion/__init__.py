"""Ingestion package export."""

from app.ingestion.adapters import ADAPTER_REGISTRY, BaseAdapter, OpenMeteoAdapter
from app.ingestion.normalizers import (
    NormalizedWeatherRecord,
    compute_content_hash,
    normalize_open_meteo_record,
    parse_utc_timestamp,
    validate_range,
)
from app.ingestion.pipeline import IngestionPipeline

__all__ = [
    "ADAPTER_REGISTRY",
    "BaseAdapter",
    "IngestionPipeline",
    "NormalizedWeatherRecord",
    "OpenMeteoAdapter",
    "compute_content_hash",
    "normalize_open_meteo_record",
    "parse_utc_timestamp",
    "validate_range",
]
