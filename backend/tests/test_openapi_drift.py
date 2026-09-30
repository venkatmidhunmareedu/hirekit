"""The committed contract (api/openapi.yaml) covers every route the code serves."""

from pathlib import Path

import yaml
from fastapi import FastAPI

from app.core.config import Settings
from app.main import create_app

SPEC = Path(__file__).resolve().parents[1] / "api" / "openapi.yaml"
METHODS = ("get", "post", "put", "delete", "patch")
DB = "postgresql+asyncpg://postgres:postgres@localhost:5432/test"


def spec_operations() -> set[tuple[str, str]]:
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    return {(m.upper(), p) for p, item in spec["paths"].items() for m in item if m in METHODS}


def code_operations(app: FastAPI) -> set[tuple[str, str]]:
    schema = app.openapi()
    return {(m.upper(), p) for p, item in schema["paths"].items() for m in item if m in METHODS}


def undocumented(app: FastAPI) -> set[tuple[str, str]]:
    """Routes the code serves that the spec does not list."""
    return code_operations(app) - spec_operations()


def test_every_route_in_the_code_is_in_the_spec() -> None:
    app = create_app(Settings(_env_file=None, database_url=DB))
    assert undocumented(app) == set()


def test_the_detector_finds_a_route_missing_from_the_spec() -> None:
    app = create_app(Settings(_env_file=None, database_url=DB))

    @app.get("/v1/secret-route")
    async def secret() -> dict[str, str]:
        return {}

    assert undocumented(app) == {("GET", "/v1/secret-route")}


def test_the_spec_has_the_operations_the_api_design_lists() -> None:
    """A cheap floor: the design's route table (docs/design/api-lld.md) has 37 operations."""
    assert len(spec_operations()) == 37


def test_every_operation_declares_its_stories_and_an_operation_id() -> None:
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    ids: list[str] = []
    for item in spec["paths"].values():
        for method, op in item.items():
            if method in METHODS:
                assert op["x-story-ids"], op["operationId"]
                ids.append(op["operationId"])
    assert len(ids) == len(set(ids))


def test_every_schema_has_an_example() -> None:
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    missing = [
        name for name, schema in spec["components"]["schemas"].items() if "example" not in schema
    ]
    assert missing == []
