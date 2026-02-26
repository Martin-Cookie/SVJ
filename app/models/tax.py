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


class SendStatus(str, enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    SENDING = "sending"
    PAUSED = "paused"
    COMPLETED = "completed"


class EmailDeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaxSession(Base):
    __tablename__ = "tax_sessions"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    year = Column(Integer, nullable=True)
    email_subject = Column(String(500), nullable=True)
    email_body = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Send workflow
    send_batch_size = Column(Integer, default=10)
    send_batch_interval = Column(Integer, default=5)
    send_scheduled_at = Column(DateTime, nullable=True)
    send_status = Column(Enum(SendStatus), default=SendStatus.DRAFT, index=True)
    test_email_passed = Column(Boolean, default=False)
    send_confirm_each_batch = Column(Boolean, default=False)

    documents = relationship(
        "TaxDocument", back_populates="session", cascade="all, delete-orphan"
    )


class TaxDocument(Base):
    __tablename__ = "tax_documents"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("tax_sessions.id"), nullable=False, index=True)
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
    document_id = Column(Integer, ForeignKey("tax_documents.id"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=True, index=True)
    match_status = Column(Enum(MatchStatus), default=MatchStatus.UNMATCHED, index=True)
    match_confidence = Column(Float, nullable=True)
    admin_note = Column(Text, nullable=True)
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)

    # Email delivery (new workflow)
    email_status = Column(Enum(EmailDeliveryStatus), default=EmailDeliveryStatus.PENDING, index=True)
    email_address_used = Column(String(200), nullable=True)
    email_error = Column(Text, nullable=True)

    # Ad-hoc external recipient (not in DB)
    ad_hoc_name = Column(String(300), nullable=True)
    ad_hoc_email = Column(String(200), nullable=True)

    document = relationship("TaxDocument", back_populates="distributions")
    owner = relationship("Owner", back_populates="tax_distributions")
