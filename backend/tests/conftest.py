import asyncio
import os
import sys
from pathlib import Path

import httpx
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.db.database import get_connection, init_db
from app.main import app, task_service


@pytest.fixture
def api(tmp_path, monkeypatch):
    database_url = os.getenv("TEST_DATABASE_URL", "postgresql://opspilot:opspilot@localhost:5433/opspilot")
    monkeypatch.setattr(task_service.repository, "database_url", database_url)
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
    return os.getenv("TEST_DATABASE_URL", "postgresql://opspilot:opspilot@localhost:5433/opspilot")
