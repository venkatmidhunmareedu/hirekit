"""The handler registry: job type to handler, built from the collaborators each one needs."""

from app.worker.handlers.process_resume import ResumeDeps, make_process_resume
from app.worker.handlers.rescore import make_rescore
from app.worker.handlers.scoring import ScoringDeps
from app.worker.loop import Handler


def build_handlers(scoring: ScoringDeps, resume: ResumeDeps) -> dict[str, Handler]:
    """`process_resume` and `rescore` now; the later handler items add their entries here."""
    return {
        "process_resume": make_process_resume(resume, scoring),
        "rescore": make_rescore(scoring),
    }
