import asyncio

import httpx

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


def test_cors_allows_local_frontend_get_requests() -> None:
    response = asyncio.run(
        request(
            "OPTIONS",
            "/contacts",
            {
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "GET" in response.headers["access-control-allow-methods"]


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
