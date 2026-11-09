"""Book analytics: reproducible data, a loop baseline and equivalent vectorization."""

from dataclasses import dataclass
from functools import lru_cache
from math import sqrt
from random import Random
from threading import RLock

from book_catalog.catalog import Catalog
from book_catalog.models import Book


@dataclass(frozen=True, slots=True)
class PageStatistics:
    count: int
    average: float
    minimum: float
    maximum: float
    std: float


def generate_books(count: int, seed: int = 42) -> tuple[Book, ...]:
    if type(count) is not int or count < 0:
        raise ValueError("count must be a nonnegative integer")
    random = Random(seed)
    return tuple(
        Book(
            str(i),
            f"Книга {i}",
            f"Автор {i % 100:03}",
            random.randint(1800, 2026),
            random.randint(40, 1200),
        )
        for i in range(count)
    )


def statistics_python(values) -> PageStatistics:
    """Two-pass population statistics; pages are positive domain integers."""
    if len(values) == 0:
        return PageStatistics(0, 0.0, 0.0, 0.0, 0.0)
    total = 0
    minimum = maximum = values[0]
    for value in values:
        total += value
        minimum = min(minimum, value)
        maximum = max(maximum, value)
    average = total / len(values)
    squared = 0.0
    for value in values:
        squared += (value - average) ** 2
    return PageStatistics(
        len(values),
        average,
        float(minimum),
        float(maximum),
        sqrt(squared / len(values)),
    )


def statistics_numpy(values) -> PageStatistics:
    import numpy as np

    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        return PageStatistics(0, 0.0, 0.0, 0.0, 0.0)
    return PageStatistics(
        int(array.size),
        float(array.mean()),
        float(array.min()),
        float(array.max()),
        float(array.std()),
    )


def group_by_author(books) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for book in books:
        groups.setdefault(book.author, []).append(book.pages)
    return groups


def author_statistics(books) -> dict[str, PageStatistics]:
    return {
        author: statistics_python(pages)
        for author, pages in group_by_author(books).items()
    }


def analyze_catalog(catalog: Catalog) -> dict:
    """Profile all variant-2 operations on the existing Book/Catalog model."""
    largest = catalog.largest()
    return {
        "author_matches": len(catalog.by_author("Автор 042")),
        "year_matches": len(catalog.by_year(2000)),
        "average_pages": catalog.average_pages(),
        "largest_isbn": largest.isbn if largest else None,
        "page_statistics": statistics_python([b.pages for b in catalog.books]),
        "authors": author_statistics(catalog.books),
    }


class CachedAuthorAnalytics:
    """Bounded cache for immutable catalog snapshots; mutations invalidate it."""

    def __init__(self, books=()):
        self._catalog = Catalog(books)
        self._version = 0
        self._lock = RLock()
        self._cached = lru_cache(maxsize=128)(self._calculate)

    def _calculate(self, author: str, version: int) -> PageStatistics:
        return statistics_python(
            [b.pages for b in self._catalog.books if b.author.casefold() == author]
        )

    def statistics(self, author: str) -> PageStatistics:
        key = " ".join(author.split()).casefold()
        with self._lock:
            return self._cached(key, self._version)

    def replace_books(self, books) -> None:
        replacement = Catalog(books)  # Validate before changing the live snapshot.
        with self._lock:
            self._catalog = replacement
            self._version += 1
            self._cached.cache_clear()

    def add_book(self, book: Book) -> None:
        with self._lock:
            self.replace_books((*self._catalog.books, book))

    def cache_info(self):
        with self._lock:
            return self._cached.cache_info()

    @property
    def version(self):
        with self._lock:
            return self._version
