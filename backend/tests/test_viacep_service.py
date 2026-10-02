import asyncio
from typing import Any

import httpx
import pytest

from app.services import viacep_service
from app.services.viacep_service import (
    ViaCEPNotFoundError,
    ViaCEPServiceError,
    ViaCEPTimeoutError,
    fetch_address,
)


class StubAsyncClient:
    def __init__(
        self,
        response: httpx.Response | None = None,
        error: httpx.HTTPError | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.requested_url: str | None = None

    async def __aenter__(self) -> "StubAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str) -> httpx.Response:
        self.requested_url = url
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def mock_client(
    monkeypatch: pytest.MonkeyPatch,
    client: StubAsyncClient,
) -> dict[str, Any]:
    options: dict[str, Any] = {}

    def build_client(**kwargs: Any) -> StubAsyncClient:
        options.update(kwargs)
        return client

    monkeypatch.setattr(viacep_service.httpx, "AsyncClient", build_client)
    return options


def make_response(
    status_code: int,
    *,
    json: object | None = None,
    content: bytes | None = None,
) -> httpx.Response:
    request = httpx.Request("GET", "https://viacep.com.br/ws/22451900/json/")
    return httpx.Response(
        status_code,
        json=json,
        content=content,
        request=request,
    )


def test_fetch_address_maps_viacep_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = make_response(
        200,
        json={
            "cep": "22451-900",
            "logradouro": "Rua Major Rubens Vaz",
            "complemento": "unused",
            "bairro": "Gavea",
            "localidade": "Rio de Janeiro",
            "uf": "RJ",
            "ibge": "unused",
        },
    )
    client = StubAsyncClient(response=response)
    options = mock_client(monkeypatch, client)

    address = asyncio.run(fetch_address("22451900"))

    assert address.model_dump() == {
        "cep": "22451-900",
        "logradouro": "Rua Major Rubens Vaz",
        "bairro": "Gavea",
        "cidade": "Rio de Janeiro",
        "uf": "RJ",
    }
    assert client.requested_url == "https://viacep.com.br/ws/22451900/json/"
    assert options["timeout"] == 5.0


def test_fetch_address_rejects_unknown_cep(monkeypatch: pytest.MonkeyPatch) -> None:
    client = StubAsyncClient(response=make_response(200, json={"erro": True}))
    mock_client(monkeypatch, client)

    with pytest.raises(ViaCEPNotFoundError):
        asyncio.run(fetch_address("99999999"))


def test_fetch_address_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", "https://viacep.com.br")
    client = StubAsyncClient(error=httpx.ReadTimeout("timeout", request=request))
    mock_client(monkeypatch, client)

    with pytest.raises(ViaCEPTimeoutError):
        asyncio.run(fetch_address("22451900"))


def test_fetch_address_handles_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("GET", "https://viacep.com.br")
    client = StubAsyncClient(error=httpx.ConnectError("offline", request=request))
    mock_client(monkeypatch, client)

    with pytest.raises(ViaCEPServiceError):
        asyncio.run(fetch_address("22451900"))


def test_fetch_address_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = StubAsyncClient(
        response=make_response(200, content=b"not-json"),
    )
    mock_client(monkeypatch, client)

    with pytest.raises(ViaCEPServiceError):
        asyncio.run(fetch_address("22451900"))


def test_fetch_address_rejects_unexpected_http_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = StubAsyncClient(response=make_response(503, json={"error": "down"}))
    mock_client(monkeypatch, client)

    with pytest.raises(ViaCEPServiceError):
        asyncio.run(fetch_address("22451900"))
