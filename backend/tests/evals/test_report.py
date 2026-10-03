"""Report wording and determinism, on hand-built results."""

from app.evals.agreement import evaluate_agreement
from app.evals.nameswap import evaluate_name_swap
from app.evals.report import render_agreement_report, render_name_swap_report
from app.evals.run import CriterionScore, ResumeResult
from app.seed.data import SeedPair

KW = {"model_id": "model-x", "prompt_version": "v7", "run_date_label": "2026-01-02"}


def make(resume_id: str, value: int | None, text: str = "t") -> ResumeResult:
    s = CriterionScore("X", "failed" if value is None else "scored", value, "a quote", None)
    return ResumeResult(resume_id, "rola", text, (s,))


def agreement(good: bool) -> str:
    score = 2 if good else 0
    out = evaluate_agreement(
        [make("r1", score), make("r2", None)], {"r1": {"X": 2}, "r2": {"X": 2}}
    )
    return render_agreement_report(out, **KW)


def swap(good: bool) -> str:
    results = [make("a", 0, "Hi\nOne\n"), make("b", 1 if good else 4, "Hi\nTwo\n")]
    out = evaluate_name_swap(results, [SeedPair("a", "b", "origin-a", ("name",))])
    return render_name_swap_report(out, **KW)


def first_line(text: str) -> str:
    return text.splitlines()[0]


def test_agreement_heading_and_model() -> None:
    fail = agreement(True)  # one failed row of two: 50 percent, fails
    assert first_line(fail).startswith("# FAIL")
    assert "model-x" in fail
    assert "v7" in fail
    assert "2026-01-02" in fail
    ok = render_agreement_report(evaluate_agreement([make("r1", 2)], {"r1": {"X": 2}}), **KW)
    assert first_line(ok).startswith("# PASS")


def test_agreement_wording() -> None:
    text = agreement(False)
    for needle in (
        "another model of the same family that wrote the resumes and the scores",
        "consistency with a reference",
        "not ground truth about candidate quality",
        "80 percent threshold is proposed and to be confirmed after a baseline run",
        "Exact agreement",
        "Agreement within 1 point",
        "quadratic-weighted kappa",
        "Missing (failed) rows: 1",
        "| X |",
        "More than 1 point off",
        "| r1 | X | 2 | 0 | a quote |",
    ):
        assert needle in text, needle


def test_name_swap_heading_and_wording() -> None:
    bad = swap(False)
    assert first_line(bad).startswith("# FAIL")
    assert first_line(swap(True)).startswith("# PASS")
    assert "model-x" in bad
    for needle in (
        "removal of the named signals (name, email, profile link, pronouns, nickname, city)",
        "not absence of proxy bias",
        "Anonymization is a floor, not proof of fairness",
        "Identical anonymized text: 0 of 1 pairs",
        "origin-a",
        "-One",
        "+Two",
    ):
        assert needle in bad, needle


def test_deterministic_and_ascii() -> None:
    for render in (agreement, swap):
        a, b = render(False), render(False)
        assert a == b
        assert a.isascii()
        assert "—" not in a
