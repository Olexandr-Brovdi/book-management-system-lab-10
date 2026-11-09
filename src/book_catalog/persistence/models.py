"""Normalized Author one-to-many Book tables with database-enforced invariants."""

from __future__ import annotations
from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Author(Base):
    __tablename__ = "authors"
    __table_args__ = (
        UniqueConstraint("name", name="uq_authors_name"),
        CheckConstraint("length(trim(name)) > 0", name="ck_authors_name"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    books: Mapped[list[Book]] = relationship(
        back_populates="author", cascade="all, delete-orphan", passive_deletes=True
    )


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_books_title"),
        CheckConstraint(
            "typeof(year) = 'integer' AND year BETWEEN 1 AND 9999", name="ck_books_year"
        ),
        CheckConstraint(
            "typeof(pages) = 'integer' AND pages > 0", name="ck_books_pages"
        ),
        UniqueConstraint("isbn", name="uq_books_isbn"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    pages: Mapped[int] = mapped_column(nullable=False)
    author_id: Mapped[int] = mapped_column(
        ForeignKey("authors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    isbn: Mapped[str | None] = mapped_column(String(32), nullable=True)
    author: Mapped[Author] = relationship(back_populates="books")
