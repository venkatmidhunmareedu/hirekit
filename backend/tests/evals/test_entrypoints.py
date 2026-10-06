"""`python -m app.evals` and `python -m app.evals.record`: exit codes, refusals, call counts."""

import io
from collections.abc import Awaitable
from pathlib import Path

import pytest

from app.core.config import Settings
from app.evals.__main__ import EvalOutcome, run_evals
from app.evals.__main__ import main as eval_main
from app.evals.record import main as record_main
from app.evals.record import run_record
from app.gateway.errors import RecordingMissingError
from app.gateway.transport import Transport, TransportReply, TransportRequest
from app.gateway.types import GatewayRequest, GatewayResponse
from app.seed.data import SeedData, load_seed
from app.worker.handlers.scoring import ScoringGateway
from tests.evals.test_run import EXPECTED, GOOD, FakeGateway, always, root, scores_json, text_reply
from tests.gateway.fakes import DB, FakeLedger, make_gateway, make_settings

__all__ = ["root"]


@pytest.fixture
def seed(root: Path) -> SeedData:
    return load_seed(root, EXPECTED)


def _run(gateway: ScoringGateway, seed: SeedData, root: Path) -> Awaitable[EvalOutcome]:
    return run_evals(gateway, seed, root, model_id="m", prompt_version="v1", label="t")


async def test_all_pass_is_exit_0(seed: SeedData, root: Path) -> None:
    outcome = await _run(always(GOOD), seed, root)
    assert outcome.exit_code == 0
    assert outcome.agreement_report is not None
    assert outcome.agreement_report.startswith("# PASS")


async def test_a_mislabelled_scenario_is_exit_1(seed: SeedData, root: Path) -> None:
    far = scores_json((0, "Senior Python developer"), (0, "Wrote SQL reports."))
    outcome = await _run(always(far), seed, root)
    assert outcome.exit_code == 1
    assert outcome.agreement_report is not None
    assert outcome.agreement_report.startswith("# FAIL")


async def test_a_missing_recording_is_exit_2(seed: SeedData, root: Path) -> None:
    def missing(_: object) -> Exception:
        return RecordingMissingError("abc123")

    outcome = await _run(FakeGateway(missing), seed, root)
    assert outcome.exit_code == 2
    assert "abc123" in outcome.message
    assert "make record" in outcome.message


class _Boom(Transport):
    touched = False

    async def send(self, request: TransportRequest) -> TransportReply:
        _Boom.touched = True
        raise AssertionError("live transport touched")

    async def aclose(self) -> None:
        return None


async def test_replay_with_no_recordings_never_goes_live(
    seed: SeedData, root: Path, tmp_path: Path
) -> None:
    settings = make_settings(tmp_path / "empty")
    gateway = make_gateway(settings, FakeLedger(), transport_factory=_Boom)
    outcome = await _run(gateway, seed, root)
    assert outcome.exit_code == 2
    assert not _Boom.touched


async def test_main_refuses_live_mode(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, model_mode="live", openrouter_api_key="k")
    out = io.StringIO()
    assert await eval_main([], settings=settings, out=out) == 2
    assert "live" in out.getvalue()


def _rec_settings(tmp_path: Path, *, ci: bool) -> Settings:
    return Settings(_env_file=None, database_url=DB, recordings_dir=tmp_path, ci=ci)


async def test_record_refuses_without_record_responses(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, model_mode="live", openrouter_api_key="k")
    out = io.StringIO()
    assert await record_main([], settings=settings, out=out) == 2
    assert "RECORD_RESPONSES" in out.getvalue()


async def test_record_refuses_in_replay_mode(tmp_path: Path) -> None:
    out = io.StringIO()
    assert await record_main([], settings=make_settings(tmp_path), out=out) == 2


async def test_record_refuses_under_ci(tmp_path: Path) -> None:
    out = io.StringIO()
    assert await record_main([], settings=_rec_settings(tmp_path, ci=True), out=out) == 2
    assert "CI" in out.getvalue()


def _writing(directory: Path, text: str) -> FakeGateway:
    """A fake that, like the live gateway, leaves one recording file per call."""
    from app.gateway.types import Recording

    def answer(request: GatewayRequest) -> GatewayResponse:
        key = f"{len(list(directory.glob('*.json'))):064x}"
        recording = Recording.model_validate(
            {
                "key_version": 1,
                "request_key": key,
                "input_sha256": "0" * 64,
                "model": "m",
                "prompt_version": request.prompt_version,
                "schema_retry": request.schema_retry,
                "purpose": "scoring",
                "response": {
                    "text": text,
                    "input_tokens": 10,
                    "output_tokens": 10,
                    "finish_reason": "stop",
                },
            }
        )
        (directory / f"{key}.json").write_text(recording.model_dump_json(), encoding="utf-8")
        return text_reply(text)

    return FakeGateway(answer)


async def test_smoke_makes_one_call(seed: SeedData, root: Path, tmp_path: Path) -> None:
    gateway = _writing(tmp_path, GOOD)
    out = io.StringIO()
    assert await run_record(gateway, seed, root, tmp_path, smoke=True, out=out) == 0
    assert len(gateway.requests) == 1
    assert "1 recording written" in out.getvalue()
    assert "input tokens 10" in out.getvalue()


async def test_full_run_makes_one_call_per_resume(
    seed: SeedData, root: Path, tmp_path: Path
) -> None:
    gateway = _writing(tmp_path, GOOD)
    out = io.StringIO()
    assert await run_record(gateway, seed, root, tmp_path, smoke=False, out=out) == 0
    assert len(gateway.requests) == len(seed.resumes)
    assert f"{len(seed.resumes)} recordings written" in out.getvalue()
    assert "make eval" in out.getvalue()
