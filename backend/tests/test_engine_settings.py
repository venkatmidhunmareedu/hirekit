"""The engine must not echo bound parameters (token hashes, password hashes) into errors."""

from app.core.config import Settings
from app.db.session import make_engine


def test_the_engine_hides_statement_parameters() -> None:
    settings = Settings(
        _env_file=None,
        env="test",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/test",
    )

    assert make_engine(settings).sync_engine.hide_parameters is True
