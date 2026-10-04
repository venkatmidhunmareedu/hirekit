"""Request and response models for the auth routes."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Sign-in credentials."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class UserOut(BaseModel):
    """The signed-in user; never the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: Literal["recruiter", "interviewer"]


class SessionOut(BaseModel):
    """The user and the token the client echoes in X-CSRF-Token on state-changing requests."""

    user: UserOut
    csrf_token: str
