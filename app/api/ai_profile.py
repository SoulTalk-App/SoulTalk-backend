from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.user_ai_profile import UserAIProfile
from app.schemas.ai_profile import AIProfileUpdate, AIProfileResponse

router = APIRouter()


@router.get("/", response_model=AIProfileResponse)
async def get_ai_profile(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's AI preferences"""
    result = await db.execute(
        select(UserAIProfile).where(UserAIProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        # Create default profile
        profile = UserAIProfile(user_id=current_user.id)
        db.add(profile)
        await db.flush()
        await db.refresh(profile)

    return AIProfileResponse.model_validate(profile)


@router.put("/", response_model=AIProfileResponse)
async def update_ai_profile(
    data: AIProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's AI preferences"""
    result = await db.execute(
        select(UserAIProfile).where(UserAIProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserAIProfile(user_id=current_user.id)
        db.add(profile)

    if data.main_focus is not None:
        profile.main_focus = data.main_focus
    if data.tone_preference is not None:
        profile.tone_preference = data.tone_preference
    if data.spiritual_metadata is not None:
        profile.spiritual_metadata = data.spiritual_metadata
    if data.soulpal_name is not None:
        profile.soulpal_name = data.soulpal_name

    await db.flush()
    await db.refresh(profile)
    return AIProfileResponse.model_validate(profile)
