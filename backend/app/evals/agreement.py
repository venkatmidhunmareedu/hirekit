"""Agreement between reference labels and model scores, over already-computed results."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.evals.metrics import (
    exact_agreement,
    quadratic_weighted_kappa,
    within_one_agreement,
)
from app.evals.run import CriterionScore, ResumeResult


@dataclass(frozen=True, slots=True)
class CriterionAgreement:
    name: str
    total: int
    exact: float
    within_one: float


@dataclass(frozen=True, slots=True)
class OffRow:
    """A scored row more than one point from its label."""

    resume_id: str
    criterion: str
    label: int
    score: int
    quote: str | None


@dataclass(frozen=True, slots=True)
class AgreementResult:
    passed: bool
    threshold: float
    total: int
    exact: float
    within_one: float
    kappa: float | None
    missing: int
    failed: int
    no_evidence: int
    per_criterion: tuple[CriterionAgreement, ...]
    off_rows: tuple[OffRow, ...]


def evaluate_agreement(
    results: Sequence[ResumeResult],
    labels: Mapping[str, Mapping[str, int]],
    *,
    threshold: float = 0.8,
) -> AgreementResult:
    """Pair every score with its label; passed when within-one agreement reaches the threshold."""
    by_id = {r.resume_id: r for r in results}
    for resume_id in sorted(set(by_id) ^ set(labels)):
        side = "label" if resume_id in by_id else "result"
        raise ValueError(f"{resume_id}: no {side}")
    rows: list[tuple[str, str, int, CriterionScore]] = []
    for resume_id in sorted(by_id):
        scores = {s.name: s for s in by_id[resume_id].scores}
        if set(scores) != set(labels[resume_id]):
            raise ValueError(f"{resume_id}: criteria of result and label rows differ")
        rows.extend((resume_id, n, labels[resume_id][n], scores[n]) for n in sorted(scores))

    labs = [r[2] for r in rows]
    vals = [r[3].value for r in rows]
    kappa_metrics = (
        quadratic_weighted_kappa(labs, vals) if any(v is not None for v in vals) else None
    )
    per_criterion = []
    for name in sorted({r[1] for r in rows}):
        sub = [r for r in rows if r[1] == name]
        sub_l = [r[2] for r in sub]
        sub_v = [r[3].value for r in sub]
        per_criterion.append(
            CriterionAgreement(
                name, len(sub), exact_agreement(sub_l, sub_v), within_one_agreement(sub_l, sub_v)
            )
        )
    within = within_one_agreement(labs, vals)
    return AgreementResult(
        passed=within >= threshold,
        threshold=threshold,
        total=len(rows),
        exact=exact_agreement(labs, vals),
        within_one=within,
        kappa=None if kappa_metrics is None else kappa_metrics.value,
        missing=sum(1 for v in vals if v is None),
        failed=sum(1 for r in rows if r[3].status == "failed"),
        no_evidence=sum(1 for r in rows if r[3].status == "no_evidence"),
        per_criterion=tuple(per_criterion),
        off_rows=tuple(
            OffRow(rid, name, lab, s.value, s.quote)
            for rid, name, lab, s in rows
            if s.value is not None and abs(lab - s.value) > 1
        ),
    )
