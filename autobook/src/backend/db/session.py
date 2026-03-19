from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy
from threading import RLock
from uuid import uuid4

from backend.config import get_settings
from backend.db.base import AuthRepository
from backend.models.user_model import AuditEvent, UserModel
from backend.schema.user import UserRole


class InMemoryAuthDB:
    def __init__(self) -> None:
        self._lock = RLock()
        self._users_by_id: dict[str, UserModel] = {}
        self._user_ids_by_email: dict[str, str] = {}
        self._audit_events: list[AuditEvent] = []

    def clear(self) -> None:
        with self._lock:
            self._users_by_id.clear()
            self._user_ids_by_email.clear()
            self._audit_events.clear()

    def add_user(self, user: UserModel) -> UserModel:
        with self._lock:
            self._users_by_id[user.id] = deepcopy(user)
            self._user_ids_by_email[user.email] = user.id
            return deepcopy(self._users_by_id[user.id])

    def get_user_by_id(self, user_id: str) -> UserModel | None:
        with self._lock:
            user = self._users_by_id.get(user_id)
            return deepcopy(user) if user else None

    def get_user_by_email(self, email: str) -> UserModel | None:
        with self._lock:
            user_id = self._user_ids_by_email.get(email)
            if not user_id:
                return None
            user = self._users_by_id.get(user_id)
            return deepcopy(user) if user else None

    def get_user_by_reset_token_hash(self, reset_token_hash: str) -> UserModel | None:
        with self._lock:
            for user in self._users_by_id.values():
                if user.reset_token_hash == reset_token_hash:
                    return deepcopy(user)
        return None

    def save_user(self, user: UserModel) -> UserModel:
        with self._lock:
            previous = self._users_by_id.get(user.id)
            if previous and previous.email != user.email:
                self._user_ids_by_email.pop(previous.email, None)
            self._users_by_id[user.id] = deepcopy(user)
            self._user_ids_by_email[user.email] = user.id
            return deepcopy(self._users_by_id[user.id])

    def list_users(self) -> list[UserModel]:
        with self._lock:
            return [deepcopy(user) for user in self._users_by_id.values()]

    def add_audit_event(self, event: AuditEvent) -> AuditEvent:
        with self._lock:
            self._audit_events.append(deepcopy(event))
            return deepcopy(event)

    def list_audit_events(self) -> list[AuditEvent]:
        with self._lock:
            return [deepcopy(event) for event in self._audit_events]


_db: InMemoryAuthDB | None = None


def _seed_users(db: AuthRepository) -> None:
    from backend.services.user.password_service import hash_password

    settings = get_settings()
    seeds = [
        (
            settings.default_regular_email.strip().lower(),
            settings.default_regular_password,
            UserRole.REGULAR,
            "Default User",
        ),
        (
            settings.default_manager_email.strip().lower(),
            settings.default_manager_password,
            UserRole.MANAGER,
            "Default Manager",
        ),
        (
            settings.default_superuser_email.strip().lower(),
            settings.default_superuser_password,
            UserRole.SUPERUSER,
            "Default Superuser",
        ),
    ]
    for email, password, role, full_name in seeds:
        user = UserModel(
            id=str(uuid4()),
            email=email,
            password_hash=hash_password(password),
            role=role,
            full_name=full_name,
            is_verified=True,
        )
        db.add_user(user)


def get_auth_db() -> AuthRepository:
    global _db
    if _db is None:
        _db = InMemoryAuthDB()
        _seed_users(_db)
    return _db


def get_db() -> Generator[AuthRepository, None, None]:
    yield get_auth_db()


def reset_auth_db_for_tests() -> InMemoryAuthDB:
    global _db
    _db = InMemoryAuthDB()
    _seed_users(_db)
    return _db
