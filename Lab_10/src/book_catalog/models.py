"""Immutable book values and explicit year policy."""

from dataclasses import asdict, dataclass

from book_catalog.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class YearPolicy:
    min_year: int = 1
    max_year: int = 2026

    def __post_init__(self) -> None:
        if (
            type(self.min_year) is not int
            or type(self.max_year) is not int
            or not 1 <= self.min_year <= self.max_year <= 9999
        ):
            raise ValidationError("Invalid year range")

    def validate(self, year: int) -> None:
        if type(year) is not int or not self.min_year <= year <= self.max_year:
            raise ValidationError("Year is outside the allowed range")


@dataclass(frozen=True, slots=True)
class Book:
    isbn: str
    title: str
    author: str
    year: int
    pages: int

    def __post_init__(self) -> None:
        for field in ("isbn", "title", "author"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{field} must be nonempty text")
            object.__setattr__(self, field, " ".join(value.split()))
        YearPolicy(1, 9999).validate(self.year)
        if type(self.pages) is not int or self.pages <= 0:
            raise ValidationError("Pages must be a positive integer")

    def to_dict(self) -> dict:
        return asdict(self)
