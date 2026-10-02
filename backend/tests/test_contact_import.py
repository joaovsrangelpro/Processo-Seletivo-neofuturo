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


async def import_contacts(
    payload: list[object],
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
            return await client.post("/contacts/import", json=payload)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_imports_multiple_contacts_with_normalized_data(db_session: Session) -> None:
    response = asyncio.run(
        import_contacts(
            [
                {
                    "full_name": "  Ana   Souza ",
                    "email": " ANA@EXAMPLE.COM ",
                    "phone": "(21) 98765-4321",
                    "source": " spreadsheet ",
                },
                {
                    "full_name": "Bruno Lima",
                    "email": "bruno@example.com",
                    "phone": "11 91234-5678",
                },
            ],
            db_session,
        )
    )

    assert response.status_code == 200
    assert response.json() == {"imported": 2, "rejected": 0, "errors": []}

    contacts = db_session.scalars(select(Contact).order_by(Contact.email)).all()
    assert [contact.email for contact in contacts] == [
        "ana@example.com",
        "bruno@example.com",
    ]
    assert contacts[0].full_name == "Ana Souza"
    assert contacts[0].phone == "(21) 98765-4321"
    assert contacts[0].source == "spreadsheet"
    assert contacts[1].phone == "(11) 91234-5678"


def test_rejects_invalid_email_without_persisting_contact(
    db_session: Session,
) -> None:
    response = asyncio.run(
        import_contacts(
            [
                {
                    "full_name": "Invalid Email",
                    "email": "not-an-email",
                    "phone": "21987654321",
                }
            ],
            db_session,
        )
    )

    data = response.json()
    assert response.status_code == 200
    assert data["imported"] == 0
    assert data["rejected"] == 1
    assert data["errors"][0]["index"] == 0
    assert "email" in data["errors"][0]["reason"].lower()
    assert db_session.scalar(select(Contact)) is None


def test_rejects_email_that_already_exists(db_session: Session) -> None:
    db_session.add(
        Contact(
            full_name="Existing Contact",
            email="existing@example.com",
            phone="(21) 98765-4321",
        )
    )
    db_session.commit()

    response = asyncio.run(
        import_contacts(
            [
                {
                    "full_name": "Duplicate Contact",
                    "email": " EXISTING@EXAMPLE.COM ",
                    "phone": "11912345678",
                }
            ],
            db_session,
        )
    )

    assert response.status_code == 200
    assert response.json() == {
        "imported": 0,
        "rejected": 1,
        "errors": [
            {
                "index": 0,
                "reason": "A contact with this email already exists.",
            }
        ],
    }
    assert len(db_session.scalars(select(Contact)).all()) == 1


def test_rejects_duplicate_email_within_batch(db_session: Session) -> None:
    response = asyncio.run(
        import_contacts(
            [
                {
                    "full_name": "First Contact",
                    "email": "same@example.com",
                    "phone": "21987654321",
                },
                {
                    "full_name": "Second Contact",
                    "email": " SAME@EXAMPLE.COM ",
                    "phone": "11912345678",
                },
            ],
            db_session,
        )
    )

    assert response.status_code == 200
    assert response.json() == {
        "imported": 1,
        "rejected": 1,
        "errors": [
            {"index": 1, "reason": "Duplicate email in import batch."}
        ],
    }
    contacts = db_session.scalars(select(Contact)).all()
    assert len(contacts) == 1
    assert contacts[0].full_name == "First Contact"


def test_mixed_batch_persists_valid_contacts_and_reports_errors(
    db_session: Session,
) -> None:
    response = asyncio.run(
        import_contacts(
            [
                {
                    "full_name": "Valid One",
                    "email": "valid-one@example.com",
                    "phone": "21987654321",
                },
                {
                    "full_name": "Bad Email",
                    "email": "invalid",
                    "phone": "21987654321",
                },
                {
                    "full_name": "Bad Phone",
                    "email": "bad-phone@example.com",
                    "phone": "1234",
                },
                {
                    "full_name": "  Valid   Two ",
                    "email": " VALID-TWO@EXAMPLE.COM ",
                    "phone": "(11) 91234-5678",
                },
            ],
            db_session,
        )
    )

    data = response.json()
    assert response.status_code == 200
    assert data["imported"] == 2
    assert data["rejected"] == 2
    assert [error["index"] for error in data["errors"]] == [1, 2]
    assert "email" in data["errors"][0]["reason"].lower()
    assert "11 digits" in data["errors"][1]["reason"]

    contacts = db_session.scalars(select(Contact).order_by(Contact.email)).all()
    assert [contact.email for contact in contacts] == [
        "valid-one@example.com",
        "valid-two@example.com",
    ]
    assert contacts[1].full_name == "Valid Two"


def test_imports_empty_array(db_session: Session) -> None:
    response = asyncio.run(import_contacts([], db_session))

    assert response.status_code == 200
    assert response.json() == {"imported": 0, "rejected": 0, "errors": []}
    assert db_session.scalar(select(Contact)) is None
