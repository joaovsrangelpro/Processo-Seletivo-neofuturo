import asyncio
from collections.abc import Generator
from unittest.mock import Mock

import httpx
import pytest
from openai import OpenAI
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models.ai_summary import AISummary
from app.models.contact import Contact
from app.models.contact_tag import ContactTag
from app.models.tag import Tag
from app.routers import contacts as contacts_router
from app.services import openai_service
from app.services.openai_service import (
    OpenAIRateLimitError,
    OpenAIServiceError,
    OpenAITimeoutError,
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


def create_contact(db: Session) -> Contact:
    contact = Contact(
        full_name="Joao Victor Rangel",
        email="joao@example.com",
        phone="(21) 98765-4321",
    )
    db.add(contact)
    db.flush()
    return contact


def add_tag(db: Session, contact: Contact, name: str) -> Tag:
    tag = Tag(name=name)
    db.add(tag)
    db.flush()
    db.add(ContactTag(contact_id=contact.id, tag_id=tag.id))
    db.flush()
    return tag


async def request(method: str, path: str, db: Session) -> httpx.Response:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path)
    finally:
        app.dependency_overrides.pop(get_db, None)


def configure_openai(
    monkeypatch: pytest.MonkeyPatch,
    result: str = "Professional contact summary.",
) -> Mock:
    generate_summary = Mock(return_value=result)
    monkeypatch.setattr(
        contacts_router.settings,
        "openai_api_key",
        "test-api-key",
    )
    monkeypatch.setattr(
        contacts_router,
        "generate_contact_summary",
        generate_summary,
    )
    return generate_summary


