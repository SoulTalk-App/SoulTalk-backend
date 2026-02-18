from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
import logging

from app.db.dependencies import get_db
from app.api.deps import get_current_user, get_client_info
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.models.user import User
from app.schemas.auth import (
    UserRegistration,
    UserLogin,
    TokenRefresh,
    PasswordReset,
    NewPasswordRequest,
    SetPasswordRequest,
    AuthResponse,
    VerifyOTPRequest,
    ResendVerificationRequest,
    MessageResponse,
    UserIdResponse
)
from app.schemas.user import UserResponse, UserUpdate

logger = logging.getLogger(__name__)
router = APIRouter()

auth_service = AuthService()
user_service = UserService()


@router.post("/register", response_model=UserIdResponse)
async def register_user(
    user_data: UserRegistration,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user with email/password"""
    try:
        user, _ = await auth_service.register(
            db=db,
            email=user_data.email,
            password=user_data.password,
            first_name=user_data.first_name,
            last_name=user_data.last_name
        )
        return UserIdResponse(
            message="User registered successfully. Please check your email for verification.",
            user_id=str(user.id)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=AuthResponse)
async def login_user(
    login_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return tokens"""
    device_info, ip_address = get_client_info(request)

    try:
        access_token, refresh_token, expires_in = await auth_service.login(
            db=db,
            email=login_data.email,
            password=login_data.password,
            device_info=device_info,
            ip_address=ip_address
        )

        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_access_token(
    token_data: TokenRefresh,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    device_info, ip_address = get_client_info(request)

    try:
        access_token, refresh_token, expires_in = await auth_service.refresh_tokens(
            db=db,
            refresh_token=token_data.refresh_token,
            device_info=device_info,
            ip_address=ip_address
        )

        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/logout", response_model=MessageResponse)
async def logout_user(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db)
):
    """Logout user by invalidating refresh token"""
    success = await auth_service.logout(db, token_data.refresh_token)
    if success:
        return MessageResponse(message="Logged out successfully")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logout failed"
        )


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout from all devices"""
    count = await auth_service.logout_all_devices(db, current_user.id)
    return MessageResponse(message=f"Logged out from {count} device(s)")


@router.get("/me", response_model=UserResponse)
async def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user profile"""
    providers = await user_service.get_user_providers(db, current_user.id)

    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        display_name=current_user.display_name,
        username=current_user.username,
        bio=current_user.bio,
        pronoun=current_user.pronoun,
        email_verified=current_user.email_verified,
        providers=providers,
        created_at=current_user.created_at
    )


@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user profile"""
    update_fields = data.model_dump(exclude_unset=True)
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    # Check username uniqueness if being changed
    if "username" in update_fields and update_fields["username"] is not None:
        existing = await db.execute(
            select(User).where(
                User.username == update_fields["username"],
                User.id != current_user.id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken"
            )

    user = await user_service.update_user(db, current_user, **update_fields)
    providers = await user_service.get_user_providers(db, current_user.id)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        display_name=user.display_name,
        username=user.username,
        bio=user.bio,
        pronoun=user.pronoun,
        email_verified=user.email_verified,
        providers=providers,
        created_at=user.created_at
    )


@router.get("/verify-token")
async def verify_token(current_user: User = Depends(get_current_user)):
    """Verify if current token is valid"""
    return {
        "valid": True,
        "user_id": str(current_user.id),
        "email": current_user.email
    }


@router.post("/reset-password", response_model=MessageResponse)
async def request_password_reset(
    reset_data: PasswordReset,
    db: AsyncSession = Depends(get_db)
):
    """Send password reset email"""
    # Always return same message for security (don't reveal if email exists)
    await auth_service.request_password_reset(db, reset_data.email)
    return MessageResponse(
        message="If the email exists, a password reset link has been sent"
    )


@router.post("/reset-password/confirm", response_model=MessageResponse)
async def confirm_password_reset(
    reset_data: NewPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Reset password using token"""
    try:
        await auth_service.reset_password(
            db=db,
            token=reset_data.token,
            new_password=reset_data.new_password
        )
        return MessageResponse(message="Password reset successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/verify-email", response_model=AuthResponse)
async def verify_email(
    data: VerifyOTPRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Verify user email with OTP code and auto-login"""
    try:
        device_info, ip_address = get_client_info(request)
        user = await auth_service.verify_email(db, data.email, data.code)
        # Auto-login: generate tokens
        access_token, refresh_token, expires_in = await auth_service._generate_tokens(
            db, user, device_info, ip_address
        )
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification_email(
    data: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Resend email verification"""
    try:
        success = await auth_service.resend_verification_email(db, data.email)
        if success:
            return MessageResponse(
                message="Verification email sent. Please check your inbox."
            )
        else:
            # Don't reveal if email exists
            return MessageResponse(
                message="If the email exists, a verification link has been sent"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/check-username")
async def check_username(
    username: str = Query(..., min_length=1, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    """Check if a username is available"""
    result = await db.execute(
        select(User).where(User.username == username)
    )
    existing = result.scalar_one_or_none()
    return {"available": existing is None}


@router.post("/set-password", response_model=MessageResponse)
async def set_password(
    data: SetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Set password for social-only users"""
    try:
        await auth_service.set_password_for_social_user(
            db=db,
            user=current_user,
            password=data.password
        )
        return MessageResponse(message="Password set successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
