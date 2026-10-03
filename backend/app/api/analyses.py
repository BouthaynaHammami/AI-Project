import logging
import json
from pathlib import Path

import pandas as pd
from groq import APIStatusError, RateLimitError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.analysis import Analysis
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.analysis import (
    AnalysisAskResponse,
    AnalysisCreate,
    AnalysisResponse,
)
from app.services.ai_service import analyze_dataset
from app.services.file_service import read_file_as_dataframe

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analysis",
    tags=["Analyses"],
)


def _load_dataframe(dataset: Dataset) -> pd.DataFrame:
    """Charge le DataFrame depuis le fichier du dataset."""
    file_path = Path(dataset.file_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Dataset file not found on disk: {dataset.filename}",
        )

    try:
        return read_file_as_dataframe(file_path)
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=f"Could not read dataset file {dataset.filename}: {error}",
        ) from error
    except Exception as error:
        logger.exception("Could not read dataset: %s", dataset.filename)

        raise HTTPException(
            status_code=500,
            detail=f"Could not read dataset file: {dataset.filename}",
        ) from error


def _combine_datasets(
    datasets: list[Dataset],
) -> pd.DataFrame:
    """
    Charge plusieurs datasets et les combine dans un seul DataFrame.

    Une colonne __source_file est ajoutée afin que l'IA puisse
    identifier de quel fichier provient chaque ligne.
    """
    dataframes = []

    for dataset in datasets:
        df = _load_dataframe(dataset).copy()

        # Ajoute le nom du fichier à chaque ligne
        df["__source_file"] = dataset.filename

        dataframes.append(df)

    if not dataframes:
        raise HTTPException(
            status_code=422,
            detail="At least one dataset is required.",
        )

    # Les fichiers peuvent avoir des colonnes différentes.
    # pandas crée automatiquement les colonnes manquantes avec NaN.
    combined_df = pd.concat(
        dataframes,
        ignore_index=True,
        sort=False,
    )

    return combined_df


@router.post("/ask", response_model=AnalysisAskResponse)
def ask_question(
    analysis: AnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reçoit une question en langage naturel sur un ou plusieurs datasets.

    Les datasets sélectionnés sont chargés puis combinés dans un seul
    DataFrame avant d'être envoyés au service IA.
    """

    # ── Validation de la question ────────────────────────────────────────
    question = analysis.question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Question cannot be empty.",
        )

    # ── Validation des datasets ──────────────────────────────────────────
    if not analysis.dataset_ids:
        raise HTTPException(
            status_code=422,
            detail="At least one dataset must be selected.",
        )

    # Supprime les IDs en double tout en gardant leur ordre
    dataset_ids = list(dict.fromkeys(analysis.dataset_ids))

    # ── Chargement des datasets ──────────────────────────────────────────
    datasets = []

    for dataset_id in dataset_ids:
        dataset = db.get(Dataset, dataset_id)

        if dataset is None:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {dataset_id} not found.",
            )

        if dataset.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"You do not have access to dataset "
                    f"{dataset_id}."
                ),
            )

        datasets.append(dataset)

    # ── Chargement et combinaison des fichiers ───────────────────────────
    try:
        combined_df = _combine_datasets(datasets)
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Error while combining datasets")
        raise HTTPException(
            status_code=500,
            detail="Could not combine the selected datasets.",
        ) from error

    # ── Appel au service IA ──────────────────────────────────────────────
    try:
        result = analyze_dataset(
            question,
            combined_df,
            generate_chart=any(dataset.file_type.lower() in {"csv", "xls", "xlsx"} for dataset in datasets),
        )

    except RuntimeError as error:
        logger.error("ai_service error: %s", error)

        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    except RateLimitError as error:
        logger.warning("Groq generation limit reached: %s", error)
        raise HTTPException(
            status_code=503,
            detail="La limite de génération de l’IA est atteinte. Réessayez dans une minute.",
        ) from error

    except APIStatusError as error:
        logger.exception("Groq API request failed with status %s", error.status_code)
        detail = (
            "Le document dépasse la limite de contexte du service IA. "
            "Le contenu envoyé a été réduit; réessayez."
            if error.status_code == 413
            else "Le service IA a refusé la requête. Réessayez dans un instant."
        )
        raise HTTPException(status_code=503, detail=detail) from error

    except Exception as error:
        logger.exception("Unexpected error from ai_service")

        raise HTTPException(
            status_code=500,
            detail="Une erreur est survenue lors de l'analyse. Réessayez.",
        ) from error

    answer = result["answer"]
    chart_config = result["chart_config"]

    # ── Sauvegarde en DB ─────────────────────────────────────────────────
    #
    # Pour l'instant, la table analyses possède encore un seul
    # dataset_id. On conserve donc le premier dataset comme dataset
    # principal de l'analyse.
    #
    # Les fichiers sélectionnés sont néanmoins tous envoyés à l'IA.
    primary_dataset = datasets[0]

    record = Analysis(
        user_id=current_user.id,
        dataset_id=primary_dataset.id,
        question=question,
        answer=answer,
        result_type="text",
        result_data=json.dumps({"dataset_ids": dataset_ids}),
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
    """Retourne l'historique des analyses de l'utilisateur."""
    return (
        db.query(Analysis)
        .filter(Analysis.user_id == current_user.id)
        .order_by(Analysis.created_at.desc())
        .all()
    )