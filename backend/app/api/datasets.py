from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from pathlib import Path

import pandas as pd

from app.core.database import get_db
from app.models.dataset import Dataset
from app.schemas.dataset import (
    DatasetPreviewResponse,
    DatasetResponse,
)
from app.services.file_service import save_and_read_file


router = APIRouter(
    prefix="/api/datasets",
    tags=["Datasets"]
)


@router.post("/upload", response_model=DatasetResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload and register a CSV or XLSX dataset.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided."
        )

    try:
        content = await file.read()

        file_path, dataframe = save_and_read_file(
            file.filename,
            content
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    dataset = Dataset(
        filename=file.filename,
        file_path=str(file_path),
        file_type=file_path.suffix.lower().replace(".", ""),
        row_count=len(dataframe),
        column_count=len(dataframe.columns)
    )

    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return dataset

@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def get_dataset_preview(
    dataset_id: int,
    db: Session = Depends(get_db)
):
    """
    Return basic information and a preview of an uploaded dataset.
    """

    dataset = db.get(Dataset, dataset_id)

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found."
        )

    file_path = Path(dataset.file_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Dataset file not found."
        )

    try:
        if dataset.file_type == "csv":
            dataframe = pd.read_csv(file_path)
        elif dataset.file_type == "xlsx":
            dataframe = pd.read_excel(file_path)
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format."
            )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Could not read the dataset."
        ) from error

    preview = dataframe.head(5).to_dict(orient="records")

    return DatasetPreviewResponse(
        id=dataset.id,
        filename=dataset.filename,
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        column_names=dataframe.columns.tolist(),
        preview=preview
    )