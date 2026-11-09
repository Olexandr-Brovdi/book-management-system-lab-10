"""Execute with the clean wheel interpreter, from a directory outside the source."""

from importlib.metadata import version
from pathlib import Path
import json
import tempfile
from fastapi.testclient import TestClient
import book_catalog
from book_catalog.api import create_app
from book_catalog.config import Settings


def main():
    with tempfile.TemporaryDirectory(prefix="book-wheel-") as folder:
        database = Path(folder) / "library.db"
        config = Settings(
            database_url=f"sqlite:///{database}", environment="test", _env_file=None
        )
        app = create_app(runtime=config)
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            author = client.post("/authors", json={"name": "Іван Франко"}).json()
            book = client.post(
                "/books",
                json={
                    "title": "Захар Беркут",
                    "author_id": author["id"],
                    "year": 1883,
                    "pages": 192,
                },
            )
            assert book.status_code == 201
            assert client.get("/books?year=1883").json()[0]["pages"] == 192
            assert client.get("/books/statistics").json()["average_pages"] == 192
            assert client.get("/swagger-assets/swagger-ui-bundle.js").status_code == 200
            assert client.get("/docs").status_code == 200
        with TestClient(create_app(runtime=config)) as restarted:
            assert len(restarted.get("/books").json()) == 1
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "distribution": "book-catalog",
                    "version": version("book-catalog"),
                    "module": str(Path(book_catalog.__file__).resolve()),
                    "checks": [
                        "packaged migrations",
                        "health",
                        "author/book CRUD",
                        "filters/statistics",
                        "Swagger assets",
                        "SQLite persistence across restart",
                    ],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
