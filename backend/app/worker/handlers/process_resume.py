"""`process_resume`: read the file, extract, anonymize, store the texts, then score.

Order (docs/design/worker-lld.md section 4.2): status `parsing`; if the anonymized text is
already stored (a retry after T3) skip to scoring; else read the file, extract and anonymize in
a thread with no transaction open, and store raw text, anonymized text, the name found and the
anonymizer version while deleting the file in one fenced transaction (T3); then the shared
scoring step ends the job. The file stays until T3, so a failed extraction can be retried.

Lock mode: every write here is `fenced()` without `exclusive`: none of them changes the role.
A name that was not found is stored as a NULL `identity_name`; the schema has no other place
for the "name not found" warning, so Reveal identity derives it from the NULL.
"""

import asyncio
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.anonymizer import Anonymized
from app.anonymizer.pipeline import InputTooLargeError
from app.anonymizer.verify import AnonymizationLeakError
from app.db.repositories.worker_writes import StoredFile
from app.gateway.text import AnonymizedText
from app.worker.context import JobContext
from app.worker.errors import ExtractionError
from app.worker.handlers.scoring import NO_CANDIDATE, ScoringDeps, score_candidate
from app.worker.loop import Handler
from app.worker.outcome import (
    ANONYMIZATION_LEAK,
    EXTRACTION_FAILED,
    INPUT_TOO_LARGE,
    NO_FILE,
    SOMETHING_WENT_WRONG,
    Failed,
    Outcome,
)
from app.worker.ports import Anonymizer, Extractor

NO_FILE_CODE = "no_file"


class ResumeWrites(Protocol):
    """The part of `app.db.repositories.worker_writes` this handler calls (Q7, Q8a, T3)."""

    async def read_file(self, session: AsyncSession, candidate_id: UUID) -> StoredFile | None: ...

    async def text_exists(self, session: AsyncSession, candidate_id: UUID) -> bool: ...

    async def set_status(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        status: str,
        failure_reason: str | None = None,
    ) -> None: ...

    async def store_texts(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        *,
        raw_text: str,
        anonymized: AnonymizedText,
        anonymizer_version: int,
        identity_name: str | None,
        status: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ResumeDeps:
    """What `process_resume` needs beside the scoring step."""

    extractor: Extractor
    anonymizer: Anonymizer
    writes: ResumeWrites


def make_process_resume(deps: ResumeDeps, scoring: ScoringDeps) -> Handler:
    async def process_resume(ctx: JobContext) -> Outcome:
        candidate_id = ctx.job.candidate_id
        if candidate_id is None:
            return Failed(NO_CANDIDATE, SOMETHING_WENT_WRONG)
        async with ctx.fenced() as session:
            await deps.writes.set_status(session, candidate_id, "parsing")
            exists = await deps.writes.text_exists(session, candidate_id)
            stored = None if exists else await deps.writes.read_file(session, candidate_id)
            if exists:
                await deps.writes.set_status(session, candidate_id, "scoring")
        if not exists:
            if stored is None:
                return Failed(NO_FILE_CODE, NO_FILE)
            failure = await _store_text(ctx, deps, candidate_id, stored)
            if failure is not None:
                return failure
        return await score_candidate(ctx, scoring, mark_done=True)

    return process_resume


async def _store_text(
    ctx: JobContext, deps: ResumeDeps, candidate_id: UUID, stored: StoredFile
) -> Failed | None:
    """Extract and anonymize with no transaction open, then T3; a Failed leaves the file."""
    await ctx.renew()
    try:
        raw = await asyncio.to_thread(deps.extractor.extract, stored.content, stored.media_type)
    except ExtractionError as error:
        return Failed(error.code, EXTRACTION_FAILED)
    async with ctx.fenced() as session:
        await deps.writes.set_status(session, candidate_id, "anonymizing")
    await ctx.renew()
    try:
        result: Anonymized = await asyncio.to_thread(deps.anonymizer.anonymize, raw)
    except InputTooLargeError as error:
        return Failed(error.code, INPUT_TOO_LARGE)
    except AnonymizationLeakError as error:
        return Failed(error.code, ANONYMIZATION_LEAK)
    async with ctx.fenced() as session:
        await deps.writes.store_texts(
            session,
            candidate_id,
            raw_text=raw,
            anonymized=result.text,
            anonymizer_version=result.report.anonymizer_version,
            identity_name=result.identity_name,
            status="scoring",
        )
    return None
