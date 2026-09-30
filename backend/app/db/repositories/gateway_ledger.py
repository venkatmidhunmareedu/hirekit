"""All SQL the gateway runs: reserve, settle, release, log a replay, seed the budget.

Methods take the caller's `AsyncSession` and never commit; `Gateway` owns the transactions
(docs/design/gateway-lld.md section 5). Lock order is the `call_log` row first, then the
`budget` row. `reserve` locks only `budget` and inserts a new `call_log` row nobody else can
hold, so no two transactions can wait on each other.
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, insert, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Budget, CallLog


@dataclass(frozen=True)
class Reservation:
    """A committed hold on part of the budget, tied to its `call_log` row."""

    call_id: int
    amount: Decimal


class GatewayLedger:
    """Repository for `budget` and `call_log` as the gateway uses them."""

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
        """Add `amount` to the total only if it stays within `limit`, and log it as reserved.

        One atomic UPDATE: under READ COMMITTED Postgres re-checks the WHERE clause on the
        latest row version after waiting for the lock, so concurrent callers cannot overshoot.
        Returns None when it does not fit or the budget row is missing; the caller tells the two
        apart with `read_spent`.
        """
        updated = await session.scalar(
            update(Budget)
            .where(Budget.id == 1, Budget.spent_usd + amount <= limit)
            .values(spent_usd=Budget.spent_usd + amount, updated_at=func.now())
            .returning(Budget.spent_usd)
        )
        if updated is None:
            return None
        call_id = await session.scalar(
            insert(CallLog)
            .values(
                role_id=role_id,
                purpose=purpose,
                status="reserved",
                model=model,
                request_key=request_key,
                schema_retry=schema_retry,
                cost_usd=amount,
            )
            .returning(CallLog.id)
        )
        if call_id is None:  # pragma: no cover  (INSERT ... RETURNING always yields the id)
            msg = "call_log insert returned no id"
            raise RuntimeError(msg)
        return Reservation(call_id=call_id, amount=amount)

    async def _lock_reserved(self, session: AsyncSession, call_id: int) -> Decimal | None:
        """Lock a still-reserved row and return the amount it holds; None if it is not reserved."""
        result = await session.execute(
            select(CallLog.cost_usd)
            .where(CallLog.id == call_id, CallLog.status == "reserved")
            .with_for_update()
        )
        return result.scalar_one_or_none()

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
        """Replace the reserved amount with the actual cost. False if the row is not reserved.

        The budget moves only when the guarded `call_log` update matched, using the amount that
        row held, so a second settle, or a settle after a release, changes nothing. The total is
        clamped to `limit`; `call_log.cost_usd` keeps the true cost.
        """
        reserved = await self._lock_reserved(session, call_id)
        if reserved is None:
            return False
        await session.execute(
            update(CallLog)
            .where(CallLog.id == call_id)
            .values(
                status="settled",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=actual,
                updated_at=func.now(),
            )
        )
        await session.execute(
            update(Budget)
            .where(Budget.id == 1)
            .values(
                spent_usd=func.least(
                    limit, func.greatest(literal(0), Budget.spent_usd - reserved + actual)
                ),
                updated_at=func.now(),
            )
        )
        return True

    async def release(self, session: AsyncSession, *, call_id: int) -> bool:
        """Give the reservation back (the provider reported no usage). False if not reserved."""
        reserved = await self._lock_reserved(session, call_id)
        if reserved is None:
            return False
        await session.execute(
            update(CallLog)
            .where(CallLog.id == call_id)
            .values(status="released", cost_usd=0, updated_at=func.now())
        )
        await session.execute(
            update(Budget)
            .where(Budget.id == 1)
            .values(
                spent_usd=func.greatest(literal(0), Budget.spent_usd - reserved),
                updated_at=func.now(),
            )
        )
        return True

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
        """Log a replayed call: cost 0, and the budget row is not touched."""
        call_id = await session.scalar(
            insert(CallLog)
            .values(
                role_id=role_id,
                purpose=purpose,
                status="replayed",
                model=model,
                request_key=request_key,
                schema_retry=schema_retry,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=0,
            )
            .returning(CallLog.id)
        )
        if call_id is None:  # pragma: no cover  (INSERT ... RETURNING always yields the id)
            msg = "call_log insert returned no id"
            raise RuntimeError(msg)
        return call_id

    async def ensure_budget(self, session: AsyncSession, *, ledger: Decimal) -> None:
        """Create the budget row from the ledger, or raise it to the ledger, never lower it.

        GREATEST(database, ledger): a recreated database cannot reset the cap, and a database
        that already holds more (reserved rows) keeps it.
        """
        statement = pg_insert(Budget).values(id=1, spent_usd=ledger)
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[Budget.id],
                set_={
                    "spent_usd": func.greatest(Budget.spent_usd, statement.excluded.spent_usd),
                    "updated_at": func.now(),
                },
            )
        )
