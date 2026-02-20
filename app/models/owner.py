import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class OwnerType(str, enum.Enum):
    PHYSICAL = "physical"
    SJM = "sjm"
    LEGAL_ENTITY = "legal"
    PARTIAL = "partial"


class Owner(Base):
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True)
    name_with_titles = Column(String(300), nullable=False)
    name_normalized = Column(String(300), nullable=False)
    owner_type = Column(Enum(OwnerType), nullable=False, default=OwnerType.PHYSICAL)
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    proxy_raw = Column(String(200), nullable=True)
    data_source = Column(String(50), default="excel")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    units = relationship("OwnerUnit", back_populates="owner", cascade="all, delete-orphan")
    ballots = relationship("Ballot", back_populates="owner")
    tax_distributions = relationship("TaxDistribution", back_populates="owner")
    given_proxies = relationship(
        "Proxy", foreign_keys="Proxy.grantor_id", back_populates="grantor"
    )
    received_proxies = relationship(
        "Proxy", foreign_keys="Proxy.proxy_holder_id", back_populates="proxy_holder"
    )


class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True)
    unit_number = Column(String(20), nullable=False)
    sub_number = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owners = relationship("OwnerUnit", back_populates="unit", cascade="all, delete-orphan")


class OwnerUnit(Base):
    __tablename__ = "owner_units"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    share = Column(Float, nullable=False, default=1.0)
    votes = Column(Integer, nullable=False, default=1)
    excel_row_number = Column(Integer, nullable=True)

    owner = relationship("Owner", back_populates="units")
    unit = relationship("Unit", back_populates="owners")


class Proxy(Base):
    __tablename__ = "proxies"

    id = Column(Integer, primary_key=True)
    grantor_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    proxy_holder_id = Column(Integer, ForeignKey("owners.id"), nullable=True)
    proxy_holder_name = Column(String(300), nullable=True)
    voting_id = Column(Integer, ForeignKey("votings.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    grantor = relationship("Owner", foreign_keys=[grantor_id], back_populates="given_proxies")
    proxy_holder = relationship(
        "Owner", foreign_keys=[proxy_holder_id], back_populates="received_proxies"
    )
