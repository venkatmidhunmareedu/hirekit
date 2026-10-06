"""The seed users: password choice, the create/keep/reset decision and the output line."""

import io
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import pytest

from app.core.config import Settings
from app.seed import __main__ as seed_main
from app.seed.users import (
    USERS,
    SeedError,
    UserOutcome,
    check_environment,
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
    second, second_generated = choose_password(RECRUITER, {"SEED_PASSWORD_RECRUITER": ""})

    assert generated is True
    assert len(first) >= 20
    assert second_generated is True
    assert len(second) >= 20
    assert first != second


def test_the_variable_overrides_only_its_own_user() -> None:
    env = {"SEED_PASSWORD_RECRUITER": "chosen-password-16"}

    assert choose_password(RECRUITER, env) == ("chosen-password-16", False)
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


def test_a_chosen_password_shorter_than_16_is_refused_without_echoing_it() -> None:
    with pytest.raises(SeedError) as caught:
        choose_password(RECRUITER, {"SEED_PASSWORD_RECRUITER": "short-secret-15"})

    assert "SEED_PASSWORD_RECRUITER" in str(caught.value)
    assert "short-secret-15" not in str(caught.value)


def test_a_chosen_password_of_16_is_accepted() -> None:
    value = "a" * 16

    assert choose_password(RECRUITER, {"SEED_PASSWORD_RECRUITER": value}) == (value, False)


def test_generating_is_refused_when_not_allowed_and_names_the_variable() -> None:
    with pytest.raises(SeedError, match="SEED_PASSWORD_RECRUITER"):
        choose_password(RECRUITER, {}, allow_generate=False)


def test_a_chosen_password_needs_no_terminal() -> None:
    value = "b" * 16

    assert choose_password(RECRUITER, {"SEED_PASSWORD_RECRUITER": value}, allow_generate=False) == (
        value,
        False,
    )


BOTH = {"SEED_PASSWORD_RECRUITER": "r" * 16, "SEED_PASSWORD_INTERVIEWER": "i" * 16}


@pytest.mark.parametrize("env_name", ["development", "test"])
def test_development_and_test_pass_the_guard(env_name: str) -> None:
    check_environment(env_name, allow_production=False, environ={})


@pytest.mark.parametrize("env_name", ["production", "staging", None])
def test_other_and_unset_environments_are_refused(env_name: str | None) -> None:
    with pytest.raises(SeedError, match="--allow-production"):
        check_environment(env_name, allow_production=False, environ=BOTH)


@pytest.mark.parametrize("missing", list(BOTH))
def test_the_flag_without_both_passwords_is_refused(missing: str) -> None:
    environ = {k: v for k, v in BOTH.items() if k != missing}

    with pytest.raises(SeedError, match=missing):
        check_environment("production", allow_production=True, environ=environ)


def test_the_flag_with_both_passwords_is_allowed() -> None:
    check_environment("production", allow_production=True, environ=BOTH)
    check_environment(None, allow_production=True, environ=BOTH)


class _Tty(io.StringIO):
    def __init__(self, tty: bool) -> None:
        super().__init__()
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


class _Engine:
    async def dispose(self) -> None:
        return None


class _Factory:
    @asynccontextmanager
    async def begin(self) -> AsyncIterator[None]:
        yield None


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """main() with the database replaced; `seen` records the seed_users call."""
    seen: dict[str, object] = {"engines": 0}

    def make_engine(_settings: Settings) -> _Engine:
        seen["engines"] = int(str(seen["engines"])) + 1
        return _Engine()

    async def run_seed(_factory: object) -> seed_main.SeedResult:
        return seed_main.SeedResult(roles_created=0, candidates_created=0)

    async def seed_users(
        _session: object, env: Mapping[str, str], *, reset: bool, allow_generate: bool
    ) -> list[UserOutcome]:
        seen["allow_generate"] = allow_generate
        return [UserOutcome("a@hirekit.local", "recruiter", "created", "pw-generated")]

    monkeypatch.setattr(seed_main, "make_engine", make_engine)
    monkeypatch.setattr(seed_main, "make_session_factory", lambda _e: _Factory())
    monkeypatch.setattr(seed_main, "run_seed", run_seed)
    monkeypatch.setattr(seed_main, "seed_users", seed_users)
    monkeypatch.setattr(seed_main, "configure_logging", lambda *_a: None)
    monkeypatch.delenv("ENV", raising=False)
    return seen


def _settings(monkeypatch: pytest.MonkeyPatch, env: str | None) -> None:
    if env is not None:
        monkeypatch.setenv("ENV", env)
    settings = Settings(_env_file=None, database_url="postgresql+asyncpg://u:p@localhost:5432/x")
    monkeypatch.setattr(seed_main, "get_settings", lambda: settings)


async def test_main_refuses_production_before_touching_the_database(
    monkeypatch: pytest.MonkeyPatch, wired: dict[str, object]
) -> None:
    _settings(monkeypatch, "production")

    with pytest.raises(SystemExit) as caught:
        await seed_main.main([])

    assert caught.value.code not in (0, None)
    assert wired["engines"] == 0


async def test_main_refuses_an_unset_environment(
    monkeypatch: pytest.MonkeyPatch, wired: dict[str, object]
) -> None:
    _settings(monkeypatch, None)

    with pytest.raises(SystemExit):
        await seed_main.main([])

    assert wired["engines"] == 0


async def test_main_prints_a_generated_password_only_to_a_terminal(
    monkeypatch: pytest.MonkeyPatch, wired: dict[str, object]
) -> None:
    _settings(monkeypatch, "development")
    out = _Tty(tty=True)
    monkeypatch.setattr("sys.stdout", out)

    await seed_main.main([])

    assert wired["allow_generate"] is True
    assert "password: pw-generated" in out.getvalue()


async def test_main_does_not_generate_when_stdout_is_not_a_terminal(
    monkeypatch: pytest.MonkeyPatch, wired: dict[str, object]
) -> None:
    _settings(monkeypatch, "development")
    monkeypatch.setattr("sys.stdout", _Tty(tty=False))

    await seed_main.main([])

    assert wired["allow_generate"] is False


async def test_main_exits_with_the_message_when_a_password_is_refused(
    monkeypatch: pytest.MonkeyPatch, wired: dict[str, object]
) -> None:
    _settings(monkeypatch, "development")

    async def refuse(*_a: object, **_k: object) -> list[UserOutcome]:
        raise SeedError("SEED_PASSWORD_RECRUITER must be set")

    monkeypatch.setattr(seed_main, "seed_users", refuse)

    with pytest.raises(SystemExit) as caught:
        await seed_main.main([])

    assert "SEED_PASSWORD_RECRUITER" in str(caught.value.code)


async def test_main_allows_production_with_the_flag_and_both_passwords(
    monkeypatch: pytest.MonkeyPatch, wired: dict[str, object]
) -> None:
    _settings(monkeypatch, "production")
    for name, value in BOTH.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("sys.stdout", _Tty(tty=False))

    await seed_main.main(["--allow-production"])

    assert wired["engines"] == 1
    assert wired["allow_generate"] is False
