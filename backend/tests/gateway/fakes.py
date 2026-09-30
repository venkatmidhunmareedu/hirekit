"""In-memory stand-ins for the ledger, the transaction and the transport."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateway.key import input_sha256, request_key
from app.gateway.recordings import RecordingStore
from app.gateway.service import Gateway, Transaction
from app.gateway.transport import Transport, TransportReply, TransportRequest
from app.gateway.types import GatewayRequest, RecordedResponse, Recording

DB = "postgresql+asyncpg://postgres:postgres@localhost:5432/test"


@dataclass
class ReplayRow:
    role_id: UUID | None
    purpose: str
    model: str
    request_key: str
    schema_retry: int
    input_tokens: int
    output_tokens: int


@dataclass
class FakeLedger:
    """Records replay logs; reserve, settle and release are noted so a test can see none ran."""

    rows: list[ReplayRow] = field(default_factory=list)
    fail_log: bool = False
    forbidden_calls: list[str] = field(default_factory=list)

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
            raise OperationalError("INSERT", {}, Exception("database down"))
        self.rows.append(
            ReplayRow(
                role_id, purpose, model, request_key, schema_retry, input_tokens, output_tokens
            )
        )
        return len(self.rows)

    async def reserve(self, *args: object, **kwargs: object) -> None:
        self.forbidden_calls.append("reserve")

    async def settle(self, *args: object, **kwargs: object) -> None:
        self.forbidden_calls.append("settle")

    async def release(self, *args: object, **kwargs: object) -> None:
        self.forbidden_calls.append("release")


@asynccontextmanager
async def fake_transaction() -> AsyncIterator[AsyncSession]:
    """A transaction with an unbound session: the fake ledger never uses it."""
    yield AsyncSession()


class ExplodingTransport:
    """Any use of it is a test failure: replay must never build or call a transport."""

    async def post(self, request: TransportRequest) -> TransportReply:
        msg = "the transport was used"
        raise AssertionError(msg)

    async def aclose(self) -> None:
        return None


def make_settings(
    recordings_dir: Path,
    *,
    model_mode: Literal["replay", "live"] = "replay",
    openrouter_api_key: str | None = None,
) -> Settings:
    """Settings that ignore any .env file and write recordings under `recordings_dir`."""
    return Settings(
        _env_file=None,
        database_url=DB,
        recordings_dir=recordings_dir,
        model_mode=model_mode,
        openrouter_api_key=SecretStr(openrouter_api_key) if openrouter_api_key else None,
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
