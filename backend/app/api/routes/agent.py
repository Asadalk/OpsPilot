from fastapi import APIRouter, HTTPException

from app.agent.agent import OpsAgent
from app.agent.schemas import AgentState, InvestigationRequest
from app.auth.dependencies import get_current_user
from app.auth.schemas import UserPrincipal
from fastapi import Depends


def build_agent_router(agent: OpsAgent) -> APIRouter:
    route = APIRouter(prefix="/agent")

    @route.post("/investigate", response_model=AgentState)
    async def investigate(payload: InvestigationRequest, principal: UserPrincipal = Depends(get_current_user)) -> AgentState:
        try:
            return await agent.investigate(payload.request, principal)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Investigation failed") from exc

    return route