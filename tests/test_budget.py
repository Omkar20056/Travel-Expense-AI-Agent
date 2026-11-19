from datetime import date
from app.models.trip import Trip
from app.models.expense import Expense
from app.services.budget import BudgetService

def test_budget_burn_rate_and_warning(db_session):
    trip = db_session.query(Trip).first()
    # Trip budget is $2000.00
    # Add an expense that exceeds the budget
    exp = Expense(
        trip_id=trip.id,
        category_id=1,
        date=date.today(),
        amount=2500.0,
        currency="USD",
        exchange_rate=1.0,
        amount_home=2500.0,
        description="Luxury Hotel",
        city="Paris"
    )
    db_session.add(exp)
    db_session.commit()

    status = BudgetService.calculate_budget_status(trip, db_session)
    assert status.is_over_budget is True
    assert status.total_spent_home == 2500.0
    assert "exceeded" in status.warning_message.lower()
