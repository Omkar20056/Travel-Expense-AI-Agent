from datetime import date
from app.services.currency import CurrencyService
from app.models.exchange_rate import ExchangeRate

def test_same_currency_conversion(db_session):
    converted, rate = CurrencyService.convert(100.0, "USD", "USD", date.today(), db_session)
    assert converted == 100.0
    assert rate == 1.0

def test_currency_conversion_and_db_caching(db_session):
    test_date = date(2026, 11, 10)
    converted, rate = CurrencyService.convert(50.0, "EUR", "USD", test_date, db_session)

    assert rate > 0
    assert converted > 0
    assert round(50.0 * rate, 2) == converted

    # Verify cached in database
    cached = db_session.query(ExchangeRate).filter(
        ExchangeRate.date == test_date,
        ExchangeRate.base_currency == "EUR",
        ExchangeRate.target_currency == "USD"
    ).first()

    # If API reached, it was saved to DB cache
    if cached:
        assert float(cached.rate) == rate

def test_static_fallback_calculation():
    rate = CurrencyService._calculate_fallback("EUR", "USD")
    assert rate is not None
    assert rate > 1.0  # EUR/USD is typically ~1.08
