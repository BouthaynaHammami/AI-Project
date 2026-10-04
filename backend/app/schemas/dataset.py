from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


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


class DatasetUploadResponse(DatasetPreviewResponse):
    dataset_id: int


class DatasetHistoryResponse(BaseModel):
    id: int
    filename: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)