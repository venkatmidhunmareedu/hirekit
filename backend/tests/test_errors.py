"""Every failure comes back in the one envelope."""

from typing import Annotated

from fastapi import FastAPI, Query
from httpx import AsyncClient

from app.core.errors import (
    CriteriaChangedError,
    IncompleteRubricError,
    NoCriteriaError,
    NotFoundError,
    RoleNotApprovedError,
)


async def test_domain_error_is_mapped(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise NotFoundError("invoice 7", details={"id": 7})

    response = await client.get("/boom")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "not_found",
        "message": "invoice 7",
        "details": {"id": 7},
        "request_id": response.headers["x-request-id"],
    }


async def test_validation_error_is_422_in_envelope(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/items")
    async def items(limit: Annotated[int, Query(le=100)]) -> dict[str, int]:
        return {"limit": limit}

    response = await client.get("/items", params={"limit": "500"})

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"]["errors"][0]["loc"] == ["query", "limit"]


async def test_unknown_route_uses_envelope(client: AsyncClient) -> None:
    response = await client.get("/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"


async def test_unhandled_error_is_500_without_detail(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/crash")
    async def crash() -> dict[str, str]:
        raise RuntimeError("secret internals")

    response = await client.get("/crash")

    assert response.status_code == 500
    assert "secret internals" not in response.text
    assert response.json()["error"] == {
        "code": "internal",
        "message": "internal error",
        "details": {},
        "request_id": response.headers["x-request-id"],
    }


async def test_roles_errors_map_to_their_status_and_code(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/roles-errors/{name}")
    async def raise_it(name: str) -> dict[str, str]:
        raise {
            "changed": CriteriaChangedError("changed", details={"current_version": 3}),
            "none": NoCriteriaError("none"),
            "draft": RoleNotApprovedError("draft"),
            "rubric": IncompleteRubricError("rubric", details={"criterion_ids": ["a"]}),
        }[name]

    got = {
        n: await client.get(f"/roles-errors/{n}") for n in ("changed", "none", "draft", "rubric")
    }

    assert {n: (r.status_code, r.json()["error"]["code"]) for n, r in got.items()} == {
        "changed": (409, "criteria_changed"),
        "none": (422, "no_criteria"),
        "draft": (409, "role_not_approved"),
        "rubric": (422, "incomplete_rubric"),
    }
    assert got["changed"].json()["error"]["details"] == {"current_version": 3}
