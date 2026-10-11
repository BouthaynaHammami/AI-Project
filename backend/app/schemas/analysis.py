
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AnalysisCreate(BaseModel):
    dataset_ids: list[int] = Field(..., min_length=1)
    question: str = Field(..., min_length=1, max_length=1000)
    conversation_id: int | None = Field(default=None, gt=0)


class FeedbackResponse(BaseModel):
    id: int
    analysis_id: int
    user_id: int
    rating: Literal[-1, 1]
    comment: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedbackCreate(BaseModel):
    rating: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=500)


class NegativeFeedbackQuestion(BaseModel):
    question: str
    created_at: datetime


class AnalysisFeedbackStats(BaseModel):
    like_rate: float
    total_votes: int
    recent_negative_questions: list[NegativeFeedbackQuestion]


class AnalysisResponse(BaseModel):
    id: int
    conversation_id: int | None = None
    conversation_title: str | None = None
    conversation_dataset_ids: list[int] = Field(default_factory=list)
    dataset_id: int | None
    question: str
    answer: str
    result_type: str
    result_data: str | None = None
    chart_config: str | None = None
    generated_code: str | None = None
    code_explanation: str | None = None
    code_retried: bool = False
    feedback: FeedbackResponse | None = None
    title: str | None = None
    is_favorite: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisAskResponse(BaseModel):
    id: int
    conversation_id: int
    dataset_id: int
    question: str
    type: str
    content: str
    result_data: str | None = None
    chart_config: str | None = None
    generated_code: str | None = None
    code_explanation: str | None = None
    code_retried: bool = False
    feedback: FeedbackResponse | None = None
    created_at: datetime


class AnalysisHistoryPage(BaseModel):
    items: list[AnalysisResponse]
    total: int
    has_more: bool


class AnalysisUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    is_favorite: bool | None = None

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_update(self):
        if not self.model_fields_set:
            raise ValueError("Au moins un champ doit être fourni.")
        if "is_favorite" in self.model_fields_set and self.is_favorite is None:
            raise ValueError("is_favorite ne peut pas être null.")
        return self


class SuggestedQuestion(BaseModel):
    question: str
    category: Literal["classement", "evolution", "comparaison", "repartition", "qualite", "synthese"]
    chart: bool


class AnalysisSuggestionsResponse(BaseModel):
    suggestions: list[SuggestedQuestion]
    source: Literal["ai", "rules", "cache"]