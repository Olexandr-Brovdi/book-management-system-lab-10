import logging
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from book_catalog.api import create_app
from book_catalog.config import Settings
from book_catalog.runtime import configure_logging


def test_settings_use_environment_without_code_changes(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'books.sqlite'}")
    settings = Settings(_env_file=None)
    assert settings.environment == "production" and settings.log_level == "DEBUG"
    assert settings.database_path == tmp_path / "books.sqlite"
    assert configure_logging(settings.log_level).level == logging.DEBUG


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://localhost/books",
        "sqlite:///:memory:",
        "sqlite://",
        "sqlite:///books.db?mode=ro",
    ],
)
def test_invalid_database_configuration_fails_fast(url):
    with pytest.raises(ValidationError):
        Settings(database_url=url, _env_file=None)


def test_dotenv_is_optional_and_environment_takes_precedence(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("APP_ENV=test\nLOG_LEVEL=WARNING\n", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    settings = Settings(_env_file=path)
    assert settings.environment == "production" and settings.log_level == "WARNING"


def test_health_environment_schema_and_persistent_database(tmp_path):
    path = tmp_path / "production.sqlite"
    settings = Settings(
        database_url=f"sqlite:///{path}", environment="production", _env_file=None
    )
    app = create_app(runtime=settings)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {
            "status": "ok",
            "environment": "production",
            "version": "1.0.0",
        }
        author = client.post("/authors", json={"name": "Іван Франко"}).json()
        assert (
            client.post(
                "/books",
                json={
                    "title": "Мойсей",
                    "author_id": author["id"],
                    "year": 1905,
                    "pages": 80,
                },
            ).status_code
            == 201
        )
    with TestClient(create_app(runtime=settings)) as restarted:
        assert restarted.get("/books").json()[0]["title"] == "Мойсей"
        assert restarted.get("/docs").status_code == 200
        assert "/health" in restarted.get("/openapi.json").json()["paths"]


def test_health_database_failure_is_503(tmp_path, monkeypatch):
    app = create_app(tmp_path / "health.sqlite")
    with TestClient(app) as client:

        def unavailable():
            raise OperationalError("SELECT 1", {}, RuntimeError("offline"))

        monkeypatch.setattr(app.state.engine, "connect", unavailable)
        assert client.get("/health").status_code == 503


def test_packaged_migrations_match_development_versions():
    root = Path(__file__).resolve().parents[2]
    for path in (root / "migrations").rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            assert (
                path.read_bytes()
                == (
                    root
                    / "src/book_catalog/migration_assets"
                    / path.relative_to(root / "migrations")
                ).read_bytes()
            )
