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


type Json = dict[str, Json] | list[Json] | str | int | float | bool | None


def _obj(node: Json) -> dict[str, Json]:
    return node if isinstance(node, dict) else {}


def _list(node: Json) -> list[Json]:
    return node if isinstance(node, list) else []


def _fields(schema: Json, doc: Json, prefix: str = "") -> set[str]:
    """Every property path in a schema, following $ref, allOf and array items."""
    obj = _obj(schema)
    ref = obj.get("$ref")
    if isinstance(ref, str):
        node = doc
        for part in ref.removeprefix("#/").split("/"):
            node = _obj(node).get(part)
        return _fields(node, doc, prefix)
    found: set[str] = set()
    for sub_schema in _list(obj.get("allOf")):
        found |= _fields(sub_schema, doc, prefix)
    for name, sub in _obj(obj.get("properties")).items():
        found |= {f"{prefix}{name}"} | _fields(sub, doc, f"{prefix}{name}.")
    items = obj.get("items")
    if isinstance(items, dict):
        found |= _fields(items, doc, prefix)
    return found


def _response_fields(doc: Json) -> dict[tuple[str, str], set[str]]:
    result: dict[tuple[str, str], set[str]] = {}
    for path, item in _obj(_obj(doc).get("paths")).items():
        for method, op in _obj(item).items():
            if method not in METHODS:
                continue
            for status, response in _obj(_obj(op).get("responses")).items():
                if not str(status).startswith("2"):
                    continue
                content = _obj(_obj(response).get("content"))
                body = _obj(content.get("application/json")).get("schema")
                if body:
                    result[(method.upper(), f"{path} {status}")] = _fields(body, doc)
    return result


def _missing_fields(served: Json, documented: Json) -> dict[tuple[str, str], list[str]]:
    served_fields = _response_fields(served)
    documented_fields = _response_fields(documented)
    return {
        key: sorted(fields - documented_fields.get(key, set()))
        for key, fields in served_fields.items()
        if fields - documented_fields.get(key, set())
    }


def test_every_response_schema_field_exists_in_openapi() -> None:
    app = create_app(Settings(_env_file=None, database_url=DB))
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    assert _missing_fields(app.openapi(), spec) == {}


def test_the_field_detector_flags_a_field_missing_from_the_spec() -> None:
    app = create_app(Settings(_env_file=None, database_url=DB))
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]
    ready = schemas["Ready"]["properties"]
    assert "checks" in ready
    del ready["checks"]

    missing = _missing_fields(app.openapi(), spec)

    assert any("checks" in fields for fields in missing.values())


def test_the_upload_request_body_matches_the_spec() -> None:
    """The route takes `Request`, so FastAPI emits no body; openapi_extra restates the spec's."""
    app = create_app(Settings(_env_file=None, database_url=DB))
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    path = "/v1/roles/{role_id}/resumes"
    committed = spec["paths"][path]["post"]["requestBody"]
    media = committed["content"]["multipart/form-data"]
    name = media["schema"]["$ref"].rsplit("/", 1)[-1]
    expected = {
        **committed,
        "content": {"multipart/form-data": {"schema": spec["components"]["schemas"][name]}},
    }

    served = app.openapi()["paths"][path]["post"]["requestBody"]

    assert _strip_examples(served) == _strip_examples(expected)


def _strip_examples(node: Json) -> Json:
    if isinstance(node, dict):
        return {k: _strip_examples(v) for k, v in node.items() if k != "example"}
    return node
