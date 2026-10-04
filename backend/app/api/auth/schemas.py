"""Request and response models for the auth routes."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Sign-in credentials."""

    model_config = ConfigDict(extra="forbid")

    # Mirrors chk_users_email_shape (one @, no whitespace) and also refuses control characters.
    email: str = Field(
        min_length=3, max_length=254, pattern=r"^[^@\s\x00-\x1f\x7f]+@[^@\s\x00-\x1f\x7f]+$"
    )
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
