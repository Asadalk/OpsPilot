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
        f"sqlite:///{Path(os.getenv('TASKS_DB_PATH', BACKEND_ROOT / 'tasks.db')).resolve()}",
    )
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_timeout_seconds: int = _parse_timeout(os.getenv("GEMINI_TIMEOUT_SECONDS", "25"))
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_fallback_models: str = os.getenv("GEMINI_FALLBACK_MODELS", "")
    environment: str = os.getenv("ENVIRONMENT", "development")


settings = Settings()