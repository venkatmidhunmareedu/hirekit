"""The eval runner: extract, anonymize and score every seed resume, in order, from file bytes."""

import csv
import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest
from scripts.build_seed_resumes import build

from app.evals.run import ResumeResult, criterion_specs, run_scoring, score_resume
from app.gateway.errors import RecordingMissingError
from app.gateway.types import GatewayRequest, GatewayResponse
from app.prompts.scoring_prompt import ScoringPromptBuilder
from app.seed.data import Expected, SeedData, load_seed
from tests.gateway.fakes import FakeLedger, make_gateway, make_settings, record

EXPECTED = Expected(roles=2, resumes=4, per_role=2, pairs=1)
RESUMES = ("rola-01", "rola-02", "rolb-01", "rolb-02")
BODY = "Jane Doe\njane.doe@example.com\nSenior Python developer at Acme.\nWrote SQL reports."
PDF = "application/pdf"


def _role_md(title: str) -> str:
    levels = "\n".join(f"{n}: level {n}" for n in range(5))
    return (
        f"# {title}\n\n## Job description\nBuild things.\n\n"
        f"## Criterion: Python\nkind: must_have\nweight: 3\n{levels}\n\n"
        f"## Criterion: SQL\nkind: nice_to_have\nweight: 1\n{levels}\n"
    )


def _csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "roles").mkdir()
    (tmp_path / "resumes").mkdir()
    for slug in ("rola", "rolb"):
        (tmp_path / "roles" / f"{slug}.md").write_text(_role_md(f"Role {slug}"))
    for resume_id in RESUMES:
        (tmp_path / "resumes" / f"{resume_id}.txt").write_text(BODY)
        (tmp_path / "resumes" / f"{resume_id}.pdf").write_bytes(build(BODY, "single", "pdf"))
    rows = [[r, c, "3", "ok"] for r in RESUMES for c in ("Python", "SQL")]
    _csv(tmp_path / "labels.csv", [["resume_id", "criterion", "label", "rationale"], *rows])
    _csv(
        tmp_path / "pairs.csv",
        [
            ["base_id", "swap_id", "origin_pair", "signals_swapped"],
            ["rola-01", "rola-02", "p1", "name"],
        ],
    )
    return tmp_path


@pytest.fixture
def seed(root: Path) -> SeedData:
    return load_seed(root, EXPECTED)


def scores_json(python: tuple[int, str], sql: tuple[int, str]) -> str:
    items = [
        {"criterion": n, "value": v, "quote": q} for n, (v, q) in enumerate((python, sql), start=1)
    ]
    return json.dumps({"scores": items})


GOOD = scores_json((4, "Senior Python developer"), (2, "Wrote SQL reports."))


class FakeGateway:
    """Answers each call with `answer(request)` and keeps the requests."""

    def __init__(self, answer: Callable[[GatewayRequest], GatewayResponse | Exception]) -> None:
        self.answer = answer
        self.requests: list[GatewayRequest] = []

    async def complete(self, request: GatewayRequest) -> GatewayResponse:
        self.requests.append(request)
        result = self.answer(request)
        if isinstance(result, Exception):
            raise result
        return result


def text_reply(text: str) -> GatewayResponse:
    return GatewayResponse(text, 10, 10, "stop", "key", True, Decimal(0))


def always(text: str) -> FakeGateway:
    return FakeGateway(lambda _: text_reply(text))


async def test_one_result_per_resume_in_sorted_order(seed: SeedData, root: Path) -> None:
    gateway = always(GOOD)
    results = await run_scoring(seed, gateway, seed_root=root)
    assert [r.resume_id for r in results] == sorted(RESUMES)
    assert [r.role_slug for r in results] == ["rola", "rola", "rolb", "rolb"]
    assert len(gateway.requests) == 4


async def test_scores_map_to_criterion_names(seed: SeedData, root: Path) -> None:
    [first, *_] = await run_scoring(seed, always(GOOD), seed_root=root)
    got = {s.name: (s.status, s.value, s.quote) for s in first.scores}
    assert got == {
        "Python": ("scored", 4, "Senior Python developer"),
        "SQL": ("scored", 2, "Wrote SQL reports."),
    }


