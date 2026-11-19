from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from app.database import get_db
from app.models.trip import Trip
from app.models.expense import Expense, ExpenseItem
from app.models.category import Category
from app.schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseRead
from app.services.currency import CurrencyService
from app.services.categorization import CategorizationService
from app.services.sms_parser import SmsParserService
from app.services.anomaly_detector import AnomalyDetectorService
from pydantic import BaseModel

router = APIRouter(prefix="/api/expenses", tags=["Expenses"])

def _format_expense(exp: Expense) -> dict:
    return {
        "id": exp.id,
        "trip_id": exp.trip_id,
        "category_id": exp.category_id,
        "category_name": exp.category.name if exp.category else "other",
        "category_icon": exp.category.icon if exp.category else "📦",
        "paid_by_id": exp.paid_by_id,
        "paid_by_name": exp.paid_by_name,
        "split_with": exp.split_with,
        "payment_mode": exp.payment_mode or "Cash",
        "reference_id": exp.reference_id,
        "is_anomaly": bool(exp.is_anomaly),
        "anomaly_reason": exp.anomaly_reason,
        "date": exp.date,
        "amount": float(exp.amount),
        "currency": exp.currency,
        "exchange_rate": float(exp.exchange_rate),
        "amount_home": float(exp.amount_home),
        "home_currency": exp.trip.home_currency if exp.trip else "USD",
        "merchant": exp.merchant,
        "description": exp.description,
        "city": exp.city,
        "split_notes": exp.split_notes,
        "receipt_path": exp.receipt_path,
        "raw_input": exp.raw_input,
        "created_at": exp.created_at,
        "updated_at": exp.updated_at,
        "items": exp.items
    }

@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(expense_in: ExpenseCreate, db: Session = Depends(get_db)):
    # Resolve trip
    trip_id = expense_in.trip_id
    if not trip_id:
        active = db.query(Trip).order_by(Trip.id.desc()).first()
        if not active:
            raise HTTPException(status_code=400, detail="No trips exist. Please create a trip first.")
        trip_id = active.id

    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Resolve category
    category = None
    if expense_in.category:
        category = CategorizationService.get_category_by_name(db, expense_in.category)
    if not category:
        category = CategorizationService.classify(db, expense_in.description, expense_in.merchant)

    # Convert currency
    amount_home, rate = CurrencyService.convert(
        amount=expense_in.amount,
        from_currency=expense_in.currency,
        to_currency=trip.home_currency,
        rate_date=expense_in.date,
        db=db
    )

    expense = Expense(
        trip_id=trip.id,
        category_id=category.id,
        date=expense_in.date,
        amount=expense_in.amount,
        currency=expense_in.currency.upper(),
        exchange_rate=rate,
        amount_home=amount_home,
        merchant=expense_in.merchant,
        description=expense_in.description,
        city=expense_in.city,
        split_notes=expense_in.split_notes,
        receipt_path=expense_in.receipt_path,
        raw_input=expense_in.raw_input
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)

    # Optional line items
    if expense_in.items:
        for item_data in expense_in.items:
            item = ExpenseItem(
                expense_id=expense.id,
                name=item_data.name,
                quantity=item_data.quantity,
                unit_price=item_data.unit_price,
                total_price=item_data.total_price
            )
            db.add(item)
        db.commit()
        db.refresh(expense)

    return _format_expense(expense)

