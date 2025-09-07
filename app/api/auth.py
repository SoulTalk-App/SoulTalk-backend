from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Dict, Optional
import logging

from app.services.keycloak_service import keycloak_service
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()


class UserRegistration(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenRefresh(BaseModel):
    refresh_token: str


class PasswordReset(BaseModel):
    email: EmailStr


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    email_verified: bool
    groups: list


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Dependency to get current authenticated user"""
    try:
        token = credentials.credentials
        user_info = await keycloak_service.verify_token(token)
        return user_info
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(current_user: Dict = Depends(get_current_user)) -> Dict:
    """Dependency to get current active user"""
    if not current_user.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not verified"
        )
    return current_user


@router.post("/register", response_model=Dict)
async def register_user(user_data: UserRegistration):
    """Register a new user"""
    try:
        result = await keycloak_service.register_user(
            email=user_data.email,
            password=user_data.password,
            first_name=user_data.first_name,
            last_name=user_data.last_name
        )
        return {
            "message": "User registered successfully. Please check your email for verification.",
            "user_id": result["user_id"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=AuthResponse)
async def login_user(login_data: UserLogin):
    """Authenticate user and return tokens"""
    try:
        token_response = await keycloak_service.authenticate_user(
            email=login_data.email,
            password=login_data.password
        )
        
        return AuthResponse(
            access_token=token_response["access_token"],
            refresh_token=token_response["refresh_token"],
            expires_in=token_response["expires_in"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_access_token(token_data: TokenRefresh):
    """Refresh access token using refresh token"""
    try:
        token_response = await keycloak_service.refresh_token(token_data.refresh_token)
        
        return AuthResponse(
            access_token=token_response["access_token"],
            refresh_token=token_response["refresh_token"],
            expires_in=token_response["expires_in"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/logout")
async def logout_user(token_data: TokenRefresh):
    """Logout user by invalidating refresh token"""
    try:
        success = await keycloak_service.logout_user(token_data.refresh_token)
        if success:
            return {"message": "Logged out successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Logout failed"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/me", response_model=UserInfo)
async def get_user_profile(current_user: Dict = Depends(get_current_user)):
    """Get current user profile"""
    try:
        user_id = current_user.get("sub")
        user_data = await keycloak_service.get_user_by_id_direct(user_id)
        user_groups = await keycloak_service.get_user_groups(user_id)
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserInfo(
            id=user_data["id"],
            email=user_data["email"],
            first_name=user_data.get("firstName", ""),
            last_name=user_data.get("lastName", ""),
            email_verified=user_data.get("emailVerified", False),
            groups=[group["name"] for group in user_groups]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/reset-password")
async def reset_password(reset_data: PasswordReset):
    """Send password reset email"""
    try:
        success = await keycloak_service.reset_password(reset_data.email)
        if success:
            return {"message": "Password reset email sent"}
        else:
            return {"message": "If the email exists, a password reset link has been sent"}
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        return {"message": "If the email exists, a password reset link has been sent"}


@router.get("/verify-token")
async def verify_token(current_user: Dict = Depends(get_current_user)):
    """Verify if current token is valid"""
    return {
        "valid": True,
        "user_id": current_user.get("sub"),
        "email": current_user.get("email"),
        "exp": current_user.get("exp")
    }