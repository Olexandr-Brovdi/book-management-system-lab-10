"""Real ORM/repository/service tests against independently migrated SQLite files."""

import sqlite3
from contextlib import closing

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from book_catalog.database import (
    PersistenceConflict,
    make_engine,
    session_factory,
    upgrade_database,
)
from book_catalog.exceptions import ValidationError
from book_catalog.persistence.dbapi import find_books_by_author
from book_catalog.persistence.models import Author, Book
from book_catalog.persistence.repositories import AuthorRepository, BookRepository
from book_catalog.persistence.services import BookDraft, LibraryService

pytestmark = pytest.mark.integration


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "test-library.sqlite"
    upgrade_database(path)
    return path


@pytest.fixture
def factory(database):
    engine = make_engine(database)
    yield session_factory(engine)
    engine.dispose()


@pytest.fixture
def library(factory):
    return LibraryService(factory)


@pytest.fixture
def stored(library):
    return library.add_author_with_books(
        "Іван Франко",
        [
            BookDraft("Захар Беркут", 1883, 192, "9780000000019"),
            BookDraft("Мойсей", 1905, 80, "9780000000026"),
        ],
    )


def test_create_author_is_visible_to_independent_connection(library, database):
    author = library.create_author("  Леся  Українка ")
    assert author.id > 0 and author.name == "Леся Українка" and author.book_ids == ()
    with closing(sqlite3.connect(database)) as connection, connection:
        assert connection.execute("SELECT name FROM authors").fetchall() == [
            ("Леся Українка",)
        ]


def test_read_author_and_relationship(library, stored):
    author = library.get_author(stored.id)
    assert author == stored
    assert len(author.book_ids) == 2
    assert library.get_book(author.book_ids[0]).author == "Іван Франко"
    assert library.get_author(999999) is None


def test_list_authors_and_update_name(library, stored):
    assert library.list_authors() == [stored]
    updated = library.update_author(stored.id, "І. Франко")
    assert updated.name == "І. Франко"
    assert library.get_book(stored.book_ids[0]).author == "І. Франко"
    assert library.update_author(99999, "Nobody") is None


def test_delete_author_cascades_books(library, stored):
    assert library.delete_author(stored.id) is True
    assert library.get_author(stored.id) is None
    assert library.list_books() == []
    assert library.delete_author(stored.id) is False


def test_create_and_read_book(library):
    author = library.create_author("Автор")
    book = library.create_book(author.id, BookDraft("Книга", 2000, 201))
    assert book.title == "Книга" and book.author_id == author.id
    assert book.isbn is None and book.pages == 201
    assert library.get_book(book.id) == book
    assert library.get_book(99999) is None


def test_update_book_can_change_author(library, stored):
    other = library.create_author("Леся Українка")
    book = library.update_book(
        stored.book_ids[0],
        other.id,
        BookDraft("Лісова пісня", 1911, 160, "9780000000033"),
    )
    assert (
        book.title,
        book.year,
        book.pages,
        book.author,
        book.author_id,
        book.isbn,
    ) == ("Лісова пісня", 1911, 160, "Леся Українка", other.id, "9780000000033")
    assert library.get_book(book.id) == book
    assert library.get_author(other.id).book_ids == (book.id,)
    assert library.update_book(999999, other.id, BookDraft("Absent", 2000, 1)) is None


def test_delete_book_keeps_author(library, stored):
    book_id = stored.book_ids[0]
    assert library.delete_book(book_id) is True
    assert library.get_book(book_id) is None
    assert library.get_author(stored.id) is not None
    assert library.delete_book(book_id) is False


def test_find_author_and_filter_year(library, stored):
    assert [b.title for b in library.find_by_author("Іван Франко")] == [
        "Захар Беркут",
        "Мойсей",
    ]
    assert library.find_by_author("Unknown") == []
    assert [b.title for b in library.filter_by_year(1883)] == ["Захар Беркут"]
    assert library.filter_by_year(2000) == []
    with pytest.raises(ValidationError):
        library.filter_by_year(0)


def test_sql_largest_and_average_pages(library, stored):
    assert library.largest_book().title == "Захар Беркут"
    assert library.average_pages() == pytest.approx(136.0)
    library.create_book(stored.id, BookDraft("Tie", 2000, 192))
    assert library.largest_book().id == stored.book_ids[0]
    assert library.average_pages() == pytest.approx(464 / 3)


def test_empty_database_has_neutral_results(library):
    assert library.largest_book() is None
    assert library.average_pages() == 0.0
    assert (
        library.list_authors()
        == library.list_books()
        == library.author_statistics()
        == []
    )


def test_join_group_by_count_sum_avg_include_empty_author(library, stored):
    library.create_author("Порожній автор")
    assert library.author_statistics() == [
        ("Іван Франко", 2, 272, 136.0),
        ("Порожній автор", 0, 0, 0.0),
    ]


def test_pagination_is_stable(library, stored):
    assert [b.id for b in library.list_books(limit=1)] == [stored.book_ids[0]]
    assert [b.id for b in library.list_books(offset=1, limit=1)] == [stored.book_ids[1]]
    assert library.list_books(offset=100) == []


@pytest.mark.parametrize("offset,limit", [(-1, 1), (0, 0), (True, 1), (0, 1.5)])
def test_invalid_pagination(library, offset, limit):
    with pytest.raises(ValueError, match="pagination"):
        library.list_books(offset=offset, limit=limit)


