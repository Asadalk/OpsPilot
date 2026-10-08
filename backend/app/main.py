from contextlib import asynccontextmanager
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.tasks import build_task_router
from app.api.routes.simulator import build_simulator_router, build_incidents_router
from app.api.routes.agent import build_agent_router
from app.api.routes.auth import router as auth_router
from app.api.routes.approvals import build_approval_router
from app.api.routes.audit import build_audit_router
from app.agent.agent import build_agent
from app.agent.provider import GeminiDecisionProvider
from app.core.config import settings
from app.db.database import init_db
from app.db.repositories import TaskRepository
from app.db.simulator import SimulatorRepository
from app.audit.repository import AuditRepository
from app.services.simulator import SimulatorService
from app.services.tasks import TaskService

task_service = TaskService(TaskRepository(settings.database_url))
simulator_service = SimulatorService(SimulatorRepository(settings.database_url))
ops_agent = build_agent(settings.database_url, GeminiDecisionProvider())


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(settings.database_url)
    yield


app = FastAPI(title="Ops Pilot API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ops-pilot-api"}


@app.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "Ops Pilot API is running", "health": "/health"}


app.include_router(build_task_router(task_service))
app.include_router(build_simulator_router(simulator_service))
app.include_router(build_incidents_router(simulator_service))
app.include_router(build_agent_router(ops_agent))
app.include_router(auth_router)
app.include_router(build_approval_router(ops_agent.approval_service))
app.include_router(build_audit_router(AuditRepository(settings.database_url)))


@app.get("/evaluation/latest")
async def latest_evaluation():
    artifact = Path(__file__).resolve().parents[1] / "benchmarks" / "opsbench" / "v1" / "results" / "phase20-ablation.json"
    try:
        return json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="No valid recorded evaluation artifact is available") from exc
