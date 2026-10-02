from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tag import Tag
from app.schemas.tag import TagCreate, TagResponse


router = APIRouter(prefix="/tags", tags=["tags"])

DUPLICATE_TAG_DETAIL = "A tag with this name already exists."


@router.get("", response_model=list[TagResponse])
def list_tags(db: Session = Depends(get_db)) -> list[Tag]:
    return list(db.scalars(select(Tag).order_by(func.lower(Tag.name), Tag.id)).all())


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
) -> Tag:
    existing_tag = db.scalar(
        select(Tag).where(func.lower(Tag.name) == payload.name.lower())
    )
    if existing_tag is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_TAG_DETAIL,
        )

    tag = Tag(name=payload.name)
    db.add(tag)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_TAG_DETAIL,
        ) from error

    db.refresh(tag)
    return tag
