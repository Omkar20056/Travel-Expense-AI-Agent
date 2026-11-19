from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models.trip import Trip
from app.schemas.chat import ChatRequest, ChatResponse
from app.agent.runner import AgentRunner

router = APIRouter(prefix="/api/chat", tags=["Agent Chat"])

@router.post("", response_model=ChatResponse)
def chat_with_agent(chat_in: ChatRequest, db: Session = Depends(get_db)):
    # Find active trip
    trip = None
    if chat_in.trip_id:
        trip = db.query(Trip).filter(Trip.id == chat_in.trip_id).first()
    else:
        today = datetime.utcnow().date()
        trip = db.query(Trip).filter(Trip.start_date <= today, Trip.end_date >= today).first()
        if not trip:
            trip = db.query(Trip).order_by(Trip.id.desc()).first()

    response = AgentRunner.run_turn(
        user_message=chat_in.message,
        history=chat_in.history or [],
        db=db,
        active_trip=trip
    )
    return response
