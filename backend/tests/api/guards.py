"""Detectors for the Api's structural guards (api-lld section 9 item 12), written over the AST.

Each takes the root of an `app` package, so the tests can also run on a small synthetic tree
with the breach planted and prove the detector catches it.
"""

import ast
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from tests.gateway.boundaries import module_name, py_files

# Routes a signed-out caller may reach (AC-US-00-012-5).
PUBLIC_PATHS = frozenset({"/healthz", "/readyz", "/v1/auth/login"})
AUTH_MODULE = "app.core.auth"
# A module whose last segment is `stage` is the stage route's code path (tenet 4).
STAGE_MODULE = "stage"
CANDIDATE_TABLES = re.compile(r"\b(candidates|scores|resume_texts|feedback|assignments)\b")
# A write to the stage column: a SET list that assigns `stage`. Updates of other candidate columns
# (processing_status, identity_name) are not stage writes.
STAGE_SQL = re.compile(r"\bSET\b[^;]*\bstage\s*=", re.I | re.S)
# A function that returns one of these answers a question about candidates but hands back no
# candidate data: it writes (None), checks (bool) or looks one id up.
SCALAR_RETURN = re.compile(r"^(None|bool|int|str|(uuid\.)?UUID)(\s*\|\s*None)?$")
# Repository reads that return candidate data without a `viewer`, each with its reason. A stale
# entry (the function is gone or now takes a viewer) fails `unused_viewer_exceptions`.
VIEWER_EXCEPTIONS = {
    "app.db.repositories.candidates.ranked": "recruiter-only route; the role is the scope",
    "app.db.repositories.assignments.for_interviewer": "keyed by the interviewer's own user id",
}


def _depends_on_auth(dep: Dependant) -> bool:
    if dep.call is not None and getattr(dep.call, "__module__", "") == AUTH_MODULE:
        return True
    return any(_depends_on_auth(sub) for sub in dep.dependencies)


def routes_without_a_role(app: FastAPI) -> list[str]:
    """`METHOD path` of every non-public API route with no dependency from `app.core.auth`.

    FastAPI 0.142 keeps included routers lazy, so `app.routes` holds wrappers; `iter_route_contexts`
    yields each served route with its include-time prefix and dependencies applied.
    """
    found = []
    for ctx in iter_route_contexts(app.routes):
        if not isinstance(ctx.original_route, APIRoute) or ctx.path in PUBLIC_PATHS:
            continue
        if not _depends_on_auth(ctx.dependant):
            found.append(f"{sorted(ctx.methods or [])[0]} {ctx.path}")
    return sorted(found)


def _writes_stage(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return STAGE_SQL.search(node.value) is not None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr == "values" and any(k.arg == "stage" for k in node.keywords)
    if isinstance(node, ast.Assign):
        return any(isinstance(t, ast.Attribute) and t.attr == "stage" for t in node.targets)
    if isinstance(node, ast.AugAssign):
        return isinstance(node.target, ast.Attribute) and node.target.attr == "stage"
    return False


def stage_writers(root: Path) -> list[str]:
    """Modules, other than a `stage` module, that write `candidates.stage`: SQL text,
    `.values(stage=...)` or an attribute assignment `x.stage = ...`."""
    hits = []
    for path in py_files(root):
        name = module_name(root, path)
        if name.rsplit(".", 1)[-1] == STAGE_MODULE:
            continue
        if any(_writes_stage(n) for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))):
            hits.append(name)
    return hits


def _candidate_reads_without_viewer(root: Path) -> list[str]:
    """Every public repository function that names a candidate table, returns more than a
    scalar (so it hands back candidate data) and has no `viewer` parameter."""
    hits = []
    for path in py_files(root / "db" / "repositories"):
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name.startswith("_"):
                continue
            returns = ast.unparse(node.returns) if node.returns is not None else ""
            if SCALAR_RETURN.match(returns):
                continue
            params = {a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
            body = ast.get_source_segment(source, node) or ""
            if CANDIDATE_TABLES.search(body) and "viewer" not in params:
                hits.append(f"{module_name(root, path)}.{node.name}")
    return sorted(hits)


def repository_functions_without_viewer(
    root: Path, exceptions: dict[str, str] = VIEWER_EXCEPTIONS
) -> list[str]:
    """`module.function` of every repository read of candidate data with no `viewer` parameter
    and no entry in `exceptions` (tenet 6). Writes and bool or id lookups are not reads of
    candidate data."""
    return [name for name in _candidate_reads_without_viewer(root) if name not in exceptions]


def unused_viewer_exceptions(
    root: Path, exceptions: dict[str, str] = VIEWER_EXCEPTIONS
) -> list[str]:
    """Exceptions that no longer match a flagged function: delete them."""
    flagged = set(_candidate_reads_without_viewer(root))
    return sorted(name for name in exceptions if name not in flagged)
