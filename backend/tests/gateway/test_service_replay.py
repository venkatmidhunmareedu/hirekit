"""Gateway.complete in replay mode: input checks first, recordings only, the budget untouched."""

from pathlib import Path
from uuid import UUID

import pytest
from structlog.testing import capture_logs

from app.gateway.errors import (
    InputNotAllowedError,
    LedgerUnavailableError,
    RecordingMissingError,
)
from app.gateway.text import mint_anonymized, mint_job_description
from app.gateway.transport import Transport
from app.gateway.types import GatewayRequest
from tests.gateway.fakes import (
    ExplodingTransport,
    FakeLedger,
    key_for,
    make_gateway,
    make_settings,
    record,
)
from tests.gateway.helpers import make_request

RESUME = "Built a payments service in Python at Acme."
ROLE = UUID("10000000-0000-0000-0000-000000000001")


def wrong(**overrides: object) -> GatewayRequest:
    """A request with fields replaced by the wrong type, as a careless caller might build it."""
    good = make_request(text=RESUME)
    fields: dict[str, object] = {
        "purpose": good.purpose,
        "role_id": good.role_id,
        "prompt_version": good.prompt_version,
        "system": good.system,
        "input": good.input,
        "max_tokens": good.max_tokens,
        "schema_retry": good.schema_retry,
    }
    return GatewayRequest(**{**fields, **overrides})  # type: ignore[arg-type]  # deliberate


async def test_raw_text_passed_as_string_is_refused(tmp_path: Path) -> None:
    """AC-US-00-005-3."""
    gateway = make_gateway(make_settings(tmp_path), FakeLedger())
    with pytest.raises(InputNotAllowedError):
        await gateway.complete(wrong(input=RESUME))


async def test_raw_text_wrapped_in_job_description_class_is_refused_for_scoring(
    tmp_path: Path,
) -> None:
    """AC-US-00-005-4, tenet 2: the wrong class for the purpose is refused too."""
    gateway = make_gateway(make_settings(tmp_path), FakeLedger())
    with pytest.raises(InputNotAllowedError, match="AnonymizedText"):
        await gateway.complete(wrong(input=mint_job_description(RESUME)))


async def test_anonymized_text_is_refused_for_the_job_description_purposes(tmp_path: Path) -> None:
    gateway = make_gateway(make_settings(tmp_path), FakeLedger())
    for purpose in ("criteria", "kit"):
        with pytest.raises(InputNotAllowedError, match="JobDescriptionText"):
            await gateway.complete(wrong(purpose=purpose, input=mint_anonymized(RESUME)))


async def test_raw_text_in_the_system_field_is_refused(tmp_path: Path) -> None:
    """AC-US-00-005-3, tenet 2: a plain string cannot be smuggled in as the system prompt."""
    gateway = make_gateway(make_settings(tmp_path), FakeLedger())
    with pytest.raises(InputNotAllowedError, match="PromptText"):
        await gateway.complete(wrong(system=RESUME))


async def test_input_check_runs_before_any_key_database_or_network_work(tmp_path: Path) -> None:
    """AC-US-00-005-3: a refused request touches no store, no ledger, no transport."""
    ledger = FakeLedger()

    def explode() -> None:
        pytest.fail("the transaction was opened before the input check")

    gateway = make_gateway(
        make_settings(tmp_path / "never-created"),
        ledger,
        transport_factory=ExplodingTransport,
        transaction=explode,  # type: ignore[arg-type]  # fails the test if it is called
    )
    with pytest.raises(InputNotAllowedError):
        await gateway.complete(wrong(input=RESUME))
    assert not (tmp_path / "never-created").exists()
    assert ledger.rows == []


async def test_refusal_messages_name_classes_not_text(tmp_path: Path) -> None:
    gateway = make_gateway(make_settings(tmp_path), FakeLedger())
    with pytest.raises(InputNotAllowedError) as caught:
        await gateway.complete(wrong(input=RESUME))
    assert "Acme" not in caught.value.message
    assert "Python" not in caught.value.message


