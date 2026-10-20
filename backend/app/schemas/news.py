"""Pydantic v2 schemas for news and advisory items conforming to PRD Section 4.7 and Section 7.2."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NewsSourceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    display_name: str
    trust_level: str


class NewsItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    source: NewsSourceSummary
    title: str = Field(..., max_length=500)
    summary: str | None = Field(default=None, max_length=2000)
    url: str = Field(..., max_length=2048)
    published_at: datetime | None = None
    fetched_at: datetime
    category: str
    is_official: bool = Field(
        ...,
        description="True if the originating source trust_level is 'official'; otherwise False.",
    )