def test_summarizes_contact_without_tags_and_persists_result(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact = create_contact(db_session)
    generate_summary = configure_openai(monkeypatch)

    response = asyncio.run(
        request("POST", f"/contacts/{contact.id}/summarize", db_session)
    )

    assert response.status_code == 201
    data = response.json()
    assert data["contact_id"] == contact.id
    assert data["summary_text"] == "Professional contact summary."
    assert data["id"]
    assert data["generated_at"]
    generate_summary.assert_called_once_with(
        api_key="test-api-key",
        full_name="Joao Victor Rangel",
        email="joao@example.com",
        phone="(21) 98765-4321",
        tags=[],
    )

    stored_summary = db_session.get(AISummary, data["id"])
    assert stored_summary is not None
    assert stored_summary.contact_id == contact.id
    assert stored_summary.summary_text == "Professional contact summary."


@pytest.mark.parametrize(
    ("tag_names", "expected_tags"),
    [
        (["Cliente"], ["Cliente"]),
        (["Prospect", "Cliente"], ["Cliente", "Prospect"]),
    ],
)
def test_summarize_passes_contact_tags_to_service(
    tag_names: list[str],
    expected_tags: list[str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact = create_contact(db_session)
    for tag_name in tag_names:
        add_tag(db_session, contact, tag_name)
    generate_summary = configure_openai(monkeypatch)

    response = asyncio.run(
        request("POST", f"/contacts/{contact.id}/summarize", db_session)
    )

    assert response.status_code == 201
    assert generate_summary.call_count == 1
    assert generate_summary.call_args.kwargs["tags"] == expected_tags


def test_summarize_rejects_missing_contact_without_calling_openai(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generate_summary = configure_openai(monkeypatch)

    response = asyncio.run(
        request("POST", "/contacts/999999999/summarize", db_session)
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Contact not found."}
    generate_summary.assert_not_called()


def test_summarize_without_api_key_returns_service_unavailable(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact = create_contact(db_session)
    generate_summary = Mock()
    monkeypatch.setattr(contacts_router.settings, "openai_api_key", None)
    monkeypatch.setattr(
        contacts_router,
        "generate_contact_summary",
        generate_summary,
    )

    response = asyncio.run(
        request("POST", f"/contacts/{contact.id}/summarize", db_session)
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "OpenAI service is not configured."}
    generate_summary.assert_not_called()
    assert db_session.scalar(select(func.count(AISummary.id))) == 0


@pytest.mark.parametrize(
    ("service_error", "expected_status", "expected_detail"),
    [
        (
            OpenAIRateLimitError(),
            429,
            "OpenAI rate limit exceeded.",
        ),
        (
            OpenAITimeoutError(),
            504,
            "OpenAI request timed out.",
        ),
        (
            OpenAIServiceError(),
            502,
            "OpenAI service is unavailable.",
        ),
        (
            OpenAIServiceError(),
            502,
            "OpenAI service is unavailable.",
        ),
        (
            OpenAIServiceError(),
            502,
            "OpenAI service is unavailable.",
        ),
    ],
    ids=["rate-limit", "timeout", "connection", "api-error", "empty-response"],
)
def test_summarize_handles_openai_failure_without_persisting(
    service_error: Exception,
    expected_status: int,
    expected_detail: str,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact = create_contact(db_session)
    generate_summary = configure_openai(monkeypatch)
    generate_summary.side_effect = service_error

    response = asyncio.run(
        request("POST", f"/contacts/{contact.id}/summarize", db_session)
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    generate_summary.assert_called_once()
    assert db_session.scalar(select(func.count(AISummary.id))) == 0


def test_sdk_rate_limit_returns_429_without_retry_or_database_changes(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact = create_contact(db_session)
    generate_summary = configure_openai(monkeypatch)
    generate_summary.side_effect = openai_service.generate_contact_summary
    transport_handler = Mock(
        return_value=httpx.Response(
            429,
            json={"error": {
                "message": "internal-provider-detail",
                "type": "rate_limit_error",
                "code": "rate_limit_exceeded",
            }},
            headers={"x-provider-sensitive": "provider-only-marker"},
        )
    )
    with httpx.Client(transport=httpx.MockTransport(transport_handler)) as client:
        constructor = Mock(side_effect=lambda **options: OpenAI(**options, http_client=client))
        monkeypatch.setattr(openai_service, "OpenAI", constructor)

        response = asyncio.run(
            request("POST", f"/contacts/{contact.id}/summarize", db_session)
        )

    assert response.status_code == 429
    assert response.json() == {"detail": "OpenAI rate limit exceeded."}
    assert "internal-provider-detail" not in response.text
    assert "provider-only-marker" not in response.text
    assert "test-api-key" not in response.text
    assert "x-provider-sensitive" not in response.headers
    assert "authorization" not in response.headers
    generate_summary.assert_called_once()
    constructor.assert_called_once_with(
        api_key="test-api-key", max_retries=0, timeout=15.0,
    )
    transport_handler.assert_called_once()
    assert db_session.scalar(select(func.count(AISummary.id))) == 0
    db_session.refresh(contact)
    assert contact.full_name == "Joao Victor Rangel"
    assert db_session.is_active


def test_multiple_generations_create_history_and_get_returns_latest(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact = create_contact(db_session)
    generate_summary = configure_openai(monkeypatch)
    generate_summary.side_effect = ["First summary.", "Second summary."]

    first_response = asyncio.run(
        request("POST", f"/contacts/{contact.id}/summarize", db_session)
    )
    assert generate_summary.call_count == 1
    second_response = asyncio.run(
        request("POST", f"/contacts/{contact.id}/summarize", db_session)
    )
    assert generate_summary.call_count == 2

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    summaries = db_session.scalars(
        select(AISummary)
        .where(AISummary.contact_id == contact.id)
        .order_by(AISummary.id)
    ).all()
    assert [summary.summary_text for summary in summaries] == [
        "First summary.",
        "Second summary.",
    ]

    detail_response = asyncio.run(
        request("GET", f"/contacts/{contact.id}", db_session)
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["latest_ai_summary"] == {
        "id": summaries[1].id,
        "contact_id": contact.id,
        "summary_text": "Second summary.",
        "generated_at": summaries[1].generated_at.isoformat().replace(
            "+00:00", "Z"
        ),
    }


def test_persistence_failure_rolls_back_summary(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact = create_contact(db_session)
    configure_openai(monkeypatch)
    monkeypatch.setattr(
        db_session,
        "commit",
        Mock(side_effect=SQLAlchemyError("database failure")),
    )

    response = asyncio.run(
        request("POST", f"/contacts/{contact.id}/summarize", db_session)
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "The summary could not be saved."}
    assert db_session.scalar(select(func.count(AISummary.id))) == 0
