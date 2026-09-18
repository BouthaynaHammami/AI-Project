from datetime import datetime

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
    column_names: list[str]
    preview: list[dict]