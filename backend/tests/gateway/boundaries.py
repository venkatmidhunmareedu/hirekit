"""Detectors for the gateway's boundaries, written over the AST so a comment cannot fool them.

Each takes the root of an `app` package, so the tests can also run them on a small synthetic
tree with the violation planted and prove they catch it.
"""

import ast
from pathlib import Path


def py_files(root: Path) -> list[Path]:
    """Every Python file under `root`, sorted."""
    return sorted(root.rglob("*.py"))


def module_name(root: Path, path: Path) -> str:
    """`app/gateway/text.py` under a root named `app` is `app.gateway.text`."""
    parts = list(path.relative_to(root.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_modules(path: Path) -> set[str]:
    """Absolute module names a file imports, including `pkg.name` for `from pkg import name`."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def files_importing(root: Path, prefix: str) -> list[str]:
    """Modules under `root` that import `prefix` or anything below it."""
    hits = []
    for path in py_files(root):
        if any(m == prefix or m.startswith(prefix + ".") for m in imported_modules(path)):
            hits.append(module_name(root, path))
    return hits


def files_containing(root: Path, needle: str) -> list[str]:
    """Modules under `root` whose source text contains `needle`."""
    return [
        module_name(root, path)
        for path in py_files(root)
        if needle in path.read_text(encoding="utf-8")
    ]


def files_importing_name(root: Path, module: str, name: str) -> list[str]:
    """Modules under `root` that import `name` from `module` (`from module import name`)."""
    hits = []
    for path in py_files(root):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == module
                and any(alias.name == name for alias in node.names)
            ):
                hits.append(module_name(root, path))
    return hits


def constructor_calls(root: Path, names: set[str]) -> list[tuple[str, str]]:
    """(module, class) for every direct call `Name(...)` of one of `names` under `root`."""
    hits = []
    for path in py_files(root):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in names
            ):
                hits.append((module_name(root, path), node.func.id))
    return hits


def _file_for(root: Path, module: str) -> Path | None:
    """The file that defines `module`, or None (a name imported from a module is not a file)."""
    if module == root.name:
        init = root / "__init__.py"
        return init if init.is_file() else None
    relative = Path(*module.split(".")[1:])  # drop the leading "app"
    for candidate in (root / relative.with_suffix(".py"), root / relative / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def import_closure(root: Path, start: str) -> set[str]:
    """Every first-party module reachable from `start` by imports (the process's import set)."""
    seen: set[str] = set()
    pending = [start]
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        path = _file_for(root, module)
        if path is None:
            continue
        seen.add(module)
        for imported in imported_modules(path):
            if imported == root.name or imported.startswith(root.name + "."):
                pending.append(imported)
        # importing `a.b.c` also runs `a` and `a.b`
        parts = module.split(".")
        pending.extend(".".join(parts[:i]) for i in range(1, len(parts)))
    return seen


def defined_test_names(tests_root: Path) -> set[str]:
    """Names of every `test_*` function or method defined under `tests_root`."""
    names: set[str] = set()
    for path in py_files(tests_root):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
                "test_"
            ):
                names.add(node.name)
    return names
