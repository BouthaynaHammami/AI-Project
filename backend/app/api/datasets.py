import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.dataset import (
    DatasetHistoryResponse,
    DatasetPreviewResponse,
    DatasetUploadResponse,
)
from app.services.file_service import get_document_page_count, read_file_as_dataframe, save_and_read_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Datasets"])


def _json_safe(value: Any) -> Any:
    """Convert pandas and numpy values into JSON-compatible values."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "isoformat") and not isinstance(value, (str, int, float, bool)):
        try:
            return value.isoformat()
        except (ValueError, TypeError):
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _build_preview(dataframe: pd.DataFrame) -> list[dict]:
    preview_df = dataframe.head(5)
    records = preview_df.to_dict(orient="records")
    return [_json_safe(record) for record in records]


@router.get("/history", response_model=list[DatasetHistoryResponse])
def get_dataset_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Dataset)
        .filter(Dataset.user_id == current_user.id)
        .order_by(Dataset.created_at.desc())
        .all()
    )


@router.post("/upload", response_model=list[DatasetUploadResponse])
async def upload_datasets(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload supported tabular, document, and image files as datasets."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    uploaded_datasets = []

    try:
        for file in files:
            if not file.filename:
                raise HTTPException(status_code=400, detail="No filename provided.")

            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail=f"The file {file.filename} is empty.")

            try:
                file_path, dataframe = save_and_read_file(file.filename, content)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=f"{file.filename}: {error}") from error

            dataset = Dataset(
                user_id=current_user.id,
                filename=file.filename,
                file_path=str(file_path),
                file_type=file_path.suffix.lower().replace(".", ""),
                row_count=int(len(dataframe)),
                column_count=int(len(dataframe.columns)),
            )
            db.add(dataset)
            db.flush()

            uploaded_datasets.append(
                DatasetUploadResponse(
                    dataset_id=int(dataset.id),
                    id=int(dataset.id),
                    filename=dataset.filename,
                    row_count=int(len(dataframe)),
                    column_count=int(len(dataframe.columns)),
                    file_size_bytes=len(content),
                    page_count=get_document_page_count(file_path),
                    column_names=[str(column) for column in dataframe.columns],
                    preview=_build_preview(dataframe),
                )
            )

        db.commit()
        return uploaded_datasets

    except HTTPException:
        db.rollback()
        raise
    except Exception as error:
        db.rollback()
        logger.exception("Error uploading datasets")
        raise HTTPException(status_code=500, detail="Could not upload the selected files.") from error
    finally:
        for file in files:
            await file.close()


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def get_dataset_preview(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this dataset.")

    file_path = Path(dataset.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Dataset file not found.")

    try:
        dataframe = read_file_as_dataframe(file_path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("Could not read dataset preview")
        raise HTTPException(status_code=500, detail="Could not read the dataset.") from error

    return DatasetPreviewResponse(
        id=int(dataset.id),
        filename=dataset.filename,
        row_count=int(dataset.row_count),
        column_count=int(dataset.column_count),
        file_size_bytes=file_path.stat().st_size,
        page_count=get_document_page_count(file_path),
        column_names=[str(column) for column in dataframe.columns],
        preview=_build_preview(dataframe),
    )