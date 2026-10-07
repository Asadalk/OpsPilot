from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.tasks import build_task_router
from app.core.config import settings
from app.db.database import init_db
from app.db.repositories import TaskRepository
from app.services.tasks import TaskService

task_service = TaskService(TaskRepository(settings.database_url))


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(settings.database_url)
    yield


app = FastAPI(title="Ops Assistant API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ops-assistant-api"}


@app.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "Ops Assistant API is running", "health": "/health"}


app.include_router(build_task_router(task_service))