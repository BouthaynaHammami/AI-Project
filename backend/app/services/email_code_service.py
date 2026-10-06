import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import SECRET_KEY
from app.models.email_code import EmailCode
from app.models.user import User

CODE_LIFETIME = timedelta(minutes=10)
CODE_RESEND_INTERVAL = timedelta(seconds=60)
MAX_CODE_ATTEMPTS = 5


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def hash_email_code(user_id: int, purpose: str, code: str) -> str:
    payload = f"{user_id}:{purpose}:{code}".encode("utf-8")
    return hmac.new(SECRET_KEY.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def issue_email_code(
    db: Session,
    user: User,
    purpose: str,
    *,
    enforce_cooldown: bool = True,
) -> str:
    now = datetime.now(timezone.utc)
    previous = (
        db.query(EmailCode)
        .filter(EmailCode.user_id == user.id, EmailCode.purpose == purpose)
        .order_by(EmailCode.created_at.desc())
        .first()
    )
    if previous and enforce_cooldown and now - _utc(previous.created_at) < CODE_RESEND_INTERVAL:
        retry_after = max(
            1,
            int((CODE_RESEND_INTERVAL - (now - _utc(previous.created_at))).total_seconds()),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Veuillez attendre avant de demander un nouveau code.",
            headers={"Retry-After": str(retry_after)},
        )

    if previous is not None:
        db.delete(previous)
        db.flush()
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(EmailCode(
        user_id=user.id,
        purpose=purpose,
        code_hash=hash_email_code(user.id, purpose, code),
        attempts=0,
        created_at=now,
        expires_at=now + CODE_LIFETIME,
    ))
    db.commit()
    return code


def consume_email_code(db: Session, user: User, purpose: str, code: str) -> None:
    record = (
        db.query(EmailCode)
        .filter(EmailCode.user_id == user.id, EmailCode.purpose == purpose)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=400, detail="Code invalide ou expiré.")

    now = datetime.now(timezone.utc)
    expires_at = _utc(record.expires_at)
    if now >= expires_at:
        db.delete(record)
        db.commit()
        raise HTTPException(status_code=400, detail="Code invalide ou expiré.")

    if record.attempts >= MAX_CODE_ATTEMPTS:
        db.delete(record)
        db.commit()
        raise HTTPException(status_code=400, detail="Nombre maximal de tentatives atteint. Demandez un nouveau code.")

    expected = hash_email_code(user.id, purpose, code)
    if not hmac.compare_digest(record.code_hash, expected):
        record.attempts += 1
        attempts_exhausted = record.attempts >= MAX_CODE_ATTEMPTS
        if attempts_exhausted:
            db.delete(record)
        db.commit()
        detail = (
            "Nombre maximal de tentatives atteint. Demandez un nouveau code."
            if attempts_exhausted
            else "Code invalide."
        )
        raise HTTPException(status_code=400, detail=detail)

    db.delete(record)
    db.commit()
