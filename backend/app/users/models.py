import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # Nullable - accounts created via Google OIDC have no password at all.
    hashed_password = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    is_active    = Column(Boolean, default=True)
    is_admin     = Column(Boolean, default=False, nullable=False)
    is_verified  = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    preferences = Column(JSON, nullable=True)
    avatar_key  = Column(String, nullable=True)  # self-hosted avatar, S3 object key

    # Google OIDC
    google_id  = Column(String, unique=True, index=True, nullable=True)
    avatar_url = Column(String, nullable=True)  # Google-provided profile picture URL

    analyses = relationship("Analysis", back_populates="user", cascade="all, delete-orphan")

    @property
    def has_password(self) -> bool:
        return self.hashed_password is not None