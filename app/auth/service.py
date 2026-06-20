from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.auth.utils import create_access_token, hash_password, verify_password
from app.logger import get_logger
from app.users.service import create_user, get_user_by_email

logger = get_logger(__name__)


async def register(db: AsyncSession, data: RegisterRequest) -> TokenResponse:
    if await get_user_by_email(db, data.email):
        logger.warning("[auth] Registration failed — email already exists: %s", data.email)
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await create_user(db, data.email, hash_password(data.password), data.full_name)
    logger.info("[auth] New user registered: %s (id=%s)", data.email, user.id)
    return TokenResponse(access_token=create_access_token({"sub": str(user.id)}))


async def login(db: AsyncSession, data: LoginRequest) -> TokenResponse:
    user = await get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.hashed_password):
        logger.warning("[auth] Failed login attempt: %s", data.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    logger.info("[auth] User logged in: %s (id=%s)", data.email, user.id)
    return TokenResponse(access_token=create_access_token({"sub": str(user.id)}))