"""Dependency boundaries used by mocks, fakes and real adapters."""

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from book_catalog.models import Book


class BookRepository(Protocol):
    def all(self) -> tuple[Book, ...]: ...
    def add(self, book: Book) -> None: ...


class ReportExporter(Protocol):
    def write(self, books: Iterable[Book], path: Path) -> int: ...


class ExternalCatalog(Protocol):
    async def fetch(self, query: str) -> list[dict]: ...
