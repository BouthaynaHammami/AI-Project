from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PiiColumnPreferenceUpdate(BaseModel):
    preferences: dict[str, Literal["exclude", "mask", "allow"]] = Field(default_factory=dict)


class PiiColumnPreferenceResponse(BaseModel):
    dataset_id: int
    preferences: dict[str, Literal["exclude", "mask", "allow"]]


class DatasetResponse(BaseModel):
    id: int
    filename: str
    file_path: str
    file_type: str
    row_count: int
    column_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetPreviewResponse(BaseModel):
    id: int
    filename: str
    row_count: int
    column_count: int
    file_size_bytes: int
    page_count: int | None = None
    column_names: list[str]
    preview: list[dict]
    profile: dict[str, Any] | None = None
    pii_report: dict[str, Any] = Field(default_factory=lambda: {"columns": [], "column_count": 0, "values_touched": 0})
    pii_preferences: dict[str, Literal["exclude", "mask", "allow"]] = Field(default_factory=dict)


class DatasetUploadResponse(DatasetPreviewResponse):
    dataset_id: int


class DatasetHistoryResponse(BaseModel):
    id: int
    filename: str
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)