import logging
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from groq import APIStatusError, RateLimitError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.groq_limit import GroqGlobalLimitExceeded
from app.core.rate_limit import authenticated_user_rate_key, limiter
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
    AnalysisHistoryPage,
    AnalysisResponse,
    AnalysisSuggestionsResponse,
    FeedbackCreate,
    FeedbackResponse,
    AnalysisUpdate,
)
from app.services.ai_service import analyze_dataset
from app.services.export_service import (
    build_pdf_export,
    build_xlsx_export,
    export_filename,
    pdf_export_filename,
)
from app.services.file_service import read_file_as_dataframe
from app.services.pii_service import detect_pii, prepare_dataframes
from app.services.suggestion_service import build_data_context, get_suggestions
from app.services.usage_service import add_usage_event, check_quota

logger = logging.getLogger(__name__)
RESTORE_WINDOW_SECONDS = 30

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
        logger.error("Dataset read failed")

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


def _dataset_preferences(dataset: Dataset) -> dict[str, str]:
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


def _prepare_datasets_for_llm(
    datasets: list[Dataset],
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict[str, Any]]:
    execution_frames: list[pd.DataFrame] = []
    prompt_frames: list[pd.DataFrame] = []
    sensitive_values: list[str] = []
    reports: list[dict[str, Any]] = []

    for dataset in datasets:
        original = _load_dataframe(dataset)
        report = detect_pii(original)
        execution, prompt, _, values = prepare_dataframes(
            original,
            report,
            _dataset_preferences(dataset),
        )
        execution["__source_file"] = dataset.filename
        prompt["__source_file"] = dataset.filename
        execution_frames.append(execution)
        prompt_frames.append(prompt)
        sensitive_values.extend(values)
        reports.append({
            "dataset_id": dataset.id,
            "column_count": report["column_count"],
            "values_touched": report["values_touched"],
        })

    return (
        pd.concat(execution_frames, ignore_index=True, sort=False),
        pd.concat(prompt_frames, ignore_index=True, sort=False),
        sensitive_values,
        {"datasets": reports, "column_count": sum(item["column_count"] for item in reports)},
    )


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
        dataframe = _load_dataframe(dataset)
        _, prompt_dataframe, _, _ = prepare_dataframes(
            dataframe,
            detect_pii(dataframe),
            _dataset_preferences(dataset),
        )
        file_columns.append((dataset.filename, [str(column) for column in prompt_dataframe.columns]))
        prompt_dataframe["__source_file"] = dataset.filename
        frames.append(prompt_dataframe)
    dataframe = pd.concat(frames, ignore_index=True, sort=False)
    context = build_data_context(
        dataframe,
        [dataset.filename for dataset in datasets],
        file_columns=file_columns,
    )
    suggestion_tokens_in = 0
    suggestion_tokens_out = 0
    suggestion_model: str | None = None

    def record_suggestion_tokens(tokens_in: int, tokens_out: int, model: str) -> None:
        nonlocal suggestion_tokens_in, suggestion_tokens_out, suggestion_model
        suggestion_tokens_in += tokens_in
        suggestion_tokens_out += tokens_out
        suggestion_model = model

    try:
        result = get_suggestions(
            context,
            current_user.id,
            refresh=refresh,
            usage_callback=record_suggestion_tokens,
        )
    except ValueError as error:
        if str(error) == "refresh_too_soon":
            raise HTTPException(
                status_code=429,
                detail="Vous pourrez demander d’autres idées dans quelques secondes.",
                headers={"Retry-After": "10"},
            ) from error
        raise
    except GroqGlobalLimitExceeded as error:
        raise HTTPException(
            status_code=429,
            detail=f"Le service IA est temporairement occupé. Réessayez dans {error.retry_after} secondes.",
            headers={"Retry-After": str(error.retry_after)},
        ) from error
    add_usage_event(
        db,
        current_user.id,
        "suggestion",
        tokens_in=suggestion_tokens_in,
        tokens_out=suggestion_tokens_out,
        model=suggestion_model,
    )
    db.commit()
    return result.model_dump()


