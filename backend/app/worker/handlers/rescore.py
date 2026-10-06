"""`rescore`: run the scoring step again for one candidate.

The candidate keeps its `processing_status` (`done`) on every end: a failed or stale rescore
leaves its earlier scores valid (docs/design/worker-lld.md section 3).
"""

from app.worker.context import JobContext
from app.worker.handlers.scoring import ScoringDeps, score_candidate
from app.worker.loop import Handler
from app.worker.outcome import Outcome


def make_rescore(deps: ScoringDeps) -> Handler:
    async def rescore(ctx: JobContext) -> Outcome:
        return await score_candidate(ctx, deps, mark_done=False)

    return rescore
