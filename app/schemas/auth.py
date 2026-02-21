import re
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional

PASSWORD_PATTERN = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^a-zA-Z0-9])'
)
PASSWORD_ERROR = (
    "Password must contain at least one uppercase letter, "
    "one lowercase letter, one digit, and one special character"
)


def validate_password_complexity(password: str) -> str:
    if not PASSWORD_PATTERN.search(password):
        raise ValueError(PASSWORD_ERROR)
    return password


class UserRegistration(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)

    @field_validator('password')
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenRefresh(BaseModel):
    refresh_token: str


class PasswordReset(BaseModel):
    email: EmailStr


class NewPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator('new_password')
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator('new_password')
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)


class SetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator('password')
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SocialAuthRequest(BaseModel):
    id_token: str  # For Google, this is the ID token from Google Sign-In
    # For Facebook, this is the access token from Facebook Login


class VerifyEmailRequest(BaseModel):
    token: str


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class TokenVerifyResponse(BaseModel):
    valid: bool
    user_id: str
    email: str
    exp: int


class MessageResponse(BaseModel):
    message: str


class UserIdResponse(BaseModel):
    message: str
    user_id: str
