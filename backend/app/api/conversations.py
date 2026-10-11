import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.analyses import ask_question
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.analysis import Analysis
from app.models.conversation import Conversation
from app.models.dataset import Dataset
from app.models.feedback import Feedback
from app.models.message import Message
from app.models.share_link import ShareLink
from app.models.user import User
from app.schemas.analysis import AnalysisAskResponse, AnalysisCreate
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationMessageCreate,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
from app.services.usage_service import check_quota

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def _dataset_ids(conversation: Conversation) -> list[int]:
    try:
        value = json.loads(conversation.dataset_ids)
    except (TypeError, json.JSONDecodeError):
        return []
    return [item for item in value if isinstance(item, int) and not isinstance(item, bool)]


def _conversation_response(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        dataset_ids=_dataset_ids(conversation),
        is_favorite=conversation.is_favorite,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _message_response(message: Message) -> MessageResponse:
    result_data = None
    if message.result_data:
        try:
            parsed = json.loads(message.result_data)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            result_data = parsed
    return MessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        result_data=result_data,
        created_at=message.created_at,
    )


def _get_owned_conversation(conversation_id: int, user_id: int, db: Session) -> Conversation:
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,
    ).first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    return conversation


def _validate_datasets(dataset_ids: list[int], user_id: int, db: Session) -> None:
    unique_ids = set(dataset_ids)
    if not unique_ids:
        return
    owned_ids = {
        dataset_id
        for (dataset_id,) in db.query(Dataset.id).filter(
            Dataset.id.in_(unique_ids),
            Dataset.user_id == user_id,
        ).all()
    }
    if owned_ids != unique_ids:
        raise HTTPException(status_code=404, detail="Un ou plusieurs fichiers sont introuvables.")


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset_ids = list(dict.fromkeys(payload.dataset_ids))
    _validate_datasets(dataset_ids, current_user.id, db)
    now = datetime.now(timezone.utc)
    conversation = Conversation(
        user_id=current_user.id,
        title="Nouvelle analyse",
        dataset_ids=json.dumps(dataset_ids),
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return _conversation_response(conversation)


@router.get("", response_model=list[ConversationResponse])
def list_conversations(
    q: str | None = Query(default=None, max_length=200),
    favorite: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
    if favorite is True:
        query = query.filter(Conversation.is_favorite.is_(True))
    if q and q.strip():
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(Conversation.title.ilike(f"%{escaped}%", escape="\\"))
    conversations = query.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).all()
    return [_conversation_response(conversation) for conversation in conversations]


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(conversation_id, current_user.id, db)
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at, Message.id)
        .all()
    )
    if not messages:
        analyses = (
            db.query(Analysis)
            .filter(
                Analysis.conversation_id == conversation.id,
                Analysis.user_id == current_user.id,
                Analysis.deleted_at.is_(None),
            )
            .order_by(Analysis.created_at, Analysis.id)
            .all()
        )
        result = []
        for analysis in analyses:
            result.append(MessageResponse(
                id=analysis.id * 2,
                role="user",
                content=analysis.question,
                created_at=analysis.created_at,
            ))
            result.append(MessageResponse(
                id=analysis.id * 2 + 1,
                role="assistant",
                content=analysis.answer,
                result_data={
                    "chart_config": analysis.chart_config,
                    "result_data": analysis.result_data,
                    "generated_code": analysis.generated_code,
                    "code_explanation": analysis.code_explanation,
                    "code_retried": analysis.code_retried,
                },
                created_at=analysis.created_at,
            ))
        return ConversationDetail(**_conversation_response(conversation).model_dump(), messages=result)
    return ConversationDetail(
        **_conversation_response(conversation).model_dump(),
        messages=[_message_response(message) for message in messages],
    )


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not payload.model_fields_set:
        raise HTTPException(status_code=422, detail="Au moins un champ doit être fourni.")
    conversation = _get_owned_conversation(conversation_id, current_user.id, db)
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes:
        conversation.title = changes["title"].strip()
    if "is_favorite" in changes:
        conversation.is_favorite = changes["is_favorite"]
    if "dataset_ids" in changes:
        dataset_ids = list(dict.fromkeys(changes["dataset_ids"]))
        _validate_datasets(dataset_ids, current_user.id, db)
        conversation.dataset_ids = json.dumps(dataset_ids)
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conversation)
    return _conversation_response(conversation)


@router.post(
    "/{conversation_id}/messages",
    response_model=AnalysisAskResponse,
    dependencies=[Depends(check_quota)],
)
def add_conversation_message(
    conversation_id: int,
    payload: ConversationMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_conversation(conversation_id, current_user.id, db)
    return ask_question(
        request=request,
        analysis=AnalysisCreate(
            dataset_ids=payload.dataset_ids,
            question=payload.question,
            conversation_id=conversation_id,
        ),
        db=db,
        current_user=current_user,
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(conversation_id, current_user.id, db)
    analysis_ids = [
        analysis_id
        for (analysis_id,) in db.query(Analysis.id).filter(
            Analysis.conversation_id == conversation.id,
            Analysis.user_id == current_user.id,
        ).all()
    ]
    if analysis_ids:
        db.query(Feedback).filter(Feedback.analysis_id.in_(analysis_ids)).delete(synchronize_session=False)
        db.query(ShareLink).filter(ShareLink.analysis_id.in_(analysis_ids)).delete(synchronize_session=False)
        db.query(Analysis).filter(Analysis.id.in_(analysis_ids)).delete(synchronize_session=False)
    db.query(Message).filter(Message.conversation_id == conversation.id).delete(synchronize_session=False)
    db.delete(conversation)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
