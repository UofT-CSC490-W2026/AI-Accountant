from __future__ import annotations

from backend.schema.auth import MessageResponse


def logout() -> MessageResponse:
    return MessageResponse(message="Log out through the Cognito client flow. Backend tokens are verified, not issued.")
