"""Compatibility helpers for building HTTP clients in tests."""
from __future__ import annotations

from typing import Any, Protocol

import anyio
from fastapi import FastAPI
from fastapi.testclient import TestClient as FastAPITestClient
from httpx import ASGITransport, AsyncClient as HTTPXAsyncClient


class SupportsClose(Protocol):
    """Protocol describing the ``close`` method shared by test clients."""

    def close(self) -> Any:  # pragma: no cover - signature compatibility only
        ...


class _AsyncClientAdapter:
    """Synchronous facade over ``httpx.AsyncClient`` for ASGI apps."""

    def __init__(self, app: FastAPI):
        self._client = HTTPXAsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            follow_redirects=True,
        )

    def request(self, method: str, url: str, **kwargs):
        async def _send():
            return await self._client.request(method, url, **kwargs)

        return anyio.run(_send)

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def close(self) -> None:
        anyio.run(self._client.aclose)


def build_test_client(app: FastAPI) -> SupportsClose:
    """Return a sync HTTP client that works across httpx versions.

    ``fastapi.testclient.TestClient`` relies on the ``httpx`` ``app=`` shortcut that
    was removed in 0.28.  When that happens we transparently fall back to a plain
    ``httpx.Client`` that mounts the ASGI transport manually, ensuring the tests can
    run even if the environment ships with a newer ``httpx`` release.
    """

    try:
        return FastAPITestClient(app)
    except TypeError as exc:
        if "unexpected keyword argument 'app'" not in str(exc):
            raise

    return _AsyncClientAdapter(app)
