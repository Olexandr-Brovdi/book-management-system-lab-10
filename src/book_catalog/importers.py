"""Validate each external CSV row at the system boundary."""

import csv
from pathlib import Path

from book_catalog.exceptions import ImportError, ValidationError
from book_catalog.models import Book, YearPolicy

FIELDS = ("isbn", "title", "author", "year", "pages")


def read_books(path: Path, policy: YearPolicy) -> list[Book]:
    books = []
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            if tuple(reader.fieldnames or ()) != FIELDS:
                raise ValidationError("CSV header does not match book schema")
            for row in reader:
                if set(row) != set(FIELDS) or any(
                    value is None for value in row.values()
                ):
                    raise ValidationError(f"Malformed record at line {reader.line_num}")
                try:
                    book = Book(
                        row["isbn"],
                        row["title"],
                        row["author"],
                        int(row["year"]),
                        int(row["pages"]),
                    )
                    policy.validate(book.year)
                except (ValueError, TypeError) as error:
                    raise ValidationError(
                        f"Invalid book at line {reader.line_num}"
                    ) from error
                books.append(book)
        return books
    except (OSError, UnicodeError, csv.Error, ValidationError) as error:
        raise ImportError("Cannot import book catalog") from error
