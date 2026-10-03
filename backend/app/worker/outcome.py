"""How a job ends, and the plain sentences the UI shows when it fails.

Failure texts carry no ids, codes or resume text (tenet 7).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from app.budget.policy import BUDGET_LIMIT_USD

MODEL_UNAVAILABLE: Final = "The model service is unavailable. Try again later."
DATABASE_UNAVAILABLE: Final = "The service is unavailable. Try again later."
BUDGET_REACHED: Final = (
    f"The model budget of ${BUDGET_LIMIT_USD:.2f} has been reached. No new model calls can be made."
)
BUDGET_NOT_INITIALISED: Final = "The model budget has not been set up. Ask the maintainer."
RECORDING_MISSING: Final = "No recorded response exists for this request."
EXTRACTION_FAILED: Final = (
    "No text could be read from this file (a scanned image or a corrupt file). "
    "Retry, or upload a text-based copy."
)
NO_FILE: Final = "The uploaded file is no longer stored. Upload it again."
INPUT_TOO_LARGE: Final = "This file is too long to process."
ANONYMIZATION_LEAK: Final = (
    "This resume could not be made anonymous, so it was not sent to the model."
)
SCORING_FAILED: Final = "Scoring failed. Try again, or contact the maintainer."
SOMETHING_WENT_WRONG: Final = "Something went wrong. Try again."


@dataclass(frozen=True, slots=True)
class Succeeded:
    """The result was written inside the fenced transaction; the job is done."""


@dataclass(frozen=True, slots=True)
class Retry:
    """Put the job back to queued at `run_after`; `code` becomes `jobs.last_error`."""

    run_after: datetime
    code: str


@dataclass(frozen=True, slots=True)
class Failed:
    """Dead-letter the job; `reason` is the plain sentence for the candidate."""

    code: str
    reason: str


@dataclass(frozen=True, slots=True)
class Stale:
    """The criteria or the role changed since the job was enqueued; nothing was written."""


Outcome = Succeeded | Retry | Failed | Stale
