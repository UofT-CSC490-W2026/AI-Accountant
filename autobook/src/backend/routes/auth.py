from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.db.base import AuthRepository
from backend.db.session import get_db
from backend.deps.auth import get_current_user, require_role
from backend.models.user_model import UserModel
from backend.schema.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from backend.schema.user import MeResponse, UpdateUserRoleRequest, UserRole, UserSummary, UserUpdateRequest
from backend.services.user import auth_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _to_user_summary(user: UserModel) -> UserSummary:
    return UserSummary.model_validate(user)


def _to_me_response(user: UserModel) -> MeResponse:
    return MeResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[AuthRepository, Depends(get_db)],
) -> TokenResponse:
    return auth_service.login(
        db,
        email=payload.email,
        password=payload.password,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )


@router.post("/logout", response_model=MessageResponse)
def logout() -> MessageResponse:
    return auth_service.logout()


@router.get("/me", response_model=MeResponse)
def get_me(current_user: Annotated[UserModel, Depends(get_current_user)]) -> MeResponse:
    return _to_me_response(current_user)


@router.patch("/me", response_model=MeResponse)
def update_me(
    payload: UserUpdateRequest,
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AuthRepository, Depends(get_db)],
) -> MeResponse:
    updated_user = user_service.update_user_profile(db, current_user, payload)
    return _to_me_response(updated_user)


@router.patch("/me/password", response_model=MessageResponse)
def change_my_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AuthRepository, Depends(get_db)],
) -> MessageResponse:
    return auth_service.change_password(
        db,
        current_user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Annotated[AuthRepository, Depends(get_db)],
) -> MessageResponse:
    return auth_service.forgot_password(
        db,
        email=payload.email,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Annotated[AuthRepository, Depends(get_db)],
) -> MessageResponse:
    return auth_service.reset_password(
        db,
        token=payload.token,
        new_password=payload.new_password,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )


@router.post("/users/{user_id}/verify", response_model=UserSummary)
def verify_user(
    user_id: str,
    db: Annotated[AuthRepository, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_role(UserRole.MANAGER))],
) -> UserSummary:
    target = user_service.ensure_user_exists(db, user_id)
    updated = user_service.verify_user(db, target)
    user_service.write_audit_event(
        db,
        event_type="user_verified",
        actor_user_id=current_user.id,
        target_user_id=target.id,
    )
    return _to_user_summary(updated)


@router.post("/users/{user_id}/clear-suspicious", response_model=UserSummary)
def clear_suspicious_flag(
    user_id: str,
    db: Annotated[AuthRepository, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_role(UserRole.MANAGER))],
) -> UserSummary:
    target = user_service.ensure_user_exists(db, user_id)
    updated = user_service.clear_suspicious_flag(db, target)
    user_service.write_audit_event(
        db,
        event_type="suspicious_flag_cleared",
        actor_user_id=current_user.id,
        target_user_id=target.id,
    )
    return _to_user_summary(updated)


@router.patch("/users/{user_id}/role", response_model=UserSummary)
def update_user_role(
    user_id: str,
    payload: UpdateUserRoleRequest,
    db: Annotated[AuthRepository, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(require_role(UserRole.SUPERUSER))],
) -> UserSummary:
    target = user_service.ensure_user_exists(db, user_id)
    updated = user_service.update_role(db, target, payload.role)
    user_service.write_audit_event(
        db,
        event_type="user_role_updated",
        actor_user_id=current_user.id,
        target_user_id=target.id,
        metadata={"role": payload.role.value},
    )
    return _to_user_summary(updated)
