import pytest

from book_catalog.catalog import Catalog
from book_catalog.exceptions import ValidationError

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "query,indices",
    [("франКО", (1, 2)), ("  Шевченко ", (0,)), ("немає", ()), ("", ())],
)
def test_search_by_author_is_case_insensitive(books, query, indices):
    assert Catalog(books).by_author(query) == tuple(books[i] for i in indices)


@pytest.mark.parametrize(
    "query,indices", [("берКУТ", (1,)), ("МОЙ", (2,)), ("unknown", ()), (" ", ())]
)
def test_search_by_title_uses_normalized_substring(books, query, indices):
    assert Catalog(books).by_title(query) == tuple(books[i] for i in indices)


def test_filter_by_year_returns_matching_books(books):
    assert Catalog(books).by_year(1883) == (books[1],)
    assert Catalog(books).by_year(1990) == ()


@pytest.mark.parametrize("year", [0, 10000, True, "1883"])
def test_invalid_filter_year(books, year):
    with pytest.raises(ValidationError, match="filter year"):
        Catalog(books).by_year(year)


def test_largest_book_resolves_equal_pages_by_first_occurrence(books):
    assert Catalog(books).largest() == books[1]


def test_average_pages_keeps_fraction(books):
    assert Catalog(books).average_pages() == pytest.approx(100.66666666666667)


def test_empty_catalog_has_defined_neutral_results():
    catalog = Catalog()
    assert catalog.books == ()
    assert catalog.largest() is None
    assert catalog.average_pages() == 0.0
    assert (
        catalog.by_title("book")
        == catalog.by_author("author")
        == catalog.by_year(2000)
        == ()
    )


def test_duplicate_isbn_rejected(book_factory):
    with pytest.raises(ValidationError, match="Duplicate"):
        Catalog([book_factory(), book_factory(title="Another")])
