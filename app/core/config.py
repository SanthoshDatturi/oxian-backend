import os
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    CONCURRENCY_LIMIT: int = 5
    FIREBASE_PROJECT_ID: Optional[str] = os.getenv("FIREBASE_PROJECT_ID")
    FIREBASE_SERVICE_ACCOUNT_PATH: Optional[str] = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH"
    )
    FIREBASE_SERVICE_ACCOUNT_JSON: Optional[str] = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON"
    )
    MONGO_URI: str = os.environ.get("MONGO_URI", "")
    MONGO_DIRECT_URI: str = os.environ.get("MONGO_DIRECT_URI", "")
    MONGO_DB_NAME: str = os.environ.get("MONGO_DB_NAME", "")
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = os.getenv(
        "AZURE_STORAGE_CONNECTION_STRING"
    )
    OPENWEATHERMAP_API_KEY: Optional[str] = os.getenv("OPENWEATHERMAP_API_KEY")
    GEMINI_CHAT_MODEL: str = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
    GEMINI_TTS_MODEL: str = os.getenv(
        "GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"
    )
    CHAT_HISTORY_LIMIT: int = int(os.getenv("CHAT_HISTORY_LIMIT", "16"))


settings = Settings()
