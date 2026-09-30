"""Process configuration from the environment.

Construction fails fast and names every invalid variable at once. Secrets
have no defaults. `get_settings` is the one module-level singleton.
"""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import PostgresDsn, SecretStr, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

Env = Literal["development", "test", "production"]
ModelMode = Literal["replay", "live"]
# backend/recordings, resolved from this file so a Worker started elsewhere
# still writes into the repository (docs/design/gateway-lld.md section 7).
DEFAULT_RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "recordings"
LogLevel = Literal["debug", "info", "warning", "error"]
LogFormat = Literal["json", "console"]


class _DotenvWithoutMode(PydanticBaseSettingsSource):
    """The .env source minus `model_mode`: live mode is switched on per process (HLD section 12)."""

    def __init__(self, inner: PydanticBaseSettingsSource) -> None:
        super().__init__(inner.settings_cls)
        self._inner = inner

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[object, str, bool]:
        """Unused: `__call__` delegates to the wrapped source."""
        return None, field_name, False

    def __call__(self) -> dict[str, object]:
        values = dict(self._inner())
        values.pop("model_mode", None)
        return values


class Settings(BaseSettings):
    """Validated process configuration, read from the environment and .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "HireKitApp"
    env: Env = "development"
    port: int = 8080
    log_level: LogLevel = "info"
    log_format: LogFormat = "json"
    database_url: PostgresDsn
    db_pool_size: int = 5
    db_pool_max_overflow: int = 10
    db_echo: bool = False

    # Model gateway (docs/design/gateway-lld.md section 7).
    model_mode: ModelMode = "replay"
    ci: bool = False
    openrouter_api_key: SecretStr | None = None
    model_id: str = "anthropic/claude-haiku-4.5"
    gateway_timeout_seconds: float = 60.0
    price_input_usd_per_mtok: Decimal = Decimal(1)
    price_output_usd_per_mtok: Decimal = Decimal(5)
    recordings_dir: Path = DEFAULT_RECORDINGS_DIR
    record_responses: bool = False
    key_credit_limit_confirmed: str | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Read `model_mode` from the process environment only, never from .env."""
        return (
            init_settings,
            env_settings,
            _DotenvWithoutMode(dotenv_settings),
            file_secret_settings,
        )

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, value: PostgresDsn) -> PostgresDsn:
        """The whole stack is async; a sync driver here would block the loop."""
        if value.scheme != "postgresql+asyncpg":
            msg = f"DATABASE_URL must use postgresql+asyncpg://, got {value.scheme}://"
            raise ValueError(msg)
        return value

    @field_validator("gateway_timeout_seconds")
    @classmethod
    def _positive_timeout(cls, value: float) -> float:
        """A zero or negative timeout would cancel every call before it starts."""
        if value <= 0:
            msg = "GATEWAY_TIMEOUT_SECONDS must be greater than 0"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _live_mode_rules(self) -> Self:
        """Live calls are never allowed in CI and need a key (AC-US-02-003-4)."""
        if self.model_mode == "live":
            if self.ci:
                msg = "MODEL_MODE=live is not allowed when CI is set"
                raise ValueError(msg)
            if self.openrouter_api_key is None:
                msg = "OPENROUTER_API_KEY is required when MODEL_MODE=live"
                raise ValueError(msg)
        return self


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process."""
    return Settings()
