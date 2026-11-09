"""Application operations coordinate domain validation and atomic persistence."""

from collections.abc import Iterable
from dataclasses import dataclass
from sqlalchemy.orm import Session, sessionmaker
from book_catalog.database import unit_of_work
from book_catalog.exceptions import ValidationError
from book_catalog.models import Book as DomainBook, YearPolicy
from book_catalog.persistence.models import Author, Book
from book_catalog.persistence.repositories import AuthorRepository, BookRepository


@dataclass(frozen=True)
class BookDraft:
    title: str
    year: int
    pages: int
    isbn: str | None = None


@dataclass(frozen=True)
class AuthorView:
    id: int
    name: str
    book_ids: tuple[int, ...]


@dataclass(frozen=True)
class BookView:
    id: int
    title: str
    author: str
    author_id: int
    year: int
    pages: int
    isbn: str | None


def author_view(author: Author) -> AuthorView:
    return AuthorView(author.id, author.name, tuple(sorted(b.id for b in author.books)))


def book_view(book: Book) -> BookView:
    return BookView(
        book.id,
        book.title,
        book.author.name,
        book.author_id,
        book.year,
        book.pages,
        book.isbn,
    )


def normalize_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("Author name must be nonempty text")
    return " ".join(name.split())


class LibraryService:
    def __init__(
        self, factory: sessionmaker[Session], policy: YearPolicy | None = None
    ) -> None:
        self.factory = factory
        self.policy = policy if policy is not None else YearPolicy(1, 2026)

    def list_filtered(self, **filters):
        with unit_of_work(self.factory) as session:
            return [
                book_view(book) for book in BookRepository(session).search(**filters)
            ]

    def _book(self, draft: BookDraft, author: Author) -> Book:
        if draft.isbn is not None and (
            not isinstance(draft.isbn, str) or not draft.isbn.strip()
        ):
            raise ValidationError("ISBN must be nonempty text or None")
        value = DomainBook(
            draft.isbn or "unassigned",
            draft.title,
            author.name,
            draft.year,
            draft.pages,
        )
        self.policy.validate(value.year)
        return Book(
            title=value.title,
            year=value.year,
            pages=value.pages,
            author_id=author.id,
            isbn=draft.isbn.strip() if draft.isbn is not None else None,
        )

    def add_author_with_books(
        self, name: str, drafts: Iterable[BookDraft]
    ) -> AuthorView:
        with unit_of_work(self.factory) as session:
            author = AuthorRepository(session).add(normalize_name(name))
            repository = BookRepository(session)
            for draft in drafts:
                repository.add(self._book(draft, author))
            session.expire(author, ["books"])
            result = author_view(author)
        return result

    def create_author(self, name: str) -> AuthorView:
        return self.add_author_with_books(name, [])

    def get_author(self, author_id: int) -> AuthorView | None:
        with unit_of_work(self.factory) as session:
            author = AuthorRepository(session).get_by_id(author_id)
            return author_view(author) if author is not None else None

    def list_authors(self) -> list[AuthorView]:
        with unit_of_work(self.factory) as session:
            return [author_view(a) for a in AuthorRepository(session).get_all()]

    def update_author(self, author_id: int, name: str) -> AuthorView | None:
        with unit_of_work(self.factory) as session:
            author = AuthorRepository(session).update(author_id, normalize_name(name))
            return author_view(author) if author is not None else None

    def delete_author(self, author_id: int) -> bool:
        with unit_of_work(self.factory) as session:
            return AuthorRepository(session).delete(author_id)

    def create_book(self, author_id: int, draft: BookDraft) -> BookView:
        with unit_of_work(self.factory) as session:
            author = AuthorRepository(session).get_by_id(author_id)
            if author is None:
                raise ValidationError("Author not found")
            return book_view(BookRepository(session).add(self._book(draft, author)))

    def get_book(self, book_id: int) -> BookView | None:
        with unit_of_work(self.factory) as session:
            book = BookRepository(session).get_by_id(book_id)
            return book_view(book) if book is not None else None

    def update_book(
        self, book_id: int, author_id: int, draft: BookDraft
    ) -> BookView | None:
        with unit_of_work(self.factory) as session:
            author = AuthorRepository(session).get_by_id(author_id)
            if author is None:
                raise ValidationError("Author not found")
            value = self._book(draft, author)
            book = BookRepository(session).update(
                book_id,
                title=value.title,
                year=value.year,
                pages=value.pages,
                author_id=author_id,
                isbn=value.isbn,
            )
            # An already loaded relationship may refer to the previous author.
            if book is not None:
                session.expire(book, ["author"])
            return book_view(book) if book is not None else None

    def delete_book(self, book_id: int) -> bool:
        with unit_of_work(self.factory) as session:
            return BookRepository(session).delete(book_id)

    def list_books(self, *, offset: int = 0, limit: int = 100) -> list[BookView]:
        with unit_of_work(self.factory) as session:
            return [
                book_view(b)
                for b in BookRepository(session).get_all(offset=offset, limit=limit)
            ]

    def find_by_author(self, name: str) -> list[BookView]:
        with unit_of_work(self.factory) as session:
            return [book_view(b) for b in BookRepository(session).find_by_author(name)]

    def filter_by_year(self, year: int) -> list[BookView]:
        self.policy.validate(year)
        with unit_of_work(self.factory) as session:
            return [book_view(b) for b in BookRepository(session).filter_by_year(year)]

    def largest_book(self) -> BookView | None:
        with unit_of_work(self.factory) as session:
            book = BookRepository(session).largest_book()
            return book_view(book) if book is not None else None

    def average_pages(self) -> float:
        with unit_of_work(self.factory) as session:
            return BookRepository(session).average_pages()

    def author_statistics(self) -> list[tuple[str, int, int, float]]:
        with unit_of_work(self.factory) as session:
            return BookRepository(session).author_statistics()
