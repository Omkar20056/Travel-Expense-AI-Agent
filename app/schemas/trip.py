from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime
from typing import List, Optional

class TravelerBase(BaseModel):
    name: str
    email: Optional[str] = None
    is_primary: bool = False

class TravelerCreate(TravelerBase):
    pass

class TravelerRead(TravelerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    created_at: datetime

class TripBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    destinations: List[str] = Field(default_factory=list)
    total_budget: float
    home_currency: str = "USD"

class TripCreate(TripBase):
    primary_traveler_name: Optional[str] = "Me"

class TripUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    destinations: Optional[List[str]] = None
    total_budget: Optional[float] = None
    home_currency: Optional[str] = None

class TripRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_date: date
    end_date: date
    destinations: List[str]
    total_budget: float
    home_currency: str
    created_at: datetime
    updated_at: datetime
    travelers: List[TravelerRead] = []
