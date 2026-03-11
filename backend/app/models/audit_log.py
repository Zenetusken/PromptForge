"""Audit log model for authentication events."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(64), nullable=False, index=True)
    user_id = Column(Text, nullable=True, index=True)  # nullable for failed logins
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    user_agent = Column(Text, nullable=True)
    metadata_ = Column("metadata", Text, nullable=True)  # JSON
    created_at = Column(DateTime, default=_utcnow, nullable=False, index=True)
