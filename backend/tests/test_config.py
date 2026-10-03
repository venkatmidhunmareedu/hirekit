"""Settings fail fast and name the problem."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

DB = "postgresql+asyncpg://postgres:postgres@localhost:5432/test"


def test_defaults() -> None:
    settings = Settings(_env_file=None, database_url=DB)

    assert settings.env == "development"
    assert settings.port == 8080
    assert settings.log_level == "info"
    assert settings.log_format == "json"


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("PORT", "9000")

    settings = Settings(_env_file=None, database_url=DB)

    assert settings.log_level == "debug"
    assert settings.port == 9000


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("LOG_LEVEL", "loud"),
        ("ENV", "staging"),
        ("PORT", "eighty"),
    ],
)
def test_invalid_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError, match=variable.lower()):
        Settings(_env_file=None, database_url=DB)


def test_sync_driver_is_rejected() -> None:
    with pytest.raises(ValidationError, match="postgresql\\+asyncpg"):
        Settings(_env_file=None, database_url="postgresql://postgres:postgres@localhost/test")


def test_model_base_url_is_unset_by_default() -> None:
    settings = Settings(_env_file=None, database_url=DB)

    assert settings.model_base_url is None


def test_model_base_url_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_BASE_URL", "https://proxy.example.com/v1")

    settings = Settings(_env_file=None, database_url=DB)

    assert settings.model_base_url == "https://proxy.example.com/v1"


@pytest.mark.parametrize(
    "url", ["http://localhost:8000/v1", "http://127.0.0.1:8000/v1", "http://[::1]:8000/v1"]
)
def test_model_base_url_allows_plain_http_on_loopback(url: str) -> None:
    settings = Settings(_env_file=None, database_url=DB, model_base_url=url)

    assert settings.model_base_url == url


def test_model_base_url_strips_a_trailing_slash() -> None:
    settings = Settings(
        _env_file=None, database_url=DB, model_base_url="https://proxy.example.com/v1/"
    )

    assert settings.model_base_url == "https://proxy.example.com/v1"


@pytest.mark.parametrize(
    ("url", "rule"),
    [
        ("http://proxy.example.com/v1?k=s3cret", "https"),
        ("ftp://proxy.example.com/v1?k=s3cret", "http"),
        ("https://user:s3cret@proxy.example.com/v1", "credentials"),
        ("https:///v1?k=s3cret", "host"),
    ],
)
def test_model_base_url_rule_failures_do_not_echo_the_url(url: str, rule: str) -> None:
    with pytest.raises(ValidationError, match=rule) as caught:
        Settings(_env_file=None, database_url=DB, model_base_url=url)

    message = str(caught.value)
    assert "s3cret" not in message
    assert "proxy.example.com" not in message
