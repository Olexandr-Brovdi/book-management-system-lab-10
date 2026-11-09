from pathlib import Path
import sqlite3
from contextlib import closing

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from book_catalog.database import make_engine, upgrade_database


def test_isbn_upgrade_and_downgrade_preserve_existing_books(tmp_path):
    database = tmp_path / "migration.sqlite"
    upgrade_database(database, "0001")
    with closing(sqlite3.connect(database)) as connection, connection:
        assert "isbn" not in [
            r[1] for r in connection.execute("PRAGMA table_info(books)")
        ]
        connection.execute(
            "INSERT INTO authors(id,name) VALUES(1,?)", ("Legacy author",)
        )
        connection.execute(
            "INSERT INTO books(title,year,pages,author_id) VALUES(?,?,?,?)",
            ("Legacy book", 2000, 100, 1),
        )
    upgrade_database(database)
    engine = make_engine(database)
    try:
        assert "isbn" in [c["name"] for c in inspect(engine).get_columns("books")]
        assert any(
            c["column_names"] == ["isbn"]
            for c in inspect(engine).get_unique_constraints("books")
        )
        with closing(sqlite3.connect(database)) as connection, connection:
            assert connection.execute("SELECT title,isbn FROM books").fetchall() == [
                ("Legacy book", None)
            ]
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.check(config)
            command.downgrade(config, "0001")
        with closing(sqlite3.connect(database)) as connection, connection:
            assert "isbn" not in [
                r[1] for r in connection.execute("PRAGMA table_info(books)")
            ]
            assert connection.execute("SELECT title FROM books").fetchall() == [
                ("Legacy book",)
            ]
        upgrade_database(database)
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "base")
        assert "books" not in inspect(engine).get_table_names()
        assert "authors" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_repeated_upgrade_head_is_idempotent(tmp_path):
    database = tmp_path / "idempotent.sqlite"
    upgrade_database(database)
    upgrade_database(database)
    with closing(sqlite3.connect(database)) as connection, connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("0002",)
