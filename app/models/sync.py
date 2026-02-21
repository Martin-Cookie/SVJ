import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class SyncStatus(str, enum.Enum):
    MATCH = "match"
    DIFFERENCE = "difference"
    MISSING_CSV = "missing_csv"
    MISSING_EXCEL = "missing_excel"


class SyncResolution(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_EDIT = "manual_edit"


class SyncSession(Base):
    __tablename__ = "sync_sessions"

    id = Column(Integer, primary_key=True)
    csv_filename = Column(String(300), nullable=False)
    csv_path = Column(String(500), nullable=False)
    total_records = Column(Integer, default=0)
    total_matches = Column(Integer, default=0)
    total_differences = Column(Integer, default=0)
    total_missing = Column(Integer, default=0)
    is_finalized = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    records = relationship(
        "SyncRecord", back_populates="session", cascade="all, delete-orphan"
    )


class SyncRecord(Base):
    __tablename__ = "sync_records"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sync_sessions.id"), nullable=False)
    unit_number = Column(String(20), nullable=True)
    csv_owner_name = Column(String(300), nullable=True)
    excel_owner_name = Column(String(300), nullable=True)
    csv_ownership_type = Column(String(50), nullable=True)
    excel_ownership_type = Column(String(50), nullable=True)
    csv_email = Column(String(200), nullable=True)
    csv_phone = Column(String(50), nullable=True)
    excel_space_type = Column(String(50), nullable=True)
    excel_podil_scd = Column(Integer, nullable=True)
    status = Column(Enum(SyncStatus), nullable=False)
    resolution = Column(Enum(SyncResolution), default=SyncResolution.PENDING)
    admin_corrected_name = Column(String(300), nullable=True)
    admin_note = Column(Text, nullable=True)
    match_details = Column(Text, nullable=True)

    session = relationship("SyncSession", back_populates="records")
