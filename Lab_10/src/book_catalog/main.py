"""Small demonstrator of the real import search export integration."""

import argparse
from pathlib import Path

from book_catalog.config import load_config
from book_catalog.exceptions import CatalogError
from book_catalog.exporters import JsonExporter
from book_catalog.importers import read_books
from book_catalog.repositories import InMemoryBookRepository
from book_catalog.services import CatalogReportService


def run(config_path: Path, author: str) -> int:
    config = load_config(config_path)
    books = read_books(config.input, config.policy)
    return CatalogReportService(
        InMemoryBookRepository(books), JsonExporter()
    ).export_author(author, config.output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lab_10 variant 2 book catalog")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--author", default="Франко")
    args = parser.parse_args()
    try:
        count = run(args.config, args.author)
    except CatalogError as error:
        parser.exit(1, f"Catalog error: {error}\n")
    print(f"Exported books: {count}")


if __name__ == "__main__":
    main()
