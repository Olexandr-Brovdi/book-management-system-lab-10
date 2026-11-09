"""Async REST façade: synchronous DB work is offloaded to a worker thread."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

import httpx
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Path as PathParam,
    Response,
    Request,
)
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from pydantic import TypeAdapter, ValidationError as SchemaError
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from book_catalog.config import Settings
from book_catalog.runtime import configure_logging


from book_catalog.database import (
    make_engine,
    session_factory,
    upgrade_database,
    PersistenceConflict,
)
from book_catalog.exceptions import ValidationError
from book_catalog.external_api import (
    HTTPSettings,
    ExternalError,
    ExternalTimeout,
    fetch_many,
)
from book_catalog.persistence.services import BookDraft, LibraryService
from book_catalog.schemas import (
    AuthorCreate,
    AuthorResponse,
    BookCreate,
    BookPatch,
    BookResponse,
    Statistics,
    BatchRequest,
    AuthorBooks,
)

Id = Annotated[int, PathParam(gt=0)]


def get_service(request: Request) -> LibraryService:
    return request.app.state.library


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


def not_found(resource: str):
    raise HTTPException(
        404, detail={"code": "not_found", "message": f"{resource} not found"}
    )


def create_app(
    database: Path | None = None,
    settings: HTTPSettings | None = None,
    runtime: Settings | None = None,
) -> FastAPI:
    runtime = runtime if runtime is not None else Settings()
    database = (
        database
        if database is not None
        else Path(os.environ["BOOK_DATABASE"])
        if "BOOK_DATABASE" in os.environ
        else runtime.database_path
    )
    settings = settings if settings is not None else HTTPSettings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        logger = configure_logging(runtime.log_level)
        await run_in_threadpool(upgrade_database, database)
        engine = make_engine(database)
        app.state.engine = engine
        app.state.runtime = runtime
        app.state.library = LibraryService(session_factory(engine))
        app.state.http_settings = settings
        app.state.semaphore = asyncio.Semaphore(settings.concurrency)
        try:
            async with httpx.AsyncClient(
                base_url=os.getenv("BOOK_UPSTREAM_URL", "http://127.0.0.1:8000"),
                timeout=settings.request_timeout,
                follow_redirects=False,
            ) as client:
                app.state.http = client
                logger.info(
                    "Book Catalog started version=1.0.0 environment=%s",
                    runtime.environment,
                )
                yield
        finally:
            await run_in_threadpool(engine.dispose)
            logger.info("Book Catalog stopped")

    app = FastAPI(
        title=runtime.app_name,
        version="1.0.0",
        description="Lab_10 variant 2 — Бровді Олександр, ФеП-32",
        lifespan=lifespan,
        docs_url=None,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        def check_database() -> None:
            with app.state.engine.connect() as connection:
                connection.exec_driver_sql("SELECT 1")

        try:
            await run_in_threadpool(check_database)
        except SQLAlchemyError as error:
            raise HTTPException(503, detail={"code": "database_unavailable"}) from error
        return {"status": "ok", "environment": runtime.environment, "version": "1.0.0"}

    app.mount(
        "/swagger-assets",
        StaticFiles(directory=Path(__file__).parent / "swagger_assets"),
        name="swagger-assets",
    )

    @app.get("/docs", include_in_schema=False)
    async def swagger():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="Book Catalog API — Swagger UI",
            swagger_js_url="/swagger-assets/swagger-ui-bundle.js",
            swagger_css_url="/swagger-assets/swagger-ui.css",
            swagger_ui_parameters={"defaultModelsExpandDepth": -1},
        )

    @app.exception_handler(PersistenceConflict)
    async def conflict(request, error):
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "code": "conflict",
                    "message": "Author name or ISBN already exists",
                }
            },
        )

    @app.exception_handler(ValidationError)
    async def invalid(request, error):
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "invalid_data", "message": str(error)}},
        )

    @app.exception_handler(ExternalError)
    async def upstream_error(request, error):
        return JSONResponse(
            status_code=504 if isinstance(error, ExternalTimeout) else 503,
            content={"detail": {"code": "upstream_error", "message": str(error)}},
        )

    @app.get("/")
    async def root():
        return {"message": "Book Catalog API", "lab": "Lab_10", "variant": 2}

    @app.post("/authors", response_model=AuthorResponse, status_code=201)
    async def create_author(data: AuthorCreate, service=Depends(get_service)):
        return await run_in_threadpool(service.create_author, data.name)

    @app.get("/authors", response_model=list[AuthorResponse])
    async def list_authors(service=Depends(get_service)):
        return await run_in_threadpool(service.list_authors)

    @app.post("/authors/batch", response_model=list[AuthorBooks])
    async def batch(
        data: BatchRequest, request: Request, client=Depends(get_http_client)
    ):
        try:
            raw = await asyncio.wait_for(
                fetch_many(
                    client, data.author_ids, request.app.state.semaphore, settings
                ),
                timeout=settings.batch_timeout,
            )
            return [
                AuthorBooks(
                    author_id=key,
                    books=TypeAdapter(list[BookResponse]).validate_python(value),
                )
                for key, value in zip(data.author_ids, raw)
            ]
        except TimeoutError as error:
            raise ExternalTimeout("Batch operation timed out") from error
        except SchemaError as error:
            raise ExternalError(
                "Upstream response does not match book schema"
            ) from error

    @app.get("/authors/{author_id}", response_model=AuthorResponse)
    async def get_author(author_id: Id, service=Depends(get_service)):
        author = await run_in_threadpool(service.get_author, author_id)
        return author if author is not None else not_found("Author")

    @app.patch("/authors/{author_id}", response_model=AuthorResponse)
    async def update_author(
        author_id: Id, data: AuthorCreate, service=Depends(get_service)
    ):
        author = await run_in_threadpool(service.update_author, author_id, data.name)
        return author if author is not None else not_found("Author")

    @app.delete("/authors/{author_id}", status_code=204)
    async def delete_author(author_id: Id, service=Depends(get_service)):
        if not await run_in_threadpool(service.delete_author, author_id):
            not_found("Author")
        return Response(status_code=204)

    @app.get("/authors/{author_id}/books", response_model=list[BookResponse])
    async def author_books(author_id: Id, service=Depends(get_service)):
        def load():
            author = service.get_author(author_id)
            if author is None:
                not_found("Author")
            return service.find_by_author(author.name)

        return await run_in_threadpool(load)

    @app.get("/books/statistics", response_model=Statistics)
    async def statistics(service=Depends(get_service)):
        def load():
            return Statistics(
                count=sum(row[1] for row in service.author_statistics()),
                average_pages=service.average_pages(),
                largest=service.largest_book(),
            )

        return await run_in_threadpool(load)

    @app.get("/books", response_model=list[BookResponse])
    async def list_books(
        author: str | None = None,
        year: int | None = Query(None, ge=1, le=2026),
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        sort: Literal["id", "year", "pages"] = "id",
        descending: bool = False,
        service=Depends(get_service),
    ):
        return await run_in_threadpool(
            service.list_filtered,
            author=author,
            year=year,
            offset=offset,
            limit=limit,
            sort=sort,
            descending=descending,
        )

    @app.post("/books", response_model=BookResponse, status_code=201)
    async def create_book(data: BookCreate, service=Depends(get_service)):
        def create():
            if service.get_author(data.author_id) is None:
                not_found("Author")
            return service.create_book(
                data.author_id, BookDraft(**data.model_dump(exclude={"author_id"}))
            )

        return await run_in_threadpool(create)

    @app.get("/books/{book_id}", response_model=BookResponse)
    async def get_book(book_id: Id, service=Depends(get_service)):
        book = await run_in_threadpool(service.get_book, book_id)
        return book if book is not None else not_found("Book")

    @app.patch("/books/{book_id}", response_model=BookResponse)
    async def update_book(book_id: Id, data: BookPatch, service=Depends(get_service)):
        def update():
            book = service.get_book(book_id)
            if book is None:
                not_found("Book")
            values = BookCreate.model_validate(
                BookResponse.model_validate(book).model_dump(exclude={"id", "author"})
                | data.model_dump(exclude_unset=True)
            )
            if service.get_author(values.author_id) is None:
                not_found("Author")
            return service.update_book(
                book_id,
                values.author_id,
                BookDraft(**values.model_dump(exclude={"author_id"})),
            )

        return await run_in_threadpool(update)

    @app.delete("/books/{book_id}", status_code=204)
    async def delete_book(book_id: Id, service=Depends(get_service)):
        if not await run_in_threadpool(service.delete_book, book_id):
            not_found("Book")
        return Response(status_code=204)

    return app


app = create_app()
