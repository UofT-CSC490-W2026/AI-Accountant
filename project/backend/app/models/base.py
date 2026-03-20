import uuid
from datetime import datetime

from sqlalchemy import Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Reusable Numeric type for monetary columns: up to 999_999_999_999_999.9999
MONEY = Numeric(19, 4)


class Base(DeclarativeBase):
    pass


class AuditMixin:
    """Adds a UUID primary key and audit timestamps to every model."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
