from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models.ai_summary import AISummary
from app.models.contact import Contact
from app.models.contact_tag import ContactTag
from app.models.tag import Tag
from app.schemas.contact import (
    AddressEnrichmentRequest,
    AddressEnrichmentResponse,
    AISummaryResponse,
    ContactCreate,
    ContactDetailResponse,
    ContactImportError,
    ContactImportResponse,
    ContactListItem,
    ContactListResponse,
    ContactResponse,
)
from app.schemas.tag import ContactTagCreate, ContactTagResponse, TagResponse
from app.services.openai_service import (
    OpenAIRateLimitError,
    OpenAIServiceError,
    OpenAITimeoutError,
    generate_contact_summary,
)
from app.services.viacep_service import (
    ViaCEPNotFoundError,
    ViaCEPServiceError,
    ViaCEPTimeoutError,
    fetch_address,
)


router = APIRouter(prefix="/contacts", tags=["contacts"])

DUPLICATE_EMAIL_DETAIL = "A contact with this email already exists."
DUPLICATE_BATCH_EMAIL_DETAIL = "Duplicate email in import batch."
CONTACT_NOT_FOUND_DETAIL = "Contact not found."
TAG_NOT_FOUND_DETAIL = "Tag not found."
DUPLICATE_ASSOCIATION_DETAIL = "This tag is already associated with the contact."
ASSOCIATION_NOT_FOUND_DETAIL = "This tag is not associated with the contact."
ASSOCIATION_DELETE_CONFLICT_DETAIL = "The tag association could not be removed."
CEP_NOT_FOUND_DETAIL = "CEP not found."
VIACEP_UNAVAILABLE_DETAIL = "ViaCEP service is unavailable."
VIACEP_TIMEOUT_DETAIL = "ViaCEP request timed out."
ADDRESS_PERSISTENCE_DETAIL = "The address could not be saved."
OPENAI_KEY_MISSING_DETAIL = "OpenAI service is not configured."
OPENAI_RATE_LIMIT_DETAIL = "OpenAI rate limit exceeded."
OPENAI_UNAVAILABLE_DETAIL = "OpenAI service is unavailable."
OPENAI_TIMEOUT_DETAIL = "OpenAI request timed out."
SUMMARY_PERSISTENCE_DETAIL = "The summary could not be saved."


def _format_validation_error(error: ValidationError) -> str:
    messages = []
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"])
        prefix = f"{location}: " if location else ""
        messages.append(f"{prefix}{detail['msg']}")
    return "; ".join(messages)


@router.get("", response_model=ContactListResponse)
def list_contacts(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    tag: str | None = None,
    db: Session = Depends(get_db),
) -> ContactListResponse:
    tag_filter = None
    if tag is not None:
        tag_filter = Contact.tags.any(func.lower(Tag.name) == tag.strip().lower())

    count_query = select(func.count(Contact.id))
    has_ai_summary = (
        exists()
        .where(AISummary.contact_id == Contact.id)
        .label("has_ai_summary")
    )
    query = (
        select(
            Contact.id,
            Contact.full_name,
            Contact.email,
            Contact.phone,
            Contact.source,
            Contact.address,
            Contact.created_at,
            has_ai_summary,
        )
        .order_by(Contact.created_at.desc(), Contact.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if tag_filter is not None:
        count_query = count_query.where(tag_filter)
        query = query.where(tag_filter)

    total = db.scalar(count_query) or 0
    items = [
        ContactListItem.model_validate(row)
        for row in db.execute(query).mappings().all()
    ]

    return ContactListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
) -> Contact:
    existing_contact = db.scalar(select(Contact).where(Contact.email == payload.email))
    if existing_contact is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_EMAIL_DETAIL,
        )

    contact = Contact(
        full_name=payload.full_name,
        email=str(payload.email),
        phone=payload.phone,
        source=payload.source,
    )
    db.add(contact)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_EMAIL_DETAIL,
        ) from error

    db.refresh(contact)
    return contact


@router.post("/import", response_model=ContactImportResponse)
def import_contacts(
    raw_contacts: list[Any],
    db: Session = Depends(get_db),
) -> ContactImportResponse:
    errors: list[ContactImportError] = []
    candidates: list[tuple[int, ContactCreate]] = []
    seen_emails: set[str] = set()

    for index, raw_contact in enumerate(raw_contacts):
        try:
            payload = ContactCreate.model_validate(raw_contact)
        except ValidationError as error:
            errors.append(
                ContactImportError(
                    index=index,
                    reason=_format_validation_error(error),
                )
            )
            continue

        email = str(payload.email)
        if email in seen_emails:
            errors.append(
                ContactImportError(
                    index=index,
                    reason=DUPLICATE_BATCH_EMAIL_DETAIL,
                )
            )
            continue

        seen_emails.add(email)
        candidates.append((index, payload))

    existing_emails = set(
        db.scalars(
            select(func.lower(Contact.email)).where(
                func.lower(Contact.email).in_(seen_emails)
            )
        ).all()
    )
    imported = 0

    for index, payload in candidates:
        email = str(payload.email)
        if email in existing_emails:
            errors.append(
                ContactImportError(index=index, reason=DUPLICATE_EMAIL_DETAIL)
            )
            continue

        contact = Contact(
            full_name=payload.full_name,
            email=email,
            phone=payload.phone,
            source=payload.source,
        )
        try:
            with db.begin_nested():
                db.add(contact)
                db.flush()
        except IntegrityError:
            errors.append(
                ContactImportError(index=index, reason=DUPLICATE_EMAIL_DETAIL)
            )
            continue

        imported += 1

    db.commit()
    errors.sort(key=lambda error: error.index)
    return ContactImportResponse(
        imported=imported,
        rejected=len(errors),
        errors=errors,
    )