async def test_the_model_sees_no_name_or_email(seed: SeedData, root: Path) -> None:
    gateway = always(GOOD)
    [first, *_] = await run_scoring(seed, gateway, seed_root=root)
    assert "Jane Doe" not in first.anonymized_text
    assert "jane.doe@example.com" not in first.anonymized_text
    assert "Senior Python developer" in first.anonymized_text
    assert gateway.requests[0].input.value == first.anonymized_text


async def test_a_quote_not_in_the_text_is_no_evidence(seed: SeedData) -> None:
    reply = scores_json((4, "Led a team of fifty"), (2, "Wrote SQL reports."))
    result = await _one(seed, always(reply))
    python = result.scores[0]
    assert (python.name, python.status, python.value, python.quote) == (
        "Python",
        "no_evidence",
        0,
        None,
    )
    assert python.flag_reason is not None
    assert result.scores[1].status == "scored"


async def test_two_bad_replies_fail_every_criterion(seed: SeedData) -> None:
    gateway = always("not json")
    result = await _one(seed, gateway)
    assert [(s.status, s.value) for s in result.scores] == [("failed", None), ("failed", None)]
    assert [r.schema_retry for r in gateway.requests] == [0, 1]


async def test_a_missing_recording_propagates(seed: SeedData, root: Path) -> None:
    gateway = FakeGateway(lambda _: RecordingMissingError("k"))
    with pytest.raises(RecordingMissingError):
        await run_scoring(seed, gateway, seed_root=root)
    assert len(gateway.requests) == 1


async def test_exactly_one_built_file_must_exist(seed: SeedData, root: Path) -> None:
    (root / "resumes" / "rola-01.pdf").unlink()
    with pytest.raises(ValueError, match="rola-01"):
        await run_scoring(seed, always(GOOD), seed_root=root)


async def test_the_system_prompt_is_identical_across_runs(seed: SeedData, root: Path) -> None:
    first, second = always(GOOD), always(GOOD)
    await run_scoring(seed, first, seed_root=root)
    await run_scoring(load_seed(root, EXPECTED), second, seed_root=root)
    assert [r.system.value for r in first.requests] == [r.system.value for r in second.requests]
    assert first.requests[0].system.value == first.requests[1].system.value


def test_criterion_specs_are_deterministic(seed: SeedData) -> None:
    role = seed.roles[0]
    assert criterion_specs(role) == criterion_specs(role)
    specs = criterion_specs(role)
    assert [(s.name, s.position) for s in specs] == [("Python", 0), ("SQL", 1)]
    assert specs[0].rubric == tuple((n, f"level {n}") for n in range(5))
    assert len({s.id for s in specs}) == 2
    assert criterion_specs(seed.roles[1])[0].id != specs[0].id
    builder = ScoringPromptBuilder()
    assert builder.build(specs).value == builder.build(criterion_specs(role)).value


async def test_real_gateway_in_replay_mode(seed: SeedData, root: Path, tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "rec")
    gateway = make_gateway(settings, FakeLedger())
    role = seed.roles[0]
    seen = always(GOOD)
    result = await score_resume(
        seen,
        role=role,
        resume_id="rola-01",
        content=(root / "resumes" / "rola-01.pdf").read_bytes(),
        media_type=PDF,
    )
    record(seen.requests[0], settings, GOOD)
    replayed = await score_resume(
        gateway,
        role=role,
        resume_id="rola-01",
        content=(root / "resumes" / "rola-01.pdf").read_bytes(),
        media_type=PDF,
    )
    assert replayed == result
    with pytest.raises(RecordingMissingError):
        await score_resume(
            gateway,
            role=seed.roles[1],
            resume_id="rolb-01",
            content=build("Other Person\nWrote Go services.", "single", "pdf"),
            media_type=PDF,
        )


async def _one(seed: SeedData, gateway: FakeGateway) -> ResumeResult:
    content = build(BODY, "single", "pdf")
    return await score_resume(
        gateway, role=seed.roles[0], resume_id="rola-01", content=content, media_type=PDF
    )
