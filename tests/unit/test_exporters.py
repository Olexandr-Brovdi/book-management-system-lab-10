import json

import pytest

from book_catalog import exporters
from book_catalog.exceptions import ExportError
from book_catalog.exporters import JsonExporter, atomic_output

pytestmark = pytest.mark.unit


def test_json_export_preserves_unicode_and_all_fields(tmp_path, books):
    target = tmp_path / "new" / "books.json"
    assert JsonExporter().write(books, target) == 3
    assert json.loads(target.read_text(encoding="utf-8")) == [
        b.to_dict() for b in books
    ]
    assert "Франко" in target.read_text(encoding="utf-8")
    assert not list(target.parent.glob("*.tmp"))


def test_empty_export_is_valid_json_array(tmp_path):
    path = tmp_path / "empty.json"
    assert JsonExporter().write([], path) == 0
    assert json.loads(path.read_text()) == []


def test_mid_export_failure_preserves_old_output_and_cleans_temp(tmp_path, books):
    path = tmp_path / "books.json"
    path.write_text("old valid data", encoding="utf-8")

    def failing_books():
        yield books[0]
        raise ExportError("injected failure")

    with pytest.raises(ExportError, match="injected"):
        JsonExporter().write(failing_books(), path)
    assert path.read_text() == "old valid data"
    assert not list(tmp_path.glob("*.tmp"))


def test_replace_permission_failure_is_chained(tmp_path, monkeypatch, books):
    path = tmp_path / "books.json"
    path.write_text("old")

    def denied(*args):
        raise PermissionError("locked")

    monkeypatch.setattr(exporters.os, "replace", denied)
    with pytest.raises(ExportError) as error:
        JsonExporter().write(books, path)
    assert isinstance(error.value.__cause__, PermissionError)
    assert path.read_text() == "old"
    assert not list(tmp_path.glob("*.tmp"))


def test_context_manager_closes_file_on_exception(tmp_path):
    with pytest.raises(RuntimeError, match="body"):
        with atomic_output(tmp_path / "out.json") as handle:
            assert not handle.closed
            raise RuntimeError("body")
    assert handle.closed
    assert not list(tmp_path.iterdir())


def test_temporary_creation_failure_is_domain_error(tmp_path, monkeypatch):
    def fail(**kwargs):
        raise OSError("no disk space")

    monkeypatch.setattr(exporters.tempfile, "NamedTemporaryFile", fail)
    with pytest.raises(ExportError) as error:
        JsonExporter().write([], tmp_path / "out.json")
    assert isinstance(error.value.__cause__, OSError)
    assert not list(tmp_path.iterdir())


def test_yield_fixture_provides_open_isolated_resource(open_resource):
    open_resource.write("fixture lifecycle")
    assert not open_resource.closed
