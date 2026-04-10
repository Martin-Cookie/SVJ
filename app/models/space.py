"""Modely pro prostory SVJ — prostory, nájemci, nájemní vztahy."""

import enum
from datetime import datetime

from app.utils import utcnow

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, Float,
    ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.owner import OwnerType


# ── Enumy ──────────────────────────────────────────────────────────────


class SpaceStatus(str, enum.Enum):
    RENTED = "rented"
    VACANT = "vacant"
    BLOCKED = "blocked"


# ── Prostor ────────────────────────────────────────────────────────────


class Space(Base):
    __tablename__ = "spaces"

    id = Column(Integer, primary_key=True)
    space_number = Column(Integer, nullable=False, unique=True, index=True)
    designation = Column(String(100), nullable=False)
    section = Column(String(20), nullable=True, index=True)
    floor = Column(Integer, nullable=True)
    area = Column(Float, nullable=True)
    status = Column(Enum(SpaceStatus), nullable=False, default=SpaceStatus.VACANT, index=True)
    blocked_reason = Column(String(200), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    tenants = relationship("SpaceTenant", back_populates="space", cascade="all, delete-orphan")

    @property
    def active_tenant_rel(self):
        """Return active SpaceTenant or None."""
        for st in self.tenants:
            if st.is_active:
                return st
        return None


# ── Nájemce ────────────────────────────────────────────────────────────


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)

    # Link to Owner (if tenant is also an owner in the building)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=True, index=True)

    # Identity — used only when owner_id is NULL
    first_name = Column(String(200), nullable=True, index=True)
    last_name = Column(String(200), nullable=True, index=True)
    title = Column(String(50), nullable=True)
    name_with_titles = Column(String(300), nullable=True, index=True)
    name_normalized = Column(String(300), nullable=True, index=True)
    tenant_type = Column(Enum(OwnerType), nullable=True, default=OwnerType.PHYSICAL, index=True)

    # Identification
    birth_number = Column(String(20), nullable=True, index=True)
    company_id = Column(String(20), nullable=True, index=True)

    # Permanent address
    perm_street = Column(String(200), nullable=True)
    perm_district = Column(String(100), nullable=True)
    perm_city = Column(String(100), nullable=True)
    perm_zip = Column(String(20), nullable=True)
    perm_country = Column(String(50), nullable=True)

    # Correspondence address
    corr_street = Column(String(200), nullable=True)
    corr_district = Column(String(100), nullable=True)
    corr_city = Column(String(100), nullable=True)
    corr_zip = Column(String(20), nullable=True)
    corr_country = Column(String(50), nullable=True)

    # Contact
    phone = Column(String(50), nullable=True, index=True)
    phone_landline = Column(String(50), nullable=True)
    phone_secondary = Column(String(50), nullable=True)
    email = Column(String(200), nullable=True, index=True)
    email_secondary = Column(String(200), nullable=True)

    # Metadata
    is_active = Column(Boolean, default=True, index=True)
    note = Column(Text, nullable=True)
    data_source = Column(String(50), default="manual")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    owner = relationship("Owner")
    spaces = relationship("SpaceTenant", back_populates="tenant", cascade="all, delete-orphan")

    # ── Properties that resolve from Owner when linked ──

    @property
    def display_name(self) -> str:
        if self.owner_id and self.owner:
            return self.owner.display_name
        parts = []
        if self.title:
            parts.append(self.title)
        if self.last_name:
            parts.append(self.last_name)
        if self.first_name:
            parts.append(self.first_name)
        return " ".join(parts) if parts else (self.name_with_titles or "")

    @property
    def resolved_phone(self) -> str:
        if self.owner_id and self.owner:
            return self.owner.phone or ""
        return self.phone or ""

    @property
    def resolved_email(self) -> str:
        if self.owner_id and self.owner:
            return self.owner.email or ""
        return self.email or ""

    @property
    def resolved_type(self):
        if self.owner_id and self.owner:
            return self.owner.owner_type
        return self.tenant_type

    @property
    def resolved_birth_number(self) -> str:
        if self.owner_id and self.owner:
            return self.owner.birth_number or ""
        return self.birth_number or ""

    @property
    def resolved_company_id(self) -> str:
        if self.owner_id and self.owner:
            return self.owner.company_id or ""
        return self.company_id or ""

    @property
    def resolved_name_normalized(self) -> str:
        if self.owner_id and self.owner:
            return self.owner.name_normalized or ""
        return self.name_normalized or ""

    @property
    def is_linked(self) -> bool:
        return self.owner_id is not None

    @property
    def active_space_rel(self):
        """Return active SpaceTenant or None (první aktivní dle space_number)."""
        rels = self.active_space_rels
        return rels[0] if rels else None

    @property
    def active_space_rels(self):
        """Všechny aktivní SpaceTenants, seřazené podle čísla prostoru."""
        rels = [st for st in self.spaces if st.is_active]
        rels.sort(key=lambda st: (st.space.space_number if st.space else 0))
        return rels


# ── Nájemní vztah ──────────────────────────────────────────────────────


class SpaceTenant(Base):
    __tablename__ = "space_tenants"

    id = Column(Integer, primary_key=True)
    space_id = Column(Integer, ForeignKey("spaces.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Contract details
    contract_number = Column(String(50), nullable=True)
    contract_start = Column(Date, nullable=True)
    contract_end = Column(Date, nullable=True)
    monthly_rent = Column(Float, nullable=False, default=0.0)
    variable_symbol = Column(String(20), nullable=True, index=True)
    contract_path = Column(String(500), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True, index=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    space = relationship("Space", back_populates="tenants")
    tenant = relationship("Tenant", back_populates="spaces")

    __table_args__ = (
        Index("ix_space_tenant_composite", "space_id", "tenant_id"),
    )
