from app.agent.runner import AgentRunner
from app.models.trip import Trip
from app.models.expense import Expense
from app.models.category import CategoryRule

def test_ambiguous_input_triggers_clarification(db_session):
    trip = db_session.query(Trip).first()

    # User gives an ambiguous expense without amount or currency
    resp = AgentRunner.run_turn("Bought dinner in Rome", [], db_session, trip)

    # Agent MUST ask a clarifying question and NOT invent values or call add_expense
    assert resp.clarification_needed is True
    assert "?" in resp.response
    assert len(resp.tools_called) == 0

    # Ensure no expense was hallucinated into DB
    count = db_session.query(Expense).count()
    assert count == 0

def test_natural_language_expense_logging(db_session):
    trip = db_session.query(Trip).first()

    msg = "Paid 45 euros for dinner in Rome, split with Sam"
    resp = AgentRunner.run_turn(msg, [], db_session, trip)

    assert resp.clarification_needed is False
    assert "Saved:" in resp.response
    assert "45.00" in resp.response
    assert "Dinner" in resp.response or "Rome" in resp.response

    # Verify stored in DB
    expense = db_session.query(Expense).first()
    assert expense is not None
    assert float(expense.amount) == 45.0
    assert expense.currency == "EUR"
    assert expense.amount_home > 0
    assert expense.category.name == "food"
    assert "Sam" in expense.split_notes

def test_user_category_correction_learning(db_session):
    trip = db_session.query(Trip).first()

    # 1. First add an expense
    add_resp = AgentRunner.run_turn("Paid 12 euros at Starbucks", [], db_session, trip)
    exp = db_session.query(Expense).first()
    assert exp is not None

    # 2. User tells agent to correct category
    correct_msg = f"Change expense #{exp.id} to food"
    resp = AgentRunner.run_turn(correct_msg, [], db_session, trip)

    assert "Updated" in resp.response
    assert "Food" in resp.response

    # Verify category updated
    db_session.refresh(exp)
    assert exp.category.name == "food"

    # Verify rule learned in category_rules table
    rules = db_session.query(CategoryRule).all()
    assert len(rules) > 0

def test_indian_rupees_logging(db_session):
    trip = db_session.query(Trip).first()

    # Test suffix format: "500 rupees"
    resp1 = AgentRunner.run_turn("Paid 500 rupees for lunch in Mumbai", [], db_session, trip)
    assert resp1.clarification_needed is False
    assert "₹500.00" in resp1.response or "INR 500.00" in resp1.response

    exp1 = db_session.query(Expense).filter(Expense.amount == 500.0).first()
    assert exp1 is not None
    assert exp1.currency == "INR"
    assert exp1.amount_home > 0
    assert exp1.category.name == "food"

    # Test prefix format: "₹1200 for taxi"
    resp2 = AgentRunner.run_turn("Spent ₹1200 on taxi to airport", [], db_session, trip)
    assert resp2.clarification_needed is False
    assert "₹1200.00" in resp2.response or "INR 1200.00" in resp2.response

    exp2 = db_session.query(Expense).filter(Expense.amount == 1200.0).first()
    assert exp2 is not None
    assert exp2.currency == "INR"
    assert exp2.category.name == "transport"
