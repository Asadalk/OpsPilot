from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["viewer", "operator", "admin"]


class TokenRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UserPrincipal(BaseModel):
    username: str
    role: Role