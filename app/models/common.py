import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text

from app.database import Base


class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True)
    recipient_email = Column(String(200), nullable=False)
    recipient_name = Column(String(300), nullable=True)
    subject = Column(String(500), nullable=False)
    body_preview = Column(Text, nullable=True)
    status = Column(Enum(EmailStatus), default=EmailStatus.PENDING, index=True)
    error_message = Column(Text, nullable=True)
    module = Column(String(50), nullable=False, index=True)
    reference_id = Column(Integer, nullable=True, index=True)
    attachment_paths = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ImportLog(Base):
    __tablename__ = "import_logs"

    id = Column(Integer, primary_key=True)
    filename = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=False)
    import_type = Column(String(50), nullable=False, index=True)
    rows_total = Column(Integer, default=0)
    rows_imported = Column(Integer, default=0)
    rows_skipped = Column(Integer, default=0)
    errors = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
