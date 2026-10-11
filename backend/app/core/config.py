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
    # Which model backs the agent and task extraction: "groq", "gemini", or "mock" (offline,
    # deterministic; used for the keyless demo and failure injection).
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    mock_llm_mode: str = os.getenv("MOCK_LLM_MODE", "normal").strip().lower()
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    # Client-side pacing to the account's tokens-per-minute limit (Groq free tier: 8000); 0 disables it.
    groq_tokens_per_minute: int = int(os.getenv("GROQ_TOKENS_PER_MINUTE", "8000"))
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_timeout_seconds: int = _parse_timeout(os.getenv("GEMINI_TIMEOUT_SECONDS", "25"))
    llm_timeout_seconds: int = _parse_timeout(os.getenv("LLM_TIMEOUT_SECONDS", os.getenv("GEMINI_TIMEOUT_SECONDS", "25")))
    tool_timeout_seconds: int = _parse_timeout(os.getenv("TOOL_TIMEOUT_SECONDS", "5"))
    retrieval_timeout_seconds: int = _parse_timeout(os.getenv("RETRIEVAL_TIMEOUT_SECONDS", "5"))
    database_connect_timeout_seconds: int = _parse_timeout(os.getenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "3"))
    database_statement_timeout_ms: int = _parse_timeout(os.getenv("DATABASE_STATEMENT_TIMEOUT_MS", "5000"))
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    gemini_fallback_models: str = os.getenv("GEMINI_FALLBACK_MODELS", "")
    # "development" allows the built-in dev secret and accounts; anything else refuses them at startup.
    environment: str = os.getenv("ENVIRONMENT", "development")
    # Optional customer TOML (services in scope, integrations, stricter policy); unset = whole simulator.
    customer_config: str = os.getenv("CUSTOMER_CONFIG", "")
    # When set, startup ingests this directory so retrieval never silently runs on an empty index.
    knowledge_dir: str = os.getenv("KNOWLEDGE_DIR", "")
    jwt_secret: str = os.getenv("JWT_SECRET", "ops-pilot-development-secret-change-me")
    jwt_expire_minutes: int = _parse_timeout(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    auth_users_json: str = os.getenv(
        "AUTH_USERS_JSON",
        '{"viewer":{"password":"viewer","role":"viewer"},"operator":{"password":"operator","role":"operator"},"admin":{"password":"admin","role":"admin"}}',
    )


settings = Settings()


DEVELOPMENT_SECRETS = {"ops-pilot-development-secret-change-me", "change-this-development-secret"}


def insecure_settings(config: Settings) -> list[str]:
    """Problems that are acceptable locally but must stop a non-development deployment."""
    import json

    problems = []
    if config.jwt_secret in DEVELOPMENT_SECRETS or len(config.jwt_secret) < 32:
        problems.append("JWT_SECRET is a development default or shorter than 32 characters")
    try:
        users = json.loads(config.auth_users_json)
    except json.JSONDecodeError:
        users = {}
    if any(isinstance(user, dict) and user.get("password") == name for name, user in users.items()):
        problems.append("AUTH_USERS_JSON contains an account whose password equals its username")
    return problems


def check_deployment_settings(config: Settings) -> None:
    if config.environment != "development" and (problems := insecure_settings(config)):
        raise RuntimeError(f"Refusing to start with ENVIRONMENT={config.environment}: " + "; ".join(problems))

