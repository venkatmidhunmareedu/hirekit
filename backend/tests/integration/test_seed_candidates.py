"""`seed_candidates` stores each built resume file for its role, and twice changes nothing."""

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest
from scripts.build_seed_resumes import DOCX_MEDIA_TYPE, build
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.seed.candidates import seed_candidates
from app.seed.data import SeedCriterion, SeedData, SeedRole
from app.seed.load import seed_roles

pytestmark = pytest.mark.integration

LEVELS = ("none", "basic", "some", "good", "expert")
CRITERIA = (SeedCriterion("Python", "must_have", Decimal(3), LEVELS),)
ROLES = (
    SeedRole("alpha", "Seed Alpha Role", "Build alpha.", CRITERIA),
    SeedRole("beta", "Seed Beta Role", "Build beta.", CRITERIA),
)
# (id, kind): two roles, both file kinds each.
FILES = (("alpha-01", "pdf"), ("alpha-02", "docx"), ("beta-01", "pdf"), ("beta-02", "docx"))
DATA = SeedData(
    roles=ROLES,
    resumes={f"{rid}": f"Resume {rid}\nPython for {rid}." for rid, _ in FILES},
    labels={},
    pairs=(),
)


@pytest.fixture
def files_dir(tmp_path: Path) -> Path:
    for rid, kind in FILES:
        (tmp_path / f"{rid}.{kind}").write_bytes(build(DATA.resumes[rid], "single", kind))
    return tmp_path


async def _seed(session: AsyncSession, files_dir: Path) -> int:
    await seed_roles(session, ROLES)
    return await seed_candidates(session, DATA, files_dir)


async def test_each_resume_is_stored_for_its_role(session: AsyncSession, files_dir: Path) -> None:
    created = await _seed(session, files_dir)

    assert created == 4
    rows = (
        await session.execute(
            text(
                "SELECT r.title, c.file_name, c.content_hash, f.media_type, f.content, "
                "c.stage::text, c.processing_status::text "
                "FROM candidates c JOIN roles r ON r.id = c.role_id "
                "JOIN resume_files f ON f.candidate_id = c.id "
                "WHERE r.title LIKE 'Seed % Role' ORDER BY c.file_name"
            )
        )
    ).all()
    assert [(r[0], r[1]) for r in rows] == [
        ("Seed Alpha Role", "alpha-01.pdf"),
        ("Seed Alpha Role", "alpha-02.docx"),
        ("Seed Beta Role", "beta-01.pdf"),
        ("Seed Beta Role", "beta-02.docx"),
    ]
    assert [r[3] for r in rows] == ["application/pdf", DOCX_MEDIA_TYPE] * 2
    for row in rows:
        assert row[2] == hashlib.sha256(bytes(row[4])).hexdigest()
        assert (row[5], row[6]) == ("new", "queued")


async def test_no_jobs_are_enqueued(session: AsyncSession, files_dir: Path) -> None:
    before = await session.scalar(text("SELECT count(*) FROM jobs"))

    await _seed(session, files_dir)

    assert await session.scalar(text("SELECT count(*) FROM jobs")) == before


async def test_a_second_run_changes_nothing(session: AsyncSession, files_dir: Path) -> None:
    await _seed(session, files_dir)

    assert await seed_candidates(session, DATA, files_dir) == 0
    count = await session.scalar(
        text(
            "SELECT count(*) FROM candidates c JOIN roles r ON r.id = c.role_id "
            "WHERE r.title LIKE 'Seed % Role'"
        )
    )
    assert count == 4


async def test_a_missing_or_doubled_file_is_an_error(
    session: AsyncSession, files_dir: Path
) -> None:
    await seed_roles(session, ROLES)
    (files_dir / "alpha-01.pdf").rename(files_dir / "alpha-01.docx")
    (files_dir / "alpha-01.pdf").write_bytes(b"%PDF")
    with pytest.raises(ValueError, match="alpha-01"):
        await seed_candidates(session, DATA, files_dir)

    (files_dir / "alpha-01.pdf").unlink()
    (files_dir / "alpha-01.docx").unlink()
    with pytest.raises(ValueError, match="alpha-01"):
        await seed_candidates(session, DATA, files_dir)
