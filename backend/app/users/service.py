from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_google_id(db: AsyncSession, google_id: str) -> User | None:
    result = await db.execute(select(User).where(User.google_id == google_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, hashed_password: str, full_name: str) -> User:
    user = User(email=email, hashed_password=hashed_password, full_name=full_name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_google_user(
    db: AsyncSession, email: str, google_id: str, full_name: str | None, avatar_url: str | None
) -> User:
    # Google already verified this email address - no password, no verification email needed.
    user = User(
        email=email, hashed_password=None, full_name=full_name,
        google_id=google_id, avatar_url=avatar_url, is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def link_google_account(
    db: AsyncSession, user: User, google_id: str, avatar_url: str | None
) -> User:
    """Links Google to an existing email/password account on first Google sign-in
    with a matching email, instead of creating a duplicate account."""
    user.google_id = google_id
    if avatar_url and not user.avatar_url:
        user.avatar_url = avatar_url
    await db.commit()
    await db.refresh(user)
    return user


async def get_all_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def set_admin_status(db: AsyncSession, user_id: UUID, is_admin: bool) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.is_admin = is_admin
        await db.commit()
        await db.refresh(user)
    return user


async def update_avatar_key(db: AsyncSession, user_id: UUID, avatar_key: str | None) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.avatar_key = avatar_key
        await db.commit()
        await db.refresh(user)
    return user


async def update_user_preferences(db: AsyncSession, user_id: UUID, preferences: dict) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.preferences = preferences
        await db.commit()
        await db.refresh(user)
    return user


async def update_user_profile(db: AsyncSession, user_id: UUID, full_name: str | None = None, email: str | None = None) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        if full_name is not None:
            user.full_name = full_name
        if email is not None:
            user.email = email
        await db.commit()
        await db.refresh(user)
    return user


async def update_user_password(db: AsyncSession, user_id: UUID, hashed_password: str) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.hashed_password = hashed_password
        await db.commit()


async def verify_user(db: AsyncSession, user_id: UUID) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.is_verified = True
        await db.commit()


async def deactivate_user(db: AsyncSession, user_id: UUID) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.is_active = False
        await db.commit()