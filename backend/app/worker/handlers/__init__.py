"""The handler registry: job type to handler, built from the collaborators each one needs."""

from app.worker.handlers.process_resume import ResumeDeps, make_process_resume
from app.worker.handlers.propose_criteria import CriteriaDeps, make_propose_criteria
from app.worker.handlers.rescore import make_rescore
from app.worker.handlers.scoring import ScoringDeps
from app.worker.loop import Handler


def build_handlers(
    scoring: ScoringDeps, resume: ResumeDeps, criteria: CriteriaDeps
) -> dict[str, Handler]:
    """`process_resume`, `rescore` and `propose_criteria`; the kit item adds its entries here."""
    return {
        "process_resume": make_process_resume(resume, scoring),
        "rescore": make_rescore(scoring),
        "propose_criteria": make_propose_criteria(criteria),
    }
