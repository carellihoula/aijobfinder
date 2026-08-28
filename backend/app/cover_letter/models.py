import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID

from app.db.session import Base


class AnalysisCoverLetter(Base):
    """
    Persisted CoverLetterContent for a (analysis, job_index) pair.

    Deliberately a plain FK column with no relationship() back to Analysis - this
    table is only ever queried directly by (analysis_id, job_index), and skipping
    the ORM relationship avoids the cross-model mapper registration requirement
    that has repeatedly broken Celery tasks this session (a relationship() forces
    every process that touches one model to have imported both).
    """
    __tablename__ = "analysis_cover_letters"
    __table_args__ = (UniqueConstraint("analysis_id", "job_index", name="uq_analysis_cover_letter"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=False, index=True)
    job_index = Column(Integer, nullable=False)

    content = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
