import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
REVOKED_TOKENS: set[str] = set()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str) -> str:
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token.",
        )

    token = credentials.credentials
    if token in REVOKED_TOKENS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
            )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        ) from exc

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for this token.",
        )

    return user
