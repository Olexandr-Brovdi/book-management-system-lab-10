"""Reproducible demonstration of persisted catalog behavior and rollback."""

import argparse
from pathlib import Path

from book_catalog.database import make_engine, session_factory, upgrade_database
from book_catalog.exceptions import ValidationError
from book_catalog.persistence.dbapi import find_books_by_author
from book_catalog.persistence.services import BookDraft, LibraryService


def demo(database: Path) -> None:
    upgrade_database(database)
    engine = make_engine(database)
    try:
        library = LibraryService(session_factory(engine))
        if not library.list_authors():
            library.add_author_with_books(
                "Іван Франко",
                [
                    BookDraft("Захар Беркут", 1883, 192, "9780000000019"),
                    BookDraft("Мойсей", 1905, 80, "9780000000026"),
                ],
            )
            library.add_author_with_books(
                "Леся Українка", [BookDraft("Лісова пісня", 1911, 160, "9780000000033")]
            )
        print("Lab_10 variant 2: SQLite book catalog; migration head 0002")
        print("BOOKS:")
        for book in library.list_books():
            print(
                f"{book.id}: {book.title} | {book.author} | {book.year} | {book.pages} | {book.isbn}"
            )
        print(
            "Author filter:", [b.title for b in library.find_by_author("Іван Франко")]
        )
        print("Year 1883:", [b.title for b in library.filter_by_year(1883)])
        largest = library.largest_book()
        print("Largest:", largest.title if largest is not None else None)
        print("Average pages:", round(library.average_pages(), 4))
        print("JOIN + GROUP BY (name, count, sum, avg):", library.author_statistics())
        print(
            "DB-API parameterized search:",
            find_books_by_author(database, "Іван Франко"),
        )
        print("SQL injection as text:", find_books_by_author(database, "' OR 1=1 --"))
        temporary = library.create_author("CRUD demonstration")
        renamed = library.update_author(temporary.id, "CRUD updated")
        created = library.create_book(temporary.id, BookDraft("Draft", 2000, 10))
        updated = library.update_book(
            created.id, temporary.id, BookDraft("Updated", 2001, 20)
        )
        assert renamed is not None and updated is not None
        print(
            "CRUD author/book:",
            renamed.name,
            updated.title,
            library.delete_book(created.id),
            library.delete_author(temporary.id),
        )
        before = (len(library.list_authors()), len(library.list_books()))
        try:
            library.add_author_with_books(
                "Rollback demo",
                [
                    BookDraft("Flushed first", 2000, 10),
                    BookDraft("Invalid second", 2000, 0),
                ],
            )
        except ValidationError as error:
            print("ROLLBACK:", type(error).__name__, str(error))
        after = (len(library.list_authors()), len(library.list_books()))
        print(
            "Counts before/after failure:", before, after, "unchanged:", before == after
        )
        print(
            "ROLLBACK author absent:",
            all(a.name != "Rollback demo" for a in library.list_authors()),
        )
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lab_10 variant 2 persisted library demonstration"
    )
    parser.add_argument("--database", type=Path, default=Path("data/library.db"))
    args = parser.parse_args()
    demo(args.database)


if __name__ == "__main__":
    main()
