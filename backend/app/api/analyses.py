from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.dataset import Dataset
from app.models.analysis import Analysis
from app.models.user import User
from app.schemas.analysis import AnalysisAskResponse, AnalysisCreate, AnalysisResponse


router = APIRouter(
    prefix="/analysis",
    tags=["Analyses"]
)


@router.post("/ask", response_model=AnalysisAskResponse)
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

    if not analysis.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    answer = "Analyse mockée : les données montrent une corrélation positive entre l'assiduité et les scores. Les étudiants les plus assidus dépassent la moyenne de 9 points."
    record = Analysis(
        user_id=current_user.id,
        dataset_id=dataset.id,
        question=analysis.question.strip(),
        answer=answer,
        result_type="text",
    )
    # TODO: remplacer cette réponse mockée par l'appel au LLM avec le dataset nettoyé.
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "dataset_id": record.dataset_id, "question": record.question, "type": "text", "content": record.answer, "created_at": record.created_at}


@router.get("/history", response_model=list[AnalysisResponse])
def get_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Analysis).filter(Analysis.user_id == current_user.id).order_by(Analysis.created_at.desc()).all()