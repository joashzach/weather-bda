"""Health check response models for Kubernetes, cloud, and local orchestrators."""

from pydantic import BaseModel, ConfigDict


class LivenessResponse(BaseModel):
    status: str = "ok"
    model_config = ConfigDict(extra="forbid")


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]
    model_config = ConfigDict(extra="forbid")
