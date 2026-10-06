"""Who is looking: the session user as a repository query sees them (tenet 6)."""

from dataclasses import dataclass
from uuid import UUID

from app.db.models import User


@dataclass(frozen=True, slots=True)
class Viewer:
    """The caller. An interviewer's queries carry the assignment predicate in SQL."""

    user_id: UUID
    role: str

    @classmethod
    def of(cls, user: User) -> Viewer:
        return cls(user.id, user.role)

    @property
    def is_interviewer(self) -> bool:
        return self.role == "interviewer"
