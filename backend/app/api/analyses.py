from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.dataset import Dataset
from app.schemas.analysis import AnalysisCreate


router = APIRouter(
    prefix="/api/analyses",
    tags=["Analyses"]
)


@router.post("/question")
def ask_question(
    analysis: AnalysisCreate,
    db: Session = Depends(get_db)
):
    """
    Receive a natural-language question about a dataset.
    """

    dataset = db.get(Dataset, analysis.dataset_id)

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found."
        )

    return {
        "message": "Question received successfully.",
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "question": analysis.question
    }