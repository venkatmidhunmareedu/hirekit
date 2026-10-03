"""Name discovery and removal: the candidate's own name goes, everyone else's and evidence stay."""

import subprocess
import sys
from pathlib import Path

import pytest

from app.anonymizer import anonymize
from app.anonymizer.names import MAX_NAME_CHARS, discover, mask_names, split_parts
from app.anonymizer.pipeline import PASSES
from app.anonymizer.tokens import NameSet, apply_replacements

SHY, NBSP, ZWSP, LIG_FI, DOTTED_I = chr(0xAD), chr(0xA0), chr(0x200B), chr(0xFB01), chr(0x130)


PAD = "Built a thing.\n" * 5  # pushes what follows out of the header block


def out(raw: str) -> str:
    return anonymize(raw).text.value


def test_the_pass_is_registered() -> None:
    assert mask_names in PASSES


def test_the_full_name_is_masked_wherever_it_appears() -> None:
    raw = "Jane Doe\nSenior Engineer\nJANE DOE led the work. jane doe shipped it.\nSkills: Python"
    assert (
        out(raw)
        == "[NAME]\nSenior Engineer\n[NAME] led the work. [NAME] shipped it.\nSkills: Python"
    )


def test_each_name_part_alone_is_masked() -> None:
    raw = "Jane Doe\nJane built it. Doe's team grew. Ask Doe."
    assert out(raw) == "[NAME]\n[NAME] built it. [NAME]'s team grew. Ask [NAME]."


def test_initials_and_reversed_order_are_masked() -> None:
    raw = "Jane Doe\nAuthor: J. Doe\nCited as Doe, J.\nListed: Doe, Jane\nBuilt it\nIn the body: JD"
    expected = "[NAME]\nAuthor: [NAME]\nCited as [NAME]\nListed: [NAME]\nBuilt it\nIn the body: JD"
    assert out(raw) == expected


def test_a_hyphenated_and_a_multi_part_name_are_masked() -> None:
    raw = "Mary-Ann van der Berg\nMary-Ann led it. Berg shipped it. Ask Mary Ann."
    assert out(raw) == "[NAME]\n[NAME] led it. [NAME] shipped it. Ask [NAME]."


def test_the_name_in_a_repeated_header_and_footer_is_masked() -> None:
    raw = "Page header\nJane Doe\nBuilt services.\nPage 2\nJane Doe\nRegards,\nJane"
    assert out(raw).count("Jane") == 0
    assert out(raw).count("Doe") == 0


def test_the_name_inside_an_email_address_is_masked() -> None:
    raw = "Jane Doe\njane.doe@example.com\njdoe@example.com"
    assert out(raw) == "[NAME]\n[EMAIL]\n[EMAIL]"


def test_the_name_inside_a_profile_url_is_masked() -> None:
    raw = "Jane Doe\nlinkedin.com/in/jane-doe\nhttps://example.com/~janedoe"
    assert out(raw) == "[NAME]\n[URL]\n[URL]"


def test_a_common_word_name_is_masked_in_name_positions_and_not_in_running_text() -> None:
    raw = "Will Young\nName: Will\n" + PAD + "I will lead a young team.\nRegards,\nWill"
    assert (
        out(raw) == "[NAME]\nName: [NAME]\n" + PAD + "I will lead a young team.\nRegards,\n[NAME]"
    )


@pytest.mark.parametrize("name", ["Will Young", "Grace Hall", "Rose King", "Mark Swift"])
def test_a_common_word_name_never_fails_the_candidate(name: str) -> None:
    result = anonymize(f"{name}\nBuilt a payments service in Python.\nWrote about {name}.")
    assert result.text.value == "[NAME]\nBuilt a payments service in Python.\nWrote about [NAME]."
    assert result.identity_name == name
    assert result.report.name_found is True


def test_running_text_with_will_young_rose_mark_swift_is_kept_whole() -> None:
    raw = (
        "Jane Doe\nI will mark a swift, young rose as done, and will rose to lead the king's hall."
    )
    assert out(raw).split("\n")[1] == raw.split("\n")[1]


def test_initials_are_masked_only_in_name_positions_and_js_cs_ml_ai_qa_pm_jd_are_kept() -> None:
    raw = (
        "Jane Doe\nJD\n"
        + PAD
        + "Built JS, CS, ML, AI, QA and PM tools.\nRead the JD and the J.D. notes."
    )
    assert (
        out(raw)
        == "[NAME]\n[NAME]\n"
        + PAD
        + "Built JS, CS, ML, AI, QA and PM tools.\nRead the JD and the J.D. notes."
    )


