from fastapi import APIRouter, HTTPException

from app.agent.agent import OpsAgent
from app.agent.schemas import AgentState, InvestigationRequest
from app.auth.dependencies import get_current_user
from app.auth.schemas import UserPrincipal
from fastapi import Depends
from uuid import UUID

from app.agent.events import AgentRunTrace
from app.db.agent_events import AgentEventRepository


def build_agent_router(agent: OpsAgent) -> APIRouter:
    route = APIRouter(prefix="/agent")
    event_repository = AgentEventRepository(agent.repository.database_url)

    @route.get("/runs/{run_id}/events")
    async def get_run_events(run_id: UUID, principal: UserPrincipal = Depends(get_current_user)) -> AgentRunTrace:
        trace = event_repository.for_run(run_id, principal)
        if trace is None:
            raise HTTPException(status_code=404, detail="Agent run not found")
        return trace

    @route.get("/runs")
    async def list_runs(limit: int = 100, principal: UserPrincipal = Depends(get_current_user)):
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
        return event_repository.list_runs(principal, limit)

    @route.post("/investigate", response_model=AgentState)
    async def investigate(payload: InvestigationRequest, principal: UserPrincipal = Depends(get_current_user)) -> AgentState:
        try:
            return await agent.investigate(payload.request, principal)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Investigation failed") from exc

    return route
