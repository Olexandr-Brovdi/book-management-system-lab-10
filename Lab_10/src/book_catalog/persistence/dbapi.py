"""A raw DB-API JOIN uses placeholders; closing also closes the connection."""

from contextlib import closing
from pathlib import Path
import sqlite3


def find_books_by_author(database: Path, author: str) -> list[tuple]:
    uri = database.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT books.id, books.title, authors.name, books.year, books.pages, books.isbn
                FROM books JOIN authors ON books.author_id = authors.id
                WHERE authors.name = ?
                ORDER BY books.id
            """,
                (author,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
