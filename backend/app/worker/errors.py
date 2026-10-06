"""Errors the Worker's own collaborators raise.

They never reach HTTP; `status_code` only satisfies the `DomainError` base. Messages
must not carry resume text (tenet 7).
"""

from app.core.errors import DomainError


class ExtractionError(DomainError):
    """No text could be read from the file: a scanned image, a corrupt file or empty text."""

    status_code = 422
    code = "extraction_failed"


class SchemaError(DomainError):
    """A model reply deviated from the strict schema (REQ-023)."""

    status_code = 502
    code = "schema_error"


class LeaseLostError(DomainError):
    """The job's lease is gone (expired and re-claimed, or cancelled): write nothing."""

    status_code = 409
    code = "lease_lost"
