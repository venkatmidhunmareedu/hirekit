"""The handler registry: job type to handler, built from the collaborators each one needs."""

from app.worker.handlers.rescore import make_rescore
from app.worker.handlers.scoring import ScoringDeps
from app.worker.loop import Handler


def build_handlers(scoring: ScoringDeps) -> dict[str, Handler]:
    """`rescore` now; the later handler items add their entries here."""
    return {"rescore": make_rescore(scoring)}
