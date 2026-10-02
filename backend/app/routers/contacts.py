from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contact import Contact
from app.models.contact_tag import ContactTag
from app.models.tag import Tag
from app.schemas.contact import ContactCreate, ContactResponse
from app.schemas.tag import ContactTagCreate, ContactTagResponse


router = APIRouter(prefix="/contacts", tags=["contacts"])

DUPLICATE_EMAIL_DETAIL = "A contact with this email already exists."
CONTACT_NOT_FOUND_DETAIL = "Contact not found."
TAG_NOT_FOUND_DETAIL = "Tag not found."
DUPLICATE_ASSOCIATION_DETAIL = "This tag is already associated with the contact."
ASSOCIATION_NOT_FOUND_DETAIL = "This tag is not associated with the contact."
ASSOCIATION_DELETE_CONFLICT_DETAIL = "The tag association could not be removed."


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