async def test_replay_returns_recording_with_no_network_call(tmp_path: Path) -> None:
    """AC-US-02-003-1: no transport factory is even supplied."""
    settings = make_settings(tmp_path)
    request = make_request(text=RESUME)
    key = record(request, settings, text='{"scores": [3]}')

    reply = await make_gateway(settings, FakeLedger()).complete(request)

    assert reply.text == '{"scores": [3]}'
    assert (reply.input_tokens, reply.output_tokens, reply.finish_reason) == (1234, 321, "stop")
    assert reply.replayed is True
    assert reply.request_key == key
    assert reply.cost_usd == 0


async def test_replay_never_constructs_the_transport(tmp_path: Path) -> None:
    """AC-US-02-003-1, tenet 5."""
    settings = make_settings(tmp_path)
    request = make_request(text=RESUME)
    record(request, settings)
    built: list[int] = []

    def factory() -> Transport:
        built.append(1)
        return ExplodingTransport()

    await make_gateway(settings, FakeLedger(), transport_factory=factory).complete(request)

    assert built == []


async def test_replay_never_calls_reserve_settle_or_release_on_the_ledger(tmp_path: Path) -> None:
    """AC-US-02-003-1, HLD section 16: replay does not touch the budget."""
    settings = make_settings(tmp_path)
    request = make_request(text=RESUME)
    record(request, settings)
    ledger = FakeLedger()

    await make_gateway(settings, ledger).complete(request)

    assert ledger.forbidden_calls == []


async def test_ten_replay_passes_never_touch_the_budget(tmp_path: Path) -> None:
    """HLD section 16 falsifier, unit twin: replaying a tape ten times reserves nothing."""
    settings = make_settings(tmp_path)
    requests = [make_request(text=f"resume number {n}") for n in range(9)]
    for request in requests:
        record(request, settings)
    ledger = FakeLedger()
    gateway = make_gateway(settings, ledger)

    for _ in range(10):
        for request in requests:
            await gateway.complete(request)

    assert ledger.forbidden_calls == []
    assert len(ledger.rows) == 90


async def test_replayed_call_logs_one_row_with_cost_zero_fields(tmp_path: Path) -> None:
    """AC-US-02-001-4, AC-US-02-003-1."""
    settings = make_settings(tmp_path)
    request = make_request(purpose="scoring", schema_retry=0, text=RESUME)
    key = record(request, settings)
    ledger = FakeLedger()

    await make_gateway(settings, ledger).complete(request)

    [row] = ledger.rows
    assert row.purpose == "scoring"
    assert row.role_id == ROLE
    assert row.request_key == key
    assert (row.input_tokens, row.output_tokens, row.schema_retry) == (1234, 321, 0)
    assert row.model == settings.model_id


async def test_missing_recording_fails_naming_the_key(tmp_path: Path) -> None:
    """AC-US-02-003-2."""
    settings = make_settings(tmp_path)
    request = make_request(text=RESUME)

    with pytest.raises(RecordingMissingError) as caught:
        await make_gateway(settings, FakeLedger()).complete(request)

    assert key_for(request, settings) in caught.value.message
    assert caught.value.stale is False


async def test_missing_recording_never_falls_back_to_a_live_call(tmp_path: Path) -> None:
    """AC-US-02-003-2: the transport factory is supplied and must stay unused."""
    settings = make_settings(tmp_path)
    ledger = FakeLedger()
    gateway = make_gateway(settings, ledger, transport_factory=ExplodingTransport)

    with pytest.raises(RecordingMissingError):
        await gateway.complete(make_request(text=RESUME))

    assert ledger.rows == []
    assert ledger.forbidden_calls == []


