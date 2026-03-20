from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.errors import NotFoundError
from app.models.enums import IntegrationPlatform, IntegrationStatus
from app.models.integration import IntegrationConnection


def create_integration_connection(
    db: Session,
    *,
    org_id: uuid.UUID,
    platform: IntegrationPlatform,
    credentials: str | None = None,
    status: IntegrationStatus = IntegrationStatus.INACTIVE,
    last_sync: datetime | None = None,
    webhook_secret: str | None = None,
    config: dict | None = None,
) -> IntegrationConnection:
    conn = IntegrationConnection(
        org_id=org_id,
        platform=platform,
        credentials=credentials,
        status=status,
        last_sync=last_sync,
        webhook_secret=webhook_secret,
        config=config,
    )
    db.add(conn)
    db.flush()
    return conn


def update_integration_status(
    db: Session,
    *,
    connection_id: uuid.UUID,
    status: IntegrationStatus,
    last_sync: datetime | None = None,
) -> IntegrationConnection:
    conn = db.get(IntegrationConnection, connection_id)
    if conn is None:
        raise NotFoundError(f"integration connection {connection_id} not found")
    conn.status = status
    if last_sync is not None:
        conn.last_sync = last_sync
    db.flush()
    return conn


def list_integration_connections(
    db: Session, *, org_id: uuid.UUID
) -> list[IntegrationConnection]:
    stmt = (
        select(IntegrationConnection)
        .where(IntegrationConnection.org_id == org_id)
        .order_by(IntegrationConnection.platform)
    )
    return list(db.execute(stmt).scalars().all())
