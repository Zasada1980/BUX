"""Compatibility helpers for building HTTP clients in tests."""
from __future__ import annotations

from typing import Any, Protocol

from fastapi import FastAPI
from fastapi.testclient import TestClient as FastAPITestClient
from httpx import ASGITransport, Client as HTTPXClient


class SupportsClose(Protocol):
    """Protocol describing the ``close`` method shared by test clients."""

    def close(self) -> Any:  # pragma: no cover - signature compatibility only
        ...


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

    transport = ASGITransport(app=app)
    return HTTPXClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=True,
    )

