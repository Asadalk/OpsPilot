from contextlib import asynccontextmanager
import logging
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
from app.agent.provider import build_decision_provider
from app.core.config import check_deployment_settings, settings
from app.core.customer import load_customer_config
from app.db.database import init_db
from app.db.repositories import TaskRepository
from app.db.simulator import SimulatorRepository
from app.rag.ingest import ingest_directory
from app.audit.repository import AuditRepository
from app.services.simulator import SimulatorService
from app.services.tasks import TaskService

task_service = TaskService(TaskRepository(settings.database_url))
simulator_service = SimulatorService(SimulatorRepository(settings.database_url))
customer = load_customer_config(settings.customer_config)
ops_agent = build_agent(settings.database_url, build_decision_provider(), customer)


@asynccontextmanager
async def lifespan(_: FastAPI):
    check_deployment_settings(settings)
    init_db(settings.database_url)
    if settings.knowledge_dir:
        count = ingest_directory(Path(settings.knowledge_dir), settings.database_url)
        logging.getLogger("uvicorn.error").info("Ingested %d knowledge documents from %s", count, settings.knowledge_dir)
    yield


app = FastAPI(title="Ops Pilot API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ops-pilot-api"}


@app.get("/customer")
async def read_customer() -> dict[str, object]:
    return {"name": customer.name, "managed_services": sorted(customer.managed_services or []) or None,
            "github_enabled": customer.github_enabled,
            "production_restart_requires_approval": customer.production_restart_requires_approval}


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


BENCHMARKS_DIR = Path(__file__).resolve().parents[1] / "benchmarks" / "opsbench"


@app.get("/evaluation/latest")
async def latest_evaluation():
    """Serve the checked-in evaluation artifacts; nothing here is computed on request."""
    from fastapi import HTTPException

    def read(path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=503, detail=f"Evaluation artifact is unreadable: {path.name}") from exc

    component_study = read(BENCHMARKS_DIR / "v1" / "results" / "phase20-ablation.json")
    opsbench = read(BENCHMARKS_DIR / "v2" / "results" / "summary.json")
    if component_study is None and opsbench is None:
        raise HTTPException(status_code=503, detail="No recorded evaluation artifact is available")
    return {"opsbench": opsbench, "component_study": component_study}
