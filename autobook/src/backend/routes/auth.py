from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.db.base import AuthRepository
from backend.db.session import get_db
from backend.deps.auth import AuthContext, get_current_user, require_role
from backend.models.user_model import UserModel
from backend.schema.auth import MessageResponse
from backend.schema.user import MeResponse, UserRole, UserSummary, UserUpdateRequest
from backend.services.user import auth_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_summary(user: UserModel) -> UserSummary:
    return UserSummary.model_validate(user)


def _to_me_response(context: AuthContext) -> MeResponse:
    return MeResponse(
        id=context.user.id,
        email=context.user.email,
        full_name=context.user.full_name,
        role=context.role,
        identity_provider=context.user.identity_provider,
        is_verified=context.user.is_verified,
        is_suspicious=context.user.is_suspicious,
        is_disabled=context.user.is_disabled,
        last_authenticated_at=context.user.last_authenticated_at,
        token_use=context.claims.token_use,
        cognito_groups=context.claims.cognito_groups,
    )


@router.post("/logout", response_model=MessageResponse)
def logout() -> MessageResponse:
    return auth_service.logout()


@router.get("/me", response_model=MeResponse)
def get_me(current_user: Annotated[AuthContext, Depends(get_current_user)]) -> MeResponse:
    return _to_me_response(current_user)


@router.patch("/me", response_model=MeResponse)
def update_me(
    payload: UserUpdateRequest,
    current_user: Annotated[AuthContext, Depends(get_current_user)],
    db: Annotated[AuthRepository, Depends(get_db)],
) -> MeResponse:
    updated_user = user_service.update_user_profile(db, current_user.user, payload)
    return _to_me_response(AuthContext(user=updated_user, claims=current_user.claims, role=current_user.role))


@router.post("/users/{user_id}/verify", response_model=UserSummary)
def verify_user(
    user_id: str,
    db: Annotated[AuthRepository, Depends(get_db)],
    current_user: Annotated[AuthContext, Depends(require_role(UserRole.MANAGER))],
) -> UserSummary:
    target = user_service.ensure_user_exists(db, user_id)
    updated = user_service.verify_user(db, target)
    user_service.write_audit_event(
        db,
        event_type="user_verified",
        actor_user_id=current_user.user.id,
        target_user_id=target.id,
    )
    return _to_user_summary(updated)


@router.post("/users/{user_id}/clear-suspicious", response_model=UserSummary)
def clear_suspicious_flag(
    user_id: str,
    db: Annotated[AuthRepository, Depends(get_db)],
    current_user: Annotated[AuthContext, Depends(require_role(UserRole.MANAGER))],
) -> UserSummary:
    target = user_service.ensure_user_exists(db, user_id)
    updated = user_service.clear_suspicious_flag(db, target)
    user_service.write_audit_event(
        db,
        event_type="suspicious_flag_cleared",
        actor_user_id=current_user.user.id,
        target_user_id=target.id,
    )
    return _to_user_summary(updated)
