"""Write the seed resumes as candidates with their file bytes (US-02-007).

Reads the files built by `scripts/build_seed_resumes.py`. Enqueues nothing: the caller
decides when processing starts.
"""

import hashlib
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.seed.data import SeedData

log = structlog.get_logger()

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


async def seed_candidates(session: AsyncSession, data: SeedData, files_dir: Path) -> int:
    """Insert a candidate and its file per resume; returns how many were created.

    The role is the one whose slug starts the resume id, found by title (roles must already
    exist). A resume is skipped when its role already has that file name or content hash.
    The caller owns the transaction.
    """
    created = 0
    for resume_id in data.resumes:
        found = [p for ext in MEDIA_TYPES if (p := files_dir / f"{resume_id}.{ext}").is_file()]
        if len(found) != 1:
            raise ValueError(
                f"{resume_id}: expected one .pdf or .docx in {files_dir}, found {len(found)}"
            )
        path = found[0]
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        role = next(r for r in data.roles if resume_id.startswith(f"{r.slug}-"))
        role_id = await session.scalar(
            text("SELECT id FROM roles WHERE title = :title"), {"title": role.title}
        )
        if role_id is None:
            raise ValueError(f"{resume_id}: role {role.title!r} is not in the database")
        exists = await session.scalar(
            text(
                "SELECT 1 FROM candidates WHERE role_id = :role "
                "AND (content_hash = :hash OR file_name = :name) LIMIT 1"
            ),
            {"role": role_id, "hash": digest, "name": path.name},
        )
        if exists is not None:
            log.info("seed_candidate_skipped", resume_id=resume_id)
            continue
        candidate_id = await session.scalar(
            text(
                "INSERT INTO candidates (role_id, file_name, content_hash) "
                "VALUES (:role, :name, :hash) RETURNING id"
            ),
            {"role": role_id, "name": path.name, "hash": digest},
        )
        await session.execute(
            text(
                "INSERT INTO resume_files (candidate_id, media_type, content) "
                "VALUES (:candidate, :media, :content)"
            ),
            {"candidate": candidate_id, "media": MEDIA_TYPES[path.suffix[1:]], "content": content},
        )
        log.info("seed_candidate_created", resume_id=resume_id)
        created += 1
    return created
