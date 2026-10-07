from fastapi import APIRouter, HTTPException, status

from app.auth.schemas import TokenRequest, TokenResponse
from app.auth.service import AuthenticationError, AuthService

router = APIRouter(prefix="/auth")


@router.post("/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest) -> TokenResponse:
    try:
        principal = AuthService().authenticate(payload.username, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from exc
    return TokenResponse(access_token=AuthService().issue_token(principal))