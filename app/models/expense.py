from sqlalchemy import Column, Integer, String, Date, Numeric, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, index=True)
    paid_by_id = Column(Integer, ForeignKey("travelers.id", ondelete="SET NULL"), nullable=True)
    paid_by_name = Column(String(100), nullable=True)
    split_with = Column(Text, nullable=True)  # JSON list string: '["Me", "Rahul", "Priya"]'
    payment_mode = Column(String(50), nullable=True, default="Cash")  # UPI, Card, NetBanking, Cash
    reference_id = Column(String(100), nullable=True)  # UPI Ref / Card Txn ID
    is_anomaly = Column(Boolean, default=False)
    anomaly_reason = Column(String(255), nullable=True)
    date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    exchange_rate = Column(Numeric(14, 6), nullable=False)
    amount_home = Column(Numeric(12, 2), nullable=False)
    merchant = Column(String(100), nullable=True)
    description = Column(Text, nullable=False)
    city = Column(String(100), nullable=True, index=True)
    split_notes = Column(Text, nullable=True)
    receipt_path = Column(String(255), nullable=True)
    raw_input = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    trip = relationship("Trip", back_populates="expenses")
    category = relationship("Category", back_populates="expenses")
    items = relationship("ExpenseItem", back_populates="expense", cascade="all, delete-orphan")

class ExpenseItem(Base):
    __tablename__ = "expense_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(12, 2), nullable=True)
    total_price = Column(Numeric(12, 2), nullable=False)

    expense = relationship("Expense", back_populates="items")
