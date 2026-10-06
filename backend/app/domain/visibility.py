"""Who is asking, for every query that returns candidate data (api-lld section 3)."""

import uuid
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Viewer:
    """The signed-in user as a candidate query sees them.

    A repository query for an interviewer carries the assignment predicate in SQL, so no service
    loads a row and then compares in Python (tenet 6).
    """

    user_id: uuid.UUID
    role: Literal["recruiter", "interviewer"]

    @property
    def is_recruiter(self) -> bool:
        return self.role == "recruiter"
