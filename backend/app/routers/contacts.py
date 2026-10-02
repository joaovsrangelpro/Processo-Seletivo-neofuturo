from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contact import Contact
from app.schemas.contact import ContactCreate, ContactResponse


router = APIRouter(prefix="/contacts", tags=["contacts"])

DUPLICATE_EMAIL_DETAIL = "A contact with this email already exists."


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
