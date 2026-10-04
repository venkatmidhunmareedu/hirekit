"""Write the sign-in users: one recruiter and one interviewer (US-02-007, ADR-0005).

Passwords are never committed and never read by the Api. Each is generated here, or taken from
`SEED_PASSWORD_RECRUITER` / `SEED_PASSWORD_INTERVIEWER` when set (read only in this module).
A generated password is returned once for the command to print; only its hash is stored.
"""

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.passwords import hash_password

Status = Literal["created", "kept", "reset"]


@dataclass(frozen=True, slots=True)
class SeedUser:
    name: str
    email: str
    role: Literal["recruiter", "interviewer"]
    env_var: str


USERS = (
    SeedUser("Seed Recruiter", "recruiter@hirekit.local", "recruiter", "SEED_PASSWORD_RECRUITER"),
    SeedUser(
        "Seed Interviewer", "interviewer@hirekit.local", "interviewer", "SEED_PASSWORD_INTERVIEWER"
    ),
)


@dataclass(frozen=True, slots=True)
class UserOutcome:
    email: str
    role: str
    status: Status
    generated_password: str | None  # set only when the command made the password up


def decide(exists: bool, reset: bool) -> Status:
    """created when absent; an existing user is kept unless a reset was asked for."""
    if not exists:
        return "created"
    return "reset" if reset else "kept"


def choose_password(user: SeedUser, env: Mapping[str, str]) -> tuple[str, bool]:
    """The password and whether it was generated (an empty variable counts as unset)."""
    given = env.get(user.env_var)
    if given:
        return given, False
    return secrets.token_urlsafe(16), True


def format_outcome(outcome: UserOutcome) -> str:
    line = f"user {outcome.status}: {outcome.email} ({outcome.role})"
    if outcome.generated_password is not None:
        line += f" password: {outcome.generated_password}"
    return line


async def seed_users(
    session: AsyncSession, env: Mapping[str, str], *, reset: bool = False
) -> list[UserOutcome]:
    """Create each missing user (matched by lower(email)); the caller owns the transaction."""
    outcomes: list[UserOutcome] = []
    for user in USERS:
        exists = (
            await session.scalar(
                text("SELECT 1 FROM users WHERE lower(email) = :email"), {"email": user.email}
            )
            is not None
        )
        status = decide(exists, reset)
        generated: str | None = None
        if status != "kept":
            password, was_generated = choose_password(user, env)
            generated = password if was_generated else None
            digest = hash_password(password)
            if status == "created":
                await session.execute(
                    text(
                        "INSERT INTO users (name, email, role, password_hash) "
                        "VALUES (:name, :email, CAST(:role AS user_role), :hash)"
                    ),
                    {"name": user.name, "email": user.email, "role": user.role, "hash": digest},
                )
            else:
                await session.execute(
                    text("UPDATE users SET password_hash = :hash WHERE lower(email) = :email"),
                    {"hash": digest, "email": user.email},
                )
        outcomes.append(UserOutcome(user.email, user.role, status, generated))
    return outcomes
