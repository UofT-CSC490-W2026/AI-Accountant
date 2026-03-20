from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.enums import AccountCreator, AccountSubType, AccountType

if TYPE_CHECKING:
    from app.models.journal import JournalEntryLine
    from app.models.organization import Organization


class ChartOfAccounts(AuditMixin, Base):
    __tablename__ = "chart_of_accounts"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    account_number: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(255))
    account_type: Mapped[AccountType]
    sub_type: Mapped[AccountSubType | None]
    parent_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chart_of_accounts.id")
    )
    currency: Mapped[str] = mapped_column(String(3), default="CAD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[AccountCreator] = mapped_column(default=AccountCreator.USER)
    auto_created: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── relationships ──────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="accounts"
    )
    parent_account: Mapped["ChartOfAccounts | None"] = relationship(
        back_populates="sub_accounts", remote_side="ChartOfAccounts.id"
    )
    sub_accounts: Mapped[list["ChartOfAccounts"]] = relationship(
        back_populates="parent_account"
    )
    journal_entry_lines: Mapped[list["JournalEntryLine"]] = relationship(
        "JournalEntryLine", back_populates="account"
    )
