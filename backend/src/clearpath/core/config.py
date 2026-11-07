from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[4] / ".env",
        extra="ignore", populate_by_name=True,
    )
    database_url: str = "postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/clearpath"
    api_key: SecretStr = Field(validation_alias="CLEARPATH_API_KEY")
    mode: Literal["public", "synthetic"] = Field(default="public", validation_alias="CLEARPATH_MODE")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list, validation_alias="CLEARPATH_CORS_ORIGINS"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
