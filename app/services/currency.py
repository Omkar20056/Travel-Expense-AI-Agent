import httpx
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.exchange_rate import ExchangeRate
from app.config import settings

class CurrencyService:
    BASE_URL = settings.EXCHANGE_RATE_API_URL

    # Static fallback rates to USD in case external network is unreachable
    STATIC_FALLBACKS_TO_USD = {
        "USD": 1.0,
        "EUR": 1.08,
        "GBP": 1.28,
        "JPY": 0.0066,
        "CAD": 0.74,
        "AUD": 0.66,
        "CHF": 1.12,
        "INR": 0.0107,  # ~93.5 INR per USD
        "CNY": 0.14,
        "SGD": 0.75,
    }

    @classmethod
    def get_rate(
        cls,
        base_currency: str,
        target_currency: str,
        rate_date: Optional[date] = None,
        db: Optional[Session] = None
    ) -> float:
        """
        Get exchange rate from base_currency to target_currency for a given date.
        Checks SQLite cache first; if missing, calls free FX API and caches the rate.
        Falls back gracefully if network fails.
        """
        base = base_currency.strip().upper()
        target = target_currency.strip().upper()

        if base == target:
            return 1.0

        target_date = rate_date or date.today()

        # 1. Check local DB cache
        if db:
            cached = db.query(ExchangeRate).filter(
                ExchangeRate.date == target_date,
                ExchangeRate.base_currency == base,
                ExchangeRate.target_currency == target
            ).first()
            if cached:
                return float(cached.rate)

        # 2. Try fetching from free FX API (Frankfurter)
        rate = cls._fetch_from_api(base, target, target_date)

        # If direct fetch succeeded, save to cache
        if rate is not None and db:
            try:
                new_rate = ExchangeRate(
                    date=target_date,
                    base_currency=base,
                    target_currency=target,
                    rate=rate,
                    fetched_at=datetime.now(timezone.utc)
                )
                db.add(new_rate)
                db.commit()
            except Exception:
                db.rollback()
            return rate

        # 3. If API failed or was unreachable, try static fallbacks or inverted pairs
        fallback_rate = cls._calculate_fallback(base, target)
        if fallback_rate is not None:
            return fallback_rate

        # Default fallback
        return 1.0

    @classmethod
    def _fetch_from_api(cls, base: str, target: str, rate_date: date) -> Optional[float]:
        try:
            date_str = rate_date.strftime("%Y-%m-%d")
            url = f"{cls.BASE_URL}/{date_str}?from={base}&to={target}"
            with httpx.Client(timeout=4.0, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    rates = data.get("rates", {})
                    if target in rates:
                        return float(rates[target])
        except Exception:
            pass

        # Try latest endpoint as secondary attempt
        try:
            url = f"{cls.BASE_URL}/latest?from={base}&to={target}"
            with httpx.Client(timeout=3.0, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    rates = data.get("rates", {})
                    if target in rates:
                        return float(rates[target])
        except Exception:
            pass

        return None

    @classmethod
    def _calculate_fallback(cls, base: str, target: str) -> Optional[float]:
        usd_base = cls.STATIC_FALLBACKS_TO_USD.get(base)
        usd_target = cls.STATIC_FALLBACKS_TO_USD.get(target)
        if usd_base and usd_target:
            # e.g., EUR to GBP = (EUR->USD) / (GBP->USD) = 1.08 / 1.28
            return round(usd_base / usd_target, 6)
        return None

    @classmethod
    def convert(
        cls,
        amount: float,
        from_currency: str,
        to_currency: str,
        rate_date: Optional[date] = None,
        db: Optional[Session] = None
    ) -> tuple[float, float]:
        """Returns (converted_amount, applied_rate)."""
        rate = cls.get_rate(from_currency, to_currency, rate_date, db)
        converted = round(amount * rate, 2)
        return converted, rate
