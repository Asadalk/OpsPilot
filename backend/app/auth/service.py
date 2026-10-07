import json
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.auth.schemas import Role, UserPrincipal
from app.core.config import settings


class AuthenticationError(Exception):
    pass


class AuthService:
    def __init__(self, secret: str = settings.jwt_secret, users_json: str = settings.auth_users_json):
        self.secret = secret
        self.users = json.loads(users_json)

    def authenticate(self, username: str, password: str) -> UserPrincipal:
        record = self.users.get(username)
        if not record or record.get("password") != password:
            raise AuthenticationError
        return UserPrincipal(username=username, role=record["role"])

    def issue_token(self, principal: UserPrincipal) -> str:
        payload = {
            "sub": principal.username,
            "role": principal.role,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
        }
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def decode_token(self, token: str) -> UserPrincipal:
        try:
            payload: dict[str, Any] = jwt.decode(token, self.secret, algorithms=["HS256"])
            return UserPrincipal(username=payload["sub"], role=payload["role"])
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise AuthenticationError from exc