@router.post("/ask", response_model=AnalysisAskResponse, dependencies=[Depends(check_quota)])
@limiter.limit("5/minute", key_func=authenticated_user_rate_key)
def ask_question(
    request: Request,
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
        combined_df, prompt_df, sensitive_values, pii_counts = _prepare_datasets_for_llm(datasets)
    except HTTPException:
        raise
    except Exception as error:
        logger.error("Dataset combination failed: dataset_count=%s", len(datasets))
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
            prompt_dataframe=prompt_df,
            sensitive_values=sensitive_values,
            pii_column_count=pii_counts["column_count"],
        )

    except RuntimeError as error:
        logger.error("AI service configuration error")
        add_usage_event(db, current_user.id, "analysis", status="error")
        db.commit()

        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    except RateLimitError as error:
        logger.warning("Groq generation limit reached")
        add_usage_event(db, current_user.id, "analysis", status="error")
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="La limite de génération de l’IA est atteinte. Réessayez dans une minute.",
        ) from error

    except APIStatusError as error:
        logger.error("Groq API request failed: status=%s", error.status_code)
        add_usage_event(db, current_user.id, "analysis", status="error")
        db.commit()
        detail = (
            "Le document dépasse la limite de contexte du service IA. "
            "Le contenu envoyé a été réduit; réessayez."
            if error.status_code == 413
            else "Le service IA a refusé la requête. Réessayez dans un instant."
        )
        raise HTTPException(status_code=503, detail=detail) from error

    except GroqGlobalLimitExceeded as error:
        raise HTTPException(
            status_code=429,
            detail=f"Le service IA est temporairement occupé. Réessayez dans {error.retry_after} secondes.",
            headers={"Retry-After": str(error.retry_after)},
        ) from error

    except Exception as error:
        logger.error("Unexpected AI service failure")
        add_usage_event(db, current_user.id, "analysis", status="error")
        db.commit()

        raise HTTPException(
            status_code=500,
            detail="Une erreur est survenue lors de l'analyse. Réessayez.",
        ) from error

    answer = result["answer"]
    chart_config = result["chart_config"]
    generated_code = result.get("code")
    code_explanation = result.get("code_explanation")
    code_retried = bool(result.get("retried", False))
    result_data = {
        "dataset_ids": dataset_ids,
        "result_table": result.get("result_table"),
    }

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
        result_data=json.dumps(result_data, ensure_ascii=False, allow_nan=False),
        chart_config=chart_config,
        generated_code=generated_code,
        code_explanation=code_explanation,
        code_retried=code_retried,
    )

    db.add(record)
    add_usage_event(
        db,
        current_user.id,
        "analysis",
        tokens_in=result.get("tokens_in", 0),
        tokens_out=result.get("tokens_out", 0),
        model=result.get("model"),
    )
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


def _analysis_history_item(analysis: Analysis, db: Session, current_user: User) -> AnalysisResponse:
    feedback = db.query(Feedback).filter(
        Feedback.analysis_id == analysis.id,
        Feedback.user_id == current_user.id,
    ).first()
    conversation = db.get(Conversation, analysis.conversation_id) if analysis.conversation_id else None
    return AnalysisResponse.model_validate(analysis).model_copy(update={
        "conversation_title": conversation.title if conversation and conversation.user_id == current_user.id else None,
        "conversation_dataset_ids": (
            json.loads(conversation.dataset_ids)
            if conversation and conversation.user_id == current_user.id
            else []
        ),
        "feedback": FeedbackResponse.model_validate(feedback) if feedback else None,
    })


