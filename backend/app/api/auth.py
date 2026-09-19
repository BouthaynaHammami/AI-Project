from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user, get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import Token, UserCreate, UserLogin, UserPublic, UserUpdate

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    normalized_email = user_data.email.lower()
    existing_user = db.query(User).filter(User.email == normalized_email).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )

    user = User(
        name=user_data.name,
        email=normalized_email,
        password_hash=get_password_hash(user_data.password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    access_token = create_access_token(user.email)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    normalized_email = login_data.email.lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    if user is None or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    access_token = create_access_token(user.email)
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserPublic)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserPublic)
def update_me(user_data: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user_data.email and user_data.email.lower() != current_user.email:
        if db.query(User).filter(User.email == user_data.email.lower()).first():
            raise HTTPException(status_code=409, detail="Email already registered.")
        current_user.email = user_data.email.lower()
    if user_data.name:
        current_user.name = user_data.name.strip()
    if user_data.password:
        current_user.password_hash = get_password_hash(user_data.password)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    current_user: User = Depends(get_current_user),
):
    from app.core.security import REVOKED_TOKENS
    REVOKED_TOKENS.add(credentials.credentials)
    return None
