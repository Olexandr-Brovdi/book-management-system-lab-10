"""Atomic JSON report, with cleanup even if serialization fails."""

import json
import os
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

from book_catalog.exceptions import ExportError
from book_catalog.models import Book


@contextmanager
def atomic_output(path: Path) -> Iterator[TextIO]:
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            yield handle
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except (OSError, TypeError, ValueError) as error:
        raise ExportError("Cannot export book catalog") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class JsonExporter:
    def write(self, books: Iterable[Book], path: Path) -> int:
        count = 0
        with atomic_output(path) as handle:
            handle.write("[\n")
            for book in books:
                if count:
                    handle.write(",\n")
                json.dump(book.to_dict(), handle, ensure_ascii=False, allow_nan=False)
                count += 1
            handle.write("\n]\n")
        return count
