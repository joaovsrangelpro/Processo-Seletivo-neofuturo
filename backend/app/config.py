from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/contact_manager",
        validation_alias="DATABASE_URL",
        repr=False,
    )
    openai_api_key: str | None = Field(
        default=None, validation_alias="OPENAI_API_KEY", repr=False,
    )
    frontend_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        validation_alias="FRONTEND_ORIGINS",
    )

    @property
    def allowed_frontend_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.frontend_origins.split(",")
            if origin.strip()
        ]

    @field_validator("frontend_origins")
    @classmethod
    def reject_wildcard_origins(cls, value: str) -> str:
        if any(origin.strip() == "*" for origin in value.split(",")):
            raise ValueError("FRONTEND_ORIGINS must use explicit origins, not '*'.")
        return value

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        try:
            url = make_url(value)
        except ArgumentError:
            raise ValueError("DATABASE_URL must be a valid SQLAlchemy URL.") from None
        if url.drivername == "postgresql":
            return url.set(drivername="postgresql+psycopg").render_as_string(
                hide_password=False,
            )
        return value

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )


settings = Settings()
