"""The only module that imports httpx or names the provider URL (AC-US-02-001-1).

`OpenRouterTransport.post` makes one chat-completion call and turns every outcome into a
typed reply or a typed error. On an error, `error.billed` says whether the reservation stays
(the call may have been billed) or is released (the provider reported no usage); the table is in
docs/design/gateway-lld.md section 6. Nothing here logs, and no error message carries a response
body, a prompt or the key (tenet 7).
"""

import asyncio
from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import BaseModel, Field, SecretStr, ValidationError

from app.budget.policy import MAX_TOKENS_CAP
from app.core.config import Settings
from app.gateway.errors import (
    GatewayError,
    InvalidRequestError,
    LiveCallForbiddenError,
    ProviderCreditExhaustedError,
    ProviderProtocolError,
    ProviderRejectedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)

BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class TransportRequest:
    """What goes on the wire: already clamped, hashed and checked by `Gateway.complete`."""

    model: str
    system: str
    user: str
    max_tokens: int
    temperature: int = 0


@dataclass(frozen=True)
class TransportReply:
    """A parsed 2xx reply with the token counts the provider reported."""

    text: str
    input_tokens: int
    output_tokens: int
    finish_reason: str


class Transport(Protocol):
    """What `Gateway` needs from a transport; tests inject a fake."""

    async def post(self, request: TransportRequest) -> TransportReply:
        """Make one call or raise a `GatewayError` whose `billed` says what to do."""
        ...

    async def aclose(self) -> None:
        """Release the connection pool."""
        ...


class _Message(BaseModel):
    content: str


class _Choice(BaseModel):
    message: _Message
    finish_reason: str | None = None


class _Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int


class _Completion(BaseModel):
    choices: list[_Choice] = Field(min_length=1)
    usage: _Usage


def _error(cls: type[GatewayError], message: str, *, billed: bool) -> GatewayError:
    err = cls(message)
    err.billed = billed
    return err


def _reports_usage(response: httpx.Response) -> bool:
    """True when an error reply still reports token usage, so the call was billed."""
    try:
        return _Usage.model_validate(response.json().get("usage")) is not None
    except ValueError, ValidationError, AttributeError:
        return False


class OpenRouterTransport:
    """Calls OpenRouter's chat-completions endpoint with one whole-call timeout."""

    def __init__(
        self,
        *,
        api_key: SecretStr | None,
        timeout_seconds: float,
        ci: bool,
        base_url: str = BASE_URL,
        http_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if ci:
            msg = "a live model call is not allowed when CI is set"
            raise LiveCallForbiddenError(msg)
        if api_key is None:
            msg = "OPENROUTER_API_KEY is required for a live call"
            raise LiveCallForbiddenError(msg)
        self._key = api_key
        self._timeout = timeout_seconds
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds),
            transport=http_transport,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> OpenRouterTransport:
        """Build from process settings; the CI and key checks run in `__init__`."""
        return cls(
            api_key=settings.openrouter_api_key,
            timeout_seconds=settings.gateway_timeout_seconds,
            ci=settings.ci,
            base_url=settings.model_base_url or BASE_URL,
        )

    async def aclose(self) -> None:
        """Close the connection pool."""
        await self._client.aclose()

    async def post(self, request: TransportRequest) -> TransportReply:
        """One call. The whole exchange, not each phase, is bounded by the timeout."""
        if request.max_tokens > MAX_TOKENS_CAP:
            msg = f"max_tokens {request.max_tokens} is above the cap of {MAX_TOKENS_CAP}"
            raise InvalidRequestError(msg)
        payload = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        headers = {"Authorization": f"Bearer {self._key.get_secret_value()}"}
        try:
            async with asyncio.timeout(self._timeout):
                response = await self._client.post(
                    "/chat/completions", json=payload, headers=headers
                )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            msg = "the model service could not be reached"
            raise _error(ProviderUnavailableError, msg, billed=False) from exc
        except (
            httpx.TimeoutException,
            httpx.ReadError,
            httpx.RemoteProtocolError,
            TimeoutError,
        ) as exc:
            msg = "the model call timed out or the connection was lost after it was sent"
            raise _error(ProviderTimeoutError, msg, billed=True) from exc
        except httpx.TransportError as exc:
            msg = "the model call failed in transport"
            # Unclassified: it may have been sent, so keep the reservation (the safe side).
            raise _error(ProviderUnavailableError, msg, billed=True) from exc
        return self._reply(response)

    def _reply(self, response: httpx.Response) -> TransportReply:
        status = response.status_code
        if 200 <= status < 300:
            try:
                completion = _Completion.model_validate_json(response.content)
            except ValidationError as exc:
                # `from None`: the validation error's repr repeats the body, which may echo the
                # prompt. Keep only the names of the offending fields.
                fields = ", ".join(
                    ".".join(str(part) for part in e["loc"])
                    for e in exc.errors(include_input=False, include_url=False)
                )
                msg = f"the model reply could not be parsed (fields: {fields})"
                raise _error(ProviderProtocolError, msg, billed=True) from None
            return TransportReply(
                text=completion.choices[0].message.content,
                input_tokens=completion.usage.prompt_tokens,
                output_tokens=completion.usage.completion_tokens,
                finish_reason=completion.choices[0].finish_reason or "unknown",
            )
        if status == 402:
            raise _error(
                ProviderCreditExhaustedError, "the provider reported no credit", billed=False
            )
        if status == 429:
            raise _error(RateLimitedError, "the provider rate-limited the call", billed=False)
        if status == 408:
            raise _error(
                ProviderTimeoutError, "the provider reported a request timeout", billed=True
            )
        if 400 <= status < 500:
            raise _error(
                ProviderRejectedError, f"the provider refused the request ({status})", billed=False
            )
        raise _error(
            ProviderUnavailableError,
            f"the provider failed ({status})",
            billed=_reports_usage(response),
        )
