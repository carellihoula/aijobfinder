import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.sql import func

from app.db.session import Base


class CV(Base):
    __tablename__ = "cvs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    version = Column(Integer, default=1, nullable=False)
    source = Column(String, default="upload", nullable=False)  # upload | manual | ai

    pdf_path = Column(String, nullable=True)           # storage key (local path or S3 key)
    pdf_hash = Column(String(64), nullable=True)       # SHA-256 of the PDF content
    raw_text = Column(String, nullable=True)           # original extracted text
    data = Column(JSON, nullable=False)                # CVSchema stored as JSON

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())