@router.get("/history", response_model=AnalysisHistoryPage)
def get_history(
    q: str | None = Query(default=None, max_length=200),
    favorite: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a user's active analysis history with search and pagination."""
    query = db.query(Analysis).filter(
        Analysis.user_id == current_user.id,
        Analysis.deleted_at.is_(None),
    )
    if favorite is True:
        query = query.filter(Analysis.is_favorite.is_(True))
    if q and q.strip():
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = query.filter(
            Analysis.question.ilike(pattern, escape="\\")
            | Analysis.answer.ilike(pattern, escape="\\")
            | Analysis.title.ilike(pattern, escape="\\")
        )
    total = query.count()
    analyses = query.order_by(Analysis.created_at.desc()).offset(offset).limit(limit).all()
    return AnalysisHistoryPage(
        items=[_analysis_history_item(analysis, db, current_user) for analysis in analyses],
        total=total,
        has_more=offset + len(analyses) < total,
    )


@router.patch("/{analysis_id}", response_model=AnalysisResponse)
def update_analysis(
    analysis_id: int,
    payload: AnalysisUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id,
        Analysis.deleted_at.is_(None),
    ).first()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analyse introuvable.")
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes:
        analysis.title = changes["title"] or None
    if "is_favorite" in changes:
        analysis.is_favorite = changes["is_favorite"]
    db.commit()
    db.refresh(analysis)
    return _analysis_history_item(analysis, db, current_user)


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id,
        Analysis.deleted_at.is_(None),
    ).first()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analyse introuvable.")
    deleted_at = datetime.now(timezone.utc)
    affected = [analysis]
    if analysis.conversation_id is not None:
        affected = (
            db.query(Analysis)
            .filter(
                Analysis.conversation_id == analysis.conversation_id,
                Analysis.user_id == current_user.id,
                Analysis.deleted_at.is_(None),
            )
            .all()
        )
    for item in affected:
        item.deleted_at = deleted_at
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{analysis_id}/restore", response_model=AnalysisResponse)
def restore_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id,
        Analysis.deleted_at.is_not(None),
    ).first()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analyse supprimée introuvable.")
    deleted_at = analysis.deleted_at
    if deleted_at.tzinfo is None:
        deleted_at = deleted_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - deleted_at > timedelta(seconds=RESTORE_WINDOW_SECONDS):
        raise HTTPException(status_code=404, detail="Le délai de restauration est dépassé.")
    affected = [analysis]
    if analysis.conversation_id is not None:
        affected = (
            db.query(Analysis)
            .filter(
                Analysis.conversation_id == analysis.conversation_id,
                Analysis.user_id == current_user.id,
                Analysis.deleted_at == analysis.deleted_at,
            )
            .all()
        )
    for item in affected:
        item.deleted_at = None
    db.commit()
    db.refresh(analysis)
    return _analysis_history_item(analysis, db, current_user)


