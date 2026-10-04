"""In-memory stand-ins for the user and session repositories."""

import uuid
from datetime import UTC, datetime, timedelta

from app.db.models import User, UserSession
from app.db.repositories.sessions import hash_token


class FakeUsers:
    def __init__(self) -> None:
        self.rows: list[User] = []

    def add(
        self, *, email: str, role: str, password_hash: str | None = None, name: str = "Riya"
    ) -> User:
        user = User(
            id=uuid.uuid4(),
            name=name,
            email=email,
            role=role,
            password_hash=password_hash or "unused",
        )
        self.rows.append(user)
        return user

    async def by_email(self, email: str) -> User | None:
        return next((u for u in self.rows if u.email.lower() == email.lower()), None)

    async def by_id(self, user_id: uuid.UUID) -> User | None:
        return next((u for u in self.rows if u.id == user_id), None)


class FakeSessions:
    def __init__(self) -> None:
        self.rows: dict[bytes, UserSession] = {}

    async def create(
        self, token: str, user_id: uuid.UUID, csrf_token: str, expires_at: datetime
    ) -> None:
        self.rows[hash_token(token)] = UserSession(
            token_hash=hash_token(token),
            user_id=user_id,
            csrf_token=csrf_token,
            expires_at=expires_at,
        )

    async def read_valid(self, token: str) -> UserSession | None:
        row = self.rows.get(hash_token(token))
        if row is None or row.expires_at <= datetime.now(UTC):
            return None
        return row

    async def delete(self, token: str) -> None:
        self.rows.pop(hash_token(token), None)

    async def sign_in(self, user: User, *, ttl: timedelta = timedelta(hours=1)) -> SignedIn:
        token = f"tok-{uuid.uuid4().hex}"
        csrf = f"csrf-{uuid.uuid4().hex}"
        await self.create(token, user.id, csrf, datetime.now(UTC) + ttl)
        return SignedIn(token=token, csrf=csrf)


class SignedIn:
    def __init__(self, *, token: str, csrf: str) -> None:
        self.token = token
        self.csrf = csrf

    @property
    def cookie(self) -> dict[str, str]:
        return {"Cookie": f"hirekit_session={self.token}"}

    @property
    def unsafe_headers(self) -> dict[str, str]:
        return {**self.cookie, "X-CSRF-Token": self.csrf}
