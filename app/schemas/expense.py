from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime
from typing import List, Optional

class ExpenseItemBase(BaseModel):
    name: str
    quantity: int = 1
    unit_price: Optional[float] = None
    total_price: float

class ExpenseItemCreate(ExpenseItemBase):
    pass

class ExpenseItemRead(ExpenseItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    expense_id: int

class ExpenseBase(BaseModel):
    trip_id: Optional[int] = None
    date: date
    amount: float = Field(gt=0, description="Amount in original currency")
    currency: str = Field(min_length=3, max_length=3, description="3-letter currency code")
    description: str
    category: Optional[str] = "other"
    merchant: Optional[str] = None
    city: Optional[str] = None
    paid_by_name: Optional[str] = None
    split_with: Optional[str] = None
    payment_mode: Optional[str] = "Cash"
    reference_id: Optional[str] = None
    is_anomaly: Optional[bool] = False
    anomaly_reason: Optional[str] = None
    split_notes: Optional[str] = None
    receipt_path: Optional[str] = None
    raw_input: Optional[str] = None

class ExpenseCreate(ExpenseBase):
    items: Optional[List[ExpenseItemCreate]] = None

class ExpenseUpdate(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    merchant: Optional[str] = None
    city: Optional[str] = None
    date: Optional[date] = None
    paid_by_name: Optional[str] = None
    split_with: Optional[str] = None
    payment_mode: Optional[str] = None
    reference_id: Optional[str] = None
    split_notes: Optional[str] = None
    learn_category_rule: Optional[bool] = False

class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    category_id: int
    category_name: str
    category_icon: Optional[str] = None
    paid_by_id: Optional[int] = None
    paid_by_name: Optional[str] = None
    split_with: Optional[str] = None
    payment_mode: Optional[str] = "Cash"
    reference_id: Optional[str] = None
    is_anomaly: Optional[bool] = False
    anomaly_reason: Optional[str] = None
    date: date
    amount: float
    currency: str
    exchange_rate: float
    amount_home: float
    home_currency: str
    merchant: Optional[str] = None
    description: str
    city: Optional[str] = None
    split_notes: Optional[str] = None
    receipt_path: Optional[str] = None
    raw_input: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[ExpenseItemRead] = []
