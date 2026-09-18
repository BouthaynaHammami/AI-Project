from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnalysisCreate(BaseModel):
    dataset_id: int
    question: str = Field(..., min_length=1, max_length=1000)


class AnalysisResponse(BaseModel):
    id: int
    dataset_id: int
    question: str
    answer: str
    result_type: str
    result_data: str | None = None
    chart_config: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)