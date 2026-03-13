"""Refinement branch and pairwise preference ORM models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Text

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class RefinementBranch(Base):
    __tablename__ = "refinement_branch"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    optimization_id = Column(Text, ForeignKey("optimizations.id", ondelete="CASCADE"), nullable=False)
    parent_branch_id = Column(Text, ForeignKey("refinement_branch.id", ondelete="SET NULL"), nullable=True)
    forked_at_turn = Column(Integer, nullable=True)
    label = Column(Text, nullable=False, default="trunk")
    optimized_prompt = Column(Text, nullable=True)
    scores = Column(Text, nullable=True)  # JSON
    session_context = Column(Text, nullable=True)  # JSON (SessionContext)
    turn_count = Column(Integer, default=0)
    turn_history = Column(Text, default="[]")  # JSON array
    status = Column(Text, default="active", nullable=False)  # active | selected | abandoned
    row_version = Column(Integer, nullable=False, server_default="0", default=0)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_branch_optimization", "optimization_id"),
        Index("ix_branch_opt_status", "optimization_id", "status"),
    )


class PairwisePreference(Base):
    __tablename__ = "pairwise_preference"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    optimization_id = Column(Text, ForeignKey("optimizations.id", ondelete="CASCADE"), nullable=False)
    preferred_branch_id = Column(Text, ForeignKey("refinement_branch.id", ondelete="SET NULL"), nullable=True)
    rejected_branch_id = Column(Text, ForeignKey("refinement_branch.id", ondelete="SET NULL"), nullable=True)
    preferred_scores = Column(Text, nullable=True)  # JSON
    rejected_scores = Column(Text, nullable=True)  # JSON
    user_id = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_pairwise_user", "user_id"),
        Index("ix_pairwise_optimization", "optimization_id"),
        Index("ix_pairwise_user_created", "user_id", "created_at"),
    )
