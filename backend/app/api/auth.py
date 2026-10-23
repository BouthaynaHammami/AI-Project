import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.rate_limit import limiter
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    get_current_user,
    get_password_hash,
    revoke_token,
    revoke_user_tokens,
    verify_password,
)
from app.models.analysis import Analysis
from app.models.conversation import Conversation
from app.models.dataset import Dataset
from app.models.email_code import EmailCode
from app.models.feedback import Feedback
from app.models.message import Message
from app.models.share_link import ShareLink
from app.models.usage_event import UsageEvent
from app.models.user import User
from app.schemas.auth import (
    AccountDeleteRequest,
    AccountDeleteResponse,
    EmailCodeRequest,
    PasswordResetRequest,
    SignupAccepted,
    Token,
    UserCreate,
    UserLogin,
    UserPublic,
    UserUpdate,
    VerifyEmailRequest,
)
from app.services.email_code_service import consume_email_code, hash_email_code, issue_email_code
from app.services.email_service import (
    EmailDeliveryMode,
    get_email_delivery_mode,
    send_email_code,
)
from app.services.file_service import UPLOAD_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
SIGNUP_ACCEPTED_MESSAGE = "Si cette adresse peut être traitée, la demande d'envoi d'un code a été prise en compte."


def login_rate_key(request: Request) -> str:
    client_ip = request.client.host if request.client else "unknown"
    email = request.headers.get("x-auth-email", "").strip().lower()
    return f"{client_ip}:{email}" if email else client_ip


def _deliver_email_code_background(
    user_id: int,
    recipient: str,
    code: str,
    purpose: str,
) -> None:
    try:
        send_email_code(recipient, code, purpose)
    except RuntimeError as exc:
        with SessionLocal() as db:
            db.query(EmailCode).filter(
                EmailCode.user_id == user_id,
                EmailCode.purpose == purpose,
                EmailCode.code_hash == hash_email_code(user_id, purpose, code),
            ).delete(synchronize_session=False)
            db.commit()
        logger.error("Email delivery failed (%s).", type(exc).__name__)


def _schedule_email_code(
    background_tasks: BackgroundTasks,
    user: User,
    recipient: str,
    code: str,
    purpose: str,
) -> EmailDeliveryMode:
    background_tasks.add_task(
        _deliver_email_code_background,
        user.id,
        recipient,
        code,
        purpose,
    )
    return get_email_delivery_mode()


@router.post("/signup", response_model=SignupAccepted, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/hour")
def register(
    request: Request,
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    normalized_email = str(user_data.email).lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    if user and user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse email possède déjà un compte vérifié.",
        )
    if user is None and db.query(User).filter(User.pending_email == normalized_email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse email possède déjà un compte.",
        )

    if user is None:
        user = User(
            name=user_data.name.strip(),
            email=normalized_email,
            password_hash=get_password_hash(user_data.password),
            is_verified=False,
        )
        db.add(user)
    else:
        user.name = user_data.name.strip()
        user.password_hash = get_password_hash(user_data.password)

    db.flush()
    code = issue_email_code(db, user, "verify")
    delivery_mode = _schedule_email_code(background_tasks, user, user.email, code, "verify")
    return {
        "message": "Un code de vérification va être envoyé à votre adresse email.",
        "delivery_mode": delivery_mode,
    }


@router.post("/verify-email", response_model=Token)
@limiter.limit("10/minute")
def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    normalized_email = str(payload.email).lower()
    user = db.query(User).filter(
        or_(User.email == normalized_email, User.pending_email == normalized_email)
    ).first()
    if user is None:
        raise HTTPException(status_code=400, detail="Code invalide ou expiré.")

    consume_email_code(db, user, "verify", payload.code)
    if user.pending_email and user.pending_email.lower() == normalized_email:
        user.email = user.pending_email
        user.pending_email = None
    user.is_verified = True
    db.commit()
    return {
        "access_token": create_access_token(str(user.id), user.token_version),
        "token_type": "bearer",
    }


@router.post("/resend-code", response_model=SignupAccepted, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/10 minutes")
def resend_code(
    request: Request,
    payload: EmailCodeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    normalized_email = str(payload.email).lower()
    delivery_mode = get_email_delivery_mode()
    user = db.query(User).filter(
        or_(User.email == normalized_email, User.pending_email == normalized_email)
    ).first()
    if user is not None and (not user.is_verified or user.pending_email == normalized_email):
        send_address = user.pending_email if user.pending_email == normalized_email else user.email
        try:
            code = issue_email_code(db, user, "verify")
        except HTTPException as exc:
            if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                raise
        else:
            delivery_mode = _schedule_email_code(background_tasks, user, send_address, code, "verify")
    return {"message": SIGNUP_ACCEPTED_MESSAGE, "delivery_mode": delivery_mode}


@router.post("/login", response_model=Token)
@limiter.limit("5/minute", key_func=login_rate_key)
def login(request: Request, login_data: UserLogin, db: Session = Depends(get_db)):
    normalized_email = str(login_data.email).lower()
    rate_limit_email = request.headers.get("x-auth-email", "").strip().lower()
    if rate_limit_email and rate_limit_email != normalized_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adresse email ou mot de passe incorrect.",
        )
    user = db.query(User).filter(User.email == normalized_email).first()

    if user is None:
        verify_password(login_data.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Adresse email ou mot de passe incorrect.",
        )
    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Adresse email ou mot de passe incorrect.",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ACCOUNT_DISABLED")
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EMAIL_NOT_VERIFIED",
        )

    return {
        "access_token": create_access_token(str(user.id), user.token_version),
        "token_type": "bearer",
    }


