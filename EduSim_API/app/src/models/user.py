import uuid

from sqlalchemy import Column, DateTime, Integer, String, Boolean, UUID, Text, Index, ForeignKey, CheckConstraint
from sqlalchemy.sql import func

from app.src.config.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100))
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String(20), default="student", server_default="student")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_active_at = Column(DateTime(timezone=True), nullable=True)
    avatar = Column(String(500), nullable=True)
    
    # New columns for advanced authentication & verification
    mobile_number = Column(String(20), nullable=True)
    is_email_verified = Column(Boolean, default=False)
    is_mobile_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    otp_code = Column(String, nullable=True)
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    otp_attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    otp_locked_until = Column(DateTime(timezone=True), nullable=True)
    reset_token_expires_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def auth_provider(self) -> str:
        if self.password_hash and self.password_hash.startswith("OAUTH_GOOGLE_SENTINEL_"):
            return "google"
        return "password"

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_role", "role"),
        Index("ix_users_last_active_at", "last_active_at"),
        CheckConstraint("role IN ('student', 'teacher', 'admin')", name="ck_users_role"),
    )


