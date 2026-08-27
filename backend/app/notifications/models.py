import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base

# analysis_completed | analysis_failed | cover_letter_ready | cover_letter_failed | new_matches
NOTIFICATION_TYPES = (
    "analysis_completed",
    "analysis_failed",
    "cover_letter_ready",
    "cover_letter_failed",
    "new_matches",
)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    link = Column(String, nullable=True)  # frontend route to navigate to on click

    read = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
