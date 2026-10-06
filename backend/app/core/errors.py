"""Domain errors and their single mapping to the JSON error envelope.

Services raise `DomainError` subclasses. Routers never build an error body;
`register_exception_handlers` turns every failure into the same shape.
"""

from collections.abc import Mapping

import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger()


class DomainError(Exception):
    """Base class for errors the API maps to a status code."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, message: str, *, details: Mapping[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, object] = dict(details or {})


class UnauthenticatedError(DomainError):
    """No valid session, or the sign-in credentials were wrong."""

    status_code = 401
    code = "unauthenticated"


class CsrfError(DomainError):
    """A state-changing request without the session's CSRF token."""

    status_code = 403
    code = "csrf_failed"


class ForbiddenError(DomainError):
    """Signed in, but the role does not allow the route."""

    status_code = 403
    code = "forbidden"


class NotFoundError(DomainError):
    """The requested resource does not exist or is not visible to the caller."""

    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    """The request conflicts with the current state (duplicate, stale version)."""

    status_code = 409
    code = "conflict"


class ValidationFailedError(DomainError):
    """A request the shape check passed but the stored state refuses (same envelope as a 422)."""

    status_code = 422
    code = "validation_error"


class CriteriaChangedError(ConflictError):
    """The criteria changed since the caller loaded them; details carry current_version."""

    code = "criteria_changed"


class RoleNotApprovedError(ConflictError):
    """The role is still Draft; the criteria must be approved first."""

    code = "role_not_approved"


class BudgetReachedError(ConflictError):
    """Live mode and the USD 8 model budget has no room for another model action."""

    code = "budget_reached"


class JobAlreadyOpenError(ConflictError):
    """A scoring, proposal or kit job for the same target is already queued or running."""

    code = "job_already_open"


class TooManyFilesError(DomainError):
    """More files in one upload than the limit allows."""

    status_code = 422
    code = "too_many_files"


class PayloadTooLargeError(DomainError):
    """The request body is over the size cap."""

    status_code = 413
    code = "payload_too_large"


class NoCriteriaError(DomainError):
    """The role has no live criteria to approve."""

    status_code = 422
    code = "no_criteria"


class IncompleteRubricError(DomainError):
    """A live criterion lacks a descriptor for one of the levels 0 to 4."""

    status_code = 422
    code = "incomplete_rubric"


class ServiceUnavailableError(DomainError):
    """A dependency the request needs is not reachable."""

    status_code = 503
    code = "service_unavailable"


class ErrorBody(BaseModel):
    """The inner error object."""

    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    """Every non-2xx response has this shape."""

    error: ErrorBody


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Mapping[str, object] | None = None,
) -> JSONResponse:
    """Build the envelope with the current request id attached."""
    request_id = structlog.contextvars.get_contextvars().get("request_id")
    body = ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=message,
            details=dict(details or {}),
            request_id=request_id if isinstance(request_id, str) else None,
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """Install the one mapping from exceptions to the envelope."""

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = jsonable_encoder(exc.errors(), exclude={"input", "url"})
        return error_response(
            422, "validation_error", "request failed validation", {"errors": errors}
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return error_response(exc.status_code, "http_error", str(exc.detail))


def unhandled_response(exc: Exception) -> JSONResponse:
    """Log the traceback once and hide it from the client.

    Called from `RequestIdMiddleware`, not registered on the app: Starlette's
    own server-error layer sits outside every middleware, so a handler there
    would answer after the request id and its log context are gone.
    """
    log.exception("unhandled error", error_type=type(exc).__name__)
    return error_response(500, "internal", "internal error")