def test_nicknames_of_the_first_name_are_masked() -> None:
    raw = "Robert Hale\nRobert led it. Bob shipped it. Bobby tested it."
    assert out(raw) == "[NAME]\n[NAME] led it. [NAME] shipped it. [NAME] tested it."


@pytest.mark.parametrize(
    "header",
    [
        "Resume\nJane Doe",
        "Curriculum Vitae\nJane Doe",
        "Senior Software Engineer\nJane Doe",
        "CV\nJane Doe",
    ],
)
def test_discovery_skips_resume_curriculum_vitae_and_job_titles(header: str) -> None:
    assert discover(header + "\nPython").full == "Jane Doe"


def test_a_discovered_name_is_escaped_and_capped_so_it_can_never_be_a_pattern() -> None:
    odd = NameSet("A.* (B+)", frozenset({"a.*"}))
    assert mask_names("A.* (B+) and Axxxx", odd) == mask_names("A.* (B+) and Axxxx", odd)
    assert mask_names("anything", NameSet("x" * MAX_NAME_CHARS, frozenset({"x"}))) == []
    assert discover("Jane " + "D" * 100 + "\nPython").full is None


def test_a_ligature_a_soft_hyphen_and_a_no_break_space_inside_a_name_still_match() -> None:
    raw = f"Jane Doe\nJ{SHY}ane{NBSP}Doe and Do{ZWSP}e built {LIG_FI}nance tools."
    assert out(raw) == "[NAME]\n[NAME] and [NAME] built finance tools."


def test_a_dotted_capital_i_name_keeps_offsets_correct() -> None:
    raw = f"{DOTTED_I}lkay Demir\n{DOTTED_I}LKAY built it, {DOTTED_I}lkay shipped it."
    assert out(raw) == "[NAME]\n[NAME] built it, [NAME] shipped it."


def test_the_name_is_found_from_a_name_field_the_first_lines_and_the_email() -> None:
    assert discover("Name: Jane Doe\nPython").full == "Jane Doe"
    assert discover("Candidate: Jane Doe\nPython").full == "Jane Doe"
    assert discover("Jane Doe | Engineer\nPython").full == "Jane Doe"
    assert discover("Mail: jane.doe@example.com\nBuilt things.").full == "Jane Doe"
    assert discover("Python developer\nSan Francisco\njohn.smith@x.io").full == "John Smith"


def test_identity_name_is_returned_for_the_reveal_and_none_when_absent() -> None:
    assert anonymize("Jane Doe\nBuilt things.").identity_name == "Jane Doe"
    none = anonymize("built a payments service in python.")
    assert none.identity_name is None
    assert none.report.name_found is False


def test_another_persons_name_such_as_a_referee_is_kept() -> None:
    raw = "Jane Doe\nReferee: Peter Hughes, manager at Acme."
    assert out(raw) == "[NAME]\nReferee: Peter Hughes, manager at Acme."


def test_swapping_the_candidate_name_gives_identical_text() -> None:
    body = "\nBuilt payments. Mail {m}. Wrote {n} twice, {n}.\n"
    a = out("Jane Doe" + body.format(m="jane.doe@x.com", n="Jane Doe"))
    b = out("Priya Raman" + body.format(m="priya.raman@x.com", n="Priya Raman"))
    assert a == b


def test_the_split_puts_common_words_and_short_parts_in_name_positions_only() -> None:
    always, position_only = split_parts("Will Young")
    assert not always & {"will", "young"}
    assert {"will", "young", "bill"} <= position_only
    assert split_parts("Jane Doe")[0] == {"jane", "doe"}


def test_the_replacements_apply_with_no_gap_between_a_name_and_its_variants() -> None:
    text = "Jane Doe\nDoe, Jane"
    names = discover(text)
    assert apply_replacements(text, mask_names(text, names))[0] == "[NAME]\n[NAME]"


def test_names_adversarial_input_finishes_quickly() -> None:
    """A regex runs in C and cannot be interrupted, so the proof is a subprocess with a timeout."""
    code = (
        "from app.anonymizer.names import discover, mask_names\n"
        "n = 150_000\n"
        "for s in ['Jane Doe\\n' + 'Jane ' * (n // 5), 'Jane Doe\\n' + 'J.' * (n // 2),"
        " 'Jane Doe\\n' + 'Doe,' * (n // 4), 'Jane Doe\\n' + ' ' * n + 'Doe', 'a ' * (n // 2),"
        " 'Jane Doe\\n' + 'Jane\\n' * (n // 5), 'Name:' * (n // 5), 'Regards,\\n' * (n // 9)]:\n"
        "    mask_names(s, discover(s))\n"
    )
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-c", code],
        check=True,
        timeout=60,
        cwd=Path(__file__).parents[2],
    )
