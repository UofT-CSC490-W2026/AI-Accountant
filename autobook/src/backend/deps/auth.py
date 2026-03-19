from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.db.base import AuthRepository
from backend.db.session import get_db
from backend.models.user_model import UserModel
from backend.schema.user import UserRole
from backend.services.user import token_service, user_service


ROLE_LEVEL = {
    UserRole.REGULAR: 1,
    UserRole.MANAGER: 2,
    UserRole.SUPERUSER: 3,
}

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AuthRepository, Depends(get_db)],
) -> UserModel:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    try:
        payload = token_service.decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = user_service.get_by_id(db, payload.sub)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown token subject.")
    if payload.token_version != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked.")
    user_service.ensure_account_active(user)
    return user


def require_role(required_role: UserRole) -> Callable[[UserModel], UserModel]:
    def dependency(current_user: Annotated[UserModel, Depends(get_current_user)]) -> UserModel:
        if ROLE_LEVEL[current_user.role] < ROLE_LEVEL[required_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role.")
        return current_user

    return dependency
