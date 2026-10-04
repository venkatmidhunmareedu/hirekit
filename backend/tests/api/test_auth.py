"""Sign in, sign out and the current user (AC-US-00-012-5)."""

import hashlib

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response

from app.core.config import Settings
from app.core.passwords import hash_password, verify_password
from tests.api.fakes import FakeSessions, FakeUsers

PHRASE = "correct-horse-battery"


@pytest.fixture
def recruiter(users: FakeUsers) -> str:
    users.add(email="Riya@Example.com", role="recruiter", password_hash=hash_password(PHRASE))
    return "Riya@Example.com"


async def login(client: AsyncClient, email: str, password: str) -> Response:
    return await client.post("/v1/auth/login", json={"email": email, "password": password})


def cookie_value(response: Response) -> str:
    return response.cookies["hirekit_session"]


async def test_login_sets_a_hardened_cookie_and_returns_the_csrf_token(
    client: AsyncClient, sessions: FakeSessions, recruiter: str
) -> None:
    response = await login(client, recruiter, PHRASE)

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == recruiter
    assert body["csrf_token"]
    flags = response.headers["set-cookie"].lower()
    assert "httponly" in flags
    assert "samesite=lax" in flags
    assert "max-age=43200" in flags
    assert "secure" not in flags


async def test_cookie_is_secure_and_ttl_follows_the_settings(
    app: FastAPI, settings: Settings, client: AsyncClient, sessions: FakeSessions, recruiter: str
) -> None:
    app.state.settings = settings.model_copy(
        update={"session_cookie_secure": True, "session_ttl_hours": 1}
    )

    flags = (await login(client, recruiter, PHRASE)).headers["set-cookie"].lower()

    assert "secure" in flags
    assert "max-age=3600" in flags


async def test_the_stored_session_is_the_hash_never_the_cookie_value(
    client: AsyncClient, sessions: FakeSessions, recruiter: str
) -> None:
    response = await login(client, recruiter, PHRASE)

    token = cookie_value(response)
    assert list(sessions.rows) == [hashlib.sha256(token.encode()).digest()]
    assert token.encode() not in sessions.rows[hashlib.sha256(token.encode()).digest()].token_hash


async def test_unknown_email_and_wrong_password_look_identical_and_both_verify(
    client: AsyncClient,
    sessions: FakeSessions,
    recruiter: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    real = verify_password

    def counting(hashed: str, password: str) -> bool:
        calls.append(hashed)
        return real(hashed, password)

    monkeypatch.setattr("app.domain.auth.service.verify_password", counting)

    unknown = await login(client, "nobody@example.com", PHRASE)
    wrong = await login(client, recruiter, "not-the-password")

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["code"] == "unauthenticated"
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]
    assert len(calls) == 2
    assert "set-cookie" not in unknown.headers
    assert sessions.rows == {}


async def test_email_match_ignores_case(
    client: AsyncClient, sessions: FakeSessions, recruiter: str
) -> None:
    response = await login(client, "RIYA@EXAMPLE.COM", PHRASE)

    assert response.status_code == 200


async def test_login_refuses_unknown_fields(client: AsyncClient, recruiter: str) -> None:
    response = await client.post(
        "/v1/auth/login", json={"email": recruiter, "password": PHRASE, "role": "admin"}
    )

    assert response.status_code == 422


async def test_me_without_a_session_is_401(client: AsyncClient, sessions: FakeSessions) -> None:
    response = await client.get("/v1/auth/me")

    assert response.status_code == 401


async def test_me_returns_the_user_without_the_password_hash(
    client: AsyncClient, sessions: FakeSessions, recruiter: str
) -> None:
    signed_in = await login(client, recruiter, PHRASE)

    response = await client.get(
        "/v1/auth/me", headers={"Cookie": f"hirekit_session={cookie_value(signed_in)}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "recruiter"
    assert body["csrf_token"] == signed_in.json()["csrf_token"]
    assert "password" not in response.text


async def test_logout_deletes_the_session_and_clears_the_cookie(
    client: AsyncClient, sessions: FakeSessions, recruiter: str
) -> None:
    signed_in = await login(client, recruiter, PHRASE)
    headers = {
        "Cookie": f"hirekit_session={cookie_value(signed_in)}",
        "X-CSRF-Token": signed_in.json()["csrf_token"],
    }

    response = await client.post("/v1/auth/logout", headers=headers)

    assert response.status_code == 204
    assert sessions.rows == {}
    assert "max-age=0" in response.headers["set-cookie"].lower()


async def test_logout_needs_the_csrf_token(
    client: AsyncClient, sessions: FakeSessions, recruiter: str
) -> None:
    signed_in = await login(client, recruiter, PHRASE)

    response = await client.post(
        "/v1/auth/logout", headers={"Cookie": f"hirekit_session={cookie_value(signed_in)}"}
    )

    assert response.status_code == 403
    assert len(sessions.rows) == 1


async def test_a_second_login_replaces_the_cookie_and_deletes_the_old_session(
    client: AsyncClient, sessions: FakeSessions, recruiter: str
) -> None:
    first = cookie_value(await login(client, recruiter, PHRASE))

    second = await client.post(
        "/v1/auth/login",
        json={"email": recruiter, "password": PHRASE},
        headers={"Cookie": f"hirekit_session={first}"},
    )

    assert cookie_value(second) != first
    assert list(sessions.rows) == [hashlib.sha256(cookie_value(second).encode()).digest()]
