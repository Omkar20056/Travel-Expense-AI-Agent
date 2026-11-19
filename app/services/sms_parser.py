import re
import json
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional
from app.config import settings
from app.services.categorization import CategorizationService

logger = logging.getLogger("travel_agent")

class SmsParserService:
    """
    Parser for Indian UPI (Google Pay, PhonePe, Paytm, BHIM) and Global Bank 
    transaction SMS / notifications (Credit Card, Debit Card, NetBanking).
    """

    @classmethod
    def parse_sms(cls, text: str, default_currency: str = "INR", db: Any = None) -> Dict[str, Any]:
        """
        Parses an SMS text and extracts financial transaction details.
        Uses deterministic pattern matching first, with Gemini AI enhancement if available.
        """
        clean_text = text.strip()
        if not clean_text:
            return {"error": "Empty SMS text"}

        # Try deterministic pattern extraction
        result = cls._deterministic_parse(clean_text, default_currency, db)

        # If deterministic parse found amount and merchant, return it
        if result.get("amount") and result.get("merchant"):
            return result

        # Optional Gemini fallback for heavily obscured or conversational SMS
        if settings.GEMINI_API_KEY:
            try:
                ai_result = cls._ai_parse(clean_text, default_currency)
                if ai_result and ai_result.get("amount"):
                    return ai_result
            except Exception as e:
                logger.debug("AI SMS parsing skipped (%s), using regex result", e)

        return result

    @classmethod
    def _deterministic_parse(cls, text: str, default_currency: str = "INR", db: Any = None) -> Dict[str, Any]:
        # 1. Amount and Currency Extraction
        amount = None
        currency = default_currency

        amt_match = re.search(
            r"(?:(Rs\.?|INR|₹|USD|\$|EUR|€|GBP|£)\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)|([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*(Rs\.?|INR|₹|USD|EUR|GBP))",
            text,
            re.IGNORECASE
        )

        if amt_match:
            raw_amt = amt_match.group(2) or amt_match.group(3)
            sym = (amt_match.group(1) or amt_match.group(4) or "").upper()
            if raw_amt:
                try:
                    amount = float(raw_amt.replace(",", ""))
                except ValueError:
                    amount = None

            if "USD" in sym or "$" in sym:
                currency = "USD"
            elif "EUR" in sym or "€" in sym:
                currency = "EUR"
            elif "GBP" in sym or "£" in sym:
                currency = "GBP"
            else:
                currency = "INR"

        # 2. Payment Mode Detection
        payment_mode = "Cash"
        text_lower = text.lower()
        if "upi" in text_lower or "gpay" in text_lower or "phonepe" in text_lower or "paytm" in text_lower:
            payment_mode = "UPI"
        elif "credit card" in text_lower or "cc " in text_lower or "card ending" in text_lower:
            payment_mode = "Credit Card"
        elif "debit card" in text_lower or "dc " in text_lower:
            payment_mode = "Debit Card"
        elif "debited" in text_lower or "a/c" in text_lower or "acct" in text_lower:
            payment_mode = "NetBanking"

        # 3. Reference ID / Txn ID
        ref_id = None
        ref_match = re.search(
            r"(?:UPI Ref|Ref no|Ref|Txn ID|Txn|UTR|reference)\s*(?:no\.?|id|:)?\s*([A-Za-z0-9_-]{6,22})",
            text,
            re.IGNORECASE
        )
        if ref_match:
            ref_id = ref_match.group(1).strip()

        # 4. Merchant Extraction
        merchant = None
        # Patterns like: "to SWIGGY", "at CAFE COFFEE DAY", "info: UBER", "vpa ...@okaxis"
        merchant_patterns = [
            r"(?:to|at|info[\*:\s]+|vpa\s+)\s*([A-Za-z0-9 &._'-]{2,35}?)(?=\s+(?:via|on|ref|using|avail|bal|a/c|\.|$))",
            r"(?:paid to|sent to|spent at)\s+([A-Za-z0-9 &._'-]{2,35}?)(?=\s+(?:via|on|ref|for|\.|$))",
            r"(?:transfer to|debited for)\s+([A-Za-z0-9 &._'-]{2,35}?)(?=\s+(?:via|on|ref|\.|$))",
        ]
        for pattern in merchant_patterns:
            m_match = re.search(pattern, text, re.IGNORECASE)
            if m_match:
                cand = m_match.group(1).strip()
                # Exclude common false positives
                if cand.lower() not in ["your", "a/c", "account", "the", "bank", "credit card", "vpa", "upi"]:
                    merchant = cand
                    break

        if not merchant and ref_id:
            merchant = "UPI Merchant"
        elif not merchant:
            merchant = "Vendor"

        # 5. Date Extraction
        txn_date = date.today()
        date_match = re.search(
            r"(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2,4})",
            text,
            re.IGNORECASE
        )
        if date_match:
            raw_date = date_match.group(1)
            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y", "%d-%b-%y", "%d-%b-%Y"):
                try:
                    txn_date = datetime.strptime(raw_date, fmt).date()
                    break
                except ValueError:
                    pass

        # 6. Description & Category
        description = f"{payment_mode} payment to {merchant}"
        suggested_category = "other"
        if db is not None:
            try:
                cat_obj = CategorizationService.classify(db, description, merchant)
                if cat_obj:
                    suggested_category = cat_obj.name
            except Exception:
                suggested_category = "other"
        else:
            # Fallback simple keyword match
            text_combo = f"{merchant} {description}".lower()
            if any(k in text_combo for k in ["swiggy", "zomato", "starbucks", "cafe", "restaurant", "food", "dinner", "lunch"]):
                suggested_category = "food"
            elif any(k in text_combo for k in ["uber", "ola", "metro", "flight", "indigo", "makemytrip", "fuel", "petrol"]):
                suggested_category = "transport"
            elif any(k in text_combo for k in ["hotel", "airbnb", "stay"]):
                suggested_category = "lodging"

        return {
            "success": amount is not None,
            "amount": amount,
            "currency": currency,
            "merchant": merchant,
            "description": description,
            "payment_mode": payment_mode,
            "reference_id": ref_id,
            "date": txn_date.strftime("%Y-%m-%d"),
            "category": suggested_category,
            "raw_sms": text
        }

    @classmethod
    def _ai_parse(cls, text: str, default_currency: str) -> Optional[Dict[str, Any]]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=8000))
        prompt = (
            "Extract structured financial payment information from this transaction SMS alert. "
            "Output strictly raw JSON without markdown formatting with fields:\n"
            "{\n"
            '  "amount": number or null,\n'
            f'  "currency": "3-letter ISO currency code (default: {default_currency})",\n'
            '  "merchant": "merchant name or null",\n'
            '  "description": "short clear description",\n'
            '  "payment_mode": "one of: UPI, Credit Card, Debit Card, NetBanking, Cash",\n'
            '  "reference_id": "UPI ref or txn id or null",\n'
            '  "category": "one of: food, transport, lodging, activities, shopping, fees, other"\n'
            "}\n\n"
            f"SMS text:\n{text}"
        )
        res = client.models.generate_content(model=settings.GEMINI_MODEL, contents=prompt)
        raw = res.text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\n", "", raw)
            raw = re.sub(r"\n```$", "", raw)
        data = json.loads(raw)
        data["date"] = date.today().strftime("%Y-%m-%d")
        data["raw_sms"] = text
        data["success"] = data.get("amount") is not None
        return data
