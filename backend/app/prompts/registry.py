"""Load `app/prompts/<name>/v<N>.md` and render it into a `PromptText`.

The only importer of `mint_prompt` (tenet 2). Error messages name variables and limits,
never values: a value can be resume text (tenet 7). Frontmatter is a strict subset of
YAML (`key: value`, inline lists, one `variables:` list of flat mappings) parsed here so
the registry needs no YAML dependency.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import DomainError
from app.gateway.text import PromptText, mint_prompt

PROMPTS_DIR = Path(__file__).parent
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
_VERSION_FILE = re.compile(r"v(\d+)\.md")
_TYPES: dict[str, type] = {"str": str, "int": int}


class PromptRegistryError(DomainError):
    """A prompt is missing, malformed or rendered with bad variables."""

    status_code = 500
    code = "prompt_registry_error"


@dataclass(frozen=True)
class Variable:
    name: str
    type: str
    required: bool
    max_chars: int
    enum: tuple[str, ...] | None


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    template: str
    model: str
    effort: str
    max_tokens: int
    variables: tuple[Variable, ...]
    owner: str
    eval_set: str
    status: str

    @property
    def prompt_version(self) -> str:
        return f"{self.name}-v{self.version}"


def _scalar(raw: str) -> object:
    raw = raw.strip()
    if raw in {"true", "false"}:
        return raw == "true"
    if raw.isdigit():
        return int(raw)
    if raw.startswith("[") and raw.endswith("]"):
        return [_scalar(p) for p in raw[1:-1].split(",") if p.strip()]
    return raw


def _parse_frontmatter(block: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Parse the strict subset into (scalars, the `variables` entries); else raise."""
    scalars: dict[str, object] = {}
    entries: list[dict[str, object]] = []
    in_list = False
    for line in block.splitlines():
        if not line.strip():
            continue
        text = line.strip()
        if not line.startswith(" "):
            key, sep, value = line.partition(":")
            if not sep:
                raise PromptRegistryError("frontmatter line is not 'key: value'")
            in_list = key == "variables" and not value.strip()
            if not in_list:
                scalars[key] = _scalar(value)
            continue
        if not in_list:
            raise PromptRegistryError("indented frontmatter line outside the variables list")
        if text.startswith("- "):
            entries.append({})
            text = text[2:]
        key, sep, value = text.partition(":")
        if not sep or not entries:
            raise PromptRegistryError("variables entry is not 'key: value'")
        entries[-1][key.strip()] = _scalar(value)
    return scalars, entries


def _variable(entry: dict[str, object]) -> Variable:
    enum = entry.get("enum")
    name, type_, required, max_chars = (
        entry.get(k) for k in ("name", "type", "required", "max_chars")
    )
    if not (isinstance(name, str) and isinstance(type_, str) and type_ in _TYPES):
        raise PromptRegistryError("a variable needs a name and a type of str or int")
    if not (isinstance(required, bool) and isinstance(max_chars, int)):
        raise PromptRegistryError(f"variable {name} needs required (bool) and max_chars (int)")
    if enum is not None and not (isinstance(enum, list) and all(isinstance(e, str) for e in enum)):
        raise PromptRegistryError(f"variable {name} has a bad enum")
    return Variable(name, type_, required, max_chars, tuple(enum) if enum else None)


def _read(name: str, path: Path, version: int) -> Prompt:
    head, sep, body = path.read_text(encoding="utf-8").removeprefix("---\n").partition("\n---\n")
    if not sep:
        raise PromptRegistryError(f"{name}-v{version}: frontmatter is missing")
    meta, entries = _parse_frontmatter(head)
    try:
        prompt = Prompt(
            name=name,
            version=version,
            template=body,
            model=str(meta["model"]),
            effort=str(meta["effort"]),
            max_tokens=int(str(meta["max_tokens"])),
            variables=tuple(_variable(e) for e in entries),
            owner=str(meta["owner"]),
            eval_set=str(meta["eval_set"]),
            status=str(meta["status"]),
        )
    except KeyError as exc:
        raise PromptRegistryError(f"{name}-v{version}: frontmatter lacks {exc.args[0]}") from exc
    if prompt.status not in {"draft", "active", "retired"}:
        raise PromptRegistryError(
            f"{prompt.prompt_version}: status must be draft, active or retired"
        )
    used = set(_PLACEHOLDER.findall(body))
    if used != {v.name for v in prompt.variables}:
        raise PromptRegistryError(
            f"{prompt.prompt_version}: body placeholders differ from variables"
        )
    return prompt


def load_prompt(name: str, version: int | None = None, *, root: Path = PROMPTS_DIR) -> Prompt:
    """Load one version; with no version, the highest `active` one (drafts need `version`)."""
    folder = root / name
    found = {
        int(m.group(1)): p for p in folder.glob("v*.md") if (m := _VERSION_FILE.fullmatch(p.name))
    }
    if version is not None:
        if version not in found:
            raise PromptRegistryError(f"{name}-v{version} does not exist")
        return _read(name, found[version], version)
    for n in sorted(found, reverse=True):
        prompt = _read(name, found[n], n)
        if prompt.status == "active":
            return prompt
    raise PromptRegistryError(f"{name} has no active version")


def render(prompt: Prompt, variables: dict[str, object]) -> PromptText:
    """Validate `variables` against the frontmatter, then substitute `{{name}}` in one pass."""
    declared = {v.name: v for v in prompt.variables}
    if unknown := sorted(set(variables) - set(declared)):
        raise PromptRegistryError(f"{prompt.prompt_version}: unknown variables {unknown}")
    values: dict[str, str] = {}
    for v in prompt.variables:
        if v.name not in variables:
            if v.required:
                raise PromptRegistryError(f"{prompt.prompt_version}: {v.name} is required")
            values[v.name] = ""
            continue
        value = variables[v.name]
        if type(value) is not _TYPES[v.type]:
            raise PromptRegistryError(f"{prompt.prompt_version}: {v.name} must be {v.type}")
        text = str(value)
        if len(text) > v.max_chars:
            raise PromptRegistryError(
                f"{prompt.prompt_version}: {v.name} exceeds {v.max_chars} chars"
            )
        if v.enum is not None and text not in v.enum:
            raise PromptRegistryError(
                f"{prompt.prompt_version}: {v.name} is not one of {list(v.enum)}"
            )
        values[v.name] = text
    return mint_prompt(_PLACEHOLDER.sub(lambda m: values[m.group(1)], prompt.template))
