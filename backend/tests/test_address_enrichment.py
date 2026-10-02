import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models.contact import Contact
from app.routers import contacts as contacts_router
from app.schemas.contact import AddressEnrichmentResponse
from app.services.viacep_service import (
    ViaCEPNotFoundError,
    ViaCEPServiceError,
    ViaCEPTimeoutError,
)


ADDRESS = AddressEnrichmentResponse(
    cep="22451-900",
    logradouro="Rua Major Rubens Vaz",
    bairro="Gavea",
    cidade="Rio de Janeiro",
    uf="RJ",
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def create_contact(
    db: Session,
    address: dict[str, str] | None = None,
) -> Contact:
    contact = Contact(
        full_name="Address Test",
        email="address-test@example.com",
        phone="(21) 98765-4321",
        address=address,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


async def post_enrichment(
    contact_id: int,
    cep: str,
    db: Session,
) -> httpx.Response:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                f"/contacts/{contact_id}/enrich-address",
                json={"cep": cep},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize("cep", ["22451-900", "22451900"])
def test_enriches_contact_with_normalized_cep(
    cep: str,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact = create_contact(db_session)
    fetch_address = AsyncMock(return_value=ADDRESS)
    monkeypatch.setattr(contacts_router, "fetch_address", fetch_address)

    response = asyncio.run(post_enrichment(contact.id, cep, db_session))

    assert response.status_code == 200
    assert response.json() == ADDRESS.model_dump()
    fetch_address.assert_awaited_once_with("22451900")

    db_session.refresh(contact)
    assert contact.address == ADDRESS.model_dump()


@pytest.mark.parametrize("cep", ["2245190", "22451A900"])
def test_rejects_invalid_cep(
    cep: str,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact = create_contact(db_session)
    fetch_address = AsyncMock()
    monkeypatch.setattr(contacts_router, "fetch_address", fetch_address)

    response = asyncio.run(post_enrichment(contact.id, cep, db_session))

    assert response.status_code == 422
    assert "exactly 8 digits" in response.json()["detail"][0]["msg"]
    fetch_address.assert_not_awaited()


def test_rejects_missing_contact_without_calling_viacep(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_address = AsyncMock()
    monkeypatch.setattr(contacts_router, "fetch_address", fetch_address)

    response = asyncio.run(post_enrichment(999999, "22451-900", db_session))

    assert response.status_code == 404
    assert response.json() == {"detail": "Contact not found."}
    fetch_address.assert_not_awaited()


@pytest.mark.parametrize(
    ("external_error", "expected_status", "expected_detail"),
    [
        (ViaCEPNotFoundError(), 404, "CEP not found."),
        (ViaCEPTimeoutError(), 504, "ViaCEP request timed out."),
        (ViaCEPServiceError(), 502, "ViaCEP service is unavailable."),
    ],
)
def test_external_failure_preserves_existing_address(
    external_error: Exception,
    expected_status: int,
    expected_detail: str,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_address = {
        "cep": "01001-000",
        "logradouro": "Praca da Se",
        "bairro": "Se",
        "cidade": "Sao Paulo",
        "uf": "SP",
    }
    contact = create_contact(db_session, address=previous_address)
    monkeypatch.setattr(
        contacts_router,
        "fetch_address",
        AsyncMock(side_effect=external_error),
    )

    response = asyncio.run(post_enrichment(contact.id, "22451-900", db_session))

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    db_session.refresh(contact)
    assert contact.address == previous_address


def test_replaces_existing_address(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact = create_contact(
        db_session,
        address={
            "cep": "01001-000",
            "logradouro": "Praca da Se",
            "bairro": "Se",
            "cidade": "Sao Paulo",
            "uf": "SP",
        },
    )
    monkeypatch.setattr(
        contacts_router,
        "fetch_address",
        AsyncMock(return_value=ADDRESS),
    )

    response = asyncio.run(post_enrichment(contact.id, "22451-900", db_session))

    assert response.status_code == 200
    db_session.refresh(contact)
    assert contact.address == ADDRESS.model_dump()
