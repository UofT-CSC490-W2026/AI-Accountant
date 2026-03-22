from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from auth.schemas import TokenPayload, UserRole
from auth.token_service import decode_access_token
from config import get_settings
from db.connection import get_db
from db.dao.users import UserDAO
from db.models.user import User

ROLE_RANK: dict[UserRole, int] = {
    UserRole.REGULAR: 0,
    UserRole.MANAGER: 1,
    UserRole.SUPERUSER: 2,
}


@dataclass
class AuthContext:
    user: User
    claims: TokenPayload
    role: UserRole
    role_source: str


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    return resolve_auth_context(credentials.credentials, db)


def resolve_auth_context(token: str, db: Session) -> AuthContext:
    try:
        claims = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = UserDAO.get_or_create_from_cognito_claims(
        db,
        cognito_sub=claims.sub,
        email=claims.email or claims.username,
    )
    role, role_source = _resolve_role(claims)
    return AuthContext(user=user, claims=claims, role=role, role_source=role_source)


def resolve_auth_context_from_request(request: Request, db: Session) -> AuthContext:
    token = _extract_token(
        request.headers.get("authorization"),
        request.query_params.get("access_token"),
    )
    return resolve_auth_context(token, db)


def resolve_auth_context_from_websocket(websocket: WebSocket, db: Session) -> AuthContext:
    token = _extract_token(
        websocket.headers.get("authorization"),
        websocket.query_params.get("access_token"),
    )
    return resolve_auth_context(token, db)


def _extract_token(authorization_header: str | None, query_token: str | None) -> str:
    if authorization_header:
        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed bearer token.")
        return token
    if query_token:
        return query_token
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")


def require_role(minimum_role: UserRole) -> Callable[[AuthContext], AuthContext]:
    def dependency(current_user: AuthContext = Depends(get_current_user)) -> AuthContext:
        if ROLE_RANK[current_user.role] < ROLE_RANK[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{minimum_role.value} role required.",
            )
        return current_user

    return dependency


def _resolve_role(claims: TokenPayload) -> tuple[UserRole, str]:
    settings = get_settings()

    if settings.COGNITO_ROLE_CLAIM_SOURCE == "custom:role":
        custom_role = _parse_single_role(claims.custom_role)
        if custom_role is not None:
            return custom_role, "custom:role"
        group_role = _parse_group_role(claims.cognito_groups)
        if group_role is not None:
            return group_role, "cognito:groups"
    else:
        group_role = _parse_group_role(claims.cognito_groups)
        if group_role is not None:
            return group_role, "cognito:groups"
        custom_role = _parse_single_role(claims.custom_role)
        if custom_role is not None:
            return custom_role, "custom:role"

    return UserRole.REGULAR, "default"


def _parse_group_role(groups: list[str]) -> UserRole | None:
    resolved_roles = [
        role
        for group in groups
        if (role := _parse_single_role(group)) is not None
    ]
    if not resolved_roles:
        return None
    return max(resolved_roles, key=lambda role: ROLE_RANK[role])


def _parse_single_role(value: str | None) -> UserRole | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    for role in UserRole:
        if normalized == role.value:
            return role
    return None
