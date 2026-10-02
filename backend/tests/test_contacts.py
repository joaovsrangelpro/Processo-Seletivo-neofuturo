import asyncio
from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models.contact import Contact


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


async def post_contact(payload: dict[str, object], db: Session) -> httpx.Response:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post("/contacts", json=payload)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_create_contact(db_session: Session) -> None:
    response = asyncio.run(
        post_contact(
            {
                "full_name": "  João   Victor Rangel ",
                "email": " JOAO@EMAIL.COM ",
                "phone": "21 98765-4321",
                "source": " manual ",
            },
            db_session,
        )
    )

    assert response.status_code == 201
    response_data = response.json()
    assert isinstance(response_data["id"], int)
    assert response_data["created_at"]
    assert response_data == {
        "id": response_data["id"],
        "full_name": "João Victor Rangel",
        "email": "joao@email.com",
        "phone": "(21) 98765-4321",
        "source": "manual",
        "address": None,
        "created_at": response_data["created_at"],
    }

    stored_contact = db_session.scalar(
        select(Contact).where(Contact.email == "joao@email.com")
    )
    assert stored_contact is not None
    assert stored_contact.full_name == "João Victor Rangel"
    assert stored_contact.phone == "(21) 98765-4321"
    assert stored_contact.source == "manual"


def test_create_contact_rejects_invalid_email(db_session: Session) -> None:
    response = asyncio.run(
        post_contact(
            {
                "full_name": "João Victor",
                "email": "not-an-email",
                "phone": "21987654321",
            },
            db_session,
        )
    )

    assert response.status_code == 422


def test_create_contact_rejects_invalid_phone(db_session: Session) -> None:
    response = asyncio.run(
        post_contact(
            {
                "full_name": "João Victor",
                "email": "invalid-phone@example.com",
                "phone": "21 8765-4321",
            },
            db_session,
        )
    )

    assert response.status_code == 422
    assert "exactly 11 digits" in response.json()["detail"][0]["msg"]


def test_create_contact_rejects_duplicate_email(db_session: Session) -> None:
    payload = {
        "full_name": "João Victor",
        "email": "duplicate@example.com",
        "phone": "21987654321",
    }

    first_response = asyncio.run(post_contact(payload, db_session))
    duplicate_response = asyncio.run(post_contact(payload, db_session))

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "A contact with this email already exists."
    }
