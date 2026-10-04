"""The seed users: password choice, the create/keep/reset decision and the output line."""

from app.seed.users import (
    USERS,
    UserOutcome,
    choose_password,
    decide,
    format_outcome,
)

RECRUITER, INTERVIEWER = USERS


def test_the_two_users_are_one_recruiter_and_one_interviewer() -> None:
    assert [u.role for u in USERS] == ["recruiter", "interviewer"]
    assert all(u.email.endswith("@hirekit.local") for u in USERS)


def test_a_password_is_generated_when_the_variable_is_unset_or_empty() -> None:
    first, generated = choose_password(RECRUITER, {})
    second, _ = choose_password(RECRUITER, {"SEED_PASSWORD_RECRUITER": ""})

    assert generated is True
    assert len(first) >= 20
    assert first != second


def test_the_variable_overrides_only_its_own_user() -> None:
    env = {"SEED_PASSWORD_RECRUITER": "chosen-pw"}

    assert choose_password(RECRUITER, env) == ("chosen-pw", False)
    assert choose_password(INTERVIEWER, env)[1] is True


def test_decide_keeps_an_existing_user_unless_reset() -> None:
    assert decide(exists=False, reset=False) == "created"
    assert decide(exists=False, reset=True) == "created"
    assert decide(exists=True, reset=False) == "kept"
    assert decide(exists=True, reset=True) == "reset"


def test_the_password_is_printed_only_when_generated() -> None:
    made = UserOutcome("a@hirekit.local", "recruiter", "created", "pw-123")
    given = UserOutcome("a@hirekit.local", "recruiter", "reset", None)
    kept = UserOutcome("a@hirekit.local", "recruiter", "kept", None)

    assert format_outcome(made) == "user created: a@hirekit.local (recruiter) password: pw-123"
    assert format_outcome(given) == "user reset: a@hirekit.local (recruiter)"
    assert format_outcome(kept) == "user kept: a@hirekit.local (recruiter)"
