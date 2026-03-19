from __future__ import annotations

from typing import Protocol

from backend.models.user_model import AuditEvent, UserModel


class AuthRepository(Protocol):
    def add_user(self, user: UserModel) -> UserModel:
        ...

    def get_user_by_id(self, user_id: str) -> UserModel | None:
        ...

    def get_user_by_email(self, email: str) -> UserModel | None:
        ...

    def get_user_by_reset_token_hash(self, reset_token_hash: str) -> UserModel | None:
        ...

    def save_user(self, user: UserModel) -> UserModel:
        ...

    def add_audit_event(self, event: AuditEvent) -> AuditEvent:
        ...

    def list_audit_events(self) -> list[AuditEvent]:
        ...


Database = AuthRepository
