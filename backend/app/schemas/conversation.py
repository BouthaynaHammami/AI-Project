from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ConversationCreate(BaseModel):
    dataset_ids: list[int] = Field(default_factory=list)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    is_favorite: bool | None = None
    dataset_ids: list[int] | None = None

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def reject_null_updates(self):
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title ne peut pas être null.")
        if "is_favorite" in self.model_fields_set and self.is_favorite is None:
            raise ValueError("is_favorite ne peut pas être null.")
        if "dataset_ids" in self.model_fields_set and self.dataset_ids is None:
            raise ValueError("dataset_ids ne peut pas être null.")
        return self


class ConversationMessageCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    dataset_ids: list[int] = Field(..., min_length=1)


class MessageResponse(BaseModel):
    id: int
    analysis_id: int | None = None
    role: Literal["user", "assistant"]
    content: str
    result_data: dict[str, object] | None = None
    created_at: datetime


class ConversationResponse(BaseModel):
    id: int
    title: str
    dataset_ids: list[int]
    is_favorite: bool
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationResponse):
    messages: list[MessageResponse]
