from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import AuditMixin, Base
from db.models.enums import IntegrationPlatform, IntegrationStatus

if TYPE_CHECKING:
    from db.models.organization import Organization


class IntegrationConnection(AuditMixin, Base):
    __tablename__ = "integration_connections"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[IntegrationPlatform]
    credentials: Mapped[str | None] = mapped_column(Text)
    status: Mapped[IntegrationStatus] = mapped_column(
        default=IntegrationStatus.INACTIVE
    )
    last_sync: Mapped[datetime | None]
    webhook_secret: Mapped[str | None] = mapped_column(String(255))
    config: Mapped[dict | None] = mapped_column(JSONB)

    # ── relationships ──────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="integration_connections"
    )
