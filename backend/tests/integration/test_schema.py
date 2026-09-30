"""The migrated database has the designed tables and refuses the rows the design forbids."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

IDS = {
    "user": "00000000-0000-0000-0000-000000000001",
    "role": "10000000-0000-0000-0000-000000000001",
    "criterion": "20000000-0000-0000-0000-000000000001",
    "candidate": "30000000-0000-0000-0000-000000000001",
}


async def seed(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO users(id, name, email, role, password_hash) "
            "VALUES (:user, 'R', 'r@x.io', 'recruiter', 'h')"
        ),
        IDS,
    )
    await session.execute(
        text("INSERT INTO roles(id, title, job_description) VALUES (:role, 'T', 'JD')"), IDS
    )
    await session.execute(
        text(
            "INSERT INTO criteria(id, role_id, name, kind, weight, position) "
            "VALUES (:criterion, :role, 'C1', 'must_have', 1, 1)"
        ),
        IDS,
    )
    await session.execute(
        text(
            "INSERT INTO candidates(id, role_id, file_name, content_hash) "
            "VALUES (:candidate, :role, 'f.pdf', repeat('a', 64))"
        ),
        IDS,
    )


async def reveal_identity(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO audit_events(candidate_id, actor_id, kind) "
            "VALUES (:candidate, :user, 'identity_reveal')"
        ),
        IDS,
    )


async def refused(session: AsyncSession, sql: str) -> str:
    """Run `sql` in a savepoint and return the database's complaint."""
    with pytest.raises(DBAPIError) as caught:
        async with session.begin_nested():
            await session.execute(text(sql), IDS)
    return str(caught.value)


async def test_all_eighteen_tables_exist(session: AsyncSession) -> None:
    count = await session.scalar(
        text(
            "SELECT count(*) FROM pg_tables WHERE schemaname = current_schema() "
            "AND tablename <> 'alembic_version'"
        )
    )
    assert count == 18


async def test_scored_row_without_a_quote_is_refused(session: AsyncSession) -> None:
    """Tenet 3: a score exists only with its quote."""
    await seed(session)
    error = await refused(
        session,
        "INSERT INTO scores(candidate_id, criterion_id, criteria_version, status, model_score) "
        "VALUES (:candidate, :criterion, 1, 'scored', 3)",
    )
    assert "chk_scores_status_shape" in error


async def test_audit_rows_cannot_be_updated(session: AsyncSession) -> None:
    """REQ-030: the audit history is append-only."""
    await seed(session)
    await reveal_identity(session)
    error = await refused(session, "UPDATE audit_events SET kind = 'identity_reveal'")
    assert "cannot be updated" in error


async def test_budget_cannot_pass_eight_dollars(session: AsyncSession) -> None:
    """Tenet 8 backstop: even an UPDATE that skipped the reserve predicate is refused."""
    await session.execute(text("INSERT INTO budget(id) VALUES (1)"))
    error = await refused(session, "UPDATE budget SET spent_usd = 8.000001")
    assert "chk_budget_spent_cap" in error


async def test_second_open_job_for_a_candidate_is_refused(session: AsyncSession) -> None:
    await seed(session)
    job = (
        "INSERT INTO jobs(type, role_id, candidate_id, criteria_version) "
        "VALUES ('process_resume', :role, :candidate, 1)"
    )
    await session.execute(text(job), IDS)
    assert "uq_jobs_open_candidate" in await refused(session, job)


async def test_deleting_a_candidate_with_history_is_refused(session: AsyncSession) -> None:
    await seed(session)
    await reveal_identity(session)
    error = await refused(session, "DELETE FROM candidates WHERE id = :candidate")
    assert "audit_events_candidate_id_fkey" in error
