from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ChartOfAccounts(Base):
    __tablename__ = "chart_of_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "account_code", name="uq_chart_of_accounts_user_code"),
        CheckConstraint(
            "account_type IN ('asset', 'liability', 'equity', 'revenue', 'expense')",
            name="ck_chart_of_accounts_account_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_code: Mapped[str] = mapped_column(String(20))
    account_name: Mapped[str] = mapped_column(String(255))
    account_type: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    auto_created: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="chart_of_accounts")

    @property
    def account_number(self) -> str:
        return self.account_code

    @account_number.setter
    def account_number(self, value: str) -> None:
        self.account_code = value

    @property
    def name(self) -> str:
        return self.account_name

    @name.setter
    def name(self, value: str) -> None:
        self.account_name = value

    @property
    def org_id(self) -> uuid.UUID:
        return self.user_id
