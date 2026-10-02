import asyncio
from collections.abc import Generator
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models.contact import Contact
from app.models.contact_tag import ContactTag
from app.models.tag import Tag


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


async def request(
    method: str,
    path: str,
    db: Session,
    json: dict[str, Any] | None = None,
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
            return await client.request(method, path, json=json)
    finally:
        app.dependency_overrides.pop(get_db, None)


def create_contact(db: Session, email: str = "tags@example.com") -> Contact:
    contact = Contact(
        full_name="Tag Test Contact",
        email=email,
        phone="(21) 98765-4321",
    )
    db.add(contact)
    db.flush()
    return contact


def create_tag(db: Session, name: str = "Cliente") -> Tag:
    tag = Tag(name=name)
    db.add(tag)
    db.flush()
    return tag


def test_create_tag(db_session: Session) -> None:
    response = asyncio.run(request("POST", "/tags", db_session, {"name": "Cliente"}))

    assert response.status_code == 201
    assert isinstance(response.json()["id"], int)
    assert response.json()["name"] == "Cliente"


def test_create_tag_trims_name(db_session: Session) -> None:
    response = asyncio.run(
        request("POST", "/tags", db_session, {"name": "  Cliente Premium  "})
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Cliente Premium"


def test_create_tag_rejects_empty_name(db_session: Session) -> None:
    response = asyncio.run(request("POST", "/tags", db_session, {"name": "   "}))

    assert response.status_code == 422
    assert "cannot be empty" in response.json()["detail"][0]["msg"]


def test_create_tag_rejects_duplicate_name(db_session: Session) -> None:
    first_response = asyncio.run(
        request("POST", "/tags", db_session, {"name": "Cliente"})
    )
    duplicate_response = asyncio.run(
        request("POST", "/tags", db_session, {"name": "Cliente"})
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "A tag with this name already exists."
    }


def test_create_tag_rejects_case_insensitive_duplicate(db_session: Session) -> None:
    first_response = asyncio.run(
        request("POST", "/tags", db_session, {"name": "Cliente"})
    )
    duplicate_response = asyncio.run(
        request("POST", "/tags", db_session, {"name": "CLIENTE"})
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409


def test_add_tag_to_contact(db_session: Session) -> None:
    contact = create_contact(db_session)
    tag = create_tag(db_session)

    response = asyncio.run(
        request(
            "POST",
            f"/contacts/{contact.id}/tags",
            db_session,
            {"tag_id": tag.id},
        )
    )

    assert response.status_code == 201
    assert response.json() == {
        "contact_id": contact.id,
        "tag_id": tag.id,
        "tag_name": "Cliente",
    }
    assert db_session.get(ContactTag, (contact.id, tag.id)) is not None


def test_add_tag_rejects_missing_contact(db_session: Session) -> None:
    tag = create_tag(db_session)

    response = asyncio.run(
        request(
            "POST",
            "/contacts/999999999/tags",
            db_session,
            {"tag_id": tag.id},
        )
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Contact not found."}


def test_add_tag_rejects_missing_tag(db_session: Session) -> None:
    contact = create_contact(db_session)

    response = asyncio.run(
        request(
            "POST",
            f"/contacts/{contact.id}/tags",
            db_session,
            {"tag_id": 999999999},
        )
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Tag not found."}


def test_add_tag_rejects_duplicate_association(db_session: Session) -> None:
    contact = create_contact(db_session)
    tag = create_tag(db_session)
    db_session.add(ContactTag(contact_id=contact.id, tag_id=tag.id))
    db_session.flush()

    response = asyncio.run(
        request(
            "POST",
            f"/contacts/{contact.id}/tags",
            db_session,
            {"tag_id": tag.id},
        )
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "This tag is already associated with the contact."
    }


def test_remove_tag_from_contact_preserves_records(db_session: Session) -> None:
    contact = create_contact(db_session)
    tag = create_tag(db_session)
    db_session.add(ContactTag(contact_id=contact.id, tag_id=tag.id))
    db_session.flush()

    response = asyncio.run(
        request(
            "DELETE",
            f"/contacts/{contact.id}/tags/{tag.id}",
            db_session,
        )
    )

    assert response.status_code == 204
    assert response.content == b""
    assert db_session.get(ContactTag, (contact.id, tag.id)) is None
    assert db_session.get(Contact, contact.id) is not None
    assert db_session.get(Tag, tag.id) is not None


def test_remove_tag_rejects_missing_association(db_session: Session) -> None:
    contact = create_contact(db_session)
    tag = create_tag(db_session)

    response = asyncio.run(
        request(
            "DELETE",
            f"/contacts/{contact.id}/tags/{tag.id}",
            db_session,
        )
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "This tag is not associated with the contact."
    }
