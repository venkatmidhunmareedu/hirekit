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


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """ids of the string nodes that are module, class or function docstrings."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                found.add(id(first.value))
    return found


def string_literals(root: Path, package: str) -> list[tuple[str, str]]:
    """(module, text) for every string literal in `package` that is not a docstring."""
    hits: list[tuple[str, str]] = []
    for path in py_files(root):
        module = module_name(root, path)
        if module != package and not module.startswith(package + "."):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip = _docstring_nodes(tree)
        hits.extend(
            (module, node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in skip
        )
    return hits


def attribute_reads(root: Path, package: str, owner: str) -> set[str]:
    """Attribute names read on the variable `owner` (`owner.name`) anywhere in `package`."""
    reads: set[str] = set()
    for path in py_files(root):
        module = module_name(root, path)
        if module != package and not module.startswith(package + "."):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == owner
            ):
                reads.add(node.attr)
    return reads


def module_level_calls(root: Path, names: set[str]) -> list[tuple[str, str]]:
    """(module, name) for a call of one of `names` that runs at import time (not in a def)."""
    hits = []
    for path in py_files(root):
        stack: list[ast.AST] = list(ast.parse(path.read_text(encoding="utf-8")).body)
        while stack:
            node = stack.pop()
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
                continue
            if isinstance(node, ast.Call):
                func = node.func
                called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                if called in names:
                    hits.append((module_name(root, path), called))
            stack.extend(ast.iter_child_nodes(node))
    return hits


class _FenceScan(ast.NodeVisitor):
    """Finds repository calls (`<x>.writes.f(...)`, `<x>.jobs.f(...)`) outside a fenced session."""

    def __init__(self) -> None:
        self.fenced = 0
        self.scopes: list[bool] = []  # does the enclosing def take a `session` parameter
        self.lines: list[int] = []

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        fenced = any(
            isinstance(i.context_expr, ast.Call)
            and isinstance(i.context_expr.func, ast.Attribute)
            and i.context_expr.func.attr == "fenced"
            for i in node.items
        )
        self.fenced += fenced
        self.generic_visit(node)
        self.fenced -= fenced

    def _scoped(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.scopes.append(any(a.arg == "session" for a in node.args.args))
        self.generic_visit(node)
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scoped(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._scoped(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == "sessions" and isinstance(node.value, ast.Name) and node.value.id == "ctx":
            self.lines.append(node.lineno)  # a handler never opens its own transaction
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Attribute)
            and func.value.attr in {"writes", "jobs"}
        ):
            first = node.args[0] if node.args else None
            in_session = self.fenced > 0 or (bool(self.scopes) and self.scopes[-1])
            if not (isinstance(first, ast.Name) and first.id == "session" and in_session):
                self.lines.append(node.lineno)
        self.generic_visit(node)


def unfenced_calls(root: Path, package: str) -> list[tuple[str, int]]:
    """(module, line) of each repository call in `package` not made on a fenced `session`."""
    hits: list[tuple[str, int]] = []
    for path in py_files(root):
        module = module_name(root, path)
        if module != package and not module.startswith(package + "."):
            continue
        scan = _FenceScan()
        scan.visit(ast.parse(path.read_text(encoding="utf-8")))
        hits.extend((module, line) for line in scan.lines)
    return hits
