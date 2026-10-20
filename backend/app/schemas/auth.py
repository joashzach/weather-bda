"""Authentication and credential schemas conforming to PRD Section 6.1 and 7.5."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.users import UserPublic


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User account email address")
    password: str = Field(..., min_length=1, description="Account password")
    model_config = ConfigDict(extra="forbid")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="HS256 signed JWT access token")
    token_type: Literal["bearer"] = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Access token time-to-live in seconds")
    user: UserPublic = Field(..., description="Authenticated user summary")
    model_config = ConfigDict(extra="forbid")


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="Current account password")
    new_password: str = Field(
        ...,
        min_length=12,
        description="New password meeting minimum 12-character security threshold",
    )
    model_config = ConfigDict(extra="forbid")


class MessageResponse(BaseModel):
    message: str = Field(..., description="Status or result message")
    model_config = ConfigDict(extra="forbid")
