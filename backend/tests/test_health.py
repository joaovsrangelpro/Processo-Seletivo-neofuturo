import asyncio

import httpx
import pytest

from app.main import app


async def request(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(method, path, headers=headers)


def test_health_check() -> None:
    response = asyncio.run(request("GET", "/health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
def test_cors_allows_local_frontend_requests(origin: str, method: str) -> None:
    response = asyncio.run(
        request(
            "OPTIONS",
            "/contacts",
            {
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "content-type",
            },
        )
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert method in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in response.headers


def test_cors_rejects_unsupported_methods() -> None:
    response = asyncio.run(
        request(
            "OPTIONS",
            "/contacts",
            {
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "PUT",
            },
        )
    )

    assert response.status_code == 400
    assert "PUT" not in response.headers["access-control-allow-methods"]


def test_cors_does_not_allow_unknown_origins() -> None:
    response = asyncio.run(
        request(
            "OPTIONS",
            "/contacts",
            {
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    )

    assert "access-control-allow-origin" not in response.headers
