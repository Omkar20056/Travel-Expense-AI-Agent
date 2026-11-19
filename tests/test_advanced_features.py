import pytest
from datetime import date
from app.models.trip import Trip
from app.models.expense import Expense
from app.models.category import Category
from app.services.sms_parser import SmsParserService
from app.services.settlement import SettlementService
from app.services.anomaly_detector import AnomalyDetectorService
from app.agent.runner import AgentRunner

def test_sms_parser_upi_and_cards():
    # 1. Kotak Bank UPI
    sms1 = "Sent Rs.450.00 from Kotak Bank AC X1234 to STARBUCKS via UPI Ref 412345678901 on 18-11-26"
    p1 = SmsParserService._deterministic_parse(sms1, default_currency="INR")
    assert p1["success"] is True
    assert p1["amount"] == 450.0
    assert p1["currency"] == "INR"
    assert "STARBUCKS" in p1["merchant"]
    assert p1["payment_mode"] == "UPI"
    assert p1["reference_id"] == "412345678901"
    assert p1["category"] == "food"

    # 2. Credit Card swipe alert
    sms2 = "Alert: USD 42.50 spent on your Credit Card ending 9876 at UBER TRIP on 18/11/2026."
    p2 = SmsParserService._deterministic_parse(sms2, default_currency="USD")
    assert p2["success"] is True
    assert p2["amount"] == 42.5
    assert p2["currency"] == "USD"
    assert "UBER" in p2["merchant"]
    assert p2["payment_mode"] == "Credit Card"
    assert p2["category"] == "transport"

    # 3. PhonePe Zomato
    sms3 = "Paid Rs 1,250 to SWIGGY via PhonePe UPI txn ID P123456789"
    p3 = SmsParserService._deterministic_parse(sms3, default_currency="INR")
    assert p3["amount"] == 1250.0
    assert p3["merchant"] == "SWIGGY"
    assert p3["payment_mode"] == "UPI"

def test_group_settlement_minimum_cash_flow(db_session):
    trip = db_session.query(Trip).first()
    cat = db_session.query(Category).first()

    # Exp 1: Alice paid 3000, split with Bob and Charlie (equal split: 1000 each)
    exp1 = Expense(
        trip_id=trip.id,
        category_id=cat.id,
        date=date.today(),
        amount=3000,
        currency="INR",
        exchange_rate=1.0,
        amount_home=3000,
        description="Dinner at Royal Dine",
        paid_by_name="Alice",
        split_with='["Alice", "Bob", "Charlie"]'
    )
    # Exp 2: Bob paid 600 for taxi for Bob and Alice (300 each)
    exp2 = Expense(
        trip_id=trip.id,
        category_id=cat.id,
        date=date.today(),
        amount=600,
        currency="INR",
        exchange_rate=1.0,
        amount_home=600,
        description="Taxi ride",
        paid_by_name="Bob",
        split_with='["Bob", "Alice"]'
    )
    db_session.add_all([exp1, exp2])
    db_session.commit()

    res = SettlementService.calculate_settlements(db_session, trip.id)
    assert res["trip_id"] == trip.id
    balances = res["net_balances"]

    # Alice paid 3000, share is 1000 + 300 = 1300 -> net +1700
    assert balances["Alice"] == 1700.0
    # Bob paid 600, share is 1000 + 300 = 1300 -> net -700
    assert balances["Bob"] == -700.0
    # Charlie paid 0, share is 1000 -> net -1000
    assert balances["Charlie"] == -1000.0

    # Total balances must sum to exactly 0 (Zero-Sum invariant)
    assert round(sum(balances.values()), 2) == 0.0

    # Simplified transfers: Charlie pays Alice 1000, Bob pays Alice 700 (2 transfers instead of multiple)
    debts = res["simplified_debts"]
    assert len(debts) == 2
    from_persons = {d["from_person"] for d in debts}
    assert "Bob" in from_persons
    assert "Charlie" in from_persons

    # Check WhatsApp message formatting
    assert "Group Expense Settlements" in res["whatsapp_message"]
    assert "Alice" in res["whatsapp_message"]

def test_anomaly_detector_duplicate_and_spike(db_session):
    trip = db_session.query(Trip).first()
    cat = db_session.query(Category).filter(Category.name == "food").first()

    # Log first expense
    exp1 = Expense(
        trip_id=trip.id,
        category_id=cat.id,
        date=date.today(),
        amount=450,
        currency="INR",
        exchange_rate=1.0,
        amount_home=450,
        description="Cafe Coffee Day",
        merchant="Cafe Coffee Day"
    )
    db_session.add(exp1)
    db_session.commit()

    # Log duplicate candidate (same date, same merchant, amount 450)
    exp2 = Expense(
        trip_id=trip.id,
        category_id=cat.id,
        date=date.today(),
        amount=450,
        currency="INR",
        exchange_rate=1.0,
        amount_home=450,
        description="Cafe Coffee Day",
        merchant="Cafe Coffee Day"
    )
    is_anomaly, reason = AnomalyDetectorService.check_anomaly(exp2, db_session)
    assert is_anomaly is True
    assert "duplicate" in reason.lower()

def test_agent_runner_sms_and_settlement_queries(db_session):
    trip = db_session.query(Trip).first()

    # Test auto-routing SMS
    sms = "Sent Rs.320.00 to SWIGGY via UPI Ref 987654321098"
    resp = AgentRunner.run_turn(sms, [], db_session, trip)
    assert "SWIGGY" in resp.response
    assert "320" in resp.response

    # Test auto-routing settlement question
    q = "Who owes whom in this trip? Show settlements"
    s_resp = AgentRunner.run_turn(q, [], db_session, trip)
    assert "Settlements" in s_resp.response or "settled" in s_resp.response.lower()
