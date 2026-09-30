"""Request, response and recording types for the gateway.

`GatewayRequest` validates its own values (a `Literal` is not enforced at
runtime). Whether `system` and `input` are the right text classes is checked in
`Gateway.complete`, before anything else, so a raw string never reaches a key,
the database or the network.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.budget.policy import MAX_TOKENS_CAP
from app.gateway.errors import InvalidRequestError
from app.gateway.text import AnonymizedText, JobDescriptionText, PromptText

Purpose = Literal["criteria", "scoring", "kit", "eval"]

__all__ = [
    "MAX_TOKENS_CAP",
    "PURPOSE_INPUT",
    "GatewayRequest",
    "GatewayResponse",
    "Purpose",
    "RecordedResponse",
    "Recording",
]

# Which text class each purpose accepts, so a raw resume wrapped in the wrong
# class is refused too (AC-US-00-005-4).
PURPOSE_INPUT: Final[dict[str, type[AnonymizedText] | type[JobDescriptionText]]] = {
    "scoring": AnonymizedText,
    "eval": AnonymizedText,
    "criteria": JobDescriptionText,
    "kit": JobDescriptionText,
}


@dataclass(frozen=True)
class GatewayRequest:
    """One model call. `role_id` is logged but never part of the replay key."""

    purpose: Purpose
    role_id: UUID | None
    prompt_version: str
    system: PromptText
    input: AnonymizedText | JobDescriptionText
    max_tokens: int
    schema_retry: int

    def __post_init__(self) -> None:
        if self.purpose not in get_args(Purpose):
            msg = f"purpose must be one of {get_args(Purpose)}, got {self.purpose!r}"
            raise InvalidRequestError(msg)
        if not self.prompt_version.strip():
            msg = "prompt_version must not be empty"
            raise InvalidRequestError(msg)
        if isinstance(self.max_tokens, bool) or self.max_tokens < 1:
            msg = f"max_tokens must be at least 1, got {self.max_tokens!r}"
            raise InvalidRequestError(msg)
        if isinstance(self.schema_retry, bool) or self.schema_retry not in (0, 1):
            msg = f"schema_retry must be 0 or 1, got {self.schema_retry!r}"
            raise InvalidRequestError(msg)

    @property
    def clamped_max_tokens(self) -> int:
        """The value that is hashed and sent: never above the cap (REQ-041)."""
        return min(self.max_tokens, MAX_TOKENS_CAP)


@dataclass(frozen=True)
class GatewayResponse:
    """What the caller gets back. `finish_reason == "length"` means truncated output."""

    text: str
    input_tokens: int
    output_tokens: int
    finish_reason: str
    request_key: str
    replayed: bool
    cost_usd: Decimal


class RecordedResponse(BaseModel):
    """The provider reply as recorded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    input_tokens: int
    output_tokens: int
    finish_reason: str


class Recording(BaseModel):
    """One file in `RECORDINGS_DIR`: the reply plus what is needed to find and explain it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key_version: int
    request_key: str
    input_sha256: str
    model: str
    prompt_version: str
    schema_retry: Literal[0, 1]
    purpose: Purpose
    response: RecordedResponse
