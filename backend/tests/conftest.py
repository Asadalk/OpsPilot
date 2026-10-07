import asyncio
import sys
from pathlib import Path

import httpx
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.db.database import init_db
from app.main import app, task_service


@pytest.fixture
def api(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(task_service.repository, "database_url", database_url)
    init_db(database_url)

    async def send(method, url, **kwargs):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, url, **kwargs)

    def request(method, url, **kwargs):
        return asyncio.run(send(method, url, **kwargs))

    return request


@pytest.fixture
def database_path(tmp_path, monkeypatch):
    return f"sqlite:///{tmp_path / 'db_ops.sqlite'}"
