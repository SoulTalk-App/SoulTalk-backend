import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.social_account import SocialAccount, ProviderEnum
from app.services.password_service import password_service


class UserService:
    async def create_user(
        self,
        db: AsyncSession,
        email: str,
        first_name: str,
        last_name: str,
        password: Optional[str] = None,
        email_verified: bool = False
    ) -> User:
        """Create a new user"""
        password_hash = None
        if password:
            password_hash = password_service.hash_password(password)

        user = User(
            email=email.lower(),
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            display_first_name=first_name,
            email_verified=email_verified
        )

        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    async def get_user_by_id(
        self,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> Optional[User]:
        """Get user by ID"""
        result = await db.execute(
            select(User)
            .options(selectinload(User.social_accounts))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(
        self,
        db: AsyncSession,
        email: str
    ) -> Optional[User]:
        """Get user by email"""
        result = await db.execute(
            select(User)
            .options(selectinload(User.social_accounts))
            .where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def update_user(
        self,
        db: AsyncSession,
        user: User,
        **kwargs
    ) -> User:
        """Update user fields"""
        for key, value in kwargs.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)

        user.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(user)
        return user

    async def set_password(
        self,
        db: AsyncSession,
        user: User,
        password: str
    ) -> User:
        """Set user password"""
        user.password_hash = password_service.hash_password(password)
        user.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return user

    async def verify_password(
        self,
        user: User,
        password: str
    ) -> bool:
        """Verify user password"""
        if not user.password_hash:
            return False
        return password_service.verify_password(password, user.password_hash)

    async def mark_email_verified(
        self,
        db: AsyncSession,
        user: User
    ) -> User:
        """Mark user email as verified"""
        user.email_verified = True
        user.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return user

    async def update_last_login(
        self,
        db: AsyncSession,
        user: User
    ) -> User:
        """Update last login timestamp"""
        user.last_login_at = datetime.now(timezone.utc)
        await db.flush()
        return user

    async def link_social_account(
        self,
        db: AsyncSession,
        user: User,
        provider: ProviderEnum,
        provider_user_id: str,
        provider_email: Optional[str] = None,
        profile_data: Optional[dict] = None
    ) -> SocialAccount:
        """Link a social account to user"""
        social_account = SocialAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=provider_email,
            profile_data=profile_data
        )
        db.add(social_account)
        await db.flush()
        await db.refresh(social_account)
        return social_account

    async def get_social_account(
        self,
        db: AsyncSession,
        provider: ProviderEnum,
        provider_user_id: str
    ) -> Optional[SocialAccount]:
        """Get social account by provider and provider user ID"""
        result = await db.execute(
            select(SocialAccount)
            .options(selectinload(SocialAccount.user))
            .where(
                SocialAccount.provider == provider,
                SocialAccount.provider_user_id == provider_user_id
            )
        )
        return result.scalar_one_or_none()

    async def get_user_social_accounts(
        self,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> List[SocialAccount]:
        """Get all social accounts for a user"""
        result = await db.execute(
            select(SocialAccount)
            .where(SocialAccount.user_id == user_id)
        )
        return list(result.scalars().all())

    async def unlink_social_account(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        provider: ProviderEnum
    ) -> bool:
        """Unlink a social account from user"""
        result = await db.execute(
            delete(SocialAccount)
            .where(
                SocialAccount.user_id == user_id,
                SocialAccount.provider == provider
            )
        )
        return result.rowcount > 0

    async def get_user_providers(
        self,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> List[str]:
        """Get list of provider names linked to user"""
        accounts = await self.get_user_social_accounts(db, user_id)
        return [account.provider.value for account in accounts]

    async def has_password(self, user: User) -> bool:
        """Check if user has a password set"""
        return user.password_hash is not None
