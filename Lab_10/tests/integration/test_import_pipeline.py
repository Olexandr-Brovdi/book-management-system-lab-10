import pytest

from book_catalog.importers import read_books

pytestmark = pytest.mark.integration


def test_real_csv_import_validates_full_catalog(
    csv_factory, books, policy, csv_encoding
):
    path = csv_factory(books, encoding=csv_encoding)
    assert tuple(read_books(path, policy)) == books


def test_multiline_quoted_title_roundtrip(csv_factory, book_factory, policy):
    book = book_factory(title='Книга, "перша" частина')
    assert read_books(csv_factory([book]), policy) == [book]
