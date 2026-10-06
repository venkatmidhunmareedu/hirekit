"""Load and validate the seed data under `seed/` (US-02-007).

Layout: `roles/<slug>.md`, `resumes/<id>.txt`, `labels.csv`, `pairs.csv`. A resume id starts
with its role slug followed by a dash. Labels are written by the same model family that
wrote the resumes, so they are a consistency check, not independent ground truth.
"""

import csv
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

CRITERION_KINDS = ("must_have", "nice_to_have")
LEVEL_LINE = re.compile(r"^([0-4]): (.+)$")


class SeedError(Exception):
    """The seed data breaks a rule; the message names the file and the row."""


@dataclass(frozen=True, slots=True)
class Expected:
    """The counts the real seed must hold; tests pass smaller ones."""

    roles: int = 2
    resumes: int = 40
    per_role: int = 20
    pairs: int = 20


@dataclass(frozen=True, slots=True)
class SeedCriterion:
    name: str
    kind: str
    weight: Decimal
    levels: tuple[str, str, str, str, str]


@dataclass(frozen=True, slots=True)
class SeedRole:
    slug: str
    title: str
    job_description: str
    criteria: tuple[SeedCriterion, ...]


@dataclass(frozen=True, slots=True)
class SeedPair:
    base_id: str
    swap_id: str
    origin_pair: str
    signals_swapped: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SeedData:
    roles: tuple[SeedRole, ...]
    resumes: dict[str, str]
    labels: dict[str, dict[str, int]]
    pairs: tuple[SeedPair, ...]


def _criterion(slug: str, block: list[str]) -> SeedCriterion:
    name = block[0].removeprefix("## Criterion:").strip()
    fields: dict[str, str] = {}
    levels: dict[int, str] = {}
    for line in block[1:]:
        if match := LEVEL_LINE.match(line):
            levels[int(match.group(1))] = match.group(2).strip()
        elif ": " in line:
            key, _, value = line.partition(": ")
            fields[key] = value.strip()
    kind = fields.get("kind", "")
    if kind not in CRITERION_KINDS:
        raise SeedError(f"roles/{slug}.md: criterion {name!r} has kind {kind!r}")
    try:
        weight = Decimal(fields.get("weight", ""))
    except InvalidOperation:
        raise SeedError(f"roles/{slug}.md: criterion {name!r} has no numeric weight") from None
    if weight <= 0:
        raise SeedError(f"roles/{slug}.md: criterion {name!r} weight must be positive")
    if sorted(levels) != [0, 1, 2, 3, 4]:
        raise SeedError(f"roles/{slug}.md: criterion {name!r} needs descriptors 0 to 4")
    return SeedCriterion(
        name, kind, weight, (levels[0], levels[1], levels[2], levels[3], levels[4])
    )


def _role(path: Path) -> SeedRole:
    slug = path.stem
    lines = path.read_text().splitlines()
    if not lines or not lines[0].startswith("# "):
        raise SeedError(f"roles/{slug}.md: first line must be '# <title>'")
    title = lines[0].removeprefix("# ").strip()
    blocks: list[list[str]] = []
    for line in lines[1:]:
        if line.startswith("## "):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
    description = next((b for b in blocks if b[0] == "## Job description"), None)
    if description is None or not "\n".join(description[1:]).strip():
        raise SeedError(f"roles/{slug}.md: missing '## Job description'")
    criteria = tuple(_criterion(slug, b) for b in blocks if b[0].startswith("## Criterion:"))
    if not criteria:
        raise SeedError(f"roles/{slug}.md: no criteria")
    names = [c.name for c in criteria]
    if len(set(names)) != len(names):
        raise SeedError(f"roles/{slug}.md: duplicate criterion name")
    return SeedRole(slug, title, "\n".join(description[1:]).strip(), criteria)


def _rows(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != columns:
            raise SeedError(f"{path.name}: header must be {','.join(columns)}")
        return list(reader)


def _labels(root: Path) -> dict[str, dict[str, int]]:
    labels: dict[str, dict[str, int]] = {}
    for row in _rows(root / "labels.csv", ("resume_id", "criterion", "label", "rationale")):
        resume, criterion = row["resume_id"], row["criterion"]
        if not row["label"].isdigit() or int(row["label"]) > 4:
            raise SeedError(f"labels.csv: {resume}/{criterion} label must be 0 to 4")
        if criterion in labels.setdefault(resume, {}):
            raise SeedError(f"labels.csv: duplicate row {resume}/{criterion}")
        labels[resume][criterion] = int(row["label"])
    return labels


def _pairs(root: Path) -> tuple[SeedPair, ...]:
    rows = _rows(root / "pairs.csv", ("base_id", "swap_id", "origin_pair", "signals_swapped"))
    return tuple(
        SeedPair(
            r["base_id"], r["swap_id"], r["origin_pair"], tuple(r["signals_swapped"].split(";"))
        )
        for r in rows
    )


def _validate(
    expected: Expected,
    roles: tuple[SeedRole, ...],
    resumes: dict[str, str],
    labels: dict[str, dict[str, int]],
    pairs: tuple[SeedPair, ...],
) -> None:
    if len(roles) != expected.roles:
        raise SeedError(f"expected {expected.roles} roles, found {len(roles)}")
    if len(resumes) != expected.resumes:
        raise SeedError(f"expected {expected.resumes} resumes, found {len(resumes)}")
    if len(pairs) != expected.pairs:
        raise SeedError(f"expected {expected.pairs} pairs, found {len(pairs)}")
    owner: dict[str, SeedRole] = {}
    for resume_id in resumes:
        found = [r for r in roles if resume_id.startswith(f"{r.slug}-")]
        if not found:
            raise SeedError(f"resumes/{resume_id}.txt: id does not start with a role slug")
        owner[resume_id] = found[0]
    for role in roles:
        count = sum(1 for o in owner.values() if o is role)
        if count != expected.per_role:
            raise SeedError(
                f"role {role.slug}: expected {expected.per_role} resumes, found {count}"
            )
    for resume_id, role in owner.items():
        wanted = {c.name for c in role.criteria}
        got = set(labels.get(resume_id, {}))
        if got != wanted:
            raise SeedError(
                f"labels.csv: {resume_id} labels {sorted(got)} but role needs {sorted(wanted)}"
            )
    for resume_id in labels.keys() - resumes.keys():
        raise SeedError(f"labels.csv: unknown resume {resume_id}")
    used: set[str] = set()
    for pair in pairs:
        for resume_id in (pair.base_id, pair.swap_id):
            if resume_id not in resumes:
                raise SeedError(f"pairs.csv: unknown resume {resume_id}")
            if resume_id in used:
                raise SeedError(f"pairs.csv: {resume_id} is in more than one pair")
            used.add(resume_id)
        if labels[pair.base_id] != labels[pair.swap_id]:
            raise SeedError(f"pairs.csv: labels of {pair.base_id} and {pair.swap_id} differ")


def load_seed(root: Path, expected: Expected | None = None) -> SeedData:
    """Read `root` and return it validated; raises `SeedError` on the first broken rule."""
    expected = expected or Expected()
    roles = tuple(_role(p) for p in sorted((root / "roles").glob("*.md")))
    resumes = {p.stem: p.read_text() for p in sorted((root / "resumes").glob("*.txt"))}
    labels = _labels(root)
    pairs = _pairs(root)
    _validate(expected, roles, resumes, labels, pairs)
    return SeedData(roles, resumes, labels, pairs)
