"""Explicit environment configuration. No default credentials or implicit demo mode."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

DataMode = Literal["public", "synthetic"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLEARPATH_", hide_input_in_errors=True, extra="forbid"
    )

    database_url: SecretStr
    api_key: SecretStr
    data_mode: DataMode = "public"

    @field_validator("api_key")
    @classmethod
    def validate_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("API key must contain at least 32 characters")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = url.drivername == "postgresql+psycopg" and bool(url.host and url.database)
        except (ArgumentError, ValueError):
            valid = False
        if not valid:
            raise ValueError("A PostgreSQL psycopg database URL with host and database is required")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
