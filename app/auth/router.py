from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.schemas import LoginRequest, RegisterRequest
from app.config import settings
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])

_COOKIE_NAME = "token"
_COOKIE_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )


@router.post("/register", status_code=201)
async def register(data: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    token = await service.register(db, data)
    _set_auth_cookie(response, token)
    return {"ok": True}


@router.post("/login")
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    token = await service.login(db, data)
    _set_auth_cookie(response, token)
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=_COOKIE_NAME, path="/")
    return {"ok": True}