@router.get("/{contact_id}", response_model=ContactDetailResponse)
def get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
) -> ContactDetailResponse:
    contact = db.scalar(
        select(Contact)
        .options(selectinload(Contact.tags))
        .where(Contact.id == contact_id)
    )
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=CONTACT_NOT_FOUND_DETAIL,
        )

    latest_summary = db.scalar(
        select(AISummary)
        .where(AISummary.contact_id == contact_id)
        .order_by(AISummary.generated_at.desc(), AISummary.id.desc())
        .limit(1)
    )
    contact_data = ContactResponse.model_validate(contact).model_dump()
    tags = [
        TagResponse.model_validate(tag)
        for tag in sorted(contact.tags, key=lambda item: (item.name.lower(), item.id))
    ]

    return ContactDetailResponse(
        **contact_data,
        tags=tags,
        latest_ai_summary=(
            AISummaryResponse.model_validate(latest_summary)
            if latest_summary is not None
            else None
        ),
    )


@router.post(
    "/{contact_id}/summarize",
    response_model=AISummaryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Contact not found."},
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "OpenAI rate limit exceeded.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "OpenAI returned an error or invalid response.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "OpenAI API key is not configured.",
        },
        status.HTTP_504_GATEWAY_TIMEOUT: {
            "description": "OpenAI request timed out.",
        },
    },
)
def summarize_contact(
    contact_id: int,
    db: Session = Depends(get_db),
) -> AISummary:
    contact = db.scalar(
        select(Contact)
        .options(selectinload(Contact.tags))
        .where(Contact.id == contact_id)
    )
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=CONTACT_NOT_FOUND_DETAIL,
        )

    api_key = settings.openai_api_key
    if api_key is None or not api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=OPENAI_KEY_MISSING_DETAIL,
        )

    tag_names = [
        tag.name
        for tag in sorted(contact.tags, key=lambda tag: (tag.name.lower(), tag.id))
    ]
    try:
        summary_text = generate_contact_summary(
            api_key=api_key.strip(),
            full_name=contact.full_name,
            email=contact.email,
            phone=contact.phone,
            tags=tag_names,
        )
    except OpenAIRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=OPENAI_RATE_LIMIT_DETAIL,
        ) from error
    except OpenAITimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=OPENAI_TIMEOUT_DETAIL,
        ) from error
    except OpenAIServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=OPENAI_UNAVAILABLE_DETAIL,
        ) from error

    summary = AISummary(contact_id=contact.id, summary_text=summary_text)
    db.add(summary)
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SUMMARY_PERSISTENCE_DETAIL,
        ) from error

    db.refresh(summary)
    return summary


@router.post(
    "/{contact_id}/enrich-address",
    response_model=AddressEnrichmentResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Contact or CEP not found.",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "The address could not be saved.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "ViaCEP is unavailable or returned an invalid response.",
        },
        status.HTTP_504_GATEWAY_TIMEOUT: {
            "description": "ViaCEP request timed out.",
        },
    },
)
async def enrich_contact_address(
    contact_id: int,
    payload: AddressEnrichmentRequest,
    db: Session = Depends(get_db),
) -> AddressEnrichmentResponse:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=CONTACT_NOT_FOUND_DETAIL,
        )

    try:
        address = await fetch_address(payload.cep)
    except ViaCEPNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=CEP_NOT_FOUND_DETAIL,
        ) from error
    except ViaCEPTimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=VIACEP_TIMEOUT_DETAIL,
        ) from error
    except ViaCEPServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=VIACEP_UNAVAILABLE_DETAIL,
        ) from error

    contact.address = address.model_dump()
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ADDRESS_PERSISTENCE_DETAIL,
        ) from error
    db.refresh(contact, attribute_names=["address"])
    return AddressEnrichmentResponse.model_validate(contact.address)


@router.post(
    "/{contact_id}/tags",
    response_model=ContactTagResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_tag_to_contact(
    contact_id: int,
    payload: ContactTagCreate,
    db: Session = Depends(get_db),
) -> ContactTagResponse:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=CONTACT_NOT_FOUND_DETAIL,
        )

    tag = db.get(Tag, payload.tag_id)
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=TAG_NOT_FOUND_DETAIL,
        )

    association_key = (contact_id, payload.tag_id)
    if db.get(ContactTag, association_key) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_ASSOCIATION_DETAIL,
        )

    association = ContactTag(contact_id=contact_id, tag_id=payload.tag_id)
    db.add(association)
    tag_name = tag.name

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_ASSOCIATION_DETAIL,
        ) from error

    return ContactTagResponse(
        contact_id=contact_id,
        tag_id=payload.tag_id,
        tag_name=tag_name,
    )


@router.delete(
    "/{contact_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_tag_from_contact(
    contact_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
) -> Response:
    if db.get(Contact, contact_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=CONTACT_NOT_FOUND_DETAIL,
        )

    if db.get(Tag, tag_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=TAG_NOT_FOUND_DETAIL,
        )

    association = db.get(ContactTag, (contact_id, tag_id))
    if association is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ASSOCIATION_NOT_FOUND_DETAIL,
        )

    db.delete(association)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ASSOCIATION_DELETE_CONFLICT_DETAIL,
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
