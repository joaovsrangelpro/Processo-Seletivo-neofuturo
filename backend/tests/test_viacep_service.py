import asyncio
from collections.abc import Generator
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


@pytest.fixture(autouse=True)
def clear_address_cache() -> Generator[None, None, None]:
    viacep_service._cache.clear()
    try:
        yield
    finally:
        viacep_service._cache.clear()


class StubAsyncClient:
    def __init__(
        self,
        response: httpx.Response | None = None,
        error: httpx.HTTPError | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.requested_url: str | None = None
        self.request_count = 0

    async def __aenter__(self) -> "StubAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str) -> httpx.Response:
        self.request_count += 1
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


@pytest.fixture
def successful_client(monkeypatch: pytest.MonkeyPatch) -> StubAsyncClient:
    client = StubAsyncClient(response=make_response(200, json={
        "logradouro": "Rua Major Rubens Vaz",
        "bairro": "Gavea",
        "localidade": "Rio de Janeiro",
        "uf": "RJ",
    }))
    mock_client(monkeypatch, client)
    return client


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


@pytest.mark.parametrize("error_value", [True, "true"])
def test_fetch_address_rejects_unknown_cep(
    error_value: bool | str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = StubAsyncClient(
        response=make_response(200, json={"erro": error_value})
    )
    mock_client(monkeypatch, client)

    for _ in range(2):
        with pytest.raises(ViaCEPNotFoundError):
            asyncio.run(fetch_address("99999999"))
    assert client.request_count == 2
    assert viacep_service._cache == {}


def test_fetch_address_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", "https://viacep.com.br")
    client = StubAsyncClient(error=httpx.ReadTimeout("timeout", request=request))
    mock_client(monkeypatch, client)

    for _ in range(2):
        with pytest.raises(ViaCEPTimeoutError):
            asyncio.run(fetch_address("22451900"))
    assert client.request_count == 2
    assert viacep_service._cache == {}


def test_fetch_address_handles_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("GET", "https://viacep.com.br")
    client = StubAsyncClient(error=httpx.ConnectError("offline", request=request))
    mock_client(monkeypatch, client)

    for _ in range(2):
        with pytest.raises(ViaCEPServiceError):
            asyncio.run(fetch_address("22451900"))
    assert client.request_count == 2
    assert viacep_service._cache == {}


def test_fetch_address_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = StubAsyncClient(
        response=make_response(200, content=b"not-json"),
    )
    mock_client(monkeypatch, client)

    for _ in range(2):
        with pytest.raises(ViaCEPServiceError):
            asyncio.run(fetch_address("22451900"))
    assert client.request_count == 2
    assert viacep_service._cache == {}


def test_fetch_address_rejects_unexpected_http_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = StubAsyncClient(response=make_response(503, json={"error": "down"}))
    mock_client(monkeypatch, client)

    for _ in range(2):
        with pytest.raises(ViaCEPServiceError):
            asyncio.run(fetch_address("22451900"))
    assert client.request_count == 2
    assert viacep_service._cache == {}


def test_cache_miss_then_hit_for_equivalent_normalized_ceps(
    successful_client: StubAsyncClient,
) -> None:
    first = asyncio.run(fetch_address(" 22451-900 "))
    assert successful_client.request_count == 1
    assert successful_client.requested_url == "https://viacep.com.br/ws/22451900/json/"
    assert set(viacep_service._cache) == {"22451900"}

    second = asyncio.run(fetch_address("22451900"))
    assert successful_client.request_count == 1
    assert second.model_dump() == first.model_dump() == {
        "cep": "22451-900",
        "logradouro": "Rua Major Rubens Vaz",
        "bairro": "Gavea",
        "cidade": "Rio de Janeiro",
        "uf": "RJ",
    }


def test_different_cep_has_an_independent_cache_entry(
    successful_client: StubAsyncClient,
) -> None:
    first = asyncio.run(fetch_address("22451900"))
    second = asyncio.run(fetch_address("01001000"))

    assert successful_client.request_count == 2
    assert first.cep == "22451-900"
    assert second.cep == "01001-000"
    assert set(viacep_service._cache) == {"22451900", "01001000"}


def test_cache_ttl_expires_and_is_renewed_after_a_new_lookup(
    successful_client: StubAsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [1000.0]
    monkeypatch.setattr(viacep_service, "monotonic", lambda: clock[0])
    ttl = viacep_service.VIACEP_CACHE_TTL_SECONDS
    asyncio.run(fetch_address("22451900"))
    assert viacep_service._cache["22451900"][1] == 1000.0 + ttl

    clock[0] = 1000.0 + ttl - 0.001
    asyncio.run(fetch_address("22451900"))
    assert successful_client.request_count == 1

    clock[0] = 1000.0 + ttl
    asyncio.run(fetch_address("22451900"))
    assert successful_client.request_count == 2
    assert viacep_service._cache["22451900"][1] == clock[0] + ttl


def test_callers_cannot_mutate_cached_address(
    successful_client: StubAsyncClient,
) -> None:
    first = asyncio.run(fetch_address("22451900"))
    first.logradouro = "Changed by caller"
    second = asyncio.run(fetch_address("22451900"))
    assert second.logradouro == "Rua Major Rubens Vaz"
    second.logradouro = "Changed on cache hit"
    third = asyncio.run(fetch_address("22451900"))

    assert third.logradouro == "Rua Major Rubens Vaz"
    assert successful_client.request_count == 1


def test_cache_size_is_bounded_and_oldest_entry_is_evicted(
    successful_client: StubAsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(viacep_service, "monotonic", lambda: 1000.0)
    limit = viacep_service.VIACEP_CACHE_MAX_ENTRIES
    for number in range(limit + 1):
        asyncio.run(fetch_address(f"{number:08d}"))

    assert len(viacep_service._cache) == limit
    assert "00000000" not in viacep_service._cache
    assert "00000001" in viacep_service._cache
    assert f"{limit:08d}" in viacep_service._cache
    assert successful_client.request_count == limit + 1

    asyncio.run(fetch_address("00000000"))
    assert successful_client.request_count == limit + 2
    assert len(viacep_service._cache) == limit
    assert "00000001" not in viacep_service._cache


def test_expired_entries_are_removed_before_evicting_valid_entries(
    successful_client: StubAsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [0.0]
    monkeypatch.setattr(viacep_service, "monotonic", lambda: clock[0])
    monkeypatch.setattr(viacep_service, "VIACEP_CACHE_MAX_ENTRIES", 3)
    asyncio.run(fetch_address("22451900"))
    clock[0] = 100.0
    asyncio.run(fetch_address("01001000"))
    clock[0] = 200.0
    asyncio.run(fetch_address("30140071"))
    clock[0] = viacep_service.VIACEP_CACHE_TTL_SECONDS
    asyncio.run(fetch_address("20040002"))

    assert set(viacep_service._cache) == {"01001000", "30140071", "20040002"}
    asyncio.run(fetch_address("01001000"))
    assert successful_client.request_count == 4


@pytest.mark.parametrize("data", [
    [],
    {"logradouro": "Rua", "localidade": "Cidade", "uf": "RJ"},
    {"logradouro": None, "bairro": "Bairro", "localidade": "Cidade", "uf": "RJ"},
])
def test_invalid_response_is_never_cached(
    data: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = StubAsyncClient(response=make_response(200, json=data))
    mock_client(monkeypatch, client)

    for _ in range(2):
        with pytest.raises(ViaCEPServiceError):
            asyncio.run(fetch_address("22451900"))
    assert client.request_count == 2
    assert viacep_service._cache == {}


def test_invalid_cep_does_not_call_viacep_or_populate_cache(
    successful_client: StubAsyncClient,
) -> None:
    with pytest.raises(ValueError):
        asyncio.run(fetch_address("22451A900"))
    assert successful_client.request_count == 0
    assert viacep_service._cache == {}
