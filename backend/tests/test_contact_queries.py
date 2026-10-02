import asyncio
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models.ai_summary import AISummary
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


async def get(path: str, db: Session) -> httpx.Response:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)
    finally:
        app.dependency_overrides.pop(get_db, None)


def create_contact(db: Session, number: int) -> Contact:
    contact = Contact(
        full_name=f"Contact {number}",
        email=f"contact-{number}@example.com",
        phone="(21) 98765-4321",
        source="test",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        + timedelta(minutes=number),
    )
    db.add(contact)
    db.flush()
    return contact


def create_tag(db: Session, name: str) -> Tag:
    tag = Tag(name=name)
    db.add(tag)
    db.flush()
    return tag


def associate(db: Session, contact: Contact, tag: Tag) -> None:
    db.add(ContactTag(contact_id=contact.id, tag_id=tag.id))
    db.flush()


def create_summary(
    db: Session,
    contact: Contact,
    text: str,
    generated_at: datetime,
) -> AISummary:
    summary = AISummary(
        contact_id=contact.id,
        summary_text=text,
        generated_at=generated_at,
    )
    db.add(summary)
    db.flush()
    return summary


def test_list_contacts_returns_empty_page(db_session: Session) -> None:
    response = asyncio.run(get("/contacts", db_session))

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 1,
        "page_size": 10,
        "total": 0,
        "pages": 0,
    }


def test_list_contacts_returns_existing_contacts(db_session: Session) -> None:
    contact = create_contact(db_session, 1)

    response = asyncio.run(get("/contacts", db_session))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["pages"] == 1
    assert response.json()["items"][0]["id"] == contact.id
    assert response.json()["items"][0]["has_ai_summary"] is False


def test_list_contacts_paginates_with_stable_order(db_session: Session) -> None:
    contacts = [create_contact(db_session, number) for number in range(1, 4)]

    first_page = asyncio.run(get("/contacts?page=1&page_size=2", db_session))
    second_page = asyncio.run(get("/contacts?page=2&page_size=2", db_session))

    assert first_page.status_code == 200
    assert first_page.json()["page"] == 1
    assert first_page.json()["page_size"] == 2
    assert first_page.json()["total"] == 3
    assert first_page.json()["pages"] == 2
    assert [item["id"] for item in first_page.json()["items"]] == [
        contacts[2].id,
        contacts[1].id,
    ]
    assert second_page.json()["page"] == 2
    assert [item["id"] for item in second_page.json()["items"]] == [
        contacts[0].id
    ]


@pytest.mark.parametrize(
    "path",
    [
        "/contacts?page=0",
        "/contacts?page_size=0",
        "/contacts?page_size=101",
    ],
)
def test_list_contacts_rejects_invalid_pagination(
    path: str,
    db_session: Session,
) -> None:
    response = asyncio.run(get(path, db_session))

    assert response.status_code == 422


def test_list_contacts_filters_by_tag_case_insensitively(
    db_session: Session,
) -> None:
    matching_contact = create_contact(db_session, 1)
    other_contact = create_contact(db_session, 2)
    client_tag = create_tag(db_session, "Cliente")
    other_tag = create_tag(db_session, "Prospect")
    associate(db_session, matching_contact, client_tag)
    associate(db_session, other_contact, other_tag)

    response = asyncio.run(get("/contacts?tag=cLiEnTe", db_session))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["pages"] == 1
    assert [item["id"] for item in response.json()["items"]] == [
        matching_contact.id
    ]


def test_list_contacts_returns_empty_page_for_unknown_tag(
    db_session: Session,
) -> None:
    create_contact(db_session, 1)

    response = asyncio.run(get("/contacts?tag=Unknown", db_session))

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0
    assert response.json()["pages"] == 0


def test_list_contacts_indicates_existing_ai_summary(db_session: Session) -> None:
    contact = create_contact(db_session, 1)
    create_summary(
        db_session,
        contact,
        "Summary content",
        datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    response = asyncio.run(get("/contacts", db_session))

    assert response.status_code == 200
    assert response.json()["items"][0]["has_ai_summary"] is True
    assert "summary_text" not in response.json()["items"][0]


def test_get_contact_without_tags_or_summary(db_session: Session) -> None:
    contact = create_contact(db_session, 1)

    response = asyncio.run(get(f"/contacts/{contact.id}", db_session))

    assert response.status_code == 200
    assert response.json()["id"] == contact.id
    assert response.json()["address"] is None
    assert response.json()["tags"] == []
    assert response.json()["latest_ai_summary"] is None


def test_get_contact_returns_not_found(db_session: Session) -> None:
    response = asyncio.run(get("/contacts/999999999", db_session))

    assert response.status_code == 404
    assert response.json() == {"detail": "Contact not found."}


def test_get_contact_with_one_tag(db_session: Session) -> None:
    contact = create_contact(db_session, 1)
    tag = create_tag(db_session, "Cliente")
    associate(db_session, contact, tag)

    response = asyncio.run(get(f"/contacts/{contact.id}", db_session))

    assert response.status_code == 200
    assert response.json()["tags"] == [{"id": tag.id, "name": "Cliente"}]


def test_get_contact_with_multiple_tags(db_session: Session) -> None:
    contact = create_contact(db_session, 1)
    prospect = create_tag(db_session, "Prospect")
    client = create_tag(db_session, "Cliente")
    associate(db_session, contact, prospect)
    associate(db_session, contact, client)

    response = asyncio.run(get(f"/contacts/{contact.id}", db_session))

    assert response.status_code == 200
    assert response.json()["tags"] == [
        {"id": client.id, "name": "Cliente"},
        {"id": prospect.id, "name": "Prospect"},
    ]


def test_get_contact_with_one_summary(db_session: Session) -> None:
    contact = create_contact(db_session, 1)
    summary = create_summary(
        db_session,
        contact,
        "Only summary",
        datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    response = asyncio.run(get(f"/contacts/{contact.id}", db_session))

    assert response.status_code == 200
    assert response.json()["latest_ai_summary"]["id"] == summary.id
    assert response.json()["latest_ai_summary"]["summary_text"] == "Only summary"


def test_get_contact_returns_latest_summary(db_session: Session) -> None:
    contact = create_contact(db_session, 1)
    create_summary(
        db_session,
        contact,
        "Older summary",
        datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    latest_summary = create_summary(
        db_session,
        contact,
        "Latest summary",
        datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    response = asyncio.run(get(f"/contacts/{contact.id}", db_session))

    assert response.status_code == 200
    assert response.json()["latest_ai_summary"]["id"] == latest_summary.id
    assert response.json()["latest_ai_summary"]["summary_text"] == "Latest summary"
