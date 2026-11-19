import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app.database import get_db
from app.models.trip import Trip, Traveler
from app.schemas.trip import TripCreate, TripUpdate, TripRead, TravelerCreate
from app.services.settlement import SettlementService

router = APIRouter(prefix="/api/trips", tags=["Trips"])

def _format_trip(trip: Trip) -> dict:
    dest_list = []
    if trip.destinations:
        try:
            dest_list = json.loads(trip.destinations)
        except Exception:
            dest_list = [d.strip() for d in trip.destinations.split(",") if d.strip()]

    return {
        "id": trip.id,
        "name": trip.name,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "destinations": dest_list,
        "total_budget": float(trip.total_budget),
        "home_currency": trip.home_currency,
        "created_at": trip.created_at,
        "updated_at": trip.updated_at,
        "travelers": trip.travelers
    }

@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED)
def create_trip(trip_in: TripCreate, db: Session = Depends(get_db)):
    dest_json = json.dumps(trip_in.destinations)
    trip = Trip(
        name=trip_in.name,
        start_date=trip_in.start_date,
        end_date=trip_in.end_date,
        destinations=dest_json,
        total_budget=trip_in.total_budget,
        home_currency=trip_in.home_currency.upper()
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)

    # Add primary traveler
    traveler = Traveler(
        trip_id=trip.id,
        name=trip_in.primary_traveler_name or "Me",
        is_primary=True
    )
    db.add(traveler)
    db.commit()
    db.refresh(trip)

    return _format_trip(trip)

@router.get("", response_model=List[TripRead])
def list_trips(db: Session = Depends(get_db)):
    trips = db.query(Trip).order_by(Trip.start_date.desc()).all()
    return [_format_trip(t) for t in trips]

@router.get("/active", response_model=TripRead)
def get_active_trip(db: Session = Depends(get_db)):
    # Look for trip currently in progress or most recently created
    today = datetime.utcnow().date()
    trip = db.query(Trip).filter(Trip.start_date <= today, Trip.end_date >= today).first()
    if not trip:
        trip = db.query(Trip).order_by(Trip.id.desc()).first()

    if not trip:
        raise HTTPException(status_code=404, detail="No trips found. Please create a trip first.")
    return _format_trip(trip)

@router.get("/{trip_id}", response_model=TripRead)
def get_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return _format_trip(trip)

@router.put("/{trip_id}", response_model=TripRead)
def update_trip(trip_id: int, trip_in: TripUpdate, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if trip_in.name is not None:
        trip.name = trip_in.name
    if trip_in.start_date is not None:
        trip.start_date = trip_in.start_date
    if trip_in.end_date is not None:
        trip.end_date = trip_in.end_date
    if trip_in.destinations is not None:
        trip.destinations = json.dumps(trip_in.destinations)
    if trip_in.total_budget is not None:
        trip.total_budget = trip_in.total_budget
    if trip_in.home_currency is not None:
        trip.home_currency = trip_in.home_currency.upper()

    db.commit()
    db.refresh(trip)
    return _format_trip(trip)

@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    db.delete(trip)
    db.commit()
    return None

@router.get("/{trip_id}/settlements")
def get_trip_settlements(trip_id: int, db: Session = Depends(get_db)):
    """Calculate multi-person group settlements and minimal debt settlement transfers."""
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return SettlementService.calculate_settlements(db, trip_id)
