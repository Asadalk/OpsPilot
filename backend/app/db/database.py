import sqlite3
from pathlib import Path

from app.core.config import settings


def sqlite_path(database_url: str = settings.database_url) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only SQLite DATABASE_URL values are supported")
    return Path(database_url.removeprefix("sqlite:///"))


def get_connection(database_url: str = settings.database_url) -> sqlite3.Connection:
    path = sqlite_path(database_url).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(database_url: str = settings.database_url) -> None:
    with get_connection(database_url) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                owner TEXT NOT NULL,
                deadline TEXT NOT NULL,
                priority TEXT NOT NULL CHECK (priority IN ('high', 'medium', 'low')),
                status TEXT NOT NULL CHECK (status IN ('todo', 'in_progress', 'done')),
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()