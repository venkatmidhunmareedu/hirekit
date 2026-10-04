"""Auth errors map to the envelope; session settings default per environment."""

from fastapi import FastAPI
from httpx import AsyncClient

from app.core.config import Settings
from app.core.errors import CsrfError, ForbiddenError, UnauthenticatedError

DB = "postgresql+asyncpg://postgres:postgres@localhost:5432/test"


async def test_auth_errors_have_their_status_and_code(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/e/{kind}")
    async def raise_it(kind: str) -> None:
        raise {"u": UnauthenticatedError, "c": CsrfError, "f": ForbiddenError}[kind]("x")

    seen = {k: await client.get(f"/e/{k}") for k in "ucf"}

    assert [(r.status_code, r.json()["error"]["code"]) for r in seen.values()] == [
        (401, "unauthenticated"),
        (403, "csrf_failed"),
        (403, "forbidden"),
    ]


def test_session_defaults_are_insecure_cookie_and_12_hours_outside_production() -> None:
    settings = Settings(_env_file=None, env="development", database_url=DB)

    assert settings.cookie_secure is False
    assert settings.session_ttl_hours == 12


def test_session_cookie_is_secure_by_default_in_production() -> None:
    settings = Settings(_env_file=None, env="production", database_url=DB)

    assert settings.cookie_secure is True


def test_session_cookie_secure_can_be_set_explicitly() -> None:
    settings = Settings(
        _env_file=None, env="production", database_url=DB, session_cookie_secure=False
    )

    assert settings.cookie_secure is False
