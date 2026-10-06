"""OpenRouterTransport maps every outcome to a reply or a typed error, and never leaks."""

import asyncio
import json
from collections.abc import Callable, Coroutine

import httpx
import pytest
from pydantic import SecretStr

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
from app.gateway.transport import BASE_URL, OpenRouterTransport, TransportRequest

KEY = "sk-or-secret-key-value"
BODY_LEAK = "the-prompt-text-the-provider-echoed"
REQUEST = TransportRequest(
    model="anthropic/claude-haiku-4.5", system="sys", user="resume", max_tokens=1500
)
GOOD = {
    "choices": [{"message": {"content": '{"scores": []}'}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 1234, "completion_tokens": 321},
}
Handler = (
    Callable[[httpx.Request], httpx.Response]
    | Callable[[httpx.Request], Coroutine[None, None, httpx.Response]]
)


def transport(handler: Handler, *, timeout: float = 5.0) -> OpenRouterTransport:
    return OpenRouterTransport(
        api_key=SecretStr(KEY),
        timeout_seconds=timeout,
        ci=False,
        http_transport=httpx.MockTransport(handler),
    )


def reply(status: int, body: object = GOOD) -> Handler:
    return lambda _request: httpx.Response(status, json=body)


def raising(exc: Exception) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


async def failure(handler: Handler, *, limit: float = 5.0) -> GatewayError:
    with pytest.raises(GatewayError) as caught:
        await transport(handler, timeout=limit).post(REQUEST)
    return caught.value


async def test_a_good_reply_is_parsed_with_token_counts() -> None:
    result = await transport(reply(200)).post(REQUEST)

    assert result.text == '{"scores": []}'
    assert (result.input_tokens, result.output_tokens) == (1234, 321)
    assert result.finish_reason == "stop"


async def test_finish_reason_length_is_passed_through() -> None:
    body = {**GOOD, "choices": [{"message": {"content": "{"}, "finish_reason": "length"}]}
    assert (await transport(reply(200, body)).post(REQUEST)).finish_reason == "length"


async def test_a_missing_finish_reason_reads_as_unknown() -> None:
    body = {**GOOD, "choices": [{"message": {"content": "x"}}]}
    assert (await transport(reply(200, body)).post(REQUEST)).finish_reason == "unknown"


async def test_the_request_carries_model_messages_cap_temperature_and_bearer_key() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=GOOD)

    await transport(handler).post(REQUEST)

    sent = json.loads(seen[0].content)
    assert seen[0].url.path.endswith("/chat/completions")
    assert seen[0].headers["Authorization"] == f"Bearer {KEY}"
    assert sent["model"] == "anthropic/claude-haiku-4.5"
    assert sent["max_tokens"] == 1500
    assert sent["temperature"] == 0
    assert sent["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "resume"},
    ]


