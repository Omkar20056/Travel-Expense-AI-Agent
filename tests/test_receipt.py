import os
import tempfile
from app.services.receipt_parser import ReceiptParserService
from app.agent.runner import AgentRunner
from app.models.trip import Trip
from app.models.expense import Expense

def test_mock_receipt_parsing():
    # Create temporary dummy image file
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(b"fake image data")
        tmp_path = tmp.name

    try:
        parsed = ReceiptParserService.parse_receipt(tmp_path)
        assert parsed is not None
        assert "amount" in parsed
        assert "currency" in parsed
        assert "merchant" in parsed
        assert parsed["amount"] > 0
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def test_agent_parse_receipt_tool(db_session):
    trip = db_session.query(Trip).first()

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(b"dummy image bytes")
        tmp_path = tmp.name

    try:
        result = AgentRunner.execute_tool("parse_receipt", {
            "receipt_id": tmp_path,
            "trip_id": trip.id,
            "auto_save": True
        }, db_session, trip)

        assert "parsed" in result
        assert "saved_expense" in result
        assert result["saved_expense"]["success"] is True

        # Check DB
        expense = db_session.query(Expense).first()
        assert expense is not None
        assert float(expense.amount) > 0
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
