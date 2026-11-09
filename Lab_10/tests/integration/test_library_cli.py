import sys
from contextlib import closing
import sqlite3
import pytest

from book_catalog.database import make_engine, session_factory, upgrade_database
from book_catalog.persistence.main import demo, main
from book_catalog.persistence.services import LibraryService

pytestmark = pytest.mark.integration


def test_library_demo_repeats_without_duplicate_seed(tmp_path, monkeypatch, capsys):
    database = tmp_path / "demo.sqlite"
    monkeypatch.setattr(sys, "argv", ["book-library", "--database", str(database)])
    main()
    first = capsys.readouterr().out
    main()
    second = capsys.readouterr().out
    assert "unchanged: True" in first and "unchanged: True" in second
    assert "SQL injection as text: []" in second
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM authors").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 3


def test_demo_keeps_existing_empty_catalog(tmp_path, capsys):
    database = tmp_path / "existing.sqlite"
    upgrade_database(database)
    engine = make_engine(database)
    try:
        LibraryService(session_factory(engine)).create_author("Existing empty author")
    finally:
        engine.dispose()
    demo(database)
    output = capsys.readouterr().out
    assert "Largest: None" in output and "Average pages: 0.0" in output
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT name FROM authors").fetchall() == [
            ("Existing empty author",)
        ]
        assert connection.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0
