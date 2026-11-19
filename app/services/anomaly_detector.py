from typing import Tuple, Optional
from sqlalchemy.orm import Session
from app.models.expense import Expense
from app.models.trip import Trip

class AnomalyDetectorService:
    """
    Real-time fraud, duplicate swipe, and spending spike anomaly detection.
    """

    @classmethod
    def check_anomaly(cls, expense: Expense, db: Session) -> Tuple[bool, Optional[str]]:
        """
        Evaluates an expense against historical trip data to detect:
        1. Duplicate swipes / accidental double entries
        2. Unusually high spending spikes compared to category baseline
        3. Severe budget drain risk
        Returns (is_anomaly, reason_description)
        """
        trip_id = expense.trip_id
        if not trip_id:
            return False, None

        # 1. Duplicate Swipes Check
        # Same trip, same date, amount within 2%, same category or merchant
        existing_expenses = db.query(Expense).filter(
            Expense.trip_id == trip_id,
            Expense.date == expense.date
        ).all()

        current_amount = float(expense.amount)
        for existing in existing_expenses:
            # Skip comparing with self if already persisted
            if existing.id and expense.id and existing.id == expense.id:
                continue

            ex_amount = float(existing.amount)
            # Check if amount is identical or within 1%
            if ex_amount > 0 and abs(current_amount - ex_amount) / ex_amount < 0.02:
                # Check matching merchant or category
                same_merchant = (
                    expense.merchant and existing.merchant and 
                    expense.merchant.strip().lower() == existing.merchant.strip().lower()
                )
                same_cat = existing.category_id == expense.category_id
                if same_merchant or same_cat:
                    return True, f"Possible duplicate: Similar to Expense #{existing.id} ({existing.currency} {ex_amount:,.2f} logged on {existing.date})"

        # 2. Category Spending Spike
        cat_expenses = db.query(Expense).filter(
            Expense.trip_id == trip_id,
            Expense.category_id == expense.category_id
        ).all()

        cat_costs = [float(e.amount_home) for e in cat_expenses if e.id != expense.id]
        if len(cat_costs) >= 2:
            avg_cat_cost = sum(cat_costs) / len(cat_costs)
            curr_home = float(expense.amount_home) if expense.amount_home else current_amount
            if avg_cat_cost > 0 and curr_home >= (2.5 * avg_cat_cost) and curr_home > 800:
                ratio = curr_home / avg_cat_cost
                cat_name = expense.category.name if expense.category else "this category"
                return True, f"Spending surge: {ratio:.1f}x higher than your average {cat_name} spend"

        # 3. Severe Budget Drain
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if trip and trip.total_budget:
            budget = float(trip.total_budget)
            curr_home = float(expense.amount_home) if expense.amount_home else current_amount
            if budget > 0 and (curr_home / budget) >= 0.35:
                pct = (curr_home / budget) * 100
                return True, f"Severe budget impact: Consumes {pct:.0f}% of your total trip budget"

        return False, None
