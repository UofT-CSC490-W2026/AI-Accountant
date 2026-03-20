from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.db.base import AuthRepository
from backend.db.session import get_db
from backend.models.user_model import UserModel
from backend.schema.auth import TokenPayload
from backend.schema.user import UserRole
from backend.services.user import token_service, user_service


ROLE_LEVEL = {
    UserRole.REGULAR: 1,
    UserRole.MANAGER: 2,
    UserRole.SUPERUSER: 3,
}


@dataclass
class AuthContext:
    user: UserModel
    claims: TokenPayload
    role: UserRole


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AuthRepository, Depends(get_db)],
) -> AuthContext:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    try:
        claims = token_service.decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    role = token_service.extract_role(claims)
    user = user_service.sync_cognito_user(db, claims=claims, role=role)
    user_service.ensure_account_active(user)
    user = user_service.record_authentication(db, user)
    return AuthContext(user=user, claims=claims, role=role)


def require_role(required_role: UserRole) -> Callable[[AuthContext], AuthContext]:
    def dependency(current_user: Annotated[AuthContext, Depends(get_current_user)]) -> AuthContext:
        if ROLE_LEVEL[current_user.role] < ROLE_LEVEL[required_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role.")
        return current_user

    return dependency
