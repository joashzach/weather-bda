"""Location response schemas for public API consumption."""

from pydantic import BaseModel, ConfigDict, Field


class LocationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    slug: str
    name: str
    region: str | None = None
    country_code: str
    latitude: float
    longitude: float


class LocationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LocationPublic] = Field(default_factory=list)
