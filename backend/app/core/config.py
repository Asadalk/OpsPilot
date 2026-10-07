import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / ".env")


def _parse_timeout(value: str) -> int:
    try:
        return max(1, int(value))
    except ValueError:
        return 25


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://opspilot:opspilot@localhost:5433/opspilot",
    )
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_timeout_seconds: int = _parse_timeout(os.getenv("GEMINI_TIMEOUT_SECONDS", "25"))
    tool_timeout_seconds: int = _parse_timeout(os.getenv("TOOL_TIMEOUT_SECONDS", "5"))
    retrieval_timeout_seconds: int = _parse_timeout(os.getenv("RETRIEVAL_TIMEOUT_SECONDS", "5"))
    database_connect_timeout_seconds: int = _parse_timeout(os.getenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "3"))
    database_statement_timeout_ms: int = _parse_timeout(os.getenv("DATABASE_STATEMENT_TIMEOUT_MS", "5000"))
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_fallback_models: str = os.getenv("GEMINI_FALLBACK_MODELS", "")
    environment: str = os.getenv("ENVIRONMENT", "development")
    jwt_secret: str = os.getenv("JWT_SECRET", "ops-pilot-development-secret-change-me")
    jwt_expire_minutes: int = _parse_timeout(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    auth_users_json: str = os.getenv(
        "AUTH_USERS_JSON",
        '{"viewer":{"password":"viewer","role":"viewer"},"operator":{"password":"operator","role":"operator"},"admin":{"password":"admin","role":"admin"}}',
    )


settings = Settings()
