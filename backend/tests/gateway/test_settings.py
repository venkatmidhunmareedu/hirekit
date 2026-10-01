"""Gateway settings: replay by default, live only from the process environment, never in CI."""

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_RECORDINGS_DIR, Settings

DB = "postgresql+asyncpg://postgres:postgres@localhost:5432/test"


def make(**kw: object) -> Settings:
    return Settings(_env_file=None, database_url=DB, **kw)  # type: ignore[arg-type]  # test kwargs


def test_defaults_are_replay_and_free() -> None:
    settings = make()
    assert settings.model_mode == "replay"
    assert settings.ci is False
    assert settings.record_responses is False
    assert settings.gateway_timeout_seconds == 60
    assert settings.price_input_usd_per_mtok == Decimal(1)
    assert settings.price_output_usd_per_mtok == Decimal(5)


def test_provider_and_model_come_from_one_setting() -> None:
    """AC-US-02-001-2: one value names the model."""
    assert make().model_id == "anthropic/claude-haiku-4.5"
    assert make(model_id="other/model").model_id == "other/model"


def test_recordings_dir_default_is_absolute_and_inside_backend() -> None:
    assert DEFAULT_RECORDINGS_DIR.is_absolute()
    assert DEFAULT_RECORDINGS_DIR.name == "recordings"
    assert DEFAULT_RECORDINGS_DIR.parent.name == "backend"


def test_ci_rejects_live_mode_at_startup() -> None:
    """AC-US-02-003-4."""
    with pytest.raises(ValidationError, match="CI"):
        make(model_mode="live", ci=True, openrouter_api_key="k")


def test_ci_variable_in_the_environment_rejects_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("MODEL_MODE", "live")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    with pytest.raises(ValidationError, match="CI"):
        make()


def test_live_mode_needs_a_key() -> None:
    with pytest.raises(ValidationError, match="OPENROUTER_API_KEY"):
        make(model_mode="live")


def test_live_mode_from_the_process_environment_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_MODE", "live")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    assert make().model_mode == "live"


def test_mode_is_not_read_from_the_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HLD section 12: a stray MODEL_MODE=live in .env must not start live mode."""
    monkeypatch.delenv("MODEL_MODE", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"MODEL_MODE=live\nOPENROUTER_API_KEY=k\nDATABASE_URL={DB}\nMODEL_ID=from-file\n"
    )

    settings = Settings(_env_file=env_file)

    assert settings.model_mode == "replay"
    assert settings.model_id == "from-file"  # other values still come from the file


def test_api_key_is_a_secret_and_never_printed() -> None:
    settings = make(openrouter_api_key="sk-secret-value")
    assert "sk-secret-value" not in repr(settings)
    assert "sk-secret-value" not in str(settings.model_dump())


def test_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="GATEWAY_TIMEOUT_SECONDS"):
        make(gateway_timeout_seconds=0)
