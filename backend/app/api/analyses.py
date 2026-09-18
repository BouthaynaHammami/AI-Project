from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.analysis import AnalysisCreate


router = APIRouter(
    prefix="/api/analyses",
    tags=["Analyses"]
)


@router.post("/question")
def ask_question(
    analysis: AnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

    if dataset.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this dataset."
        )

    return {
        "message": "Question received successfully.",
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "question": analysis.question
    }