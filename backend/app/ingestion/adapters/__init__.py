"""Ingestion adapters package."""

from app.ingestion.adapters.base import AdapterResult, BaseAdapter, TargetError
from app.ingestion.adapters.open_meteo import OpenMeteoAdapter

ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    OpenMeteoAdapter.key: OpenMeteoAdapter,
}

__all__ = [
    "ADAPTER_REGISTRY",
    "AdapterResult",
    "BaseAdapter",
    "OpenMeteoAdapter",
    "TargetError",
]
