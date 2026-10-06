"""The real `seed/` tree: counts, the no-real-people rules, built files and the anonymizer."""

import re
from pathlib import Path

import pytest
from scripts.build_seed_resumes import DOCX_MEDIA_TYPE

from app.anonymizer import anonymize
from app.extraction import ResumeExtractor
from app.seed.data import SeedData, load_seed

SEED = Path(__file__).resolve().parents[3] / "seed"
MEDIA = {".pdf": "application/pdf", ".docx": DOCX_MEDIA_TYPE}
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+")
PHONE = re.compile(r"\b\d{3}-\d{4}\b")

# N-091: the anonymizer leaves many nicknames in place, so these name-swap pairs anonymize
# to different text (support-06 and support-09 also differ on a city the places pass does not
# know, Tehran and Dakar). Frozen on purpose: a fix shrinks the set and a regression grows it,
# and either shows up here. Update this set only together with the anonymizer change.
NICKNAME_GAP_PAIRS = frozenset(
    {
        "backend-01",
        "backend-02",
        "backend-04",
        "backend-05",
        "backend-06",
        "backend-07",
        "backend-08",
        "backend-09",
        "backend-10",
        "support-01",
        "support-03",
        "support-05",
        "support-06",
        "support-07",
        "support-09",
    }
)


@pytest.fixture(scope="module")
def data() -> SeedData:
    return load_seed(SEED)


def test_real_seed_loads_with_default_counts(data: SeedData) -> None:
    assert len(data.roles) == 2
    assert len(data.resumes) == 40
    assert len(data.pairs) == 20


def test_emails_phones_and_ascii(data: SeedData) -> None:
    for resume_id, text in data.resumes.items():
        assert text.isascii(), resume_id
        assert "—" not in text
        emails = EMAIL.findall(text)
        assert emails, resume_id
        assert all(e.endswith("@example.com") for e in emails), resume_id
        phones = PHONE.findall(text)
        assert phones, resume_id
        assert all(re.fullmatch(r"555-01\d\d", p) for p in phones), resume_id


def test_each_resume_has_one_built_file_with_its_words(data: SeedData) -> None:
    extractor = ResumeExtractor()
    for resume_id, text in data.resumes.items():
        files = [p for p in (SEED / "resumes").glob(f"{resume_id}.*") if p.suffix != ".txt"]
        assert len(files) == 1, resume_id
        out = " ".join(extractor.extract(files[0].read_bytes(), MEDIA[files[0].suffix]).split())
        for word in re.findall(r"[A-Za-z0-9@.]+", text):
            assert word in out, (resume_id, word)


def _identity(text: str) -> tuple[str, str, str]:
    name = text.splitlines()[0].split(" - ")[0].strip()
    return name, EMAIL.findall(text)[0], PHONE.findall(text)[0]


def test_anonymizer_removes_name_email_and_phone(data: SeedData) -> None:
    for resume_id, text in data.resumes.items():
        name, email, phone = _identity(text)
        out = anonymize(text).text.value
        assert name not in out, resume_id
        assert email not in out, resume_id
        assert phone not in out, resume_id


def test_pairs_whose_anonymized_text_differs_are_exactly_the_frozen_set(data: SeedData) -> None:
    differing = {
        p.base_id
        for p in data.pairs
        if anonymize(data.resumes[p.base_id]).text.value
        != anonymize(data.resumes[p.swap_id]).text.value
    }
    assert differing == NICKNAME_GAP_PAIRS
