import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text,
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

    # Identity (columns L, M, N from Excel)
    first_name = Column(String(200), nullable=False, index=True)
    last_name = Column(String(200), nullable=True, index=True)
    title = Column(String(50), nullable=True)
    name_with_titles = Column(String(300), nullable=False, index=True)
    name_normalized = Column(String(300), nullable=False, index=True)
    owner_type = Column(Enum(OwnerType), nullable=False, default=OwnerType.PHYSICAL, index=True)

    # Identification (column O)
    birth_number = Column(String(20), nullable=True, index=True)
    company_id = Column(String(20), nullable=True, index=True)

    # Permanent address (columns P-T)
    perm_street = Column(String(200), nullable=True)
    perm_district = Column(String(100), nullable=True)
    perm_city = Column(String(100), nullable=True, index=True)
    perm_zip = Column(String(20), nullable=True)
    perm_country = Column(String(50), nullable=True)

    # Correspondence address (columns U-Y)
    corr_street = Column(String(200), nullable=True)
    corr_district = Column(String(100), nullable=True)
    corr_city = Column(String(100), nullable=True)
    corr_zip = Column(String(20), nullable=True)
    corr_country = Column(String(50), nullable=True)

    # Contact (columns Z, AA, AB, AC)
    phone = Column(String(50), nullable=True, index=True)
    phone_landline = Column(String(50), nullable=True)
    email = Column(String(200), nullable=True, index=True)
    email_secondary = Column(String(200), nullable=True)

    # Metadata (columns AD, AE)
    owner_since = Column(String(50), nullable=True)
    note = Column(Text, nullable=True)

    data_source = Column(String(50), default="excel")
    is_active = Column(Boolean, default=True, index=True)
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
    unit_number = Column(String(20), nullable=False, unique=True, index=True)
    building_number = Column(String(20), nullable=True, index=True)
    podil_scd = Column(Integer, nullable=True)
    floor_area = Column(Float, nullable=True)
    room_count = Column(String(20), nullable=True)
    space_type = Column(String(50), nullable=True, index=True)
    section = Column(String(10), nullable=True, index=True)
    orientation_number = Column(Integer, nullable=True)
    address = Column(String(200), nullable=True)
    lv_number = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owners = relationship("OwnerUnit", back_populates="unit", cascade="all, delete-orphan")


class OwnerUnit(Base):
    __tablename__ = "owner_units"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    ownership_type = Column(String(20), nullable=True, index=True)
    share = Column(Float, nullable=False, default=1.0)
    votes = Column(Integer, nullable=False, default=0)
    excel_row_number = Column(Integer, nullable=True)

    owner = relationship("Owner", back_populates="units")
    unit = relationship("Unit", back_populates="owners")

    __table_args__ = (
        Index("ix_owner_unit_composite", "owner_id", "unit_id"),
    )


class Proxy(Base):
    __tablename__ = "proxies"

    id = Column(Integer, primary_key=True)
    grantor_id = Column(Integer, ForeignKey("owners.id"), nullable=False, index=True)
    proxy_holder_id = Column(Integer, ForeignKey("owners.id"), nullable=True, index=True)
    proxy_holder_name = Column(String(300), nullable=True)
    voting_id = Column(Integer, ForeignKey("votings.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    grantor = relationship("Owner", foreign_keys=[grantor_id], back_populates="given_proxies")
    proxy_holder = relationship(
        "Owner", foreign_keys=[proxy_holder_id], back_populates="received_proxies"
    )
