from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
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
from app.models.email_code import EmailCode
from app.models.user import User
from app.schemas.auth import (
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
from app.services.email_code_service import consume_email_code, issue_email_code
from app.services.email_service import send_email_code

router = APIRouter(prefix="/auth", tags=["Authentication"])
SIGNUP_ACCEPTED_MESSAGE = "Si cette adresse peut être traitée, un email contenant un code a été envoyé."


def login_rate_key(request: Request) -> str:
    client_ip = request.client.host if request.client else "unknown"
    email = request.headers.get("x-auth-email", "").strip().lower()
    return f"{client_ip}:{email}" if email else client_ip


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
    background_tasks.add_task(send_email_code, user.email, code, "verify")
    return {"message": "Un code de vérification a été envoyé à votre adresse email."}


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
            background_tasks.add_task(send_email_code, send_address, code, "verify")
    return {"message": SIGNUP_ACCEPTED_MESSAGE}


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
    user = db.query(User).filter(User.email == str(payload.email).lower()).first()
    if user is not None and user.is_verified:
        try:
            code = issue_email_code(db, user, "reset")
        except HTTPException as exc:
            if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                raise
        else:
            background_tasks.add_task(send_email_code, user.email, code, "reset")
    return {"message": SIGNUP_ACCEPTED_MESSAGE}


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
        background_tasks.add_task(send_email_code, current_user.pending_email, code, "verify")
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
