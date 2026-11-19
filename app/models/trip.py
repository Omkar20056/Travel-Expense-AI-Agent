from sqlalchemy import Column, Integer, String, Date, Numeric, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    destinations = Column(Text, nullable=False)  # JSON array string: '["Rome", "Paris"]'
    total_budget = Column(Numeric(12, 2), nullable=False)
    home_currency = Column(String(3), nullable=False, default="USD")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    travelers = relationship("Traveler", back_populates="trip", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="trip", cascade="all, delete-orphan")

class Traveler(Base):
    __tablename__ = "travelers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    trip = relationship("Trip", back_populates="travelers")
