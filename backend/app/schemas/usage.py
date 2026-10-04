from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UsageMe(BaseModel):
    used: int
    quota: int
    unit: Literal["analyses"] = "analyses"
    tokens_in: int
    tokens_out: int
    reset_at: datetime


class AdminUserUpdate(BaseModel):
    monthly_quota: int | None = Field(default=None, ge=0, le=1_000_000)
    is_active: bool | None = None


class AdminUserSummary(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    monthly_quota: int
    analyses_used: int
    tokens_in: int
    tokens_out: int
    last_activity: datetime | None


class DailyAdminStats(BaseModel):
    date: str
    analyses: int
    errors: int
    tokens: int


class AdminStats(BaseModel):
    analyses_today: int
    error_rate: float
    like_rate: float
    tokens_in: int
    tokens_out: int
    daily: list[DailyAdminStats]
