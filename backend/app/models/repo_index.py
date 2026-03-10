import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, LargeBinary, Text

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class RepoFileIndex(Base):
    __tablename__ = "repo_file_index"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_full_name = Column(Text, nullable=False)      # e.g. "owner/repo"
    branch = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    file_sha = Column(Text, nullable=True)              # for cache invalidation
    file_size_bytes = Column(Integer, nullable=True)
    outline = Column(Text, nullable=True)               # function/class signatures
    embedding = Column(LargeBinary, nullable=False)     # numpy float32 tobytes (384 * 4 = 1536 bytes)
    indexed_at = Column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_repo_file_index_repo_branch", "repo_full_name", "branch"),
        Index(
            "idx_repo_file_index_unique_file",
            "repo_full_name",
            "branch",
            "file_path",
            unique=True,
        ),
        {"sqlite_autoincrement": False},  # Use UUID primary key
    )


class RepoIndexMeta(Base):
    __tablename__ = "repo_index_meta"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_full_name = Column(Text, nullable=False)
    branch = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="pending")  # pending, building, ready, partial, failed, expired
    file_count = Column(Integer, nullable=True)
    indexed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_repo_index_meta_repo_branch", "repo_full_name", "branch", unique=True),
    )
