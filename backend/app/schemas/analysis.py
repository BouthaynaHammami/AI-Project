
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    dataset_id: int
    question: str
    answer: str
    result_type: str
    result_data: str | None = None
    chart_config: str | None = None
    generated_code: str | None = None
    code_explanation: str | None = None
    code_retried: bool = False
    feedback: FeedbackResponse | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisAskResponse(BaseModel):
    id: int
    conversation_id: int
    dataset_id: int
    question: str
    type: str
    content: str
    chart_config: str | None = None
    generated_code: str | None = None
    code_explanation: str | None = None
    code_retried: bool = False
    feedback: FeedbackResponse | None = None
    created_at: datetime


class SuggestedQuestion(BaseModel):
    question: str
    category: Literal["classement", "evolution", "comparaison", "repartition", "qualite", "synthese"]
    chart: bool


class AnalysisSuggestionsResponse(BaseModel):
    suggestions: list[SuggestedQuestion]
    source: Literal["ai", "rules", "cache"]