from fastapi import APIRouter, HTTPException, status

from app.auth.schemas import TokenRequest, TokenResponse
from app.auth.service import AuthenticationError, AuthService
from app.audit.repository import AuditRepository
from app.core.config import settings

router = APIRouter(prefix="/auth")


@router.post("/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest) -> TokenResponse:
    audit = AuditRepository(settings.database_url)
    try:
        principal = AuthService().authenticate(payload.username, payload.password)
    except AuthenticationError as exc:
        audit.record(actor=payload.username, event_type="auth.login", entity_type="user", entity_id=payload.username,
                     reason="Authentication failed.", result={"status": "denied"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from exc
    audit.record(actor=principal.username, event_type="auth.login", entity_type="user", entity_id=principal.username,
                 reason="Authentication succeeded.", result={"status": "success", "role": principal.role})
    return TokenResponse(access_token=AuthService().issue_token(principal))
