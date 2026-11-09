"""Repositories flush only; the service Unit of Work commits the whole operation."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from book_catalog.persistence.models import Author, Book


class AuthorRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, name: str) -> Author:
        author = Author(name=name)
        self.session.add(author)
        self.session.flush()
        return author

    def get_by_id(self, author_id: int) -> Author | None:
        return self.session.get(Author, author_id, options=[selectinload(Author.books)])

    def get_all(self) -> list[Author]:
        return list(
            self.session.scalars(
                select(Author).options(selectinload(Author.books)).order_by(Author.id)
            )
        )

    def get_by_name(self, name: str) -> Author | None:
        return self.session.scalar(select(Author).where(Author.name == name))

    def update(self, author_id: int, name: str) -> Author | None:
        author = self.get_by_id(author_id)
        if author is not None:
            author.name = name
            self.session.flush()
        return author

    def delete(self, author_id: int) -> bool:
        author = self.get_by_id(author_id)
        if author is None:
            return False
        self.session.delete(author)
        self.session.flush()
        return True


class BookRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(
        self, *, author=None, year=None, offset=0, limit=20, sort="id", descending=False
    ):
        columns = {"id": Book.id, "year": Book.year, "pages": Book.pages}
        statement = select(Book).join(Author)
        if author is not None:
            statement = statement.where(Author.name == author)
        if year is not None:
            statement = statement.where(Book.year == year)
        column = columns[sort]
        statement = statement.order_by(
            column.desc() if descending else column.asc(), Book.id
        )
        return list(self.session.scalars(statement.offset(offset).limit(limit)))

    def add(self, book: Book) -> Book:
        self.session.add(book)
        self.session.flush()
        return book

    def get_by_id(self, book_id: int) -> Book | None:
        return self.session.get(Book, book_id)

    def get_all(self, *, offset: int = 0, limit: int = 100) -> list[Book]:
        if type(offset) is not int or type(limit) is not int or offset < 0 or limit < 1:
            raise ValueError("Invalid pagination")
        return list(
            self.session.scalars(
                select(Book).order_by(Book.id).offset(offset).limit(limit)
            )
        )

    def find_by_author(self, name: str) -> list[Book]:
        return list(
            self.session.scalars(
                select(Book).join(Author).where(Author.name == name).order_by(Book.id)
            )
        )

    def filter_by_year(self, year: int) -> list[Book]:
        return list(
            self.session.scalars(
                select(Book).where(Book.year == year).order_by(Book.id)
            )
        )

    def largest_book(self) -> Book | None:
        return self.session.scalar(
            select(Book).order_by(Book.pages.desc(), Book.id).limit(1)
        )

    def average_pages(self) -> float:
        value = self.session.scalar(select(func.avg(Book.pages)))
        return float(value) if value is not None else 0.0

    def author_statistics(self) -> list[tuple[str, int, int, float]]:
        statement = (
            select(
                Author.name,
                func.count(Book.id),
                func.coalesce(func.sum(Book.pages), 0),
                func.coalesce(func.avg(Book.pages), 0.0),
            )
            .outerjoin(Book)
            .group_by(Author.id, Author.name)
            .order_by(Author.id)
        )
        return [tuple(row) for row in self.session.execute(statement)]

    def update(
        self,
        book_id: int,
        *,
        title: str,
        year: int,
        pages: int,
        author_id: int,
        isbn: str | None,
    ) -> Book | None:
        book = self.get_by_id(book_id)
        if book is not None:
            book.title, book.year, book.pages = title, year, pages
            book.author_id, book.isbn = author_id, isbn
            self.session.flush()
        return book

    def delete(self, book_id: int) -> bool:
        book = self.get_by_id(book_id)
        if book is None:
            return False
        self.session.delete(book)
        self.session.flush()
        self.session.expire(book.author, ["books"])
        return True
