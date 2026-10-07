from fastapi import APIRouter, HTTPException

from app.agent.agent import OpsAgent
from app.agent.schemas import AgentState, InvestigationRequest


def build_agent_router(agent: OpsAgent) -> APIRouter:
    route = APIRouter(prefix="/agent")

    @route.post("/investigate", response_model=AgentState)
    async def investigate(payload: InvestigationRequest) -> AgentState:
        try:
            return await agent.investigate(payload.request)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Investigation failed") from exc

    return route