from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

TRIVIAL_PASSWORDS = {
    "password123",
    "password1234",
    "qwerty12345",
    "azerty12345",
    "1234567890",
    "iloveyou123",
}


def validate_password_policy(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise PydanticCustomError("password_too_long", "Le mot de passe ne doit pas dépasser 72 octets.")
    if len(password) < 10 or not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        raise PydanticCustomError(
            "password_policy",
            "Le mot de passe doit contenir au moins 10 caractères, une lettre et un chiffre.",
        )
    if password.lower() in TRIVIAL_PASSWORDS:
        raise PydanticCustomError("password_too_common", "Ce mot de passe est trop facile à deviner.")
    return password


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str

    _password_policy = field_validator("password")(validate_password_policy)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)

    @field_validator("password")
    @classmethod
    def password_bcrypt_limit(cls, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise PydanticCustomError("password_too_long", "Le mot de passe ne doit pas dépasser 72 octets.")
        return password


class UserPublic(BaseModel):
    id: int
    name: str
    email: EmailStr
    pending_email: EmailStr | None = None
    profile_photo: str | None = None
    created_at: datetime
    email_change_pending: bool = False
    role: str = "user"
    monthly_quota: int = 50
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EmailCodeRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(EmailCodeRequest):
    code: str = Field(..., pattern=r"^\d{6}$")
    new_password: str

    _password_policy = field_validator("new_password")(validate_password_policy)


class VerifyEmailRequest(EmailCodeRequest):
    code: str = Field(..., pattern=r"^\d{6}$")


class SignupAccepted(BaseModel):
    message: str
    delivery_mode: Literal["email", "console", "unavailable"] | None = None


class AccountDeleteRequest(BaseModel):
    current_password: str = Field(..., min_length=1)

    @field_validator("current_password")
    @classmethod
    def validate_current_password_length(cls, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise PydanticCustomError(
                "password_too_long",
                "Le mot de passe actuel ne doit pas dépasser 72 octets.",
            )
        return password


class AccountDeleteResponse(BaseModel):
    message: str
    files_cleanup_pending: int = 0


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    password: str | None = None
    profile_photo: str | None = None
    current_password: str | None = None

    @field_validator("password")
    @classmethod
    def validate_new_password(cls, password: str | None) -> str | None:
        return validate_password_policy(password) if password is not None else None

    @field_validator("current_password")
    @classmethod
    def validate_current_password_length(cls, password: str | None) -> str | None:
        if password is not None and len(password.encode("utf-8")) > 72:
            raise PydanticCustomError(
                "password_too_long",
                "Le mot de passe actuel ne doit pas dépasser 72 octets.",
            )
        return password

    @model_validator(mode="after")
    def require_current_password_for_sensitive_changes(self) -> Self:
        if (self.password is not None or self.email is not None) and not self.current_password:
            raise PydanticCustomError(
                "current_password_required",
                "Le mot de passe actuel est obligatoire pour cette modification.",
            )
        return self
