import os
import json
import mimetypes
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from app.config import settings

class ReceiptParserService:
    @classmethod
    def parse_receipt(cls, image_path: str) -> Dict[str, Any]:
        """
        Parses a receipt image using Google Gemini Vision (gemini-3.8-flash).
        Falls back to structured mock parser if API key is not set or network fails.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Receipt image not found at {image_path}")

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return cls._mock_receipt_parse(image_path)

        try:
            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type or not mime_type.startswith("image/"):
                mime_type = "image/jpeg"

            with open(image_path, "rb") as img_file:
                image_bytes = img_file.read()

            client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=10000))

            prompt = (
                "You are an expert receipt OCR and expense parsing system. "
                "Analyze this receipt image and extract the following details as valid, strictly formatted JSON only. "
                "Do NOT wrap in markdown code blocks. Output raw JSON with these exact fields:\n"
                "{\n"
                '  "merchant": "string or null",\n'
                '  "date": "YYYY-MM-DD or null if unreadable",\n'
                '  "amount": number (total amount paid),\n'
                '  "currency": "3-letter ISO code e.g. EUR, USD, JPY, GBP",\n'
                '  "suggested_category": "one of: food, transport, lodging, activities, shopping, fees, other",\n'
                '  "items": [\n'
                '    {"name": "item description", "quantity": 1, "unit_price": 0.0, "total_price": 0.0}\n'
                "  ],\n"
                '  "raw_notes": "short summary of merchant and items"\n'
                "}\n"
                "If any field cannot be determined, provide null for merchant/date or 0.0 for amount."
            )

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                ]
            )

            text_content = response.text.strip()
            # Clean possible markdown fencing
            if text_content.startswith("```"):
                text_content = text_content.strip("`")
                if text_content.startswith("json"):
                    text_content = text_content[4:].strip()

            parsed = json.loads(text_content)
            return parsed

        except Exception as e:
            return cls._mock_receipt_parse(image_path, error_note=str(e))

    @classmethod
    def _mock_receipt_parse(cls, image_path: str, error_note: Optional[str] = None) -> Dict[str, Any]:
        """Provides a safe structured fallback when API key is unset or offline."""
        filename = os.path.basename(image_path)
        return {
            "merchant": "Local Merchant",
            "date": "2026-11-18",
            "amount": 25.50,
            "currency": "EUR",
            "suggested_category": "food",
            "items": [
                {"name": "Standard item", "quantity": 1, "unit_price": 25.50, "total_price": 25.50}
            ],
            "raw_notes": f"Parsed from {filename}" + (f" (Fallback note: {error_note})" if error_note else ""),
            "is_mock": True
        }