async def test_changed_prompt_reports_a_recording_for_the_same_input(tmp_path: Path) -> None:
    """AC-US-02-003-3."""
    settings = make_settings(tmp_path)
    old = make_request(prompt_version="score-v1", text=RESUME)
    old_key = record(old, settings)

    with pytest.raises(RecordingMissingError) as caught:
        await make_gateway(settings, FakeLedger()).complete(
            make_request(prompt_version="score-v2", text=RESUME)
        )

    assert caught.value.stale is True
    assert caught.value.found_key == old_key
    assert "different prompt" in caught.value.message


async def test_schema_retry_one_has_its_own_recording(tmp_path: Path) -> None:
    """REQ-023, decisions.md conflict 2: a recording for the first try does not serve the retry."""
    settings = make_settings(tmp_path)
    first = make_request(schema_retry=0, text=RESUME)
    record(first, settings, text="malformed")
    retry = make_request(schema_retry=1, text=RESUME)
    gateway = make_gateway(settings, FakeLedger())

    with pytest.raises(RecordingMissingError) as caught:
        await gateway.complete(retry)
    assert caught.value.stale is False  # a different retry index is a different input

    record(retry, settings, text='{"scores": []}')
    assert (await gateway.complete(first)).text == "malformed"
    assert (await gateway.complete(retry)).text == '{"scores": []}'


async def test_same_request_gives_same_key_on_any_role_id(tmp_path: Path) -> None:
    """AC-US-02-003-1: a recording made for one role replays for another."""
    settings = make_settings(tmp_path)
    request = make_request(text=RESUME)
    record(request, settings)
    other_role = GatewayRequest(
        purpose=request.purpose,
        role_id=UUID("99999999-0000-0000-0000-000000000009"),
        prompt_version=request.prompt_version,
        system=request.system,
        input=request.input,
        max_tokens=request.max_tokens,
        schema_retry=request.schema_retry,
    )

    reply = await make_gateway(settings, FakeLedger()).complete(other_role)

    assert reply.request_key == key_for(request, settings)


async def test_max_tokens_above_the_cap_hashes_like_the_cap(tmp_path: Path) -> None:
    """AC-US-02-001-3: the clamped value is what is keyed, so 5000 and 1500 share a recording."""
    settings = make_settings(tmp_path)
    record(make_request(max_tokens=1500, text=RESUME), settings)

    reply = await make_gateway(settings, FakeLedger()).complete(
        make_request(max_tokens=5000, text=RESUME)
    )

    assert reply.replayed is True


async def test_replay_log_failure_raises_ledger_unavailable(tmp_path: Path) -> None:
    """4.1 error branch: a database failure while logging is retryable and costs nothing."""
    settings = make_settings(tmp_path)
    request = make_request(text=RESUME)
    record(request, settings)

    with pytest.raises(LedgerUnavailableError) as caught:
        await make_gateway(settings, FakeLedger(fail_log=True)).complete(request)

    assert caught.value.retryable is True


async def test_no_resume_text_in_log_lines_or_error_messages(tmp_path: Path) -> None:
    """AC-US-02-001-6, AC-US-00-005-6, tenet 7."""
    settings = make_settings(tmp_path)
    request = make_request(text=RESUME)
    record(request, settings)
    gateway = make_gateway(settings, FakeLedger())

    with capture_logs() as logs:
        await gateway.complete(request)
        with pytest.raises(RecordingMissingError) as caught:
            await gateway.complete(make_request(prompt_version="v9", text=RESUME))

    text = f"{logs} {caught.value.message} {caught.value.details}"
    assert "Acme" not in text
    assert "payments" not in text
    assert any(line["event"] == "gateway_call" for line in logs)


async def test_live_mode_is_not_built_until_item_6(tmp_path: Path) -> None:
    """Placeholder that item 6 replaces with the live-path tests."""
    settings = make_settings(tmp_path, model_mode="live", openrouter_api_key="k")
    gateway = make_gateway(settings, FakeLedger())
    with pytest.raises(NotImplementedError):
        await gateway.complete(make_request(text=RESUME))
