from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.schemas import AnalysisResponse
from app.analysis.service import get_user_analyses
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.users.models import User
from app.users.schemas import UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/me/analyses", response_model=list[AnalysisResponse])
async def get_my_analyses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_analyses(db, current_user.id)