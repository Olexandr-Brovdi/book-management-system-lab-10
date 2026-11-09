"""Fresh function-scoped state; only immutable policy is shared."""

import csv

import pytest
import yaml

from book_catalog.models import Book, YearPolicy
from book_catalog.repositories import InMemoryBookRepository


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    monkeypatch.delenv("BOOK_ENV", raising=False)
    monkeypatch.delenv("BOOK_MAX_YEAR", raising=False)


@pytest.fixture(scope="module")
def policy():
    return YearPolicy(1800, 2026)


@pytest.fixture
def book_factory():
    def make(**changes):
        values = dict(
            isbn="9780000000002",
            title="Кобзар",
            author="Тарас Шевченко",
            year=2000,
            pages=100,
        )
        return Book(**(values | changes))

    return make


@pytest.fixture
def books(book_factory):
    return (
        book_factory(),
        book_factory(
            isbn="9780000000019",
            title="Захар Беркут",
            author="Іван Франко",
            year=1883,
            pages=101,
        ),
        book_factory(
            isbn="9780000000026",
            title="Мойсей",
            author="Іван Франко",
            year=1905,
            pages=101,
        ),
    )


@pytest.fixture
def repository(books):
    return InMemoryBookRepository(books)


@pytest.fixture(params=["utf-8", "utf-8-sig"], ids=["utf8", "utf8-bom"])
def csv_encoding(request):
    return request.param


@pytest.fixture
def csv_factory(tmp_path):
    def write(books, *, encoding="utf-8", name="books.csv"):
        path = tmp_path / name
        with path.open("w", encoding=encoding, newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["isbn", "title", "author", "year", "pages"]
            )
            writer.writeheader()
            writer.writerows(book.to_dict() for book in books)
        return path

    return write


@pytest.fixture
def config_path(tmp_path, csv_factory, books):
    incoming = csv_factory(books)
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            dict(
                min_year=1800,
                max_year=2026,
                input=incoming.name,
                output="reports/books.json",
            )
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def open_resource(tmp_path):
    handle = (tmp_path / "resource.txt").open("w", encoding="utf-8")
    yield handle
    handle.close()
