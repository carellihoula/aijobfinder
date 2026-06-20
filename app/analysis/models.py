import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    cv_id = Column(UUID(as_uuid=True), ForeignKey("cvs.id"), nullable=True)

    status = Column(String, default="pending", nullable=False)  # pending | processing | completed | failed
    error = Column(Text, nullable=True)

    search_filters = Column(JSON, nullable=True)   # filters provided by the user at request time
    keywords = Column(JSON, nullable=True)
    matches = Column(JSON, nullable=True)
    final_report = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="analyses")