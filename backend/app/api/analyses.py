import logging
import json
from pathlib import Path

import pandas as pd
from groq import APIStatusError, RateLimitError
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.analysis import Analysis
from app.models.conversation import Conversation
from app.models.dataset import Dataset
from app.models.feedback import Feedback
from app.models.user import User
from app.schemas.analysis import (
    AnalysisAskResponse,
    AnalysisCreate,
    AnalysisFeedbackStats,
    AnalysisResponse,
    AnalysisSuggestionsResponse,
    FeedbackCreate,
    FeedbackResponse,
)
from app.services.ai_service import analyze_dataset
from app.services.file_service import read_file_as_dataframe
from app.services.suggestion_service import build_data_context, get_suggestions

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


@router.get("/suggestions", response_model=AnalysisSuggestionsResponse)
def suggest_questions(
    dataset_ids: str,
    refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suggest questions based on a privacy-filtered data profile."""
    try:
        parsed_ids = [int(value.strip()) for value in dataset_ids.split(",") if value.strip()]
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="dataset_ids doit être une liste d'identifiants séparés par des virgules.",
        ) from error

    unique_ids = list(dict.fromkeys(parsed_ids))
    if not unique_ids or len(unique_ids) > 20:
        raise HTTPException(
            status_code=422,
            detail="Sélectionnez entre 1 et 20 jeux de données.",
        )

    datasets: list[Dataset] = []
    for dataset_id in unique_ids:
        dataset = db.get(Dataset, dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found.")
        if dataset.user_id != current_user.id:
            raise HTTPException(status_code=403, detail=f"You do not have access to dataset {dataset_id}.")
        datasets.append(dataset)

    frames = []
    file_columns = []
    for dataset in datasets:
        dataframe = _load_dataframe(dataset).copy()
        file_columns.append((dataset.filename, [str(column) for column in dataframe.columns]))
        dataframe["__source_file"] = dataset.filename
        frames.append(dataframe)
    dataframe = pd.concat(frames, ignore_index=True, sort=False)
    context = build_data_context(
        dataframe,
        [dataset.filename for dataset in datasets],
        file_columns=file_columns,
    )
    try:
        result = get_suggestions(context, current_user.id, refresh=refresh)
    except ValueError as error:
        if str(error) == "refresh_too_soon":
            raise HTTPException(
                status_code=429,
                detail="Vous pourrez demander d’autres idées dans quelques secondes.",
                headers={"Retry-After": "10"},
            ) from error
        raise
    return result.model_dump()


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
    conversation = None
    conversation_history: list[dict[str, str]] = []
    if analysis.conversation_id is not None:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.id == analysis.conversation_id,
                Conversation.user_id == current_user.id,
            )
            .first()
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation introuvable.")
        previous_analyses = (
            db.query(Analysis)
            .filter(
                Analysis.conversation_id == conversation.id,
                Analysis.user_id == current_user.id,
            )
            .order_by(Analysis.created_at.desc(), Analysis.id.desc())
            .limit(3)
            .all()
        )
        conversation_history = [
            {
                "question": item.question,
                "answer": item.answer,
                "code": item.generated_code or "",
            }
            for item in reversed(previous_analyses)
        ]

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
            conversation_history=conversation_history,
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
    generated_code = result.get("code")
    code_explanation = result.get("code_explanation")
    code_retried = bool(result.get("retried", False))

    # ── Sauvegarde en DB ─────────────────────────────────────────────────
    #
    # Pour l'instant, la table analyses possède encore un seul
    # dataset_id. On conserve donc le premier dataset comme dataset
    # principal de l'analyse.
    #
    # Les fichiers sélectionnés sont néanmoins tous envoyés à l'IA.
    primary_dataset = datasets[0]
    if conversation is None:
        conversation = Conversation(
            user_id=current_user.id,
            title=question[:80] or "Nouvelle conversation",
            dataset_ids=json.dumps(dataset_ids),
        )
        db.add(conversation)
        db.flush()
    else:
        conversation.dataset_ids = json.dumps(dataset_ids)

    record = Analysis(
        user_id=current_user.id,
        conversation_id=conversation.id,
        dataset_id=primary_dataset.id,
        question=question,
        answer=answer,
        result_type="text",
        result_data=json.dumps({"dataset_ids": dataset_ids}),
        chart_config=chart_config,
        generated_code=generated_code,
        code_explanation=code_explanation,
        code_retried=code_retried,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "conversation_id": record.conversation_id,
        "dataset_id": record.dataset_id,
        "question": record.question,
        "type": "text",
        "content": record.answer,
        "chart_config": record.chart_config,
        "generated_code": record.generated_code,
        "code_explanation": record.code_explanation,
        "code_retried": record.code_retried,
        "created_at": record.created_at,
    }


@router.get("/history", response_model=list[AnalysisResponse])
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne l'historique des analyses de l'utilisateur."""
    analyses = (
        db.query(Analysis)
        .filter(Analysis.user_id == current_user.id)
        .order_by(Analysis.created_at.desc())
        .all()
    )
    analysis_ids = [analysis.id for analysis in analyses]
    feedback_by_analysis = {}
    if analysis_ids:
        feedback_by_analysis = {
            feedback.analysis_id: feedback
            for feedback in db.query(Feedback)
            .filter(
                Feedback.user_id == current_user.id,
                Feedback.analysis_id.in_(analysis_ids),
            )
            .all()
        }
    conversation_ids = list({
        analysis.conversation_id
        for analysis in analyses
        if analysis.conversation_id is not None
    })
    conversations_by_id = {}
    if conversation_ids:
        conversations_by_id = {
            conversation.id: conversation
            for conversation in db.query(Conversation)
            .filter(
                Conversation.user_id == current_user.id,
                Conversation.id.in_(conversation_ids),
            )
            .all()
        }
    return [
        AnalysisResponse.model_validate(analysis).model_copy(
            update={
                "conversation_title": (
                    conversations_by_id[analysis.conversation_id].title
                    if analysis.conversation_id in conversations_by_id
                    else None
                ),
                "conversation_dataset_ids": (
                    json.loads(conversations_by_id[analysis.conversation_id].dataset_ids)
                    if analysis.conversation_id in conversations_by_id
                    else []
                ),
                "feedback": (
                    FeedbackResponse.model_validate(feedback_by_analysis[analysis.id])
                    if analysis.id in feedback_by_analysis
                    else None
                )
            }
        )
        for analysis in analyses
    ]


@router.put("/{analysis_id}/feedback", response_model=FeedbackResponse)
def save_feedback(
    analysis_id: int,
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crée ou remplace le vote de l'utilisateur pour une analyse qui lui appartient."""
    analysis = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == current_user.id)
        .first()
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analyse introuvable.")

    feedback = (
        db.query(Feedback)
        .filter(
            Feedback.analysis_id == analysis_id,
            Feedback.user_id == current_user.id,
        )
        .first()
    )
    if feedback is None:
        feedback = Feedback(
            analysis_id=analysis_id,
            user_id=current_user.id,
            rating=payload.rating,
            comment=payload.comment,
        )
        db.add(feedback)
    else:
        feedback.rating = payload.rating
        feedback.comment = payload.comment

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        feedback = (
            db.query(Feedback)
            .filter(
                Feedback.analysis_id == analysis_id,
                Feedback.user_id == current_user.id,
            )
            .first()
        )
        if feedback is None:
            raise error
        feedback.rating = payload.rating
        feedback.comment = payload.comment
        db.commit()
    db.refresh(feedback)
    return feedback


@router.delete("/{analysis_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def delete_feedback(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Annule le vote de l'utilisateur pour une analyse qui lui appartient."""
    analysis = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == current_user.id)
        .first()
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analyse introuvable.")

    feedback = (
        db.query(Feedback)
        .filter(
            Feedback.analysis_id == analysis_id,
            Feedback.user_id == current_user.id,
        )
        .first()
    )
    if feedback is not None:
        db.delete(feedback)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/stats", response_model=AnalysisFeedbackStats)
def get_feedback_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne le taux de satisfaction et les derniers retours négatifs de l'utilisateur."""
    owned_feedback = (
        db.query(Feedback)
        .join(Analysis, Feedback.analysis_id == Analysis.id)
        .filter(
            Feedback.user_id == current_user.id,
            Analysis.user_id == current_user.id,
        )
    )
    total_votes = owned_feedback.with_entities(func.count(Feedback.id)).scalar() or 0
    positive_votes = (
        owned_feedback.with_entities(func.count(Feedback.id))
        .filter(Feedback.rating == 1)
        .scalar()
        or 0
    )
    negative_feedback = (
        db.query(Feedback, Analysis.question)
        .join(Analysis, Feedback.analysis_id == Analysis.id)
        .filter(
            Feedback.user_id == current_user.id,
            Feedback.rating == -1,
            Analysis.user_id == current_user.id,
        )
        .order_by(Feedback.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "like_rate": round(positive_votes * 100 / total_votes, 1) if total_votes else 0.0,
        "total_votes": total_votes,
        "recent_negative_questions": [
            {"question": question, "created_at": feedback.created_at}
            for feedback, question in negative_feedback
        ],
    }