from fastapi import APIRouter, HTTPException, Depends, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.dependencies import get_db
from app.api.deps import get_current_user, get_client_info
from app.services.social_auth_service import social_auth_service, SocialUserInfo
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.models.user import User
from app.models.social_account import ProviderEnum
from app.schemas.auth import SocialAuthRequest, AuthResponse, MessageResponse
from app.schemas.user import LinkedAccountResponse

logger = logging.getLogger(__name__)
router = APIRouter()

auth_service = AuthService()
user_service = UserService()


async def _handle_social_auth(
    db: AsyncSession,
    provider: ProviderEnum,
    user_info: SocialUserInfo,
    device_info: str | None,
    ip_address: str | None
) -> tuple[str, str, int]:
    """
    Handle social authentication logic.

    Account linking rules:
    - If social account exists: Login
    - If email exists but social not linked: Link provider and login
    - If nothing exists: Create new user
    """
    # Check if social account already exists
    social_account = await user_service.get_social_account(
        db, provider, user_info.provider_user_id
    )

    if social_account:
        # Social account exists - just login
        user = social_account.user
        if not user.is_active:
            raise ValueError("Account is deactivated")

        await user_service.update_last_login(db, user)
        return await auth_service._generate_tokens(db, user, device_info, ip_address)

    # Check if user exists with this email
    user = await user_service.get_user_by_email(db, user_info.email)

    if user:
        # User exists - link the social account
        await user_service.link_social_account(
            db=db,
            user=user,
            provider=provider,
            provider_user_id=user_info.provider_user_id,
            provider_email=user_info.email,
            profile_data=user_info.profile_data
        )

        # Update email verification if social provider verifies email
        if user_info.email_verified and not user.email_verified:
            await user_service.mark_email_verified(db, user)

        await user_service.update_last_login(db, user)
        return await auth_service._generate_tokens(db, user, device_info, ip_address)

    # Create new user
    user = await user_service.create_user(
        db=db,
        email=user_info.email,
        first_name=user_info.first_name or "User",
        last_name=user_info.last_name or "",
        password=None,  # Social-only user
        email_verified=user_info.email_verified
    )

    # Link social account
    await user_service.link_social_account(
        db=db,
        user=user,
        provider=provider,
        provider_user_id=user_info.provider_user_id,
        provider_email=user_info.email,
        profile_data=user_info.profile_data
    )

    await user_service.update_last_login(db, user)
    return await auth_service._generate_tokens(db, user, device_info, ip_address)


@router.post("/google", response_model=AuthResponse)
async def google_auth(
    auth_data: SocialAuthRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate with Google ID token"""
    device_info, ip_address = get_client_info(request)

    try:
        # Verify Google token
        user_info = await social_auth_service.verify_google_token(auth_data.id_token)

        if not user_info.email:
            raise ValueError("Email not provided by Google")

        # Handle authentication
        access_token, refresh_token, expires_in = await _handle_social_auth(
            db=db,
            provider=ProviderEnum.GOOGLE,
            user_info=user_info,
            device_info=device_info,
            ip_address=ip_address
        )

        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in
        )

    except ValueError as e:
        logger.error(f"Google auth error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/facebook", response_model=AuthResponse)
async def facebook_auth(
    auth_data: SocialAuthRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate with Facebook access token"""
    device_info, ip_address = get_client_info(request)

    try:
        # Verify Facebook token
        user_info = await social_auth_service.verify_facebook_token(auth_data.id_token)

        if not user_info.email:
            raise ValueError("Email not provided by Facebook. Please ensure email permission is granted.")

        # Handle authentication
        access_token, refresh_token, expires_in = await _handle_social_auth(
            db=db,
            provider=ProviderEnum.FACEBOOK,
            user_info=user_info,
            device_info=device_info,
            ip_address=ip_address
        )

        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in
        )

    except ValueError as e:
        logger.error(f"Facebook auth error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/link/google", response_model=MessageResponse)
async def link_google(
    auth_data: SocialAuthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Link Google account to existing user"""
    try:
        # Verify Google token
        user_info = await social_auth_service.verify_google_token(auth_data.id_token)

        # Check if this social account is already linked to another user
        existing = await user_service.get_social_account(
            db, ProviderEnum.GOOGLE, user_info.provider_user_id
        )
        if existing:
            if existing.user_id == current_user.id:
                raise ValueError("Google account is already linked to your account")
            raise ValueError("This Google account is linked to another user")

        # Link the account
        await user_service.link_social_account(
            db=db,
            user=current_user,
            provider=ProviderEnum.GOOGLE,
            provider_user_id=user_info.provider_user_id,
            provider_email=user_info.email,
            profile_data=user_info.profile_data
        )

        return MessageResponse(message="Google account linked successfully")

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/link/facebook", response_model=MessageResponse)
async def link_facebook(
    auth_data: SocialAuthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Link Facebook account to existing user"""
    try:
        # Verify Facebook token
        user_info = await social_auth_service.verify_facebook_token(auth_data.id_token)

        # Check if this social account is already linked to another user
        existing = await user_service.get_social_account(
            db, ProviderEnum.FACEBOOK, user_info.provider_user_id
        )
        if existing:
            if existing.user_id == current_user.id:
                raise ValueError("Facebook account is already linked to your account")
            raise ValueError("This Facebook account is linked to another user")

        # Link the account
        await user_service.link_social_account(
            db=db,
            user=current_user,
            provider=ProviderEnum.FACEBOOK,
            provider_user_id=user_info.provider_user_id,
            provider_email=user_info.email,
            profile_data=user_info.profile_data
        )

        return MessageResponse(message="Facebook account linked successfully")

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/link/{provider}", response_model=MessageResponse)
async def unlink_provider(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Unlink a social account from user"""
    # Validate provider
    try:
        provider_enum = ProviderEnum(provider.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider: {provider}"
        )

    # Cannot unlink email provider
    if provider_enum == ProviderEnum.EMAIL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unlink email provider"
        )

    # Get all linked providers
    providers = await user_service.get_user_providers(db, current_user.id)

    # Ensure user has another way to login
    if len(providers) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unlink the only authentication method"
        )

    # Check if user has password if unlinking social
    if not await user_service.has_password(current_user):
        remaining_providers = [p for p in providers if p != provider_enum.value]
        if "email" not in remaining_providers and len(remaining_providers) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Set a password before unlinking social accounts"
            )

    # Unlink
    success = await user_service.unlink_social_account(
        db, current_user.id, provider_enum
    )

    if success:
        return MessageResponse(message=f"{provider.capitalize()} account unlinked successfully")
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{provider.capitalize()} account not linked"
        )


@router.get("/linked-accounts")
async def get_linked_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of linked social accounts"""
    accounts = await user_service.get_user_social_accounts(db, current_user.id)

    return [
        LinkedAccountResponse(
            provider=account.provider.value,
            provider_email=account.provider_email,
            linked_at=account.created_at
        )
        for account in accounts
    ]
