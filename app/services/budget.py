from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from typing import List, Optional
from app.models.trip import Trip
from app.models.expense import Expense
from app.models.category import Category
from app.schemas.report import (
    BudgetStatus, CategorySummary, DaySummary, CitySummary, TripSummaryResponse
)

class BudgetService:
    @classmethod
    def calculate_budget_status(cls, trip: Trip, db: Session, as_of_date: Optional[date] = None) -> BudgetStatus:
        current_date = as_of_date or date.today()

        # Total spent in home currency
        total_spent_query = db.query(func.coalesce(func.sum(Expense.amount_home), 0.0)).filter(
            Expense.trip_id == trip.id
        ).scalar()
        total_spent = round(float(total_spent_query), 2)
        total_budget = round(float(trip.total_budget), 2)
        remaining = round(total_budget - total_spent, 2)
        percentage_used = round((total_spent / total_budget * 100), 1) if total_budget > 0 else 0.0

        # Trip duration calculations
        trip_start = trip.start_date
        trip_end = trip.end_date
        trip_days_total = max(1, (trip_end - trip_start).days + 1)

        if current_date < trip_start:
            days_elapsed = 0
            days_remaining = trip_days_total
        elif current_date > trip_end:
            days_elapsed = trip_days_total
            days_remaining = 0
        else:
            days_elapsed = max(1, (current_date - trip_start).days + 1)
            days_remaining = max(0, (trip_end - current_date).days)

        # Burn rate and targets
        calc_days_for_avg = max(1, days_elapsed)
        daily_avg = round(total_spent / calc_days_for_avg, 2)

        target_daily = round(remaining / max(1, days_remaining), 2) if remaining > 0 and days_remaining > 0 else 0.0

        # Projected spend
        projected_total = round(daily_avg * trip_days_total, 2) if days_elapsed > 0 else 0.0
        projected_overspend = round(max(0.0, projected_total - total_budget), 2)

        is_over = total_spent > total_budget
        is_projected_over = projected_total > total_budget and not is_over

        warning_message = None
        if is_over:
            over_by = round(total_spent - total_budget, 2)
            warning_message = f"CRITICAL: Budget exceeded by {trip.home_currency} {over_by:,.2f}!"
        elif is_projected_over:
            warning_message = (
                f"WARNING: Current burn rate is {trip.home_currency} {daily_avg:.2f}/day. "
                f"At this pace, you will overspend by ~{trip.home_currency} {projected_overspend:.2f}."
            )
        elif days_remaining > 0 and remaining > 0:
            warning_message = (
                f"On track: You have {trip.home_currency} {remaining:,.2f} remaining "
                f"({trip.home_currency} {target_daily:.2f}/day for {days_remaining} remaining days)."
            )

        return BudgetStatus(
            total_budget=total_budget,
            total_spent_home=total_spent,
            remaining_budget=remaining,
            percentage_used=percentage_used,
            home_currency=trip.home_currency,
            trip_days_total=trip_days_total,
            days_elapsed=days_elapsed,
            days_remaining=days_remaining,
            daily_average_spent=daily_avg,
            target_daily_budget=target_daily,
            projected_total_spent=projected_total,
            projected_overspend=projected_overspend,
            is_over_budget=is_over,
            is_projected_over_budget=is_projected_over,
            warning_message=warning_message
        )

    @classmethod
    def get_summary_by_category(cls, trip_id: int, db: Session) -> List[CategorySummary]:
        results = db.query(
            Category.name,
            Category.icon,
            func.coalesce(func.sum(Expense.amount_home), 0.0).label("total"),
            func.count(Expense.id).label("count")
        ).join(Expense, Expense.category_id == Category.id)\
         .filter(Expense.trip_id == trip_id)\
         .group_by(Category.name, Category.icon)\
         .order_by(func.sum(Expense.amount_home).desc())\
         .all()

        total_sum = sum(float(r.total) for r in results) or 1.0

        summaries = []
        for name, icon, total, count in results:
            tot = round(float(total), 2)
            summaries.append(CategorySummary(
                category=name,
                icon=icon,
                total_amount_home=tot,
                percentage_of_total=round((tot / total_sum) * 100, 1),
                count=count
            ))
        return summaries

    @classmethod
    def get_summary_by_day(cls, trip_id: int, db: Session) -> List[DaySummary]:
        results = db.query(
            Expense.date,
            func.coalesce(func.sum(Expense.amount_home), 0.0).label("total"),
            func.count(Expense.id).label("count")
        ).filter(Expense.trip_id == trip_id)\
         .group_by(Expense.date)\
         .order_by(Expense.date.asc())\
         .all()

        return [
            DaySummary(
                date=r.date.strftime("%Y-%m-%d"),
                total_amount_home=round(float(r.total), 2),
                count=r.count
            )
            for r in results
        ]

    @classmethod
    def get_summary_by_city(cls, trip_id: int, db: Session) -> List[CitySummary]:
        results = db.query(
            func.coalesce(Expense.city, "Unknown").label("city"),
            func.coalesce(func.sum(Expense.amount_home), 0.0).label("total"),
            func.count(Expense.id).label("count")
        ).filter(Expense.trip_id == trip_id)\
         .group_by(Expense.city)\
         .order_by(func.sum(Expense.amount_home).desc())\
         .all()

        return [
            CitySummary(
                city=r.city,
                total_amount_home=round(float(r.total), 2),
                count=r.count
            )
            for r in results
        ]

    @classmethod
    def get_trip_summary(cls, trip: Trip, db: Session) -> TripSummaryResponse:
        budget_status = cls.calculate_budget_status(trip, db)
        by_category = cls.get_summary_by_category(trip.id, db)
        by_day = cls.get_summary_by_day(trip.id, db)
        by_city = cls.get_summary_by_city(trip.id, db)

        return TripSummaryResponse(
            trip_id=trip.id,
            trip_name=trip.name,
            budget_status=budget_status,
            by_category=by_category,
            by_day=by_day,
            by_city=by_city
        )
