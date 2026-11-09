"""YAML paths are relative to the configuration file; env override is optional."""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from typing import Literal

from book_catalog.exceptions import ConfigurationError
from book_catalog.models import YearPolicy


class Settings(BaseSettings):
    """Validated runtime environment; .env is optional and never committed."""

    app_name: str = "Book Catalog API"
    environment: Literal["development", "test", "production"] = Field(
        default="development", validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT")
    )
    database_url: str = "sqlite:///data/library.db"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        try:
            url = make_url(value)
        except ArgumentError as error:
            raise ValueError("DATABASE_URL must be a valid SQLite URL") from error
        if url.drivername != "sqlite" or not url.database or url.database == ":memory:":
            raise ValueError("DATABASE_URL must identify a persistent SQLite file")
        if url.username or url.password or url.host or url.port or url.query:
            raise ValueError(
                "SQLite URL must not contain credentials or query parameters"
            )
        return value

    @property
    def database_path(self) -> Path:
        return Path(str(make_url(self.database_url).database))


@dataclass(frozen=True, slots=True)
class Config:
    policy: YearPolicy
    input: Path
    output: Path


def get_environment() -> str:
    return os.getenv("BOOK_ENV", "development")


def load_config(path: Path) -> Config:
    try:
        with path.open(encoding="utf-8-sig") as handle:
            raw = yaml.safe_load(handle)
        if not isinstance(raw, dict):
            raise ValueError("Configuration must be a mapping")
        policy = YearPolicy(raw["min_year"], raw["max_year"])
        override = os.getenv("BOOK_MAX_YEAR")
        if override is not None:
            policy = YearPolicy(policy.min_year, int(override))

        def resolve(value: object) -> Path:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Path must be nonempty text")
            return (path.resolve().parent / value).resolve()

        incoming, outgoing = resolve(raw["input"]), resolve(raw["output"])
        if len({incoming, outgoing, path.resolve()}) != 3:
            raise ValueError("Input output and config paths must differ")
        return Config(policy, incoming, outgoing)
    except (
        OSError,
        UnicodeError,
        yaml.YAMLError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise ConfigurationError("Invalid book catalog configuration") from error
