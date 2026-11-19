from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    icon = Column(String(10), nullable=True)
    description = Column(Text, nullable=True)

    rules = relationship("CategoryRule", back_populates="category", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="category")

class CategoryRule(Base):
    __tablename__ = "category_rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pattern = Column(String(100), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    user_corrected = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    category = relationship("Category", back_populates="rules")
