"""LLD section 8: a login flood cannot run more than four password hashes at once."""

import asyncio
import threading
from datetime import timedelta
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.sessions import SessionRepository
from app.db.repositories.users import UserRepository
from app.domain.auth.service import login
from tests.api.fakes import FakeSessions, FakeUsers


class FakeDb:
    async def commit(self) -> None:
        return None

    def begin(self) -> FakeDb:
        return self

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> None:
        return None


async def test_login_hashing_is_bounded_by_a_semaphore(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = threading.Lock()
    release = threading.Event()
    state = {"now": 0, "max": 0}

    def tracking(hashed: str, password: str) -> bool:
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        release.wait(timeout=5)
        with lock:
            state["now"] -= 1
        return True

    monkeypatch.setattr("app.domain.auth.service.verify_password", tracking)
    users = FakeUsers()
    users.add(email="a@example.com", role="recruiter")
    db = cast(AsyncSession, FakeDb())

    attempts = [
        asyncio.create_task(
            login(
                db,
                cast(UserRepository, users),
                cast(SessionRepository, FakeSessions()),
                email="a@example.com",
                password="p",
                ttl=timedelta(hours=1),
            )
        )
        for _ in range(12)
    ]
    for _ in range(200):  # yield until the hashes in flight stop growing
        await asyncio.sleep(0)
    release.set()
    await asyncio.gather(*attempts)

    assert state["max"] == 4
