import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID

from app.cortex.db import CortexBase

EMBEDDING_DIM = 1536  # text-embedding-3-small


class CortexJob(CortexBase):
    __tablename__ = "cortex_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_hash = Column(String, unique=True, nullable=False, index=True)

    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, default="")
    description = Column(Text, default="")
    url = Column(String, default="")
    source = Column(String, default="")        # jsearch | adzuna | ...
    contract_type = Column(String, default="")
    remote = Column(Boolean, default=False)

    seniority = Column(String, nullable=True, default="", index=True)  # junior | mid | senior | ""
    skills = Column(JSON, nullable=True, default=list)                  # reserved for future enrichment

    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True, index=True)