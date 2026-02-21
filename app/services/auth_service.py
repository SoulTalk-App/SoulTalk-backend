import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.email_verification import EmailVerificationToken
from app.models.social_account import ProviderEnum
from app.services.user_service import UserService
from app.services.jwt_service import jwt_service
from app.services.email_service import email_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        self.user_service = UserService()

    async def register(
        self,
        db: AsyncSession,
        email: str,
        password: str,
        first_name: str,
        last_name: str
    ) -> Tuple[User, str]:
        """
        Register a new user with email/password.
        Returns (user, verification_token)
        """
        # Check if user exists
        existing_user = await self.user_service.get_user_by_email(db, email)
        if existing_user:
            raise ValueError("Email already registered")

        # Create user
        user = await self.user_service.create_user(
            db=db,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            email_verified=False
        )

        # Link email provider
        await self.user_service.link_social_account(
            db=db,
            user=user,
            provider=ProviderEnum.EMAIL,
            provider_user_id=email.lower(),
            provider_email=email.lower()
        )

        # Create OTP code
        otp_code, code_hash = jwt_service.generate_otp_code(settings.OTP_LENGTH)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.OTP_EXPIRE_MINUTES
        )

        verification = EmailVerificationToken(
            user_id=user.id,
            token_hash=code_hash,
            token_type="email_verification",
            expires_at=expires_at
        )
        db.add(verification)

        logger.info(f"OTP code for {email}: {otp_code}")

        # Send verification email
        await email_service.send_verification_email(
            to_email=email,
            first_name=first_name,
            otp_code=otp_code
        )

        return user, otp_code

    async def login(
        self,
        db: AsyncSession,
        email: str,
        password: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[str, str, int]:
        """
        Authenticate user with email/password.
        Returns (access_token, refresh_token, expires_in)
        """
        user = await self.user_service.get_user_by_email(db, email)
        if not user:
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is deactivated")

        if not await self.user_service.verify_password(user, password):
            raise ValueError("Invalid email or password")

        if not user.email_verified:
            raise ValueError("Please verify your email before logging in")

        # Update last login
        await self.user_service.update_last_login(db, user)

        # Generate tokens
        return await self._generate_tokens(db, user, device_info, ip_address)

    async def refresh_tokens(
        self,
        db: AsyncSession,
        refresh_token: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[str, str, int]:
        """
        Refresh access token using refresh token.
        Returns (access_token, new_refresh_token, expires_in)
        """
        token_hash = jwt_service.hash_refresh_token(refresh_token)

        # Find refresh token
        result = await db.execute(
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
        )
        stored_token = result.scalar_one_or_none()

        if not stored_token:
            raise ValueError("Invalid refresh token")

        if stored_token.is_revoked:
            raise ValueError("Refresh token has been revoked")

        if stored_token.is_expired:
            raise ValueError("Refresh token has expired")

        # Get user
        user = await self.user_service.get_user_by_id(db, stored_token.user_id)
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")

        # Revoke old token
        stored_token.is_revoked = True

        # Generate new tokens
        return await self._generate_tokens(db, user, device_info, ip_address)

    async def logout(
        self,
        db: AsyncSession,
        refresh_token: str
    ) -> bool:
        """Logout by revoking refresh token"""
        token_hash = jwt_service.hash_refresh_token(refresh_token)

        result = await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(is_revoked=True)
        )

        return result.rowcount > 0

    async def logout_all_devices(
        self,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> int:
        """Logout from all devices by revoking all refresh tokens"""
        result = await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False
            )
            .values(is_revoked=True)
        )

        return result.rowcount

    async def verify_access_token(
        self,
        token: str
    ) -> Optional[dict]:
        """Verify access token and return payload"""
        return jwt_service.decode_access_token(token)

    async def verify_email(
        self,
        db: AsyncSession,
        email: str,
        code: str
    ) -> User:
        """Verify user email with OTP code"""
        # Look up user by email
        user = await self.user_service.get_user_by_email(db, email)
        if not user:
            raise ValueError("Invalid verification code")

        code_hash = jwt_service.hash_refresh_token(code)  # Same hashing mechanism

        result = await db.execute(
            select(EmailVerificationToken)
            .where(
                EmailVerificationToken.token_hash == code_hash,
                EmailVerificationToken.token_type == "email_verification",
                EmailVerificationToken.user_id == user.id
            )
        )
        verification = result.scalar_one_or_none()

        if not verification:
            raise ValueError("Invalid verification code")

        if verification.is_used:
            raise ValueError("Code has already been used")

        if verification.is_expired:
            raise ValueError("Code has expired")

        # Mark token as used
        verification.is_used = True

        await self.user_service.mark_email_verified(db, user)

        return user

    async def request_password_reset(
        self,
        db: AsyncSession,
        email: str
    ) -> Optional[str]:
        """
        Request password reset.
        Returns token if user exists, None otherwise (for security)
        """
        user = await self.user_service.get_user_by_email(db, email)
        if not user:
            # Don't reveal whether email exists
            return None

        # Social-only users (Google/Facebook) have no password to reset
        if not user.password_hash:
            raise ValueError("social_auth_only")

        # Create reset token
        raw_token, token_hash = jwt_service.create_verification_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.PASSWORD_RESET_EXPIRE_HOURS
        )

        reset_token = EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            token_type="password_reset",
            expires_at=expires_at
        )
        db.add(reset_token)

        # Send reset email
        await email_service.send_password_reset_email(
            to_email=email,
            first_name=user.first_name,
            token=raw_token
        )

        return raw_token

    async def reset_password(
        self,
        db: AsyncSession,
        token: str,
        new_password: str
    ) -> User:
        """Reset password using token"""
        token_hash = jwt_service.hash_refresh_token(token)

        result = await db.execute(
            select(EmailVerificationToken)
            .where(
                EmailVerificationToken.token_hash == token_hash,
                EmailVerificationToken.token_type == "password_reset"
            )
        )
        reset_token = result.scalar_one_or_none()

        if not reset_token:
            raise ValueError("Invalid reset token")

        if reset_token.is_used:
            raise ValueError("Token has already been used")

        if reset_token.is_expired:
            raise ValueError("Token has expired")

        # Mark token as used
        reset_token.is_used = True

        # Get user and set password
        user = await self.user_service.get_user_by_id(db, reset_token.user_id)
        if not user:
            raise ValueError("User not found")

        await self.user_service.set_password(db, user, new_password)

        # Revoke all refresh tokens for security
        await self.logout_all_devices(db, user.id)

        return user

    async def resend_verification_email(
        self,
        db: AsyncSession,
        email: str
    ) -> bool:
        """Resend verification email"""
        user = await self.user_service.get_user_by_email(db, email)
        if not user:
            return False

        if user.email_verified:
            raise ValueError("Email is already verified")

        # Invalidate old tokens
        await db.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.token_type == "email_verification",
                EmailVerificationToken.is_used == False
            )
            .values(is_used=True)
        )

        # Create new OTP code
        otp_code, code_hash = jwt_service.generate_otp_code(settings.OTP_LENGTH)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.OTP_EXPIRE_MINUTES
        )

        verification = EmailVerificationToken(
            user_id=user.id,
            token_hash=code_hash,
            token_type="email_verification",
            expires_at=expires_at
        )
        db.add(verification)

        logger.info(f"OTP code for {email}: {otp_code}")

        # Send email
        await email_service.send_verification_email(
            to_email=email,
            first_name=user.first_name,
            otp_code=otp_code
        )

        return True

    async def change_password(
        self,
        db: AsyncSession,
        user: User,
        current_password: str,
        new_password: str
    ) -> User:
        """Change password for a logged-in email user"""
        if not user.password_hash:
            raise ValueError("No password set. You signed up with a social provider.")

        if not await self.user_service.verify_password(user, current_password):
            raise ValueError("Current password is incorrect")

        await self.user_service.set_password(db, user, new_password)

        # Revoke all refresh tokens — forces re-login on all devices
        await self.logout_all_devices(db, user.id)

        return user

    async def set_password_for_social_user(
        self,
        db: AsyncSession,
        user: User,
        password: str
    ) -> User:
        """Set password for a social-only user"""
        if user.password_hash:
            raise ValueError("User already has a password")

        await self.user_service.set_password(db, user, password)

        # Link email provider if not already linked
        providers = await self.user_service.get_user_providers(db, user.id)
        if "email" not in providers:
            await self.user_service.link_social_account(
                db=db,
                user=user,
                provider=ProviderEnum.EMAIL,
                provider_user_id=user.email,
                provider_email=user.email
            )

        return user

    async def _generate_tokens(
        self,
        db: AsyncSession,
        user: User,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[str, str, int]:
        """Generate access and refresh tokens"""
        # Create access token
        access_token, expires_in = jwt_service.create_access_token(
            user_id=user.id,
            email=user.email
        )

        # Create refresh token
        raw_refresh, refresh_hash, refresh_expires = jwt_service.create_refresh_token()

        # Store refresh token
        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=refresh_expires
        )
        db.add(refresh_token_record)

        return access_token, raw_refresh, expires_in