@router.get("/{analysis_id}/export")
def export_analysis(
    analysis_id: int,
    file_format: Literal["pdf", "xlsx"] = Query(alias="format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exporte une analyse existante sans relancer son traitement."""
    analysis = (
        db.query(Analysis)
        .filter(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id,
            Analysis.deleted_at.is_(None),
        )
        .first()
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analyse introuvable.")

    try:
        stored_result = json.loads(analysis.result_data or "{}")
    except (TypeError, json.JSONDecodeError):
        stored_result = {}
    if not isinstance(stored_result, dict):
        stored_result = {}
    dataset_ids = stored_result.get("dataset_ids", [analysis.dataset_id])
    if not isinstance(dataset_ids, list):
        dataset_ids = [analysis.dataset_id]
    dataset_ids = [value for value in dataset_ids if isinstance(value, int) and not isinstance(value, bool)]
    if not dataset_ids:
        dataset_ids = [analysis.dataset_id]
    datasets = (
        db.query(Dataset)
        .filter(Dataset.id.in_(dataset_ids), Dataset.user_id == current_user.id)
        .all()
    )
    filenames_by_id = {dataset.id: dataset.filename for dataset in datasets}
    source_files = [filenames_by_id[dataset_id] for dataset_id in dataset_ids if dataset_id in filenames_by_id]
    try:
        chart_config = json.loads(analysis.chart_config) if analysis.chart_config else None
    except json.JSONDecodeError:
        chart_config = None

    if file_format == "xlsx":
        content = build_xlsx_export(
            question=analysis.question,
            answer=analysis.answer,
            created_at=analysis.created_at,
            source_files=source_files,
            result_table=stored_result.get("result_table"),
            chart_config=chart_config,
        )
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = export_filename(analysis.id, file_format)
    else:
        pdf_analyses = [analysis]
        if analysis.conversation_id is not None:
            pdf_analyses = (
                db.query(Analysis)
                .filter(
                    Analysis.conversation_id == analysis.conversation_id,
                    Analysis.user_id == current_user.id,
                    Analysis.deleted_at.is_(None),
                )
                .order_by(Analysis.created_at.asc(), Analysis.id.asc())
                .all()
            )

        pdf_turns = []
        pdf_dataset_ids = list(dataset_ids)
        for conversation_analysis in pdf_analyses:
            try:
                turn_data = json.loads(conversation_analysis.result_data or "{}")
            except (TypeError, json.JSONDecodeError):
                turn_data = {}
            if not isinstance(turn_data, dict):
                turn_data = {}
            turn_dataset_ids = turn_data.get("dataset_ids", [])
            if isinstance(turn_dataset_ids, list):
                pdf_dataset_ids.extend(
                    dataset_id
                    for dataset_id in turn_dataset_ids
                    if isinstance(dataset_id, int) and not isinstance(dataset_id, bool)
                )
            try:
                turn_chart = (
                    json.loads(conversation_analysis.chart_config)
                    if conversation_analysis.chart_config
                    else None
                )
            except json.JSONDecodeError:
                turn_chart = None
            pdf_turns.append({
                "question": conversation_analysis.question,
                "answer": conversation_analysis.answer,
                "created_at": conversation_analysis.created_at,
                "result_table": turn_data.get("result_table"),
                "chart_config": turn_chart,
            })

        pdf_dataset_ids = list(dict.fromkeys(pdf_dataset_ids))
        pdf_datasets = (
            db.query(Dataset)
            .filter(
                Dataset.id.in_(pdf_dataset_ids),
                Dataset.user_id == current_user.id,
            )
            .all()
        )
        pdf_source_files_by_id = {dataset.id: dataset.filename for dataset in pdf_datasets}
        pdf_source_files = [
            pdf_source_files_by_id[dataset_id]
            for dataset_id in pdf_dataset_ids
            if dataset_id in pdf_source_files_by_id
        ]
        primary_question = pdf_turns[0]["question"] if pdf_turns else analysis.question
        content = build_pdf_export(
            question=primary_question,
            answer=analysis.answer,
            created_at=analysis.created_at,
            source_files=pdf_source_files,
            result_table=stored_result.get("result_table"),
            chart_config=chart_config,
            conversation_turns=pdf_turns,
        )
        media_type = "application/pdf"
        conversation_analysis_ids = [item.id for item in pdf_analyses]
        existing_questions_query = db.query(Analysis.question).filter(
            Analysis.user_id == current_user.id,
            Analysis.id.notin_(conversation_analysis_ids),
        )
        existing_questions = existing_questions_query.all()
        filename = pdf_export_filename(
            primary_question,
            analysis.id,
            unique=any(
                pdf_export_filename(existing[0], analysis.id).casefold()
                == pdf_export_filename(primary_question, analysis.id).casefold()
                for existing in existing_questions
            ),
        )

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
        .filter(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id,
            Analysis.deleted_at.is_(None),
        )
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
        .filter(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id,
            Analysis.deleted_at.is_(None),
        )
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