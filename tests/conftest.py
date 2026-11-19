import pytest
import json
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.trip import Trip, Traveler
from app.services.categorization import CategorizationService

@pytest.fixture
def db_session():
    # Use SQLite in-memory database for isolated tests
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # Seed default categories
    CategorizationService.seed_categories(db)

    # Seed a standard test trip
    today = date.today()
    trip = Trip(
        name="Test Trip to Europe",
        start_date=today - timedelta(days=2),
        end_date=today + timedelta(days=8),
        destinations=json.dumps(["Rome", "Paris"]),
        total_budget=2000.0,
        home_currency="USD"
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)

    traveler = Traveler(trip_id=trip.id, name="Tester", is_primary=True)
    db.add(traveler)
    db.commit()

    yield db

    db.close()
