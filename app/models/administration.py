from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class SvjInfo(Base):
    __tablename__ = "svj_info"

    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=True)
    building_type = Column(String(100), nullable=True)
    total_shares = Column(Integer, nullable=True)
    unit_count = Column(Integer, nullable=True)
    voting_import_mapping = Column(Text, nullable=True)  # Global JSON — last used import column mapping
    owner_import_mapping = Column(Text, nullable=True)   # JSON — last used owner import column mapping
    contact_import_mapping = Column(Text, nullable=True)  # JSON — last used contact import column mapping
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    addresses = relationship("SvjAddress", back_populates="svj_info",
                             order_by="SvjAddress.address", cascade="all, delete-orphan")


class SvjAddress(Base):
    __tablename__ = "svj_addresses"

    id = Column(Integer, primary_key=True)
    svj_info_id = Column(Integer, ForeignKey("svj_info.id"), nullable=False, index=True)
    address = Column(String(300), nullable=False)
    order = Column(Integer, default=0)

    svj_info = relationship("SvjInfo", back_populates="addresses")


class BoardMember(Base):
    __tablename__ = "board_members"

    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=False)
    role = Column(String(200), nullable=True)
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    group = Column(String(50), nullable=False, default="board", index=True)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class CodeListItem(Base):
    __tablename__ = "code_list_items"
    __table_args__ = (
        Index("ix_code_list_category_value", "category", "value", unique=True),
    )

    id = Column(Integer, primary_key=True)
    category = Column(String(50), nullable=False, index=True)
    # "space_type" | "section" | "room_count" | "ownership_type"
    value = Column(String(200), nullable=False)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True)
    subject_template = Column(String(500), nullable=False)
    body_template = Column(Text, nullable=False)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
