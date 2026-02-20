import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class MatchStatus(str, enum.Enum):
    AUTO_MATCHED = "auto_matched"
    CONFIRMED = "confirmed"
    MANUAL = "manual"
    UNMATCHED = "unmatched"


class TaxSession(Base):
    __tablename__ = "tax_sessions"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    year = Column(Integer, nullable=True)
    email_subject = Column(String(500), nullable=True)
    email_body = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship(
        "TaxDocument", back_populates="session", cascade="all, delete-orphan"
    )


class TaxDocument(Base):
    __tablename__ = "tax_documents"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("tax_sessions.id"), nullable=False)
    filename = Column(String(300), nullable=False)
    unit_number = Column(String(20), nullable=True)
    unit_letter = Column(String(5), nullable=True)
    file_path = Column(String(500), nullable=False)
    extracted_owner_name = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("TaxSession", back_populates="documents")
    distributions = relationship(
        "TaxDistribution", back_populates="document", cascade="all, delete-orphan"
    )


class TaxDistribution(Base):
    __tablename__ = "tax_distributions"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("tax_documents.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=True)
    match_status = Column(Enum(MatchStatus), default=MatchStatus.UNMATCHED)
    match_confidence = Column(Float, nullable=True)
    admin_note = Column(Text, nullable=True)
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)

    document = relationship("TaxDocument", back_populates="distributions")
    owner = relationship("Owner", back_populates="tax_distributions")
