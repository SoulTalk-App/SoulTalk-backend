from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.api.deps import get_current_active_user
from app.services.soul_bar_service import soul_bar_service
from app.schemas.soul_bar import SoulBarResponse
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=SoulBarResponse)
async def get_soul_bar(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's SoulBar progress"""
    bar = await soul_bar_service.get_or_create(db, current_user.id)
    return SoulBarResponse(
        points=bar.points,
        total_filled=bar.total_filled,
    )
