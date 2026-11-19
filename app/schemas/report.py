from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import date

class CategorySummary(BaseModel):
    category: str
    icon: Optional[str] = None
    total_amount_home: float
    percentage_of_total: float
    count: int

class DaySummary(BaseModel):
    date: str
    total_amount_home: float
    count: int

class CitySummary(BaseModel):
    city: str
    total_amount_home: float
    count: int

class BudgetStatus(BaseModel):
    total_budget: float
    total_spent_home: float
    remaining_budget: float
    percentage_used: float
    home_currency: str
    trip_days_total: int
    days_elapsed: int
    days_remaining: int
    daily_average_spent: float
    target_daily_budget: float
    projected_total_spent: float
    projected_overspend: float
    is_over_budget: bool
    is_projected_over_budget: bool
    warning_message: Optional[str] = None

class TripSummaryResponse(BaseModel):
    trip_id: int
    trip_name: str
    budget_status: BudgetStatus
    by_category: List[CategorySummary] = []
    by_day: List[DaySummary] = []
    by_city: List[CitySummary] = []
