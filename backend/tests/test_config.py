import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.config import Settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_normalizes_postgresql_url_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://example:sample@database.invalid:5432/contacts?sslmode=require",
    )

    config = Settings(_env_file=None)

    assert config.database_url == (
        "postgresql+psycopg://example:sample@database.invalid:5432/contacts"
        "?sslmode=require"
    )


def test_preserves_database_url_already_using_psycopg() -> None:
    url = "postgresql+psycopg://example:sample@database.invalid:5432/contacts"

    config = Settings(_env_file=None, DATABASE_URL=url)

    assert config.database_url == url


def test_normalization_preserves_encoded_credentials_and_connection_parameters() -> None:
    url = (
        "postgresql://example:sample%40%2F%3A%25@database.invalid:6543/contacts"
        "?sslmode=require&connect_timeout=10"
    )

    config = Settings(_env_file=None, DATABASE_URL=url)
    normalized = make_url(config.database_url)

    assert normalized == make_url(url).set(drivername="postgresql+psycopg")
    assert normalized.password == "sample@/:%"


def test_openai_key_is_optional() -> None:
    config = Settings(_env_file=None)

    assert config.openai_api_key is None


def test_settings_representation_omits_sensitive_fields() -> None:
    config = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://example:sample@database.invalid/contacts",
        OPENAI_API_KEY="fake-configuration-value",
    )

    assert "database_url" not in repr(config)
    assert "openai_api_key" not in repr(config)
    assert "fake-configuration-value" not in repr(config)


def test_invalid_database_url_error_does_not_display_the_input() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, DATABASE_URL="invalid-url-with-fake-secret")

    assert "DATABASE_URL must be a valid SQLAlchemy URL." in str(error.value)
    assert "invalid-url-with-fake-secret" not in str(error.value)
