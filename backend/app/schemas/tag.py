from pydantic import BaseModel, ConfigDict, Field, field_validator


class TagCreate(BaseModel):
    name: str

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        normalized = value.strip()
        if not normalized:
            raise ValueError("Tag name cannot be empty.")
        return normalized


class TagResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class ContactTagCreate(BaseModel):
    tag_id: int = Field(gt=0)


class ContactTagResponse(BaseModel):
    contact_id: int
    tag_id: int
    tag_name: str
