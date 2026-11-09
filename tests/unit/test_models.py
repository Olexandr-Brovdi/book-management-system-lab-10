from dataclasses import FrozenInstanceError

import pytest

from book_catalog.exceptions import ValidationError
from book_catalog.models import YearPolicy

pytestmark = pytest.mark.unit


def test_book_creation_preserves_all_domain_fields(book_factory):
    assert book_factory().to_dict() == dict(
        isbn="9780000000002",
        title="Кобзар",
        author="Тарас Шевченко",
        year=2000,
        pages=100,
    )


def test_book_normalizes_whitespace(book_factory):
    book = book_factory(title="  Лісова   пісня ", author=" Леся  Українка ")
    assert (book.title, book.author) == ("Лісова пісня", "Леся Українка")


def test_book_is_immutable(book_factory):
    with pytest.raises(FrozenInstanceError):
        book_factory().pages = 10


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", ""),
        ("author", "  "),
        ("isbn", None),
        ("title", 42),
        ("pages", 0),
        ("pages", -1),
        ("pages", True),
        ("pages", 1.5),
        ("year", 0),
        ("year", 10000),
        ("year", True),
        ("year", 2000.5),
    ],
    ids=[
        "empty-title",
        "blank-author",
        "missing-isbn",
        "numeric-title",
        "zero-pages",
        "negative-pages",
        "bool-pages",
        "float-pages",
        "year-zero",
        "year-overflow",
        "bool-year",
        "float-year",
    ],
)
def test_invalid_book_values_raise_custom_error(book_factory, field, value):
    with pytest.raises(ValidationError):
        book_factory(**{field: value})


@pytest.mark.parametrize(
    "year", [1800, 1801, 2025, 2026], ids=["min", "above-min", "below-max", "max"]
)
def test_permitted_year_boundaries(policy, year):
    assert policy.validate(year) is None


@pytest.mark.parametrize("year", [1799, 2027, "2000", True])
def test_year_outside_policy_is_rejected(policy, year):
    with pytest.raises(ValidationError, match="allowed range"):
        policy.validate(year)


@pytest.mark.parametrize(
    "low,high", [(0, 2026), (2027, 2026), (1800, 10000), (True, 2026), (1, 1.5)]
)
def test_invalid_year_policy(low, high):
    with pytest.raises(ValidationError, match="range"):
        YearPolicy(low, high)


@pytest.mark.parametrize(
    "pages", [1, 2, 1000000], ids=["minimum", "above-minimum", "large"]
)
def test_valid_page_boundaries(book_factory, pages):
    assert book_factory(pages=pages).pages == pages
