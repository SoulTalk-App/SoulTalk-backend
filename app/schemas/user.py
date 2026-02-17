from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
import uuid


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    display_name: Optional[str] = None
    username: Optional[str] = None
    bio: Optional[str] = None
    pronoun: Optional[str] = None
    email_verified: bool
    providers: List[str]  # List of linked providers (google, facebook, email)
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    username: Optional[str] = Field(None, min_length=2, max_length=50, pattern=r'^[a-zA-Z0-9_]+$')
    bio: Optional[str] = Field(None, max_length=200)
    pronoun: Optional[str] = Field(None, max_length=30)


class LinkedAccountResponse(BaseModel):
    provider: str
    provider_email: Optional[str] = None
    linked_at: datetime

    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    display_name: Optional[str] = None
    username: Optional[str] = None
    bio: Optional[str] = None
    pronoun: Optional[str] = None
    email_verified: bool
    is_active: bool
    providers: List[str]
    linked_accounts: List[LinkedAccountResponse]
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True
