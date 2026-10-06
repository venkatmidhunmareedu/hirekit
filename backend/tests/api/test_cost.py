"""GET /v1/cost-log against a fake call log (HK-65)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.errors import ValidationFailedError
from app.domain.cost.service import decode_cursor, encode_cursor
from tests.api.fakes import FakeCost, FakeSessions, FakeUsers

T0 = datetime(2026, 9, 30, 9, 0, tzinfo=UTC)


@pytest.fixture
async def recruiter(users: FakeUsers, sessions: FakeSessions) -> dict[str, str]:
    return (await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))).cookie


async def test_a_recruiter_sees_the_budget_and_the_calls_newest_first(
    client: AsyncClient, costs: FakeCost, recruiter: dict[str, str]
) -> None:
    costs.add(1, T0)
    costs.add(2, T0 + timedelta(minutes=1))

    response = await client.get("/v1/cost-log", headers=recruiter)

    body = response.json()
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert body["budget"] == {
        "spent_usd": "0.412300",
        "limit_usd": "8",
        "mode": "replay",
        "model_actions_allowed": True,
    }
    assert [c["id"] for c in body["data"]] == [2, 1]
    assert body["data"][0]["cost_usd"] == "0.002700"
    assert body["page"] == {"next_cursor": None, "has_more": False}


async def test_a_missing_budget_row_reads_as_nothing_spent(
    client: AsyncClient, costs: FakeCost, recruiter: dict[str, str]
) -> None:
    costs.spent = None

    body = (await client.get("/v1/cost-log", headers=recruiter)).json()

    assert body["budget"]["spent_usd"] == "0"
    assert body["data"] == []


async def test_in_live_mode_at_the_cap_model_actions_are_not_allowed(
    client: AsyncClient, app: FastAPI, costs: FakeCost, recruiter: dict[str, str]
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"model_mode": "live"})
    costs.spent = Decimal("7.99")

    budget = (await client.get("/v1/cost-log", headers=recruiter)).json()["budget"]

    assert (budget["mode"], budget["model_actions_allowed"]) == ("live", False)


async def test_pages_follow_the_cursor_without_gaps_or_repeats(
    client: AsyncClient, costs: FakeCost, recruiter: dict[str, str]
) -> None:
    for n in range(1, 6):
        costs.add(n, T0 + timedelta(seconds=n // 2))  # ids 2 and 3 share a timestamp

    first = (await client.get("/v1/cost-log?limit=2", headers=recruiter)).json()
    second = (
        await client.get(
            f"/v1/cost-log?limit=2&cursor={first['page']['next_cursor']}", headers=recruiter
        )
    ).json()
    third = (
        await client.get(
            f"/v1/cost-log?limit=2&cursor={second['page']['next_cursor']}", headers=recruiter
        )
    ).json()

    pages = [[c["id"] for c in p["data"]] for p in (first, second, third)]
    assert pages == [[5, 4], [3, 2], [1]]
    assert [p["page"]["has_more"] for p in (first, second, third)] == [True, True, False]
    assert third["page"]["next_cursor"] is None


@pytest.mark.parametrize("limit", ["0", "101", "x"])
async def test_a_limit_outside_1_to_100_is_422(
    client: AsyncClient, costs: FakeCost, recruiter: dict[str, str], limit: str
) -> None:
    response = await client.get(f"/v1/cost-log?limit={limit}", headers=recruiter)

    assert response.status_code == 422


@pytest.mark.parametrize("limit", ["1", "100"])
async def test_the_limits_themselves_are_accepted(
    client: AsyncClient, costs: FakeCost, recruiter: dict[str, str], limit: str
) -> None:
    assert (await client.get(f"/v1/cost-log?limit={limit}", headers=recruiter)).status_code == 200


@pytest.mark.parametrize("cursor", ["not-base64!", "bm9waXBl", "MjAyNi0wOS0zMHwx"])
async def test_a_bad_cursor_is_422_never_500(
    client: AsyncClient, costs: FakeCost, recruiter: dict[str, str], cursor: str
) -> None:
    response = await client.get(f"/v1/cost-log?cursor={cursor}", headers=recruiter)

    assert (response.status_code, response.json()["error"]["code"]) == (422, "validation_error")


async def test_an_interviewer_cannot_read_the_cost_log(
    client: AsyncClient, users: FakeUsers, sessions: FakeSessions, costs: FakeCost
) -> None:
    headers = (await sessions.sign_in(users.add(email="i@example.com", role="interviewer"))).cookie

    response = await client.get("/v1/cost-log", headers=headers)

    assert (response.status_code, response.json()["error"]["code"]) == (403, "forbidden")


def test_a_cursor_round_trips_and_a_naive_one_is_refused() -> None:
    assert decode_cursor(encode_cursor(T0, 7)) == (T0, 7)
    with pytest.raises(ValidationFailedError):
        decode_cursor(encode_cursor(T0.replace(tzinfo=None), 7))
