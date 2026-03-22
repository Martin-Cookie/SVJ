"""Modely pro evidenci plateb — předpisy, VS mapování, bankovní výpisy, platby, vyúčtování."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, Float,
    Integer, String, Text, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ── Enumy ──────────────────────────────────────────────────────────────


class SymbolSource(str, enum.Enum):
    AUTO = "auto"
    MANUAL = "manual"
    LEGACY = "legacy"


class BalanceSource(str, enum.Enum):
    MANUAL = "manual"
    IMPORT = "import"
    CARRYOVER = "carryover"


class PrescriptionCategory(str, enum.Enum):
    PROVOZNI = "provozni"
    FOND_OPRAV = "fond_oprav"
    SLUZBY = "sluzby"


class ImportStatus(str, enum.Enum):
    IMPORTED = "imported"
    PROCESSED = "processed"


class PaymentDirection(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class PaymentMatchStatus(str, enum.Enum):
    AUTO_MATCHED = "auto_matched"
    SUGGESTED = "suggested"
    MANUAL = "manual"
    UNMATCHED = "unmatched"


class SettlementStatus(str, enum.Enum):
    GENERATED = "generated"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"


# ── Variabilní symboly ────────────────────────────────────────────────


class VariableSymbolMapping(Base):
    __tablename__ = "variable_symbol_mappings"

    id = Column(Integer, primary_key=True)
    variable_symbol = Column(String(20), nullable=False, unique=True, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    source = Column(Enum(SymbolSource), default=SymbolSource.MANUAL, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    unit = relationship("Unit")


# ── Počáteční zůstatky ────────────────────────────────────────────────


class UnitBalance(Base):
    __tablename__ = "unit_balances"

    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    opening_amount = Column(Float, default=0.0)  # kladné=dluh, záporné=přeplatek
    source = Column(Enum(BalanceSource), default=BalanceSource.MANUAL)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    unit = relationship("Unit")

    __table_args__ = (
        UniqueConstraint("unit_id", "year", name="uq_unit_balance_year"),
    )


# ── Předpisy ──────────────────────────────────────────────────────────


class PrescriptionYear(Base):
    __tablename__ = "prescription_years"

    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False, unique=True, index=True)
    valid_from = Column(Date, nullable=True)
    description = Column(Text, nullable=True)
    source_filename = Column(String(300), nullable=True)
    total_units = Column(Integer, default=0)
    total_monthly = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    prescriptions = relationship(
        "Prescription", back_populates="prescription_year", cascade="all, delete-orphan"
    )


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True)
    prescription_year_id = Column(Integer, ForeignKey("prescription_years.id"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True, index=True)
    variable_symbol = Column(String(20), nullable=True, index=True)
    space_number = Column(Integer, nullable=True)
    section = Column(String(10), nullable=True)
    space_type = Column(String(50), nullable=True)
    owner_name = Column(String(300), nullable=True)
    monthly_total = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    prescription_year = relationship("PrescriptionYear", back_populates="prescriptions")
    items = relationship("PrescriptionItem", back_populates="prescription", cascade="all, delete-orphan")
    unit = relationship("Unit")


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id = Column(Integer, primary_key=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    amount = Column(Float, default=0.0)
    category = Column(Enum(PrescriptionCategory), default=PrescriptionCategory.PROVOZNI)
    order = Column(Integer, default=0)

    prescription = relationship("Prescription", back_populates="items")


# ── Bankovní výpisy ──────────────────────────────────────────────────


class BankStatement(Base):
    __tablename__ = "bank_statements"

    id = Column(Integer, primary_key=True)
    filename = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=True)
    bank_account = Column(String(30), nullable=True)
    period_from = Column(Date, nullable=True)
    period_to = Column(Date, nullable=True)
    opening_balance = Column(Float, nullable=True)
    closing_balance = Column(Float, nullable=True)
    total_income = Column(Float, default=0.0)
    total_expense = Column(Float, default=0.0)
    transaction_count = Column(Integer, default=0)
    matched_count = Column(Integer, default=0)
    import_status = Column(Enum(ImportStatus), default=ImportStatus.IMPORTED, index=True)
    locked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    payments = relationship("Payment", back_populates="statement", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    statement_id = Column(Integer, ForeignKey("bank_statements.id"), nullable=False, index=True)
    operation_id = Column(String(30), nullable=True, unique=True, index=True)
    date = Column(Date, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    direction = Column(Enum(PaymentDirection), nullable=False)
    counter_account = Column(String(50), nullable=True)
    counter_account_name = Column(String(200), nullable=True)
    bank_code = Column(String(10), nullable=True)
    bank_name = Column(String(100), nullable=True)
    ks = Column(String(20), nullable=True)
    vs = Column(String(20), nullable=True, index=True)
    ss = Column(String(20), nullable=True)
    note = Column(Text, nullable=True)
    message = Column(Text, nullable=True)
    payment_type = Column(String(50), nullable=True)
    match_status = Column(Enum(PaymentMatchStatus), default=PaymentMatchStatus.UNMATCHED, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=True, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=True, index=True)
    assigned_month = Column(Integer, nullable=True)  # 1-12
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    statement = relationship("BankStatement", back_populates="payments")
    prescription = relationship("Prescription")
    unit = relationship("Unit")
    owner = relationship("Owner")
    allocations = relationship("PaymentAllocation", back_populates="payment", cascade="all, delete-orphan")


# ── Mapování sloupců bankovních výpisů ────────────────────────────────


class BankStatementColumnMapping(Base):
    __tablename__ = "bank_statement_column_mappings"

    id = Column(Integer, primary_key=True)
    mapping_json = Column(Text, nullable=False)
    used_count = Column(Integer, default=1)
    last_used_at = Column(DateTime, default=datetime.utcnow)


# ── Vyúčtování (Fáze 4) ──────────────────────────────────────────────


# ── Alokace plateb (multi-unit) ──────────────────────────────────────


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"

    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=True, index=True)
    amount = Column(Float, nullable=False)

    payment = relationship("Payment", back_populates="allocations")
    unit = relationship("Unit")
    owner = relationship("Owner")
    prescription = relationship("Prescription")


# ── Vyúčtování (Fáze 4) ──────────────────────────────────────────────


class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=True, index=True)
    result_amount = Column(Float, default=0.0)
    variable_symbol = Column(String(20), nullable=True)
    specific_symbol = Column(String(20), nullable=True)
    pdf_path = Column(String(500), nullable=True)
    status = Column(Enum(SettlementStatus), default=SettlementStatus.GENERATED, index=True)
    penalty_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    unit = relationship("Unit")
    owner = relationship("Owner")
    items = relationship("SettlementItem", back_populates="settlement", cascade="all, delete-orphan")


class SettlementItem(Base):
    __tablename__ = "settlement_items"

    id = Column(Integer, primary_key=True)
    settlement_id = Column(Integer, ForeignKey("settlements.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    distribution_key = Column(String(100), nullable=True)
    cost_building = Column(Float, default=0.0)
    cost_unit = Column(Float, default=0.0)
    paid = Column(Float, default=0.0)
    result = Column(Float, default=0.0)

    settlement = relationship("Settlement", back_populates="items")
