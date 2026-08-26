import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base

# applied | in_progress | rejected | accepted — French labels are frontend-only
APPLICATION_STATUSES = ("applied", "in_progress", "rejected", "accepted")

# pending | processing | completed | failed — state of the background cover-letter generation task
COVER_LETTER_STATUSES = ("pending", "processing", "completed", "failed")


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    url = Column(String, nullable=True)         # set when added via scraped link
    summary = Column(Text, nullable=True)       # short display summary
    # Cleaned full job text — kept (unlike the rest of the pipeline) so a future
    # AI interview-prep feature can reuse it without re-scraping/re-pasting.
    description = Column(Text, nullable=True)

    status = Column(String, default="applied", nullable=False)  # overall current status

    cover_letter_status = Column(String, default="pending", nullable=False)
    cover_letter_content = Column(JSON, nullable=True)  # rendered CoverLetterContent, once generation completes

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    steps = relationship("ApplicationStep", back_populates="application", cascade="all, delete-orphan", order_by="ApplicationStep.created_at")


class ApplicationStep(Base):
    __tablename__ = "application_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True)

    label = Column(String, nullable=False)   # free text, e.g. "Entretien RH"
    status = Column(String, default="applied", nullable=False)
    date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    application = relationship("Application", back_populates="steps")
