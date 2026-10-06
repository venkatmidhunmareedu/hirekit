"""Fake repositories wired into the app through dependency overrides."""

import pytest
from fastapi import FastAPI

from app.core.auth import get_sessions, get_users
from tests.api.fakes import FakeSessions, FakeUsers


@pytest.fixture
def users(app: FastAPI) -> FakeUsers:
    fake = FakeUsers()
    app.dependency_overrides[get_users] = lambda: fake
    return fake


@pytest.fixture
def sessions(app: FastAPI) -> FakeSessions:
    fake = FakeSessions()
    app.dependency_overrides[get_sessions] = lambda: fake
    return fake
