"""Public catalog behavior: case-insensitive search and page statistics."""

from collections.abc import Iterable

from book_catalog.exceptions import ValidationError
from book_catalog.models import Book


class Catalog:
    def __init__(self, books: Iterable[Book] = ()) -> None:
        self._books = tuple(books)
        if len({b.isbn for b in self._books}) != len(self._books):
            raise ValidationError("Duplicate ISBN")

    @property
    def books(self) -> tuple[Book, ...]:
        return self._books

    def by_author(self, query: str) -> tuple[Book, ...]:
        needle = query.strip().casefold()
        return tuple(b for b in self._books if needle and needle in b.author.casefold())

    def by_title(self, query: str) -> tuple[Book, ...]:
        needle = query.strip().casefold()
        return tuple(b for b in self._books if needle and needle in b.title.casefold())

    def by_year(self, year: int) -> tuple[Book, ...]:
        if type(year) is not int or not 1 <= year <= 9999:
            raise ValidationError("Invalid filter year")
        return tuple(b for b in self._books if b.year == year)

    def largest(self) -> Book | None:
        return max(self._books, key=lambda b: b.pages, default=None)

    def average_pages(self) -> float:
        if not self._books:
            return 0.0
        return sum(b.pages for b in self._books) / len(self._books)
