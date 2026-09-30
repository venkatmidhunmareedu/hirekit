"""`Gateway.complete`: the single public entry through which every model call passes.

Order of work (docs/design/gateway-lld.md section 4.1): check the input classes, clamp and hash
the request, then replay a recording or (item 6) make a live call under a budget reservation.
Nothing before the class check touches a key, the database or the network. Replay never builds a
transport and never touches the budget row (tenets 5 and 8).
"""

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from decimal import Decimal
from typing import Protocol
from uuid import UUID

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateway.errors import (
    InputNotAllowedError,
    LedgerUnavailableError,
    RecordingMissingError,
)
from app.gateway.key import input_sha256, request_key
from app.gateway.recordings import RecordingStore
from app.gateway.text import PromptText
from app.gateway.transport import Transport
from app.gateway.types import PURPOSE_INPUT, GatewayRequest, GatewayResponse, Recording

log = structlog.get_logger()

Transaction = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class Ledger(Protocol):
    """What the gateway needs from `GatewayLedger`; unit tests inject a fake."""

    async def log_replay(
        self,
        session: AsyncSession,
        *,
        role_id: UUID | None,
        purpose: str,
        model: str,
        request_key: str,
        schema_retry: int,
        input_tokens: int,
        output_tokens: int,
    ) -> int:
        """Log a replayed call with cost 0."""
        ...


class Gateway:
    """One instance per process. It owns its transactions and never sees the caller's session."""

    def __init__(
        self,
        *,
        settings: Settings,
        transaction: Transaction,
        ledger: Ledger,
        store: RecordingStore,
        transport_factory: Callable[[], Transport] | None = None,
    ) -> None:
        self._settings = settings
        self._transaction = transaction
        self._ledger = ledger
        self._store = store
        self._transport_factory = transport_factory

    async def complete(self, request: GatewayRequest) -> GatewayResponse:
        """Make or replay one model call. Raises a `GatewayError` on any failure."""
        self._check_classes(request)
        key = request_key(
            model=self._settings.model_id,
            prompt_version=request.prompt_version,
            schema_retry=request.schema_retry,
            max_tokens=request.clamped_max_tokens,
            system=request.system.value,
            input_text=request.input.value,
        )
        if self._settings.model_mode == "replay":
            return await self._replay(request, key)
        return await self._live(request, key)

    def _check_classes(self, request: GatewayRequest) -> None:
        """Refuse anything but the exact text classes (AC-US-00-005-3, AC-US-00-005-4).

        Messages name classes and the purpose, never the text.
        """
        system: object = request.system  # typed, but a caller can still pass a plain str
        if not isinstance(system, PromptText):
            msg = f"system must be a PromptText, got {type(system).__name__}"
            raise InputNotAllowedError(msg)
        wanted = PURPOSE_INPUT[request.purpose]
        if not isinstance(request.input, wanted):
            msg = (
                f"purpose {request.purpose!r} takes {wanted.__name__}, "
                f"got {type(request.input).__name__}"
            )
            raise InputNotAllowedError(msg)

    async def _replay(self, request: GatewayRequest, key: str) -> GatewayResponse:
        recording = await asyncio.to_thread(self._store.get, key)
        if recording is None:
            found = await asyncio.to_thread(
                self._store.find_stale,
                input_sha256(
                    purpose=request.purpose,
                    schema_retry=request.schema_retry,
                    input_text=request.input.value,
                ),
                exclude_key=key,
            )
            raise RecordingMissingError(key, found)
        await self._log_replay(request, recording)
        reply = recording.response
        log.info(
            "gateway_call",
            purpose=request.purpose,
            request_key=key,
            replayed=True,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            cost_usd="0",
        )
        return GatewayResponse(
            text=reply.text,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            finish_reason=reply.finish_reason,
            request_key=key,
            replayed=True,
            cost_usd=Decimal(0),
        )

    async def _log_replay(self, request: GatewayRequest, recording: Recording) -> None:
        """One `call_log` row, status replayed. A database failure is retryable and free."""
        try:
            async with self._transaction() as session:
                await self._ledger.log_replay(
                    session,
                    role_id=request.role_id,
                    purpose=request.purpose,
                    model=self._settings.model_id,
                    request_key=recording.request_key,
                    schema_retry=request.schema_retry,
                    input_tokens=recording.response.input_tokens,
                    output_tokens=recording.response.output_tokens,
                )
        except (SQLAlchemyError, OSError) as exc:
            msg = "the call log could not be written"
            raise LedgerUnavailableError(msg) from exc

    async def _live(self, request: GatewayRequest, key: str) -> GatewayResponse:
        """The live path (reserve, call, settle or release) arrives in gateway LLD item 6."""
        msg = "the live path is not built yet (docs/design/gateway-lld.md item 6)"
        raise NotImplementedError(msg)
