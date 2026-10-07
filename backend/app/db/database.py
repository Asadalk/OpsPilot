from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def get_connection(database_url: str = settings.database_url) -> psycopg.Connection:
    return psycopg.connect(database_url, row_factory=dict_row)


def init_db(database_url: str = settings.database_url) -> None:
    with get_connection(database_url) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        )
        applied = {row["version"] for row in connection.execute("SELECT version FROM schema_migrations")}
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migration.name in applied:
                continue
            connection.execute(migration.read_text(encoding="utf-8"))
            connection.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration.name,))