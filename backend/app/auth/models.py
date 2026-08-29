import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class RefreshToken(Base):
    """
    One row per issued refresh token. The raw token never touches the DB - only
    its SHA-256 hash - so a DB leak alone doesn't hand out usable tokens.

    Rotation: every /auth/refresh call revokes the presented token and issues a
    new one carrying the same family_id. If a REVOKED token is ever presented
    again (a stolen, already-rotated-out token being replayed), the whole
    family is revoked, forcing that user to log in again everywhere.

    Deliberately a plain FK column with no relationship() back to User - see
    the same rationale in app/cover_letter/models.py.
    """
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    token_hash = Column(String, unique=True, index=True, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
