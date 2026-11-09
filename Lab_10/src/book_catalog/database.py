"""Connection lifecycle, FK enforcement, migrations and transaction ownership."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from importlib.resources import files
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker


class PersistenceConflict(ValueError):
    """A database constraint rejected a transaction."""


def make_engine(path: Path) -> Engine:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(URL.create("sqlite", database=str(path)))

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def unit_of_work(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as session:
        try:
            yield session
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise PersistenceConflict(
                "Database constraint rejected the transaction"
            ) from error
        except Exception:
            session.rollback()
            raise


def upgrade_database(path: Path, revision: str = "head") -> None:
    config = Config()
    config.set_main_option(
        "script_location", str(files("book_catalog").joinpath("migration_assets"))
    )
    engine = make_engine(path)
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, revision)
    finally:
        engine.dispose()
