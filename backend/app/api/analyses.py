import logging
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.analysis import Analysis
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.analysis import AnalysisAskResponse, AnalysisCreate, AnalysisResponse
from app.services.ai_service import analyze_dataset

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analysis",
    tags=["Analyses"]
)


def _load_dataframe(dataset: Dataset) -> pd.DataFrame:
    """Charge le DataFrame depuis le fichier du dataset."""
    file_path = Path(dataset.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Dataset file not found on disk.")
    try:
        if dataset.file_type == "csv":
            return pd.read_csv(file_path)
        return pd.read_excel(file_path)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Could not read the dataset file."
        ) from error


@router.post("/ask", response_model=AnalysisAskResponse)
def ask_question(
    analysis: AnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reçoit une question en langage naturel sur un dataset, appelle le LLM
    (Groq — Llama 3.3 70B) pour analyser les données et retourne une réponse
    textuelle + une configuration de graphique.
    """
    # ── Validation du dataset ──────────────────────────────────────────────
    dataset = db.get(Dataset, analysis.dataset_id)

    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    if dataset.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this dataset."
        )

    if not analysis.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    # ── Chargement du DataFrame ────────────────────────────────────────────
    df = _load_dataframe(dataset)

    # ── Appel au service IA ────────────────────────────────────────────────
    try:
        result = analyze_dataset(analysis.question.strip(), df)
    except RuntimeError as error:
        # GROQ_API_KEY manquante ou erreur de configuration
        logger.error("ai_service error: %s", error)
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.exception("Unexpected error from ai_service")
        raise HTTPException(
            status_code=500,
            detail="Une erreur est survenue lors de l'analyse. Réessayez."
        ) from error

    answer = result["answer"]
    chart_config = result["chart_config"]

    # ── Sauvegarde en DB (structure inchangée) ─────────────────────────────
    record = Analysis(
        user_id=current_user.id,
        dataset_id=dataset.id,
        question=analysis.question.strip(),
        answer=answer,
        result_type="text",
        chart_config=chart_config,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "dataset_id": record.dataset_id,
        "question": record.question,
        "type": "text",
        "content": record.answer,
        "chart_config": record.chart_config,
        "created_at": record.created_at,
    }


@router.get("/history", response_model=list[AnalysisResponse])
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Analysis)
        .filter(Analysis.user_id == current_user.id)
        .order_by(Analysis.created_at.desc())
        .all()
    )
