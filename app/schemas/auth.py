from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserRegistration(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)


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


class SetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=8, max_length=128)


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
