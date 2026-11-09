from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, create_autospec

import pytest

from book_catalog.exceptions import ExportError, ExternalCatalogError, ValidationError
from book_catalog.protocols import BookRepository, ExternalCatalog, ReportExporter
from book_catalog.repositories import InMemoryBookRepository
from book_catalog.services import AsyncCatalogService, CatalogReportService

pytestmark = pytest.mark.unit


def test_report_uses_repository_return_value_and_exports_only_matches(books):
    repository = Mock(spec=BookRepository)
    repository.all.return_value = books
    exporter = create_autospec(ReportExporter, instance=True)
    exporter.write.return_value = 2
    path = Path("result.json")
    result = CatalogReportService(repository, exporter).export_author("Франко", path)
    assert result == 2
    repository.all.assert_called_once_with()
    exporter.write.assert_called_once_with(books[1:], path)


def test_repository_failure_prevents_export_interaction():
    repository = Mock(spec=BookRepository)
    repository.all.side_effect = ConnectionError("repository offline")
    exporter = Mock(spec=ReportExporter)
    with pytest.raises(ConnectionError, match="offline"):
        CatalogReportService(repository, exporter).export_author("a", Path("out.json"))
    exporter.write.assert_not_called()
    repository.add.assert_not_called()


def test_export_failure_propagates_without_retry(repository):
    exporter = Mock(spec=ReportExporter)
    exporter.write.side_effect = ExportError("disk full")
    with pytest.raises(ExportError, match="disk full"):
        CatalogReportService(repository, exporter).export_author(
            "Франко", Path("out.json")
        )
    exporter.write.assert_called_once()
    assert len(repository.all()) == 3


def test_fake_repository_records_state_and_rejects_duplicates(book_factory):
    repository = InMemoryBookRepository()
    assert repository.all() == ()
    book = book_factory()
    repository.add(book)
    assert repository.all() == (book,)
    with pytest.raises(ValidationError, match="Duplicate"):
        repository.add(book)
    assert repository.all() == (book,)


def test_magicmock_iterable_contract_is_consumed(books):
    from book_catalog.catalog import Catalog

    source = MagicMock()
    source.__iter__.return_value = iter(books)
    assert Catalog(source).books == books
    source.__iter__.assert_called_once_with()


def test_autospec_rejects_wrong_exporter_signature():
    exporter = create_autospec(ReportExporter, instance=True)
    with pytest.raises(TypeError):
        exporter.write()


@pytest.mark.asyncio
async def test_async_external_catalog_success(books, policy):
    external = AsyncMock(spec=ExternalCatalog)
    external.fetch.return_value = [b.to_dict() for b in books]
    repository = InMemoryBookRepository()
    result = await AsyncCatalogService(external, repository, policy).refresh("Франко")
    assert result == 3
    assert repository.all() == books
    external.fetch.assert_awaited_once_with("Франко")


@pytest.mark.asyncio
async def test_async_dependency_failure_does_not_mutate_repository(policy):
    external = AsyncMock(spec=ExternalCatalog)
    cause = ConnectionError("offline")
    external.fetch.side_effect = cause
    repository = Mock(spec=BookRepository)
    with pytest.raises(ExternalCatalogError, match="refresh failed") as error:
        await AsyncCatalogService(external, repository, policy).refresh("book")
    assert error.value.__cause__ is cause
    repository.add.assert_not_called()
    repository.all.assert_not_called()
    external.fetch.assert_awaited_once_with("book")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        {"title": "incomplete"},
        dict(isbn="x", title="x", author="a", year=1700, pages=1),
    ],
)
async def test_async_invalid_batch_does_not_partially_add(books, bad, policy):
    external = AsyncMock(spec=ExternalCatalog)
    external.fetch.return_value = [books[0].to_dict(), bad]
    repository = InMemoryBookRepository()
    with pytest.raises(ExternalCatalogError):
        await AsyncCatalogService(external, repository, policy).refresh("book")
    assert repository.all() == ()


@pytest.mark.asyncio
async def test_async_duplicate_batch_preserves_existing_state(books, policy):
    external = AsyncMock(spec=ExternalCatalog)
    external.fetch.return_value = [books[0].to_dict()]
    repository = InMemoryBookRepository(books)
    with pytest.raises(ExternalCatalogError):
        await AsyncCatalogService(external, repository, policy).refresh("book")
    assert repository.all() == books
