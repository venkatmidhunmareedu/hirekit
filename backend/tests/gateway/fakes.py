"""In-memory stand-ins for the ledger, the transaction and the transport.

`FakeLedger` follows the real repository's rules (an atomic reserve under the limit, settle and
release only on a still-reserved row) so the service can be tested without Postgres; the real
repository is proven against Postgres in tests/integration/test_gateway_ledger.py.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.repositories.gateway_ledger import Reservation
from app.gateway.errors import GatewayError
from app.gateway.key import input_sha256, request_key
from app.gateway.recordings import RecordingStore
from app.gateway.service import Gateway, Transaction
from app.gateway.transport import Transport, TransportReply, TransportRequest
from app.gateway.types import GatewayRequest, RecordedResponse, Recording

DB = "postgresql+asyncpg://postgres:postgres@localhost:5432/test"


@dataclass
class CallRow:
    """One fake `call_log` row."""

    id: int
    role_id: UUID | None
    purpose: str
    status: str
    model: str
    request_key: str
    schema_retry: int
    cost_usd: Decimal
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class FakeLedger:
    """A budget and a call log in memory. `budget_calls` names every reserve, settle, release."""

    spent: Decimal | None = Decimal(0)
    rows: list[CallRow] = field(default_factory=list)
    budget_calls: list[str] = field(default_factory=list)
    fail_log: bool = False
    fail_reserve: bool = False
    fail_settle: bool = False
    fail_release: bool = False

    def _down(self) -> OperationalError:
        return OperationalError("STATEMENT", {}, Exception("database down"))

    async def read_spent(self, session: AsyncSession) -> Decimal | None:
        return self.spent

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
        if self.fail_log:
            raise self._down()
        row = CallRow(
            len(self.rows) + 1,
            role_id,
            purpose,
            "replayed",
            model,
            request_key,
            schema_retry,
            Decimal(0),
            input_tokens,
            output_tokens,
        )
        self.rows.append(row)
        return row.id

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
        self.budget_calls.append("reserve")
        if self.fail_reserve:
            raise self._down()
        if self.spent is None or self.spent + amount > limit:
            return None
        self.spent += amount
        row = CallRow(
            len(self.rows) + 1,
            role_id,
            purpose,
            "reserved",
            model,
            request_key,
            schema_retry,
            amount,
        )
        self.rows.append(row)
        return Reservation(call_id=row.id, amount=amount)

    def _reserved(self, call_id: int) -> CallRow | None:
        row = self.rows[call_id - 1]
        return row if row.status == "reserved" else None

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
        self.budget_calls.append("settle")
        if self.fail_settle:
            raise self._down()
        row = self._reserved(call_id)
        if row is None or self.spent is None:
            return False
        self.spent = min(limit, max(Decimal(0), self.spent - row.cost_usd + actual))
        row.status, row.cost_usd = "settled", actual
        row.input_tokens, row.output_tokens = input_tokens, output_tokens
        return True

    async def release(self, session: AsyncSession, *, call_id: int) -> bool:
        self.budget_calls.append("release")
        if self.fail_release:
            raise self._down()
        row = self._reserved(call_id)
        if row is None or self.spent is None:
            return False
        self.spent = max(Decimal(0), self.spent - row.cost_usd)
        row.status, row.cost_usd = "released", Decimal(0)
        return True


class TrackingTransaction:
    """A transaction factory that counts how many are open right now."""

    def __init__(self) -> None:
        self.open = 0
        self.total = 0

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AsyncSession]:
        self.open += 1
        self.total += 1
        try:
            yield AsyncSession()
        finally:
            self.open -= 1


@asynccontextmanager
async def fake_transaction() -> AsyncIterator[AsyncSession]:
    """A transaction with an unbound session: the fake ledger never uses it."""
    yield AsyncSession()


class ScriptedTransport:
    """Returns or raises what it was given, in order, and records every request."""

    def __init__(
        self,
        *results: TransportReply | BaseException,
        transactions: TrackingTransaction | None = None,
    ) -> None:
        self.results = list(results)
        self.requests: list[TransportRequest] = []
        self.open_transactions_at_call: list[int] = []
        self.closed = False
        self._transactions = transactions

    async def post(self, request: TransportRequest) -> TransportReply:
        self.requests.append(request)
        if self._transactions is not None:
            self.open_transactions_at_call.append(self._transactions.open)
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    async def aclose(self) -> None:
        self.closed = True


class ExplodingTransport:
    """Any use of it is a test failure: replay must never build or call a transport."""

    async def post(self, request: TransportRequest) -> TransportReply:
        msg = "the transport was used"
        raise AssertionError(msg)

    async def aclose(self) -> None:
        return None


def billed(error: GatewayError, *, kept: bool) -> GatewayError:
    """Set what the transport would: whether the call may have been billed."""
    error.billed = kept
    return error


def make_settings(
    recordings_dir: Path,
    *,
    model_mode: Literal["replay", "live"] = "replay",
    openrouter_api_key: str | None = None,
    record_responses: bool = False,
) -> Settings:
    """Settings that ignore any .env file and write recordings under `recordings_dir`."""
    return Settings(
        _env_file=None,
        database_url=DB,
        recordings_dir=recordings_dir,
        model_mode=model_mode,
        openrouter_api_key=SecretStr(openrouter_api_key) if openrouter_api_key else None,
        record_responses=record_responses,
    )


def key_for(request: GatewayRequest, settings: Settings) -> str:
    return request_key(
        model=settings.model_id,
        prompt_version=request.prompt_version,
        schema_retry=request.schema_retry,
        max_tokens=request.clamped_max_tokens,
        system=request.system.value,
        input_text=request.input.value,
    )


def record(request: GatewayRequest, settings: Settings, text: str = '{"scores": []}') -> str:
    """Write a recording for `request` into the settings' directory and return its key."""
    key = key_for(request, settings)
    RecordingStore(settings.recordings_dir).put(
        Recording(
            key_version=1,
            request_key=key,
            input_sha256=input_sha256(
                purpose=request.purpose,
                schema_retry=request.schema_retry,
                input_text=request.input.value,
            ),
            model=settings.model_id,
            prompt_version=request.prompt_version,
            schema_retry=request.schema_retry,
            purpose=request.purpose,
            response=RecordedResponse(
                text=text, input_tokens=1234, output_tokens=321, finish_reason="stop"
            ),
        )
    )
    return key


def make_gateway(
    settings: Settings,
    ledger: FakeLedger,
    *,
    transport_factory: Callable[[], Transport] | None = None,
    transaction: Transaction = fake_transaction,
) -> Gateway:
    return Gateway(
        settings=settings,
        transaction=transaction,
        ledger=ledger,
        store=RecordingStore(settings.recordings_dir),
        transport_factory=transport_factory,
    )
