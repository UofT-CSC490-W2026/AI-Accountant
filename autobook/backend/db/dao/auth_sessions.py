from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.auth_session import AuthSession
from db.models.user import User


class AuthSessionDAO:
    @staticmethod
    def fingerprint(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def record_token(
        db: Session,
        user: User,
        cognito_sub: str,
        token: str,
        token_use: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> AuthSession:
        fingerprint = AuthSessionDAO.fingerprint(token)
        stmt = select(AuthSession).where(AuthSession.token_fingerprint == fingerprint)
        auth_session = db.execute(stmt).scalar_one_or_none()
        now = datetime.now(timezone.utc)

        if auth_session is None:
            auth_session = AuthSession(
                user_id=user.id,
                cognito_sub=cognito_sub,
                token_fingerprint=fingerprint,
                token_use=token_use,
                issued_at=issued_at,
                expires_at=expires_at,
                last_seen_at=now,
            )
        else:
            auth_session.user_id = user.id
            auth_session.cognito_sub = cognito_sub
            auth_session.token_use = token_use
            auth_session.issued_at = issued_at
            auth_session.expires_at = expires_at
            auth_session.last_seen_at = now
            auth_session.revoked_at = None

        user.last_authenticated_at = now
        db.add(auth_session)
        db.add(user)
        db.flush()
        return auth_session
