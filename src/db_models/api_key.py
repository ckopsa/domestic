import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text

from .base import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    key_hash = Column(String, nullable=False, unique=True, index=True)
    key_name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    revoked = Column(Boolean, nullable=False, default=False)

    def __repr__(self):
        return f"<APIKey(id={self.id}, user_id={self.user_id}, key_name={self.key_name})>"
