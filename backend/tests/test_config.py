import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_loads_database_url_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://example:sample@database.invalid:5432/contacts",
    )

    config = Settings(_env_file=None)

    assert config.database_url == (
        "postgresql+psycopg://example:sample@database.invalid:5432/contacts"
    )


def test_preserves_database_url_already_using_psycopg() -> None:
    url = "postgresql+psycopg://example:sample@database.invalid:5432/contacts"

    config = Settings(_env_file=None, DATABASE_URL=url)

    assert config.database_url == url


def test_openai_key_is_optional() -> None:
    config = Settings(_env_file=None)

    assert config.openai_api_key is None


def test_settings_representation_omits_sensitive_fields() -> None:
    config = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+psycopg://example:sample@database.invalid/contacts",
        OPENAI_API_KEY="fake-configuration-value",
    )

    assert "database_url" not in repr(config)
    assert "openai_api_key" not in repr(config)
    assert "fake-configuration-value" not in repr(config)


def test_validation_error_does_not_display_sensitive_input() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, OPENAI_API_KEY={"token": "fake-configuration-value"})

    assert "fake-configuration-value" not in str(error.value)
