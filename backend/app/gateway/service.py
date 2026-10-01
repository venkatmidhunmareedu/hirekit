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
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.budget.policy import BUDGET_LIMIT_USD, actual_cost, reserve_amount
from app.core.config import Settings
from app.db.repositories.gateway_ledger import Reservation
from app.gateway.errors import (
    BudgetNotInitialisedError,
    BudgetReachedError,
    GatewayError,
    InputNotAllowedError,
    LedgerUnavailableError,
    RecordingMissingError,
)
from app.gateway.key import KEY_VERSION, input_sha256, request_key
from app.gateway.recordings import RecordingStore
from app.gateway.text import PromptText
from app.gateway.transport import OpenRouterTransport, Transport, TransportReply, TransportRequest
from app.gateway.types import (
    PURPOSE_INPUT,
    GatewayRequest,
    GatewayResponse,
    RecordedResponse,
    Recording,
)

log = structlog.get_logger()

Transaction = Callable[[], AbstractAsyncContextManager[AsyncSession]]

# Only "the database cannot be reached" is retryable and free. An IntegrityError (a role id that
# does not exist, say) is a bug: it propagates as is instead of looking like an outage.
_UNREACHABLE = (OperationalError, InterfaceError, OSError)


class Ledger(Protocol):
    """What the gateway needs from `GatewayLedger`; unit tests inject a fake."""

    async def read_spent(self, session: AsyncSession) -> Decimal | None:
        """USD spent or reserved so far, or None when the budget row is missing."""
        ...

    async def reserve(
        self,
        session: AsyncSession,
        *,
        amount: Decimal,
        limit: Decimal,
        role_id: UUID | None,
        purpose: str,
        model: str,
        request_key: str,
        schema_retry: int,
    ) -> Reservation | None:
        """Hold `amount` under `limit`, or return None."""
        ...

    async def settle(
        self,
        session: AsyncSession,
        *,
        call_id: int,
        input_tokens: int,
        output_tokens: int,
        actual: Decimal,
        limit: Decimal,
    ) -> bool:
        """Replace a reservation with the actual cost."""
        ...

    async def release(self, session: AsyncSession, *, call_id: int) -> bool:
        """Give a reservation back."""
        ...

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
        self._transport: Transport | None = None

    async def aclose(self) -> None:
        """Close the transport if a live call ever built one."""
        if self._transport is not None:
            await self._transport.aclose()

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
        except _UNREACHABLE as exc:
            msg = "the call log could not be written"
            raise LedgerUnavailableError(msg) from exc

    def _get_transport(self) -> Transport:
        """Build the transport on the first live call; its constructor checks CI and the key."""
        if self._transport is None:
            factory = self._transport_factory or (
                lambda: OpenRouterTransport.from_settings(self._settings)
            )
            self._transport = factory()
        return self._transport

    async def _live(self, request: GatewayRequest, key: str) -> GatewayResponse:
        """Reserve, call, then settle or release (docs/design/gateway-lld.md section 4.2).

        The transport is built first, so a refusal (CI, no key) makes no reservation. A
        `CancelledError` or crash after the reservation leaves it in place: over-counted, never
        under-counted.
        """
        transport = self._get_transport()
        s = self._settings
        price_in, price_out = s.price_input_usd_per_mtok, s.price_output_usd_per_mtok
        amount = reserve_amount(
            request.clamped_max_tokens,
            len(request.system.value) + len(request.input.value),
            price_in,
            price_out,
        )
        reservation = await self._reserve(request, key, amount)
        try:
            reply = await transport.post(
                TransportRequest(
                    model=s.model_id,
                    system=request.system.value,
                    user=request.input.value,
                    max_tokens=request.clamped_max_tokens,
                )
            )
        except GatewayError as error:
            if not error.billed:
                await self._release(reservation, key)
            raise
        cost = actual_cost(reply.input_tokens, reply.output_tokens, price_in, price_out)
        await self._settle(reservation, key, reply, cost)
        if s.record_responses:
            await asyncio.to_thread(self._store.put, self._recording(request, key, reply))
        log.info(
            "gateway_call",
            purpose=request.purpose,
            request_key=key,
            replayed=False,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            cost_usd=str(cost),
        )
        return GatewayResponse(
            text=reply.text,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            finish_reason=reply.finish_reason,
            request_key=key,
            replayed=False,
            cost_usd=cost,
        )

    async def _reserve(self, request: GatewayRequest, key: str, amount: Decimal) -> Reservation:
        """T1: hold the amount and log it as reserved, committed before the HTTP call."""
        spent: Decimal | None = None
        try:
            async with self._transaction() as session:
                reservation = await self._ledger.reserve(
                    session,
                    amount=amount,
                    limit=BUDGET_LIMIT_USD,
                    role_id=request.role_id,
                    purpose=request.purpose,
                    model=self._settings.model_id,
                    request_key=key,
                    schema_retry=request.schema_retry,
                )
                if reservation is None:
                    spent = await self._ledger.read_spent(session)
        except _UNREACHABLE as exc:
            msg = "the budget could not be reserved"
            raise LedgerUnavailableError(msg) from exc
        if reservation is not None:
            return reservation
        if spent is None:
            msg = "the budget row does not exist; start live mode through the spend ledger"
            raise BudgetNotInitialisedError(msg)
        raise BudgetReachedError(spent, BUDGET_LIMIT_USD)

    async def _settle(
        self, reservation: Reservation, key: str, reply: TransportReply, cost: Decimal
    ) -> None:
        """T2: replace the reservation with the actual cost. A failure keeps it reserved."""
        try:
            async with self._transaction() as session:
                await self._ledger.settle(
                    session,
                    call_id=reservation.call_id,
                    input_tokens=reply.input_tokens,
                    output_tokens=reply.output_tokens,
                    actual=cost,
                    limit=BUDGET_LIMIT_USD,
                )
        except SQLAlchemyError, OSError:
            # The call was paid for, so the reply is still returned; the row stays reserved
            # at its full reservation until a person reconciles it (HLD section 7).
            log.warning("budget_settle_failed", call_id=reservation.call_id, request_key=key)

    async def _release(self, reservation: Reservation, key: str) -> None:
        """T3: give the reservation back. A failure keeps it reserved, which over-counts."""
        try:
            async with self._transaction() as session:
                await self._ledger.release(session, call_id=reservation.call_id)
        except SQLAlchemyError, OSError:
            log.warning("budget_release_failed", call_id=reservation.call_id, request_key=key)

    def _recording(self, request: GatewayRequest, key: str, reply: TransportReply) -> Recording:
        """The file `make record` writes: only 2xx replies get here."""
        return Recording(
            key_version=KEY_VERSION,
            request_key=key,
            input_sha256=input_sha256(
                purpose=request.purpose,
                schema_retry=request.schema_retry,
                input_text=request.input.value,
            ),
            model=self._settings.model_id,
            prompt_version=request.prompt_version,
            schema_retry=1 if request.schema_retry else 0,
            purpose=request.purpose,
            response=RecordedResponse(
                text=reply.text,
                input_tokens=reply.input_tokens,
                output_tokens=reply.output_tokens,
                finish_reason=reply.finish_reason,
            ),
        )
