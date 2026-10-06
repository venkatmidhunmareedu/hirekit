"""Fake repositories wired into the app through dependency overrides."""

import pytest
from fastapi import FastAPI

from app.api.compare.router import get_compare
from app.api.resumes.router import get_uploads
from app.api.roles.router import get_criteria, get_roles
from app.core.auth import get_sessions, get_users
from tests.api.fake_compare import FakeCompare
from tests.api.fakes import FakeCriteria, FakeRoles, FakeSessions, FakeUploads, FakeUsers


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


@pytest.fixture
def roles(app: FastAPI) -> FakeRoles:
    fake = FakeRoles()
    app.dependency_overrides[get_roles] = lambda: fake
    return fake


@pytest.fixture
def criteria(app: FastAPI) -> FakeCriteria:
    fake = FakeCriteria()
    app.dependency_overrides[get_criteria] = lambda: fake
    return fake


@pytest.fixture
def uploads(app: FastAPI, roles: FakeRoles) -> FakeUploads:
    fake = FakeUploads(roles)
    app.dependency_overrides[get_uploads] = lambda: fake
    return fake


@pytest.fixture
def compare(app: FastAPI) -> FakeCompare:
    fake = FakeCompare()
    app.dependency_overrides[get_compare] = lambda: fake
    return fake
