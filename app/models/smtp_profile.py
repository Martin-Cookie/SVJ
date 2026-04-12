"""SMTP profily — uložení více SMTP konfigurací v DB."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils import utcnow


class SmtpProfile(Base):
    __tablename__ = "smtp_profiles"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    smtp_host = Column(String(255), nullable=False)
    smtp_port = Column(Integer, default=465)
    smtp_user = Column(String(255), nullable=False)
    smtp_password_b64 = Column(Text, nullable=False)
    smtp_from_name = Column(String(255), default="")
    smtp_from_email = Column(String(255), nullable=False)
    smtp_use_tls = Column(Boolean, default=True)
    imap_save_sent = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
