"""The session cookie and CSRF checks every protected route inherits."""

from datetime import timedelta

from fastapi import FastAPI
from httpx import AsyncClient

from tests.api.fakes import FakeSessions, FakeUsers
from tests.api.test_permission_matrix import register_test_routes


async def test_no_cookie_is_401(app: FastAPI, client: AsyncClient, users: FakeUsers) -> None:
    register_test_routes(app)

    response = await client.get("/t/anyone")

    assert (response.status_code, response.json()["error"]["code"]) == (401, "unauthenticated")


async def test_unknown_token_is_401(
    app: FastAPI, client: AsyncClient, users: FakeUsers, sessions: FakeSessions
) -> None:
    register_test_routes(app)

    response = await client.get("/t/anyone", headers={"Cookie": "hirekit_session=nope"})

    assert response.status_code == 401


async def test_expired_session_is_401(
    app: FastAPI, client: AsyncClient, users: FakeUsers, sessions: FakeSessions
) -> None:
    register_test_routes(app)
    signed_in = await sessions.sign_in(
        users.add(email="a@example.com", role="recruiter"), ttl=timedelta(seconds=-1)
    )

    response = await client.get("/t/anyone", headers=signed_in.cookie)

    assert response.status_code == 401


async def test_get_needs_no_csrf_token(
    app: FastAPI, client: AsyncClient, users: FakeUsers, sessions: FakeSessions
) -> None:
    register_test_routes(app)
    signed_in = await sessions.sign_in(users.add(email="a@example.com", role="recruiter"))

    response = await client.get("/t/recruiter", headers=signed_in.cookie)

    assert response.status_code == 200


async def test_post_without_csrf_token_is_403_csrf_failed(
    app: FastAPI, client: AsyncClient, users: FakeUsers, sessions: FakeSessions
) -> None:
    register_test_routes(app)
    signed_in = await sessions.sign_in(users.add(email="a@example.com", role="recruiter"))

    response = await client.post("/t/recruiter", headers=signed_in.cookie)

    assert (response.status_code, response.json()["error"]["code"]) == (403, "csrf_failed")


async def test_post_with_wrong_csrf_token_is_403_csrf_failed(
    app: FastAPI, client: AsyncClient, users: FakeUsers, sessions: FakeSessions
) -> None:
    register_test_routes(app)
    signed_in = await sessions.sign_in(users.add(email="a@example.com", role="recruiter"))

    response = await client.post(
        "/t/recruiter", headers={**signed_in.cookie, "X-CSRF-Token": "wrong"}
    )

    assert (response.status_code, response.json()["error"]["code"]) == (403, "csrf_failed")


async def test_csrf_failure_is_checked_before_the_role(
    app: FastAPI, client: AsyncClient, users: FakeUsers, sessions: FakeSessions
) -> None:
    register_test_routes(app)
    signed_in = await sessions.sign_in(users.add(email="i@example.com", role="interviewer"))

    response = await client.post("/t/recruiter", headers=signed_in.cookie)

    assert response.json()["error"]["code"] == "csrf_failed"
