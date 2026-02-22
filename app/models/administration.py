from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class SvjInfo(Base):
    __tablename__ = "svj_info"

    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=True)
    building_type = Column(String(100), nullable=True)
    total_shares = Column(Integer, nullable=True)
    unit_count = Column(Integer, nullable=True)
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
