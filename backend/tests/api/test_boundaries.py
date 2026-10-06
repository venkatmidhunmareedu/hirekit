"""The Api's structural guards hold in the real tree, and each detector catches a planted breach."""

from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI

from app.core.config import Settings
from app.main import create_app
from tests.api import guards as g

APP = Path(__file__).resolve().parents[2] / "app"
DB = "postgresql+asyncpg://postgres:postgres@localhost:5432/test"


def tree(root: Path, files: dict[str, str]) -> Path:
    """Write a small `app` package under `root` and return its path."""
    app = root / "app"
    for relative, source in {"__init__.py": "", **files}.items():
        path = app / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return app


def real_app() -> FastAPI:
    return create_app(Settings(_env_file=None, database_url=DB))


# The real tree ---------------------------------------------------------------------------


def test_every_route_declares_a_role() -> None:
    """AC-US-00-012-1, tenet 6: no route but login and health is open to anyone."""
    assert g.routes_without_a_role(real_app()) == []


def test_no_module_but_the_stage_route_writes_the_stage() -> None:
    """AC-US-00-011-4, tenet 4."""
    assert g.stage_writers(APP) == []


def test_every_repository_function_returning_candidate_data_takes_a_viewer() -> None:
    """Tenet 6: visibility is in the query, so the query needs the viewer."""
    assert g.repository_functions_without_viewer(APP) == []


# The detectors ---------------------------------------------------------------------------


def test_the_role_check_finds_a_route_with_no_auth_dependency() -> None:
    app = real_app()
    router = APIRouter()

    @router.get("/v1/open")
    async def open_route() -> dict[str, str]:
        return {}

    app.include_router(router)
    assert g.routes_without_a_role(app) == ["GET /v1/open"]


def test_the_role_check_accepts_a_route_that_depends_on_the_auth_module() -> None:
    async def current_user() -> str:
        return "u"

    current_user.__module__ = g.AUTH_MODULE
    app = real_app()

    @app.get("/v1/closed")
    async def closed(user: str = Depends(current_user)) -> dict[str, str]:
        return {"user": user}

    assert g.routes_without_a_role(app) == []


def test_the_stage_scan_finds_sql_values_and_attribute_writes(tmp_path: Path) -> None:
    app = tree(
        tmp_path,
        {
            "a.py": 's = "UPDATE candidates SET stage = :s"\n',
            "b.py": "q = update(T).values(stage='x')\n",
            "c.py": "def f(c):\n    c.stage = 'x'\n",
            "d.py": "x = 1\n",
            "api/stage.py": "def f(c):\n    c.stage = 'x'\n",
        },
    )
    assert g.stage_writers(app) == ["app.a", "app.b", "app.c"]


def test_the_viewer_scan_finds_a_candidate_query_without_a_viewer(tmp_path: Path) -> None:
    app = tree(
        tmp_path,
        {
            "db/repositories/__init__.py": "",
            "db/repositories/c.py": (
                "def ok(session, viewer):\n    return 'SELECT * FROM candidates'\n"
                "def leak(session):\n    return 'SELECT * FROM candidates'\n"
                "def _private(session):\n    return 'SELECT * FROM candidates'\n"
                "def other(session):\n    return 'SELECT 1 FROM roles'\n"
            ),
        },
    )
    assert g.repository_functions_without_viewer(app) == ["app.db.repositories.c.leak"]
