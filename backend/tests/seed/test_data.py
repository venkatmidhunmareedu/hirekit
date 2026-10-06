"""The seed loader and validator, on tiny fixture data written to tmp_path."""

from decimal import Decimal
from pathlib import Path

import pytest

from app.seed.data import Expected, SeedError, load_seed

TINY = Expected(roles=1, resumes=2, per_role=2, pairs=1)

ROLE = """# Backend Engineer

## Job description

Build services.
Own them.

## Criterion: Python
kind: must_have
weight: 3
0: none
1: basic
2: some
3: good
4: expert

## Criterion: Testing
kind: nice_to_have
weight: 1.5
0: none
1: basic
2: some
3: good
4: expert
"""


def write_seed(root: Path, *, labels: str | None = None, pairs: str | None = None) -> Path:
    (root / "roles").mkdir()
    (root / "resumes").mkdir()
    (root / "roles" / "backend.md").write_text(ROLE)
    (root / "resumes" / "backend-01.txt").write_text("Jane Doe\nPython")
    (root / "resumes" / "backend-01-swap.txt").write_text("Ravi Kumar\nPython")
    default_labels = (
        "resume_id,criterion,label,rationale\n"
        "backend-01,Python,3,r\nbackend-01,Testing,1,r\n"
        "backend-01-swap,Python,3,r\nbackend-01-swap,Testing,1,r\n"
    )
    (root / "labels.csv").write_text(labels or default_labels)
    (root / "pairs.csv").write_text(
        pairs
        or "base_id,swap_id,origin_pair,signals_swapped\n"
        "backend-01,backend-01-swap,western-indian,name;email\n"
    )
    return root


def test_loads_a_role_with_criteria_and_rubric(tmp_path: Path) -> None:
    data = load_seed(write_seed(tmp_path), TINY)

    role = data.roles[0]
    assert (role.slug, role.title) == ("backend", "Backend Engineer")
    assert role.job_description == "Build services.\nOwn them."
    assert [(c.name, c.kind, c.weight) for c in role.criteria] == [
        ("Python", "must_have", Decimal(3)),
        ("Testing", "nice_to_have", Decimal("1.5")),
    ]
    assert role.criteria[0].levels == ("none", "basic", "some", "good", "expert")


def test_loads_resumes_labels_and_pairs(tmp_path: Path) -> None:
    data = load_seed(write_seed(tmp_path), TINY)

    assert sorted(data.resumes) == ["backend-01", "backend-01-swap"]
    assert data.labels["backend-01"]["Python"] == 3
    assert data.pairs[0].swap_id == "backend-01-swap"
    assert data.pairs[0].signals_swapped == ("name", "email")


def test_rejects_the_wrong_resume_count(tmp_path: Path) -> None:
    with pytest.raises(SeedError, match="resumes"):
        load_seed(write_seed(tmp_path), Expected(roles=1, resumes=40, per_role=2, pairs=1))


def test_rejects_a_score_outside_0_to_4(tmp_path: Path) -> None:
    labels = (
        "resume_id,criterion,label,rationale\n"
        "backend-01,Python,5,r\nbackend-01,Testing,1,r\n"
        "backend-01-swap,Python,5,r\nbackend-01-swap,Testing,1,r\n"
    )
    with pytest.raises(SeedError, match="0 to 4"):
        load_seed(write_seed(tmp_path, labels=labels), TINY)


def test_rejects_a_resume_missing_a_criterion_label(tmp_path: Path) -> None:
    labels = (
        "resume_id,criterion,label,rationale\n"
        "backend-01,Python,3,r\nbackend-01,Testing,1,r\n"
        "backend-01-swap,Python,3,r\n"
    )
    with pytest.raises(SeedError, match="backend-01-swap"):
        load_seed(write_seed(tmp_path, labels=labels), TINY)


def test_rejects_a_label_for_an_unknown_criterion(tmp_path: Path) -> None:
    labels = (
        "resume_id,criterion,label,rationale\n"
        "backend-01,Python,3,r\nbackend-01,Testing,1,r\nbackend-01,Go,1,r\n"
        "backend-01-swap,Python,3,r\nbackend-01-swap,Testing,1,r\n"
    )
    with pytest.raises(SeedError, match="Go"):
        load_seed(write_seed(tmp_path, labels=labels), TINY)


def test_rejects_a_duplicate_label_row(tmp_path: Path) -> None:
    labels = (
        "resume_id,criterion,label,rationale\n"
        "backend-01,Python,3,r\nbackend-01,Python,3,r\nbackend-01,Testing,1,r\n"
        "backend-01-swap,Python,3,r\nbackend-01-swap,Testing,1,r\n"
    )
    with pytest.raises(SeedError, match="duplicate"):
        load_seed(write_seed(tmp_path, labels=labels), TINY)


def test_rejects_a_swap_whose_labels_differ_from_its_base(tmp_path: Path) -> None:
    labels = (
        "resume_id,criterion,label,rationale\n"
        "backend-01,Python,3,r\nbackend-01,Testing,1,r\n"
        "backend-01-swap,Python,2,r\nbackend-01-swap,Testing,1,r\n"
    )
    with pytest.raises(SeedError, match="differ"):
        load_seed(write_seed(tmp_path, labels=labels), TINY)


def test_rejects_a_pair_naming_an_unknown_resume(tmp_path: Path) -> None:
    pairs = "base_id,swap_id,origin_pair,signals_swapped\nbackend-01,ghost,x,name\n"
    with pytest.raises(SeedError, match="ghost"):
        load_seed(write_seed(tmp_path, pairs=pairs), TINY)


def test_rejects_a_resume_used_in_two_pairs(tmp_path: Path) -> None:
    pairs = (
        "base_id,swap_id,origin_pair,signals_swapped\n"
        "backend-01,backend-01-swap,x,name\nbackend-01,backend-01-swap,x,name\n"
    )
    with pytest.raises(SeedError, match="more than one pair"):
        load_seed(
            write_seed(tmp_path, pairs=pairs), Expected(roles=1, resumes=2, per_role=2, pairs=2)
        )


def test_rejects_a_resume_with_no_role_prefix(tmp_path: Path) -> None:
    root = write_seed(tmp_path)
    (root / "resumes" / "stray.txt").write_text("x")
    with pytest.raises(SeedError, match="stray"):
        load_seed(root, Expected(roles=1, resumes=3, per_role=2, pairs=1))
