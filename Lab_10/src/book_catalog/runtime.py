"""Installed production entry point; configuration and logging contain no secrets."""

import argparse
import logging
import uvicorn

from book_catalog.config import Settings


def configure_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("book_catalog")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Book Catalog production API · Lab_10 variant 2"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    settings = Settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        "book_catalog.api:app",
        host=args.host,
        port=args.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
