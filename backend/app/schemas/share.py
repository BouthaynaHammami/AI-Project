from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ShareLinkCreate(BaseModel):
    expires_in_days: Literal[1, 7, 30] = 7


class ShareLinkCreated(BaseModel):
    id: int
    token: str
    expires_at: datetime


class ShareLinkSummary(BaseModel):
    id: int
    created_at: datetime
    expires_at: datetime
    view_count: int

    model_config = ConfigDict(from_attributes=True)


class PublicAnalysis(BaseModel):
    question: str
    answer: str
    chart_config: str | None
    created_at: datetime
