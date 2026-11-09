"""Search/report orchestration and an injected asynchronous external catalog."""

from pathlib import Path

from book_catalog.catalog import Catalog
from book_catalog.exceptions import ExternalCatalogError, ValidationError
from book_catalog.models import Book, YearPolicy
from book_catalog.protocols import BookRepository, ExternalCatalog, ReportExporter


class CatalogReportService:
    def __init__(self, repository: BookRepository, exporter: ReportExporter) -> None:
        self.repository = repository
        self.exporter = exporter

    def export_author(self, query: str, path: Path) -> int:
        books = Catalog(self.repository.all()).by_author(query)
        return self.exporter.write(books, path)


class AsyncCatalogService:
    def __init__(
        self, external: ExternalCatalog, repository: BookRepository, policy: YearPolicy
    ) -> None:
        self.external = external
        self.repository = repository
        self.policy = policy

    async def refresh(self, query: str) -> int:
        try:
            rows = await self.external.fetch(query)
            # Validate the entire batch before mutating repository state.
            books = [Book(**row) for row in rows]
            for book in books:
                self.policy.validate(book.year)
            combined = Catalog((*self.repository.all(), *books))
        except (ConnectionError, TimeoutError, TypeError, ValidationError) as error:
            raise ExternalCatalogError("External catalog refresh failed") from error
        for book in combined.books[len(self.repository.all()) :]:
            self.repository.add(book)
        return len(books)
