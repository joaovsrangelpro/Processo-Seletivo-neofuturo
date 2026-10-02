from pydantic import BaseModel, ConfigDict, field_validator


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
