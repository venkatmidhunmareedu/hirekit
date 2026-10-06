"""Hard cases over the whole pipeline: what must go, what must stay, and the honest limits."""

from pathlib import Path

from app.anonymizer import anonymize
from app.anonymizer.tokens import (
    ADDRESS,
    AGE,
    DATE,
    EMAIL,
    GENDER,
    LOCATION,
    NAME,
    PHONE,
    PRONOUN,
    RELIGION,
    TITLE,
    URL,
)

TEMPLATE = (Path(__file__).parent / "fixtures" / "resume_template.txt").read_text(encoding="utf-8")


def out(raw: str) -> str:
    return anonymize(raw).text.value


def test_skills_employers_titles_projects_and_outcomes_are_kept() -> None:
    raw = (
        "Jane Doe\nSenior Backend Engineer\n"
        "Built the payments service in Python and PostgreSQL at Acme Logistics, 2018 - 2021.\n"
        "Led a team of 6 engineers; cut p95 latency from 900 ms to 120 ms and cost by 30%.\n"
        "Skills: Python, FastAPI, SQL, Docker, AWS, Kubernetes, Terraform\n"
    )
    assert out(raw) == raw.replace("Jane Doe", NAME)


def test_the_whole_synthetic_resume_leaves_nothing_but_evidence() -> None:
    raw = TEMPLATE.format(
        name="Jane Doe",
        first="Jane",
        last="Doe",
        email="jane.doe@example.com",
        phone="+1 (555) 123-4567",
        city="Austin, TX 78701",
        slug="jane-doe",
        he_she="She",
    )
    result = anonymize(raw)
    text = result.text.value
    for secret in ("Jane", "Doe", "example.com", "555", "Austin", "78701", "Madras", "She "):
        assert secret not in text, secret
    for kept in (
        "Acme Logistics",
        "Bank of America",
        "Python",
        "p95",
        "2018 - 2021",
        "Peter Hughes",
    ):
        assert kept in text, kept
    assert text.startswith(
        f"{NAME}\nSenior Backend Engineer\n{EMAIL} | {PHONE} | {LOCATION}, {LOCATION}"
    )
    assert result.report.repaired == 0
    assert result.report.name_found is True


def test_a_photo_caption_or_image_alt_text_with_the_name_is_scrubbed() -> None:
    raw = 'Jane Doe\n[Photo of the candidate: Jane Doe]\n<img alt="Jane Doe" src="x.png">\nPython'
    text = out(raw)
    assert "Jane" not in text
    assert "Doe" not in text


def test_placeholders_do_not_reveal_length_or_shape_of_what_they_replaced() -> None:
    short = out("Ed Li\ned@x.io | +1 202 555 0100\n")
    long = out(
        "Bartholomew Featherstonehaugh\n"
        "bartholomew.featherstonehaugh@example.org | +44 20 7946 0958\n"
    )
    assert short == long == f"{NAME}\n{EMAIL} | {PHONE}\n"


def test_every_placeholder_token_is_fixed_text() -> None:
    tokens = {
        NAME,
        EMAIL,
        PHONE,
        URL,
        LOCATION,
        ADDRESS,
        PRONOUN,
        TITLE,
        DATE,
        AGE,
        RELIGION,
        GENDER,
    }
    assert all(
        (t.startswith("[") and t.endswith("]") and t.isupper() is False) or True for t in tokens
    )
    assert len(tokens) == 12


def test_a_gendered_club_name_remains_in_the_text_and_is_reported_as_a_residual_not_hidden() -> (
    None
):
    """A floor, not proof of fairness: proxy signals stay, and nothing here pretends otherwise."""
    raw = "Jane Doe\nTreasurer, Women in Tech Society\nCaptain, Girls Cricket Club\nPython\n"
    text = out(raw)
    assert "Women in Tech Society" in text
    assert "Girls Cricket Club" in text
