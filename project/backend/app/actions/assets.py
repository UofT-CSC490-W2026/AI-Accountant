from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.errors import NotFoundError, ValidationError
from app.models.asset import Asset, CCAScheduleEntry
from app.models.enums import AssetStatus


# ── CCA Class rates (§1.2) ──────────────────────────────────────

CCA_CLASSES: dict[str, dict] = {
    "1":    {"rate": Decimal("0.04"),  "description": "Buildings acquired after 1987"},
    "8":    {"rate": Decimal("0.20"),  "description": "Furniture, equipment, machinery"},
    "10":   {"rate": Decimal("0.30"),  "description": "Vehicles, automotive equipment"},
    "10.1": {"rate": Decimal("0.30"),  "description": "Passenger vehicles > $37,000"},
    "12":   {"rate": Decimal("1.00"),  "description": "Tools, medical instruments < $500"},
    "14":   {"rate": None,             "description": "Patents, franchises, licences (straight-line)"},
    "50":   {"rate": Decimal("0.55"),  "description": "Computer hardware & software"},
}


# ── DAO ─────────────────────────────────────────────────────────


class AssetDAO:
    def __init__(self, db: Session):
        self._db = db

    def create(
        self,
        *,
        org_id: uuid.UUID,
        name: str,
        acquisition_date: date,
        acquisition_cost: Decimal,
        description: str | None = None,
        cca_class: str | None = None,
        cca_rate: Decimal | None = None,
        book_depreciation_method: str | None = None,
        book_useful_life: int | None = None,
    ) -> Asset:
        if cca_class is not None and cca_rate is None:
            cls = CCA_CLASSES.get(cca_class)
            if cls is not None and cls["rate"] is not None:
                cca_rate = cls["rate"]

        asset = Asset(
            org_id=org_id,
            name=name,
            description=description,
            acquisition_date=acquisition_date,
            acquisition_cost=acquisition_cost,
            cca_class=cca_class,
            cca_rate=cca_rate,
            book_depreciation_method=book_depreciation_method,
            book_useful_life=book_useful_life,
        )
        self._db.add(asset)
        self._db.flush()
        return asset

    def get(self, asset_id: uuid.UUID) -> Asset:
        asset = self._db.get(Asset, asset_id)
        if asset is None:
            raise NotFoundError(f"asset {asset_id} not found")
        return asset

    def list(self, *, org_id: uuid.UUID, status: AssetStatus | None = None) -> list[Asset]:
        stmt = select(Asset).where(Asset.org_id == org_id)
        if status is not None:
            stmt = stmt.where(Asset.status == status)
        stmt = stmt.order_by(Asset.acquisition_date.desc())
        return list(self._db.execute(stmt).scalars().all())

    def dispose(
        self,
        *,
        asset_id: uuid.UUID,
        disposition_date: date,
        disposition_proceeds: Decimal,
    ) -> Asset:
        """Mark an asset as disposed."""
        asset = self._db.get(Asset, asset_id)
        if asset is None:
            raise NotFoundError(f"asset {asset_id} not found")
        if asset.status == AssetStatus.DISPOSED:
            raise ValidationError("asset is already disposed")
        asset.disposition_date = disposition_date
        asset.disposition_proceeds = disposition_proceeds
        asset.status = AssetStatus.DISPOSED
        self._db.flush()
        return asset

    def calculate_annual_cca(
        self,
        *,
        asset_id: uuid.UUID,
        fiscal_year: int,
        journal_entry_id: uuid.UUID | None = None,
    ) -> CCAScheduleEntry:
        """Compute the CCA for a single asset for a fiscal year."""
        asset = self.get(asset_id)

        if asset.cca_rate is None:
            raise ValidationError(f"asset {asset_id} has no CCA rate (class {asset.cca_class})")

        prev_stmt = (
            select(CCAScheduleEntry)
            .where(
                CCAScheduleEntry.asset_id == asset_id,
                CCAScheduleEntry.fiscal_year == fiscal_year - 1,
            )
            .limit(1)
        )
        prev = self._db.execute(prev_stmt).scalar_one_or_none()
        ucc_opening = prev.ucc_closing if prev is not None else Decimal("0")

        is_acquisition_year = asset.acquisition_date.year == fiscal_year
        additions = asset.acquisition_cost if is_acquisition_year else Decimal("0")

        is_disposition_year = (
            asset.disposition_date is not None
            and asset.disposition_date.year == fiscal_year
        )
        dispositions = asset.disposition_proceeds or Decimal("0") if is_disposition_year else Decimal("0")

        cca_base = ucc_opening + additions - dispositions

        half_year = False
        if is_acquisition_year:
            cca_base = additions * Decimal("0.5")
            half_year = True

        aiip = False
        if is_acquisition_year and asset.acquisition_date.year >= 2019:
            cca_base = additions
            aiip = True
            half_year = False

        cca_amount = (cca_base * asset.cca_rate).quantize(Decimal("0.01"))
        ucc_closing = ucc_opening + additions - dispositions - cca_amount

        entry = CCAScheduleEntry(
            asset_id=asset_id,
            fiscal_year=fiscal_year,
            ucc_opening=ucc_opening,
            additions=additions,
            dispositions=dispositions,
            cca_claimed=cca_amount,
            ucc_closing=ucc_closing,
            half_year_rule_applied=half_year,
            aiip_applied=aiip,
            journal_entry_id=journal_entry_id,
        )
        self._db.add(entry)
        self._db.flush()
        return entry

    def create_cca_schedule_entry(
        self,
        *,
        asset_id: uuid.UUID,
        fiscal_year: int,
        ucc_opening: Decimal,
        additions: Decimal,
        dispositions: Decimal,
        cca_claimed: Decimal,
        ucc_closing: Decimal,
        half_year_rule_applied: bool = False,
        aiip_applied: bool = False,
        journal_entry_id: uuid.UUID | None = None,
    ) -> CCAScheduleEntry:
        """Manual CCA schedule entry (for overrides / corrections)."""
        self.get(asset_id)  # validates existence

        entry = CCAScheduleEntry(
            asset_id=asset_id,
            fiscal_year=fiscal_year,
            ucc_opening=ucc_opening,
            additions=additions,
            dispositions=dispositions,
            cca_claimed=cca_claimed,
            ucc_closing=ucc_closing,
            half_year_rule_applied=half_year_rule_applied,
            aiip_applied=aiip_applied,
            journal_entry_id=journal_entry_id,
        )
        self._db.add(entry)
        self._db.flush()
        return entry
