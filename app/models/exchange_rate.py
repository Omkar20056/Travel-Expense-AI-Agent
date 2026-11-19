from sqlalchemy import Column, Integer, String, Date, Numeric, DateTime, UniqueConstraint
from datetime import datetime, timezone
from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    base_currency = Column(String(3), nullable=False)
    target_currency = Column(String(3), nullable=False)
    rate = Column(Numeric(14, 6), nullable=False)
    fetched_at = Column(DateTime, default=utc_now)

    __table_args__ = (
        UniqueConstraint("date", "base_currency", "target_currency", name="uq_fx_date_base_target"),
    )
