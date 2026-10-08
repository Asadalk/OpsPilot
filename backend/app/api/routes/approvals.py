from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.approval.repository import ApprovalConflict, ApprovalNotFound
from app.approval.schemas import ApprovalDecisionRequest, ApprovalRecord
from app.approval.service import ApprovalAuthorizationError, ApprovalService
from app.auth.dependencies import get_current_user
from app.auth.schemas import UserPrincipal


def build_approval_router(approval_service: ApprovalService) -> APIRouter:
    route = APIRouter(prefix="/approvals")

    @route.get("", response_model=list[ApprovalRecord])
    async def list_approvals(decision: str = Query(default="pending", pattern="^(pending|all)$"),
                             _: UserPrincipal = Depends(get_current_user)) -> list[ApprovalRecord]:
        if decision == "all":
            return approval_service.repository.list_all()
        return approval_service.repository.list_pending()

    @route.get("/{approval_id}", response_model=ApprovalRecord)
    async def get_approval(approval_id: int, _: UserPrincipal = Depends(get_current_user)) -> ApprovalRecord:
        try:
            return approval_service.get(approval_id)
        except ApprovalNotFound as exc:
            raise HTTPException(status_code=404, detail="Approval not found") from exc

    async def decide(approval_id: int, decision: str, payload: ApprovalDecisionRequest, principal: UserPrincipal) -> ApprovalRecord:
        try:
            return approval_service.decide(approval_id, decision, principal, payload.reason)
        except ApprovalAuthorizationError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Approval authority required") from exc
        except ApprovalNotFound as exc:
            raise HTTPException(status_code=404, detail="Approval not found") from exc
        except ApprovalConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @route.post("/{approval_id}/approve", response_model=ApprovalRecord)
    async def approve(approval_id: int, payload: ApprovalDecisionRequest, principal: UserPrincipal = Depends(get_current_user)) -> ApprovalRecord:
        return await decide(approval_id, "approved", payload, principal)

    @route.post("/{approval_id}/reject", response_model=ApprovalRecord)
    async def reject(approval_id: int, payload: ApprovalDecisionRequest, principal: UserPrincipal = Depends(get_current_user)) -> ApprovalRecord:
        return await decide(approval_id, "rejected", payload, principal)

    return route
