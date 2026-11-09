"""Reusable HTTPX client, bounded concurrency, safe GET retries and cancellation."""

import asyncio
import math
import os
from dataclasses import dataclass
import httpx


class ExternalError(RuntimeError):
    pass


class ExternalTimeout(ExternalError):
    pass


@dataclass(frozen=True)
class HTTPSettings:
    request_timeout: float = 2.0
    batch_timeout: float = 10.0
    attempts: int = 3
    concurrency: int = 3
    backoff: float = 0.05

    def __post_init__(self):
        if (
            not all(
                math.isfinite(x) and x > 0
                for x in (self.request_timeout, self.batch_timeout)
            )
            or type(self.attempts) is not int
            or not 1 <= self.attempts <= 5
            or type(self.concurrency) is not int
            or not 1 <= self.concurrency <= 20
            or not math.isfinite(self.backoff)
            or self.backoff < 0
        ):
            raise ValueError("Invalid HTTP settings")

    @classmethod
    def from_env(cls):
        return cls(
            request_timeout=float(os.getenv("BOOK_HTTP_TIMEOUT", "2")),
            batch_timeout=float(os.getenv("BOOK_BATCH_TIMEOUT", "10")),
            attempts=int(os.getenv("BOOK_HTTP_ATTEMPTS", "3")),
            concurrency=int(os.getenv("BOOK_HTTP_CONCURRENCY", "3")),
            backoff=float(os.getenv("BOOK_HTTP_BACKOFF", "0.05")),
        )


async def fetch_with_retry(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
    settings: HTTPSettings,
):
    for attempt in range(settings.attempts):
        try:
            async with semaphore:
                response = await asyncio.wait_for(
                    client.get(url, timeout=settings.request_timeout),
                    timeout=settings.request_timeout,
                )
            response.raise_for_status()
            return response.json()
        except (TimeoutError, httpx.TimeoutException) as error:
            if attempt == settings.attempts - 1:
                raise ExternalTimeout("Upstream request timed out") from error
        except httpx.HTTPStatusError as error:
            if (
                response.status_code not in (429, 500, 502, 503, 504)
                or attempt == settings.attempts - 1
            ):
                raise ExternalError(
                    "Upstream returned an unsuccessful status"
                ) from error
        except httpx.RequestError as error:
            if attempt == settings.attempts - 1:
                raise ExternalError("Upstream network failure") from error
        except ValueError as error:
            raise ExternalError("Upstream returned invalid JSON") from error
        # Release the concurrency slot while waiting for exponential backoff.
        await asyncio.sleep(settings.backoff * (2**attempt))


async def fetch_many(
    client: httpx.AsyncClient,
    author_ids: list[int],
    semaphore: asyncio.Semaphore,
    settings: HTTPSettings,
) -> list:
    tasks = [
        asyncio.create_task(
            fetch_with_retry(client, semaphore, f"/authors/{author_id}/books", settings)
        )
        for author_id in author_ids
    ]
    try:
        return list(await asyncio.gather(*tasks))
    except BaseException:
        # gather does not cancel siblings automatically after an ordinary failure.
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
