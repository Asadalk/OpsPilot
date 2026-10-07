from fastapi import APIRouter, Depends, HTTPException

from app.audit.repository import AuditRepository
from app.audit.schemas import IncidentAuditStory
from app.auth.dependencies import get_current_user
from app.auth.schemas import UserPrincipal


def build_audit_router(repository: AuditRepository) -> APIRouter:
    route = APIRouter(prefix="/audit", tags=["audit"])

    @route.get("/incidents/{incident_id}", response_model=IncidentAuditStory)
    async def incident_story(incident_id: int, _: UserPrincipal = Depends(get_current_user)) -> IncidentAuditStory:
        story = repository.incident_story(incident_id)
        if story is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return story

    return route
