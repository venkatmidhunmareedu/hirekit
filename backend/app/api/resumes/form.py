"""Parse the multipart body once, with Starlette's own limits, and map its failures to ours."""

from starlette.datastructures import FormData
from starlette.exceptions import HTTPException
from starlette.requests import Request

from app.core.errors import TooManyFilesError, ValidationFailedError

# Starlette raises HTTPException(400) with this prefix for the file past `max_files`.
_TOO_MANY_FILES = "Too many files"
_MAX_FIELDS = 5


async def read_form(request: Request, max_files: int = 100) -> FormData:
    """The form, holding at most `max_files + 1` files so the caller can count the excess.

    A 102nd file makes Starlette raise; that and a malformed body become our errors.
    """
    try:
        return await request.form(max_files=max_files + 1, max_fields=_MAX_FIELDS)
    except HTTPException as exc:
        if str(exc.detail).startswith(_TOO_MANY_FILES):
            raise TooManyFilesError(f"at most {max_files} files per upload") from None
        raise ValidationFailedError("the multipart body could not be read") from None
