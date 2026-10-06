"""The handler registry: job type to handler, built from the collaborators each one needs."""

from app.worker.handlers.kit import KitDeps, make_generate_kit, make_regenerate_question
from app.worker.handlers.process_resume import ResumeDeps, make_process_resume
from app.worker.handlers.propose_criteria import CriteriaDeps, make_propose_criteria
from app.worker.handlers.rescore import make_rescore
from app.worker.handlers.scoring import ScoringDeps
from app.worker.loop import Handler


def build_handlers(
    scoring: ScoringDeps, resume: ResumeDeps, criteria: CriteriaDeps, kit: KitDeps
) -> dict[str, Handler]:
    """One handler for each of the five job types."""
    return {
        "process_resume": make_process_resume(resume, scoring),
        "rescore": make_rescore(scoring),
        "propose_criteria": make_propose_criteria(criteria),
        "generate_kit": make_generate_kit(kit),
        "regenerate_question": make_regenerate_question(kit),
    }
