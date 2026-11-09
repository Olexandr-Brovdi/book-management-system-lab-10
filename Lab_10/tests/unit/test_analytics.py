from dataclasses import FrozenInstanceError
from dataclasses import replace
import pytest
from book_catalog.analytics import (
    CachedAuthorAnalytics,
    analyze_catalog,
    generate_books,
    statistics_numpy,
    statistics_python,
)
from book_catalog.catalog import Catalog
from book_catalog.exceptions import ValidationError
from book_catalog.models import Book


@pytest.mark.parametrize(
    "values", [[], [80], [80, 192, 160], [1200] * 1000, [40, 1200] * 500]
)
def test_numpy_matches_independent_loop_baseline(values):
    expected = statistics_python(values)
    actual = statistics_numpy(values)
    assert actual.count == expected.count
    for field in ["average", "minimum", "maximum", "std"]:
        assert getattr(actual, field) == pytest.approx(
            getattr(expected, field), abs=1e-8
        )


def test_known_population_statistics():
    result = statistics_python([100, 200, 300])
    assert result.average == 200 and result.minimum == 100 and result.maximum == 300
    assert result.std == pytest.approx((20000 / 3) ** 0.5)


@pytest.mark.parametrize("count", [-1, 1.5, True])
def test_invalid_generator_count(count):
    with pytest.raises(ValueError):
        generate_books(count)


def test_reproducible_books_and_original_variant_operations():
    books = generate_books(300)
    assert books == generate_books(300) and books != generate_books(300, 43)
    catalog = Catalog(books)
    report = analyze_catalog(catalog)
    assert report["author_matches"] == 3
    assert sum(s.count for s in report["authors"].values()) == 300
    assert report["average_pages"] == pytest.approx(report["page_statistics"].average)
    assert report["largest_isbn"] == catalog.largest().isbn
    assert report["year_matches"] == len(catalog.by_year(2000))
    assert analyze_catalog(Catalog())["largest_isbn"] is None


def test_cache_hits_normalization_immutability_and_invalidation():
    original = Book("1", "Мойсей", "Іван Франко", 1905, 80)
    analytics = CachedAuthorAnalytics([original])
    first = analytics.statistics(" ІВАН   Франко ")
    assert analytics.statistics("Іван Франко") is first
    assert analytics.cache_info().hits == 1 and analytics.cache_info().misses == 1
    with pytest.raises(FrozenInstanceError):
        first.average = 999
    analytics.add_book(Book("2", "Захар Беркут", "Іван Франко", 1883, 192))
    assert analytics.cache_info().currsize == 0 and analytics.version == 1
    assert analytics.statistics("Іван Франко").average == 136
    analytics.replace_books([replace(original, pages=160)])
    assert analytics.statistics("Іван Франко").average == 160
    analytics.replace_books([])
    assert analytics.statistics("Іван Франко").count == 0


def test_rejected_mutation_preserves_cache_and_catalog():
    book = generate_books(1)[0]
    analytics = CachedAuthorAnalytics([book])
    result = analytics.statistics(book.author)
    with pytest.raises(ValidationError):
        analytics.add_book(book)
    assert analytics.version == 0 and analytics.statistics(book.author) is result