def test_parameterized_dbapi_join(database, library, stored):
    rows = find_books_by_author(database, "Іван Франко")
    assert [(row[1], row[2], row[4]) for row in rows] == [
        ("Захар Беркут", "Іван Франко", 192),
        ("Мойсей", "Іван Франко", 80),
    ]
    assert find_books_by_author(database, "' OR 1=1 --") == []
    assert len(library.list_books()) == 2


def test_sql_injection_text_is_literal_author(database, library, stored):
    literal = "O'Brian'; DROP TABLE books; --"
    author = library.add_author_with_books(literal, [BookDraft("Literal", 2000, 10)])
    assert len(find_books_by_author(database, literal)) == 1
    assert library.get_author(author.id).name == literal
    assert len(library.list_books()) == 3


def test_missing_dbapi_database_does_not_create_file(tmp_path):
    path = tmp_path / "absent.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        find_books_by_author(path, "author")
    assert not path.exists()


def test_atomic_author_and_books_commit(library, database):
    author = library.add_author_with_books(
        "Тарас Шевченко", [BookDraft("Кобзар", 1840, 240)]
    )
    assert len(author.book_ids) == 1
    assert len(find_books_by_author(database, "Тарас Шевченко")) == 1


def test_invalid_second_book_rolls_back_author_and_first_book(library, database):
    with pytest.raises(ValidationError, match="Pages"):
        library.add_author_with_books(
            "Rollback author",
            [BookDraft("Valid first", 2000, 100), BookDraft("Invalid second", 2000, 0)],
        )
    with closing(sqlite3.connect(database)) as observer, observer:
        assert observer.execute("SELECT COUNT(*) FROM authors").fetchone()[0] == 0
        assert observer.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0


def test_duplicate_isbn_rolls_back_whole_batch(library, stored, database):
    with pytest.raises(PersistenceConflict) as error:
        library.add_author_with_books(
            "New author",
            [
                BookDraft("New first", 2000, 1, "new-isbn"),
                BookDraft("Duplicate second", 2000, 2, "9780000000019"),
            ],
        )
    assert isinstance(error.value.__cause__, IntegrityError)
    assert library.list_authors() == [stored]
    assert len(library.list_books()) == 2
    assert find_books_by_author(database, "New author") == []
    # A fresh operation remains usable after rollback.
    assert library.create_author("After rollback").id > 0


def test_duplicate_author_is_integrity_conflict(library, stored):
    with pytest.raises(PersistenceConflict):
        library.create_author("Іван Франко")
    assert library.list_authors() == [stored]


@pytest.mark.parametrize(
    "draft",
    [
        BookDraft("", 2000, 1),
        BookDraft("x", 2027, 1),
        BookDraft("x", 2000, True),
        BookDraft("x", 2000, 1, ""),
        BookDraft("x", 2000, 1, 42),
    ],
)
def test_invalid_domain_input_does_not_persist(library, draft):
    author = library.create_author("Valid author")
    with pytest.raises(ValidationError):
        library.create_book(author.id, draft)
    assert library.list_books() == []


@pytest.mark.parametrize("name", ["", None, "   "])
def test_invalid_author_name(library, name):
    with pytest.raises(ValidationError, match="name"):
        library.create_author(name)
    assert library.list_authors() == []


def test_missing_author_for_create_and_update(library):
    with pytest.raises(ValidationError, match="not found"):
        library.create_book(99999, BookDraft("x", 2000, 1))
    with pytest.raises(ValidationError, match="not found"):
        library.update_book(1, 99999, BookDraft("x", 2000, 1))


def test_foreign_keys_enabled_on_every_connection(factory):
    for _ in range(2):
        with factory() as session:
            assert session.scalar(text("PRAGMA foreign_keys")) == 1
            session.add(Book(title="Orphan", year=2000, pages=1, author_id=99999))
            with pytest.raises(IntegrityError):
                session.flush()
            session.rollback()


@pytest.mark.parametrize(
    "column,value",
    [("pages", 0), ("pages", -1), ("pages", 1.5), ("year", 0), ("title", "")],
)
def test_database_check_constraints_cannot_be_bypassed(factory, column, value):
    with factory() as session:
        author = AuthorRepository(session).add("Database author")
        values = dict(title="Valid", year=2000, pages=1, author_id=author.id)
        values[column] = value
        session.add(Book(**values))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
        assert session.scalar(select(func.count()).select_from(Author)) == 0


def test_repository_full_crud_and_relationship(factory):
    with factory() as session:
        authors, books = AuthorRepository(session), BookRepository(session)
        author = authors.add("Repo author")
        book = books.add(
            Book(title="Repo book", year=2000, pages=10, author_id=author.id)
        )
        session.commit()
        assert authors.get_by_name("Repo author").id == author.id
        assert books.get_by_id(book.id).author.name == "Repo author"
        assert authors.get_by_id(author.id).books == [book]
        assert books.get_all() == [book]
        assert books.delete(book.id)
        assert author.books == []
        assert authors.delete(author.id)
        session.commit()
        assert authors.get_all() == books.get_all() == []


def test_unit_of_work_rolls_back_when_commit_fails(factory, monkeypatch):
    from book_catalog.database import unit_of_work
    from sqlalchemy.orm import Session

    def fail_commit(session):
        raise RuntimeError("commit failure")

    monkeypatch.setattr(Session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="commit failure"):
        with unit_of_work(factory) as session:
            AuthorRepository(session).add("Must roll back")
    with factory() as observer:
        assert AuthorRepository(observer).get_all() == []
