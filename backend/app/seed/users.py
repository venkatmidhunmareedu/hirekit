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
from app.db.repositories.sessions import SessionRepository

MIN_PASSWORD_LENGTH = 16
SAFE_ENVIRONMENTS = ("development", "test")

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


class SeedError(Exception):
    """A refusal the command reports and exits on; the message never carries a password."""


def check_environment(
    env_name: str | None, *, allow_production: bool, environ: Mapping[str, str]
) -> None:
    """Refuse unless ENV is development or test (unset counts as neither).

    `--allow-production` lifts that, but only when both passwords are supplied: nothing is
    generated in that mode.
    """
    if env_name in SAFE_ENVIRONMENTS:
        return
    if not allow_production:
        msg = (
            f"refusing to seed users: ENV is {env_name or 'unset'}, not development or test; "
            "pass --allow-production (with both SEED_PASSWORD_* set) to override"
        )
        raise SeedError(msg)
    for user in USERS:
        if not environ.get(user.env_var):
            msg = f"--allow-production requires {user.env_var} to be set"
            raise SeedError(msg)


def decide(exists: bool, reset: bool) -> Status:
    """created when absent; an existing user is kept unless a reset was asked for."""
    if not exists:
        return "created"
    return "reset" if reset else "kept"


def choose_password(
    user: SeedUser, env: Mapping[str, str], *, allow_generate: bool = True
) -> tuple[str, bool]:
    """The password and whether it was generated (an empty variable counts as unset).

    A chosen value must be at least 16 characters; the error names the variable, never the value.
    """
    given = env.get(user.env_var)
    if given:
        if len(given) < MIN_PASSWORD_LENGTH:
            msg = f"{user.env_var} must be at least {MIN_PASSWORD_LENGTH} characters"
            raise SeedError(msg)
        return given, False
    if not allow_generate:
        msg = f"{user.env_var} must be set: a password is generated only on an interactive terminal"
        raise SeedError(msg)
    return secrets.token_urlsafe(16), True


def format_outcome(outcome: UserOutcome) -> str:
    line = f"user {outcome.status}: {outcome.email} ({outcome.role})"
    if outcome.generated_password is not None:
        line += f" password: {outcome.generated_password}"
    return line


async def seed_users(
    session: AsyncSession,
    env: Mapping[str, str],
    *,
    reset: bool = False,
    allow_generate: bool = True,
) -> list[UserOutcome]:
    """Create each missing user (matched by lower(email)); the caller owns the transaction.

    A reset also deletes the user's sessions, in that transaction.
    """
    outcomes: list[UserOutcome] = []
    for user in USERS:
        exists = (
            await session.scalar(
                text("SELECT 1 FROM users WHERE lower(email) = lower(:email)"),
                {"email": user.email},
            )
            is not None
        )
        status = decide(exists, reset)
        generated: str | None = None
        if status != "kept":
            password, was_generated = choose_password(user, env, allow_generate=allow_generate)
            digest = hash_password(password)
            if status == "created":
                inserted = await session.scalar(
                    text(
                        "INSERT INTO users (name, email, role, password_hash) "
                        "VALUES (:name, :email, CAST(:role AS user_role), :hash) "
                        "ON CONFLICT DO NOTHING RETURNING id"
                    ),
                    {"name": user.name, "email": user.email, "role": user.role, "hash": digest},
                )
                if inserted is None:  # another run created it first: keep theirs
                    status = "kept"
            else:
                user_id = await session.scalar(
                    text(
                        "UPDATE users SET password_hash = :hash "
                        "WHERE lower(email) = lower(:email) RETURNING id"
                    ),
                    {"hash": digest, "email": user.email},
                )
                await SessionRepository(session).delete_for_user(user_id)
            if status != "kept":
                generated = password if was_generated else None
        outcomes.append(UserOutcome(user.email, user.role, status, generated))
    return outcomes
