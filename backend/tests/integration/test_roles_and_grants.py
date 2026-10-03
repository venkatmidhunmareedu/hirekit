"""Migration 2: what hirekit_api and hirekit_worker may and may not do, proven by acting as them."""

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

WORKER_FORBIDDEN_COUNTS = (
    "SELECT count(*) FROM feedback",
    "SELECT count(*) FROM audit_events",
    "SELECT count(*) FROM users",
    "SELECT count(*) FROM sessions",
    "SELECT count(*) FROM assignments",
)


async def seed_as_owner(session: AsyncSession) -> None:
    """Rows the role tests act on, written by the owner before the role is assumed."""
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
    await session.execute(
        text(
            "INSERT INTO scores(candidate_id, criterion_id, criteria_version, status, model_score, "
            "quote) VALUES (:candidate, :criterion, 1, 'scored', 3, 'q')"
        ),
        IDS,
    )
    await session.execute(
        text(
            "INSERT INTO audit_events(candidate_id, actor_id, kind) "
            "VALUES (:candidate, :user, 'identity_reveal')"
        ),
        IDS,
    )


async def become(session: AsyncSession, role: str) -> None:
    await session.execute(text(f"SET LOCAL ROLE {role}"))


async def allowed(session: AsyncSession, sql: str) -> None:
    async with session.begin_nested():
        await session.execute(text(sql), IDS)


async def denied(session: AsyncSession, sql: str) -> None:
    with pytest.raises(DBAPIError, match=r"permission denied|must be owner"):
        async with session.begin_nested():
            await session.execute(text(sql), IDS)


async def test_api_role_cannot_update_the_model_columns_of_a_score_but_can_override(
    session: AsyncSession,
) -> None:
    """Tenet 3: a route bug cannot forge a score, only record a recruiter override."""
    await seed_as_owner(session)
    await become(session, "hirekit_api")

    await denied(session, "UPDATE scores SET model_score = 4")
    await denied(session, "UPDATE scores SET quote = 'x'")
    await denied(session, "UPDATE scores SET status = 'no_evidence'")
    await allowed(
        session,
        "UPDATE scores SET override_score = 4, override_note = 'a long enough note', "
        "overridden_by = :user, updated_at = now()",
    )


async def test_api_role_can_insert_audit_rows_but_never_change_or_remove_them(
    session: AsyncSession,
) -> None:
    """REQ-030, data-model open concern 16."""
    await seed_as_owner(session)
    await become(session, "hirekit_api")

    await allowed(
        session,
        "INSERT INTO audit_events(candidate_id, actor_id, kind) "
        "VALUES (:candidate, :user, 'identity_reveal')",
    )
    await denied(session, "UPDATE audit_events SET kind = 'identity_reveal'")
    await denied(session, "DELETE FROM audit_events")
    await denied(session, "TRUNCATE audit_events")


async def test_api_role_can_change_a_stage(session: AsyncSession) -> None:
    await seed_as_owner(session)
    await become(session, "hirekit_api")
    await allowed(session, "UPDATE candidates SET stage = 'screened', updated_at = now()")


async def test_worker_role_cannot_change_a_stage(session: AsyncSession) -> None:
    """Tenet 4: only the stage route (the Api role) may write a stage."""
    await seed_as_owner(session)
    await become(session, "hirekit_worker")
    await denied(session, "UPDATE candidates SET stage = 'screened'")
    await denied(session, "UPDATE candidates SET stage = 'rejected', processing_status = 'done'")


async def test_worker_role_can_update_processing_status_failure_reason_and_identity_name(
    session: AsyncSession,
) -> None:
    await seed_as_owner(session)
    await become(session, "hirekit_worker")
    await allowed(
        session,
        "UPDATE candidates SET processing_status = 'failed', failure_reason = 'no text', "
        "identity_name = 'Jane', updated_at = now()",
    )
    await denied(session, "UPDATE candidates SET file_name = 'other.pdf'")
    await denied(session, "UPDATE candidates SET content_hash = repeat('b', 64)")


async def test_worker_role_cannot_write_an_override(session: AsyncSession) -> None:
    await seed_as_owner(session)
    await become(session, "hirekit_worker")
    await denied(session, "UPDATE scores SET override_score = 4")
    await denied(session, "UPDATE scores SET overridden_by = :user")


async def test_worker_role_can_upsert_the_model_columns_of_a_score(session: AsyncSession) -> None:
    await seed_as_owner(session)
    await become(session, "hirekit_worker")
    await allowed(
        session,
        "INSERT INTO scores(candidate_id, criterion_id, criteria_version, status, model_score, "
        "quote) VALUES (:candidate, :criterion, 2, 'scored', 2, 'q2') "
        "ON CONFLICT (candidate_id, criterion_id, criteria_version) DO UPDATE SET "
        "status = EXCLUDED.status, model_score = EXCLUDED.model_score, quote = EXCLUDED.quote, "
        "flag_reason = EXCLUDED.flag_reason, updated_at = now()",
    )
    await allowed(session, "UPDATE scores SET model_score = 1, updated_at = now()")


async def test_api_role_cannot_write_the_budget_or_the_call_log(session: AsyncSession) -> None:
    """Tenet 8: only the gateway's role spends."""
    await session.execute(text("INSERT INTO budget(id) VALUES (1)"))
    await become(session, "hirekit_api")
    await allowed(session, "SELECT spent_usd FROM budget")
    await denied(session, "UPDATE budget SET spent_usd = 0")
    await denied(session, "INSERT INTO budget(id) VALUES (2)")
    await denied(
        session,
        "INSERT INTO call_log(purpose, status, model, request_key) "
        "VALUES ('scoring', 'replayed', 'm', repeat('a', 64))",
    )


async def test_worker_role_can_write_the_budget_and_the_call_log(session: AsyncSession) -> None:
    await become(session, "hirekit_worker")
    await allowed(session, "INSERT INTO budget(id) VALUES (1)")
    await allowed(session, "UPDATE budget SET spent_usd = 1, updated_at = now()")
    await allowed(
        session,
        "INSERT INTO call_log(purpose, status, model, request_key) "
        "VALUES ('scoring', 'reserved', 'm', repeat('a', 64))",
    )
    await allowed(
        session,
        "UPDATE call_log SET status = 'settled', input_tokens = 1, output_tokens = 1, "
        "updated_at = now()",
    )


@pytest.mark.parametrize("role", ["hirekit_api", "hirekit_worker"])
async def test_neither_role_can_read_the_migration_table_or_create_objects(
    session: AsyncSession, role: str
) -> None:
    await become(session, role)
    await denied(session, "SELECT version_num FROM alembic_version")
    await denied(session, "CREATE TABLE scratch (id int)")
    await denied(session, "DROP TABLE budget")


async def test_worker_role_has_no_access_to_feedback_audit_users_sessions_or_assignments(
    session: AsyncSession,
) -> None:
    await seed_as_owner(session)
    await become(session, "hirekit_worker")
    for sql in WORKER_FORBIDDEN_COUNTS:
        await denied(session, sql)


async def test_the_roles_exist_and_cannot_log_in_when_no_password_was_given(
    session: AsyncSession,
) -> None:
    rows = await session.execute(
        text(
            "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles "
            "WHERE rolname IN ('hirekit_api', 'hirekit_worker') ORDER BY rolname"
        )
    )
    assert [tuple(r) for r in rows] == [
        ("hirekit_api", False, False, False, False),
        ("hirekit_worker", False, False, False, False),
    ]
