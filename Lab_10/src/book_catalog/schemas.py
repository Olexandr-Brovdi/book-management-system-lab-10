"""Explicit request/response contracts for books, authors and async batches."""

from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=250)
]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
Year = Annotated[int, Field(strict=True, ge=1, le=2026)]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AuthorCreate(Schema):
    name: Text = Field(max_length=200)


class AuthorResponse(AuthorCreate):
    id: int
    book_ids: tuple[int, ...]


class BookCreate(Schema):
    title: Text
    author_id: PositiveInt
    year: Year
    pages: PositiveInt
    isbn: Text | None = Field(default=None, max_length=32)


class BookPatch(Schema):
    title: Text | None = None
    author_id: PositiveInt | None = None
    year: Year | None = None
    pages: PositiveInt | None = None
    isbn: Text | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("PATCH must contain at least one field")
        if any(
            getattr(self, name) is None for name in self.model_fields_set - {"isbn"}
        ):
            raise ValueError("Only isbn can be null")
        return self


class BookResponse(BookCreate):
    id: int
    author: str


class Statistics(Schema):
    count: int
    average_pages: float
    largest: BookResponse | None


class BatchRequest(Schema):
    author_ids: list[PositiveInt] = Field(min_length=1, max_length=50)


class AuthorBooks(Schema):
    author_id: int
    books: list[BookResponse]
