"""
File storage abstraction - local disk or AWS S3.

Backend selection (automatic):
  - S3_BUCKET + AWS_ACCESS_KEY_ID set in config → AWS S3
  - Otherwise → local UPLOAD_DIR (dev / no-S3 environments)

The rest of the codebase only calls:
  save_cv()         - persist an uploaded CV PDF
  read_file()       - read bytes by storage key
  get_presigned_url() - temporary download URL (S3) or None (local)
  delete_file()     - remove a stored file
"""
import os
import uuid as _uuid
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


# ── S3 client ─────────────────────────────────────────────────────────────────

def _client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION or None,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )


def s3_enabled() -> bool:
    return bool(settings.S3_BUCKET and settings.AWS_ACCESS_KEY_ID)


# ── Public interface ──────────────────────────────────────────────────────────

async def save_cv(
    data: bytes,
    user_id: str,
    cv_id: str,
    original_filename: str,
) -> str:
    """
    Persist a CV PDF. Returns the storage key used to retrieve it later.
    Key format: cvs/{user_id}/{cv_id}.pdf
    """
    ext = Path(original_filename).suffix or ".pdf"
    key = f"cvs/{user_id}/{cv_id}{ext}"

    if s3_enabled():
        _client().put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=data,
            ContentType="application/pdf",
            ContentDisposition=f'attachment; filename="{original_filename}"',
            Metadata={
                "user_id": user_id,
                "cv_id": cv_id,
                "original_filename": original_filename,
            },
        )
        logger.info("[storage] S3 upload - key=%s (%d bytes)", key, len(data))
    else:
        local_path = Path(settings.UPLOAD_DIR) / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        logger.info("[storage] Local save - path=%s (%d bytes)", local_path, len(data))

    return key


async def read_file(key: str) -> bytes:
    """Read file bytes by storage key. Raises FileNotFoundError if missing."""
    if s3_enabled():
        try:
            obj = _client().get_object(Bucket=settings.S3_BUCKET, Key=key)
            data = obj["Body"].read()
            logger.debug("[storage] S3 read - key=%s (%d bytes)", key, len(data))
            return data
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise FileNotFoundError(f"S3 key not found: {key}") from exc
            raise
    else:
        local_path = Path(settings.UPLOAD_DIR) / key
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")
        return local_path.read_bytes()


def get_presigned_url(key: str, expires_in: int = 3600) -> str | None:
    """
    Return a temporary download URL for the file.
    S3: presigned URL valid for `expires_in` seconds.
    Local: returns None (caller serves the file directly).
    """
    if not s3_enabled():
        return None
    url = _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )
    logger.debug("[storage] presigned URL generated for key=%s (expires=%ds)", key, expires_in)
    return url


async def save_avatar(data: bytes, user_id: str, content_type: str, ext: str) -> str:
    """
    Persist a user avatar image. Overwrites any previous avatar for the same user.
    Key format: avatars/{user_id}.{ext}
    """
    key = f"avatars/{user_id}.{ext}"

    if s3_enabled():
        _client().put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl="no-cache",
        )
        logger.info("[storage] S3 avatar upload - key=%s (%d bytes)", key, len(data))
    else:
        local_path = Path(settings.UPLOAD_DIR) / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        logger.info("[storage] Local avatar save - path=%s (%d bytes)", local_path, len(data))

    return key


async def delete_file(key: str) -> None:
    """Delete a file. Silently ignores missing files."""
    if s3_enabled():
        try:
            _client().delete_object(Bucket=settings.S3_BUCKET, Key=key)
            logger.info("[storage] S3 delete - key=%s", key)
        except ClientError:
            pass
    else:
        local_path = Path(settings.UPLOAD_DIR) / key
        if local_path.exists():
            local_path.unlink()
            logger.info("[storage] Local delete - path=%s", local_path)