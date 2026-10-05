import asyncio
import json
from pathlib import Path
import subprocess
import sys

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


@pytest.mark.parametrize(
    ("origin", "method", "expected_status", "allowed_origin"),
    [
        ("https://frontend.example.test", "GET", 200, True),
        ("https://frontend.example.test", "POST", 200, True),
        ("https://frontend.example.test", "DELETE", 200, True),
        ("https://admin.example.test", "GET", 200, True),
        ("https://unknown.example.test", "GET", 400, False),
        ("http://localhost:3000", "GET", 400, False),
        ("https://frontend.example.test", "PUT", 400, True),
    ],
)
def test_startup_and_cors_with_production_environment_without_openai(
    origin: str,
    method: str,
    expected_status: int,
    allowed_origin: bool,
) -> None:
    # A fresh process verifies middleware reads configuration at startup.
    script = """
import json
import sys
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    health = client.get('/health')
    preflight = client.options('/contacts', headers={
        'Origin': sys.argv[1],
        'Access-Control-Request-Method': sys.argv[2],
        'Access-Control-Request-Headers': 'content-type',
    })
    print(json.dumps({
        'health_status': health.status_code,
        'health_body': health.json(),
        'preflight_status': preflight.status_code,
        'headers': dict(preflight.headers),
    }))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, origin, method],
        cwd=Path(__file__).resolve().parents[1],
        env={
            "DATABASE_URL": "postgresql://example:sample@database.invalid/contacts",
            "OPENAI_API_KEY": "",
            "FRONTEND_ORIGINS": (
                " https://frontend.example.test , , https://admin.example.test, "
            ),
        },
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    assert data["health_status"] == 200
    assert data["health_body"] == {"status": "ok"}
    assert data["preflight_status"] == expected_status
    headers = data["headers"]
    if allowed_origin:
        assert headers["access-control-allow-origin"] == origin
    else:
        assert "access-control-allow-origin" not in headers
    assert headers["access-control-allow-methods"] == "GET, POST, DELETE"
    assert "access-control-allow-credentials" not in headers
