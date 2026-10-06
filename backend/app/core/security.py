import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.revoked_token import RevokedToken
from app.models.user import User

ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
if ALGORITHM != "HS256":
    raise RuntimeError("JWT_ALGORITHM must be HS256.")
ENVIRONMENT = os.getenv("ENV", "production").lower()
configured_secret = os.getenv("JWT_SECRET_KEY", "")
if ENVIRONMENT == "dev":
    SECRET_KEY = configured_secret or secrets.token_urlsafe(48)
elif len(configured_secret) < 32 or configured_secret == "change-me-in-production":
    raise RuntimeError("JWT_SECRET_KEY must be configured with at least 32 characters.")
else:
    SECRET_KEY = configured_secret

try:
    ACCESS_TOKEN_EXPIRE_MINUTES = min(30, int(os.getenv("JWT_EXPIRE_MINUTES", "30")))
except ValueError as exc:
    raise RuntimeError("JWT_EXPIRE_MINUTES must be a positive integer.") from exc
if ACCESS_TOKEN_EXPIRE_MINUTES < 1:
    raise RuntimeError("JWT_EXPIRE_MINUTES must be a positive integer.")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
DUMMY_PASSWORD_HASH = pwd_context.hash(secrets.token_urlsafe(32))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, token_version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "jti": str(uuid4()),
        "type": "access",
        "ver": token_version,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def cleanup_expired_revocations(db: Session) -> None:
    now = datetime.now(timezone.utc)
    db.query(RevokedToken).filter(RevokedToken.expires_at <= now).delete(synchronize_session=False)
    db.commit()


def revoke_token(db: Session, token: str) -> None:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    jti = payload.get("jti")
    expires_at = payload.get("exp")
    if not isinstance(jti, str) or not isinstance(expires_at, (int, float)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")
    cleanup_expired_revocations(db)
    if db.query(RevokedToken).filter(RevokedToken.jti == jti).first() is None:
        db.add(RevokedToken(
            jti=jti,
            expires_at=datetime.fromtimestamp(expires_at, tz=timezone.utc),
        ))
        db.commit()


def revoke_user_tokens(user: User) -> None:
    user.token_version += 1


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token.",
        )

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        jti = payload.get("jti")
        token_version = payload.get("ver")
        if (
            payload.get("type") != "access"
            or not isinstance(subject, str)
            or not subject.isdigit()
            or not isinstance(jti, str)
            or not isinstance(token_version, int)
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        ) from exc

    cleanup_expired_revocations(db)
    if db.query(RevokedToken).filter(RevokedToken.jti == jti).first() is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")

    user = db.query(User).filter(User.id == int(subject)).first()
    if user is None or user.token_version != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for this token.",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ACCOUNT_DISABLED")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="EMAIL_NOT_VERIFIED")

    return user
