import asyncio
import httpx
import pytest
from book_catalog.external_api import (
    HTTPSettings,
    ExternalError,
    ExternalTimeout,
    fetch_many,
    fetch_with_retry,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def test_concurrency_is_bounded_and_results_keep_input_order():
    active = peak = 0

    async def handler(request):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.005)
            return httpx.Response(200, json={"url": request.url.path})
        finally:
            active -= 1

    settings = HTTPSettings(concurrency=2, backoff=0)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as client:
        results = await fetch_many(
            client, [1, 2, 3, 4, 5], asyncio.Semaphore(2), settings
        )
    assert peak == 2 and active == 0
    assert [r["url"] for r in results] == [f"/authors/{i}/books" for i in range(1, 6)]


async def test_retry_transient_status_with_exponential_backoff(monkeypatch):
    calls = 0
    sleeps = []

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503 if calls < 3 else 200, json={"ok": True})

    async def sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr("book_catalog.external_api.asyncio.sleep", sleep)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as client:
        result = await fetch_with_retry(
            client, asyncio.Semaphore(1), "/x", HTTPSettings(backoff=0.1)
        )
    assert result == {"ok": True} and calls == 3 and sleeps == [0.1, 0.2]


@pytest.mark.parametrize("kind", ["timeout", "network", "permanent", "json", "status"])
async def test_failure_policy_is_bounded(kind):
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        if kind == "timeout":
            raise httpx.ReadTimeout("slow")
        if kind == "network":
            raise httpx.ConnectError("offline")
        if kind == "json":
            return httpx.Response(200, text="invalid json")
        return httpx.Response(404 if kind == "permanent" else 503)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as client:
        with pytest.raises(ExternalTimeout if kind == "timeout" else ExternalError):
            await fetch_with_retry(
                client, asyncio.Semaphore(1), "/x", HTTPSettings(attempts=2, backoff=0)
            )
    assert calls == (1 if kind in ("permanent", "json") else 2)


async def test_sibling_tasks_cancelled_after_failure():
    active = 0

    async def handler(request):
        nonlocal active
        if "/1/" in request.url.path:
            await asyncio.sleep(0.01)
            return httpx.Response(404)
        active += 1
        try:
            await asyncio.sleep(1)
            return httpx.Response(200, json=[])
        finally:
            active -= 1

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as client:
        with pytest.raises(ExternalError):
            await fetch_many(client, [1, 2], asyncio.Semaphore(2), HTTPSettings())
    assert active == 0


async def test_http_settings_from_environment(monkeypatch):
    monkeypatch.setenv("BOOK_HTTP_ATTEMPTS", "2")
    monkeypatch.setenv("BOOK_HTTP_CONCURRENCY", "4")
    assert HTTPSettings.from_env().attempts == 2
    assert HTTPSettings.from_env().concurrency == 4


@pytest.mark.parametrize(
    "changes",
    [
        {"attempts": 0},
        {"concurrency": 0},
        {"request_timeout": 0},
        {"batch_timeout": float("inf")},
        {"backoff": -1},
    ],
)
async def test_invalid_http_settings(changes):
    with pytest.raises(ValueError):
        HTTPSettings(**changes)
