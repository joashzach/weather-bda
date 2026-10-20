"""Ingestion adapters package."""

from app.ingestion.adapters.base import AdapterResult, BaseAdapter, TargetError
from app.ingestion.adapters.data_gov_in import DataGovInAdapter
from app.ingestion.adapters.open_meteo import OpenMeteoAdapter
from app.ingestion.adapters.rss_atom import RssAtomAdapter

ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    OpenMeteoAdapter.key: OpenMeteoAdapter,
    RssAtomAdapter.key: RssAtomAdapter,
    DataGovInAdapter.key: DataGovInAdapter,
}

__all__ = [
    "ADAPTER_REGISTRY",
    "AdapterResult",
    "BaseAdapter",
    "DataGovInAdapter",
    "OpenMeteoAdapter",
    "RssAtomAdapter",
    "TargetError",
]
