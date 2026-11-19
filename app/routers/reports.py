import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.trip import Trip
from app.models.expense import Expense
from app.schemas.report import TripSummaryResponse
from app.services.budget import BudgetService

router = APIRouter(prefix="/api/reports", tags=["Reports & Analytics"])

@router.get("/summary", response_model=TripSummaryResponse)
def get_trip_report(trip_id: int = Query(None), db: Session = Depends(get_db)):
    if trip_id:
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
    else:
        trip = db.query(Trip).order_by(Trip.id.desc()).first()

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    return BudgetService.get_trip_summary(trip, db)

@router.get("/export")
def export_trip_expenses_csv(trip_id: int = Query(None), db: Session = Depends(get_db)):
    if trip_id:
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
    else:
        trip = db.query(Trip).order_by(Trip.id.desc()).first()

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    expenses = db.query(Expense).filter(Expense.trip_id == trip.id).order_by(Expense.date.asc()).all()

    # Generate CSV in-memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Expense ID", "Date", "Description", "Merchant", "Category", "City",
        "Original Amount", "Currency", "Exchange Rate",
        f"Amount ({trip.home_currency})", "Split Notes"
    ])

    for exp in expenses:
        writer.writerow([
            exp.id,
            exp.date.strftime("%Y-%m-%d"),
            exp.description,
            exp.merchant or "",
            exp.category.name if exp.category else "other",
            exp.city or "",
            f"{float(exp.amount):.2f}",
            exp.currency,
            f"{float(exp.exchange_rate):.6f}",
            f"{float(exp.amount_home):.2f}",
            exp.split_notes or ""
        ])

    output.seek(0)
    filename = f"trip_{trip.id}_{trip.name.replace(' ', '_')}_expenses.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
