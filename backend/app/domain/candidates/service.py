"""Resume upload: sniff each file, then store candidate, file and job in one transaction per file.

Each file commits on its own, so a bad file never stops the others and a database error rolls back
only the file it hit. The role is locked FOR SHARE per file, so a role that turns Draft mid-request
stops the remaining files (they report `role_not_approved`).
"""

import hashlib
import io
import re
import uuid
import zipfile
from dataclasses import dataclass
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.resumes.schemas import UploadFileResult, UploadResponse
from app.budget.policy import BUDGET_LIMIT_USD, model_actions_allowed
from app.core.config import Settings
from app.core.errors import BudgetReachedError, NotFoundError, RoleNotApprovedError
from app.db.repositories.roles import RoleRepository
from app.db.repositories.uploads import UploadRepository

PDF_TYPE: Final = "application/pdf"
DOCX_TYPE: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF_MAGIC: Final = b"%PDF-"
_ZIP_MAGIC: Final = b"PK\x03\x04"
_DOCX_BODY: Final = "word/document.xml"
_FILE_NAME_MAX: Final = 255
_CONTROL: Final = re.compile(r"[\x00-\x1f\x7f-\x9f]")

WRONG_TYPE: Final = "Only PDF and DOCX files are accepted."
EMPTY: Final = "The file is empty."
TOO_LARGE: Final = "The file is too large."
NOT_APPROVED: Final = "The criteria were changed; approve them again, then upload."
BUDGET_MESSAGE: Final = (
    f"The model budget of ${BUDGET_LIMIT_USD:.2f} has been reached. No new model calls can be made."
)


@dataclass(frozen=True, slots=True)
class IncomingFile:
    """One uploaded file as the router read it; `oversize` files carry no content."""

    file_name: str
    content: bytes
    oversize: bool = False


def clean_file_name(raw: str | None) -> str:
    """The base name only, without control characters, at most 255 characters."""
    base = re.split(r"[/\\]", raw or "")[-1]
    return _CONTROL.sub("", base)[:_FILE_NAME_MAX] or "resume"


def sniff_media_type(content: bytes) -> str | None:
    """PDF or DOCX from the first bytes and the zip directory; nothing is decompressed or parsed."""
    if content.startswith(_PDF_MAGIC):
        return PDF_TYPE
    if content.startswith(_ZIP_MAGIC):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                return DOCX_TYPE if _DOCX_BODY in archive.namelist() else None
        except zipfile.BadZipFile:
            return None
    return None


def _rejected(name: str, reason: str) -> UploadFileResult:
    return UploadFileResult(file_name=name, status="rejected", reason=reason)


def _not_approved(name: str) -> UploadFileResult:
    return UploadFileResult(file_name=name, status="role_not_approved", reason=NOT_APPROVED)


async def upload(
    db: AsyncSession,
    roles: RoleRepository,
    uploads: UploadRepository,
    role_id: uuid.UUID,
    files: list[IncomingFile],
    settings: Settings,
) -> UploadResponse:
    """One result per file; an unknown or Draft role or a spent budget refuses the whole upload."""
    role = await roles.get(role_id)
    if role is None:
        raise NotFoundError("role not found")
    if role.status == "draft":
        raise RoleNotApprovedError("approve the criteria first")
    allowed = model_actions_allowed(
        settings.model_mode,
        await uploads.spent_usd(),
        settings.price_input_usd_per_mtok,
        settings.price_output_usd_per_mtok,
    )
    if not allowed:
        raise BudgetReachedError(BUDGET_MESSAGE)
    results: list[UploadFileResult] = []
    approved = True
    for incoming in files:
        name = clean_file_name(incoming.file_name)
        media_type = sniff_media_type(incoming.content)
        if not approved:
            results.append(_not_approved(name))
        elif incoming.oversize:
            results.append(_rejected(name, TOO_LARGE))
        elif not incoming.content:
            results.append(_rejected(name, EMPTY))
        elif media_type is None:
            results.append(_rejected(name, WRONG_TYPE))
        else:
            stored = await _store(db, uploads, role_id, name, media_type, incoming.content)
            approved = stored is not None
            results.append(stored or _not_approved(name))
    return UploadResponse(results=results)


async def _store(
    db: AsyncSession,
    uploads: UploadRepository,
    role_id: uuid.UUID,
    name: str,
    media_type: str,
    content: bytes,
) -> UploadFileResult | None:
    """Candidate, file and job in one transaction; None when the role turned Draft."""
    digest = hashlib.sha256(content).hexdigest()
    await db.commit()  # ends the read transaction the previous step opened
    async with db.begin():
        state = await uploads.lock_role(role_id)
        if state is None:
            raise NotFoundError("role not found")
        if state.status == "draft":
            return None
        duplicate = await uploads.find_duplicate(role_id, digest)
        candidate_id, number = await uploads.insert_candidate(
            role_id, name, digest, duplicate[0] if duplicate else None
        )
        await uploads.insert_file(candidate_id, media_type, content)
        await uploads.enqueue_process_resume(role_id, candidate_id, state.criteria_version)
    return UploadFileResult(
        file_name=name,
        status="accepted",
        candidate_id=candidate_id,
        candidate_no=number,
        duplicate_of_candidate_no=duplicate[1] if duplicate else None,
    )