@router.post("/forgot-password", response_model=SignupAccepted, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/10 minutes")
def forgot_password(
    request: Request,
    payload: EmailCodeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    delivery_mode = get_email_delivery_mode()
    user = db.query(User).filter(User.email == str(payload.email).lower()).first()
    if user is not None and user.is_verified:
        try:
            code = issue_email_code(db, user, "reset")
        except HTTPException as exc:
            if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                raise
        else:
            delivery_mode = _schedule_email_code(background_tasks, user, user.email, code, "reset")
    return {"message": SIGNUP_ACCEPTED_MESSAGE, "delivery_mode": delivery_mode}


@router.post("/reset-password", response_model=SignupAccepted)
@limiter.limit("10/minute")
def reset_password(payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == str(payload.email).lower()).first()
    if user is None or not user.is_verified:
        raise HTTPException(status_code=400, detail="Code invalide ou expiré.")
    consume_email_code(db, user, "reset", payload.code)
    user.password_hash = get_password_hash(payload.new_password)
    revoke_user_tokens(user)
    db.commit()
    return {"message": "Votre mot de passe a été réinitialisé."}


@router.get("/me", response_model=UserPublic)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.delete("/me", response_model=AccountDeleteResponse)
def delete_me(
    payload: AccountDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Le mot de passe actuel est incorrect.")

    user_id = current_user.id
    analyses = db.query(Analysis.id).filter(Analysis.user_id == user_id).all()
    analysis_ids = [analysis_id for (analysis_id,) in analyses]
    datasets = db.query(Dataset).filter(Dataset.user_id == user_id).all()
    upload_root = Path(UPLOAD_DIR).resolve()
    upload_paths: set[Path] = set()
    files_cleanup_pending = 0
    for dataset in datasets:
        file_path = Path(dataset.file_path).resolve()
        if file_path != upload_root and file_path.is_relative_to(upload_root):
            upload_paths.add(file_path)
        else:
            files_cleanup_pending += 1

    try:
        db.query(EmailCode).filter(EmailCode.user_id == user_id).delete(synchronize_session=False)
        db.query(UsageEvent).filter(UsageEvent.user_id == user_id).delete(synchronize_session=False)
        conversation_ids = [
            conversation_id
            for (conversation_id,) in db.query(Conversation.id).filter(Conversation.user_id == user_id).all()
        ]
        if conversation_ids:
            db.query(Message).filter(Message.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
        db.query(Conversation).filter(Conversation.user_id == user_id).delete(synchronize_session=False)
        feedback_query = db.query(Feedback).filter(Feedback.user_id == user_id)
        share_link_query = db.query(ShareLink).filter(ShareLink.created_by == user_id)
        if analysis_ids:
            feedback_query = db.query(Feedback).filter(
                or_(Feedback.user_id == user_id, Feedback.analysis_id.in_(analysis_ids))
            )
            share_link_query = db.query(ShareLink).filter(
                or_(ShareLink.created_by == user_id, ShareLink.analysis_id.in_(analysis_ids))
            )
        feedback_query.delete(synchronize_session=False)
        share_link_query.delete(synchronize_session=False)
        db.query(Analysis).filter(Analysis.user_id == user_id).delete(synchronize_session=False)
        db.query(Dataset).filter(Dataset.user_id == user_id).delete(synchronize_session=False)
        db.delete(current_user)
        db.commit()
    except Exception:
        db.rollback()
        raise

    for file_path in upload_paths:
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            files_cleanup_pending += 1
            logger.exception("Could not remove an uploaded file during account deletion.")

    return {
        "message": "Votre compte et ses données ont été supprimés.",
        "files_cleanup_pending": files_cleanup_pending,
    }


@router.put("/me", response_model=UserPublic)
def update_me(
    user_data: UserUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sensitive_change = user_data.email is not None or user_data.password is not None
    if sensitive_change and not verify_password(user_data.current_password or "", current_user.password_hash):
        raise HTTPException(status_code=400, detail="Le mot de passe actuel est incorrect.")

    issue_verification_code = False
    if user_data.email is not None:
        normalized_email = str(user_data.email).lower()
        if normalized_email == current_user.pending_email:
            pass
        elif normalized_email == current_user.email:
            if current_user.pending_email is not None:
                current_user.pending_email = None
                db.query(EmailCode).filter(
                    EmailCode.user_id == current_user.id,
                    EmailCode.purpose == "verify",
                ).delete(synchronize_session=False)
        else:
            existing_user = db.query(User).filter(
                or_(User.email == normalized_email, User.pending_email == normalized_email),
                User.id != current_user.id,
            ).first()
            if existing_user:
                raise HTTPException(status_code=409, detail="Cette adresse email possède déjà un compte.")
            current_user.pending_email = normalized_email
            issue_verification_code = True

    if user_data.name:
        current_user.name = user_data.name.strip()
    if user_data.password:
        current_user.password_hash = get_password_hash(user_data.password)
        revoke_user_tokens(current_user)
    if user_data.profile_photo is not None:
        current_user.profile_photo = user_data.profile_photo

    if issue_verification_code:
        db.flush()
        code = issue_email_code(db, current_user, "verify")
        if current_user.pending_email is None:
            raise HTTPException(status_code=400, detail="Aucune adresse email en attente de vérification.")
        _schedule_email_code(background_tasks, current_user, current_user.pending_email, code, "verify")
    else:
        db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    revoke_token(db, credentials.credentials)
    return None
