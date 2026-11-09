import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from book_catalog.api import create_app, get_http_client
from book_catalog.external_api import HTTPSettings

pytestmark = pytest.mark.integration


@pytest.fixture
def api(tmp_path):
    settings = HTTPSettings(request_timeout=0.1, batch_timeout=0.5, backoff=0)
    app = create_app(tmp_path / "api.sqlite", settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def author(api):
    response = api.post("/authors", json={"name": "Іван Франко"})
    assert response.status_code == 201
    return response.json()


def create(api, author, **changes):
    return api.post(
        "/books",
        json=dict(
            title="Мойсей", author_id=author["id"], year=1905, pages=80, isbn="isbn-1"
        )
        | changes,
    )


def test_api_crud_uses_real_database(api, author):
    made = create(api, author)
    assert made.status_code == 201
    book = made.json()
    assert book["author"] == "Іван Франко"
    assert api.get(f"/books/{book['id']}").json() == book
    changed = api.patch(f"/books/{book['id']}", json={"pages": 100, "isbn": None})
    assert changed.status_code == 200 and changed.json()["pages"] == 100
    assert changed.json()["title"] == "Мойсей" and changed.json()["isbn"] is None
    assert api.get(f"/authors/{author['id']}/books").json() == [changed.json()]
    deleted = api.delete(f"/books/{book['id']}")
    assert deleted.status_code == 204 and deleted.content == b""
    assert api.get(f"/books/{book['id']}").status_code == 404
    assert api.delete(f"/books/{book['id']}").status_code == 404


def test_author_crud_and_cascade(api, author):
    assert api.get("/authors").json() == [author]
    assert api.get(f"/authors/{author['id']}").json() == author
    assert (
        api.patch(f"/authors/{author['id']}", json={"name": "Франко"}).status_code
        == 200
    )
    book = create(api, author).json()
    assert api.delete(f"/authors/{author['id']}").status_code == 204
    assert api.get(f"/books/{book['id']}").status_code == 404
    assert api.delete(f"/authors/{author['id']}").status_code == 404


def test_filter_pagination_sort_and_statistics(api, author):
    create(api, author)
    create(api, author, title="Захар Беркут", year=1883, pages=192, isbn="isbn-2")
    other = api.post("/authors", json={"name": "Інший автор"}).json()
    create(api, other, title="Інша", year=1883, pages=10, isbn=None)
    result = api.get("/books", params={"author": "Іван Франко", "year": 1883}).json()
    assert [b["title"] for b in result] == ["Захар Беркут"]
    assert len(api.get("/books?offset=1&limit=1").json()) == 1
    ordered = api.get("/books?sort=pages&descending=true").json()
    assert [b["pages"] for b in ordered] == [192, 80, 10]
    stats = api.get("/books/statistics").json()
    assert stats["count"] == 3 and stats["average_pages"] == pytest.approx(282 / 3)
    assert stats["largest"]["title"] == "Захар Беркут"


@pytest.mark.parametrize(
    "changes",
    [
        {"title": " "},
        {"pages": 0},
        {"pages": True},
        {"pages": 1.2},
        {"year": 2027},
        {"year": "1905"},
        {"author_id": 0},
        {"extra": "field"},
        {"isbn": ""},
    ],
)
def test_invalid_create_rejected_without_database_changes(api, author, changes):
    assert create(api, author, **changes).status_code == 422
    assert api.get("/books").json() == []


@pytest.mark.parametrize(
    "body", [{}, {"title": None}, {"pages": None}, {"pages": 0}, {"unknown": 1}]
)
def test_invalid_patch_rejected(api, author, body):
    book = create(api, author).json()
    assert api.patch(f"/books/{book['id']}", json=body).status_code == 422
    assert api.get(f"/books/{book['id']}").json() == book


def test_patch_transfer_and_missing_author(api, author):
    book = create(api, author).json()
    other = api.post("/authors", json={"name": "Інший"}).json()
    changed = api.patch(f"/books/{book['id']}", json={"author_id": other["id"]})
    assert changed.status_code == 200 and changed.json()["author"] == "Інший"
    assert api.patch(f"/books/{book['id']}", json={"author_id": 999}).status_code == 404
    assert create(api, {"id": 999}, isbn=None).status_code == 404


def test_conflicts_are_409_and_rollback(api, author):
    first = create(api, author).json()
    assert api.post("/authors", json={"name": "Іван Франко"}).status_code == 409
    assert create(api, author, title="Duplicate").status_code == 409
    assert len(api.get("/books").json()) == 1
    assert api.get(f"/books/{first['id']}").status_code == 200


def test_service_validation_has_structured_response(api, author):
    from book_catalog.api import get_service
    from book_catalog.models import YearPolicy
    from book_catalog.persistence.services import LibraryService

    library = LibraryService(api.app.state.library.factory, YearPolicy(1900, 2026))
    api.app.dependency_overrides[get_service] = lambda: library
    try:
        response = create(api, author, year=1883)
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "invalid_data"
        assert api.get("/books").json() == []
    finally:
        api.app.dependency_overrides.clear()


@pytest.mark.parametrize("url", ["/books/999", "/authors/999", "/authors/999/books"])
def test_missing_resources_404(api, url):
    assert api.get(url).status_code == 404


def test_missing_patch_resources_and_validation(api):
    assert api.patch("/books/999", json={"title": "X"}).status_code == 404
    assert api.patch("/authors/999", json={"name": "X"}).status_code == 404
    assert api.get("/books/0").status_code == 422
    assert api.get("/books?limit=0").status_code == 422
    assert api.get("/books?sort=invalid").status_code == 422
    assert api.post("/authors", json={"name": " "}).status_code == 422
    assert api.get("/books/statistics").json() == {
        "count": 0,
        "average_pages": 0.0,
        "largest": None,
    }


def test_openapi_and_local_swagger_assets(api):
    assert api.get("/").json()["variant"] == 2
    assert api.get("/docs").status_code == 200
    assert api.get("/swagger-assets/swagger-ui-bundle.js").status_code == 200
    assert api.get("/openapi.json").json()["info"]["version"] == "1.0.0"
    assert api.get("/redoc").status_code == 200


@pytest.mark.asyncio
async def test_async_httpx_api_and_batch_real_flow(api, author):
    book = create(api, author).json()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api.app), base_url="http://test"
    ) as client:
        api.app.dependency_overrides[get_http_client] = lambda: client
        try:
            response = await client.post(
                "/authors/batch", json={"author_ids": [author["id"], author["id"]]}
            )
            assert response.status_code == 200
            assert response.json() == [{"author_id": author["id"], "books": [book]}] * 2
        finally:
            api.app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "body",
    [
        {"author_ids": []},
        {"author_ids": [0]},
        {"author_ids": [True]},
        {"author_ids": list(range(1, 52))},
    ],
)
def test_batch_input_is_bounded(api, body):
    assert api.post("/authors/batch", json=body).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,expected", [("status", 503), ("shape", 503), ("slow", 504)]
)
async def test_batch_failure_mapping(api, kind, expected):
    async def upstream(request):
        if kind == "slow":
            await asyncio.sleep(2)
        return httpx.Response(
            404 if kind == "status" else 200, json={"invalid": "shape"}
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(upstream), base_url="http://upstream"
    ) as client:
        api.app.dependency_overrides[get_http_client] = lambda: client
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=api.app), base_url="http://test"
            ) as caller:
                response = await caller.post(
                    "/authors/batch", json={"author_ids": [1, 2]}
                )
                assert response.status_code == expected
        finally:
            api.app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_total_batch_deadline(tmp_path):
    app = create_app(
        tmp_path / "deadline.sqlite",
        HTTPSettings(request_timeout=1, batch_timeout=0.01, backoff=0),
    )
    with TestClient(app):

        async def slow(request):
            await asyncio.sleep(1)
            return httpx.Response(200, json=[])

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(slow), base_url="http://upstream"
        ) as upstream:
            app.dependency_overrides[get_http_client] = lambda: upstream
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as caller:
                assert (
                    await caller.post("/authors/batch", json={"author_ids": [1]})
                ).status_code == 504
