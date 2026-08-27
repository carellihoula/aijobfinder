from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.schemas import AnalysisResponse
from app.analysis.service import get_user_analyses
from app.auth.dependencies import get_current_user
from app.auth.utils import hash_password, verify_password
from app.db.session import get_db
from app.storage import delete_file, read_file, save_avatar
from app.users.models import User
from app.users.schemas import UserResponse
from app.users import service as user_svc

router = APIRouter(prefix="/users", tags=["Users"])

_AVATAR_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png":  "png",
    "image/webp": "webp",
    "image/gif":  "gif",
}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/me/analyses", response_model=list[AnalysisResponse])
async def get_my_analyses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_analyses(db, current_user.id)


@router.get("/me/preferences")
async def get_preferences(current_user: User = Depends(get_current_user)):
    """Return the user's saved job-search preferences."""
    return current_user.preferences or {}


@router.get("/me/avatar")
async def get_avatar(current_user: User = Depends(get_current_user)):
    """Serve the user's avatar as a byte stream (S3 or local - no redirect)."""
    if not current_user.avatar_key:
        raise HTTPException(status_code=404, detail="No avatar set")

    key = current_user.avatar_key
    ext = Path(key).suffix.lstrip(".")
    content_type = next(
        (ct for ct, e in _ALLOWED_CONTENT_TYPES.items() if e == ext),
        "image/jpeg",
    )

    try:
        data = await read_file(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Avatar file not found")

    return StreamingResponse(
        iter([data]),
        media_type=content_type,
        headers={"Cache-Control": "no-cache, no-store"},
    )


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new profile avatar (JPEG, PNG, WebP, GIF - max 5 MB)."""
    ct = file.content_type or ""
    if ct not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image format. Use JPEG, PNG, WebP or GIF.")

    data = await file.read()
    if len(data) > _AVATAR_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 5 MB).")

    # Delete old avatar if it exists
    if current_user.avatar_key:
        await delete_file(current_user.avatar_key)

    ext = _ALLOWED_CONTENT_TYPES[ct]
    key = await save_avatar(data, str(current_user.id), ct, ext)
    await user_svc.update_avatar_key(db, current_user.id, key)

    return {"avatar_url": f"/api/users/me/avatar"}


@router.delete("/me/avatar", status_code=204)
async def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the user's avatar."""
    if current_user.avatar_key:
        await delete_file(current_user.avatar_key)
        await user_svc.update_avatar_key(db, current_user.id, None)


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update full_name and/or email."""
    if payload.email and payload.email != current_user.email:
        existing = await user_svc.get_user_by_email(db, payload.email)
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use")
    user = await user_svc.update_user_profile(
        db, current_user.id,
        full_name=payload.full_name,
        email=str(payload.email) if payload.email else None,
    )
    return user


@router.post("/me/change-password", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password after verifying the current one."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    await user_svc.update_user_password(db, current_user.id, hash_password(payload.new_password))


@router.delete("/me", status_code=204)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate the account (soft delete)."""
    await user_svc.deactivate_user(db, current_user.id)


@router.patch("/me/preferences")
async def update_preferences(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Partially update the user's job-search preferences (deep merge at top-level keys)."""
    merged = {**(current_user.preferences or {}), **payload}
    await user_svc.update_user_preferences(db, current_user.id, merged)
    return merged