"""Small in-memory repository, also reusable as a stateful test fake."""

from collections.abc import Iterable

from book_catalog.exceptions import ValidationError
from book_catalog.models import Book


class InMemoryBookRepository:
    def __init__(self, books: Iterable[Book] = ()) -> None:
        self._books: dict[str, Book] = {}
        for book in books:
            self.add(book)

    def all(self) -> tuple[Book, ...]:
        return tuple(self._books.values())

    def add(self, book: Book) -> None:
        if book.isbn in self._books:
            raise ValidationError("Duplicate ISBN")
        self._books[book.isbn] = book
