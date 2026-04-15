import enum
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils import utcnow


class MeterType(str, enum.Enum):
    COLD = "cold"    # SV — studená voda
    HOT = "hot"      # TV — teplá voda


class WaterMeter(Base):
    __tablename__ = "water_meters"

    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True, index=True)
    unit_number = Column(Integer, index=True)
    unit_letter = Column(String(5), default="")
    meter_serial = Column(String(50), index=True)
    meter_type = Column(Enum(MeterType), index=True)
    location = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    unit = relationship("Unit", back_populates="water_meters")
    readings = relationship("WaterReading", back_populates="meter", cascade="all, delete-orphan")


class WaterReading(Base):
    __tablename__ = "water_readings"

    id = Column(Integer, primary_key=True)
    meter_id = Column(Integer, ForeignKey("water_meters.id"), nullable=False, index=True)
    reading_date = Column(Date, index=True)
    value = Column(Float)
    import_batch = Column(String(50), index=True)
    created_at = Column(DateTime, default=utcnow)

    meter = relationship("WaterMeter", back_populates="readings")