@router.get("", response_model=List[ExpenseRead])
def list_expenses(
    trip_id: Optional[int] = None,
    category: Optional[str] = None,
    city: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    query = db.query(Expense)
    if trip_id:
        query = query.filter(Expense.trip_id == trip_id)
    if category:
        cat = CategorizationService.get_category_by_name(db, category)
        if cat:
            query = query.filter(Expense.category_id == cat.id)
    if city:
        query = query.filter(Expense.city.ilike(f"%{city.strip()}%"))
    if start_date:
        query = query.filter(Expense.date >= start_date)
    if end_date:
        query = query.filter(Expense.date <= end_date)

    expenses = query.order_by(Expense.date.desc(), Expense.id.desc()).limit(limit).all()
    return [_format_expense(e) for e in expenses]

@router.get("/{expense_id}", response_model=ExpenseRead)
def get_expense(expense_id: int, db: Session = Depends(get_db)):
    exp = db.query(Expense).filter(Expense.id == expense_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    return _format_expense(exp)

@router.put("/{expense_id}", response_model=ExpenseRead)
def update_expense(expense_id: int, exp_in: ExpenseUpdate, db: Session = Depends(get_db)):
    exp = db.query(Expense).filter(Expense.id == expense_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")

    recalculate = False
    if exp_in.amount is not None:
        exp.amount = exp_in.amount
        recalculate = True
    if exp_in.currency is not None:
        exp.currency = exp_in.currency.upper().strip()
        recalculate = True
    if exp_in.date is not None:
        exp.date = exp_in.date
        recalculate = True
    if exp_in.description is not None:
        exp.description = exp_in.description
    if exp_in.merchant is not None:
        exp.merchant = exp_in.merchant
    if exp_in.city is not None:
        exp.city = exp_in.city
    if exp_in.split_notes is not None:
        exp.split_notes = exp_in.split_notes

    if exp_in.category is not None:
        cat = CategorizationService.get_category_by_name(db, exp_in.category)
        if cat:
            exp.category_id = cat.id
            if exp_in.learn_category_rule:
                pattern = exp.merchant or exp.description
                CategorizationService.learn_rule(db, pattern, cat.name)

    if recalculate:
        converted, rate = CurrencyService.convert(
            amount=float(exp.amount),
            from_currency=exp.currency,
            to_currency=exp.trip.home_currency,
            rate_date=exp.date,
            db=db
        )
        exp.amount_home = converted
        exp.exchange_rate = rate

    db.commit()
    db.refresh(exp)
    return _format_expense(exp)

@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    exp = db.query(Expense).filter(Expense.id == expense_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(exp)
    db.commit()
    return None

class SmsParseRequest(BaseModel):
    sms_text: str
    trip_id: Optional[int] = None
    auto_save: Optional[bool] = True

@router.post("/parse-sms")
def parse_and_log_sms(req: SmsParseRequest, db: Session = Depends(get_db)):
    """Parse payment notification or UPI SMS and optionally log it immediately."""
    trip_id = req.trip_id
    if not trip_id:
        active = db.query(Trip).order_by(Trip.id.desc()).first()
        if not active:
            raise HTTPException(status_code=400, detail="No active trips found.")
        trip = active
    else:
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found.")

    parsed = SmsParserService.parse_sms(req.sms_text, default_currency=trip.home_currency, db=db)
    if not parsed.get("success") or not parsed.get("amount"):
        return {"success": False, "error": "Could not identify amount or merchant from SMS.", "parsed": parsed}

    if not req.auto_save:
        return {"success": True, "parsed": parsed}

    # Save to expenses
    cat = CategorizationService.get_category_by_name(db, parsed.get("category", "other"))
    if not cat:
        cat = CategorizationService.classify(db, parsed["description"], parsed["merchant"])

    amount = float(parsed["amount"])
    curr = parsed["currency"]
    d_val = date.fromisoformat(parsed["date"])

    converted, rate = CurrencyService.convert(amount, curr, trip.home_currency, d_val, db)

    expense = Expense(
        trip_id=trip.id,
        category_id=cat.id,
        date=d_val,
        amount=amount,
        currency=curr,
        exchange_rate=rate,
        amount_home=converted,
        merchant=parsed.get("merchant"),
        description=parsed.get("description"),
        payment_mode=parsed.get("payment_mode", "UPI"),
        reference_id=parsed.get("reference_id"),
        raw_input=f"SMS: {req.sms_text[:100]}"
    )
    db.add(expense)
    db.flush()

    is_anomaly, reason = AnomalyDetectorService.check_anomaly(expense, db)
    if is_anomaly:
        expense.is_anomaly = True
        expense.anomaly_reason = reason

    db.commit()
    db.refresh(expense)

    return {
        "success": True,
        "expense": _format_expense(expense),
        "parsed": parsed
    }

@router.get("/anomalies/{trip_id}")
def get_trip_anomalies(trip_id: int, db: Session = Depends(get_db)):
    """Fetch all flagged anomalies, duplicate swipes, and surges for a trip."""
    expenses = db.query(Expense).filter(Expense.trip_id == trip_id, Expense.is_anomaly == True).all()
    return {
        "trip_id": trip_id,
        "count": len(expenses),
        "anomalies": [_format_expense(e) for e in expenses]
    }
