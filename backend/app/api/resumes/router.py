"""POST /v1/roles/{id}/resumes: upload up to 100 PDF or DOCX files.

The handler takes the raw `Request`, not `File(...)` parameters: FastAPI would parse the body
before the auth and CSRF dependencies ran. Size caps are checked before the body is read.
"""

import uuid
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.api.resumes.form import read_form
from app.api.resumes.schemas import UploadResponse
from app.api.roles.router import Roles
from app.core.auth import RecruiterUser
from app.core.config import Settings
from app.core.errors import (
    ErrorEnvelope,
    PayloadTooLargeError,
    TooManyFilesError,
    ValidationFailedError,
)
from app.db.repositories.uploads import UploadRepository
from app.db.session import get_session
from app.domain.candidates import service
from app.domain.candidates.service import IncomingFile

router = APIRouter(prefix="/v1/roles", tags=["resumes"])

_CHUNK: Final = 64 * 1024
# The spec's UploadRequest, restated because the handler takes `Request` and FastAPI sees no body.
_REQUEST_BODY: Final = {
    "required": True,
    "content": {
        "multipart/form-data": {
            "schema": {
                "type": "object",
                "required": ["files"],
                "properties": {
                    "files": {
                        "type": "array",
                        "maxItems": 100,
                        "items": {"type": "string", "format": "binary"},
                    }
                },
            }
        }
    },
}
_ERRORS: Final[dict[int | str, dict[str, type[ErrorEnvelope]]]] = {
    code: {"model": ErrorEnvelope} for code in (401, 403, 404, 409, 413, 422)
}


def get_uploads(session: Annotated[AsyncSession, Depends(get_session)]) -> UploadRepository:
    """The upload repository for this request."""
    return UploadRepository(session)


Db = Annotated[AsyncSession, Depends(get_session)]
Uploads = Annotated[UploadRepository, Depends(get_uploads)]


async def _read_file(file: UploadFile, limit: int) -> IncomingFile:
    """Stream the file in chunks; one byte past `limit` stops the read and marks it oversize."""
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(_CHUNK):
        size += len(chunk)
        if size > limit:
            return IncomingFile(file.filename or "", b"", oversize=True)
        chunks.append(chunk)
    return IncomingFile(file.filename or "", b"".join(chunks))


@router.post(
    "/{role_id}/resumes",
    status_code=207,
    response_model=UploadResponse,
    responses=_ERRORS,
    openapi_extra={"requestBody": _REQUEST_BODY},
)
async def upload_resumes(
    role_id: uuid.UUID,
    _: RecruiterUser,
    request: Request,
    db: Db,
    roles: Roles,
    uploads: Uploads,
    response: Response,
) -> UploadResponse:
    """Accept or reject each file on its own; a Draft role or a spent budget refuses all."""
    settings: Settings = request.app.state.settings
    response.headers["Cache-Control"] = "no-store"
    declared = request.headers.get("content-length", "")
    if declared.isdecimal() and int(declared) > settings.max_request_bytes:
        raise PayloadTooLargeError("request too large")
    form = await read_form(request, settings.max_files_per_upload)
    try:
        parts = form.getlist("files")
        if len(parts) > settings.max_files_per_upload:
            raise TooManyFilesError(f"at most {settings.max_files_per_upload} files per upload")
        if not parts or not all(isinstance(p, UploadFile) for p in parts):
            raise ValidationFailedError(
                "request failed validation",
                details={
                    "errors": [{"loc": ["body", "files"], "msg": "send files", "type": "missing"}]
                },
            )
        files = [
            await _read_file(p, settings.max_upload_bytes)
            for p in parts
            if isinstance(p, UploadFile)
        ]
    finally:
        await form.close()
    return await service.upload(db, roles, uploads, role_id, files, settings)
