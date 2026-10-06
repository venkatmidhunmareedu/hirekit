"""Fake repositories wired into the app through dependency overrides."""

import pytest
from fastapi import FastAPI

from app.api.candidates.assignments import get_assignments
from app.api.candidates.decisions import get_audit, get_decisions
from app.api.compare.router import get_compare
from app.api.cost.router import get_costs
from app.api.feedback.router import get_feedback
from app.api.jobs.deps import get_jobs
from app.api.kit.router import get_kits
from app.api.resumes.router import get_uploads
from app.api.roles.router import get_criteria, get_roles
from app.api.scoring.router import get_scoring_jobs
from app.core.auth import get_sessions, get_users
from tests.api.fake_assignments import FakeAssignments
from tests.api.fake_compare import FakeCompare
from tests.api.fake_decisions import FakeAudit, FakeDecisions
from tests.api.fakes import (
    FakeCost,
    FakeCriteria,
    FakeFeedback,
    FakeJobs,
    FakeKit,
    FakeRoles,
    FakeScoringJobs,
    FakeSessions,
    FakeUploads,
    FakeUsers,
)


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
def assignments(app: FastAPI, users: FakeUsers) -> FakeAssignments:
    fake = FakeAssignments(users)
    app.dependency_overrides[get_assignments] = lambda: fake
    return fake


@pytest.fixture
def uploads(app: FastAPI, roles: FakeRoles) -> FakeUploads:
    fake = FakeUploads(roles)
    app.dependency_overrides[get_uploads] = lambda: fake
    return fake


@pytest.fixture
def feedback(app: FastAPI) -> FakeFeedback:
    fake = FakeFeedback()
    app.dependency_overrides[get_feedback] = lambda: fake
    return fake


@pytest.fixture
def kit(app: FastAPI, roles: FakeRoles) -> FakeKit:
    fake = FakeKit(roles)
    app.dependency_overrides[get_kits] = lambda: fake
    return fake


@pytest.fixture
def scoring_jobs(app: FastAPI, roles: FakeRoles) -> FakeScoringJobs:
    fake = FakeScoringJobs(roles)
    app.dependency_overrides[get_scoring_jobs] = lambda: fake
    return fake


@pytest.fixture
def decisions(app: FastAPI) -> FakeDecisions:
    fake = FakeDecisions()
    app.dependency_overrides[get_decisions] = lambda: fake
    return fake


@pytest.fixture
def costs(app: FastAPI) -> FakeCost:
    fake = FakeCost()
    app.dependency_overrides[get_costs] = lambda: fake
    return fake


@pytest.fixture
def audit(app: FastAPI) -> FakeAudit:
    fake = FakeAudit()
    app.dependency_overrides[get_audit] = lambda: fake
    return fake


@pytest.fixture
def compare(app: FastAPI) -> FakeCompare:
    fake = FakeCompare()
    app.dependency_overrides[get_compare] = lambda: fake
    return fake


@pytest.fixture
def jobs(app: FastAPI) -> FakeJobs:
    fake = FakeJobs()
    app.dependency_overrides[get_jobs] = lambda: fake
    return fake
