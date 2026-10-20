"""Base adapter interface and result structures for ingestion adapters conforming to PRD Section 8.1."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.core.http_client import SafeHttpClient
from app.db.models.data_sources import DataSource
from app.ingestion.normalizers import NormalizedWeatherRecord


class TargetError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_key: str
    error_code: str
    message: str = Field(max_length=1000)


class AdapterResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[NormalizedWeatherRecord] = Field(default_factory=list)
    errors: list[TargetError] = Field(default_factory=list)
    fetched_count: int = 0
    failed_count: int = 0


class BaseAdapter(ABC):
    key: str

    @abstractmethod
    def is_configured(self, source: DataSource, settings: Settings) -> bool:
        """Check whether the adapter has the necessary configuration / credentials to execute."""
        raise NotImplementedError

    @abstractmethod
    def run(
        self,
        source: DataSource,
        targets: list[Any],
        http_client: SafeHttpClient,
        settings: Settings,
    ) -> AdapterResult:
        """Execute ingestion against targets, return normalized records and sanitized errors."""
        raise NotImplementedError
