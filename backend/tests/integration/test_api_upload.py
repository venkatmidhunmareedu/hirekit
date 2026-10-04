"""The upload route end to end against Postgres: real sessions, real transactions, real rows."""

import hashlib
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.passwords import hash_password
from app.db.repositories import worker_writes
from app.db.repositories.uploads import UploadRepository
from app.extraction.extractor import ResumeExtractor
from app.main import create_app
from tests.files import DOCX_TYPE, PDF_TYPE, docx_bytes, pdf_bytes

pytestmark = pytest.mark.integration

PASSWORD = f"pw-{uuid4().hex}"
SEED_RESUMES = Path(__file__).resolve().parents[3] / "seed" / "resumes"
Part = tuple[str, tuple[str, bytes, str]]


@dataclass
class Env:
    engine: AsyncEngine
    client: AsyncClient
    tag: str


def part(name: str, data: bytes) -> Part:
    return ("files", (name, data, "application/octet-stream"))


@pytest.fixture
async def env(engine: AsyncEngine) -> AsyncIterator[Env]:
    tag = f"it58-{uuid4().hex[:12]}"
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as setup:
        await setup.execute(
            text(
                "INSERT INTO users(name, email, role, password_hash) "
                "VALUES (:n, :e, 'recruiter', :h)"
            ),
            {"n": tag, "e": f"r-{tag}@example.com", "h": hash_password(PASSWORD)},
        )
    settings = Settings(
        _env_file=None, env="test", database_url=os.environ["DATABASE_URL"], log_format="console"
    )
    app = create_app(settings)
    try:
        async with (
            LifespanManager(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            login = await client.post(
                "/v1/auth/login", json={"email": f"r-{tag}@example.com", "password": PASSWORD}
            )
            assert login.status_code == 200, login.text
            client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            yield Env(engine, client, tag)
    finally:
        async with factory.begin() as cleanup:
            like = {"t": f"{tag}%"}
            # candidates cascade to resume_files and jobs
            await cleanup.execute(
                text(
                    "DELETE FROM candidates WHERE role_id IN "
                    "(SELECT id FROM roles WHERE title LIKE :t)"
                ),
                like,
            )
            await cleanup.execute(text("DELETE FROM roles WHERE title LIKE :t"), like)
            await cleanup.execute(text("DELETE FROM users WHERE name = :n"), {"n": tag})


async def make_role(env: Env, *, status: str = "approved", version: int = 2) -> UUID:
    async with env.engine.begin() as conn:
        row = await conn.execute(
            text(
                "INSERT INTO roles(title, job_description, status, criteria_version) "
                "VALUES (:t, 'Build.', :s, :v) RETURNING id"
            ),
            {"t": f"{env.tag} {uuid4().hex[:6]}", "s": status, "v": version},
        )
        return UUID(str(row.scalar_one()))


async def send(env: Env, role_id: UUID, parts: list[Part]) -> Response:
    return await env.client.post(f"/v1/roles/{role_id}/resumes", files=parts)


async def rows(env: Env, sql: str, role_id: UUID, **more: object) -> list[tuple[object, ...]]:
    async with env.engine.connect() as conn:
        result = await conn.execute(text(sql), {"r": role_id, **more})
        return [tuple(r) for r in result]


async def test_upload_creates_candidate_file_and_job_together(env: Env) -> None:
    role_id = await make_role(env, version=2)
    data = pdf_bytes("one")

    response = await send(env, role_id, [part("cv.pdf", data), part("cv2.docx", docx_bytes())])

    assert response.status_code == 207
    first, second = response.json()["results"]
    assert (first["status"], second["status"]) == ("accepted", "accepted")
    candidate = await rows(
        env,
        "SELECT c.file_name, c.content_hash, c.processing_status, c.duplicate_of_id, "
        "f.media_type, f.content, j.type, j.status, j.criteria_version, j.role_id "
        "FROM candidates c JOIN resume_files f ON f.candidate_id = c.id "
        "JOIN jobs j ON j.candidate_id = c.id WHERE c.role_id = :r AND c.candidate_no = :n",
        role_id,
        n=first["candidate_no"],
    )
    assert candidate == [
        (
            "cv.pdf",
            hashlib.sha256(data).hexdigest(),
            "queued",
            None,
            PDF_TYPE,
            data,
            "process_resume",
            "queued",
            2,
            role_id,
        )
    ]
    media = await rows(
        env,
        "SELECT f.media_type FROM candidates c JOIN resume_files f ON f.candidate_id = c.id "
        "WHERE c.role_id = :r ORDER BY c.candidate_no",
        role_id,
    )
    assert media == [(PDF_TYPE,), (DOCX_TYPE,)]


async def test_a_duplicate_is_flagged_in_the_same_request_and_across_requests(env: Env) -> None:
    role_id = await make_role(env)
    same = pdf_bytes("dup")

    one = (await send(env, role_id, [part("a.pdf", same), part("b.pdf", same)])).json()["results"]
    two = (await send(env, role_id, [part("c.pdf", same)])).json()["results"]

    assert [r["status"] for r in one + two] == ["accepted"] * 3
    assert [r["duplicate_of_candidate_no"] for r in one + two] == [
        None,
        one[0]["candidate_no"],
        one[0]["candidate_no"],
    ]
    stored = await rows(env, "SELECT count(*) FROM candidates WHERE role_id = :r", role_id)
    assert stored == [(3,)]


async def test_the_same_file_in_another_role_is_not_a_duplicate(env: Env) -> None:
    first, other = await make_role(env), await make_role(env)
    same = pdf_bytes("shared")

    await send(env, first, [part("a.pdf", same)])
    result = (await send(env, other, [part("a.pdf", same)])).json()["results"][0]

    assert (result["status"], result["duplicate_of_candidate_no"]) == ("accepted", None)


async def test_a_bad_file_in_the_batch_does_not_stop_the_others(env: Env) -> None:
    role_id = await make_role(env)
    parts = [
        part("a.pdf", pdf_bytes("1")),
        part("notes.txt", b"hello"),
        part("b.pdf", pdf_bytes("2")),
    ]

    results = (await send(env, role_id, parts)).json()["results"]

    assert [r["status"] for r in results] == ["accepted", "rejected", "accepted"]
    stored = await rows(env, "SELECT count(*) FROM candidates WHERE role_id = :r", role_id)
    assert stored == [(2,)]


async def test_a_draft_role_is_refused_and_no_candidate_row_exists(env: Env) -> None:
    role_id = await make_role(env, status="draft")

    response = await send(env, role_id, [part("a.pdf", pdf_bytes())])

    assert (response.status_code, response.json()["error"]["code"]) == (409, "role_not_approved")
    assert await rows(env, "SELECT count(*) FROM candidates WHERE role_id = :r", role_id) == [(0,)]


async def test_a_failure_inside_one_file_rolls_back_candidate_file_and_job(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    role_id = await make_role(env)
    real = UploadRepository.enqueue_process_resume
    calls = 0

    async def fail_second(
        self: UploadRepository, role: UUID, candidate: UUID, version: int
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            msg = "boom"
            raise RuntimeError(msg)
        await real(self, role, candidate, version)

    monkeypatch.setattr(UploadRepository, "enqueue_process_resume", fail_second)

    response = await send(
        env, role_id, [part("a.pdf", pdf_bytes("1")), part("b.pdf", pdf_bytes("2"))]
    )

    assert response.status_code == 500
    counts = await rows(
        env,
        "SELECT (SELECT count(*) FROM candidates WHERE role_id = :r), "
        "(SELECT count(*) FROM resume_files f JOIN candidates c ON c.id = f.candidate_id "
        "WHERE c.role_id = :r), (SELECT count(*) FROM jobs WHERE role_id = :r)",
        role_id,
    )
    assert counts == [(1, 1, 1)]


async def test_the_worker_reads_what_the_upload_wrote(env: Env) -> None:
    role_id = await make_role(env)
    seed = (SEED_RESUMES / "backend-01.pdf").read_bytes()
    result = (await send(env, role_id, [part("backend-01.pdf", seed)])).json()["results"][0]

    async with async_sessionmaker(env.engine)() as session:
        stored = await worker_writes.read_file(session, UUID(result["candidate_id"]))

    assert stored is not None
    assert stored.media_type == PDF_TYPE
    assert ResumeExtractor().extract(stored.content, stored.media_type).strip() != ""


async def test_100_files_in_one_request_all_land(env: Env) -> None:
    role_id = await make_role(env)

    response = await send(env, role_id, [part(f"{n}.pdf", pdf_bytes(str(n))) for n in range(100)])

    assert response.status_code == 207
    assert {r["status"] for r in response.json()["results"]} == {"accepted"}
    counts = await rows(
        env,
        "SELECT (SELECT count(*) FROM candidates WHERE role_id = :r), "
        "(SELECT count(*) FROM jobs WHERE role_id = :r AND status = 'queued')",
        role_id,
    )
    assert counts == [(100, 100)]


async def test_hirekit_api_can_insert_the_three_tables_but_not_change_the_content(
    session: AsyncSession,
) -> None:
    role, candidate = uuid4(), uuid4()
    await session.execute(
        text("INSERT INTO roles(id, title, job_description) VALUES (:r, 'it58 grants', 'x')"),
        {"r": role},
    )
    await session.execute(text("SET LOCAL ROLE hirekit_api"))

    await session.execute(
        text(
            "INSERT INTO candidates(id, role_id, file_name, content_hash) "
            "VALUES (:c, :r, 'f.pdf', repeat('a', 64))"
        ),
        {"c": candidate, "r": role},
    )
    await session.execute(
        text(
            "INSERT INTO resume_files(candidate_id, media_type, content) "
            "VALUES (:c, 'application/pdf', '\\x25504446')"
        ),
        {"c": candidate},
    )
    await session.execute(
        text(
            "INSERT INTO jobs(type, role_id, candidate_id, criteria_version) "
            "VALUES ('process_resume', :r, :c, 1)"
        ),
        {"c": candidate, "r": role},
    )

    for sql in (
        "UPDATE resume_files SET content = '\\x00'",
        "UPDATE candidates SET file_name = 'x'",
        "UPDATE candidates SET content_hash = repeat('b', 64)",
    ):
        with pytest.raises(DBAPIError, match="permission denied"):
            async with session.begin_nested():
                await session.execute(text(sql))
