import os
import shutil
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models.trip import Trip
from app.agent.runner import AgentRunner
from app.services.receipt_parser import ReceiptParserService

router = APIRouter(prefix="/api/receipts", tags=["Receipts"])

@router.post("/parse")
async def parse_receipt_file(
    file: UploadFile = File(...),
    trip_id: int = Form(None),
    auto_save: bool = Form(False),
    db: Session = Depends(get_db)
):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Save uploaded file safely
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    safe_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    active_trip = None
    if trip_id:
        active_trip = db.query(Trip).filter(Trip.id == trip_id).first()
    else:
        active_trip = db.query(Trip).order_by(Trip.id.desc()).first()

    # Call agent tool parse_receipt
    result = AgentRunner.execute_tool("parse_receipt", {
        "receipt_id": file_path,
        "trip_id": active_trip.id if active_trip else None,
        "auto_save": auto_save
    }, db, active_trip)

    return {
        "file_path": file_path,
        "filename": file.filename,
        "result": result
    }
