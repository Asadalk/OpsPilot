import asyncio
import os
import sys
from pathlib import Path

import httpx
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def _test_database_url() -> str:
    """Tests truncate and seed tables, so they get their own database on the same server."""
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        url = explicit
    else:
        base = os.getenv("DATABASE_URL", "postgresql://opspilot:opspilot@localhost:5433/opspilot")
        url = base.rsplit("/", 1)[0] + "/opspilot_test"
    if not url.rsplit("/", 1)[-1].endswith("_test"):
        raise RuntimeError(f"Refusing to run tests against non-test database: {url.rsplit('/', 1)[-1]}")
    return url


TEST_DATABASE_URL = _test_database_url()
# Settings are read at import time, so every repository built by app.main uses the test database.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# Tests never call a hosted model: blank keys make any accidental live call fail deterministically.
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

import psycopg  # noqa: E402

with psycopg.connect(TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres", autocommit=True) as _admin:
    _name = TEST_DATABASE_URL.rsplit("/", 1)[-1]
    if not _admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (_name,)).fetchone():
        _admin.execute(f'CREATE DATABASE "{_name}"')

from app.db.database import get_connection, init_db  # noqa: E402
from app.main import app, ops_agent, simulator_service, task_service  # noqa: E402


@pytest.fixture
def api(tmp_path, monkeypatch):
    database_url = TEST_DATABASE_URL
    monkeypatch.setattr(task_service.repository, "database_url", database_url)
    monkeypatch.setattr(simulator_service.repository, "database_url", database_url)
    monkeypatch.setattr(ops_agent.repository, "database_url", database_url)
    init_db(database_url)
    with get_connection(database_url) as connection:
        connection.execute("TRUNCATE tasks RESTART IDENTITY")

    async def send(method, url, **kwargs):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, url, **kwargs)

    def request(method, url, **kwargs):
        return asyncio.run(send(method, url, **kwargs))

    return request


@pytest.fixture
def database_path():
    return TEST_DATABASE_URL