async def test_request_sent_never_exceeds_1500_tokens() -> None:
    """AC-US-02-001-3: with no clamp upstream the transport still refuses and sends nothing."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=GOOD)

    too_big = TransportRequest(model="m", system="s", user="u", max_tokens=1501)
    with pytest.raises(InvalidRequestError):
        await transport(handler).post(too_big)
    assert calls == []


@pytest.mark.parametrize(
    ("status", "error", "billed"),
    [
        (402, ProviderCreditExhaustedError, False),
        (429, RateLimitedError, False),
        (408, ProviderTimeoutError, True),
        (400, ProviderRejectedError, False),
        (401, ProviderRejectedError, False),
        (404, ProviderRejectedError, False),
        (500, ProviderUnavailableError, False),
        (503, ProviderUnavailableError, False),
    ],
)
async def test_each_status_maps_to_its_error_and_reservation_action(
    status: int, error: type[GatewayError], billed: bool
) -> None:
    err = await failure(reply(status, {"error": {"message": BODY_LEAK}}))
    assert type(err) is error
    assert err.billed is billed


async def test_5xx_with_usage_in_the_body_keeps_the_reservation() -> None:
    err = await failure(reply(502, {"usage": {"prompt_tokens": 10, "completion_tokens": 0}}))
    assert isinstance(err, ProviderUnavailableError)
    assert err.billed is True


async def test_429_releases_the_reservation_and_is_retryable() -> None:
    err = await failure(reply(429))
    assert isinstance(err, RateLimitedError)
    assert (err.billed, err.retryable) == (False, True)


async def test_402_releases_the_reservation_and_is_not_retryable() -> None:
    err = await failure(reply(402))
    assert isinstance(err, ProviderCreditExhaustedError)
    assert (err.billed, err.retryable) == (False, False)


@pytest.mark.parametrize(
    "body",
    [
        {"usage": {"prompt_tokens": 1, "completion_tokens": 1}},
        {"choices": [], "usage": {}},
        {"x": 1},
    ],
)
async def test_unparseable_2xx_keeps_the_reservation(body: object) -> None:
    err = await failure(reply(200, body))
    assert isinstance(err, ProviderProtocolError)
    assert (err.billed, err.retryable) == (True, False)


async def test_non_json_2xx_keeps_the_reservation() -> None:
    err = await failure(lambda _request: httpx.Response(200, content=b"<html>oops</html>"))
    assert isinstance(err, ProviderProtocolError)
    assert err.billed is True


@pytest.mark.parametrize("exc", [httpx.ConnectError("no route"), httpx.ConnectTimeout("slow")])
async def test_connect_errors_release_the_reservation(exc: Exception) -> None:
    """The request was never sent, so nothing was billed."""
    err = await failure(raising(exc))
    assert isinstance(err, ProviderUnavailableError)
    assert (err.billed, err.retryable) == (False, True)


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ReadTimeout("slow"),
        httpx.WriteTimeout("slow"),
        httpx.PoolTimeout("busy"),
        httpx.ReadError("reset"),
        httpx.RemoteProtocolError("dropped"),
    ],
)
async def test_timeouts_and_a_lost_connection_after_send_keep_the_reservation(
    exc: Exception,
) -> None:
    err = await failure(raising(exc))
    assert isinstance(err, ProviderTimeoutError)
    assert (err.billed, err.retryable) == (True, True)


async def test_an_unclassified_transport_error_keeps_the_reservation() -> None:
    err = await failure(raising(httpx.UnsupportedProtocol("weird")))
    assert isinstance(err, ProviderUnavailableError)
    assert err.billed is True


async def test_whole_call_is_bounded_by_the_timeout_not_each_phase() -> None:
    """HLD section 8: one call cannot outlast the lease, however the phases add up."""

    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200, json=GOOD)

    err = await failure(slow, limit=0.05)
    assert isinstance(err, ProviderTimeoutError)
    assert err.billed is True


@pytest.mark.parametrize("status", [400, 429, 500, 200])
async def test_no_error_carries_the_key_or_the_response_body(status: int) -> None:
    """AC-US-02-001-5, AC-US-02-001-6, tenet 7."""
    body = {"error": {"message": BODY_LEAK}, "usage": None} if status != 200 else {"x": BODY_LEAK}
    err = await failure(reply(status, body))
    text = f"{err.message} {err.details} {err!r} {err.__cause__!r}"
    assert KEY not in text
    assert BODY_LEAK not in text


async def test_a_transport_failure_error_does_not_carry_the_key() -> None:
    err = await failure(raising(httpx.ReadTimeout(f"timed out talking with {BODY_LEAK}")))
    assert KEY not in f"{err.message} {err!r}"
    assert BODY_LEAK not in err.message


def test_ci_blocks_transport_construction_even_if_mode_is_live() -> None:
    """AC-US-02-003-4: the guard sits where the client is built, so a fake can still be injected."""
    with pytest.raises(LiveCallForbiddenError, match="CI"):
        OpenRouterTransport(api_key=SecretStr(KEY), timeout_seconds=5, ci=True)


def test_a_live_transport_needs_a_key() -> None:
    with pytest.raises(LiveCallForbiddenError, match="OPENROUTER_API_KEY"):
        OpenRouterTransport(api_key=None, timeout_seconds=5, ci=False)


async def test_from_settings_reads_key_timeout_and_ci() -> None:
    from app.core.config import Settings

    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://u:p@localhost:5432/t",
        model_mode="live",
        openrouter_api_key=KEY,
        gateway_timeout_seconds=7,
    )
    live = OpenRouterTransport.from_settings(settings)
    await live.aclose()
    with pytest.raises(LiveCallForbiddenError):
        OpenRouterTransport.from_settings(
            Settings(
                _env_file=None, database_url="postgresql+asyncpg://u:p@localhost:5432/t", ci=True
            )
        )


async def test_from_settings_uses_the_configured_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import Settings

    seen: dict[str, object] = {}
    real_client = httpx.AsyncClient

    def spy(
        *, base_url: str, timeout: httpx.Timeout, transport: httpx.AsyncBaseTransport | None
    ) -> httpx.AsyncClient:
        seen["base_url"] = base_url
        return real_client(base_url=base_url, timeout=timeout, transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", spy)
    live = OpenRouterTransport.from_settings(
        Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://u:p@localhost:5432/t",
            model_mode="live",
            openrouter_api_key=KEY,
            model_base_url="https://proxy.example.com/v1/",
        )
    )
    await live.aclose()

    assert seen["base_url"] == "https://proxy.example.com/v1"


async def test_from_settings_defaults_to_the_openrouter_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import Settings

    seen: dict[str, object] = {}
    real_client = httpx.AsyncClient

    def spy(
        *, base_url: str, timeout: httpx.Timeout, transport: httpx.AsyncBaseTransport | None
    ) -> httpx.AsyncClient:
        seen["base_url"] = base_url
        return real_client(base_url=base_url, timeout=timeout, transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", spy)
    live = OpenRouterTransport.from_settings(
        Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://u:p@localhost:5432/t",
            model_mode="live",
            openrouter_api_key=KEY,
        )
    )
    await live.aclose()

    assert seen["base_url"] == BASE_URL == "https://openrouter.ai/api/v1"
