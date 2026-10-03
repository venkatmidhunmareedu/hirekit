"""Markdown reports for the two evals; no clock, the caller passes the date label."""

from app.evals.agreement import AgreementResult
from app.evals.nameswap import NameSwapResult


def _verdict(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def _cell(value: int | None) -> str:
    return "failed" if value is None else str(value)


def _pct(value: float) -> str:
    return f"{value * 100:.1f} percent"


def render_agreement_report(
    result: AgreementResult, *, model_id: str, prompt_version: str, run_date_label: str
) -> str:
    """The agreement eval as markdown; the heading starts with PASS or FAIL."""
    kappa = "not computable (no scored rows)" if result.kappa is None else f"{result.kappa:.3f}"
    lines = [
        f"# {_verdict(result.passed)}: agreement eval, model {model_id}",
        "",
        f"- Model: {model_id}",
        f"- Prompt version: {prompt_version}",
        f"- Run: {run_date_label}",
        "",
        "## What this measures",
        "",
        "The labels come from another model of the same family that wrote the resumes and the "
        "scores. This result measures consistency with a reference. It is not ground truth "
        "about candidate quality.",
        "",
        f"The {result.threshold * 100:.0f} percent threshold is proposed and to be confirmed "
        "after a baseline run. The pass rule is agreement within 1 point at or above it.",
        "",
        "## Results",
        "",
        f"- Rows: {result.total}",
        f"- Exact agreement: {_pct(result.exact)}",
        f"- Agreement within 1 point: {_pct(result.within_one)}",
        f"- Weighted kappa (quadratic-weighted kappa): {kappa}",
        f"- Missing (failed) rows: {result.missing}",
        f"- Failed rows: {result.failed}",
        f"- No-evidence rows: {result.no_evidence}",
        "",
        "## Per criterion",
        "",
        "| Criterion | Rows | Exact | Within 1 |",
        "| --- | --- | --- | --- |",
        *(
            f"| {c.name} | {c.total} | {_pct(c.exact)} | {_pct(c.within_one)} |"
            for c in result.per_criterion
        ),
        "",
        "## More than 1 point off",
        "",
    ]
    if result.off_rows:
        lines += [
            "| Resume | Criterion | Label | Score | Quote |",
            "| --- | --- | --- | --- | --- |",
            *(
                f"| {r.resume_id} | {r.criterion} | {r.label} | {r.score} | {r.quote or ''} |"
                for r in result.off_rows
            ),
        ]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def render_name_swap_report(
    result: NameSwapResult, *, model_id: str, prompt_version: str, run_date_label: str
) -> str:
    """The name-swap eval as markdown; the heading starts with PASS or FAIL."""
    failed = [p for p in result.pairs if not p.passed]
    lines = [
        f"# {_verdict(result.passed)}: name-swap eval, model {model_id}",
        "",
        f"- Model: {model_id}",
        f"- Prompt version: {prompt_version}",
        f"- Run: {run_date_label}",
        "",
        "## What this shows",
        "",
        "This shows removal of the named signals (name, email, profile link, pronouns, "
        "nickname, city), and not absence of proxy bias. Anonymization is a floor, "
        "not proof of fairness.",
        "",
        "## Results",
        "",
        f"- Pairs passed: {len(result.pairs) - len(failed)} of {len(result.pairs)}",
        f"- Identical anonymized text: {result.identical_count} of {len(result.pairs)} pairs",
        "",
        "## Failed pairs",
        "",
    ]
    if not failed:
        lines.append("None.")
    for p in failed:
        lines += [f"### {p.pair_id} ({p.base_id} vs {p.swap_id})", ""]
        lines += [
            f"- {d.criterion}: base {_cell(d.base)}, swap {_cell(d.swap)}" for d in p.differences
        ]
        lines += ["", "```diff", p.text_diff, "```", ""]
    return "\n".join(lines) + "\n"
