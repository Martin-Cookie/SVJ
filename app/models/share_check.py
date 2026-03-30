import enum
from datetime import datetime

from app.utils import utcnow

from sqlalchemy import (
    Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ShareCheckStatus(str, enum.Enum):
    MATCH = "match"
    DIFFERENCE = "difference"
    MISSING_DB = "missing_db"
    MISSING_FILE = "missing_file"


class ShareCheckResolution(str, enum.Enum):
    PENDING = "pending"
    UPDATED = "updated"
    SKIPPED = "skipped"


class ShareCheckSession(Base):
    __tablename__ = "share_check_sessions"

    id = Column(Integer, primary_key=True)
    filename = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=False)
    col_unit = Column(String(100), nullable=True)
    col_share = Column(String(100), nullable=True)
    total_records = Column(Integer, default=0)
    total_matches = Column(Integer, default=0)
    total_differences = Column(Integer, default=0)
    total_missing_db = Column(Integer, default=0)
    total_missing_file = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    records = relationship(
        "ShareCheckRecord", back_populates="session", cascade="all, delete-orphan"
    )


class ShareCheckRecord(Base):
    __tablename__ = "share_check_records"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("share_check_sessions.id"), nullable=False, index=True)
    unit_number = Column(Integer, nullable=True)
    db_share = Column(Float, nullable=True)
    file_share = Column(Float, nullable=True)
    status = Column(Enum(ShareCheckStatus), nullable=False, index=True)
    resolution = Column(Enum(ShareCheckResolution), default=ShareCheckResolution.PENDING, index=True)
    admin_note = Column(Text, nullable=True)

    session = relationship("ShareCheckSession", back_populates="records")


class ShareCheckColumnMapping(Base):
    __tablename__ = "share_check_column_mappings"

    id = Column(Integer, primary_key=True)
    col_unit = Column(String(100), nullable=False)
    col_share = Column(String(100), nullable=False)
    used_count = Column(Integer, default=1)
    last_used_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("col_unit", "col_share", name="uq_share_check_mapping"),
    )
