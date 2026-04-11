import enum
from datetime import datetime

from app.utils import utcnow

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Session, relationship

from app.database import Base


class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class BounceType(str, enum.Enum):
    HARD = "hard"
    SOFT = "soft"
    UNKNOWN = "unknown"


class EmailBounce(Base):
    __tablename__ = "email_bounces"

    id = Column(Integer, primary_key=True)
    recipient_email = Column(String(200), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=True, index=True)
    email_log_id = Column(Integer, ForeignKey("email_logs.id"), nullable=True, index=True)
    bounce_type = Column(Enum(BounceType), default=BounceType.UNKNOWN, index=True)
    reason = Column(Text, nullable=True)
    diagnostic_code = Column(String(500), nullable=True)
    subject = Column(String(500), nullable=True)
    module = Column(String(50), nullable=True, index=True)
    reference_id = Column(Integer, nullable=True, index=True)
    bounced_at = Column(DateTime, nullable=True, index=True)
    imap_uid = Column(String(50), nullable=True, index=True)
    imap_message_id = Column(String(300), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, index=True)

    owner = relationship("Owner", lazy="joined")
    email_log = relationship("EmailLog", lazy="joined")


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
    name_normalized = Column(String(300), nullable=True, index=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


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
    created_at = Column(DateTime, default=utcnow)


class ActivityAction(str, enum.Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    STATUS_CHANGED = "status_changed"
    IMPORTED = "imported"
    EXPORTED = "exported"
    RESTORED = "restored"


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)
    action = Column(Enum(ActivityAction), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    entity_name = Column(String(300), nullable=True)
    description = Column(String(500), nullable=True)
    module = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)


def log_activity(db: Session, action: ActivityAction, entity_type: str,
                 module: str, entity_id: int = None, entity_name: str = None,
                 description: str = None):
    """Log an activity event. Call before db.commit() in the router."""
    db.add(ActivityLog(
        action=action, entity_type=entity_type, entity_id=entity_id,
        entity_name=entity_name, description=description, module=module,
    ))
