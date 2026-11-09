import json

import pytest

from book_catalog.catalog import Catalog
from book_catalog.exporters import JsonExporter
from book_catalog.importers import read_books
from book_catalog.repositories import InMemoryBookRepository
from book_catalog.services import CatalogReportService

pytestmark = pytest.mark.integration


def test_import_search_export_matches_author(csv_factory, books, policy, tmp_path):
    incoming = read_books(csv_factory(books), policy)
    output = tmp_path / "result.json"
    result = CatalogReportService(
        InMemoryBookRepository(incoming), JsonExporter()
    ).export_author("ФРАНКО", output)
    assert result == 2
    assert json.loads(output.read_text(encoding="utf-8")) == [
        b.to_dict() for b in books[1:]
    ]
    assert Catalog(incoming).average_pages() == pytest.approx(302 / 3)


def test_repeated_export_replaces_result_without_old_records(tmp_path, books):
    target = tmp_path / "out.json"
    exporter = JsonExporter()
    exporter.write(books, target)
    assert exporter.write([books[0]], target) == 1
    assert json.loads(target.read_text(encoding="utf-8")) == [books[0].to_dict()]
