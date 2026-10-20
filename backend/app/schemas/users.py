"""User response and credential schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr


class UserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    role: str
    model_config = ConfigDict(extra="forbid")
