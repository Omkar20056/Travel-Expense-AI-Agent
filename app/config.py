import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Travel Expense Tracker AI Agent"
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-3.8-flash"
    DATABASE_URL: str = "sqlite:///./travel_expenses.db"
    DEFAULT_HOME_CURRENCY: str = "USD"
    EXCHANGE_RATE_API_URL: str = "https://api.frankfurter.dev/v1"
    UPLOAD_DIR: str = "./uploads"

settings = Settings()
