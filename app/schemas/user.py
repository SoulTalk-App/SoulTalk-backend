from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
import uuid


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    email_verified: bool
    providers: List[str]  # List of linked providers (google, facebook, email)
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None


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
    email_verified: bool
    is_active: bool
    providers: List[str]
    linked_accounts: List[LinkedAccountResponse]
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True
