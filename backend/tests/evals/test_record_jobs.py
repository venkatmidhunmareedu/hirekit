"""`python -m app.evals.record --jobs`: the criteria, process_resume and kit recording jobs."""

import io
from decimal import Decimal
from pathlib import Path

import pytest

from app.evals.record import main, run_record
from app.gateway.errors import BudgetReachedError
from app.seed.data import SeedData, load_seed
from tests.evals.test_entrypoints import _writing
from tests.evals.test_prompts_run import backend
from tests.evals.test_run import EXPECTED, GOOD, FakeGateway, root
from tests.gateway.fakes import make_settings

__all__ = ["backend", "root"]


@pytest.fixture
def seed(root: Path) -> SeedData:
    return load_seed(root, EXPECTED)


async def _record(
    seed: SeedData, root: Path, backend: Path, tmp_path: Path, jobs: tuple[str, ...], *, smoke: bool
) -> tuple[int, int, str]:
    gateway = _writing(tmp_path, GOOD)
    out = io.StringIO()
    code = await run_record(
        gateway, seed, root, tmp_path, smoke=smoke, out=out, jobs=jobs, backend=backend
    )
    return code, len(gateway.requests), out.getvalue()


async def test_each_job_makes_one_call_per_case(
    seed: SeedData, root: Path, backend: Path, tmp_path: Path
) -> None:
    for job, calls in (("scoring", 4), ("process_resume", 1), ("criteria", 1), ("kit", 1)):
        (tmp_path / job).mkdir()
        code, made, _ = await _record(seed, root, backend, tmp_path / job, (job,), smoke=False)
        assert (code, made) == (0, calls), job


async def test_all_jobs_print_the_plan_and_the_counts(
    seed: SeedData, root: Path, backend: Path, tmp_path: Path
) -> None:
    jobs = ("scoring", "process_resume", "criteria", "kit")
    code, made, text = await _record(seed, root, backend, tmp_path, jobs, smoke=False)
    assert (code, made) == (0, 7)
    assert "plan: 7 calls (4 scoring, 1 process_resume, 1 criteria, 1 kit)" in text
    assert "7 recordings written" in text
    assert "make eval-prompts" in text


async def test_smoke_limits_every_job_to_one_call(
    seed: SeedData, root: Path, backend: Path, tmp_path: Path
) -> None:
    jobs = ("scoring", "process_resume", "criteria", "kit")
    code, made, text = await _record(seed, root, backend, tmp_path, jobs, smoke=True)
    assert (code, made) == (0, 4)
    assert "plan: 4 calls (1 scoring, 1 process_resume, 1 criteria, 1 kit)" in text


async def test_a_refusal_stops_the_run_with_exit_1(
    seed: SeedData, root: Path, backend: Path, tmp_path: Path
) -> None:
    gateway = FakeGateway(lambda _: BudgetReachedError(Decimal(8), Decimal(8)))
    out = io.StringIO()
    code = await run_record(
        gateway, seed, root, tmp_path, smoke=False, out=out, jobs=("kit",), backend=backend
    )
    assert code == 1
    assert "stopped" in out.getvalue()
    assert len(gateway.requests) == 1


async def test_the_new_jobs_keep_the_refusals(tmp_path: Path) -> None:
    out = io.StringIO()
    assert await main(["--jobs", "kit"], settings=make_settings(tmp_path), out=out) == 2
    with pytest.raises(SystemExit):
        await main(["--jobs", "nonsense"], settings=make_settings(tmp_path), out=out)
