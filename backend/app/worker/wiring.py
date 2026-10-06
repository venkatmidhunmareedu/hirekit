"""The Worker's composition root: every real collaborator, built once and handed to the handlers.

The model mode is whatever `Settings` says (replay by default, live only from the process
environment with a key, which `Settings` checks at construction); the Gateway is the same one in
both, so a replay build needs no key and no network (docs/design/gateway-lld.md section 4).
"""

from collections.abc import Awaitable, Callable

import app.anonymizer as anonymizer
from app.core.config import Settings
from app.db.repositories import jobs, worker_writes
from app.db.repositories.gateway_ledger import GatewayLedger
from app.extraction import ResumeExtractor
from app.gateway import Gateway
from app.gateway.recordings import RecordingStore
from app.gateway.service import Transaction
from app.jobs.job_description import load_job_description
from app.prompts.criteria_prompt import CriteriaPromptBuilder
from app.prompts.kit_prompt import KitPromptBuilder
from app.prompts.scoring_parser import ScoreReplyParser
from app.prompts.scoring_prompt import ScoringPromptBuilder
from app.worker.handlers import build_handlers
from app.worker.handlers.kit import KitDeps
from app.worker.handlers.process_resume import ResumeDeps
from app.worker.handlers.propose_criteria import CriteriaDeps
from app.worker.handlers.scoring import ScoringDeps
from app.worker.loop import Handler
from app.worker.quotes import WhitespaceQuoteVerifier


def build_worker(
    settings: Settings, transaction: Transaction
) -> tuple[dict[str, Handler], Callable[[], Awaitable[None]]]:
    """The handler registry over a real Gateway, and the coroutine function that closes it."""
    gateway = Gateway(
        settings=settings,
        transaction=transaction,
        ledger=GatewayLedger(),
        store=RecordingStore(settings.recordings_dir),
    )
    scoring_prompt = ScoringPromptBuilder()
    criteria_prompt = CriteriaPromptBuilder()
    kit_prompt = KitPromptBuilder()
    scoring = ScoringDeps(
        gateway,
        worker_writes,
        jobs,
        anonymizer.load_anonymized,
        scoring_prompt,
        ScoreReplyParser(),
        WhitespaceQuoteVerifier(),
        scoring_prompt.prompt_version,
    )
    handlers = build_handlers(
        scoring,
        ResumeDeps(ResumeExtractor(), anonymizer, worker_writes),
        CriteriaDeps(
            gateway,
            worker_writes,
            jobs,
            load_job_description,
            criteria_prompt,
            criteria_prompt.prompt_version,
        ),
        KitDeps(
            gateway,
            worker_writes,
            jobs,
            load_job_description,
            kit_prompt,
            kit_prompt.prompt_version,
        ),
    )
    return handlers, gateway.aclose
