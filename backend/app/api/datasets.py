import logging
import json
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.analysis import Analysis
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.dataset import (
    DatasetHistoryResponse,
    DatasetPreviewResponse,
    DatasetUploadResponse,
    PiiColumnPreferenceResponse,
    PiiColumnPreferenceUpdate,
)
from app.services.file_service import get_document_page_count, read_file_as_dataframe, save_and_read_file
from app.services.pii_service import detect_pii
from app.services.profiling_service import profile_dataframe
from app.services.usage_service import add_usage_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Datasets"])
TABULAR_EXTENSIONS = {".csv", ".xls", ".xlsx"}


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


def _get_preferences(dataset: Dataset) -> dict[str, str]:
    try:
        preferences = json.loads(dataset.pii_preferences or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(preferences, dict):
        return {}
    return {
        str(column): preference
        for column, preference in preferences.items()
        if preference in {"exclude", "mask", "allow"}
    }


@router.get("/history", response_model=list[DatasetHistoryResponse])
def get_dataset_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Dataset)
        .filter(Dataset.user_id == current_user.id)
        .order_by(Dataset.created_at.desc())
        .all()
    )


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(
    dataset_id: int,
    cascade: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.user_id == current_user.id,
    ).first()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    active_analyses = db.query(Analysis).filter(
        Analysis.dataset_id == dataset.id,
        Analysis.deleted_at.is_(None),
    )
    analysis_count = active_analyses.count()
    if analysis_count and not cascade:
        raise HTTPException(
            status_code=409,
            detail={"detail": "Des analyses actives utilisent ce fichier.", "analysis_count": analysis_count},
        )
    if cascade:
        active_analyses.update(
            {"deleted_at": datetime.now(timezone.utc)},
            synchronize_session=False,
        )

    from app.services.file_service import UPLOAD_DIR
    file_path = Path(dataset.file_path).resolve()
    upload_root = Path(UPLOAD_DIR).resolve()
    if not file_path.is_relative_to(upload_root):
        db.rollback()
        logger.warning("Rejected dataset path outside upload directory: dataset_id=%s", dataset.id)
        raise HTTPException(status_code=400, detail="Invalid dataset file location.")
    try:
        if file_path.exists():
            file_path.unlink()
    except OSError as error:
        db.rollback()
        logger.error("Dataset file deletion failed: dataset_id=%s", dataset.id)
        raise HTTPException(status_code=500, detail="Could not delete the dataset file.") from error

    db.delete(dataset)
    db.commit()
    return Response(status_code=204)


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
            add_usage_event(db, current_user.id, "upload")
            profile = profile_dataframe(dataframe) if file_path.suffix.lower() in TABULAR_EXTENSIONS else None
            pii_report = detect_pii(dataframe)

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
                    profile=profile,
                    pii_report=pii_report,
                    pii_preferences={},
                )
            )

        db.commit()
        return uploaded_datasets

    except HTTPException:
        db.rollback()
        raise
    except Exception as error:
        db.rollback()
        logger.error("Dataset upload failed: uploaded_count=%s", len(uploaded_datasets))
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
        logger.error("Dataset preview failed")
        raise HTTPException(status_code=500, detail="Could not read the dataset.") from error

    profile = profile_dataframe(dataframe) if file_path.suffix.lower() in TABULAR_EXTENSIONS else None
    pii_report = detect_pii(dataframe)
    return DatasetPreviewResponse(
        id=int(dataset.id),
        filename=dataset.filename,
        row_count=int(dataset.row_count),
        column_count=int(dataset.column_count),
        file_size_bytes=file_path.stat().st_size,
        page_count=get_document_page_count(file_path),
        column_names=[str(column) for column in dataframe.columns],
        preview=_build_preview(dataframe),
        profile=profile,
        pii_report=pii_report,
        pii_preferences=_get_preferences(dataset),
    )


@router.put("/{dataset_id}/pii-preferences", response_model=PiiColumnPreferenceResponse)
def update_pii_preferences(
    dataset_id: int,
    payload: PiiColumnPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this dataset.")

    file_path = Path(dataset.file_path)
    try:
        dataframe = read_file_as_dataframe(file_path)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=422, detail="Could not inspect the dataset columns.") from error
    report = detect_pii(dataframe)
    detected_columns = {item["name"] for item in report["columns"]}
    unknown_columns = set(payload.preferences) - detected_columns
    if unknown_columns:
        raise HTTPException(
            status_code=422,
            detail="Les préférences ne peuvent concerner que les colonnes détectées comme sensibles.",
        )

    dataset.pii_preferences = json.dumps(payload.preferences, ensure_ascii=False)
    db.commit()
    return PiiColumnPreferenceResponse(
        dataset_id=dataset.id,
        preferences=payload.preferences,
    )